# uvedit

Switch `uv` dependencies between local editable checkouts and remote git sources.

Useful when you are a developer of a package that another project depends on via a git source, and you want to work on both simultaneously.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) installed
- The package must already have a `git` entry in `[tool.uv.sources]` in `pyproject.toml`:

```toml
[tool.uv.sources]
my-lib = { git = "https://github.com/you/my-lib" }
```

## Usage

```bash
uvedit local <package> [--dir PATH]
uvedit restore <package>
```

### `local` — switch to a local editable checkout

```bash
uvedit local my-lib
uv sync
```

- Clones the git repository to `../my-lib` (relative to `pyproject.toml`) if it doesn't already exist
- Use `--dir PATH` to specify a different checkout location
- Saves the original git source to `.uvedit.toml` so it can be restored later
- Rewrites the `[tool.uv.sources]` entry to `{ path = "../my-lib", editable = true }`
- Adds `.uvedit.toml` to `.gitignore` if one exists

### `restore` — restore the remote git source

```bash
uvedit restore my-lib
uv sync
```

- Reads the original source from `.uvedit.toml`
- Rewrites the `[tool.uv.sources]` entry back to the original git source
- Removes the package entry from `.uvedit.toml` (deletes the file if empty)

## How it works

`uvedit` stores the original remote source in `.uvedit.toml` at the project root when switching to a local checkout. This file should not be committed (it is added to `.gitignore` automatically). The local checkout is not affected by `restore` — it stays on disk and will be reused if you run `local` again.

## Installation

```console
uv tool install 'git+https://github.com/mjdemilliano/uvedit'
```
