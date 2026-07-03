# Toolchain Detection

ForgeProof auto-detects the project's language and toolchain by scanning for configuration files at the project root.

## Supported Languages

### Python
- **Config files**: `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt`
- **Test runners** (checked in order): pytest
- **Linters** (checked in order): ruff, flake8
- **Interpreter**: the project's virtualenv (`.venv/` or `venv/`) when one exists, otherwise the interpreter running the engine — so recorded test and lint results reflect the project's environment, not the plugin's
- **Tool availability**: `<interpreter> -m <tool> --version` (list-form subprocess, no shell)

### TypeScript / JavaScript
- **Config files**: `package.json`
- **Test runners** (checked in order): jest, vitest, mocha
- **Linters** (checked in order): eslint
- **Runtime check**: `node` on `PATH` (via Python's `shutil.which`)
- **Tool availability**: filesystem-first — `node_modules/.bin/<tool>` (including `.cmd`/`.exe` on Windows), falling back to `PATH`. Detection never probes via bare `npx`, which could fetch from the registry; emitted commands use `npx --no-install`.

### Go
- **Config files**: `go.mod`
- **Test runners**: go test
- **Linters** (checked in order): golangci-lint
- **Runtime check**: `go` on `PATH` (via Python's `shutil.which`)

## Detection Logic

The `forgeproof.py detect` command:
1. Scans the project root for config files from each language
2. For each detected language, checks if the runtime is available
3. For each detected language, finds the first available test runner and linter
4. Outputs JSON with the detection results

Every check is a filesystem lookup or a list-form subprocess call — no shell
strings, no POSIX tools (`which`, `head`, `2>/dev/null`), no network. Each
detected test runner and linter carries both a `command` string (for display
and for Claude's shell tool) and an `argv` array (used internally by `lint`
and `lint-hook` for shell-free execution).

Multi-language projects (e.g., a repo with both `pyproject.toml` and `package.json`) will detect all languages. The skill should run tests and linting for all detected languages.

## Fallback

If no language is detected, the skill asks the user to manually specify:
- The command to run tests
- The command to run the linter

These commands are used directly in Phase 3 (Evaluate).
