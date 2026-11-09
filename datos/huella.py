"""huella(problema) -> dict[str, float]: solo números sobre la FORMA de los datos, nunca sobre el tema.

No cambiar los nombres de las llaves: memoria compara huellas por distancia.
Mismas llaves y escala que comun.falsos.huella_falsa (porcentajes como fracción 0-1).
Importar este módulo no lee datos.
"""
from pandas.api.types import is_numeric_dtype

from comun.contratos import Problema
from datos.problemas import cargar_datos
from evaluacion.fuga import auc_por_columna

LLAVES_CLASIFICACION = ("filas", "columnas", "proporcion_positiva", "pct_faltantes",
                        "pct_categoricas", "max_auc_columna")
LLAVES_SERIE = ("longitud", "pct_ceros", "cv", "fuerza_semanal", "tendencia", "pct_dias_atipicos")


def huella(problema: Problema) -> dict[str, float]:
    if problema.tipo_tarea == "serie":
        raise NotImplementedError("huella de series no implementada todavía")
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
