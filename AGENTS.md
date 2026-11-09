# Contexto del proyecto: RSI Hackathon (KAVAK x OpenAI x Primero AI)

Este archivo da contexto a los asistentes de IA (Claude, Codex) de cada integrante del equipo. Léelo completo antes de ayudar. Si una petición contradice lo que dice aquí, avisa antes de actuar.

- **Equipo:** Paco, Diego y Eduardo.
- **Fecha:** lunes 9 de noviembre de 2026, durante el evento.
- **Repositorio:** `Pacocerv08/Hackathon_Ditirambo_AI` (GitHub).

---

## 1. El reto y cómo nos califican

**Consigna oficial:** construir un sistema de agentes que aprenda de sus ejecuciones y use lo aprendido para construir un **sistema sucesor funcional**. En la demo hay que mostrar qué cambió entre versiones y qué efecto tuvo ese cambio.

**Formato:** 3 minutos de demostración y 2 minutos de preguntas.

### Rúbrica (cuatro criterios, 25% cada uno)

1. **Impacto.** Quién se beneficia, qué problema resuelve y por qué importa. Medir un resultado con sentido para el problema (por ejemplo errores por lote, casos resueltos o tiempo de revisión). *Mostrar:* versión inicial contra sucesora sobre los mismos casos de evaluación; si se puede, casos que el sistema no vio al aprender, y explicar qué sigue fallando.
2. **Aplicación de Codex.** Contar cómo usamos Codex en el proyecto.
3. **Uso creativo de habilidades.** Cómo diseñamos el ciclo de aprendizaje: qué señal detectó una falla, cómo se guardó la lección y cómo se incorporó al construir el sucesor. *Mostrar:* una lección concreta que cambie el comportamiento del sucesor (en una prueba, una herramienta, una regla o un cambio en el flujo). Si el sucesor vuelve a aprender y crea otra versión, mostrar qué se acumuló.
4. **Demostración y presentación.** Que sea fácil seguir la secuencia falla → decisión del sistema → resultado de la siguiente versión. Distinguir las acciones del sistema de las intervenciones del equipo. *Mostrar:* un caso representativo, el cambio que produjo el sistema, y el antes y después. Si usamos una base previa, decir qué trajimos y qué construimos durante el hackathon.

### Guía oficial para la demo

- **0:00–0:40, versión inicial.** El problema en una frase. Correr el caso, señalar dónde se rompe y qué resultado se esperaba. Enseñar el registro, la salida o la prueba que hace visible la falla.
- **0:40–1:45, qué aprendió y qué construyó.** Abrir la lección guardada y señalar qué parte del sucesor cambió por ella. Mostrar al sucesor haciendo su tarea. Si hubo intervención humana, decir en qué punto.
- **1:45–3:00, comparar resultados.** Correr las versiones sobre los mismos casos de evaluación y explicar qué se atribuye a la lección. Cerrar contando cómo usamos Codex.

**Ejemplo oficial (pedidos → devoluciones → reembolsos):**
- La versión inicial duplica un evento y guarda una regla de deduplicación.
- El primer sucesor (devoluciones) usa esa regla, pero descubre otra falla: confirmó una devolución que nunca se guardó.
- El segundo sucesor (reembolsos) conserva ambas lecciones.
- En un banco común de seis casos, las tres versiones resuelven 2, 4 y 6. **Si se desactiva una lección, vuelve la falla correspondiente.**

**Preguntas del jurado:** tener a mano una ejecución, la lección que salió de ella y el cambio que heredó el sucesor. Pueden preguntar cómo aislamos el efecto del cambio (respuesta: desactivando la lección) o qué haría fallar la última versión.

### Consecuencias para nuestro diseño

- El centro es la **cadena falla → lección → sucesor → mejor resultado en los mismos casos**, no una estadística agregada.
- Cada lección debe poder **apagarse** para demostrar que la falla vuelve.
- Todo cambio hecho a mano por el equipo se registra como **intervención humana**.
- **Codex vale 25%:** hay que usarlo de verdad y documentarlo (sección 10).

---

## 2. El proyecto

### En una frase

Un sistema de agentes que resuelve problemas de predicción para tomar decisiones de negocio, aprende de sus fallas y construye versiones sucesoras de sí mismo que ya no cometen esos errores.

### El problema y el impacto

Las empresas predicen algo para tomar una decisión, y equivocarse para un lado casi nunca cuesta lo mismo que para el otro:
- Aprobar un crédito a quien no paga cuesta más que rechazar a un buen cliente.
- Quedarse sin producto cuesta distinto que tener de más.

Hoy, para cada problema nuevo, una persona que sabe de modelos repite el mismo trabajo: entender los datos, elegir un modelo, decidir cómo usar la predicción y validar.

**Quién se beneficia:**
- Empresas como Kavak (créditos, precios de autos).
- Los clientes de Primero AI (inventario, cancelaciones, revisión de cobros).
- Cualquier equipo que despliega modelos de predicción en procesos nuevos.

**Métrica principal:** costo en dinero de las decisiones, relativo a una referencia simple, sobre un banco fijo de casos. Métrica de apoyo: casos resueltos (sección 6).

### La frase del pitch

"Cada vez que una empresa lleva una predicción a un proceso nuevo, alguien repite los mismos errores. Nuestro sistema aprende de cada falla, guarda la lección y construye una versión sucesora de sí mismo que ya no la comete, aunque el siguiente problema sea de otra industria."

### Estadística: la hacen las librerías

Nadie del equipo es estadístico, y no hace falta. Usamos métodos estándar de scikit-learn y LightGBM. La contribución del proyecto es el ciclo de aprendizaje y los sucesores, no los modelos. Si un juez pregunta, eso es lo que respondemos.

---

## 3. La cadena de versiones que vamos a demostrar

Es el guion principal de la demo. Cada versión resuelve una tarea y hereda lo aprendido por las anteriores, igual que el ejemplo oficial.

### v0: riesgo de crédito (clasificación)

- **Tarea:** decidir a quién aprobar un crédito.
- **Falla esperada:** usa el umbral por defecto de 0.5 y aprueba a muchos que no pagan.
- **Señal que la detecta:** el diagnóstico ve que casi todo el costo viene de falsos negativos (impagos aprobados).
- **Lección:** "Con costos desiguales, calcula el umbral con la fórmula de costos y calibra las probabilidades."
- **Tipo de cambio:** chequeo en el flujo de decisión.

### v1: cancelación de clientes (clasificación), hereda la lección de v0

- **Tarea:** decidir a qué clientes ofrecer un descuento de retención.
- **Falla esperada:** una columna delata la respuesta (fuga de información) y el resultado en validación es sospechosamente bueno, pero no se sostiene en los casos reservados.
- **Señal:** brecha grande entre el resultado en validación y en reservados, o una sola variable con importancia desproporcionada.
- **Lección:** "Si el resultado es demasiado bueno, revisa variables que contienen información del resultado o del futuro y exclúyelas."
- **Tipo de cambio:** prueba automática antes de aceptar un candidato.

Si el dataset elegido no tiene una fuga natural, Diego puede agregar una columna con fuga de forma controlada. Si lo hacemos, se declara en la demo como preparación del equipo.

### v2: demanda diaria de una tienda (serie de tiempo), hereda las lecciones de v0 y v1

- **Tarea:** pronosticar demanda para decidir cuánto pedir.
- **Falla esperada:** errores grandes en días festivos y fechas especiales.
- **Señal:** los días con mayor error se concentran en ciertas fechas. El diagnóstico usa la herramienta `contexto_de_fecha` para revisar qué pasó esos días (festivo, quincena, fin de mes, evento del calendario del dataset).
- **Lección:** "Si los errores se concentran en fechas especiales, agrega variables de calendario (festivo, quincena, evento)."
- **Tipo de cambio:** nueva variable disponible para el modelo.

### Banco de casos y ablación

- Un banco fijo de casos (sección 6) sobre el que se corren v0, v1 y v2. Ejemplo de resultado esperado: 2, 4 y 6 casos resueltos.
- **Ablación:** al apagar cualquier lección, su falla debe volver. Se demuestra con un interruptor por lección en la configuración.

### Si sobra tiempo

Que el sistema genere una v3 por sí solo a partir de las fallas que queden en v2, para mostrar acumulación.

---

## 4. Arquitectura

### Agentes LLM (OpenAI Agents SDK)

| Agente | Cuándo corre | Recibe | Produce |
| --- | --- | --- | --- |
| Analista | Una vez por problema | Huella, estadísticas de los datos, tipo de tarea, costos | Descripción del problema en texto |
| Proponente | Cada iteración | Descripción, lecciones activas, historial de intentos, diagnóstico anterior | 3 candidatos |
| Diagnóstico | Cada iteración | Resultados de los candidatos, peores casos y su contexto | Qué falló, por qué y qué probar |
| Curador | Al terminar un problema | Todo lo que pasó en el problema | Lecciones nuevas, con la señal que las detectó y la evidencia |
| Constructor | Entre versiones | Versión actual y lecciones nuevas | La configuración de la versión sucesora |

### Piezas de código (sin LLM)

- **Evaluador:** entrena candidatos, decide con los costos y mide el costo. Los agentes no lo pueden tocar.
- **Coordinador:** reglas fijas de parada; por ejemplo, máximo 5 iteraciones o parar si 2 seguidas no mejoran.
- **Memoria:** SQLite con todo lo que pasa.

### Qué es una versión del sistema

Una versión es una carpeta `versiones/vN/` con:
- `config.json`: modelo de cada agente, interruptores de las capacidades activas (por ejemplo `umbral_por_costos`, `revisar_fuga`, `variables_calendario`) y lista de lecciones activas.
- `instrucciones/`: un archivo de texto por agente.
- `lecciones/`: un archivo Markdown por lección activa, legible en la demo.
- `cambios.md`: qué cambió respecto a la versión padre y quién lo cambió (sistema o equipo).

**El constructor** lee las lecciones nuevas y escribe la versión `vN+1`:
- Activa las capacidades que correspondan.
- Agrega reglas a las instrucciones de los agentes.
- Copia los archivos de las lecciones.

Así el cambio entre versiones es un diff visible.

**Honestidad en la demo:** las capacidades (umbral por costos, revisión de fuga, variables de calendario) las programa el equipo como herramientas disponibles. El sistema decide cuándo activarlas y con qué reglas. Eso se dice explícitamente al presentar.

### Cómo se ve un ciclo por problema

1. El analista describe el problema.
2. El proponente sugiere 3 candidatos usando las lecciones activas.
3. El evaluador los califica (en paralelo).
4. El diagnóstico explica qué falló, revisando los peores casos y su contexto.
5. El coordinador decide si hay otra iteración (volver al paso 2) o se termina.
6. Al terminar, el mejor candidato se evalúa una vez en producción y el curador escribe lecciones comparando validación contra producción.
7. Entre problemas, el constructor genera la versión sucesora.

---

## 5. Datos

| Versión | Tarea | Dataset sugerido | Cómo obtenerlo |
| --- | --- | --- | --- |
| v0 | Riesgo de crédito | German Credit (`credit-g`) | `sklearn.datasets.fetch_openml("credit-g")` |
| v1 | Cancelación de clientes | Un dataset público de churn (OpenML o Kaggle Telco Customer Churn) | OpenML desde scikit-learn, o Kaggle con cuenta |
| v2 | Demanda diaria | Una tienda de Favorita (trae archivo de festivos y eventos) o una serie de M5 (trae calendario de eventos) | Kaggle con cuenta |

- Muestras pequeñas: cada evaluación debe tardar segundos.
- Los costos de cada error los define el equipo, con una justificación de una frase en el `Problema`.
- El contexto de fechas sale del calendario del dataset más la librería `holidays` de Python.

---

## 6. Evaluación

### Cómo se califica un candidato

1. **Traducir el candidato a un modelo** con el registro de Diego (por ejemplo `"logistica"` → regresión logística de scikit-learn).
2. **Construir variables** con los generadores permitidos.
3. **Obtener predicciones sin usar datos ya vistos:**
   - Clasificación: `cross_val_predict` con probabilidades, calibradas con `CalibratedClassifierCV`.
   - Serie: validación por ventanas de tiempo, entrenando solo con el pasado.
4. **Decidir con los costos:**
   - Clasificación (clase positiva = el error caro, por ejemplo impago): actuar si `p > costo_FP / (costo_FP + costo_FN)`. Sin la lección de v0, el umbral es 0.5.
   - Serie: costo por día = `costo_faltante * max(real - pronostico, 0) + costo_sobrante * max(pronostico - real, 0)`.
5. **Costo relativo** = costo del candidato / costo de la referencia simple en el mismo caso. Menos de 1 es mejor que la referencia.

### Tres pedazos de datos por problema

- **Validación:** lo que ven los agentes en cada iteración.
- **Producción:** al terminar un problema, el candidato elegido se evalúa una vez aquí. Simula "lo pusimos en producción y así le fue". Es la señal principal del curador: si producción es mucho peor que validación, algo se aprendió mal (por ejemplo, fuga).
- **Prueba:** solo para el banco de casos. Nadie aprende de aquí.

### Banco de casos

- Un **caso** es una combinación fija de problema, partición de datos y costos.
- El banco tiene unos 6 casos repartidos entre las tres tareas, más casos reservados que ninguna versión ve al aprender.
- Un caso está **resuelto** si su costo relativo es menor a 0.9.
- Todas las versiones se corren sobre exactamente el mismo banco, con semillas fijas.

### Salvaguardas

- Los agentes solo producen configuraciones con valores permitidos, nunca código libre.
- El evaluador está fuera del alcance de los agentes.
- El presupuesto de iteraciones es igual para todas las versiones.

---

## 7. Contratos (`comun/contratos.py`)

Clases de Pydantic que todos respetan. **El código exacto está en `comun/AGENTS.md`**; esta sección es solo el resumen. Los cambios a ese archivo se avisan a los tres.

- **Problema:** `id`, `dominio`, `tipo_tarea` (`"clasificacion"` o `"serie"`), `descripcion_negocio`, `archivo`, `objetivo`, `columna_fecha`, `clase_positiva`, `pais`, `costos` (`costo_fn` y `costo_fp`, o `costo_faltante` y `costo_sobrante`, con justificación), `particion`, `reservado`.
- **Candidato:** `modelo` (valor permitido del registro), `features` (series), `excluir_columnas` (clasificación), `hiperparametros` (pares `nombre` y `valor`, para que funcione con salidas estructuradas), `justificacion`.
- **Capacidades:** interruptores `umbral_por_costos`, `revisar_fuga`, `variables_calendario`.
- **Resultado:** `problema_id`, `candidato_id`, `version`, `modo` (`validacion`, `produccion` o `prueba`), `costo`, `costo_referencia`, `costo_relativo`, `resuelto`, `metricas`, `alertas`, `peores_casos`, `segundos`, `error`.
- **Leccion:** `id`, `version_origen`, `problema_origen`, `senal`, `evidencia`, `texto`, `tipo_cambio` (`regla`, `chequeo`, `variable` o `flujo`), `capacidad` (qué interruptor enciende en el sucesor, si alguno), `regla_para` (a qué agentes se les agrega como regla), `alcance`, `activa`, `veces_usada`, `veces_que_ayudo`.
- **Version:** `id` (`v0`, `v1`...), `padre`, `capacidades`, `lecciones_activas`, `creada_por` (`sistema` o `equipo`), `cambios`.
- **ResultadoCiclo:** lo que devuelve un problema resuelto por una versión: mejor candidato, mejor resultado, historial, diagnósticos y el resultado en producción.

### Funciones públicas entre carpetas

| Función | Dueño | Quién la usa |
| --- | --- | --- |
| `cargar_problema(id) -> Problema`, `listar_problemas()`, `cargar_datos(problema)` | Diego (`datos/`) | Paco, Eduardo |
| `huella(problema) -> dict` | Diego (`datos/`) | Paco, Eduardo |
| `contexto_de_fecha(fecha, pais) -> dict` | Diego (`datos/`) | Paco |
| `evaluar(problema, candidato, capacidades, modo, version) -> Resultado` | Diego (`evaluacion/`) | Paco, Eduardo |
| `resolver(problema, version, run_id) -> ResultadoCiclo` | Paco (`agentes/`) | Eduardo |
| `cargar_version(id) -> Version`, `Almacen` | Eduardo (`memoria/`) | Paco |
| `curar(...) -> list[Leccion]`, `construir_sucesor(...) -> Version` | Eduardo (`memoria/`) | Eduardo (`experimento/`) |

Todos importan `evaluar`, `huella` y `contexto_de_fecha` desde `comun/puertos.py`, que elige entre la versión real y la falsa.

### Herramientas de los agentes

Son adaptadores delgados a funciones de Diego y Eduardo. Devuelven respuestas cortas.

- `resumen_datos()`: huella y estadísticas básicas.
- `consultar_lecciones()`: lecciones activas de la versión, ordenadas por relevancia.
- `historial_intentos()`: candidatos ya probados en este problema y sus resultados.
- `peores_casos(candidato_id)`: filas o fechas con mayor error.
- `contexto_de_fecha(fecha)`: si fue festivo, quincena, fin de mes, o un evento del calendario del dataset.

Los agentes **no** tienen herramienta para evaluar: el ciclo en código evalúa, para que el presupuesto sea el mismo para todas las versiones.

---

## 8. Estructura del repositorio y dueños

```
comun/          Eduardo   contratos.py, config.py, falsos.py
datos/          Diego     carga de datasets, problemas, huella, contexto de fechas
evaluacion/     Diego     registro de modelos, evaluar(), costos, banco de casos
agentes/        Paco      analista, proponente, diagnóstico, herramientas, ciclo
memoria/        Eduardo   SQLite, lecciones, curador, constructor
versiones/      sistema   v0/, v1/, v2/ (escritas por el constructor)
experimento/    Eduardo   correr el banco por versión, ablación, gráficas, demo
salidas/        (no se sube) base de datos, figuras, logs
```

- Cada carpeta tiene su propio `AGENTS.md` con lo concreto: archivos, firmas, orden de trabajo y cuándo está terminado. Codex lo lee al trabajar dentro de esa carpeta, junto con este.
- Todo se corre desde la raíz con `python -m`, por ejemplo `python -m experimento.humo`.
- Cada quien trabaja en su rama y solo en su carpeta.
- Mientras una pieza no está lista, los demás usan su versión falsa en `comun/falsos.py`, con la misma firma.

---

## 9. Reparto

### Diego: datos y evaluador (`datos/`, `evaluacion/`)

- Cargar los tres datasets y convertirlos en `Problema`, con costos justificados.
- Huella:
  - Clasificación: desbalance, filas, variables, porcentaje de faltantes.
  - Serie: estacionalidad, tendencia, ceros, longitud.
- Registro de modelos:
  - Clasificación: referencia (clase mayoritaria), regresión logística, árbol, LightGBM.
  - Serie: referencia (repetir la semana pasada) y LightGBM con rezagos.
- `evaluar(problema, candidato) -> Resultado`, con las capacidades encendibles:
  - umbral por costos;
  - revisión de fuga;
  - variables de calendario.
- `contexto_de_fecha(fecha)` y el banco de casos.
- **Primera entrega:** el problema de crédito y `evaluar` con la referencia y la regresión logística.

### Paco: agentes (`agentes/`)

- Analista, proponente y diagnóstico con el Agents SDK.
- Herramientas de los agentes.
- El ciclo con las reglas del coordinador.
- Instrucciones en archivos de texto, leídas desde `versiones/vN/instrucciones/`.
- **Primera entrega:** el ciclo sin LLM (lista fija de modelos) contra el evaluador falso; luego el proponente.

### Eduardo: base común, memoria, sucesores y demo (`comun/`, `memoria/`, `experimento/`)

- **Primero:** contratos, config y falsos, para desbloquear a los demás.
- SQLite: ejecuciones, candidatos, resultados, llamadas a agentes, lecciones, versiones.
- Curador y constructor de versiones.
- Correr el banco por versión, la ablación de lecciones, las gráficas y la demo.
- **Primera entrega:** contratos y falsos; luego guardar resultados y una gráfica.

---

## 10. Codex (25% de la calificación)

**Mínimo, todos:**
- Usar Codex para programar partes reales del proyecto.
- Registrar cada uso relevante en `CODEX_LOG.md`: quién, qué se le pidió, qué produjo, qué se aceptó o se cambió a mano.

**Ambicioso, si da tiempo:**
- Que el constructor use Codex para aplicar las lecciones al código de la versión sucesora, por ejemplo escribiendo una nueva prueba o variable.
- Así Codex forma parte del ciclo de auto-mejora, no solo del desarrollo.

Confirmar con los organizadores qué acceso a Codex tenemos, y si "habilidades" en la rúbrica se refiere a *skills*. Si es así, guardar cada lección como un skill que el sucesor carga sería lo ideal.

---

## 11. Plan del día

1. **Juntos, 20 minutos:** confirmar llave de API, modelos habilitados y acceso a Codex. Cerrar contratos. Crear ramas.
2. **Primer bloque:** primeras entregas.
3. **Integración 1:** crédito de punta a punta con datos reales, sin LLM. Sale una gráfica.
4. **Segundo bloque:**
   - Paco: proponente y diagnóstico.
   - Diego: churn y demanda, con sus capacidades.
   - Eduardo: lecciones, curador y constructor.
5. **Integración 2:** v0 genera una lección y el constructor produce v1.
6. **Tercer bloque:**
   - Cadena completa v0 → v1 → v2.
   - Banco de casos y ablación.
   - `contexto_de_fecha` en el diagnóstico.
7. **Integración 3 y congelar:** solo se corrigen errores.
8. **Cierre:** correr el banco final, gráficas, ensayar los 3 minutos y preparar las respuestas.

---

## 12. Reglas de trabajo

- Nadie cambia `comun/` sin avisar a los tres.
- Antes de cada integración, correr `python -m experimento.humo` en la rama propia.
- Commits pequeños y frecuentes.
- **Commits de `versiones/`:** Eduardo hace commit de v1 en adelante; Paco puede hacer `git add`/commit solo de `versiones/v0/instrucciones/*.md`. `crear_v0()` escribe únicamente `versiones/v0/config.json` y nunca toca instrucciones.
- Nunca subir `.env` ni llaves de API.
- **Intervenciones humanas:** todo cambio manual a una versión, una lección o una instrucción se anota en `INTERVENCIONES.md` (qué, quién, cuándo, por qué). La rúbrica pide distinguirlas.
- Si alguien se atrasa, los demás siguen con los falsos.

### Recortes, en este orden, si vamos tarde

1. v3 automática.
2. Codex dentro del constructor (se queda solo como herramienta de desarrollo).
3. LightGBM en serie (se queda solo la referencia y un modelo).
4. Si todo falla: cadena de dos versiones, v0 → v1 en crédito y churn.

---

## 13. Glosario

- **Candidato:** un modelo estadístico o de ML con su configuración. No es un agente.
- **Huella:** números que describen la forma de los datos, no su tema. Sirve para saber qué lecciones aplican.
- **Lección:** algo que el sistema aprendió de una falla, con la señal que la detectó, la evidencia y el cambio que produce en el sucesor.
- **Sucesor:** la siguiente versión del sistema, construida a partir de las lecciones.
- **Costo relativo:** costo de una decisión dividido entre el de la referencia simple en el mismo caso.
- **Ablación:** apagar una lección para comprobar que su falla regresa.
- **Intervención humana:** cualquier cambio hecho por el equipo y no por el sistema.
