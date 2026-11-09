"""Detección de fuga: AUC de cada columna sola contra el objetivo.

Contrato con evaluador.py (no cambiar):
    revisar(X, y, quitar: bool) -> (columnas_a_quitar, alertas, metricas)

Funciones puras: no leen archivos; la única partición aleatoria usa una semilla fija (config.SEMILLA).
El evaluador las llama solo con los datos con los que entrena.
"""
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from comun import config

UMBRAL_FUGA = 0.95        # una columna sola con AUC > 0.95 es sospechosa
FOLDS_CODIFICACION = 5
CATEGORIA_FALTANTE = "faltante"


def _validar(X, y) -> np.ndarray:
    if not isinstance(X, pd.DataFrame):
        raise ValueError(f"X debe ser un DataFrame, llegó {type(X).__name__}")
    if X.shape[0] == 0 or X.shape[1] == 0:
        raise ValueError(f"X está vacío (forma {X.shape})")
    y = np.asarray(y)
    if y.ndim != 1:
        raise ValueError(f"y debe ser un vector, llegó con forma {y.shape}")
    if len(y) != len(X):
        raise ValueError(f"X tiene {len(X)} filas y y {len(y)} valores; deben ser iguales")
    if pd.isna(y).any() or not np.isin(y, [0, 1]).all():
        raise ValueError(f"y debe ser binario 0/1, tiene {sorted(set(pd.unique(y).tolist()), key=str)}")
    conteo = np.bincount(y.astype(int), minlength=2)
    if conteo.min() < 2:
        raise ValueError(f"y necesita al menos 2 casos de cada clase, tiene {conteo.tolist()}")
    return y.astype(int)


def _auc_simetrico(y: np.ndarray, x: np.ndarray) -> float:
    if np.all(x == x[0]):
        return 0.5
    auc = roc_auc_score(y, x)
    return float(max(auc, 1 - auc))


def _numerica(serie: pd.Series) -> np.ndarray:
    x = serie.astype(float)
    mediana = x.median()
    return x.fillna(0.0 if pd.isna(mediana) else mediana).to_numpy()


def _categorica_fuera_de_muestra(serie: pd.Series, y: np.ndarray) -> np.ndarray:
    """Cada categoría -> media del objetivo calculada en los otros folds. No vistas -> media global del fold."""
    cats = serie.astype(object).where(serie.notna(), CATEGORIA_FALTANTE).astype(str).to_numpy()
    n_folds = min(FOLDS_CODIFICACION, int(np.bincount(y).min()))
    folds = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=config.SEMILLA)
    codificada = np.empty(len(y), dtype=float)
    for entrena, valida in folds.split(cats, y):
        medias = pd.Series(y[entrena]).groupby(cats[entrena]).mean()
        global_ = float(y[entrena].mean())
        codificada[valida] = pd.Series(cats[valida]).map(medias).fillna(global_).to_numpy()
    return codificada


def auc_por_columna(X: pd.DataFrame, y) -> dict[str, float]:
    """AUC de cada columna sola contra y, como max(auc, 1 - auc). Columna constante: 0.5."""
    y = _validar(X, y)
    aucs = {}
    for col in X.columns:
        serie = X[col]
        if is_numeric_dtype(serie):
            x = _numerica(serie)
        else:
            x = _categorica_fuera_de_muestra(serie, y)
        aucs[str(col)] = _auc_simetrico(y, x)
    return aucs


def revisar(X: pd.DataFrame, y, quitar: bool) -> tuple[list[str], list[str], dict[str, float]]:
    """Siempre calcula. Devuelve (columnas_a_quitar, alertas, metricas).

    - alertas: "posible_fuga: <columna> (AUC 0.99)" por cada columna con AUC > 0.95.
    - metricas: {"max_auc_columna": AUC más alto}.
    - columnas_a_quitar: las sospechosas si quitar=True; [] si quitar=False.
    """
    aucs = auc_por_columna(X, y)
    sospechosas = sorted((c for c, a in aucs.items() if a > UMBRAL_FUGA), key=lambda c: (-aucs[c], c))
    alertas = [f"posible_fuga: {c} (AUC {aucs[c]:.2f})" for c in sospechosas]
    metricas = {"max_auc_columna": max(aucs.values())}
    return (list(sospechosas) if quitar else []), alertas, metricas
