import tomllib
from pathlib import Path
from typing import Any

import tomlkit

SAVEDSTATE_FILE = ".uvedit.toml"


def load_savedstate(project_dir: Path) -> dict[str, Any]:
    path = project_dir / SAVEDSTATE_FILE
    if path.exists():
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def save_savedstate(project_dir: Path, data: dict[str, Any]) -> None:
    path = project_dir / SAVEDSTATE_FILE
    if not data:
        path.unlink(missing_ok=True)
        return
    doc = tomlkit.document()
    for pkg, source in data.items():
        tbl = tomlkit.inline_table()
        for k, v in source.items():
            tbl.append(k, v)
        doc.add(pkg, tbl)
    path.write_text(tomlkit.dumps(doc))
