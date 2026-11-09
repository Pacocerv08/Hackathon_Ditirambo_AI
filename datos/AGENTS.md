# datos/ — problemas, huella y contexto de fechas

**Dueño:** Diego. **Lo usan:** Paco (`agentes/`) y Eduardo (`memoria/`, `experimento/`).

Lee primero el `AGENTS.md` de la raíz y `comun/AGENTS.md` (los contratos). No toques `comun/`, `agentes/`, `memoria/` ni `experimento/`.

## Archivos

```
datos/
  __init__.py
  descargar.py        # baja los datasets crudos a datos/crudos/ (no se sube a git)
  preparar.py         # crudos -> datos/procesados/*.parquet
  problemas/          # un JSON por caso del banco, con forma de Problema
    credito_a.json
    credito_b.json
    churn_a.json
    churn_b.json
    demanda_a.json
    demanda_b.json
    (reservados: credito_r.json, churn_r.json, demanda_r.json)
  problemas.py        # listar_problemas, cargar_problema, cargar_datos
  huella.py           # huella(problema)
  contexto.py         # contexto_de_fecha(fecha, pais)
```

Agrega `datos/crudos/` a `.gitignore`. Los parquet procesados sí se suben si pesan menos de 5 MB; así nadie depende de internet durante la demo.

## Funciones públicas (firmas exactas)

```python
from comun.contratos import Problema
import pandas as pd

def listar_problemas(reservados: bool | None = False) -> list[str]:
    """ids de datos/problemas/. False: solo los de aprendizaje. True: solo reservados. None: todos."""

def cargar_problema(id: str) -> Problema: ...

def cargar_datos(problema: Problema) -> pd.DataFrame:
    """Lee problema.archivo. Clasificación: objetivo ya en 0/1, con 1 = clase_positiva.
    Serie: ordenado por columna_fecha, una fila por día, sin huecos."""

def huella(problema: Problema) -> dict[str, float]:
    """Solo números sobre la FORMA de los datos, nunca sobre el tema."""

def contexto_de_fecha(fecha: str, pais: str | None = None) -> dict:
    """fecha en 'YYYY-MM-DD'."""
```

## Los tres problemas

### Crédito (v0): `credit-g`

- `sklearn.datasets.fetch_openml("credit-g", version=1, as_frame=True)`.
- `clase_positiva="bad"` (300 de 1000).
- Costos: `costo_fn=5`, `costo_fp=1`. Justificación: es la matriz de costos documentada del dataset (aprobar a un mal pagador cuesta 5 veces más que rechazar a uno bueno).
- `credito_a` y `credito_b` son el mismo dataset con distinta `semilla` de partición (42 y 7). `credito_r` (reservado) usa semilla 123.
- Con umbral 0.5 el costo sale alto; con umbral por costos (≈0.167) baja. **Esa es la falla que v0 debe descubrir.** Verifícalo tú a mano antes de integrar y anota los dos números en tu PR.

### Churn (v1): con una columna con fuga controlada

- Telco Customer Churn (OpenML o Kaggle). Si no hay acceso, un churn sintético con `make_classification` con nombres de columnas de negocio.
- `clase_positiva="churn"`. Costos sugeridos: `costo_fn=4` (perder un cliente), `costo_fp=1` (descuento de retención innecesario).
- **Fuga controlada:** agrega una columna que delate el objetivo, por ejemplo `dias_desde_baja` (vale 0 si no hubo baja y un número si sí la hubo, con un poco de ruido). Debe parecer una columna normal.
- Anótalo en `INTERVENCIONES.md`: "Diego agregó `dias_desde_baja` a churn como fuga controlada para probar si el sistema la detecta". En la demo se dice.
- `churn_a`, `churn_b` con semillas distintas, `churn_r` reservado.

### Demanda (v2): serie diaria con calendario mexicano

- **Primero sintético** (para no depender de Kaggle): 3 años diarios desde 2022-01-01, `pais="MX"`.
  - Base + tendencia suave + estacionalidad semanal + ruido.
  - Picos en quincena (días 15 y último del mes) y caída o pico en festivos de `holidays.Mexico()`.
  - Algunos eventos fuertes (Buen Fin, por ejemplo) que solo se explican con el calendario.
- Costos: `costo_faltante=3`, `costo_sobrante=1` (vender de menos cuesta más que guardar de más).
- `fecha_corte_prueba` = último 20% de las fechas.
- `demanda_a` y `demanda_b`: dos series con distinta semilla y distintos productos o tiendas. `demanda_r` reservado.
- Favorita o M5: solo si sobra tiempo, con el mismo formato.

## `huella`

Clasificación:
- `filas`, `columnas`, `proporcion_positiva`, `pct_faltantes`, `pct_categoricas`
- `max_auc_columna`: el AUC más alto de una sola columna contra el objetivo (cuidado: para la fuga debe salir cerca de 1).

Serie:
- `longitud`, `pct_ceros`, `cv` (coeficiente de variación)
- `fuerza_semanal` (autocorrelación en rezago 7), `tendencia` (pendiente normalizada)
- `pct_dias_atipicos`: días con error de la referencia > 3 desviaciones.

Todas las llaves presentes siempre para su tipo, en `float`. Memoria compara huellas por distancia, así que no cambies nombres una vez publicado.

## `contexto_de_fecha`

Ejemplo de salida:

```python
{
  "fecha": "2024-11-15",
  "dia_semana": "viernes",
  "es_festivo": False, "nombre_festivo": None,
  "es_quincena": True, "es_fin_de_mes": False,
  "evento": "Buen Fin",          # de la tabla de eventos del dataset, si la hay
  "dias_a_festivo_mas_cercano": 3,
}
```

Usa `holidays.country_holidays(pais)` y una tabla `datos/eventos.csv` (fecha, pais, evento). Sin `pais`, solo campos de calendario.

## Orden de trabajo

1. **Primera entrega:** `credito_a.json`, `cargar_problema`, `cargar_datos` para crédito. Avisa a Paco y Eduardo.
2. `huella` para clasificación.
3. Churn con la fuga, y `huella` incluyendo `max_auc_columna`.
4. Demanda sintética, `contexto_de_fecha`, `huella` para serie.
5. Casos `_b` y reservados.

## Hecho cuando

- `python -m datos.problemas` imprime los ids y una línea por problema con filas, columnas y proporción positiva o longitud.
- `cargar_datos(cargar_problema(x))` funciona para los 9 ids sin internet.
- `huella` de churn tiene `max_auc_columna > 0.95`; la de crédito, no.
- `contexto_de_fecha("2024-09-16", "MX")["es_festivo"]` es `True`.

Registra en `CODEX_LOG.md` lo que Codex haya escrito aquí.
