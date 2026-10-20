# Architecture overview

## Data flow

```text
CSV / XLSX target list
        |
        v
core.py — normalize columns, preserve asset metadata
        |
        v
Bounded ThreadPoolExecutor
        |
        +---- inspector.py — SSH + Linux hardware collection
        |
        v
Normalized per-host Terminal records
        |
        v
reporting.py — XLSX / CSV / self-contained HTML
        |
        v
User Documents / Invent-SSH Reports
```

## Responsibilities

- **app.py** — CustomTkinter desktop interface, SSH credentials, scan configuration, progress/log modal, and configuration persistence.
- **core.py** — Input contract, per-host record model, bounded concurrency, cancellation, circuit breaker, and report coordination.
- **inspector.py** — SSH lifecycle and a bounded, read-only POSIX-shell probe. Reads kernel interfaces and optional tools including `lscpu`, `lsblk`, `dmidecode`, `lspci`, `ip`, sysfs and `systemd-detect-virt`; missing optional tools reduce detail, not connectivity status.
- **reporting.py** — Builds XLSX/CSV/HTML without GUI or database dependencies.
- **i18n.py** — User-facing strings in Brazilian Portuguese and English; first-run locale follows the OS when supported.
- **build.py** — Native PyInstaller package build for the OS on which it runs; it never deletes unrelated outputs or installs system packages.
- **tests/** — Regression checks for export escaping and report structure, with engine tests to grow alongside the input contract.

## Record contract

Each row keeps the endpoint (`ip`), arbitrary input metadata (`metadata`), outcome (`status`), hardware fields, optional error detail, and collection timestamp. Extra asset columns survive the scan even if the collector does not understand their semantics.

The UI should not own collection rules. Keep normalization and scan orchestration in `core.py`; keep format rendering in `reporting.py`.

## Large input lists

Only at most `max_workers` tasks are in flight. The engine fills its worker window as futures complete instead of scheduling every machine at once. Cancellation stops submitting new targets and cancels tasks that have not started; active SSH calls follow their connection and command timeouts.

The input list and final records remain in memory. For exceptionally large fleets, streaming/chunked input and incremental persistence are future work, not a claim of unbounded scale.

## Security boundaries

- Host-key verification is strict by default against the local SSH known-hosts database.
- `trust_unknown_hosts` is an explicit, lower-assurance compatibility choice.
- CSV/XLSX values that could be interpreted as spreadsheet formulas are prefixed before writing.
- HTML output escapes user-controlled fields.
- No target-side service or database is required.
- Reports are local sensitive outputs; users decide where to store and share them.

## Hardware collection contract

One bounded read-only SSH command returns named sections. A section parser separates command output from hardware-specific parsers, so collection is not tied to a single Linux distribution or exact utility output order. Primary sources are `/etc/os-release`, `uname`, `lscpu`/`/proc/cpuinfo`, `/proc/meminfo`, `lsblk` JSON (with a quoted key/value fallback), sysfs DMI, optional `dmidecode`/`lspci`, network sysfs and `/proc/uptime`.

Core-field coverage counts required facts actually detected. Optional facts such as module speed, GPU model or NIC driver are listed as unavailable rather than inferred. Storage labels expose their classification basis: the kernel rotational flag can classify virtual or flash media as non-rotating, so it does not prove a physical SSD.
