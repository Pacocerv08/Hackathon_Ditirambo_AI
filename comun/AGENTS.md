# comun/ — contratos, configuración y falsos

**Dueño:** Eduardo. **Se usa en:** todo el proyecto.

Lee primero el `AGENTS.md` de la raíz. Esta carpeta es la única compartida: **ningún cambio aquí sin avisar a Paco y Diego**. Si un cambio es necesario, agrega campos con valor por defecto en lugar de renombrar o quitar, para no romper a nadie.

## Archivos

| Archivo | Qué contiene |
| --- | --- |
| `contratos.py` | Las clases de Pydantic de esta página, tal cual |
| `config.py` | Constantes del experimento |
| `falsos.py` | Versiones falsas de las funciones públicas de los demás módulos |
| `puertos.py` | El único lugar que decide si se usa la versión real o la falsa |

## 1. `contratos.py` (primera entrega, antes que todo)

```python
from typing import Literal
from pydantic import BaseModel, Field

TipoTarea = Literal["clasificacion", "serie"]
NombreModelo = Literal["referencia", "logistica", "arbol", "lightgbm"]
Modo = Literal["validacion", "produccion", "prueba"]
# validacion: lo que ven los agentes en cada iteración
# produccion: una sola evaluación del candidato elegido al final del ciclo; la ve el curador
#             (simula "lo pusimos en producción y así le fue")
# prueba:     solo el banco de experimento/; nadie aprende de aquí
NombreCapacidad = Literal["umbral_por_costos", "revisar_fuga", "variables_calendario"]
NombreAgente = Literal["analista", "proponente", "diagnostico"]


class Costos(BaseModel):
    """Clasificación usa costo_fn y costo_fp. Serie usa costo_faltante y costo_sobrante."""
    costo_fn: float | None = None        # no actuar cuando había que actuar (aprobar a quien no paga)
    costo_fp: float | None = None        # actuar sin necesidad (rechazar a un buen cliente)
    costo_faltante: float | None = None  # pronosticar de menos, por unidad
    costo_sobrante: float | None = None  # pronosticar de más, por unidad
    justificacion: str


class Particion(BaseModel):
    semilla: int = 42
    folds: int = 5                         # clasificación: validación cruzada sobre entrenamiento
    proporcion_prueba: float = 0.25        # clasificación: holdout fijo para el banco
    proporcion_produccion: float = 0.2     # parte del entrenamiento apartada para el modo produccion
    fecha_corte_prueba: str | None = None  # serie: todo lo posterior es prueba


class Problema(BaseModel):
    id: str
    dominio: str
    tipo_tarea: TipoTarea
    descripcion_negocio: str
    archivo: str                           # ruta al parquet, relativa a la raíz
    objetivo: str
    columna_fecha: str | None = None
    clase_positiva: str | None = None      # la clase cuyo error es caro: "bad", "churn"...
    pais: str | None = None                # para contexto_de_fecha ("MX", "EC")
    costos: Costos
    particion: Particion = Particion()
    reservado: bool = False                # True: solo se usa en el banco final, nunca para aprender


class Hiperparametro(BaseModel):
    nombre: str
    valor: float | int | str


class Candidato(BaseModel):
    justificacion: str = Field(description="Por qué este candidato, en una o dos frases")
    modelo: NombreModelo
    features: list[str] = Field(default_factory=list,
        description="Solo series: generadores de variables del catálogo del evaluador")
    excluir_columnas: list[str] = Field(default_factory=list,
        description="Solo clasificación: columnas que no se deben usar")
    hiperparametros: list[Hiperparametro] = Field(default_factory=list)


class Capacidades(BaseModel):
    umbral_por_costos: bool = False
    revisar_fuga: bool = False
    variables_calendario: bool = False


class PeorCaso(BaseModel):
    referencia: str      # fecha (serie) o índice de fila (clasificación)
    real: float
    predicho: float
    costo: float


class Resultado(BaseModel):
    problema_id: str
    candidato_id: str
    version: str
    modo: Modo
    costo: float
    costo_referencia: float
    costo_relativo: float                  # costo / costo_referencia; < 1 mejora la referencia
    resuelto: bool                         # costo_relativo < config.UMBRAL_RESUELTO
    metricas: dict[str, float] = Field(default_factory=dict)
    alertas: list[str] = Field(default_factory=list)   # "posible_fuga: columna X (AUC 0.99)"
    peores_casos: list[PeorCaso] = Field(default_factory=list)
    segundos: float = 0.0
    error: str | None = None


class Leccion(BaseModel):
    id: str
    version_origen: str
    problema_origen: str
    senal: str = Field(description="Qué se observó que delató la falla")
    evidencia: list[str] = Field(description="ids de candidatos o ejecuciones que la respaldan")
    texto: str = Field(description="La lección en una o dos frases, aplicable a otros problemas")
    tipo_cambio: Literal["regla", "chequeo", "variable", "flujo"]
    capacidad: NombreCapacidad | None = None           # qué capacidad activa en el sucesor
    regla_para: list[NombreAgente] = Field(default_factory=list)  # a qué instrucciones se agrega
    alcance: Literal["general", "clasificacion", "serie"] = "general"
    activa: bool = True
    veces_usada: int = 0
    veces_que_ayudo: int = 0


class Version(BaseModel):
    id: str                                # "v0", "v1"...
    padre: str | None
    capacidades: Capacidades
    lecciones_activas: list[str]
    creada_por: Literal["sistema", "equipo"]
    cambios: list[str]


class ResultadoCiclo(BaseModel):
    problema_id: str
    version: str
    run_id: str
    mejor_candidato: Candidato | None
    mejor_resultado: Resultado | None
    historial: list[Resultado]
    diagnosticos: list[str]
    resultado_produccion: Resultado | None = None   # el mejor candidato evaluado en modo produccion
```

## 2. `config.py`

```python
import os

SEMILLA = 42
UMBRAL_RESUELTO = 0.9          # un caso está resuelto si costo_relativo < 0.9
MAX_ITERACIONES = 5
CANDIDATOS_POR_ITERACION = 3
PARAR_SI_NO_MEJORA = 2         # iteraciones seguidas sin mejora
LIMITE_SEGUNDOS_CANDIDATO = 60

MODELOS = {                    # confirmar qué modelos tiene habilitados la llave del evento
    "analista": "gpt-6-luna",
    "proponente": "gpt-6.1-sol",
    "diagnostico": "gpt-6.1-sol",
    "curador": "gpt-6.1-sol",
}

USAR_FALSOS = os.getenv("USAR_FALSOS", "1") == "1"
RUTA_DB = "salidas/memoria.db"
RUTA_VERSIONES = "versiones"
RUTA_PROBLEMAS = "datos/problemas"
BANCO = ["credito_a", "credito_b", "churn_a", "churn_b", "demanda_a", "demanda_b"]
```

**`UMBRAL_RESUELTO` y `BANCO` se fijan antes de ver resultados.** Si después de correr v0 los números no cuentan la historia que esperábamos, se reporta así; no se ajustan para que salga bonita.

## 3. `falsos.py`

Mismas firmas que las funciones reales, con resultados plausibles y deterministas (semilla fija):

- `problema_falso(tipo: TipoTarea) -> Problema`
- `evaluar_falso(problema, candidato, capacidades, modo="validacion", version="v0") -> Resultado` — `costo_relativo` aleatorio entre 0.6 y 1.2, y `peores_casos` con 5 entradas.
- `contexto_de_fecha_falso(fecha: str, pais: str | None = None) -> dict`
- `huella_falsa(problema) -> dict[str, float]`
- `resolver_falso(problema: Problema, version: Version, run_id: str | None = None) -> ResultadoCiclo` — resuelve sin LLM con tres candidatos fijos y evalúa el mejor en producción.

## 4. `puertos.py`

Todos los módulos importan de aquí, nunca directamente de `evaluacion` o `datos`. Cada puerto selecciona real o falso de forma independiente.

```python
PUERTOS_FALSOS: dict[str, bool]  # claves: "evaluar", "huella", "contexto_de_fecha", "resolver"
```

Para cada función (`evaluar`, `huella`, `contexto_de_fecha`), intenta importar su módulo real por separado. Si `USAR_FALSOS=1` o ese import falla con `ImportError`, usa solo el falso de ese puerto e imprime una advertencia visible, por ejemplo `[FALSO] usando evaluar falso`. `PUERTOS_FALSOS` indica con un booleano por puerto cuál está usando falso (`True`) o real (`False`). Un fallo de importación de un puerto no debe cambiar los otros.

El puerto `resolver` selecciona `agentes.ciclo.resolver_sync` o `resolver_falso` de forma independiente y registra su estado en `PUERTOS_FALSOS`.

## Hecho cuando

- `python -c "from comun.contratos import *; from comun.puertos import evaluar"` corre sin error.
- Paco puede llamar `evaluar(problema_falso("clasificacion"), candidato, Capacidades())` y recibe un `Resultado`.
- Está en `main` y Paco y Diego hicieron `git pull`.

Registra en `CODEX_LOG.md` lo que Codex haya escrito aquí.
