"""Proponente con modelo y respaldo determinista, con propuestas siempre inéditas."""

from __future__ import annotations

import json
import logging

from agents import Agent, Runner

from agentes import fijo
from agentes.contexto import ContextoCiclo
from agentes.esquemas import Descripcion, Diagnostico, Propuesta
from agentes.entradas import entrada_proponente
from agentes.herramientas import consultar_lecciones, historial_intentos
from agentes.instrucciones import leer_instrucciones
from comun import config
from comun.llm import allamar_modelo


logger = logging.getLogger(__name__)
_MAX_TURNS = 5


def _entrada(descripcion: Descripcion, ultimo_diagnostico: Diagnostico | None) -> str:
    datos = {
        "descripcion_problema": descripcion.model_dump(),
        "ultimo_diagnostico": (
            ultimo_diagnostico.model_dump() if ultimo_diagnostico is not None else None
        ),
    }
    return json.dumps(datos, ensure_ascii=False, default=str)


async def _llamar_modelo(ctx: ContextoCiclo, entrada: str) -> Propuesta:
    """Único adaptador al Agents SDK; reemplazable sin cambiar la lógica de propuestas."""
    instrucciones = leer_instrucciones(ctx.version, "proponente")
    if config.LLM_BACKEND == "codex":
        aviso = "En este entorno no tienes herramientas: toda la información que necesitas viene en la entrada.\n\n"
        return await allamar_modelo("proponente", aviso + instrucciones, entrada, Propuesta)
    agente = Agent(
        name="Proponente",
        instructions=instrucciones,
        model=config.MODELOS["proponente"],
        output_type=Propuesta,
        tools=[consultar_lecciones, historial_intentos],
    )
    resultado = await Runner.run(
        agente,
        entrada,
        context=ctx,
        max_turns=_MAX_TURNS,
    )
    salida = resultado.final_output
    if isinstance(salida, Propuesta):
        return salida
    return Propuesta.model_validate(salida)


def _completar(ctx: ContextoCiclo, propuesta: Propuesta) -> Propuesta:
    vistos = {fijo.clave_candidato(candidato) for candidato, _ in ctx.historial}
    candidatos = []
    for candidato in propuesta.candidatos:
        clave = fijo.clave_candidato(candidato)
        if clave in vistos:
            continue
        vistos.add(clave)
        candidatos.append(candidato)
        if len(candidatos) == 3:
            break

    faltan = 3 - len(candidatos)
    if faltan:
        candidatos.extend(fijo.candidatos_ineditos(ctx, faltan, vistos))
    return Propuesta(candidatos=candidatos)


async def proponer_con_llm(
    ctx: ContextoCiclo,
    descripcion: Descripcion,
    ultimo_diagnostico: Diagnostico | None,
) -> Propuesta:
    """Propone tres candidatos nuevos y reintenta el modelo una vez.

    Si ambas llamadas al modelo fallan, usa ``fijo.proponer``. Si ya no hay
    suficientes candidatos inéditos en el catálogo fijo, propaga
    ``SinCandidatosNuevos`` para que el ciclo decida cómo manejarlo.
    """
    entrada = entrada_proponente(ctx, descripcion, ultimo_diagnostico) if config.LLM_BACKEND == "codex" else _entrada(descripcion, ultimo_diagnostico)
    propuesta: Propuesta | None = None
    for intento in range(2):
        try:
            propuesta = await _llamar_modelo(ctx, entrada)
            break
        except Exception as exc:
            logger.warning(
                "Falló el proponente LLM (intento %d/2): %s: %s",
                intento + 1,
                type(exc).__name__,
                exc,
            )

    if propuesta is None:
        logger.warning("[RESPALDO] proponente: usando fijo")
        propuesta = fijo.proponer(ctx)

    try:
        return _completar(ctx, propuesta)
    except Exception:
        logger.exception("No se pudo completar la propuesta del modelo; usando propuesta fija")
        return fijo.proponer(ctx)


__all__ = ["proponer_con_llm"]
