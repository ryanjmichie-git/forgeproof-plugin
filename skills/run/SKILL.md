---
name: run
description: >
  Create provenance-tracked code from a GitHub issue with a cryptographically
  signed audit trail. Use when the user asks to "forgeproof an issue", "create
  a provenance bundle", "generate auditable code from an issue", or wants
  cryptographically signed proof of AI-generated work. Supports Python,
  TypeScript/JavaScript, and Go projects. Invoke with an issue number or
  without one to browse assigned issues.
argument-hint: "[issue-number]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
effort: high
---

# ForgeProof: Provenance-Tracked Code Generation

Execute a cryptographically signed development workflow. Every action is
recorded in a tamper-evident Ed25519 hash chain. The output is an `.rpack`
provenance bundle that proves what was done, why, and that nothing was
altered after signing.

The provenance engine script is at `${CLAUDE_PLUGIN_ROOT}/skills/run/scripts/forgeproof.py`.
Reference it as `$FP` in all commands below for brevity.

**Interpreter setup (do this once, before anything else):** determine the
Python interpreter: run `python3 --version`; if that fails or reports that
Python is not found, run `python --version`. Set `$FP_PY` to whichever
succeeded and use it for every engine invocation below. The examples below
use bash syntax (`"$FP_PY" "$FP" <subcommand> ...`); if your shell is
PowerShell, adapt the invocation (`& $FP_PY $FP <subcommand> ...`) and any
command substitutions accordingly — execute the intent, not the literal
bash syntax.

## Issue Selection

If `$ARGUMENTS` is empty (no issue number provided):

1. Run: `"$FP_PY" "$FP" issues --assignee @me`
2. Present the list to the user as a numbered list showing issue number, title, and labels
3. Ask the user to pick one
4. Set `$ISSUE` to the chosen issue number and continue

If `$ARGUMENTS` contains an issue number, set `$ISSUE` to that number and continue.

## Phase 0 — Preflight

Run the dependency check:
```
"$FP_PY" "$FP" preflight
```

If any check fails, stop and tell the user exactly what is missing and how to install it. Do not proceed until all checks pass.

Then detect the project toolchain:
```
"$FP_PY" "$FP" detect
```

Parse the JSON output. Store the detected `test_runner.command` and `linter.command` for use in Phase 3. If no language is detected, ask the user to specify their test command and lint command.

## Phase 1 — Parse & Plan

Fetch the issue:
```
gh issue view $ISSUE --json title,body,labels,assignees,comments
```

Read the issue body carefully. Extract structured requirements from it. Number them as REQ-1, REQ-2, etc. Each requirement should be a single, testable statement.

If the issue body is vague or lacks clear requirements, propose reasonable requirements based on the title and body, and ask the user to confirm or adjust.

Scan the repository structure using Glob and Grep to understand the codebase. Identify relevant files, patterns, and conventions.

Propose an implementation plan:
- Which files will be created or modified
- How each requirement maps to specific changes
- What tests will be written

**STOP and present the plan to the user. Wait for approval before proceeding.** The user may adjust the plan, add constraints, or reject parts of it. This is a conversation, not an automated pipeline.

## Phase 2 — Generate

Once the plan is approved, begin implementation.

### .gitignore check

Before writing any code, check for a `.gitignore`:
```
ls .gitignore
```
If missing, warn the user: "No `.gitignore` found. Generated files like `__pycache__/` and `*.pyc` may be committed. Consider creating one before proceeding."

### Initialize and branch

Initialize the provenance chain (repeat `--requirement` once per requirement):
```
"$FP_PY" "$FP" init --issue $ISSUE --force --title "<issue title>" --requirement "REQ-1: <text>" --requirement "REQ-2: <text>"
```
The `--force` flag safely handles re-runs by cleaning up any prior chain for
this issue. Pass the title and each requirement as ordinary quoted arguments —
there is no JSON to escape, so titles containing quotes are safe.

Check for an existing local branch and clean up if needed:
```
git branch --list forgeproof/$ISSUE
```
If it exists, delete it: `git branch -D forgeproof/$ISSUE`

Check for an existing remote branch (note this for the push step later):
```
git ls-remote --heads origin forgeproof/$ISSUE
```

Create the feature branch:
```
git checkout -b forgeproof/$ISSUE origin/main
```
Then record it:
```
"$FP_PY" "$FP" record --issue $ISSUE --action branch-create --branch forgeproof/$ISSUE --base main --base-sha <sha>
```

Implement the changes. After EVERY file you create or modify, record it:
```
"$FP_PY" "$FP" record --issue $ISSUE --action file-edit --path <filepath> --operation modify
```
Use `--operation create` for new files. The engine computes the file's
SHA-256 from `--path` itself — do not compute or pass a hash.

Log significant decisions as you work. When you choose an approach, skip an alternative, or make a non-obvious judgment call:
```
"$FP_PY" "$FP" record --issue $ISSUE --action decision --context "<what you were deciding>" --choice "<what you chose>" --rationale "<why>"
```

Write tests that cover each requirement. Record test file creation as file-edit blocks.

### Rules during generation
- NEVER skip recording a file edit or decision in the chain
- NEVER modify `.forgeproof/` files directly — only through the Python scripts
- Record each file AFTER writing it, not before — the engine hashes what is
  on disk at record time
- If you edit a file again after recording it, record it again (`--operation
  modify`); `finalize` refuses to sign if any recorded file no longer matches
  disk
- Create focused, minimal changes — do not refactor unrelated code

## Phase 3 — Evaluate

Run the test suite using the command detected in Phase 0:
```
<detected test command> 2>&1
```

Record the results (repeat `--covers` once per requirement; repeat
`--failed-test` once per failing test, if any):
```
"$FP_PY" "$FP" record --issue $ISSUE --action test-result --suite <name> --passed <N> --failed <N> --covers "REQ-1=<test_name>,<test_name>" --covers "REQ-2=<test_name>"
```

Run the linter using the command detected in Phase 0:
```
<detected lint command> 2>&1
```

Record lint results:
```
"$FP_PY" "$FP" record --issue $ISSUE --action lint-result --tool <name> --errors <N> --warnings <N>
```

If tests or linting fail, attempt ONE auto-fix cycle:
1. Analyze the failure
2. Fix the issue
3. Record the fix as a file-edit block (the chain preserves the failure-then-fix sequence)
4. Re-run tests and linter
5. Record the new results

If still failing after the retry, proceed to Phase 4 anyway. The bundle is always produced — the evaluation status will reflect the failures.

## Phase 4 — Package

Stage ONLY the files recorded in the provenance chain and the `.forgeproof/` directory.
Do NOT use `git add -A` or `git add .` — this prevents committing generated files like
`__pycache__/`, `*.pyc`, or other untracked artifacts.

```
git add <file1> <file2> ...
git add .forgeproof/
git commit -m "forgeproof(#$ISSUE): <concise description>"
```

The file list comes from the `file-edit` records you made during Phase 2. Stage each
file path that appeared in a `--action file-edit --path ...` call.

Finalize the chain and build the `.rpack` bundle:
```
"$FP_PY" "$FP" finalize --issue $ISSUE --commit $(git rev-parse HEAD)
```

This command:
- Re-checks every recorded file against disk — if any file changed after it
  was recorded, finalize refuses to sign and names the stale paths; record
  the current state of each named file (`--action file-edit`) and re-run
- Adds a finalize block to the chain
- Builds the `.rpack` bundle with all artifacts, requirements, decisions, and evaluation data
- Signs the bundle with the ephemeral Ed25519 key
- Deletes the private key

**Seal the bundle into the branch.** The commit above was made before
finalize, so it contains neither the `.rpack` bundle nor the finalize block.
Commit them as a second, plain commit:
```
git add .forgeproof/ && git commit -m "forgeproof(#$ISSUE): seal provenance bundle"
```
Confirm with `git cat-file -e HEAD:.forgeproof/issue-$ISSUE.rpack` (must exit 0).
Do NOT use `--amend`: finalize recorded `commit_sha` as the work commit's SHA,
and amending would replace that commit with a new SHA, orphaning the recorded
linkage — the same class of break as the documented post-rebase mismatch.

Report the result to the user. Include:
- The evaluation status (pass / partial / fail)
- The requirement coverage summary
- The path to the `.rpack` file, and that it is committed on the branch — the
  branch ends in two commits: the work commit the bundle references, then the
  seal commit that carries the bundle
- Next step: run `/forgeproof:push` to create a PR, or `/forgeproof:verify` to verify the bundle

## Reference Documentation

Detailed specifications are in `references/`:
- `chain-format.md` — Hash chain block format and action types
- `rpack-format.md` — `.rpack` bundle JSON schema
- `toolchain-detection.md` — Supported languages and detection logic
