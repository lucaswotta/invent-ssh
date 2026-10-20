# Changelog

Notable changes to Invent-SSH are recorded here.

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
