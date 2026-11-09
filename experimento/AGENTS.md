# experimento/ — prueba de humo, cadena de versiones, banco, ablación y demo

**Dueño:** Eduardo. **Usa:** todo lo demás, solo por sus funciones públicas.

Lee primero el `AGENTS.md` de la raíz. No toques otras carpetas: si algo falla en ellas, avisa a su dueño.

Esta carpeta produce lo que el jurado ve: la cadena v0 → v1 → v2, la gráfica de mejora y la ablación.

## Archivos

```
experimento/
  __init__.py
  humo.py            # python -m experimento.humo
  cadena.py          # python -m experimento.cadena
  banco.py           # python -m experimento.banco v0 v1 v2
  ablacion.py        # python -m experimento.ablacion v2
  graficas.py        # python -m experimento.graficas
  demo.py            # python -m experimento.demo
```

Salidas a `salidas/` (no se sube a git), excepto las figuras finales: cópialas a `docs/figuras/` para el repo.

## `humo.py`

Un problema de cada tipo, una iteración, de punta a punta. Corre con `USAR_FALSOS=1` (siempre debe pasar) y con `USAR_FALSOS=0` (pasa cuando ya hay piezas reales). Todos lo corren antes de cada integración. Menos de 1 minuto.

## `cadena.py`: el RSI

```python
def correr_cadena(pasos=(("v0", "credito_a"), ("v1", "churn_a"), ("v2", "demanda_a"))) -> list[Version]:
    # por cada paso:
    #   ciclo = resolver_sync(problema, version)
    #   lecciones = curar(problema, ciclo, version)
    #   sucesor = construir_sucesor(version, lecciones)
    #   imprimir: costo validación, costo producción, lecciones nuevas, diff de la versión
```

Lo que esperamos (no lo forcemos; si no pasa, se reporta así):
- v0 en crédito usa umbral 0.5 → lección de umbral por costos → v1.
- v1 en churn confía en la columna con fuga → brecha validación vs. producción → lección de fuga → v2.
- v2 en demanda falla en festivos y quincenas → el diagnóstico revisa esas fechas con `contexto_de_fecha` → lección de calendario → v3.

Si una lección no aparece sola, **no** la escribas a mano en silencio: anótalo en `INTERVENCIONES.md` y márcalo en la demo como intervención humana.

## `banco.py`: la evaluación justa

```python
def correr_banco(version_id: str, desactivar: list[str] = [], incluir_reservados: bool = True) -> pd.DataFrame:
    # antes de correr: si any(PUERTOS_FALSOS.values()), lanzar un error claro y detenerse
    # por cada caso de config.BANCO (+ reservados):
    #   ciclo = resolver(problema, version)               # mismo presupuesto para todas
    #   prueba = evaluar(problema, ciclo.mejor_candidato, version.capacidades, modo="prueba")
    # columnas: version, caso, tipo, reservado, costo_relativo, resuelto, segundos
```

`correr_banco` debe negarse a correr y lanzar un error claro si cualquier valor de `comun.puertos.PUERTOS_FALSOS` es `True`; el banco de evaluación requiere todos los puertos reales.

- Corre los casos en paralelo con `asyncio.gather` y un `Semaphore(3)`.
- Aquí **no** se cura ni se construye nada. El banco solo mide.
- Mismas semillas para todas las versiones. Si sobra tiempo, 2 repeticiones por versión para ver la variación del LLM.
- Guarda la tabla en `salidas/banco_{version}.csv`.
- Honestidad: los casos `_a` se usaron para aprender. Los que prueban que generaliza son los `_b` y los reservados. La gráfica los separa.

## `ablacion.py`

Para cada lección activa de la última versión: `version_sin(version, leccion)`, correr el banco, comparar. Tabla: lección, casos resueltos con ella, sin ella, diferencia de costo relativo medio. Es la prueba de que cada lección importa.

## `graficas.py`

1. **Casos resueltos por versión** (barras v0, v1, v2, v3), separando aprendizaje (`_a`) de generalización (`_b` + reservados).
2. **Costo relativo por caso y versión** (puntos conectados por caso), con la línea de `UMBRAL_RESUELTO`.
3. **Ablación:** una barra por lección con lo que se pierde al quitarla.

Simple y legible a 3 metros: títulos en español, nada de leyendas innecesarias.

## `demo.py`: los 3 minutos

Script que imprime paso a paso, con pausas de Enter, usando resultados ya guardados (nada en vivo que pueda fallar, salvo una iteración corta opcional):

- **0:00–0:40, el problema:** cada vez que una empresa lleva una predicción a un proceso nuevo, repite errores. Un ejemplo de cada patrocinador (crédito, churn, demanda).
- **0:40–1:45, el sistema:** v0 falla en crédito → la lección (su `SKILL.md`) → el diff `v0 → v1`. Repetir rápido con churn y demanda, mostrando la fecha que el diagnóstico revisó.
- **1:45–3:00, la prueba:** gráfica 1, gráfica 3 (ablación), qué hizo Codex, qué intervenciones humanas hubo y qué no funcionó.

## Orden de trabajo

1. `humo.py` con falsos (justo después de `comun/`).
2. `banco.py` con el ciclo fijo de Paco: sale la primera gráfica aunque todavía no haya LLM.
3. `cadena.py` cuando estén curador y constructor.
4. `ablacion.py`, `graficas.py` finales.
5. `demo.py` y ensayo cronometrado.

## Hecho cuando

- `python -m experimento.humo` pasa en las ramas de los tres.
- `salidas/banco_v0.csv`, `banco_v1.csv`, `banco_v2.csv` existen con los mismos casos.
- Las tres gráficas están en `docs/figuras/`.
- `demo.py` corre en menos de 3 minutos sin conexión a la API.

Registra en `CODEX_LOG.md` lo que Codex haya escrito aquí.
