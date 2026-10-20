# Security policy

## Reporting a vulnerability

Do not publish host inventories, private keys, credentials, internal addresses, or unredacted crash/log files in public issues.

For a suspected vulnerability, contact the maintainer privately through the contact details on the maintainer's GitHub profile. Include the affected version and OS, impact, safe reproduction steps, and a mitigation suggestion if known. Allow time to investigate before publishing details that could put users at risk.

## Current security model

- Collection is intended only for Linux endpoints the operator owns or is authorized to assess.
- Hardware collection is designed to be read-only; it uses SSH and system-information commands.
- SSH host keys use trust on first use (`trust_unknown_hosts`, on by default): an unknown key is accepted once and stored in the app `known_hosts`; a later key change is rejected. The first connection to each host is not protected against machine-in-the-middle attacks. Turn the option off in the SSH panel to accept only keys already in `known_hosts`.
- The local interface listens only on `127.0.0.1`, requires a per-process token and rejects requests whose `Host` is not `127.0.0.1` or `localhost`.
- The SSH password is not saved by the application. The UI may remember the SSH username and private-key path in local configuration.
- Reports and logs may contain infrastructure identifiers and should be protected appropriately.
- Spreadsheet exports neutralize formula-like values; HTML exports escape target-provided and user-supplied fields.

## Limitations

Invenux is not a vulnerability scanner or hardware-attestation mechanism. Results depend on the target OS, available tools, and permissions. A successful SSH connection is not proof of asset identity beyond the SSH key trust model.
