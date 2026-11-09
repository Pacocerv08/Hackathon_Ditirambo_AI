from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from comun.contratos import Candidato, Problema, Resultado, Version

if TYPE_CHECKING:
    from memoria.almacen import Almacen


@dataclass
class ContextoCiclo:
    problema: Problema
    version: Version
    run_id: str
    almacen: "Almacen"
    historial: list[tuple[Candidato, Resultado]] = field(default_factory=list)
