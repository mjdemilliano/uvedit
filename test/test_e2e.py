"""End-to-end tests for uvedit local <-> restore functionality."""

import subprocess
import sys
import tomllib
from pathlib import Path

import tomlkit


def run_uvedit_cmd(project_dir: Path, *args) -> tuple[int, str, str]:
    """Run uvedit command as subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "uvedit"] + list(args),
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def read_pyproject(project_dir: Path) -> dict:
    """Read pyproject.toml as dict."""
    doc = tomlkit.parse((project_dir / "pyproject.toml").read_text())
    return dict(doc)


def get_sources(project_dir: Path) -> dict:
    """Get [tool.uv.sources] from pyproject.toml."""
    doc = tomlkit.parse((project_dir / "pyproject.toml").read_text())
    if "tool" in doc and "uv" in doc["tool"] and "sources" in doc["tool"]["uv"]:
        return dict(doc["tool"]["uv"]["sources"])
    return {}


def read_saved_state(project_dir: Path) -> dict:
    """Read .uvedit.toml if it exists."""
    path = project_dir / ".uvedit.toml"
    if path.exists():
        with open(path, "rb") as f:
            return tomllib.load(f)
    return {}


def saved_state_exists(project_dir: Path) -> bool:
    """Check if .uvedit.toml exists."""
    return (project_dir / ".uvedit.toml").exists()


class TestBasicLocalRestore:
    """Test basic local <-> restore workflow."""

    def test_local_then_restore_default_path(self, project_with_git_source: Path) -> None:
        """Switch to local, verify state, then restore to git source."""
        project = project_with_git_source

        # Initial state: should have git source
        sources = get_sources(project)
        assert "dummy-pkg" in sources
        assert "git" in sources["dummy-pkg"]
        git_url = sources["dummy-pkg"]["git"]
        assert not saved_state_exists(project)

        # Run: uvedit local dummy-pkg
        returncode, stdout, stderr = run_uvedit_cmd(project, "local", "dummy-pkg")
        assert returncode == 0, f"Failed to run local: {stderr}"
        assert "Cloning" in stdout or "Using existing" in stdout

        # After local: should have path source
        sources = get_sources(project)
        assert "dummy-pkg" in sources
        assert "path" in sources["dummy-pkg"]
        assert sources["dummy-pkg"]["editable"] is True
        assert "git" not in sources["dummy-pkg"]

        # Saved state should exist and contain original git source
        assert saved_state_exists(project)
        saved = read_saved_state(project)
        assert "dummy-pkg" in saved
        assert saved["dummy-pkg"]["git"] == git_url

        # Checkout should exist in default location (../dummy-pkg)
        checkout = project.parent / "dummy-pkg"
        assert checkout.exists()
        assert (checkout / ".git").exists()

        # Run: uvedit restore dummy-pkg
        returncode, stdout, stderr = run_uvedit_cmd(project, "restore", "dummy-pkg")
        assert returncode == 0, f"Failed to run restore: {stderr}"
        assert "Restored" in stdout

        # After restore: should be back to git source
        sources = get_sources(project)
        assert "dummy-pkg" in sources
        assert "git" in sources["dummy-pkg"]
        assert sources["dummy-pkg"]["git"] == git_url
        assert "path" not in sources["dummy-pkg"]

        # Saved state should be cleaned up (package entry removed)
        saved = read_saved_state(project)
        assert "dummy-pkg" not in saved

        # Checkout should still exist (not deleted by restore)
        assert checkout.exists()

    def test_local_with_custom_dir(self, project_with_git_source: Path) -> None:
        """Test local with custom --dir path."""
        project = project_with_git_source
        sources = get_sources(project)
        git_url = sources["dummy-pkg"]["git"]

        # Use custom directory
        custom_dir = project.parent / "my_custom_checkout"

        # Run: uvedit local dummy-pkg --dir <custom_dir>
        returncode, stdout, stderr = run_uvedit_cmd(project, "local", "dummy-pkg", "--dir", str(custom_dir))
        assert returncode == 0, f"Failed: {stderr}"
        assert "Cloning" in stdout or "Using existing" in stdout

        # Verify checkout is at custom location
        assert custom_dir.exists()
        assert (custom_dir / ".git").exists()

        # Verify source points to custom dir
        sources = get_sources(project)
        assert "path" in sources["dummy-pkg"]
        # The path should resolve to custom_dir
        path_in_config = sources["dummy-pkg"]["path"]
        resolved_path = (project / path_in_config).resolve()
        assert resolved_path == custom_dir.resolve()

        # Saved state has original git source
        saved = read_saved_state(project)
        assert saved["dummy-pkg"]["git"] == git_url

        # Restore back
        returncode, stdout, stderr = run_uvedit_cmd(project, "restore", "dummy-pkg")
        assert returncode == 0, f"Failed to restore: {stderr}"

        sources = get_sources(project)
        assert sources["dummy-pkg"]["git"] == git_url
        assert "path" not in sources["dummy-pkg"]


class TestWithSubdirectory:
    """Test local <-> restore with subdirectory in git source."""

    def test_local_restore_with_subdirectory(self, project_with_git_source_and_subdir: tuple[Path, Path]) -> None:
        """Test when git source has subdirectory field."""
        project, repo = project_with_git_source_and_subdir

        # Initial state
        sources = get_sources(project)
        assert "sub-pkg" in sources
        assert "git" in sources["sub-pkg"]
        assert sources["sub-pkg"]["subdirectory"] == "subpkg"
        git_url = sources["sub-pkg"]["git"]

        # Run local
        returncode, stdout, stderr = run_uvedit_cmd(project, "local", "sub-pkg")
        assert returncode == 0, f"Failed: {stderr}"

        # After local: path should include subdirectory
        sources = get_sources(project)
        assert "path" in sources["sub-pkg"]
        assert sources["sub-pkg"]["editable"] is True
        path_in_config = sources["sub-pkg"]["path"]
        resolved_path = (project / path_in_config).resolve()
        # Should resolve to ../repo_with_subdir/subpkg
        assert resolved_path == (project.parent / "sub-pkg" / "subpkg").resolve()

        # Saved state should preserve subdirectory
        saved = read_saved_state(project)
        assert saved["sub-pkg"]["git"] == git_url
        assert saved["sub-pkg"]["subdirectory"] == "subpkg"

        # Restore
        returncode, stdout, stderr = run_uvedit_cmd(project, "restore", "sub-pkg")
        assert returncode == 0, f"Failed: {stderr}"

        # After restore: back to git with subdirectory
        sources = get_sources(project)
        assert sources["sub-pkg"]["git"] == git_url
        assert sources["sub-pkg"]["subdirectory"] == "subpkg"
        assert "path" not in sources["sub-pkg"]

    def test_local_with_custom_dir_and_subdirectory(
        self, project_with_git_source_and_subdir: tuple[Path, Path]
    ) -> None:
        """Test custom --dir with subdirectory in git source."""
        project, repo = project_with_git_source_and_subdir
        sources = get_sources(project)
        git_url = sources["sub-pkg"]["git"]

        custom_dir = project.parent / "special_checkout"

        # Run local with custom dir
        returncode, stdout, stderr = run_uvedit_cmd(project, "local", "sub-pkg", "--dir", str(custom_dir))
        assert returncode == 0, f"Failed: {stderr}"

        # Checkout should be at custom location
        assert custom_dir.exists()

        # Path should be custom_dir/subpkg
        sources = get_sources(project)
        path_in_config = sources["sub-pkg"]["path"]
        resolved_path = (project / path_in_config).resolve()
        assert resolved_path == (custom_dir / "subpkg").resolve()

        # Restore
        returncode, stdout, stderr = run_uvedit_cmd(project, "restore", "sub-pkg")
        assert returncode == 0, f"Failed: {stderr}"

        sources = get_sources(project)
        assert sources["sub-pkg"]["git"] == git_url
        assert sources["sub-pkg"]["subdirectory"] == "subpkg"


class TestMultiplePackages:
    """Test handling multiple packages."""

    def test_local_multiple_packages(self, tmp_path: Path) -> None:
        """Test switching multiple packages to local simultaneously."""
        # Create two git repos
        repo1 = tmp_path / "repo1"
        repo1.mkdir()
        subprocess.run(["git", "init"], cwd=repo1, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo1,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo1,
            check=True,
            capture_output=True,
        )
        (repo1 / "pyproject.toml").write_text('[project]\nname="pkg1"\n')
        (repo1 / "README.md").write_text("# Repo 1\n")
        subprocess.run(["git", "add", "."], cwd=repo1, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo1,
            check=True,
            capture_output=True,
        )

        repo2 = tmp_path / "repo2"
        repo2.mkdir()
        subprocess.run(["git", "init"], cwd=repo2, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo2,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo2,
            check=True,
            capture_output=True,
        )
        (repo2 / "pyproject.toml").write_text('[project]\nname="pkg2"\n')
        (repo2 / "README.md").write_text("# Repo 2\n")
        subprocess.run(["git", "add", "."], cwd=repo2, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo2,
            check=True,
            capture_output=True,
        )

        # Create project with both sources
        project = tmp_path / "project"
        project.mkdir()

        doc = tomlkit.document()
        doc.add("project", tomlkit.table())
        doc["project"].add("name", "my-project")
        doc["project"].add("dependencies", ["pkg1", "pkg2"])

        tool = tomlkit.table()
        uv = tomlkit.table()
        sources = tomlkit.table()

        src1 = tomlkit.inline_table()
        src1["git"] = repo1.as_uri()
        sources["pkg1"] = src1

        src2 = tomlkit.inline_table()
        src2["git"] = repo2.as_uri()
        sources["pkg2"] = src2

        uv["sources"] = sources
        tool["uv"] = uv
        doc["tool"] = tool

        (project / "pyproject.toml").write_text(tomlkit.dumps(doc))
        (project / ".gitignore").write_text("*.pyc\n")

        # Make both local
        returncode, _, stderr = run_uvedit_cmd(project, "local", "pkg1")
        assert returncode == 0, f"Failed pkg1: {stderr}"

        returncode, _, stderr = run_uvedit_cmd(project, "local", "pkg2")
        assert returncode == 0, f"Failed pkg2: {stderr}"

        sources = get_sources(project)
        assert "path" in sources["pkg1"] and sources["pkg1"]["editable"]
        assert "path" in sources["pkg2"] and sources["pkg2"]["editable"]

        # Restore pkg1 only
        returncode, _, stderr = run_uvedit_cmd(project, "restore", "pkg1")
        assert returncode == 0, f"Failed restore pkg1: {stderr}"

        sources = get_sources(project)
        assert sources["pkg1"]["git"] == repo1.as_uri()
        assert "path" not in sources["pkg1"]
        assert "path" in sources["pkg2"]  # pkg2 still local

        # Restore pkg2
        returncode, _, stderr = run_uvedit_cmd(project, "restore", "pkg2")
        assert returncode == 0, f"Failed restore pkg2: {stderr}"

        sources = get_sources(project)
        assert sources["pkg1"]["git"] == repo1.as_uri()
        assert sources["pkg2"]["git"] == repo2.as_uri()
        assert saved_state_exists(project) is False


class TestErrorCases:
    """Test error handling."""

    def test_restore_without_local_first(self, project_with_git_source: Path) -> None:
        """Restore should fail if local was never run."""
        project = project_with_git_source

        # Try to restore without running local first
        returncode, stdout, stderr = run_uvedit_cmd(project, "restore", "dummy-pkg")
        assert returncode != 0, "Should fail"
        assert "No saved source" in stderr or "No saved source" in stdout

    def test_local_with_invalid_package(self, project_with_git_source: Path) -> None:
        """Local should fail for non-existent package."""
        project = project_with_git_source

        returncode, stdout, stderr = run_uvedit_cmd(project, "local", "nonexistent-pkg")
        assert returncode != 0, "Should fail"


class TestRoundTrips:
    """Test multiple local/restore cycles."""

    def test_multiple_local_restore_cycles(self, project_with_git_source: Path) -> None:
        """Test doing local -> restore multiple times."""
        project = project_with_git_source
        sources_initial = get_sources(project)
        git_url = sources_initial["dummy-pkg"]["git"]

        for cycle in range(3):
            # Go local
            rc, _, stderr = run_uvedit_cmd(project, "local", "dummy-pkg")
            assert rc == 0, f"Cycle {cycle}: local failed: {stderr}"

            sources = get_sources(project)
            assert "path" in sources["dummy-pkg"], f"Cycle {cycle}: no path"
            assert sources["dummy-pkg"]["editable"], f"Cycle {cycle}: not editable"

            # Go back to git
            rc, _, stderr = run_uvedit_cmd(project, "restore", "dummy-pkg")
            assert rc == 0, f"Cycle {cycle}: restore failed: {stderr}"

            sources = get_sources(project)
            assert sources["dummy-pkg"]["git"] == git_url, f"Cycle {cycle}: git mismatch"
            assert "path" not in sources["dummy-pkg"], f"Cycle {cycle}: path still present"


class TestCheckoutRevisions:
    """Test that rev/branch/tag are properly checked out."""

    def test_local_checks_out_branch(self, tmp_path: Path) -> None:
        """Test that local checks out the specified branch."""
        # Create a git repo with multiple branches
        repo = tmp_path / "multi_branch_repo"
        repo.mkdir()

        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
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

        # Create main branch
        (repo / "main.txt").write_text("main branch")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # Create develop branch
        subprocess.run(
            ["git", "checkout", "-b", "develop"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "develop.txt").write_text("develop branch")
        (repo / "main.txt").unlink()
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "develop"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # Create project with develop branch source
        project = tmp_path / "project"
        project.mkdir()

        doc = tomlkit.document()
        doc.add("project", tomlkit.table())
        doc["project"].add("name", "my-project")
        doc["project"].add("dependencies", ["multi-pkg"])

        tool = tomlkit.table()
        uv = tomlkit.table()
        sources = tomlkit.table()

        source_entry = tomlkit.inline_table()
        source_entry["git"] = repo.as_uri()
        source_entry["branch"] = "develop"
        sources["multi-pkg"] = source_entry

        uv["sources"] = sources
        tool["uv"] = uv
        doc["tool"] = tool

        (project / "pyproject.toml").write_text(tomlkit.dumps(doc))
        (project / ".gitignore").write_text("*.pyc\n")

        # Run local
        rc, _, stderr = run_uvedit_cmd(project, "local", "multi-pkg")
        assert rc == 0, f"Failed: {stderr}"

        # Verify checkout is on develop branch with develop.txt
        checkout = project.parent / "multi-pkg"
        assert checkout.exists()
        assert (checkout / "develop.txt").exists(), "Not on develop branch"
        assert not (checkout / "main.txt").exists(), "On main branch, not develop"
