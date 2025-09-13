<div align="center"><img src="app.ico" alt="invent-ssh icon" width="128"></div> 

# invent-ssh

**Inventário de Hardware Linux via SSH**

---

Uma ferramenta open source para automatizar a coleta de informações de hardware em sistemas Linux através de conexões SSH. Desenvolvida para resolver problemas reais de visibilidade de infraestrutura em ambientes distribuídos.

![Demo do invent-ssh](https://i.imgur.com/Bba4sRb.gif)

[![GitHub Release](https://img.shields.io/github/v/release/lucaswotta/invent-ssh?include_prereleases&label=versão&color=5cb85c)](https://github.com/lucaswotta/invent-ssh/releases)
[![License: MIT](https://img.shields.io/badge/Licença-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://python.org)

---

## O Problema

"Precisamos fazer o upgrade das máquinas... mas qual é o hardware atual? Qual upgrade é mais necessário? Trocar o HDD por SSD? Aumentar a RAM? Ou substituir a máquina inteira?"

A falta de visibilidade sobre o hardware instalado em terminais Linux distribuídos era um problema comum. Esta ferramenta nasceu dessa necessidade real: um script interno que evoluiu para uma solução completa quando outros profissionais enfrentavam o mesmo ponto cego na infraestrutura.

---

## Como Funciona

### Coleta Inteligente
- **Estratégia Híbrida**: Usa `inxi` como fonte primária, com fallback para `dmidecode`, `lscpu` e comandos nativos do Linux
- **100% Somente Leitura**: Zero modificações no sistema alvo
- **Detecção Automática**: Identifica as melhores ferramentas disponíveis em cada sistema

### Performance
- **Processamento Paralelo**: Coleta dados de dezenas de máquinas simultaneamente
- **Timeouts Configuráveis**: Otimização para diferentes condições de rede
- **Escalabilidade**: Validado em ambientes com 500+ endpoints

### Segurança
- **Credenciais Temporárias**: Nunca persistidas em disco
- **Suporte SSH Keys**: Autenticação padrão da indústria
- **Logs Detalhados**: Auditoria completa de operações

---

## Início Rápido

### Windows
1. Baixe o executável em [Releases](https://github.com/lucaswotta/invent-ssh/releases)
2. Execute o arquivo `.exe` - sem instalação necessária
3. Siga o guia da interface gráfica

### Linux/macOS
```bash
git clone https://github.com/lucaswotta/invent-ssh.git
cd invent-ssh

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
python app.py
```

**Requisito**: Python 3.8+

---

## Dados Coletados

| Componente | Informações |
|------------|------------|
| **Sistema** | Distribuição, kernel |
| **Placa-mãe** | Fabricante, modelo |
| **Processador** | Modelo, cores físicos/lógicos, frequência |
| **Memória** | Capacidade total, tipo (DDR5/4/3) |
| **Armazenamento** | Tipo (NVMe/SSD/HDD), capacidade |

### Exemplo de Saída
```
IP: 10.1.3.20
NROEMPRESA: 100
NROCHECKOUT: 20
STATUS: ONLINE
PLACA_MAE: PCWARE - IPX4120G
PROCESSADOR: Intel(R) Celeron(R) N4120 CPU @ 1.10GHz
CORES_THREADS: 4/4
RAM: 8GB DDR4
TIPO_DISCO: NVMe
TAMANHO_DISCO: 128GB
DISTRO: Ubuntu 18.04.3 LTS
KERNEL: 5.3
DTAATUALIZACAO: 2025-09-13 01:45:08
```

---

## Configurações

### Otimização
- **Conexões Paralelas**: 1-50 simultâneas (padrão: 15)
- **Timeout SSH**: 5-120 segundos (padrão: 30)

### Fontes de Dados
- **Planilhas**: Excel (.xlsx) ou CSV
- **Oracle Database**: Query personalizada para descoberta de ativos

### Saída
- **Planilhas**: XLSX ou CSV para relatórios
- **Banco Oracle**: Inserção direta em tabelas corporativas

---

## Estrutura

```
invent-ssh/
├── app.py           # Interface gráfica (CustomTkinter)
├── core.py          # Lógica de negócio  
├── inspector.py     # Coleta e parsing do hardware
├── build.py         # Script de empacotamento (.exe)
├── requirements.txt # Dependências
├── app.ico
├── LICENSE
└── README.md
```

### Fluxo de Processamento
1. **Carregamento**: Lê lista de IPs (planilha ou Oracle)
2. **Conexão**: Estabelece pool de conexões SSH
3. **Coleta**: Executa comandos de hardware em paralelo
4. **Parsing**: Normaliza dados para formato padrão
5. **Saída**: Gera relatório ou insere no banco

---

## Segurança

### Práticas Recomendadas
- Use autenticação por chaves SSH sempre que possível
- Execute apenas em redes controladas e confiáveis
- Aplique o princípio do menor privilégio para contas de acesso

### Garantias
- Não instala ou modifica software nas máquinas alvo
- Não armazena credenciais permanentemente
- Não executa comandos de escrita ou configuração

---

## Stack

| Componente | Tecnologia |
|------------|------------|
| **Interface** | CustomTkinter |
| **SSH** | Paramiko |
| **Dados** | Pandas |
| **Database** | oracledb |
| **Build** | PyInstaller |

---

## Contribuição

1. Abra uma Issue descrevendo sua ideia
2. Fork o projeto e crie uma branch
3. Implemente suas mudanças
4. Teste em ambiente real
5. Submeta um Pull Request

---

## Licença

MIT License - use, modifique e distribua livremente.

---

**Lucas Motta**  
[GitHub](https://github.com/lucaswotta) • [LinkedIn](https://www.linkedin.com/in/lucaswotta)