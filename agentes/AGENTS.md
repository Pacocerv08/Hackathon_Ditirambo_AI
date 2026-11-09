# agentes/ — analista, proponente, diagnóstico y el ciclo

**Dueño:** Paco. **Lo usa:** Eduardo (`experimento/` llama `resolver`).

Lee primero el `AGENTS.md` de la raíz y `comun/AGENTS.md`. No toques `comun/`, `datos/`, `evaluacion/`, `memoria/` ni `experimento/`. Importa `evaluar`, `huella` y `contexto_de_fecha` **solo desde `comun.puertos`**.

## Archivos

```
agentes/
  __init__.py
  esquemas.py        # salidas estructuradas de los agentes (solo internas a esta carpeta)
  contexto.py        # ContextoCiclo, el estado que comparten las herramientas
  herramientas.py    # function_tool para los agentes
  instrucciones.py   # lee versiones/vN/instrucciones/{agente}.md
  analista.py
  proponente.py
  diagnostico.py
  ciclo.py           # resolver(...)
  fijo.py            # proponente sin LLM, para la primera entrega y como respaldo
```

## Función pública (firma exacta)

```python
from comun.contratos import Problema, Version, ResultadoCiclo

async def resolver(problema: Problema, version: Version, run_id: str | None = None) -> ResultadoCiclo: ...

def resolver_sync(problema: Problema, version: Version, run_id: str | None = None) -> ResultadoCiclo:
    return asyncio.run(resolver(problema, version, run_id))
```

## Esquemas internos (`esquemas.py`)

```python
from pydantic import BaseModel, Field
from comun.contratos import Candidato

class Descripcion(BaseModel):
    resumen: str = Field(description="Qué se decide, con qué datos y qué error es caro, en 3-5 frases")
    riesgos: list[str] = Field(description="Cosas raras de los datos que podrían engañar al modelo")

class Propuesta(BaseModel):
    candidatos: list[Candidato] = Field(description="Exactamente 3, distintos entre sí y a lo ya probado")

class Diagnostico(BaseModel):
    que_fallo: str
    por_que: str
    evidencia: list[str] = Field(description="Fechas, filas, alertas o métricas que lo respaldan")
    que_probar: str
    seguir: bool = Field(description="False si no vale la pena otra iteración")
```

## Contexto compartido (`contexto.py`)

```python
from dataclasses import dataclass, field

@dataclass
class ContextoCiclo:
    problema: Problema
    version: Version
    run_id: str
    almacen: "Almacen"                      # de memoria.almacen, de Eduardo
    historial: list[tuple[Candidato, Resultado]] = field(default_factory=list)
```

Las herramientas lo reciben con `RunContextWrapper[ContextoCiclo]` y el ciclo lo pasa en `Runner.run(..., context=ctx)`.

## Herramientas (`herramientas.py`)

Respuestas cortas en texto o JSON pequeño (menos de ~1500 caracteres).

| Herramienta | Agentes | Devuelve |
| --- | --- | --- |
| `resumen_datos()` | analista | `huella` + tipos de columnas + costos |
| `consultar_lecciones()` | proponente, diagnóstico | lecciones activas de la versión con `alcance` compatible, `texto` y `senal` |
| `historial_intentos()` | proponente, diagnóstico | tabla: modelo, features, excluidas, costo_relativo, alertas |
| `peores_casos(candidato_id)` | diagnóstico | los 10 peores casos de ese candidato |
| `contexto_de_fecha(fecha)` | diagnóstico | lo de Diego, con el `pais` del problema |

Los agentes **no** tienen herramienta para evaluar ni para escribir lecciones.

## Instrucciones

- Se leen de `versiones/{version.id}/instrucciones/{agente}.md` (`analista`, `proponente`, `diagnostico`). Nunca escritas en el código.
- Paco es dueño de `versiones/v0/instrucciones/*.md` y escribe esas instrucciones. **Deben ser genéricas:** cómo razonar, qué formato devolver, que las propuestas sean distintas entre sí. **Prohibido** mencionar umbrales por costos, fuga, columnas sospechosas o calendario. Eso es justo lo que el sistema tiene que aprender; si v0 ya lo sabe, la demo no demuestra nada.
- Las versiones siguientes las escribe el constructor de Eduardo agregando reglas al final del archivo. Tu código no cambia entre versiones.
- Lo que sí puede ir en v0: la lista de modelos e hiperparámetros permitidos y el catálogo de variables (sin explicar `calendario`).

## Modelos

`config.MODELOS[agente]`. Usa `output_type` con los esquemas de arriba. Si una llamada falla, un reintento; si vuelve a fallar, el proponente cae a `fijo.py` y el diagnóstico devuelve un `Diagnostico` vacío con `seguir=True`. Nada de esto debe tumbar el ciclo.

## El ciclo (`ciclo.py`)

```
ctx = ContextoCiclo(...)
descripcion = analista(problema)                         # una vez
mejor = None; sin_mejora = 0
for i in range(config.MAX_ITERACIONES):
    propuesta = proponente(descripcion, ultimo_diagnostico)   # 3 candidatos
    resultados = await evaluar en paralelo (asyncio.to_thread + Semaphore(3)),
                 modo="validacion", capacidades=version.capacidades
    tras completar asyncio.gather, guardar cada resultado en almacen desde el hilo principal; agregar a ctx.historial
    actualizar mejor por costo_relativo; si no mejoró, sin_mejora += 1
    diag = diagnostico(resultados)
    si sin_mejora >= config.PARAR_SI_NO_MEJORA o not diag.seguir: romper
produccion = evaluar(problema, mejor_candidato, capacidades, modo="produccion")
devolver ResultadoCiclo(..., resultado_produccion=produccion)
```

- El presupuesto (`MAX_ITERACIONES`, `CANDIDATOS_POR_ITERACION`) es el mismo para todas las versiones. No lo cambies por versión.
- Guarda cada llamada a un agente con `almacen.guardar_llamada(run_id, agente, entrada, salida, segundos)`.
- Los resultados se guardan en `Almacen` después de `asyncio.gather`, en el hilo principal; nunca dentro de los hilos de `asyncio.to_thread`, porque SQLite no es seguro entre hilos.
- Envuelve todo el problema en `with trace(f"{version.id}-{problema.id}")` para ver las trazas.
- `run_id` por defecto: `f"{version.id}-{problema.id}-{timestamp}"`.

## Orden de trabajo

1. **Primera entrega:** `fijo.py` + `ciclo.py` sin LLM contra los falsos (`USAR_FALSOS=1`). Que `resolver_sync(problema_falso("clasificacion"), version_v0)` devuelva un `ResultadoCiclo`. Mientras Eduardo no tenga `Almacen`, usa una clase falsa que solo imprime.
2. Instrucciones de v0 y el proponente con LLM.
3. Analista y diagnóstico con sus herramientas.
4. Con `USAR_FALSOS=0`, correr `credito_a` de punta a punta con el evaluador real de Diego.
5. Revisar en las trazas que el diagnóstico de demanda sí llame `contexto_de_fecha` en las fechas con más error.

## Hecho cuando

- `python -m agentes.ciclo credito_a v0` corre de punta a punta e imprime el mejor candidato, su costo relativo en validación y en producción.
- Una falla de la API no tumba el ciclo.
- Las 3 propuestas de una iteración nunca repiten un candidato ya probado.
- Cambiar `versiones/v1/instrucciones/proponente.md` cambia el comportamiento sin tocar código.

Registra en `CODEX_LOG.md` lo que Codex haya escrito aquí.
