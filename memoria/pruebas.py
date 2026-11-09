"""Pruebas de contrato del almacén SQLite, ejecutables sin pytest."""

from tempfile import TemporaryDirectory
from pathlib import Path
import json

from comun import config
from comun.contratos import (
    Candidato,
    Capacidades,
    Leccion,
    Modo,
    Resultado,
    Version,
)
from comun.falsos import evaluar_falso, problema_falso
from memoria.almacen import Almacen
from memoria.versiones import crear_v0, cargar_version, version_sin


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


def prueba_crear_y_cargar_v0() -> None:
    with TemporaryDirectory() as directorio:
        raiz = Path(directorio)
        creada = crear_v0(raiz=raiz)
        cargada = cargar_version("v0", raiz=raiz)

        esperada = Version(
            id="v0",
            padre=None,
            capacidades=Capacidades(),
            lecciones_activas=[],
            creada_por="equipo",
            cambios=[],
        )
        assert creada == cargada == esperada
        config_path = raiz / "v0" / "config.json"
        assert config_path.is_file()
        assert "modelos" in json.loads(config_path.read_text(encoding="utf-8"))
        assert not (raiz / "v0" / "instrucciones").exists()


def prueba_version_sin() -> None:
    with TemporaryDirectory() as directorio:
        raiz = Path(directorio)
        version_dir = raiz / "v1"
        instrucciones = version_dir / "instrucciones"
        carpeta_leccion = version_dir / "lecciones" / "L001-umbral-por-costos"
        instrucciones.mkdir(parents=True)
        carpeta_leccion.mkdir(parents=True)

        version = Version(
            id="v1",
            padre="v0",
            capacidades=Capacidades(umbral_por_costos=True),
            lecciones_activas=["L001"],
            creada_por="sistema",
            cambios=["Activa el umbral por costos."],
        )
        config_data = version.model_dump(mode="json")
        config_data["modelos"] = config.MODELOS
        (version_dir / "config.json").write_text(
            json.dumps(config_data, ensure_ascii=False), encoding="utf-8"
        )

        texto_instruccion = (
            "Instrucción base.\n"
            "<!-- leccion:L001 -->\n"
            "- (L001) Considera los costos desiguales.\n"
            "<!-- /leccion:L001 -->\n"
            "Otra línea.\n"
        )
        archivo_instruccion = instrucciones / "proponente.md"
        archivo_instruccion.write_text(texto_instruccion, encoding="utf-8")
        leccion = Leccion(
            id="L001",
            version_origen="v0",
            problema_origen="credito_a",
            senal="El error caro domina el costo.",
            evidencia=["candidato-1"],
            texto="Considera los costos desiguales al decidir.",
            tipo_cambio="regla",
            capacidad="umbral_por_costos",
            regla_para=["proponente"],
        )
        (carpeta_leccion / "leccion.json").write_text(
            leccion.model_dump_json(), encoding="utf-8"
        )
        (carpeta_leccion / "SKILL.md").write_text("Skill de prueba.\n", encoding="utf-8")

        sin_leccion = version_sin("v1", "L001", raiz=raiz)

        assert sin_leccion.id == "v1-sin-L001"
        assert sin_leccion.padre == "v1"
        assert sin_leccion.capacidades.umbral_por_costos is False
        assert "L001" not in sin_leccion.lecciones_activas
        copia_instruccion = (raiz / "v1-sin-L001" / "instrucciones" / "proponente.md").read_text(
            encoding="utf-8"
        )
        assert "L001" not in copia_instruccion
        assert "Instrucción base." in copia_instruccion
        assert "Otra línea." in copia_instruccion
        assert not (raiz / "v1-sin-L001" / "lecciones" / "L001-umbral-por-costos").exists()

        assert "L001" in archivo_instruccion.read_text(encoding="utf-8")
        assert carpeta_leccion.is_dir()


def prueba_version_inexistente() -> None:
    with TemporaryDirectory() as directorio:
        try:
            cargar_version("v9", raiz=Path(directorio))
        except FileNotFoundError:
            return
        raise AssertionError("cargar_version('v9') debió lanzar FileNotFoundError")


def main() -> None:
    pruebas = (
        prueba_guardar_y_leer,
        prueba_filtros_historial,
        prueba_leccion_inexistente,
        prueba_crear_y_cargar_v0,
        prueba_version_sin,
        prueba_version_inexistente,
    )
    for prueba in pruebas:
        prueba()
        print(f"OK {prueba.__name__}")


if __name__ == "__main__":
    main()
