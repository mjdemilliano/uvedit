from pathlib import Path


def ensure_gitignore_entry(project_dir: Path, entry: str) -> None:
    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        return
    lines = gitignore.read_text().splitlines()
    if entry not in lines:
        with open(gitignore, "a") as f:
            f.write(f"\n{entry}\n")
