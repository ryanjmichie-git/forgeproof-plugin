---
name: verify
description: >
  Verify a ForgeProof provenance bundle (.rpack file). Use when the user asks
  to "verify a bundle", "check provenance", "validate an rpack", "verify
  forgeproof", or wants to confirm that AI-generated code has not been
  tampered with since signing. Supports verifying bundles from other
  repositories or PRs.
argument-hint: "[path-to-rpack]"
allowed-tools:
  - Bash
  - Read
  - Grep
---

# ForgeProof Verify: Bundle Integrity Check

Verify the cryptographic integrity of a ForgeProof `.rpack` provenance bundle.

The provenance engine script is at `${CLAUDE_PLUGIN_ROOT}/skills/run/scripts/forgeproof.py`
(referenced as `$FP` below). Determine the Python interpreter once: run
`python3 --version`; if that fails or reports Python is not found, use
`python`. Set `$FP_PY` to whichever succeeded. The examples use bash syntax;
if your shell is PowerShell, adapt the invocation (`& $FP_PY $FP ...`).

## Step 1 — Locate the bundle

If `$ARGUMENTS` contains a path, use it directly.

If `$ARGUMENTS` is empty, look for `.rpack` files:
```
ls .forgeproof/*.rpack 2>/dev/null
```

If multiple bundles exist, list them and ask the user which to verify.
If none exist, tell the user no bundles were found.

## Step 2 — Run verification

Default invocation:
```
"$FP_PY" "$FP" verify --rpack <path>
```

Add flags when the situation calls for them:
- `--strict` — use when verifying in the origin repo or in CI, where all
  evidence should be present: a missing chain or missing artifacts become
  failures instead of warnings.
- `--project-root <dir>` — use when the bundle sits outside the project
  layout (by default verify anchors artifact paths to the bundle's location,
  falling back to the current directory).
- `--format markdown` — use when the user wants the full human audit report;
  relay its output verbatim instead of parsing JSON.

Example strict CI invocation:
```
"$FP_PY" "$FP" verify --rpack <path> --strict
```
Example human audit report:
```
"$FP_PY" "$FP" verify --rpack <path> --format markdown
```

## Step 3 — Report results

Parse the JSON output (if you ran `--format markdown`, relay the report
verbatim and skip the JSON parsing). Lead the report with two keys, not one:
- `verified` — integrity of what is present: nothing that could be checked
  was tampered with
- `complete` — completeness of the evidence set: the chain was found and no
  artifacts were missing

A green-but-incomplete result (`verified: true`, `complete: false`) must be
reported as "integrity confirmed for what is present, but evidence is
missing" — never as a clean pass.

**If verified (no errors):**
Report that the bundle integrity is confirmed. Show:
- Evaluation status (pass/partial/fail)
- Number of artifacts checked
- Any warnings (missing artifacts are normal if verifying from a different checkout)

Note the deliberate distinction ForgeProof draws: a **modified** artifact or chain
turns verification RED (tamper detected), but a **missing** artifact or chain file is
a WARNING, not an error — a `.rpack` is a portable receipt meant to be verified in
checkouts that may not contain the original files, so absence is "cannot check here,"
not "tampered." If you are verifying in the origin repo and expect the files to be
present, treat `artifacts_missing > 0` or a "Chain file not found" warning as a signal
that the working tree is incomplete, and say so.

**If verification failed (errors present):**
Report each error clearly. Common failure scenarios:
- "Root digest mismatch" — the bundle contents have been modified since signing
- "Signature verification FAILED" — the signature does not match the public key
- "Chain hash mismatch" — the chain file was modified after the bundle was signed
- "Block N: prev_hash does not match" — a block in the chain was tampered with
- "Artifact tampered" — a source file was modified after the bundle was signed
- "[strict] ..." — evidence is missing under `--strict` mode (absent chain or
  artifacts), NOT tamper — the same condition is a warning without `--strict`

For each error, explain what it means in plain language and what the user
should do about it.

## Verify a PR's bundle

To verify the bundle attached to a pull request (if the PR belongs to another
repository, clone it first and run these steps inside the clone):

1. Check out the PR head: `gh pr checkout <number>` (or fetch it:
   `git fetch origin pull/<number>/head` and check out `FETCH_HEAD`)
2. Locate the bundle: `ls .forgeproof/*.rpack 2>/dev/null`
3. Verify it as in Step 2 and report as in Step 3
4. When done, return to the previous branch: `git checkout -`

Choose strictness by context: ad-hoc cross-repo verification stays LENIENT by
default — missing artifacts are warnings, because the bundle is a portable
receipt meant to travel without its source tree. Origin-repo or CI
verification, where the full evidence set should be present, should use
`--strict`.
