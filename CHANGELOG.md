# Changelog

All notable changes to ForgeProof are documented in this file.

## [1.4.0] - 2026-09-20

"A name of its own." **No bundle byte changed**: the bundle format stays at
1.1.0, no member is added, removed, or re-typed, and the code that writes,
canonicalizes, signs, and verifies a bundle is untouched. (A bundle written
by this release differs from a v1.3.0 one only where its attestation records
the plugin version.) What the release adds is around the format, not in it:
a normative specification, a published JSON Schema, opt-in detection files,
and a media type name — `application/vnd.forgeproof.rpack+json` (vendor
tree; proposed, status in `docs/media-type.md`). A name is not a trust
signal: it changes nothing about what a bundle proves.

Every prior `.rpack` still verifies with zero errors and zero warnings,
strict mode included, now enforced in CI by **four** frozen fixtures (v1.0.1,
v1.1.0, v1.2.2, v1.3.0 engines). **forgeproof-verify v1.1.0 remains current
— the verifier is unchanged.**

### Added

- **Normative specification.** `skills/run/references/rpack-format.md` — same
  path, same `#slsa-buildtype-v1` anchor, both sealed into every attestation
  — is now the normative description of the format: a stability statement,
  an identity section, what is normative for *validity* (the member table,
  the exact canonical serialization behind `root_digest`, the canonical
  SSHSIG rule, and the four attestation checks that bind a verifier) kept
  apart from what is normative for *emission* (bytes on disk: `version` then
  `format` first, which puts the `format` marker within the first 256 bytes;
  UTF-8 without BOM; LF or CRLF), the verification requirements (Python
  3.11+ stdlib plus `ssh-keygen`), and a format-bump checklist.
- **JSON Schema for format 1.x** at `schemas/forgeproof-rpack-1.schema.json`
  (2020-12), with an immutable tag-pinned `$id`. It describes the
  specification's member table, allows unknown members at every level, and
  never infers a member from `version`; `attestation` is optional, and when
  present only `dsseEnvelope` is required of it. `verify` never reads the
  schema. Proven against the four frozen fixtures and fresh bundles only:
  v1.0.x engines accepted free-form record data, so no claim is made that
  every historical bundle validates.
- **Opt-in detection files**: `share/mime/packages/forgeproof-rpack.xml`
  (shared-mime-info) and `share/magic/forgeproof` (libmagic). **ForgeProof
  never installs them** and never runs `update-mime-database` or `xdg-mime`;
  the manual recipes are in `docs/media-type.md`, with the limits stated
  up front: plain `file` prints `application/json` unless told `-e json`,
  and a key-sorted or BOM-prefixed copy is recognized by its file name only.
- **`docs/media-type.md`**: the one ledger line that records where the media
  type's registration stands (today: not yet submitted), the RFC 6838 §5.6
  template as it will be submitted, what a registration does and does not
  change (trust, verification, GitHub: nothing), the detection recipes, the
  `.gitattributes` and editor snippets, and the known limits. Every other
  surface uses the bare type name and points there.
- **`format-identity` CI job**, the only place the consumer-side tools run
  (`jsonschema==4.26.0` installed with `--require-hashes`; `shared-mime-info`,
  `gio`, `file` with versions printed). It asserts that the four fixtures, a
  fresh bundle, and two tolerated variants validate against the schema and
  that five invalid documents fail for their intended reason; that the XML
  and the magic rule detect every fixture and a fresh bundle as written, with
  CRLF line endings, and compact; and that the documented limits hold.
- **Fourth frozen compat fixture** (`fixtures/v130/`, v1.3.0 engine, format
  1.1.0) — the first with an attestation: green lenient and strict with zero
  warnings, the three attestation checks `ok`, four tamper cases red.
- `.gitattributes`: `*.rpack linguist-language=JSON`, so bundles in this
  repo render as JSON on GitHub; the same optional line is documented for
  user repos. ForgeProof never writes it for you.
- 21 tests (290 → 311): `TestV130Compat` and `TestFormatIdentity` — spec path
  and anchor frozen, canonical form matches the spec, no floats in any
  fixture, the format marker within the first 256 bytes, schema structure,
  one spelling of the type across every surface, consumer-side tools absent
  from the engine, no skill touches repo or desktop configuration, and the
  registration-wording sweep with its one-ledger-line rule.

### Changed

- `README.md`: a "Format identity" section, the `verify` requirement stated
  in one sentence, fixture and test counts refreshed.
- `PRIVACY.md` **corrects an omission**: from v1.3.0 the attestation carries
  `startedOn` / `finishedOn` (the first and last chain block times), and the
  chain file has always recorded a time per block. Not a new disclosure —
  the data was already there; the policy now lists it. The "does not" list
  gains the MIME / `.gitattributes` / editor-settings line.
- `ROADMAP.md`: v1.4.0 is this release; the keyless-signing milestone moves
  to v1.5.0 and attested review to v1.6.0 (order unchanged).

### Compatibility

- `hooks/hooks.json` and every `SKILL.md` byte-identical to v1.3.0; no new
  preflight requirement; nothing new is installed, required, or run on a
  user's machine.
- Engine remains a single stdlib-only file with no new import; the schema
  validator and the MIME tools are CI-only and never named in it.

## [1.3.0] - 2026-08-15

"Speak the industry's language." Every bundle now *also* carries a
standards-conformant attestation — an in-toto Statement v1 with a SLSA
Provenance v1 predicate, DSSE-signed inside a Sigstore bundle by the same
ephemeral Ed25519 key that signs the chain — verifiable with plain cosign and
no ForgeProof code present. Still pure stdlib; cosign is consumer-side only.

The bundle **format version bumped, for the first time, to 1.1.0 —
additively**. Every prior `.rpack` still verifies with zero errors *and zero
warnings*, strict mode included, enforced in CI by three frozen fixtures
(v1.0.1, v1.1.0, v1.2.2 engines). In the reverse direction, a v1.1.0 bundle
verified by a **pre-v1.3 verifier is green with exactly one benign warning**
("Version mismatch: expected 1.0.0, got 1.1.0") — expected behavior, not a
failure.

### Added

- **Pure-stdlib RFC 8032 Ed25519** (sign/verify/public-from-seed), locked to
  the RFC's own test vectors and hardened for hostile input: `s >= L`
  malleability, non-canonical (`y >= p`), non-square, invalid-sign-bit, and
  wrong-length encodings are all rejected without raising. OpenSSH
  `openssh-key-v1` seed extraction dies actionably on encrypted, foreign, or
  truncated keys and refuses to sign if the derived public key does not match
  the embedded blob.
- **Attestation emission in `finalize`.** Subjects are the deduplicated
  artifacts (a zero-edit run attests the chain itself); the predicate carries
  the issue, requirements, **human approval events**, builder identity with
  per-field provenance labels (model `self-reported` via the new `--model`
  flag, Claude Code version `measured`, plugin version `engine-constant`),
  the base branch as a resolved dependency, and the chain byproduct reusing
  the sealed LF-normalized `chain_hash`. Embedded under a new top-level
  `attestation` key — inside `root_digest`, so the SSHSIG covers it — and
  exported byte-identically as `.forgeproof/issue-N.sigstore.json` with the
  key as `issue-N.pub.pem`; the ordinary seal commit stages both. The DSSE
  layout (exactly one keyid-free signature, empty `publicKey` identifier) is
  the one both pinned cosign binaries verify.
- **`approval` chain action** (`--gate`, `--decision
  approved|rejected|changes-requested`, `--note`), recorded by the run skill
  at the plan gate. The engine fills `approver` from `git config user.email`
  itself — never from a flag — degrading to `""` rather than blocking.
  Labeled `evidence: agent-recorded` in the predicate: the AI asserts the
  human approved; it is not cryptographic proof of consent.
- **Three additive verify checks**: `attestation` (statement/envelope
  well-formed, hostile payloads fail cleanly), `attestation_signature` (DSSE
  verifies under the bundle's **own** ssh-ed25519 key — the key binding is
  the point), `attestation_subjects` (signed subjects equal the bundle's
  artifacts; chain byproduct equals the sealed `chain_hash`, compared never
  recomputed). An absent attestation is **silent**: `skipped`, zero errors,
  zero warnings, in every mode including `--strict`. Real alteration is
  tamper-class; a signed-malformed attestation is VERIFICATION FAILED, never
  TAMPER. New additive result key `attestation` and a markdown report
  section with the exact cosign reproduction command.
- **Required `cosign-interop` CI job**: builds a real bundle with the actual
  engine and verifies it with **two exactly-pinned cosign binaries (v2.6.5
  and v3.1.3)** — one run per artifact with cosign hashing the file itself
  (never fed the attestation's own digest, which is vacuous for tamper), a
  `--digest` run recomputed from disk, and tampered-artifact plus
  tampered-envelope cases proven red.
- **`docs/cosign-interop.md`** (the exact tested recipe and its pitfalls) and
  **`docs/compliance-mapping.md`** (SSDF/CISA-form and EU CRA mapping as of
  2026, with the honest limits: fields required at SLSA Build L1 — no level
  claim; approvals agent-recorded; model self-reported; no compliance
  conferred).

### Changed

- **`finalize` is transactional.** The signing seed is parsed and bound to
  the published public key *before* any chain mutation, and everything after
  the chain save runs under a rollback guard: on any failure the chain file
  is restored byte-for-byte, partial outputs are removed, and the ephemeral
  key is retained so the run can simply be re-run.
- **Version recognition is membership, not equality.** `verify` accepts any
  version in `KNOWN_RPACK_VERSIONS` (append-only, membership-only, never an
  ordering) with no warning, and the format check's detail now names the
  *bundle's* version — an audit report describes the bundle, not the
  verifier. Unknown versions warn, exactly as before.
- `reset`, `init --force`, and `summary` know the attestation sidecars
  (cleanup, stale-sidecar removal, and a summary section with the cosign
  command). The PR gate and lint hook are **deliberately unchanged**:
  attestation-unaware, same budgets, same globs — verified by test.
- `PRIVACY.md` **corrects a live inaccuracy**: the bundle has always carried
  `username@hostname` in the ssh-keygen public-key comment, so the "no
  personal information" claim was false before v1.3.0 existed. It now states
  that plainly and documents the new approver-email field and sidecar files.
- **PR gate on the authoritative CI check re-pinned.** The dogfood workflow and
  the consumer recipe (`README.md`, `docs/branch-protection.md`) now pin
  `forgeproof-verify` **v1.1.0** (commit `6101dd7`), which vendors this
  v1.3.0 engine — so the authoritative PR check runs the three attestation
  checks and exposes an additive `attestation` output, while frozen v1.0.x,
  v1.1.x, and v1.2.x bundles still pass it with zero warnings.

### Compatibility

- Hooks (`hooks/hooks.json`) byte-identical; no new preflight requirements —
  cosign is never required for anything.
- Engine remains a single stdlib-only file; the only new import is `base64`.

## [1.2.2] - 2026-07-17

Hardening follow-up to v1.2.1's require-signature fix, from a second independent
review. No legitimate bundle changes verdict; both frozen compat fixtures
(v1.0.1, v1.1.0) still verify.

### Security

- **Whitespace signature malleability closed.** `signature_is_canonical` called
  `sig.strip()` before checking the SSHSIG armor, so appending whitespace (a
  newline, space, tab, or blank line) to a valid signature survived the check
  and — because `ssh-keygen -Y verify` ignores trailing bytes — still verified
  green. That violated the promise that *any* post-signing change to the
  signature turns verify red. The canonical check no longer strips; a stored
  signature is already stripped at signing time, so pristine bundles are
  unaffected while any added whitespace now turns verification red.
- **PR gate on the authoritative CI check re-pinned.** The dogfood workflow and
  the consumer recipe (`README.md`, `docs/branch-protection.md`) pinned
  `forgeproof-verify@v1.0.0`, whose vendored verifier predates the
  require-signature fix and still passed unsigned bundles. All three now pin
  **v1.0.2** (commit `0bd8aae`), which vendors this v1.2.2 engine — so the
  authoritative PR check rejects unsigned *and* whitespace-tampered bundles.
- **PR gate fails closed on crafted input.** `gate-pr` caught only
  `(OSError, ValueError)` around its bundle parse, so a deeply nested `.rpack`
  raised an uncaught `RecursionError` → exit 1 with no deny payload, which Claude
  Code treats as non-blocking (a fail-open gate bypass). It now swallows any
  parse failure and falls through to a clean block (exit 2).
- **Gate shape check tightened.** The gate accepted any non-empty
  `signature`/`public_key`/`root_digest` strings, so "a signed bundle is present"
  overstated what it checked. It now requires SSHSIG armor, an `ssh-*` public
  key, and a 64-char hex digest (still no cryptography — full verification
  remains CI's job under the 10s hook budget).

### Fixed

- **`verify` no longer tracebacks on a non-string `root_digest`.** A bundle with
  e.g. `"root_digest": 7` crashed on `stored_digest[:16]` (and, when a signature
  was present, on handing a non-string to `verify_signature`). Both paths now
  produce a clean red verdict, honoring the wrong-shape clean-error guarantee.
- **`summary` no longer tracebacks on a non-string `root_digest`.** It sliced
  `bundle['root_digest'][:16]` directly; a non-string digest now fails through
  the command's existing required-field guard like any other malformed field.
- **Deeply nested JSON dies cleanly at every entry point.** `read_json_file`
  (the shared chain/bundle reader) and the *separate* stdin-event parses in
  `gate-pr` and `lint-hook` all caught only `(json.JSONDecodeError, ValueError)`,
  so deeply nested input raised an uncaught `RecursionError`. All three now
  catch it — file reads die with an actionable error; the hooks exit cleanly
  (the gate's fail-safe is allow, lint-hook no-ops) — instead of tracebacking.

## [1.2.1] - 2026-07-17

Security patch. `verify` now requires a signature — closing a forgery hole in
which an unsigned bundle verified green. No legitimate bundle is affected:
every `.rpack` finalize produces is signed, and both frozen compat fixtures
(v1.0.1, v1.1.0) still verify, enforced in CI.

### Security

- **`verify` rejects an unsigned bundle.** A missing or blank `signature` (or a
  missing/blank `public_key`) was previously only a warning, so verification
  still passed. Because the signature is excluded from the `root_digest` (it is
  what gets signed), an attacker could rewrite a recorded artifact, re-record
  its hash, strip the signature, and recompute the keyless, public `root_digest`
  to forge `verified: true` — and the GitHub Action, which verifies with
  `--strict` by default, would show that forged PR green. `verify` now treats an
  absent signature or public key as a hard failure in every mode (not gated on
  `--strict`); the signature lives inside the `.rpack` and always travels with
  it, so its absence is never legitimate. The verdict reads `VERIFICATION
  FAILED` (not `TAMPER DETECTED`): stripping cannot be distinguished from
  never-signed, so the claim stays honest.
- **The PR gate requires a structurally valid signed bundle.** `gate-pr`
  previously allowed `gh pr create` when `.forgeproof/` held *any* file named
  `*.rpack`, so a garbage file satisfied it. It now parses each candidate and
  requires the `format`, `signature`, `public_key`, and `root_digest` fields to
  be present and non-empty. This is a fast structural check only — no
  cryptographic verification runs in the hook; that remains CI's job.

### Tests

- New `TestVerifyRequiresSignature`: deleted signature, blank signature, blank
  public key, and a full content-forge all verify red; markdown renders
  `VERIFICATION FAILED`. New `gate-pr` cases for garbage and wrong-shape
  bundles. Test fixtures that build bundles for verification now sign for real.

## [1.2.0] - 2026-07-12

"Verification by default": every PR that carries a ForgeProof bundle can now
be mechanically verified — a companion GitHub Action turns tamper or missing
evidence into a red check, and the run/push skills now guarantee the sealed
bundle is actually in the branch being verified. Bundle format unchanged —
every v1.0.x and v1.1.x `.rpack` still verifies, enforced by two frozen
fixtures in CI (v1.0.1 and v1.1.0).

### Fixed

- **The signed bundle never landed in the pushed branch.** The run skill
  committed the working tree *before* finalize produced the `.rpack`, so the
  bundle only ever existed locally — the workflow hole that would have made
  PR verification vacuous. The run skill now makes a post-finalize seal
  commit, and push refuses to proceed unless the bundle is committed at HEAD.
- `record` rejects negative `--passed`/`--failed`/`--errors`/`--warnings`
  counts and malformed `--covers` specs instead of sealing nonsense into the
  chain (issue #6).
- `record` refuses to append to a finalized chain instead of silently
  extending evidence that was already signed (issue #7).
- `detect` no longer crashes on a broken virtualenv interpreter — it falls
  back past a venv whose Python is missing or non-executable (issue #5,
  partial).

### Added

- **`verify --strict` and the `complete` output key** — verification now
  answers two questions separately: *integrity* (was anything that could be
  checked tampered with?) and *completeness* (is the chain and every recorded
  artifact actually present?). Lenient mode warns on missing evidence;
  `--strict` makes it red (issue #9).
- **`verify --project-root` and bundle-anchored path resolution** — artifact
  paths resolve relative to the bundle's location first, so a bundle
  verifies from any working directory (issue #8).
- **Structured verify JSON**: per-check `checks` array and a `bundle`
  metadata object alongside the legacy keys.
- **`verify --format markdown`** — a human audit report suitable for PR
  display, hardened against markdown/HTML injection from bundle-controlled
  strings.
- **forgeproof-verify GitHub Action** (companion repo:
  [ryanjmichie-git/forgeproof-verify](https://github.com/ryanjmichie-git/forgeproof-verify)) —
  verifies the bundle in a checked-out PR, writes the audit report to the job
  summary and as an upserted PR comment, red on tamper or missing evidence.
  This repo dogfoods it (`.github/workflows/verify-provenance.yml`), and
  `docs/branch-protection.md` is the consumer recipe: required-check setup
  (rulesets and classic), the `forgeproof/*` head-branch selectivity pattern,
  and fork-PR behavior.
- **v1.1.0 compatibility fixture** frozen in the repo with `TestV110Compat` —
  the forever contract now has two enforcement points (v1.0.1 and v1.1.0).
- README badges for CI and the companion Action.

### Changed

- `verify` JSON output gains new keys (`complete`, `checks`, `bundle`,
  `anchor`, `strict`). The legacy seven keys are byte-identical and all exit
  codes are unchanged; the new keys are purely additive, so consumers reading
  specific keys are unaffected, but whole-output comparisons will see the
  new keys.
- The push skill's PR template now mentions that bundles are verified
  automatically on PRs via the forgeproof-verify Action.

## [1.1.0] - 2026-07-03

"Runs everywhere": macOS, Windows (Git Bash and PowerShell), and minimal
Linux with no `python` symlink. Bundle format unchanged — every v1.0.x
`.rpack` still verifies, enforced by a frozen v1.0.1 fixture in CI.

### Breaking

- **Command surface renamed** (old names removed, not aliased):

  | v1.0.x | v1.1.0 |
  |--------|--------|
  | `/forgeproof <issue>` | `/forgeproof:run <issue>` |
  | `/forgeproof-push` | `/forgeproof:push` |
  | `/forgeproof-verify <path>` | `/forgeproof:verify <path>` |
  | `/forgeproof-reset <issue\|--all>` | `/forgeproof:reset <issue\|--all>` |

  No state migration needed; the `.forgeproof/` layout is unchanged.

- **`--data` removed from `init` and `record`** — quoted JSON broke on any
  shell whenever a value contained a quote character. Discrete flags replace
  it (the produced chain data is shape-identical):

  | v1.0.x | v1.1.0 |
  |--------|--------|
  | `init --data '{"title": ..., "requirements": [...]}'` | `init --title TEXT --requirement "REQ-1: text"` (repeatable) |
  | `record --action branch-create --data '{...}'` | `--branch NAME --base BASE --base-sha SHA` |
  | `record --action file-edit --data '{...}'` | `--path FILE --operation create\|modify` (engine computes the SHA-256) |
  | `record --action decision --data '{...}'` | `--context TEXT --choice TEXT --rationale TEXT` |
  | `record --action test-result --data '{...}'` | `--suite NAME --passed N --failed N [--covers "REQ-1=test_a,test_b"]... [--failed-test NAME]...` |
  | `record --action lint-result --data '{...}'` | `--tool NAME --errors N --warnings N` |

  Passing `--data` now fails with this mapping in the error message.

### Fixed

- **Signature-field malleability.** `ssh-keygen -Y verify` ignores bytes after
  the SSHSIG END marker, so the `signature` field could be altered (junk
  appended) while still verifying. Verify now also requires the signature to be
  canonical SSHSIG armor, so any post-signing change to it turns verification
  red. (Content was always protected by the root digest; no forgery was ever
  possible — this closes the cosmetic malleability.)
- **Wrong-shape (not just malformed) chain/bundle files no longer traceback.**
  A bundle whose `issue` is not an object, a chain that is `[null]` or a JSON
  object instead of a list, and an empty-object bundle passed to `summary` now
  produce a clean error or a red verdict instead of a raw AttributeError /
  TypeError / KeyError. Complements the earlier malformed-JSON hardening.
- **`preflight` could hang forever.** It probed ssh-keygen with
  `ssh-keygen -h`, which is not a help flag — it starts *interactive key
  generation* and blocks on a stdin prompt (observed freezing live sessions
  for minutes). The probe is removed (availability is a PATH lookup) and
  every engine subprocess now runs with stdin closed, so no child can ever
  block waiting for interactive input.
- **PR gate now covers the PowerShell tool.** Claude Code on Windows exposes
  a first-class PowerShell tool alongside Bash; the v1.0.x matcher (`Bash`)
  and the gate's tool check let `gh pr create` through PowerShell bypass the
  gate entirely. The matcher is now `Bash|PowerShell` and the gate accepts
  both tool names.
- **PR gate failed open on python3-only systems.** The v1.0.1 hook command
  `python3 ... gate-pr 2>/dev/null || python ... gate-pr` converted a
  legitimate block (exit 2) into `python: not found` (exit 127 —
  non-blocking) precisely on the systems the fallback targeted. Hooks are
  now two independent single-command entries (`python3` and `python`); the
  gate additionally blocks via a structured permission denial on stdout, so
  it fails closed regardless of shell exit-code translation.
- **Hook command was a PowerShell parse error.** On Windows without Git
  Bash, hooks run under PowerShell 5.1, which cannot parse `||`. No hook
  command uses shell chaining anymore.
- **Engine broke on Windows**: toolchain detection shelled out to `which`,
  `2>/dev/null`, and `| head -20`. Detection and lint now use list-form
  subprocess calls and Python-side truncation exclusively; `shell=True` no
  longer appears in the engine.
- **README pointed `claude plugin validate` at the repo root**, which
  triggers marketplace validation instead of plugin validation.
- **README overstated hook scoping** ("neither fires during normal
  sessions"); the hooks section now documents the honest per-call cost.

### Added

- **Finalize artifact recheck**: `finalize` re-hashes every recorded file
  before signing and refuses (naming the stale paths) if any changed on
  disk after recording — a signed bundle now provably matches disk at
  signing time. Bundle artifacts are deduplicated per path (latest record
  wins) so re-edited files verify correctly.
- **`lint-hook` subcommand** (new PostToolUse handler): lints only the
  edited file, only during an active run, surfaces up to 20 lines of
  findings as context, always exits 0. Replaces the full-project lint that
  previously ran on every edit.
- **Portable toolchain detection**: prefers the project's virtualenv Python
  over the engine's interpreter; JS tools are found filesystem-first in
  `node_modules/.bin` with `npx --no-install` only (never a bare `npx`
  probe, which could hit the npm registry); `detect` emits an `argv` array
  alongside each command string.
- **v1.0.1 compatibility fixture** generated with the unmodified v1.0.1
  engine and frozen in the repo; `TestV101Compat` is the forever contract
  from the roadmap's Principle 1.
- **CI platform matrix**: Ubuntu, macOS, Windows (default shell, Git Bash,
  and cmd.exe), a python3-only Debian container, and
  `claude plugin validate` against the plugin manifest (`--strict` is
  documented but not implemented on current CLI 2.1.x; CI adds it back
  once the flag exists).
- **Hook regression tests** that spawn the exact configured hook commands
  against block/allow scenarios, and a **skill-contract test** that parses
  every documented engine invocation against the real CLI.

### Changed

- Skills detect the Python interpreter once (`python3`, then `python`) and
  adapt invocation syntax to the active shell; no bare `python` assumptions
  remain anywhere.
- `lint` gained `--file` for single-file scope.
- `marketplace.json` no longer carries version fields; `plugin.json` is the
  single source of version truth (it wins anyway, so the copies were dead
  weight that could only mislead).

### Removed

- `--data` (see Breaking), `shell_run()` (the engine's last `shell=True`
  path), the `sha256sum` instruction from the skill, and both
  `marketplace.json` version fields.

### Known caveat for plugin developers

Claude Code 2.1.128 silently ignores the documented exec form for hooks
(`command` + `args` array) — the args are dropped at spawn time and
`claude plugin validate` does not flag it. ForgeProof's hooks deliberately
use single-command shell strings; do not convert them to exec form without
a live plugin-loaded retest (see the note inside `hooks/hooks.json`).

## [1.0.1] - 2026-05-12

### Fixed
- **Plugin failed to load.** `hooks/hooks.json` was missing the top-level `"hooks"` wrapper expected by Claude Code's Zod schema, producing a validation error on install (reported via `/doctor`). The events are now nested under `hooks` and the file references `https://json.schemastore.org/claude-code-settings.json` for editor validation.
- **PreToolUse PR gate never fired.** The matcher `Bash(gh pr create)` is permission-rule syntax, not hook-matcher syntax (matchers are regex against the tool name only). The gate is now a regex match on `Bash`, with the command inspection handled by a new `gate-pr` subcommand in `forgeproof.py` that parses the hook event JSON from stdin and exits with code 2 (block + surface stderr to Claude) when no `.rpack` bundle is present.
- Hook command falls back from `python3` to `python` so the gate works on Linux installs that ship only `python3` and Windows installs that ship only `python`.

### Tests
- Added `TestCmdGatePr` covering allow/block paths, unrelated commands, non-Bash tools, and malformed stdin. 44 tests pass.

## [1.0.0] - 2026-04-15

Initial public release.

### Skills
- `/forgeproof <issue>` — Full 4-phase pipeline: parse & plan, generate, evaluate, package
- `/forgeproof-push` — Push branch and create PR with provenance metadata
- `/forgeproof-verify <path>` — Verify .rpack bundle integrity (signature, chain, artifacts)
- `/forgeproof-reset <issue|--all>` — Clean up provenance state, branches, and ephemeral keys

### Provenance Engine
- Ed25519-signed SHA-256 hash chain with tamper-evident block linkage
- Ephemeral keypair generation per bundle (private key deleted after signing)
- Multi-language toolchain detection (Python, TypeScript/JavaScript, Go)
- Explicit file staging (no `git add -A`) to prevent committing generated artifacts
- Re-run handling: `--force` flag on init, graceful branch/PR detection
- `reset` subcommand for cleaning up chains, bundles, and keys

### Hooks
- PreToolUse: blocks `gh pr create` without a signed .rpack bundle
- PostToolUse: runs project linter during active ForgeProof runs (scoped to sessions with an active chain)

### Testing
- 38 automated tests covering all subcommands, chain integrity, verification, and E2E pipeline
- `claude plugin validate` passes with 0 errors
- Validated end-to-end across 4 GitHub issues on a real Python project

### Security
- No external network calls beyond `gh` CLI and `ssh-keygen`
- No telemetry, analytics, or credential persistence
- All provenance data stored locally in `.forgeproof/`
