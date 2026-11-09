# memoria/ — almacén, curador y constructor de versiones

**Dueño:** Eduardo. **Lo usan:** Paco (`Almacen`, `cargar_version`) y `experimento/`.

Lee primero el `AGENTS.md` de la raíz y `comun/AGENTS.md`. No toques `datos/`, `evaluacion/` ni `agentes/`.

Aquí vive el RSI: **falla → señal → lección → versión sucesora**. Todo lo que pase aquí tiene que poder enseñarse en la demo como un diff.

## Archivos

```
memoria/
  __init__.py
  almacen.py         # Almacen (SQLite)
  versiones.py       # cargar_version, crear_v0, version_sin
  curador.py         # curar(...) con un agente LLM + validación en código
  constructor.py     # construir_sucesor(...), solo código
  pruebas.py         # python -m memoria.pruebas
```

## Funciones públicas (firmas exactas)

```python
from comun.contratos import *

class Almacen:
    def __init__(self, ruta: str = config.RUTA_DB): ...
    def iniciar_ejecucion(self, run_id: str, version: str, problema_id: str) -> None: ...
    def guardar_resultado(self, run_id: str, candidato: Candidato, resultado: Resultado) -> None: ...
    def guardar_llamada(self, run_id: str, agente: str, entrada: str, salida: str, segundos: float) -> None: ...
    def historial(self, problema_id: str, version: str | None = None, modo: Modo | None = None) -> list[Resultado]: ...
    def guardar_huella(self, problema_id: str, huella: dict[str, float]) -> None: ...
    def guardar_leccion(self, leccion: Leccion) -> None: ...
    def lecciones(self, ids: list[str]) -> list[Leccion]: ...
    def lecciones_relevantes(self, version: Version, problema: Problema, k: int = 5) -> list[Leccion]: ...

def cargar_version(id: str) -> Version: ...                     # lee versiones/{id}/config.json
def crear_v0() -> Version: ...                                  # escribe versiones/v0/config.json
def version_sin(id: str, leccion_id: str) -> Version: ...       # para la ablación (ver abajo)
def curar(problema: Problema, ciclo: ResultadoCiclo, version: Version) -> list[Leccion]: ...
def construir_sucesor(version: Version, lecciones: list[Leccion]) -> Version: ...
```

## `almacen.py`: SQLite, sin base vectorial

Tablas (todo lo complejo se guarda como JSON en una columna de texto):

```sql
ejecuciones(run_id PK, version, problema_id, inicio, fin)
resultados(id PK, run_id, problema_id, version, modo, candidato_id, candidato_json, resultado_json,
           costo_relativo, resuelto, creado)
llamadas(id PK, run_id, agente, entrada, salida, segundos, creado)
huellas(problema_id PK, huella_json)
lecciones(id PK, version_origen, problema_origen, leccion_json, activa)
versiones(id PK, padre, version_json, creada)
```

`lecciones_relevantes`: toma `version.lecciones_activas`, filtra por `alcance` compatible con `problema.tipo_tarea` y ordena por distancia euclidiana entre la huella normalizada del problema actual y la del `problema_origen`. Eso es todo el "retrieval": son decenas de lecciones, no millones.

## `versiones.py`

Una versión en disco:

```
versiones/v1/
  config.json            # Version serializada + config.MODELOS
  instrucciones/
    analista.md
    proponente.md
    diagnostico.md
  lecciones/
    L001-umbral-por-costos/SKILL.md
  cambios.md
```

- `crear_v0()`: capacidades todas apagadas, sin lecciones, `creada_por="equipo"`. Las instrucciones de v0 las escribe Paco.
- `version_sin(id, leccion_id)`: copia `versiones/{id}` a `versiones/{id}-sin-{leccion_id}`, apaga su capacidad, quita su bloque de las instrucciones y su carpeta de lecciones. Paco no tiene que saber nada de ablación.

## `curador.py`

Un agente LLM (`config.MODELOS["curador"]`) con `output_type`:

```python
class LeccionPropuesta(BaseModel):
    senal: str
    evidencia: list[str]          # candidato_id del historial
    texto: str
    tipo_cambio: Literal["regla", "chequeo", "variable", "flujo"]
    capacidad: NombreCapacidad | None
    regla_para: list[NombreAgente]
    alcance: Literal["general", "clasificacion", "serie"]

class PropuestaCurador(BaseModel):
    lecciones: list[LeccionPropuesta] = Field(description="0 a 2 lecciones")
```

Recibe un resumen corto (no todo el historial crudo):
- descripción y tipo del problema, costos;
- los 5 mejores intentos con `costo_relativo`, `metricas` y `alertas`;
- los diagnósticos;
- **validación vs. producción** del candidato elegido. Una brecha grande es la señal más fuerte;
- las capacidades disponibles y cuáles están apagadas en esta versión;
- las lecciones que ya tiene la versión, para no repetirlas.

Validación en código, después del LLM (descarta lo que no pase):
- cada `evidencia` existe en el historial de ese run;
- `capacidad` no está ya encendida;
- el `texto` no menciona el nombre del dataset ni del dominio: tiene que servir en otra industria;
- máximo 2 lecciones por problema.

Asigna `id` (`L001`, `L002`…), `version_origen`, `problema_origen` y guarda con `almacen.guardar_leccion`.

## `constructor.py`: solo código, sin LLM

`construir_sucesor(version, lecciones)`:

1. Copia `versiones/{version.id}` a `versiones/v{N+1}`.
2. Por cada lección: si tiene `capacidad`, la enciende en `config.json`.
3. Por cada agente en `regla_para`, agrega al final de su instrucción:
   ```
   <!-- leccion:L001 -->
   - (L001) Cuando el error de un lado cuesta más que el del otro, ... [texto]
   <!-- /leccion:L001 -->
   ```
   Los marcadores sirven para que `version_sin` pueda quitarla.
4. Escribe `lecciones/L001-<slug>/SKILL.md`:
   ```markdown
   ---
   name: l001-umbral-por-costos
   description: <texto de la lección en una línea>
   ---
   ## Señal
   ## Evidencia
   ## Qué cambia en el sucesor
   ## Origen (versión, problema)
   ```
5. Escribe `cambios.md` (padre, lecciones nuevas, capacidades encendidas, reglas agregadas, `creada_por: sistema`).
6. Guarda la versión en la tabla `versiones` y la devuelve.

Si alguna vez editas a mano algo dentro de `versiones/`, va a `INTERVENCIONES.md`. Sin excepciones.

**Ambicioso (solo si sobra tiempo):** que el paso 3 lo haga Codex sobre el código de la versión (por ejemplo una prueba nueva) en lugar de solo texto. Registrar en `CODEX_LOG.md`.

## Orden de trabajo

1. Después de `comun/`: `Almacen` con `guardar_resultado`, `guardar_llamada`, `historial`. Avisa a Paco.
2. `crear_v0`, `cargar_version`.
3. `construir_sucesor` con una lección escrita a mano (prueba), revisando el diff `v0 → v1` con `git diff --no-index versiones/v0 versiones/v1`.
4. `curar` con el LLM, primero sobre un `ResultadoCiclo` falso.
5. `version_sin` y `lecciones_relevantes`.

## Hecho cuando (`python -m memoria.pruebas`)

- Guardar y leer 10 resultados da los mismos objetos.
- Con una lección de prueba (`capacidad="umbral_por_costos"`), v1 tiene la capacidad encendida, la regla en `proponente.md` y su `SKILL.md`.
- `version_sin("v1", "L001")` deja una carpeta idéntica a v0 salvo por `config.json` (id y padre).
- Con el `ResultadoCiclo` real de `credito_a` en v0, el curador propone una lección sobre el umbral sin que nadie se lo haya dicho.

Registra en `CODEX_LOG.md` lo que Codex haya escrito aquí.
