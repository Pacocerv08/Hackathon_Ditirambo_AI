"""Selección independiente de implementaciones reales o falsas."""

from comun import config
from comun.contratos import Capacidades, Candidato, Modo, Problema, Resultado
from comun.falsos import (
    contexto_de_fecha_falso,
    evaluar_falso,
    huella_falsa,
    resolver_falso,
)


def _seleccionar(nombre: str, modulo: str, funcion: str, falso):
    if config.USAR_FALSOS:
        print(f"[FALSO] usando {nombre} falso")
        return falso, True
    try:
        import importlib

        real = getattr(importlib.import_module(modulo), funcion)
        return real, False
    except (ImportError, AttributeError):
        print(f"[FALSO] usando {nombre} falso")
        return falso, True


evaluar, _evaluar_falso = _seleccionar(
    "evaluar", "evaluacion.evaluador", "evaluar", evaluar_falso
)
huella, _huella_falsa = _seleccionar("huella", "datos.huella", "huella", huella_falsa)
contexto_de_fecha, _contexto_de_fecha_falso = _seleccionar(
    "contexto_de_fecha", "datos.contexto", "contexto_de_fecha", contexto_de_fecha_falso
)
resolver, _resolver_falso = _seleccionar(
    "resolver", "agentes.ciclo", "resolver_sync", resolver_falso
)

PUERTOS_FALSOS: dict[str, bool] = {
    "evaluar": _evaluar_falso,
    "huella": _huella_falsa,
    "contexto_de_fecha": _contexto_de_fecha_falso,
    "resolver": _resolver_falso,
}

__all__ = ["evaluar", "huella", "contexto_de_fecha", "resolver", "PUERTOS_FALSOS"]
