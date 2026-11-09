"""Carga las instrucciones de agente de una versión en disco."""

from pathlib import Path

from comun.contratos import NombreAgente, Version


_RAIZ = Path(__file__).resolve().parent.parent


def leer_instrucciones(version: Version, agente: NombreAgente) -> str:
    """Devuelve el Markdown del agente o falla indicando la ruta ausente."""
    ruta = _RAIZ / "versiones" / version.id / "instrucciones" / f"{agente}.md"
    try:
        return ruta.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Faltan las instrucciones requeridas: {ruta}") from exc

