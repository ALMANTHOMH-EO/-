# Security baseline — ALMANTHOMH EO CN v1.0

- No GitHub token, API secret, private key, or user password belongs in this repository.
- The public web interface is a static frontend. It does not implement shared accounts, reservations, developer bans, remote device control, or encrypted per-slot storage.
- Remote screen access must require explicit, visible consent on the Android device for each capture session and an obvious stop control.
- Never request broad file access as a substitute for scoped file selection.
- Do not collect or persist a user's IP address unless a documented security need and retention period exist. Minimize and redact logs.
- Use HTTPS/TLS for all production traffic. Use a managed key service for backend encryption keys; never store keys in GitHub Pages files.
- A developer role may administer accounts and revoke sessions but must not expose private phone content.
- Rate-limit login, pairing, token issuance, and recovery endpoints. Store password hashes using a modern password-hashing function, not plaintext or reversible encryption.
- Do not treat display name, age, or an unverified phone number as proof of identity.
