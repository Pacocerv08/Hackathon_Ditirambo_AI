"""Ciclo de evaluación con agentes LLM y respaldos deterministas."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import sys
import time

from comun import config
from comun.contratos import Capacidades, Problema, ResultadoCiclo, Version
from comun.puertos import evaluar
from agentes.contexto import ContextoCiclo
from agentes.fijo import SinCandidatosNuevos
from agentes.analista import describir
from agentes.diagnostico import diagnosticar
from agentes.esquemas import Diagnostico
from agentes.proponente import proponer_con_llm

try:
    from memoria.almacen import Almacen
except ImportError:
    class Almacen:  # type: ignore[no-redef]
        """Almacén provisional mientras memoria todavía no está disponible."""

        def iniciar_ejecucion(self, *args, **kwargs) -> None:
            print("[ALMACEN FALSO] iniciar_ejecucion", args, kwargs)

        def guardar_resultado(self, *args, **kwargs) -> None:
            print("[ALMACEN FALSO] guardar_resultado", args, kwargs)

        def guardar_llamada(self, *args, **kwargs) -> None:
            print("[ALMACEN FALSO] guardar_llamada", args, kwargs)


try:
    from agents import trace
except ImportError:
    trace = None


async def resolver(
    problema: Problema, version: Version, run_id: str | None = None
) -> ResultadoCiclo:
    if run_id is None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        run_id = f"{version.id}-{problema.id}-{timestamp}"

    almacen = Almacen()
    almacen.iniciar_ejecucion(run_id, version.id, problema.id)
    ctx = ContextoCiclo(problema=problema, version=version, run_id=run_id, almacen=almacen)
    limite = asyncio.Semaphore(3)
    mejor_candidato = None
    mejor_resultado = None
    sin_mejora = 0
    historial_resultados = []
    diagnosticos: list[str] = []
    traza = trace(f"{version.id}-{problema.id}") if trace else nullcontext()

    with traza:
        inicio = time.perf_counter()
        descripcion = await describir(ctx)
        almacen.guardar_llamada(
            run_id,
            "analista",
            problema.model_dump_json(),
            descripcion.model_dump_json(),
            time.perf_counter() - inicio,
        )
        ultimo_diagnostico: Diagnostico | None = None

        for _ in range(config.MAX_ITERACIONES):
            inicio = time.perf_counter()
            try:
                propuesta = await proponer_con_llm(
                    ctx, descripcion, ultimo_diagnostico
                )
            except SinCandidatosNuevos:
                break
            almacen.guardar_llamada(
                run_id,
                "proponente",
                json.dumps(
                    {
                        "descripcion": descripcion.model_dump(),
                        "ultimo_diagnostico": (
                            ultimo_diagnostico.model_dump()
                            if ultimo_diagnostico is not None
                            else None
                        ),
                        "intentos": len(ctx.historial),
                    },
                    ensure_ascii=False,
                ),
                propuesta.model_dump_json(),
                time.perf_counter() - inicio,
            )

            async def evaluar_limitado(candidato):
                async with limite:
                    return await asyncio.to_thread(
                        evaluar,
                        problema,
                        candidato,
                        version.capacidades,
                        modo="validacion",
                        version=version.id,
                    )

            resultados = await asyncio.gather(
                *(evaluar_limitado(candidato) for candidato in propuesta.candidatos)
            )

            # Toda escritura sucede aquí, en el hilo del ciclo, después del gather.
            for candidato, resultado in zip(propuesta.candidatos, resultados):
                almacen.guardar_resultado(run_id, candidato, resultado)
                ctx.historial.append((candidato, resultado))
                historial_resultados.append(resultado)

            anterior = mejor_resultado
            for candidato, resultado in zip(propuesta.candidatos, resultados):
                if resultado.error is not None:
                    continue
                if mejor_resultado is None or resultado.costo_relativo < mejor_resultado.costo_relativo:
                    mejor_candidato, mejor_resultado = candidato, resultado
            if anterior is not None and mejor_resultado is not anterior:
                sin_mejora = 0
            elif anterior is not None:
                sin_mejora += 1

            inicio = time.perf_counter()
            diagnostico = await diagnosticar(ctx, resultados)
            almacen.guardar_llamada(
                run_id,
                "diagnostico",
                json.dumps(
                    [
                        {
                            "candidato_id": resultado.candidato_id,
                            "costo_relativo": resultado.costo_relativo,
                            "alertas": resultado.alertas,
                            "error": resultado.error,
                        }
                        for resultado in resultados
                    ],
                    ensure_ascii=False,
                ),
                diagnostico.model_dump_json(),
                time.perf_counter() - inicio,
            )
            diagnosticos.append(diagnostico.model_dump_json())
            ultimo_diagnostico = diagnostico
            if sin_mejora >= config.PARAR_SI_NO_MEJORA or not diagnostico.seguir:
                break

        produccion = None
        if mejor_candidato is not None:
            produccion = await asyncio.to_thread(
                evaluar,
                problema,
                mejor_candidato,
                version.capacidades,
                modo="produccion",
                version=version.id,
            )
            almacen.guardar_resultado(run_id, mejor_candidato, produccion)

    return ResultadoCiclo(
        problema_id=problema.id,
        version=version.id,
        run_id=run_id,
        mejor_candidato=mejor_candidato,
        mejor_resultado=mejor_resultado,
        historial=historial_resultados,
        diagnosticos=diagnosticos,
        resultado_produccion=produccion,
    )


def resolver_sync(
    problema: Problema, version: Version, run_id: str | None = None
) -> ResultadoCiclo:
    return asyncio.run(resolver(problema, version, run_id))


def _cargar_desde_modulo(modulo: str, funcion: str, identificador: str):
    try:
        return getattr(importlib.import_module(modulo), funcion)(identificador)
    except (ImportError, AttributeError) as exc:
        raise LookupError(f"No está disponible {modulo}.{funcion}") from exc


def _argumentos_cli(argumentos: list[str]) -> tuple[Problema, Version]:
    if len(argumentos) != 2:
        raise SystemExit("Uso: python -m agentes.ciclo <problema_id> <version_id>")
    problema_id, version_id = argumentos

    ruta_config = Path(config.RUTA_VERSIONES) / version_id / "config.json"
    if not ruta_config.is_file():
        comando = 'python -c "from memoria.versiones import crear_v0; crear_v0()"' if version_id == "v0" else f"Crea {ruta_config} con memoria.versiones."
        raise SystemExit(f"Falta la configuración de {version_id}: {ruta_config}.\nCorre: {comando}")
    try:
        problema = _cargar_desde_modulo(
            "datos.problemas", "cargar_problema", problema_id
        )
    except LookupError as exc:
        raise SystemExit(
            f"No existe el problema '{problema_id}'. Corre: "
            "python -m datos.problemas para ver los ids disponibles."
        ) from exc

    try:
        version = _cargar_desde_modulo(
            "memoria.versiones", "cargar_version", version_id
        )
    except LookupError as exc:
        raise SystemExit(f"No se pudo cargar la versión {version_id!r}: {exc}.") from exc

    if problema is None or version is None:
        from comun.falsos import problema_falso

        if problema is None:
            print(
                f"[CLI FALSO] {problema_id}: usando problema_falso('clasificacion')"
            )
            problema = problema_falso("clasificacion")
        if version is None:
            print(f"[CLI FALSO] {version_id}: usando configuración de versión local")
            version = Version(
                id=version_id,
                padre=None,
                capacidades=Capacidades(),
                lecciones_activas=[],
                creada_por="equipo",
                cambios=["Versión local de respaldo para ejecución falsa"],
            )
    return problema, version


def main(argumentos: list[str] | None = None) -> int:
    problema, version = _argumentos_cli(
        sys.argv[1:] if argumentos is None else argumentos
    )
    resultado = resolver_sync(problema, version)
    print(f"Problema: {resultado.problema_id} | Versión: {resultado.version}")
    if resultado.mejor_candidato is None or resultado.mejor_resultado is None:
        print("Mejor candidato: ninguno")
        print("Costo relativo en validación: no disponible")
    else:
        print(f"Mejor candidato: {resultado.mejor_candidato.model_dump_json()}")
        print(
            "Costo relativo en validación: "
            f"{resultado.mejor_resultado.costo_relativo:.4f}"
        )
    if resultado.resultado_produccion is None:
        print("Costo relativo en producción: no disponible")
    else:
        print(
            "Costo relativo en producción: "
            f"{resultado.resultado_produccion.costo_relativo:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["resolver", "resolver_sync", "main"]
