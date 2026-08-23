"""Controls verifiable by inspecting the codebase itself.

Some controls are properties of the whole repository rather than of one function.
C-24 (no string-built SQL) is the clearest example: it cannot be demonstrated by
exercising an endpoint, only by showing that no such construction exists anywhere,
including in analytics and migration scripts.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
#: Runtime code: everything that can ever see user input. The C-24 check is strict here.
RUNTIME_DIRS = [REPO / "src", REPO / "scripts"]
#: Migrations are checked separately -- see test_migrations_interpolate_only_literals.
MIGRATION_DIR = REPO / "migrations"
SOURCE_DIRS = [*RUNTIME_DIRS, MIGRATION_DIR]

SQL_VERBS = r"(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|GRANT|REVOKE|TRUNCATE)"


def _python_files(dirs: list[pathlib.Path] | None = None) -> list[pathlib.Path]:
    return [
        path
        for directory in (dirs if dirs is not None else SOURCE_DIRS)
        if directory.is_dir()
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


# --- C-24: parameterised queries everywhere -----------------------------------------


def test_no_fstring_or_percent_built_sql() -> None:
    """C-24 / threat T-13: no SQL is built by string formatting in runtime code.

    Scoped to src/ and scripts/ -- every code path that can see user input. Migrations
    are covered by test_migrations_interpolate_only_literals below, because SQL cannot
    bind an identifier: a table name in DDL has to be interpolated, and a migration
    takes no user input at all.
    """
    offenders: list[str] = []

    for path in _python_files(RUNTIME_DIRS):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            fragment = ""
            if isinstance(node, ast.JoinedStr):
                fragment = "".join(
                    part.value for part in node.values if isinstance(part, ast.Constant)
                )
            elif (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Mod)
                and isinstance(node.left, ast.Constant)
                and isinstance(node.left.value, str)
            ):
                fragment = node.left.value
            if not fragment or not re.search(SQL_VERBS, fragment, re.I):
                continue
            offenders.append(f"{path.relative_to(REPO)}:{node.lineno}: {fragment[:70]}")

    assert not offenders, "string-built SQL found (control C-24):\n" + "\n".join(offenders)


def test_migrations_interpolate_only_module_level_literals() -> None:
    """Migrations may interpolate identifiers, but only from literal constants.

    SQL cannot parameterise a table name, so DDL interpolation is unavoidable. What
    matters is that the interpolated value can never be attacker-influenced: every
    f-string in a migration must substitute a name bound from a module-level literal
    (a constant, or the loop variable over one), never a function argument or an
    external value.
    """
    allowed_names = {"table", "command", "predicate", "clause"}
    offenders: list[str] = []
    for path in _python_files([MIGRATION_DIR]):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            for part in node.values:
                if not isinstance(part, ast.FormattedValue):
                    continue
                # Resolve to the root identifier: `command.lower()` is still `command`.
                roots = {sub.id for sub in ast.walk(part.value) if isinstance(sub, ast.Name)}
                if roots and roots <= allowed_names:
                    continue
                expression = part.value
                offenders.append(
                    f"{path.relative_to(REPO)}:{node.lineno}: "
                    f"interpolates {ast.dump(expression)[:60]}"
                )
    assert not offenders, "migration interpolates a non-literal:\n" + "\n".join(offenders)


def test_sql_text_calls_use_bound_parameters() -> None:
    """Any text() containing a value placeholder must use :named binding, not literals."""
    pattern = re.compile(r"text\(\s*f[\"']", re.M)
    offenders = [
        str(path.relative_to(REPO))
        for path in _python_files()
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"text() built from an f-string: {offenders}"


# --- C-35: no secrets in code --------------------------------------------------------


def test_no_hardcoded_secret_defaults_in_settings() -> None:
    """C-35: secret_key and database_url must have no default at all."""
    config = (REPO / "src" / "adai" / "config.py").read_text(encoding="utf-8")
    assert (
        "secret_key: SecretStr = Field(..." in config
        or "secret_key: SecretStr = Field(...," in config
    )
    assert "database_url: str = Field(..." in config


def test_env_example_contains_no_real_looking_secrets() -> None:
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    for pattern in (r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{20,}"):
        assert not re.search(pattern, text), f"{pattern} appears in .env.example"


# --- C-45: the API image contains no ML stack ----------------------------------------


def test_api_lockfile_has_no_ml_dependency() -> None:
    """Mirrors scripts/check_api_isolation.py so the property is also a test."""
    lock = (REPO / "requirements" / "api.lock.txt").read_text(encoding="utf-8")
    pins = {
        line.split("==")[0].lower()
        for line in lock.splitlines()
        if "==" in line and not line.startswith(" ")
    }
    forbidden = {"torch", "surya-ocr", "paddlepaddle", "paddleocr", "kraken", "onnxruntime"}
    assert not (pins & forbidden), f"ML stack in the api image: {sorted(pins & forbidden)}"


# --- C-05: no static file serving, so no directory listing ---------------------------


def test_no_staticfiles_mount() -> None:
    """C-05: the API serves no static directory, so there is nothing to list.

    User uploads are served only through an authenticated, authorising endpoint (C-30).
    """
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (REPO / "src" / "adai").rglob("*.py")
    )
    assert "StaticFiles" not in source
    assert "html=True" not in source


# --- C-34: no torch.load anywhere ----------------------------------------------------


@pytest.mark.parametrize("forbidden", ["torch.load(", "pickle.load(", "pickle.loads("])
def test_no_pickle_deserialisation_in_source(forbidden: str) -> None:
    """C-34 / threat T-05: pickle deserialisation is arbitrary code execution."""
    offenders = [
        str(path.relative_to(REPO))
        for path in _python_files()
        if forbidden in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"{forbidden} found in: {offenders}"
