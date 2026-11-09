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
    ResultadoCiclo,
    Resultado,
    Version,
)
from comun.falsos import evaluar_falso, problema_falso
from memoria.almacen import Almacen
from memoria.constructor import construir_sucesor
from memoria.curador import LeccionPropuesta, _validar
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


def _leccion_umbral() -> Leccion:
    return Leccion(
        id="L001",
        version_origen="v0",
        problema_origen="credito_a",
        senal="El error caro domina el costo.",
        evidencia=["cand-1"],
        texto="Cuando un error cuesta más que otro, ajusta el umbral de decisión a los costos.",
        tipo_cambio="regla",
        capacidad="umbral_por_costos",
        regla_para=["proponente"],
    )


def _preparar_v0(raiz: Path) -> Version:
    version = crear_v0(raiz=raiz)
    instrucciones = raiz / "v0" / "instrucciones"
    instrucciones.mkdir()
    (instrucciones / "proponente.md").write_text("Instrucción base.\n", encoding="utf-8")
    return version


def prueba_construir_sucesor() -> None:
    with TemporaryDirectory() as directorio:
        raiz = Path(directorio)
        v0 = _preparar_v0(raiz)
        leccion = _leccion_umbral()

        v1 = construir_sucesor(v0, [leccion], raiz=raiz)

        assert v1.id == "v1"
        assert v1.padre == "v0"
        assert v1.capacidades.umbral_por_costos is True
        assert v1.lecciones_activas == ["L001"]
        assert v1.creada_por == "sistema"
        assert cargar_version("v1", raiz=raiz) == v1

        instruccion_v1 = (raiz / "v1" / "instrucciones" / "proponente.md").read_text(
            encoding="utf-8"
        )
        assert "Instrucción base." in instruccion_v1
        assert "<!-- leccion:L001 -->" in instruccion_v1
        assert "<!-- /leccion:L001 -->" in instruccion_v1
        assert leccion.texto in instruccion_v1

        carpetas_leccion = list((raiz / "v1" / "lecciones").glob("L001-*"))
        assert len(carpetas_leccion) == 1
        carpeta_leccion = carpetas_leccion[0]
        skill = (carpeta_leccion / "SKILL.md").read_text(encoding="utf-8")
        assert skill.startswith("---")
        assert any(line.startswith("name:") for line in skill.splitlines())
        assert any(line.startswith("description:") for line in skill.splitlines())
        leccion_guardada = Leccion.model_validate_json(
            (carpeta_leccion / "leccion.json").read_text(encoding="utf-8")
        )
        assert leccion_guardada == leccion
        assert (raiz / "v1" / "cambios.md").is_file()

        config_v0 = json.loads((raiz / "v0" / "config.json").read_text(encoding="utf-8"))
        config_v1 = json.loads((raiz / "v1" / "config.json").read_text(encoding="utf-8"))
        assert config_v1["modelos"] == config_v0["modelos"]
        assert (raiz / "v0" / "instrucciones" / "proponente.md").read_text(
            encoding="utf-8"
        ) == "Instrucción base.\n"
        assert not (raiz / "v0" / "lecciones").exists()


def prueba_construir_y_ablacionar() -> None:
    with TemporaryDirectory() as directorio:
        raiz = Path(directorio)
        v0 = _preparar_v0(raiz)
        v1 = construir_sucesor(v0, [_leccion_umbral()], raiz=raiz)

        v1_sin = version_sin("v1", "L001", raiz=raiz)

        assert v1_sin.capacidades == v0.capacidades
        assert v1_sin.lecciones_activas == []
        instruccion_sin = (raiz / v1_sin.id / "instrucciones" / "proponente.md").read_text(
            encoding="utf-8"
        )
        instruccion_v0 = (raiz / "v0" / "instrucciones" / "proponente.md").read_text(
            encoding="utf-8"
        )
        assert instruccion_sin == instruccion_v0


def prueba_sucesor_existente() -> None:
    with TemporaryDirectory() as directorio:
        raiz = Path(directorio)
        v0 = _preparar_v0(raiz)
        destino = raiz / "v1"
        destino.mkdir()
        protegido = destino / "no_tocar.txt"
        protegido.write_text("conservar\n", encoding="utf-8")

        try:
            construir_sucesor(v0, [_leccion_umbral()], raiz=raiz)
        except FileExistsError:
            pass
        else:
            raise AssertionError("construir_sucesor debió lanzar FileExistsError")
        assert protegido.read_text(encoding="utf-8") == "conservar\n"


def _contexto_curador(umbral_activo: bool = False):
    problema = problema_falso("clasificacion")
    problema.id = "curador_prueba"
    candidatos = [_candidato("referencia"), _candidato("logistica")]
    historial = [
        evaluar_falso(problema, candidato, Capacidades(), version="v0")
        for candidato in candidatos
    ]
    ciclo = ResultadoCiclo(
        problema_id=problema.id,
        version="v0",
        run_id="run_curador_pruebas",
        mejor_candidato=None,
        mejor_resultado=None,
        historial=historial,
        diagnosticos=[],
    )
    version = Version(
        id="v0",
        padre=None,
        capacidades=Capacidades(umbral_por_costos=umbral_activo),
        lecciones_activas=[],
        creada_por="equipo",
        cambios=[],
    )
    return problema, ciclo, version


def _propuesta_curador(
    evidencia: list[str],
    texto: str = "Ajusta la decisión según los costos de error.",
    capacidad: str | None = None,
) -> LeccionPropuesta:
    return LeccionPropuesta(
        senal="El costo se concentra en errores de un tipo.",
        evidencia=evidencia,
        texto=texto,
        tipo_cambio="regla",
        capacidad=capacidad,
        regla_para=["proponente"],
    )


def prueba_curador_evidencia() -> None:
    problema, ciclo, version = _contexto_curador()
    candidato_id = ciclo.historial[0].candidato_id
    propuestas = [
        _propuesta_curador([candidato_id]),
        _propuesta_curador(["inventado"], texto="Esta evidencia no existe."),
    ]

    lecciones = _validar(propuestas, problema, ciclo, version, ids_existentes=[])

    assert len(lecciones) == 1
    assert lecciones[0].id == "L001"
    assert lecciones[0].evidencia == [candidato_id]
    assert lecciones[0].version_origen == "v0"
    assert lecciones[0].problema_origen == problema.id


def prueba_curador_capacidad_activa() -> None:
    problema, ciclo, version = _contexto_curador(umbral_activo=True)
    propuesta = _propuesta_curador(
        [ciclo.historial[0].candidato_id],
        capacidad="umbral_por_costos",
    )

    lecciones = _validar([propuesta], problema, ciclo, version, ids_existentes=[])

    assert lecciones == []


def prueba_curador_limite_y_dominio() -> None:
    problema, ciclo, version = _contexto_curador()
    evidencia = [resultado.candidato_id for resultado in ciclo.historial]
    propuestas = [
        _propuesta_curador([evidencia[0]], texto=f"Evita repetir {problema.id.upper()} en reglas."),
        _propuesta_curador([evidencia[0]], texto="Ajusta decisiones con costos asimétricos."),
        _propuesta_curador([evidencia[1]], texto="Comprueba el resultado en casos reservados."),
        _propuesta_curador([evidencia[1]], texto="Revisa columnas que predicen demasiado bien."),
    ]

    lecciones = _validar(
        propuestas,
        problema,
        ciclo,
        version,
        ids_existentes=["L001", "L003"],
    )

    assert len(lecciones) == 2
    assert all(problema.id.lower() not in leccion.texto.lower() for leccion in lecciones)
    assert [leccion.id for leccion in lecciones] == ["L004", "L005"]


def main() -> None:
    pruebas = (
        prueba_guardar_y_leer,
        prueba_filtros_historial,
        prueba_leccion_inexistente,
        prueba_crear_y_cargar_v0,
        prueba_version_sin,
        prueba_version_inexistente,
        prueba_construir_sucesor,
        prueba_construir_y_ablacionar,
        prueba_sucesor_existente,
        prueba_curador_evidencia,
        prueba_curador_capacidad_activa,
        prueba_curador_limite_y_dominio,
    )
    for prueba in pruebas:
        prueba()
        print(f"OK {prueba.__name__}")


if __name__ == "__main__":
    main()
