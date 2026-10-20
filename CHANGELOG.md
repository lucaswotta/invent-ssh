# Changelog

Notable changes to Invent-SSH are recorded here.

## [Unreleased]

### Added

- First-run guide in three steps, a `Como usar` sheet with the spreadsheet format, collected data, status meanings and folders, and `Abrir pasta`/`Abrir` buttons after exports.
- Drag and drop of the target spreadsheet onto the window.
- System details in the inspector and reports: OS version and codename, desktop and display server, connected displays, package count, init, time zone, root filesystem usage, IPv4 and MAC per adapter.
- Every memory slot with locator, size, type, speed and part number, total slots and maximum capacity.
- Collection time per machine in the table and the inspector.
- Responsive layout down to 600 px wide; the window minimum is 720x520 and it opens maximized on smaller screens.
- Excel export with the logo, indicator cards, storage/memory/distribution/location tables with data bars, grouped and colored inventory columns, real dates and numeric coverage.
- After loading targets, the app lists rows without an address and repeated addresses, and opens the SSH panel when access is missing.

### Changed

- Reports and the template go to `Invent-SSH` in the localized Documents folder (`~/Documentos/Invent-SSH` on pt-BR Linux).
- Offline hosts state the cause: connection refused, no answer on the network, time limit, or DNS failure, instead of "Timeout" for all.
- The inspector shows only the diagnosis for hosts that were not collected.

### Fixed

- Alvos, SSH and Exportar did not open in browsers with the Popover API: the inline `togglePopover()` call resolved to the native element method.
- The probe parser dropped sections whose name has a digit (`ipv4`).
- A repeated address in the spreadsheet left one row in `PENDING` after the scan.
- The log claimed a report was saved after each scan and recorded every host's full record.

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
