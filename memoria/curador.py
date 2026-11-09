"""Propone lecciones a partir de resultados y las valida antes de guardarlas."""

import json
from pathlib import Path
import re
from time import perf_counter
from typing import Literal

from pydantic import BaseModel, Field

from comun import config
from comun.contratos import (
    Leccion,
    NombreAgente,
    NombreCapacidad,
    Problema,
    ResultadoCiclo,
    Version,
)


class LeccionPropuesta(BaseModel):
    senal: str = Field(description="Señal observable que reveló la falla")
    evidencia: list[str] = Field(description="Ids de candidatos del historial que sustentan la lección")
    texto: str = Field(description="Lección breve y transferible a problemas futuros")
    tipo_cambio: Literal["regla", "chequeo", "variable", "flujo"] = Field(
        description="Tipo de cambio que debe producir la lección"
    )
    capacidad: NombreCapacidad | None = Field(
        default=None,
        description="Capacidad disponible que corresponde activar, si la evidencia la justifica",
    )
    regla_para: list[NombreAgente] = Field(
        default_factory=list,
        description="Agentes que deben recibir la regla",
    )
    alcance: Literal["general", "clasificacion", "serie"] = Field(
        default="general",
        description="Tipos de problema a los que se aplica la lección",
    )


class PropuestaCurador(BaseModel):
    lecciones: list[LeccionPropuesta] = Field(description="0 a 2 lecciones")


def _validar(
    propuestas: list[LeccionPropuesta],
    problema: Problema,
    ciclo: ResultadoCiclo,
    version: Version,
    ids_existentes: list[str],
) -> list[Leccion]:
    evidencia_disponible = {resultado.candidato_id for resultado in ciclo.historial}
    if ciclo.resultado_produccion is not None:
        evidencia_disponible.add(ciclo.resultado_produccion.candidato_id)

    nombres_prohibidos = {
        nombre.casefold()
        for nombre in (problema.id, problema.dominio, problema.dominio.replace("_", " "))
        if nombre
    }
    numeros_existentes = [
        int(coincidencia.group(1))
        for existente in ids_existentes
        if (coincidencia := re.fullmatch(r"L(\d+)", existente)) is not None
    ]
    siguiente = max(numeros_existentes, default=0) + 1

    aceptadas: list[Leccion] = []
    for propuesta in propuestas:
        if not propuesta.evidencia or not all(
            evidencia in evidencia_disponible for evidencia in propuesta.evidencia
        ):
            continue
        if propuesta.capacidad is not None and getattr(version.capacidades, propuesta.capacidad):
            continue
        texto_casefold = propuesta.texto.casefold()
        if any(nombre in texto_casefold for nombre in nombres_prohibidos):
            continue
        if len(aceptadas) >= 2:
            break

        aceptadas.append(
            Leccion(
                id=f"L{siguiente:03d}",
                version_origen=version.id,
                problema_origen=problema.id,
                senal=propuesta.senal,
                evidencia=propuesta.evidencia,
                texto=propuesta.texto,
                tipo_cambio=propuesta.tipo_cambio,
                capacidad=propuesta.capacidad,
                regla_para=propuesta.regla_para,
                alcance=propuesta.alcance,
            )
        )
        siguiente += 1
    return aceptadas


def _resumen(
    problema: Problema,
    ciclo: ResultadoCiclo,
    version: Version,
    lecciones_actuales: list[Leccion],
) -> str:
    costos = problema.costos.model_dump(mode="json")
    resultados = sorted(ciclo.historial, key=lambda resultado: resultado.costo_relativo)[:5]
    lineas = [
        f"Problema: {problema.descripcion_negocio}",
        f"Tipo de tarea: {problema.tipo_tarea}",
        f"Costos: {json.dumps(costos, ensure_ascii=False, separators=(',', ':'))}",
        "Mejores resultados del historial (por costo relativo):",
    ]
    for resultado in resultados:
        datos = {
            "candidato_id": resultado.candidato_id,
            "costo_relativo": resultado.costo_relativo,
            "metricas": resultado.metricas,
            "alertas": resultado.alertas,
        }
        lineas.append(json.dumps(datos, ensure_ascii=False, separators=(",", ":")))

    lineas.append("Diagnósticos:")
    lineas.extend(f"- {diagnostico}" for diagnostico in ciclo.diagnosticos)

    validacion = ciclo.mejor_resultado.costo_relativo if ciclo.mejor_resultado else None
    produccion = ciclo.resultado_produccion.costo_relativo if ciclo.resultado_produccion else None
    diferencia = produccion - validacion if produccion is not None and validacion is not None else None
    lineas.append(
        "Validación vs producción del mejor candidato: "
        f"validación={validacion}, producción={produccion}, diferencia={diferencia}"
    )

    capacidades = version.capacidades.model_dump()
    apagadas = [nombre for nombre, activa in capacidades.items() if not activa]
    lineas.append(
        "Capacidades disponibles: "
        f"{', '.join(capacidades)}. Apagadas en esta versión: {', '.join(apagadas) or 'ninguna'}."
    )
    lineas.append("Lecciones actuales:")
    lineas.extend(f"- {leccion.id}: {leccion.texto}" for leccion in lecciones_actuales)

    resumen = "\n".join(lineas)
    if len(resumen) > 2900:
        resumen = resumen[:2897].rstrip() + "..."
    return resumen


def _parsear_salida(salida) -> PropuestaCurador:
    if isinstance(salida, PropuestaCurador):
        return salida
    if isinstance(salida, str):
        return PropuestaCurador.model_validate_json(salida)
    if isinstance(salida, BaseModel):
        salida = salida.model_dump(mode="python")
    return PropuestaCurador.model_validate(salida)


def curar(
    problema: Problema,
    ciclo: ResultadoCiclo,
    version: Version,
    almacen,
) -> list[Leccion]:
    lecciones_actuales = almacen.lecciones(version.lecciones_activas)
    resumen = _resumen(problema, ciclo, version, lecciones_actuales)

    try:
        from agents import Agent, Runner

        instrucciones_path = Path(__file__).with_name("instrucciones_curador.md")
        with instrucciones_path.open("r", encoding="utf-8") as archivo:
            instrucciones = archivo.read()
        agente = Agent(
            name="curador",
            instructions=instrucciones,
            model=config.MODELOS["curador"],
            output_type=PropuestaCurador,
        )
        inicio = perf_counter()
        resultado_runner = Runner.run_sync(agente, resumen)
        segundos = perf_counter() - inicio
        propuesta = _parsear_salida(resultado_runner.final_output)
        salida_json = propuesta.model_dump_json()
        almacen.guardar_llamada(ciclo.run_id, "curador", resumen, salida_json, segundos)
    except Exception as error:
        print(f"[CURADOR] advertencia: no se pudieron proponer lecciones: {error}")
        return []

    lecciones = _validar(
        propuesta.lecciones,
        problema,
        ciclo,
        version,
        ids_existentes=almacen.ids_lecciones(),
    )
    for leccion in lecciones:
        almacen.guardar_leccion(leccion)
    return lecciones
