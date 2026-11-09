"""Pruebas de contrato del almacén SQLite, ejecutables sin pytest."""

from tempfile import TemporaryDirectory
from pathlib import Path

from comun.contratos import Candidato, Capacidades, Modo, Resultado
from comun.falsos import evaluar_falso, problema_falso
from memoria.almacen import Almacen


def _almacen_temporal(directorio: str) -> Almacen:
    return Almacen(str(Path(directorio) / "memoria_pruebas.db"))


def _candidato(modelo: str) -> Candidato:
    return Candidato(
        modelo=modelo,
        justificacion=f"Candidato de prueba basado en {modelo}.",
    )


def _guardar(
    almacen: Almacen,
    problema_id: str,
    candidato: Candidato,
    version: str,
    modo: Modo,
    run_id: str,
) -> Resultado:
    problema = problema_falso("clasificacion")
    problema.id = problema_id
    resultado = evaluar_falso(
        problema,
        candidato,
        Capacidades(),
        modo=modo,
        version=version,
    )
    almacen.iniciar_ejecucion(run_id, version, problema_id)
    almacen.guardar_resultado(run_id, candidato, resultado)
    return resultado


def prueba_guardar_y_leer() -> None:
    with TemporaryDirectory() as directorio:
        almacen = _almacen_temporal(directorio)
        problema_id = "prueba_historial"
        guardados = [
            _guardar(almacen, problema_id, _candidato(modelo), "v0", "validacion", f"run_{i}")
            for i, modelo in enumerate(("referencia", "logistica", "arbol"))
        ]

        leidos = almacen.historial(problema_id)
        assert len(leidos) == 3
        assert leidos == guardados


def prueba_filtros_historial() -> None:
    with TemporaryDirectory() as directorio:
        almacen = _almacen_temporal(directorio)
        problema_id = "prueba_filtros"
        combinaciones = (
            ("referencia", "v0", "validacion"),
            ("logistica", "v1", "validacion"),
            ("arbol", "v0", "produccion"),
            ("lightgbm", "v1", "produccion"),
        )
        guardados = [
            _guardar(
                almacen,
                problema_id,
                _candidato(modelo),
                version,
                modo,
                f"run_{i}",
            )
            for i, (modelo, version, modo) in enumerate(combinaciones)
        ]

        filtrados = almacen.historial(problema_id, version="v1", modo="produccion")
        assert filtrados == [guardados[3]]


def prueba_leccion_inexistente() -> None:
    with TemporaryDirectory() as directorio:
        almacen = _almacen_temporal(directorio)
        assert almacen.lecciones(["L999"]) == []


def main() -> None:
    pruebas = (
        prueba_guardar_y_leer,
        prueba_filtros_historial,
        prueba_leccion_inexistente,
    )
    for prueba in pruebas:
        prueba()
        print(f"OK {prueba.__name__}")


if __name__ == "__main__":
    main()
