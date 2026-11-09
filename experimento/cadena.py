"""Ejecuta la cadena de problemas y construye sucesores con las lecciones."""

import argparse
from datetime import datetime
from pathlib import Path
import re
import shutil
import subprocess

from comun import config, puertos
from comun.contratos import Leccion, Version
from comun.falsos import problema_falso
from memoria.almacen import Almacen
from memoria.constructor import construir_sucesor
from memoria.curador import curar
from memoria.versiones import cargar_version, crear_v0


def _reiniciar_versiones() -> None:
    raiz = Path(config.RUTA_VERSIONES)
    if not raiz.is_dir():
        return

    patron = re.compile(r"^v[1-9]\d*(-sin-.+)?$")
    carpetas = sorted(
        ruta for ruta in raiz.iterdir() if ruta.is_dir() and patron.fullmatch(ruta.name)
    )
    if not carpetas:
        return

    marca_tiempo = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino_raiz = Path("salidas") / "versiones_anteriores" / marca_tiempo
    movidas = 0
    for carpeta in carpetas:
        resultado = subprocess.run(
            ["git", "ls-files", str(carpeta)],
            capture_output=True,
            text=True,
            check=True,
        )
        if resultado.stdout.strip():
            print(f"AVISO: no se mueve {carpeta}; contiene archivos rastreados por git")
            continue

        destino = destino_raiz / carpeta.name
        if destino.exists():
            raise FileExistsError(f"Ya existe el destino de respaldo: {destino}")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(carpeta), str(destino))
        movidas += 1
        print(f"Movido {carpeta} -> {destino}")
    if movidas == 0:
        print("Reinicio: no había carpetas de versión sin rastrear para mover")


def _cargar_problema(caso: str, permitir_falsos: bool):
    try:
        from datos.problemas import cargar_problema

        return cargar_problema(caso)
    except Exception as error:
        if not permitir_falsos:
            raise RuntimeError(f"No se pudo cargar el problema {caso!r}: {error}") from error
        tipo = "serie" if caso.startswith("demanda") else "clasificacion"
        problema = problema_falso(tipo)
        problema.id = caso
        print(f"AVISO: se usará problema falso para {caso}: {error}")
        return problema


def _seccion_paso(
    numero: int,
    version_usada: Version,
    caso: str,
    ciclo,
    lecciones: list[Leccion],
    version_resultante: Version,
) -> str:
    mejor = ciclo.mejor_resultado
    produccion = ciclo.resultado_produccion
    alertas = mejor.alertas if mejor is not None else []
    lineas = [
        f"## Paso {numero}: {caso}",
        f"- Versión usada: {version_usada.id}",
        f"- Caso: {caso}",
        f"- Costo relativo validación: {mejor.costo_relativo if mejor else 'sin resultado'}",
        f"- Costo relativo producción: {produccion.costo_relativo if produccion else 'sin resultado'}",
        f"- Alertas: {', '.join(alertas) if alertas else 'ninguna'}",
        "- Lecciones:",
    ]
    if lecciones:
        lineas.extend(
            f"  - {leccion.id} (capacidad={leccion.capacidad}): {leccion.texto}"
            for leccion in lecciones
        )
    else:
        lineas.append("  - ninguna")
    lineas.append(f"- Versión resultante: {version_resultante.id}")
    return "\n".join(lineas)


def correr_cadena(
    casos: list[str] = ["credito_a", "churn_a", "demanda_a"],
    version_inicial: str = "v0",
    permitir_falsos: bool = False,
    reiniciar: bool = False,
) -> list[Version]:
    puertos_falsos = [nombre for nombre, falso in puertos.PUERTOS_FALSOS.items() if falso]
    if puertos_falsos and not permitir_falsos:
        raise RuntimeError(f"Hay puertos falsos activos: {', '.join(puertos_falsos)}")
    if puertos_falsos and permitir_falsos:
        print("CADENA CON PUERTOS FALSOS: LOS RESULTADOS NO VALEN")

    if reiniciar:
        _reiniciar_versiones()

    version = crear_v0() if version_inicial == "v0" else cargar_version(version_inicial)
    versiones = [version]
    secciones = ["# Ejecución de la cadena", ""]
    almacen = Almacen()
    try:
        for numero, caso in enumerate(casos, start=1):
            problema = _cargar_problema(caso, permitir_falsos)
            version_usada = version
            ciclo = puertos.resolver(
                problema,
                version,
                run_id=f"cadena-{version.id}-{caso}",
            )
            if ciclo.mejor_candidato is None or ciclo.mejor_resultado is None:
                raise RuntimeError(f"El ciclo de {caso!r} no devolvió el mejor candidato y resultado")
            if ciclo.resultado_produccion is None:
                raise RuntimeError(f"El ciclo de {caso!r} no devolvió resultado de producción")

            print(
                f"Versión {version.id} | caso {caso} | modelo {ciclo.mejor_candidato.modelo} | "
                f"validación={ciclo.mejor_resultado.costo_relativo:.3f} | "
                f"producción={ciclo.resultado_produccion.costo_relativo:.3f} | "
                f"alertas={ciclo.mejor_resultado.alertas}"
            )
            lecciones = curar(problema, ciclo, version, almacen)
            for leccion in lecciones:
                print(
                    f"Lección {leccion.id} | capacidad={leccion.capacidad} | "
                    f"regla_para={leccion.regla_para} | {leccion.texto}"
                )

            sucesor = construir_sucesor(version, lecciones, almacen=almacen)
            if sucesor.id == version.id:
                print("sin lecciones nuevas: la versión no cambia")
            else:
                ruta_cambios = Path(config.RUTA_VERSIONES) / sucesor.id / "cambios.md"
                print(f"Cambios de versión: {ruta_cambios}")
                versiones.append(sucesor)

            secciones.append(
                _seccion_paso(numero, version_usada, caso, ciclo, lecciones, sucesor)
            )
            secciones.append("")
            version = sucesor

        carpeta_salidas = Path("salidas")
        carpeta_salidas.mkdir(parents=True, exist_ok=True)
        ruta_cadena = carpeta_salidas / "cadena.md"
        with ruta_cadena.open("w", encoding="utf-8", newline="\n") as archivo:
            archivo.write("\n".join(secciones).rstrip() + "\n")
        return versiones
    finally:
        almacen.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta la cadena de aprendizaje RSI")
    parser.add_argument(
        "--casos",
        nargs="+",
        default=["credito_a", "churn_a", "demanda_a"],
        help="Ids de problemas a procesar, en orden",
    )
    parser.add_argument("--permitir-falsos", action="store_true")
    parser.add_argument("--reiniciar", action="store_true")
    argumentos = parser.parse_args()
    correr_cadena(
        casos=argumentos.casos,
        permitir_falsos=argumentos.permitir_falsos,
        reiniciar=argumentos.reiniciar,
    )


if __name__ == "__main__":
    main()
