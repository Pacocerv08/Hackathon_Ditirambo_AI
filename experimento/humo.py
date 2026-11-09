"""Prueba de humo aislada para el ciclo, la memoria y el constructor."""

from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

from comun import puertos
from comun.contratos import Leccion
from comun.falsos import problema_falso
from memoria.almacen import Almacen
from memoria.constructor import construir_sucesor
from memoria.curador import curar
from memoria.versiones import crear_v0


def main() -> None:
    inicio = perf_counter()
    paso = "inicio"
    almacen = None
    try:
        print(f"PUERTOS_FALSOS={puertos.PUERTOS_FALSOS}")

        paso = "crear v0"
        v0 = crear_v0()

        with TemporaryDirectory() as temporal:
            tmp = Path(temporal)
            paso = "abrir almacén temporal"
            almacen = Almacen(str(tmp / "humo.db"))
            ultimo_ciclo = None
            tipos_elegidos = 0

            try:
                for tipo in ("clasificacion", "serie"):
                    paso = f"elegir problema {tipo}"
                    if puertos.PUERTOS_FALSOS["evaluar"]:
                        problema = problema_falso(tipo)
                    else:
                        problema_id = "credito_a" if tipo == "clasificacion" else "demanda_a"
                        try:
                            from datos.problemas import cargar_problema

                            problema = cargar_problema(problema_id)
                        except (ImportError, FileNotFoundError, KeyError, ValueError) as error:
                            print(f"SALTO {tipo}: {error}")
                            continue
                    print(f"problema: {problema.id}")
                    tipos_elegidos += 1

                    paso = f"resolver {tipo}"
                    ciclo = puertos.resolver(problema, v0)
                    assert ciclo.mejor_candidato is not None, "falta mejor_candidato"
                    assert ciclo.mejor_resultado is not None, "falta mejor_resultado"
                    assert ciclo.resultado_produccion is not None, "falta resultado_produccion"
                    assert ciclo.historial, "historial vacío"
                    ultimo_ciclo = ciclo

                    paso = f"curar {tipo}"
                    lecciones = curar(problema, ciclo, v0, almacen)
                    assert isinstance(lecciones, list), "curar no devolvió una lista"

                    print(
                        f"OK {tipo}: {ciclo.mejor_candidato.modelo} "
                        f"validación={ciclo.mejor_resultado.costo_relativo:.3f} "
                        f"producción={ciclo.resultado_produccion.costo_relativo:.3f} "
                        f"lecciones={len(lecciones)}"
                    )

                if tipos_elegidos == 0:
                    print("FALLO en elegir problema: no hay ningún problema disponible")
                    sys.exit(1)

                paso = "preparar versiones temporales"
                raiz_versiones = tmp / "versiones"
                raiz_versiones.mkdir()
                shutil.copytree(Path("versiones") / "v0", raiz_versiones / "v0")

                paso = "construir sucesor temporal"
                assert ultimo_ciclo is not None
                leccion_prueba = Leccion(
                    id="L900",
                    version_origen=v0.id,
                    problema_origen=ultimo_ciclo.problema_id,
                    senal="Prueba controlada del constructor.",
                    evidencia=[ultimo_ciclo.historial[0].candidato_id],
                    texto="Cuando un error cuesta más, ajusta la decisión a los costos.",
                    tipo_cambio="regla",
                    capacidad="umbral_por_costos",
                    regla_para=["proponente"],
                )
                sucesor = construir_sucesor(
                    v0,
                    [leccion_prueba],
                    raiz=raiz_versiones,
                )
                assert sucesor.id == "v1", f"id inesperado: {sucesor.id}"
                assert sucesor.capacidades.umbral_por_costos is True
                print("OK constructor")
            finally:
                if almacen is not None:
                    almacen.close()
                    almacen = None

        print(f"Segundos totales: {perf_counter() - inicio:.3f}")
    except Exception as error:
        print(f"FALLO en {paso}: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
