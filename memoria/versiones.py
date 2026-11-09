"""Lectura, creación inicial y ablación de versiones del sistema."""

import json
import re
import shutil
from pathlib import Path

from comun import config
from comun.contratos import Capacidades, Leccion, Version


def _escribir_config(ruta: Path, version: Version, modelos: dict) -> None:
    datos = version.model_dump(mode="json")
    datos["modelos"] = modelos
    with ruta.open("w", encoding="utf-8", newline="\n") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)
        archivo.write("\n")


def _leer_modelos(id: str, raiz: str | Path = config.RUTA_VERSIONES) -> dict:
    ruta_config = Path(raiz) / id / "config.json"
    with ruta_config.open("r", encoding="utf-8", newline="\n") as archivo:
        return json.load(archivo)["modelos"]


def _leer_leccion(carpeta: Path) -> Leccion:
    ruta = carpeta / "leccion.json"
    with ruta.open("r", encoding="utf-8", newline="\n") as archivo:
        return Leccion.model_validate_json(archivo.read())


def crear_v0(raiz: str | Path = config.RUTA_VERSIONES) -> Version:
    raiz_path = Path(raiz)
    carpeta = raiz_path / "v0"
    ruta_config = carpeta / "config.json"
    if ruta_config.exists():
        return cargar_version("v0", raiz=raiz_path)

    carpeta.mkdir(parents=True, exist_ok=True)
    version = Version(
        id="v0",
        padre=None,
        capacidades=Capacidades(),
        lecciones_activas=[],
        creada_por="equipo",
        cambios=[],
    )
    _escribir_config(ruta_config, version, config.MODELOS)
    return version


def cargar_version(id: str, raiz: str | Path = config.RUTA_VERSIONES) -> Version:
    ruta_config = Path(raiz) / id / "config.json"
    if not ruta_config.is_file():
        raise FileNotFoundError(f"No se encontró la versión {id!r}; se buscó {ruta_config}")
    with ruta_config.open("r", encoding="utf-8", newline="\n") as archivo:
        datos = json.load(archivo)
    datos.pop("modelos", None)
    return Version.model_validate(datos)


def _carpeta_de_leccion(raiz_version: Path, leccion_id: str) -> Path:
    carpeta_lecciones = raiz_version / "lecciones"
    coincidencias = sorted(carpeta_lecciones.glob(f"{leccion_id}-*"))
    for carpeta in coincidencias:
        if carpeta.is_dir() and (carpeta / "leccion.json").is_file():
            return carpeta
    raise ValueError(
        f"No se encontró leccion.json para {leccion_id!r} en {carpeta_lecciones}"
    )


def _lecciones_activas(raiz_version: Path, ids: list[str]) -> list[Leccion]:
    lecciones = []
    for leccion_id in ids:
        try:
            carpeta = _carpeta_de_leccion(raiz_version, leccion_id)
        except ValueError:
            continue
        lecciones.append(_leer_leccion(carpeta))
    return lecciones


def version_sin(
    id: str,
    leccion_id: str,
    raiz: str | Path = config.RUTA_VERSIONES,
) -> Version:
    raiz_path = Path(raiz)
    version = cargar_version(id, raiz=raiz_path)
    if leccion_id not in version.lecciones_activas:
        raise ValueError(f"La lección {leccion_id!r} no está activa en la versión {id!r}")

    origen = raiz_path / id
    destino = raiz_path / f"{id}-sin-{leccion_id}"
    modelos = _leer_modelos(id, raiz=raiz_path)
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origen, destino)

    carpeta_leccion = _carpeta_de_leccion(destino, leccion_id)
    leccion = _leer_leccion(carpeta_leccion)
    ids_restantes = [actual for actual in version.lecciones_activas if actual != leccion_id]
    if leccion.capacidad is not None:
        capacidad_compartida = any(
            otra.capacidad == leccion.capacidad
            for otra in _lecciones_activas(destino, ids_restantes)
        )
        if not capacidad_compartida:
            setattr(version.capacidades, leccion.capacidad, False)

    version.lecciones_activas = ids_restantes
    version.id = f"{id}-sin-{leccion_id}"
    version.padre = id
    version.creada_por = "equipo"
    version.cambios = [f"Ablación: sin {leccion_id}"]

    patron = re.compile(
        rf"<!-- leccion:{re.escape(leccion_id)} -->.*?"
        rf"<!-- /leccion:{re.escape(leccion_id)} -->(?:\r?\n)?",
        re.DOTALL,
    )
    carpeta_instrucciones = destino / "instrucciones"
    if carpeta_instrucciones.is_dir():
        for ruta in carpeta_instrucciones.glob("*.md"):
            with ruta.open("r", encoding="utf-8") as archivo:
                contenido = archivo.read()
            contenido = patron.sub("", contenido)
            with ruta.open("w", encoding="utf-8", newline="\n") as archivo:
                archivo.write(contenido)

    shutil.rmtree(carpeta_leccion)
    _escribir_config(destino / "config.json", version, modelos)
    return version
