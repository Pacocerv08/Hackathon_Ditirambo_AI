"""Crudos -> datos/procesados/*.parquet.

Uso, desde la raíz (después de python -m datos.descargar):
    python -m datos.preparar

Solo transforma el objetivo. Las variables quedan con sus valores originales y el CSV crudo
no se modifica (se abre en modo lectura).
"""
from pathlib import Path

import pandas as pd

RUTA_CRUDOS = Path("datos/crudos")
RUTA_PROCESADOS = Path("datos/procesados")


def preparar_credito() -> Path:
    """credit-g: 'class' pasa de good/bad a 0/1, con 1 = 'bad' (la clase cuyo error es caro)."""
    origen = RUTA_CRUDOS / "credit-g.csv"
    destino = RUTA_PROCESADOS / "credito.parquet"
    if not origen.exists():
        raise SystemExit(f"falta {origen}: corre primero python -m datos.descargar")

    # keep_default_na=False: que pandas no convierta textos como "None" en faltantes.
    crudo = pd.read_csv(origen, keep_default_na=False, na_values=[""])
    df = crudo.copy()

    valores = set(df["class"].unique())
    if valores != {"good", "bad"}:
        raise SystemExit(f"valores inesperados en 'class': {valores}")
    df["class"] = (df["class"] == "bad").astype("int64")

    # Verificación: las variables son idénticas al crudo; solo cambió el objetivo.
    variables = [c for c in df.columns if c != "class"]
    pd.testing.assert_frame_equal(df[variables], crudo[variables])
    if df.isna().any().any():
        raise SystemExit("hay faltantes inesperados después de leer el CSV")

    RUTA_PROCESADOS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)

    categoricas = [c for c in variables if df[c].dtype == object]
    print(f"guardado {destino}: {len(df)} filas, {df.shape[1]} columnas, "
          f"{destino.stat().st_size / 1024:.1f} KB")
    print(f"objetivo 'class': {int(df['class'].sum())} unos ('bad') de {len(df)}")
    print(f"categóricas como texto ({len(categoricas)}): {', '.join(categoricas)}")
    print(f"numéricas ({len(variables) - len(categoricas)}): "
          f"{', '.join(c for c in variables if c not in categoricas)}")
    return destino


def main() -> None:
    preparar_credito()


if __name__ == "__main__":
    main()
