"""Smoke test manual de conexión real a los tres agentes."""

import os
import asyncio
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

if not os.getenv("OPENAI_API_KEY"):
    print("Falta OPENAI_API_KEY. Configúrala para ejecutar este smoke test.")
    raise SystemExit(2)

from agentes.contexto import ContextoCiclo
from agentes.analista import _llamar_modelo as llamar_analista
from agentes.proponente import _llamar_modelo as llamar_proponente
from agentes.diagnostico import _llamar_modelo as llamar_diagnostico
from agentes.esquemas import Descripcion, Diagnostico, Propuesta
from agentes.fijo import proponer as proponer_fijo
from comun import config
from comun.contratos import Capacidades, Candidato, Resultado, Version
from comun.falsos import evaluar_falso, problema_falso
from memoria.almacen import Almacen


def main():
    print(f"MODELOS: {config.MODELOS}")
    problema = problema_falso("clasificacion")
    directorio = TemporaryDirectory()
    almacen = Almacen(str(Path(directorio.name) / "memoria.db"))
    version = Version(id="v0", padre=None, capacidades=Capacidades(),
                      lecciones_activas=[], creada_por="equipo", cambios=[])
    almacen.iniciar_ejecucion("smoke-llm", version.id, problema.id)
    candidato_fijo = proponer_fijo(
        ContextoCiclo(problema=problema, version=version, run_id="smoke-llm", almacen=almacen)
    ).candidatos[0]
    candidatos = [candidato_fijo]
    for modelo in ("referencia", "logistica"):
        candidato = Candidato(
            modelo=modelo, justificacion="Registro falso para smoke test."
        )
        resultado = evaluar_falso(problema, candidato, version.capacidades, version=version.id)
        almacen.guardar_resultado("smoke-llm", candidato, resultado)
        candidatos.append(candidato)
    ctx = ContextoCiclo(
        problema=problema, version=version, run_id="smoke-llm", almacen=almacen,
        historial=[
            (candidato, evaluar_falso(problema, candidato, version.capacidades, version=version.id))
            for candidato in candidatos
        ],
    )
    tabla = []

    async def ejecutar(nombre, funcion, entrada, esquema, resumen):
        inicio = time.perf_counter()
        try:
            salida = await funcion(ctx, entrada)
            esquema.model_validate(salida.model_dump())
            segundos = time.perf_counter() - inicio
            print(f"{nombre}: {resumen(salida)}")
            tabla.append((nombre, "OK", segundos))
        except Exception as exc:
            segundos = time.perf_counter() - inicio
            print(f"{nombre}: {type(exc).__name__}: {exc}")
            tabla.append((nombre, "FALLA", segundos))

    async def correr():
        await ejecutar("analista", llamar_analista, "Resume el problema y sus riesgos.", Descripcion,
                       lambda s: f"esquema válido; resumen={s.resumen[:100]!r}")
        await ejecutar("proponente", llamar_proponente, '{"smoke": true}', Propuesta,
                       lambda s: f"esquema válido; candidatos={len(s.candidatos)}")
        resultados = [Resultado(
            problema_id=problema.id, candidato_id="smoke", version="v0", modo="validacion",
            costo=10, costo_referencia=20, costo_relativo=0.5, resuelto=True,
        )]
        await ejecutar("diagnostico", llamar_diagnostico, json.dumps([
            {"candidato_id": r.candidato_id, "costo_relativo": r.costo_relativo,
             "alertas": r.alertas, "error": r.error} for r in resultados
        ]), Diagnostico, lambda s: f"esquema válido; seguir={s.seguir}")

    asyncio.run(correr())
    almacen.close()
    directorio.cleanup()
    print("\nagente | estado | segundos")
    for nombre, estado, segundos in tabla:
        print(f"{nombre} | {estado} | {segundos:.2f}")
    return 0 if all(estado == "OK" for _, estado, _ in tabla) else 1


if __name__ == "__main__":
    raise SystemExit(main())
