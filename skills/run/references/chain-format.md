# Hash Chain Format

Each ForgeProof chain is a JSON array of blocks stored at `.forgeproof/chain-<issue>.json`.

## Block Structure

```json
{
  "index": 0,
  "timestamp": "2026-04-06T14:30:00.000000+00:00",
  "action": "<action-type>",
  "data": {},
  "prev_hash": "<SHA-256 of previous block, or 64 zeros for genesis>",
  "hash": "<SHA-256 of this block, excluding hash and signature fields>",
  "signature": "<Ed25519 signature of the hash field via ssh-keygen>"
}
```

The `hash` is computed over the canonical JSON (sorted keys, no whitespace) of the block with the `hash` and `signature` fields excluded.

## Action Types

| Action | When recorded | Data fields |
|--------|--------------|-------------|
| `genesis` | Chain initialization | `issue` (int), `title` (string), `requirements` (array of "REQ-N: text") |
| `branch-create` | Feature branch created | `branch` (string), `base` (string), `base_sha` (string) |
| `file-edit` | File created or modified | `path` (string), `operation` ("create" or "modify"), `sha256` (string) |
| `decision` | Significant decision made | `context` (string), `choice` (string), `rationale` (string) |
| `test-result` | Test suite executed | `suite` (string), `passed` (int), `failed` (int), `coverage` (object mapping REQ-N to test names), `failed_tests` (array) |
| `lint-result` | Linter executed | `tool` (string), `errors` (int), `warnings` (int) |
| `finalize` | Chain finalized | `commit_sha` (string), `chain_length` (int) |

## Integrity Properties

- **Hash chain**: Each block's `prev_hash` must equal the preceding block's `hash`. The genesis block uses 64 zeros as `prev_hash`.
- **Tamper evidence**: Modifying any field in any block changes its hash, which breaks the chain linkage for all subsequent blocks.
- **Signatures**: Each block is signed with the ephemeral Ed25519 key generated at `init` time. Signatures are verified using `ssh-keygen -Y verify`.

## Known Limitations

### Post-rebase commit SHA mismatch

The `finalize` block records the `commit_sha` at bundle creation time. If the branch is rebased after finalization (e.g., to resolve conflicts before merging), the commit SHA changes but the bundle retains the original value.

**What still works:** Verification checks chain integrity, artifact hashes, root digest, and Ed25519 signatures. All of these remain valid after a rebase because they depend on file content and chain structure, not git commit identity.

**What breaks:** The `commit_sha` in the bundle no longer matches the branch HEAD. Anyone correlating the bundle to git history will see a mismatch.

**Workaround:** Re-run `/forgeproof:run` on the issue after rebasing to generate a fresh bundle with the new commit SHA. Use `/forgeproof:reset` to clean up the old state first.
