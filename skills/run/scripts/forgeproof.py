#!/usr/bin/env python3
"""ForgeProof — Ed25519-signed SHA-256 hash chain provenance engine.

Python 3.11+ stdlib only. No pip dependencies.
Cryptographic signing via ssh-keygen (OpenSSH 8.0+).

Subcommands:
    preflight   Check core dependencies (gh, ssh-keygen, python)
    detect      Detect project language and toolchain, output JSON
    init        Create genesis block for an issue
    record      Add a block to the chain
    finalize    Finalize chain and build .rpack bundle
    verify      Verify a .rpack bundle's integrity
    summary     Output PR-ready summary for an issue
    issues      List open GitHub issues assigned to current user
    lint        Run detected linter (project-wide, or one file via --file)
    lint-hook   PostToolUse hook: lint the edited file during an active run
    reset       Clean up provenance state for an issue (or --all)
    gate-pr     PreToolUse gate that blocks 'gh pr create' without a bundle
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHAIN_DIR = Path(".forgeproof")
# Mirrors .claude-plugin/plugin.json, which stays the single source of
# version truth — a sync test fails the build if the two ever drift.
PLUGIN_VERSION = "1.3.0"
RPACK_VERSION = "1.1.0"
# Every bundle format version ever shipped. Membership-only and append-only:
# NEVER an ordering, and no version implies any particular key is present
# (in-test bundle builders and the frozen fixtures depend on that).
KNOWN_RPACK_VERSIONS = frozenset({"1.0.0", "1.1.0"})
RPACK_FORMAT = "forgeproof-rpack"
GENESIS_PREV_HASH = "0" * 64

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def sha256_hex(data: str) -> str:
    """Return hex SHA-256 digest of a UTF-8 string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization (sorted keys, no extra whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def read_json_file(path: Path, what: str) -> Any:
    """Load JSON from a file, dying cleanly on any read/parse failure.

    Every on-disk chain/bundle read goes through here so a truncated, empty,
    BOM-prefixed, or otherwise corrupt file produces an actionable error
    instead of a raw traceback.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")  # tolerate a UTF-8 BOM
    except OSError as e:
        die(f"cannot read {what} ({path}): {e}")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, RecursionError) as e:
        # RecursionError: deeply nested JSON overflows json's recursive scanner.
        # Catch it here so a crafted file dies cleanly like any other bad input
        # instead of leaking a traceback through every chain/bundle read.
        die(f"{what} is not valid JSON ({path}): {e}")


def is_canonical_issue(issue: str) -> bool:
    """A canonical issue number is ASCII decimal with no leading zeros, so the
    string used for filenames and the int stored in the bundle always agree
    (guards a false-green where a tampered chain-007.json is never checked
    because the bundle records issue 7)."""
    s = str(issue)
    if not (s.isascii() and s.isdigit()):
        return False
    return s == "0" or not s.startswith("0")


def now_iso() -> str:
    """Current UTC time in ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def die(msg: str, code: int = 1) -> None:
    """Print error to stderr and exit."""
    print(f"forgeproof: error: {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str) -> None:
    """Print info to stderr (keeps stdout clean for JSON output)."""
    print(f"forgeproof: {msg}", file=sys.stderr)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess, returning the result.

    stdin is closed by default so no child can ever block waiting for
    interactive input (a hung ssh-keygen prompt froze preflight for minutes
    inside Claude Code sessions). Callers that feed stdin pass input=.
    """
    if "input" not in kwargs:
        kwargs.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def generate_ephemeral_keypair(issue: str) -> tuple[Path, Path]:
    """Generate an ephemeral Ed25519 keypair in /tmp. Returns (private, public)."""
    private = Path(tempfile.gettempdir()) / f"forgeproof_{issue}_ed25519"
    public = Path(f"{private}.pub")
    # Remove existing files to avoid ssh-keygen prompt
    private.unlink(missing_ok=True)
    public.unlink(missing_ok=True)
    # -N "" (no passphrase) is a load-bearing contract, not a convenience:
    # openssh_ed25519_seed can only parse the unencrypted openssh-key-v1
    # container, and finalize hard-fails on an unparseable key rather than
    # emit a bundle without its attestation.
    result = run(["ssh-keygen", "-t", "ed25519", "-f", str(private), "-N", "", "-q"])
    if result.returncode != 0:
        die(f"ssh-keygen failed: {result.stderr.strip()}")
    return private, public


def sign_ed25519(message: str, key_path: Path) -> str:
    """Sign a message string using ssh-keygen -Y sign. Returns the signature blob."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dat", delete=False) as f:
        f.write(message)
        f.flush()
        data_path = Path(f.name)

    try:
        result = run([
            "ssh-keygen", "-Y", "sign",
            "-f", str(key_path),
            "-n", "forgeproof",
            str(data_path),
        ])
        sig_path = Path(f"{data_path}.sig")
        if result.returncode != 0 or not sig_path.exists():
            die(f"Signing failed: {result.stderr.strip()}")
        signature = sig_path.read_text().strip()
        sig_path.unlink(missing_ok=True)
        return signature
    finally:
        data_path.unlink(missing_ok=True)


def verify_signature(message: str, signature: str, public_key: str) -> bool:
    """Verify an ssh-keygen signature against a public key string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # Write data to verify
        data_path = tmpdir / "data.dat"
        data_path.write_text(message)
        # Write signature
        sig_path = tmpdir / "data.dat.sig"
        sig_path.write_text(signature)
        # Write allowed signers file (principal = "forgeproof")
        allowed_path = tmpdir / "allowed_signers"
        allowed_path.write_text(f"forgeproof {public_key}\n")

        result = run([
            "ssh-keygen", "-Y", "verify",
            "-f", str(allowed_path),
            "-I", "forgeproof",
            "-n", "forgeproof",
            "-s", str(sig_path),
        ], input=message)
        return result.returncode == 0


SSHSIG_BEGIN = "-----BEGIN SSH SIGNATURE-----"
SSHSIG_END = "-----END SSH SIGNATURE-----"
_SSHSIG_BODY_CHARS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n")


def signature_is_canonical(sig: str) -> bool:
    """A bundle signature must be exactly the SSHSIG armor ssh-keygen emitted,
    with no leading or trailing bytes of ANY kind — including whitespace.
    `ssh-keygen -Y verify` ignores data after the END marker, and a stored
    signature is already stripped at signing time, so without this check the
    signature field could be altered post-signing (junk OR whitespace appended)
    while still verifying — a change that must instead turn verify red. Do NOT
    strip() here: stripping re-admits the whitespace-trailer malleability this
    guards against. Content is always protected by the root digest regardless;
    this closes the cosmetic malleability of the signature field itself."""
    if not (sig.startswith(SSHSIG_BEGIN) and sig.endswith(SSHSIG_END)):
        return False
    body = sig[len(SSHSIG_BEGIN):len(sig) - len(SSHSIG_END)]
    return all(c in _SSHSIG_BODY_CHARS for c in body)


def read_public_key(pub_path: Path) -> str:
    """Read the public key string from a .pub file."""
    return pub_path.read_text().strip()


def delete_private_key(private_path: Path) -> None:
    """Securely delete the ephemeral private key."""
    private_path.unlink(missing_ok=True)
    # Also remove the public key file from /tmp (it's embedded in the bundle)
    pub = Path(f"{private_path}.pub")
    pub.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Raw Ed25519 (RFC 8032) — the cosign-verifiable tier
#
# A pure-stdlib RFC 8032 implementation over the SAME ephemeral key that signs
# the SSHSIG chain/bundle signature: the 32-byte seed is parsed out of the
# unencrypted openssh-key-v1 file generate_ephemeral_keypair writes. Signing
# is deterministic per the RFC, which is what makes the attestation sidecar
# reproducible. Verification is hardened for attacker-supplied input: it
# returns False rather than raising, and rejects non-canonical encodings —
# s >= L (the signature-malleability class this repo has patched twice at the
# SSHSIG tier), y >= p, non-square x, and x = 0 with the sign bit set.
# Deliberately absent: a small-order-point blocklist. The DSSE key must equal
# the bundle's own ssh-ed25519 key, which a bundle-forging attacker controls
# outright — they would use a well-formed key they own, so a blocklist has no
# detection power in this trust model; the anchor is the committed bundle.
# ---------------------------------------------------------------------------

_ED25519_P = 2**255 - 19
_ED25519_L = 2**252 + 27742317777372353535851937790883648493
_ED25519_D = (-121665 * pow(121666, _ED25519_P - 2, _ED25519_P)) % _ED25519_P
_ED25519_SQRT_M1 = pow(2, (_ED25519_P - 1) // 4, _ED25519_P)


def _ed25519_decode_point(encoded: bytes) -> tuple[int, int]:
    """Decode a 32-byte point encoding, canonically (RFC 8032 5.1.3).
    Raises ValueError on any invalid or non-canonical encoding."""
    if len(encoded) != 32:
        raise ValueError("point encoding must be 32 bytes")
    p = _ED25519_P
    val = int.from_bytes(encoded, "little")
    sign = val >> 255
    y = val & ((1 << 255) - 1)
    if y >= p:
        raise ValueError("non-canonical point encoding (y >= p)")
    xx = (y * y - 1) * pow(_ED25519_D * y * y + 1, p - 2, p) % p
    x = pow(xx, (p + 3) // 8, p)
    if (x * x - xx) % p:
        x = x * _ED25519_SQRT_M1 % p
    if (x * x - xx) % p:
        raise ValueError("invalid point encoding (x is not a square)")
    if x == 0 and sign:
        raise ValueError("invalid point encoding (x = 0 with sign bit set)")
    if x & 1 != sign:
        x = p - x
    return (x, y)


def _ed25519_encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _ed25519_add(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    """Affine twisted-Edwards addition (the formula is complete for Ed25519,
    so it also serves as doubling)."""
    p = _ED25519_P
    x1, y1 = a
    x2, y2 = b
    dxy = _ED25519_D * x1 * x2 * y1 * y2 % p
    x3 = (x1 * y2 + x2 * y1) * pow(1 + dxy, p - 2, p)
    y3 = (y1 * y2 + x1 * x2) * pow(1 - dxy, p - 2, p)
    return (x3 % p, y3 % p)


def _ed25519_scalarmult(point: tuple[int, int], e: int) -> tuple[int, int]:
    result = (0, 1)  # neutral element
    while e:
        if e & 1:
            result = _ed25519_add(result, point)
        point = _ed25519_add(point, point)
        e >>= 1
    return result


# Base point B: y = 4/5, x even (decoded from its canonical encoding so the
# same validated path defines it).
_ED25519_B = _ed25519_decode_point(
    ((4 * pow(5, _ED25519_P - 2, _ED25519_P)) % _ED25519_P).to_bytes(32, "little"))


def _ed25519_secret_scalar(seed: bytes) -> tuple[int, bytes]:
    """(clamped scalar, prefix) from a 32-byte seed (RFC 8032 5.1.5)."""
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    h = hashlib.sha512(bytes(seed)).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public_from_seed(seed: bytes) -> bytes:
    """Derive the 32-byte public key from a 32-byte seed."""
    a, _ = _ed25519_secret_scalar(seed)
    return _ed25519_encode_point(_ed25519_scalarmult(_ED25519_B, a))


def ed25519_sign(seed: bytes, message: bytes) -> bytes:
    """Deterministic RFC 8032 Ed25519 signature: 64 bytes, R || s. Plain
    Ed25519 — NOT Ed25519ph — which is the variant the pinned cosign binaries
    verify (spike-proven; see PLAN_v1.3.0.md Phase 0)."""
    a, prefix = _ed25519_secret_scalar(seed)
    public = _ed25519_encode_point(_ed25519_scalarmult(_ED25519_B, a))
    r = int.from_bytes(
        hashlib.sha512(prefix + bytes(message)).digest(), "little") % _ED25519_L
    r_enc = _ed25519_encode_point(_ed25519_scalarmult(_ED25519_B, r))
    k = int.from_bytes(
        hashlib.sha512(r_enc + public + bytes(message)).digest(),
        "little") % _ED25519_L
    s = (r + k * a) % _ED25519_L
    return r_enc + s.to_bytes(32, "little")


def ed25519_verify(public: bytes, message: bytes, signature: bytes) -> bool:
    """Verify an RFC 8032 Ed25519 signature over hostile input: returns False
    on any malformed or non-canonical value, never raises."""
    if len(public) != 32 or len(signature) != 64:
        return False
    try:
        point_a = _ed25519_decode_point(bytes(public))
        point_r = _ed25519_decode_point(bytes(signature[:32]))
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _ED25519_L:
        return False
    k = int.from_bytes(
        hashlib.sha512(
            bytes(signature[:32]) + bytes(public) + bytes(message)).digest(),
        "little") % _ED25519_L
    left = _ed25519_scalarmult(_ED25519_B, s)
    right = _ed25519_add(point_r, _ed25519_scalarmult(point_a, k))
    return left == right


def openssh_ed25519_seed(private_path: Path) -> bytes:
    """Extract the 32-byte Ed25519 seed from an UNENCRYPTED openssh-key-v1
    private key file (the kind generate_ephemeral_keypair writes with -N "").
    Dies with an actionable message on any structural surprise — an encrypted
    key, a non-ed25519 key, truncation, or an embedded public key that does
    not match the one derived from the seed (a parse bug must die loudly,
    never sign with the wrong key)."""
    label = f"ephemeral private key ({private_path})"
    try:
        text = private_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        die(f"cannot read {label}: {e}")

    begin = "-----BEGIN OPENSSH PRIVATE KEY-----"
    end = "-----END OPENSSH PRIVATE KEY-----"
    start = text.find(begin)
    stop = text.find(end)
    if start < 0 or stop <= start:
        die(f"{label} is not an OpenSSH private key (missing PEM armor)")
    try:
        blob = base64.b64decode(text[start + len(begin):stop].encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        die(f"{label} has a corrupt base64 body")

    def _cursor(buf: bytes):
        state = [0]

        def take(n: int, what: str) -> bytes:
            if state[0] + n > len(buf):
                die(f"{label} is truncated or corrupt (while reading {what})")
            piece = buf[state[0]:state[0] + n]
            state[0] += n
            return piece

        def take_str(what: str) -> bytes:
            n = int.from_bytes(take(4, what + " length"), "big")
            return take(n, what)

        return take, take_str

    magic = b"openssh-key-v1\x00"
    if not blob.startswith(magic):
        die(f"{label} is not an openssh-key-v1 container")
    take, take_str = _cursor(blob[len(magic):])
    cipher = take_str("cipher name")
    kdf = take_str("kdf name")
    take_str("kdf options")
    if cipher != b"none" or kdf != b"none":
        die(f"{label} is encrypted (cipher "
            f"{cipher.decode(errors='replace')!r}) — ForgeProof ephemeral "
            "keys are always written without a passphrase")
    nkeys = int.from_bytes(take(4, "key count"), "big")
    if nkeys != 1:
        die(f"{label} contains {nkeys} keys (expected exactly 1)")
    take_str("public key blob")
    private_section = take_str("private key section")

    ptake, ptake_str = _cursor(private_section)
    if ptake(4, "check value") != ptake(4, "check value"):
        die(f"{label} check values differ — corrupt or encrypted key")
    keytype = ptake_str("key type")
    if keytype != b"ssh-ed25519":
        die(f"{label} is a {keytype.decode(errors='replace')!r} key "
            "(expected ssh-ed25519)")
    pub = ptake_str("public key")
    priv = ptake_str("private key")
    ptake_str("comment")
    if len(pub) != 32 or len(priv) != 64 or priv[32:] != pub:
        die(f"{label} has malformed ed25519 key material")
    seed = priv[:32]
    if ed25519_public_from_seed(seed) != pub:
        die(f"{label}: public key derived from the seed does not match the "
            "embedded key blob — refusing to sign with a misparsed key")
    return seed


def ssh_ed25519_pubkey_bytes(pub_line: str) -> bytes:
    """Raw 32-byte key from an OpenSSH public-key line ('ssh-ed25519 <b64>
    [comment]'). Raises ValueError on malformed input so each caller decides
    the failure mode (finalize dies; verify turns a check red). Only the first
    two whitespace-separated fields are read — the comment may itself contain
    spaces (ssh-keygen defaults it to username@hostname)."""
    fields = pub_line.split()
    if len(fields) < 2 or fields[0] != "ssh-ed25519":
        raise ValueError("not an ssh-ed25519 public key line")
    try:
        blob = base64.b64decode(fields[1].encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as e:
        raise ValueError(f"invalid public key base64: {e}")
    # SSH wire blob: string("ssh-ed25519") + string(32-byte key), exactly.
    header = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"
    if not blob.startswith(header) or len(blob) != len(header) + 32:
        raise ValueError("public key blob is not a raw ssh-ed25519 key")
    return blob[len(header):]


# RFC 8410 section 10.1: DER SubjectPublicKeyInfo header for Ed25519; the
# 12-byte prefix + 32 raw key bytes = exactly 44 bytes.
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


def ed25519_spki_pem(public: bytes) -> str:
    """SubjectPublicKeyInfo PEM for a raw Ed25519 key. The block type must be
    PUBLIC KEY (sigstore accepts only PUBLIC KEY and RSA PUBLIC KEY); LF line
    endings; the 44-byte DER fits one base64 line, always starting
    MCowBQYDK2VwAyEA."""
    if len(public) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    body = base64.b64encode(ED25519_SPKI_PREFIX + bytes(public)).decode("ascii")
    return f"-----BEGIN PUBLIC KEY-----\n{body}\n-----END PUBLIC KEY-----\n"


# ---------------------------------------------------------------------------
# DSSE envelope + Sigstore bundle encoding (amendment-v2 layout)
# ---------------------------------------------------------------------------

DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
SIGSTORE_BUNDLE_MEDIA_TYPE = "application/vnd.dev.sigstore.bundle.v0.3+json"


def dsse_pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding: 'DSSEv1' + ASCII decimal lengths,
    exactly four single spaces, no trailing separator."""
    ptype = payload_type.encode("utf-8")
    return b"DSSEv1 %d %s %d %s" % (len(ptype), ptype, len(payload), payload)


def build_dsse_envelope(payload: bytes, signer) -> dict:
    """DSSE envelope over an in-toto payload: standard base64 WITH padding for
    payload and sig (protojson round-trips those byte-identically, which the
    sidecar contract needs), exactly ONE signature, and the signature object
    carries `sig` only — NO keyid (cosign's envelope verifier skips any
    signature whose non-empty keyid differs from its own derivation)."""
    sig = signer.sign(dsse_pae(DSSE_PAYLOAD_TYPE, payload))
    return {
        "payload": base64.b64encode(payload).decode("ascii"),
        "payloadType": DSSE_PAYLOAD_TYPE,
        "signatures": [{"sig": base64.b64encode(sig).decode("ascii")}],
    }


def build_sigstore_bundle(envelope: dict, signer) -> dict:
    """Sigstore bundle v0.3 wrapper. protojson rejects unknown fields, so the
    wrapper carries nothing ForgeProof-specific — everything of ours lives
    inside the in-toto predicate. `dsseEnvelope` is a sibling of
    `verificationMaterial`, never nested inside it."""
    return {
        "mediaType": SIGSTORE_BUNDLE_MEDIA_TYPE,
        "verificationMaterial": signer.verification_material(),
        "dsseEnvelope": envelope,
    }


class EphemeralEd25519Signer:
    """v1.3 attestation signer, and the v1.4 seam: a signer is anything with
    .public_bytes, .sign(data) -> bytes, and .verification_material() -> dict.
    The keyless tier (Fulcio cert + Rekor tlogEntries) implements the same
    three members and swaps only the verification material, leaving the
    envelope byte-identical.

    verification_material() is the EMPTY public-key identifier (amendment v2):
    the bundle wrapper carries no key ids at all. The key itself travels in
    the .rpack public_key field and the .pub.pem sidecar."""

    def __init__(self, seed: bytes):
        self.seed = seed
        self.public_bytes = ed25519_public_from_seed(seed)

    @classmethod
    def from_private_key(cls, private_path: Path) -> "EphemeralEd25519Signer":
        return cls(openssh_ed25519_seed(private_path))

    def sign(self, data: bytes) -> bytes:
        return ed25519_sign(self.seed, data)

    def verification_material(self) -> dict:
        return {"publicKey": {}}


# ---------------------------------------------------------------------------
# Chain operations
# ---------------------------------------------------------------------------


def chain_path(issue: str) -> Path:
    """Path to the chain file for an issue."""
    return CHAIN_DIR / f"chain-{issue}.json"


def load_chain(issue: str) -> list[dict]:
    """Load an existing chain or die if it doesn't exist."""
    path = chain_path(issue)
    if not path.exists():
        die(f"No chain found for issue {issue}. Run 'init' first.")
    chain = read_json_file(path, f"chain for issue {issue}")
    if not isinstance(chain, list) or not all(isinstance(b, dict) for b in chain):
        die(f"chain for issue {issue} is corrupt (expected a list of blocks): {path}")
    return chain


def save_chain(issue: str, chain: list[dict]) -> None:
    """Write chain to disk."""
    CHAIN_DIR.mkdir(exist_ok=True)
    chain_path(issue).write_text(json.dumps(chain, indent=2) + "\n")


def build_block(
    index: int,
    action: str,
    data: dict,
    prev_hash: str,
    key_path: Path | None,
) -> dict:
    """Construct a new block, compute its hash, and optionally sign it."""
    block = {
        "index": index,
        "timestamp": now_iso(),
        "action": action,
        "data": data,
        "prev_hash": prev_hash,
    }
    # Hash = SHA-256 of canonical JSON of block (without hash and signature)
    block_hash = sha256_hex(canonical_json(block))
    block["hash"] = block_hash

    # Sign if key is available
    if key_path and key_path.exists():
        block["signature"] = sign_ed25519(block_hash, key_path)
    else:
        block["signature"] = ""

    return block


def get_key_path(issue: str) -> Path | None:
    """Return the ephemeral private key path if it exists."""
    key = Path(tempfile.gettempdir()) / f"forgeproof_{issue}_ed25519"
    return key if key.exists() else None


# ---------------------------------------------------------------------------
# Subcommand: preflight
# ---------------------------------------------------------------------------


def cmd_preflight(_args: argparse.Namespace) -> None:
    """Check that all core dependencies are available."""
    checks: list[dict] = []

    # gh CLI
    has_gh = shutil.which("gh") is not None
    gh_version = None
    if has_gh:
        result = run(["gh", "--version"])
        gh_version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else None
    checks.append({
        "dependency": "gh",
        "ok": has_gh,
        "version": gh_version,
        "install": "https://cli.github.com/",
    })

    # gh auth
    gh_auth_ok = False
    gh_auth_detail = "gh not installed"
    if has_gh:
        result = run(["gh", "auth", "status"])
        gh_auth_ok = result.returncode == 0
        gh_auth_detail = "authenticated" if gh_auth_ok else result.stderr.strip()
    checks.append({
        "dependency": "gh-auth",
        "ok": gh_auth_ok,
        "detail": gh_auth_detail,
        "install": "Run: gh auth login",
    })

    # ssh-keygen: availability via PATH lookup ONLY. Never spawn a bare
    # ssh-keygen probe — `-h` is not a help flag (it means "host certificate")
    # and invoking it starts INTERACTIVE key generation that blocks forever
    # on a stdin prompt.
    has_sshkeygen = shutil.which("ssh-keygen") is not None
    checks.append({
        "dependency": "ssh-keygen",
        "ok": has_sshkeygen,
        "install": "Install OpenSSH 8.0+ (included on macOS/Linux)",
    })

    # Python version
    v = sys.version_info
    py_ok = v.major == 3 and v.minor >= 11
    checks.append({
        "dependency": "python",
        "ok": py_ok,
        "version": f"{v.major}.{v.minor}.{v.micro}",
        "install": "Python 3.11+ required: https://python.org",
    })

    all_ok = all(c["ok"] for c in checks)
    output = {"ok": all_ok, "checks": checks}
    print(json.dumps(output, indent=2))
    sys.exit(0 if all_ok else 1)


# ---------------------------------------------------------------------------
# Subcommand: detect
# ---------------------------------------------------------------------------

# Structured tool specs: availability is probed with list-form subprocess
# calls and filesystem checks only — no shell strings, no POSIX tools, no
# network (npx is only ever emitted with --no-install).
TOOLCHAIN_MAP = {
    "python": {
        "config_files": ["pyproject.toml", "setup.cfg", "setup.py", "requirements.txt"],
        "test_runners": [
            {"name": "pytest", "module": "pytest", "args": ["-m", "pytest"]},
        ],
        "linters": [
            {"name": "ruff", "module": "ruff", "args": ["-m", "ruff", "check", "."]},
            {"name": "flake8", "module": "flake8", "args": ["-m", "flake8", "."]},
        ],
    },
    "javascript": {
        "config_files": ["package.json"],
        "test_runners": [
            {"name": "jest", "tool": "jest", "args": []},
            {"name": "vitest", "tool": "vitest", "args": ["run"]},
            {"name": "mocha", "tool": "mocha", "args": []},
        ],
        "linters": [
            {"name": "eslint", "tool": "eslint", "args": ["."]},
        ],
    },
    "go": {
        "config_files": ["go.mod"],
        "test_runners": [
            {"name": "go test", "tool": "go", "args": ["test", "./..."]},
        ],
        "linters": [
            {"name": "golangci-lint", "tool": "golangci-lint", "args": ["run"]},
        ],
    },
}

# Used by lint-hook to lint the edited file with the right language's linter.
LANG_EXTENSIONS = {
    "python": {".py", ".pyi"},
    "javascript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"},
    "go": {".go"},
}


def find_project_python(project_root: Path) -> str:
    """Interpreter for the *project*, not the engine: prefer the project's
    virtualenv so recorded test/lint results reflect its environment; fall
    back to the interpreter running this script."""
    if os.name == "nt":
        candidates = ("Scripts/python.exe",)
    else:
        candidates = ("bin/python", "bin/python3")
    for venv_dir in (".venv", "venv"):
        for rel in candidates:
            candidate = project_root / venv_dir / rel
            if candidate.exists():
                return str(candidate)
    return sys.executable


def find_js_tool(project_root: Path, tool: str) -> str | None:
    """Locate a JS tool filesystem-first (node_modules/.bin), falling back to
    PATH. Never probes via bare npx, which may fetch from the registry."""
    bin_dir = project_root / "node_modules" / ".bin"
    suffixes = (".cmd", ".exe", "") if os.name == "nt" else ("",)
    for suffix in suffixes:
        candidate = bin_dir / f"{tool}{suffix}"
        if candidate.exists():
            return str(candidate)
    return shutil.which(tool)


def _probe_ok(argv: list[str]) -> bool:
    """Spawn an availability probe, treating an unspawnable executable as
    unavailable. A broken venv (0-byte or truncated python binary) raises
    OSError from subprocess — detect must degrade to runtime_available: false
    and still emit valid JSON, never a traceback."""
    try:
        return run(argv).returncode == 0
    except OSError:
        return False


def _python_candidates(project_root: Path, spec: dict) -> tuple[bool, list[dict], list[dict]]:
    py = find_project_python(project_root)
    runtime_ok = _probe_ok([py, "--version"])

    def build(items: list[dict]) -> list[dict]:
        out = []
        for item in items:
            argv = [py] + item["args"]
            out.append({
                "name": item["name"],
                "command": " ".join([f'"{py}"'] + item["args"]),
                "argv": argv,
                "ok": _probe_ok([py, "-m", item["module"], "--version"]),
            })
        return out

    return runtime_ok, build(spec["test_runners"]), build(spec["linters"])


def _js_candidates(project_root: Path, spec: dict) -> tuple[bool, list[dict], list[dict]]:
    runtime_ok = shutil.which("node") is not None

    def build(items: list[dict]) -> list[dict]:
        out = []
        for item in items:
            path = find_js_tool(project_root, item["tool"])
            argv = ([path] if path else ["npx", "--no-install", item["tool"]]) + item["args"]
            out.append({
                "name": item["name"],
                "command": " ".join(["npx", "--no-install", item["tool"]] + item["args"]),
                "argv": argv,
                "ok": path is not None,
            })
        return out

    return runtime_ok, build(spec["test_runners"]), build(spec["linters"])


def _go_candidates(spec: dict) -> tuple[bool, list[dict], list[dict]]:
    runtime_ok = shutil.which("go") is not None

    def build(items: list[dict]) -> list[dict]:
        out = []
        for item in items:
            argv = [item["tool"]] + item["args"]
            out.append({
                "name": item["name"],
                "command": " ".join(argv),
                "argv": argv,
                "ok": shutil.which(item["tool"]) is not None,
            })
        return out

    return runtime_ok, build(spec["test_runners"]), build(spec["linters"])


def detect_toolchain(project_root: Path) -> dict:
    """Detect project language and available toolchain. Shared by cmd_detect,
    cmd_lint, and cmd_lint_hook (no self-subprocess)."""
    detected: list[dict] = []

    for lang, spec in TOOLCHAIN_MAP.items():
        config_found = [f for f in spec["config_files"] if (project_root / f).exists()]
        if not config_found:
            continue

        if lang == "python":
            runtime_ok, runner_cands, linter_cands = _python_candidates(project_root, spec)
        elif lang == "javascript":
            runtime_ok, runner_cands, linter_cands = _js_candidates(project_root, spec)
        else:
            runtime_ok, runner_cands, linter_cands = _go_candidates(spec)

        # First available test runner; default to the first candidate if none
        test_runner = None
        for cand in runner_cands:
            if cand["ok"]:
                test_runner = {"name": cand["name"], "command": cand["command"], "argv": cand["argv"]}
                break
        if not test_runner and runner_cands:
            first = runner_cands[0]
            test_runner = {
                "name": first["name"],
                "command": first["command"],
                "argv": first["argv"],
                "available": False,
            }

        # First available linter
        linter = None
        for cand in linter_cands:
            if cand["ok"]:
                linter = {"name": cand["name"], "command": cand["command"], "argv": cand["argv"]}
                break

        detected.append({
            "language": lang,
            "config_files": config_found,
            "runtime_available": runtime_ok,
            "test_runner": test_runner,
            "linter": linter,
        })

    if not detected:
        return {
            "detected": False,
            "languages": [],
            "message": "No supported project configuration found. Looked for: "
                       + ", ".join(f for spec in TOOLCHAIN_MAP.values() for f in spec["config_files"]),
        }
    return {"detected": True, "languages": detected}


def cmd_detect(args: argparse.Namespace) -> None:
    """Detect project language and available toolchain."""
    project_root = Path(args.project_root) if args.project_root else Path.cwd()
    print(json.dumps(detect_toolchain(project_root), indent=2))


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a provenance chain for an issue."""
    issue = args.issue
    # Validate before any side effect (keypair generation writes temp files).
    # Canonical = ASCII decimal, no leading zeros, so the filename string and
    # the int stored in the bundle can never disagree.
    if not is_canonical_issue(issue):
        die(f"--issue must be a canonical number (ASCII digits, no leading "
            f"zeros), e.g. 7 not 007 (got: {issue!r})")
    # Requirements must carry a 'REQ-N: text' colon; a colonless requirement
    # would be silently dropped at finalize and inflate coverage to 100%.
    for req in args.requirement or []:
        if ":" not in req:
            die(f"--requirement must look like 'REQ-1: text' (missing ':' "
                f"in {req!r})")
    path = chain_path(issue)

    if path.exists():
        if getattr(args, "force", False):
            # Clean up prior run state
            path.unlink(missing_ok=True)
            rpack = CHAIN_DIR / f"issue-{issue}.rpack"
            rpack.unlink(missing_ok=True)
            # Attestation sidecars too: a stale sidecar surviving --force
            # could later be committed next to a bundle it does not match.
            (CHAIN_DIR / f"issue-{issue}.sigstore.json").unlink(missing_ok=True)
            (CHAIN_DIR / f"issue-{issue}.pub.pem").unlink(missing_ok=True)
            key = Path(tempfile.gettempdir()) / f"forgeproof_{issue}_ed25519"
            key.unlink(missing_ok=True)
            Path(f"{key}.pub").unlink(missing_ok=True)
            info(f"Cleaned up prior state for issue {issue}")
        else:
            die(f"Chain already exists for issue {issue}: {path}. Use --force to overwrite.")

    # Generate ephemeral keypair
    private_key, public_key = generate_ephemeral_keypair(issue)
    info(f"Generated ephemeral keypair for issue {issue}")

    # Genesis data from discrete flags (quote-safe on every shell; same dict
    # shape the v1.0.x --data JSON produced)
    genesis_data = {
        "issue": int(issue),
        "title": args.title or "",
        "requirements": list(args.requirement or []),
    }

    # Build genesis block
    genesis = build_block(
        index=0,
        action="genesis",
        data=genesis_data,
        prev_hash=GENESIS_PREV_HASH,
        key_path=private_key,
    )

    save_chain(issue, [genesis])
    info(f"Initialized chain: {path}")

    # Output result
    result = {
        "chain_file": str(path),
        "genesis_hash": genesis["hash"],
        "public_key": read_public_key(public_key),
        "key_path": str(private_key),
    }
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: record
# ---------------------------------------------------------------------------


# Per-action flag contract. Each action builds the exact same data dict shape
# the v1.0.x --data JSON produced — chain and bundle formats are untouched.
RECORD_FLAG_SPEC = {
    "approval": {"required": ["gate", "decision"], "optional": ["note"]},
    "branch-create": {"required": ["branch", "base", "base_sha"], "optional": []},
    "file-edit": {"required": ["path", "operation"], "optional": []},
    "decision": {"required": ["context", "choice", "rationale"], "optional": []},
    "test-result": {"required": ["suite", "passed", "failed"], "optional": ["covers", "failed_test"]},
    "lint-result": {"required": ["tool", "errors", "warnings"], "optional": []},
}

# Every flag declared in build_parser for record MUST be listed here, or its
# value is invisible to the missing/unexpected guard below — silently dropped
# on its own action and silently accepted on every other.
_RECORD_DATA_FLAGS = [
    "branch", "base", "base_sha", "path", "operation",
    "context", "choice", "rationale",
    "suite", "passed", "failed", "covers", "failed_test",
    "tool", "errors", "warnings",
    "gate", "decision", "note",
]


def _approver_email() -> str:
    """Approver identity for approval blocks, read from git config rather
    than trusted from a flag. Best-effort by design: returns "" on ANY
    failure — git absent, no identity configured, non-zero exit, timeout —
    because an approval record must never die or block on identity lookup.
    Module-level so tests patch it in one place."""
    if not shutil.which("git"):
        return ""
    try:
        result = run(["git", "config", "user.email"], timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _flag_name(attr: str) -> str:
    return "--" + attr.replace("_", "-")


def _record_data_from_flags(args: argparse.Namespace) -> dict:
    """Validate the per-action flag set and assemble the block's data dict."""
    action = args.action
    spec = RECORD_FLAG_SPEC[action]
    provided = {f for f in _RECORD_DATA_FLAGS if getattr(args, f, None) is not None}
    allowed = set(spec["required"]) | set(spec["optional"])

    missing = [_flag_name(f) for f in spec["required"] if f not in provided]
    extra = [_flag_name(f) for f in sorted(provided - allowed)]
    if missing or extra:
        expected = ", ".join(_flag_name(f) for f in spec["required"] + spec["optional"])
        problems = []
        if missing:
            problems.append(f"missing {', '.join(missing)}")
        if extra:
            problems.append(f"unexpected {', '.join(extra)}")
        die(f"action '{action}' takes: {expected} ({'; '.join(problems)})")

    # Counts seal into the bundle's evaluation math (sums, pass/fail status);
    # a negative count would silently skew it, so reject at the input edge.
    for attr in ("passed", "failed", "errors", "warnings"):
        value = getattr(args, attr, None)
        if value is not None and value < 0:
            die(f"{_flag_name(attr)} must not be negative (got {value}); "
                f"pass the real count, e.g. {_flag_name(attr)} 0")

    if action == "branch-create":
        return {"branch": args.branch, "base": args.base, "base_sha": args.base_sha}

    if action == "file-edit":
        raw = args.path
        path = Path(raw)
        # The recorded path must be repo-relative and inside the project: verify
        # later resolves it relative to the checkout, so an absolute path (or one
        # escaping the root) would verify GREEN on a reviewer's machine even if
        # the file there was modified — the artifact simply "isn't found". Store
        # a normalized forward-slash relative path so re-edits of the same file
        # dedup to one artifact regardless of spelling.
        if path.is_absolute() or (len(raw) >= 2 and raw[1] == ":"):
            die(f"--path must be relative to the project root, not absolute: {raw!r}")
        root = Path.cwd().resolve()
        try:
            resolved = (root / path).resolve()
            rel = resolved.relative_to(root)
        except (ValueError, OSError):
            die(f"--path must stay inside the project root: {raw!r}")
        if not resolved.is_file():
            die(f"file not found: {raw} — record a file edit after writing the file")
        rel_str = rel.as_posix()
        # The engine hashes what is on disk; there is deliberately no override.
        return {"path": rel_str, "operation": args.operation,
                "sha256": sha256_file(resolved)}

    if action == "decision":
        return {"context": args.context, "choice": args.choice, "rationale": args.rationale}

    if action == "test-result":
        coverage: dict[str, list[str]] = {}
        for spec_str in args.covers or []:
            if "=" not in spec_str:
                die(f"--covers must look like REQ-1=test_a,test_b (got: {spec_str})")
            req_id, tests = spec_str.split("=", 1)
            names = [t.strip() for t in tests.split(",") if t.strip()]
            # An empty id or test list would seal vacuous coverage into the
            # bundle (a "" requirement, or a requirement covered by zero
            # tests) and inflate the coverage percentage.
            if not req_id.strip():
                die(f"--covers requirement id is empty (got: {spec_str!r}); "
                    f"expected REQ-1=test_a,test_b — note requirement ids "
                    f"must not contain '='")
            if not names:
                die(f"--covers test list is empty (got: {spec_str!r}); "
                    f"expected REQ-1=test_a,test_b — note requirement ids "
                    f"must not contain '='")
            coverage.setdefault(req_id.strip(), []).extend(names)
        return {
            "suite": args.suite,
            "passed": args.passed,
            "failed": args.failed,
            "coverage": coverage,
            "failed_tests": list(args.failed_test or []),
        }

    if action == "approval":
        # The engine fills approver itself; a flag would let the recording
        # agent assert an arbitrary identity.
        return {
            "gate": args.gate,
            "decision": args.decision,
            "note": args.note or "",
            "approver": _approver_email(),
        }

    if action == "lint-result":
        return {"tool": args.tool, "errors": args.errors, "warnings": args.warnings}

    # Explicit fallthrough: an action added to RECORD_FLAG_SPEC without a
    # branch above must fail loudly, never seal a wrong-shaped data dict
    # built from unset attributes.
    die(f"internal error: action '{action}' has no data builder in "
        "_record_data_from_flags")


def cmd_record(args: argparse.Namespace) -> None:
    """Record a new block in the chain."""
    issue = args.issue
    chain = load_chain(issue)
    # A finalized chain is sealed: its hash is embedded in the signed bundle,
    # so appending anything would only guarantee a chain-hash mismatch at
    # verify time. Refuse before touching the file.
    if chain and chain[-1].get("action") == "finalize":
        die("chain already finalized; run init --force to start over")
    data = _record_data_from_flags(args)

    last_block = chain[-1]
    key_path = get_key_path(issue)

    block = build_block(
        index=last_block["index"] + 1,
        action=args.action,
        data=data,
        prev_hash=last_block["hash"],
        key_path=key_path,
    )

    chain.append(block)
    save_chain(issue, chain)

    result = {
        "index": block["index"],
        "action": block["action"],
        "hash": block["hash"],
        "chain_length": len(chain),
    }
    print(json.dumps(result, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: finalize
# ---------------------------------------------------------------------------


def _claude_code_version() -> str:
    """Best-effort Claude Code CLI version probe ('measured' in the builder
    identity). Resolved through shutil.which ONLY — never exec an env-var
    path directly; which() also resolves the .cmd shim on Windows — with a
    hard timeout. Degrades to "unknown" on every failure."""
    exe = shutil.which("claude")
    if not exe:
        return "unknown"
    try:
        result = run([exe, "--version"], timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return result.stdout.strip() or "unknown"


# Attestation-tier constants. The buildType URI documents the parameter
# schema; builder.id is version-scoped and resolves to documentation of its
# scope and trust base (references/rpack-format.md).
FORGEPROOF_REPO_URL = "https://github.com/ryanjmichie-git/forgeproof-plugin"
FORGEPROOF_BUILD_TYPE = (
    FORGEPROOF_REPO_URL
    + "/blob/main/skills/run/references/rpack-format.md#slsa-buildtype-v1")


def forgeproof_builder_id() -> str:
    return f"{FORGEPROOF_REPO_URL}/tree/v{PLUGIN_VERSION}"


def load_attestation_signer(key_path: Path, public_key: str) -> EphemeralEd25519Signer:
    """Parse the ephemeral key's seed and bind it to the published public
    key. Called BEFORE any chain mutation: an attestation in every v1.3
    bundle is the product promise, so an unparseable or mismatched key is a
    hard fail while the chain is still un-finalized — never a silently
    degraded bundle. Module-level so tests that feed finalize a fake key
    file can patch it."""
    signer = EphemeralEd25519Signer.from_private_key(key_path)
    try:
        expected = ssh_ed25519_pubkey_bytes(public_key)
    except ValueError as e:
        die(f"public key file is not a valid ssh-ed25519 line: {e}")
    if signer.public_bytes != expected:
        die(f"ephemeral key mismatch: the private key at {key_path} does not "
            "correspond to the published public key — refusing to sign")
    return signer


def build_intoto_statement(bundle: dict, chain: list[dict],
                           approvals: list[dict], repo_url: str) -> dict:
    """in-toto Statement v1 carrying a SLSA Provenance v1 predicate.
    Deterministic and time-free: timestamps are copied verbatim from chain
    blocks (already RFC 3339 UTC) and invocationId is the genesis hash."""
    issue_num = bundle["issue"]["number"]
    chain_name = f".forgeproof/chain-{issue_num}.json"
    subjects = [{"name": a["path"], "digest": {"sha256": a["sha256"]}}
                for a in bundle["artifacts"]]
    if not subjects:
        # A statement subject may not be empty (in-toto rejects it), so a
        # zero-file-edit run attests the chain itself.
        subjects = [{"name": chain_name,
                     "digest": {"sha256": bundle["chain_hash"]}}]

    resolved = []
    for block in chain:
        if block.get("action") == "branch-create":
            data = block.get("data", {})
            base = data.get("base", "")
            uri = (f"git+{repo_url}@refs/heads/{base}" if repo_url
                   else f"git+refs/heads/{base}")
            resolved.append({"uri": uri,
                             "digest": {"gitCommit": data.get("base_sha", "")}})
            break

    genesis = chain[0]
    finalize_block = chain[-1]
    builder_identity = finalize_block.get("data", {}).get("builder", {})

    predicate = {
        "buildDefinition": {
            "buildType": FORGEPROOF_BUILD_TYPE,
            "externalParameters": {
                "issue": bundle["issue"],
                "requirements": bundle["requirements"],
                # The AI records that the human approved: asserted evidence,
                # not cryptographic proof of consent.
                "approvals": [dict(a, evidence="agent-recorded")
                              for a in approvals],
            },
            "internalParameters": {"builder": builder_identity},
            "resolvedDependencies": resolved,
        },
        "runDetails": {
            "builder": {"id": forgeproof_builder_id()},
            "metadata": {
                "invocationId": genesis["hash"],
                "startedOn": genesis["timestamp"],
                "finishedOn": finalize_block["timestamp"],
            },
            "byproducts": [
                {
                    "name": chain_name,
                    # MUST be the same chain_hash the bundle seals: sha256
                    # over the UTF-8, LF-normalized DECODED TEXT of the chain
                    # file, never a re-hash of its raw bytes (which would
                    # false-red every Windows-authored bundle).
                    "digest": {"sha256": bundle["chain_hash"]},
                    "annotations": {
                        "digestOver": "utf-8 lf-normalized decoded text"},
                },
                {
                    "name": "evaluation",
                    "mediaType": "application/json",
                    "content": base64.b64encode(
                        canonical_json(bundle["evaluation"]).encode("utf-8")
                    ).decode("ascii"),
                },
            ],
        },
    }
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": predicate,
    }


def build_attestation(statement: dict, signer) -> dict:
    """DSSE-sign a statement and wrap it in a Sigstore bundle. Module-level
    so finalize tests can patch it for failure injection."""
    payload = canonical_json(statement).encode("utf-8")
    return build_sigstore_bundle(build_dsse_envelope(payload, signer), signer)


def cmd_finalize(args: argparse.Namespace) -> None:
    """Finalize the chain and build the .rpack bundle."""
    issue = args.issue
    chain = load_chain(issue)
    key_path = get_key_path(issue)
    if not key_path:
        die(f"No ephemeral key found for issue {issue}. Was the chain initialized in this session?")

    pub_path = Path(f"{key_path}.pub")
    if not pub_path.exists():
        die(f"Public key not found: {pub_path}")

    public_key = read_public_key(pub_path)

    # Artifact recheck BEFORE touching the chain: the signed bundle must match
    # what is on disk at signing time. Only the latest record per path counts
    # (earlier records of a re-edited file are legitimately superseded).
    latest_edit: dict[str, str] = {}
    for block in chain:
        if block["action"] == "file-edit" and block["data"].get("path"):
            latest_edit[block["data"]["path"]] = block["data"].get("sha256", "")
    stale = []
    missing_files = []
    for path_str, recorded_hash in latest_edit.items():
        p = Path(path_str)
        if not p.is_file():
            missing_files.append(path_str)
        else:
            try:
                current = sha256_file(p)
            except OSError:
                missing_files.append(path_str)  # unreadable == can't attest
                continue
            if current != recorded_hash:
                stale.append(path_str)
    if stale or missing_files:
        problems = []
        if stale:
            problems.append("changed on disk since recorded: " + ", ".join(stale))
        if missing_files:
            problems.append("missing from disk: " + ", ".join(missing_files))
        die(
            "artifact recheck failed — " + "; ".join(problems)
            + ". Record the current state of each file "
            "(record --action file-edit --path <file> --operation modify) "
            "and re-run finalize."
        )

    # Parse the attestation signing seed and bind it to the published public
    # key BEFORE any chain mutation: an attestation in every v1.3 bundle is
    # the product promise, so an unparseable or mismatched key must hard-fail
    # while the chain is still un-finalized (resolved question 8).
    attestation_signer = load_attestation_signer(key_path, public_key)

    # Builder identity, with per-field provenance labels. The model id is
    # whatever the agent claims; the same shape-check discipline as
    # cmd_verify's flag reads keeps a MagicMock namespace from leaking a
    # non-string into json.dumps.
    model = getattr(args, "model", None)
    model = model if isinstance(model, str) else ""
    builder_identity = {
        "model": {"id": model, "source": "self-reported"},
        "claude_code": {"version": _claude_code_version(), "source": "measured"},
        "plugin": {"version": PLUGIN_VERSION, "source": "engine-constant"},
    }

    # Build finalize block
    last_block = chain[-1]
    finalize_data = {
        "commit_sha": args.commit,
        "chain_length": len(chain) + 1,  # including the finalize block itself
        "builder": builder_identity,
    }

    finalize_block = build_block(
        index=last_block["index"] + 1,
        action="finalize",
        data=finalize_data,
        prev_hash=last_block["hash"],
        key_path=key_path,
    )

    # Everything from the chain append through the sidecar writes runs under
    # a rollback guard. chain_hash is derived from the chain file ON DISK
    # (LF-normalized decoded text), so the chain must be saved before the
    # attestation can be built; if anything after that save fails, the chain
    # file is restored byte-for-byte and every partial output removed, so a
    # failed finalize never strands a finalized chain without its outputs.
    # The private key is deleted only after all outputs, keeping the run
    # retryable.
    chain_file = chain_path(issue)
    chain_before = chain_file.read_bytes()
    rpack_path = CHAIN_DIR / f"issue-{issue}.rpack"
    attestation_path = CHAIN_DIR / f"issue-{issue}.sigstore.json"
    pem_path = CHAIN_DIR / f"issue-{issue}.pub.pem"
    try:
        chain.append(finalize_block)
        save_chain(issue, chain)

        # Extract data from chain for the bundle
        genesis = chain[0]
        issue_data = genesis["data"]

        # Collect artifacts, decisions, approvals, and evaluation data from
        # chain. Artifacts are deduplicated per path keeping the latest
        # record, so a re-edited file appears once, with the hash that
        # matches disk at signing time (the full edit history stays in the
        # chain).
        artifacts_by_path: dict[str, dict] = {}
        decisions = []
        approvals = []
        test_results = []
        lint_results = []

        for block in chain:
            action = block["action"]
            d = block["data"]
            if action == "file-edit":
                artifacts_by_path[d.get("path", "")] = {
                    "path": d.get("path", ""),
                    "operation": d.get("operation", ""),
                    "sha256": d.get("sha256", ""),
                }
            elif action == "decision":
                decisions.append({
                    "context": d.get("context", ""),
                    "choice": d.get("choice", ""),
                    "rationale": d.get("rationale", ""),
                })
            elif action == "approval":
                approvals.append({
                    "gate": d.get("gate", ""),
                    "decision": d.get("decision", ""),
                    "note": d.get("note", ""),
                    "approver": d.get("approver", ""),
                })
            elif action == "test-result":
                test_results.append(d)
            elif action == "lint-result":
                lint_results.append(d)

        artifacts = list(artifacts_by_path.values())

        # Compute evaluation status
        total_passed = sum(t.get("passed", 0) for t in test_results)
        total_failed = sum(t.get("failed", 0) for t in test_results)
        total_lint_errors = sum(l.get("errors", 0) for l in lint_results)

        # Collect coverage and failure info
        all_coverage = {}
        for t in test_results:
            for req_id, tests in t.get("coverage", {}).items():
                all_coverage.setdefault(req_id, []).extend(tests)

        all_reqs = issue_data.get("requirements", [])
        req_ids = []
        for r in all_reqs:
            if isinstance(r, str) and ":" in r:
                req_ids.append(r.split(":")[0].strip())
            elif isinstance(r, dict):
                req_ids.append(r.get("id", ""))

        uncovered = [rid for rid in req_ids if rid not in all_coverage] if req_ids else []
        failed_tests = []
        for t in test_results:
            failed_tests.extend(t.get("failed_tests", []))

        if total_failed == 0 and total_lint_errors == 0 and not uncovered:
            eval_status = "pass"
        elif total_passed == 0 and total_failed > 0:
            eval_status = "fail"
        else:
            eval_status = "partial"

        coverage_pct = "0%"
        if req_ids:
            covered_count = len(req_ids) - len(uncovered)
            coverage_pct = f"{round(covered_count / len(req_ids) * 100)}%"

        # Get repo URL from gh if available
        repo_url = ""
        if shutil.which("gh"):
            gh_result = run(["gh", "repo", "view", "--json", "url", "-q", ".url"])
            if gh_result.returncode == 0:
                repo_url = gh_result.stdout.strip()

        # Build requirements list for bundle
        bundle_reqs = []
        for r in all_reqs:
            if isinstance(r, str) and ":" in r:
                rid, rtext = r.split(":", 1)
                rid = rid.strip()
                rtext = rtext.strip()
            elif isinstance(r, dict):
                rid = r.get("id", "")
                rtext = r.get("text", "")
            else:
                continue
            status = "covered" if rid in all_coverage else "uncovered"
            bundle_reqs.append({
                "id": rid,
                "text": rtext,
                "status": status,
                "tests": all_coverage.get(rid, []),
            })

        # Assemble the bundle (without root_digest and signature yet)
        bundle = {
            "version": RPACK_VERSION,
            "format": RPACK_FORMAT,
            "issue": {
                "number": issue_data.get("issue", int(issue)),
                "title": issue_data.get("title", ""),
                "url": f"{repo_url}/issues/{issue}" if repo_url else "",
            },
            "requirements": bundle_reqs,
            "artifacts": artifacts,
            "decisions": decisions,
            "evaluation": {
                "status": eval_status,
                "tests_passed": total_passed,
                "tests_failed": total_failed,
                "lint_errors": total_lint_errors,
                "requirement_coverage": coverage_pct,
                "uncovered_requirements": uncovered,
                "failed_tests": failed_tests,
            },
            "chain_hash": sha256_hex(chain_path(issue).read_text()),
            "public_key": public_key,
        }

        # Attestation: a statement over the assembled bundle core, DSSE-signed
        # with the same ephemeral key, embedded BEFORE root_digest is computed
        # so the SSHSIG covers it (and pre-v1.3 verifiers hash it blindly via
        # the denylist). Serialized to its canonical string ONCE — the sidecar
        # must be byte-identical to canonical_json of the embedded copy.
        statement = build_intoto_statement(bundle, chain, approvals, repo_url)
        attestation_bundle = build_attestation(statement, attestation_signer)
        attestation_canon = canonical_json(attestation_bundle)
        bundle["attestation"] = attestation_bundle

        # Compute root digest over the bundle content
        root_digest = sha256_hex(canonical_json(bundle))
        bundle["root_digest"] = root_digest

        # Sign the root digest
        bundle["signature"] = sign_ed25519(root_digest, key_path)

        # Write the .rpack file, then the sidecars — all before the key
        # deletion below (anything after it would operate on a deleted key).
        CHAIN_DIR.mkdir(exist_ok=True)
        rpack_path.write_text(json.dumps(bundle, indent=2) + "\n")

        # Sidecar contracts: the .sigstore.json is the same canonical string
        # as the embedded copy with NO newline characters at all, written with
        # explicit encoding and newline="" so neither Python nor git can
        # translate anything; the PEM is LF-only. Never copy save_chain or the
        # rpack write above — both append "\n" with default translation.
        attestation_path.write_text(attestation_canon,
                                    encoding="utf-8", newline="")
        pem_path.write_text(ed25519_spki_pem(attestation_signer.public_bytes),
                            encoding="utf-8", newline="\n")
    except BaseException as e:
        chain_file.write_bytes(chain_before)
        rpack_path.unlink(missing_ok=True)
        attestation_path.unlink(missing_ok=True)
        pem_path.unlink(missing_ok=True)
        info("finalize failed after the chain was updated — chain file "
             "restored, partial outputs removed")
        if isinstance(e, (SystemExit, KeyboardInterrupt)):
            raise
        die(f"finalize failed while building outputs ({e}); chain restored, "
            "ephemeral key retained — fix the cause and re-run finalize")

    # Delete ephemeral private key
    delete_private_key(key_path)
    info(f"Ephemeral private key deleted")

    result = {
        "rpack_path": str(rpack_path),
        "root_digest": root_digest,
        "evaluation_status": eval_status,
        "chain_length": len(chain),
        "artifacts_count": len(artifacts),
        "requirements_count": len(bundle_reqs),
        "attestation_path": str(attestation_path),
        "public_key_path": str(pem_path),
    }
    print(json.dumps(result, indent=2))
    info(f"Bundle written: {rpack_path}")


# ---------------------------------------------------------------------------
# Subcommand: verify
# ---------------------------------------------------------------------------


# Prefix marking missing-evidence errors appended under --strict; the
# renderer filters on it to keep strict failures out of the tamper verdict.
STRICT_PREFIX = "[strict] "

# Substrings identifying tamper-class integrity errors — positive evidence
# of alteration, as opposed to "cannot verify" errors (unknown format, a
# signature field that was never verifiable). Must be kept in sync with the
# error strings cmd_verify appends.
TAMPER_ERROR_MARKERS = (
    "Root digest mismatch",
    "signature verification FAILED",
    "Chain hash mismatch",
    "hash mismatch",
    "prev_hash",
    "Artifact tampered",
    "Artifact is not a file",
    "trailing or altered",
    # v1.3 attestation invariants. These strings deliberately avoid the
    # legacy "hash mismatch"/"prev_hash" fragments (substring matching), and
    # "Attestation malformed" errors deliberately match NONE of these —
    # signed-malformed content is an engine bug, not evidence of alteration.
    "Attestation signature invalid",
    "Attestation key mismatch",
    "Attestation subjects",
    "Attestation chain digest",
)


def _attestation_statement(att: Any) -> "tuple[dict | None, bytes | None, str]":
    """Parse and shape-check an embedded attestation, returning
    (statement, payload_bytes, problem) with problem == "" on success.

    Every input byte is attacker-controlled, so every failure is a clean
    description and never an exception — including the payload json parse,
    which is a NEW json.loads over hostile bytes and carries the same guard
    trio as read_json_file. Problem strings must never embed attacker values:
    they feed error strings whose tamper classification is substring-based,
    so embedded content could forge a tamper (or hide one)."""
    if not isinstance(att, dict):
        return None, None, "attestation is not an object"
    env = att.get("dsseEnvelope")
    if not isinstance(env, dict):
        return None, None, "dsseEnvelope missing or not an object"
    if env.get("payloadType") != DSSE_PAYLOAD_TYPE:
        return None, None, "unexpected payloadType"
    sigs = env.get("signatures")
    if not isinstance(sigs, list) or len(sigs) != 1:
        return None, None, "expected exactly one signature"
    if not isinstance(sigs[0], dict) or not isinstance(sigs[0].get("sig"), str):
        return None, None, "signature entry malformed"
    payload_b64 = env.get("payload")
    if not isinstance(payload_b64, str):
        return None, None, "payload missing or not a string"
    try:
        payload = base64.b64decode(payload_b64.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        return None, None, "payload is not valid base64"
    try:
        statement = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, ValueError, RecursionError,
            UnicodeDecodeError):
        return None, None, "payload is not valid JSON"
    if not isinstance(statement, dict):
        return None, None, "statement is not an object"
    if statement.get("_type") != "https://in-toto.io/Statement/v1":
        return None, None, "unexpected statement _type"
    if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
        return None, None, "unexpected predicateType"
    if not isinstance(statement.get("subject"), list) or not statement["subject"]:
        return None, None, "subject missing or empty"
    return statement, payload, ""


def _render_verify_markdown(result: dict, bundle: dict,
                            chain_blocks: list | None,
                            artifact_rows: list[dict]) -> str:
    """Render the verify result as a human-readable audit report.

    Same data, second view: cmd_verify builds one result dict and either
    dumps it as JSON or renders it here — there is no separate markdown
    verification pass. The verdict wording distinguishes tampering (a
    TAMPER_ERROR_MARKERS match) from unverifiable input and from missing
    evidence: a strict-mode failure whose only errors are STRICT_PREFIX
    missing-evidence entries must not cry tamper."""
    def md_cell(value: Any) -> str:
        """Neutralize bundle-controlled text for markdown output: this
        report lands in PR comments / job summaries where bundle content
        is attacker-controlled, so backslash-escape everything that could
        form links, images, emphasis, code spans, or HTML, and keep cells
        to one line. Engine-generated literals (check names, statuses,
        headings) are rendered directly and stay unescaped."""
        text = str(value).replace("\\", "\\\\")
        for ch in "`[]*_<>|":
            text = text.replace(ch, "\\" + ch)
        return text.replace("\r", " ").replace("\n", " ")

    integrity_errors = [e for e in result["errors"]
                        if not e.startswith(STRICT_PREFIX)]
    tampered = any(marker in err for err in integrity_errors
                   for marker in TAMPER_ERROR_MARKERS)
    lines: list[str] = []
    # Verdict emoji as \u escapes: some of their raw UTF-8 bytes (0x8F, 0x9D)
    # are undefined in cp1252, and this source file must stay decodable under
    # a legacy-codepage read_text() (stdout itself is reconfigured to UTF-8
    # in main(), so the rendered report is always real UTF-8).
    if integrity_errors and tampered:
        lines.append("## \u274c TAMPER DETECTED")
    elif integrity_errors:
        lines.append("## \u274c VERIFICATION FAILED")
    elif result["verified"] and result["complete"]:
        lines.append("## \u2705 VERIFIED")
    else:
        lines.append("## \u26a0\ufe0f VERIFIED (incomplete — evidence missing)")
        if not result["verified"]:
            lines += ["", "**FAILED under --strict:** required evidence is "
                          "missing, so this verification does not pass."]

    binfo = result["bundle"]
    if binfo.get("issue") is not None or binfo.get("title"):
        lines += ["", f"**Bundle:** issue #{md_cell(binfo.get('issue'))} — "
                      f"{md_cell(binfo.get('title') or '(untitled)')}"]

    lines += ["", "### Checks", "", "| Check | Status | Detail |",
              "|---|---|---|"]
    for c in result["checks"]:
        lines.append(f"| {c['name']} | {c['status']} | {md_cell(c['detail'])} |")

    if chain_blocks is not None:
        lines += ["", "### Provenance timeline", "",
                  "| # | Action | Timestamp |", "|---|---|---|"]
        for block in chain_blocks:
            if isinstance(block, dict):
                lines.append(f"| {md_cell(block.get('index'))} "
                             f"| {md_cell(block.get('action'))} "
                             f"| {md_cell(block.get('timestamp'))} |")
            else:
                lines.append("| ? | (malformed block) | ? |")

    lines += ["", "### Artifacts", ""]
    if artifact_rows:
        lines += ["| Path | SHA-256 | Status |", "|---|---|---|"]
        for row in artifact_rows:
            sha = md_cell(str(row["sha256"])[:16])
            lines.append(f"| `{md_cell(row['path'])}` | `{sha}` "
                         f"| {row['status']} |")
    else:
        lines.append("_No artifacts recorded in this bundle._")

    decisions = bundle.get("decisions")
    lines += ["", "### Decisions", ""]
    if isinstance(decisions, list) and decisions:
        for d in decisions:
            if isinstance(d, dict):
                lines.append(f"- **{md_cell(d.get('context', ''))}** — "
                             f"{md_cell(d.get('choice', ''))} "
                             f"({md_cell(d.get('rationale', ''))})")
    else:
        lines.append("_No decisions recorded in this bundle._")

    evaluation = bundle.get("evaluation")
    ev = evaluation if isinstance(evaluation, dict) else {}
    lines += ["", "### Evaluation (recorded claims)", "",
              "> These are the claims recorded at signing time; verification "
              "proves they are unaltered, not that they are true.", "",
              f"- Status: {md_cell(ev.get('status', 'unknown'))}",
              f"- Tests passed: {md_cell(ev.get('tests_passed', 'n/a'))}",
              f"- Tests failed: {md_cell(ev.get('tests_failed', 'n/a'))}",
              f"- Lint errors: {md_cell(ev.get('lint_errors', 'n/a'))}",
              f"- Requirement coverage: "
              f"{md_cell(ev.get('requirement_coverage', 'n/a'))}"]

    att_info = result.get("attestation")
    att_info = att_info if isinstance(att_info, dict) else {}
    if att_info.get("present"):
        # Everything here is bundle-controlled and goes through md_cell —
        # approver emails and notes land in PR comments.
        lines += ["", "### Attestation", ""]
        lines.append(f"- Predicate type: {md_cell(att_info.get('predicate_type'))}")
        builder = att_info.get("builder")
        builder = builder if isinstance(builder, dict) else {}
        if isinstance(builder.get("id"), str):
            lines.append(f"- Builder id: {md_cell(builder['id'])}")
        model_obj = builder.get("model")
        if isinstance(model_obj, dict):
            lines.append(f"- Model (self-reported): "
                         f"{md_cell(model_obj.get('id', ''))}")
        plugin_obj = builder.get("plugin")
        if isinstance(plugin_obj, dict):
            lines.append(f"- Plugin version: "
                         f"{md_cell(plugin_obj.get('version', ''))}")
        lines.append(f"- Subjects: {md_cell(att_info.get('subject_count'))}")
        lines.append(f"- Key id (verifier-derived): "
                     f"{md_cell(att_info.get('key_id'))}")
        approvals = att_info.get("approvals")
        if isinstance(approvals, list) and approvals:
            lines += ["", "**Approvals (agent-recorded — the AI asserts the "
                          "human approved; not cryptographic proof of "
                          "consent):**", ""]
            for a in approvals:
                if isinstance(a, dict):
                    lines.append(f"- {md_cell(a.get('gate', ''))}: "
                                 f"{md_cell(a.get('decision', ''))} — "
                                 f"{md_cell(a.get('approver', '') or '(unknown)')} "
                                 f"({md_cell(a.get('note', '') or 'no note')})")
        issue_no = md_cell(binfo.get("issue"))
        lines += ["", "Reproduce this check without ForgeProof (cosign):", "",
                  "```",
                  f"cosign verify-blob-attestation --key .forgeproof/issue-{issue_no}.pub.pem \\",
                  f"  --bundle .forgeproof/issue-{issue_no}.sigstore.json \\",
                  "  --type slsaprovenance1 --insecure-ignore-tlog <artifact-path>",
                  "```"]

    lines += ["", "---",
              f"Strict mode: {'on' if result['strict'] else 'off'} · "
              f"Complete: {'yes' if result['complete'] else 'no'} · "
              f"Anchor: `{result['anchor']}`"]
    return "\n".join(lines)


def resolve_verify_anchor(rpack_path: Path, project_root: str | None) -> Path:
    """Directory that verification paths are resolved against.

    An explicit --project-root always wins. Otherwise a bundle sitting in a
    .forgeproof/ directory anchors to that directory's parent (the project
    root it was signed in), and a bare bundle anchors to its own directory.
    cmd_verify falls back to cwd-relative resolution whenever a path is not
    found at the anchor, so every pre-v1.2.0 layout (cwd == anchor) behaves
    exactly as before."""
    if isinstance(project_root, str) and project_root:
        return Path(project_root)
    parent = rpack_path.parent
    if parent.name == ".forgeproof":
        return parent.parent
    return parent


def cmd_verify(args: argparse.Namespace) -> None:
    """Verify a .rpack bundle's integrity."""
    rpack_path = Path(args.rpack)
    if not rpack_path.is_file():
        die(f"Bundle not found (or not a file): {rpack_path}")

    # v1.2.0 flags, shape-checked: cmd_verify is also driven in-process by
    # tests with partial namespaces (MagicMock args), and only well-typed
    # values may activate the new behavior.
    project_root = getattr(args, "project_root", None)
    if not isinstance(project_root, str):
        project_root = None
    strict = getattr(args, "strict", None) is True
    out_format = "markdown" if getattr(args, "format", None) == "markdown" else "json"

    bundle = read_json_file(rpack_path, "bundle")
    if not isinstance(bundle, dict):
        die(f"bundle is not a JSON object: {rpack_path}")
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []

    def check(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    anchor = resolve_verify_anchor(rpack_path, project_root)
    info(f"Verify anchor: {anchor}")

    # 1. Check format and version. Version recognition is MEMBERSHIP in
    # KNOWN_RPACK_VERSIONS — never equality with RPACK_VERSION and never an
    # ordering — so every version this engine line has ever shipped verifies
    # without a spurious warning, forever. The detail prints the BUNDLE's
    # version: an audit report must describe the bundle it verified, not the
    # verifier that ran.
    format_ok = bundle.get("format") == RPACK_FORMAT
    version_known = bundle.get("version") in KNOWN_RPACK_VERSIONS
    unknown_version_msg = (
        f"Unknown bundle version: {bundle.get('version')} "
        f"(known: {', '.join(sorted(KNOWN_RPACK_VERSIONS))})")
    if not format_ok:
        errors.append(f"Unknown format: {bundle.get('format')}")
    if not version_known:
        warnings.append(unknown_version_msg)
    if not format_ok:
        check("format", "fail", f"Unknown format: {bundle.get('format')}")
    elif not version_known:
        check("format", "warn", unknown_version_msg)
    else:
        check("format", "ok", f"{RPACK_FORMAT} v{bundle.get('version')}")

    # 2. Verify root digest
    stored_digest = bundle.get("root_digest", "")
    stored_signature = bundle.get("signature", "")
    public_key = bundle.get("public_key", "")

    # Recompute root digest: hash the bundle without root_digest and signature
    bundle_for_hash = {k: v for k, v in bundle.items() if k not in ("root_digest", "signature")}
    computed_digest = sha256_hex(canonical_json(bundle_for_hash))

    if computed_digest != stored_digest:
        errors.append(f"Root digest mismatch: computed {computed_digest[:16]}..., stored {str(stored_digest)[:16]}...")
        check("root_digest", "fail",
              f"computed {computed_digest[:16]}..., stored {str(stored_digest)[:16]}...")
    else:
        info("Root digest: OK")
        check("root_digest", "ok", "recomputed digest matches bundle content")

    # 3. Verify signature
    if not isinstance(stored_signature, str):
        errors.append("Signature field is not a string")
        check("signature", "fail", "Signature field is not a string")
    elif stored_signature and public_key:
        canonical_ok = signature_is_canonical(stored_signature)
        if not canonical_ok:
            errors.append("Signature field has trailing or altered data "
                          "(not canonical SSHSIG)")
        # stored_digest must be a str to sign/verify. A non-string root_digest
        # is already a mismatch error above; guard here so verify_signature is
        # never handed a non-str (which crashed on write_text) — a malformed
        # bundle fails cleanly instead of tracebacking.
        sig_ok = (isinstance(stored_digest, str)
                  and verify_signature(stored_digest, stored_signature, public_key))
        if not sig_ok:
            errors.append("Ed25519 signature verification FAILED")
        elif not errors:
            info("Signature: OK")
        if canonical_ok and sig_ok:
            check("signature", "ok", "Ed25519 signature valid for stored root digest")
        elif not sig_ok:
            check("signature", "fail", "Ed25519 signature verification FAILED")
        else:
            check("signature", "fail", "signature not canonical SSHSIG")
    elif not stored_signature:
        # A missing/blank signature is not "cannot verify yet" — the signature
        # lives inside the .rpack and always travels with it (finalize signs
        # before it ever writes the bundle), so its absence means the bundle is
        # unsigned or was stripped. Either way provenance cannot be established,
        # so this is a hard failure in every mode, not a warning. Without this,
        # an attacker can rewrite content, re-record hashes, drop the signature,
        # and recompute the (keyless, public) root_digest to forge verified:true.
        errors.append("No signature present in bundle — provenance cannot be verified")
        check("signature", "fail", "no signature present in bundle")
    else:
        # Signature present but no public_key to check it against — the same
        # forgery hole from the other side. public_key is inside the signed
        # digest, so a real bundle always carries it; its absence is a hard fail.
        errors.append("No public key present in bundle — signature cannot be verified")
        check("signature", "fail", "no public key present in bundle to verify signature")

    # 4. Verify chain hash. The chain file resolves against the anchor first
    # (bundle-relative layouts verify from any cwd), falling back to the
    # pre-v1.2.0 cwd-relative path so existing layouts are untouched.
    issue_field = bundle.get("issue")
    issue_num = str(issue_field.get("number", "")) if isinstance(issue_field, dict) else ""
    if issue_num:
        anchored_chain = anchor / chain_path(issue_num)
        chain_file = anchored_chain if anchored_chain.is_file() else chain_path(issue_num)
    else:
        chain_file = None
    chain_found = bool(chain_file and chain_file.is_file())
    chain_blocks: list | None = None
    if chain_found:
        actual_chain_hash = sha256_hex(chain_file.read_text())
        if actual_chain_hash != bundle.get("chain_hash"):
            errors.append(f"Chain hash mismatch: chain file has been modified since bundle was signed")
            check("chain_hash", "fail",
                  "chain file has been modified since bundle was signed")
        else:
            info("Chain hash: OK")
            check("chain_hash", "ok", "chain file matches sealed chain_hash")

        # 5. Verify chain integrity (block linkage). A corrupt chain that still
        # matched chain_hash is impossible, but a corrupt chain alongside an
        # intact bundle must fail closed, not traceback.
        linkage_start = len(errors)
        chain = read_json_file(chain_file, f"chain for issue {issue_num}")
        if not isinstance(chain, list):
            errors.append("Chain file is corrupt (not a list of blocks)")
            chain = []
        for i, block in enumerate(chain):
            if not isinstance(block, dict):
                errors.append(f"Block {i}: malformed (not an object)")
                continue
            if i == 0:
                if block.get("prev_hash") != GENESIS_PREV_HASH:
                    errors.append(f"Block 0: invalid genesis prev_hash")
            else:
                prev = chain[i - 1]
                prev_hash = prev.get("hash") if isinstance(prev, dict) else None
                if block.get("prev_hash") != prev_hash:
                    errors.append(f"Block {i}: prev_hash does not match block {i-1} hash")

            # Verify block hash
            block_for_hash = {
                k: v for k, v in block.items() if k not in ("hash", "signature")
            }
            expected_hash = sha256_hex(canonical_json(block_for_hash))
            if expected_hash != block.get("hash"):
                errors.append(f"Block {i}: hash mismatch (block has been tampered with)")

        info(f"Chain integrity: verified {len(chain)} blocks")
        linkage_errors = errors[linkage_start:]
        if linkage_errors:
            check("chain_linkage", "fail", "; ".join(linkage_errors[:3]))
        else:
            check("chain_linkage", "ok", f"verified {len(chain)} blocks")
        chain_blocks = chain
    else:
        missing_msg = (f"Chain file not found ({chain_file}). Cannot verify chain integrity. "
                       "This is normal if verifying a bundle from another repository.")
        if strict:
            errors.append(STRICT_PREFIX + missing_msg)
            check("chain_hash", "fail", STRICT_PREFIX + missing_msg)
        else:
            warnings.append(missing_msg)
            check("chain_hash", "warn", missing_msg)
        check("chain_linkage", "skipped", "no chain file to verify")

    # 6. Verify artifact hashes. Each artifact resolves against the anchor
    # first, falling back to the pre-v1.2.0 cwd-relative path.
    artifacts_checked = 0
    artifacts_missing = 0
    artifacts_tampered = 0
    artifact_rows: list[dict] = []
    for artifact in bundle.get("artifacts", []):
        recorded_path = Path(artifact["path"])
        anchored_artifact = anchor / recorded_path
        # Deliberate asymmetry: the chain path uses is_file() with a cwd
        # fallback; exists() here makes a directory squatting at the anchored
        # path resolve to it and fail closed below as "not a file".
        artifact_path = anchored_artifact if anchored_artifact.exists() else recorded_path
        row_status = "checked"
        if artifact_path.is_file():
            try:
                actual_hash = sha256_file(artifact_path)
            except OSError as e:
                # Unreadable (locked, permission) — can't confirm integrity,
                # so it's an error, never a crash.
                errors.append(f"Artifact unreadable: {artifact['path']} ({e})")
                artifacts_tampered += 1
                artifact_rows.append({"path": artifact["path"],
                                      "sha256": artifact.get("sha256", ""),
                                      "status": "tampered"})
                continue
            if actual_hash != artifact["sha256"]:
                errors.append(f"Artifact tampered: {artifact['path']} hash mismatch")
                artifacts_tampered += 1
                row_status = "tampered"
            artifacts_checked += 1
        elif artifact_path.exists():
            # Path exists but is not a regular file (e.g. replaced by a dir).
            errors.append(f"Artifact is not a file: {artifact['path']}")
            artifacts_tampered += 1
            row_status = "tampered"
        else:
            missing_msg = f"Artifact not found: {artifact['path']}"
            if strict:
                errors.append(STRICT_PREFIX + missing_msg)
            else:
                warnings.append(missing_msg)
            artifacts_missing += 1
            row_status = "missing"
        artifact_rows.append({"path": artifact["path"],
                              "sha256": artifact.get("sha256", ""),
                              "status": row_status})

    if artifacts_checked > 0:
        info(f"Artifacts: verified {artifacts_checked} files")
    if artifacts_missing > 0:
        info(f"Artifacts: {artifacts_missing} files not found (may be in a different checkout)")

    if artifacts_tampered > 0:
        check("artifacts", "fail",
              f"{artifacts_tampered} tampered/unreadable, {artifacts_checked} checked, "
              f"{artifacts_missing} missing")
    elif artifacts_missing > 0:
        check("artifacts", "fail" if strict else "warn",
              f"{artifacts_missing} missing, {artifacts_checked} checked")
    else:
        check("artifacts", "ok", f"{artifacts_checked} artifacts checked")

    # 7. Check requirement coverage
    eval_info = bundle.get("evaluation", {})
    eval_status = eval_info.get("status", "unknown")
    uncovered = eval_info.get("uncovered_requirements", [])
    if uncovered:
        warnings.append(f"Uncovered requirements: {', '.join(uncovered)}")
        check("coverage", "warn", f"Uncovered requirements: {', '.join(uncovered)}")
    else:
        check("coverage", "ok",
              f"requirement coverage {eval_info.get('requirement_coverage', 'n/a')}")

    # 8. Attestation checks (v1.3, additive). An ABSENT attestation is
    # silent: skipped status, zero errors, zero warnings, in every mode
    # including --strict — no version implies its presence. And verify never
    # touches the filesystem for attestation purposes: the embedded copy is
    # inside root_digest; the sidecar is the one file no signature covers.
    # These are INVARIANT checks over the signed payload, never a byte
    # re-derivation of the statement (a future predicate change must not turn
    # valid old bundles red).
    attestation_summary: dict[str, Any] = {
        "present": False, "predicate_type": None, "subject_count": None,
        "key_id": None, "builder": None, "approvals": []}
    if "attestation" not in bundle:
        check("attestation", "skipped", "no attestation in bundle (pre-v1.3 format)")
        check("attestation_signature", "skipped", "no attestation in bundle")
        check("attestation_subjects", "skipped", "no attestation in bundle")
    else:
        attestation_summary["present"] = True
        statement, att_payload, att_problem = _attestation_statement(
            bundle["attestation"])
        if att_problem:
            # Root digest intact + malformed attestation = it was SIGNED
            # malformed (an engine bug or hand-built statement), not altered
            # afterwards — a plain error that matches no tamper marker.
            errors.append(f"Attestation malformed: {att_problem}")
            check("attestation", "fail", f"Attestation malformed: {att_problem}")
            check("attestation_signature", "skipped",
                  "not evaluated (attestation malformed)")
            check("attestation_subjects", "skipped",
                  "not evaluated (attestation malformed)")
        else:
            subject_list = statement["subject"]
            predicate = statement.get("predicate")
            predicate = predicate if isinstance(predicate, dict) else {}
            build_def = predicate.get("buildDefinition")
            build_def = build_def if isinstance(build_def, dict) else {}
            run_details = predicate.get("runDetails")
            run_details = run_details if isinstance(run_details, dict) else {}
            internal = build_def.get("internalParameters")
            internal = internal if isinstance(internal, dict) else {}
            external = build_def.get("externalParameters")
            external = external if isinstance(external, dict) else {}

            attestation_summary["predicate_type"] = statement["predicateType"]
            attestation_summary["subject_count"] = len(subject_list)
            approvals_val = external.get("approvals")
            attestation_summary["approvals"] = (
                approvals_val if isinstance(approvals_val, list) else [])
            builder_summary: dict[str, Any] = {}
            rd_builder = run_details.get("builder")
            if isinstance(rd_builder, dict) and isinstance(rd_builder.get("id"), str):
                builder_summary["id"] = rd_builder["id"]
            internal_builder = internal.get("builder")
            if isinstance(internal_builder, dict):
                builder_summary.update(internal_builder)
            attestation_summary["builder"] = builder_summary or None
            check("attestation", "ok",
                  f"in-toto statement, {len(subject_list)} subject(s)")

            # 9. DSSE signature, verified against the bundle's OWN
            # ssh-ed25519 key — never against key material carried inside the
            # attestation, which would prove nothing. This binding is the
            # payoff of signing both tiers with one key.
            dsse_key = None
            if isinstance(public_key, str):
                try:
                    dsse_key = ssh_ed25519_pubkey_bytes(public_key)
                except ValueError:
                    dsse_key = None
            if dsse_key is None:
                errors.append("Attestation key mismatch: bundle public_key is "
                              "not a parseable ssh-ed25519 key")
                check("attestation_signature", "fail",
                      "bundle public_key is not a parseable ssh-ed25519 key")
            else:
                attestation_summary["key_id"] = base64.b64encode(
                    hashlib.sha256(ED25519_SPKI_PREFIX + dsse_key).digest()
                ).decode("ascii")
                env = bundle["attestation"]["dsseEnvelope"]
                try:
                    dsse_sig = base64.b64decode(
                        env["signatures"][0]["sig"].encode("ascii"),
                        validate=True)
                except (ValueError, UnicodeEncodeError):
                    dsse_sig = b""
                pae = dsse_pae(env["payloadType"], att_payload)
                if ed25519_verify(dsse_key, pae, dsse_sig):
                    check("attestation_signature", "ok",
                          "DSSE signature valid under the bundle's own key")
                else:
                    errors.append(
                        "Attestation signature invalid: DSSE signature does "
                        "not verify under the bundle's key")
                    check("attestation_signature", "fail",
                          "DSSE signature does not verify under the bundle's key")

            # 10. Subjects equal the bundle's artifact set exactly (or the
            # single chain descriptor for a zero-artifact bundle), and the
            # chain byproduct digest equals the SEALED chain_hash — compared,
            # never recomputed (LF-normalization, finding 8).
            subj_problem = ""
            actual_subjects = set()
            for s in subject_list:
                if (not isinstance(s, dict)
                        or not isinstance(s.get("name"), str)
                        or not isinstance(s.get("digest"), dict)
                        or not isinstance(s["digest"].get("sha256"), str)):
                    subj_problem = "subject entry malformed"
                    break
                actual_subjects.add((s["name"], s["digest"]["sha256"]))
            bundle_artifacts = bundle.get("artifacts")
            expected_subjects = set()
            if isinstance(bundle_artifacts, list) and bundle_artifacts:
                for a in bundle_artifacts:
                    if isinstance(a, dict):
                        expected_subjects.add(
                            (str(a.get("path", "")), str(a.get("sha256", ""))))
            else:
                expected_subjects.add(
                    (f".forgeproof/chain-{issue_num}.json",
                     str(bundle.get("chain_hash", ""))))
            chain_byproduct = None
            byproducts = run_details.get("byproducts")
            for b in (byproducts if isinstance(byproducts, list) else []):
                if (isinstance(b, dict)
                        and b.get("name") == f".forgeproof/chain-{issue_num}.json"):
                    chain_byproduct = b
                    break
            if subj_problem:
                errors.append(f"Attestation malformed: {subj_problem}")
                check("attestation_subjects", "fail",
                      f"Attestation malformed: {subj_problem}")
            elif actual_subjects != expected_subjects:
                errors.append(
                    "Attestation subjects do not match the bundle's artifacts")
                check("attestation_subjects", "fail",
                      "subject set does not equal the bundle's artifact set")
            elif (not isinstance(chain_byproduct, dict)
                    or not isinstance(chain_byproduct.get("digest"), dict)
                    or not isinstance(chain_byproduct["digest"].get("sha256"), str)):
                errors.append(
                    "Attestation malformed: chain byproduct descriptor missing")
                check("attestation_subjects", "fail",
                      "chain byproduct descriptor missing")
            elif chain_byproduct["digest"]["sha256"] != bundle.get("chain_hash"):
                errors.append(
                    "Attestation chain digest does not match the sealed chain_hash")
                check("attestation_subjects", "fail",
                      "chain byproduct digest does not match the sealed chain_hash")
            else:
                check("attestation_subjects", "ok",
                      f"{len(actual_subjects)} subject(s) match the bundle; "
                      "chain byproduct matches the sealed chain_hash")

    # Bundle summary (recorded claims + chain metadata when available)
    commit_sha = None
    first_timestamp = last_timestamp = None
    chain_length = None
    if chain_blocks is not None:
        chain_length = len(chain_blocks)
        if chain_blocks:
            first = chain_blocks[0]
            last = chain_blocks[-1]
            first_timestamp = first.get("timestamp") if isinstance(first, dict) else None
            last_timestamp = last.get("timestamp") if isinstance(last, dict) else None
        for block in reversed(chain_blocks):
            if isinstance(block, dict) and block.get("action") == "finalize":
                data = block.get("data")
                commit_sha = data.get("commit_sha") if isinstance(data, dict) else None
                break
    bundle_summary = {
        "issue": issue_field.get("number") if isinstance(issue_field, dict) else None,
        "title": issue_field.get("title") if isinstance(issue_field, dict) else None,
        "root_digest": stored_digest,
        "public_key": public_key,
        "chain_length": chain_length,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "commit_sha": commit_sha,
        "evaluation_status": eval_status,
    }

    # Build result: the seven pre-v1.2.0 keys first, in their frozen order
    # and with their frozen values, then the additive v1.2.0 keys.
    verified = len(errors) == 0
    complete = chain_found and artifacts_missing == 0
    result = {
        "verified": verified,
        "evaluation_status": eval_status,
        "errors": errors,
        "warnings": warnings,
        "artifacts_checked": artifacts_checked,
        "artifacts_missing": artifacts_missing,
        "artifacts_tampered": artifacts_tampered,
        "anchor": str(anchor),
        "strict": strict,
        "complete": complete,
        "checks": checks,
        "bundle": bundle_summary,
        "attestation": attestation_summary,
    }
    if out_format == "markdown":
        print(_render_verify_markdown(result, bundle, chain_blocks, artifact_rows))
    else:
        print(json.dumps(result, indent=2))
    sys.exit(0 if verified else 1)


# ---------------------------------------------------------------------------
# Subcommand: summary
# ---------------------------------------------------------------------------


def cmd_summary(args: argparse.Namespace) -> None:
    """Output a PR-ready summary for an issue."""
    issue = args.issue
    rpack_path = CHAIN_DIR / f"issue-{issue}.rpack"

    if not rpack_path.is_file():
        die(f"No .rpack bundle found for issue {issue}. Run 'finalize' first.")

    bundle = read_json_file(rpack_path, "bundle")
    if not isinstance(bundle, dict):
        die(f"bundle is not a JSON object: {rpack_path}")
    try:
        issue_info = bundle["issue"]
        evaluation = bundle["evaluation"]
        reqs = bundle["requirements"]
        artifacts = bundle["artifacts"]
        status = evaluation["status"]
        _ = issue_info["number"]
        root_digest = bundle["root_digest"]
        # A non-string digest would traceback on the [:16] slice below; treat it
        # like any other malformed required field and die cleanly.
        if not isinstance(root_digest, str):
            raise TypeError("root_digest must be a string")
    except (KeyError, TypeError):
        die(f"bundle is missing required fields (corrupt or not a ForgeProof "
            f"bundle): {rpack_path}")

    # Additive v1.3 key, read OUTSIDE the required-field guard above: a
    # pre-v1.3 bundle without it must never be declared corrupt.
    attestation = bundle.get("attestation")

    # Status emoji
    status_badge = {"pass": "PASS", "partial": "PARTIAL", "fail": "FAIL"}.get(status, "UNKNOWN")

    lines = [
        f"## ForgeProof Provenance — Issue #{issue_info['number']}",
        "",
        f"**Status:** {status_badge}",
        f"**Bundle:** `.forgeproof/issue-{issue}.rpack`",
        f"**Root Digest:** `{root_digest[:16]}...`",
        "",
        "### Requirement Coverage",
        "",
        "| ID | Requirement | Status | Tests |",
        "|----|-------------|--------|-------|",
    ]

    for req in reqs:
        tests_str = ", ".join(req.get("tests", [])) or "—"
        lines.append(f"| {req['id']} | {req['text']} | {req['status']} | {tests_str} |")

    lines.extend([
        "",
        "### Evaluation",
        "",
        f"- Tests passed: {evaluation['tests_passed']}",
        f"- Tests failed: {evaluation['tests_failed']}",
        f"- Lint errors: {evaluation['lint_errors']}",
        f"- Coverage: {evaluation['requirement_coverage']}",
    ])

    if evaluation.get("uncovered_requirements"):
        lines.append(f"- Uncovered: {', '.join(evaluation['uncovered_requirements'])}")

    lines.extend([
        "",
        "### Artifacts",
        "",
    ])
    for a in artifacts:
        lines.append(f"- `{a['path']}` ({a['operation']})")

    if isinstance(attestation, dict):
        lines.extend([
            "",
            "### Attestation",
            "",
            f"- Sigstore bundle: `.forgeproof/issue-{issue}.sigstore.json`",
            f"- Public key (SPKI PEM): `.forgeproof/issue-{issue}.pub.pem`",
            "- Verify without ForgeProof (optional): "
            f"`cosign verify-blob-attestation --key .forgeproof/issue-{issue}.pub.pem "
            f"--bundle .forgeproof/issue-{issue}.sigstore.json "
            "--type slsaprovenance1 --insecure-ignore-tlog <artifact-path>`",
        ])

    lines.extend([
        "",
        "---",
        f"*Verify: `/forgeproof:verify .forgeproof/issue-{issue}.rpack`*",
    ])

    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Subcommand: issues
# ---------------------------------------------------------------------------


def cmd_issues(args: argparse.Namespace) -> None:
    """List open GitHub issues assigned to the current user."""
    assignee = args.assignee or "@me"
    limit = args.limit or 20

    result = run([
        "gh", "issue", "list",
        "--assignee", assignee,
        "--state", "open",
        "--limit", str(limit),
        "--json", "number,title,labels,updatedAt,url",
    ])

    if result.returncode != 0:
        die(f"gh issue list failed: {result.stderr.strip()}")

    # Pass through the JSON output
    print(result.stdout.strip())


# ---------------------------------------------------------------------------
# Subcommand: lint
# ---------------------------------------------------------------------------


def cmd_lint(args: argparse.Namespace) -> None:
    """Run the detected linter for the project (or one file via --file)."""
    detection = detect_toolchain(Path.cwd())
    if not detection.get("detected"):
        die("No supported project configuration found")

    # Run first available linter — list-form spawn, no shell; output merging
    # and truncation happen here in Python, not via POSIX tools.
    for lang in detection.get("languages", []):
        linter = lang.get("linter")
        if linter and linter.get("argv"):
            argv = list(linter["argv"])
            if args.file:
                if argv[-1] == ".":
                    argv[-1] = args.file
                # Project-scope linters (golangci-lint) ignore --file.
            if args.quiet:
                argv.append("--quiet")
            result = run(argv)
            output = (result.stdout or "") + (result.stderr or "")
            if args.quiet:
                output = "\n".join(output.splitlines()[:20])
            if output.strip():
                print(output.rstrip("\n"))
            sys.exit(result.returncode)

    info("No linter available for this project")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Subcommand: lint-hook (PostToolUse hook)
# ---------------------------------------------------------------------------


def cmd_lint_hook(_args: argparse.Namespace) -> None:
    """PostToolUse hook: lint just the edited file during an active run.

    Reads the hook event JSON from stdin. Exits 0 silently unless there is an
    active chain in the cwd AND the edited file lints with findings, in which
    case the findings are surfaced to Claude via additionalContext JSON on
    stdout. Always exits 0 — lint feedback must never block an edit.
    """
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError, RecursionError):
        # RecursionError: a deeply nested event JSON overflows json's scanner.
        # Any unparseable event means "nothing to act on" — exit cleanly (the
        # gate's fail-safe is allow; lint-hook always no-ops), never traceback.
        sys.exit(0)
    if not isinstance(event, dict):
        sys.exit(0)  # well-formed JSON of the wrong shape must never crash

    # Session scoping: only active ForgeProof runs pay the lint cost.
    if not list(CHAIN_DIR.glob("chain-*.json")):
        sys.exit(0)

    tool_input = event.get("tool_input")
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str) or not file_path:
        sys.exit(0)
    target = Path(file_path)
    if not target.is_file():
        sys.exit(0)
    try:
        rel = target.resolve().relative_to(Path.cwd().resolve())
    except (ValueError, OSError):
        sys.exit(0)  # outside the project

    detection = detect_toolchain(Path.cwd())
    if not detection.get("detected"):
        sys.exit(0)

    suffix = target.suffix.lower()
    for lang in detection.get("languages", []):
        if suffix not in LANG_EXTENSIONS.get(lang["language"], set()):
            continue
        linter = lang.get("linter")
        if not linter or not linter.get("argv"):
            continue
        argv = list(linter["argv"])
        if argv[-1] != ".":
            continue  # project-scope-only linter; per-file lint unsupported
        argv[-1] = str(rel)
        try:
            result = run(argv)
        except OSError:
            sys.exit(0)
        findings = ((result.stdout or "") + (result.stderr or "")).strip()
        if result.returncode != 0 and findings:
            context = (
                f"forgeproof lint ({linter['name']}) findings for {rel}:\n"
                + "\n".join(findings.splitlines()[:20])
            )
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context,
                }
            }))
        break

    sys.exit(0)


# ---------------------------------------------------------------------------
# Subcommand: reset
# ---------------------------------------------------------------------------


def cmd_reset(args: argparse.Namespace) -> None:
    """Clean up ForgeProof state for an issue or all issues."""
    deleted = []

    if getattr(args, "all", False):
        # Delete all chains, rpacks, and ephemeral keys
        if CHAIN_DIR.exists():
            for f in CHAIN_DIR.glob("chain-*.json"):
                f.unlink()
                deleted.append(str(f))
            for f in CHAIN_DIR.glob("issue-*.rpack"):
                f.unlink()
                deleted.append(str(f))
            # Attestation sidecars: two NAMED globs, never a broad issue-*
            # (which would also eat unrelated files someone parked there).
            for f in CHAIN_DIR.glob("issue-*.sigstore.json"):
                f.unlink()
                deleted.append(str(f))
            for f in CHAIN_DIR.glob("issue-*.pub.pem"):
                f.unlink()
                deleted.append(str(f))
        # Clean up temp keys
        tmpdir = Path(tempfile.gettempdir())
        for f in tmpdir.glob("forgeproof_*_ed25519*"):
            f.unlink()
            deleted.append(str(f))
    elif args.issue:
        issue = args.issue
        chain = chain_path(issue)
        if chain.exists():
            chain.unlink()
            deleted.append(str(chain))
        rpack = CHAIN_DIR / f"issue-{issue}.rpack"
        if rpack.exists():
            rpack.unlink()
            deleted.append(str(rpack))
        attestation = CHAIN_DIR / f"issue-{issue}.sigstore.json"
        if attestation.exists():
            attestation.unlink()
            deleted.append(str(attestation))
        pem = CHAIN_DIR / f"issue-{issue}.pub.pem"
        if pem.exists():
            pem.unlink()
            deleted.append(str(pem))
        # Clean up ephemeral key
        key = Path(tempfile.gettempdir()) / f"forgeproof_{issue}_ed25519"
        key.unlink(missing_ok=True)
        Path(f"{key}.pub").unlink(missing_ok=True)
    else:
        die("Specify --issue N or --all")

    output = {"deleted": deleted, "count": len(deleted)}
    print(json.dumps(output, indent=2))
    if deleted:
        info(f"Deleted {len(deleted)} file(s)")
    else:
        info("Nothing to clean up")


# ---------------------------------------------------------------------------
# Subcommand: gate-pr (PreToolUse hook)
# ---------------------------------------------------------------------------


def cmd_gate_pr(_args: argparse.Namespace) -> None:
    """PreToolUse gate: block 'gh pr create' if no .rpack bundle exists.

    Reads the hook event JSON from stdin. Exits 0 when the call should be
    allowed (event unparseable, tool that is not a shell, command not 'gh pr
    create', or a bundle already exists in .forgeproof/). Blocks via
    permissionDecision deny JSON on stdout plus exit 2 with the reason on
    stderr.

    Both shell tools are covered: Claude Code exposes Bash everywhere and a
    first-class PowerShell tool on Windows — gating only Bash would let
    'gh pr create' through PowerShell bypass the gate entirely.
    """
    try:
        event = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError, RecursionError):
        # RecursionError: a deeply nested event JSON overflows json's scanner.
        # Any unparseable event means "nothing to act on" — exit cleanly (the
        # gate's fail-safe is allow; lint-hook always no-ops), never traceback.
        sys.exit(0)
    if not isinstance(event, dict):
        sys.exit(0)  # well-formed JSON of the wrong shape must never crash

    tool = event.get("tool_name")
    tool_input = event.get("tool_input")
    cmd = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(cmd, str):
        cmd = ""

    # The gate blocks only on a positively-identified 'gh pr create'; anything
    # it cannot interpret is allowed (consistent with the unparseable case),
    # but it must decide that WITHOUT crashing.
    if tool not in ("Bash", "PowerShell") or "gh pr create" not in cmd:
        sys.exit(0)

    # A structurally valid signed bundle is required — not just any file named
    # *.rpack (a garbage file used to satisfy an existence check would sail
    # through). This is a lightweight shape check only: parse as JSON and
    # confirm the signing fields are present and non-empty. It deliberately
    # does NOT run the cryptographic verify (no ssh-keygen, no SHA-256 over
    # artifacts) — the gate runs synchronously under a 10s hook budget on every
    # 'gh pr create', and full verification is CI's job. A parse failure on one
    # candidate is swallowed (that file simply isn't a valid bundle); the gate
    # allows iff at least one candidate is structurally valid.
    for candidate in CHAIN_DIR.glob("*.rpack"):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            # Any failure — unreadable, invalid JSON, or RecursionError on
            # deeply nested input — means this candidate is not a usable bundle.
            # Swallow it and keep looking; a crafted .rpack must never crash the
            # gate into a non-2 exit that Claude Code reads as fail-open.
            continue
        if not isinstance(data, dict):
            continue
        if data.get("format") != RPACK_FORMAT:
            continue
        sig = data.get("signature")
        pub = data.get("public_key")
        digest = data.get("root_digest")
        # Shape-check the signing fields — NOT the cryptography. The gate runs
        # synchronously under a 10s hook budget, so full verification (ssh-keygen
        # + artifact hashing) is CI's job; here we confirm the fields at least
        # LOOK like a signed bundle: SSHSIG armor, an ssh-* public key, and a
        # 64-char hex digest. This keeps "a signed bundle is present" honest
        # rather than accepting any non-empty strings.
        if (isinstance(sig, str) and signature_is_canonical(sig)
                and isinstance(pub, str) and pub.startswith("ssh-")
                and isinstance(digest, str) and len(digest) == 64
                and all(c in "0123456789abcdef" for c in digest)):
            sys.exit(0)

    reason = (
        "No structurally valid signed .rpack bundle found in .forgeproof/. "
        "Run /forgeproof:run first to generate a provenance bundle, "
        "then use /forgeproof:push to create the PR."
    )
    # Dual-protocol block: permissionDecision JSON on stdout is honored
    # independent of shell and exit-code translation (e.g. PowerShell-spawned
    # hooks); exit 2 + stderr is the classic path. Whichever protocol the
    # running Claude Code honors, the gate fails closed.
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    print(f"BLOCK: {reason}", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


class _RemovedDataFlag(argparse.Action):
    """--data was the v1.0.x quoted-JSON surface; it breaks on any shell when
    a value contains quotes. Fail loudly with the migration mapping."""

    def __call__(self, parser, namespace, values, option_string=None):
        parser.error(
            "--data was removed in v1.1.0; recording uses discrete flags now. "
            "init: --title TEXT --requirement 'REQ-1: text' (repeatable). "
            "record: branch-create --branch --base --base-sha | "
            "file-edit --path --operation (sha256 is computed by the engine) | "
            "decision --context --choice --rationale | "
            "test-result --suite --passed --failed [--covers 'REQ-1=test_a,test_b'] [--failed-test NAME] | "
            "lint-result --tool --errors --warnings | "
            "approval --gate --decision [--note]"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="forgeproof",
        description="Ed25519-signed SHA-256 hash chain provenance engine",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # preflight
    sub.add_parser("preflight", help="Check core dependencies")

    # detect
    p = sub.add_parser("detect", help="Detect project language and toolchain")
    p.add_argument("--project-root", help="Project root directory (default: cwd)")

    # init
    p = sub.add_parser("init", help="Initialize chain for an issue")
    p.add_argument("--issue", required=True, help="Issue number")
    p.add_argument("--title", help="Issue title")
    p.add_argument("--requirement", action="append", metavar="'REQ-1: text'",
                   help="Requirement (repeatable)")
    p.add_argument("--force", action="store_true", help="Overwrite existing chain")
    p.add_argument("--data", action=_RemovedDataFlag, help=argparse.SUPPRESS)

    # record
    p = sub.add_parser("record", help="Record a block in the chain")
    p.add_argument("--issue", required=True, help="Issue number")
    p.add_argument("--action", required=True, choices=sorted(RECORD_FLAG_SPEC),
                   help="Action type")
    p.add_argument("--data", action=_RemovedDataFlag, help=argparse.SUPPRESS)
    # branch-create
    p.add_argument("--branch", help="[branch-create] Branch name")
    p.add_argument("--base", help="[branch-create] Base branch name")
    p.add_argument("--base-sha", help="[branch-create] Base branch commit SHA")
    # file-edit
    p.add_argument("--path", help="[file-edit] File path (engine computes its SHA-256)")
    p.add_argument("--operation", choices=["create", "modify"],
                   help="[file-edit] Operation")
    # decision
    p.add_argument("--context", help="[decision] What was being decided")
    p.add_argument("--choice", help="[decision] What was chosen")
    p.add_argument("--rationale", help="[decision] Why")
    # test-result
    p.add_argument("--suite", help="[test-result] Test suite name")
    p.add_argument("--passed", type=int, help="[test-result] Tests passed")
    p.add_argument("--failed", type=int, help="[test-result] Tests failed")
    p.add_argument("--covers", action="append", metavar="'REQ-1=test_a,test_b'",
                   help="[test-result] Requirement coverage (repeatable)")
    p.add_argument("--failed-test", action="append", metavar="NAME",
                   help="[test-result] Name of a failing test (repeatable)")
    # lint-result
    p.add_argument("--tool", help="[lint-result] Linter name")
    p.add_argument("--errors", type=int, help="[lint-result] Error count")
    p.add_argument("--warnings", type=int, help="[lint-result] Warning count")
    # approval
    p.add_argument("--gate", help="[approval] Gate the human approved (e.g. plan)")
    p.add_argument("--decision",
                   choices=["approved", "rejected", "changes-requested"],
                   help="[approval] Human decision at the gate")
    p.add_argument("--note", help="[approval] Optional approval note")

    # finalize
    p = sub.add_parser("finalize", help="Finalize chain and build .rpack")
    p.add_argument("--issue", required=True, help="Issue number")
    p.add_argument("--commit", required=True, help="Commit SHA")
    p.add_argument("--model",
                   help="Model id the agent reports it is running as "
                        "(recorded self-reported in the builder identity)")

    # verify
    p = sub.add_parser("verify", help="Verify a .rpack bundle")
    p.add_argument("--rpack", required=True, help="Path to .rpack file")
    p.add_argument("--project-root",
                   help="Resolve chain/artifact paths against this directory "
                        "(default: inferred from the bundle's location)")
    p.add_argument("--strict", action="store_true",
                   help="Treat missing evidence (chain file, artifacts) as "
                        "errors instead of warnings")
    p.add_argument("--format", choices=["json", "markdown"], default="json",
                   help="Output format: machine-readable JSON (default) or "
                        "a markdown audit report")

    # summary
    p = sub.add_parser("summary", help="Output PR-ready summary")
    p.add_argument("--issue", required=True, help="Issue number")

    # issues
    p = sub.add_parser("issues", help="List open GitHub issues")
    p.add_argument("--assignee", default="@me", help="Assignee filter")
    p.add_argument("--limit", type=int, default=20, help="Max issues to list")

    # lint
    p = sub.add_parser("lint", help="Run detected linter")
    p.add_argument("--quiet", action="store_true", help="Minimal output")
    p.add_argument("--file", help="Lint a single file instead of the project")

    # lint-hook (consumes hook event JSON on stdin; no flags)
    sub.add_parser("lint-hook", help="PostToolUse per-file lint hook")

    # reset
    p = sub.add_parser("reset", help="Clean up ForgeProof state")
    p.add_argument("--issue", help="Issue number to clean up")
    p.add_argument("--all", action="store_true", help="Clean up all issues")

    # gate-pr (consumes hook event JSON on stdin; no flags)
    sub.add_parser("gate-pr", help="PreToolUse gate for 'gh pr create'")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # Emit UTF-8 no matter the platform: Windows encodes piped stdout with a
    # legacy codepage by default, which turned summary punctuation (em dash)
    # into mojibake for whoever captured the output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass

    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "preflight": cmd_preflight,
        "detect": cmd_detect,
        "init": cmd_init,
        "record": cmd_record,
        "finalize": cmd_finalize,
        "verify": cmd_verify,
        "summary": cmd_summary,
        "issues": cmd_issues,
        "lint": cmd_lint,
        "lint-hook": cmd_lint_hook,
        "reset": cmd_reset,
        "gate-pr": cmd_gate_pr,
    }

    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
