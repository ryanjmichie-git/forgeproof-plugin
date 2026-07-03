# ForgeProof

Turn GitHub issues into working code with cryptographically signed provenance bundles.

When you invoke ForgeProof, Claude reads a GitHub issue, extracts requirements, plans an implementation, writes code and tests, then packages everything into a tamper-evident `.rpack` bundle. The bundle proves what was done, why, and that nothing was altered after signing.

## Install

In Claude Code:

```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install forgeproof@claude-community
/reload-plugins
```

Or browse interactively: run `/plugin`, go to the **Discover** tab, search for `forgeproof`, press Enter, and choose your install scope.

Prefer the CLI? Same commands without the leading slash:

```bash
claude plugin marketplace add anthropics/claude-plugins-community
claude plugin install forgeproof@claude-community
```

## Requirements

- **Python 3.11+** (stdlib only — no pip dependencies). Either `python3` or `python` on `PATH` works; the plugin detects which one you have.
- **OpenSSH 8.0+** (provides `ssh-keygen` for Ed25519 signing). Included on macOS and Linux. On Windows it ships as the "OpenSSH Client" optional feature (present by default on Windows 10+, occasionally disabled — enable it under *Settings → System → Optional features*, or install [Git for Windows](https://gitforwindows.org/), which bundles it).
- **GitHub CLI** (`gh`) authenticated to your account — [install](https://cli.github.com/)

ForgeProof checks all of this for you at the start of every `/forgeproof:run` (the preflight step) and tells you exactly what is missing.

## Upgrading from 1.0.x

v1.1.0 renames the command surface so slash commands read naturally. Old names are removed, not aliased:

| v1.0.x | v1.1.0 |
|--------|--------|
| `/forgeproof <issue>` | `/forgeproof:run <issue>` |
| `/forgeproof-push` | `/forgeproof:push` |
| `/forgeproof-verify <path>` | `/forgeproof:verify <path>` |
| `/forgeproof-reset <issue\|--all>` | `/forgeproof:reset <issue\|--all>` |

No state migration is needed: the `.forgeproof/` directory layout is unchanged, and **every bundle ever signed by any v1.0.x release still verifies** — that is a permanent compatibility promise, enforced in CI by a frozen v1.0.1 fixture bundle.

## Supported Languages

ForgeProof auto-detects your project's language and toolchain:

| Language | Config file | Test runner | Linter |
|----------|-------------|-------------|--------|
| Python | `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt` | pytest | ruff, flake8 |
| TypeScript/JavaScript | `package.json` | jest, vitest, mocha | eslint |
| Go | `go.mod` | go test | golangci-lint |

## Usage

### Generate code from an issue

```
/forgeproof:run 42
```

Runs the full pipeline: fetch issue → extract requirements → plan → generate code → run tests → sign `.rpack` bundle. You'll be asked to approve the plan before code generation begins.

Browse your assigned issues instead:
```
/forgeproof:run
```

### Push to a PR

```
/forgeproof:push
```

Creates a git branch and opens a pull request with the provenance summary embedded in the PR description.

### Verify a bundle

```
/forgeproof:verify .forgeproof/issue-42.rpack
```

Checks the Ed25519 signature, hash chain integrity, and artifact hashes. Reports whether the bundle has been tampered with.

### Clean up state

```
/forgeproof:reset 42
```

Removes provenance chains, bundles, ephemeral keys, and branches for a specific issue. Use `--all` to clean everything.

### Re-running on the same issue

ForgeProof handles re-runs gracefully. Running `/forgeproof:run 42` again will:
- Clean up the previous chain and bundle (via `--force`)
- Delete and recreate the local branch
- Push with `--force-with-lease` if the remote branch exists
- Update the existing PR instead of creating a duplicate

## How It Works

ForgeProof operates in four phases:

1. **Parse & Plan** — Fetches the GitHub issue, extracts structured requirements (REQ-1, REQ-2, ...), scans the repo, and proposes a plan. Waits for your approval.
2. **Generate** — Writes implementation and tests. Every file edit and decision is logged to a SHA-256 hash chain with Ed25519 signatures.
3. **Evaluate** — Runs your project's test suite and linter. Maps results back to requirements. Attempts one auto-fix if something fails.
4. **Package** — Builds the `.rpack` provenance bundle: manifest, artifact hashes, requirement coverage, decision log, and a root Ed25519 signature. The ephemeral private key is deleted after signing.

## The .rpack Bundle

The `.rpack` file is a JSON document containing:

- **Issue metadata** — number, title, URL
- **Requirements** — extracted from the issue, with coverage status
- **Artifacts** — every file created or modified, with SHA-256 hashes
- **Decisions** — why Claude chose each approach
- **Evaluation** — test results, lint results, coverage percentage
- **Signature** — Ed25519 signature over a root digest of all the above

The evaluation status is one of:
- `pass` — all requirements covered, all tests pass
- `partial` — some requirements uncovered or tests failing (details included)
- `fail` — critical failures

Bundles are always produced regardless of status. The status tells reviewers whether to trust the bundle at a glance.

## Security Model

- **Ephemeral keys** — a new Ed25519 keypair is generated per bundle. The private key is deleted after signing. The public key is embedded in the `.rpack` for self-contained verification.
- **Tamper evidence** — modifying any field in the bundle, any block in the chain, or any artifact file causes verification to fail.
- **No external data transmission** — all data stays local. ForgeProof only calls `gh` CLI (which uses your existing GitHub auth) and `ssh-keygen`.

## Privacy

ForgeProof stores provenance data locally in the `.forgeproof/` directory at your project root. No data is sent to external servers beyond what `gh` CLI sends to GitHub (issue reads, PR creation). No telemetry, no analytics, no third-party services.

## Troubleshooting

**"No chain found for issue N"** — Run `/forgeproof:run N` first to initialize the chain.

**"No ephemeral key found"** — The key is session-scoped. If you initialized the chain in a previous session, you'll need to re-run `/forgeproof:run N` to generate a new key.

**"ssh-keygen failed"** — Ensure OpenSSH 8.0+ is installed. On macOS, the built-in ssh-keygen works. On Linux, install `openssh-client`. On Windows, enable the "OpenSSH Client" optional feature or install Git for Windows.

**"artifact recheck failed" during finalize** — A recorded file changed on disk after it was recorded. This is finalize refusing to sign a bundle that doesn't match reality. Record the current state of each named file (`record --action file-edit`) and finalize again.

**"gh issue list failed"** — Run `gh auth status` to check authentication. Run `gh auth login` if needed.

**Verification fails with "Root digest mismatch"** — The bundle contents were modified after signing. This is the tamper detection working as intended.

**Verification warns "Artifact not found"** — Normal when verifying a bundle from a different checkout or branch. The artifact hashes can only be checked against files that exist locally.

## Known Limitations

- **Recording completeness is prompt-enforced** — `finalize` re-hashes every recorded file and refuses to sign if any no longer matches disk, so a signed bundle is guaranteed to match reality *for the files it records, at signing time*. That Claude recorded *every* edit it made is enforced by the skill instructions, not by cryptography. Provenance makes work attributable and tamper-evident; it does not make unrecorded work impossible.
- **Post-rebase commit SHA mismatch** — If you rebase a forgeproof branch after finalization, the `commit_sha` in the bundle no longer matches the branch HEAD. Verification still passes (it checks artifacts and chain integrity, not git commits). Workaround: re-run `/forgeproof:run` after rebasing.
- **Ephemeral keys are session-scoped** — The Ed25519 private key exists only in the system temp directory for the current session. If the session ends before finalization, re-run `/forgeproof:run` to generate a new key.
- **No `.gitignore` enforcement** — ForgeProof warns if no `.gitignore` exists but does not create one. Ensure your project has one to avoid committing `__pycache__/` and other generated files.

## Hooks (Automatic Behavior)

ForgeProof registers two hooks. Honest accounting of what they cost and when they act:

- **PreToolUse (PR gate)** — Spawns on *every* Bash or PowerShell tool call while the plugin is enabled (a fast, read-only Python process that exits immediately for anything that isn't `gh pr create`). When the command *is* `gh pr create` and no signed `.rpack` exists in `.forgeproof/`, it blocks the call and tells Claude to run `/forgeproof:run` first. Both shell tools are gated — covering Bash alone would let PRs bypass provenance from Windows PowerShell sessions. It blocks through two independent protocols (a structured permission denial on stdout and exit code 2), so the gate fails **closed** regardless of which one your Claude Code version honors.

- **PostToolUse (lint feedback)** — Spawns after each `Edit`/`Write` and exits silently unless an active ForgeProof chain exists (`.forgeproof/chain-*.json`). During an active run it lints **only the edited file** (never the whole project) and surfaces up to 20 lines of findings to Claude as context. It never blocks an edit.

Both hooks are registered twice, once for `python3` and once for `python`, so whichever interpreter your system has delivers the verdict — a missing interpreter produces harmless spawn noise, never a silently disabled gate. On systems with both interpreters the hooks run twice; both are read-only and idempotent, so the duplicate is cosmetic.

## Testing & Validation

ForgeProof includes 83 automated tests covering:

- Utility functions (SHA-256, canonical JSON determinism)
- Chain operations (hash linkage, block structure, save/load)
- All subcommands (init, record, finalize, verify, detect, summary, reset, lint-hook, gate-pr)
- **v1.0.x compatibility** — a bundle generated by the unmodified v1.0.1 engine is frozen in the repo and must verify forever
- **Hook configuration** — the exact configured hook commands are spawned against block/allow scenarios, so a never-fires misconfiguration fails CI loudly
- **Skill contract** — every engine invocation documented in the skills is parsed against the real CLI, so a stale example fails CI instead of breaking a run
- End-to-end integration (full pipeline with real Ed25519 signing and tamper detection)

CI runs the suite on Ubuntu, macOS, and Windows (both Git Bash and cmd.exe), plus a python3-only Debian container that has no `python` command at all.

Run the test suite:
```bash
python -m pytest skills/run/scripts/test_forgeproof.py -v
```

Plugin validation (validate the plugin manifest explicitly — pointing `validate` at the repo root triggers *marketplace* validation instead, because `.claude-plugin/marketplace.json` exists):
```bash
claude plugin validate .claude-plugin/plugin.json
```

The plugin was validated end-to-end across 4 GitHub issues on a real Python project, covering bug fixes, feature additions, search functionality, and JSON serialization. All provenance bundles were verified with `/forgeproof:verify`.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.
