"""Columnas que no existen todavía en el momento de decidir (intervención del equipo, declarada).

En la vida real, 'dias_desde_baja' solo se conoce después de que el cliente se fue. En los datos
históricos sí está, por eso en validación el modelo se ve excelente. Para simular la realidad, el
evaluador reemplaza estas columnas por ruido en los pedazos de producción y prueba.

La llave es problema.archivo (campo del contrato), porque Problema no tiene un campo para esto y no
se toca comun/. Los agentes no tienen herramienta para leer esta tabla.
"""

COLUMNAS_FUTURAS: dict[str, list[str]] = {
    "datos/procesados/churn.parquet": ["dias_desde_baja"],
}


def columnas_futuras(archivo: str) -> list[str]:
    return list(COLUMNAS_FUTURAS.get(archivo.replace("\\", "/"), []))
