# Intervenciones humanas

Todo cambio manual a datos, evaluación, versiones, lecciones o instrucciones que afecte lo que el sistema aprende. La rúbrica pide distinguir lo que hizo el sistema de lo que hicimos nosotros.

| Hora | Quién | Qué cambió | Por qué | ¿Afecta la demo? |
| --- | --- | --- | --- | --- |
| | Diego | Columna `dias_desde_baja` en churn como fuga controlada; ruido en producción y prueba | Probar si el sistema detecta fuga | Sí, se dice al presentar |
| | Paco | Instrucciones genéricas de v0 | Punto de partida; sin lecciones incluidas | Sí, v0 es la línea base |
| | Diego | Muestra estratificada de 3000 filas (semilla 42) en churn | Mantener la evaluación por debajo de 10 s | No, es un detalle técnico |
| | Diego | Serie de demanda sintética con efectos de calendario (demanda, demanda_b y demanda_r) | Tener un caso donde la lección de calendario sí ayude | Sí, se dice al presentar |
| | Diego | Umbral de resuelto 0.9 contra referencia "nunca actuar" (clasificación) o valor de hace 7 días (series) | Criterio de evaluación acordado con el equipo | Sí, define qué cuenta como resuelto |