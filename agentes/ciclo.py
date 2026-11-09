"""Ciclo de evaluación sin LLM para la primera entrega de agentes."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from datetime import datetime, timezone
import json
import time

from comun import config
from comun.contratos import Problema, ResultadoCiclo, Version
from comun.puertos import evaluar
from agentes.contexto import ContextoCiclo
from agentes.fijo import SinCandidatosNuevos, proponer
from agentes.esquemas import Diagnostico

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
        for _ in range(config.MAX_ITERACIONES):
            inicio = time.perf_counter()
            try:
                propuesta = proponer(ctx)
            except SinCandidatosNuevos:
                break
            almacen.guardar_llamada(
                run_id,
                "proponente",
                json.dumps({"intentos": len(ctx.historial)}, ensure_ascii=False),
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

            diagnostico = Diagnostico(
                que_fallo="",
                por_que="",
                evidencia=[],
                que_probar="",
                seguir=True,
            )
            diagnosticos.append(diagnostico.model_dump_json())
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


__all__ = ["resolver", "resolver_sync"]
