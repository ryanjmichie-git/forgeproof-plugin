---
name: forgeproof-push
description: >
  Push a ForgeProof branch and open a pull request with provenance metadata
  embedded in the PR description. Use after running /forgeproof to create
  a PR from the generated code. Triggers on "push forgeproof", "create PR
  from forgeproof", or "open pull request with provenance".
allowed-tools:
  - Bash
  - Read
---

# ForgeProof Push: Branch & PR Creation

Create a pull request from a completed ForgeProof run with provenance
metadata embedded in the PR description.

The provenance engine script is at `${CLAUDE_PLUGIN_ROOT}/skills/forgeproof/scripts/forgeproof.py`
(referenced as `$FP` below). Determine the Python interpreter once: run
`python3 --version`; if that fails or reports Python is not found, use
`python`. Set `$FP_PY` to whichever succeeded. The examples use bash syntax;
if your shell is PowerShell, adapt the invocation (`& $FP_PY $FP ...`).

## Step 1 — Identify the ForgeProof branch

Check the current branch:
```
git branch --show-current
```

If it matches `forgeproof/<N>`, extract the issue number. If not, look for
recent forgeproof branches:
```
git branch --list 'forgeproof/*' --sort=-committerdate
```

Pick the most recent one (or ask the user if multiple exist). Set `$ISSUE`
to the issue number.

## Step 2 — Verify bundle exists

Check that a finalized `.rpack` bundle exists:
```
ls .forgeproof/issue-$ISSUE.rpack
```

If it does not exist, tell the user to run `/forgeproof $ISSUE` first.

## Step 3 — Push branch

First check if the remote branch already exists (from a previous run):
```
git ls-remote --heads origin forgeproof/$ISSUE
```

If the remote branch exists, force-push with lease to update it:
```
git push --force-with-lease -u origin forgeproof/$ISSUE
```

Otherwise, push normally:
```
git push -u origin forgeproof/$ISSUE
```

## Step 4 — Generate PR body

Run the summary command to get the provenance table:
```
"$FP_PY" "$FP" summary --issue $ISSUE
```

Build the PR body with this structure:

```
Closes #$ISSUE

<summary output from above>

---
*This PR was generated with [ForgeProof](https://github.com/...). The `.rpack`
bundle in `.forgeproof/` is a cryptographically signed provenance record.
Run `/forgeproof-verify .forgeproof/issue-$ISSUE.rpack` to verify integrity.*
```

## Step 5 — Create PR

First check if a PR already exists for this branch (from a previous run):
```
gh pr list --head forgeproof/$ISSUE --state open --json number,url
```

If a PR already exists, update it instead of creating a new one:
```
gh pr edit <number> \
  --title "forgeproof(#$ISSUE): <concise description from commit>" \
  --body "<PR body from above>"
```

If no PR exists, create one:
```
gh pr create \
  --title "forgeproof(#$ISSUE): <concise description from commit>" \
  --body "<PR body from above>" \
  --base main \
  --head forgeproof/$ISSUE
```

Report the PR URL to the user.
