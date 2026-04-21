import sys
from pathlib import Path

import tomlkit


def find_pyproject() -> Path:
    path = Path.cwd()
    while path != path.parent:
        candidate = path / "pyproject.toml"
        if candidate.exists():
            return candidate
        path = path.parent
    print("Error: No pyproject.toml found in current or parent directories.")
    sys.exit(1)


def get_sources(doc: tomlkit.TOMLDocument) -> tomlkit.container.Container:
    """Return [tool.uv.sources], creating intermediate tables if needed."""
    if "tool" not in doc:
        doc.add("tool", tomlkit.table())
    if "uv" not in doc["tool"]:
        doc["tool"].add("uv", tomlkit.table())
    if "sources" not in doc["tool"]["uv"]:
        doc["tool"]["uv"].add("sources", tomlkit.table())
    return doc["tool"]["uv"]["sources"]
