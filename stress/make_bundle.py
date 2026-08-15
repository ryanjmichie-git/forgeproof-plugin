"""Build one real attested bundle for the cosign-interop CI job.

Drives the ACTUAL engine CLI end to end (init -> records -> approval ->
finalize) in a scratch project, then prints a JSON object on stdout with the
absolute paths the job needs:

    {"project": ..., "rpack": ..., "attestation": ..., "pem": ...,
     "artifacts": [...]}

Usage: python stress/make_bundle.py [project-dir]

Python stdlib only; zero network. The interop job feeds the artifact PATHS to
cosign so it hashes the files itself — never the attestation's own digests,
which would be vacuous for tamper detection (see docs/cosign-interop.md).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "skills" / "run" / "scripts" / "forgeproof.py"
ISSUE = "321"
TIMEOUT = 180


def engine(args: list[str], cwd: Path) -> None:
    p = subprocess.run(
        [sys.executable, str(ENGINE), *args], cwd=cwd, capture_output=True,
        text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL,
    )
    if p.returncode != 0:
        sys.stderr.write(p.stdout + p.stderr)
        raise SystemExit(f"engine {args[0]} failed with rc={p.returncode}")


def main() -> None:
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = Path(tempfile.mkdtemp(prefix="fp-interop-"))
    (root / "src").mkdir(exist_ok=True)
    artifacts = []
    for i in range(3):
        rel = f"src/mod_{i}.py"
        (root / rel).write_text(f"VALUE_{i} = {i}\n", encoding="utf-8")
        artifacts.append(rel)

    engine(["init", "--issue", ISSUE, "--force", "--title", "cosign interop",
            "--requirement", "REQ-1: verify with cosign alone"], root)
    for rel in artifacts:
        engine(["record", "--issue", ISSUE, "--action", "file-edit",
                "--path", rel, "--operation", "create"], root)
    engine(["record", "--issue", ISSUE, "--action", "test-result",
            "--suite", "pytest", "--passed", "1", "--failed", "0",
            "--covers", "REQ-1=test_interop"], root)
    engine(["record", "--issue", ISSUE, "--action", "approval",
            "--gate", "plan", "--decision", "approved",
            "--note", "interop job"], root)
    engine(["finalize", "--issue", ISSUE, "--commit", "0" * 40,
            "--model", "ci-interop"], root)

    fdir = root / ".forgeproof"
    print(json.dumps({
        "project": str(root),
        "rpack": str(fdir / f"issue-{ISSUE}.rpack"),
        "attestation": str(fdir / f"issue-{ISSUE}.sigstore.json"),
        "pem": str(fdir / f"issue-{ISSUE}.pub.pem"),
        "artifacts": [str(root / a) for a in artifacts],
    }))


if __name__ == "__main__":
    main()
