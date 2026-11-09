"""Baja los datasets crudos a datos/crudos/ (carpeta ignorada por git).

Uso, desde la raíz:
    python -m datos.descargar            # baja lo que falte
    python -m datos.descargar --forzar   # vuelve a bajar todo
"""
import argparse
from pathlib import Path

from sklearn.datasets import fetch_openml

RUTA_CRUDOS = Path("datos/crudos")


def descargar_credito(forzar: bool = False) -> Path:
    """German Credit (credit-g, OpenML versión 1): 1000 filas, 20 variables y la columna 'class'."""
    destino = RUTA_CRUDOS / "credit-g.csv"
    if destino.exists() and not forzar:
        print(f"ya existe {destino}, no se descarga")
        return destino
    RUTA_CRUDOS.mkdir(parents=True, exist_ok=True)
    datos = fetch_openml(
        "credit-g", version=1, as_frame=True, parser="auto",
        data_home=str(RUTA_CRUDOS / "cache_openml"),
    )
    datos.frame.to_csv(destino, index=False)
    print(f"guardado {destino}: {datos.frame.shape[0]} filas, {datos.frame.shape[1]} columnas")
    return destino


def descargar_churn(forzar: bool = False) -> Path:
    """Telco Customer Churn (OpenML): ~7043 clientes, columna 'Churn' (Yes/No)."""
    destino = RUTA_CRUDOS / "telco-churn.csv"
    if destino.exists() and not forzar:
        print(f"ya existe {destino}, no se descarga")
        return destino
    RUTA_CRUDOS.mkdir(parents=True, exist_ok=True)
    datos = fetch_openml(
        "Telco-Customer-Churn", version=1, as_frame=True, parser="auto",
        data_home=str(RUTA_CRUDOS / "cache_openml"),
    )
    datos.frame.to_csv(destino, index=False)
    print(f"guardado {destino}: {datos.frame.shape[0]} filas, {datos.frame.shape[1]} columnas")
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga los datasets crudos.")
    parser.add_argument("--forzar", action="store_true", help="volver a descargar aunque ya exista")
    args = parser.parse_args()
    descargar_credito(forzar=args.forzar)
    descargar_churn(forzar=args.forzar)


if __name__ == "__main__":
    main()
