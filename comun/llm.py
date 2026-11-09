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
    from agents import Agent, Runner

    agente = Agent(
        name="agente",
        instructions=instrucciones,
        model=modelo,
        output_type=esquema,
    )
    resultado = Runner.run_sync(agente, entrada)
    salida = resultado.final_output
    if isinstance(salida, esquema):
        return salida
    if isinstance(salida, str):
        return _validar_salida(salida, esquema)
    return esquema.model_validate(salida)


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

    if config.LLM_BACKEND == "codex":
        return _llamar_codex(agente, instrucciones, entrada, esquema, modelo, esfuerzo)
    if config.LLM_BACKEND == "api":
        return _llamar_api(instrucciones, entrada, esquema, modelo)
    raise ValueError(f"LLM_BACKEND no reconocido: {config.LLM_BACKEND!r}")


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
