# PLAN_v1.1.0.md — ForgeProof "Runs everywhere"

> **Executor instructions:** This plan is self-contained — it assumes you have this document and the repo at `c:\Dev\FORGEPROOF_SKILL2` (github.com/ryanjmichie-git/forgeproof-plugin), and nothing else. Execute phases in order, one commit per phase, on branch `release/v1.1.0`. Commit this document as the first action of Phase 0 (before the release branch is cut, alongside the `ROADMAP.md` hygiene commit on `main`).

**Status:** Approved 2026-07-03 (plan approved in-session; two external LLM reviews incorporated — see disposition note below)
**Target version:** 1.1.0 (plugin.json bumps exactly once, as the final step of Phase 5)
**Baseline:** `main` @ `d71376c` (v1.0.1, marketplace manifest merged)

---

## Context

ForgeProof (a Claude Code plugin) turns GitHub issues into code sealed in Ed25519-signed, SHA-256 hash-chained `.rpack` provenance bundles. v1.0.x works where it was developed (Linux-ish dev machine with both `python` and `python3`, POSIX shell everywhere). The v1.1.0 release theme from ROADMAP.md is **"Runs everywhere"**: macOS, Windows, and minimal Linux, plus a native-feeling command surface (`/forgeproof:run` et al.). Out of scope (binding, per ROADMAP): anything that changes the bundle format or adds new workflow capabilities.

### Where the review file went

`FORGEPROOF_REVIEW.md` (the 16-issue review) **does not exist** — not in the working tree, the repo's git history, any branch, the parent repo (`c:\Dev\ForgeProof`), or Desktop folders. ROADMAP.md references it, but it was never committed. **User decision (2026-07-03): reconstruct the triage from evidence** — code inspection, git history, and CHANGELOG — rather than block. The triage table in this plan covers the 8 findings recoverable from evidence plus 6 additional defects found during plan research. It does not claim to reproduce the original 16 items.

### Review-vs-reality corrections (findings that contradict the brief)

1. **"`cmd_record` shells out to `sha256sum`" is imprecise.** The engine already computes hashes natively (`sha256_file()`, `skills/forgeproof/scripts/forgeproof.py:53-59`) and `cmd_record` never invokes `sha256sum`. The shell-out lives in **`skills/forgeproof/SKILL.md:122`**, which instructs Claude to run `sha256sum <filepath> | cut -d' ' -f1` and paste the result into `--data`. The fix is therefore: teach `cmd_record` to compute the digest itself from a `--path` flag (using the existing `sha256_file()`), and delete the `sha256sum` instruction from the skill.
2. **The v1.0.1 interpreter fallback has a fail-open bug worse than reported.** `hooks/hooks.json` PreToolUse runs `python3 $FP gate-pr 2>/dev/null || python $FP gate-pr`. On python3-only Linux (the common case the fallback targets), a legitimate **block** (exit 2) from `python3` triggers the `||`, `python` is not found (exit 127), and the hook's final exit is 127 — a *non-blocking* error. **The gate fails open exactly when it must block.** Additionally `2>/dev/null` suppresses the block reason. The fix is structural (exec-form hooks, below), not a tweak to the chain.
3. **cmd.exe is not actually in the hook execution path.** Current official docs: hook commands run via `sh -c` on macOS/Linux and **Git Bash on Windows, or PowerShell when Git Bash isn't installed** — never cmd.exe. PowerShell 5.1 cannot parse `||`, so the current hook command is a parse error on GitBash-less Windows. SKILL.md commands run through Claude's Bash tool (Git Bash on Windows), so POSIX syntax in skills is safe. The `--data` single-quoted JSON is still worth replacing: it breaks whenever an issue title contains a quote character, on every platform.
4. **Windows breakage in the engine is in `TOOLCHAIN_MAP`, not hashing:** `which node` (no `which` outside POSIX), `2>/dev/null` (invalid path outside POSIX shells), and `cmd += " --quiet 2>&1 | head -20"` (`head` absent on Windows) at `forgeproof.py:296-330, 918`.

### Key doc facts this plan relies on (fetched 2026-07-03 from code.claude.com/docs)

- Plugin `hooks/hooks.json`: top-level `{"hooks": {...}}` wrapper; matchers are exact-or-regex against **tool name only**.
- Hooks support an **exec form**: `{"type": "command", "command": "python3", "args": [...]}` — spawned directly, **no shell at all**.
- `${CLAUDE_PLUGIN_ROOT}` is substituted by **Claude Code itself** (both `command` and each `args` element) before execution — shell-independent.
- PreToolUse: exit 2 = block, stderr fed to Claude. Exit 0 + stdout JSON `hookSpecificOutput.permissionDecision` is the newer alternative. Other exits = non-blocking.
- PostToolUse: exit 0 + stdout JSON `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "..."}}` adds context for Claude.
- Skill invocation name for `skills/<dir>/SKILL.md` = directory basename; frontmatter `name` controls it when set. Commands read `/<plugin-name>:<skill-name>`.
- `plugin.json` `version` **pins the released version — users only receive updates when it bumps**. If a marketplace entry also sets `version`, **plugin.json wins** (the marketplace copy is dead weight).
- `claude plugin validate <path>` validates plugin.json, skill frontmatter, and hooks.json; `--strict` escalates warnings. Validating the repo root triggers **marketplace mode** because `.claude-plugin/marketplace.json` exists — always validate `.claude-plugin/plugin.json` explicitly.

---

## Summary

v1.1.0 delivers ROADMAP's "Runs everywhere" trust floor: the engine drops every shell-ism (native hashing, `shutil.which`/`sys.executable`-based toolchain detection, Python-side output truncation), the hooks move to shell-free exec-form entries with a dual-interpreter pair so the PR gate **fails closed** on macOS, Windows (Git Bash or PowerShell), and python3-only Linux, and the recording CLI replaces quoted-JSON `--data` with discrete flags that survive any shell and any issue title. The command surface renames to `/forgeproof:run`, `/forgeproof:push`, `/forgeproof:verify`, `/forgeproof:reset` with no aliases, and manifests lose their redundant version fields. Bundle format is untouched (`RPACK_VERSION` stays `1.0.0`); a checked-in v1.0.1 fixture created *before* any code change proves every v1.0.x `.rpack` still verifies.

---

## Resolved questions (decided with user, 2026-07-03)

| Question | Decision |
|---|---|
| `FORGEPROOF_REVIEW.md` is lost — how to satisfy Step 2.7? | **Reconstruct triage from evidence**; plan states this plainly. |
| PostToolUse hook: keep or remove? | **Keep, scoped**: new `lint-hook` subcommand lints only the edited file, exits silently without an active chain. Honest cost documented: 1-2 Python spawns (~50-100 ms) per Edit/Write in any session while the plugin is enabled. |
| `marketplace.json` version fields | Constraint "no other version fields anywhere" → remove **both** `plugins[0].version` and `metadata.version`. |
| Gate blocking mechanism | Keep **exit-2 + stderr** semantics (proven, works on every CLI version) rather than migrating to `permissionDecision` JSON. Exec form removes the shell chain that corrupted exit codes; exit 2 from a directly-spawned process is delivered intact. |

**External review (2026-07-03) — disposition.** A second-model review was incorporated selectively. *Accepted:* shell-adaptive skill instructions (Phase 3.1), cmd.exe engine-CLI testing + precise claim scoping (Phase 0.5, Test plan), mandatory plugin-loaded hook smoke with a pre-designed fallback (Phase 2), network-free JS toolchain detection (Phase 1.3), venv-first Python detection + argv output (Phase 1.3), finalize-time artifact recheck + honest completeness limitation (Phase 1.7, 5.2), skill-contract test robustness (Phase 1.8), untracked-ROADMAP fix (Phase 0.1). *Rejected:* keeping `--data` for a transition release (the CLI is internal to the skills, the ROADMAP commits to replacement, and the argparse error names the new flags); requiring Git Bash for skills (shell-adaptive instructions are strictly more robust than a hard dependency).

---

## Phases

Dependency order: fixture before any engine change (Phase 0) → engine before hooks and skills that reference new flags (1 → 2, 3) → renames last because they touch everything (4) → manifests/docs/version/release (5).

### Phase 0 — Baseline, compatibility fixture, CI scaffold

Goal: freeze the v1.0.1 behavior as a verifiable artifact and stand up the platform matrix **before** anything changes.

Tasks:
1. **Baseline hygiene:** `git status` — `ROADMAP.md` is currently **untracked** (verified 2026-07-03) despite being this release's normative scope document. On `main`, commit it first (`docs: add roadmap`), resolve any other stray untracked files (there should be none), then `git checkout -b release/v1.1.0`.
2. Housekeeping: the root `lib/` and `tests/` directories are empty leftovers from the pre-plugin layout (git does not track them). Verify empty (`find lib tests -type f` → nothing), then remove. Add `.pytest_cache/` root turd to `.gitignore` if not covered (it is — verify).
3. **Create the v1.0.x compatibility fixture using the CURRENT (unmodified) engine.** In a temp directory containing a small dummy artifact file:
   - `python skills/forgeproof/scripts/forgeproof.py init --issue 999 --force --data '{"title": "fixture", "requirements": ["REQ-1: fixture requirement"]}'`
   - one `record --action file-edit` (with the dummy file's sha256), one `record --action decision`, one `record --action test-result` (use the current `--data` JSON forms — this is the point)
   - `finalize --issue 999 --commit 0000000000000000000000000000000000000000`
   - Copy the resulting `.forgeproof/chain-999.json`, `.forgeproof/issue-999.rpack`, and the dummy artifact into `skills/forgeproof/scripts/fixtures/v101/` (this path renames along with the skill in Phase 4, keeping the fixture inside the plugin's test tree).
4. Add `TestV101Compat` to `skills/forgeproof/scripts/test_forgeproof.py`: copies the fixture tree into `tmp_path` (artifact at recorded relative path, chain under `.forgeproof/`), chdirs there, runs `cmd_verify` on the fixture `.rpack`, asserts `verified: true`, zero errors. Also a tamper case: flip one byte in the fixture copy's artifact → assert verification fails. This test is the **forever contract** (ROADMAP Principle 1) and must never be weakened.
5. Add `.github/workflows/ci.yml`:
   - `test` job matrix: `ubuntu-latest`, `macos-latest`, `windows-latest` → `python -m pytest skills/forgeproof/scripts/test_forgeproof.py -v` (adjust path after Phase 4 — the workflow references the path via a single env var to make Phase 4's edit one line).
   - `test-python3-only` job: `runs-on: ubuntu-latest`, `container: debian:stable-slim`, install `python3 openssh-client git` via apt **without** creating a `python` symlink → run pytest. This simulates the minimal-Linux case that broke the gate.
   - `windows-gitbash` job step: run pytest from `shell: bash` on windows-latest (Git Bash path).
   - `windows-cmd` job step: run pytest from `shell: cmd` on windows-latest — exercises the engine CLI (argparse flags, subprocess spawning, path handling) under cmd.exe-spawned Python, which is what the ROADMAP's "Windows cmd.exe" criterion realistically means (no ForgeProof *hook or skill* surface executes under cmd.exe; see Test plan).
   - `validate` job: `npm install -g @anthropic-ai/claude-code && claude plugin validate .claude-plugin/plugin.json --strict` (never `validate .` — marketplace mode landmine).
6. Run locally: full pytest (expect 44 existing + new fixture tests passing).

Verification: `python -m pytest skills/forgeproof/scripts/test_forgeproof.py -q` → all pass; fixture files committed; `git log --oneline -1` on the new branch.

Commit: `test: freeze v1.0.1 compat fixture, add CI platform matrix`

### Phase 1 — Engine: cross-platform core (`skills/forgeproof/scripts/forgeproof.py` + tests)

Goal: no shell strings, no interpreter-name assumptions, no POSIX tools anywhere inside the engine. Bundle/chain byte-shapes unchanged.

Tasks:
1. **Native hashing into `cmd_record`.** New flag `--path` behavior for `file-edit`: engine computes `sha256_file(Path(args.path))` itself (die with actionable message if the file doesn't exist). No `--sha256` override — the engine hashes what is on disk, which is the trust-relevant value.
2. **Discrete flags replace `--data` on `init` and `record`** (constraint: cmd-safe, quote-safe). `--data` is **removed**; passing it produces an argparse error whose message names the replacement flags. Per-action surface (each builds the exact same `data` dict shape v1.0.x wrote — chain and bundle formats are untouched):
   - `init --issue N [--force] --title TEXT [--requirement "REQ-1: text"]...` (repeatable `--requirement` → `requirements` list)
   - `record --action branch-create --branch NAME --base BASE --base-sha SHA`
   - `record --action file-edit --path FILE --operation {create,modify}` (sha256 computed)
   - `record --action decision --context TEXT --choice TEXT --rationale TEXT`
   - `record --action test-result --suite NAME --passed N --failed N [--covers "REQ-1=test_a,test_b"]... [--failed-test NAME]...` (repeatable `--covers` → `coverage` dict; repeatable `--failed-test` → `failed_tests` list)
   - `record --action lint-result --tool NAME --errors N --warnings N`
   - Validation: required flags per action; irrelevant flags for the given action → die with a message naming the expected set.
3. **`TOOLCHAIN_MAP` rework — no shell, no network.** Replace every `check`/`runtime_check` shell string with structured checks executed in Python:
   - python: **prefer the project's virtualenv** — check `.venv`/`venv` for `bin/python` (POSIX) or `Scripts/python.exe` (Windows) in the project root; fall back to `sys.executable`. The chosen interpreter (call it `detected_python`) is what test/lint commands are built from — `sys.executable` alone would point at whatever interpreter runs the *engine* (plugin-invoked), not the project's environment. Tool availability via `run([detected_python, "-m", "<tool>", "--version"]).returncode == 0`.
   - javascript: **filesystem-first, zero network** — a tool is available iff `node_modules/.bin/<tool>` (plus `.cmd`/`.ps1` variants on Windows) exists in the project root; fall back to `shutil.which(tool)`. Never probe via bare `npx <tool> --version` — npx may fetch packages from the registry, which violates ForgeProof's local-only posture. Emitted JS commands use `npx --no-install <tool>` (or the direct `node_modules/.bin` path).
   - go: `shutil.which("go")`, `shutil.which("golangci-lint")`.
   - `cmd_detect` output gains an `argv` array alongside each `command` string: the engine's internal execution (`cmd_lint`, `lint-hook`) uses `argv` (list-form `subprocess.run`, no shell); the `command` string exists for Claude to run via its shell tool and for display. Python command strings are built from `detected_python` with the path double-quoted.
4. **`cmd_lint` rework.** Kill `cmd += " --quiet 2>&1 | head -20"` (`forgeproof.py:918`): execute linters with `run(list_argv)` (no `shell=True`), merge stdout+stderr in Python, truncate to 20 lines in Python. Add `--file PATH` to lint a single file (ruff/flake8/eslint accept a file argument; golangci-lint stays project-scope — document). Replace the `run([sys.executable, __file__, "detect"])` self-subprocess with a direct internal call to the detection logic (refactor `cmd_detect` so both share a `detect_toolchain(project_root) -> dict` function).
5. **New `lint-hook` subcommand** (PostToolUse contract, mirrors `gate-pr`):
   - Parse hook event JSON from stdin; unparseable → exit 0.
   - No `.forgeproof/chain-*.json` in cwd → exit 0 silently (session scoping — this replaces the POSIX `if ls ...` guard).
   - Extract `tool_input.file_path`; missing/nonexistent/outside cwd → exit 0.
   - Single-file lint via the shared detection; findings → print `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "<≤20 lines of findings>"}}` to stdout; clean → no output. **Always exit 0.**
6. **`gate-pr` hardening (semantics unchanged, message updated).** Keep stdin-parse → allow (exit 0) / block (exit 2 + stderr). Update the block message to the post-rename command names (`/forgeproof:run`, `/forgeproof:push`) — accepted transient inconsistency until Phase 4 lands in the same release branch.
7. **Finalize-time artifact recheck (honest-claims hardening).** `cmd_finalize` re-hashes every recorded `file-edit` path before assembling the bundle; any disk-vs-recorded mismatch → die listing the stale paths and instructing to record the newer edit first (Claude then records and re-finalizes). This guarantees the signed bundle matches disk *at signing time*. Bundle format untouched — this is a pre-signing check, not a new field. Pair with a README "Known Limitations" line (Phase 5): recording **completeness** remains prompt-enforced — ForgeProof proves recorded edits are unaltered and complete-at-signing, not that Claude recorded every edit it made.
8. **Tests** (extend `test_forgeproof.py`, follow existing class-per-subcommand style):
   - `TestFinalizeRecheck`: finalize with an artifact modified after its `file-edit` record → dies naming the path; unmodified → succeeds (and fixture test still passes, since the fixture's artifact matches its recorded hash).
   - `TestCmdRecordFlags`: every action via new flags; dict shapes byte-identical to fixture-era blocks (assert against a v1.0.1-shaped literal); `--data` rejected with migration message; file-edit hash matches `sha256_file`; missing file dies.
   - `TestCmdInitFlags`: title/requirements assembly.
   - `TestCmdLintHook`: no-chain silent exit; chain + clean file → no output; chain + findings → additionalContext JSON; malformed stdin.
   - `TestDetectPortable`: monkeypatch `shutil.which` to simulate Windows (no `node`)/minimal Linux; assert no `shell=True` invocation in detection (monkeypatch `subprocess.run` to record calls and fail on `shell=True`).
   - **Skill-contract test**: parse every fenced command in all `skills/*/SKILL.md` that starts with an engine invocation, extract argv after the script path, and run it through `build_parser().parse_args()` (with `--help`-safe stubbing / catching `SystemExit(2)` as failure). Robustness requirements: join backslash line-continuations before parsing; substitute documented placeholders (`<filepath>` → a real temp file so the file-edit hash step works, `<sha>`/`$ISSUE`/`$(git rev-parse HEAD)` → dummy literals, `"$FP_PY" "$FP"` prefix stripped); skip non-engine fences (git/gh commands). This makes a stale SKILL.md example a loud CI failure — the executor-follows-text-verbatim risk, mechanized. (Written now against old skills, it fails → updated in Phase 3; mark `xfail` with reason until Phase 3 removes the marker.)
9. Update the three `references/*.md` only where they describe changed behavior (`toolchain-detection.md:11` runtime-check description). `chain-format.md` / `rpack-format.md` describe formats, which are unchanged — verify by grep, don't edit.

Verification: `python -m pytest skills/forgeproof/scripts/test_forgeproof.py -q` all green (fixture test proves old bundles still verify against the modified engine); `python skills/forgeproof/scripts/forgeproof.py record --help` shows new flags; grep engine for `shell=True` → only `shell_run()` remains and has no callers → delete `shell_run` too.

Commit: `feat: cross-platform engine — native hashing, flag-based recording, shell-free detection and lint`

### Phase 2 — Hooks: shell-free, dual-interpreter, fail-closed (`hooks/hooks.json`)

Goal: hooks that behave identically under sh, Git Bash, and PowerShell — by using no shell at all.

Replace `hooks/hooks.json` wholesale with (paths still pre-rename; Phase 4 updates them):

```json
{
  "description": "ForgeProof: PR gate (blocks gh pr create without a signed .rpack) and per-file lint during active runs.",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/skills/forgeproof/scripts/forgeproof.py", "gate-pr"], "timeout": 10 },
          { "type": "command", "command": "python",  "args": ["${CLAUDE_PLUGIN_ROOT}/skills/forgeproof/scripts/forgeproof.py", "gate-pr"], "timeout": 10 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/skills/forgeproof/scripts/forgeproof.py", "lint-hook"], "timeout": 30 },
          { "type": "command", "command": "python",  "args": ["${CLAUDE_PLUGIN_ROOT}/skills/forgeproof/scripts/forgeproof.py", "lint-hook"], "timeout": 30 }
        ]
      }
    ]
  }
}
```

Why this shape (record in CHANGELOG):
- **Exec form** = no shell → nothing for PowerShell 5.1 to fail to parse, no `2>/dev/null`, no `||` exit-code corruption. `${CLAUDE_PLUGIN_ROOT}` is substituted by Claude Code, not the shell.
- **Two entries per event**: whichever interpreter exists runs and delivers the real exit code (2 = block, delivered intact). A missing interpreter is a spawn failure = non-blocking noise, never a fake "allow". On dual-interpreter systems both run — `gate-pr` and `lint-hook` are read-only and idempotent; a duplicated block message is cosmetic. **Fail-closed property: the gate can no longer be silently converted to exit 127.**
- Drop the `$schema` line (it points at the *settings* schema, which is the wrong contract for plugin hooks and provokes editor lies; `claude plugin validate` is the real validator).

Tests (`TestHooksConfig` — this is the loud-failure regression the release demands, see Test plan):
1. Parse `hooks/hooks.json`; assert wrapper, events, matchers (`"Bash"`, `"Edit|Write"`), exec-form fields, and that every `args[0]` path exists after substituting `${CLAUDE_PLUGIN_ROOT}` with the repo root.
2. Simulated dispatch: for the event `{"tool_name": "Bash", "tool_input": {"command": "gh pr create --title x"}}`, apply the matcher exactly as documented (exact-or-regex against tool_name); for each handler whose interpreter exists on this machine (require ≥1 or fail), spawn it with the event on stdin in a bundle-less tmp cwd → assert exit 2 and stderr mentions the bundle; repeat with a `.rpack` present → assert exit 0.
3. Negative-matcher guard: assert the matcher matches `"Bash"` and does **not** match `"Edit"`; assert a deliberately wrong matcher (the v1.0.0 string `Bash(gh pr create)`) would fail check 1 — i.e., the test asserts equality with the intended matcher, so any silent drift fails CI loudly.

Verification: `claude plugin validate .claude-plugin/plugin.json` (0 errors); pytest green; **mandatory plugin-loaded smoke test** — the unit tests prove each handler's behavior in isolation, but only a live session proves Claude Code's hook manager composes two entries the way this design assumes. In a scratch repo with the plugin installed and loaded:
   1. `gh pr create` with no bundle → **blocked**, block message visible. The local Windows machine is naturally the "one spawn-fails (`python3` absent), one blocks (`python` exits 2)" composition case — confirm the spawn failure of the first entry does not mask or downgrade the second entry's block.
   2. Same command with a `.rpack` present → proceeds.
   3. On a dual-interpreter machine (CI devcontainer or WSL): confirm the duplicated block message is cosmetic only (one denial, no crash).
   4. Edit a file with an active chain → lint feedback appears as context; without a chain → silence.
   Record the outcomes in the PR description. If the hook manager does NOT tolerate the dual-entry pattern (e.g., first entry's spawn failure aborts the event), fall back to single shell-form entries — `python3 "$ROOT/…" gate-pr || python "$ROOT/…" gate-pr` is then acceptable **only because** blocking would move to `permissionDecision` JSON on stdout with exit 0 (order-independent, immune to the exit-code corruption that sank v1.0.1); this fallback is pre-designed here so the executor doesn't improvise.

Commit: `fix: fail-closed shell-free hooks — exec-form dual interpreter, per-file lint scope`

### Phase 3 — Skills: portable instructions (all four `skills/*/SKILL.md`)

Goal: every command a skill tells Claude to run works on macOS, minimal Linux, and Windows (Bash tool = Git Bash there), with no quoted-JSON and no `sha256sum`.

Tasks:
1. `skills/forgeproof/SKILL.md`:
   - After the `$FP` definition, add a **shell-adaptive** interpreter step to Phase 0 — prompt-level, not shell-syntax-level, because Claude's primary shell tool varies (Git Bash on most Windows setups, but PowerShell-primary sessions exist): *"Determine the Python interpreter once: run `python3 --version`; if that fails, run `python --version`. Set `$FP_PY` to whichever succeeded and use it for every engine invocation below. If your shell is PowerShell, invoke as `& $FP_PY $FP <subcommand> ...`; in bash, `"$FP_PY" "$FP" <subcommand> ...`."* Claude executes intent, adapting syntax to its actual shell — no single hardcoded shell-ism to break.
   - Rewrite `init`/`record` examples to the Phase 1 flag surface. Representative: `"$FP_PY" "$FP" record --issue $ISSUE --action file-edit --path <filepath> --operation modify` — and **delete line 122** (`sha256sum ... | cut ...`); replace the adjacent rule text with "the engine computes the file's SHA-256 from `--path`".
   - test-result example uses repeatable `--covers "REQ-1=test_name"` / `--failed-test`.
2. `skills/forgeproof-push/SKILL.md`, `skills/forgeproof-verify/SKILL.md`, `skills/forgeproof-reset/SKILL.md`: same `FP_PY` pattern for their engine invocations (4 sites, found by grep `python \$\{CLAUDE_PLUGIN_ROOT\}`).
3. Remove the Phase-1 `xfail` marker from the skill-contract test; it now passes against the updated SKILL.mds and permanently guards instruction/argparse drift.
4. `references/toolchain-detection.md`: update the runtime-check line to describe `sys.executable`-based detection.

Verification: `grep -rn -e "--data" -e "sha256sum" -e "python \$FP" -e "python \${CLAUDE_PLUGIN_ROOT}" skills/` → zero hits (the flag examples now start with `"$FP_PY"`); pytest (skill-contract test) green.

Commit: `docs: portable skill instructions — interpreter detection, flag-based recording`

### Phase 4 — Command-surface rename (touches everything; deliberately last)

Goal: `/forgeproof:run`, `/forgeproof:push`, `/forgeproof:verify`, `/forgeproof:reset`. No aliases; old names removed (ROADMAP policy).

Tasks:
1. `git mv skills/forgeproof skills/run && git mv skills/forgeproof-push skills/push && git mv skills/forgeproof-verify skills/verify && git mv skills/forgeproof-reset skills/reset` (engine, tests, fixtures, references move with `run/`).
2. Frontmatter `name:` → `run` / `push` / `verify` / `reset` in each SKILL.md (invocation name follows frontmatter; directory basename is the fallback — set both so neither drifts).
3. Path sweep — every reference to the old locations/names:
   - `hooks/hooks.json`: both `args[0]` paths → `${CLAUDE_PLUGIN_ROOT}/skills/run/scripts/forgeproof.py`.
   - Skill cross-references: `$FP` definition path in all four SKILL.mds → `skills/run/scripts/forgeproof.py`; every `/forgeproof-push` → `/forgeproof:push`, `/forgeproof-verify <path>` → `/forgeproof:verify <path>`, `/forgeproof $ISSUE` → `/forgeproof:run $ISSUE`, `/forgeproof-reset` → `/forgeproof:reset`.
   - Engine user-facing strings: `cmd_summary` footer (`forgeproof.py:861`) and `gate-pr` block message → new names (gate message already updated in Phase 1 — verify).
   - `TestHooksConfig` expected paths; any test referencing `skills/forgeproof`.
   - `.github/workflows/ci.yml` path env var → `skills/run/scripts/test_forgeproof.py`.
4. Draft the migration note (lands in README + CHANGELOG in Phase 5):
   | v1.0.x | v1.1.0 |
   |---|---|
   | `/forgeproof <issue>` (a.k.a. `/forgeproof:forgeproof`) | `/forgeproof:run <issue>` |
   | `/forgeproof-push` | `/forgeproof:push` |
   | `/forgeproof-verify <path>` | `/forgeproof:verify <path>` |
   | `/forgeproof-reset <issue\|--all>` | `/forgeproof:reset <issue\|--all>` |
   Old names are removed, not aliased (keeps the surface small — ROADMAP versioning policy). Existing installs pick this up on plugin update; no state migration needed (`.forgeproof/` layout unchanged).
5. `/reload-plugins` + manual smoke: `/forgeproof:verify` on the fixture bundle in a scratch checkout.

Verification: `grep -rn "forgeproof-push\|forgeproof-verify\|forgeproof-reset\|skills/forgeproof" --include="*.md" --include="*.json" --include="*.py" --include="*.yml" .` → only CHANGELOG history entries (which must not be rewritten); full pytest; `claude plugin validate .claude-plugin/plugin.json`.

Commit: `refactor!: rename command surface to /forgeproof:{run,push,verify,reset}`

### Phase 5 — Manifests, docs, version, release

Tasks:
1. `.claude-plugin/marketplace.json`: delete `plugins[0].version` **and** `metadata.version` (constraint: no version fields anywhere but plugin.json; plugin.json wins regardless, so these were dead weight that could only mislead).
2. `README.md`:
   - Usage/commands → new names + migration table ("Upgrading from 1.0.x").
   - `claude plugin validate .` → `claude plugin validate .claude-plugin/plugin.json` with a one-line warning about marketplace mode; pytest path → `skills/run/scripts/test_forgeproof.py`; test count updated to the real number.
   - Hooks section rewritten honestly: PreToolUse spawns the gate on every Bash call (fast, read-only, exits 0 unless `gh pr create` without a bundle); PostToolUse spawns on every Edit/Write and exits immediately unless an active chain exists; both are shell-free and fail closed; dual-interpreter entries may double-run on systems with both pythons (harmless).
   - Requirements: note Windows needs the OpenSSH client feature (ships with Windows 10+, sometimes disabled) for `ssh-keygen`.
   - Known Limitations: add the recording-completeness line from Phase 1.7 — v1.1.0's finalize recheck proves recorded artifacts match disk at signing time; that every edit *was* recorded remains prompt-enforced, not cryptographically enforced.
3. `CHANGELOG.md` 1.1.0 entry: Added (lint-hook, CI matrix, compat fixture, skill-contract test) / Changed (flags replace `--data` **with the migration mapping**, detect emits `sys.executable` commands, rename table) / Fixed (gate fail-open chain, PowerShell hook parse, `which node`/`head` Windows breakage, README validate landmine) / Removed (`--data`, `shell_run`, marketplace version fields).
4. `ROADMAP.md`: flip v1.1.0 `🔨 Now` → `✅ Shipped` as part of the release commit.
5. **Final content change:** `.claude-plugin/plugin.json` `"version": "1.1.0"`. (`RPACK_VERSION` in the engine stays `1.0.0` — that versions the bundle format, which this release must not touch.)
6. Gate check: `claude plugin validate .claude-plugin/plugin.json` and `--strict`; full pytest; CI green on the branch.
7. PR to `main`. **Landmine:** if the ForgeProof plugin is enabled in the releasing session, its own PreToolUse gate blocks `gh pr create` (this repo has no `.forgeproof/` bundle — working as designed). Disable it for the session (`claude plugin disable forgeproof`) or create the PR from the GitHub UI; note which was done in the PR body.
8. **Merging to `main` is the distribution event.** The community marketplace pin is advanced by `bump-plugin-shas.yml` in anthropics/claude-plugins-community — a **daily** (07:23 UTC), validate-gated sweep that bumps every entry to upstream **HEAD** (verified 2026-07: commit `1336b331`/PR #68 was its first full run; the v1.0.1 pin stall was Anthropic-side tooling since hardened, not a submission problem). Consequences the executor must respect:
   - The sweep tracks HEAD, not tags — so **never merge partial release work to `main`**; the single-PR-at-the-end strategy is load-bearing, because whatever HEAD is at 07:23 UTC ships.
   - The one way to get held back is HEAD failing `claude plugin validate` at sweep time — the CI validate job and step 6's pre-merge validation are what directly protect distribution, not formality.
   - The bumper resolves `.claude-plugin/plugin.json` first; users see v1.1.0 because the version field bumped in the merged HEAD.
9. After merge: tag `v1.1.0` on the merge commit, push the tag (for humans and history — the pin doesn't consume it).
10. **Post-release pin verification:** at T+1–2 days (allow two daily sweep runs), confirm the community entry advanced to the merge commit's SHA: `claude plugin marketplace update claude-community && claude plugin list --available --json`, or read the `forgeproof` entry in anthropics/claude-plugins-community `marketplace.json`. If it hasn't moved: first check whether *their* validate rejects our HEAD (reproduce with `claude plugin validate .claude-plugin/plugin.json --strict` on the merge commit), fix-forward if so; only escalate via the in-app submission form/ticket if HEAD validates clean and two consecutive sweeps still skipped it.

Verification: fresh install in a scratch project from the updated marketplace (or `claude plugin install` from the repo) → `/forgeproof:run` visible in `/plugin` UI, preflight passes, gate blocks bundle-less `gh pr create`.

Commit: `release: v1.1.0 — runs everywhere (manifest hygiene, docs, version bump)`

---

## Test plan (maps to ROADMAP v1.1.0 success criteria)

| Success criterion | Demonstrated by |
|---|---|
| run→push→verify passes on macOS / Ubuntu-no-`python` / Windows cmd+PowerShell | CI matrix below + engine design (no shell, no interpreter names). cmd.exe scope, stated precisely in release notes: no *hook or skill* surface executes under cmd.exe (hooks: Git Bash/PowerShell per docs; skills: Claude's shell tool) — but the engine CLI itself is tested under cmd.exe-spawned Python via the CI `shell: cmd` step, which is the surface a user could actually reach from cmd.exe. |
| `claude plugin validate` passes on current CLI | CI `validate` job (`.claude-plugin/plugin.json`, plus `--strict`) |
| Regression test proves the PR gate blocks on invalid state, loudly | `TestHooksConfig` simulated dispatch (Phase 2): asserts matcher shape *and* spawns the exact configured command against a block-scenario event, requiring exit 2. A never-fires misconfiguration (wrong matcher, wrong path, wrong form) fails the assertion — it cannot pass silently. |
| Every v1.0.x `.rpack` still verifies | `TestV101Compat` fixture (created from unmodified v1.0.1 code in Phase 0, committed) runs in every CI job on every platform |
| Zero new dependencies | Engine remains stdlib-only; tests remain stdlib+pytest; CI asserts `grep -c "^import\|^from" forgeproof.py` set unchanged modulo stdlib (manual review in PR) |

**Platform matrix:**

| Platform | Coverage | How |
|---|---|---|
| Windows 11 (Git Bash + PowerShell) | local hardware | full pytest, hook dispatch test, manual smoke of `/forgeproof:run` phases 0-1 |
| Windows (PowerShell-spawned, no bash assumptions in engine) | CI `windows-latest` default shell | pytest |
| Windows (Git Bash path) | CI `windows-latest`, `shell: bash` step | pytest |
| macOS | CI `macos-latest` | pytest incl. fixture + hook dispatch |
| Ubuntu (python + python3) | CI `ubuntu-latest` | pytest |
| Debian python3-only (no `python` symlink) | CI container `debian:stable-slim` | pytest — **this is the job that catches the gate fail-open class** |

**Manual E2E smoke (documented in PR, run once locally):** scratch Python repo + real GitHub issue → `/forgeproof:run` through finalize → `gh pr create` blocked before bundle / allowed after → `/forgeproof:verify` green → tamper one artifact → verify red.

---

## Risk register (top 5)

| # | Risk | Mitigation |
|---|---|---|
| 1 | **SKILL.md drift vs. argparse** — Claude executes skill text verbatim; one stale example breaks runs at runtime, invisibly to unit tests | Skill-contract test (Phase 1.7) parses every engine invocation in every SKILL.md through the real parser in CI; grep gates in Phases 3-4 |
| 2 | **Rename breaks users/marketplace links** — cached installs, muscle memory, external docs referencing `/forgeproof-verify` | Migration table in README+CHANGELOG; plugin update replaces the whole cached tree atomically (per-version cache dirs); no aliases is explicit ROADMAP policy — release notes lead with the mapping |
| 3 | **Hook manager behavior assumptions** — exec-form support on older CLIs; dual-entry composition (spawn-fail + block) unproven outside a live session | `claude plugin validate` in CI; dispatch test executes the exact configured commands; **mandatory** Phase 2 plugin-loaded smoke with enumerated cases; pre-designed fallback (shell-form + `permissionDecision` JSON, exit-code-independent) if the dual-entry pattern misbehaves |
| 4 | **Double execution on dual-interpreter systems** (both hook entries fire) — duplicate block messages, double lint spawn | Both subcommands are read-only and idempotent; lint-hook exits pre-lint without an active chain; cost measured and documented in README hooks section |
| 5 | **Community marketplace pin doesn't advance** (happened at v1.0.1 — root-caused to Anthropic-side sweep tooling, since replaced by a daily validate-gated workflow) | Keep HEAD always validate-clean (CI job + pre-merge gate — this is the sweep's only hold-back condition); single release PR so partial work never becomes HEAD at sweep time; Phase 5.10 dated verification with a diagnose-before-escalate path |

---

## Triage table (evidence-reconstructed; original FORGEPROOF_REVIEW.md lost)

| Finding (evidence) | v1.1.0 decision | Rationale (one sentence) |
|---|---|---|
| hooks.json missing `hooks` wrapper | Already fixed (v1.0.1) | Shipped; CHANGELOG:8 |
| `Bash(gh pr create)` permission-syntax matcher | Already fixed (v1.0.1) | Shipped; CHANGELOG:9; Phase 2 test now guards regression loudly |
| `sha256sum` dependency (SKILL.md:122) | **Include** — Phase 1.1/3.1 | Committed scope; breaks macOS/Windows |
| Bare `python` / `python3` assumptions (skills, hooks, TOOLCHAIN_MAP) | **Include** — Phases 1-3 | Committed scope; gate currently fails open on python3-only Linux |
| Quoted-JSON `--data` (cmd.exe + any quote-bearing title) | **Include** — Phase 1.2 | Committed scope; universal quoting fragility |
| PostToolUse full-project lint per edit | **Include** — Phase 1.5/2 (user: keep, scoped) | Committed scope |
| Skill naming (`/forgeproof:forgeproof`) | **Include** — Phase 4 | Committed scope |
| Redundant `marketplace.json` version | **Include** — Phase 5.1 (both version fields) | Committed scope + "no other version fields" constraint |
| Gate fail-open via `\|\|` fallback chain (found in this research) | **Include** — Phase 2 | Correctness of the release's core promise |
| PowerShell 5.1 cannot parse current hook command (found) | **Include** — Phase 2 (exec form) | Portability correctness |
| `which node`, `2>/dev/null`, `\| head` in engine (found) | **Include** — Phase 1.3/1.4 | Portability correctness |
| README `claude plugin validate .` marketplace-mode landmine (found) | **Include** — Phase 5.2 | Doc correctness, cheap |
| README hooks section overstates scoping ("neither fires during normal sessions") (found) | **Include** — Phase 5.2 | Honest-claims principle |
| `ssh-keygen` required for *verification* vs. ROADMAP "stdlib and nothing else" principle | **Defer** | Replacing signature verification touches the verification path — flagged as out of scope per constraints; candidate for v1.3.0 alongside attestation work |
| Non-constant-time crypto / PyNaCl suggestion (RPB expert review lineage) | **Defer** | Requires pip dependency (violates constraint) and touches signing; ephemeral per-bundle keys blunt the side-channel |
| Canonical JSON not RFC 8785/JCS | **Defer** | Bundle-format change, explicitly out of scope; revisit with v1.3.0 standards work |
| SBOM / SLSA / in-toto emission | **Defer** | New capability; ROADMAP reserves for v1.3.0 |
| Richer verify report output | **Defer** | ROADMAP reserves for v1.2.0 |
| Go single-file lint scoping | **Defer** | `golangci-lint` is package-oriented; project-scope lint for Go is acceptable and documented |
| `npx <tool> --version` probes can hit the npm registry (found via external review) | **Include** — Phase 1.3 | Violates local-only posture; filesystem-first detection + `npx --no-install` |
| Detected Python commands may target the plugin's interpreter, not the project venv (external review) | **Include** — Phase 1.3 | venv-first detection; correctness of recorded test results |
| Signed bundle can't prove every edit was recorded (external review) | **Include (partial)** — Phase 1.7 finalize recheck + honest README limitation | Full enforcement (e.g., hook-driven auto-recording) is a new capability — deferred |
| `ROADMAP.md` untracked in git (external review; verified) | **Include** — Phase 0.1 | Release's scope document must be in history before branching |

---

## Release checklist (Phase 5 condensed)

- [ ] `PLAN_v1.1.0.md` committed at repo root (first execution action)
- [ ] Phases 0-4 merged into `release/v1.1.0`, one commit each, CI green including debian-python3-only job
- [ ] CHANGELOG 1.1.0 entry with `--data` migration + rename table
- [ ] README updated (commands, validate form, honest hooks, OpenSSH-on-Windows note)
- [ ] ROADMAP v1.1.0 → ✅
- [ ] marketplace.json version fields removed; plugin.json → `1.1.0` (last change)
- [ ] `claude plugin validate .claude-plugin/plugin.json` and `--strict` → clean
- [ ] Full pytest on Windows local + CI matrix
- [ ] PR to main (plugin disabled for the session or web UI — own gate will fire); merge as the **single** release PR (daily sweep ships whatever HEAD is)
- [ ] Tag `v1.1.0` on merge commit; push tag
- [ ] T+1–2 days: community marketplace pin advanced to the merge SHA (daily validate-gated sweep, 07:23 UTC) — if not: reproduce validate on the merge commit first, fix-forward; escalate via form/ticket only if HEAD validates clean after two sweeps
