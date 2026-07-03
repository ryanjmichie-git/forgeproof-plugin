# .rpack Bundle Format

The `.rpack` file is a JSON document containing the complete provenance record for a ForgeProof run. Version: 1.0.0.

## Schema

```json
{
  "version": "1.0.0",
  "format": "forgeproof-rpack",
  "issue": {
    "number": 42,
    "title": "Add rate limiting",
    "url": "https://github.com/org/repo/issues/42"
  },
  "requirements": [
    {
      "id": "REQ-1",
      "text": "Add rate limiter middleware",
      "status": "covered",
      "tests": ["test_rate_limit_middleware"]
    }
  ],
  "artifacts": [
    {
      "path": "src/rate_limiter.py",
      "operation": "create",
      "sha256": "a1b2c3..."
    }
  ],
  "decisions": [
    {
      "context": "Rate limiting approach",
      "choice": "Token bucket algorithm",
      "rationale": "Simple and effective for API endpoints"
    }
  ],
  "evaluation": {
    "status": "pass",
    "tests_passed": 5,
    "tests_failed": 0,
    "lint_errors": 0,
    "requirement_coverage": "100%",
    "uncovered_requirements": [],
    "failed_tests": []
  },
  "chain_hash": "SHA-256 of the chain JSON file at finalization time",
  "root_digest": "SHA-256 of canonical JSON of all fields above (excluding root_digest and signature)",
  "public_key": "ssh-ed25519 AAAA...",
  "signature": "Ed25519 signature of root_digest"
}
```

## Evaluation Status

| Status | Meaning |
|--------|---------|
| `pass` | All requirements covered, all tests pass, no lint errors |
| `partial` | Some requirements uncovered or some tests failing |
| `fail` | Critical failures — no tests pass or chain integrity compromised |

Bundles are always produced regardless of status.

## Verification

The `verify` subcommand checks:
1. Root digest recomputation matches stored value
2. Ed25519 signature validates against embedded public key
3. Chain hash matches the chain file on disk (if present)
4. Chain block linkage is intact (each prev_hash matches)
5. Artifact SHA-256 hashes match files on disk (if present)

Missing chain files or artifacts produce warnings, not errors — this is normal when verifying bundles from a different checkout.
