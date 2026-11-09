"""Crudos -> datos/procesados/*.parquet.

Uso, desde la raíz (después de python -m datos.descargar):
    python -m datos.preparar

Solo transforma el objetivo. Las variables quedan con sus valores originales y el CSV crudo
no se modifica (se abre en modo lectura).
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

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


FILAS_CHURN = 3000          # muestra estratificada: cada evaluación con lightgbm debe tardar segundos
SEMILLA_CHURN = 42
COLUMNA_FUGA_CHURN = "dias_desde_baja"
PROPORCION_RUIDO_FUGA = 0.02  # clientes sin baja que también traen un número (parece dato sucio normal)


def preparar_churn() -> Path:
    """Telco Customer Churn -> datos/procesados/churn.parquet.

    INTERVENCIONES DEL EQUIPO (se declaran en INTERVENCIONES.md y en la demo):
    1. Muestra estratificada de 3000 de 7043 clientes (semilla 42), para que cada evaluación tarde segundos.
    2. Columna con fuga controlada 'dias_desde_baja': 0 si no hubo baja; un entero 1-120 si la hubo;
       un 2% de los clientes sin baja también trae un número. Delata el objetivo a propósito, para
       probar si el sistema detecta la fuga.
    Limpieza de formato: se quitan las comillas simples del ARFF de OpenML y TotalCharges pasa a número
    (11 vacíos -> NaN). El objetivo 'Churn' pasa de Yes/No a 0/1 con 1 = baja.
    """
    origen = RUTA_CRUDOS / "telco-churn.csv"
    destino = RUTA_PROCESADOS / "churn.parquet"
    if not origen.exists():
        raise SystemExit(f"falta {origen}: corre primero python -m datos.descargar")

    crudo = pd.read_csv(origen, keep_default_na=False, na_values=[""])
    df = crudo.copy()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip().str.removeprefix("'").str.removesuffix("'").str.strip()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"].replace("", None), errors="coerce")

    valores = set(df["Churn"].unique())
    if valores != {"Yes", "No"}:
        raise SystemExit(f"valores inesperados en 'Churn': {valores}")
    df["Churn"] = (df["Churn"] == "Yes").astype("int64")

    # 1. muestra estratificada
    df, _ = train_test_split(df, train_size=FILAS_CHURN, stratify=df["Churn"], random_state=SEMILLA_CHURN)
    df = df.sort_index()
    filas_originales = df.index
    df = df.reset_index(drop=True)

    # 2. fuga controlada, colocada junto a 'tenure' para que parezca una columna más
    rng = np.random.default_rng(SEMILLA_CHURN)
    baja = df["Churn"].to_numpy() == 1
    dias = np.where(baja, rng.integers(1, 121, len(df)), 0)
    sucio = ~baja & (rng.random(len(df)) < PROPORCION_RUIDO_FUGA)
    dias[sucio] = rng.integers(1, 121, sucio.sum())
    df.insert(df.columns.get_loc("tenure") + 1, COLUMNA_FUGA_CHURN, dias.astype("int64"))

    # Verificación: fuera de la limpieza de formato, las variables originales no cambiaron.
    variables = [c for c in crudo.columns if c not in ("Churn", "TotalCharges")]
    esperado = crudo.loc[filas_originales, variables].reset_index(drop=True)
    for col in variables:
        if esperado[col].dtype == object:
            esperado[col] = esperado[col].str.strip().str.removeprefix("'").str.removesuffix("'").str.strip()
    pd.testing.assert_frame_equal(df[variables], esperado)

    RUTA_PROCESADOS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    print(f"guardado {destino}: {len(df)} filas, {df.shape[1]} columnas, "
          f"{destino.stat().st_size / 1024:.1f} KB")
    print(f"objetivo 'Churn': {int(df['Churn'].sum())} unos (baja) de {len(df)} "
          f"({df['Churn'].mean():.3f}; original {(crudo['Churn'] == 'Yes').mean():.3f})")
    print(f"fuga '{COLUMNA_FUGA_CHURN}': {int((df[COLUMNA_FUGA_CHURN] > 0).sum())} valores > 0 "
          f"({int(sucio.sum())} de clientes sin baja); faltantes TotalCharges: {int(df['TotalCharges'].isna().sum())}")
    return destino


def main() -> None:
    preparar_credito()
    preparar_churn()


if __name__ == "__main__":
    main()
