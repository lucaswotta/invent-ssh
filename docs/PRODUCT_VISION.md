# Product vision

## Positioning

**Invent-SSH — Linux hardware inventory at scale.**

Invent-SSH turns a list of authorized Linux SSH targets into structured hardware data and portable reports. Its public value is not a company-specific connector; it is the bridge between scattered machines and decisions about upgrades, capacity, lifecycle, and fleet visibility.

## Product principles

1. **Bring your own asset list.** CSV and Excel are a portable contract, not a dependency on a particular CMDB, database, or retail-management platform.
2. **Reports are a product feature.** Exports must be clear enough for technical teams and leaders, yet structured for further analysis.
3. **Scale without surprise.** Bound in-flight work, make progress visible, keep results from failed endpoints, and expose cancellation and timeouts.
4. **Be read-only on targets.** Collect via ordinary Linux utilities and SSH; do not install agents or mutate host configuration.
5. **Make security choices explicit.** Verify SSH host keys by default; any lower-assurance compatibility mode must be opted into and explained.
6. **No invented certainty.** Preserve unknown/missing values and indicate per-host failures.
7. **Quality ships with the binary.** Tests, reproducible builds, release notes, security guidance, and privacy-conscious defaults are part of the product.

## Target users

- Infrastructure engineers managing distributed Linux workstations, terminals, servers, or appliances.
- MSPs and operations teams conducting authorized hardware discovery.
- IT asset and lifecycle teams planning RAM/storage refreshes and system retirement.
- Consultants who need a portable inventory deliverable without requiring clients to adopt a database.

## Current scope

- Linux-target hardware inspection through SSH.
- CSV and Excel target lists with a required endpoint column and optional user-defined metadata.
- Bounded parallel collection and per-host outcomes.
- XLSX, CSV, and portable HTML reports generated locally.
- Resizable desktop GUI for Windows, macOS and Linux, plus native OS-specific packages built with PyInstaller.

## Explicit non-goals for this phase

- A database-backed asset platform or enforced SaaS account.
- Unattended exploitation, password spraying, or privilege escalation.
- A target-side agent or automatic configuration management.
- Claiming universal hardware coverage across every Linux distribution and permission level.

## Roadmap

### P1 — Reliable public release

- Report tests, input validation, quality workflow, and cross-platform packaging.
- Clear SSH host identity policy and credential handling.
- Generic docs, contribution/security policy, and anonymized examples.
- Performance and cancellation verification at large input counts.

### P2 — Better insight per scan

- Compare two snapshots and show added, removed, and changed endpoints.
- Upgrade findings based on transparent rules (e.g. HDD discovery), never opaque scores.
- JSON export and a stable machine-readable schema.
- Optional per-run manifests, checksums, and audit summaries.

### P3 — Extensible fleet discovery

- Additional opt-in source adapters (DNS, subnet import, API/CMDB connectors).
- Pluggable collectors and hardware fields.
- CLI/headless runner and automation-friendly exit codes.
- Optional persistence only where it demonstrably improves the user's workflow.

## Branding direction

Keep the technical name **Invent-SSH** and use the bespoke penguin mascot, midnight navy and signal-yellow identity. The UI should feel like a deliberate infrastructure product: high-contrast data, stable side navigation, one obvious primary action and a window that uses the available viewport. Avoid generic gradients, decorative green palettes and claims of OS/agent coverage beyond the Linux-over-SSH collector. Any future name change should follow GitHub/package-name and trademark-conflict checks.

## What excellence means

- A teammate can create a useful report from an input file without a database or spreadsheet cleanup.
- A large scan never launches an unbounded number of concurrent connection tasks.
- Every machine gets an understandable outcome, including failures.
- HTML works offline and never treats inventory values as markup or script.
- CI catches regressions before a release.
- Public docs accurately describe limitations, trade-offs, and supported platforms.
