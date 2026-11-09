# Registro de uso de Codex

Una entrada por uso relevante. La rúbrica califica la aplicación de Codex (25%): esto es la evidencia.

| Hora | Quién | Carpeta | Qué se le pidió | Qué produjo | Qué se aceptó / cambió a mano |
| --- | --- | --- | --- | --- | --- |
| 12:50 | Eduardo | docs | Actualizar documentación del repo con los acuerdos de puertos falsos, banco, versiones, SQLite, caché y paralelismo | Actualicé los AGENTS.md solicitados y agregué `.gitattributes` con merge union para los registros | Aceptado |
| 13:00 | Eduardo | comun | Crear `contratos.py` y `config.py` exactamente según las secciones 1 y 2 de `comun/AGENTS.md` | Creé las clases Pydantic del contrato y las constantes del experimento | Aceptado; sin cambios manuales |
| 13:12 | Eduardo | comun | Crear `falsos.py` y `puertos.py` según secciones 3 y 4; determinar llaves de huella y contexto desde `datos/AGENTS.md` | Implementé datos falsos deterministas y selección independiente por puerto | Aceptado; corregido a mano: AttributeError en puertos y cálculo de quincena en falsos |
| 13:20 | Eduardo | memoria | Crear `memoria/pruebas.py` con tres pruebas SQLite temporales según la firma de `Almacen` | Añadí pruebas ejecutables con assert para guardar/leer, filtros de historial y lecciones inexistentes | Aceptado; sin cambios manuales |
| 13:41 | Eduardo | memoria | Implementar `Almacen` SQLite según `memoria/AGENTS.md` y hacer pasar `memoria/pruebas.py` | Añadí esquema, persistencia JSON, filtros, lectura ordenada, cierre y context manager | Aceptado; pruebas corridas a mano en WSL: 3 OK |
| 13:46 | Eduardo | memoria | Agregar pruebas temporales para `crear_v0`, `cargar_version` y `version_sin`, sin tocar las pruebas existentes | Añadí tres funciones de prueba y las incluí en `main` | Aceptado; sin cambios manuales |
| 13:49 | Eduardo | memoria | Crear `memoria/versiones.py` para soportar creación, carga y ablación de versiones | Implementé `crear_v0`, `cargar_version` y `version_sin` con escritura UTF-8/LF y copia aislada | Aceptado; pruebas corridas a mano en WSL: 6 OK |
| 13:54 | Eduardo | memoria | Agregar pruebas de contrato para `construir_sucesor` y su ablación, sin tocar las pruebas previas | Añadí tres pruebas temporales y helpers para preparar v0 y L001 | Aceptado; no ejecutadas porque `memoria/constructor.py` aún no existe |
| 13:59 | Eduardo | memoria | Implementar `construir_sucesor` y persistir modelos/versiones con los contratos indicados | Añadí el constructor, lectura/escritura de modelos en versiones y `Almacen.guardar_version` | Aceptado; pruebas corridas a mano en WSL: 9 OK |
| 14:18 | Eduardo | memoria | Agregar pruebas de validación de propuestas del curador sin alterar las pruebas existentes | Añadí preparación de ciclos falsos y tres pruebas para evidencia, capacidad activa y límite/dominio | Aceptado; corregido a mano: cuarta propuesta para probar el límite de 2 |
| 14:25 | Eduardo | memoria | Crear curador, instrucciones y listado de ids de lecciones, sin ejecutar Python | Añadí `_validar`, `_resumen`, ejecución protegida del Agent y `Almacen.ids_lecciones` | Aceptado; correcciones posteriores en validación e instrucciones |
| 14:33 | Eduardo | comun | Agregar `resolver_falso`, el puerto resolver y documentarlos | Implementé el ciclo falso sin LLM con candidatos fijos y selección real/falsa independiente | Aceptado; Python no ejecutado por instrucción |
| 14:42 | Eduardo | experimento | Crear una prueba de humo aislada para puertos, curador, almacén y constructor | Añadí `experimento/humo.py` con comprobaciones y limpieza temporal | Aceptado; no ejecuté Python por instrucción |
