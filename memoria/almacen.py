"""Almacén SQLite para ejecuciones, resultados y lecciones del sistema."""

from datetime import datetime, timezone
import json
import os
import sqlite3

from comun import config
from comun.contratos import (
    Candidato,
    Leccion,
    Modo,
    Problema,
    Resultado,
    Version,
)


class Almacen:
    def __init__(self, ruta: str = config.RUTA_DB):
        self.ruta = ruta
        carpeta = os.path.dirname(os.path.abspath(ruta))
        os.makedirs(carpeta, exist_ok=True)
        self._conexion = sqlite3.connect(ruta)
        self._crear_tablas()

    def _crear_tablas(self) -> None:
        self._conexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS ejecuciones (
                run_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                problema_id TEXT NOT NULL,
                inicio TEXT NOT NULL,
                fin TEXT
            );
            CREATE TABLE IF NOT EXISTS resultados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                problema_id TEXT NOT NULL,
                version TEXT NOT NULL,
                modo TEXT NOT NULL,
                candidato_id TEXT NOT NULL,
                candidato_json TEXT NOT NULL,
                resultado_json TEXT NOT NULL,
                costo_relativo REAL NOT NULL,
                resuelto INTEGER NOT NULL,
                creado TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS llamadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                agente TEXT NOT NULL,
                entrada TEXT NOT NULL,
                salida TEXT NOT NULL,
                segundos REAL NOT NULL,
                creado TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS huellas (
                problema_id TEXT PRIMARY KEY,
                huella_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lecciones (
                id TEXT PRIMARY KEY,
                version_origen TEXT NOT NULL,
                problema_origen TEXT NOT NULL,
                leccion_json TEXT NOT NULL,
                activa INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versiones (
                id TEXT PRIMARY KEY,
                padre TEXT,
                version_json TEXT NOT NULL,
                creada TEXT NOT NULL
            );
            """
        )
        self._conexion.commit()

    @staticmethod
    def _ahora() -> str:
        return datetime.now(timezone.utc).isoformat()

    def iniciar_ejecucion(self, run_id: str, version: str, problema_id: str) -> None:
        self._conexion.execute(
            "INSERT OR IGNORE INTO ejecuciones (run_id, version, problema_id, inicio) "
            "VALUES (?, ?, ?, ?)",
            (run_id, version, problema_id, self._ahora()),
        )
        self._conexion.commit()

    def guardar_resultado(
        self, run_id: str, candidato: Candidato, resultado: Resultado
    ) -> None:
        self._conexion.execute(
            "INSERT INTO resultados "
            "(run_id, problema_id, version, modo, candidato_id, candidato_json, "
            "resultado_json, costo_relativo, resuelto, creado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                resultado.problema_id,
                resultado.version,
                resultado.modo,
                resultado.candidato_id,
                candidato.model_dump_json(),
                resultado.model_dump_json(),
                resultado.costo_relativo,
                int(resultado.resuelto),
                self._ahora(),
            ),
        )
        self._conexion.commit()

    def guardar_llamada(
        self,
        run_id: str,
        agente: str,
        entrada: str,
        salida: str,
        segundos: float,
    ) -> None:
        self._conexion.execute(
            "INSERT INTO llamadas (run_id, agente, entrada, salida, segundos, creado) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, agente, entrada, salida, segundos, self._ahora()),
        )
        self._conexion.commit()

    def historial(
        self,
        problema_id: str,
        version: str | None = None,
        modo: Modo | None = None,
    ) -> list[Resultado]:
        consulta = "SELECT resultado_json FROM resultados WHERE problema_id = ?"
        parametros: list[str] = [problema_id]
        if version is not None:
            consulta += " AND version = ?"
            parametros.append(version)
        if modo is not None:
            consulta += " AND modo = ?"
            parametros.append(modo)
        consulta += " ORDER BY id ASC"
        filas = self._conexion.execute(consulta, parametros).fetchall()
        return [Resultado.model_validate_json(fila[0]) for fila in filas]

    def guardar_huella(self, problema_id: str, huella: dict[str, float]) -> None:
        self._conexion.execute(
            "INSERT OR REPLACE INTO huellas (problema_id, huella_json) VALUES (?, ?)",
            (problema_id, json.dumps(huella, ensure_ascii=False)),
        )
        self._conexion.commit()

    def guardar_leccion(self, leccion: Leccion) -> None:
        self._conexion.execute(
            "INSERT OR REPLACE INTO lecciones "
            "(id, version_origen, problema_origen, leccion_json, activa) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                leccion.id,
                leccion.version_origen,
                leccion.problema_origen,
                leccion.model_dump_json(),
                int(leccion.activa),
            ),
        )
        self._conexion.commit()

    def guardar_version(self, version: Version) -> None:
        self._conexion.execute(
            "INSERT OR REPLACE INTO versiones (id, padre, version_json, creada) "
            "VALUES (?, ?, ?, ?)",
            (
                version.id,
                version.padre,
                version.model_dump_json(),
                self._ahora(),
            ),
        )
        self._conexion.commit()

    def ids_lecciones(self) -> list[str]:
        filas = self._conexion.execute(
            "SELECT id FROM lecciones ORDER BY rowid ASC"
        ).fetchall()
        return [fila[0] for fila in filas]

    def lecciones(self, ids: list[str]) -> list[Leccion]:
        if not ids:
            return []
        marcadores = ", ".join("?" for _ in ids)
        filas = self._conexion.execute(
            f"SELECT id, leccion_json FROM lecciones WHERE id IN ({marcadores})",
            ids,
        ).fetchall()
        por_id = {
            fila[0]: Leccion.model_validate_json(fila[1])
            for fila in filas
        }
        return [por_id[id_leccion] for id_leccion in ids if id_leccion in por_id]

    def lecciones_relevantes(
        self, version: Version, problema: Problema, k: int = 5
    ) -> list[Leccion]:
        raise NotImplementedError("pendiente: requiere la huella real de datos/")

    def close(self) -> None:
        self._conexion.close()

    def __enter__(self) -> "Almacen":
        return self

    def __exit__(self, tipo, valor, traza) -> None:
        self.close()
