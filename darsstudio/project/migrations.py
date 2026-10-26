"""project.json sxema migratsiyalari. Yangi versiyada: MIGRATIONS[eski] = funksiya(dict) -> dict (versiya + 1)."""

from collections.abc import Callable
from typing import Any

from darsstudio.project.model import SCHEMA_VERSION

MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    v = int(data.get("schema_version", 1))
    if v > SCHEMA_VERSION:
        raise ValueError(f"Loyiha Dars Studio'ning yangiroq versiyasida yaratilgan (sxema {v}). Dasturni yangilang.")
    while v < SCHEMA_VERSION:
        data = MIGRATIONS[v](data)
        v = data["schema_version"] = v + 1
    return data
