# Registro de uso de Codex

Una entrada por uso relevante. La rúbrica califica la aplicación de Codex (25%): esto es la evidencia.

| Hora | Quién | Carpeta | Qué se le pidió | Qué produjo | Qué se aceptó / cambió a mano |
| --- | --- | --- | --- | --- | --- |
| 12:50 | Eduardo | docs | Actualizar documentación del repo con los acuerdos de puertos falsos, banco, versiones, SQLite, caché y paralelismo | Actualicé los AGENTS.md solicitados y agregué `.gitattributes` con merge union para los registros | Aceptado |
| 13:00 | Eduardo | comun | Crear `contratos.py` y `config.py` exactamente según las secciones 1 y 2 de `comun/AGENTS.md` | Creé las clases Pydantic del contrato y las constantes del experimento | Aceptado; sin cambios manuales |
| 13:12 | Eduardo | comun | Crear `falsos.py` y `puertos.py` según secciones 3 y 4; determinar llaves de huella y contexto desde `datos/AGENTS.md` | Implementé datos falsos deterministas y selección independiente por puerto | Aceptado; corregido a mano: AttributeError en puertos y cálculo de quincena en falsos |
| 13:10 | Paco | versiones/v0/instrucciones | Crear instrucciones genéricas de v0 para analista, proponente y diagnóstico, sin mencionar umbral por costos, fuga ni calendario | Creó los 3 `.md` (28 líneas) con formatos de salida de la spec y catálogos de modelos, hiperparámetros y variables; verificó con `rg` que no hubiera palabras prohibidas | Aceptado; sin cambios manuales |
| 13:36 | Paco | agentes | Crear `esquemas.py` (Descripcion, Propuesta con exactamente 3 candidatos, Diagnostico) y `contexto.py` (ContextoCiclo) importando de `comun.contratos` | (completar al terminar) | (completar: aceptado / cambios a mano) |