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


def datos_resumen(ctx: ContextoCiclo) -> str:
    """Resume huella, tipo de tarea y costos del problema."""
    p = ctx.problema
    datos = {
        "problema": p.id,
        "tipo_tarea": p.tipo_tarea,
        "objetivo": p.objetivo,
        "huella": huella(p),
        "costos": p.costos.model_dump(exclude_none=True),
    }
    return _compacto(datos)


def datos_lecciones(ctx: ContextoCiclo) -> str:
    """Lista lecciones activas compatibles con la tarea."""
    almacen = ctx.almacen
    ids = ctx.version.lecciones_activas
    if not almacen or not ids or not callable(getattr(almacen, "lecciones", None)):
        return "[]"
    try:
        lecciones = almacen.lecciones(ids)
        tipo = ctx.problema.tipo_tarea
        return _compacto([
            {"id": l.id, "alcance": l.alcance, "senal": l.senal, "texto": l.texto}
            for l in lecciones if l.activa and l.alcance in ("general", tipo)
        ])
    except Exception as exc:
        return _compacto({"error": f"No se pudieron consultar lecciones: {exc}"})


def datos_historial(ctx: ContextoCiclo) -> str:
    """Devuelve un historial compacto de intentos."""
    filas = []
    for candidato, resultado in ctx.historial:
        filas.append({
            "candidato_id": resultado.candidato_id,
            "candidato": candidato.model_dump(),
            "costo_relativo": resultado.costo_relativo,
            "alertas": resultado.alertas[:5],
            "error": resultado.error,
        })
    return _compacto(filas, limite=6000)


def datos_peores_casos(ctx: ContextoCiclo, candidato_id: str) -> str:
    """Busca hasta diez casos difíciles del historial."""
    for _, resultado in reversed(ctx.historial):
        if resultado.candidato_id == candidato_id:
            return _compacto([caso.model_dump() for caso in resultado.peores_casos[:10]])
    return _compacto({"error": f"No hay historial para candidato {candidato_id!r}"})


def datos_contexto_fecha(ctx: ContextoCiclo, fecha: str) -> str:
    """Consulta el calendario con el país definido en el problema."""
    try:
        return _compacto(obtener_contexto_de_fecha(fecha, ctx.problema.pais))
    except Exception as exc:
        return _compacto({"error": f"Fecha inválida o sin contexto: {exc}"})


@function_tool
def resumen_datos(ctx: RunContextWrapper[ContextoCiclo]) -> str:
    """Resume huella, tipo de tarea, columnas conocidas y costos del problema."""
    return datos_resumen(ctx.context)


@function_tool
def consultar_lecciones(ctx: RunContextWrapper[ContextoCiclo]) -> str:
    """Lista lecciones activas de la versión compatibles con este problema."""
    return datos_lecciones(ctx.context)


@function_tool
def historial_intentos(ctx: RunContextWrapper[ContextoCiclo]) -> str:
    """Devuelve modelo, variables, costo relativo y alertas de intentos del ciclo."""
    return datos_historial(ctx.context)


@function_tool
def peores_casos(ctx: RunContextWrapper[ContextoCiclo], candidato_id: str) -> str:
    """Busca hasta diez casos difíciles en el historial local del ciclo."""
    return datos_peores_casos(ctx.context, candidato_id)


@function_tool
def contexto_de_fecha(ctx: RunContextWrapper[ContextoCiclo], fecha: str) -> str:
    """Consulta calendario para una fecha usando el país definido en el problema."""
    return datos_contexto_fecha(ctx.context, fecha)

