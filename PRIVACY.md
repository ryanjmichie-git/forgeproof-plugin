# ForgeProof Privacy Policy

**Last Updated:** 2026-07-03

---

## Summary

ForgeProof is a local-only Claude Code plugin. It does not collect telemetry, does not phone home, does not transmit data to any server it controls, and does not access files outside your project directory and the system temp directory. Every claim in this document is verifiable from the source code in this repository.

---

## Data Collection

**ForgeProof does not collect any user data.**

ForgeProof does not collect, aggregate, or store:
- User prompts or conversation content
- Bash commands or shell history
- File contents (beyond what is hashed for provenance)
- Session metadata, timestamps, or usage patterns
- Device identifiers, IP addresses, or user agents
- Claude Code account information

ForgeProof reads GitHub issue content (title, body, labels, comments) via the `gh` CLI to extract requirements. This data is processed locally and included in the `.rpack` provenance bundle stored in your project directory. ForgeProof itself makes no network requests — `gh` uses your pre-existing GitHub authentication.

---

## Network Activity

**ForgeProof makes zero outbound network requests.**

ForgeProof does not import or use any HTTP, socket, or networking libraries. The only external programs ForgeProof invokes are:

| Program | Purpose | Network activity |
|---------|---------|-----------------|
| `gh` (GitHub CLI) | Fetch issue data, create PRs, check auth status | Uses your existing GitHub auth. ForgeProof does not configure, modify, or intercept these requests. |
| `ssh-keygen` | Generate Ed25519 keypairs, sign and verify data | Fully local. No network activity. |
| Project toolchain (`python`, `pytest`, `ruff`, etc.) | Detect language, run tests, run linter | Fully local. No network activity. |

ForgeProof does not:
- Contact any analytics or telemetry endpoint
- Ping any server on startup, activation, or shutdown
- Resolve any DNS names
- Open any sockets

---

## Telemetry

**ForgeProof contains zero telemetry of any kind.**

There are no usage counters, no heartbeat pings, no crash reporters, no feature flags fetched from remote servers, no A/B testing, and no opt-in or opt-out telemetry settings — because there is no telemetry infrastructure to toggle.

This is verifiable: the provenance engine (`skills/run/scripts/forgeproof.py`) imports only Python standard library modules (`hashlib`, `json`, `subprocess`, `argparse`, `tempfile`, `pathlib`, `shutil`, `os`, `sys`). No third-party packages. No network-capable imports.

---

## Cryptographic Key Handling

**Ephemeral Ed25519 private keys are generated per-bundle and deleted immediately after signing.**

Key lifecycle:

1. **Generation** — When `/forgeproof:run` initializes a chain, `ssh-keygen` generates an Ed25519 keypair in the system temp directory (`/tmp` on Unix, `%TEMP%` on Windows) at `forgeproof_<issue>_ed25519`.
2. **Usage** — The private key signs each block in the hash chain and the final root digest of the `.rpack` bundle.
3. **Deletion** — Immediately after the bundle is finalized, the private key and its `.pub` companion are deleted from the temp directory. This is irreversible — the key cannot be recovered.
4. **Public key persistence** — The public key is embedded in the `.rpack` bundle for self-contained verification. It cannot be used to forge signatures without the deleted private key.

At no point are private keys:
- Written to the project directory
- Committed to git
- Transmitted over any network
- Stored in any persistent location

---

## File System Access

**ForgeProof reads and writes only within your project directory and the system temp directory.**

### Reads
- Project source files (to compute SHA-256 hashes for provenance)
- `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt`, `package.json`, `go.mod` (to detect project toolchain)
- `.gitignore` (to check if it exists)
- `.forgeproof/` directory contents (chain files, `.rpack` bundles)

### Writes
- `.forgeproof/chain-<issue>.json` — provenance hash chain
- `.forgeproof/issue-<issue>.rpack` — signed provenance bundle
- System temp directory — ephemeral Ed25519 keypairs (deleted after signing)
- System temp directory — transient files for `ssh-keygen` sign/verify operations (deleted immediately)

ForgeProof does not:
- Write to `${CLAUDE_PLUGIN_DATA}`
- Write to any directory outside the project root and system temp
- Modify source files (Claude Code's Edit/Write tools do that; ForgeProof only records what changed)
- Access other projects, home directory files, or system configuration

---

## Scope of Activation

**ForgeProof's hooks spawn a short-lived local Python process per matching tool call and act only during ForgeProof workflows.**

ForgeProof registers two hooks:

### PreToolUse Hook (PR gate)
- **Matcher:** `Bash|PowerShell` — the hook process spawns on every Bash or PowerShell tool call while the plugin is enabled. It is read-only and exits immediately (allow) for any command that is not `gh pr create`.
- **Behavior:** For `gh pr create`, checks whether a signed `.rpack` bundle exists in `.forgeproof/`. If not, blocks the PR creation with an informational message.
- **Data handling:** The hook reads the tool-call event (tool name and command string) from stdin to make that one local decision. It does not log, store, or transmit it.

### PostToolUse Hook (lint feedback)
- **Matcher:** `Edit|Write` — the hook process spawns after file edit operations.
- **Behavior:** Exits immediately as a no-op unless an active ForgeProof chain exists (`.forgeproof/chain-*.json`). During an active run it lints only the edited file and surfaces the findings to Claude. It never blocks an edit.
- **Scope:** No-op outside of active `/forgeproof:run` runs.

Neither hook:
- Reads or logs prompt content
- Transmits data anywhere
- Runs background processes (each invocation is a short-lived process that exits when its check completes)

---

## Third-Party Dependencies

**ForgeProof has zero third-party dependencies.**

The provenance engine is written in Python 3.11+ using only the standard library. There are no pip packages, no npm modules, no vendored libraries, and no dynamically loaded code.

External programs (`gh`, `ssh-keygen`) are invoked as subprocesses. ForgeProof does not bundle, modify, or patch these programs. They use your system installation and your existing configuration.

---

## Data Stored in .rpack Bundles

**The .rpack bundle is a local JSON file under your control. ForgeProof does not transmit it anywhere.**

An `.rpack` bundle contains:

| Field | Content | Sensitivity |
|-------|---------|-------------|
| Issue metadata | Issue number, title, URL | Low (public GitHub data) |
| Requirements | Extracted from issue body (REQ-1, REQ-2, ...) | Low (derived from public issue) |
| Artifacts | File paths and SHA-256 hashes of changed files | Low (paths, not content) |
| Decisions | Context, choice, and rationale for design decisions | Medium (contains reasoning about code) |
| Evaluation | Test pass/fail counts, lint error counts, requirement coverage | Low (aggregate metrics) |
| Chain hash | SHA-256 of the provenance chain file | Low (integrity check) |
| Public key | Ed25519 public key for signature verification | Low (public by definition) |
| Signature | Ed25519 signature over the root digest | Low (verification data) |

The bundle does **not** contain:
- Source code content (only file paths and hashes)
- User prompts or conversation history
- API keys, tokens, or credentials
- Personal information beyond what's in the GitHub issue

The bundle is written to `.forgeproof/issue-<N>.rpack` in your project directory. It is only transmitted if you explicitly push it to GitHub via `/forgeproof:push`. You can delete it at any time with `/forgeproof:reset`.

---

## Source Code Verification

Every claim in this document can be verified by reading the source code:

- **Provenance engine:** `skills/run/scripts/forgeproof.py`
- **Hook definitions:** `hooks/hooks.json`
- **Skill prompts:** `skills/*/SKILL.md`

The entire plugin is open source under the MIT license.

---

## Changes

| Date | Version | Change |
|------|---------|--------|
| 2026-07-03 | 1.1.0 | Updated hook scope to match v1.1.0 behavior (matcher `Bash\|PowerShell`, per-call spawn cost stated plainly, per-file lint); refreshed paths and command names after the skill rename |
| 2026-04-15 | 1.0.0 | Initial privacy policy |
