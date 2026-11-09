"""Adaptador común para modelos llamados por Codex CLI o Agents SDK."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Lock

from pydantic import BaseModel

from comun import config


_aviso_personal_impreso = False
_aviso_lock = Lock()
_aviso_sin_api_key_impreso = False
_aviso_api_lock = Lock()
_cliente_api = None
_cliente_api_lock = Lock()


def _avisar_agents_personal() -> None:
    global _aviso_personal_impreso
    with _aviso_lock:
        if _aviso_personal_impreso:
            return
        posibles = [Path.home() / ".codex" / "AGENTS.md"]
        codex_home = os.getenv("CODEX_HOME")
        if codex_home:
            posibles.insert(0, Path(codex_home).expanduser() / "AGENTS.md")
        ruta = next((ruta for ruta in posibles if ruta.is_file()), None)
        if ruta is not None:
            print(
                "[LLM] aviso: hay un AGENTS.md personal en "
                f"{ruta}; puede alterar las respuestas de los agentes"
            )
            _aviso_personal_impreso = True


def _validar_salida(contenido: str, esquema: type[BaseModel]) -> BaseModel:
    return esquema.model_validate_json(contenido)


def _cliente_openai():
    global _cliente_api
    with _cliente_api_lock:
        if _cliente_api is None:
            from openai import OpenAI

            _cliente_api = OpenAI()
        return _cliente_api


def _avisar_sin_api_key() -> None:
    global _aviso_sin_api_key_impreso
    with _aviso_api_lock:
        if not _aviso_sin_api_key_impreso:
            print("[LLM] sin OPENAI_API_KEY: usando codex")
            _aviso_sin_api_key_impreso = True


def _llamar_codex(
    agente: str,
    instrucciones: str,
    entrada: str,
    esquema: type[BaseModel],
    modelo: str,
    esfuerzo: str,
) -> BaseModel:
    from agents.strict_schema import ensure_strict_json_schema

    schema = ensure_strict_json_schema(esquema.model_json_schema())
    prompt = (
        instrucciones
        + "\n\n---\nEntrada:\n"
        + entrada
        + "\n\nResponde únicamente con el JSON que cumple el esquema."
    )
    with tempfile.TemporaryDirectory() as temporal:
        directorio = Path(temporal)
        ruta_esquema = directorio / "esquema.json"
        ruta_salida = directorio / "salida.json"
        ruta_esquema.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )
        argumentos = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--sandbox",
            "read-only",
            "-m",
            modelo,
            "-c",
            f'model_reasoning_effort="{esfuerzo}"',
            "--output-schema",
            str(ruta_esquema),
            "-o",
            str(ruta_salida),
            prompt,
        ]
        proceso = subprocess.run(
            argumentos,
            cwd=directorio,
            capture_output=True,
            text=True,
            timeout=config.LLM_TIMEOUT_SEGUNDOS,
        )
        if proceso.returncode != 0 or not ruta_salida.is_file():
            ultimas_lineas = "\n".join(proceso.stderr.splitlines()[-20:])
            if not ultimas_lineas:
                ultimas_lineas = "(stderr vacío)"
            raise RuntimeError(
                f"codex exec falló para {agente} (código {proceso.returncode}); "
                f"últimas líneas de stderr:\n{ultimas_lineas}"
            )
        return _validar_salida(ruta_salida.read_text(encoding="utf-8"), esquema)


def _llamar_api(
    instrucciones: str,
    entrada: str,
    esquema: type[BaseModel],
    modelo: str,
) -> BaseModel:
    cliente = _cliente_openai()
    respuesta = cliente.responses.parse(
        model=modelo,
        instructions=instrucciones,
        input=entrada,
        text_format=esquema,
    )
    if respuesta.output_parsed is None:
        texto = getattr(respuesta, "output_text", None) or str(respuesta)
        raise RuntimeError(f"La API no devolvió una salida estructurada: {texto}")
    return respuesta.output_parsed


def llamar_modelo(
    agente: str,
    instrucciones: str,
    entrada: str,
    esquema: type[BaseModel],
    modelo: str | None = None,
    esfuerzo: str | None = None,
) -> BaseModel:
    _avisar_agents_personal()
    modelo = modelo or config.MODELOS[agente]
    esfuerzo = esfuerzo or config.ESFUERZO[agente]
    motor = config.LLM_BACKEND or config.BACKEND.get(agente, "codex")
    if motor == "api" and not os.getenv("OPENAI_API_KEY"):
        _avisar_sin_api_key()
        motor = "codex"
    print(f"[LLM] {agente} -> {motor} ({modelo})")

    if motor == "codex":
        return _llamar_codex(agente, instrucciones, entrada, esquema, modelo, esfuerzo)
    if motor == "api":
        return _llamar_api(instrucciones, entrada, esquema, modelo)
    raise ValueError(f"Motor LLM no reconocido: {motor!r}")


async def allamar_modelo(
    agente: str,
    instrucciones: str,
    entrada: str,
    esquema: type[BaseModel],
    modelo: str | None = None,
    esfuerzo: str | None = None,
) -> BaseModel:
    return await asyncio.to_thread(
        llamar_modelo,
        agente,
        instrucciones,
        entrada,
        esquema,
        modelo,
        esfuerzo,
    )
