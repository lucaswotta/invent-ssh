# Contributing

Thanks for helping improve Invenux. Contributions should keep it portable, safe by default, and useful without a database service.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python -m compileall -q app.py core.py inspector.py reporting.py snapshots.py i18n.py paths.py build.py tests
python build.py --console
```

Windows PowerShell uses `.venv\\Scripts\\Activate.ps1` for activation.

## Guidelines

- Open an issue first for major product, architecture, or compatibility changes.
- Keep the GUI, inventory orchestration, SSH collector, and report rendering in separate layers.
- Add tests when changing input handling, host status semantics, report formats, or security-sensitive behavior.
- Keep examples anonymized. Never commit credentials, customer hostnames/IP ranges, output reports, private logs, or local configuration.
- Document security trade-offs and keep strict verification as the default.
- Do not add a database or vendor connector unless it is optional and the user benefit is clear.

## Pull requests

Describe the problem and intended behavior, tests run, operating systems tested, and known limitations. Avoid combining large refactors with unrelated styling changes.
