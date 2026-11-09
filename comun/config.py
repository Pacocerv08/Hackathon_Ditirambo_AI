import os
from dotenv import load_dotenv

load_dotenv()

SEMILLA = 42
UMBRAL_RESUELTO = 0.9          # un caso está resuelto si costo_relativo < 0.9
MAX_ITERACIONES = 5
CANDIDATOS_POR_ITERACION = 3
PARAR_SI_NO_MEJORA = 2         # iteraciones seguidas sin mejora
LIMITE_SEGUNDOS_CANDIDATO = 60

MODELOS = {                    # confirmar qué modelos tiene habilitados la llave del evento
    "analista": "gpt-6-luna",
    "proponente": "gpt-6-luna",
    "diagnostico": "gpt-6-luna",
    "curador": "gpt-6-luna",
}

ESFUERZO = {
    "analista": "low",
    "proponente": "medium",
    "diagnostico": "medium",
    "curador": "high",
}

BACKEND = {
    "analista": "api",
    "proponente": "api",
    "diagnostico": "api",
    "curador": "codex",
}

LLM_BACKEND = os.getenv("LLM_BACKEND")
LLM_TIMEOUT_SEGUNDOS = 180

USAR_FALSOS = os.getenv("USAR_FALSOS", "0") == "1"
RUTA_DB = "salidas/memoria.db"
RUTA_VERSIONES = "versiones"
RUTA_PROBLEMAS = "datos/problemas"
BANCO = ["credito_a", "credito_b", "churn_a", "churn_b", "demanda_a", "demanda_b"]
