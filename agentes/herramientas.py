"""Herramientas pequeñas de consulta para los agentes del ciclo."""

import json
from typing import Any

from agents import RunContextWrapper, function_tool

from agentes.contexto import ContextoCiclo
from comun.puertos import contexto_de_fecha as obtener_contexto_de_fecha
from comun.puertos import huella


def _compacto(dato: Any, limite: int = 2500) -> str:
    """Serializa JSON válido, quitando elementos enteros si hace falta."""
    if isinstance(dato, list):
        elementos = list(dato)
        omitidas = 0
        while True:
            salida = elementos + ([{"omitidas": omitidas}] if omitidas else [])
            texto = json.dumps(salida, ensure_ascii=False, separators=(",", ":"), default=str)
            if len(texto) <= limite:
                return texto
            if elementos:
                elementos.pop(0)
                omitidas += 1
            else:
                # El marcador también podría exceder el límite solo con límites minúsculos.
                return json.dumps([{"omitidas": omitidas}], separators=(",", ":"))

    texto = json.dumps(dato, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(texto) <= limite:
        return texto
    # No se puede recortar un valor serializado sin arriesgarse a romper el JSON.
    return json.dumps({"omitidas": 1}, separators=(",", ":"))


@function_tool
def resumen_datos(ctx: RunContextWrapper[ContextoCiclo]) -> str:
    """Resume huella, tipo de tarea, columnas conocidas y costos del problema."""
    p = ctx.context.problema
    datos = {
        "problema": p.id,
        "tipo_tarea": p.tipo_tarea,
        "objetivo": p.objetivo,
        "huella": huella(p),
        "costos": p.costos.model_dump(exclude_none=True),
    }
    return _compacto(datos)


@function_tool
def consultar_lecciones(ctx: RunContextWrapper[ContextoCiclo]) -> str:
    """Lista lecciones activas de la versión compatibles con este problema."""
    almacen = ctx.context.almacen
    ids = ctx.context.version.lecciones_activas
    if not almacen or not ids or not callable(getattr(almacen, "lecciones", None)):
        return "[]"
    try:
        lecciones = almacen.lecciones(ids)
        tipo = ctx.context.problema.tipo_tarea
        aplicables = [
            {"id": l.id, "alcance": l.alcance, "senal": l.senal, "texto": l.texto}
            for l in lecciones
            if l.activa and l.alcance in ("general", tipo)
        ]
        return _compacto(aplicables)
    except Exception as exc:
        return _compacto({"error": f"No se pudieron consultar lecciones: {exc}"})


@function_tool
def historial_intentos(ctx: RunContextWrapper[ContextoCiclo]) -> str:
    """Devuelve modelo, variables, costo relativo y alertas de intentos del ciclo."""
    filas = []
    for candidato, resultado in ctx.context.historial:
        filas.append({
            "candidato_id": resultado.candidato_id,
            "modelo": candidato.modelo,
            "features": candidato.features,
            "excluidas": candidato.excluir_columnas,
            "costo_relativo": resultado.costo_relativo,
            "alertas": resultado.alertas[:5],
        })
    return _compacto(filas, limite=6000)


@function_tool
def peores_casos(ctx: RunContextWrapper[ContextoCiclo], candidato_id: str) -> str:
    """Busca hasta diez casos difíciles en el historial local del ciclo."""
    for _, resultado in reversed(ctx.context.historial):
        if resultado.candidato_id == candidato_id:
            return _compacto([caso.model_dump() for caso in resultado.peores_casos[:10]])
    return _compacto({"error": f"No hay historial para candidato {candidato_id!r}"})


@function_tool
def contexto_de_fecha(ctx: RunContextWrapper[ContextoCiclo], fecha: str) -> str:
    """Consulta calendario para una fecha usando el país definido en el problema."""
    try:
        return _compacto(obtener_contexto_de_fecha(fecha, ctx.context.problema.pais))
    except (TypeError, ValueError) as exc:
        return _compacto({"error": f"Fecha inválida o sin contexto: {exc}"})

