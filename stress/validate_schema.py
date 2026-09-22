"""Validate .rpack documents against the published JSON Schema (CI only).

Positives — each MUST validate: the four frozen fixtures, one fresh bundle
built by stress/make_bundle.py with the actual engine, that bundle with an
unknown top-level member, with `mediaType` and `verificationMaterial`
removed from its `attestation`, without any `attestation` at all, at
`version` "1.0.0" (no version implies a member), with a non-string
`mediaType` and a non-object `verificationMaterial` (described, never
constrained), and with every integer count negative (the member table says
integer, with no sign restriction).

Negatives — each MUST fail, and for the intended reason: exactly one
validation error, at the expected instance path, from the expected keyword.
A negative that fails on anything else is a driver failure.

Usage: python stress/validate_schema.py

This is the ONLY file in the repository that imports `jsonschema` (pinned
with hashes in .github/jsonschema-requirements.txt). The engine and the
pytest suite never import it: baseline verification is stdlib-only by
principle. A schema-valid document is not thereby verified — digests and
signatures are the verifier's job, so the mutated copies here are not
re-signed.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "schemas" / "forgeproof-rpack-1.schema.json"
FIXTURES = REPO / "skills" / "run" / "scripts" / "fixtures"
MAKE_BUNDLE = REPO / "stress" / "make_bundle.py"
TIMEOUT = 600


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fresh_bundle(root: Path) -> dict:
    p = subprocess.run(
        [sys.executable, str(MAKE_BUNDLE), str(root)], capture_output=True,
        encoding="utf-8", errors="replace", timeout=TIMEOUT,
        stdin=subprocess.DEVNULL,
    )
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        raise SystemExit(f"make_bundle failed with rc={p.returncode}")
    return load(Path(json.loads(p.stdout)["rpack"]))


def unknown_member(b: dict) -> None:
    b["x_unknown_member"] = {"anything": [1, "two", None]}


def bare_attestation(b: dict) -> None:
    del b["attestation"]["mediaType"]
    del b["attestation"]["verificationMaterial"]


def no_attestation(b: dict) -> None:
    del b["attestation"]


def version_1_0_0(b: dict) -> None:
    b["version"] = "1.0.0"


def odd_wrapper_types(b: dict) -> None:
    b["attestation"]["mediaType"] = 7
    b["attestation"]["verificationMaterial"] = "junk"


def negative_counts(b: dict) -> None:
    b["issue"]["number"] = -1
    for key in ("tests_passed", "tests_failed", "lint_errors"):
        b["evaluation"][key] = -1


def wrong_format(b: dict) -> None:
    b["format"] = "not-forgeproof-rpack"


def missing_signature(b: dict) -> None:
    del b["signature"]


def version_2(b: dict) -> None:
    b["version"] = "2.0.0"


def two_signatures(b: dict) -> None:
    b["attestation"]["dsseEnvelope"]["signatures"].append({"sig": "AAAA"})


def float_count(b: dict) -> None:
    b["evaluation"]["tests_passed"] = 1.5


# (mutation, expected instance path, expected failing keyword)
NEGATIVES = [
    (wrong_format, "/format", "const"),
    (missing_signature, "/", "required"),
    (version_2, "/version", "pattern"),
    (two_signatures, "/attestation/dsseEnvelope/signatures", "maxItems"),
    (float_count, "/evaluation/tests_passed", "type"),
]


def main() -> None:
    schema = load(SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    def errors(doc: dict) -> list[tuple[str, str, str]]:
        return sorted(
            ("/" + "/".join(str(part) for part in e.absolute_path),
             str(e.validator), e.message)
            for e in validator.iter_errors(doc))

    with tempfile.TemporaryDirectory(prefix="fp-schema-") as tmp:
        fresh = fresh_bundle(Path(tmp) / "project")

    positives = [(str(p.relative_to(REPO).as_posix()), load(p))
                 for p in sorted(FIXTURES.glob("v*/issue-*.rpack"))]
    if len(positives) != 4:
        raise SystemExit(f"expected four frozen fixtures, found {len(positives)}")
    positives.append(("fresh bundle", fresh))
    for mutate in (unknown_member, bare_attestation, no_attestation,
                   version_1_0_0, odd_wrapper_types, negative_counts):
        doc = copy.deepcopy(fresh)
        mutate(doc)
        positives.append((f"fresh bundle + {mutate.__name__}", doc))

    failures = 0
    for label, doc in positives:
        found = errors(doc)
        failures += bool(found)
        print(f"{'FAIL' if found else 'ok  '} valid    {label}")
        for path, keyword, message in found:
            print(f"       {keyword} at {path}: {message}")

    for mutate, want_path, want_keyword in NEGATIVES:
        doc = copy.deepcopy(fresh)
        mutate(doc)
        found = errors(doc)
        good = [(p, k) for p, k, _ in found] == [(want_path, want_keyword)]
        failures += not good
        print(f"{'ok  ' if good else 'FAIL'} invalid  {mutate.__name__}: "
              f"want {want_keyword} at {want_path}")
        for path, keyword, message in found:
            print(f"       {keyword} at {path}: {message[:120]}")
        if not found:
            print("       (validated: no error at all)")

    print(f"{len(positives)} positives, {len(NEGATIVES)} negatives, "
          f"{failures} mismatches (jsonschema {version('jsonschema')})")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
