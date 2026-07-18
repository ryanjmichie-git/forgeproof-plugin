# Verify on every PR: the forgeproof-verify Action and branch protection

This recipe wires the [forgeproof-verify GitHub Action](https://github.com/ryanjmichie-git/forgeproof-verify)
into a consumer repository so that every pull request carrying a ForgeProof
bundle is mechanically verified before it can merge.

## What a green check means — and what it does not

A green `forgeproof-verify` check means the bundle in the PR passed **strict**
verification:

- **Integrity** — the Ed25519 signature is valid, the root digest matches the
  bundle contents, the hash chain links correctly, and every artifact on disk
  matches its recorded SHA-256. Nothing that could be checked was altered
  after signing.
- **Completeness** — the chain file was found and no recorded artifact is
  missing from the checkout. In strict mode, absent evidence is a failure,
  not a warning.

It does **not** mean the code was reviewed, that it is correct, or that the
signer is a particular identity. ForgeProof is a self-attestation model: the
keypair is generated at run time and the public key travels inside the bundle,
so verification proves *this evidence has not been altered since it was
sealed* — it does not bind the bundle to an external identity. A green check
tells a reviewer "what you are reading is exactly what was recorded and
signed"; the reviewing is still theirs to do.

## Consumer workflow

Add `.github/workflows/verify-provenance.yml` to your repository:

```yaml
name: Verify Provenance

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write   # lets the Action upsert its audit report as a PR comment

jobs:
  verify:
    # Stable literal — this is the name to require in branch protection.
    name: forgeproof-verify
    runs-on: ubuntu-latest
    if: startsWith(github.head_ref, 'forgeproof/')
    steps:
      - uses: actions/checkout@v4
      - uses: ryanjmichie-git/forgeproof-verify@0bd8aaec4ede6a53be0ed3dbf130c22a0cbcfe8f # v1.0.2
```

Pin the Action by **full commit SHA** (as above) — that is the only reference
GitHub cannot repoint, so it is the recommended supply-chain posture for any
third-party action. `@v1` also exists as a convenience tag if you prefer
tracking non-breaking updates automatically; the SHA pin is what we recommend
and what we dogfood.

The defaults are the enforcing configuration: `strict: "true"`,
`require-bundle: "true"`, `comment: "true"`, bundle glob `.forgeproof/*.rpack`.
The audit report is always written to the job summary, and posted as a PR
comment when the token permits.

## Making the check required

The name to require is the **job name** (`forgeproof-verify`), not the
workflow name or the step name. Keep it a stable literal and unique across
your workflows.

**Rulesets (recommended)** — work on public repos on the Free plan, and let
you type the check name directly:

1. Settings → Rules → Rulesets → **New branch ruleset**
2. Target: your default branch
3. Enable **Require status checks to pass** → add check → type
   `forgeproof-verify`
4. Set enforcement to **Active** and save

**Classic branch protection** — Settings → Branches → **Add rule** → enable
*Require status checks to pass before merging* → search for
`forgeproof-verify`. Note: the search box only finds checks that have run at
least once in the repo, so open a throwaway PR from a `forgeproof/*` branch
first if the check has never run.

## The selectivity pattern

The `if: startsWith(github.head_ref, 'forgeproof/')` filter plus a GitHub
rule quirk gives you selective enforcement:

- On PRs from `forgeproof/*` branches, the job runs and must pass.
- On every other PR, the job is **skipped** — and GitHub counts a skipped
  required check as satisfied.

Result: human PRs merge freely, while any branch claiming ForgeProof
provenance must actually verify. The branch namespace is the opt-in.
`/forgeproof:push` creates branches named `forgeproof/<issue>`, so the filter
matches plugin-created PRs with no extra configuration (don't rename those
branches).

The corollary: a `.rpack` on a branch **outside** `forgeproof/*` is never
checked under this configuration, so reviewers should not assume a bundle in
the diff was verified just because the checks are green. The advisory
alternative below covers repos that want every PR checked.

**Advisory alternative:** drop the `if:` filter and set
`require-bundle: "false"`. The check then runs on every PR, verifies a bundle
whenever one is present, and stays green when there is none — useful while
trialing the Action before enforcing it.

## Fork PRs

- **Enforcement works.** The job's red/green conclusion needs no write
  permissions, so tampered or missing bundles still fail the required check
  on PRs from forks.
- **The PR comment is skipped.** Fork PRs get a read-only `GITHUB_TOKEN`, so
  the comment upsert would 403; the Action detects this and emits a
  `::notice::` instead. The full audit report always lands in the job
  summary regardless.
- **Never** switch to `pull_request_target` to restore commenting if the
  workflow checks out PR code — that hands the fork's code a write token,
  which is a well-known privilege-escalation pattern. The job summary is the
  safe channel.

## Strict vs lenient

Verification answers two different questions (see
[forgeproof-plugin#9](https://github.com/ryanjmichie-git/forgeproof-plugin/issues/9)):

- **Integrity of what is present** — was anything that *can* be checked
  tampered with?
- **Completeness of the evidence** — is everything the bundle promises
  actually here (chain file, every recorded artifact)?

Lenient mode (the engine default) fails only on tamper; missing evidence is a
warning, because a `.rpack` is a portable receipt meant to travel without its
source tree. Strict mode (`strict: "true"`, the Action default) also fails on
missing evidence.

Guidance:

- **CI in the origin repo (this recipe): strict.** The PR checkout should
  contain the full evidence set; anything missing is a real problem.
- **Ad-hoc cross-repo verification of a lone bundle: lenient.** You have the
  receipt but not the tree; `[strict] Chain file not found` /
  `[strict] Artifact not found` there means "cannot check here", not tamper.
  Drop `--strict` (or set `strict: "false"`).
