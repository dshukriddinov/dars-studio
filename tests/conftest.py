from pathlib import Path
from typing import Any

import pytest

_DIR_MARKS = {"unit", "media", "gpu", "windows", "pilot"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # tests/<belgi>/... papkasidagi testlar avtomatik o'sha belgini oladi
    for item in items:
        mark = Path(item.path).parent.name
        if mark in _DIR_MARKS:
            item.add_marker(mark)


@pytest.fixture(scope="session")
def test_media() -> dict[str, Any]:
    """Sintetik media to'plami (TZ 13.3): {fayl nomi: {path, ...kutilgan qiymatlar}}."""
    from tools.make_test_media import generate

    files: dict[str, Any] = generate()["files"]
    return files
