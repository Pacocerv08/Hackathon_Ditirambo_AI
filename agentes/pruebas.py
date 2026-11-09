"""Verificaciones locales de agentes, sin red ni llave de API."""

import os
os.environ["USAR_FALSOS"] = "1"

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agents import AgentOutputSchema

from agentes import analista, diagnostico, fijo, proponente
from agentes.contexto import ContextoCiclo
from agentes.esquemas import Descripcion, Diagnostico, Propuesta
from agentes.herramientas import _compacto
from comun.contratos import Capacidades, Version
from comun.falsos import problema_falso
from memoria.almacen import Almacen
from agentes.ciclo import resolver_sync


def _contexto(tipo="clasificacion", almacen=None):
    return ContextoCiclo(
        problema=problema_falso(tipo),
        version=Version(id="v0", padre=None, capacidades=Capacidades(),
                        lecciones_activas=[], creada_por="equipo", cambios=[]),
        run_id="pruebas", almacen=almacen,
    )


def _candidatos_distintos(candidatos):
    return len(candidatos) == 3 and len({fijo.clave_candidato(c) for c in candidatos}) == 3


async def _fallo(*args, **kwargs):
    raise RuntimeError("fallo simulado")


async def _duplicados(*args, **kwargs):
    c = fijo.proponer(_contexto()).candidatos[0]
    return Propuesta(candidatos=[c, c, c])


def main():
    verificaciones = []
    def verificar(nombre, funcion):
        try:
            funcion()
            verificaciones.append((nombre, True, ""))
        except Exception as exc:
            verificaciones.append((nombre, False, f"{type(exc).__name__}: {exc}"))

    def propuesta_fija():
        for tipo in ("clasificacion", "serie"):
            assert _candidatos_distintos(fijo.proponer(_contexto(tipo)).candidatos)
    verificar("fijo propone tres distintos en ambas tareas", propuesta_fija)

    def historial_fijo():
        ctx = _contexto()
        primero = fijo.proponer(ctx).candidatos
        ctx.historial.extend((c, None) for c in primero)
        segundo = fijo.proponer(ctx).candidatos
        assert _candidatos_distintos(segundo)
        assert not ({fijo.clave_candidato(c) for c in primero} & {fijo.clave_candidato(c) for c in segundo})
        while True:
            try:
                lote = fijo.proponer(ctx).candidatos
                ctx.historial.extend((c, None) for c in lote)
            except fijo.SinCandidatosNuevos:
                return
    verificar("fijo evita historial y detecta agotamiento", historial_fijo)

    def proponente_fallback():
        async def run():
            ctx = _contexto()
            ctx.historial.extend((c, None) for c in fijo.proponer(ctx).candidatos)
            with patch.object(proponente, "_llamar_modelo", _fallo):
                resultado = await proponente.proponer_con_llm(ctx, Descripcion(resumen="x", riesgos=[]), None)
            assert _candidatos_distintos(resultado.candidatos)
            assert not ({fijo.clave_candidato(c) for c in resultado.candidatos} & {fijo.clave_candidato(c) for c, _ in ctx.historial})
        asyncio.run(run())
    verificar("respaldo fijo respeta historial", proponente_fallback)

    def proponente_reemplaza():
        async def run():
            ctx = _contexto()
            previos = fijo.proponer(ctx).candidatos
            ctx.historial.extend((c, None) for c in previos)
            with patch.object(proponente, "_llamar_modelo", _duplicados):
                resultado = await proponente.proponer_con_llm(ctx, Descripcion(resumen="x", riesgos=[]), None)
            assert _candidatos_distintos(resultado.candidatos)
            assert not ({fijo.clave_candidato(c) for c in resultado.candidatos} & {fijo.clave_candidato(c) for c in previos})
        asyncio.run(run())
    verificar("proponente reemplaza duplicados del modelo", proponente_reemplaza)

    def respaldos_y_compacto():
        async def run():
            ctx = _contexto()
            with patch.object(analista, "_llamar_modelo", _fallo):
                assert isinstance(await analista.describir(ctx), Descripcion)
            with patch.object(diagnostico, "_llamar_modelo", _fallo):
                salida = await diagnostico.diagnosticar(ctx, [])
                assert isinstance(salida, Diagnostico) and salida.seguir is True
        asyncio.run(run())
        salida = json.loads(_compacto(["x" * 200 for _ in range(1000)], limite=100))
        assert any(isinstance(x, dict) and "omitidas" in x for x in salida)
    verificar("respaldos de analista/diagnóstico y JSON compacto", respaldos_y_compacto)

    def esquema_estricto():
        for modelo in (Propuesta, Descripcion, Diagnostico):
            AgentOutputSchema(modelo, strict_json_schema=True).json_schema()
    verificar("esquemas estrictos offline", esquema_estricto)

    def ciclo_y_almacen():
        with TemporaryDirectory() as directorio:
            ruta = str(Path(directorio) / "memoria.db")
            with patch("agentes.ciclo.Almacen", lambda: Almacen(ruta)), \
                 patch("agentes.ciclo.evaluar", wraps=__import__("comun.falsos", fromlist=["evaluar_falso"]).evaluar_falso):
                ciclo = resolver_sync(problema_falso("clasificacion"), _contexto().version, "run-prueba")
            assert ciclo.mejor_candidato is not None and ciclo.mejor_resultado is not None
            assert ciclo.mejor_resultado.costo is not None and ciclo.resultado_produccion is not None
            db = Almacen(ruta)
            llamadas = db._conexion.execute("SELECT COUNT(*) FROM llamadas").fetchone()[0]
            ejecuciones = db._conexion.execute("SELECT COUNT(*) FROM ejecuciones").fetchone()[0]
            assert llamadas >= 3 and ejecuciones == 1
            db.close()
    verificar("resolver_sync completa y persiste en Almacen temporal", ciclo_y_almacen)

    for nombre, ok, detalle in verificaciones:
        print(f"[{'OK' if ok else 'FALLA'}] {nombre}" + (f" — {detalle}" if detalle else ""))
    exitos = sum(ok for _, ok, _ in verificaciones)
    print(f"{exitos} de {len(verificaciones)} verificaciones OK")
    return 0 if exitos == len(verificaciones) else 1


if __name__ == "__main__":
    raise SystemExit(main())
