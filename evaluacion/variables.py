"""Catálogo de generadores de variables para series. candidato.features solo acepta estos nombres.

Regla anti-fuga: ninguna variable usa la demanda del mismo día ni de días futuros (todo desplazado
al menos un día). 'calendario' usa el calendario del mismo día, que se conoce de antemano.
Las variables de calendario se calculan una vez por problema y se guardan en caché (con candado).
Importar este módulo no lee datos.
"""
import threading

import numpy as np
import pandas as pd

from comun.contratos import Capacidades, Problema
from datos.contexto import contexto_de_fecha

CATALOGO = ("rezagos", "medias_moviles", "dia_semana", "calendario")
FILAS_DE_ARRANQUE = 28          # el rezago más largo: antes de esto no hay variables completas
ALERTA_SIN_CALENDARIO = "calendario no disponible en esta versión"
DIAS_SIN_FESTIVO = 365.0        # valor para dias_a_festivo cuando no hay festivo próximo

_cache_calendario: dict[tuple, pd.DataFrame] = {}
_candado_calendario = threading.Lock()


def _calendario(problema: Problema, fechas: pd.Series) -> pd.DataFrame:
    llave = (problema.id, problema.archivo, problema.pais, len(fechas),
             str(fechas.iloc[0]), str(fechas.iloc[-1]))
    with _candado_calendario:
        if llave not in _cache_calendario:
            filas = []
            for f in fechas:
                c = contexto_de_fecha(pd.Timestamp(f).strftime("%Y-%m-%d"), problema.pais)
                dias = c["dias_a_festivo_mas_cercano"]
                filas.append({
                    "cal_festivo": float(c["es_festivo"]),
                    "cal_quincena": float(c["es_quincena"]),
                    "cal_fin_de_mes": float(c["es_fin_de_mes"]),
                    "cal_dias_a_festivo": DIAS_SIN_FESTIVO if dias is None else float(dias),
                    "cal_evento": float(c["evento"] is not None),
                })
            _cache_calendario[llave] = pd.DataFrame(filas)
        return _cache_calendario[llave].copy()


def dias_especiales(problema: Problema, fechas: pd.Series) -> np.ndarray:
    """True los días de festivo, quincena o evento (para la métrica costo_dias_festivos)."""
    cal = _calendario(problema, pd.Series(pd.to_datetime(fechas)).reset_index(drop=True))
    return ((cal["cal_festivo"] + cal["cal_quincena"] + cal["cal_evento"]) > 0).to_numpy()


def construir_variables(problema: Problema, df: pd.DataFrame, features: list[str],
                        capacidades: Capacidades) -> tuple[pd.DataFrame, list[str]]:
    """Devuelve (X con una fila por día, alertas). Las primeras FILAS_DE_ARRANQUE filas tienen NaN.

    df debe venir ordenado por fecha (datos.problemas.cargar_datos lo garantiza).
    """
    y = df[problema.objetivo].astype(float).reset_index(drop=True)
    fechas = pd.to_datetime(df[problema.columna_fecha]).reset_index(drop=True)
    alertas: list[str] = []
    bloques: list[pd.DataFrame] = []
    vistos: set[str] = set()
    for nombre in features:
        if nombre in vistos:
            continue
        vistos.add(nombre)
        if nombre not in CATALOGO:
            alertas.append(f"variable desconocida ignorada: {nombre}")
        elif nombre == "rezagos":
            bloques.append(pd.DataFrame({f"rezago_{k}": y.shift(k) for k in (7, 14, 28)}))
        elif nombre == "medias_moviles":
            pasado = y.shift(1)
            bloques.append(pd.DataFrame({f"media_{k}": pasado.rolling(k).mean() for k in (7, 28)}))
        elif nombre == "dia_semana":
            bloques.append(pd.DataFrame({"dia_semana": fechas.dt.dayofweek.astype(float)}))
        elif nombre == "calendario":
            if capacidades.variables_calendario:
                bloques.append(_calendario(problema, fechas))
            else:
                alertas.append(ALERTA_SIN_CALENDARIO)
    if not bloques:
        raise ValueError(f"el candidato de serie no tiene variables válidas; catálogo: {', '.join(CATALOGO)}")
    return pd.concat(bloques, axis=1), alertas
