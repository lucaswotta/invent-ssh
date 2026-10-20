# Changelog

Notable changes to Invent-SSH are recorded here.

## [0.5.0] — 2026-10-20

### Changed

- Replaced the Tk desktop UI with a local web interface (`ui/index.html`) served by `app.py` on `127.0.0.1` and shown in `pywebview`, GTK WebKit2 or the default browser.
- Replaced the mascot with a geometric mark and a dark macOS-style palette.
- Reports are written only through Exportar or the CLI; a scan no longer saves an XLSX by itself.
- SSH host keys use TOFU by default: unknown keys are stored in the app `known_hosts` and a changed key is rejected.

### Added

- SQLite snapshot history with field-by-field comparison and CSV export of the changes.
- Fleet view with storage, memory and distribution breakdowns per location.

### Fixed

- XLSX export failed without Pillow (`ImportError`) because of the embedded logo.
- Parallel workers overwrote each other's TOFU entries in `known_hosts`.
- CPU lists such as `0-3,8` counted a single CPU as its index.
- The local server accepted any `Host` header, so a DNS-rebinding page could read the session token.
- In browser mode the server kept running after the tab closed; it now stops after 180 s without requests.
- SQLite connections were never closed.

## [0.4.0] — 2026-10-19

### Changed

- Repositioned the application around public, company-neutral Linux hardware inventory.
- Introduced a custom penguin mark, dark navy desktop shell, yellow primary actions, persistent side navigation, maximized-by-default and resizable windows, and responsive home cards.
- Removed the mandatory database integration and company-specific input/output paths.
- Accepted generic target-column aliases and preserved arbitrary asset metadata from input spreadsheets.
- Split report generation into a dedicated module.

### Added

- Rebranded XLSX reports with embedded product mark, an executive overview, native filters, and a custom midnight-navy/signal-yellow palette.
- Self-contained HTML reports with embedded logo, localized status badges/footer, summary metrics, search, and status filtering.
- CSV formula-injection mitigation and HTML escaping tests.
- Strict SSH host-key validation by default with an explicit, warned compatibility option.
- Bounded in-flight scheduling for large target lists.
- Product vision, architecture, security, contribution, and localized README documentation.

- Added OS-locale fallback on first launch while preserving an explicitly saved language preference.
- Added Linux system-detail collection for CPU topology, RAM availability/modules, each disk and partition, GPU, NIC details, firmware, uptime, virtualization, and collection provenance.
- Reduced per-machine discovery to one bounded read-only SSH command and made core-field coverage honest about missing facts.
- Documented the actual Linux collection sources and the limits of each hardware classification.
- Added native package builds and CI artifacts for Windows, macOS and Linux, alongside a cross-platform test matrix.
