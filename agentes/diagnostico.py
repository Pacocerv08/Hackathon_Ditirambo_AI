"""Diagnóstico de una iteración con respaldo vacío si el modelo falla."""

from __future__ import annotations

import json
import logging

from agents import Agent, Runner

from agentes.contexto import ContextoCiclo
from agentes.cliente import crear_cliente_y_modelo
from agentes.esquemas import Diagnostico
from agentes.entradas import entrada_diagnostico
from agentes.herramientas import (
    consultar_lecciones,
    contexto_de_fecha,
    historial_intentos,
    peores_casos,
)
from agentes.instrucciones import leer_instrucciones
from comun import config
from comun.llm import allamar_modelo
from comun.contratos import Resultado


logger = logging.getLogger(__name__)
_MAX_TURNS = 5


def _entrada(resultados: list[Resultado]) -> str:
    """Serializa solo el resumen de resultados; los peores casos se consultan con tools."""
    resumen = [
        {
            "candidato_id": resultado.candidato_id,
            "costo_relativo": resultado.costo_relativo,
            "alertas": resultado.alertas,
            "error": resultado.error,
        }
        for resultado in resultados
    ]
    return json.dumps(resumen, ensure_ascii=False, separators=(",", ":"), default=str)


async def _llamar_modelo(ctx: ContextoCiclo, entrada: str) -> Diagnostico:
    """Único adaptador al Agents SDK; reemplazable sin cambiar el flujo diagnóstico."""
    instrucciones = leer_instrucciones(ctx.version, "diagnostico")
    if config.LLM_BACKEND == "codex":
        aviso = "En este entorno no tienes herramientas: toda la información que necesitas viene en la entrada.\n\n"
        return await allamar_modelo("diagnostico", aviso + instrucciones, entrada, Diagnostico)
    cliente, modelo = crear_cliente_y_modelo("diagnostico")
    try:
        agente = Agent(
            name="Diagnóstico",
            instructions=instrucciones,
            model=modelo,
            output_type=Diagnostico,
            tools=[
                historial_intentos,
                peores_casos,
                consultar_lecciones,
                contexto_de_fecha,
            ],
        )
        resultado = await Runner.run(
            agente,
            entrada,
            context=ctx,
            max_turns=_MAX_TURNS,
        )
        salida = resultado.final_output
        if isinstance(salida, Diagnostico):
            return salida
        return Diagnostico.model_validate(salida)
    finally:
        await cliente.close()


async def diagnosticar(
    ctx: ContextoCiclo,
    resultados: list[Resultado],
) -> Diagnostico:
    """Diagnostica la iteración; ante dos fallos devuelve un diagnóstico vacío y sigue."""
    entrada = entrada_diagnostico(ctx, resultados) if config.LLM_BACKEND == "codex" else _entrada(resultados)
    for intento in range(2):
        try:
            return await _llamar_modelo(ctx, entrada)
        except Exception as exc:
            logger.warning(
                "Falló el diagnóstico LLM (intento %d/2): %s: %s",
                intento + 1,
                type(exc).__name__,
                exc,
            )

    logger.warning("[RESPALDO] diagnóstico: devolviendo diagnóstico vacío")
    return Diagnostico(
        que_fallo="",
        por_que="",
        evidencia=[],
        que_probar="",
        seguir=True,
    )


__all__ = ["diagnosticar"]
