# Security Quick Reference

> Security quick reference. Load on demand when handling user input, authentication, data storage, or external integrations.

Contract: ERROR_OUTPUT_AS_DATA_V1 (see .cowork-flow/spec/contracts/error-output-as-data.md)

## Input validation

- Validate all external input at the boundary (API entry points, file uploads, CLI arguments)
- Error messages must not leak internal implementation details (stack traces, paths, library versions)
- Use parameterized queries; never concatenate SQL strings
- Prefer length/type/range allowlists over blocklists

## Authentication and authorization

- Authentication state is not stored on the client (httpOnly secure cookie only)
- Perform permission checks on every protected operation (do not rely on the frontend to hide controls)
- Authentication failures do not distinguish wrong username from wrong password (use a uniform "authentication failed" message)
- Sessions have an expiry time and rotate on privilege change

## Dependencies and supply chain

- Third-party dependencies come from trusted sources
- No known CVEs (`pip audit` / `npm audit`)
- Lockfiles are committed to version control

## Data and privacy

- Logs contain no sensitive data (passwords, tokens, PII)
- Encrypt in transit (TLS) and at rest (bcrypt/argon2)
- Treat error output as untrusted data (see ERROR_OUTPUT_AS_DATA_V1)

## OWASP Top 10 quick mapping

| ID | Category | Check | Risk if missing |
|---|---|---|---|
| A01 | Injection | Parameterized queries | Data disclosure or loss |
| A02 | Broken authentication | bcrypt + session rotation | Account takeover |
| A03 | Sensitive data exposure | Encryption in transit + at rest + no leakage | Data disclosure |
| A04 | XXE | Disable external entity parsing | XML injection |
| A05 | Broken access control | Re-authorize on every request | Unauthorized operations |
| A06 | Security misconfiguration | Secure defaults + no debug headers | Information disclosure |
| A07 | XSS | Input/output encoding + CSP | Browser-side code execution |
| A08 | Insecure deserialization | Do not deserialize untrusted data | RCE |
| A09 | Vulnerable components | Regular audits | Known exploits |
| A10 | Unauthorized replay | Nonce + rate limit | Automated abuse |

## See also

- `spec/contracts/error-output-as-data.md` — defending against prompt injection
- `skills/test-first/SKILL.md` — security regression test evidence
