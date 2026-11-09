"""Analista del problema con respaldo local si el modelo no está disponible."""

from __future__ import annotations

import logging

from agents import Agent, Runner

from agentes.contexto import ContextoCiclo
from agentes.cliente import crear_cliente_y_modelo
from agentes.esquemas import Descripcion
from agentes.entradas import entrada_analista
from agentes.herramientas import resumen_datos
from agentes.instrucciones import leer_instrucciones
from comun import config
from comun.llm import allamar_modelo


logger = logging.getLogger(__name__)
_MAX_TURNS = 5


async def _llamar_modelo(ctx: ContextoCiclo, entrada: str) -> Descripcion:
    """Único adaptador al Agents SDK; reemplazable sin cambiar el flujo del analista."""
    instrucciones = leer_instrucciones(ctx.version, "analista")
    if config.LLM_BACKEND == "codex":
        aviso = "En este entorno no tienes herramientas: toda la información que necesitas viene en la entrada.\n\n"
        return await allamar_modelo("analista", aviso + instrucciones, entrada_analista(ctx), Descripcion)
    cliente, modelo = crear_cliente_y_modelo("analista")
    try:
        agente = Agent(
            name="Analista",
            instructions=instrucciones,
            model=modelo,
            output_type=Descripcion,
            tools=[resumen_datos],
        )
        resultado = await Runner.run(
            agente,
            entrada,
            context=ctx,
            max_turns=_MAX_TURNS,
        )
        salida = resultado.final_output
        if isinstance(salida, Descripcion):
            return salida
        return Descripcion.model_validate(salida)
    finally:
        await cliente.close()


def _descripcion_minima(ctx: ContextoCiclo) -> Descripcion:
    problema = ctx.problema
    costos = problema.costos.model_dump(exclude_none=True)
    return Descripcion(
        resumen=(
            f"La tarea es {problema.tipo_tarea} para predecir {problema.objetivo}. "
            f"El problema pertenece al dominio {problema.dominio}. "
            f"Los costos definidos para los errores son {costos}."
        ),
        riesgos=[],
    )


async def describir(ctx: ContextoCiclo) -> Descripcion:
    """Describe el problema con el LLM; tras dos fallos devuelve una descripción mínima."""
    entrada = (
        "Describe el problema de decisión del contexto. Usa resumen_datos para revisar "
        "la huella, el objetivo y los costos antes de responder."
    )
    for intento in range(2):
        try:
            return await _llamar_modelo(ctx, entrada)
        except Exception as exc:
            logger.warning(
                "Falló el analista LLM (intento %d/2): %s: %s",
                intento + 1,
                type(exc).__name__,
                exc,
            )

    logger.warning("[RESPALDO] analista: usando descripción mínima local")
    return _descripcion_minima(ctx)


__all__ = ["describir"]
