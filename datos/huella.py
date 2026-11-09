"""huella(problema) -> dict[str, float]: solo números sobre la FORMA de los datos, nunca sobre el tema.

No cambiar los nombres de las llaves: memoria compara huellas por distancia.
Mismas llaves y escala que comun.falsos.huella_falsa (porcentajes como fracción 0-1).
Importar este módulo no lee datos.
"""
import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

from comun.contratos import Problema
from datos.problemas import cargar_datos
from evaluacion.fuga import auc_por_columna

LLAVES_CLASIFICACION = ("filas", "columnas", "proporcion_positiva", "pct_faltantes",
                        "pct_categoricas", "max_auc_columna")
LLAVES_SERIE = ("longitud", "pct_ceros", "cv", "fuerza_semanal", "tendencia", "pct_dias_atipicos")


def _huella_serie(problema: Problema) -> dict[str, float]:
    y = cargar_datos(problema)[problema.objetivo].astype(float).reset_index(drop=True)
    media = float(y.mean())
    t = np.arange(len(y))
    pendiente = float(np.polyfit(t, y.to_numpy(), 1)[0]) if len(y) > 1 else 0.0
    error_ref = (y - y.shift(7)).dropna()          # error de la referencia (repetir hace 7 días)
    sd = float(error_ref.std())
    autocorr = y.autocorr(lag=7) if len(y) > 7 else np.nan
    resultado = {
        "longitud": float(len(y)),
        "pct_ceros": float((y == 0).mean()),
        "cv": float(y.std() / media) if media else 0.0,
        "fuerza_semanal": 0.0 if pd.isna(autocorr) else float(autocorr),
        "tendencia": pendiente * len(y) / media if media else 0.0,   # cambio total / media
        "pct_dias_atipicos": float(((error_ref - error_ref.mean()).abs() > 3 * sd).mean()) if sd > 0 else 0.0,
    }
    assert tuple(resultado) == LLAVES_SERIE
    return resultado


def huella(problema: Problema) -> dict[str, float]:
    if problema.tipo_tarea == "serie":
        return _huella_serie(problema)
    df = cargar_datos(problema)
    X, y = df.drop(columns=problema.objetivo), df[problema.objetivo]
    resultado = {
        "filas": float(len(df)),
        "columnas": float(X.shape[1]),                                  # sin el objetivo
        "proporcion_positiva": float(y.mean()),
        "pct_faltantes": float(X.isna().to_numpy().mean()),             # fracción de celdas, 0-1
        "pct_categoricas": float(sum(not is_numeric_dtype(X[c]) for c in X) / X.shape[1]),
        "max_auc_columna": float(max(auc_por_columna(X, y).values())),  # sobre todos los datos
    }
    assert tuple(resultado) == LLAVES_CLASIFICACION
    return resultado
