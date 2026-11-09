"""Creación aislada del cliente OpenAI para una llamada al Agents SDK."""

from agents import OpenAIResponsesModel
from openai import AsyncOpenAI

from comun import config


def crear_cliente_y_modelo(agente: str):
    """Devuelve un cliente nuevo y su modelo Responses configurado."""
    cliente = AsyncOpenAI()
    modelo = OpenAIResponsesModel(
        model=config.MODELOS[agente],
        openai_client=cliente,
    )
    return cliente, modelo
