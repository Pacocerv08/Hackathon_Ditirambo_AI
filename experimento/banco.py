"""Corre el banco fijo de casos y compara versiones del sistema."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from comun import config, puertos
from memoria.versiones import cargar_version, version_sin


_COLUMNAS = [
    "version",
    "caso",
    "tipo",
    "reservado",
    "modelo",
    "costo",
    "costo_referencia",
    "costo_relativo",
    "resuelto",
    "segundos",
    "error",
]


def _fila_error(
    version_id: str,
    caso: str,
    error: str,
    segundos: float,
    tipo: str | None = None,
    reservado: bool | None = None,
    modelo: str | None = None,
) -> dict:
    return {
        "version": version_id,
        "caso": caso,
        "tipo": tipo,
        "reservado": reservado if reservado is not None else caso.endswith("_r"),
        "modelo": modelo,
        "costo": np.nan,
        "costo_referencia": np.nan,
        "costo_relativo": np.nan,
        "resuelto": False,
        "segundos": segundos,
        "error": error,
    }


def _correr_caso(version_id: str, caso: str) -> dict:
    inicio = time.perf_counter()
    tipo = None
    reservado = caso.endswith("_r")
    modelo = None
    try:
        version = cargar_version(version_id)
        from datos.problemas import cargar_problema

        problema = cargar_problema(caso)
        tipo = problema.tipo_tarea
        reservado = problema.reservado
        ciclo = puertos.resolver(
            problema,
            version,
            run_id=f"banco-{version.id}-{caso}",
        )
        if ciclo.mejor_candidato is None:
            return _fila_error(
                version_id,
                caso,
                "El ciclo no devolvió mejor_candidato",
                time.perf_counter() - inicio,
                tipo,
                reservado,
            )

        modelo = ciclo.mejor_candidato.modelo
        prueba = puertos.evaluar(
            problema,
            ciclo.mejor_candidato,
            version.capacidades,
            modo="prueba",
            version=version.id,
        )
        return {
            "version": version_id,
            "caso": caso,
            "tipo": tipo,
            "reservado": reservado,
            "modelo": modelo,
            "costo": prueba.costo,
            "costo_referencia": prueba.costo_referencia,
            "costo_relativo": prueba.costo_relativo,
            "resuelto": prueba.resuelto,
            "segundos": time.perf_counter() - inicio,
            "error": prueba.error,
        }
    except Exception as error:
        return _fila_error(
            version_id,
            caso,
            f"{type(error).__name__}: {error}",
            time.perf_counter() - inicio,
            tipo,
            reservado,
            modelo,
        )


def correr_banco(
    version_id: str,
    desactivar: list[str] | None = None,
    incluir_reservados: bool = True,
    procesos: int = 3,
) -> pd.DataFrame:
    falsos = [nombre for nombre, activo in puertos.PUERTOS_FALSOS.items() if activo]
    if falsos:
        raise RuntimeError(f"El banco requiere puertos reales; están falsos: {', '.join(falsos)}")

    version = cargar_version(version_id)
    for leccion_id in desactivar or []:
        version = version_sin(version.id, leccion_id)

    casos = list(config.BANCO)
    if incluir_reservados:
        from datos.problemas import listar_problemas

        casos.extend(listar_problemas(reservados=True))
    casos = list(dict.fromkeys(casos))

    filas = []
    with ProcessPoolExecutor(max_workers=procesos) as executor:
        trabajos = {
            executor.submit(_correr_caso, version.id, caso): caso
            for caso in casos
        }
        for trabajo in as_completed(trabajos):
            fila = trabajo.result()
            filas.append(fila)
            relativo = fila["costo_relativo"]
            relativo_texto = f"{relativo:.3f}" if pd.notna(relativo) else "NaN"
            print(
                f"{fila['caso']} modelo={fila['modelo']} "
                f"costo_relativo={relativo_texto} segundos={fila['segundos']:.3f}"
            )

    tabla = pd.DataFrame(filas, columns=_COLUMNAS).sort_values("caso").reset_index(drop=True)
    salidas = Path("salidas")
    salidas.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(salidas / f"banco_{version.id}.csv", index=False)
    return tabla


def mejora_entre_versiones(nueva: pd.DataFrame, anterior: pd.DataFrame) -> pd.DataFrame:
    previo = anterior[["caso", "reservado", "costo_relativo"]].rename(
        columns={"reservado": "reservado_anterior", "costo_relativo": "costo_anterior"}
    )
    actual = nueva[["caso", "reservado", "costo_relativo"]].rename(
        columns={"reservado": "reservado_nuevo", "costo_relativo": "costo_nuevo"}
    )
    comparacion = previo.merge(actual, on="caso", how="outer")
    comparacion["reservado"] = comparacion["reservado_nuevo"].combine_first(
        comparacion["reservado_anterior"]
    )
    comparacion["mejora"] = comparacion["costo_nuevo"] / comparacion[
        "costo_anterior"
    ].where(comparacion["costo_anterior"] != 0)
    return comparacion[["caso", "reservado", "costo_anterior", "costo_nuevo", "mejora"]].sort_values(
        "caso"
    ).reset_index(drop=True)


def graficar(dfs: list[pd.DataFrame], ruta: str = "salidas/banco.png") -> None:
    casos = sorted({caso for df in dfs for caso in df["caso"].dropna().tolist()})
    reservados = {}
    for df in dfs:
        for fila in df.itertuples(index=False):
            reservados[fila.caso] = bool(fila.reservado)
    etiquetas = [f"{caso} (r)" if reservados.get(caso, False) else caso for caso in casos]
    posiciones = np.arange(len(casos), dtype=float)
    cantidad = max(len(dfs), 1)
    ancho = 0.8 / cantidad

    figura, eje = plt.subplots(figsize=(max(8, len(casos) * 1.1), 5))
    for indice, df in enumerate(dfs):
        version = str(df["version"].iloc[0]) if not df.empty else f"versión {indice + 1}"
        valores_por_caso = dict(zip(df["caso"], df["costo_relativo"]))
        valores = [valores_por_caso.get(caso, np.nan) for caso in casos]
        desplazamiento = (indice - (cantidad - 1) / 2) * ancho
        eje.bar(posiciones + desplazamiento, valores, ancho, label=version)

    eje.axhline(
        config.UMBRAL_RESUELTO,
        linestyle=":",
        color="tab:green",
        label=f"umbral resuelto ({config.UMBRAL_RESUELTO})",
    )
    eje.axhline(1.0, linestyle=":", color="black", label="referencia")
    eje.set_xticks(posiciones, etiquetas)
    eje.set_ylabel("Costo relativo")
    eje.set_title("Costo relativo por caso y versión (menor es mejor)")
    eje.legend()
    figura.tight_layout()

    ruta_path = Path(ruta)
    ruta_path.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(ruta_path, dpi=150)
    plt.close(figura)


def main() -> None:
    parser = argparse.ArgumentParser(description="Corre y compara el banco de evaluación")
    parser.add_argument("versiones", nargs="+", help="Versiones a correr en orden")
    parser.add_argument("--desactivar", nargs="+", default=None, help="Lecciones a apagar en la última versión")
    parser.add_argument("--sin-reservados", action="store_true")
    parser.add_argument("--procesos", type=int, default=3)
    argumentos = parser.parse_args()

    tablas = []
    for indice, version_id in enumerate(argumentos.versiones):
        desactivar = (
            argumentos.desactivar
            if indice == len(argumentos.versiones) - 1
            else None
        )
        tabla = correr_banco(
            version_id,
            desactivar=desactivar,
            incluir_reservados=not argumentos.sin_reservados,
            procesos=argumentos.procesos,
        )
        tablas.append(tabla)
        print(tabla[["caso", "modelo", "costo_relativo", "resuelto"]].to_string(index=False))

        if indice > 0:
            anterior_id = str(tablas[indice - 1]["version"].iloc[0])
            nueva_id = str(tabla["version"].iloc[0])
            mejora = mejora_entre_versiones(tabla, tablas[indice - 1])
            print(mejora.to_string(index=False))
            Path("salidas").mkdir(parents=True, exist_ok=True)
            mejora.to_csv(
                Path("salidas") / f"mejora_{anterior_id}_{nueva_id}.csv",
                index=False,
            )

    graficar(tablas)


if __name__ == "__main__":
    main()
