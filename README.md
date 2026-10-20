# Invent-SSH

Agentless Linux hardware inventory over SSH with a local desktop/web workspace, SQLite snapshot history, and `.xlsx`, `.csv`, and `.html` exports.

Idioma: [Português (Brasil)](README.pt-BR.md)

## Requirements

- Python `3.11` or newer
- Target systems running Linux with SSH enabled (port `22`)
- Runtime Python packages (`requirements.txt`):
  - `openpyxl>=3.1.0,<4.0.0`
  - `paramiko>=3.3.0,<5.0.0`
- Optional desktop window backends: `pywebview` or `PyGObject` (`Gtk 3.0` + `WebKit2 4.1`); falls back to the system web browser when neither is installed. In browser mode the process exits about 3 minutes after the tab is closed. Packaged builds include neither backend and always use the browser.

## Installation

```bash
git clone https://github.com/lucaswotta/invent-ssh.git
cd invent-ssh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Usage

### Desktop / Web Interface

```bash
python3 app.py
```

Run only the local HTTP server without opening a window:

```bash
python3 app.py --no-window --port 8765
```

The interface provides three views occupying `100vw` by `100vh`:

- `Coleta`: target file selection, SSH credentials popover, segmented status filter (`Todas`, `Online`, `Offline`, `Falha SSH`), live inventory table, and hardware inspector panel.
- `Parque`: neutral hardware distribution charts (`Armazenamento por Tipo`, `Capacidade de Memória RAM`, `Distribuições Linux`) and location breakdown (`Unidade / Local`).
- `Snapshots`: local SQLite history of completed runs and field-by-field hardware comparison between snapshots.

### Command Line

```bash
python3 app.py --input targets.xlsx --user inv-reader --key ~/.ssh/id_ed25519 --output-format XLSX
```

## Configuration

Target files accept `.xlsx`, `.xlsm`, or `.csv` containing one address column (`IP`, `HOST`, `HOSTNAME`, `ADDRESS`, `IP_ADDRESS`, `ENDPOINT`, or `TARGET`). Additional columns (`LOCATION`, `ASSET_TAG`, `OWNER`, `NOTES`) are preserved in the workspace and in exported reports.

User paths follow platform conventions via `paths.py`:

- Configuration: `~/.config/invent-ssh/config.json` on Linux (`%APPDATA%\Invent-SSH` on Windows, `~/Library/Application Support/Invent-SSH` on macOS).
- Snapshots and TOFU host keys: `~/.local/share/invent-ssh/snapshots.db` and `~/.local/share/invent-ssh/known_hosts`.
- Exported reports: `~/Documents/Invent-SSH Reports/`.

Reports are written only when you choose `Exportar` or run the command line. SSH host keys use trust on first use by default; see [SECURITY.md](SECURITY.md).

SSH passwords are kept only in memory for the active session and are never written to `config.json`.

## Limitations

- Targets must be Linux systems accessible over SSH on port `22`; Windows and macOS endpoints are not collected.
- The interface is in Portuguese; exported reports and log messages follow the system language (`pt-br` or `en`).
- Hardware collection is read-only and executes a single POSIX shell probe per target (`inspector.py`). Fields that require root privileges (`dmidecode`, serial numbers) or optional utilities (`lscpu`, `lsblk`, `lspci`) are reported as `N/A` when unavailable or unpermitted.
- Storage classification (`NVMe`, `SSD / flash`, `HDD`) relies on transport names and the Linux kernel rotational flag (`ROTA`), which can report virtual disks as non-rotating media.

## License

MIT. See [LICENSE](LICENSE).
