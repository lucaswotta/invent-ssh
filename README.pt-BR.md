# Invent-SSH

Coletor de inventário de hardware Linux via SSH sem agente, com interface desktop/web local, histórico de snapshots em SQLite e exportação em `.xlsx`, `.csv` e `.html`.

Language: [English](README.md)

## Requisitos

- Python `3.11` ou superior
- Sistemas de destino Linux com SSH ativo (porta `22`)
- Pacotes Python de execução (`requirements.txt`):
  - `openpyxl>=3.1.0,<4.0.0`
  - `paramiko>=3.3.0,<5.0.0`
- Backends opcionais para janela nativa: `pywebview` ou `PyGObject` (`Gtk 3.0` + `WebKit2 4.1`); na ausência de ambos, abre no navegador padrão do sistema. No modo navegador, o processo encerra cerca de 3 minutos depois que a aba é fechada. Os executáveis empacotados não incluem nenhum dos dois e sempre usam o navegador.

## Instalação

```bash
git clone https://github.com/lucaswotta/invent-ssh.git
cd invent-ssh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Uso

### Interface Desktop / Web

```bash
python3 app.py
```

Para executar apenas o servidor HTTP local sem abrir janela:

```bash
python3 app.py --no-window --port 8765
```

A interface opera em três visões (`100vw` por `100vh`):

- `Coleta`: seleção de planilha de alvos, popover de credenciais SSH, filtro segmentado (`Todas`, `Online`, `Offline`, `Falha SSH`), tabela em tempo real e painel lateral de inspeção de hardware.
- `Parque`: gráficos neutros de distribuição (`Armazenamento por Tipo`, `Capacidade de Memória RAM`, `Distribuições Linux`) e tabela consolidada por `Unidade / Local`.
- `Snapshots`: histórico local em SQLite das coletas concluídas e comparação campo a campo entre execuções.

### Linha de Comando

```bash
python3 app.py --input alvos.xlsx --user inv-reader --key ~/.ssh/id_ed25519 --output-format XLSX
```

## Configuração

A lista de alvos aceita arquivos `.xlsx`, `.xlsm` ou `.csv` com uma coluna de endereço (`IP`, `HOST`, `HOSTNAME`, `ADDRESS`, `IP_ADDRESS`, `ENDPOINT` ou `TARGET`). Colunas adicionais (`LOCATION`, `ASSET_TAG`, `OWNER`, `NOTES`) são preservadas na interface e nos relatórios exportados.

Os caminhos de dados seguem as convenções do sistema operacional em `paths.py`:

- Configuração: `~/.config/invent-ssh/config.json` no Linux (`%APPDATA%\Invent-SSH` no Windows, `~/Library/Application Support/Invent-SSH` no macOS).
- Snapshots e chaves TOFU: `~/.local/share/invent-ssh/snapshots.db` e `~/.local/share/invent-ssh/known_hosts`.
- Relatórios exportados: `~/Documents/Invent-SSH Reports/`.

Relatórios só são gravados ao usar `Exportar` ou a linha de comando. As chaves de host SSH usam confiança no primeiro uso (TOFU) por padrão; veja [SECURITY.md](SECURITY.md).

Senhas SSH permanecem apenas em memória durante a sessão ativa e nunca são gravadas em `config.json`.

## Limitações

- Os alvos devem ser máquinas Linux acessíveis por SSH na porta `22`; destinos Windows e macOS não são suportados pelo coletor.
- A interface é em português; relatórios exportados e mensagens de log seguem o idioma do sistema (`pt-br` ou `en`).
- A coleta é somente de leitura e executa um único script POSIX por host (`inspector.py`). Campos que exigem privilégios elevados (`dmidecode`, número de série) ou utilitários ausentes (`lscpu`, `lsblk`, `lspci`) retornam `N/A`.
- A classificação de armazenamento (`NVMe`, `SSD / flash`, `HDD`) utiliza o barramento e o indicador de rotação do kernel Linux (`ROTA`), que pode classificar discos virtuais como mídia não rotativa.

## Licença

MIT. Consulte [LICENSE](LICENSE).
