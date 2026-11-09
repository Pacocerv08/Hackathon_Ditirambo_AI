from pydantic import BaseModel, Field, field_validator

from comun.contratos import Candidato


class Descripcion(BaseModel):
    resumen: str = Field(
        description="Qué se decide, con qué datos y qué error es caro, en 3-5 frases"
    )
    riesgos: list[str] = Field(
        description="Cosas raras de los datos que podrían engañar al modelo"
    )


class Propuesta(BaseModel):
    candidatos: list[Candidato] = Field(
        description="Exactamente 3, distintos entre sí y a lo ya probado"
    )

    @field_validator("candidatos")
    @classmethod
    def validar_tres_candidatos(cls, candidatos: list[Candidato]) -> list[Candidato]:
        if len(candidatos) != 3:
            raise ValueError("Se requieren exactamente 3 candidatos")
        return candidatos


class Diagnostico(BaseModel):
    que_fallo: str
    por_que: str
    evidencia: list[str] = Field(
        description="Fechas, filas, alertas o métricas que lo respaldan"
    )
    que_probar: str
    seguir: bool = Field(description="False si no vale la pena otra iteración")
