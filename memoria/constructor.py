"""Construye versiones sucesoras a partir de lecciones curadas."""

import re
import shutil
import unicodedata
from pathlib import Path

from comun import config
from comun.contratos import Leccion, Version
from memoria.almacen import Almacen
from memoria.versiones import _escribir_config, _leer_modelos


def _slug_leccion(leccion: Leccion) -> str:
    if leccion.capacidad:
        origen = leccion.capacidad
    else:
        origen = " ".join(leccion.texto.split()[:5])
    ascii_texto = unicodedata.normalize("NFKD", origen).encode("ascii", "ignore").decode("ascii")
    minusculas = ascii_texto.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", minusculas).strip("-")
    slug = re.sub(r"-+", "-", slug)[:40].strip("-")
    return slug or "leccion"


def _texto_una_linea(texto: str) -> str:
    return " ".join(texto.split())


def _escribir_texto(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(contenido.replace("\r\n", "\n").replace("\r", "\n"))


def _agregar_regla(ruta: Path, leccion: Leccion) -> None:
    if ruta.exists():
        with ruta.open("r", encoding="utf-8") as archivo:
            contenido = archivo.read()
    else:
        contenido = ""
    if contenido and not contenido.endswith("\n"):
        contenido += "\n"
    bloque = (
        f"<!-- leccion:{leccion.id} -->\n"
        f"- ({leccion.id}) {leccion.texto}\n"
        f"<!-- /leccion:{leccion.id} -->\n"
    )
    _escribir_texto(ruta, contenido + bloque)


def _crear_skill(leccion: Leccion, version_padre: str, carpeta: Path) -> None:
    slug = _slug_leccion(leccion)
    nombre = f"{leccion.id.lower()}-{slug}"
    texto = _texto_una_linea(leccion.texto)
    capacidad = leccion.capacidad or "ninguna"
    agentes = ", ".join(leccion.regla_para) if leccion.regla_para else "ninguno"
    contenido = (
        "---\n"
        f"name: {nombre}\n"
        f"description: {texto}\n"
        "---\n"
        "## Señal\n"
        f"{_texto_una_linea(leccion.senal)}\n"
        "## Evidencia\n"
        f"{', '.join(leccion.evidencia)}\n"
        "## Qué cambia en el sucesor\n"
        f"Capacidad: {capacidad}. Agentes con regla: {agentes}.\n"
        "## Origen\n"
        f"Versión: {version_padre}. Problema: {leccion.problema_origen}.\n"
    )
    carpeta.mkdir(parents=True, exist_ok=True)
    _escribir_texto(carpeta / "leccion.json", leccion.model_dump_json(indent=2) + "\n")
    _escribir_texto(carpeta / "SKILL.md", contenido)


def construir_sucesor(
    version: Version,
    lecciones: list[Leccion],
    raiz: str | Path = config.RUTA_VERSIONES,
    almacen: Almacen | None = None,
) -> Version:
    lecciones_nuevas = []
    ids_vistos = set(version.lecciones_activas)
    for leccion in lecciones:
        if leccion.id not in ids_vistos:
            lecciones_nuevas.append(leccion)
            ids_vistos.add(leccion.id)
    if not lecciones_nuevas:
        return version

    coincidencia = re.fullmatch(r"v(\d+)", version.id)
    if coincidencia is None:
        raise ValueError(
            f"El id de versión debe tener el formato vN (por ejemplo, v1); recibido: {version.id!r}"
        )

    raiz_path = Path(raiz)
    id_sucesor = f"v{int(coincidencia.group(1)) + 1}"
    origen = raiz_path / version.id
    destino = raiz_path / id_sucesor
    if destino.exists():
        raise FileExistsError(f"La carpeta de la versión sucesora ya existe: {destino}")

    modelos = _leer_modelos(version.id, raiz=raiz_path)
    shutil.copytree(origen, destino)

    capacidades = version.capacidades.model_copy(deep=True)
    ids_activas = list(version.lecciones_activas)
    cambios = []
    reglas_por_agente: dict[str, list[str]] = {}
    for leccion in lecciones_nuevas:
        if leccion.capacidad is not None:
            setattr(capacidades, leccion.capacidad, True)
        ids_activas.append(leccion.id)
        cambios.append(f"Se incorporó {leccion.id}: {leccion.texto}")

        for agente in leccion.regla_para:
            ruta_instruccion = destino / "instrucciones" / f"{agente}.md"
            _agregar_regla(ruta_instruccion, leccion)
            reglas_por_agente.setdefault(agente, []).append(leccion.id)

        slug = _slug_leccion(leccion)
        _crear_skill(
            leccion,
            version.id,
            destino / "lecciones" / f"{leccion.id}-{slug}",
        )

    capacidades_activadas = [
        nombre
        for nombre, activa in capacidades.model_dump().items()
        if activa and not getattr(version.capacidades, nombre)
    ]
    reglas_texto = [
        f"{agente}: {', '.join(ids)}" for agente, ids in reglas_por_agente.items()
    ]
    lineas_cambios = [
        f"Padre: {version.id}",
        "creada_por: sistema",
        "Lecciones nuevas:",
        *[f"- {leccion.id}: {leccion.texto}" for leccion in lecciones_nuevas],
        "Capacidades encendidas:",
        *([f"- {capacidad}" for capacidad in capacidades_activadas] or ["- ninguna"]),
        "Reglas agregadas por agente:",
    ]
    if reglas_texto:
        lineas_cambios.extend(f"- {regla}" for regla in reglas_texto)
    else:
        lineas_cambios.append("- ninguna")
    _escribir_texto(destino / "cambios.md", "\n".join(lineas_cambios) + "\n")

    sucesor = Version(
        id=id_sucesor,
        padre=version.id,
        capacidades=capacidades,
        lecciones_activas=ids_activas,
        creada_por="sistema",
        cambios=cambios,
    )
    _escribir_config(destino / "config.json", sucesor, modelos)

    if almacen is not None:
        for leccion in lecciones_nuevas:
            almacen.guardar_leccion(leccion)
        almacen.guardar_version(sucesor)

    return sucesor
