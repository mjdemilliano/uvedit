import subprocess
from pathlib import Path

import pytest
import tomlkit


@pytest.fixture
def dummy_git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository."""
    repo = tmp_path / "dummy_repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create a minimal Python package
    (repo / "pyproject.toml").write_text('[project]\nname = "dummy-pkg"\nversion = "0.1.0"\n')
    (repo / "README.md").write_text("# Dummy Package\n")

    # Commit
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


@pytest.fixture
def project_with_git_source(tmp_path: Path, dummy_git_repo: Path) -> Path:
    """Create a Python project with a git source in pyproject.toml."""
    project = tmp_path / "my_project"
    project.mkdir()

    # Create pyproject.toml with git source
    doc = tomlkit.document()
    doc.add("project", tomlkit.table())
    doc["project"].add("name", "my-project")
    doc["project"].add("version", "0.1.0")
    doc["project"].add("dependencies", ["dummy-pkg"])

    tool = tomlkit.table()
    uv = tomlkit.table()
    sources = tomlkit.table()

    source_entry = tomlkit.inline_table()
    source_entry["git"] = dummy_git_repo.as_uri()
    sources["dummy-pkg"] = source_entry

    uv["sources"] = sources
    tool["uv"] = uv
    doc["tool"] = tool

    pyproject_path = project / "pyproject.toml"
    pyproject_path.write_text(tomlkit.dumps(doc))

    # Create .gitignore
    (project / ".gitignore").write_text("*.pyc\n__pycache__/\n.venv/\n")

    return project


@pytest.fixture
def project_with_git_source_and_subdir(tmp_path: Path) -> tuple[Path, Path]:
    """Create a git repo with a subdirectory and a project that sources it."""
    # Create git repo with subdirectory
    repo = tmp_path / "repo_with_subdir"
    repo.mkdir()

    subprocess.run(
        ["git", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create subdirectory with package
    subdir = repo / "subpkg"
    subdir.mkdir()
    (subdir / "pyproject.toml").write_text('[project]\nname = "sub-pkg"\nversion = "0.1.0"\n')
    (repo / "README.md").write_text("# Repo with Subdir\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create project that sources the subdirectory
    project = tmp_path / "my_project"
    project.mkdir()

    doc = tomlkit.document()
    doc.add("project", tomlkit.table())
    doc["project"].add("name", "my-project")
    doc["project"].add("version", "0.1.0")
    doc["project"].add("dependencies", ["sub-pkg"])

    tool = tomlkit.table()
    uv = tomlkit.table()
    sources = tomlkit.table()

    source_entry = tomlkit.inline_table()
    source_entry["git"] = repo.as_uri()
    source_entry["subdirectory"] = "subpkg"
    sources["sub-pkg"] = source_entry

    uv["sources"] = sources
    tool["uv"] = uv
    doc["tool"] = tool

    pyproject_path = project / "pyproject.toml"
    pyproject_path.write_text(tomlkit.dumps(doc))

    (project / ".gitignore").write_text("*.pyc\n__pycache__/\n.venv/\n")

    return project, repo
