---
name: forgeproof-reset
description: >
  Clean up ForgeProof local state for an issue or all issues. Deletes
  provenance chains, bundles, ephemeral keys, and optionally branches.
  Use when you need to re-run ForgeProof on an issue or clean up after
  testing. Triggers on "reset forgeproof", "clean up forgeproof", or
  "forgeproof reset".
argument-hint: "[issue-number|--all]"
allowed-tools:
  - Bash
  - Read
---

# ForgeProof Reset: Clean Up Local State

Remove ForgeProof artifacts and optionally delete branches for a fresh run.

The provenance engine script is at `${CLAUDE_PLUGIN_ROOT}/skills/forgeproof/scripts/forgeproof.py`
(referenced as `$FP` below). Determine the Python interpreter once: run
`python3 --version`; if that fails or reports Python is not found, use
`python`. Set `$FP_PY` to whichever succeeded. The examples use bash syntax;
if your shell is PowerShell, adapt the invocation (`& $FP_PY $FP ...`).

## Step 1 — Determine scope

If `$ARGUMENTS` contains an issue number, set `$ISSUE` to that number.

If `$ARGUMENTS` is `--all` or empty, clean up all ForgeProof state.

## Step 2 — Clean up provenance state

For a single issue:
```
"$FP_PY" "$FP" reset --issue $ISSUE
```

For all issues:
```
"$FP_PY" "$FP" reset --all
```

## Step 3 — Clean up git branches

Check if currently on a forgeproof branch:
```
git branch --show-current
```
If on a `forgeproof/*` branch, switch to main first:
```
git checkout main
```

For a single issue, check for the local branch:
```
git branch --list forgeproof/$ISSUE
```
If it exists, delete it:
```
git branch -D forgeproof/$ISSUE
```

For all issues, list all forgeproof branches:
```
git branch --list 'forgeproof/*'
```
Delete each one.

## Step 4 — Optionally clean up remote branches

Ask the user if they also want to delete remote branches.

If yes, for a single issue:
```
git push origin --delete forgeproof/$ISSUE
```

For all issues, delete each remote forgeproof branch.

## Step 5 — Report

Report what was cleaned up: files deleted, branches removed. Confirm the
workspace is ready for a fresh `/forgeproof` run.
