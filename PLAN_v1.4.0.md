# PLAN_v1.4.0.md — ForgeProof "A name of its own" (format identity)

> **Executor instructions:** Self-contained — assumes this document and the plugin repo at `c:\Dev\FORGEPROOF_SKILL2` (github.com/ryanjmichie-git/forgeproof-plugin). One repo: the companion `forgeproof-verify` Action is **not** touched (resolved question 3). Work on branch `release/v1.4.0`, one commit per phase, single release PR at the end. This file is `PLAN_v1.4.0.md`, renamed from `PLAN_format_identity.md` and committed in Phase 0 (resolved question 2). Follow superpowers:executing-plans / subagent-driven-development. Every external submission (IANA form, any upstream MR or e-mail) is presented to Ryan as final text and sent only after his sign-off (hard constraint 9).

**Status:** Approved 2026-09-19 (all recommended options). Proposed 2026-09-16. Supersedes the 2026-09-05 draft, whose decisions are re-validated in §3.6. *Premise correction:* that draft's own baseline line reads `release/v1.3.0 @ e61a7d8` — it was drafted **after** the 1.1.0 format bump, not against v1.2.x; its `RPACK_VERSION` and attestation facts were already current.
**Target versions:** plugin `1.4.0` (a new minor; the keyless milestone renumbers to v1.5.0 and attested review to v1.6.0 — resolved question 1); bundle format **unchanged at 1.1.0**; **no engine code change**; `forgeproof-verify` Action **unchanged** at v1.1.0.
**Baseline:** `main` @ `e6aef5c` = `origin/main` = tag `v1.3.0` (annotated 2026-09-05). `plugin.json` 1.3.0; `RPACK_VERSION = "1.1.0"`, `KNOWN_RPACK_VERSIONS = frozenset({"1.0.0", "1.1.0"})`, `RPACK_FORMAT = "forgeproof-rpack"` (`forgeproof.py:45-50`).

---

## Step 0 — Prerequisite gate outcome (run 2026-09-16)

| Check | Result |
|---|---|
| `git fetch origin && git status -sb` | `## main...origin/main` — HEAD `e6aef5c` == `origin/main`; tracked tree clean. One untracked file: `PLAN_format_identity.md` (the 2026-09-05 draft, 88 KB) — the file this plan overwrites on approval. Not a stale clone. |
| `plugin.json` version | `"version": "1.3.0"` (line 3) |
| `RPACK_VERSION` / `KNOWN_RPACK_VERSIONS` | `"1.1.0"` / `frozenset({"1.0.0", "1.1.0"})` (`forgeproof.py:45,49`); `RPACK_FORMAT = "forgeproof-rpack"` (`:50`) |
| v1.3.0 shipped | CHANGELOG top entry `## [1.3.0] - 2026-08-15`; annotated tag `v1.3.0` exists, tagger date 2026-09-05 on merge commit `e6aef5c`. CHANGELOG dates are authoring dates (same pattern as 1.1.0 `07-03` vs tag `07-07`, 1.2.2 `07-17` vs `07-18`). Gate passes on the CHANGELOG entry as specified. |
| Root files | `ROADMAP.md` (Last updated 2026-09-05, v1.3.0 ✅, **no 🔨/🧭 anywhere** — *corrected 2026-09-20:* none on any milestone (legend rows only)), `PLAN_v1.1.0.md`, `PLAN_v1.2.0.md`, `PLAN_v1.3.0.md`, `CHANGELOG.md`, `PRIVACY.md`, `README.md`, `.gitattributes` (one rule: `skills/run/scripts/fixtures/** -text`) — all present |
| References / docs / CI | `skills/run/references/rpack-format.md` ("Version: **1.1.0**"), `chain-format.md`, `docs/cosign-interop.md`, `docs/compliance-mapping.md`, `docs/branch-protection.md`, `.github/workflows/{ci,stress,verify-provenance}.yml` — present |
| Frozen fixtures | `fixtures/v101` (issue 999), `v110` (998), `v122` (997); all three begin `{\n  "version": "1.0.0",\n  "format": "forgeproof-rpack",` (od-verified), zero CR bytes; **no v1.3.0-engine fixture** |
| Absent (confirmed) | `FORGEPROOF_REVIEW.md`, any `install*`, any `*.schema.json`, any `.vscode/` — none exist. JSON Schema is greenfield. |

**Gate: PASS.** Nothing here is void.

---

## 1. Resolved questions (proposals — to be decided with Ryan) and Open questions

Recommendation first; "prior" = the 2026-09-05 draft's decision.

| # | Question | Recommendation | Alternatives considered | Why |
|---|---|---|---|---|
| RQ1 | **Milestone home** | **New minor `v1.4.0 — A name of its own`**, inserted after v1.3.0; renumber "Identity, not just integrity" → v1.5.0 and "Attested review" → v1.6.0. Status marker 🧭 Next in Phase 0, ✅ at release. | (a) fold into the keyless v1.4.0 (prior); (b) v1.3.x patch; (c) defer | Zero engine change makes this a docs/CI release that can ship in days; the IANA "Published specification" field needs an existing tag. Both premises of the prior's fold are refuted: the Action re-vendor is not forced (E11) and the spec needs no amendment when keyless lands because `attestation.verificationMaterial` is declared opaque (owned by the Sigstore bundle format). "Identity" in the keyless milestone means *who signed*; this is *what the file is* — the fit is a pun. A patch violates "patch = fixes" (both shipped patches were pure security fixes) and would put "v1.3.1" on the IANA form. Deferral spends the standards-formation window for nothing. Renumbering cost, measured: `ROADMAP.md:90,103` headings, `docs/compliance-mapping.md:41`, `docs/cosign-interop.md:43` ("the planned v1.4 … tier"), and the engine docstring `forgeproof.py:530` ("the v1.4 seam" — comment only, updated in the release commit that bumps `PLUGIN_VERSION` anyway). Frozen plans (`PLAN_v1.2.0.md:190`, `PLAN_v1.3.0.md:236`) are left as historical records. |
| RQ2 | Rename `PLAN_format_identity.md` → `PLAN_v1.4.0.md`? | **Yes, in Phase 0** (`mv` + `git add`; the file is untracked). The approval-time write stays `PLAN_format_identity.md` per your instruction. | keep the cross-milestone name (prior) | Under RQ1 everything but the post-tag IANA submission ships in one release, so the one-plan-per-release precedent (v1.1/v1.2/v1.3) applies. |
| RQ3 | Re-vendor `forgeproof-verify` for a `PLUGIN_VERSION`-only engine diff? | **No.** The Action stays at v1.1.0; CHANGELOG states "forgeproof-verify v1.1.0 remains current — the verifier is unchanged". | Full ritual per CLAUDE.local.md step 5 (~1 h): vendor from the v1.4.0 tag, re-pin `UPSTREAM`, release v1.1.1, move `v1`, update the three plugin pins in a follow-up commit | E11: the Action's sync-check compares the vendored bytes against the **pinned ref** (`ac9da9b8`, sha256 `f713f3e9…` = today's engine), so it stays green forever. `PLUGIN_VERSION` is unused by `verify`. With the version bump as the final step (constraint 5) a re-vendor can only happen after the tag, and the plugin pins would then need a post-release commit — churn for zero verifier change. **Genuinely Ryan's call**: it departs from the letter of the local release checklist. |
| RQ4 | Tree and type string | **Vendor tree, `application/vnd.forgeproof.rpack+json`** (prior stands) | `prs.michie.rpack+json`; `vnd.forgeproof+json`; `.v1` in the subtype (OCI style); a `version` parameter (CycloneDX/Syft style) | RFC 6838 §3.2 names non-commercial producers as eligible (R1); `prs.` is for experimental/non-distributed products (R2). `+json` is SHOULD-level (R5). One media type for every `format: forgeproof-rpack` revision (Principle 1: additive forever; membership-only recognition) — a version token would retroactively make the bare name mean "1.x", and a parameter would invite dispatching on a value the engine deliberately treats as non-implicative. |
| RQ5 | Embed the media type in bundle bytes? | **Never** (prior stands). Carried externally: spec, `docs/media-type.md`, the IANA template, and `Content-Type` in the v2.0.0 MCP endpoint (first engine constant then). | add `mediaType` now (format 1.2.0); add it with some future additive change; `$schema` member | Any new top-level key enters `root_digest` input (denylist `forgeproof.py:1873`) and costs a format bump whose only beneficiary already knows the format. `format` + `version` are the in-band identity and already verified/gated (`:1851`, `:2634`). Sigstore embeds `mediaType` because its bundle is *versioned by* media type; ForgeProof versions by `version`. |
| RQ6 | Keep `.rpack`? | **Keep, no alias** (prior stands) | `.rpack.json`; dual globs | Hard-coded in six engine sites (E8), three skills, the Action's `bundle` default `.forgeproof/*.rpack` (live), fixtures, and every user repo; the Techland collision is name-only and content-disjoint (`R` vs `{`, P1–P3); no registry anywhere claims it (I1, M4, L3, M10). |
| RQ7 | Schema `$id` | **Tag-pinned raw URL of the release that last changed the schema**: `https://raw.githubusercontent.com/ryanjmichie-git/forgeproof-plugin/v1.4.0/schemas/forgeproof-rpack-1.schema.json`, with a `$comment` stating the rule. Unchanged schema ⇒ unchanged `$id` across releases. | `main`-path URL (prior RQ1 — mutable, same class as the `blob/main` buildType URI); omit `$id` (SPDX 3.0.1 precedent, J5); GitHub Pages (none exists, E15) | JSON Schema core: `$id` is a canonical identifier that "need not be downloadable" (J2); immutability is the brief's requirement; the last-changing-release rule removes the churn the prior objected to. |
| RQ8 | Schema validation tooling | **CI-only**: `jsonschema==4.26.0` (PyPI latest, released 2026-01-07, full 2020-12 support, Python ≥3.10 — checked 2026-09-16) installed with `--require-hashes` from `.github/jsonschema-requirements.txt`, in the new `format-identity` job only; plus a **stdlib structural test** in the pytest matrix. | ship unvalidated; `check-jsonschema` CLI (prior RQ2); `ajv` via npm | Python stdlib has no validator (constraint 1). The cosign-interop precedent is "consumer-side tool, exactly pinned, this job ONLY". |
| RQ9 | Fourth fixture source | **Generate fresh** in a temp checkout with the unmodified HEAD engine (`--issue 996`, mirroring the Action's numbering), LF-normalize at freeze time (as the three existing fixtures evidently were: generated on this Windows box, zero CR bytes), assert `attestation*` checks are `ok`. | import the Action repo's `fixtures/v130` (same engine bytes, CRLF, issue 996, committed 2026-08-22) | Same cadence as v110/v122 (PLAN_v1.3.0 Phase 0 item 2). LF normalization is safe: `chain_hash` is over LF-normalized text and bundle bytes are never digest input (E2). |
| RQ10 | `.vscode/settings.json` in the plugin repo | **Reject** (departs from prior T3-4). Document the `files.associations` + `json.schemas` snippet for users instead. | include (prior) | Every repo byte ships to every plugin cache (marketplace pins the repo); the benefit is three fixture files for contributors, and workspace settings apply only when the plugin repo itself is the opened folder. |
| RQ11 | Skill text changes | **None** (departs from prior T3-5's run-skill tip). The `.gitattributes`/editor snippets live in README and `docs/media-type.md`. | one-line tip in the run skill's Phase-4 report | Zero token cost per run, zero `TestSkillContract` risk, zero footprint pressure; users configure repos where they read recipes (README, branch-protection). |
| RQ12 | "Proposed" vs "registered" wording | **One status ledger line** in `docs/media-type.md` with evergreen wording states (D11); every other surface uses the bare type name; a CI grep forbids "IANA-approved" / "approved by IANA" / "IANA-registered" / "official media type" repo-wide and allows "registered with IANA" only on the ledger line. | "proposed" adjective on six surfaces + grep (prior) | Fewer places to flip; nothing is ever false if IANA never answers; the flip is a one-line docs commit to `main`, no milestone needed. |
| RQ13 | Contact / change controller | **Ryan Michie personally**, "Ryan Michie (ForgeProof project)" + repo URL (prior stands) | a project alias (none exists) | CycloneDX ("Patrick Dwyer, on behalf of CycloneDX") and Syft ("Dan Nurmi, on behalf of Anchore") precedents (I2). RFC 6838 §5.5: the owner may transfer by informing IANA; the IESG may reassign if the author is unreachable (R12) — durability is adequate. |
| RQ14 | "Published specification" URL | `https://github.com/ryanjmichie-git/forgeproof-plugin/blob/v1.4.0/skills/run/references/rpack-format.md` (tag-pinned) + "latest revision: same path on `main`" | repo root; `main` path only (Syft does this — I2) | Immutable per the brief; all registered supply-chain precedents cite a specific document (I2). |
| RQ15 | Upstream shared-mime-info / `file` submissions | **After IANA confirms**, maintainer action, not a release deliverable; each needs Ryan's sign-off on final text (prior stands; the brief's "deferred to v2.0.0" summary is re-stated as "after confirmation") | submit now with an unregistered type | CONTRIBUTING: "IANA registered mime-types when possible"; "When old mime-types become registered, the new definition should include an alias" (M6) — submitting first invites alias churn. |
| RQ16 | Emission profile normativity | **MUST for the reference producer (`finalize`), SHOULD for other producers; never binding on verifiers.** Window: `format` within the first **256 bytes**. | MUST for all producers; no clause | E1–E3: the byte prefix is an emission property; a MUST on all producers would make `jq`-reformatted (still valid) documents non-conforming *producers*. 256 is the upstream JSON-subtype idiom (M3) and the reference writer sits at byte 26/28. |
| RQ17 | ASCII / CRLF / BOM normative decisions | Encoding **UTF-8 without BOM** (RFC 8259 §8.1, R8); reference producer emits pure ASCII (documented, not required); **LF or CRLF both permitted**, not significant; registration "Encoding considerations: **binary**" | require ASCII; require LF | The IANA form itself: "If the format is based on JSON or XML, 'binary' should generally be selected due to the possibility that lines could be longer than 998 octets" (I4) — the base64 DSSE payload is one multi-kilobyte line. Verifiers already tolerate a BOM (`utf-8-sig`, `:85`) — tolerated by consumers, forbidden for producers. |
| RQ18 | Tier 2 window and priority | XML: `{` at 0 + spaced/compact `"format"` match at `offset="1:256"`, `priority="80"`, `sub-class-of application/json`; magic: `{` guard + two `search/256` continuation lines | wider windows (4096) to catch sorted re-serializations; `regex` | Upstream idiom (`application/schema+json`, M3) and "Magic offset must be as small as possible" (M6). `regex` is not a shared-mime-info match type (M2) and is "discouraged" in magic(5) (M8). Both drafts are **tested** (Appendix B evidence). |

### Open questions (not decidable from evidence; each has a test or a fallback)

| # | Question | How it resolves |
|---|---|---|
| OQ1 | Does `linguist-language=JSON` change GitHub's **diff** highlighting, or only file-view highlighting? The overrides doc promises "Highlighted and classified as name" and only `linguist-generated` mentions diffs (L2). | User-layer test in a scratch repo (Phase 4); README wording says "renders as JSON" and adds "and diffs" only if observed. |
| OQ2 | Will the IANA reviewer accept an "Interoperability considerations" field that names two unregistered conventional types, and a "File extension(s)" note about the game-archive collision? | Submit as drafted; revise on reviewer feedback (RFC 6838 §5.3: returned for revision, not rejected). Every downstream surface uses the bare name, so a forced rename touches strings only (D3). |
| OQ3 | Is `gio` (libglib2.0-bin) preinstalled on `ubuntu-latest`? | Phase 3: `apt-get install -y --no-install-recommends shared-mime-info libglib2.0-bin file` unconditionally; print versions. |
| OQ4 | Upstream shared-mime-info's appetite for a single-project vendor type. CONTRIBUTING admits "visible to end users but only used by one application" (M6). | Post-IANA; Ryan decides whether to submit at all. |
| OQ5 | filext.com attributes `.rpack` to Red Dead Redemption 2 (P4) — contradicted by its own sample data (`RP6L` = Dying Light) and every other source. | Treated as a false attribution; not cited. |

---

## 2. Context — summary and strategic framing

**Thesis link.** ROADMAP's thesis is "attest the work": a verifiable record that becomes infrastructure. Infrastructure has names. Today the industry's attestation vocabulary — `application/vnd.in-toto+json`, `application/vnd.dev.sigstore.bundle.v0.3+json`, SLSA's `predicateType` — is entirely **conventional**: none is registered with IANA (I1), SLSA's own request for a media type has been open since 2023 (I7), and in-toto's maintainers call registration something that "might even be worthwhile" (I7). The vocabulary of this field is still being formed, and formats get named by whoever names them first: `file(1)` says `application/json` for a bundle today, a Linux file manager says `text/plain` (E7), GitHub says nothing. Whichever string the first registrant chooses is what tools will print for the next decade (vocabulary path-dependence). The `.rpack` extension is already informally shared with a game archive that no registry claims (P1–P3); the first registrant sets the default without precluding the other.

**What this workstream buys.** A normative specification with a stability statement (the thing everything else cites), a published schema, detection definitions that a desktop or a CI job can adopt, and a proposed vendor-tree media type — all without changing one bundle byte.

**Where format identity explicitly does *not* matter — and the plan says so everywhere:**
- **GitHub rendering.** `raw.githubusercontent.com` serves `.rpack`, `.json`, and `.md` alike as `text/plain; charset=utf-8` (checked 2026-09-16). Registration changes nothing there; a `.gitattributes` `linguist-language=JSON` line is what changes rendering (L2).
- **Verification.** Bytes are never digest input. Six re-serializations of the v1.2.2 fixture (sorted keys, compact, CRLF, tab-indent with raw Unicode, UTF-8 BOM) verify green under `--strict` with zero errors and zero warnings (E2).
- **Trust.** "Other than IETF registrations in the standards tree, the registration of a media type does not imply endorsement, approval, or recommendation by the IANA or the IETF or even certification that the specification is adequate" (RFC 6838 §4.10, R7). `vnd.` signals vendor-specific by design. Registration is a name.

---

## 3. Research findings (verified 2026-09-16)

### 3.1 Engine and repo — empirical (each confirmed directly, not taken from the brief)

| # | Fact | Evidence | Consequence |
|---|---|---|---|
| E1 | The writer assembles an insertion-ordered dict `version, format, issue, requirements, artifacts, decisions, evaluation, chain_hash, public_key`, then `attestation` (`:1523`), `root_digest` (`:1527`), `signature` (`:1530`), and writes `json.dumps(bundle, indent=2) + "\n"` (`forgeproof.py:1491-1535`). | All three fixtures and the Action's v130 fixture begin `{\n  "version": …,\n  "format": "forgeproof-rpack",`; `"format"` at byte 26 (LF). Nothing asserts key order. | The byte prefix is an **emission** property. |
| E2 | `root_digest` = SHA-256 of `canonical_json` (sorted keys, `(",", ":")`, `ensure_ascii` default) — writer `:1526`, verifier denylist `:1873-1874`. | Experiment: v122 fixture deployed six ways — original; `sort_keys` indent; `sort_keys` compact no newline; CRLF; tab-indent `ensure_ascii=False`; BOM-prefixed. **All six: exit 0, `verified: true`, `errors: []`, `warnings: []` under `--strict`.** `"format"` sat at byte 26 / 573 / 435 / 28 / 24 / 29 respectively. | Validity is over parsed content; detection is best-effort on non-profile layouts. |
| E3 | `rpack_path.write_text(...)` passes no `encoding`/`newline` (`:1535`; contrast the sidecars `:1542-1545`). | Probe on this box: bytes `{\r\n  "version"…`, `"format"` shifts 26 → 28. The companion Action's committed `fixtures/v130/issue-996.rpack` is a **real CRLF bundle** (55 CR bytes, generated on `User@PC-951318` 2026-08-22, engine 1.3.0) — a live witness. The plugin's three fixtures are LF (0 CR) although generated on the same Windows box: normalized at freeze time. | Fixed-offset rules fail on Windows-authored bundles; use windows. |
| E4 | `ensure_ascii` is never passed anywhere in the engine. | Probe: a title `é ünïcode ✓` → pure ASCII file. `canonical_json` shares the default, so **digest input escapes non-ASCII** — part of the canonical form the spec must state. | Encoding: UTF-8 (in practice ASCII). |
| E5 | SSHSIG verification shells out (`run([... "ssh-keygen", "-Y", "verify" ...])`, `:196-202`; `run` = `subprocess.run`, `:124-133`); `FileNotFoundError` appears nowhere in the file. | With `ssh-keygen` removed from `PATH`, `verify` dies with `FileNotFoundError: [WinError 2]` traceback. `cmd_preflight` checks `shutil.which("ssh-keygen")` (`:652-656`) but `verify` alone does not. | Public text must say "stdlib **plus** `ssh-keygen`"; the actionable-error fix is deferred (triage). |
| E6 | `file(1)` runs its built-in JSON detector before soft magic: `file_is_json` → `checkdone` → `goto done` unless `MAGIC_CONTINUE` (`src/funcs.c`); no `Magdir/json` exists (M9). | Local `file-5.46`: bundle → `application/json` / "JSON text data"; with `-e json` → falls through to soft magic. A BOM-prefixed file bypasses the built-in (its parser rejects a BOM). | A libmagic rule is reached only with `-e json` / `-k`; documented, asserted in CI. |
| E7 | Linux desktop baseline (GLib via PyGObject on WSL Ubuntu 22.04, shared-mime-info 2.1): `.rpack` name+data → `text/plain`; name-only → `application/octet-stream`. | With the draft XML compiled into an isolated `XDG_DATA_HOME`: every `.rpack`-named layout → `application/vnd.forgeproof.rpack+json`; content-only sniff: LF and CRLF → ours, sorted/compact → `text/plain`; `is_a application/json` → True; description "ForgeProof provenance bundle". Full matrix in Appendix B. | The XML works as drafted; the limitation boundary is exactly the emission profile. |
| E8 | `.rpack` is hard-coded at `forgeproof.py:911, 1376, 2284-2287, 2525, 2547-2549, 2623` (init `--force`, finalize, summary, reset ×2, gate glob), in `skills/verify/SKILL.md:32,147`, `skills/push/SKILL.md:49-58`, `skills/run/SKILL.md:236-248`, `hooks/hooks.json:2`, the Action's `bundle` input default `.forgeproof/*.rpack` (`action.yml:13-15`, live), three fixture filenames. | 660 occurrences repo-wide. | Extension change = cross-repo compatibility event (D4). |
| E9 | `FORGEPROOF_BUILD_TYPE` = `…/blob/main/skills/run/references/rpack-format.md#slsa-buildtype-v1` (`:1170-1172`) is sealed into every attestation (`:1229`). | Mutable ref, frozen target. | The spec's **path and that heading are frozen forever** (constraint 7); paperwork must not move the file. |
| E10 | The run skill lists `rpack-format.md` as reference material (`skills/run/SKILL.md:263-268`). | Bytes added to the spec may be loaded during runs. | Registration paperwork goes to `docs/media-type.md` (D7). |
| E11 | The Action's `sync-check` fetches the engine at `UPSTREAM.ref` (`ac9da9b8…`, 2026-08-15) and compares fetched, recorded, and vendored sha256 (`forgeproof-verify/.github/workflows/ci.yml:15-35`). `ac9da9b8` is an ancestor of HEAD and its engine is byte-identical to HEAD (`git diff --stat` empty; sha256 `f713f3e9…` both). | A `PLUGIN_VERSION`-only bump cannot turn the Action red. | Re-vendor is optional (RQ3). |
| E12 | Tests: 290 collected (README's "290 automated tests" is current); compat classes `TestV101Compat:1888`, `TestV110Compat:2088`, `TestV122Compat:2250` deploy into `tmp_path/.forgeproof/` + `src/` and `monkeypatch.chdir`; `test_fixture_is_byte_exact` asserts no CR; `warnings == []` is asserted only in the shared attestation test (`:2072-2073`); `TestVersionAndFormat:4051`. | Patterns to mirror for `TestV130Compat`. | — |
| E13 | Bundles already carry two other formats' strings: `DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"`, `SIGSTORE_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"` (`:492-493`). Attestation shape: `mediaType`, `verificationMaterial` = `{"publicKey": {}}`, `dsseEnvelope{payload, payloadType, signatures[{sig}]}` (Action v130 fixture). | — | Scope decision D6; schema `$defs` (Appendix C). |
| E14 | Every number in every bundle is an integer; `requirement_coverage` is a string (`"100%"`); no floats (fixtures + Action v130). | — | The canonical-form clause can forbid non-integer numbers (float formatting is implementation-defined). |
| E15 | `raw.githubusercontent.com` → `text/plain; charset=utf-8` for `.rpack`, `.json`, `.md`; repo `has_pages: false`, `ryanjmichie-git.github.io/forgeproof-plugin` → 404. | — | Registration changes nothing on GitHub; no Pages hosting for `$id`. |
| E16 | Privacy: all three fixtures' `public_key` comment is `User@PC-951318`; PRIVACY.md's bundle table (`:143-154`) lists issue metadata, paths, decisions, public-key comment, approver email — but **not timestamps**, which the chain and the attestation's `startedOn`/`finishedOn` (`:1244-1246`) carry. | — | Security-considerations text lists timestamps; PRIVACY.md gains a row (T3-5). |

### 3.2 RFCs (rfc-editor.org plain-text editions, checked 2026-09-16)

| # | Source | Governing sentence (verbatim) | Use |
|---|---|---|---|
| R1 | RFC 6838 §3.2 — https://www.rfc-editor.org/rfc/rfc6838.txt | "'Vendor' and 'producer' are construed very broadly in this context and are considered equivalent. Note that industry consortia as well as non-commercial entities that do not qualify as recognized standards-related organizations can quite appropriately register media types in the vendor tree." / "Registrations in the vendor tree may be submitted directly to the IANA, where they will undergo Expert Review [RFC5226] prior to approval." | D1 |
| R2 | RFC 6838 §3.3 | "Registrations for media types created experimentally or as part of products that are not distributed commercially may be registered in the personal or vanity tree." | D1 (rejects `prs.`) |
| R3 | RFC 6838 §4.2 | ABNF: `restricted-name = restricted-name-first *126restricted-name-chars`; "Characters before first dot always specify a facet name"; "Characters after last plus always specify a structured syntax suffix"; names "SHOULD be limited to 64 characters". No rule on version tokens in subtype names (all five "version" hits in the RFC are unrelated). | D1 |
| R4 | RFC 6838 §4.4 (full) | "All registered media types MUST employ a single, canonical data format, regardless of registration tree." / "The specifications of format and processing particulars may or may not be publicly available for media types registered in the vendor and personal trees. … references to or inclusion of format specifications in registrations is encouraged but not required." | D9: "canonical data format" = one data model (the parsed JSON object), distinct from ForgeProof's digest canonicalization; the spec is published anyway. |
| R5 | RFC 6838 §4.2.8 | "Media types that make use of a named structured syntax SHOULD use the appropriate registered '+suffix' for that structured syntax when they are registered." / "'+suffix' constructs for as-yet unregistered structured syntaxes SHOULD NOT be used". §4.11: types with a registered suffix "MUST follow whatever fragment identifier rules are given in the structured syntax suffix registration." | D2 |
| R6 | RFC 6838 §4.6 (full) | "the security considerations MUST NOT state that there are 'no security issues associated with this type'" / "all known security risks MUST be identified in the registration of a media type, again regardless of registration tree." Checklist: active content; information disclosure / privacy; compression; need for external integrity/confidentiality services. | Appendix A |
| R7 | RFC 6838 §4.10 (full) | "RFC publication of vendor and personal media type registrations is allowed but not required." / "the registration of a media type does not imply endorsement, approval, or recommendation by the IANA or the IETF or even certification that the specification is adequate." | §2, constraint 3 |
| R8 | RFC 6838 §4.8; RFC 8259 §11, §8.1 — https://www.rfc-editor.org/rfc/rfc8259.txt | §4.8: "binary: The content consists of an unrestricted sequence of octets." RFC 8259 application/json: "Encoding considerations: binary"; "Magic number(s): n/a". §8.1: "JSON text exchanged between systems that are not part of a closed ecosystem MUST be encoded using UTF-8"; "Implementations MUST NOT add a byte order mark (U+FEFF) to the beginning of a networked-transmitted JSON text … implementations that parse JSON texts MAY ignore the presence of a byte order mark". | RQ17 |
| R9 | RFC 6838 §4.12 (Additional Information; the brief's "§4.11" is Fragment Identifier Requirements) | "Magic numbers are byte sequences that are always present at a given place in the file and thus can be used to identify entities as being of a given media type." Optional: file extensions, Mac OS file type codes. | Appendix A "Magic number(s)" |
| R10 | RFC 6838 §5, §5.1–5.3 | §5: "not a formal standards process, but rather an administrative procedure". §5.1: list review for non-standards trees "is entirely OPTIONAL, but is strongly encouraged." §5.2: vendor/personal "are submitted directly to the IANA"; form `http://www.iana.org/form/media-types`. §5.3: "Registrations that do not meet these requirements will be returned to the submitter for revision." **No review duration appears anywhere in RFC 6838 or 4288**; the "two-week" figure exists only in obsolete RFC 2048 — not cited. | Phases; risk 1 |
| R11 | RFC 6838 §5.6 | Registration template quoted in full (Type name … Provisional registration?). "'N/A', written exactly that way, can be used in any field". | Appendix A |
| R12 | RFC 6838 §5.5 | "the owner may request a change to its definition … The same procedure that would be appropriate for the original registration request is used"; "Media type registrations may not be deleted"; "The owner of a media type may pass responsibility to another person or agency by informing the IANA"; "The IESG may reassign responsibility … where the author of the registration has died, moved out of contact". | RQ13 |
| R13 | RFC 6839 §3.1 — https://www.rfc-editor.org/rfc/rfc6839.txt; live suffix registry (https://www.iana.org/assignments/media-type-structured-suffix/structured-syntax-suffix.csv, "Last Updated: 2026-06-25") | RFC text: "The suffix '+json' MAY be used with any media type whose representation follows that established for 'application/json'." Fragment identifiers: "SHOULD be as specified for 'application/json'. (At publication of this document, there is no fragment identification syntax defined for 'application/json'.)" The **live registry** now cites `[RFC8259][RFC6839]` with "JSON is encoded using UTF-8, and is binary data." | D2; Appendix A fragment/encoding fields |
| R14 | RFC 6901 §6 — https://www.rfc-editor.org/rfc/rfc6901.txt | "a given media type needs to specify JSON Pointer as its fragment identifier syntax explicitly (usually, in its registration [RFC6838]) … the fragment identifier syntax for application/json is not JSON Pointer." RFC 6901 registers nothing (no IANA section). | D2: JSON Pointer not adopted |
| R15 | RFC 8259 §12, §9, §4, §6 | §12: `eval()` "generally constitutes an unacceptable security risk" (the section ends there; no "safe alternative" sentence exists). §9: implementations "may set limits on the size of texts … maximum depth of nesting … range and precision of numbers". §4: "The names within an object SHOULD be unique." §6: integers in `[-(2**53)+1, (2**53)-1]` are interoperable. | Appendix A security text |

### 3.3 IANA registry and form (checked 2026-09-16)

| # | Source | Finding |
|---|---|---|
| I1 | https://www.iana.org/assignments/media-types/application.csv (full CSV, 1,800 rows, registry "Last Updated 2026-09-14"); per-type template URLs; provisional registry (49 rows — *corrected 2026-09-20:* **26 rows**, CSV at https://www.iana.org/assignments/provisional-standard-media-types/provisional-standard-types.csv; none of the terms; finding unchanged) | **Not registered:** `rpack`, `forgeproof`, `in-toto`, `intoto`, `sigstore`, `dsse`, `slsa`. Only substring hit for "rpack": `vnd.cirpack.isdn-ext`. Template URLs for `vnd.in-toto+json`, `vnd.dev.sigstore.bundle.v0.3+json` (and the `+json;version=` forms) → 404; controls (`vnd.cyclonedx+json`, `vnd.oci.image.manifest.v1+json`) → 200. `provenance` hits: `provenance+xml` (W3C PROV), `vnd.cncf.helm.chart.provenance.v1.prov`; `attestation`: `vnd.verifier-attestation+jwt`. |
| I2 | Same CSV + template pages | Precedents: `vnd.cyclonedx+json` (vendor; "Author/Change controller: Patrick Dwyer, on behalf of CycloneDX"); `vnd.syft+json` ("Dan Nurmi, on behalf of Anchore"; "Published specification: … https://github.com/anchore/syft/blob/main/schema/json" — a mutable-ref precedent, not followed); `spdx+json`, `spdx3+json` (standards, Linux Foundation); `sarif+json` (OASIS); `vnd.oci.image.manifest.v1+json` (single-integer `.v1`). Thirteen registered names carry `.v<digit>`; **none** carries a two-component `v0.3`. `vnd.oci.image.index.v1+json`, `vnd.github+json`, `vnd.docker.*` are **not** registered. |
| I3 | Suffix registry | `+json` row: `[RFC8259][RFC6839]`, registered 2012-11-27. `+dsse` is **not** a registered suffix (`+jws` is). |
| I4 | https://www.iana.org/form/media-types (server-rendered HTML) | Fields in order: contact name/e-mail; Type Name; Subtype (Vendor/Standards/Personal + name, maxlength 60); Required/Optional parameters; Encoding (7-bit/8-bit/binary/framed + notes); Security; Interoperability; Published specification; Application usage; Fragment identifier; Restrictions; Provisional (Yes/No); Additional info (deprecated alias, magic, ext, filecode, **OIDs**); Intended usage (COMMON/LIMITED USE/OBSOLETE + text); Other comments; Author/Change controller (name, e-mail, text). Quoted rules: "If the format is based on JSON or XML, 'binary' should generally be selected due to the possibility that lines could be longer than 998 octets." / "All media type registrations must describe their security considerations; simply saying there are none or leaving the section blank is unacceptable." / "(4) If the media type uses an existing format, e.g. XML or JSON, the security considerations for that format must be referenced" / "Vendor-tree and personal-tree requests must select 'No'" for provisional. **No review-time figure anywhere.** |
| I5 | https://www.iana.org/assignments/media-types/media-types.xhtml | "Registration Procedure(s): Expert Review for Vendor and Personal Trees"; experts Alexey Melnikov, Darrel Miller, Murray Kucherawy; updates to iana@iana.org. |
| I6 | in-toto `spec/v1/envelope.md` (raw, main); Sigstore `protos/sigstore_bundle.proto` (raw, main) | "`payloadType` MUST be set to `application/vnd.in-toto.<predicate>+json` or to `application/vnd.in-toto+json`." Sigstore: "MUST be application/vnd.dev.sigstore.bundle.v0.3+json when encoded as JSON"; legacy `…bundle+json;version=0.1/0.2/0.3` must be accepted. `statement.md` itself contains no media-type sentence. |
| I7 | GitHub issues via `gh api` | in-toto/attestation#271 (closed): "It might even be worthwhile to register the `application/vnd.in-toto` mediaType"; slsa-framework/slsa#933 (**open** since 2023-07-31): "It would be useful if SLSA had a mediaType … ideally registered with IANA." Zero IANA mentions in sigstore/protobuf-specs, sigstore/sigstore, secure-systems-lab/dsse. |
| I8 | IETF media-types list archive | **UNVERIFIED** — mailarchive.ietf.org returns a Cloudflare challenge (403) to curl, WebFetch, and its API. Absence of a pending list post could not be confirmed. *Updated 2026-09-20:* **recent weeks verified, archive search 403** — https://mailarchive.ietf.org/arch/browse/media-types/ now answers HTTP 200 (covers 2026-08-28 → 2026-09-16; zero hits for the terms); the archive-wide search still returns 403, so the longer-range claim stays unverified. |

### 3.4 Detection ecosystems (checked 2026-09-16)

Provenance caveat: `gitlab.freedesktop.org` is behind an Anubis proof-of-work wall for every route (raw, API, fetch tool). The shared-mime-info repository files were read from the GitHub mirror `AOSC-Tracking/shared-mime-info` @ upstream commit `eb8305ef` (2026-03-29, post-2.4 master), whose tree SHA matches an independent frozen mirror byte-for-byte; possible lag vs. today's upstream ≤ ~5.5 months. *Corrected 2026-09-20:* the "every route" statement is out of date — on 2026-09-20 the REST API answered a `curl` user-agent, `…/-/merge_requests/<iid>/discussions.json` returned reviewer comments unauthenticated, and `git ls-remote`/`fetch` worked (REST `/notes` returned 401). The lag caveat is closed: upstream HEAD is `433be9a` (2026-09-10). The rendered spec was fetched directly from specifications.freedesktop.org.

| # | Source | Finding (verbatim where it matters) |
|---|---|---|
| M1 | Spec §glob — https://specifications.freedesktop.org/shared-mime-info-spec/latest/ar01s02.html (v0.21, 2018) | "There is also an optional weight attribute … The default weight value is 50, and the maximum is 100." Globs are matched case-insensitively unless `case-sensitive="true"`. |
| M2 | Spec §magic/match | `type`: "string, host16, host32, big16, big32, little16, little32 or byte." — **no `regex`** (database census: string 1345, regex 0). `offset`: "This may be a single number or a range in the form `start:end', indicating that all offsets in the range should be checked. The range is inclusive." `value` for strings "supports the C character escapes (\0, \t, \n, \r, \xAB for hex, \777 for octal)". Nesting: "<a><b/><c/></a> means 'a and (b or c)'". `priority` default 50, max 100. |
| M3 | `data/freedesktop.org.xml.in` (mirror) | `application/json`: `<sub-class-of type="application/json5"/>`, `<glob pattern="*.json"/>`, **no `<magic>`** (test list: `json_object.json application/json ox` — data lookup expected to fail). JSON-subtype idiom: `application/schema+json` = `<magic priority="80"><match type="string" value="{" offset="0"><match type="string" value="&quot;$schema&quot;:" offset="1:256"/></match></magic>`; `application/x-ipynb+json` same shape with `"cells":`. Range-offset precedent: `%PDF-` at `offset="0:1024"`. |
| M4 | Same file, full search | `rpack` occurs only inside `*.mrpack` (Modrinth). **No `.rpack` glob upstream.** |
| M5 | Spec §install; xdg-utils `xdg-mime.in` (mirror) | "Each application that wishes to contribute to the MIME database will install a single XML file, named after the application, into one of the three `<MIME>/packages/` directories … the application MUST run the update-mime-database command". User scope: `$XDG_DATA_HOME/mime/packages/` (default `~/.local/share/mime/packages/`) then `update-mime-database ~/.local/share/mime`; `xdg-mime install --mode user FILE`. Generated: `globs2`, `magic`, `subclasses`, `mime.cache` (mmappable). **`xdg-mime query filetype` on a non-desktop session falls through to `file --mime-type` (libmagic)** unless Perl `File::MimeInfo` is installed — CI must query through `gio info` (GLib reads `mime.cache`). |
| M6 | `CONTRIBUTING.md` (mirror) | "A file type which is visible to end users but only used by one application is still useful to have in a shared database." / "Mime-types used should be IANA registered mime-types when possible" / "When old mime-types become registered, the new definition should include an alias for the old mime-type" / "Magic offset must be as small as possible." / "Merge requests are required for new mime-types and should include one or more test files". Test list syntax: `<filename> <expected mimetype> [NDF]` with `x`/`o` per name/data/file lookup. |
| M7 | magic(5) — https://man.archlinux.org/man/magic.5.txt (file 5.48), cross-checked against upstream `doc/magic.man` (the man7 `man5` URL is 404; man7 hosts it as `man4/magic.4`) | `search`: "The search expression must contain the range in the form /number, that is the number of positions at which the match will be attempted, starting from the start offset." `regex`: "their use is discouraged … The 'l' modifier, changes the limit of length to mean number of lines instead of a byte count … If neither a byte or line count is specified, the search is limited automatically to 8KiB." `!:mime MIMETYPE` "must be the next non-blank or comment line after the magic line that identifies the file type"; `!:ext ext[/ext…]`; `!:strength OP VALUE`. Text tests (`search`/`regex`) run after binary tests. **Empirically** (file-5.46): `regex/16` never fires (16 = bytes), `regex/1024` and default fire on all layouts; `search/64` fires at bytes 26/28 only. |
| M8 | file/file `README.md` (raw, master @ `5e57b94c`, 2026-08-28) | Submissions: bug tracker bugs.astron.com, `file@astron.com`, GitHub. Bar: "Initial match is preferably at least 32 bits long, and is a _unique_ match" / "Match of <= 16 bits are not accepted" / "Provide complete information with entry: One line short summary … File extension … Full name and contact method … Further reference". |
| M9 | `src/funcs.c`, `src/is_json.c` (raw, master) | Order in `file_buffer()`: encoding → apptype → compress → tar → **json** → csv → simh → cdf → elf → **soft** → ascmagic. `if (m) { if (checkdone(ms, &rv)) goto done; }` — `checkdone` returns 1 unless `MAGIC_CONTINUE`. `is_json.c` prints `application/json` / "JSON text data"; nesting limit 500. `Magdir/json` does not exist. |
| M10 | Full `file/file` master tarball grep (359 Magdir files + whole tree) | Zero occurrences of `rpack`, `RP5L`, `RP6L`, `Techland`. |

### 3.5 Linguist, JSON Schema, Apple UTI, prior art (checked 2026-09-16)

| # | Source | Finding |
|---|---|---|
| L1 | linguist `CONTRIBUTING.md` (raw, main) | "at least 2000 files per extension or filename indexed in the last year … excluding forks, for extensions or filenames expected to occur more than once per repo" / "at least 200 files … for extensions or filenames expected to only occur once per repo" / "we do not accept PRs for very new or hobby languages". Method: GitHub code search `search?type=code&q=NOT+is%3Afork+path%3A*.<ext>` (web UI only; the REST API returns 0 even for their own example). |
| L2 | linguist `docs/overrides.md` (raw, main) | "`.gitattributes` will be used to determine language statistics and will be used to syntax highlight files." Table: `linguist-language=name` → "Highlighted and classified as name"; `linguist-generated` → "Excluded from stats, hidden in diffs". JSON is `type: data` → not counted unless `linguist-detectable`. **Diff highlighting is not explicitly promised** (OQ1). |
| L3 | `lib/linguist/languages.yml` (raw, main, 9,662 lines) | `.rpack` **absent**; `JSON` has `codemirror_mime_type: application/json`. |
| J1 | https://json-schema.org/specification; `/draft/2020-12/schema` | "The current version is *2020-12*!"; meta-schema `"$schema": "https://json-schema.org/draft/2020-12/schema"`. |
| J2 | `/draft/2020-12/json-schema-core` §8.2.1, §8.2.3 | "The '$id' keyword identifies a schema resource with its canonical [RFC6596] URI. Note that this URI is an identifier and not necessarily a network locator. In the case of a network-addressable URL, a schema need not be downloadable from its canonical URI." / `$id` "MUST resolve to an absolute-URI [RFC3986] (without a fragment)". |
| J3 | `/understanding-json-schema/structuring` | "it's recommended that you always use an absolute URI when declaring a base URI with `$id`." The brief's "a URL you control" sentence is **UNVERIFIED — absent** from the current page and from the doc's repository source. |
| J4 | SchemaStore `CONTRIBUTING.md` (raw, master) | "We recommend using the `draft-07` JSON schema version. Later versions of JSON Schema are not yet recommended for use in SchemaStore until IDE and language support improves"; self-hosted route: catalog `url` may point at a raw GitHub file (ory/hydra precedent); bar: "commonly used or has potential for broad uptake". |
| J5 | Precedents | in-toto `_type` `https://in-toto.io/Statement/v1` → 200 (redirects to the GitHub blob); SLSA `https://slsa.dev/provenance/v1` → 200 → `/spec/v1.1/provenance` ("will always resolve to the latest minor version"); CycloneDX `bom-1.6.schema.json`: draft-07, `$id` on its own domain, resolves; SPDX 3.0.1 `spdx-json-schema.json`: **2020-12, no `$id` at all**. None uses a tag-pinned raw GitHub URL. |
| U1 | developer.apple.com (UTI "Defining file and data types", archive "Declaring New Uniform Type Identifiers", `UTTypeJSON`) | "You declare new UTIs in the information property list (info.plist) file of a bundle. You can declare new UTIs in any of the following: Application bundles, Spotlight Importer bundles, Automator action bundles"; JSON-based proprietary formats set `UTTypeConformsTo` `public.json`; `public.json` "conforms to UTTypeText". **No app-less registration path exists.** |
| P1 | hhrhhr/rp5l (`README`, `rp5l_structure.h`), hhrhhr RP6L gist, aluigi `dying_light.bms` | "viewer and unpacker for techland's rpack archive"; header `quint32 magic; // RP5L`; `assert("RP6L" == r:read(4))`; QuickBMS `idstring "RP6L"` for "rpack and rpacz". Binary, zlib-compressed. |
| P2 | Qivex/rpack-extract, 12brendon34 tools, ZenHAX threads, file-extensions.org | Chrome Engine / C-Engine resource packs: Dead Island (+Riptide), Dying Light 1/2/Bad Blood/The Beast, Call of Juarez: Bound in Blood and Gunslinger, Sniper Ghost Warrior. `RP5L` and `RP6L` both primary-source-verified; no `RP7L` found. |
| P3 | IANA CSV (I1), shared-mime-info (M4), Linguist (L3), `file` Magdir (M10), fileinfo.com (404), file-extension.org/.info (no MIME field) | **No registry claim anywhere** for the game format. Byte 0: `R` (0x52) vs ForgeProof `{` (0x7B) — disjoint with a one-byte test. |
| P4 | filext.com | Attributes `.rpack` to "RDR2" while its own sample data names `RP6L` and Dying Light — **UNVERIFIED / contradicted**; other non-Techland uses found are only `*.rpack.json` / `*.rpack.yaml` compounds and unrelated projects named "rpack". |

### 3.6 Priors from the 2026-09-05 draft — re-validated

| Prior decision | Did v1.3.0 / new evidence change it? | Stands? |
|---|---|---|
| Vendor tree, `application/vnd.forgeproof.rpack+json` | No; R1–R5, I2 confirm | **Stands** (RQ4) |
| Never embed the media type in bundle bytes | No; denylist unchanged (`:1873`), E2 | **Stands** (RQ5) |
| Keep `.rpack`, no alias | No; Action default confirmed live, P1–P3 | **Stands** (RQ6) |
| Upstream shared-mime-info / libmagic submissions after IANA confirmation | No; M6 confirms the alias-churn rationale | **Stands** (RQ15) |
| Linguist upstream dropped | Threshold re-confirmed (2000 / 200 per year, L1) | **Stands** |
| Apple UTI dropped | U1 confirms bundle-only declaration | **Stands** |
| Schema `$id` = `main`-path raw URL (prior RQ1) | Re-opened by the brief; J2 (identifier, need not be downloadable) makes tag-pinning free of the objection | **Changed** → RQ7 |
| `check-jsonschema` CI-only (prior RQ2) | Same principle; simpler to pin the library directly | **Stands in spirit** → RQ8 |
| `.vscode/settings.json` in the plugin repo (prior T3-4) | Ships to every user's plugin cache | **Changed** → RQ10 |
| Run-skill one-line tip (prior T3-5) | Token cost, skill-contract risk | **Changed** → RQ11 |
| "proposed" adjective on six surfaces + grep | Simplified | **Changed** → RQ12 |
| Fold into keyless v1.4.0 + new "Cross-cutting workstreams" ROADMAP section | Both premises refuted (E11; verificationMaterial opaque); an independent second opinion reached the same conclusion | **Changed** → RQ1 |
| Fixed offsets "27 (LF) / 29 (CRLF)" in the XML comment vs "37/39" in finding 2 | Measured: `"format"` at 26/28, the value `forgeproof-rpack` at 37/39 — both numbers described different things; neither is load-bearing | Corrected in Appendix B |
| "Inference, not verified: a bundle larger than the 1 MiB default read cap would fall through to soft magic" | Not needed by any decision | Dropped |

---

## 4. Hard constraints

1. **No new runtime dependency** for the engine, verifier, hooks, or skills (Principle 2). CI-only tooling is permitted under the `cosign-interop` precedent (`ci.yml:70-99`: consumer-side tools "in this job ONLY", installer pinned by 40-char SHA, binary version pinned exactly) and must be exactly pinned where the ecosystem allows (pip: hash-pinned requirements; apt packages: version printed in the log, deviation stated).
2. **Bundle compatibility is forever** (Principle 1). Every 1.0.0-format `.rpack` (v1.0.x–v1.2.x) and every 1.1.0-format bundle (v1.3.0) verifies with zero errors and zero warnings, `--strict` included, on every CI platform — now against **four** frozen fixtures. **No item in this plan touches bundle bytes, `root_digest` input, `canonical_json`, or `KNOWN_RPACK_VERSIONS`.** Anything that would is a blocker; none is proposed (the `mediaType`/`$schema` members were considered and rejected — triage).
3. **Honest claims** (Principle 3). No document may imply that registration confers trust, security, endorsement, review, or standardization. The phrase "IANA-approved" never appears; a CI grep enforces the forbidden list (RQ12).
4. **Wording states** are exact (D11); nothing claims registration until IANA confirms.
5. **Version discipline.** `.claude-plugin/plugin.json` and `PLUGIN_VERSION` change only in the release commit, as the final step.
6. **Plan mode.** Nothing in this document is implemented in this session.
7. **The spec's path and anchor are frozen**: `skills/run/references/rpack-format.md` and its heading `## SLSA buildType v1` (anchor `#slsa-buildtype-v1`; *corrected 2026-09-20:* the heading in the file is, and always was, third-level — `### SLSA buildType v1` — with the same anchor) are sealed into every attestation's `buildType` (E9). A test guards both.
8. **Zero footprint.** PRIVACY.md `:96-100`: ForgeProof does not write outside the project root and system temp. The plugin never installs MIME definitions, never runs `update-mime-database`/`xdg-mime`, never writes `.gitattributes` or editor settings into a user's repo. Detection files ship as opt-in artifacts with a manual recipe only.
9. **Ryan signs off every external submission** (IANA form text, any upstream MR or e-mail, and every reply in their review loops) before it is sent.
10. **Engine untouched** except the release-commit `PLUGIN_VERSION` bump and the `:530` docstring renumber; single-file engine; `test_engine_source_has_no_shell_isms` unchanged.
11. **Skills untouched**; `TestSkillContract` floor unchanged.
12. **`.rpack` stays**; the Action stays; `hooks/hooks.json` stays byte-identical.

---

## 5. Summary

v1.4.0 gives the `.rpack` bundle a name and a normative description without changing a single bundle byte. **Tier 3** promotes `skills/run/references/rpack-format.md` (in place — its path is sealed into every attestation) into the normative specification: a stability statement, a clear split between what is normative for *validity* (parsed content, the exact canonical serialization behind `root_digest`, the SSHSIG and DSSE checks) and what is normative for *emission* (bytes on disk: `version` then `format` first, UTF-8 without BOM, LF or CRLF), and the media type it will be known by. A JSON Schema 2020-12 for format 1.x is published at an immutable tag-pinned `$id`, permissive on unknown members and silent on version→member implications, validated in CI only. **Tier 2** ships a shared-mime-info definition and a libmagic rule under `share/` as opt-in files — tested here against every layout the engine and its users can produce, with the two honest limits stated up front (`file(1)` prints `application/json` unless told `-e json`; a key-sorted re-serialization escapes content sniffing but not the glob). A required `format-identity` CI job proves the schema and both detection files against all four frozen fixtures and a fresh bundle. **Tier 1** submits the vendor-tree registration of `application/vnd.forgeproof.rpack+json` after the tag, from the complete RFC 6838 §5.6 template in Appendix A, with security text that says exactly what a bundle proves (tamper-evidence under a self-attested key), what it discloses (paths, titles, `username@hostname`, approver e-mail, timestamps), and what verifying it requires (Python 3.11 stdlib **plus** `ssh-keygen`). One status ledger line records where the registration stands; everything else uses the bare name. Phase 0 freezes the fourth compat fixture from the v1.3.0 engine — the first with an attestation.

---

## 6. Design decisions (chosen option, alternatives, rationale, governing principle)

**D1 — Tree and name: vendor tree, `application/vnd.forgeproof.rpack+json`.** Alternatives: `prs.michie.rpack+json`; `vnd.forgeproof+json`; `vnd.forgeproof.rpack.v1+json`; a `version` parameter. Rationale: R1 admits non-commercial producers explicitly and ForgeProof is a distributed product with a marketplace listing, not an experiment (R2); both trees cost the same Expert Review, so `prs.` only signals "throwaway". `.rpack` in the subtype leaves room for a sibling type (e.g. the chain file) without renaming. No version token: Principle 1 makes the format additive forever and recognition membership-only ("no version implies any key", `forgeproof.py:46-49`), so the honest statement is *one media type for every revision whose `format` is `forgeproof-rpack`*; a `.v1` (OCI, I2) would make the bare name retroactively mean 1.x, and a `version` parameter (CycloneDX/Syft, I2) would invite consumers to dispatch on a value the engine deliberately treats as non-implicative. Principle 1, 4.

**D2 — `+json`, encoding `binary`, no fragment syntax.** `+json` is SHOULD-level (R5) and the suffix registry now cites RFC 8259 with "binary data" (R13); the IANA form's own guidance selects `binary` for JSON with lines over 998 octets (I4) — the base64 DSSE payload is one such line. Fragment identifiers: as for `+json` — none defined for `application/json` (R13); JSON Pointer is **not** adopted (R14 — a type must opt in explicitly; no consumer needs it). Principle 2 (no new semantics to implement).

**D3 — The media type is never embedded in bundle bytes.** Alternatives: add `mediaType` now (format 1.2.0); add it alongside a future additive change; add `$schema`. Rationale: any top-level member enters `root_digest` input for new bundles (E2) — a bytes-and-digest change whose only beneficiary already knows the format. `format` + `version` are the in-band identity, hard-errored by `verify` (`:1851-1857`) and required by the PR gate (`:2634`). Sigstore's wrapper carries `mediaType` because its bundle is versioned *by* media type (I6); ForgeProof is versioned by `version`. Carried externally: spec, `docs/media-type.md`, Appendix A, and `Content-Type` when the v2.0.0 MCP verify endpoint exists (the first `RPACK_MEDIA_TYPE` engine constant appears only then — a documentary string kept out of the engine never triggers an Action re-vendor). Editor validation, the one thing `$schema` would buy, is available through `json.schemas`/`files.associations` without an in-band member. A forced rename by the IANA reviewer therefore touches strings only. Principle 1.

**D4 — Keep `.rpack`; no alias.** Alternatives: `.rpack.json` / `.forgeproof.json`; dual globs. Rationale: E8 (six engine sites, three skills, the Action default, fixtures, every user repo); IANA registers media types, not extensions, so the Techland collision is irrelevant to Tier 1 and content-disjoint everywhere else (P3). Strongest counter-argument: `issue-N.rpack.json` would highlight as JSON on GitHub and in every editor with no `.gitattributes` at all. Why it loses: the extension has been public identity since v1.0.0 (marketplace description, Action glob, branch-protection recipes in the wild); a change means dual globs forever on six surfaces plus an Action release, for a collision that a one-byte content test resolves. Principle 1 (compatibility event avoided).

**D5 — The plugin never performs a local MIME registration.** Alternatives: the run skill runs `update-mime-database ~/.local/share/mime`; an opt-in `/forgeproof:install-mime` subcommand; ship the XML only. Rationale: PRIVACY.md's footprint contract is categorical (constraint 8); no ForgeProof workflow ever opens a `.rpack` from a file manager; the house precedent is warn-don't-write (the run skill warns about a missing `.gitignore` and never creates one). Files ship in-repo at XDG layout — `share/mime/packages/forgeproof-rpack.xml`, `share/magic/forgeproof` — with a documented manual recipe (Appendix B header comment; `docs/media-type.md`). A consent-gated opt-in is harmless but establishes a "ForgeProof writes to `~`" precedent that PRIVACY.md would then have to carve out. Principle 2.

**D6 — Scope: the type describes the outer `.rpack` only.** Confirmed with evidence: the DSSE `payloadType` is a MUST of the in-toto envelope spec (I6), the Sigstore `mediaType` a MUST of the bundle proto (I6); both are unregistered conventions (I1), so ForgeProof (i) references them as conventions in the Interoperability field, (ii) registers nothing on their behalf, (iii) cannot conflict with a future upstream registration because our type names a different object. The `.sigstore.json` sidecar *is* a Sigstore bundle (its own format); the `.pub.pem` sidecar is an SPKI PEM; the chain file is an internal working file that `verify` reads only if present and never needs to interchange — all out of scope. A chain-file schema is deferred (triage). Principle 4.

**D7 — Promote `rpack-format.md` in place; split the paperwork out.** Alternatives: move to `docs/` or `SPEC.md`; GitHub Pages; everything in the spec. Rationale: E9 freezes the path and anchor; E10 makes every added byte a per-run token cost. The spec gains only normative content (§7 T3-1); the registration template, status ledger, install recipes, editor snippets, and limitations go to a new `docs/media-type.md` (the `docs/cosign-interop.md` precedent for consumer-side recipes). Principle 2 (lean runtime surface).

**D8 — One schema for format 1.x, shallow on `attestation`, CI-validated.** Alternatives: one schema per format version; a deep Sigstore/DSSE schema; ship unvalidated. Rationale: a per-version schema would encode a version→member implication the engine rejects by design (PLAN_v1.3.0 finding 12). `attestation` is optional regardless of `version`, required to have the Sigstore-bundle shape **when present**, with `verificationMaterial` left untyped (owned by the Sigstore format; the keyless tier will populate it) — *corrected 2026-09-20:* the schema matches the **verifier**, not the producer's output: when present, `attestation` is required to have only the shape the reference verifier enforces (`dsseEnvelope`: `payloadType`, padded-base64 `payload`, exactly one signature object with a string `sig`); `mediaType` and `verificationMaterial` are described but neither required nor constrained, because the verifier reads neither and the spec forbids rejecting a document over them (Appendix C). Unknown members allowed at every level (additive forever). `$id` per RQ7; validation per RQ8; the stdlib structural test keeps the matrix honest without a validator. Principle 1, 2.

**D9 — Emission profile: MUST for the reference producer, SHOULD for others, never binding on verifiers.** Alternatives: MUST for all producers; no clause; fixed-offset magic. Rationale: E1–E4 and the six-way experiment: the byte layout is an emission property; the reference writer already conforms (`format` at byte 26/28) and a test pins it; the clause constrains producers and never the verifier or existing bundles, so it is compatibility-safe. RFC 6838 §4.4's "single, canonical data format" (R4) is satisfied by the one data model; ForgeProof's *digest* canonicalization is a separate, fully specified serialization. Detection keys on the profile: reliable for profile output, best-effort otherwise — stated verbatim in Appendix B and the spec. Principle 1.

**D10 — Milestone: a new minor, v1.4.0 "A name of its own".** See RQ1. Principle-neutral; governed by the SemVer policy ("minor = additive features") and "Order is firm; timing is not" (only labels shift; identity still precedes review precedes v2).

**D11 — Wording states and the single ledger.** The ledger line in `docs/media-type.md` is one of:
- **A (before submission):** "Media type: `application/vnd.forgeproof.rpack+json` (vendor tree). Registration status: not yet submitted."
- **B (submitted):** "… Registration status: submitted to IANA on YYYY-MM-DD; the IANA media types registry is authoritative for its status."
- **C (confirmed):** "… Registration status: registered with IANA on YYYY-MM-DD (https://www.iana.org/assignments/media-types/application/vnd.forgeproof.rpack+json)."
- **D (declined / renamed):** "… Registration status: request returned on YYYY-MM-DD; the type is used as an unregistered vendor-tree name" (or the replacement name and a dated note).
Every other surface (spec, README, XML `<comment>`, magic description, schema `title`, CHANGELOG, ROADMAP) uses the bare type name and may add "(vendor tree; status: docs/media-type.md)". Forbidden repo-wide, enforced by test: `IANA-approved`, `approved by IANA`, `IANA approved`, `IANA-registered`, `official media type`, `standardized media type`; `registered with IANA` allowed only on the ledger line. Principle 3.

---

## 7. Work items per tier (sequenced 3 → 2 → 1; T0 first)

**Whose repo, who writes (Principle 2 footprint decisions):**

| Item | Plugin repo | User's repo (`.forgeproof/issue-N.rpack` lands here) | Who writes it | Decision |
|---|---|---|---|---|
| `.gitattributes` `*.rpack linguist-language=JSON` | Yes — one line added (T3-3); the existing `fixtures/** -text` rule untouched | Documented snippet only | The user, by hand | **Document-only.** ForgeProof writes only `.forgeproof/` (run/SKILL.md:199-248); writing repo configuration on the user's behalf is never done. |
| Editor association (`files.associations`, `json.schemas`) | **No** `.vscode/` (RQ10) | Documented snippet | The user | Document-only |
| JSON Schema | `schemas/forgeproof-rpack-1.schema.json` | Referenced by URL only | — | n/a |
| Normative spec | `skills/run/references/rpack-format.md` (in place) | — | — | n/a |
| `docs/media-type.md` | Yes | — | — | n/a |
| `share/mime/packages/forgeproof-rpack.xml`, `share/magic/forgeproof` | Yes, opt-in files | **Never installed**; manual recipe | The user, by hand, outside any ForgeProof workflow | Never |
| Fourth fixture, tests, CI job | Yes | — | — | n/a |

Note on EOL: git EOL conversion of a user's `.rpack` does **not** break verification (E2 — canonical JSON is recomputed from parsed content), and the `.sigstore.json` sidecar is immune by construction (no newline characters at all), so **`-text` is not required for bundles in user repos**. The plugin repo keeps `fixtures/** -text` because its tests assert byte-exactness of the whole fixture directory, including the artifact whose SHA-256 covers raw bytes.

### T0 — Fourth compat fixture (Phase 0)

| | |
|---|---|
| Rationale | The established cadence (PLAN_v1.2.0 Phase 0 → v110; PLAN_v1.3.0 Phase 0 → v122): each release freezes the previous engine's output before any change. v1.3.0's output — format 1.1.0, the first with `attestation` — has no frozen witness in this repo (the Action repo holds one). The schema and detection acceptance tests need it. |
| Files | `skills/run/scripts/fixtures/v130/{chain-996.json, issue-996.rpack, src/example4.py}` — *corrected 2026-09-20:* the artifact as frozen is `src/example_v130.py` (the fixture-freeze tooling names it `example_<label>.py`; not renamed); `test_forgeproof.py` new `TestV130Compat` after `TestV122Compat` (`:2250`); `FIXTURE_V130` constant beside `:29-31`. |
| Procedure | Temp checkout at HEAD; `init --issue 996 --force --title "v130 fixture" --requirement "REQ-1: fixture requirement"` → `record` file-edit / decision / test-result / lint-result / **approval** (`--gate plan --decision approved`) → `finalize --issue 996 --commit <sha> --model <id>`; copy the three files; LF-normalize (`\r\n` → `\n`) the chain and the bundle (safe per E2/E3); artifact copied byte-exact. `.gitattributes` already covers the directory. |
| Acceptance | `TestV130Compat` mirrors V122 (`_deploy`, lenient + strict green, three tamper cases, `_require_sshkeygen` escalation, no-CR assertion) **plus**: `warnings == []` in both modes, `check("format").detail` contains `1.1.0`, and `attestation`, `attestation_signature`, `attestation_subjects` are all `ok` (first fixture where they are not `skipped`); a fourth tamper case flips one byte inside `attestation` → `root_digest` red. Fixture `public_key` comment and approver e-mail are Ryan's — acceptable (same as the three existing fixtures; noted in PRIVACY.md already) — *corrected 2026-09-20:* "same as the three existing fixtures" holds for the key comment only; v130 is the first fixture with an approval record, so the approver e-mail is new here (clear text in the chain, and inside the base64 DSSE payload of the bundle). The acceptance stands: the address is already public in `.claude-plugin/plugin.json` and the commit history, and PRIVACY.md documents the field. |
| Principle | 1 |

### Tier 3 — Developer surface (no gatekeepers)

**T3-1 — Promote `rpack-format.md` to the normative specification.**
- Rationale: the dependency for the emission clause (T2) and the "Published specification" field (T1); today it says "Version: 1.1.0" and documents the schema, but has no stability statement and never separates validity from bytes on disk.
- File: `skills/run/references/rpack-format.md` — **path and the `## SLSA buildType v1` heading unchanged** (constraint 7; *corrected 2026-09-20:* the real heading is `### SLSA buildType v1`, same anchor). Additions, in order: (1) *Status and stability* — "This document is the normative specification of the format. Format versions are additive; `KNOWN_RPACK_VERSIONS` membership; verifiers accept every historical version forever." (2) *Identity* — `format` const, `version`, media type name + pointer to the ledger (D11), file extension `.rpack` with the collision sentence. (3) *Validity (normative)* — the parsed-object model (member table with types from E14: integers only, `requirement_coverage` string), **canonical serialization defined exactly**: members sorted by code point, separators `,` and `:`, non-ASCII escaped as `\uXXXX`, UTF-8 (i.e. Python `json.dumps(obj, sort_keys=True, separators=(",", ":"))`); `root_digest` = SHA-256 hex of the canonical serialization of the object minus `root_digest` and `signature`; `signature` = canonical SSHSIG armor (no leading/trailing bytes) over the `root_digest` string under namespace `forgeproof`, verified against `public_key`; `chain_hash` derivation caveat kept; attestation invariants (existing text) — *corrected 2026-09-20:* the existing layout text is the reference producer's emission contracts, not validity rules (the verifier enforces neither "no `keyid`" nor the exact `verificationMaterial`); the spec states the verifier-binding subset separately ("What binds a verifier") and declares `verificationMaterial` opaque, as RQ1 and D8 assume. (4) *Emission profile (normative for the reference producer)* — the verbatim clause in Appendix B. (5) *Verification requirements* — "Python 3.11+ stdlib plus OpenSSH `ssh-keygen` ≥ 8.0 (*corrected 2026-09-20:* **≥ 8.1** — `ssh-keygen -Y sign`/`verify` first shipped in OpenSSH 8.1, released 2019-10-09, per https://www.openssh.com/txt/release-8.1; the 8.0 release notes carry no such entry) for the SSHSIG check; the attestation check needs the stdlib only; cosign is optional." (6) *Format-bump checklist* — a future 1.2.0 must: add to `KNOWN_RPACK_VERSIONS`, freeze a fixture, re-issue the schema `$id`, update the IANA registration (RFC 6838 §5.5). Everything registration-related beyond the one identity paragraph goes to `docs/media-type.md`.
- Acceptance: `test_spec_anchor_frozen` (the file exists at the sealed path; contains the exact heading; `fp.FORGEPROOF_BUILD_TYPE` ends with `#slsa-buildtype-v1`); `test_canonical_form_matches_spec` (the spec's canonical-serialization sentence agrees with `fp.canonical_json` on a nested fixture: sorted, compact, `\uXXXX`); `test_no_floats_in_fixtures` (all four); `test_forbidden_phrases` (D11) passes; the run-skill reference list (`SKILL.md:263-268`) unchanged.
- Principle 1, 2, 3. Milestone v1.4.0.

**T3-2 — Published JSON Schema.**
- Rationale: a machine-readable description at a stable, immutable URL; the schema's acceptance tests need all four fixtures (T0).
- Files: `schemas/forgeproof-rpack-1.schema.json` (Appendix C); `stress/validate_schema.py` (CI driver, imports `jsonschema` — never imported by the engine or the tests); `.github/jsonschema-requirements.txt` (`jsonschema==4.26.0` + transitive pins with `--hash` lines, generated once with pip-compile `--generate-hashes` — *corrected 2026-09-20:* generated with `uv pip compile --generate-hashes --universal --python-version 3.11`, uv being the house tool: one universal file installs with `--require-hashes` on the CI runner (ubuntu, Python 3.11) and on a maintainer's Windows box); `TestFormatIdentity.test_schema_is_structurally_sane` (stdlib).
- Acceptance (CI, `format-identity` job): the four fixtures, a fresh bundle from `stress/make_bundle.py`, and the fresh bundle with an extra unknown top-level member all **validate**; wrong `format`, missing `signature`, `version: "2.0.0"`, `attestation` with two signatures, `evaluation.tests_passed: 1.5` all **fail**. Stdlib test: `$schema` is the 2020-12 URI; `$id` is absolute, fragment-free, and its path ends with the schema's own repo path; `properties.format.const == fp.RPACK_FORMAT`; every member of `fp.KNOWN_RPACK_VERSIONS` matches `properties.version.pattern`; `attestation` not in `required`; no `additionalProperties: false` anywhere. *Corrected 2026-09-20 (two decisions by Ryan, made after this text was written; nothing above is withdrawn):* (1) **What the schema describes** — the specification's member table: what a valid format-1.x document looks like. It relaxes only where the specification tells verifiers to tolerate something: unknown members at every level, `mediaType`, and `verificationMaterial` (Appendix C). It is not "whatever `verify` accepts": the reference verifier tolerates more than the member table allows (an unrecognized `version`, for instance, is one warning and never an error), and the schema does not follow it there — the five negatives above stay exactly as written. (2) **One more acceptance case** — a document whose `attestation` has no `mediaType` and no `verificationMaterial` **validates** (a driver positive), and the stdlib test also asserts that the attestation sub-schema's `required` is exactly `["dsseEnvelope"]` and that `mediaType` / `verificationMaterial` carry no constraining keyword, so that nothing can quietly make them required again. The driver additionally requires each negative to fail for its intended reason: exactly one validation error, at the expected instance path, from the expected keyword.
- Scope: `.rpack` only; chain file deferred (triage). Principle 1, 2. Milestone v1.4.0.

**T3-3 — `.gitattributes` Linguist mapping (plugin repo) + documented user snippet.**
- File: `.gitattributes` gains `*.rpack linguist-language=JSON` (fixtures then render as JSON on GitHub); README "Format identity" section and `docs/media-type.md` carry the same line for users with the sentence "Optional and cosmetic: it changes how GitHub highlights the file; verification is unaffected either way, and no `-text` is needed for bundles." A `linguist-generated` variant is **not** offered (it hides the file in diffs — the opposite of the goal, L2).
- Acceptance: `test_skills_never_write_repo_config` (no SKILL.md contains `.gitattributes`, `update-mime-database`, `xdg-mime`, `files.associations`); user-layer render check (OQ1). Principle 2. Milestone v1.4.0.

**T3-4 — `docs/media-type.md`.**
- Contents: the ledger line (D11, state A at merge, B after submission); Appendix A copied verbatim as the submitted text (kept in sync by review, not by test); what registration changes and does not (GitHub `text/plain`, verification, trust); install recipes for `share/` (user scope, system scope, CI/no-install); the `file -e json -m share/magic/forgeproof` usage and the built-in-JSON precedence; editor snippet (`files.associations`, `json.schemas` → the `$id` URL); the `.rpack` collision note; known limits (sorted re-serialization escapes content sniffing; a game archive named `.rpack` is labelled by glob on a desktop with the XML installed); the Apple UTI would-be declaration (`com.forgeproof.rpack` conforming to `public.json`) for any future app; the upstream-submission checklist with the sign-off gate.
- Principle 3. Milestone v1.4.0.

**T3-5 — README, PRIVACY.md, CHANGELOG, docs renumbering.**
- README: new `### Format identity` subsection under "The .rpack Bundle" (type name, schema URL, `.gitattributes` line, detection pointer); "Verify a bundle" gains "Requires Python 3.11+ and `ssh-keygen` (for the SSHSIG check) — nothing else"; "three frozen fixture bundles" → four (`:48`, `:222`), engines list adds v1.3.0; test count refreshed from `pytest --collect-only -q`.
- PRIVACY.md: "ForgeProof does not:" list (`:96-100`) gains "Install MIME type definitions or modify `~/.local/share/mime`, `.gitattributes`, or editor settings — the files under `share/` are opt-in and documented only"; bundle table gains a **Timestamps** row (chain block times; attestation `startedOn`/`finishedOn`) — an omission corrected, not a new disclosure. Writes list unchanged.
- CHANGELOG `## [1.4.0]` in house format: the "no bundle byte changed" sentence up front; four fixtures; the Action note (RQ3); the type "proposed, status in docs/media-type.md".
- `docs/compliance-mapping.md:41`, `docs/cosign-interop.md:43`: "v1.4" → "v1.5" for the keyless tier.
- Principle 3. Milestone v1.4.0.

### Tier 2 — Detection databases

**Emission clause dependency (resolved first).** The rules below key on "`{` at byte 0 and `"format": "forgeproof-rpack"` or `"format":"forgeproof-rpack"` within bytes 1–256". That is sound only because the spec's emission profile (Appendix B, verbatim) makes it a MUST for the reference producer and a SHOULD for others. **Stated plainly everywhere the rules ship:** a canonically re-serialized bundle (sorted members put `format` behind the multi-kilobyte `attestation`) remains valid and verifiable but may escape content-based detection; it is still detected by name.

**T2-1 — shared-mime-info XML** (`share/mime/packages/forgeproof-rpack.xml`, Appendix B.1). Tested 2026-09-16 (E7). Acceptance in CI: compiles with `update-mime-database` without warnings; `gio info` under an isolated `XDG_DATA_HOME` reports our type for all four fixtures, the fresh bundle, and derived CRLF/sorted/compact/BOM copies named `.rpack`; content-only (`noext` copies) reports our type for LF and CRLF and `text/plain` for sorted/compact (asserted as the documented limit); `application/json` for a `.json`-named unrelated document; `application/octet-stream` for `RP6L…` bytes without a name. Upstream test-list line recorded in `docs/media-type.md` for a future MR: `issue-996.rpack application/vnd.forgeproof.rpack+json`. Principle 2. Milestone v1.4.0.

**T2-2 — libmagic rule** (`share/magic/forgeproof`, Appendix B.2). Tested 2026-09-16 with file-5.46. Acceptance in CI: `file -e json -m share/magic/forgeproof --mime-type` → our type for the four fixtures, the fresh bundle, CRLF and compact-insertion-order copies; `text/plain` for sorted and BOM copies and for an unrelated JSON document (asserted limits); **default `file --mime-type` on a bundle still prints `application/json`** (asserted: the precedence is documented, not hidden); `file -C -m` compiles in `$RUNNER_TEMP` (never in the checkout — it writes `<name>.mgc` into the cwd). Principle 2. Milestone v1.4.0.

**T2-3 — CI job `format-identity`** (`.github/workflows/ci.yml`, required). ubuntu-latest; why-comment mirroring `cosign-interop`'s (`:70-80`); `apt-get install -y --no-install-recommends shared-mime-info libglib2.0-bin file` with versions printed (apt cannot be exactly pinned — stated deviation from the cosign precedent; the job asserts semantics, not versions); `pip install --require-hashes -r .github/jsonschema-requirements.txt`; `python stress/make_bundle.py` for the fresh bundle; the XML is **copied** to `$RUNNER_TEMP/xdg/mime/packages/` before `update-mime-database` runs (it writes `globs2`, `magic`, `mime.cache` and more beside the XML — never into the checkout) and `gio info` runs with `XDG_DATA_HOME=$RUNNER_TEMP/xdg`; then T3-2, T2-1, T2-2 assertions as a small stdlib driver (`stress/check_detection.py`) plus the jsonschema driver. No other job installs any of these. Principle 2. Milestone v1.4.0.

**Local MIME registration in the plugin: never** (D5). Options weighed: ship as documentation/opt-in (chosen), never ship (loses the tested artifact), manual recipe only (chosen — it is the documentation).

### Tier 1 — IANA media type registration

**T1-1 — Submit the registration (after the v1.4.0 tag; Ryan's sign-off on the final text).** Tree: vendor. String: `application/vnd.forgeproof.rpack+json`. Template: Appendix A, entered into the web form (I4; fields map 1:1; OIDs "N/A"). "Published specification": the tag-pinned URL (RQ14). "Magic number(s)": none fixed — the in-band `format` member within the first 256 bytes (D9). "File extension(s)": `.rpack` with the collision note. Contact / author / change controller: RQ13. Security considerations: Appendix A — Principle 3 (tamper-evidence ≠ safety; key self-attested until the keyless tier; nothing about review or compliance), privacy (E16, PRIVACY.md), JSON parsing (R15), hostile embedded attestations, path confinement, markup injection, precise verification requirements. Acceptance: ledger flips A → B with the submission date; the IANA acknowledgement is filed in the release PR thread. Principle 3. Milestone: v1.4.0 release-checklist tail.

**T1-2 — Ledger update on IANA's answer.** One docs-only commit to `main` (state C or D); rides the next CHANGELOG section of any kind; no milestone. If a rename is demanded: the string changes in spec/README/XML/magic/schema title/docs — no bundle byte, no engine, no test data beyond string constants. Principle 3. Milestone: first release after confirmation.

**What registration changes in practice — said in the spec, README, and `docs/media-type.md`:** nothing on GitHub (E15); nothing in verification (E2); nothing about trust (R7). `.gitattributes` is what changes GitHub highlighting. Registration is a name.

---

## 8. Roadmap mapping table (core deliverable)

Milestones are the real ones from `ROADMAP.md` plus the one new milestone this plan argues for (RQ1). Placement is justified against the milestone's narrative and success criteria; the new v1.4.0's are in Appendix D.

| Work item | Target milestone | Rationale (against narrative / success criteria) | Blocking dependency | Principle | ROADMAP.md edit required |
|---|---|---|---|---|---|
| T0 fourth frozen fixture (v1.3.0 engine, format 1.1.0) | **v1.4.0** Phase 0 | Cadence: the previous engine's output is frozen before any change; v1.4.0's success criterion "every frozen fixture validates against the schema" needs it | none | 1 | No (the "four fixtures" clause is inside the new block) |
| T3-1 spec promotion + stability statement + emission profile | **v1.4.0** | The release *is* the naming release; the spec is the "published specification" the criteria cite; no engine seam is waiting on keyless (verificationMaterial declared opaque) | T0 (spec cites four fixtures) | 1, 2, 3 | Yes — new milestone block (Appendix D) |
| T3-2 JSON Schema + CI validation | **v1.4.0** | Success criterion 1 ("validates against the published schema in CI") | T3-1, T0 | 1, 2 | Same block |
| T3-3 `.gitattributes` line + user snippet | **v1.4.0** | The one thing that changes GitHub rendering; document-only for users (Principle 2) | none | 2 | Same block (one clause) |
| T3-4 `docs/media-type.md` | **v1.4.0** | Keeps paperwork out of the runtime-loaded spec (D7); hosts the ledger (D11) | T3-1 | 2, 3 | No |
| T3-5 README / PRIVACY / CHANGELOG / docs renumber | **v1.4.0** | Release hygiene; PRIVACY.md correction of an omission (timestamps) | T2-1 (the "never installs" bullet) | 3 | No (ROADMAP "Last updated" only) |
| T2-1 shared-mime-info XML | **v1.4.0** | Success criterion 2 ("the shipped MIME definition detects all four fixtures and a fresh bundle in CI with no bundle byte changed") | T3-1 (emission clause) | 2 | Same block |
| T2-2 libmagic rule | **v1.4.0** | Same criterion; ships with the built-in-JSON precedence stated | T3-1 | 2 | Same block |
| T2-3 `format-identity` CI job (required) | **v1.4.0** | The cosign-interop pattern is this repo's precedent for proving a criterion mechanically | T2-1, T2-2, T3-2 | 2 | Same block (criteria) |
| T1-1 IANA submission | **v1.4.0 — release-checklist tail (after the tag, after Ryan's sign-off)** | "Published specification" must cite a tag that exists; the security text must describe the key model as shipped (self-attested; keyless tier planned for v1.5.0 and stated as not to be assumed) | v1.4.0 tag; T3-1; constraint 9 | 3 | Same block ("submitted after the tag; status in docs/media-type.md") |
| T1-2 ledger state C/D on IANA's answer | **First release after confirmation** (docs-only commit to `main`; no milestone invented) | Gated on an event with no SLA; a one-line docs change is not a release deliverable and "patch = fixes" would not be violated if it rode a patch | IANA | 3 | No — the ledger lives in `docs/media-type.md`, not ROADMAP |
| Upstream shared-mime-info MR + `file` Magdir e-mail | **After T1-2; maintainer action** (🌅 in spirit; tracked in `docs/media-type.md`'s checklist, not on ROADMAP) | M6: upstream prefers registered types; alias churn otherwise; each needs sign-off (constraint 9) | T1-2 | 2 | No |
| MCP verify endpoint exchanges bundles under the media type | **v2.0.0 "Beyond GitHub"** | The first and only code consumer of an HTTP `Content-Type`; the endpoint is a v2.0.0 bullet | T1-1 (string fixed) | 4 | Yes — one clause on the existing bullet |
| Linguist upstream extension PR | **Dropped** (revisit only with ≥200 `.rpack` files/year across many repos, L1) | Bar unmet by policy; the per-repo override delivers the goal today | — | — | No |
| SchemaStore listing | **Deferred** (v2.0.0 directory strategy) | Needs a draft-07 variant and "broad uptake" evidence (J4) | T3-2 | — | No |
| Apple UTI | **Dropped** | No macOS bundle to declare it in (U1); a paragraph in `docs/media-type.md` records the would-be declaration | — | — | No |
| Writer hardening (`write_text(..., encoding="utf-8", newline="\n")` at `:1535`, `save_chain :579`) | **Deferred — companion item for the next engine-touching release (v1.5.0)** | Changes on-disk bytes of new bundles only (never digests); detection does not need it; the emission profile already permits CRLF | PLAN_v1.5.0 decision | 1 | No |
| `verify` dies actionably when `ssh-keygen` is absent (E5) | **Deferred — v1.5.0** (engine change) | Not this workstream's fix; public text states the requirement precisely now | — | 2 | No |
| Chain-file JSON Schema | **Deferred** | Internal working file; out of the media type's scope (D6) | — | — | No |

**Items with no natural home — argued.** T1-2 and the upstream submissions are gated on events ForgeProof does not control. Inventing a milestone for a one-line ledger flip would put a version number on IANA's calendar; the honest structure is a ledger line in `docs/media-type.md` whose wording is true in every state (D11), and a docs-only commit to `main` when the state changes — the marketplace's nightly sweep distributes it without a version, exactly as the repo already treats the marketplace pin itself (an external event tracked, not versioned). No "Cross-cutting workstreams" ROADMAP section is needed (departs from the prior).

---

## 9. Phases

Dependency order: fixture before anything (0) → spec, the dependency of everything (1) → schema (2) → detection files + CI proof (3) → developer surface and docs (4) → release (5) → post-tag submission.

### Phase 0 — Plan, branch, fourth compat fixture, roadmap entry
1. `git checkout main` (must be `e6aef5c`); `git checkout -b release/v1.4.0`; `mv PLAN_format_identity.md PLAN_v1.4.0.md` (RQ2); update its executor header line to the new name.
2. Freeze `fixtures/v130/` per T0; add `TestV130Compat`; `FIXTURE_V130`.
3. Apply the Appendix D ROADMAP diff (new 🧭 block, renumbering, policy clause, "Last updated"); `docs/compliance-mapping.md:41` and `docs/cosign-interop.md:43` renumbered here so the branch's docs are coherent from the first commit.
4. Verification: full pytest green (290 + new); fixture files contain no CR; all four compat classes green in lenient and strict.
Commit: `test: freeze v1.3.0 compat fixture (format 1.1.0, first with attestation); open v1.4.0 on the roadmap`

### Phase 1 — Normative specification
1. T3-1 edits to `rpack-format.md`; `docs/media-type.md` created with ledger state A and everything listed in T3-4 except the detection recipes (Phase 3 adds them).
2. Tests: `test_spec_anchor_frozen`, `test_canonical_form_matches_spec`, `test_no_floats_in_fixtures`, `test_forbidden_phrases`, `test_format_marker_in_prefix` (all four fixtures + a fresh CLI bundle under `_require_sshkeygen`: `data[:1] == b"{"` and the spaced or compact marker within `data[:256]`).
3. Verification: pytest green; `claude plugin validate .claude-plugin/plugin.json` clean; run-skill reference list unchanged.
Commit: `docs: promote rpack-format.md to the normative specification (validity vs emission; media type; verification requirements)`

### Phase 2 — JSON Schema
1. `schemas/forgeproof-rpack-1.schema.json` (Appendix C expanded to the full member table); `stress/validate_schema.py`; `.github/jsonschema-requirements.txt`; `test_schema_is_structurally_sane`.
2. Verification: local run of the driver with the pinned validator in a throwaway venv (`uv venv` in the scratchpad) — positives and negatives as in T3-2; pytest green.
Commit: `feat: publish the format 1.x JSON Schema at an immutable tag-pinned $id`

### Phase 3 — Detection files and the CI proof
1. `share/mime/packages/forgeproof-rpack.xml`, `share/magic/forgeproof` (Appendix B); `stress/check_detection.py`; the `format-identity` job (T2-3) marked required; detection recipes added to `docs/media-type.md`; PRIVACY.md bullet (T3-5's first item).
2. Tests: `test_detection_files_single_sourced` (the type string appears identically in the XML, the magic file, the spec, the schema, and `docs/media-type.md`; the XML's glob is `*.rpack`; the magic file's `!:ext` is `rpack`); `test_engine_never_mentions_consumer_tools` (`jsonschema`, `xdg-mime`, `update-mime-database`, `gio`, `file -m` absent from `forgeproof.py` and from `cmd_preflight`).
3. Verification: the job green on a pushed branch; both asserted limits (`file` default = `application/json`; sorted content-only = `text/plain`) proven red-if-removed by a deliberate local mutation before commit.
Commit: `ci: ship shared-mime-info and libmagic definitions for .rpack and prove them against every fixture`

### Phase 4 — Developer surface and docs
1. `.gitattributes` line (T3-3); README (T3-5); CHANGELOG `[1.4.0]`; PRIVACY.md timestamps row; `docs/media-type.md` editor snippets and limits; user-layer checks recorded (OQ1: scratch repo render/diff; VS Code association; `xdg-mime install --mode user` on a Linux desktop or WSL with a file manager available — else `gio info`, recorded as such).
2. Verification: pytest green; `test_skills_never_write_repo_config`; `claude plugin validate` clean; README numbers match `pytest --collect-only`.
Commit: `docs: format identity — README, gitattributes, privacy, changelog`

### Phase 5 — Release
1. Final step: `.claude-plugin/plugin.json` → `1.4.0` and `PLUGIN_VERSION = "1.4.0"` together (sync test); `forgeproof.py:530` docstring "v1.4 seam" → "v1.5 seam"; ROADMAP 🧭 → ✅ and "Last updated".
2. Full CI (all matrices, `cosign-interop`, `format-identity`, `validate`) + stress green.
3. Push the branch and hand Ryan the compare URL (own-gate landmine: `gh pr create` is blocked in-session; the gate also fires on its trigger phrase quoted inline — route body text through `--body-file`). **Merge with a merge commit.** Tag `v1.4.0` (annotated), GitHub Release from the CHANGELOG section.
4. Action: **no re-vendor** (RQ3) — or, if Ryan chooses the alternative, the four extra steps listed in RQ3 after the tag.
Commit: `release: v1.4.0 — a name of its own`

### Post-tag (release-checklist tail)
1. Fill Appendix A's two placeholders (tag URL, submission date), present the final text to Ryan, submit via the IANA form only after sign-off; ledger → state B in a docs-only commit; file the acknowledgement in the PR thread.
2. T+1–2 days: marketplace pin advanced; dogfood check green on a fresh PR.
3. On IANA's answer: ledger → C or D (T1-2); then the upstream-submission decision (RQ15), each behind sign-off.

---

## 10. Test plan — four layers

| Layer | What proves it | Where it runs |
|---|---|---|
| **Unit** (stdlib + pytest) | `TestV130Compat` (green lenient/strict, `warnings == []`, attestation checks `ok`, four tamper cases, no CR); `TestFormatIdentity`: `test_format_marker_in_prefix` (four fixtures + fresh bundle), `test_spec_anchor_frozen`, `test_canonical_form_matches_spec`, `test_no_floats_in_fixtures`, `test_schema_is_structurally_sane`, `test_detection_files_single_sourced`, `test_engine_never_mentions_consumer_tools`, `test_skills_never_write_repo_config`, `test_forbidden_phrases` (D11) | plugin CI matrix (ubuntu/macos/windows + windows bash&cmd + debian python3-only) via `FP_TESTS` |
| **Functional** | Required `format-identity` job: (a) schema — four fixtures + fresh + fresh-with-unknown-member validate, five negatives fail, pinned `jsonschema==4.26.0` with hashes; (b) MIME — `update-mime-database` compiles the XML; `gio info` under isolated `XDG_DATA_HOME` on the fixture/fresh/CRLF/sorted/compact/BOM/`noext`/`RP6L`/`.json` matrix with the documented limits asserted; (c) magic — `file -e json -m` matrix incl. the asserted default-`application/json` precedence and `file -C` in `$RUNNER_TEMP`; stress harness unchanged | `.github/workflows/ci.yml` |
| **User** | Scratch repo: a committed `.rpack` with and without the `.gitattributes` line — file view and diff view compared (OQ1); VS Code `files.associations` + `json.schemas` snippet validates a fixture; `xdg-mime install --mode user` on a Linux desktop → file manager shows "ForgeProof provenance bundle" (or `gio info` if no desktop); `file -e json -m share/magic/forgeproof` on a real bundle; `git status` in a user repo after a full run shows only `.forgeproof/` — recorded in the release PR | manual, recorded |
| **Regression** | Four frozen fixtures green everywhere, `--strict` included; seven-key JSON snapshots unchanged; `TestSkillContract` floor unchanged; `test_engine_source_has_no_shell_isms` unchanged; PRIVACY.md Writes list unchanged; `hooks/hooks.json` byte-identical; `PLUGIN_VERSION` ↔ `plugin.json` sync; `claude plugin validate` | plugin CI, every push |

**Success-criteria mapping (Appendix D block):** "normative spec with an emission profile" = T3-1 + Unit tests 2–4; "every frozen fixture validates against the published schema in CI" = Functional (a) + T0; "shipped MIME definition detects the four fixtures and a fresh bundle with no bundle byte changed" = Functional (b)/(c) + the four compat classes proving no byte moved; "registration submitted after the tag; status in one ledger" = post-tag step 1 + `test_forbidden_phrases`.

---

## 11. Risk register (top 5)

| # | Risk | Mitigation |
|---|---|---|
| 1 | **IANA Expert Review stalls, returns the request, or asks for a different subtype** — no SLA exists (R10), and the reviewer may object to naming unregistered conventional types or to the extension note (OQ2) | The template is complete and precedent-shaped (SARIF-grade security text, tag-pinned spec, RFC 8259 citations); every surface uses the bare name and the ledger's wording is true in every state (D11), so nothing downstream depends on confirmation; a forced rename is a string change only (D3). The type works as a convention regardless — exactly as in-toto's and Sigstore's do (I1, I6). |
| 2 | **Over-claiming** — a comment, README line, or PR body implies registration, trust, review, or compliance | `test_forbidden_phrases` in the matrix; the ledger is the only place status is stated; Appendix A's security text is copied, not paraphrased, into the spec's identity paragraph; PR bodies (push skill) do not mention the type. |
| 3 | **Detection disappoints or silently breaks** — `file` says `application/json`; a key-sorted bundle misses content sniffing; a game archive named `.rpack` is labelled ForgeProof on a desktop with the XML installed; a future engine change inserts a member before `format` | Both limits are stated in the XML/magic comments, the spec, and `docs/media-type.md`, and **asserted** in CI so they are proven, not hidden; the glob covers sorted/BOM cases; the collision note accompanies every extension-keyed snippet; `test_format_marker_in_prefix` runs on a fresh bundle so a member reorder fails the build. |
| 4 | **Renumbering confusion** — external references to "v1.4.0 = keyless" (issues, discussions, memory files, the frozen PLAN_v1.3.0) and two adjacent milestones about "identity" | The new title avoids the word "identity"; `grep` of issues/discussions before Phase 0; CHANGELOG 1.4.0 and ROADMAP both state the renumbering in one sentence; frozen plans are left as historical records. |
| 5 | **Pin and format churn** — the IANA field pins the v1.4.0 tag and the schema `$id` pins a release, so a future format bump (1.2.0) must update both; apt-installed CI tools cannot be exactly pinned and may change behaviour | The spec's format-bump checklist (T3-1 item 6) lists both updates; the `$id` rule is "last-changing release" so unchanged schemas never move; the CI job asserts semantics with versions printed, and the two tools under test are the reference implementations of their own formats (`update-mime-database`, `file`), so drift shows up as a failing assertion with a version in the log. |

---

## 12. Triage table

| Item | Decision | Rationale |
|---|---|---|
| Normative spec, emission profile, stability statement (T3-1) | **Include** — Phase 1 | The dependency of every other item |
| JSON Schema 2020-12 at a tag-pinned `$id`, CI-validated (T3-2) | **Include** — Phase 2 | Success criterion; RQ7/RQ8 |
| Fourth frozen fixture (v1.3.0 engine) | **Include** — Phase 0 | Cadence; schema tests need an attested bundle |
| shared-mime-info XML + libmagic rule + `format-identity` job (T2) | **Include** — Phase 3 | Success criterion; tested in this session |
| `.gitattributes` line in the plugin repo + documented snippet | **Include** — Phase 4 | Document-only for users |
| IANA vendor-tree submission | **Include** — post-tag, after sign-off | The naming deliverable |
| A `mediaType` (or `$schema`) top-level member in bundles | **Reject** | Enters `root_digest` input; format bump for a self-description `format`+`version` already provide (D3) |
| `RPACK_MEDIA_TYPE` engine constant before v2.0.0 | **Defer — v2.0.0** | First code consumer is the MCP endpoint; documentary strings stay out of the engine |
| Extension alias (`.rpack.json`) | **Reject** | E8; collision is name-only and content-disjoint |
| Plugin installs MIME definitions (auto or opt-in subcommand) | **Reject** | Constraint 8; D5 |
| Skill writes `.gitattributes` / editor settings into user repos | **Reject** | Constraint 8; warn-don't-write precedent |
| `.vscode/settings.json` in the plugin repo | **Reject** | RQ10 |
| Run-skill one-line tip | **Reject** | RQ11 |
| "proposed" adjective on every surface + grep | **Reject** (replaced) | D11 single ledger |
| `version` media-type parameter; JSON Pointer fragment syntax | **Reject** | D1, D2 |
| Linguist upstream extension PR | **Drop** (revisit with usage evidence) | L1 threshold |
| SchemaStore listing | **Defer — v2.0.0** | J4 draft-07 recommendation; uptake bar |
| Apple UTI | **Drop** | U1 |
| Upstream shared-mime-info MR; `file` Magdir submission | **Defer — after IANA confirmation; sign-off gated** | M6 |
| Chain-file JSON Schema | **Defer** | D6 |
| Writer hardening (`encoding`/`newline` at `:1535`, `:579`) | **Defer — v1.5.0 companion item** | Engine bytes; not needed for detection; emission profile permits CRLF |
| Actionable `die()` when `ssh-keygen` is absent (E5) | **Defer — v1.5.0** | Engine change; the requirement is now stated precisely in public text |
| Action re-vendor for the constant-only diff | **Resolved question 3** (recommend skip) | E11 |
| CHANGELOG dating policy (authoring vs tag dates) | **Note only** | Out of scope; the 1.4.0 entry uses the authoring date like its predecessors |
| Timestamps row in PRIVACY.md | **Include** — Phase 4 | Omission correction (E16), same discipline as the v1.3.0 PRIVACY fix |

---

## 13. Release checklist (conditional on RQ1 = new minor v1.4.0)

- [ ] `PLAN_format_identity.md` renamed to `PLAN_v1.4.0.md` and committed (Phase 0, first action)
- [ ] `fixtures/v130/` frozen with the unmodified v1.3.0 engine (LF, issue 996); `TestV130Compat` green with `attestation*` = `ok` and `warnings == []` in both modes
- [ ] ROADMAP: v1.4.0 block added as 🧭, keyless → v1.5.0, review → v1.6.0, v2.0.0 clause, policy clause, "Last updated"; docs parentheticals renumbered
- [ ] `rpack-format.md` promoted; path and `## SLSA buildType v1` heading unchanged (*corrected 2026-09-20:* the real heading is `### SLSA buildType v1`, same anchor); `test_spec_anchor_frozen` green; `docs/media-type.md` created with ledger state A
- [ ] `schemas/forgeproof-rpack-1.schema.json` with `$id` = v1.4.0 tag URL; hashed requirements file; driver; structural test green
- [ ] `share/mime/packages/forgeproof-rpack.xml` and `share/magic/forgeproof` shipped; `format-identity` job required and green, including both asserted limits
- [ ] `.gitattributes` line; README (format identity section, `ssh-keygen` requirement, four fixtures, test count); PRIVACY.md (never-installs bullet, timestamps row; Writes list unchanged); CHANGELOG `[1.4.0]` incl. the no-byte-changed sentence and the Action note
- [ ] Source greps green: `attestation` not in the `bundle_for_hash` denylist; `cosign`/`jsonschema`/`xdg-mime`/`update-mime-database`/`gio` absent from the engine and `cmd_preflight`; forbidden phrases absent; no SKILL.md writes repo config; no shell-isms
- [ ] Four frozen fixtures green on every platform, `--strict` included; seven-key snapshots green; `TestSkillContract` floor unchanged; `hooks/hooks.json` byte-identical
- [ ] *Added 2026-09-20:* before the tag, ONE errata sweep over `rpack-format.md`, `docs/media-type.md`, and Appendix A/C for wording findings logged since Phase 1 — the spec URL is immutable after the tag, so Minor wording findings are collected for this sweep instead of reopening a phase
- [ ] Release commit last: `plugin.json` + `PLUGIN_VERSION` → 1.4.0 together; `:530` docstring renumbered; ROADMAP 🧭 → ✅; `claude plugin validate .claude-plugin/plugin.json` clean; full CI + stress green
- [ ] Release PR pushed (compare URL handed over — own-gate landmine; `--body-file` for any gate-trigger text); **merged with a merge commit**; annotated tag `v1.4.0`; GitHub Release from the CHANGELOG section
- [ ] Action: left at v1.1.0 (RQ3) and said so in CHANGELOG — or the RQ3 alternative executed after the tag
- [ ] Post-tag: Appendix A placeholders filled; final text signed off by Ryan; submitted via the IANA form; ledger → B; acknowledgement filed
- [ ] T+1–2 days: marketplace pin advanced; dogfood check green on a fresh PR
- [ ] On IANA's answer: ledger → C/D in a docs-only commit; upstream-submission decision taken (sign-off gated)

---

## Appendix A — Draft RFC 6838 §5.6 registration template (proposed; nothing here is registered)

Field names follow RFC 6838 §5.6 verbatim (R11); the web form's extra "Object Identifier(s)/OID(s)" field is "N/A". Placeholders in angle brackets are filled at submission.

*Corrected 2026-09-20 (four changes inside the block; it is the single source of the submission text and `docs/media-type.md` carries it line for line):* (1) OpenSSH "8.0 or later" → "8.1 or later" — `ssh-keygen -Y verify` first shipped in 8.1 (openssh.com release notes); (2) "Neither is registered with IANA at the time of this registration" → "Neither appears in the IANA media types registry at the time of this registration" — this plan's own D11 allows the former words on the ledger line only; (3) "Consumers that resolve the recorded relative paths MUST confine resolution to the intended project root" → the SHOULD paragraph on recorded artifact paths — the reference verifier does not confine them (`forgeproof.py:2002-2011`), so a MUST would be a claim the reference implementation fails; the hardening is scheduled with v1.5.0. The paragraph as it now stands also covers the second unconfined value (the chain file's name is built from `str(issue.number)`, `forgeproof.py:1930-1933`), network-share paths, everything the verdict discloses (existence, regular-file status, digest match, and for the chain file whether it parses as JSON), and the fact that the producer's refusal dates from plugin v1.1.0 (commit `3175efb`; the v1.0.1 producer stored the recorded path unvalidated); (4) "can alternatively be performed with Sigstore's cosign" → the sentence stating what cosign checks (the exported attestation's DSSE signature under the exported key, and a supplied artifact's digest among the subjects — `docs/cosign-interop.md`, the `cosign-interop` CI job) and what only the format's own verification binds (the document's own "public_key", the artifact list, the chain), because the spec now defines four attestation checks and cosign performs part of them.

```
Type name: application

Subtype name: vnd.forgeproof.rpack+json

Required parameters: N/A

Optional parameters: N/A

Encoding considerations: binary
   JSON text (RFC 8259). RFC 8259 Section 8.1 requires UTF-8 for
   interchange; the reference producer escapes all non-ASCII characters
   and therefore emits pure ASCII. Lines may exceed 998 octets (the
   embedded attestation carries a base64-encoded payload on one line),
   so the content is not 7bit or 8bit text. Line-ending convention (LF
   or CRLF), indentation, and member order are not significant; see
   Interoperability considerations.

Security considerations:
   This media type shares the security considerations of JSON (RFC
   8259, Section 12): consumers MUST NOT evaluate the content as code
   and MUST NOT rely on "eval()"-style parsing. Consumers SHOULD apply
   the implementation limits RFC 8259 Section 9 permits (size, nesting
   depth, number range) and SHOULD treat duplicate member names as an
   error or ensure that the verified and the displayed views of a
   document come from the same parse (RFC 8259 Section 4). The format
   carries no active content, scripts, macros, external references, or
   URLs that a conforming consumer must dereference, and employs no
   compression; the embedded attestation payload is base64-encoded
   text whose decoded size is bounded by the encoded size.

   A ForgeProof bundle is a tamper-EVIDENT provenance record, not a
   safety, security, review, or correctness attestation. It contains an
   Ed25519 signature over a SHA-256 digest of the document's canonical
   serialization; a valid signature proves only that the document was
   not altered after signing by the holder of the corresponding private
   key. It proves nothing about the correctness, safety, or quality of
   the code the document describes. Consumers MUST NOT treat a verified
   bundle as evidence that the described change was reviewed, tested to
   any standard, or secure, and MUST NOT present it as compliance with
   any regulation or framework.

   The verifying public key travels inside the document ("public_key").
   By default it is ephemeral, generated by the producing tool, deleted
   after signing, and bound to no identity, certificate authority, or
   transparency log: it is self-attested. A valid signature therefore
   proves that the document was not altered since signing, not who
   signed it. A future revision may carry identity material (for
   example a certificate and transparency-log entry) inside
   "attestation.verificationMaterial"; consumers MUST NOT assume it is
   present and MUST treat its contents as untrusted until verified by
   the rules of the Sigstore bundle format.

   Privacy: the document discloses the issue title and URL, repository-
   relative file paths, free-text design decisions, timestamps of the
   recorded session, a public-key comment that by default embeds the
   producing machine's "username@hostname", and (from format version
   1.1.0) approval records that may contain the approver's e-mail
   address. Producers publishing bundles SHOULD be aware they disclose
   these; consumers that display bundles SHOULD treat them as personal
   data. The producer's privacy policy is published with the format
   specification.

   Free-text members (issue title, requirement text, decisions, notes,
   approver identifiers) are untrusted input: consumers that render
   them as HTML or Markdown MUST escape them to prevent markup or
   script injection.

   The recorded artifact paths, and the issue number from which the
   chain file's name is built, are untrusted input too: nothing in a
   document prevents an artifact path that is absolute or that names a
   network share, nor either value from climbing out of the project
   with "..". Consumers that resolve them SHOULD confine resolution to
   the intended project root. The reference producer has refused to
   record such an artifact path since plugin version 1.1.0; documents
   from earlier versions may carry one. At the time of this
   registration the reference verifier does not confine them: it
   resolves each as given, so verifying a document from an untrusted
   source can make it open a file outside the project and disclose,
   through its verdict, whether a file exists there, whether an
   artifact path names a regular file, whether the file matches the
   digest recorded for it, and, for the chain file, whether it parses
   as JSON.

   The embedded attestation (format version 1.1.0 and later) is an
   in-toto Statement inside a DSSE envelope inside a Sigstore-style
   bundle object. It is data, not executable content. Its signature
   MUST be verified under the key carried in the document's own
   "public_key" member, never under any key or key hint carried inside
   the attestation itself; its decoded payload is attacker-controlled
   JSON and MUST be parsed with the same limits as the outer document.

Interoperability considerations:
   The document is a single JSON object. Producers write UTF-8 without
   a byte-order mark (the reference producer writes ASCII). Member
   order, indentation, and newline convention are NOT normative:
   conforming verifiers re-serialize the parsed object in canonical
   form (members sorted by code point, no whitespace, non-ASCII escaped)
   before recomputing the digest, so consumers MUST NOT depend on byte
   layout. All numbers are integers. The format is append-only and
   versioned by the "version" member; consumers MUST ignore members
   they do not recognize and MUST NOT infer the presence of any member
   from the version value. The member "format" always has the value
   "forgeproof-rpack".

   Verifying the document's own signature requires OpenSSH "ssh-keygen"
   (8.1 or later, "ssh-keygen -Y verify") in addition to a JSON parser
   and SHA-256; the reference verifier is Python 3.11 standard library
   plus ssh-keygen and has no other dependencies. Verifying the
   embedded attestation requires only Ed25519 and JSON. Sigstore's
   cosign can independently check the DSSE signature of the
   attestation, as exported beside the document, against the exported
   public key and, for an artifact file supplied to it, that the
   file's digest is among the signed subjects. That complements and
   never replaces the verification the format specification defines,
   which additionally binds the attestation to the document's own
   "public_key", to its artifact list, and to its chain.

   From format version 1.1.0 the document may embed an attestation
   whose payload-type string "application/vnd.in-toto+json" (in-toto
   Attestation Framework) and wrapper media-type string
   "application/vnd.dev.sigstore.bundle.v0.3+json" (Sigstore bundle
   format) are conventions defined by those projects. Neither appears
   in the IANA media types registry at the time of this registration;
   this registration neither defines nor claims them.

Published specification:
   ForgeProof .rpack Bundle Format,
   https://github.com/ryanjmichie-git/forgeproof-plugin/blob/v1.4.0/skills/run/references/rpack-format.md
   (latest revision: the same path on the "main" branch).

Applications that use this media type:
   ForgeProof, a Claude Code plugin (producer and verifier), and the
   forgeproof-verify GitHub Action (verifier). Any JSON-aware tool can
   read the document.

Fragment identifier considerations:
   As specified for "+json" (RFC 6839, Section 3.1): no fragment
   identifier syntax is defined for "application/json", and this type
   defines none. JSON Pointer (RFC 6901) is not adopted.

Additional information:

   Deprecated alias names for this type: N/A
   Magic number(s): None at a fixed offset (JSON has none). The
      document begins with "{" (0x7B) and the reference producer emits
      the member "format" with the string value "forgeproof-rpack"
      within the first 256 octets; detection rules search that window
      for "\"format\": \"forgeproof-rpack\"" or
      "\"format\":\"forgeproof-rpack\"".
   File extension(s): .rpack
      (Note: ".rpack" is also used by unrelated binary game-asset
      archives whose first four octets are "RP5L" or "RP6L"; those files
      never begin with "{" and are distinguishable by content.)
   Macintosh file type code(s): N/A

Person & email address to contact for further information:
   Ryan Michie <ryanjmichie@gmail.com>

Intended usage: COMMON
   Interchanged publicly: committed to Git repositories and attached to
   pull requests.

Restrictions on usage: None

Author: Ryan Michie

Change controller: Ryan Michie (ForgeProof project),
   https://github.com/ryanjmichie-git/forgeproof-plugin

Provisional registration? (standards tree only): No
```

*Template notes.* Encoding value and RFC 8259 citations follow the live suffix registry and the IANA form's JSON guidance (R13, I4), not RFC 6839's frozen RFC 4627 text. The security section satisfies RFC 6838 §4.6's list (R6) and the form's points (1)–(5) (I4): active content (none), privacy (listed), compression (none), external services (none required; identity binding is optional and stated), links (none dereferenced), and it references JSON's own considerations as the form requires. Precedents for an individual contact and change controller: CycloneDX, Syft (I2). Two placeholders are filled at submission: the tag URL exists only after Phase 5, and the ledger records the submission date.

---

## Appendix B — Draft shared-mime-info XML, libmagic rule, and the emission-profile clause they depend on

### B.0 The emission-profile clause (verbatim; T3-1 adds it to `rpack-format.md`)

> #### Emission profile (normative for the reference producer; recommended for other producers)
>
> A `.rpack` document written by ForgeProof's `finalize` (the reference producer) MUST satisfy, and any other producer SHOULD satisfy, all of the following:
>
> 1. **Member order.** The top-level object begins with the member `version`, followed immediately by the member `format`. Consequently the byte sequence `"format": "forgeproof-rpack"` — or, for a producer that emits no whitespace after the colon, `"format":"forgeproof-rpack"` — occurs within the first 256 bytes of the file, and the first byte of the file is `{`.
> 2. **Encoding.** UTF-8 without a byte-order mark. The reference producer escapes every non-ASCII character as `\uXXXX` and therefore emits pure ASCII.
> 3. **Line endings.** Either LF or CRLF throughout, or no line breaks at all. The line-ending convention is not significant and MAY differ between platforms; the reference producer emits the platform's native convention (LF on POSIX, CRLF on Windows).
> 4. **Layout.** The reference producer emits two-space indentation and a trailing newline. Indentation and whitespace are not significant.
>
> **Validity is independent of emission.** A consumer MUST NOT reject, and a verifier MUST NOT fail, a document solely because it departs from this profile: validity is defined over the parsed JSON value (§Validity), and every digest and signature is computed over the canonical serialization of that value, never over the file's bytes. Detection rules that key on item 1 (the files under `share/`) therefore identify profile-conforming documents reliably and other valid documents on a best-effort basis; in particular, a document re-serialized with sorted members remains valid and remains verifiable but MAY escape content-based detection while still being detected by its file name.

### B.1 `share/mime/packages/forgeproof-rpack.xml` (XDG layout; modelled on upstream `application/schema+json`, M3)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!-- ForgeProof .rpack provenance bundle: application/vnd.forgeproof.rpack+json
     (vendor tree; registration status: docs/media-type.md). Format specification:
     https://github.com/ryanjmichie-git/forgeproof-plugin/blob/main/skills/run/references/rpack-format.md
     ForgeProof never installs this file (PRIVACY.md). To install it yourself:
       user scope:   xdg-mime install --mode user share/mime/packages/forgeproof-rpack.xml
                     (equivalently: copy to ~/.local/share/mime/packages/ and run
                      update-mime-database ~/.local/share/mime)
       system scope: copy to /usr/share/mime/packages/ and run update-mime-database /usr/share/mime
       no install:   T=$(mktemp -d); mkdir -p "$T/mime/packages"
                     cp share/mime/packages/forgeproof-rpack.xml "$T/mime/packages/"
                     update-mime-database "$T/mime"
                     XDG_DATA_HOME="$T" gio info -a standard::content-type FILE
                     (never run update-mime-database on share/mime itself: it writes
                      globs2, magic, mime.cache and more next to the XML)
     Content sniffing keys on the emission profile (spec): "{" at offset 0 and the
     "format" member within the first 256 bytes. A key-sorted re-serialization is still
     a valid bundle but is detected by the *.rpack glob only. -->
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/vnd.forgeproof.rpack+json">
    <comment>ForgeProof provenance bundle</comment>
    <sub-class-of type="application/json"/>
    <generic-icon name="text-x-script"/>
    <magic priority="80">
      <match type="string" value="{" offset="0">
        <match type="string" value='"format": "forgeproof-rpack"' offset="1:256"/>
        <match type="string" value='"format":"forgeproof-rpack"' offset="1:256"/>
      </match>
    </magic>
    <glob pattern="*.rpack"/>
  </mime-type>
</mime-info>
```

**Test evidence (2026-09-16; shared-mime-info 2.1 + GLib via PyGObject on WSL Ubuntu 22.04; isolated `XDG_DATA_HOME` under the scratchpad).** `update-mime-database` compiled it without warnings: `globs2` gained `50:application/vnd.forgeproof.rpack+json:*.rpack`, `subclasses` gained `… application/json`, `magic` gained the rule. `Gio.content_type_guess(name, data)`:

| Name | Data | Result |
|---|---|---|
| `issue-1.rpack` | LF / CRLF / sorted / compact / BOM bundle | `application/vnd.forgeproof.rpack+json` (all five; sorted/compact/BOM by glob) |
| `issue-1.rpack` | `RP6L…` bytes | `application/vnd.forgeproof.rpack+json` — **by glob; documented name-only collision** |
| `issue-1.json` | LF bundle | `application/json` (GLib prefers the unique `*.json` glob) |
| *(none)* | LF / CRLF bundle | `application/vnd.forgeproof.rpack+json` (content sniff) |
| *(none)* | sorted / compact bundle | `text/plain` — **documented limit** |
| *(none)* | `RP6L…` bytes | `application/octet-stream` |
| `issue-1.rpack` | *(none)* | `application/vnd.forgeproof.rpack+json` |

`Gio.content_type_is_a(ours, "application/json")` → `True`; description → "ForgeProof provenance bundle". Without the XML, the same files are `text/plain` (name+data) / `application/octet-stream` (name only). Upstream test-list line for a future MR: `issue-996.rpack application/vnd.forgeproof.rpack+json`.

### B.2 `share/magic/forgeproof` (magic(5); M7–M9)

```
# ForgeProof .rpack provenance bundle (JSON text) — application/vnd.forgeproof.rpack+json
# (vendor tree; registration status: docs/media-type.md).
# The identifier is the top-level member "format": "forgeproof-rpack"; its byte offset
# varies with indentation and newline convention (byte 26 on LF, 28 on CRLF as written
# by the reference producer), hence a search window rather than a fixed offset.
#
# IMPORTANT: file(1) runs its built-in JSON detector (src/is_json.c) BEFORE soft magic
# and stops on a match, so on a valid bundle this entry is reached only with
#   file -e json -m share/magic/forgeproof --mime-type issue-N.rpack
# (MAGIC_NO_CHECK_JSON) or with -k (MAGIC_CONTINUE). Plain `file` prints application/json.
# A key-sorted re-serialization moves "format" beyond the window and is not detected.
0	string	{
>0	search/256	"format":\ "forgeproof-rpack"	ForgeProof provenance bundle (.rpack), JSON text
!:mime	application/vnd.forgeproof.rpack+json
!:ext	rpack
>0	search/256	"format":"forgeproof-rpack"	ForgeProof provenance bundle (.rpack), JSON text
!:mime	application/vnd.forgeproof.rpack+json
!:ext	rpack
```

**Test evidence (2026-09-16; file-5.46, Git for Windows).** `file -c -m` parses both entries. Results of `file -b -m share/magic/forgeproof -e json --mime-type`:

| File | Result |
|---|---|
| LF bundle / CRLF bundle / compact insertion-order bundle | `application/vnd.forgeproof.rpack+json` |
| sorted (indented or minified) bundle / BOM-prefixed bundle | `text/plain` — **documented limit** (window / `{` guard) |
| unrelated JSON with `"format": "something-else"` | `text/plain` (no false positive) |
| **default invocation without `-e json`**, LF or CRLF bundle | `application/json` — **documented precedence** |

Probes that shaped the rule: `search/64` fires at bytes 26/28 only; `regex/16` never fires (N is bytes unless the `l` flag), `regex/1024` fires on every layout including sorted — rejected because `regex` is "discouraged" upstream (M7) and the two-`search` form matches the shared-mime-info rule's semantics exactly. The 28-byte literal clears the upstream "at least 32 bits, unique" bar (M8). `file -C` writes `<name>.mgc` into the current directory — compile only in a temp dir (CI: `$RUNNER_TEMP`).

---

## Appendix C — JSON Schema skeleton (`schemas/forgeproof-rpack-1.schema.json`)

Skeleton only: `$schema`, `$id`, the eleven required members with types from E14, and the attestation shape that applies **when the member is present** (never implied by `version`). Unknown members are allowed at every level; no `additionalProperties: false` anywhere.

*Corrected 2026-09-20 (one change inside the block, in `$defs.sigstoreBundle`):* `required` was `["mediaType", "verificationMaterial", "dsseEnvelope"]`, `mediaType` carried a pattern, and `verificationMaterial` was `{"type": "object"}`. The schema matches the **verifier**, not the producer's output: the reference verifier accepts a document whose `mediaType` is absent or arbitrary and whose `verificationMaterial` is absent, populated, or not an object (probed), and the spec's "What binds a verifier" forbids rejecting a document over either. So `required` is now `["dsseEnvelope"]` and the two members are described, not constrained. Everything the verifier does enforce stays — `payloadType`, padded-base64 `payload`, exactly one signature object with a string `sig` — so T3-2's negative "`attestation` with two signatures" still fails.

*Corrected 2026-09-20 (second note; Ryan's decision, recorded with Phase 2):* "matches the verifier" above is scoped to the attestation wrapper. The schema as a whole describes the specification's member table and relaxes only where the specification tells verifiers to tolerate something — unknown members at every level, `mediaType`, `verificationMaterial`; it is not "whatever `verify` accepts" (T3-2). The published file is the block below with `description` annotations taken from the member table and no further constraining keyword; `test_schema_is_structurally_sane` pins `required == ["dsseEnvelope"]` and annotation-only `mediaType` / `verificationMaterial`. *Corrected 2026-09-20:* the four `"minimum": 0` keywords this block carried (on `issue.number`, `tests_passed`, `tests_failed`, `lint_errors`) were removed, because the specification's member table says "integer" with no sign restriction and a released engine (v1.1.0) can emit a negative count in a bundle that every verifier passes.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://raw.githubusercontent.com/ryanjmichie-git/forgeproof-plugin/v1.4.0/schemas/forgeproof-rpack-1.schema.json",
  "$comment": "The $id pins the release that last changed this schema; an unchanged schema keeps its $id across releases. Format 1.x is additive forever: unknown members are allowed at every level and no version value implies the presence of any member. Media type: application/vnd.forgeproof.rpack+json (vendor tree; registration status in docs/media-type.md).",
  "title": "ForgeProof .rpack provenance bundle, format 1.x",
  "type": "object",
  "required": ["version", "format", "issue", "requirements", "artifacts", "decisions",
               "evaluation", "chain_hash", "public_key", "root_digest", "signature"],
  "properties": {
    "version":      { "type": "string", "pattern": "^1\\.[0-9]+\\.[0-9]+$" },
    "format":       { "const": "forgeproof-rpack" },
    "issue":        { "type": "object", "required": ["number", "title", "url"],
                      "properties": { "number": { "type": "integer" },
                                      "title": { "type": "string" }, "url": { "type": "string" } } },
    "requirements": { "type": "array", "items": { "type": "object",
                      "required": ["id", "text", "status", "tests"],
                      "properties": { "id": { "type": "string" }, "text": { "type": "string" },
                                      "status": { "enum": ["covered", "uncovered"] },
                                      "tests": { "type": "array", "items": { "type": "string" } } } } },
    "artifacts":    { "type": "array", "items": { "type": "object",
                      "required": ["path", "operation", "sha256"],
                      "properties": { "path": { "type": "string" },
                                      "operation": { "enum": ["create", "modify"] },
                                      "sha256": { "$ref": "#/$defs/sha256hex" } } } },
    "decisions":    { "type": "array", "items": { "type": "object",
                      "required": ["context", "choice", "rationale"],
                      "properties": { "context": { "type": "string" }, "choice": { "type": "string" },
                                      "rationale": { "type": "string" } } } },
    "evaluation":   { "type": "object",
                      "required": ["status", "tests_passed", "tests_failed", "lint_errors",
                                   "requirement_coverage", "uncovered_requirements", "failed_tests"],
                      "properties": { "status": { "enum": ["pass", "partial", "fail"] },
                                      "tests_passed": { "type": "integer" },
                                      "tests_failed": { "type": "integer" },
                                      "lint_errors":  { "type": "integer" },
                                      "requirement_coverage": { "type": "string" },
                                      "uncovered_requirements": { "type": "array", "items": { "type": "string" } },
                                      "failed_tests": { "type": "array", "items": { "type": "string" } } } },
    "chain_hash":   { "$ref": "#/$defs/sha256hex" },
    "public_key":   { "type": "string", "pattern": "^ssh-ed25519 [A-Za-z0-9+/=]+( .*)?$" },
    "attestation":  { "$ref": "#/$defs/sigstoreBundle" },
    "root_digest":  { "$ref": "#/$defs/sha256hex" },
    "signature":    { "type": "string",
                      "pattern": "^-----BEGIN SSH SIGNATURE-----\\n[A-Za-z0-9+/=\\n]*-----END SSH SIGNATURE-----$" }
  },
  "$defs": {
    "sha256hex": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
    "sigstoreBundle": {
      "$comment": "Present from format 1.1.0 when the producer emitted one; absence is never inferred from version. Constrains only what the reference verifier enforces (the dsseEnvelope shape). mediaType and verificationMaterial are described, never required or constrained: the verifier reads neither, the specification forbids rejecting a document over them, and verificationMaterial is owned by the Sigstore bundle format.",
      "type": "object",
      "required": ["dsseEnvelope"],
      "properties": {
        "mediaType": { "description": "Sigstore bundle media type. The reference producer emits application/vnd.dev.sigstore.bundle.v0.3+json. Not constrained." },
        "verificationMaterial": { "description": "Opaque to this format; owned by the Sigstore bundle format. The reference producer emits {\"publicKey\": {}}. Not constrained." },
        "dsseEnvelope": {
          "type": "object",
          "required": ["payload", "payloadType", "signatures"],
          "properties": {
            "payloadType": { "const": "application/vnd.in-toto+json" },
            "payload":     { "type": "string", "pattern": "^[A-Za-z0-9+/]+={0,2}$" },
            "signatures":  { "type": "array", "minItems": 1, "maxItems": 1,
                             "items": { "type": "object", "required": ["sig"],
                                        "properties": { "sig": { "type": "string" } } } }
          }
        }
      }
    }
  }
}
```

The `version`/`attestation` relationship is deliberately expressed as "optional; shaped when present", not as `if`/`then` on `version` — the engine's own rule (`forgeproof.py:46-49`).

---

## Appendix D — Proposed `ROADMAP.md` diff (not applied; Phase 0 applies it as 🧭, Phase 5 flips to ✅)

Line numbers are against `ROADMAP.md` @ `e6aef5c` (141 lines); the `-` context lines are exact.

```diff
--- a/ROADMAP.md
+++ b/ROADMAP.md
@@ -5 +5 @@
-*Last updated: 2026-09-05 · Maintainer: [@ryanjmichie-git](https://github.com/ryanjmichie-git) · Shipped details live in [CHANGELOG.md](CHANGELOG.md)*
+*Last updated: <date Phase 0 lands> · Maintainer: [@ryanjmichie-git](https://github.com/ryanjmichie-git) · Shipped details live in [CHANGELOG.md](CHANGELOG.md)*
@@ -86,7 +86,29 @@
 **Success criteria:** the emitted attestation verifies via cosign with no ForgeProof code present; `.rpack` format remains backward-verifiable.
 
 ---
 
-### 🌅 v1.4.0 — Identity, not just integrity
+### 🧭 v1.4.0 — A name of its own
+
+**Narrative.** Infrastructure has names. The industry's attestation vocabulary — in-toto's and Sigstore's media-type strings, SLSA's predicate URIs — is still conventional, unregistered, and being formed; whatever string tools learn first for a format is what they print for a decade. Today `file` calls a `.rpack` "JSON text data" and a Linux file manager calls it plain text. This release gives the bundle a normative specification, a published schema, detection definitions, and a proposed vendor-tree media type — without changing one bundle byte. A name is not a trust signal: registration confers no endorsement, review, or standardization, and every document here says so.
+
+**Major changes**
+- **Normative `.rpack` specification.** `skills/run/references/rpack-format.md` gains a stability statement, an exact definition of the canonical serialization behind `root_digest`, and an emission profile that separates what is normative for *validity* (parsed content, digests, signatures) from what is normative for *emission* (bytes on disk). Verification requirements stated precisely: Python stdlib plus `ssh-keygen`.
+- **Published JSON Schema (2020-12)** for format 1.x at an immutable, tag-pinned `$id`; permissive on unknown members; validated in CI only — the engine still imports nothing.
+- **Detection definitions shipped, never installed.** shared-mime-info XML and a libmagic rule under `share/`, keyed on the `format` member every bundle has carried since v1.0.0, proven in CI against all four frozen fixtures and a fresh bundle — with their limits stated (plain `file` still says `application/json`; a key-sorted re-serialization is detected by name only).
+- **Proposed media type `application/vnd.forgeproof.rpack+json`** (vendor tree), submitted to IANA after the tag. Its status lives in one ledger line in `docs/media-type.md`; nothing else ever claims more than the name. `.rpack` stays; the media type is never embedded in the bundle.
+- **Fourth frozen fixture** from the v1.3.0 engine — the first with an attestation.
+
+**Success criteria:** every frozen fixture and a fresh bundle validate against the published schema in CI; the shipped MIME definition detects all of them with no bundle byte changed; all four fixtures verify with zero errors and zero warnings, strict mode included.
+
+**Out of scope:** any change to bundle bytes, `root_digest` input, the engine's behavior, hooks, skills, or the companion Action. The keyless-identity milestone below is renumbered to v1.5.0 and attested review to v1.6.0; order is unchanged.
+
+---
+
+### 🌅 v1.5.0 — Identity, not just integrity
 
 **Narrative.** Self-generated Ed25519 keys prove tamper-evidence but are ultimately self-attestation. The unresolved question in every "certified AI" debate is *who issues the stamp*. Keyless signing dissolves it: signatures bound to verifiable OIDC identities (a GitHub account, a CI runner) recorded in a public transparency log. Identity plus transparency substitutes for authority — no NATO-type certifying body required.
@@ -103 +125 @@
-### 🌅 v1.5.0 — Attested review
+### 🌅 v1.6.0 — Attested review
@@ -122 +144 @@
-- **MCP verify endpoint** so Claude web/desktop/Cowork can verify any bundle conversationally.
+- **MCP verify endpoint** so Claude web/desktop/Cowork can verify any bundle conversationally, exchanging bundles under the `application/vnd.forgeproof.rpack+json` media type (status as recorded in `docs/media-type.md` — never claimed beyond it).
@@ -138 +160 @@
-- **Bundle format:** versioned independently inside the `.rpack`; changes are additive and the verifier accepts all historical formats, forever (Principle 1).
+- **Bundle format:** versioned independently inside the `.rpack`; changes are additive and the verifier accepts all historical formats, forever (Principle 1). The on-disk serialization (member order, indentation, newline convention) is not part of the format — verifiers re-canonicalize — so no consumer, including ForgeProof's own detection rules, may rely on it beyond the spec's emission profile. One media type (`application/vnd.forgeproof.rpack+json`) names every format revision whose `format` member is `forgeproof-rpack`; `format` and `version` are the in-band identity, and the media type is never embedded in the bundle.
```

At release (Phase 5) the same block's `### 🧭 v1.4.0` becomes `### ✅ v1.4.0` and "Last updated" moves to the release date, mirroring the v1.1.0–v1.3.0 flips.
