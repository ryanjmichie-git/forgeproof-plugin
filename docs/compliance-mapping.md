# Compliance mapping — what a ForgeProof attestation is evidence of

This document maps ForgeProof's v1.3.0 output (an in-toto Statement v1 with a SLSA Provenance v1 predicate, DSSE-signed, plus the `.rpack` provenance bundle) onto the secure-software-development landscape as it actually stands in 2026 — including what changed in January 2026, and the honest limits. **Nothing here claims that a ForgeProof bundle makes anyone compliant with anything.** It is evidence a producer can present; whether it satisfies a given obligation is a determination only the obligated party (and their assessor) can make.

## The US federal picture, stated accurately

- **NIST SSDF (SP 800-218) is a voluntary reference standard**, not a procurement mandate. It defines practices and tasks that organizations may adopt and reference.
- The federal *mandate* era ran **2022-09-14 → 2026-01-23**: OMB **M-22-18** (and its **M-23-16** revision) required software producers selling to federal agencies to self-attest to SSDF-aligned practices, using the CISA Secure Software Development Attestation Form. On **2026-01-23**, OMB **M-26-05** rescinded both memoranda, calling the attestation regime "unproven and burdensome"; agencies *may* now use the CISA form as an optional resource. CISA's form page carries an archive banner, and the related FAR case (2023-002) remains open and unissued.
- The durable technical target is therefore the **CISA form's item 3** — the producer "maintains provenance for internal code and third-party components" — and the SSDF tasks it cites: **PO.1.3, PO.3.2, PO.5.1, PO.5.2, PS.3.1, PS.3.2, PW.4.1, PW.4.4, RV.1.1, RV.1.2**.

### What ForgeProof output maps to

SSDF defines *provenance* as "the chronology of the origin, development, ownership, location, and changes to a system or system component and associated data" and an *artifact* as "a piece of evidence." Against that vocabulary:

| SSDF task (cited by CISA form item 3) | What a ForgeProof bundle contributes |
|---|---|
| PO.3.2 (use tools to generate evidence), PO.5.1/PO.5.2 (secure environments — evidence trail) | A tamper-evident, signed record of every file edit, decision, test and lint result in the run, generated automatically by tooling |
| PS.3.1/PS.3.2 (archive/provenance data for each release) | The `.rpack` + attestation sealed into the same branch/commit as the code they describe |
| PW.4.1/PW.4.4 (reuse and verification of existing/generated code) | Per-artifact SHA-256 subjects; AI builder identity with per-field provenance labels |
| PO.1.3, RV.1.1/RV.1.2 (requirements, review of evidence) | Requirements extracted and coverage-tracked per test; human approval events recorded at gates |
| — | **Gap worth knowing: no SSDF practice or task addresses AI authorship of code.** ForgeProof records the model identity and human approvals anyway — evidence the standard does not yet ask for. |

## The EU picture

The **Cyber Resilience Act** (Regulation (EU) 2024/2847) applies in full on **11 December 2027** (notification obligations under Art. 14 from 11 September 2026; Chapter IV from 11 June 2026). The CRA **never requires cryptographic provenance and never mentions in-toto, SLSA, or DSSE.** The honest landing spot: a ForgeProof attestation **may serve as an element of the Annex VII technical documentation** — specifically 2(c) (description of the development process) and 6 (supporting evidence) — **at the manufacturer's discretion**. It is one form of supporting evidence, not a conformity mechanism.

## SLSA, stated accurately

ForgeProof **emits a SLSA Provenance v1 predicate containing the fields REQUIRED at Build L1** (`builder.id`, the build definition, subjects by digest). That phrasing is deliberate:

- **Level attainment is a property of the producer's process and the verifier's trust decision, not of the predicate's shape.** SLSA v1.2 splits L1 between producer obligations (follow a consistent build process; distribute provenance) and the build platform (provenance exists); a verifier then assigns a level from its own root of trust keyed on `builder.id` — "the sole determiner of the SLSA Build level." A tool cannot confer a level by construction; it can only emit the evidence an L1 posture needs.
- **A workstation is not disqualified at L1.** The "hosted build platform … not on an individual's workstation" requirement begins at **L2**; the spec explicitly allows "even an individual's workstation" as a build platform. L2 and above are out of reach for a local tool by design.
- **L1 provenance is documented by SLSA itself as "trivial to bypass or forge."** Its value is catching mistakes and carrying metadata honestly, not resisting a motivated attacker. ForgeProof's own signature chain (root digest, SSHSIG, chain linkage) is what provides tamper evidence — and that protection is ForgeProof's contract, not SLSA's.
- `builder.id` (`https://github.com/ryanjmichie-git/forgeproof-plugin/tree/v<version>`) resolves to the exact released tool version, and its scope and trust base — the local workstation, its operator, and the agent — are documented in [`skills/run/references/rpack-format.md`](../skills/run/references/rpack-format.md#builder-id).

## Honest limits, all in one place

1. **Approvals are agent-recorded.** The AI asserts that the human approved at a gate; the `approver` field comes from local git config. This is asserted evidence, not cryptographic proof of consent.
2. **The model identity is self-reported** by the agent that ran; the Claude Code version is measured; the plugin version is an engine constant. Each field carries its label in the predicate.
3. **SLSA Build L1 fields, no level claim.** See above.
4. **Ephemeral keys are self-attestation.** The signing key is generated per run and proves continuity and tamper-evidence, not identity. (The planned v1.4 Sigstore keyless tier is the identity story.)
5. **No compliance is conferred.** A bundle is evidence to present, mapped above to where it plausibly fits; it does not make anyone compliant with SSDF, the rescinded OMB memoranda, the CISA form, or the CRA.

## References

- NIST SP 800-218 (SSDF v1.1), practice/task definitions
- OMB M-22-18 (2022-09-14), M-23-16 (2023-06-09), **M-26-05 (2026-01-23, rescinding both)**
- CISA Secure Software Development Attestation Form (archived; optional resource per M-26-05), item 3
- Regulation (EU) 2024/2847 (Cyber Resilience Act), Art. 14, Chapter IV, Annex VII 2(c) and 6
- SLSA v1.2: build requirements, provenance (builder semantics), build track basics
