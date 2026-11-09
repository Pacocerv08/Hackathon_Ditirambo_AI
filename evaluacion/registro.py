"""Registro de modelos: nombre del candidato -> estimador de scikit-learn sin entrenar.

Clasificación: 'referencia', 'logistica', 'arbol' y 'lightgbm'. Series: todavía ninguno.
Importar este módulo no lee datos ni entrena nada.
"""
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from comun.contratos import Candidato, Hiperparametro, Problema


def _real(valor) -> float:
    return float(valor)


def _entero(valor) -> int:
    x = float(valor)
    if not x.is_integer():
        raise ValueError("no es entero")
    return int(x)


# nombre -> (conversión del valor del contrato (float | int | str), mínimo, máximo, mínimo exclusivo)
HIPERPARAMETROS_PERMITIDOS = {
    "referencia": {},
    "logistica": {"C": (_real, 0.0, 1e6, True)},
    "arbol": {"max_depth": (_entero, 1, 50, False),
              "min_samples_leaf": (_entero, 1, 1000, False)},
    "lightgbm": {"n_estimators": (_entero, 1, 2000, False),
                 "learning_rate": (_real, 0.0, 1.0, True),
                 "num_leaves": (_entero, 2, 1024, False),
                 "min_child_samples": (_entero, 1, 1000, False)},
}
IMPLEMENTADOS = {"clasificacion": {"referencia", "logistica", "arbol", "lightgbm"}, "serie": set()}


class ErrorRegistro(ValueError):
    """El candidato pide algo que el registro no puede construir. El evaluador lo vuelve Resultado.error."""


class Referencia(ClassifierMixin, BaseEstimator):
    """Nunca actuar: la probabilidad de la clase positiva es siempre 0."""

    def fit(self, X, y):
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        p = np.zeros((len(X), 2))
        p[:, 0] = 1.0
        return p

    def predict(self, X):
        return np.zeros(len(X), dtype=int)


def _n_jobs_1(estimador):
    """Pone n_jobs=1 en el estimador y en todo lo anidado que lo acepte (evaluar corre en 3 hilos).

    Excepción: LogisticRegression, donde n_jobs no tiene efecto desde sklearn 1.8 (siempre usa un
    hilo con lbfgs) y ponerlo solo produce un aviso de deprecación en cada ajuste.
    """
    todos = estimador.get_params(deep=True)
    params = {}
    for nombre in todos:
        if nombre != "n_jobs" and not nombre.endswith("__n_jobs"):
            continue
        dueno = todos.get(nombre.rsplit("__", 1)[0]) if "__" in nombre else estimador
        if not isinstance(dueno, LogisticRegression):
            params[nombre] = 1
    return estimador.set_params(**params)


def _leer_hiperparametros(modelo: str, hiperparametros: list[Hiperparametro]):
    """Devuelve (valores convertidos, nombres ignorados). Un valor que no se puede convertir es error."""
    permitidos = HIPERPARAMETROS_PERMITIDOS[modelo]
    valores, ignorados = {}, []
    for h in hiperparametros:
        if h.nombre not in permitidos:
            ignorados.append(f"{h.nombre} (no permitido para {modelo})")
            continue
        if h.nombre in valores:
            ignorados.append(f"{h.nombre} (repetido, se usa el primero)")
            continue
        convertir, minimo, maximo, exclusivo = permitidos[h.nombre]
        tipo = "entero" if convertir is _entero else "número"
        try:
            valor = convertir(h.valor)
        except (TypeError, ValueError, OverflowError):
            raise ErrorRegistro(f"{modelo}: {h.nombre}={h.valor!r} no se puede convertir a {tipo}")
        fuera = (not np.isfinite(valor) or valor > maximo
                 or (valor <= minimo if exclusivo else valor < minimo))
        if fuera:
            rango = f"{'(' if exclusivo else '['}{minimo}, {maximo}]"
            raise ErrorRegistro(f"{modelo}: {h.nombre} debe ser un {tipo} en {rango}, llegó {h.valor!r}")
        valores[h.nombre] = valor
    return valores, ignorados


def construir_modelo(problema: Problema, candidato: Candidato):
    """Devuelve (estimador sin entrenar, hiperparámetros ignorados).

    - referencia: nunca actúa, sin calibrar.
    - logistica, arbol, lightgbm: imputación + (escalado solo en logistica) + one-hot + modelo dentro
      de un Pipeline, calibrado con CalibratedClassifierCV(cv=3). Semilla del problema; n_jobs=1.
    Lanza ErrorRegistro con un mensaje claro si el modelo no aplica o no está implementado.
    """
    modelo, tarea = candidato.modelo, problema.tipo_tarea
    if modelo not in IMPLEMENTADOS.get(tarea, set()):
        if tarea == "serie" and modelo == "logistica":
            raise ErrorRegistro("logistica no aplica a series de tiempo")
        disponibles = ", ".join(sorted(IMPLEMENTADOS.get(tarea, set()))) or "ninguno todavía"
        raise ErrorRegistro(f"modelo '{modelo}' no implementado para {tarea}; disponibles: {disponibles}")

    valores, ignorados = _leer_hiperparametros(modelo, candidato.hiperparametros)
    if modelo == "referencia":
        return Referencia(), ignorados

    semilla = problema.particion.semilla
    if modelo == "logistica":
        estimador = LogisticRegression(max_iter=1000, C=valores.get("C", 1.0), random_state=semilla)
    elif modelo == "arbol":
        estimador = DecisionTreeClassifier(random_state=semilla, **valores)
    else:  # lightgbm
        estimador = LGBMClassifier(verbose=-1, random_state=semilla, n_jobs=1, **valores)

    # Imputación determinista (mediana / "faltante"): TotalCharges de churn trae vacíos.
    pasos_numericos = [("imputar", SimpleImputer(strategy="median"))]
    if modelo == "logistica":
        pasos_numericos.append(("escalar", StandardScaler()))
    preparacion = ColumnTransformer([
        ("numericas", Pipeline(pasos_numericos), make_column_selector(dtype_include=np.number)),
        ("categoricas", Pipeline([
            ("imputar", SimpleImputer(strategy="constant", fill_value="faltante")),
            ("one_hot", OneHotEncoder(handle_unknown="ignore")),
        ]), make_column_selector(dtype_exclude=np.number)),
    ])
    pipeline = Pipeline([("preparacion", preparacion), ("modelo", estimador)])
    calibrado = CalibratedClassifierCV(estimator=pipeline, cv=3)
    return _n_jobs_1(calibrado), ignorados
