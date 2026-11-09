"""contexto_de_fecha(fecha, pais) -> dict: qué pasó ese día en el calendario.

Importar este módulo no lee archivos: datos/eventos.csv se lee al primer uso y se cachea.
Mismas llaves y reglas que comun.falsos.contexto_de_fecha_falso, para que lo real y lo falso sean
intercambiables: quincena = día 15 o último del mes; dias_a_festivo_mas_cercano cuenta hacia
adelante (0 si el día es festivo).

Fechas del Buen Fin en eventos.csv: 2022-11-18 a 21, 2023-11-17 a 20 y 2024-11-15 a 18
(verificadas en la web por Diego).
"""
import csv
import re
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import holidays

RUTA_EVENTOS = Path(__file__).parent / "eventos.csv"
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_FORMATO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@lru_cache(maxsize=1)
def _eventos() -> dict[tuple[str, str], tuple[str, ...]]:
    """(fecha, pais) -> eventos de ese día. Se lee una vez y se cachea."""
    tabla: dict[tuple[str, str], tuple[str, ...]] = {}
    with RUTA_EVENTOS.open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            llave = (fila["fecha"].strip(), fila["pais"].strip().upper())
            tabla[llave] = tabla.get(llave, ()) + (fila["evento"].strip(),)
    return tabla


@lru_cache(maxsize=32)
def _festivos(pais: str, anio: int):
    try:
        return holidays.country_holidays(pais, years=[anio, anio + 1])
    except NotImplementedError:
        raise ValueError(f"país '{pais}' no reconocido por la librería holidays")


def _leer_fecha(fecha) -> date:
    # fromisoformat en Python 3.12 también acepta "20240916" o "2024-W38-1": se exige el formato antes.
    if not isinstance(fecha, str) or not _FORMATO.match(fecha):
        raise ValueError(f"fecha debe ser texto 'YYYY-MM-DD', llegó {fecha!r}")
    try:
        return date.fromisoformat(fecha)
    except ValueError:
        raise ValueError(f"fecha inexistente: {fecha!r}")


def contexto_de_fecha(fecha: str, pais: str | None = None) -> dict:
    """fecha en 'YYYY-MM-DD'. Sin pais: solo campos de calendario (festivo/evento en False/None)."""
    dia = _leer_fecha(fecha)
    fin_de_mes = (dia + timedelta(days=1)).month != dia.month
    contexto = {
        "fecha": dia.isoformat(),
        "dia_semana": _DIAS[dia.weekday()],
        "es_festivo": False,
        "nombre_festivo": None,
        "es_quincena": dia.day == 15 or fin_de_mes,
        "es_fin_de_mes": fin_de_mes,
        "evento": None,
        "dias_a_festivo_mas_cercano": None,
    }
    if pais:
        pais = pais.strip().upper()
        festivos = _festivos(pais, dia.year)
        if dia in festivos:
            contexto["es_festivo"] = True
            contexto["nombre_festivo"] = str(festivos.get(dia))
        siguientes = [(f - dia).days for f in festivos if f >= dia]
        contexto["dias_a_festivo_mas_cercano"] = min(siguientes) if siguientes else None
        eventos = _eventos().get((dia.isoformat(), pais))
        contexto["evento"] = ", ".join(eventos) if eventos else None
    return contexto
