"""El juez: evaluar(problema, candidato, capacidades, modo, version) -> Resultado.

Sin LLM y determinista (semilla del problema). Nunca lanza excepción: si algo falla devuelve un
Resultado con `error` lleno, costo=999.0, costo_referencia=0.0, costo_relativo=999.0 y resuelto=False.
Las alertas salen solo de chequeos propios de este código (no se capturan avisos de librerías).

Primera entrega: solo clasificación. Importar este módulo no lee datos (lo importa comun/puertos.py).
"""
import hashlib
import importlib
import threading
import time

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, TimeSeriesSplit, cross_val_predict, train_test_split

from comun import config
from comun.contratos import Candidato, Capacidades, Modo, PeorCaso, Problema, Resultado
from datos.columnas_futuras import columnas_futuras
from datos.problemas import cargar_datos
from evaluacion import costos as c
from evaluacion.registro import construir_modelo
from evaluacion.variables import FILAS_DE_ARRANQUE, construir_variables, dias_especiales

MODOS = ("validacion", "produccion", "prueba")
N_PEORES_CASOS = 10
COSTO_ERROR = 999.0

_cache_referencia: dict[tuple, float] = {}
_candado_referencia = threading.Lock()


# ---------------------------------------------------------------- partición

def particion(problema: Problema, df: pd.DataFrame | None = None) -> dict[str, pd.Index]:
    """Índices (del DataFrame de cargar_datos) de los tres pedazos fijos de un problema de clasificación.

    prueba = proporcion_prueba del total; produccion = proporcion_produccion del resto;
    entrenamiento = lo que queda. Ambos cortes estratificados por el objetivo con la semilla del problema.
    """
    if df is None:
        df = cargar_datos(problema)
    p = problema.particion
    if problema.tipo_tarea == "serie":
        # prueba: después de fecha_corte_prueba; producción: último proporcion_produccion de lo
        # anterior; entrenamiento: lo que queda. Sin barajar: siempre el pasado antes del futuro.
        if p.fecha_corte_prueba is None:
            raise ValueError(f"'{problema.id}': una serie necesita particion.fecha_corte_prueba")
        fechas = pd.to_datetime(df[problema.columna_fecha])
        antes = df.index[fechas <= pd.Timestamp(p.fecha_corte_prueba)]
        n_prod = int(round(len(antes) * p.proporcion_produccion))
        return {"entrenamiento": antes[:len(antes) - n_prod], "produccion": antes[len(antes) - n_prod:],
                "prueba": df.index[fechas > pd.Timestamp(p.fecha_corte_prueba)]}
    y = df[problema.objetivo]
    resto, prueba = train_test_split(df.index, test_size=p.proporcion_prueba,
                                     stratify=y, random_state=p.semilla)
    entrenamiento, produccion = train_test_split(resto, test_size=p.proporcion_produccion,
                                                 stratify=y.loc[resto], random_state=p.semilla)
    return {"entrenamiento": pd.Index(entrenamiento), "produccion": pd.Index(produccion),
            "prueba": pd.Index(prueba)}


def _ruido_en_columnas_futuras(problema: Problema, df: pd.DataFrame,
                               pedazos: dict[str, pd.Index]) -> pd.DataFrame:
    """Intervención declarada del equipo: las columnas que solo existen después del hecho
    (datos/columnas_futuras.py, por problema.archivo) se reemplazan en producción y prueba por valores
    sacados al azar de su distribución en entrenamiento. Se ven igual pero no traen información del
    objetivo. Entrenamiento (y por tanto validación) queda intacto. Determinista con la semilla."""
    columnas = [col for col in columnas_futuras(problema.archivo) if col in df.columns]
    if not columnas:
        return df
    df = df.copy()
    rng = np.random.default_rng(problema.particion.semilla)
    filas = pedazos["produccion"].append(pedazos["prueba"])
    for col in columnas:
        valores = df.loc[pedazos["entrenamiento"], col].to_numpy()
        df.loc[filas, col] = rng.choice(valores, size=len(filas), replace=True)
    return df


# ---------------------------------------------------------------- referencia

def _llave_referencia(problema: Problema, modo: str) -> tuple:
    p = problema.particion
    k = problema.costos
    return (problema.id, p.semilla, modo, k.costo_fn, k.costo_faltante, k.costo_sobrante,
            p.folds, p.proporcion_prueba, p.proporcion_produccion, p.fecha_corte_prueba)


def costo_referencia(problema: Problema, modo: str, calcular) -> float:
    """calcular() da el costo de la referencia en el pedazo evaluado. Clasificación: nunca actuar
    (costo_fn * positivos, no depende del umbral). Serie: repetir el valor de hace 7 días.
    Se guarda en caché (con candado: evaluar corre desde varios hilos)."""
    llave = _llave_referencia(problema, modo)
    with _candado_referencia:
        if llave not in _cache_referencia:
            _cache_referencia[llave] = float(calcular())
        return _cache_referencia[llave]


# ---------------------------------------------------------------- punto de conexión de fuga

def _revisar_fuga(X: pd.DataFrame, y: pd.Series, capacidades: Capacidades,
                  alertas: list[str], metricas: dict[str, float]) -> list[str]:
    """Devuelve las columnas que hay que quitar por fuga. Lo implementa evaluacion/fuga.py, con

        fuga.revisar(X, y, quitar: bool) -> (columnas_a_quitar, alertas, metricas)

    calculado solo sobre el pedazo de entrenamiento. Mientras el módulo no exista, no se hace nada
    (y si la capacidad está encendida se avisa). Cualquier otro error se propaga al manejo normal.
    """
    try:
        # import_module (no "from evaluacion import fuga") para que la ausencia del módulo sea
        # ModuleNotFoundError con name="evaluacion.fuga" y se distinga de errores dentro de fuga.py.
        fuga = importlib.import_module("evaluacion.fuga")
    except ModuleNotFoundError as e:
        if e.name != "evaluacion.fuga":
            raise
        if capacidades.revisar_fuga:
            alertas.append("revisar_fuga no disponible todavía: no se revisó ninguna columna")
        return []
    quitar, alertas_fuga, metricas_fuga = fuga.revisar(X, y, quitar=capacidades.revisar_fuga)
    alertas.extend(alertas_fuga)
    metricas.update(metricas_fuga)
    return list(quitar)


# ---------------------------------------------------------------- evaluar

def _candidato_id(problema, candidato) -> str:
    try:
        texto = candidato.model_dump_json() + problema.id
    except Exception:
        texto = repr(candidato) + str(getattr(problema, "id", ""))
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:10]


def evaluar(problema: Problema, candidato: Candidato, capacidades: Capacidades,
            modo: Modo = "validacion", version: str = "v0") -> Resultado:
    """Nunca lanza excepción: si algo falla, devuelve Resultado con error lleno,
    costo_relativo=999.0 y resuelto=False."""
    inicio = time.perf_counter()
    alertas: list[str] = []
    problema_id = str(getattr(problema, "id", "desconocido"))
    modo_valido = modo if modo in MODOS else "validacion"
    candidato_id = "desconocido"
    try:
        candidato_id = _candidato_id(problema, candidato)
        if modo not in MODOS:
            raise ValueError(f"modo '{modo}' no válido; opciones: {', '.join(MODOS)}")
        # El juez no confía en sus entradas: las vuelve a validar contra el contrato.
        problema = Problema.model_validate(problema.model_dump())
        candidato = Candidato.model_validate(candidato.model_dump())
        capacidades = Capacidades.model_validate(capacidades.model_dump())

        evaluar_tarea = _evaluar_serie if problema.tipo_tarea == "serie" else _evaluar_clasificacion
        resultado = evaluar_tarea(problema, candidato, capacidades, modo, version, candidato_id, alertas)
    except Exception as e:
        resultado = Resultado(
            problema_id=problema_id, candidato_id=candidato_id, version=str(version), modo=modo_valido,
            costo=COSTO_ERROR, costo_referencia=0.0, costo_relativo=COSTO_ERROR, resuelto=False,
            alertas=alertas, error=f"{type(e).__name__}: {e}")

    resultado.segundos = round(time.perf_counter() - inicio, 3)
    if resultado.segundos > config.LIMITE_SEGUNDOS_CANDIDATO:
        resultado.alertas.append(
            f"tiempo excedido: {resultado.segundos:.1f} s > {config.LIMITE_SEGUNDOS_CANDIDATO} s")
    return resultado


def _evaluar_clasificacion(problema: Problema, candidato: Candidato, capacidades: Capacidades,
                           modo: str, version: str, candidato_id: str, alertas: list[str]) -> Resultado:
    if problema.tipo_tarea != "clasificacion":
        raise NotImplementedError("evaluación de series no implementada todavía")

    # El registro valida el modelo y los hiperparámetros antes de leer datos.
    estimador, ignorados = construir_modelo(problema, candidato)
    alertas.extend(f"hiperparametro ignorado: {h}" for h in ignorados)

    df = cargar_datos(problema)
    pedazos = particion(problema, df)
    df = _ruido_en_columnas_futuras(problema, df, pedazos)
    variables = [col for col in df.columns if col != problema.objetivo]
    for col in candidato.excluir_columnas:
        if col not in variables:
            alertas.append(f"columna a excluir no existe como variable: {col}")
    metricas: dict[str, float] = {}

    if modo == "validacion":
        filas_ajuste = pedazos["entrenamiento"]
        filas_evaluadas = pedazos["entrenamiento"]
    elif modo == "produccion":
        filas_ajuste = pedazos["entrenamiento"]
        filas_evaluadas = pedazos["produccion"]
    else:  # prueba
        filas_ajuste = pedazos["entrenamiento"].append(pedazos["produccion"])
        filas_evaluadas = pedazos["prueba"]

    y_ajuste = df.loc[filas_ajuste, problema.objetivo]
    # La revisión de fuga se calcula siempre sobre el pedazo de entrenamiento (nunca tiene ruido),
    # en los tres modos; lo detectado se quita del ajuste y de lo evaluado.
    entrenamiento = pedazos["entrenamiento"]
    por_fuga = _revisar_fuga(df.loc[entrenamiento, variables], df.loc[entrenamiento, problema.objetivo],
                             capacidades, alertas, metricas)
    usar = [col for col in variables if col not in set(candidato.excluir_columnas) | set(por_fuga)]
    if not usar:
        raise ValueError("no queda ninguna variable después de excluir columnas")

    y_eval = df.loc[filas_evaluadas, problema.objetivo].to_numpy()
    referencia = costo_referencia(problema, modo, lambda: c.costo_clasificacion(
        y_eval, np.zeros(len(y_eval)), c.UMBRAL_POR_DEFECTO, problema.costos.costo_fn, problema.costos.costo_fp))
    if referencia == 0:
        raise ValueError(f"el costo de la referencia es 0 en modo {modo} (no hay positivos en el "
                         f"pedazo evaluado); no se puede calcular el costo relativo")

    X_ajuste = df.loc[filas_ajuste, usar]
    if modo == "validacion":
        p = problema.particion
        cv = StratifiedKFold(n_splits=p.folds, shuffle=True, random_state=p.semilla)
        proba = cross_val_predict(estimador, X_ajuste, y_ajuste, cv=cv,
                                  method="predict_proba", n_jobs=1)[:, 1]
    else:
        estimador.fit(X_ajuste, y_ajuste)
        proba = estimador.predict_proba(df.loc[filas_evaluadas, usar])[:, 1]

    costos = problema.costos
    if capacidades.umbral_por_costos:
        umbral = c.umbral_optimo_por_costos(costos.costo_fn, costos.costo_fp)
    else:
        umbral = c.UMBRAL_POR_DEFECTO
    costo = c.costo_clasificacion(y_eval, proba, umbral, costos.costo_fn, costos.costo_fp)
    fn, fp = c.conteo_errores(y_eval, proba, umbral)
    positivos = int(y_eval.sum())
    negativos = len(y_eval) - positivos

    metricas["umbral"] = float(umbral)
    metricas["tasa_fn"] = fn / positivos
    metricas["tasa_fp"] = fp / negativos if negativos else 0.0
    if negativos:
        metricas["auc"] = float(roc_auc_score(y_eval, proba))
    else:
        alertas.append(f"sin negativos en modo {modo}: no se calcula auc")

    por_fila = c.costo_por_fila(y_eval, proba, umbral, costos.costo_fn, costos.costo_fp)
    # mayor costo primero; en empate, el índice de fila menor (orden reproducible)
    orden = np.lexsort((np.asarray(filas_evaluadas), -por_fila))[:N_PEORES_CASOS]
    peores = [PeorCaso(referencia=str(filas_evaluadas[i]), real=float(y_eval[i]),
                       predicho=float(proba[i]), costo=float(por_fila[i]))
              for i in orden if por_fila[i] > 0]

    relativo = costo / referencia
    return Resultado(
        problema_id=problema.id, candidato_id=candidato_id, version=str(version), modo=modo,
        costo=costo, costo_referencia=referencia, costo_relativo=relativo,
        resuelto=relativo < config.UMBRAL_RESUELTO, metricas=metricas, alertas=alertas,
        peores_casos=peores)


def _evaluar_serie(problema: Problema, candidato: Candidato, capacidades: Capacidades,
                   modo: str, version: str, candidato_id: str, alertas: list[str]) -> Resultado:
    modelo, ignorados = construir_modelo(problema, candidato)        # None = referencia (hace 7 días)
    alertas.extend(f"hiperparametro ignorado: {h}" for h in ignorados)
    if candidato.excluir_columnas:
        alertas.append("excluir_columnas no aplica a series: se ignora")
    df = cargar_datos(problema).reset_index(drop=True)
    y = df[problema.objetivo].astype(float)
    pronostico_referencia = y.shift(7)
    # Sin los primeros 28 días (rezagos incompletos), para todos los modelos por igual.
    pedazos = {k: v[v >= FILAS_DE_ARRANQUE] for k, v in particion(problema, df).items()}
    if modelo is None:
        if candidato.features:
            alertas.append("la referencia no usa variables: features ignoradas")
        X = None
    else:
        X, alertas_variables = construir_variables(problema, df, candidato.features, capacidades)
        alertas.extend(alertas_variables)

    def pronosticar(filas_ajuste, filas_pronostico) -> np.ndarray:
        if modelo is None:
            return pronostico_referencia.loc[filas_pronostico].to_numpy()
        m = clone(modelo).fit(X.loc[filas_ajuste], y.loc[filas_ajuste])
        return m.predict(X.loc[filas_pronostico])

    if modo == "validacion":        # TimeSeriesSplit: cada fold entrena solo con el pasado
        ent = pedazos["entrenamiento"]
        partes = [(ent[te], pronosticar(ent[tr], ent[te]))
                  for tr, te in TimeSeriesSplit(n_splits=3).split(ent)]
        filas = pd.Index(np.concatenate([f for f, _ in partes]))
        pred = np.concatenate([p for _, p in partes])
    elif modo == "produccion":
        filas = pedazos["produccion"]
        pred = pronosticar(pedazos["entrenamiento"], filas)
    else:  # prueba
        filas = pedazos["prueba"]
        pred = pronosticar(pedazos["entrenamiento"].append(pedazos["produccion"]), filas)
    pred = np.maximum(np.asarray(pred, dtype=float), 0.0)    # la demanda no puede ser negativa

    k = problema.costos
    real = y.loc[filas].to_numpy()
    referencia = costo_referencia(problema, modo, lambda: c.costo_serie(
        real, pronostico_referencia.loc[filas].to_numpy(), k.costo_faltante, k.costo_sobrante))
    if referencia == 0:
        raise ValueError(f"el costo de la referencia es 0 en modo {modo}; "
                         f"no se puede calcular el costo relativo")
    por_dia = c.costo_serie_por_dia(real, pred, k.costo_faltante, k.costo_sobrante)
    costo = float(por_dia.sum())
    especiales = dias_especiales(problema, df[problema.columna_fecha])[filas.to_numpy()]
    costo_especiales = float(por_dia[especiales].sum())
    metricas = {
        "mae": float(np.abs(pred - real).mean()),
        "sesgo": float((pred - real).mean()),
        "costo_dias_festivos": costo_especiales,                    # festivo, quincena o evento
        "porcion_costo_dias_festivos": costo_especiales / costo if costo > 0 else 0.0,
    }
    fechas = pd.to_datetime(df.loc[filas, problema.columna_fecha]).dt.strftime("%Y-%m-%d").to_numpy()
    orden = np.lexsort((fechas, -por_dia))[:N_PEORES_CASOS]       # mayor costo; empate: fecha anterior
    peores = [PeorCaso(referencia=str(fechas[i]), real=float(real[i]), predicho=float(pred[i]),
                       costo=float(por_dia[i]))
              for i in orden if por_dia[i] > 0]
    relativo = costo / referencia
    return Resultado(
        problema_id=problema.id, candidato_id=candidato_id, version=str(version), modo=modo,
        costo=costo, costo_referencia=referencia, costo_relativo=relativo,
        resuelto=relativo < config.UMBRAL_RESUELTO, metricas=metricas, alertas=alertas,
        peores_casos=peores)
