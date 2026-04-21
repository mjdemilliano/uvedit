# PYTHON_ARGCOMPLETE_OK
import argparse
from functools import lru_cache
import subprocess
import sys
from pathlib import Path
from collections.abc import Generator

import tomlkit

from uvedit.configuration import find_pyproject, get_sources
from uvedit.git import ensure_gitignore_entry
from uvedit.save_state import SAVEDSTATE_FILE, load_savedstate, save_savedstate


@lru_cache
def get_available_packages() -> list[str]:
    """Get list of available package names from pyproject.toml sources."""
    try:
        pyproject_path = find_pyproject()
        doc = tomlkit.parse(pyproject_path.read_text())
        sources = get_sources(doc)
        return sorted(sources.keys())
    except SystemExit:
        return []


def available_packages_completer(
    prefix, parsed_args, **kwargs
) -> Generator[str, None, None]:
    resource = get_available_packages()
    return (member for member in resource if member.startswith(prefix))


def cmd_local(args: argparse.Namespace) -> None:
    package = args.package
    pyproject_path = find_pyproject()
    project_dir = pyproject_path.parent

    doc = tomlkit.parse(pyproject_path.read_text())
    sources = get_sources(doc)
    current_source = sources.get(package)

    if current_source and "path" in current_source:
        print(f"'{package}' already uses a local checkout: {current_source['path']}")
        return

    if not current_source or "git" not in current_source:
        print(f"Error: No git source found for '{package}' in [tool.uv.sources].")
        sys.exit(1)

    git_url = current_source["git"]
    checkout_dir = (
        Path(args.dir).resolve()
        if args.dir
        else (project_dir.parent / package).resolve()
    )

    if not checkout_dir.exists():
        print(f"Cloning {git_url} into {checkout_dir} ...")
        result = subprocess.run(["git", "clone", git_url, str(checkout_dir)])
        if result.returncode != 0:
            print("Error: git clone failed.")
            sys.exit(1)
    else:
        print(f"Using existing checkout at {checkout_dir}")

    # Persist original source so restore can bring it back
    saved = load_savedstate(project_dir)
    if package not in saved:
        saved[package] = dict(current_source)
        save_savedstate(project_dir, saved)
        ensure_gitignore_entry(project_dir, SAVEDSTATE_FILE)

    rel_path = checkout_dir.relative_to(project_dir)

    new_source = tomlkit.inline_table()
    new_source.append("path", rel_path)
    new_source.append("editable", True)
    sources[package] = new_source

    pyproject_path.write_text(tomlkit.dumps(doc))
    print(f"Switched '{package}' to local editable checkout at '{rel_path}'.")
    print("Run 'uv sync' to apply.")


def cmd_restore(args: argparse.Namespace) -> None:
    package = args.package
    pyproject_path = find_pyproject()
    project_dir = pyproject_path.parent

    saved = load_savedstate(project_dir)
    if package not in saved:
        print(
            f"Error: No saved source for '{package}'. Was 'uvedit local {package}' run first?"
        )
        sys.exit(1)

    original = saved[package]
    doc = tomlkit.parse(pyproject_path.read_text())
    sources = get_sources(doc)

    restored = tomlkit.inline_table()
    for k, v in original.items():
        restored.append(k, v)
    sources[package] = restored

    pyproject_path.write_text(tomlkit.dumps(doc))

    del saved[package]
    save_savedstate(project_dir, saved)

    print(f"Restored '{package}' to remote source: {dict(original)}")
    print("Run 'uv sync' to apply.")


def main(argv: list[str] | None = None) -> None:
    if not argv:
        argv = sys.argv

    parser = argparse.ArgumentParser(
        description="Switch uv dependencies between local checkouts and remote git sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_local = sub.add_parser(
        "local", help="Use a local editable checkout (clones if needed)"
    )

    p_local.add_argument(
        "package",
        help="Package name as it appears in pyproject.toml",
    ).completer = available_packages_completer

    p_local.add_argument(
        "--dir", metavar="PATH", help="Where to clone (default: ../PACKAGE)"
    )
    p_local.set_defaults(func=cmd_local)

    p_restore = sub.add_parser("restore", help="Restore the original remote git source")
    p_restore.add_argument("package", help="Package name").completer = (
        available_packages_completer
    )
    p_restore.set_defaults(func=cmd_restore)

    try:
        import argcomplete

        argcomplete.autocomplete(parser)
    except (ImportError, ModuleNotFoundError):
        pass

    args = parser.parse_args(argv[1:])
    args.func(args)
