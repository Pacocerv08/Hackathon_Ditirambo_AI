"""Catálogo de problemas: un JSON con forma de Problema por caso en datos/problemas/.

Uso, desde la raíz:
    python -m datos.problemas     # una línea por problema con filas, columnas y proporción positiva

Importar este módulo no lee archivos; todo se lee al llamar a las funciones.
"""
from pathlib import Path

import pandas as pd

from comun import config
from comun.contratos import Problema

RUTA_PROBLEMAS = Path(config.RUTA_PROBLEMAS)


def _leer_json(ruta: Path) -> Problema:
    return Problema.model_validate_json(ruta.read_text(encoding="utf-8"))


def listar_problemas(reservados: bool | None = False) -> list[str]:
    """ids de datos/problemas/. False: solo los de aprendizaje. True: solo reservados. None: todos."""
    ids = []
    for ruta in RUTA_PROBLEMAS.glob("*.json"):
        problema = _leer_json(ruta)
        if reservados is None or problema.reservado == reservados:
            ids.append(problema.id)
    return sorted(ids)


def cargar_problema(id: str) -> Problema:
    ruta = RUTA_PROBLEMAS / f"{id}.json"
    if not ruta.exists():
        validos = ", ".join(listar_problemas(reservados=None)) or "(ninguno)"
        raise ValueError(f"no existe el problema '{id}'. ids válidos: {validos}")
    problema = _leer_json(ruta)
    if problema.id != id:
        raise ValueError(f"{ruta} declara id '{problema.id}', se esperaba '{id}'")
    return problema


def cargar_datos(problema: Problema) -> pd.DataFrame:
    """Lee problema.archivo. Clasificación: objetivo ya en 0/1, con 1 = clase_positiva.
    Serie: ordenado por columna_fecha, una fila por día, sin huecos."""
    ruta = Path(problema.archivo)
    if not ruta.exists():
        raise FileNotFoundError(
            f"falta {ruta} para '{problema.id}': corre python -m datos.descargar "
            f"y python -m datos.preparar")
    df = pd.read_parquet(ruta)
    if problema.objetivo not in df.columns:
        raise ValueError(f"'{problema.id}': no existe la columna objetivo '{problema.objetivo}'")

    if problema.tipo_tarea == "clasificacion":
        valores = set(df[problema.objetivo].unique())
        if not valores <= {0, 1}:
            raise ValueError(f"'{problema.id}': el objetivo debe estar en 0/1, tiene {sorted(valores)}")
    else:
        df = df.sort_values(problema.columna_fecha).reset_index(drop=True)
    return df


def _resumen(problema: Problema, df: pd.DataFrame) -> str:
    variables = df.shape[1] - 1
    marca = " [reservado]" if problema.reservado else ""
    if problema.tipo_tarea == "clasificacion":
        positiva = df[problema.objetivo].mean()
        return (f"{problema.id:<12} clasificacion  filas={len(df):>5}  columnas={variables:>3} "
                f"(sin objetivo)  proporcion_positiva={positiva:.3f}{marca}")
    return (f"{problema.id:<12} serie          longitud={len(df):>5}  "
            f"columnas={variables:>3} (sin objetivo){marca}")


def main() -> None:
    ids = listar_problemas(reservados=None)
    print(f"{len(ids)} problemas: {', '.join(ids)}")
    for id in ids:
        try:
            problema = cargar_problema(id)
            print(_resumen(problema, cargar_datos(problema)))
        except Exception as e:  # una línea por problema aunque alguno falle
            print(f"{id:<12} ERROR: {e}")


if __name__ == "__main__":
    main()
