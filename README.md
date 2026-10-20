<div align="center">

<img src="app.ico" alt="" width="96">

# invent-ssh

**Inventário de hardware de terminais Linux via SSH, com interface gráfica.**

Coleta em paralelo, somente leitura, a partir de uma planilha ou de uma consulta ao Oracle.

[Baixar (Windows)](https://github.com/lucaswotta/invent-ssh/releases) ·
[Como funciona](#como-funciona) ·
[Uso](#uso) ·
[Segurança](#segurança)

<br>

![Demonstração do invent-ssh](https://i.imgur.com/Bba4sRb.gif)

</div>

## Problema

Planejar o upgrade de uma frota de terminais Linux exige saber o que existe em cada máquina: trocar HDD por SSD, aumentar a RAM ou substituir o equipamento. Sem inventário, a decisão é no escuro. O invent-ssh nasceu como script interno e virou uma ferramenta completa. Foi validado com mais de 500 terminais.

## Como funciona

1. Lê a lista de IPs de uma planilha (`.xlsx` ou `.csv`) ou de uma consulta ao Oracle.
2. Abre um pool de conexões SSH e coleta os dados em paralelo.
3. Usa `inxi` como fonte principal, com fallback para `dmidecode`, `lscpu` e comandos nativos, conforme o que existir em cada máquina.
4. Normaliza os dados e grava em planilha (`.xlsx` ou `.csv`) ou direto em uma tabela Oracle.

## Dados coletados

| Componente | Informações |
|---|---|
| Sistema | Distribuição e kernel |
| Placa-mãe | Fabricante e modelo |
| Processador | Modelo, núcleos físicos e lógicos, frequência |
| Memória | Capacidade total e tipo (DDR3, DDR4, DDR5) |
| Armazenamento | Tipo (NVMe, SSD, HDD) e capacidade |

Exemplo de saída, com valores ilustrativos:

```
IP: 192.168.0.20
STATUS: ONLINE
PLACA_MAE: Fabricante - Modelo
PROCESSADOR: Intel(R) Celeron(R) N4120 CPU @ 1.10GHz
CORES_THREADS: 4/4
RAM: 8GB DDR4
TIPO_DISCO: NVMe
TAMANHO_DISCO: 128GB
DISTRO: Ubuntu 18.04.3 LTS
KERNEL: 5.3
```

## Uso

**Windows:** baixe o `.exe` em [Releases](https://github.com/lucaswotta/invent-ssh/releases) e execute. Não precisa instalar.

**Linux e macOS** (Python 3.8 ou superior):

```bash
git clone https://github.com/lucaswotta/invent-ssh.git
cd invent-ssh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Configuração

| Opção | Faixa | Padrão |
|---|---|---|
| Conexões paralelas | 1 a 50 | 15 |
| Timeout SSH | 5 a 120 s | 30 s |
| Idioma | Português (Brasil) ou English | Português (Brasil) |

A troca de idioma exige reiniciar o aplicativo.

## Segurança

- Somente leitura: não instala nem altera nada nas máquinas de destino.
- Credenciais informadas na sessão e nunca gravadas em disco. Aceita chave SSH.
- No modo Oracle, valida que a consulta de busca é um `SELECT` e que a tabela de destino é um identificador válido antes de executar qualquer SQL.

## Estrutura

```
app.py         interface gráfica (CustomTkinter)
core.py        orquestração e regras de negócio
inspector.py   coleta e parsing do hardware
i18n.py        textos em pt-BR e inglês
build.py       empacotamento do .exe
```

Stack: CustomTkinter, Paramiko, Pandas, oracledb, PyInstaller.

## Licença

MIT. Veja [LICENSE](LICENSE).
