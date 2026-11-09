# Diagnóstico

Compara los resultados de esta iteración con el historial y las lecciones activas aplicables. Usa `historial_intentos()` y consulta `peores_casos(candidato_id)` cuando ayude a explicar el desempeño. Basa tus conclusiones en métricas, alertas y casos observados; distingue los hechos de las hipótesis y recomienda un cambio concreto que pueda probar la siguiente iteración. Decide si vale la pena continuar.

Devuelve únicamente la salida estructurada `Diagnostico`:
- `que_fallo`: problema principal observado, o indica que no se observa una falla clara.
- `por_que`: explicación breve apoyada en la evidencia disponible.
- `evidencia`: lista de métricas, alertas, identificadores o casos que respalden el análisis.
- `que_probar`: siguiente cambio concreto; si no hay uno razonable, indícalo.
- `seguir`: `true` si otra iteración puede aportar información o mejorar resultados; `false` si no.
<!-- leccion:L001 -->
- (L001) Cuando los costos de error son asimétricos, elige el umbral con los costos explícitos y el desempeño en validación; no asumas que 0.5 minimiza el costo.
<!-- /leccion:L001 -->
<!-- leccion:L002 -->
- (L002) Antes de aceptar métricas altas, revisa columnas que revelen información posterior al momento de decisión o que predigan casi perfectamente el objetivo; exclúyelas y vuelve a validar.
<!-- /leccion:L002 -->
