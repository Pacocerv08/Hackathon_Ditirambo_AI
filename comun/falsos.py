"""Implementaciones deterministas para trabajar sin los módulos de datos reales."""

from datetime import date, timedelta
import hashlib
import random

from comun import config
from comun.contratos import (
    Capacidades,
    Candidato,
    Costos,
    Modo,
    PeorCaso,
    Problema,
    Resultado,
    TipoTarea,
)


def problema_falso(tipo: TipoTarea) -> Problema:
    """Construye un problema pequeño y plausible para cada tipo de tarea."""
    if tipo == "clasificacion":
        return Problema(
            id="falso_clasificacion",
            dominio="riesgo_crediticio",
            tipo_tarea=tipo,
            descripcion_negocio="Estimar el riesgo de impago para decidir si aprobar un crédito.",
            archivo="datos/procesados/falso_clasificacion.parquet",
            objetivo="impago",
            clase_positiva="impago",
            costos=Costos(
                costo_fn=5,
                costo_fp=1,
                justificacion="Aprobar a quien no paga cuesta más que rechazar a un buen cliente.",
            ),
        )
    if tipo == "serie":
        return Problema(
            id="falso_serie",
            dominio="demanda_minorista",
            tipo_tarea=tipo,
            descripcion_negocio="Pronosticar demanda diaria para planear el inventario.",
            archivo="datos/procesados/falso_serie.parquet",
            objetivo="demanda",
            columna_fecha="fecha",
            pais="MX",
            costos=Costos(
                costo_faltante=3,
                costo_sobrante=1,
                justificacion="Quedarse corto de inventario cuesta más que conservar excedente.",
            ),
        )
    raise ValueError(f"Tipo de tarea no reconocido: {tipo!r}")


def evaluar_falso(
    problema: Problema,
    candidato: Candidato,
    capacidades: Capacidades,
    modo: Modo = "validacion",
    version: str = "v0",
) -> Resultado:
    """Devuelve una evaluación plausible, repetible y aislada del random global."""
    candidato_json = candidato.model_dump_json()
    candidato_id = hashlib.sha1((candidato_json + problema.id).encode("utf-8")).hexdigest()[:10]
    semilla_texto = f"{candidato_id}:{modo}"
    semilla = int(hashlib.sha1(semilla_texto.encode("utf-8")).hexdigest(), 16)
    rng = random.Random(semilla)

    costo_relativo = rng.uniform(0.6, 1.2)
    costo_referencia = 100.0
    costo = costo_relativo * costo_referencia
    peores_casos = [
        PeorCaso(
            referencia=(date(2024, 1, 1) + timedelta(days=i)).isoformat()
            if problema.tipo_tarea == "serie"
            else str(i),
            real=float(rng.randint(0, 100)),
            predicho=float(rng.randint(0, 100)),
            costo=round(rng.uniform(0.0, 20.0), 4),
        )
        for i in range(5)
    ]
    return Resultado(
        problema_id=problema.id,
        candidato_id=candidato_id,
        version=version,
        modo=modo,
        costo=costo,
        costo_referencia=costo_referencia,
        costo_relativo=costo_relativo,
        resuelto=costo_relativo < config.UMBRAL_RESUELTO,
        metricas={"costo_relativo": costo_relativo},
        peores_casos=peores_casos,
    )


_DIAS_SEMANA = (
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"
)


def contexto_de_fecha_falso(fecha: str, pais: str | None = None) -> dict:
    """Entrega calendario básico con el mismo esquema del contexto real."""
    dia = date.fromisoformat(fecha)
    es_fin_de_mes = (dia + timedelta(days=1)).month != dia.month
    contexto = {
        "fecha": dia.isoformat(),
        "dia_semana": _DIAS_SEMANA[dia.weekday()],
        "es_festivo": False,
        "nombre_festivo": None,
        "es_quincena": dia.day == 15 or es_fin_de_mes,
        "es_fin_de_mes": es_fin_de_mes,
        "evento": None,
        "dias_a_festivo_mas_cercano": None,
    }
    if pais:
        try:
            import holidays

            feriados = holidays.country_holidays(pais, years=range(dia.year, dia.year + 2))
            if dia in feriados:
                contexto["es_festivo"] = True
                contexto["nombre_festivo"] = str(feriados.get(dia))
            fechas = [
                (feriado - dia).days
                for feriado in feriados
                if feriado >= dia
            ]
            if fechas:
                contexto["dias_a_festivo_mas_cercano"] = min(fechas)
        except (ImportError, NotImplementedError):
            pass
    return contexto


def huella_falsa(problema: Problema) -> dict[str, float]:
    """Estadísticas sintéticas con todas las llaves pactadas para cada tarea."""
    if problema.tipo_tarea == "clasificacion":
        return {
            "filas": 1000.0,
            "columnas": 20.0,
            "proporcion_positiva": 0.3,
            "pct_faltantes": 0.02,
            "pct_categoricas": 0.4,
            "max_auc_columna": 0.72,
        }
    return {
        "longitud": 1095.0,
        "pct_ceros": 0.01,
        "cv": 0.25,
        "fuerza_semanal": 0.65,
        "tendencia": 0.08,
        "pct_dias_atipicos": 0.03,
    }
