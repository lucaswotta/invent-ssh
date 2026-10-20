<div align="center">

<img src="brand/invent-ssh-mark-128.png" alt="Invent-SSH penguin mark" width="88">

# Invent-SSH

**Linux hardware inventory at scale.**

Collect hardware facts from Linux machines over SSH, then turn the results into useful reports — without an agent, a database, or a vendor-specific inventory system.

[Getting started](#getting-started) · [Reports](#reports) · [Security](#security) · [Roadmap](docs/PRODUCT_VISION.md)

[Português (Brasil)](README.pt-BR.md)

</div>

---

## Why Invent-SSH?

Infrastructure teams often inherit hundreds or thousands of machines with incomplete hardware records. Invent-SSH helps answer practical questions: which devices are online, what CPU and memory do they have, which systems still use HDDs, and where is an upgrade likely to have the most impact?

Its public contract is intentionally simple: **provide a list of authorized targets and receive a report you can inspect, filter, share, or process elsewhere.**

## What it collects

| Area | Examples |
| --- | --- |
| Operating system | Linux distribution and kernel |
| Processor | Model, physical cores / logical threads where available |
| Memory | Total capacity and memory type when available |
| Storage | Device type (NVMe, SSD, HDD) and capacity |
| Mainboard | Manufacturer and model when available |
| Reachability | Online, offline, authentication or SSH errors |
| Your asset context | Hostname, asset tag, location, owner, department, notes, and any extra input columns |

Actual fields depend on the target OS, installed utilities, and SSH account permissions. Missing data is reported as unavailable instead of being fabricated.

## Getting started

### 1. Prepare the target list

Create an Excel (.xlsx/.xlsm) or CSV (.csv) file with one column identifying the machine. Accepted column names:

`IP`, `HOST`, `HOSTNAME`, `ADDRESS`, `IP_ADDRESS`, `ENDPOINT`, or `TARGET`.

Other columns are preserved as asset metadata and added to the report. For example:

| IP | HOSTNAME | ASSET_TAG | LOCATION | OWNER |
| --- | --- | --- | --- | --- |
| 192.0.2.10 | lab-node-01 | ASSET-001 | Test Lab | Infrastructure |
| 192.0.2.11 | lab-node-02 | ASSET-002 | Remote Office | Operations |

The sample IPs above are documentation-only addresses. Use your own authorized targets.

### 2. Connect over SSH

- Use an account with the minimum permissions necessary to read the required hardware information.
- Prefer SSH keys to passwords.
- By default, Invent-SSH checks host keys against your local SSH known-hosts database. Unknown hosts are rejected. Enroll expected keys before a scan whenever practical.
- A compatibility option can trust unknown host keys. It is **less secure** and should only be enabled intentionally on a trusted network; it weakens protection against machine-in-the-middle attacks.

### 3. Run the inventory

**Windows:** use a compatible package from [GitHub Releases](https://github.com/lucaswotta/invent-ssh/releases) when one is published, or build natively from source.

**Linux / macOS:** Python 3.11+ is recommended. The desktop interface requires Tcl/Tk support in the selected Python installation.

On Debian/Ubuntu, install the matching system Tk module before creating the virtual environment:

```bash
sudo apt install python3-tk
```

On Fedora, use `sudo dnf install python3-tkinter`. On macOS, use a Python distribution that includes Tcl/Tk.

```bash
git clone https://github.com/lucaswotta/invent-ssh.git
cd invent-ssh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1` instead of the Unix `source` command.

## Reports

Choose the format that suits the next step:

- **Excel (.xlsx)** — executive overview and inventory sheet with filters, frozen headings, readable widths, status styling, and print-friendly page setup.
- **HTML (.html)** — one self-contained report with summary metrics, a searchable and filterable inventory table, responsive styling, and no server or external assets required.
- **CSV (.csv)** — UTF-8 with BOM and semicolon-delimited fields for spreadsheet compatibility and data exchange.

Reports are saved locally in your Documents folder under `Invent-SSH Reports`. The path is independent of the working directory. Treat them as infrastructure data: they can include hostnames, addresses, device identifiers, and ownership/location metadata.

## Scale and operating model

- Concurrent SSH connections are bounded by the configured worker count. The engine does not create one pending task per target up front, reducing memory overhead for large input lists.
- Each endpoint produces an individual status, so one unreachable host does not erase the rest of the inventory.
- Tune concurrency and timeouts for your workstation, network, and targets. More workers are not always faster.
- The collector is designed for Linux targets and read-only inspection. It does not install an agent or configure the target.

## Security

- Run inventories only against systems you own or are explicitly authorized to assess.
- SSH credentials are supplied for the session. The application does not persist the SSH password; it may remember the username and private-key **path** in the local UI configuration. The key file itself is never copied into the application configuration.
- Keep reports and logs out of public issue attachments unless sanitized. They may contain infrastructure identifiers and error messages.
- Unknown-host trust is disabled by default; the opt-in compatibility setting weakens SSH host identity verification.
- This tool is an inventory aid, not a guarantee of hardware attestation or a security scanner.

See [SECURITY.md](SECURITY.md) for security reporting and current limitations.

## Visual identity and responsive desktop

The interface uses a custom penguin mark, midnight navy surfaces and signal-yellow primary actions. The main window opens maximized and remains resizable; content panels reflow where needed and long inventory views stay scrollable. Exported reports use the same identity, with an embedded logo in offline HTML and Excel reports.

The first launch inherits a supported operating-system locale (Brazilian Portuguese or English). A language preference explicitly saved in the application takes precedence on later launches.

## Build from source

Builds are native to the operating system being used; PyInstaller does not cross-compile Windows, macOS and Linux packages from a single host.

```bash
python -m pip install -r requirements-build.txt
python build.py
```

The package is placed under `dist/`; intermediate files are isolated under `build/`. Use `python build.py --console` for diagnostic builds.

## Project quality

The test suite covers Linux hardware parsers, SSH policy, bounded collection, path/config migration, locale resolution, report escaping and responsive-card layout. GitHub Actions runs tests across Windows, macOS and Linux and builds a native package on each OS.

- [Product vision and roadmap](docs/PRODUCT_VISION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).
