# Security policy

## Reporting a vulnerability

Do not publish host inventories, private keys, credentials, internal addresses, or unredacted crash/log files in public issues.

For a suspected vulnerability, contact the maintainer privately through the contact details on the maintainer's GitHub profile. Include the affected version and OS, impact, safe reproduction steps, and a mitigation suggestion if known. Allow time to investigate before publishing details that could put users at risk.

## Current security model

- Collection is intended only for Linux endpoints the operator owns or is authorized to assess.
- Hardware collection is designed to be read-only; it uses SSH and system-information commands.
- SSH host-key verification is strict by default. The opt-in `trust_unknown_hosts` setting accepts unknown host keys and weakens resistance to machine-in-the-middle attacks.
- The SSH password is not saved by the application. The UI may remember the SSH username and private-key path in local configuration.
- Reports and logs may contain infrastructure identifiers and should be protected appropriately.
- Spreadsheet exports neutralize formula-like values; HTML exports escape target-provided and user-supplied fields.

## Limitations

Invent-SSH is not a vulnerability scanner or hardware-attestation mechanism. Results depend on the target OS, available tools, and permissions. A successful SSH connection is not proof of asset identity beyond the SSH key trust model.
