"""Verificaciones locales de agentes, sin red ni llave de API."""

import os
os.environ["USAR_FALSOS"] = "1"

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from agents import AgentOutputSchema

from agentes import analista, diagnostico, entradas, fijo, proponente
from agentes.contexto import ContextoCiclo
from agentes.esquemas import Descripcion, Diagnostico, Propuesta
from agentes.herramientas import _compacto
from comun import config
from comun.contratos import Candidato, Capacidades, Hiperparametro, PeorCaso, Resultado, Version
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
            ctx.historial.extend((c, Resultado(
                problema_id=ctx.problema.id, candidato_id=f"previo-{i}", version="v0",
                modo="validacion", costo=1, costo_referencia=2, costo_relativo=0.5,
                resuelto=True,
            )) for i, c in enumerate(fijo.proponer(ctx).candidatos))
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
            ctx.historial.extend((c, Resultado(
                problema_id=ctx.problema.id, candidato_id=f"previo-{i}", version="v0",
                modo="validacion", costo=1, costo_referencia=2, costo_relativo=0.5,
                resuelto=True,
            )) for i, c in enumerate(previos))
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

    def entradas_autocontenidas():
        for tipo in ("clasificacion", "serie"):
            ctx = _contexto(tipo)
            r = Resultado(problema_id=ctx.problema.id, candidato_id="c1", version="v0",
                          modo="validacion", costo=1, costo_referencia=2,
                          costo_relativo=0.5, resuelto=True)
            textos = [entradas.entrada_analista(ctx),
                      entradas.entrada_proponente(ctx, Descripcion(resumen="x", riesgos=[]), None),
                      entradas.entrada_diagnostico(ctx, [r])]
            for texto in textos:
                assert len(texto) <= 12000
                assert "## Problema" in texto
            assert all("## " in texto for texto in textos)
            assert "## Resumen de datos" in textos[0] and "## Lecciones activas" in textos[0]
            assert "## Ya probado (no repetir)" in textos[1]
            assert "## Peores casos" in textos[2]
        assert "Contexto de fechas" in entradas.entrada_diagnostico(_contexto("serie"), [r])
    verificar("entradas autocontenidas para clasificación y serie", entradas_autocontenidas)

    def entrada_diagnostico_elige_validos():
        def resultado(ctx, cid, relativo, error=None, fecha="2026-01-15"):
            return Resultado(
                problema_id=ctx.problema.id, candidato_id=cid, version="v0", modo="validacion",
                costo=relativo, costo_referencia=1, costo_relativo=relativo, resuelto=False,
                error=error,
                peores_casos=[PeorCaso(referencia=fecha, real=10, predicho=2, costo=8)],
            )
        ctx = _contexto("serie")
        con_error = resultado(ctx, "error", 999.0, "falló")
        valido_alto = resultado(ctx, "valido-alto", 0.8, fecha="2026-02-01")
        valido_bajo = resultado(ctx, "valido-bajo", 0.2, fecha="2026-01-15")
        ctx.historial.extend((Candidato(modelo="referencia", justificacion=cid), r)
                             for cid, r in (("error", con_error), ("valido-alto", valido_alto), ("valido-bajo", valido_bajo)))
        texto = entradas.entrada_diagnostico(ctx, [con_error, valido_alto, valido_bajo])
        seccion = texto.split("## Peores casos\n", 1)[1].split("\n\n## ", 1)[0]
        assert "valido-bajo" in seccion and "valido-alto" in seccion
        assert "error\"" not in seccion and "999.0" not in seccion
        fechas = texto.split("## Contexto de fechas\n", 1)[1].split("\n\n## ", 1)[0]
        assert fechas not in ("[]", "no disponible") and "2026-01-15" in fechas

        fallidos = entradas.entrada_diagnostico(ctx, [con_error])
        assert "sin candidatos válidos en este lote" in fallidos
    verificar("diagnóstico elige dos válidos de menor costo y fechas reales", entrada_diagnostico_elige_validos)

    def entrada_proponente_configuraciones():
        ctx = _contexto()
        for i in range(30):
            candidato = Candidato(
                modelo="logistica" if i == 0 else "arbol",
                justificacion=f"intento {i}",
                features=[f"feature_{i}"],
                excluir_columnas=[f"col_{i}"],
                hiperparametros=[Hiperparametro(nombre="C", valor=0.75 + i)],
            )
            resultado = Resultado(
                problema_id=ctx.problema.id, candidato_id=f"c{i}", version="v0", modo="validacion",
                costo=1, costo_referencia=2, costo_relativo=0.5 + i / 100,
                resuelto=True, alertas=["a", "b", "c", "d"],
            )
            ctx.historial.append((candidato, resultado))
        texto = entradas.entrada_proponente(ctx, Descripcion(resumen="breve", riesgos=[]), None)
        seccion = texto.split("## Ya probado (no repetir)\n", 1)[1].split("\n\n## ", 1)[0]
        assert "logistica" in seccion and '"valor":0.75' in seccion
        assert len(texto) <= 12000
        assert texto.index("## Ya probado") < texto.index("## Último diagnóstico") < texto.index("## Lecciones activas")
        assert "justificacion" not in seccion
    verificar("proponente incluye configuraciones breves ya probadas", entrada_proponente_configuraciones)

    def backends_adaptadores():
        async def run():
            ctx = _contexto()
            obj_a = Descripcion(resumen="fijo", riesgos=[])
            obj_p = fijo.proponer(_contexto())
            obj_d = Diagnostico(que_fallo="x", por_que="y", evidencia=[], que_probar="z", seguir=True)
            esperados = {"analista": (obj_a, Descripcion), "proponente": (obj_p, Propuesta), "diagnostico": (obj_d, Diagnostico)}
            for modulo, nombre, funcion, args in (
                (analista, "analista", analista._llamar_modelo, (ctx, "entrada")),
                (proponente, "proponente", proponente._llamar_modelo, (ctx, "entrada")),
                (diagnostico, "diagnostico", diagnostico._llamar_modelo, (ctx, "entrada")),
            ):
                llamadas = []
                async def falso(agente, instrucciones, entrada, esquema, **kwargs):
                    llamadas.append((agente, instrucciones, entrada, esquema))
                    return esperados[agente][0]
                with patch.object(config, "LLM_BACKEND", "codex"), patch.object(modulo, "allamar_modelo", falso):
                    salida = await funcion(*args)
                llamada = llamadas[0]
                assert salida is esperados[nombre][0], (nombre, type(salida), llamadas)
                assert llamada[0] == nombre and "En este entorno no tienes herramientas" in llamada[1]
                assert llamada[2] and llamada[3] is esperados[nombre][1]

            for modulo, funcion, args in (
                (analista, analista._llamar_modelo, (ctx, "entrada")),
                (proponente, proponente._llamar_modelo, (ctx, "entrada")),
                (diagnostico, diagnostico._llamar_modelo, (ctx, "entrada")),
            ):
                with patch.object(config, "LLM_BACKEND", "codex"), patch.object(modulo, "allamar_modelo", _fallo):
                    try:
                        await funcion(*args)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("se esperaba el fallo simulado")

            with patch.object(config, "LLM_BACKEND", "codex"), patch.object(analista, "allamar_modelo", _fallo):
                assert isinstance(await analista.describir(ctx), Descripcion)
            with patch.object(config, "LLM_BACKEND", "codex"), patch.object(proponente, "allamar_modelo", _fallo):
                assert _candidatos_distintos((await proponente.proponer_con_llm(
                    ctx, Descripcion(resumen="x", riesgos=[]), None
                )).candidatos)
            with patch.object(config, "LLM_BACKEND", "codex"), patch.object(diagnostico, "allamar_modelo", _fallo):
                assert (await diagnostico.diagnosticar(ctx, [])).seguir

            # El backend API usa Runner local y nunca llama allamar_modelo.
            class RunnerFalso:
                @staticmethod
                async def run(agente, entrada, **kwargs):
                    return type("Salida", (), {"final_output": esperados[agente.name.lower() if agente.name != "Diagnóstico" else "diagnostico"][0]})()
            for modulo, nombre, funcion, args in (
                (analista, "analista", analista._llamar_modelo, (ctx, "entrada")),
                (proponente, "proponente", proponente._llamar_modelo, (ctx, "entrada")),
                (diagnostico, "diagnostico", diagnostico._llamar_modelo, (ctx, "entrada")),
            ):
                with patch.object(config, "LLM_BACKEND", "api"), \
                     patch.object(modulo, "allamar_modelo", side_effect=AssertionError("allamar_modelo en API")), \
                     patch.object(modulo, "Runner", RunnerFalso):
                    await funcion(*args)
        asyncio.run(run())
    verificar("adaptadores Codex y API sin llamadas reales", backends_adaptadores)

    def clientes_api_por_llamada_y_cierre():
        ctx = _contexto()
        salidas = {
            "Analista": Descripcion(resumen="ok", riesgos=[]),
            "Proponente": fijo.proponer(ctx),
            "Diagnóstico": Diagnostico(que_fallo="", por_que="", evidencia=[], que_probar="", seguir=True),
        }

        class ClienteFalso:
            def __init__(self):
                self.cierres = 0

            async def close(self):
                self.cierres += 1

        clientes = []

        def crear_cliente():
            cliente = ClienteFalso()
            clientes.append(cliente)
            return cliente

        class RunnerFalso:
            falla = False

            @classmethod
            async def run(cls, agente, entrada, **kwargs):
                if cls.falla:
                    raise RuntimeError("fallo Runner simulado")
                return type("Salida", (), {"final_output": salidas[agente.name]})()

        def llamada_en_loop_propio(funcion, args):
            return asyncio.run(funcion(*args))

        modulos = (
            (analista, analista._llamar_modelo, (ctx, "entrada")),
            (proponente, proponente._llamar_modelo, (ctx, "entrada")),
            (diagnostico, diagnostico._llamar_modelo, (ctx, "entrada")),
        )
        with patch.object(config, "LLM_BACKEND", "api"), \
             patch("agentes.cliente.AsyncOpenAI", side_effect=crear_cliente):
            for modulo, funcion, args in modulos:
                with patch.object(modulo, "Runner", RunnerFalso):
                    llamada_en_loop_propio(funcion, args)
                    llamada_en_loop_propio(funcion, args)
            assert len(clientes) == 6
            assert len({id(cliente) for cliente in clientes}) == len(clientes)
            assert all(cliente.cierres == 1 for cliente in clientes)

            inicio = len(clientes)
            RunnerFalso.falla = True
            for modulo, funcion, args in modulos:
                with patch.object(modulo, "Runner", RunnerFalso):
                    try:
                        llamada_en_loop_propio(funcion, args)
                    except RuntimeError as exc:
                        assert "Runner simulado" in str(exc)
                    else:
                        raise AssertionError("se esperaba fallo de Runner.run")
            assert len(clientes) == inicio + 3
            assert all(cliente.cierres == 1 for cliente in clientes[inicio:])

    verificar("API crea cliente independiente por llamada y lo cierra incluso al fallar", clientes_api_por_llamada_y_cierre)

    def ciclo_y_almacen():
        with TemporaryDirectory() as directorio:
            ruta = str(Path(directorio) / "memoria.db")
            async def descripcion_fija(ctx):
                return Descripcion(resumen="prueba local", riesgos=[])
            async def diagnostico_fijo(ctx, resultados):
                return Diagnostico(que_fallo="", por_que="", evidencia=[], que_probar="", seguir=False)
            async def propuesta_fija_ciclo(ctx, descripcion, ultimo):
                return fijo.proponer(ctx)
            with patch("agentes.ciclo.Almacen", lambda: Almacen(ruta)), \
                 patch.object(config, "LLM_BACKEND", "api"), \
                 patch("agentes.ciclo.describir", descripcion_fija), \
                 patch("agentes.ciclo.proponer_con_llm", propuesta_fija_ciclo), \
                 patch("agentes.ciclo.diagnosticar", diagnostico_fijo), \
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
