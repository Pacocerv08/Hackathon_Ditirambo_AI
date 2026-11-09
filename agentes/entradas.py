"""Construye entradas autocontenidas para los agentes sin invocar modelos."""

import json

from agentes.contexto import ContextoCiclo
from agentes.herramientas import (
    _compacto,
    datos_contexto_fecha,
    datos_historial,
    datos_lecciones,
    datos_peores_casos,
    datos_resumen,
)
from comun.contratos import Resultado


_LIMITE = 12000


def _seccion(titulo: str, contenido: str) -> str:
    return f"## {titulo}\n{contenido}"


def _problema(ctx: ContextoCiclo) -> str:
    p = ctx.problema
    return _compacto({
        "tipo_tarea": p.tipo_tarea,
        "objetivo": p.objetivo,
        "dominio": p.dominio,
        "pais": p.pais,
        "costos": p.costos.model_dump(exclude_none=True),
    })


def variables_disponibles(ctx: ContextoCiclo) -> list[str]:
    """Catálogo de features de serie habilitado por la versión actual."""
    if ctx.problema.tipo_tarea != "serie":
        return []
    disponibles = ["rezagos", "medias_moviles", "dia_semana"]
    if ctx.version.capacidades.variables_calendario:
        disponibles.append("calendario")
    return disponibles


def _seccion_variables(ctx: ContextoCiclo) -> str | None:
    if ctx.problema.tipo_tarea != "serie":
        return None
    disponibles = variables_disponibles(ctx)
    texto = (
        "\n".join(disponibles)
        + "\nEsta lista manda sobre cualquier otra lista de variables en tus instrucciones; usa solo estas."
    )
    if "calendario" in disponibles:
        texto += "\ncalendario es una variable nueva en esta versión: pruébala al menos una vez."
    return _seccion("Variables disponibles (catálogo vigente de esta versión)", texto)


def _limitar(secciones: list[str]) -> str:
    salida = []
    usados = 0
    for seccion in secciones:
        adicional = len(seccion) + (2 if salida else 0)
        if usados + adicional <= _LIMITE:
            salida.append(seccion)
            usados += adicional
    return "\n\n".join(salida)


def entrada_analista(ctx: ContextoCiclo) -> str:
    try:
        resumen = datos_resumen(ctx)
    except Exception:
        resumen = "no disponible"
    try:
        lecciones = datos_lecciones(ctx)
    except Exception:
        lecciones = "no disponible"
    return _limitar([
        _seccion("Problema", _problema(ctx)),
        _seccion("Resumen de datos", resumen),
        _seccion("Lecciones activas", lecciones),
    ])


def entrada_proponente(
    ctx: ContextoCiclo,
    descripcion: object,
    ultimo_diagnostico: object | None,
) -> str:
    try:
        lecciones = datos_lecciones(ctx)
    except Exception:
        lecciones = "no disponible"
    probados = []
    for candidato, resultado in ctx.historial[-40:]:
        probados.append({
            "modelo": candidato.modelo,
            "features": candidato.features,
            "excluir_columnas": candidato.excluir_columnas,
            "hiperparametros": [hp.model_dump() for hp in candidato.hiperparametros],
            "costo_relativo": resultado.costo_relativo,
            "alertas": resultado.alertas[:3],
            "error": resultado.error,
        })
    desc = descripcion.model_dump() if hasattr(descripcion, "model_dump") else str(descripcion)
    diag = ultimo_diagnostico.model_dump() if hasattr(ultimo_diagnostico, "model_dump") else "ninguno"
    secciones = [
        _seccion("Problema", _problema(ctx)),
    ]
    variables = _seccion_variables(ctx)
    if variables:
        secciones.append(variables)
    secciones.extend([
        _seccion("Ya probado (no repetir)", _compacto(probados, limite=7500)),
        _seccion("Último diagnóstico", _compacto(diag) if diag != "ninguno" else "ninguno"),
        _seccion("Lecciones activas", lecciones),
        _seccion("Descripción del analista", _compacto(desc)),
    ])
    return _limitar(secciones)


def entrada_diagnostico(ctx: ContextoCiclo, resultados: list[Resultado]) -> str:
    resumen = [{
        "candidato_id": r.candidato_id,
        "costo_relativo": r.costo_relativo,
        "alertas": r.alertas,
        "error": r.error,
    } for r in resultados]
    casos = []
    fechas = []
    validos = [r for r in resultados if not r.error]
    for r in sorted(validos, key=lambda x: x.costo_relativo)[:2]:
        try:
            lista = json.loads(datos_peores_casos(ctx, r.candidato_id))
            casos.append({"candidato_id": r.candidato_id, "casos": lista[:5] if isinstance(lista, list) else lista})
            if ctx.problema.tipo_tarea == "serie" and isinstance(lista, list):
                fechas.extend(str(c.get("referencia")) for c in lista[:5] if isinstance(c, dict) and c.get("referencia"))
        except Exception:
            casos.append({"candidato_id": r.candidato_id, "casos": "no disponible"})
    contextos = []
    for fecha in dict.fromkeys(fechas[:5]):
        try:
            valor = datos_contexto_fecha(ctx, fecha)
        except Exception:
            valor = "no disponible"
        contextos.append({"fecha": fecha, "contexto": valor})
    try:
        historial = datos_historial(ctx)
    except Exception:
        historial = "no disponible"
    return _limitar([
        _seccion("Problema", _problema(ctx)),
        _seccion("Resultados del lote", _compacto(resumen)),
        _seccion("Peores casos", _compacto(casos) if casos else "sin candidatos válidos en este lote"),
        _seccion("Contexto de fechas", _compacto(contextos) if ctx.problema.tipo_tarea == "serie" else "no aplica"),
        _seccion("Historial", historial),
    ])
