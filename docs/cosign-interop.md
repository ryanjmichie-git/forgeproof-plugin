# Verifying a ForgeProof attestation with cosign

Every bundle from v1.3.0 on carries an in-toto/SLSA attestation that verifies with **plain cosign and no ForgeProof code present**. This document is the exact, tested recipe.

**Baseline verification never requires cosign.** ForgeProof's own `verify` subcommand (pure Python stdlib) remains the source of truth and checks strictly more than cosign does (chain linkage, artifact hashes, the root-digest signature, and the attestation's binding to the bundle). cosign is a consumer-side, independent second opinion — useful precisely because it shares no code with ForgeProof.

## Tested versions

The interop contract is validated in CI against two pinned cosign binaries on every push:

| Binary | Version |
|--------|---------|
| cosign v2 line | **v2.6.5** |
| cosign v3 line | **v3.1.3** |

Both auto-detect the v0.3 Sigstore bundle media type; `--new-bundle-format` is not needed on either. Newer cosign releases are expected to work but are not part of the pinned contract.

## The two files

A ForgeProof run exports, next to the `.rpack`:

- `.forgeproof/issue-<N>.sigstore.json` — the Sigstore bundle (DSSE envelope + in-toto statement)
- `.forgeproof/issue-<N>.pub.pem` — the ephemeral Ed25519 public key as an SPKI PEM (cosign's `--key` input)

To extract them from a PR: check out the PR head (`gh pr checkout <number>`) and both files are in `.forgeproof/`.

## The command

Once per artifact listed in the bundle:

```
cosign verify-blob-attestation --key .forgeproof/issue-<N>.pub.pem \
  --bundle .forgeproof/issue-<N>.sigstore.json \
  --type slsaprovenance1 --insecure-ignore-tlog <artifact-path>
```

Exit 0 with `Verified OK` means: the DSSE envelope's signature verifies under the key you supplied, the payload is an in-toto statement with a SLSA Provenance v1 predicate, and the SHA-256 of `<artifact-path>` — which cosign computes itself from the file — appears among the signed subject digests.

## What each flag proves (and does not)

- **`--key`** — verification is against the key *you* supply, out of band. The attestation wrapper deliberately carries no key material or key hints, so there is nothing self-referential to be fooled by. Cross-check the PEM against the `.rpack`'s `public_key` field (same 32 raw bytes) if you want the binding ForgeProof's own verifier enforces.
- **`--type slsaprovenance1`** — requires `predicateType` to be `https://slsa.dev/provenance/v1`.
- **`--insecure-ignore-tlog`** — **required** for these bundles: with `--key`, cosign otherwise demands a Rekor transparency-log entry, and an offline, ephemeral-key bundle has none. This flag does not weaken the signature or claim checks; it skips only the transparency-log lookup. (The planned v1.4 keyless tier is what adds Rekor entries.)
- **The positional artifact path** — makes cosign hash the file itself. The claim check compares **digests only, never subject names**.

## Pitfall: do not feed the attestation's own digest back

`verify-blob-attestation` also accepts `--digest <hex> --digestAlg sha256` in place of the artifact path. With `--digest`, **cosign never reads any file** — it only checks that the hex you supplied appears among the signed subjects. Supplying a digest copied out of the attestation therefore verifies *green even when the artifact on disk is tampered*; it proves the attestation is internally consistent, nothing more. Use `--digest` only with a digest you computed yourself from the file (e.g. `sha256 <path>` via your platform's tool). When both a path and `--digest` are given, the path wins with a warning. Note v2.6.5 hardcodes SHA-256 when hashing a file path, while v3.1.3 honors `--digestAlg`.

## What failure looks like

- Artifact byte changed on disk → `provided artifact digest does not match any digest in statement`, exit 1.
- Envelope or payload altered → `accepted signatures do not match threshold, Found: 0, Expected 1`, exit 1.

## Verify the whole bundle, not just the attestation

cosign checks the attestation tier only. The `.rpack`'s chain integrity, decisions, evaluation claims, and the root-digest signature are ForgeProof's contract:

```
python3 skills/run/scripts/forgeproof.py verify --rpack .forgeproof/issue-<N>.rpack
```

or `/forgeproof:verify` in a Claude Code session, or the [forgeproof-verify GitHub Action](https://github.com/ryanjmichie-git/forgeproof-verify) on PRs.
