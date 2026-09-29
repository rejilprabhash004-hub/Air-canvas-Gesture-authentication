# SecureAir threat model and limitations

## Assets

- Account identifiers and password verifiers, never plaintext passwords.
- Locally enrolled biometric features and trained models.
- One-time challenge state, configured protected domains, and sessions.
- Security events, chain state, and exported reports/digests.

## Threats addressed in part

- Observation of a previously used gesture: vary challenges and expire them quickly.
- Repeated guessing: rate limiting and temporary lockout.
- Challenge replay: bind a one-time challenge to the user and expire it.
- Unconfigured-site access in the demo: explicit site settings and server-side demo authorization.
- Individual event-row changes: verify the cryptographic hash chain before writes and dashboard reads; reject direct profile deletes and route profile removal through chain-aware atomic deletion/re-chaining.
- Oversized export inputs: enforce a bounded event count during iterable consumption and cap text-field lengths.

## Residual risk / out of scope

A compromised operating system, administrator malware, or theft of the computer can expose local data and rewrite local logs, remove database triggers, and recompute chains. Local chain hashes are not an external trust anchor, signature, trusted timestamp, or non-repudiation mechanism. A report digest is useful only when compared with a separately trusted digest; replacing both report and digest defeats the check. Camera tampering, advanced spoofing, coercion, false accepts/rejects, and shoulder-surfing cannot be eliminated. API observations and behavioral scores are caller-supplied and forgeable. The browser extension is not an authentication boundary and does not block navigation. Model performance depends on sample quality, evaluation splits, camera, lighting, and thresholds.

## Controls and privacy boundaries

- No cloud upload and no raw-video storage.
- Minimize stored features and provide profile deletion through the chain-aware helper.
- Never collect passwords, cookies, messages, form data, or page content.
- Limit extension status checks to user-configured exact hostnames; keep local history separate from backend event reports.
- Bind service to loopback and validate local requests; reject unverified event history before dashboard exposure or append.
- Keep secrets/biometric data out of Git; apply restrictive local file permissions where possible.
- Explain lockout and recovery; do not present visual biometrics as perfect or sufficient alone.
- Treat reports and their digest files as private. Do not expose export helpers over an unauthenticated network endpoint.

SecureAir is an educational/research prototype, not a production identity system.
