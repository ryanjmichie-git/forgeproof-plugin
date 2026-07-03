"""Tests for ForgeProof provenance engine (forgeproof.py).

Run with: python -m pytest test_forgeproof.py -v
Integration tests require ssh-keygen: python -m pytest test_forgeproof.py -m integration -v
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Import forgeproof.py as a module (it's not a package)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
FORGEPROOF_PY = SCRIPT_DIR / "forgeproof.py"
FIXTURE_V101 = SCRIPT_DIR / "fixtures" / "v101"

spec = importlib.util.spec_from_file_location("forgeproof", FORGEPROOF_PY)
fp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fp)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_chain_dir(tmp_path, monkeypatch):
    """Redirect CHAIN_DIR to a temp directory."""
    monkeypatch.setattr(fp, "CHAIN_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def sample_chain(tmp_chain_dir):
    """Create a sample initialized chain (genesis block, no real keypair)."""
    issue = "99"
    genesis = {
        "index": 0,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "action": "genesis",
        "data": {
            "issue": 99,
            "title": "Test issue",
            "requirements": ["REQ-1: Do something", "REQ-2: Test it"],
        },
        "prev_hash": fp.GENESIS_PREV_HASH,
        "hash": "",
        "signature": "",
    }
    # Compute real hash
    block_for_hash = {k: v for k, v in genesis.items() if k not in ("hash", "signature")}
    genesis["hash"] = fp.sha256_hex(fp.canonical_json(block_for_hash))

    fp.save_chain(issue, [genesis])
    return issue, [genesis]


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------


class TestSha256:
    def test_sha256_hex_empty_string(self):
        # Known SHA-256 of empty string
        assert fp.sha256_hex("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_sha256_hex_known_value(self):
        assert fp.sha256_hex("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_sha256_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert fp.sha256_file(f) == fp.sha256_hex("hello")

    def test_sha256_file_binary(self, tmp_path):
        f = tmp_path / "bin.dat"
        f.write_bytes(b"\x00\x01\x02")
        result = fp.sha256_file(f)
        assert len(result) == 64  # valid hex digest


class TestCanonicalJson:
    def test_sorted_keys(self):
        result = fp.canonical_json({"b": 2, "a": 1})
        assert result == '{"a":1,"b":2}'

    def test_no_whitespace(self):
        result = fp.canonical_json({"key": "value"})
        assert " " not in result

    def test_deterministic(self):
        obj1 = {"z": 1, "a": 2, "m": 3}
        obj2 = {"a": 2, "m": 3, "z": 1}
        assert fp.canonical_json(obj1) == fp.canonical_json(obj2)

    def test_nested(self):
        obj = {"outer": {"b": 2, "a": 1}}
        result = fp.canonical_json(obj)
        assert '"a":1' in result
        assert result.index('"a"') < result.index('"b"')


# ---------------------------------------------------------------------------
# Chain operation tests
# ---------------------------------------------------------------------------


class TestChainOperations:
    def test_chain_path(self, tmp_chain_dir):
        assert fp.chain_path("42") == tmp_chain_dir / "chain-42.json"

    def test_save_and_load_roundtrip(self, tmp_chain_dir):
        chain = [{"index": 0, "action": "genesis", "data": {}}]
        fp.save_chain("1", chain)
        loaded = fp.load_chain("1")
        assert loaded == chain

    def test_load_chain_missing_exits(self, tmp_chain_dir):
        with pytest.raises(SystemExit):
            fp.load_chain("nonexistent")

    def test_build_block_computes_hash(self):
        block = fp.build_block(
            index=0, action="genesis", data={"test": True},
            prev_hash=fp.GENESIS_PREV_HASH, key_path=None,
        )
        assert "hash" in block
        assert len(block["hash"]) == 64

    def test_build_block_hash_is_correct(self):
        block = fp.build_block(
            index=0, action="genesis", data={"test": True},
            prev_hash=fp.GENESIS_PREV_HASH, key_path=None,
        )
        # Recompute manually
        block_for_hash = {k: v for k, v in block.items() if k not in ("hash", "signature")}
        expected = fp.sha256_hex(fp.canonical_json(block_for_hash))
        assert block["hash"] == expected

    def test_build_block_chain_linkage(self):
        b0 = fp.build_block(
            index=0, action="genesis", data={},
            prev_hash=fp.GENESIS_PREV_HASH, key_path=None,
        )
        b1 = fp.build_block(
            index=1, action="file-edit", data={"path": "a.py"},
            prev_hash=b0["hash"], key_path=None,
        )
        assert b1["prev_hash"] == b0["hash"]
        assert b1["hash"] != b0["hash"]

    def test_build_block_without_key_empty_signature(self):
        block = fp.build_block(
            index=0, action="genesis", data={},
            prev_hash=fp.GENESIS_PREV_HASH, key_path=None,
        )
        assert block["signature"] == ""

    def test_get_key_path_missing(self):
        assert fp.get_key_path("nonexistent_99999") is None


# ---------------------------------------------------------------------------
# cmd_init tests
# ---------------------------------------------------------------------------


class TestCmdInit:
    def _make_args(self, issue="1", title=None, requirements=(), force=False):
        argv = ["init", "--issue", issue]
        if title is not None:
            argv += ["--title", title]
        for r in requirements:
            argv += ["--requirement", r]
        if force:
            argv.append("--force")
        return fp.build_parser().parse_args(argv)

    def _mock_keygen_and_sign(self, tmp_chain_dir):
        """Context manager that mocks both keypair generation and signing."""
        priv = tmp_chain_dir / "key"
        pub = tmp_chain_dir / "key.pub"
        priv.write_text("fake_private")
        pub.write_text("ssh-ed25519 AAAA fake")
        keygen_patch = patch.object(fp, "generate_ephemeral_keypair", return_value=(priv, pub))
        sign_patch = patch.object(fp, "sign_ed25519", return_value="fake-signature")
        return keygen_patch, sign_patch

    def test_init_creates_chain(self, tmp_chain_dir):
        keygen_patch, sign_patch = self._mock_keygen_and_sign(tmp_chain_dir)
        with keygen_patch, sign_patch, patch("sys.stdout"):
            fp.cmd_init(self._make_args(
                issue="1",
                title="Test",
                requirements=("REQ-1: Do it",),
            ))

        assert (tmp_chain_dir / "chain-1.json").exists()
        chain = json.loads((tmp_chain_dir / "chain-1.json").read_text())
        assert len(chain) == 1
        assert chain[0]["action"] == "genesis"
        assert chain[0]["data"]["title"] == "Test"
        assert chain[0]["data"]["requirements"] == ["REQ-1: Do it"]

    def test_init_title_survives_quotes(self, tmp_chain_dir):
        """The whole point of the flag surface: titles containing quote
        characters reach the chain intact (v1.0.x quoted-JSON --data broke)."""
        title = """He said "don't" — 100% of $titles `work` now"""
        keygen_patch, sign_patch = self._mock_keygen_and_sign(tmp_chain_dir)
        with keygen_patch, sign_patch, patch("sys.stdout"):
            fp.cmd_init(self._make_args(issue="8", title=title))
        chain = json.loads((tmp_chain_dir / "chain-8.json").read_text())
        assert chain[0]["data"]["title"] == title

    def test_init_data_flag_rejected(self, tmp_chain_dir, capsys):
        with pytest.raises(SystemExit) as exc_info:
            fp.build_parser().parse_args(["init", "--issue", "1", "--data", "{}"])
        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "removed in v1.1.0" in err
        assert "--title" in err

    def test_init_genesis_block_structure(self, tmp_chain_dir):
        keygen_patch, sign_patch = self._mock_keygen_and_sign(tmp_chain_dir)
        with keygen_patch, sign_patch, patch("sys.stdout"):
            fp.cmd_init(self._make_args(issue="5"))

        chain = json.loads((tmp_chain_dir / "chain-5.json").read_text())
        genesis = chain[0]
        assert genesis["index"] == 0
        assert genesis["action"] == "genesis"
        assert genesis["prev_hash"] == fp.GENESIS_PREV_HASH

    def test_init_dies_if_chain_exists_no_force(self, tmp_chain_dir):
        (tmp_chain_dir / "chain-1.json").write_text("[]")
        with pytest.raises(SystemExit):
            fp.cmd_init(self._make_args(issue="1"))

    def test_init_force_overwrites(self, tmp_chain_dir):
        (tmp_chain_dir / "chain-1.json").write_text("[]")
        (tmp_chain_dir / "issue-1.rpack").write_text("{}")

        keygen_patch, sign_patch = self._mock_keygen_and_sign(tmp_chain_dir)
        with keygen_patch, sign_patch, patch("sys.stdout"):
            fp.cmd_init(self._make_args(issue="1", force=True))

        chain = json.loads((tmp_chain_dir / "chain-1.json").read_text())
        assert len(chain) == 1
        assert chain[0]["action"] == "genesis"
        # Old rpack should be deleted
        assert not (tmp_chain_dir / "issue-1.rpack").exists()


# ---------------------------------------------------------------------------
# cmd_record tests
# ---------------------------------------------------------------------------


class TestCmdRecord:
    def _parse(self, *argv):
        return fp.build_parser().parse_args(["record", *argv])

    def _record(self, *argv):
        with patch.object(fp, "get_key_path", return_value=None), patch("sys.stdout"):
            fp.cmd_record(self._parse(*argv))

    def test_record_appends_block(self, sample_chain, tmp_chain_dir, tmp_path):
        issue, chain = sample_chain
        f = tmp_path / "test.py"
        f.write_text("print('x')\n")
        self._record("--issue", issue, "--action", "file-edit",
                     "--path", str(f), "--operation", "create")

        loaded = fp.load_chain(issue)
        assert len(loaded) == 2
        assert loaded[1]["action"] == "file-edit"
        # The engine computed the hash natively — no shell, no sha256sum
        assert loaded[1]["data"]["sha256"] == fp.sha256_file(f)

    def test_record_increments_index(self, sample_chain, tmp_chain_dir):
        issue, chain = sample_chain
        self._record("--issue", issue, "--action", "decision",
                     "--context", "test", "--choice", "a", "--rationale", "because")

        loaded = fp.load_chain(issue)
        assert loaded[1]["index"] == 1

    def test_record_links_prev_hash(self, sample_chain, tmp_chain_dir):
        issue, chain = sample_chain
        self._record("--issue", issue, "--action", "decision",
                     "--context", "c", "--choice", "x", "--rationale", "r")

        loaded = fp.load_chain(issue)
        assert loaded[1]["prev_hash"] == loaded[0]["hash"]

    def test_record_rejects_invalid_action(self, sample_chain, tmp_chain_dir, capsys):
        issue, _ = sample_chain
        with pytest.raises(SystemExit) as exc_info:
            self._parse("--issue", issue, "--action", "invalid-action")
        assert exc_info.value.code == 2
        capsys.readouterr()

    def test_record_rejects_data_flag(self, sample_chain, tmp_chain_dir, capsys):
        issue, _ = sample_chain
        with pytest.raises(SystemExit) as exc_info:
            self._parse("--issue", issue, "--action", "decision", "--data", '{"x": 1}')
        assert exc_info.value.code == 2
        err = capsys.readouterr().err
        assert "removed in v1.1.0" in err
        assert "--context" in err


class TestCmdRecordFlags:
    """The discrete-flag surface must produce data dicts byte-identical in
    shape to what the v1.0.x --data JSON produced (bundle compat)."""

    def _record(self, issue, *argv):
        with patch.object(fp, "get_key_path", return_value=None), patch("sys.stdout"):
            fp.cmd_record(fp.build_parser().parse_args(
                ["record", "--issue", issue, *argv]))

    def test_shapes_match_v101_literals(self, sample_chain, tmp_chain_dir, tmp_path):
        issue, _ = sample_chain
        f = tmp_path / "x.py"
        f.write_text("y = 1\n")
        cases = [
            (
                ["--action", "branch-create", "--branch", "forgeproof/1",
                 "--base", "main", "--base-sha", "abc123"],
                {"branch": "forgeproof/1", "base": "main", "base_sha": "abc123"},
            ),
            (
                ["--action", "file-edit", "--path", str(f), "--operation", "create"],
                {"path": str(f), "operation": "create", "sha256": fp.sha256_file(f)},
            ),
            (
                ["--action", "decision", "--context", "ctx",
                 "--choice", "ch", "--rationale", "why"],
                {"context": "ctx", "choice": "ch", "rationale": "why"},
            ),
            (
                ["--action", "test-result", "--suite", "pytest",
                 "--passed", "3", "--failed", "1",
                 "--covers", "REQ-1=test_a,test_b", "--covers", "REQ-2=test_c",
                 "--failed-test", "test_d"],
                {"suite": "pytest", "passed": 3, "failed": 1,
                 "coverage": {"REQ-1": ["test_a", "test_b"], "REQ-2": ["test_c"]},
                 "failed_tests": ["test_d"]},
            ),
            (
                ["--action", "lint-result", "--tool", "ruff",
                 "--errors", "0", "--warnings", "2"],
                {"tool": "ruff", "errors": 0, "warnings": 2},
            ),
        ]
        for argv, expected in cases:
            self._record(issue, *argv)
            assert fp.load_chain(issue)[-1]["data"] == expected, argv

    def test_shapes_match_fixture_blocks(self):
        """Key sets must equal what the real v1.0.1 engine wrote (the frozen
        fixture), not just what this suite believes v1.0.1 wrote."""
        chain = json.loads((FIXTURE_V101 / "chain-999.json").read_text())
        by_action = {b["action"]: b["data"] for b in chain}
        assert set(by_action["file-edit"]) == {"path", "operation", "sha256"}
        assert set(by_action["decision"]) == {"context", "choice", "rationale"}
        assert set(by_action["test-result"]) == {
            "suite", "passed", "failed", "coverage", "failed_tests"}

    def test_file_edit_missing_file_dies(self, sample_chain, tmp_chain_dir, capsys):
        issue, _ = sample_chain
        with pytest.raises(SystemExit):
            self._record(issue, "--action", "file-edit",
                         "--path", "does/not/exist.py", "--operation", "create")
        assert "file not found" in capsys.readouterr().err

    def test_wrong_flags_for_action_die(self, sample_chain, tmp_chain_dir, capsys):
        issue, _ = sample_chain
        with pytest.raises(SystemExit):
            self._record(issue, "--action", "decision",
                         "--context", "c", "--choice", "x", "--rationale", "r",
                         "--branch", "nope")
        err = capsys.readouterr().err
        assert "unexpected --branch" in err
        assert "--context" in err  # names the expected set

    def test_missing_required_flag_dies(self, sample_chain, tmp_chain_dir, capsys):
        issue, _ = sample_chain
        with pytest.raises(SystemExit):
            self._record(issue, "--action", "test-result", "--suite", "pytest")
        err = capsys.readouterr().err
        assert "missing" in err
        assert "--passed" in err

    def test_covers_malformed_dies(self, sample_chain, tmp_chain_dir, capsys):
        issue, _ = sample_chain
        with pytest.raises(SystemExit):
            self._record(issue, "--action", "test-result", "--suite", "pytest",
                         "--passed", "1", "--failed", "0", "--covers", "no-equals-sign")
        assert "--covers" in capsys.readouterr().err

    def test_zero_counts_are_recorded(self, sample_chain, tmp_chain_dir):
        issue, _ = sample_chain
        self._record(issue, "--action", "test-result", "--suite", "pytest",
                     "--passed", "0", "--failed", "0")
        data = fp.load_chain(issue)[-1]["data"]
        assert data["passed"] == 0 and data["failed"] == 0
        assert data["coverage"] == {} and data["failed_tests"] == []


# ---------------------------------------------------------------------------
# cmd_verify tests (using pre-built bundles)
# ---------------------------------------------------------------------------


class TestCmdVerify:
    def _build_minimal_bundle(self, tmp_chain_dir, issue="1"):
        """Build a minimal valid bundle for testing verification."""
        genesis = fp.build_block(
            index=0, action="genesis",
            data={"issue": 1, "title": "Test", "requirements": ["REQ-1: X"]},
            prev_hash=fp.GENESIS_PREV_HASH, key_path=None,
        )
        fp.save_chain(issue, [genesis])

        bundle = {
            "version": fp.RPACK_VERSION,
            "format": fp.RPACK_FORMAT,
            "issue": {"number": 1, "title": "Test", "url": ""},
            "requirements": [{"id": "REQ-1", "text": "X", "status": "covered", "tests": ["t1"]}],
            "artifacts": [],
            "decisions": [],
            "evaluation": {
                "status": "pass",
                "tests_passed": 1,
                "tests_failed": 0,
                "lint_errors": 0,
                "requirement_coverage": "100%",
                "uncovered_requirements": [],
                "failed_tests": [],
            },
            "chain_hash": fp.sha256_hex(fp.chain_path(issue).read_text()),
            "public_key": "",
        }
        root_digest = fp.sha256_hex(fp.canonical_json(bundle))
        bundle["root_digest"] = root_digest
        bundle["signature"] = ""

        rpack_path = tmp_chain_dir / f"issue-{issue}.rpack"
        rpack_path.write_text(json.dumps(bundle, indent=2))
        return rpack_path, bundle

    def test_verify_valid_bundle(self, tmp_chain_dir, capsys):
        rpack_path, _ = self._build_minimal_bundle(tmp_chain_dir)
        args = MagicMock()
        args.rpack = str(rpack_path)

        with pytest.raises(SystemExit) as exc_info:
            fp.cmd_verify(args)
        assert exc_info.value.code == 0  # verified

        output = json.loads(capsys.readouterr().out)
        assert output["verified"] is True
        assert output["errors"] == []

    def test_verify_tampered_bundle_fails(self, tmp_chain_dir, capsys):
        rpack_path, bundle = self._build_minimal_bundle(tmp_chain_dir)
        # Tamper with the bundle
        bundle["evaluation"]["tests_passed"] = 999
        rpack_path.write_text(json.dumps(bundle, indent=2))

        args = MagicMock()
        args.rpack = str(rpack_path)

        with pytest.raises(SystemExit) as exc_info:
            fp.cmd_verify(args)
        assert exc_info.value.code == 1  # failed

        output = json.loads(capsys.readouterr().out)
        assert output["verified"] is False
        assert any("Root digest mismatch" in e for e in output["errors"])

    def test_verify_missing_bundle_exits(self, tmp_chain_dir):
        args = MagicMock()
        args.rpack = str(tmp_chain_dir / "nonexistent.rpack")
        with pytest.raises(SystemExit):
            fp.cmd_verify(args)

    def test_verify_tampered_chain(self, tmp_chain_dir, capsys):
        rpack_path, bundle = self._build_minimal_bundle(tmp_chain_dir)
        # Tamper with the chain file
        chain_file = fp.chain_path("1")
        chain_file.write_text("[]")

        args = MagicMock()
        args.rpack = str(rpack_path)

        with pytest.raises(SystemExit) as exc_info:
            fp.cmd_verify(args)

        output = json.loads(capsys.readouterr().out)
        assert any("Chain hash mismatch" in e for e in output["errors"])


# ---------------------------------------------------------------------------
# cmd_detect tests
# ---------------------------------------------------------------------------


class TestCmdDetect:
    def test_detect_python_project(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        args = MagicMock()
        args.project_root = str(tmp_path)

        # Mock subprocess for runtime checks
        with patch.object(fp, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Python 3.11.0")
            fp.cmd_detect(args)

        output = json.loads(capsys.readouterr().out)
        assert output["detected"] is True
        assert output["languages"][0]["language"] == "python"

    def test_detect_no_config(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        args = MagicMock()
        args.project_root = str(tmp_path)

        fp.cmd_detect(args)

        output = json.loads(capsys.readouterr().out)
        assert output["detected"] is False


# ---------------------------------------------------------------------------
# cmd_reset tests
# ---------------------------------------------------------------------------


class TestCmdReset:
    def _make_args(self, issue=None, all_flag=False):
        args = MagicMock()
        args.issue = issue
        # Use setattr for 'all' since it's a keyword
        args.all = all_flag
        return args

    def test_reset_single_issue(self, tmp_chain_dir, capsys):
        (tmp_chain_dir / "chain-5.json").write_text("[]")
        (tmp_chain_dir / "issue-5.rpack").write_text("{}")

        fp.cmd_reset(self._make_args(issue="5"))

        assert not (tmp_chain_dir / "chain-5.json").exists()
        assert not (tmp_chain_dir / "issue-5.rpack").exists()
        output = json.loads(capsys.readouterr().out)
        assert output["count"] == 2

    def test_reset_all(self, tmp_chain_dir, capsys):
        (tmp_chain_dir / "chain-1.json").write_text("[]")
        (tmp_chain_dir / "chain-2.json").write_text("[]")
        (tmp_chain_dir / "issue-1.rpack").write_text("{}")

        fp.cmd_reset(self._make_args(all_flag=True))

        assert not (tmp_chain_dir / "chain-1.json").exists()
        assert not (tmp_chain_dir / "chain-2.json").exists()
        assert not (tmp_chain_dir / "issue-1.rpack").exists()
        output = json.loads(capsys.readouterr().out)
        assert output["count"] == 3

    def test_reset_nonexistent_issue(self, tmp_chain_dir, capsys):
        fp.cmd_reset(self._make_args(issue="999"))
        output = json.loads(capsys.readouterr().out)
        assert output["count"] == 0

    def test_reset_no_args_exits(self, tmp_chain_dir):
        with pytest.raises(SystemExit):
            fp.cmd_reset(self._make_args())


# ---------------------------------------------------------------------------
# cmd_summary tests
# ---------------------------------------------------------------------------


class TestCmdSummary:
    def test_summary_outputs_markdown(self, tmp_chain_dir, capsys):
        bundle = {
            "version": fp.RPACK_VERSION,
            "format": fp.RPACK_FORMAT,
            "issue": {"number": 1, "title": "Test", "url": ""},
            "requirements": [{"id": "REQ-1", "text": "Do it", "status": "covered", "tests": ["test_x"]}],
            "artifacts": [{"path": "src/a.py", "operation": "create", "sha256": "abc"}],
            "decisions": [],
            "evaluation": {
                "status": "pass", "tests_passed": 5, "tests_failed": 0,
                "lint_errors": 0, "requirement_coverage": "100%",
                "uncovered_requirements": [], "failed_tests": [],
            },
            "root_digest": "abc123",
            "public_key": "",
            "signature": "",
            "chain_hash": "",
        }
        (tmp_chain_dir / "issue-1.rpack").write_text(json.dumps(bundle))

        args = MagicMock()
        args.issue = "1"
        fp.cmd_summary(args)

        output = capsys.readouterr().out
        assert "## ForgeProof Provenance" in output
        assert "REQ-1" in output
        assert "PASS" in output
        assert "test_x" in output

    def test_summary_missing_rpack_exits(self, tmp_chain_dir):
        args = MagicMock()
        args.issue = "999"
        with pytest.raises(SystemExit):
            fp.cmd_summary(args)


class TestCmdGatePr:
    """PreToolUse hook gate for 'gh pr create'."""

    def _run_gate(self, event: dict | str | None) -> int:
        stdin_text = "" if event is None else (
            event if isinstance(event, str) else json.dumps(event)
        )
        with patch("sys.stdin", new=__import__("io").StringIO(stdin_text)):
            with pytest.raises(SystemExit) as exc_info:
                fp.cmd_gate_pr(MagicMock())
        code = exc_info.value.code
        return 0 if code is None else code

    def test_allows_when_bundle_exists(self, tmp_chain_dir):
        (tmp_chain_dir / "issue-1.rpack").write_text("{}")
        event = {"tool_name": "Bash", "tool_input": {"command": "gh pr create --fill"}}
        assert self._run_gate(event) == 0

    def test_blocks_when_no_bundle(self, tmp_chain_dir, capsys):
        event = {"tool_name": "Bash", "tool_input": {"command": "gh pr create --fill"}}
        assert self._run_gate(event) == 2
        captured = capsys.readouterr()
        assert "BLOCK" in captured.err
        # Dual-protocol: deny JSON on stdout for exit-code-independent blocking
        decision = json.loads(captured.out)["hookSpecificOutput"]
        assert decision["permissionDecision"] == "deny"
        assert decision["hookEventName"] == "PreToolUse"

    def test_allows_unrelated_bash_command(self, tmp_chain_dir):
        event = {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        assert self._run_gate(event) == 0

    def test_allows_non_bash_tool(self, tmp_chain_dir):
        event = {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x"}}
        assert self._run_gate(event) == 0

    def test_allows_when_stdin_unparseable(self, tmp_chain_dir):
        assert self._run_gate("not json {") == 0

    def test_allows_when_stdin_empty(self, tmp_chain_dir):
        assert self._run_gate("") == 0


# ---------------------------------------------------------------------------
# cmd_finalize artifact recheck
# ---------------------------------------------------------------------------


class TestFinalizeRecheck:
    """finalize must refuse to sign a bundle whose recorded artifacts no
    longer match disk — and must not corrupt the chain when it refuses."""

    def _setup(self, tmp_chain_dir, tmp_path, monkeypatch, issue="3"):
        monkeypatch.chdir(tmp_path)
        priv = tmp_path / "key"
        pub = tmp_path / "key.pub"
        priv.write_text("fake_private")
        pub.write_text("ssh-ed25519 AAAA fake")
        artifact = tmp_path / "art.py"
        artifact.write_text("a = 1\n")
        with patch.object(fp, "generate_ephemeral_keypair", return_value=(priv, pub)), \
             patch.object(fp, "sign_ed25519", return_value="sig"), patch("sys.stdout"):
            fp.cmd_init(fp.build_parser().parse_args(
                ["init", "--issue", issue, "--title", "recheck", "--force"]))
        self._record(issue, priv, "--action", "file-edit",
                     "--path", "art.py", "--operation", "create")
        return issue, artifact, priv

    def _record(self, issue, priv, *argv):
        with patch.object(fp, "get_key_path", return_value=priv), \
             patch.object(fp, "sign_ed25519", return_value="sig"), patch("sys.stdout"):
            fp.cmd_record(fp.build_parser().parse_args(
                ["record", "--issue", issue, *argv]))

    def _finalize(self, issue, priv):
        args = fp.build_parser().parse_args(
            ["finalize", "--issue", issue, "--commit", "0" * 40])
        with patch.object(fp, "get_key_path", return_value=priv), \
             patch.object(fp, "sign_ed25519", return_value="sig"), \
             patch.object(fp, "delete_private_key"), \
             patch.object(fp.shutil, "which", return_value=None), \
             patch("sys.stdout"):
            fp.cmd_finalize(args)

    def test_finalize_dies_on_stale_artifact(
            self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        issue, artifact, priv = self._setup(tmp_chain_dir, tmp_path, monkeypatch)
        chain_len_before = len(fp.load_chain(issue))
        artifact.write_text("a = 2  # modified after recording\n")

        with pytest.raises(SystemExit):
            self._finalize(issue, priv)
        err = capsys.readouterr().err
        assert "artifact recheck failed" in err
        assert "art.py" in err
        # The refused finalize must not have appended a finalize block
        assert len(fp.load_chain(issue)) == chain_len_before

    def test_finalize_dies_on_missing_artifact(
            self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        issue, artifact, priv = self._setup(tmp_chain_dir, tmp_path, monkeypatch)
        artifact.unlink()
        with pytest.raises(SystemExit):
            self._finalize(issue, priv)
        assert "missing from disk" in capsys.readouterr().err

    def test_finalize_succeeds_when_clean(
            self, tmp_chain_dir, tmp_path, monkeypatch):
        issue, artifact, priv = self._setup(tmp_chain_dir, tmp_path, monkeypatch)
        self._finalize(issue, priv)
        bundle = json.loads((tmp_chain_dir / f"issue-{issue}.rpack").read_text())
        assert bundle["artifacts"] == [
            {"path": "art.py", "operation": "create",
             "sha256": fp.sha256_file(artifact)}]

    def test_reedited_file_rechecks_latest_and_dedups(
            self, tmp_chain_dir, tmp_path, monkeypatch):
        """Earlier records of a re-edited file are superseded, not stale: the
        recheck uses the latest record per path, and the bundle lists the file
        once with the hash that matches disk."""
        issue, artifact, priv = self._setup(tmp_chain_dir, tmp_path, monkeypatch)
        artifact.write_text("a = 2\n")
        self._record(issue, priv, "--action", "file-edit",
                     "--path", "art.py", "--operation", "modify")
        self._finalize(issue, priv)
        bundle = json.loads((tmp_chain_dir / f"issue-{issue}.rpack").read_text())
        assert bundle["artifacts"] == [
            {"path": "art.py", "operation": "modify",
             "sha256": fp.sha256_file(artifact)}]


# ---------------------------------------------------------------------------
# cmd_lint_hook (PostToolUse hook)
# ---------------------------------------------------------------------------


class TestCmdLintHook:
    def _invoke(self, stdin_text: str) -> int:
        with patch("sys.stdin", io.StringIO(stdin_text)):
            with pytest.raises(SystemExit) as exc_info:
                fp.cmd_lint_hook(MagicMock())
        code = exc_info.value.code
        return 0 if code is None else code

    def _detection(self, argv=("lintx", "check", "."), language="python"):
        return {"detected": True, "languages": [{
            "language": language,
            "config_files": ["pyproject.toml"],
            "runtime_available": True,
            "test_runner": None,
            "linter": {"name": "lintx", "command": " ".join(argv), "argv": list(argv)},
        }]}

    def _event(self, path) -> str:
        return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})

    def test_malformed_stdin_silent(self, tmp_chain_dir, capsys):
        assert self._invoke("not json {") == 0
        assert capsys.readouterr().out == ""

    def test_no_active_chain_silent(self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1\n")
        # No chain-*.json in CHAIN_DIR: the hook must not even detect/lint
        with patch.object(fp, "detect_toolchain",
                          side_effect=AssertionError("must not detect without a chain")):
            assert self._invoke(self._event(target)) == 0
        assert capsys.readouterr().out == ""

    def _activate_chain(self, tmp_chain_dir):
        (tmp_chain_dir / "chain-1.json").write_text("[]")

    def test_clean_file_silent(self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        self._activate_chain(tmp_chain_dir)
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1\n")
        clean = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with patch.object(fp, "detect_toolchain", return_value=self._detection()), \
             patch.object(fp, "run", return_value=clean) as mock_run:
            assert self._invoke(self._event(target)) == 0
        assert capsys.readouterr().out == ""
        # Lint ran against the single edited file, not the project
        assert mock_run.call_args[0][0] == ["lintx", "check", "x.py"]

    def test_findings_emitted_as_additional_context(
            self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        self._activate_chain(tmp_chain_dir)
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("import os\n")
        dirty = subprocess.CompletedProcess(
            [], 1, stdout="x.py:1:1: F401 'os' imported but unused\n", stderr="")
        with patch.object(fp, "detect_toolchain", return_value=self._detection()), \
             patch.object(fp, "run", return_value=dirty):
            assert self._invoke(self._event(target)) == 0  # findings never block
        out = json.loads(capsys.readouterr().out)
        hook_out = out["hookSpecificOutput"]
        assert hook_out["hookEventName"] == "PostToolUse"
        assert "F401" in hook_out["additionalContext"]
        assert "x.py" in hook_out["additionalContext"]

    def test_findings_truncated_to_20_lines(
            self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        self._activate_chain(tmp_chain_dir)
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "x.py"
        target.write_text("x = 1\n")
        many = "\n".join(f"x.py:{i}:1: E501 line too long" for i in range(1, 100))
        dirty = subprocess.CompletedProcess([], 1, stdout=many, stderr="")
        with patch.object(fp, "detect_toolchain", return_value=self._detection()), \
             patch.object(fp, "run", return_value=dirty):
            self._invoke(self._event(target))
        context = json.loads(capsys.readouterr().out)[
            "hookSpecificOutput"]["additionalContext"]
        # header line + at most 20 finding lines
        assert len(context.splitlines()) <= 21

    def test_file_outside_project_silent(
            self, tmp_chain_dir, tmp_path, monkeypatch, capsys, tmp_path_factory):
        self._activate_chain(tmp_chain_dir)
        monkeypatch.chdir(tmp_path)
        outside = tmp_path_factory.mktemp("elsewhere") / "y.py"
        outside.write_text("y = 1\n")
        with patch.object(fp, "detect_toolchain",
                          side_effect=AssertionError("must not lint outside files")):
            assert self._invoke(self._event(outside)) == 0
        assert capsys.readouterr().out == ""

    def test_extension_language_mismatch_silent(
            self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        self._activate_chain(tmp_chain_dir)
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "notes.md"
        target.write_text("# notes\n")
        with patch.object(fp, "detect_toolchain", return_value=self._detection()), \
             patch.object(fp, "run",
                          side_effect=AssertionError("must not lint .md with a python linter")):
            assert self._invoke(self._event(target)) == 0
        assert capsys.readouterr().out == ""

    def test_project_scope_linter_skipped(
            self, tmp_chain_dir, tmp_path, monkeypatch, capsys):
        """golangci-lint has no per-file mode; the hook must not run a
        project-wide lint on every edit (that is the v1.0.x behavior this
        release removes)."""
        self._activate_chain(tmp_chain_dir)
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "m.go"
        target.write_text("package m\n")
        detection = self._detection(argv=("golangci-lint", "run"), language="go")
        with patch.object(fp, "detect_toolchain", return_value=detection), \
             patch.object(fp, "run",
                          side_effect=AssertionError("must not run project-scope lint")):
            assert self._invoke(self._event(target)) == 0
        assert capsys.readouterr().out == ""


# ---------------------------------------------------------------------------
# Portable toolchain detection
# ---------------------------------------------------------------------------


class TestDetectPortable:
    def test_find_project_python_prefers_venv(self, tmp_path):
        if os.name == "nt":
            venv_py = tmp_path / ".venv" / "Scripts" / "python.exe"
        else:
            venv_py = tmp_path / ".venv" / "bin" / "python"
        venv_py.parent.mkdir(parents=True)
        venv_py.write_text("")
        assert fp.find_project_python(tmp_path) == str(venv_py)

    def test_find_project_python_falls_back_to_engine(self, tmp_path):
        assert fp.find_project_python(tmp_path) == sys.executable

    def test_find_js_tool_filesystem_first(self, tmp_path, monkeypatch):
        bin_dir = tmp_path / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        for name in ("eslint", "eslint.cmd", "eslint.exe"):
            (bin_dir / name).write_text("")
        monkeypatch.setattr(fp.shutil, "which",
                            lambda _: pytest.fail("PATH consulted before node_modules/.bin"))
        found = fp.find_js_tool(tmp_path, "eslint")
        assert found is not None
        assert "node_modules" in found

    def test_find_js_tool_never_probes_npx(self, tmp_path, monkeypatch):
        """A missing JS tool is 'unavailable', never a network fetch."""
        monkeypatch.setattr(fp.shutil, "which", lambda _: None)
        with patch.object(fp, "run",
                          side_effect=AssertionError("no subprocess probes for JS tools")):
            assert fp.find_js_tool(tmp_path, "eslint") is None

    def test_detect_structured_no_shell(self, tmp_path, monkeypatch):
        """Simulated minimal machine (nothing on PATH): detection must use
        list-form subprocess calls only and degrade gracefully."""
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "package.json").write_text("{}\n")
        (tmp_path / "go.mod").write_text("module x\n")
        monkeypatch.setattr(fp.shutil, "which", lambda _: None)

        calls = []

        def fake_run(cmd, **kwargs):
            assert isinstance(cmd, list), f"string command passed to run(): {cmd!r}"
            assert not kwargs.get("shell"), f"shell=True used: {cmd!r}"
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(fp, "run", fake_run)
        result = fp.detect_toolchain(tmp_path)

        assert result["detected"] is True
        langs = {l["language"]: l for l in result["languages"]}
        assert set(langs) == {"python", "javascript", "go"}
        # No node on PATH, no node_modules: JS runtime and tools unavailable
        assert langs["javascript"]["runtime_available"] is False
        assert langs["javascript"]["linter"] is None
        assert langs["javascript"]["test_runner"]["available"] is False
        assert langs["go"]["runtime_available"] is False
        # Python probes ran (list-form) and produced argv + command pairs
        assert calls
        runner = langs["python"]["test_runner"]
        assert isinstance(runner["argv"], list)
        assert all(isinstance(a, str) for a in runner["argv"])
        assert isinstance(runner["command"], str)

    def test_engine_source_has_no_shell_isms(self):
        source = FORGEPROOF_PY.read_text()
        for banned in ("shell=True", "sha256sum", "head -20", "2>/dev/null",
                       '"which ', "shell_run"):
            assert banned not in source, f"shell-ism found in engine: {banned}"


# ---------------------------------------------------------------------------
# Hooks configuration (the loud PR-gate regression test)
# ---------------------------------------------------------------------------

PLUGIN_ROOT = SCRIPT_DIR.parents[2]
HOOKS_JSON = PLUGIN_ROOT / "hooks" / "hooks.json"


class TestHooksConfig:
    """Guards the v1.0.0 silent-failure class: these tests assert the exact
    matcher and handler shape AND spawn the exact configured commands against
    a block-scenario event. A never-fires misconfiguration (wrong matcher,
    wrong path, wrong form) fails loudly here — it cannot pass silently.

    Shape note: entries are single-command SHELL strings, not exec-form
    (command + args array). Exec form is documented, but Claude Code 2.1.128
    silently ignored the args array at runtime (verified live 2026-07-03):
    the manager spawned a bare `python`, which swallowed the stdin event and
    exited 0 — the gate never fired and nothing errored. Keep these tests
    asserting shell-string form until a live plugin-loaded retest proves
    exec form works."""

    _COMMAND_RE = re.compile(
        r'^(python3?) "\$\{CLAUDE_PLUGIN_ROOT\}/skills/[^"]+/forgeproof\.py" (gate-pr|lint-hook)$'
    )

    def _config(self) -> dict:
        return json.loads(HOOKS_JSON.read_text(encoding="utf-8"))

    def _argv(self, handler) -> list[str]:
        """The argv the shell would produce from the configured command, with
        ${CLAUDE_PLUGIN_ROOT} substituted the way Claude Code does."""
        resolved = handler["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))
        return shlex.split(resolved)

    def _real_interpreters(self, handlers):
        """(handler, argv) for each handler whose interpreter is a *working*
        Python — on Windows, `python3` may resolve to the Microsoft Store
        stub, which exists on PATH but is not an interpreter (exactly the
        case the dual-entry design tolerates: its noise is non-blocking while
        the real interpreter delivers the verdict)."""
        available = []
        for handler in handlers:
            argv = self._argv(handler)
            exe = shutil.which(argv[0])
            if not exe:
                continue
            probe = subprocess.run([exe, "--version"], capture_output=True, text=True)
            if probe.returncode == 0 and "Python" in (probe.stdout + probe.stderr):
                available.append((handler, [exe] + argv[1:]))
        return available

    def test_structure(self):
        cfg = self._config()
        hooks = cfg["hooks"]  # top-level wrapper required by the plugin schema
        assert set(hooks) == {"PreToolUse", "PostToolUse"}

        pre = hooks["PreToolUse"]
        assert len(pre) == 1
        assert pre[0]["matcher"] == "Bash"
        post = hooks["PostToolUse"]
        assert len(post) == 1
        assert post[0]["matcher"] == "Edit|Write"

        for event_name, subcommand in (("PreToolUse", "gate-pr"),
                                       ("PostToolUse", "lint-hook")):
            handlers = hooks[event_name][0]["hooks"]
            interpreters = []
            for handler in handlers:
                assert handler["type"] == "command"
                assert isinstance(handler["timeout"], int)
                m = self._COMMAND_RE.match(handler["command"])
                assert m, (
                    f"hook command must be a single quoted engine invocation: "
                    f"{handler['command']}")
                assert m.group(2) == subcommand
                interpreters.append(m.group(1))
                # script path resolves to a real file
                argv = self._argv(handler)
                assert Path(argv[1]).is_file(), f"hook target missing: {argv[1]}"
            # dual interpreter, python3 first
            assert interpreters == ["python3", "python"]

    def test_no_shell_chaining_in_hooks(self):
        """The v1.0.1 fail-open bug lived in shell chaining (`||` converted a
        block into exit 127) and PowerShell 5.1 cannot even parse `||`. Each
        command must stay a single simple invocation."""
        cfg = self._config()
        for event in cfg["hooks"].values():
            for entry in event:
                for handler in entry["hooks"]:
                    cmd = handler["command"]
                    for banned in ("||", "&&", "2>/dev/null", "|", ";", "$(", ">"):
                        assert banned not in cmd, (
                            f"shell syntax crept back into hook command: "
                            f"{banned!r} in {cmd}")

    def test_matcher_semantics(self):
        """Matchers are exact-or-regex against the tool NAME only. The v1.0.0
        bug was permission-rule syntax ('Bash(gh pr create)') here — assert
        exact equality so any drift fails CI."""
        cfg = self._config()
        pre_matcher = cfg["hooks"]["PreToolUse"][0]["matcher"]
        assert pre_matcher == "Bash"
        assert re.fullmatch(pre_matcher, "Bash")
        assert not re.fullmatch(pre_matcher, "Edit")
        assert pre_matcher != "Bash(gh pr create)"

        post_matcher = cfg["hooks"]["PostToolUse"][0]["matcher"]
        assert re.fullmatch(post_matcher, "Edit")
        assert re.fullmatch(post_matcher, "Write")
        assert not re.fullmatch(post_matcher, "Bash")

    def test_gate_dispatch_blocks_without_bundle(self, tmp_path):
        """Spawn the exact configured command the way the hook manager would:
        event JSON on stdin, cwd without a bundle. Must block via BOTH
        protocols: permissionDecision deny JSON on stdout (shell- and
        exit-code-independent) and exit 2 with the reason on stderr."""
        entry = self._config()["hooks"]["PreToolUse"][0]
        event = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "gh pr create --title x"}})
        assert re.fullmatch(entry["matcher"], "Bash")

        available = self._real_interpreters(entry["hooks"])
        assert available, "no working python interpreter found on this machine"
        for handler, argv in available:
            result = subprocess.run(argv, input=event, capture_output=True,
                                    text=True, cwd=tmp_path,
                                    timeout=handler["timeout"])
            assert result.returncode == 2, (
                f"gate must BLOCK (exit 2), got {result.returncode}; "
                f"stderr: {result.stderr}")
            assert ".rpack" in result.stderr
            decision = json.loads(result.stdout)["hookSpecificOutput"]
            assert decision["hookEventName"] == "PreToolUse"
            assert decision["permissionDecision"] == "deny"
            assert ".rpack" in decision["permissionDecisionReason"]

    def test_gate_dispatch_allows_with_bundle(self, tmp_path):
        entry = self._config()["hooks"]["PreToolUse"][0]
        event = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "gh pr create --title x"}})
        (tmp_path / ".forgeproof").mkdir()
        (tmp_path / ".forgeproof" / "issue-1.rpack").write_text("{}")

        available = self._real_interpreters(entry["hooks"])
        assert available
        for handler, argv in available:
            result = subprocess.run(argv, input=event, capture_output=True,
                                    text=True, cwd=tmp_path,
                                    timeout=handler["timeout"])
            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == ""  # silence = defer to normal flow

    def test_lint_hook_dispatch_silent_without_chain(self, tmp_path):
        entry = self._config()["hooks"]["PostToolUse"][0]
        target = tmp_path / "x.py"
        target.write_text("x = 1\n")
        event = json.dumps(
            {"tool_name": "Edit", "tool_input": {"file_path": str(target)}})

        available = self._real_interpreters(entry["hooks"])
        assert available
        for handler, argv in available:
            result = subprocess.run(argv, input=event, capture_output=True,
                                    text=True, cwd=tmp_path,
                                    timeout=handler["timeout"])
            assert result.returncode == 0
            assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# Skill contract: SKILL.md examples must parse against the real CLI
# ---------------------------------------------------------------------------

SKILLS_DIR = SCRIPT_DIR.parent.parent

_REDIRECT_TOKENS = {">", ">>", "|", "||", "&&", ";", "2>&1"}


def _extract_engine_argvs(text: str):
    """Yield (line, argv) for each engine invocation in fenced code blocks."""
    for fence in re.findall(r"```[^\n]*\n(.*?)```", text, re.DOTALL):
        joined = re.sub(r"\\\n\s*", " ", fence)  # join line continuations
        for raw in joined.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "$FP" not in line and "forgeproof.py" not in line:
                continue
            # unwrap VAR=$(engine ...) command substitutions
            m = re.match(r"^(?:export\s+)?[A-Za-z_]\w*=\$\((.+)\)$", line)
            if m:
                line_cmd = m.group(1).strip()
            elif re.match(r"^(?:export\s+)?[A-Za-z_]\w*=", line):
                continue  # plain assignment, e.g. FP=${CLAUDE_PLUGIN_ROOT}/...
            else:
                line_cmd = line
            line_cmd = line_cmd.replace("$(git rev-parse HEAD)", "0" * 40)
            tokens = shlex.split(line_cmd)
            # locate the engine script token
            idx = None
            for i, tok in enumerate(tokens):
                if tok == "$FP" or tok.endswith("forgeproof.py"):
                    idx = i
                    break
            if idx is None:
                continue
            argv = tokens[idx + 1:]
            for stop in _REDIRECT_TOKENS:
                if stop in argv:
                    argv = argv[:argv.index(stop)]
            # placeholders and shell variables -> parseable dummies
            argv = [re.sub(r"<[^<>]+>", "1", tok) for tok in argv]
            argv = [re.sub(r"\$\{?\w+\}?", "1", tok) for tok in argv]
            yield line, argv


class TestSkillContract:
    """Every engine invocation documented in any SKILL.md must parse against
    the real argparse surface — a stale example is a loud CI failure, not a
    silent runtime break inside a Claude session."""

    @pytest.mark.xfail(
        reason="SKILL.md examples still use the removed v1.0.x --data surface; "
               "rewritten in the skill-instructions phase of the v1.1.0 release",
        strict=True,
    )
    def test_skill_examples_parse(self, capsys):
        failures = []
        checked = 0
        for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            for line, argv in _extract_engine_argvs(skill_md.read_text(encoding="utf-8")):
                checked += 1
                try:
                    fp.build_parser().parse_args(argv)
                except SystemExit as e:
                    if e.code not in (0, None):
                        failures.append(f"{skill_md.parent.name}: {line}")
        capsys.readouterr()  # swallow argparse usage noise
        assert checked >= 5, (
            f"only {checked} engine invocations found across SKILL.md files — "
            "the extractor is broken or the skills no longer document the engine"
        )
        assert failures == [], "\n".join(failures)


# ---------------------------------------------------------------------------
# v1.0.x compatibility (forever contract — ROADMAP Principle 1)
# ---------------------------------------------------------------------------


class TestV101Compat:
    """The checked-in fixture bundle was generated by the unmodified v1.0.1
    engine. Any `.rpack` ever signed must verify with every future version of
    the verifier — this test must never be weakened and the fixture must never
    be regenerated. If a change breaks it, the change is wrong.
    """

    def _require_sshkeygen(self):
        # The fixture carries a real Ed25519 signature. In CI this dependency
        # is guaranteed (installed in every job); locally, skip rather than
        # error on machines without OpenSSH.
        if not shutil.which("ssh-keygen"):
            if os.environ.get("CI"):
                pytest.fail("ssh-keygen missing in CI — compat test must not be skipped")
            pytest.skip("ssh-keygen not available")

    def _deploy(self, tmp_path):
        """Lay the fixture out the way a real checkout looks: chain and bundle
        under .forgeproof/, artifact at its recorded relative path."""
        chain_dir = tmp_path / ".forgeproof"
        chain_dir.mkdir()
        shutil.copyfile(FIXTURE_V101 / "chain-999.json", chain_dir / "chain-999.json")
        shutil.copyfile(FIXTURE_V101 / "issue-999.rpack", chain_dir / "issue-999.rpack")
        src = tmp_path / "src"
        src.mkdir()
        shutil.copyfile(FIXTURE_V101 / "src" / "example.py", src / "example.py")
        return chain_dir / "issue-999.rpack"

    def _verify(self, rpack_path, capsys) -> tuple[int, dict]:
        args = MagicMock()
        args.rpack = str(rpack_path)
        with pytest.raises(SystemExit) as exc_info:
            fp.cmd_verify(args)
        code = exc_info.value.code
        return (0 if code is None else code), json.loads(capsys.readouterr().out)

    def test_fixture_files_present(self):
        assert (FIXTURE_V101 / "chain-999.json").exists()
        assert (FIXTURE_V101 / "issue-999.rpack").exists()
        assert (FIXTURE_V101 / "src" / "example.py").exists()

    def test_fixture_is_byte_exact(self):
        """Guards against EOL conversion or accidental edits. Fixture files are
        stored LF-only (see .gitattributes): the artifact hash covers raw bytes,
        and chain_hash covers the text the engine sees via read_text() — with
        LF bytes on disk the two views are identical on every platform."""
        for rel in ("chain-999.json", "issue-999.rpack", "src/example.py"):
            assert b"\r" not in (FIXTURE_V101 / rel).read_bytes(), (
                f"fixture file {rel} gained CR bytes (EOL conversion?)"
            )
        bundle = json.loads((FIXTURE_V101 / "issue-999.rpack").read_bytes())
        [artifact] = bundle["artifacts"]
        assert artifact["path"] == "src/example.py"
        actual = fp.sha256_file(FIXTURE_V101 / "src" / "example.py")
        assert actual == artifact["sha256"], (
            "fixture artifact bytes changed on disk"
        )
        chain_text = (FIXTURE_V101 / "chain-999.json").read_bytes().decode("utf-8")
        assert fp.sha256_hex(chain_text) == bundle["chain_hash"], (
            "fixture chain file bytes changed on disk"
        )

    def test_v101_bundle_verifies(self, tmp_path, monkeypatch, capsys):
        self._require_sshkeygen()
        rpack = self._deploy(tmp_path)
        monkeypatch.chdir(tmp_path)
        code, output = self._verify(rpack, capsys)
        assert code == 0
        assert output["verified"] is True
        assert output["errors"] == []
        assert output["artifacts_checked"] == 1
        assert output["artifacts_missing"] == 0
        assert output["artifacts_tampered"] == 0

    def test_v101_tampered_artifact_fails(self, tmp_path, monkeypatch, capsys):
        self._require_sshkeygen()
        rpack = self._deploy(tmp_path)
        artifact = tmp_path / "src" / "example.py"
        data = bytearray(artifact.read_bytes())
        data[0] ^= 0xFF  # flip one byte
        artifact.write_bytes(bytes(data))
        monkeypatch.chdir(tmp_path)
        code, output = self._verify(rpack, capsys)
        assert code == 1
        assert output["verified"] is False
        assert output["artifacts_tampered"] == 1

    def test_v101_tampered_chain_fails(self, tmp_path, monkeypatch, capsys):
        self._require_sshkeygen()
        rpack = self._deploy(tmp_path)
        chain_file = tmp_path / ".forgeproof" / "chain-999.json"
        chain = json.loads(chain_file.read_text())
        chain[2]["data"]["choice"] = "history, rewritten"
        chain_file.write_text(json.dumps(chain, indent=2) + "\n")
        monkeypatch.chdir(tmp_path)
        code, output = self._verify(rpack, capsys)
        assert code == 1
        assert output["verified"] is False
        assert any("hash mismatch" in e.lower() for e in output["errors"])


# ---------------------------------------------------------------------------
# Integration test (requires ssh-keygen)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEndToEnd:
    """Full pipeline: init → record → finalize → verify → tamper → verify fails.

    Requires ssh-keygen on PATH. Skip with: pytest -m 'not integration'
    """

    def test_full_pipeline(self, tmp_chain_dir, tmp_path, capsys):
        if not shutil.which("ssh-keygen"):
            pytest.skip("ssh-keygen not available")

        issue = "42"

        # Create a source file to reference as an artifact
        src = tmp_path / "src"
        src.mkdir()
        test_file = src / "hello.py"
        test_file.write_text("print('hello')")
        file_hash = fp.sha256_file(test_file)

        # 1. Init
        fp.cmd_init(fp.build_parser().parse_args([
            "init", "--issue", issue, "--force",
            "--title", "Integration test",
            "--requirement", "REQ-1: Print hello",
        ]))
        capsys.readouterr()  # clear output

        def record(*argv):
            fp.cmd_record(fp.build_parser().parse_args(
                ["record", "--issue", issue, *argv]))
            capsys.readouterr()

        # 2. Record branch-create
        record("--action", "branch-create",
               "--branch", "forgeproof/42", "--base", "main", "--base-sha", "abc")

        # 3. Record file-edit (engine hashes the file natively)
        record("--action", "file-edit",
               "--path", str(test_file), "--operation", "create")

        # 4. Record test-result
        record("--action", "test-result", "--suite", "pytest",
               "--passed", "1", "--failed", "0", "--covers", "REQ-1=test_hello")

        # 5. Record lint-result
        record("--action", "lint-result", "--tool", "ruff",
               "--errors", "0", "--warnings", "0")

        # 6. Finalize
        fp.cmd_finalize(fp.build_parser().parse_args(
            ["finalize", "--issue", issue, "--commit", "abc123def456"]))
        capsys.readouterr()

        rpack_path = tmp_chain_dir / f"issue-{issue}.rpack"
        assert rpack_path.exists()

        bundle = json.loads(rpack_path.read_text())
        assert bundle["evaluation"]["status"] == "pass"
        assert bundle["root_digest"]
        assert bundle["signature"]
        assert bundle["artifacts"][0]["sha256"] == file_hash

        # 7. Verify — should pass
        ver_args = MagicMock()
        ver_args.rpack = str(rpack_path)
        with pytest.raises(SystemExit) as exc_info:
            fp.cmd_verify(ver_args)
        assert exc_info.value.code == 0

        capsys.readouterr()

        # 8. Tamper with an artifact and re-verify — should fail
        test_file.write_text("print('TAMPERED')")

        with pytest.raises(SystemExit) as exc_info:
            fp.cmd_verify(ver_args)
        assert exc_info.value.code == 1

        output = json.loads(capsys.readouterr().out)
        assert output["verified"] is False
        assert output["artifacts_tampered"] == 1


# Need shutil for the integration test
import shutil
