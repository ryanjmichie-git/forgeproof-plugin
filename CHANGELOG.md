# Changelog

All notable changes to ForgeProof are documented in this file.

## [1.2.0] - 2026-07-12

"Verification by default": every PR that carries a ForgeProof bundle can now
be mechanically verified — a companion GitHub Action turns tamper or missing
evidence into a red check, and the run/push skills now guarantee the sealed
bundle is actually in the branch being verified. Bundle format unchanged —
every v1.0.x and v1.1.x `.rpack` still verifies, enforced by two frozen
fixtures in CI (v1.0.1 and v1.1.0).

### Fixed

- **The signed bundle never landed in the pushed branch.** The run skill
  committed the working tree *before* finalize produced the `.rpack`, so the
  bundle only ever existed locally — the workflow hole that would have made
  PR verification vacuous. The run skill now makes a post-finalize seal
  commit, and push refuses to proceed unless the bundle is committed at HEAD.
- `record` rejects negative `--passed`/`--failed`/`--errors`/`--warnings`
  counts and malformed `--covers` specs instead of sealing nonsense into the
  chain (issue #6).
- `record` refuses to append to a finalized chain instead of silently
  extending evidence that was already signed (issue #7).
- `detect` no longer crashes on a broken virtualenv interpreter — it falls
  back past a venv whose Python is missing or non-executable (issue #5,
  partial).

### Added

- **`verify --strict` and the `complete` output key** — verification now
  answers two questions separately: *integrity* (was anything that could be
  checked tampered with?) and *completeness* (is the chain and every recorded
  artifact actually present?). Lenient mode warns on missing evidence;
  `--strict` makes it red (issue #9).
- **`verify --project-root` and bundle-anchored path resolution** — artifact
  paths resolve relative to the bundle's location first, so a bundle
  verifies from any working directory (issue #8).
- **Structured verify JSON**: per-check `checks` array and a `bundle`
  metadata object alongside the legacy keys.
- **`verify --format markdown`** — a human audit report suitable for PR
  display, hardened against markdown/HTML injection from bundle-controlled
  strings.
- **forgeproof-verify GitHub Action** (companion repo:
  [ryanjmichie-git/forgeproof-verify](https://github.com/ryanjmichie-git/forgeproof-verify)) —
  verifies the bundle in a checked-out PR, writes the audit report to the job
  summary and as an upserted PR comment, red on tamper or missing evidence.
  This repo dogfoods it (`.github/workflows/verify-provenance.yml`), and
  `docs/branch-protection.md` is the consumer recipe: required-check setup
  (rulesets and classic), the `forgeproof/*` head-branch selectivity pattern,
  and fork-PR behavior.
- **v1.1.0 compatibility fixture** frozen in the repo with `TestV110Compat` —
  the forever contract now has two enforcement points (v1.0.1 and v1.1.0).
- README badges for CI and the companion Action.

### Changed

- `verify` JSON output gains additive keys only (`complete`, `checks`,
  `bundle`, `anchor`, `strict`); the legacy seven keys and all exit codes are
  unchanged — byte-compatible for existing consumers.
- The push skill's PR template now mentions that bundles are verified
  automatically on PRs via the forgeproof-verify Action.

## [1.1.0] - 2026-07-03

"Runs everywhere": macOS, Windows (Git Bash and PowerShell), and minimal
Linux with no `python` symlink. Bundle format unchanged — every v1.0.x
`.rpack` still verifies, enforced by a frozen v1.0.1 fixture in CI.

### Breaking

- **Command surface renamed** (old names removed, not aliased):

  | v1.0.x | v1.1.0 |
  |--------|--------|
  | `/forgeproof <issue>` | `/forgeproof:run <issue>` |
  | `/forgeproof-push` | `/forgeproof:push` |
  | `/forgeproof-verify <path>` | `/forgeproof:verify <path>` |
  | `/forgeproof-reset <issue\|--all>` | `/forgeproof:reset <issue\|--all>` |

  No state migration needed; the `.forgeproof/` layout is unchanged.

- **`--data` removed from `init` and `record`** — quoted JSON broke on any
  shell whenever a value contained a quote character. Discrete flags replace
  it (the produced chain data is shape-identical):

  | v1.0.x | v1.1.0 |
  |--------|--------|
  | `init --data '{"title": ..., "requirements": [...]}'` | `init --title TEXT --requirement "REQ-1: text"` (repeatable) |
  | `record --action branch-create --data '{...}'` | `--branch NAME --base BASE --base-sha SHA` |
  | `record --action file-edit --data '{...}'` | `--path FILE --operation create\|modify` (engine computes the SHA-256) |
  | `record --action decision --data '{...}'` | `--context TEXT --choice TEXT --rationale TEXT` |
  | `record --action test-result --data '{...}'` | `--suite NAME --passed N --failed N [--covers "REQ-1=test_a,test_b"]... [--failed-test NAME]...` |
  | `record --action lint-result --data '{...}'` | `--tool NAME --errors N --warnings N` |

  Passing `--data` now fails with this mapping in the error message.

### Fixed

- **Signature-field malleability.** `ssh-keygen -Y verify` ignores bytes after
  the SSHSIG END marker, so the `signature` field could be altered (junk
  appended) while still verifying. Verify now also requires the signature to be
  canonical SSHSIG armor, so any post-signing change to it turns verification
  red. (Content was always protected by the root digest; no forgery was ever
  possible — this closes the cosmetic malleability.)
- **Wrong-shape (not just malformed) chain/bundle files no longer traceback.**
  A bundle whose `issue` is not an object, a chain that is `[null]` or a JSON
  object instead of a list, and an empty-object bundle passed to `summary` now
  produce a clean error or a red verdict instead of a raw AttributeError /
  TypeError / KeyError. Complements the earlier malformed-JSON hardening.
- **`preflight` could hang forever.** It probed ssh-keygen with
  `ssh-keygen -h`, which is not a help flag — it starts *interactive key
  generation* and blocks on a stdin prompt (observed freezing live sessions
  for minutes). The probe is removed (availability is a PATH lookup) and
  every engine subprocess now runs with stdin closed, so no child can ever
  block waiting for interactive input.
- **PR gate now covers the PowerShell tool.** Claude Code on Windows exposes
  a first-class PowerShell tool alongside Bash; the v1.0.x matcher (`Bash`)
  and the gate's tool check let `gh pr create` through PowerShell bypass the
  gate entirely. The matcher is now `Bash|PowerShell` and the gate accepts
  both tool names.
- **PR gate failed open on python3-only systems.** The v1.0.1 hook command
  `python3 ... gate-pr 2>/dev/null || python ... gate-pr` converted a
  legitimate block (exit 2) into `python: not found` (exit 127 —
  non-blocking) precisely on the systems the fallback targeted. Hooks are
  now two independent single-command entries (`python3` and `python`); the
  gate additionally blocks via a structured permission denial on stdout, so
  it fails closed regardless of shell exit-code translation.
- **Hook command was a PowerShell parse error.** On Windows without Git
  Bash, hooks run under PowerShell 5.1, which cannot parse `||`. No hook
  command uses shell chaining anymore.
- **Engine broke on Windows**: toolchain detection shelled out to `which`,
  `2>/dev/null`, and `| head -20`. Detection and lint now use list-form
  subprocess calls and Python-side truncation exclusively; `shell=True` no
  longer appears in the engine.
- **README pointed `claude plugin validate` at the repo root**, which
  triggers marketplace validation instead of plugin validation.
- **README overstated hook scoping** ("neither fires during normal
  sessions"); the hooks section now documents the honest per-call cost.

### Added

- **Finalize artifact recheck**: `finalize` re-hashes every recorded file
  before signing and refuses (naming the stale paths) if any changed on
  disk after recording — a signed bundle now provably matches disk at
  signing time. Bundle artifacts are deduplicated per path (latest record
  wins) so re-edited files verify correctly.
- **`lint-hook` subcommand** (new PostToolUse handler): lints only the
  edited file, only during an active run, surfaces up to 20 lines of
  findings as context, always exits 0. Replaces the full-project lint that
  previously ran on every edit.
- **Portable toolchain detection**: prefers the project's virtualenv Python
  over the engine's interpreter; JS tools are found filesystem-first in
  `node_modules/.bin` with `npx --no-install` only (never a bare `npx`
  probe, which could hit the npm registry); `detect` emits an `argv` array
  alongside each command string.
- **v1.0.1 compatibility fixture** generated with the unmodified v1.0.1
  engine and frozen in the repo; `TestV101Compat` is the forever contract
  from the roadmap's Principle 1.
- **CI platform matrix**: Ubuntu, macOS, Windows (default shell, Git Bash,
  and cmd.exe), a python3-only Debian container, and
  `claude plugin validate` against the plugin manifest (`--strict` is
  documented but not implemented on current CLI 2.1.x; CI adds it back
  once the flag exists).
- **Hook regression tests** that spawn the exact configured hook commands
  against block/allow scenarios, and a **skill-contract test** that parses
  every documented engine invocation against the real CLI.

### Changed

- Skills detect the Python interpreter once (`python3`, then `python`) and
  adapt invocation syntax to the active shell; no bare `python` assumptions
  remain anywhere.
- `lint` gained `--file` for single-file scope.
- `marketplace.json` no longer carries version fields; `plugin.json` is the
  single source of version truth (it wins anyway, so the copies were dead
  weight that could only mislead).

### Removed

- `--data` (see Breaking), `shell_run()` (the engine's last `shell=True`
  path), the `sha256sum` instruction from the skill, and both
  `marketplace.json` version fields.

### Known caveat for plugin developers

Claude Code 2.1.128 silently ignores the documented exec form for hooks
(`command` + `args` array) — the args are dropped at spawn time and
`claude plugin validate` does not flag it. ForgeProof's hooks deliberately
use single-command shell strings; do not convert them to exec form without
a live plugin-loaded retest (see the note inside `hooks/hooks.json`).

## [1.0.1] - 2026-05-12

### Fixed
- **Plugin failed to load.** `hooks/hooks.json` was missing the top-level `"hooks"` wrapper expected by Claude Code's Zod schema, producing a validation error on install (reported via `/doctor`). The events are now nested under `hooks` and the file references `https://json.schemastore.org/claude-code-settings.json` for editor validation.
- **PreToolUse PR gate never fired.** The matcher `Bash(gh pr create)` is permission-rule syntax, not hook-matcher syntax (matchers are regex against the tool name only). The gate is now a regex match on `Bash`, with the command inspection handled by a new `gate-pr` subcommand in `forgeproof.py` that parses the hook event JSON from stdin and exits with code 2 (block + surface stderr to Claude) when no `.rpack` bundle is present.
- Hook command falls back from `python3` to `python` so the gate works on Linux installs that ship only `python3` and Windows installs that ship only `python`.

### Tests
- Added `TestCmdGatePr` covering allow/block paths, unrelated commands, non-Bash tools, and malformed stdin. 44 tests pass.

## [1.0.0] - 2026-04-15

Initial public release.

### Skills
- `/forgeproof <issue>` — Full 4-phase pipeline: parse & plan, generate, evaluate, package
- `/forgeproof-push` — Push branch and create PR with provenance metadata
- `/forgeproof-verify <path>` — Verify .rpack bundle integrity (signature, chain, artifacts)
- `/forgeproof-reset <issue|--all>` — Clean up provenance state, branches, and ephemeral keys

### Provenance Engine
- Ed25519-signed SHA-256 hash chain with tamper-evident block linkage
- Ephemeral keypair generation per bundle (private key deleted after signing)
- Multi-language toolchain detection (Python, TypeScript/JavaScript, Go)
- Explicit file staging (no `git add -A`) to prevent committing generated artifacts
- Re-run handling: `--force` flag on init, graceful branch/PR detection
- `reset` subcommand for cleaning up chains, bundles, and keys

### Hooks
- PreToolUse: blocks `gh pr create` without a signed .rpack bundle
- PostToolUse: runs project linter during active ForgeProof runs (scoped to sessions with an active chain)

### Testing
- 38 automated tests covering all subcommands, chain integrity, verification, and E2E pipeline
- `claude plugin validate` passes with 0 errors
- Validated end-to-end across 4 GitHub issues on a real Python project

### Security
- No external network calls beyond `gh` CLI and `ssh-keygen`
- No telemetry, analytics, or credential persistence
- All provenance data stored locally in `.forgeproof/`
