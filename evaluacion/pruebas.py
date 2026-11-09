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
    verificar("partición disjunta", disjunta, f"tamaños {tamanos}")
    verificar("partición completa", completa, f"{sum(tamanos.values())} de {len(df)} filas")
    verificar("partición estratificada", all(abs(v - 0.3) < 0.01 for v in positivos.values()),
              f"proporción positiva {positivos}")
    # misma semilla, misma partición
    otra = particion(problema, df)
    verificar("partición repetible", all(otra[k].equals(pedazos[k]) for k in pedazos), "")


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
        ("arbol (no implementado todavía)", problema, Candidato(justificacion="x", modelo="arbol"), "validacion"),
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


def main() -> int:
    problema = cargar_problema(PROBLEMA)
    prueba_particion(problema)
    tabla_principal(problema)
    prueba_determinismo(problema)
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
