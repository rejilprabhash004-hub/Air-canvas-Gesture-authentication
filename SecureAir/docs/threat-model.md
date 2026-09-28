# SecureAir threat model and limitations

## Assets

- Account identifiers and password verifiers, never plaintext passwords.
- Locally enrolled biometric features and trained models.
- One-time challenge state, configured protected domains, and sessions.
- Security events and exported forensic reports.

## Threats addressed in part

- Observation of a previously used gesture: vary challenges and expire them quickly.
- Repeated guessing: rate limiting and temporary lockout.
- Challenge replay: bind a one-time challenge to the user and expire it.
- Unconfigured-site access: explicit site settings; enforce demo authorization server-side.
- Individual event-row changes: verify a cryptographic hash chain.

## Residual risk / out of scope

A compromised operating system, administrator malware, or theft of the computer can expose local data and rewrite local logs. Camera tampering, advanced spoofing, coercion, false accepts/rejects, and shoulder-surfing cannot be eliminated. A compromised browser can bypass extension controls. Extensions cannot replace third-party login. Hashing is integrity checking, not encryption, trusted time, or non-repudiation. Model performance depends on sample quality, evaluation splits, camera, lighting, and thresholds.

## Controls and privacy boundaries

- No cloud upload and no raw-video storage.
- Minimize stored features and provide profile deletion.
- Never collect passwords, cookies, messages, form data, or page content.
- Limit monitoring to user-configured domains.
- Bind service to loopback and validate local requests.
- Keep secrets/biometric data out of Git; apply restrictive local file permissions where possible.
- Explain lockout and recovery; do not present visual biometrics as perfect or sufficient alone.

SecureAir is an educational/research prototype, not a production identity system.
