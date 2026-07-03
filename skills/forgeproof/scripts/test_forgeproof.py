"""Tests for ForgeProof provenance engine (forgeproof.py).

Run with: python -m pytest test_forgeproof.py -v
Integration tests require ssh-keygen: python -m pytest test_forgeproof.py -m integration -v
"""

from __future__ import annotations

import importlib.util
import json
import os
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
    def _make_args(self, issue="1", data=None, force=False):
        args = MagicMock()
        args.issue = issue
        args.data = data
        args.force = force
        return args

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
                data='{"title": "Test", "requirements": ["REQ-1: Do it"]}',
            ))

        assert (tmp_chain_dir / "chain-1.json").exists()
        chain = json.loads((tmp_chain_dir / "chain-1.json").read_text())
        assert len(chain) == 1
        assert chain[0]["action"] == "genesis"
        assert chain[0]["data"]["title"] == "Test"

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
    def _make_args(self, issue, action, data):
        args = MagicMock()
        args.issue = issue
        args.action = action
        args.data = data
        return args

    def test_record_appends_block(self, sample_chain, tmp_chain_dir):
        issue, chain = sample_chain
        with patch.object(fp, "get_key_path", return_value=None), patch("sys.stdout"):
            fp.cmd_record(self._make_args(
                issue=issue,
                action="file-edit",
                data='{"path": "test.py", "operation": "create", "sha256": "abc123"}',
            ))

        loaded = fp.load_chain(issue)
        assert len(loaded) == 2
        assert loaded[1]["action"] == "file-edit"

    def test_record_increments_index(self, sample_chain, tmp_chain_dir):
        issue, chain = sample_chain
        with patch.object(fp, "get_key_path", return_value=None), patch("sys.stdout"):
            fp.cmd_record(self._make_args(
                issue=issue, action="decision",
                data='{"context": "test", "choice": "a", "rationale": "because"}',
            ))

        loaded = fp.load_chain(issue)
        assert loaded[1]["index"] == 1

    def test_record_links_prev_hash(self, sample_chain, tmp_chain_dir):
        issue, chain = sample_chain
        with patch.object(fp, "get_key_path", return_value=None), patch("sys.stdout"):
            fp.cmd_record(self._make_args(
                issue=issue, action="file-edit",
                data='{"path": "a.py", "operation": "create", "sha256": "x"}',
            ))

        loaded = fp.load_chain(issue)
        assert loaded[1]["prev_hash"] == loaded[0]["hash"]

    def test_record_rejects_invalid_action(self, sample_chain, tmp_chain_dir):
        issue, _ = sample_chain
        with pytest.raises(SystemExit):
            fp.cmd_record(self._make_args(
                issue=issue, action="invalid-action",
                data='{"foo": "bar"}',
            ))

    def test_record_rejects_invalid_json(self, sample_chain, tmp_chain_dir):
        issue, _ = sample_chain
        with pytest.raises(SystemExit):
            fp.cmd_record(self._make_args(
                issue=issue, action="file-edit",
                data="not valid json{{{",
            ))


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
        assert "BLOCK" in capsys.readouterr().err

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
        init_args = MagicMock()
        init_args.issue = issue
        init_args.data = json.dumps({
            "title": "Integration test",
            "requirements": ["REQ-1: Print hello"],
        })
        init_args.force = True
        fp.cmd_init(init_args)
        capsys.readouterr()  # clear output

        # 2. Record branch-create
        rec_args = MagicMock()
        rec_args.issue = issue
        rec_args.action = "branch-create"
        rec_args.data = json.dumps({"branch": "forgeproof/42", "base": "main", "base_sha": "abc"})
        fp.cmd_record(rec_args)
        capsys.readouterr()

        # 3. Record file-edit
        rec_args.action = "file-edit"
        rec_args.data = json.dumps({"path": str(test_file), "operation": "create", "sha256": file_hash})
        fp.cmd_record(rec_args)
        capsys.readouterr()

        # 4. Record test-result
        rec_args.action = "test-result"
        rec_args.data = json.dumps({
            "suite": "pytest", "passed": 1, "failed": 0,
            "coverage": {"REQ-1": ["test_hello"]}, "failed_tests": [],
        })
        fp.cmd_record(rec_args)
        capsys.readouterr()

        # 5. Record lint-result
        rec_args.action = "lint-result"
        rec_args.data = json.dumps({"tool": "ruff", "errors": 0, "warnings": 0})
        fp.cmd_record(rec_args)
        capsys.readouterr()

        # 6. Finalize
        fin_args = MagicMock()
        fin_args.issue = issue
        fin_args.commit = "abc123def456"
        fp.cmd_finalize(fin_args)
        capsys.readouterr()

        rpack_path = tmp_chain_dir / f"issue-{issue}.rpack"
        assert rpack_path.exists()

        bundle = json.loads(rpack_path.read_text())
        assert bundle["evaluation"]["status"] == "pass"
        assert bundle["root_digest"]
        assert bundle["signature"]

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
