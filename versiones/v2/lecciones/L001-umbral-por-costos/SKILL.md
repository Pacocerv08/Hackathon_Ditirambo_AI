---
name: l001-umbral-por-costos
description: Cuando los costos de error son asimétricos, elige el umbral con los costos explícitos y el desempeño en validación; no asumas que 0.5 minimiza el costo.
---
## Señal
Con umbral 0.5, los candidatos mantienen tasas de falsos negativos de alrededor de 0.66; los diagnósticos señalan casos reales de clase 1 con probabilidades inferiores a 0.5, aunque cada falso negativo cuesta cinco veces más que un falso positivo.
## Evidencia
db135b265a, 0d79463184, 5c5fb065b0
## Qué cambia en el sucesor
Capacidad: umbral_por_costos. Agentes con regla: analista, proponente, diagnostico.
## Origen
Versión: v0. Problema: credito_a.
