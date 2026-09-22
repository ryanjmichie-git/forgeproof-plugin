# .rpack Bundle Format

The `.rpack` file is a JSON document containing the complete provenance record for a ForgeProof run. Version: **1.1.0**.

## Status and stability

This document is the normative specification of the format. The key words "MUST", "MUST NOT", "SHOULD", and "MAY" in this document are to be interpreted as described in BCP 14 (RFC 2119, RFC 8174) when, and only when, they appear in all capitals, as shown here.

**Compatibility is forever.** Format versions are additive-only: every `.rpack` ever signed by any released ForgeProof (the 1.0.0 line included) verifies with every future verifier, and a verifier recognizes versions by *membership* in its known set — never by ordering, and no version implies any particular key is present. A 1.0.0 bundle without an `attestation` key is fully valid forever.

The known set is the engine constant `KNOWN_RPACK_VERSIONS` — today `1.0.0` and `1.1.0`. It is append-only: verifiers accept every historical version forever, and an unrecognized `version` is one warning, never an error.

## Identity

- **`format`** is always the string `forgeproof-rpack`. It is the in-band identity: a verifier MUST fail a document whose `format` is anything else.
- **`version`** is the format version, a string. Every format 1.x version has the form `1.<minor>.<patch>` (decimal integers, as in `1.0.0` and `1.1.0`); the known set and the treatment of an unrecognized version are stated under Status and stability. This document describes `1.1.0`.
- **Media type:** `application/vnd.forgeproof.rpack+json` (vendor tree; status: `docs/media-type.md`). One name covers every revision whose `format` is `forgeproof-rpack`; it carries no version token and no parameters. The media type is never written into the document — it travels outside it (for example in a `Content-Type` header).
- **File extension:** `.rpack`. The extension is also used by unrelated binary game-asset archives whose first four bytes are `RP5L` or `RP6L`; those files never begin with `{` and are distinguishable by content.

A name is not a trust signal. From the security considerations published with the media type (`docs/media-type.md`), verbatim:

> A ForgeProof bundle is a tamper-EVIDENT provenance record, not a safety, security, review, or correctness attestation. It contains an Ed25519 signature over a SHA-256 digest of the document's canonical serialization; a valid signature proves only that the document was not altered after signing by the holder of the corresponding private key. It proves nothing about the correctness, safety, or quality of the code the document describes. Consumers MUST NOT treat a verified bundle as evidence that the described change was reviewed, tested to any standard, or secure, and MUST NOT present it as compliance with any regulation or framework.

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

## Validity (normative)

Validity is a property of the **parsed JSON value**; the one requirement on the file's bytes is their encoding. A `.rpack` document is a single JSON object (RFC 8259) encoded in **UTF-8** — RFC 8259 §8.1: "JSON text exchanged between systems that are not part of a closed ecosystem MUST be encoded using UTF-8". A file in any other encoding (UTF-16 or UTF-32, for example) is not a `.rpack` document, and verification fails. That is a validity failure, not enforcement of the emission profile below: of the profile's encoding item, the UTF-8 half restates this rule, and only the no-byte-order-mark half is an emission matter. Member order, indentation, line endings, and a leading UTF-8 byte-order mark do not affect validity; a verifier ignores such a mark, parses the document, and recomputes every digest from the parsed value.

| Member | Type | Notes |
|--------|------|-------|
| `version` | string | See Identity |
| `format` | string | Always `forgeproof-rpack` |
| `issue` | object | `number` (integer), `title` (string), `url` (string, may be empty) |
| `requirements` | array of objects | `id`, `text` (strings), `status` (`covered` or `uncovered`), `tests` (array of strings) |
| `artifacts` | array of objects | `path` (string: project-relative, forward slashes), `operation` (`create` or `modify`), `sha256` (lowercase hex SHA-256 of the file's raw bytes) |
| `decisions` | array of objects | `context`, `choice`, `rationale` (strings) |
| `evaluation` | object | `status` (string, see Evaluation Status), `tests_passed`, `tests_failed`, `lint_errors` (integers), `requirement_coverage` (a **string** such as `"100%"`), `uncovered_requirements`, `failed_tests` (arrays of strings) |
| `chain_hash` | string | Lowercase hex; see the caveat above |
| `public_key` | string | OpenSSH public-key line (`ssh-ed25519 <base64> [comment]`) |
| `attestation` | object | Optional at every version; see The attestation |
| `root_digest` | string | 64 lowercase hex characters |
| `signature` | string | SSHSIG armor |

**Every number is an integer.** Producers MUST NOT emit non-integer numbers: their canonical serialization would be implementation-defined. Members a consumer does not recognize are permitted at every level; consumers MUST ignore them rather than reject the document, and they are covered by `root_digest` like any other member.

### Canonical serialization

Every digest below is taken over the **canonical serialization** of a JSON value, defined as exactly the output of Python's `json.dumps(obj, sort_keys=True, separators=(",", ":"))`:

- Object members are sorted by name in Unicode **code point** order (not UTF-16 code unit order) at every nesting level; arrays keep their order.
- No whitespace: the only separators are `,` and `:`.
- In strings, `"` and `\` are escaped as `\"` and `\\`; U+0008, U+0009, U+000A, U+000C, and U+000D as `\b`, `\t`, `\n`, `\f`, and `\r`; every other character outside U+0020–U+007E as `\uXXXX` with lowercase hex digits, a character above U+FFFF as its UTF-16 surrogate pair. `/` is not escaped.
- Integers are decimal with no leading zeros; `true`, `false`, and `null` are literal.
- The result is pure ASCII, and it is hashed as those bytes (UTF-8).

### `root_digest` and `signature`

- **`root_digest`** is the lowercase hex SHA-256 of the canonical serialization of the top-level object with exactly two members removed: `root_digest` and `signature`. Everything else — `attestation` and any unrecognized member included — is digest input. A verifier MUST recompute it and MUST fail on a mismatch.
- **`signature`** is an SSHSIG signature (`ssh-keygen -Y sign`) under the namespace `forgeproof` over the `root_digest` string itself — its 64 ASCII characters, no trailing newline — and MUST verify under `public_key`. The member MUST be exactly the armor: it begins with `-----BEGIN SSH SIGNATURE-----`, ends with `-----END SSH SIGNATURE-----`, and carries only base64 characters and LF between the two — no leading or trailing bytes of any kind, whitespace included. The LF directly after the BEGIN marker is required in practice as well: `ssh-keygen -Y verify` rejects armor without it, and the JSON Schema's `signature` pattern requires it. A missing, empty, non-string, or non-canonical `signature`, or a missing `public_key`, fails verification in every mode.
- **`chain_hash`** is derived as the caveat above describes. What a verifier checks about an `attestation` is stated under The attestation → "What binds a verifier"; an absent `attestation` is valid at every version.

## The attestation (format 1.1.0, additive)

From format 1.1.0 the reference producer embeds in every bundle a standards-conformant attestation under the top-level `attestation` key: an **in-toto Statement v1** (`https://in-toto.io/Statement/v1`) carrying a **SLSA Provenance v1** predicate (`https://slsa.dev/provenance/v1`), DSSE-signed (`application/vnd.in-toto+json`) inside a **Sigstore bundle** (`application/vnd.dev.sigstore.bundle.v0.3+json`).

Layout contracts — what the reference producer emits at format 1.1.0 (the subset that binds a verifier follows the list):

- The DSSE envelope has **exactly one** signature; the signature object carries `sig` only — **no `keyid`** — and `verificationMaterial` is exactly `{"publicKey": {}}` (the empty public-key identifier). The key travels in the bundle's own `public_key` field and the `.pub.pem` sidecar, not in the attestation wrapper.
- The DSSE signature is **plain Ed25519** (RFC 8032), not Ed25519ph, over the DSSE PAE, made with the **same ephemeral key** that signs the chain and the bundle's `root_digest`. Check 2 below holds a verifier to that key equality (the DSSE key is the bundle's `public_key`) — the binding that makes the attestation inseparable from the bundle.
- `payload` and `sig` are standard base64 **with padding**.
- The wrapper carries nothing ForgeProof-specific; everything ForgeProof-specific lives inside the predicate.
- The embedded copy sits **inside `root_digest`**, so the SSHSIG signature covers it and pre-1.1.0 verifiers hash it blindly and stay green (with one benign unknown-version warning on pre-v1.3 verifiers).

**What binds a verifier (normative).** The list above describes the reference producer's output; it is not a validity rule. When `attestation` is present, a conforming verifier MUST perform at least the following checks — the ones the reference verifier performs, in every mode — and MUST fail the document when any of them fails:

1. **Shape.** `attestation` is an object; its `dsseEnvelope` is an object whose `payloadType` is `application/vnd.in-toto+json`, whose `signatures` is an array of exactly one object with a string `sig`, and whose `payload` is a string of standard base64 with padding (the reference verifier accepts only the standard alphabet with no whitespace, requires the padding to be present and nothing to follow it, and does not require the unused bits of a final partial group to be zero; whether surplus padding after a complete final group is rejected depends on the interpreter — CPython 3.12 and later reject it, 3.11 accepts it — and `sig` in check 2 is decoded under the same rule). The decoded payload is UTF-8 JSON with no byte-order mark (unlike the outer document, where one is tolerated): an object whose `_type` is `https://in-toto.io/Statement/v1`, whose `predicateType` is `https://slsa.dev/provenance/v1`, and whose `subject` is a non-empty array.
2. **Signature.** `public_key` parses as an `ssh-ed25519` key, and `sig`, decoded from standard base64 with padding, is a plain Ed25519 (RFC 8032) signature by that key over the DSSE PAE of `payloadType` and the decoded payload. The key is always the bundle's own `public_key` — never key material or a key hint carried inside the attestation.
3. **Subjects.** Every `subject` entry is an object with a string `name` and a `digest` object with a string `sha256`, and the set of (`name`, `digest.sha256`) pairs equals the set of (`path`, `sha256`) pairs of the bundle's `artifacts`, each artifact value taken as a string (the member table permits nothing else; the reference verifier stops with an error before check 3 on an artifact whose `path` is not a string, compares a `sha256` of another type as its Python `str()` form, and on an absent `sha256` stops with an error when the file is on disk and compares the empty string when it is not) — or, when the bundle has no `artifacts` array or the array is empty, exactly the one pair (`.forgeproof/chain-<N>.json`, `chain_hash`), `<N>` being `issue.number`.
4. **Chain byproduct.** The first entry of `predicate.runDetails.byproducts` named `.forgeproof/chain-<N>.json` exists, and its `digest.sha256` equals the bundle's `chain_hash` — compared, never recomputed.

A verifier MUST NOT reject a document solely because its signature object carries additional members (`keyid` included), because of the value or absence of `mediaType`, or because `verificationMaterial` is absent, not an object, in its empty state, or populated: none of these is a validity rule of this format, and the reference verifier reads none of the three. A verifier that also implements the Sigstore bundle format's own rules MAY verify a *populated* `verificationMaterial` — one that carries key or identity material, such as a certificate or transparency-log entries — under those rules and fail a document that does not satisfy them; that check is additional to check 2, never a substitute for it, and it licenses no rejection over `mediaType`, nor over a `verificationMaterial` that is absent, not an object, or in the empty state `{"publicKey": {}}` the reference producer emits at format 1.1.0, which carries nothing to verify.

**`verificationMaterial` is opaque to this format.** It is owned by the Sigstore bundle format. The reference producer emits `{"publicKey": {}}` at format 1.1.0; a later producer MAY populate it (for example with a certificate and transparency-log entries) without a change to this specification. Its contents are untrusted until verified under the Sigstore bundle format's own rules.

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

## Emission profile (normative for the reference producer; recommended for other producers)

A `.rpack` document written by ForgeProof's `finalize` (the reference producer) MUST satisfy, and any other producer SHOULD satisfy, all of the following:

1. **Member order.** The top-level object begins with the member `version`, followed immediately by the member `format`. Consequently the byte sequence `"format": "forgeproof-rpack"` — or, for a producer that emits no whitespace after the colon, `"format":"forgeproof-rpack"` — occurs within the first 256 bytes of the file, and the first byte of the file is `{`.
2. **Encoding.** UTF-8 without a byte-order mark. The reference producer escapes every non-ASCII character as `\uXXXX` and therefore emits pure ASCII.
3. **Line endings.** Either LF or CRLF throughout, or no line breaks at all. The line-ending convention is not significant and MAY differ between platforms; the reference producer emits the platform's native convention (LF on POSIX, CRLF on Windows).
4. **Layout.** The reference producer emits two-space indentation and a trailing newline. Indentation and whitespace are not significant.

**Validity is independent of emission.** A consumer MUST NOT reject, and a verifier MUST NOT fail, a document solely because it departs from this profile: validity is defined over the parsed JSON value (§Validity), and every digest and signature is computed over the canonical serialization of that value, never over the file's bytes. Detection rules that key on item 1 (the files under `share/`) therefore identify profile-conforming documents reliably and other valid documents on a best-effort basis; in particular, a document re-serialized with sorted members remains valid and remains verifiable but MAY escape content-based detection while still being detected by its file name.

## Verification

The `verify` subcommand checks:
1. Format known, version recognized by membership (unknown version = one warning, never an error)
2. Root digest recomputation matches stored value (covers the embedded attestation)
3. SSHSIG Ed25519 signature validates against embedded public key
4. Chain hash matches the chain file on disk (if present)
5. Chain block linkage is intact (each prev_hash matches)
6. Artifact SHA-256 hashes match files on disk (if present)
7. Attestation well-formed; DSSE signature verifies **under the bundle's own key**; signed subjects equal the bundle's artifacts and the chain byproduct equals the sealed `chain_hash`

An **absent** attestation is silent: the reference verifier's three attestation check rows (`attestation`, `attestation_signature`, `attestation_subjects` — which together carry the four numbered checks above) report `skipped` with zero errors and zero warnings in every mode, `--strict` included. `verify` performs **zero filesystem reads for attestation purposes** — it never reads or compares the sidecars; a `.rpack` remains a receipt that verifies alone from any directory. Missing chain files or artifacts produce warnings, not errors — this is normal when verifying bundles from a different checkout.

### Verification requirements

The reference verifier needs Python 3.11+ (standard library only) **plus** OpenSSH `ssh-keygen` 8.1 or later for the SSHSIG check (`ssh-keygen -Y verify`). The attestation checks need the standard library only. cosign is optional (`docs/cosign-interop.md`).

## Format-bump checklist

A future format version (say `1.2.0`) MUST, in the release that introduces it:

1. be added to `KNOWN_RPACK_VERSIONS` — append-only, and additive over every earlier version;
2. freeze a fixture bundle from the last engine of the previous format, before any change, never to be regenerated — and raise the fixture count the two CI drivers pin (`stress/validate_schema.py` and `stress/check_detection.py` expect an exact number of frozen fixtures and fail on any other, so that a fixture cannot go unproven);
3. re-issue the JSON Schema under a new `$id` if the schema changes;
4. update the media type's registration record, if one exists by then, through the change procedure of RFC 6838 §5.5, and the ledger in `docs/media-type.md`.
