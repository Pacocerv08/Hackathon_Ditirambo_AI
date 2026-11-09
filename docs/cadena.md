# Ejecución de la cadena

## Paso 1: credito_a
- Versión usada: v0
- Caso: credito_a
- Costo relativo validación: 0.6944444444444444
- Costo relativo producción: 0.6355555555555555
- Alertas: ninguna
- Lecciones:
  - L001 (capacidad=umbral_por_costos): Cuando los costos de error son asimétricos, elige el umbral con los costos explícitos y el desempeño en validación; no asumas que 0.5 minimiza el costo.
- Versión resultante: v1

## Paso 2: churn_a
- Versión usada: v1
- Caso: churn_a
- Costo relativo validación: 0.01202928870292887
- Costo relativo producción: 0.8760504201680672
- Alertas: posible_fuga: dias_desde_baja (AUC 0.99)
- Lecciones:
  - L002 (capacidad=revisar_fuga): Antes de aceptar métricas altas, revisa columnas que revelen información posterior al momento de decisión o que predigan casi perfectamente el objetivo; exclúyelas y vuelve a validar.
- Versión resultante: v2

## Paso 3: demanda_a
- Versión usada: v2
- Caso: demanda_a
- Costo relativo validación: 0.8557728235094254
- Costo relativo producción: 1.0871360189026964
- Alertas: ninguna
- Lecciones:
  - L003 (capacidad=variables_calendario): Si los costos se concentran en fechas especiales, revisa si el modelo representa esos efectos y evalúa variables de calendario con validación temporal.
- Versión resultante: v3
