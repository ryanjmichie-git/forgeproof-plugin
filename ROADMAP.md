# ForgeProof Roadmap

**Thesis:** Don't certify the model — attest the work. As AI authors more of the world's code, a verifiable record of *what the AI did, who authorized it, and whether it changed since* stops being a nice-to-have and becomes infrastructure. Every release below advances one layer of that trust stack.

*Last updated: 2026-07-03 · Maintainer: [@ryanjmichie-git](https://github.com/ryanjmichie-git) · Shipped details live in [CHANGELOG.md](CHANGELOG.md)*

This roadmap is directional, not a contract. Order is firm; timing is not. To influence it, open an issue or a discussion.

## Status legend

| Status | Meaning |
|---|---|
| ✅ Shipped | Released and tagged |
| 🔨 Now | Actively being built |
| 🧭 Next | Committed, design underway |
| 🌅 Later | Planned, order may shift |
| 🔬 Exploring | Under research, not committed |

## Guiding principles

1. **Verification is forever.** Any `.rpack` ever signed must verify with every future version of the verifier. Bundle-format changes are additive; the verifier accepts all historical formats. This is a hard compatibility promise.
2. **Zero-dependency verification.** Verifying a bundle requires Python stdlib and nothing else — no pip installs, no API keys, no network. Optional trust tiers (Sigstore) may add tooling for *signing*, never for baseline *verification*.
3. **Honest claims.** Provenance makes code attributable and tamper-evident, not safe. ForgeProof never implies a signed bundle means reviewed or secure code. Features that close the review gap (attested review) record verdicts verifiably; they don't launder trust.
4. **Attest work, not models.** Per-change evidence over per-vendor stamps. No central authority required to verify a ForgeProof bundle.

---

## Release arc

### ✅ v1.0.0 — Launch
GitHub issue → working code → Ed25519-signed, SHA-256 hash-chained `.rpack` provenance bundle. Stdlib-only Python engine, `gh`-CLI workflow, skills for run/push/verify.

### ✅ v1.0.1 — Hooks actually fire
Fixed the two launch-critical hook bugs: missing top-level `hooks` wrapper in `hooks/hooks.json` (Zod schema violation) and invalid `PreToolUse` matcher syntax that caused the PR gate to silently never fire. Marketplace listing live; direct install available via `/plugin marketplace add ryanjmichie-git/forgeproof-plugin`.

---

### ✅ v1.1.0 — Runs everywhere

**Narrative.** A provenance tool earns nothing if it breaks on the reviewer's machine. v1.0.x works where it was developed; v1.1.0 makes it work where users actually are — macOS, Windows, and minimal Linux — and cleans up the command surface so the plugin feels native to Claude Code. This is the trust floor: every later release assumes this one.

**Major changes**
- **Cross-platform engine.** Hash computation moves into the Python engine (`cmd_record`), removing the `sha256sum` shell dependency that doesn't exist on macOS or Windows.
- **Interpreter portability.** All invocations use `python3` with `python` fallback; no reliance on a `python` symlink.
- **Windows compatibility.** Single-quoted JSON `--data` arguments replaced with discrete CLI flags (cmd.exe cannot pass quoted JSON safely).
- **Hook performance.** PostToolUse no longer runs full-project lint on every file edit during active sessions; linting is scoped to ForgeProof-touched files.
- **Command surface rename.** Skills renamed so slash commands read naturally: `/forgeproof:run`, `/forgeproof:push`, `/forgeproof:verify`, `/forgeproof:reset` (previously `/forgeproof:forgeproof` et al.). Docs updated to match.
- **Manifest hygiene.** `version` field dropped from `marketplace.json` (`plugin.json` is authoritative and silently wins).
- **Triage of remaining review items.** Non-critical findings from the 16-issue review (`FORGEPROOF_REVIEW.md`) resolved or explicitly deferred with rationale.

**Success criteria**
- Full run→push→verify workflow passes on macOS, Ubuntu (no `python` symlink), and Windows (cmd.exe and PowerShell).
- `claude plugin validate .claude-plugin/plugin.json` passes on current CLI.
- Regression test proves the PR gate blocks when the chain is invalid (guarding against the v1.0.0 silent-failure class).
- Every v1.0.x `.rpack` still verifies (Principle 1).
- Zero new dependencies.

**Out of scope:** anything that changes the bundle format or adds new workflow capabilities.

---

### 🧭 v1.2.0 — Verification by default

**Narrative.** Provenance nobody checks is theater. Today, verifying a bundle is something a diligent person *can* do; v1.2.0 makes it something that *happens* — a red/green check on every PR, enforceable via branch protection. This is the release where "who's allowed to merge AI-written fixes?" gets a mechanical answer: changes whose provenance verifies.

**Major changes**
- **`forgeproof-verify` GitHub Action** (companion repo / published action): verifies the attached `.rpack` on every PR, posts a status check, comments a human-readable audit summary. Runs the stdlib verifier directly — no Claude Code required in CI.
- **Required-check recipe.** Documented branch-protection setup so orgs can enforce "no AI-authored PR merges without a valid bundle."
- **README badge** advertising verified provenance.
- **Richer verify output.** `/forgeproof:verify` and the CLI emit a structured, human-readable audit report (phases, timestamps, approvals, file digests), not just pass/fail.

**Success criteria:** a tampered bundle turns the PR check red; an untouched one turns it green; a repo with branch protection cannot merge the red case.

---

### 🧭 v1.3.0 — Speak the industry's language

**Narrative.** ForgeProof's `.rpack` proves integrity, but only to ForgeProof's own verifier. Supply-chain security already standardized how attestations are expressed — in-toto, SLSA, DSSE — and regulation (US federal secure-development attestations, EU Cyber Resilience Act) is converging on those formats. This release makes every bundle *also* a standards-conformant attestation, so AI-written code becomes compliance-ready by default and verifiable with tools the industry already trusts.

**Major changes**
- **in-toto Statement v1 emission** with a **SLSA Provenance v1 predicate** alongside (and referenced inside) the `.rpack`, wrapped in a DSSE envelope.
- **Builder identity in the predicate:** model identifier, Claude Code CLI version, plugin/skill version, and human approval events — the record shows not just what the AI did, but who authorized it and with what toolchain.
- **`cosign` interop:** documented `cosign verify-blob-attestation` path for the emitted attestation.
- **Compliance mapping doc:** how ForgeProof output maps to secure-development attestation requirements (OMB M-22-18 lineage) and EU CRA expectations.

**Success criteria:** the emitted attestation verifies via cosign with no ForgeProof code present; `.rpack` format remains backward-verifiable.

---

### 🌅 v1.4.0 — Identity, not just integrity

**Narrative.** Self-generated Ed25519 keys prove tamper-evidence but are ultimately self-attestation. The unresolved question in every "certified AI" debate is *who issues the stamp*. Keyless signing dissolves it: signatures bound to verifiable OIDC identities (a GitHub account, a CI runner) recorded in a public transparency log. Identity plus transparency substitutes for authority — no NATO-type certifying body required.

**Major changes**
- **Optional Sigstore keyless signing tier** (Fulcio certificates, Rekor transparency log) for signing; stdlib Ed25519 remains the zero-dependency default.
- **Identity display in verify output:** who (which identity) signed, per block or per bundle.
- **Key lifecycle docs:** rotation, revocation posture, and how the two tiers coexist in one chain.

**Success criteria:** a keyless-signed bundle's identity is independently confirmable via Rekor; baseline verification still requires nothing but stdlib.

---

### 🌅 v1.5.0 — Attested review

**Narrative.** "Nobody can check code anymore" is the honest problem statement — and provenance alone doesn't fix it; it makes bad code attributable, not detected. This release closes the gap the honest way: an independent review pass (a second, isolated Claude session and/or static analyzers) whose verdict and findings digest are recorded as signed blocks *in the chain*. Not a trust-us stamp on the outside — a verifiable review event on the inside.

**Major changes**
- **`/forgeproof:review`:** runs the independent pass, records reviewer identity, tool versions, verdict, and findings hash as chain blocks.
- **Gate integration:** PR gate and CI Action can require a passing attested review, not just chain integrity.
- **Honest-limits doc:** what attested review does and does not guarantee.

**Success criteria:** a bundle's verify report distinguishes "integrity verified" from "integrity + review verified"; review blocks are tamper-evident like all others.

---

### 🔬 v2.0.0 — Beyond GitHub

**Narrative.** The trust layer shouldn't care which forge you use or which surface you're on. v2 expands ForgeProof from a GitHub-and-terminal tool to a provenance layer: GitLab issue→MR workflows, and verification available anywhere Claude runs. Major version because the configuration surface and workflow assumptions change.

**Exploring**
- **GitLab support:** issue → merge request with provenance, via an MCP server (Streamable HTTP, OAuth 2.1 + PKCE, `readOnlyHint`/`destructiveHint` annotations on every tool).
- **MCP verify endpoint** so Claude web/desktop/Cowork can verify any bundle conversationally.
- **Directory strategy:** submissions to the claude.com plugin and connector directories; pursue Anthropic Verified (privacy policy, test project with sample issues, ≥3 example prompts).
- **Multi-agent provenance:** in coordinated-agent workflows, each subagent signs its own blocks — a chain of custody across a team of AIs.

---

## Non-goals

- **Malware detection.** ForgeProof records and attests; it is not a scanner. Attested review records a reviewer's verdict — it doesn't make ForgeProof one.
- **Hosted service / telemetry.** Local-first. Nothing phones home.
- **Release-artifact signing.** ForgeProof attests the *development* of changes, not binary distribution (use Sigstore/SLSA build tooling for that — we interoperate, we don't replace).
- **Payments or monetization features** of any kind.

## Versioning & compatibility policy

- **SemVer.** Patch = fixes, minor = additive features, major = workflow/config breaking changes.
- **Bundle format:** versioned independently inside the `.rpack`; changes are additive and the verifier accepts all historical formats, forever (Principle 1).
- **Command renames** (as in v1.1.0) ship with doc updates and a migration note; old invocations are removed, not aliased, to keep the surface small.
- **Support:** latest minor release receives fixes; verification of old bundles is supported unconditionally.
