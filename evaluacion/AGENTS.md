# evaluacion/ — el evaluador

**Dueño:** Diego. **Lo usan:** Paco (el ciclo) y Eduardo (el banco y la ablación).

Lee primero el `AGENTS.md` de la raíz y `comun/AGENTS.md`. No toques `comun/`, `agentes/`, `memoria/` ni `experimento/`.

**Regla de oro:** el evaluador es el juez. Ningún agente lo puede modificar ni llamar con parámetros fuera del contrato. Si hay que cambiar cómo se mide, se cambia antes de correr v0 y se anota en `INTERVENCIONES.md`.

## Archivos

```
evaluacion/
  __init__.py
  registro.py        # nombre de modelo -> estimador de scikit-learn / LightGBM
  variables.py       # catálogo de generadores de variables para series
  costos.py          # costo de clasificación y de serie, umbral por costos
  fuga.py            # AUC por columna
  evaluador.py       # evaluar(...)
  pruebas.py         # python -m evaluacion.pruebas
```

## Función pública (firma exacta)

```python
from comun.contratos import Problema, Candidato, Capacidades, Resultado, Modo

def evaluar(problema: Problema, candidato: Candidato, capacidades: Capacidades,
            modo: Modo = "validacion", version: str = "v0") -> Resultado:
    """Nunca lanza excepción: si algo falla, devuelve Resultado con error lleno,
    costo_relativo=999.0 y resuelto=False."""
```

- `candidato_id` = primeros 10 caracteres del sha1 de `candidato.model_dump_json()` + `problema.id`. Mismo candidato, mismo id.
- Semilla fija en todo (`problema.particion.semilla`). Mismo input, mismo resultado.
- Tiempo máximo por candidato: `config.LIMITE_SEGUNDOS_CANDIDATO`.

## Modos

Los datos se parten en tres pedazos fijos (misma semilla siempre):

| Pedazo | Clasificación | Serie |
| --- | --- | --- |
| prueba | `proporcion_prueba` estratificado | todo después de `fecha_corte_prueba` |
| producción | `proporcion_produccion` del resto, estratificado | las últimas `proporcion_produccion` fechas antes del corte |
| entrenamiento | lo que queda | lo que queda |

| Modo | Qué hace | Quién lo ve |
| --- | --- | --- |
| `validacion` | Clasificación: `cross_val_predict(method="predict_proba", cv=folds)` sobre entrenamiento. Serie: `TimeSeriesSplit(n_splits=3)` sobre entrenamiento, solo con el pasado | Agentes, en cada iteración |
| `produccion` | Entrena en entrenamiento, predice el pedazo de producción | El curador, una vez por problema (lo pide el ciclo de Paco al final) |
| `prueba` | Entrena en entrenamiento + producción, predice el pedazo de prueba | Solo el banco de Eduardo. Nadie aprende de aquí |

## Registro de modelos

| `modelo` | Clasificación | Serie |
| --- | --- | --- |
| `referencia` | Nunca actuar (predice siempre la clase negativa, p = 0) | Repetir el valor de hace 7 días |
| `logistica` | `LogisticRegression(max_iter=1000)` con escalado y one-hot | No aplica: devuelve `error` |
| `arbol` | `DecisionTreeClassifier` | `DecisionTreeRegressor` sobre las variables |
| `lightgbm` | `LGBMClassifier(verbose=-1)` | `LGBMRegressor(verbose=-1)` sobre las variables |

Hiperparámetros permitidos (los demás se ignoran y se anota en `alertas`):
- `logistica`: `C`
- `arbol`: `max_depth`, `min_samples_leaf`
- `lightgbm`: `n_estimators`, `learning_rate`, `num_leaves`, `min_child_samples`

Clasificación: probabilidades calibradas con `CalibratedClassifierCV(cv=3)` excepto la referencia.

## Catálogo de variables (series)

`candidato.features` solo acepta estos nombres; cualquier otro se ignora con alerta.

| Nombre | Qué genera | Requiere capacidad |
| --- | --- | --- |
| `rezagos` | valores de hace 7, 14 y 28 días | no |
| `medias_moviles` | media de 7 y 28 días, desplazada un día | no |
| `dia_semana` | día de la semana | no |
| `calendario` | festivo, quincena, fin de mes, días al festivo más cercano, evento | `variables_calendario` |

Todo desplazado: ninguna variable puede usar el valor del mismo día. Si piden `calendario` sin la capacidad, se ignora y se anota `alerta: "calendario no disponible en esta versión"`. **Esa alerta es la señal que el curador puede usar.**

## Capacidades

### `umbral_por_costos` (clasificación)

- Apagada: actuar si `p > 0.5`.
- Encendida: actuar si `p > costo_fp / (costo_fp + costo_fn)`.

### `revisar_fuga` (clasificación)

- **Siempre:** calcula el AUC de cada columna sola contra el objetivo (en entrenamiento). Si alguna pasa 0.95, agrega `alerta: "posible_fuga: <columna> (AUC 0.99)"` y `metricas["max_auc_columna"]`.
- Encendida: además quita automáticamente esas columnas antes de entrenar.
- `candidato.excluir_columnas` se respeta siempre, con o sin la capacidad.

Importante: con fuga, el modelo saca un costo de validación bajísimo. Para que la falla sea real, **en los pedazos de producción y prueba de churn la columna con fuga se reemplaza por ruido** (en la vida real ese dato todavía no existe cuando hay que decidir). Así v0 se ve excelente en validación y mal en producción, y el curador tiene la alerta para explicar la diferencia. Anótalo en `INTERVENCIONES.md`.

### `variables_calendario` (serie)

Habilita la variable `calendario` (arriba).

## Costos

```python
def costo_clasificacion(y, actuar, costos) -> float:
    fn = ((y == 1) & (actuar == 0)).sum(); fp = ((y == 0) & (actuar == 1)).sum()
    return costos.costo_fn * fn + costos.costo_fp * fp

def costo_serie(real, pred, costos) -> float:
    return (costos.costo_faltante * np.maximum(real - pred, 0)
            + costos.costo_sobrante * np.maximum(pred - real, 0)).sum()
```

- `costo_referencia`: el del modelo `referencia` con la misma partición y modo (cachéalo por problema y modo).
- Protege el caché de `costo_referencia` con `threading.Lock`: `evaluar` puede ejecutarse desde 3 hilos a la vez.
- Configura todos los modelos con `n_jobs=1` (LightGBM y cualquier otro estimador que acepte ese parámetro) para no saturar los núcleos.
- `costo_relativo = costo / costo_referencia`. `resuelto = costo_relativo < config.UMBRAL_RESUELTO`.

## Resultado

- `metricas`, clasificación: `auc`, `umbral`, `tasa_fn`, `tasa_fp`, `max_auc_columna`.
- `metricas`, serie: `mae`, `sesgo` (media de pred − real), `costo_dias_festivos` (porción del costo en festivos y quincenas).
- `peores_casos`: los 10 con mayor costo. Serie: la fecha en `referencia`. Clasificación: el índice de fila.

## Orden de trabajo

1. **Primera entrega:** `evaluar` para clasificación con `referencia` y `logistica`, umbral 0.5 y por costos. Prueba con `credito_a`.
2. `arbol`, `lightgbm`, hiperparámetros.
3. `revisar_fuga` y el holdout con ruido para churn.
4. Series: referencia, catálogo de variables, `TimeSeriesSplit`, `calendario`.
5. Modo `prueba` completo y caché de referencia.

## Hecho cuando (`python -m evaluacion.pruebas`)

- `credito_a`, `logistica`: el costo con umbral por costos es menor que con 0.5.
- `churn_a`, `lightgbm`: aparece la alerta de fuga; sin `revisar_fuga` el costo en `produccion` es mucho peor que en `validacion`; con `revisar_fuga` la diferencia casi desaparece.
- `demanda_a`, `lightgbm` con `rezagos`: con `calendario` y la capacidad, `costo_dias_festivos` baja.
- Un candidato inválido (`logistica` en serie) devuelve `error`, no excepción.
- Dos llamadas idénticas dan el mismo `costo`.
- Cada evaluación tarda menos de 10 segundos.

Imprime una tabla con esos números; Eduardo la usa para la gráfica y Paco para ver que hay espacio para mejorar.

Registra en `CODEX_LOG.md` lo que Codex haya escrito aquí.
