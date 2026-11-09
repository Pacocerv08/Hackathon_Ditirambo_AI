"""Verificaciones del evaluador. Uso, desde la raíz:

    python -m evaluacion.pruebas

Imprime una tabla y un resumen de verificaciones. Termina con código 1 si alguna falla.
Si algo falla, se reportan los números tal cual: aquí no se ajusta ningún umbral ni configuración.
"""
import sys
from concurrent.futures import ThreadPoolExecutor

from comun import config
from comun.contratos import Candidato, Capacidades, Hiperparametro
from comun.falsos import problema_falso
from datos.problemas import cargar_datos, cargar_problema
from evaluacion import evaluador
from evaluacion.evaluador import MODOS, evaluar, particion

PROBLEMA = "credito_a"
LIMITE_SEGUNDOS_PRUEBA = 10.0

SIN_LECCION = Capacidades()
CON_UMBRAL = Capacidades(umbral_por_costos=True)
REFERENCIA = Candidato(justificacion="nunca actuar", modelo="referencia")
LOGISTICA = Candidato(justificacion="modelo lineal calibrado", modelo="logistica")

verificaciones: list[tuple[str, bool, str]] = []
tiempos: list[tuple[str, float]] = []


def verificar(nombre: str, ok: bool, detalle: str = "") -> None:
    verificaciones.append((nombre, bool(ok), detalle))


def correr(etiqueta: str, *args, **kwargs):
    r = evaluar(*args, **kwargs)
    tiempos.append((etiqueta, r.segundos))
    return r


def prueba_particion(problema) -> None:
    df = cargar_datos(problema)
    pedazos = particion(problema, df)
    ent, prod, pru = (set(pedazos[k]) for k in ("entrenamiento", "produccion", "prueba"))
    disjunta = not (ent & prod) and not (ent & pru) and not (prod & pru)
    completa = (ent | prod | pru) == set(df.index)
    tamanos = {k: len(v) for k, v in pedazos.items()}
    positivos = {k: round(float(df.loc[v, problema.objetivo].mean()), 3) for k, v in pedazos.items()}
    total = float(df[problema.objetivo].mean())
    pid = problema.id
    verificar(f"{pid}: partición disjunta", disjunta, f"tamaños {tamanos}")
    verificar(f"{pid}: partición completa", completa, f"{sum(tamanos.values())} de {len(df)} filas")
    verificar(f"{pid}: partición estratificada", all(abs(v - total) < 0.01 for v in positivos.values()),
              f"proporción positiva {positivos}, total {total:.3f}")
    # misma semilla, misma partición
    otra = particion(problema, df)
    verificar(f"{pid}: partición repetible", all(otra[k].equals(pedazos[k]) for k in pedazos), "")


def tabla_principal(problema) -> dict:
    filas = []
    resultados = {}
    for modo in MODOS:
        for nombre, cand, cap in [("referencia", REFERENCIA, SIN_LECCION),
                                  ("logistica, umbral 0.5", LOGISTICA, SIN_LECCION),
                                  ("logistica, umbral por costos", LOGISTICA, CON_UMBRAL)]:
            r = correr(f"{modo} / {nombre}", problema, cand, cap, modo)
            resultados[(modo, nombre)] = r
            filas.append((modo, nombre, r))

    print(f"\n=== {problema.id}: costo por modo (UMBRAL_RESUELTO = {config.UMBRAL_RESUELTO}) ===")
    print(f"{'modo':<11}{'candidato':<30}{'umbral':>7}{'costo':>8}{'ref':>7}{'relativo':>10}"
          f"{'resuelto':>10}{'tasa_fn':>9}{'tasa_fp':>9}{'auc':>7}{'seg':>7}  error")
    for modo, nombre, r in filas:
        m = r.metricas
        print(f"{modo:<11}{nombre:<30}{m.get('umbral', float('nan')):>7.3f}{r.costo:>8.1f}"
              f"{r.costo_referencia:>7.1f}{r.costo_relativo:>10.3f}{('sí' if r.resuelto else 'no'):>10}"
              f"{m.get('tasa_fn', float('nan')):>9.3f}{m.get('tasa_fp', float('nan')):>9.3f}"
              f"{m.get('auc', float('nan')):>7.3f}{r.segundos:>7.2f}  {r.error or ''}")

    for modo in MODOS:
        r = resultados[(modo, "referencia")]
        verificar(f"referencia costo_relativo == 1.0 ({modo})",
                  r.error is None and r.costo_relativo == 1.0, f"{r.costo_relativo}")
    for modo in MODOS:
        a, b = resultados[(modo, "logistica, umbral 0.5")], resultados[(modo, "logistica, umbral por costos")]
        verificar(f"umbral por costos < umbral 0.5 ({modo})",
                  a.error is None and b.error is None and b.costo < a.costo,
                  f"{a.costo:.1f} -> {b.costo:.1f}")

    a = resultados[("validacion", "logistica, umbral 0.5")]
    b = resultados[("validacion", "logistica, umbral por costos")]
    print(f"\n=== Lección de v0 en {problema.id}, validación (lo que ven los agentes) ===")
    for etiqueta, r in [("umbral 0.5 (sin lección)", a), ("umbral por costos (con lección)", b)]:
        print(f"  {etiqueta:<34} costo {r.costo:>6.1f}  costo relativo {r.costo_relativo:.3f}  "
              f"resuelto: {'sí' if r.resuelto else 'no'} (< {config.UMBRAL_RESUELTO})")
    return resultados


def prueba_determinismo(problema) -> None:
    r1 = correr("determinismo 1", problema, LOGISTICA, CON_UMBRAL, "validacion")
    r2 = correr("determinismo 2", problema, LOGISTICA, CON_UMBRAL, "validacion")
    verificar("dos llamadas idénticas: mismo costo", r1.costo == r2.costo, f"{r1.costo} vs {r2.costo}")
    verificar("dos llamadas idénticas: mismo candidato_id", r1.candidato_id == r2.candidato_id,
              f"{r1.candidato_id}")
    verificar("dos llamadas idénticas: mismos peores_casos", r1.peores_casos == r2.peores_casos,
              f"{len(r1.peores_casos)} casos")

    evaluador._cache_referencia.clear()   # que los hilos compitan por llenar la caché
    with ThreadPoolExecutor(max_workers=3) as hilos:
        rs = list(hilos.map(lambda _: evaluar(problema, LOGISTICA, CON_UMBRAL, "validacion"), range(3)))
    costos = [r.costo for r in rs]
    verificar("3 hilos a la vez: mismo costo", all(r.error is None for r in rs) and len(set(costos)) == 1
              and costos[0] == r1.costo, f"{costos}")
    tiempos.extend((f"hilo {i}", r.segundos) for i, r in enumerate(rs))


def pruebas_invalidas(problema) -> None:
    sin_archivo = problema.model_copy(update={"id": "credito_sin_archivo",
                                              "archivo": "datos/procesados/no_existe.parquet"})
    columnas = [c for c in cargar_datos(problema).columns if c != problema.objetivo]
    casos = [
        ("modelo que nunca existirá (xgboost)", problema,
         Candidato.model_construct(justificacion="x", modelo="xgboost", features=[],
                                   excluir_columnas=[], hiperparametros=[]), "validacion"),
        ("arbol en serie (no implementado todavía)", problema_falso("serie"),
         Candidato(justificacion="x", modelo="arbol"), "validacion"),
        ("num_leaves no entero", problema, Candidato(justificacion="x", modelo="lightgbm",
                                                    hiperparametros=[Hiperparametro(nombre="num_leaves", valor=15.5)]),
         "validacion"),
        ("max_depth fuera de rango", problema, Candidato(justificacion="x", modelo="arbol",
                                                        hiperparametros=[Hiperparametro(nombre="max_depth", valor=0)]),
         "validacion"),
        ("logistica en serie", problema_falso("serie"), LOGISTICA, "validacion"),
        ("C no numérico", problema, Candidato(justificacion="x", modelo="logistica",
                                             hiperparametros=[Hiperparametro(nombre="C", valor="mucho")]),
         "validacion"),
        ("excluir todas las columnas", problema,
         Candidato(justificacion="x", modelo="logistica", excluir_columnas=columnas), "validacion"),
        ("archivo inexistente", sin_archivo, LOGISTICA, "validacion"),
        ("modo inválido", problema, LOGISTICA, "entrenamiento"),
    ]
    print("\n=== Candidatos inválidos: deben devolver error, no excepción ===")
    for nombre, prob, cand, modo in casos:
        try:
            r = correr(f"inválido / {nombre}", prob, cand, SIN_LECCION, modo)
        except Exception as e:  # evaluar nunca debería llegar aquí
            verificar(f"inválido sin excepción: {nombre}", False, f"lanzó {type(e).__name__}: {e}")
            print(f"  {nombre:<38} LANZÓ EXCEPCIÓN {type(e).__name__}: {e}")
            continue
        ok = r.error is not None and r.costo_relativo == 999.0 and r.resuelto is False
        verificar(f"inválido devuelve error: {nombre}", ok, r.error or "sin error")
        print(f"  {nombre:<38} relativo={r.costo_relativo:.1f} resuelto={r.resuelto}  {r.error}")

    # hiperparámetro no permitido: se ignora con alerta y la evaluación sigue
    r = correr("hiperparámetro ignorado", problema,
               Candidato(justificacion="x", modelo="logistica",
                         hiperparametros=[Hiperparametro(nombre="max_depth", valor=3)]),
               SIN_LECCION, "validacion")
    verificar("hiperparámetro no permitido -> alerta, sin error",
              r.error is None and any("max_depth" in a for a in r.alertas), f"{r.alertas}")


PROBLEMA_FUGA = "churn_a"
COLUMNA_FUGA = "dias_desde_baja"
# Criterios fijados antes de ver resultados (plan aprobado). No se ajustan.
BRECHA_MINIMA_SIN_REVISAR = 0.30   # costo relativo producción/prueba - validación, sin revisar_fuga
BRECHA_MAXIMA_CON_REVISAR = 0.15   # |costo relativo producción/prueba - validación|, con revisar_fuga


def prueba_ruido(problema) -> None:
    df = cargar_datos(problema)
    pedazos = particion(problema, df)
    con_ruido = evaluador._ruido_en_columnas_futuras(problema, df, pedazos)
    ent = pedazos["entrenamiento"]
    otros = pedazos["produccion"].append(pedazos["prueba"])
    verificar("ruido: entrenamiento intacto",
              con_ruido.loc[ent, COLUMNA_FUGA].equals(df.loc[ent, COLUMNA_FUGA]), f"{len(ent)} filas")
    cambiadas = float((con_ruido.loc[otros, COLUMNA_FUGA] != df.loc[otros, COLUMNA_FUGA]).mean())
    verificar("ruido: producción y prueba reemplazadas", cambiadas > 0.2,
              f"{cambiadas:.0%} de {len(otros)} valores cambiaron")
    otras_columnas = [col for col in df.columns if col != COLUMNA_FUGA]
    verificar("ruido: las demás columnas no cambian", con_ruido[otras_columnas].equals(df[otras_columnas]), "")
    verificar("ruido: determinista", evaluador._ruido_en_columnas_futuras(problema, df, pedazos).equals(con_ruido), "")


def prueba_fuga(problema_credito, problema_churn) -> None:
    lgbm = Candidato(justificacion="gradient boosting", modelo="lightgbm")
    print(f"\n=== {problema_churn.id}, lightgbm con umbral por costos: fuga '{COLUMNA_FUGA}' ===")
    print(f"{'revisar_fuga':<14}{'modo':<12}{'costo':>8}{'ref':>8}{'relativo':>10}{'resuelto':>10}"
          f"{'max_auc_col':>13}{'seg':>7}  alertas / error")
    rel = {}
    for revisar in (False, True):
        cap = Capacidades(umbral_por_costos=True, revisar_fuga=revisar)
        for modo in MODOS:
            r = correr(f"{problema_churn.id} / lightgbm / revisar={revisar} / {modo}", problema_churn, lgbm, cap, modo)
            rel[(revisar, modo)] = r
            print(f"{('encendida' if revisar else 'apagada'):<14}{modo:<12}{r.costo:>8.1f}{r.costo_referencia:>8.1f}"
                  f"{r.costo_relativo:>10.3f}{('sí' if r.resuelto else 'no'):>10}"
                  f"{r.metricas.get('max_auc_columna', float('nan')):>13.3f}{r.segundos:>7.2f}  "
                  f"{r.error or '; '.join(r.alertas)}")

    sin = rel[(False, "validacion")]
    verificar("churn: aparece la alerta de fuga",
              any(a.startswith(f"posible_fuga: {COLUMNA_FUGA}") for a in sin.alertas), f"{sin.alertas}")
    for modo in ("produccion", "prueba"):
        brecha_sin = rel[(False, modo)].costo_relativo - rel[(False, "validacion")].costo_relativo
        brecha_con = rel[(True, modo)].costo_relativo - rel[(True, "validacion")].costo_relativo
        verificar(f"churn sin revisar_fuga: {modo} mucho peor que validación (>= {BRECHA_MINIMA_SIN_REVISAR})",
                  brecha_sin >= BRECHA_MINIMA_SIN_REVISAR,
                  f"{rel[(False, 'validacion')].costo_relativo:.3f} -> {rel[(False, modo)].costo_relativo:.3f}, "
                  f"brecha {brecha_sin:+.3f}")
        verificar(f"churn con revisar_fuga: brecha {modo} - validación pequeña (< {BRECHA_MAXIMA_CON_REVISAR})",
                  abs(brecha_con) < BRECHA_MAXIMA_CON_REVISAR,
                  f"{rel[(True, 'validacion')].costo_relativo:.3f} -> {rel[(True, modo)].costo_relativo:.3f}, "
                  f"brecha {brecha_con:+.3f}")

    r_cred = correr("credito / logistica / max_auc", problema_credito, LOGISTICA, SIN_LECCION, "validacion")
    verificar("crédito: max_auc_columna < 0.95", r_cred.metricas.get("max_auc_columna", 1.0) < 0.95,
              f"{r_cred.metricas.get('max_auc_columna')}")
    verificar("churn: max_auc_columna > 0.95", sin.metricas.get("max_auc_columna", 0.0) > 0.95,
              f"{sin.metricas.get('max_auc_columna')}")


def main() -> int:
    problema = cargar_problema(PROBLEMA)
    churn = cargar_problema(PROBLEMA_FUGA)
    prueba_particion(problema)
    prueba_particion(churn)
    tabla_principal(problema)
    prueba_determinismo(problema)
    prueba_ruido(churn)
    prueba_fuga(problema, churn)
    pruebas_invalidas(problema)

    lento = max(tiempos, key=lambda t: t[1])
    verificar(f"cada evaluación < {LIMITE_SEGUNDOS_PRUEBA:.0f} s",
              all(s < LIMITE_SEGUNDOS_PRUEBA for _, s in tiempos),
              f"{len(tiempos)} evaluaciones, la más lenta {lento[1]:.2f} s ({lento[0]})")

    print("\n=== Verificaciones ===")
    for nombre, ok, detalle in verificaciones:
        print(f"  [{'OK' if ok else 'FALLA'}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    fallas = sum(not ok for _, ok, _ in verificaciones)
    print(f"\n{len(verificaciones) - fallas} de {len(verificaciones)} verificaciones OK"
          + (f", {fallas} FALLAN" if fallas else ""))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
