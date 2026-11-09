"""Proponente determinista de respaldo, sin llamadas a modelos de lenguaje."""

from __future__ import annotations

import json

from comun.contratos import Candidato, Hiperparametro
from agentes.contexto import ContextoCiclo
from agentes.esquemas import Propuesta


class SinCandidatosNuevos(Exception):
    """No hay suficientes candidatos inéditos para completar una propuesta."""


def _clave(candidato: Candidato) -> str:
    """Identidad funcional: la justificación no cambia la configuración."""
    return json.dumps(
        {
            "modelo": candidato.modelo,
            "features": sorted(candidato.features),
            "excluir_columnas": sorted(candidato.excluir_columnas),
            "hiperparametros": sorted(
                (p.nombre, p.valor) for p in candidato.hiperparametros
            ),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def candidatos_ineditos(
    contexto: ContextoCiclo,
    cantidad: int = 3,
    excluir: set[str] | None = None,
) -> list[Candidato]:
    """Devuelve hasta ``cantidad`` candidatos nuevos fuera del historial y excluir.

    ``excluir`` contiene claves funcionales obtenidas con ``clave_candidato``.
    """
    if cantidad < 0:
        raise ValueError("cantidad no puede ser negativa")
    if cantidad == 0:
        return []
    # Las variaciones están acotadas a parámetros estándar del registro de modelos.
    configuraciones: list[tuple[str, list[str], list[tuple[str, int | float | str]]]]
    if contexto.problema.tipo_tarea == "serie":
        catalogo_features = ["rezagos", "medias_moviles", "dia_semana"]
        configuraciones = []
        for features in (
            ["rezagos"],
            ["medias_moviles"],
            ["dia_semana"],
            ["rezagos", "medias_moviles"],
            ["rezagos", "dia_semana"],
            ["medias_moviles", "dia_semana"],
            catalogo_features,
        ):
            configuraciones.append(("referencia", features, []))
            configuraciones.extend(
                ("arbol", features, [("max_depth", depth)])
                for depth in (2, 4, 8, 1)
            )
            configuraciones.extend(
                ("lightgbm", features, [(name, value)])
                for name, value in (
                    ("n_estimators", 50), ("n_estimators", 100),
                    ("n_estimators", 200), ("n_estimators", 25),
                    ("learning_rate", 0.05), ("learning_rate", 0.1),
                    ("num_leaves", 15), ("num_leaves", 31),
                    ("min_child_samples", 10), ("min_child_samples", 20),
                )
            )
    else:
        configuraciones = [
        ("referencia", []),
        ("logistica", [("C", 0.1)]),
        ("logistica", [("C", 1.0)]),
        ("logistica", [("C", 10.0)]),
        ("logistica", [("C", 0.01)]),
        ("arbol", [("max_depth", 2)]),
        ("arbol", [("max_depth", 4)]),
        ("arbol", [("max_depth", 8)]),
        ("arbol", [("max_depth", 1)]),
        ("lightgbm", [("n_estimators", 50)]),
        ("lightgbm", [("n_estimators", 100)]),
        ("lightgbm", [("n_estimators", 200)]),
        ("lightgbm", [("n_estimators", 25)]),
        ("lightgbm", [("num_leaves", 15)]),
        ("lightgbm", [("num_leaves", 31)]),
        ("lightgbm", [("num_leaves", 63)]),
        ("lightgbm", [("num_leaves", 7)]),
        ]
        configuraciones = [(modelo, [], parametros) for modelo, parametros in configuraciones]
    ya_probados = {_clave(candidato) for candidato, _ in contexto.historial}
    ya_probados.update(excluir or set())
    nuevos: list[Candidato] = []
    for modelo, features, parametros in configuraciones:
        candidato = Candidato(
            modelo=modelo,
            features=features,
            hiperparametros=[Hiperparametro(nombre=n, valor=v) for n, v in parametros],
            justificacion="Configuración fija de respaldo, seleccionada en orden determinista.",
        )
        clave = _clave(candidato)
        if clave in ya_probados:
            continue
        nuevos.append(candidato)
        if len(nuevos) == cantidad:
            return nuevos
    if len(nuevos) < cantidad:
        raise SinCandidatosNuevos(
            f"Solo quedan {len(nuevos)} candidatos inéditos; se solicitaron {cantidad}"
        )
    return nuevos


def clave_candidato(candidato: Candidato) -> str:
    """Clave estable para detectar configuraciones funcionalmente repetidas."""
    return _clave(candidato)


def proponer(contexto: ContextoCiclo) -> Propuesta:
    """Devuelve las siguientes tres configuraciones permitidas no probadas."""
    nuevos = candidatos_ineditos(contexto, 3)
    return Propuesta(candidatos=nuevos)


__all__ = [
    "proponer", "candidatos_ineditos", "clave_candidato", "SinCandidatosNuevos"
]
