# Registro de uso de Codex

Una entrada por uso relevante. La rúbrica califica la aplicación de Codex (25%): esto es la evidencia.

| Hora | Quién | Carpeta | Qué se le pidió | Qué produjo | Qué se aceptó / cambió a mano |
| --- | --- | --- | --- | --- | --- |
| 12:50 | Eduardo | docs | Actualizar documentación del repo con los acuerdos de puertos falsos, banco, versiones, SQLite, caché y paralelismo | Actualicé los AGENTS.md solicitados y agregué `.gitattributes` con merge union para los registros | Aceptado |
| 13:00 | Eduardo | comun | Crear `contratos.py` y `config.py` exactamente según las secciones 1 y 2 de `comun/AGENTS.md` | Creé las clases Pydantic del contrato y las constantes del experimento | Aceptado; sin cambios manuales |
| 13:12 | Eduardo | comun | Crear `falsos.py` y `puertos.py` según secciones 3 y 4; determinar llaves de huella y contexto desde `datos/AGENTS.md` | Implementé datos falsos deterministas y selección independiente por puerto | Aceptado; corregido a mano: AttributeError en puertos y cálculo de quincena en falsos |
| 13:20 | Eduardo | memoria | Crear `memoria/pruebas.py` con tres pruebas SQLite temporales según la firma de `Almacen` | Añadí pruebas ejecutables con assert para guardar/leer, filtros de historial y lecciones inexistentes | Aceptado; sin cambios manuales |
| 13:41 | Eduardo | memoria | Implementar `Almacen` SQLite según `memoria/AGENTS.md` y hacer pasar `memoria/pruebas.py` | Añadí esquema, persistencia JSON, filtros, lectura ordenada, cierre y context manager | Aceptado; pruebas corridas a mano en WSL: 3 OK |
