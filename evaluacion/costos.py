"""Costos de las decisiones. Funciones puras: no leen archivos ni usan aleatoriedad.

Clasificación: la clase positiva (1) es el error caro (por ejemplo impago).
Actuar = predecir positivo = p > umbral (estrictamente mayor).
"""
import numpy as np

UMBRAL_POR_DEFECTO = 0.5   # el que usa una versión sin la lección de umbral por costos


def umbral_optimo_por_costos(costo_fn: float, costo_fp: float) -> float:
    """Umbral que minimiza el costo esperado con probabilidades calibradas: costo_fp / (costo_fp + costo_fn)."""
    _validar_costos(costo_fn, costo_fp)
    return costo_fp / (costo_fp + costo_fn)


def conteo_errores(y_real, probabilidad, umbral: float) -> tuple[int, int]:
    """(falsos negativos, falsos positivos) al actuar si p > umbral."""
    y, p = _validar_entradas(y_real, probabilidad, umbral)
    actuar = p > umbral
    fn = int(((y == 1) & ~actuar).sum())
    fp = int(((y == 0) & actuar).sum())
    return fn, fp


def costo_clasificacion(y_real, probabilidad, umbral: float, costo_fn: float, costo_fp: float) -> float:
    """Costo total = costo_fn * falsos negativos + costo_fp * falsos positivos."""
    _validar_costos(costo_fn, costo_fp)
    fn, fp = conteo_errores(y_real, probabilidad, umbral)
    return float(costo_fn * fn + costo_fp * fp)


def costo_por_fila(y_real, probabilidad, umbral: float, costo_fn: float, costo_fp: float) -> np.ndarray:
    """Costo de cada fila (0 si acierta). Sirve para elegir los peores casos."""
    _validar_costos(costo_fn, costo_fp)
    y, p = _validar_entradas(y_real, probabilidad, umbral)
    actuar = p > umbral
    return np.where((y == 1) & ~actuar, costo_fn, 0.0) + np.where((y == 0) & actuar, costo_fp, 0.0)


def _validar_costos(costo_fn, costo_fp) -> None:
    for nombre, valor in (("costo_fn", costo_fn), ("costo_fp", costo_fp)):
        if valor is None or not np.isfinite(valor) or valor < 0:
            raise ValueError(f"{nombre} debe ser un número >= 0, llegó {valor!r}")
    if costo_fn + costo_fp == 0:
        raise ValueError("costo_fn y costo_fp no pueden ser ambos 0")


def _validar_entradas(y_real, probabilidad, umbral):
    y = np.asarray(y_real)
    p = np.asarray(probabilidad, dtype=float)
    if y.ndim != 1 or p.ndim != 1:
        raise ValueError(f"y_real y probabilidad deben ser vectores, llegaron con forma {y.shape} y {p.shape}")
    if len(y) != len(p):
        raise ValueError(f"y_real tiene {len(y)} valores y probabilidad {len(p)}; deben ser iguales")
    if len(y) == 0:
        raise ValueError("y_real y probabilidad están vacíos")
    if not np.isin(y, [0, 1]).all():
        raise ValueError(f"y_real solo puede tener 0 y 1, tiene {sorted(set(np.unique(y).tolist()))}")
    if np.isnan(p).any() or (p < 0).any() or (p > 1).any():
        raise ValueError(f"las probabilidades deben estar entre 0 y 1; rango recibido "
                         f"[{np.nanmin(p):.3f}, {np.nanmax(p):.3f}], NaN: {int(np.isnan(p).sum())}")
    if not 0 <= umbral <= 1:
        raise ValueError(f"el umbral debe estar entre 0 y 1, llegó {umbral!r}")
    return y.astype(int), p
