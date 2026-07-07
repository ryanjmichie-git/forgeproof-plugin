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

```
"$FP_PY" "$FP" verify --rpack <path>
```

## Step 3 — Report results

Parse the JSON output. Present the results clearly to the user:

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

For each error, explain what it means in plain language and what the user
should do about it.
