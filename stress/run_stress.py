"""ForgeProof v1.1.0 stress harness.

Drives the REAL engine CLI through full end-to-end lifecycles on generated
sample projects of varying complexity, on every working Python interpreter
found on this machine. Python stdlib only; zero network.

Usage:
    python stress/run_stress.py                 # all scenarios
    python stress/run_stress.py --only hooks    # one scenario
    python stress/run_stress.py --list
    python stress/run_stress.py --json out.json

Exit code 0 iff every non-skipped check passed.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_projects import ISSUE_NUMBERS, NASTY_TITLE, SCENARIOS  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "skills" / "run" / "scripts" / "forgeproof.py"
TIMEOUT = 180  # the anti-hang net: nothing the engine does may take this long


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------


class Recorder:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, scenario: str, interp: str, check: str, status: str,
            detail: str = "", seconds: float = 0.0) -> None:
        self.rows.append({
            "scenario": scenario, "interpreter": interp, "check": check,
            "status": status, "detail": detail[:500],
            "seconds": round(seconds, 2),
        })
        mark = {"pass": ".", "fail": "F", "skip": "s"}[status]
        line = f"  [{mark}] {check}"
        if status != "pass":
            line += f"  <- {status.upper()}: {detail[:200]}"
        print(line, flush=True)


class CheckFailure(Exception):
    pass


def working_pythons() -> list[tuple[str, str]]:
    found = []
    for name in ("python3", "python"):
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            p = subprocess.run([exe, "--version"], capture_output=True,
                               text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if p.returncode == 0 and "Python" in (p.stdout + p.stderr):
            found.append((name, exe))
    return found


def engine(exe: str, args: list[str], cwd: Path,
           stdin_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [exe, str(ENGINE), *args], cwd=cwd, input=stdin_text,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=TIMEOUT,
    )


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def parse_json(text: str, what: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise CheckFailure(f"{what}: output is not JSON ({e}): {text[:200]}")


def run_check(rec: Recorder, scenario: str, interp: str, name: str, fn) -> None:
    start = time.monotonic()
    try:
        fn()
    except CheckFailure as e:
        rec.add(scenario, interp, name, "fail", str(e), time.monotonic() - start)
    except subprocess.TimeoutExpired as e:
        rec.add(scenario, interp, name, "fail",
                f"TIMEOUT after {TIMEOUT}s: {e.cmd}", time.monotonic() - start)
    except Exception as e:  # noqa: BLE001 - harness must report, not crash
        rec.add(scenario, interp, name, "fail",
                f"harness error: {type(e).__name__}: {e}", time.monotonic() - start)
    else:
        rec.add(scenario, interp, name, "pass", "", time.monotonic() - start)


# ---------------------------------------------------------------------------
# Generic full lifecycle (init -> records -> recheck failures -> finalize ->
# verify -> tamper matrix), parameterized per scenario
# ---------------------------------------------------------------------------


def lifecycle(rec: Recorder, scenario: str, interp_name: str, exe: str,
              proj: Path, artifacts: list[str], title: str = NASTY_TITLE,
              check_summary_encoding: bool = True) -> None:
    issue = str(ISSUE_NUMBERS[scenario])
    chain_path = proj / ".forgeproof" / f"chain-{issue}.json"
    rpack_path = proj / ".forgeproof" / f"issue-{issue}.rpack"

    def c(name, fn):
        run_check(rec, scenario, interp_name, name, fn)

    def do_init():
        p = engine(exe, ["init", "--issue", issue, "--force",
                         "--title", title,
                         "--requirement", "REQ-1: survive any shell",
                         "--requirement", "REQ-2: verify forever"], proj)
        expect(p.returncode == 0, f"init rc={p.returncode}: {p.stderr[:200]}")
        expect(chain_path.exists(), "chain file not created")
        chain = json.loads(chain_path.read_text(encoding="utf-8"))
        expect(chain[0]["data"]["title"] == title,
               f"title mangled: {chain[0]['data']['title']!r}")
    c("init: quote/unicode title survives", do_init)

    def do_records():
        p = engine(exe, ["record", "--issue", issue, "--action", "branch-create",
                         "--branch", f"forgeproof/{issue}", "--base", "main",
                         "--base-sha", "0" * 40], proj)
        expect(p.returncode == 0, f"branch-create rc={p.returncode}: {p.stderr[:200]}")
        for rel in artifacts:
            p = engine(exe, ["record", "--issue", issue, "--action", "file-edit",
                             "--path", rel, "--operation", "create"], proj)
            expect(p.returncode == 0, f"file-edit {rel} rc={p.returncode}: {p.stderr[:200]}")
            got = parse_json(p.stdout, "record")["hash"]
            expect(len(got) == 64, "record did not return a block hash")
        p = engine(exe, ["record", "--issue", issue, "--action", "decision",
                         "--context", 'why "quotes" matter', "--choice", "flags",
                         "--rationale", "no JSON to escape"], proj)
        expect(p.returncode == 0, f"decision rc={p.returncode}")
        p = engine(exe, ["record", "--issue", issue, "--action", "test-result",
                         "--suite", "pytest", "--passed", "3", "--failed", "0",
                         "--covers", "REQ-1=test_a,test_b", "--covers", "REQ-2=test_c"], proj)
        expect(p.returncode == 0, f"test-result rc={p.returncode}")
        p = engine(exe, ["record", "--issue", issue, "--action", "lint-result",
                         "--tool", "stub", "--errors", "0", "--warnings", "0"], proj)
        expect(p.returncode == 0, f"lint-result rc={p.returncode}")
    c("record: every action type via flags", do_records)

    target = proj / artifacts[0]
    original_bytes = target.read_bytes()

    def do_recheck_stale():
        target.write_bytes(original_bytes + b"# drifted after recording\n")
        chain_before = chain_path.read_bytes()
        p = engine(exe, ["finalize", "--issue", issue, "--commit", "1" * 40], proj)
        expect(p.returncode != 0, "finalize must refuse a stale artifact")
        expect("artifact recheck failed" in p.stderr, f"wrong error: {p.stderr[:200]}")
        expect("changed on disk" in p.stderr, f"missing stale detail: {p.stderr[:200]}")
        expect(chain_path.read_bytes() == chain_before,
               "refused finalize must not mutate the chain")
        # re-record the drifted file: recheck passes on the latest record
        p = engine(exe, ["record", "--issue", issue, "--action", "file-edit",
                         "--path", artifacts[0], "--operation", "modify"], proj)
        expect(p.returncode == 0, "re-record after drift failed")
    c("finalize: refuses stale artifact, chain untouched", do_recheck_stale)

    def do_recheck_missing():
        victim = proj / artifacts[-1]
        saved = victim.read_bytes()
        victim.unlink()
        try:
            p = engine(exe, ["finalize", "--issue", issue, "--commit", "1" * 40], proj)
            expect(p.returncode != 0, "finalize must refuse a missing artifact")
            expect("missing from disk" in p.stderr, f"wrong error: {p.stderr[:200]}")
        finally:
            victim.write_bytes(saved)
    c("finalize: refuses missing artifact", do_recheck_missing)

    def do_finalize():
        p = engine(exe, ["finalize", "--issue", issue, "--commit", "1" * 40], proj)
        expect(p.returncode == 0, f"finalize rc={p.returncode}: {p.stderr[:300]}")
        out = parse_json(p.stdout, "finalize")
        expect(out["evaluation_status"] == "pass", f"status={out['evaluation_status']}")
        expect(rpack_path.exists(), "rpack not written")
    c("finalize: signs clean state", do_finalize)

    def do_verify_green():
        p = engine(exe, ["verify", "--rpack",
                         str(rpack_path.relative_to(proj))], proj)
        expect(p.returncode == 0, f"verify rc={p.returncode}: {p.stdout[:300]}")
        out = parse_json(p.stdout, "verify")
        expect(out["verified"] is True and out["errors"] == [],
               f"not verified: {out['errors']}")
        expect(out["artifacts_checked"] == len(artifacts),
               f"artifacts_checked={out['artifacts_checked']} expected {len(artifacts)}")
    c("verify: green on untouched state", do_verify_green)

    def tamper_case(name, mutate, restore, expected_error):
        def fn():
            mutate()
            try:
                p = engine(exe, ["verify", "--rpack",
                                 str(rpack_path.relative_to(proj))], proj)
                expect(p.returncode == 1, f"verify must exit 1, got {p.returncode}")
                out = parse_json(p.stdout, "verify")
                expect(out["verified"] is False, "verified must be false")
                expect(any(expected_error in e for e in out["errors"]),
                       f"expected '{expected_error}' in {out['errors']}")
            finally:
                restore()
            p = engine(exe, ["verify", "--rpack",
                             str(rpack_path.relative_to(proj))], proj)
            expect(p.returncode == 0, "restore did not return verify to green")
        c(name, fn)

    art_bytes = target.read_bytes()
    tamper_case(
        "tamper: artifact byte flip -> red",
        lambda: target.write_bytes(bytes([art_bytes[0] ^ 0xFF]) + art_bytes[1:]),
        lambda: target.write_bytes(art_bytes),
        "Artifact tampered",
    )

    chain_bytes = chain_path.read_bytes()

    def mutate_chain():
        chain = json.loads(chain_bytes.decode("utf-8"))
        chain[1]["data"]["branch"] = "history/rewritten"
        chain_path.write_text(json.dumps(chain, indent=2) + "\n", encoding="utf-8")
    tamper_case(
        "tamper: chain block edit -> red",
        mutate_chain,
        lambda: chain_path.write_bytes(chain_bytes),
        "hash mismatch",
    )

    rpack_bytes = rpack_path.read_bytes()

    def mutate_signature():
        bundle = json.loads(rpack_bytes.decode("utf-8"))
        lines = bundle["signature"].splitlines()
        lines[len(lines) // 2] = lines[len(lines) // 2][::-1]
        bundle["signature"] = "\n".join(lines)
        rpack_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    tamper_case(
        "tamper: signature corruption -> red",
        mutate_signature,
        lambda: rpack_path.write_bytes(rpack_bytes),
        "signature verification FAILED",
    )

    def mutate_bundle_field():
        bundle = json.loads(rpack_bytes.decode("utf-8"))
        bundle["evaluation"]["tests_passed"] = 999
        rpack_path.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    tamper_case(
        "tamper: bundle field edit -> red",
        mutate_bundle_field,
        lambda: rpack_path.write_bytes(rpack_bytes),
        "Root digest mismatch",
    )

    if check_summary_encoding:
        def do_summary():
            p = engine(exe, ["summary", "--issue", issue], proj)
            expect(p.returncode == 0, f"summary rc={p.returncode}")
            expect("ForgeProof Provenance" in p.stdout, "summary header missing")
            expect(title.split()[0] in p.stdout or "REQ-1" in p.stdout,
                   "summary content missing")
            expect("�" not in p.stdout,
                   "mojibake in summary output (non-UTF-8 stdout on this platform)")
        c("summary: renders, UTF-8 clean", do_summary)

    def do_cleanup():
        p = engine(exe, ["reset", "--issue", issue], proj)
        expect(p.returncode == 0, "reset failed")
    c("reset: cleans own state", do_cleanup)


# ---------------------------------------------------------------------------
# Detection expectations per scenario
# ---------------------------------------------------------------------------


def detect_for(exe: str, proj: Path) -> dict:
    p = engine(exe, ["detect"], proj)
    if p.returncode != 0:
        raise CheckFailure(f"detect rc={p.returncode}: {p.stderr[:200]}")
    return parse_json(p.stdout, "detect")


def check_detection(rec: Recorder, scenario: str, interp_name: str, exe: str,
                    proj: Path) -> None:
    def c(name, fn):
        run_check(rec, scenario, interp_name, name, fn)

    if scenario == "py-minimal":
        def fn():
            d = detect_for(exe, proj)
            langs = {l["language"] for l in d.get("languages", [])}
            expect("python" in langs, f"python not detected: {langs}")
        c("detect: python via pyproject", fn)

    elif scenario == "py-venv":
        def fn():
            d = detect_for(exe, proj)
            py = next(l for l in d["languages"] if l["language"] == "python")
            argv0 = py["test_runner"]["argv"][0]
            expect(".venv" in argv0,
                   f"venv interpreter not preferred (argv[0]={argv0})")
            expect(py["runtime_available"] is True, "venv python not runnable")
        c("detect: prefers project venv interpreter", fn)

    elif scenario == "js-stub-tools":
        def fn():
            d = detect_for(exe, proj)
            js = next(l for l in d["languages"] if l["language"] == "javascript")
            expect(js["linter"] is not None and js["linter"]["name"] == "eslint",
                   f"eslint stub not detected: {js['linter']}")
            expect("node_modules" in js["linter"]["argv"][0],
                   f"eslint not filesystem-first: {js['linter']['argv'][0]}")
            expect(js["test_runner"]["name"] == "jest", "jest stub not selected")
            expect("node_modules" in js["test_runner"]["argv"][0],
                   "jest not filesystem-first")
        c("detect: JS tools filesystem-first from node_modules/.bin", fn)

        def fn_lint():
            p = engine(exe, ["lint", "--file", "index.js"], proj)
            expect("stub-finding" in (p.stdout + p.stderr),
                   f"stub linter output missing: {p.stdout[:200]}")
            expect(p.returncode == 1, f"lint rc={p.returncode} expected 1")
        c("lint --file: spawns stub linter list-form, propagates findings", fn_lint)

    elif scenario == "ts-vitest-stub":
        def fn():
            d = detect_for(exe, proj)
            js = next(l for l in d["languages"] if l["language"] == "javascript")
            if shutil.which("jest"):
                expect(js["test_runner"]["name"] in ("jest", "vitest"),
                       "no runner selected")
            else:
                expect(js["test_runner"]["name"] == "vitest",
                       f"vitest stub not selected: {js['test_runner']}")
                expect("node_modules" in js["test_runner"]["argv"][0],
                       "vitest not filesystem-first")
        c("detect: vitest selected when jest absent", fn)

    elif scenario == "go-mod":
        def fn():
            d = detect_for(exe, proj)
            go = next(l for l in d["languages"] if l["language"] == "go")
            if shutil.which("go") is None:
                expect(go["runtime_available"] is False,
                       "go runtime claimed available without go on PATH")
                expect(go["test_runner"].get("available") is False,
                       "go test claimed available without go on PATH")
        c("detect: go degrades gracefully when toolchain absent", fn)

    elif scenario == "polyglot":
        def fn():
            d = detect_for(exe, proj)
            langs = {l["language"] for l in d.get("languages", [])}
            expect({"python", "javascript", "go"} <= langs,
                   f"expected 3 languages, got {langs}")
        c("detect: polyglot finds all three languages", fn)

    elif scenario == "no-toolchain":
        def fn():
            d = detect_for(exe, proj)
            expect(d["detected"] is False, "phantom toolchain detected")
            expect("message" in d, "no explanatory message")
        c("detect: honest 'not detected' with message", fn)


# ---------------------------------------------------------------------------
# Special scenarios
# ---------------------------------------------------------------------------


def scenario_hooks(rec: Recorder, interp_name: str, exe: str, proj: Path) -> None:
    scenario = "hooks"

    def c(name, fn):
        run_check(rec, scenario, interp_name, name, fn)

    def gate(cwd: Path, tool: str, command: str) -> subprocess.CompletedProcess:
        event = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
        return engine(exe, ["gate-pr"], cwd, stdin_text=event)

    block_dir = proj / "gate-empty"
    block_dir.mkdir(exist_ok=True)

    for tool in ("Bash", "PowerShell"):
        def fn(tool=tool):
            p = gate(block_dir, tool, "gh pr create --title x --body y")
            expect(p.returncode == 2, f"{tool}: rc={p.returncode} expected 2")
            expect("BLOCK" in p.stderr, f"{tool}: stderr missing BLOCK")
            deny = parse_json(p.stdout, "gate stdout")["hookSpecificOutput"]
            expect(deny["permissionDecision"] == "deny", f"{tool}: no deny JSON")
        c(f"gate: blocks gh pr create via {tool} tool (dual protocol)", fn)

    def fn_allow_unrelated():
        p = gate(block_dir, "Bash", "git status")
        expect(p.returncode == 0 and not p.stdout.strip(),
               f"unrelated command not silently allowed: rc={p.returncode}")
    c("gate: unrelated command allowed silently", fn_allow_unrelated)

    def fn_allow_edit_tool():
        p = gate(block_dir, "Edit", "gh pr create")
        expect(p.returncode == 0, "non-shell tool must be allowed")
    c("gate: non-shell tool allowed", fn_allow_edit_tool)

    def fn_allow_with_bundle():
        bundled = proj / "gate-bundled"
        (bundled / ".forgeproof").mkdir(parents=True, exist_ok=True)
        (bundled / ".forgeproof" / "issue-1.rpack").write_text("{}", encoding="utf-8")
        p = gate(bundled, "Bash", "gh pr create --fill")
        expect(p.returncode == 0 and not p.stdout.strip(),
               f"bundle present but rc={p.returncode}")
    c("gate: allows with bundle present", fn_allow_with_bundle)

    def fn_garbage_stdin():
        p = engine(exe, ["gate-pr"], block_dir, stdin_text="}}not json{{")
        expect(p.returncode == 0, "garbage stdin must be a silent allow")
    c("gate: garbage stdin -> silent allow", fn_garbage_stdin)

    def lint_hook(cwd: Path, file_path: Path) -> subprocess.CompletedProcess:
        event = json.dumps({"tool_name": "Edit",
                            "tool_input": {"file_path": str(file_path)}})
        return engine(exe, ["lint-hook"], cwd, stdin_text=event)

    def fn_lint_silent_no_chain():
        p = lint_hook(proj, proj / "app.js")
        expect(p.returncode == 0 and not p.stdout.strip(),
               f"lint-hook must be silent without a chain: {p.stdout[:100]}")
    c("lint-hook: silent without active chain", fn_lint_silent_no_chain)

    def fn_lint_findings():
        (proj / ".forgeproof").mkdir(exist_ok=True)
        (proj / ".forgeproof" / "chain-1.json").write_text("[]", encoding="utf-8")
        p = lint_hook(proj, proj / "app.js")
        expect(p.returncode == 0, f"lint-hook must exit 0, got {p.returncode}")
        out = parse_json(p.stdout, "lint-hook")
        ctx = out["hookSpecificOutput"]["additionalContext"]
        expect("stub-finding" in ctx, f"findings missing from context: {ctx[:200]}")
        expect(out["hookSpecificOutput"]["hookEventName"] == "PostToolUse",
               "wrong hookEventName")
    c("lint-hook: surfaces stub findings during active chain", fn_lint_findings)

    def fn_lint_wrong_ext():
        p = lint_hook(proj, proj / "notes.md")
        expect(p.returncode == 0 and not p.stdout.strip(),
               ".md must not be linted by a JS linter")
    c("lint-hook: extension/language mismatch is silent", fn_lint_wrong_ext)

    def fn_lint_outside():
        outside = Path(tempfile.mkdtemp(prefix="fp-outside-")) / "x.js"
        outside.write_text("var a = 1;\n", encoding="utf-8")
        p = lint_hook(proj, outside)
        expect(p.returncode == 0 and not p.stdout.strip(),
               "file outside project must be silent")
    c("lint-hook: file outside project is silent", fn_lint_outside)

    shutil.rmtree(proj / ".forgeproof", ignore_errors=True)


def scenario_large(rec: Recorder, interp_name: str, exe: str, proj: Path) -> None:
    scenario = "large"
    issue = str(ISSUE_NUMBERS[scenario])

    def c(name, fn):
        run_check(rec, scenario, interp_name, name, fn)

    def fn():
        p = engine(exe, ["init", "--issue", issue, "--force",
                         "--title", "large project timing",
                         "--requirement", "REQ-1: stay fast"], proj)
        expect(p.returncode == 0, f"init rc={p.returncode}")
        t0 = time.monotonic()
        for i in range(50):
            p = engine(exe, ["record", "--issue", issue, "--action", "file-edit",
                             "--path", f"pkg/mod_{i:03d}.py",
                             "--operation", "create"], proj)
            expect(p.returncode == 0, f"record {i} rc={p.returncode}")
        record_s = time.monotonic() - t0
        t0 = time.monotonic()
        p = engine(exe, ["finalize", "--issue", issue, "--commit", "2" * 40], proj)
        finalize_s = time.monotonic() - t0
        expect(p.returncode == 0, f"finalize rc={p.returncode}: {p.stderr[:200]}")
        t0 = time.monotonic()
        p = engine(exe, ["verify", "--rpack", f".forgeproof/issue-{issue}.rpack"], proj)
        verify_s = time.monotonic() - t0
        expect(p.returncode == 0, "verify failed")
        out = parse_json(p.stdout, "verify")
        expect(out["artifacts_checked"] == 50,
               f"artifacts_checked={out['artifacts_checked']}")
        expect(finalize_s < 120 and verify_s < 120,
               f"too slow: finalize={finalize_s:.1f}s verify={verify_s:.1f}s")
        print(f"    timing: 50 records={record_s:.1f}s "
              f"finalize={finalize_s:.1f}s verify={verify_s:.1f}s", flush=True)
        engine(exe, ["reset", "--issue", issue], proj)
    c("large: 50 artifacts among 500 files, recheck+verify within budget", fn)


def scenario_re_edit(rec: Recorder, interp_name: str, exe: str, proj: Path) -> None:
    scenario = "re-edit-heavy"
    issue = str(ISSUE_NUMBERS[scenario])
    churn = proj / "src" / "churn.py"

    def c(name, fn):
        run_check(rec, scenario, interp_name, name, fn)

    def fn():
        p = engine(exe, ["init", "--issue", issue, "--force",
                         "--title", "re-edit dedup",
                         "--requirement", "REQ-1: one artifact entry"], proj)
        expect(p.returncode == 0, f"init rc={p.returncode}")
        for i in range(5):
            churn.write_text(f"STATE = {i}\n", encoding="utf-8")
            op = "create" if i == 0 else "modify"
            p = engine(exe, ["record", "--issue", issue, "--action", "file-edit",
                             "--path", "src/churn.py", "--operation", op], proj)
            expect(p.returncode == 0, f"record #{i} rc={p.returncode}")
        p = engine(exe, ["finalize", "--issue", issue, "--commit", "3" * 40], proj)
        expect(p.returncode == 0, f"finalize rc={p.returncode}: {p.stderr[:200]}")
        bundle = json.loads(
            (proj / ".forgeproof" / f"issue-{issue}.rpack").read_text(encoding="utf-8"))
        expect(len(bundle["artifacts"]) == 1,
               f"expected 1 deduped artifact, got {len(bundle['artifacts'])}")
        expect(bundle["artifacts"][0]["operation"] == "modify",
               "dedup must keep the LATEST record")
        p = engine(exe, ["verify", "--rpack", f".forgeproof/issue-{issue}.rpack"], proj)
        expect(p.returncode == 0, "re-edited project must verify green")
        engine(exe, ["reset", "--issue", issue], proj)
    c("re-edit: 5x same file -> single deduped artifact, verifies", fn)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

LIFECYCLE_ARTIFACTS = {
    "py-minimal": ["src/mathy.py", "src/second.py"],
    "py-venv": ["src/mathy.py"],
    "js-stub-tools": ["index.js"],
    "go-mod": ["main.go"],
    "polyglot": ["src/mathy.py", "index.js"],
    "no-toolchain": ["README.md", "notes/design.md"],
    "nasty-strings": ["src/spä ced module.py", "src/plain.py"],
}


def run_scenario(rec: Recorder, name: str, base: Path,
                 interps: list[tuple[str, str]]) -> None:
    for interp_name, exe in interps:
        print(f"\n=== {name} [{interp_name}] ===", flush=True)
        proj = SCENARIOS[name](base / interp_name)
        check_detection(rec, name, interp_name, exe, proj)
        if name in LIFECYCLE_ARTIFACTS:
            lifecycle(rec, name, interp_name, exe, proj,
                      LIFECYCLE_ARTIFACTS[name])
        elif name == "hooks":
            scenario_hooks(rec, interp_name, exe, proj)
        elif name == "large":
            scenario_large(rec, interp_name, exe, proj)
        elif name == "re-edit-heavy":
            scenario_re_edit(rec, interp_name, exe, proj)
        elif name == "ts-vitest-stub":
            pass  # detection-only scenario


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", choices=sorted(SCENARIOS),
                        help="run one scenario (repeatable)")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json", help="write machine-readable results here")
    parser.add_argument("--base", help="projects dir (default: fresh temp dir)")
    args = parser.parse_args()

    if args.list:
        print("\n".join(sorted(SCENARIOS)))
        return

    interps = working_pythons()
    if not interps:
        print("FATAL: no working python interpreter found", file=sys.stderr)
        sys.exit(2)
    if not shutil.which("ssh-keygen"):
        print("FATAL: ssh-keygen not on PATH (required for signing)",
              file=sys.stderr)
        sys.exit(2)

    base = Path(args.base) if args.base else Path(
        tempfile.mkdtemp(prefix="fp-stress-"))
    names = args.only if args.only else list(SCENARIOS)

    print(f"platform: {platform.platform()}")
    print(f"interpreters: {', '.join(f'{n} ({e})' for n, e in interps)}")
    print(f"engine: {ENGINE}")
    print(f"projects: {base}")

    rec = Recorder()
    started = time.monotonic()
    for name in names:
        run_scenario(rec, name, base, interps)

    total = time.monotonic() - started
    passed = sum(1 for r in rec.rows if r["status"] == "pass")
    failed = [r for r in rec.rows if r["status"] == "fail"]
    skipped = sum(1 for r in rec.rows if r["status"] == "skip")

    print(f"\n{'=' * 70}")
    print(f"RESULT: {passed} passed, {len(failed)} failed, {skipped} skipped "
          f"in {total:.1f}s on {platform.system()}")
    for r in failed:
        print(f"  FAIL {r['scenario']} [{r['interpreter']}] {r['check']}: "
              f"{r['detail'][:200]}")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "platform": platform.platform(),
            "system": platform.system(),
            "interpreters": [n for n, _ in interps],
            "total_seconds": round(total, 1),
            "results": rec.rows,
        }, indent=2), encoding="utf-8")
        print(f"json: {args.json}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
