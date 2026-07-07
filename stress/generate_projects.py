"""Sample-project generators for the ForgeProof stress harness.

Python stdlib only. Each generator creates a self-contained project directory
under the given base path and returns its root. Projects deliberately vary in
complexity, toolchain, and hostility (unicode, spaces, quote-bearing titles).

No generator touches the network: JS/TS tools are deterministic stubs in
node_modules/.bin, and the venv is created --without-pip.
"""

from __future__ import annotations

import os
import venv
from pathlib import Path

# A title that breaks naive quoting on every shell.
NASTY_TITLE = """He said "don't" — 100% of $titles `work` & <more>"""

PY_MODULE = '''"""Tiny module used as a recorded artifact."""


def add(a: int, b: int) -> int:
    return a + b
'''

PY_SECOND = '''"""Second artifact for multi-file scenarios."""

GREETING = "hello"
'''


def _write(root: Path, rel: str, content: str = "", newline: str = "\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline=newline) as f:
        f.write(content)
    return p


def _pyproject(root: Path, name: str = "stress-sample") -> None:
    _write(root, "pyproject.toml", f'[project]\nname = "{name}"\nversion = "0.0.1"\n')


def _stub_js_tool(root: Path, tool: str, output: str, exit_code: int = 0) -> None:
    """A deterministic stand-in for a JS tool, runnable list-form on every OS."""
    bin_dir = root / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    posix = bin_dir / tool
    with open(posix, "w", encoding="utf-8", newline="\n") as f:
        f.write(f'#!/bin/sh\necho "{output}"\nexit {exit_code}\n')
    try:
        os.chmod(posix, 0o755)
    except OSError:
        pass
    with open(bin_dir / f"{tool}.cmd", "w", encoding="utf-8", newline="\r\n") as f:
        f.write(f"@echo off\r\necho {output}\r\nexit /b {exit_code}\r\n")


def gen_py_minimal(base: Path) -> Path:
    root = base / "py-minimal"
    _pyproject(root)
    _write(root, "src/mathy.py", PY_MODULE)
    _write(root, "src/second.py", PY_SECOND)
    return root


def gen_py_venv(base: Path) -> Path:
    root = base / "py-venv"
    _pyproject(root)
    _write(root, "src/mathy.py", PY_MODULE)
    # Real venv, no pip (works even on Debian without python3-venv's ensurepip)
    venv.EnvBuilder(with_pip=False).create(root / ".venv")
    return root


def gen_js_stub_tools(base: Path) -> Path:
    root = base / "js-stub-tools"
    _write(root, "package.json", '{"name": "stress-js", "version": "0.0.1"}\n')
    _write(root, "index.js", "module.exports = () => 42;\n")
    _stub_js_tool(root, "jest", "stub-jest ok", 0)
    _stub_js_tool(root, "eslint", "index.js:1:1: stub-finding no-answer", 1)
    return root


def gen_ts_vitest_stub(base: Path) -> Path:
    root = base / "ts-vitest-stub"
    _write(root, "package.json", '{"name": "stress-ts", "version": "0.0.1"}\n')
    _write(root, "index.ts", "export const x: number = 1;\n")
    _stub_js_tool(root, "vitest", "stub-vitest ok", 0)
    return root


def gen_go_mod(base: Path) -> Path:
    root = base / "go-mod"
    _write(root, "go.mod", "module example.com/stress\n\ngo 1.21\n")
    _write(root, "main.go", "package main\n\nfunc main() {}\n")
    return root


def gen_polyglot(base: Path) -> Path:
    root = base / "polyglot"
    _pyproject(root, "stress-polyglot")
    _write(root, "src/mathy.py", PY_MODULE)
    _write(root, "package.json", '{"name": "stress-poly", "version": "0.0.1"}\n')
    _write(root, "index.js", "module.exports = 1;\n")
    _stub_js_tool(root, "eslint", "index.js:1:1: stub-finding poly", 1)
    _write(root, "go.mod", "module example.com/poly\n\ngo 1.21\n")
    return root


def gen_no_toolchain(base: Path) -> Path:
    root = base / "no-toolchain"
    _write(root, "README.md", "# Provenance needs no toolchain\n")
    _write(root, "notes/design.md", "decisions live here\n")
    return root


def gen_nasty_strings(base: Path) -> Path:
    # Spaces and unicode in the project path AND artifact paths.
    root = base / "nästy prøject"
    _pyproject(root, "stress-nasty")
    _write(root, "src/spä ced module.py", PY_MODULE)
    _write(root, "src/plain.py", PY_SECOND)
    return root


def gen_large(base: Path) -> Path:
    root = base / "large"
    _pyproject(root, "stress-large")
    for i in range(500):
        _write(root, f"pkg/mod_{i:03d}.py", f"VALUE_{i} = {i}\n")
    return root


def gen_re_edit_heavy(base: Path) -> Path:
    root = base / "re-edit-heavy"
    _pyproject(root, "stress-reedit")
    _write(root, "src/churn.py", "STATE = 0\n")
    return root


def gen_hooks(base: Path) -> Path:
    # JS project with a failing-stub linter so lint-hook findings are
    # deterministic on every OS, plus a bare dir for gate block cases.
    root = base / "hooks"
    _write(root, "package.json", '{"name": "stress-hooks", "version": "0.0.1"}\n')
    _write(root, "app.js", "var unused = 1;\n")
    _write(root, "notes.md", "# not lintable\n")
    _stub_js_tool(root, "eslint", "app.js:1:5: stub-finding no-unused-vars", 1)
    return root


SCENARIOS = {
    "py-minimal": gen_py_minimal,
    "py-venv": gen_py_venv,
    "js-stub-tools": gen_js_stub_tools,
    "ts-vitest-stub": gen_ts_vitest_stub,
    "go-mod": gen_go_mod,
    "polyglot": gen_polyglot,
    "no-toolchain": gen_no_toolchain,
    "nasty-strings": gen_nasty_strings,
    "large": gen_large,
    "re-edit-heavy": gen_re_edit_heavy,
    "hooks": gen_hooks,
}

# Unique issue numbers so parallel runs on one machine never share ephemeral
# key paths in the system temp directory.
ISSUE_NUMBERS = {name: 9100 + i for i, name in enumerate(SCENARIOS)}
