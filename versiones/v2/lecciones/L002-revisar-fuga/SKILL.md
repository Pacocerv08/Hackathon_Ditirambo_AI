---
name: l002-revisar-fuga
description: Antes de aceptar métricas altas, revisa columnas que revelen información posterior al momento de decisión o que predigan casi perfectamente el objetivo; exclúyelas y vuelve a validar.
---
## Señal
Los candidatos 22a0c5deda, 5931428c88 y 357c7720a0 recibieron una alerta de posible fuga porque una columna alcanzó AUC 0.99.
## Evidencia
22a0c5deda, 5931428c88, 357c7720a0
## Qué cambia en el sucesor
Capacidad: revisar_fuga. Agentes con regla: analista, proponente, diagnostico.
## Origen
Versión: v1. Problema: churn_a.
