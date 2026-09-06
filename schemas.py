import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DefectExtraction(BaseModel):
    """Valida la intención y los datos extraídos de un reporte de defectos."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    intent: Literal[
        "report_defect",
        "search_defect",
        "update_defect",
        "request_guidance",
        "unknown",
    ] = Field(description="Intención identificada en el texto recibido.")
    summary: str | None = Field(default=None, description="Resumen del mensaje.")
    platform: Literal["web", "android", "ios", "desktop", "other"] | None = Field(
        default=None, description="Plataforma afectada indicada en el reporte."
    )
    app_version: str | None = Field(default=None, description="Versión informada.")
    module: str | None = Field(default=None, description="Módulo afectado.")
    error_code: str | None = Field(default=None, description="Código de error informado.")
    steps_to_reproduce: list[str] = Field(
        default_factory=list, description="Pasos de reproducción presentes en el texto."
    )
    expected_result: str | None = Field(
        default=None, description="Resultado esperado indicado por el usuario."
    )
    actual_result: str | None = Field(
        default=None, description="Resultado observado indicado por el usuario."
    )
    defect_id: str | None = Field(
        default=None, description="Identificador informado, con formato DEF-número."
    )
    keywords: list[str] = Field(
        default_factory=list, description="Palabras clave respaldadas por el mensaje."
    )
    requested_changes: str | None = Field(
        default=None, description="Cambios solicitados por el usuario, sin ejecutarlos."
    )
    missing_fields: list[str] = Field(
        default_factory=list, description="Campos identificados como faltantes."
    )

    @field_validator("defect_id", mode="before")
    @classmethod
    def normalize_defect_id(cls, value: object) -> str | None:
        """Normaliza el identificador y exige el formato DEF seguido de dígitos."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("defect_id debe ser un string o None.")
        normalized = value.strip().upper()
        if re.fullmatch(r"^DEF-\d+$", normalized) is None:
            raise ValueError("defect_id debe tener el formato DEF- seguido de dígitos.")
        return normalized

    @field_validator("steps_to_reproduce", "keywords", "missing_fields")
    @classmethod
    def clean_list_values(cls, values: list[str]) -> list[str]:
        """Quita vacíos y duplicados sin distinguir mayúsculas, conservando el orden."""
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            key = stripped.casefold()
            if stripped and key not in seen:
                cleaned.append(stripped)
                seen.add(key)
        return cleaned
