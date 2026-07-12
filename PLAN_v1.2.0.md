# PLAN_v1.2.0.md — ForgeProof "Verification by default"

> **Executor instructions:** Self-contained — assumes this document, the plugin repo at `c:\Dev\FORGEPROOF_SKILL2` (github.com/ryanjmichie-git/forgeproof-plugin), and nothing else. Two repos are involved: the plugin repo (work on branch `release/v1.2.0`, one commit per phase, single release PR at the end) and a NEW companion repo `ryanjmichie-git/forgeproof-verify` (created in Phase 3, one squashed PR). Commit this document to the plugin repo root as `PLAN_v1.2.0.md` in Phase 0. Follow superpowers:executing-plans / subagent-driven-development.

**Status:** Approved 2026-07-12 (three design questions resolved with Ryan — see Resolved questions)
**Target versions:** plugin `1.2.0` (bumped exactly once, final content change); action `v1.0.0` + floating `v1` tag (independent semver line)
**Baseline:** plugin `main` @ `c204ea9` (v1.1.0 merge, tagged, CI fully green)

---

## Resolved questions (decided with Ryan, 2026-07-12)

| Question | Decision |
|---|---|
| Action's verifier source | **Vendored copy** of `forgeproof.py` in the action repo + a CI **sync-check job** that fails when the vendored file's SHA-256 differs from the file at the pinned plugin tag. Self-contained single audit surface; drift caught mechanically. |
| Backlog scope | **#8 + #9 (mandatory) + cheap guards**: #6 record input validation, #7 record-after-finalize refusal, and only the detect-crash fix from #5 (broken venv exe must not break detect's JSON contract). Defer #5's 0-byte-tool blessing and go-PATH parts. |
| Action behavior on bundle-less PRs | **Red by default** (`require-bundle: true`). Mixed human/AI repos use the recipe's head-branch filter (`forgeproof/*`); GitHub counts a skipped required check as satisfied, so human PRs still merge. |
| Testing depth (user requirement) | Four explicit layers — unit, functional, user (live Claude Code UAT), regression — see Test plan. **Claude Code is the most visible platform**: live plugin-loaded smoke is a release gate, not optional. |

## Context

v1.1.0 ("Runs everywhere") shipped 2026-07-07 (PR #3 → `c204ea9`, tagged). ROADMAP v1.2.0 is **"Verification by default"**: provenance nobody checks is theater — this release makes verification *happen* mechanically on every PR. Scope (ROADMAP.md:62-72): a published **`forgeproof-verify` GitHub Action** (stdlib verifier, no Claude Code in CI) that turns PRs red/green with an audit comment; a **required-check recipe**; a **README badge**; **richer verify output** (not just pass/fail). Success criteria: tampered bundle → red check; untouched → green; branch protection cannot merge the red case.

### Research findings that shape this plan (verified 2026-07-12 against the live code)

1. **Critical workflow hole — the signed bundle is likely never in the PR.** `skills/run/SKILL.md:187-202` commits `.forgeproof/` *before* running `finalize` (which creates the `.rpack` and appends the finalize block). No second commit is instructed, so the pushed branch contains a pre-finalize chain and **no bundle**; `push`'s check (`ls .forgeproof/issue-$ISSUE.rpack`, push SKILL.md:40-47) passes locally while the PR head lacks the bundle. The Action depends on the bundle being at PR head — Phase 2 fixes this with a **plain second commit** (not `--amend`: finalize records `commit_sha` of the work commit, `forgeproof.py:791-794`; amending would invalidate it, same class as the documented post-rebase mismatch in `chain-format.md:41-49`).
2. **`verify` already emits stable JSON with CI-ready exit codes** (`forgeproof.py:1093-1105`: `{verified, evaluation_status, errors, warnings, artifacts_checked, artifacts_missing, artifacts_tampered}`, exit 0/1; human progress on stderr via `info()`). Richer output is therefore **additive** — new JSON keys + a Markdown format — never a breaking change.
3. **Issue #9 already specifies the strict/complete contract** (decision recorded 2026-07-07): missing chain/artifacts are warnings today (`forgeproof.py:1051,1078`) — correct for portable receipts, over-reassuring in the origin repo/CI. v1.2.0 adds `--strict` + a `complete` boolean; the Action runs strict by default. Issue #8 (paths resolve against **cwd**, `chain_path` via `CHAIN_DIR=Path(".forgeproof")` at `forgeproof.py:40,229-231,1013`; artifacts at `:1059`) is coupled: CI checkouts are exactly the cwd-mismatch case.
4. **ROADMAP's "approvals" in the report:** chain blocks carry no actor/approval fields (schema at `forgeproof.py:251-276`) — the report surfaces what exists: timestamps, action sequence, `decision` blocks, signer key. No bundle-format change (hard constraint).
5. **README.md:176 says "83 automated tests"; the suite now has 109** — refresh in Phase 4.
6. **GitHub facts** (fetched 2026-07-12, docs.github.com): Marketplace needs `action.yml` at the root of a public repo (one listed action per repo); required-check name = the **job** name (keep it a stable literal, unique across workflows); skipped required checks count as satisfied; fork PRs get a **read-only** `GITHUB_TOKEN` (check red/green still works; PR comments 403) — safe pattern is `pull_request` trigger, never `pull_request_target` with PR checkout; `$GITHUB_STEP_SUMMARY` works regardless of token perms; composite actions reference bundled files via `github.action_path`; runners: ubuntu/macos have `python3`, windows has `python` (use `shell: bash` + a two-name resolver); gh CLI preinstalled on all runners; floating major tag (`v1`) is the documented convention.

## Hard constraints

1. **Bundle compatibility is forever** (Principle 1). `RPACK_VERSION` stays `1.0.0` (`forgeproof.py:41`). All verify changes are read-side and additive. `TestV101Compat` is never weakened; Phase 0 freezes a **second** fixture (v1.1.0-era) before any verify change. Both fixtures also run in the action repo's CI.
2. **Stdlib only** in the engine and the Action's verification path (vendored `forgeproof.py` + bash/python glue; no pip, no npm, no Claude Code in CI).
3. **Version discipline**: plugin.json → exactly `1.2.0`, only as the final plugin-repo content change. Action tags `v1.0.0` + `v1`.
4. **Hooks are OUT of scope** — `hooks/hooks.json` does not change. If any change becomes unavoidable: known landmines apply (exec-form args silently dropped on CLI 2.1.128; `validate` passes with inert hooks; `--strict` unimplemented) → mandatory scratch-marketplace live smoke.
5. **Validate invocation**: always `claude plugin validate .claude-plugin/plugin.json`, never `.` (marketplace mode).
6. **Fork-PR security**: the Action runs the verifier against untrusted PR contents under `pull_request` with a read-only token; never interpolate PR-controlled strings into shell (env-var indirection); never `pull_request_target` + PR checkout.
7. **Community-pin freeze**: the community marketplace pin is stalled at `d71376c` (starvation bug, escalated to Anthropic 2026-07-12). Plugin `main` stays exactly at `c204ea9` until the bump lands or this release ships — all work stays on `release/v1.2.0`. **Pushing `release/v1.2.0` to origin is fine and required** (Phase 3's sync-check fetches an engine SHA by raw URL — only `main` is frozen). If still stalled at release time, merging v1.2.0 makes it the first bump users receive (1.0.x → 1.2.0) — acceptable; note in release PR.

## Summary

v1.2.0 makes verification the default: `verify` gains bundle-anchored path resolution (`--project-root` override), strict/complete semantics (`--strict`, new `complete` output key), a structured `checks` array, and a verification-grade Markdown audit report (`--format markdown`) — all additive on top of the existing JSON/exit-code contract. The run/push skills are fixed so the signed `.rpack` actually lands at PR head (post-finalize commit + committed-at-head push guard). A new companion repo ships `forgeproof-verify`, a stdlib-only composite GitHub Action (vendored verifier + CI sync-check) that turns PRs red/green, writes the audit report to the job summary (fork-safe), and comments when the token permits; the plugin repo dogfoods it on its own PRs, and docs deliver the branch-protection recipe and badges. Record-side guards (#6, #7, #5-partial) keep the newly-public audit surface truthful.

---

## Phases

Dependency order: fixtures before verify changes (0) → engine before skills that document new flags (1 → 2) → Action after the engine it vendors is final (3) → integration/docs after the Action exists (4) → release last (5).

### Phase 0 — Plan, branch, second compat fixture (plugin repo)

1. The working tree currently sits on `release/v1.1.0` @ `d7e33b5` (same tree as `main`, different commit). Explicitly: `git checkout main` (must be at `c204ea9`), then `git checkout -b release/v1.2.0`; commit this document as `PLAN_v1.2.0.md` (repo root).
2. **Freeze a v1.1.0-era fixture with the CURRENT, unmodified engine** (same discipline as v1.0.1's): in a temp checkout, run the real lifecycle via the engine CLI — `init --issue 998 --force --title "v110 fixture" --requirement "REQ-1: fixture requirement"`, then `record --issue 998 --action file-edit --path src/example2.py --operation create`, `record --issue 998 --action decision --context c --choice x --rationale r`, `record --issue 998 --action test-result --suite fixture --passed 1 --failed 0 --covers "REQ-1=test_fixture"` (per-action required flags per `RECORD_FLAG_SPEC`, forgeproof.py:619-625), then `finalize --issue 998 --commit <sha>` — and copy `chain-998.json`, `issue-998.rpack`, and the artifact into `skills/run/scripts/fixtures/v110/`. Uses issue 998 (999 belongs to v101). LF-only per `.gitattributes` (byte-exactness matters — `TestV101Compat` asserts no CR at `test_forgeproof.py:1648-1667`; mirror that).
3. `TestV110Compat` in `skills/run/scripts/test_forgeproof.py`: mirror `TestV101Compat` (:1607-1725) — `_deploy`-style copy into `tmp_path`, green verify, 3 tamper cases (artifact byte-flip, chain edit, signature armor mutation). Reuse its `_require_sshkeygen` CI-escalation pattern (:1614-1621).
4. No CI changes needed (`FP_TESTS` env var already points at the file, `ci.yml:10-11`).

Verification: `python -m pytest skills/run/scripts/test_forgeproof.py -q` all green (full suite, ≥109 + new); fixture committed.
Commit: `test: freeze v1.1.0 compat fixture ahead of verify changes`

### Phase 1 — Engine: verify v2 + record guards (`skills/run/scripts/forgeproof.py`)

All changes read-side or record-input-side; chain/bundle byte formats untouched.

1. **Bundle-anchored path resolution (#8).** New helper `resolve_verify_anchor(rpack_path, args.project_root) -> Path`: explicit `--project-root` wins; else if `rpack_path.parent.name == ".forgeproof"` → anchor is `rpack_path.parent.parent`; else `rpack_path.parent`. In `cmd_verify` (:963-1105): chain file = `anchor/.forgeproof/chain-{N}.json`, **falling back to the cwd-relative path if not found at the anchor** (preserves today's behavior for a bundle copied alone to a scratch dir); artifacts resolve `anchor/path` with the same cwd fallback. The used anchor is reported (stderr info + new JSON field `anchor`). Current layouts (cwd == anchor) behave identically — all existing tests must pass unmodified.
2. **Strict/complete semantics (#9).** New flag `--strict`. New output keys (additive): `complete` (bool — chain file found AND `artifacts_missing == 0`; computed in both modes) and `strict` (echo). In strict mode, missing chain/missing artifacts are appended to `errors` (with a `[strict]` prefix) instead of `warnings` → `verified` false → exit 1. Version-mismatch and uncovered-requirements stay warnings in both modes (old bundles must be able to pass strict when fully present — Principle 1).
3. **Structured checks (additive JSON).** New `checks` array — one entry per existing check, `{name, status: "ok"|"fail"|"warn"|"skipped", detail}` for: `format`, `root_digest`, `signature`, `chain_hash`, `chain_linkage`, `artifacts`, `coverage`. New `bundle` object: `{issue, title, root_digest, public_key, chain_length, first_timestamp, last_timestamp, commit_sha, evaluation_status}` (all read from bundle/chain — timestamps from chain blocks when the chain is present, else null). **Existing keys and their values are byte-for-byte unchanged** — a dedicated test asserts the old contract (see 6).
4. **Markdown audit report.** `--format {json,markdown}` (default `json`). Markdown renders from the same result data (single code path, no drift): verdict headline (✅ VERIFIED / ⚠️ VERIFIED (incomplete — evidence missing) / ❌ TAMPER DETECTED), checks table, provenance timeline (per-block `action` + timestamp when chain present), artifact digest table, decisions, evaluation **labeled as recorded claims sealed in the bundle** (honest-claims principle — verification proves the claims are unaltered, not that they are true), strict/complete footer. Exit codes identical to JSON mode. `cmd_summary` (claims-only view, :1113-1182) is unchanged.
5. **Record guards.**
   - **#6**: in `_record_data_from_flags` (:639) — reject negative `--passed/--failed/--errors/--warnings`; `--covers` requires a non-empty requirement id and a non-empty test list (`'REQ-2='` and `'=name'` die with actionable messages; document that ids must not contain `=`).
   - **#7**: `cmd_record` dies when the loaded chain's last block has `action == "finalize"`: `chain already finalized; run init --force to start over`.
   - **#5-partial**: wrap the venv interpreter probe in `detect_toolchain` (:480) so a broken/0-byte venv exe degrades to `runtime_available: false` instead of an unhandled OSError — preserves the "detect always emits valid JSON" invariant. (Rest of #5 deferred — see Triage.)
6. **Unit tests** (conventions per `test_forgeproof.py` — `TestCmd<Subcommand>` classes, `tmp_chain_dir`/`monkeypatch.chdir`, capability-skip + CI-escalate, `_no_traceback` for subprocess robustness):
   - `TestVerifyAnchoring`: rpack verified from an unrelated cwd finds chain+artifacts via the anchor (the #8 repro from the issue body); `--project-root` override; cwd fallback still works for a lone copied bundle; `anchor` reported.
   - `TestVerifyStrict`: missing artifact → lenient green+warning+`complete:false`, strict red+exit 1; missing chain likewise; fully-present bundle passes strict.
   - `TestVerifyContract`: old JSON keys/values identical to pre-change snapshots for green and tampered cases (guards the Action + skill parsers).
   - `TestVerifyMarkdown`: verdict lines for green/tampered/incomplete; claims labeled as claims; exit codes match JSON mode.
   - `TestRecordGuards`: the four #6 repros verbatim from the issue body; #7 record-after-finalize dies, chain file unchanged after refusal.
   - `TestDetectBrokenVenv`: 0-byte `.venv/Scripts/python.exe` (and POSIX twin) → valid JSON, `runtime_available: false`.
   - Extend `TestV101Compat` + `TestV110Compat`: fixtures pass `--strict` when fully deployed; strict fails when an artifact is removed; lenient behavior unchanged. (Additive test methods — existing assertions untouched.)
7. **Stress harness**: extend `stress/run_stress.py` `lifecycle()` (:122-296) — after the green verify, run `verify --strict` (expect green) and `verify --format markdown` (expect verdict line, UTF-8-clean); extend the 4-way `tamper_case` matrix (:217-233) to assert strict mode also goes red. Add a strict-incomplete case (delete one artifact → lenient green / strict red → restore).

Verification: full pytest green; `python skills/run/scripts/forgeproof.py verify --help` shows new flags; `python stress/run_stress.py` green locally; grep confirms `RPACK_VERSION = "1.0.0"` untouched.
Commit: `feat: verify v2 — bundle-anchored paths, strict/complete semantics, structured audit report; record guards`
**Then push the branch**: `git push -u origin release/v1.2.0` — Phase 3's sync-check fetches the engine file at this commit's SHA by raw URL; an unpushed SHA would 404.

### Phase 2 — Skills: seal the bundle into the branch + document verify v2

1. **`skills/run/SKILL.md` Phase 4 (:185-218)** — after the `finalize` step, add the sealing step: `git add .forgeproof/ && git commit -m "forgeproof(#$ISSUE): seal provenance bundle"` (plain second commit; explain in the skill text why not `--amend`). Update the phase-4 report text to mention the two-commit shape.
2. **`skills/push/SKILL.md` Step 2 (:40-47)** — replace the working-tree `ls` check with a committed-at-head check: `git cat-file -e HEAD:.forgeproof/issue-$ISSUE.rpack` (fallback instruction: if present on disk but not committed, run the sealing commit from run Phase 4, then push). **Step 4 template (:75-84)**: append one line: `*The `forgeproof-verify` check on this PR verifies the bundle automatically.*`
3. **`skills/verify/SKILL.md`** — document `--strict`, `--project-root`, `--format markdown`, and the `complete` key; add a "Verify a PR's bundle" flow (`gh pr checkout <N>` → locate `.forgeproof/*.rpack` → verify; ad-hoc/cross-repo stays lenient per #9, origin-repo/CI guidance points at strict); update the relay guidance to lead with the verdict + `complete`, and to show the Markdown report when the user wants detail.
4. **Skill-contract test** (`TestSkillContract`, `test_forgeproof.py:1554-1606`) parses every new documented invocation automatically (new flags exist since Phase 1 — ordering is load-bearing). Sanity floor `checked >= 5` (:1581) still holds; bump the floor if the count grows meaningfully.

Verification: full pytest green (skill-contract picks up new examples); `grep -n "cat-file" skills/push/SKILL.md`; manual read-through of the three skills for internal consistency.
Commit: `fix: seal bundle into the branch — post-finalize commit, committed-at-head push guard, verify-a-PR flow`

### Phase 3 — Companion repo: `forgeproof-verify` composite action

Create `ryanjmichie-git/forgeproof-verify` (public, MIT). One squashed PR; layout:

```
action.yml                      # root — Marketplace requirement
verifier/forgeproof.py          # vendored from plugin repo (Phase 1 final state)
verifier/UPSTREAM               # pinned plugin ref + expected sha256 (Phase 3: the pushed Phase-1 commit SHA on release/v1.2.0; Phase 5.3 re-pins to the v1.2.0 tag — file content is identical, so the recorded sha256 does not change)
scripts/run_verify.py           # stdlib glue: locate bundle(s), invoke verifier, emit outputs + markdown
fixtures/v101/  fixtures/v110/  # copies of both frozen fixtures (tamper variants generated by tests)
.github/workflows/ci.yml        # self-test matrix + sync-check
README.md  LICENSE
```

1. **`action.yml`**: `name: ForgeProof Verify` (Marketplace-unique), description, `branding: {icon: shield, color: green}`. Inputs (each with description + default): `bundle` (glob, default `.forgeproof/*.rpack`), `strict` (default `"true"`), `require-bundle` (default `"true"` — resolved question), `comment` (default `"true"`), `project-root` (default `"."`), `github-token` (default `${{ github.token }}`). Outputs: `verified`, `complete`, `bundle-path`, `report` (markdown). `runs.using: composite`; every `run` step `shell: bash` (present on all three runner OSes); interpreter resolver `PY=$(command -v python3 || command -v python)` (windows runners ship `python`, not `python3`); inputs reach scripts via `env:` indirection only (injection-safe pattern per docs); bundled files via `${{ github.action_path }}`.
2. **`scripts/run_verify.py`** (stdlib, unit-testable): glob bundles under `project-root`; 0 bundles → `require-bundle` true ? fail with actionable message (how to produce a bundle, link to plugin) : notice + success; for each bundle run `verifier/forgeproof.py verify --rpack <p> --project-root <root> [--strict] --format json`, then once more with `--format markdown` for the report (or render from JSON — pick ONE: render markdown by invoking the engine's `--format markdown`, single source of truth); write outputs to `$GITHUB_OUTPUT`, report to `$GITHUB_STEP_SUMMARY` (fork-safe — works with read-only token).
3. **Comment step**: only when `comment == 'true'`; `gh pr comment "$PR" --body-file report.md` with `GH_TOKEN` from the input; **failure tolerated** (fork PRs 403) → `::notice::comment skipped (read-only token — report is in the job summary)`; never fails the job. Check red/green comes solely from the verify step's exit code.
4. **CI (`ci.yml`)**, matrix `[ubuntu-latest, macos-latest, windows-latest]`:
   - `sync-check`: fetch `skills/run/scripts/forgeproof.py` at the ref in `verifier/UPSTREAM` (raw URL), `sha256sum` compare against the vendored copy AND the recorded hash — fail on any mismatch.
   - `self-test`: deploy fixture v110 into a scratch dir → `uses: ./` → assert `verified == true`, summary written. Same for v101 (backward compat **in the Action**).
   - `tamper-matrix`: 4 cases mirroring `stress/run_stress.py:217-280` (artifact byte-flip, chain block edit, signature armor mutation, bundle field edit) — each `uses: ./` with `continue-on-error: true`, then assert `steps.<id>.outcome == 'failure'`.
   - `strict-vs-lenient`: artifact deleted → `strict: "false"` passes with `complete == 'false'`; `strict: "true"` fails.
   - `no-bundle`: both `require-bundle` modes.
   - `unit`: `python scripts/test_run_verify.py` (stdlib asserts or pytest) for the glue.
5. **README**: usage snippet (SHA-pinned per docs guidance + `@v1` convenience), inputs/outputs table, fork behavior, CI badge (its own workflow), link to the branch-protection recipe in the plugin repo.

Verification: action-repo CI fully green on all three OSes; `sync-check` proven to fail on a deliberate 1-byte vendored edit (then reverted).
Commit(s): squashed PR `feat: forgeproof-verify v1.0.0 — composite action, vendored stdlib verifier, self-test matrix`. Tags happen in Phase 5.

### Phase 4 — Integration + docs (plugin repo)

1. **Dogfood workflow** `.github/workflows/verify-provenance.yml`: `on: pull_request`; single job with stable literal name `forgeproof-verify` (required-check name = job name; keep unique across workflows); `if: startsWith(github.head_ref, 'forgeproof/')` (skipped counts as satisfied → human PRs unaffected); `permissions: {contents: read, pull-requests: write}`; steps: checkout, `uses: ryanjmichie-git/forgeproof-verify@<full 40-char SHA>` with defaults (strict on).
2. **`docs/branch-protection.md`** (new — no docs/ exists yet): copy-paste consumer workflow; required-check setup via **rulesets** (public/Free repos; type the check name) and **classic branch protection** (check must have run once to be searchable); the skipped-check selectivity pattern; fork-PR behavior (red/green works, comments don't, job summary always); strict vs lenient guidance (#9 semantics); pin-by-SHA advice.
3. **README.md**: badge row under the H1 (plugin CI workflow badge + a static badge linking to the forgeproof-verify Marketplace listing); new `### Verify on every PR` under Usage (snippet + pointer to the recipe); update the verify usage section with `--strict`/`--format markdown`/`complete`; refresh the test count (:176, currently stale at 83 — count the real post-Phase-2 number from `pytest --collect-only -q`, don't guess); Troubleshooting entries for strict-mode failures ("evidence missing" vs "tampered").
4. **CHANGELOG.md**: draft the 1.2.0 entry (Added: strict/complete, checks/bundle JSON, markdown report, anchoring, action + recipe + dogfood workflow, v110 fixture; Fixed: bundle-not-in-PR workflow hole, #6/#7/#5-partial; note: no bundle-format change, both compat fixtures enforced).
5. ROADMAP flip (🧭 → ✅ for v1.2.0) is deferred to the Phase 5 release commit, mirroring v1.1.0.

Verification: `claude plugin validate .claude-plugin/plugin.json` clean; full pytest; open a **draft test PR** from a `forgeproof/998`-style branch **cut from `release/v1.2.0`** (it must carry `verify-provenance.yml` — a branch off frozen `main` wouldn't trigger the workflow) containing the v110 fixture → the dogfood check runs and goes green; tamper the fixture artifact on that branch → red; close the draft PR.
Commit: `feat: verify on every PR — dogfood workflow, branch-protection recipe, badges`

### Phase 5 — UAT + release (both repos)

1. **User-acceptance test (scripted; results recorded verbatim in the release PR).** Claude Code is the most visible platform — this is a release gate:
   1. Scratch-marketplace install from the working tree (recipe: scratch dir with `.claude-plugin/marketplace.json` relative-path source → `claude plugin marketplace add` → `claude plugin install forgeproof@forgeproof-smoke`; iterate = recopy + uninstall/reinstall — cache edits don't take).
   2. In a scratch GitHub repo with a real issue: `/forgeproof:run` end-to-end → **assert the seal commit exists and `git cat-file -e HEAD:.forgeproof/issue-N.rpack` passes** → `/forgeproof:push` → PR opens with the audit summary body → `forgeproof-verify` check goes **green**; comment posted (same-repo PR).
   3. Tamper a committed artifact on the branch, push → check goes **red**, report names the tampered file.
   4. Enable a ruleset on the scratch repo requiring `forgeproof-verify` → confirm the red PR **cannot be merged** (ROADMAP success criterion, mechanically).
   5. `/forgeproof:verify` in-session: verdict + report readability; a lenient cross-repo verify (bundle copied elsewhere) still green-with-warnings + `complete:false`.
   6. Gate/lint hooks still fire (headless smoke: `gh pr create` blocked without a bundle; lint context on a bad edit) — hooks didn't change, this guards packaging regressions.
   7. `claude plugin validate .claude-plugin/plugin.json` + `/doctor` clean on current CLI.
2. **Release, plugin repo**: ROADMAP flip; `plugin.json` → `1.2.0` (final content change); full CI matrix + stress green; single release PR to `main` (landmine: ForgeProof's own gate blocks `gh pr create` in a plugin-enabled session — disable the plugin for the session or use the web UI; note which in the PR body); merge; tag `v1.2.0` on the merge commit; push tag.
3. **Release, action repo**: pin `verifier/UPSTREAM` to the plugin `v1.2.0` tag (sync-check green); update the plugin dogfood workflow's SHA pin to the final action commit; tag `v1.0.0`; create `v1` tag at the same commit; publish the release to GitHub Marketplace (draft-release UI flow: check "Publish this Action", category e.g. "Continuous integration"; requires 2FA on the account).
4. **Post-release checks (dated, T+1–2 days)**: Marketplace listing live and installable; dogfood check appears on a fresh ForgeProof PR; community-marketplace pin — if Anthropic's fix landed, confirm the bump advanced to the v1.2.0 merge SHA; if still stalled at `d71376c`, v1.2.0 becomes the first bump users receive (acceptable; keep the escalation issue updated).

Commit: `release: v1.2.0 — verification by default`

---

## Test plan — four layers (maps to ROADMAP success criteria + Ryan's requirement)

| Layer | What proves it | Where it runs |
|---|---|---|
| **Unit** | `TestVerifyAnchoring/Strict/Contract/Markdown`, `TestRecordGuards`, `TestDetectBrokenVenv`, `TestV110Compat`, extended `TestV101Compat`; action-repo `test_run_verify.py` | plugin CI matrix (ubuntu/macos/windows + windows bash&cmd + debian python3-only) via `FP_TESTS`; action CI |
| **Functional** | Stress harness lifecycle + 4-way tamper matrix now asserting strict + markdown; action CI self-test/tamper/strict/no-bundle/fork-safe jobs on 3 OSes; draft-PR dogfood red/green | stress.yml; action ci.yml; plugin dogfood workflow |
| **User** | Phase 5 UAT script: live Claude Code session (scratch-marketplace install), real issue → run → push → green check → tamper → red → ruleset blocks merge; report readability; hooks still fire | manual, results recorded in release PR |
| **Regression** | Frozen v1.0.1 + v1.1.0 fixtures green on every platform in BOTH repos (forever contract); `TestVerifyContract` (old JSON keys byte-identical); the full pre-existing suite (109 tests at baseline, grows through Phases 0–2); hook regression tests (`TestHooksConfig` dispatch); skill-contract test (new flags auto-validated); `claude plugin validate` in CI | plugin CI + action CI, every push |

**Success-criteria mapping:** tampered → red = action tamper-matrix + UAT step 3; untouched → green = self-test + UAT step 2; protection blocks red = UAT step 4 (real ruleset); richer output = `TestVerifyMarkdown` + UAT step 5; no new deps = stdlib-only constraint checks (existing `TestDetectPortable` engine greps still pass).

## Risk register (top 5)

| # | Risk | Mitigation |
|---|---|---|
| 1 | **Verify changes regress the sacred verification path** (anchoring/strict touch `cmd_verify`) | Two frozen fixtures created BEFORE changes; `TestVerifyContract` byte-level old-key contract; cwd fallback preserves every current behavior; tamper matrices in three places (pytest, stress, action CI); `RPACK_VERSION` untouched |
| 2 | **The bundle still doesn't reach PR head in real runs** (skill text is prompt-enforced) | Push-skill committed-at-head guard (`git cat-file -e`) is the mechanical backstop; UAT asserts the seal commit; Action's red-by-default makes the failure loud, not silent |
| 3 | **Fork PRs behave differently than same-repo PRs** (read-only token) | Check verdict never depends on write perms; report always in job summary; comment step failure-tolerant; behavior documented in recipe; `pull_request_target` explicitly forbidden |
| 4 | **Vendored verifier drifts from the plugin engine** | `sync-check` CI job (hash vs pinned upstream ref) fails the action repo on any drift; `verifier/UPSTREAM` update is a scripted release step; deliberate-drift test in Phase 3 verification |
| 5 | **Claude Code platform regressions** (skill text drift, validate blind spots, CLI moves) | Skill-contract test auto-parses every documented invocation; hooks untouched; live scratch-marketplace UAT is a release gate; validate runs in CI on latest CLI |

## Triage table (issues #5–9 + findings from plan research)

| Item | Decision | Rationale |
|---|---|---|
| #8 verify resolves paths vs cwd | **Include** — Phase 1.1 | Mandatory: CI checkouts are the cwd-mismatch case; issue itself tags it v1.2 |
| #9 strict/complete semantics | **Include** — Phase 1.2/1.3 | The release's core contract; Action runs strict by default |
| #6 negative/malformed record counts | **Include** — Phase 1.5 | Cheap; these values now surface in a public audit comment |
| #7 record-after-finalize silent append | **Include** — Phase 1.5 | Cheap state-machine guard; tamper-evidence already held |
| #5 detect blesses broken tools | **Partial** — only the broken-venv OSError fix (Phase 1.5) | That part violates the "detect always emits JSON" invariant; 0-byte-tool blessing + go-PATH resolution are detection-quality, deferred (kept open, re-titled) |
| Bundle-not-committed workflow hole (found in this research) | **Include** — Phase 2.1/2.2 | Blocking prerequisite for the Action |
| README stale test count (83 vs 109) | **Include** — Phase 4.3 | Doc truth, one line |
| `workflow_run` comment relay for fork PRs | **Defer** (documented as advanced pattern in recipe only) | Complexity high; job summary already fork-safe |
| Richer signer identity display (who signed) | **Defer** | ROADMAP reserves identity for v1.4.0 (Sigstore) |
| `summary` enrichment | **Defer** | Verify's markdown report supersedes; summary stays the claims view |
| in-toto/SLSA/DSSE emission | **Defer** | ROADMAP v1.3.0 |

## Release checklist

- [ ] `PLAN_v1.2.0.md` committed (Phase 0, first action)
- [ ] Phases 0–4 on `release/v1.2.0`, one commit each; action repo PR squash-merged; all CI green (plugin matrix + stress + action matrix incl. sync-check)
- [ ] Both compat fixtures green everywhere; `TestVerifyContract` green
- [ ] UAT script executed in a live Claude Code session; results (incl. ruleset-blocks-merge screenshot/output) recorded in the release PR
- [ ] CHANGELOG 1.2.0 + README (badges, usage, recipe link, test count) + `docs/branch-protection.md`
- [ ] ROADMAP v1.2.0 → ✅; `plugin.json` → `1.2.0` (last change); `claude plugin validate .claude-plugin/plugin.json` clean
- [ ] Single release PR to `main` (own-gate landmine handled); merge; tag `v1.2.0`; push tag
- [ ] Action: `verifier/UPSTREAM` → plugin `v1.2.0`; tag `v1.0.0` + `v1`; Marketplace publish (2FA); dogfood workflow re-pinned to final action SHA
- [ ] T+1–2 days: Marketplace listing installable; dogfood check green on a fresh PR; community-marketplace pin status re-checked (stalled-sweep issue) — v1.2.0 as first bump is acceptable if still frozen
