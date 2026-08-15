# .rpack Bundle Format

The `.rpack` file is a JSON document containing the complete provenance record for a ForgeProof run. Version: **1.1.0**.

**Compatibility is forever.** Format versions are additive-only: every `.rpack` ever signed by any released ForgeProof (the 1.0.0 line included) verifies with every future verifier, and a verifier recognizes versions by *membership* in its known set — never by ordering, and no version implies any particular key is present. A 1.0.0 bundle without an `attestation` key is fully valid forever.

## Schema

```json
{
  "version": "1.1.0",
  "format": "forgeproof-rpack",
  "issue": {
    "number": 42,
    "title": "Add rate limiting",
    "url": "https://github.com/org/repo/issues/42"
  },
  "requirements": [
    {
      "id": "REQ-1",
      "text": "Add rate limiter middleware",
      "status": "covered",
      "tests": ["test_rate_limit_middleware"]
    }
  ],
  "artifacts": [
    {
      "path": "src/rate_limiter.py",
      "operation": "create",
      "sha256": "a1b2c3..."
    }
  ],
  "decisions": [
    {
      "context": "Rate limiting approach",
      "choice": "Token bucket algorithm",
      "rationale": "Simple and effective for API endpoints"
    }
  ],
  "evaluation": {
    "status": "pass",
    "tests_passed": 5,
    "tests_failed": 0,
    "lint_errors": 0,
    "requirement_coverage": "100%",
    "uncovered_requirements": [],
    "failed_tests": []
  },
  "chain_hash": "SHA-256 of the chain file's DECODED TEXT (see caveat below)",
  "public_key": "ssh-ed25519 AAAA...",
  "attestation": { "mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json", "...": "see below" },
  "root_digest": "SHA-256 of canonical JSON of all fields above (excluding root_digest and signature)",
  "signature": "SSHSIG Ed25519 signature of root_digest"
}
```

### chain_hash derivation caveat

`chain_hash` is the SHA-256 of the chain file's **UTF-8, LF-normalized decoded text** — the text Python's `read_text()` yields — **not** of the file's raw bytes. On Windows the chain file is written with CRLF line endings, so a byte-level hash of the file differs from `chain_hash` on every Windows-authored bundle. Any tool recomputing this value must decode first and normalize newlines; the attestation's chain byproduct (below) carries the same value and the same caveat.

## The attestation (format 1.1.0, additive)

From format 1.1.0 every bundle embeds a standards-conformant attestation under the top-level `attestation` key: an **in-toto Statement v1** (`https://in-toto.io/Statement/v1`) carrying a **SLSA Provenance v1** predicate (`https://slsa.dev/provenance/v1`), DSSE-signed (`application/vnd.in-toto+json`) inside a **Sigstore bundle** (`application/vnd.dev.sigstore.bundle.v0.3+json`).

Layout contracts:

- The DSSE envelope has **exactly one** signature; the signature object carries `sig` only — **no `keyid`** — and `verificationMaterial` is exactly `{"publicKey": {}}` (the empty public-key identifier). The key travels in the bundle's own `public_key` field and the `.pub.pem` sidecar, not in the attestation wrapper.
- The DSSE signature is **plain Ed25519** (RFC 8032), not Ed25519ph, over the DSSE PAE, made with the **same ephemeral key** that signs the chain and the bundle's `root_digest`. A verifier must check the DSSE key equals the bundle's `public_key` — that binding is what makes the attestation inseparable from the bundle.
- `payload` and `sig` are standard base64 **with padding**.
- The wrapper carries nothing ForgeProof-specific; everything ForgeProof-specific lives inside the predicate.
- The embedded copy sits **inside `root_digest`**, so the SSHSIG signature covers it and pre-1.1.0 verifiers hash it blindly and stay green (with one benign unknown-version warning on pre-v1.3 verifiers).

### Statement subjects

One subject per deduplicated artifact (`name` = repo-relative path, `digest.sha256`). A run with zero file edits attests the chain itself with exactly one subject: `{"name": ".forgeproof/chain-<N>.json", "digest": {"sha256": <chain_hash>}}` (the LF-normalized text hash — see the caveat above).

### SLSA buildType v1

`predicate.buildDefinition.buildType` is `https://github.com/ryanjmichie-git/forgeproof-plugin/blob/main/skills/run/references/rpack-format.md#slsa-buildtype-v1` — this section. The parameter schema:

- `externalParameters.issue` — the bundle's `issue` object (number, title, url).
- `externalParameters.requirements` — the bundle's requirements list.
- `externalParameters.approvals` — human approval events recorded during the run: `{gate, decision, note, approver, evidence}`. `approver` is filled by the engine from `git config user.email`, never from a flag. Every entry is labeled `"evidence": "agent-recorded"` — **the AI asserts that the human approved; this is not cryptographic proof of consent.**
- `internalParameters.builder` — builder identity with per-field provenance labels: `model` (`source: "self-reported"` — whatever the agent claims to be), `claude_code` (`source: "measured"` — probed CLI version, `"unknown"` when unavailable), `plugin` (`source: "engine-constant"`).
- `resolvedDependencies` — the recorded base branch as `git+<repo>@refs/heads/<base>` with `digest.gitCommit`, when a branch-create block exists.
- `runDetails.metadata` — `invocationId` = the genesis block hash; `startedOn`/`finishedOn` = the genesis and finalize block timestamps, copied verbatim (RFC 3339 UTC).
- `runDetails.byproducts` — the chain descriptor (same `chain_hash` value and caveat as above, annotated `digestOver: "utf-8 lf-normalized decoded text"`) and the evaluation summary as base64 `content`.

### Builder id

`runDetails.builder.id` is `https://github.com/ryanjmichie-git/forgeproof-plugin/tree/v<plugin-version>` — the exact plugin release that ran. **Scope and trust base:** ForgeProof runs on an individual workstation, inside a Claude Code session, under the operator's account; the trust base is that workstation, its operator, and the agent — there is no hosted, isolated build platform behind this id. Accordingly ForgeProof emits a SLSA Provenance v1 predicate containing the fields **required at Build L1** and claims no SLSA level: level attainment is a property of the producer's process and the verifier's trust decision, not of the predicate's shape. See `docs/compliance-mapping.md`.

## Sidecar files

`finalize` exports the attestation twice, byte-consistently:

| File | Contract |
|------|----------|
| `.forgeproof/issue-<N>.sigstore.json` | Exactly the canonical JSON (sorted keys, compact separators) of the embedded `attestation` value. Pure ASCII, **no newline characters at all** — nothing for an editor, git, or a formatter to translate. Byte-identity with the embedded copy is enforced at emission by tests; `verify` never reads the sidecar (see below). |
| `.forgeproof/issue-<N>.pub.pem` | The same Ed25519 key as `public_key`, as an RFC 8410 SubjectPublicKeyInfo PEM (`PUBLIC KEY` block type, LF endings, single base64 line starting `MCowBQYDK2VwAyEA`). This is the `--key` input for cosign. |

Both are staged by the run skill's ordinary `git add .forgeproof/` seal step. Reformatting or regenerating a sidecar does not affect verification of the `.rpack` — the sidecar's own DSSE signature is what cosign checks.

## Evaluation Status

| Status | Meaning |
|--------|---------|
| `pass` | All requirements covered, all tests pass, no lint errors |
| `partial` | Some requirements uncovered or some tests failing |
| `fail` | Critical failures — no tests pass or chain integrity compromised |

Bundles are always produced regardless of status.

## Verification

The `verify` subcommand checks:
1. Format known, version recognized by membership (unknown version = one warning, never an error)
2. Root digest recomputation matches stored value (covers the embedded attestation)
3. SSHSIG Ed25519 signature validates against embedded public key
4. Chain hash matches the chain file on disk (if present)
5. Chain block linkage is intact (each prev_hash matches)
6. Artifact SHA-256 hashes match files on disk (if present)
7. Attestation well-formed; DSSE signature verifies **under the bundle's own key**; signed subjects equal the bundle's artifacts and the chain byproduct equals the sealed `chain_hash`

An **absent** attestation is silent: the three attestation checks report `skipped` with zero errors and zero warnings in every mode, `--strict` included. `verify` performs **zero filesystem reads for attestation purposes** — it never reads or compares the sidecars; a `.rpack` remains a receipt that verifies alone from any directory. Missing chain files or artifacts produce warnings, not errors — this is normal when verifying bundles from a different checkout.
