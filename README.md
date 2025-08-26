# PDV Hardware Inspector

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Projetado para escanear informações de hardware de sistemas Linux via SSH, coletando dados detalhados sobre componentes. O aplicativo conecta-se a múltiplas máquinas em paralelo, processa os dados e gera um relatório completo em uma planilha de retorno.

O **PDV Hardware Inspector** é uma ferramenta projetada para automatizar o inventário de hardware de terminais de Ponto de Venda (PDV) baseados em Linux.

A aplicação se conecta a um banco de dados Oracle para obter uma lista de PDVs ativos, acessa cada terminal remotamente via SSH para realizar uma inspeção detalhada do hardware e, por fim, armazena os dados coletados de volta no Oracle, mantendo um inventário centralizado e sempre atualizado.

## Funcionalidades

-   **Integração com Banco de Dados Oracle**: Utiliza uma base Oracle como fonte para a lista de PDVs e como destino para os dados coletados.
-   **Coleta Remota e Paralela**: Acessa múltiplos PDVs simultaneamente via SSH, otimizando o tempo de execução.
-   **Detecção Detalhada de Hardware**: Coleta informações sobre:
    -   Placa-mãe (fabricante e modelo)
    -   Processador (modelo e contagem de núcleos/threads)
    -   Memória RAM (capacidade e tipo: DDR3/DDR4/DDR5)
    -   Armazenamento (tipo: SSD/HD e capacidade total)
    -   Versão do Kernel Linux
-   **Configuração Centralizada**: Todas as credenciais e parâmetros operacionais são gerenciados em um arquivo `.env`.
-   **Modo de Exportação CSV**: Oferece uma alternativa para salvar os dados em um arquivo `.csv` caso a integração com o banco não seja possível ou desejada.
-   **Resiliência e Fallbacks**: Emprega múltiplos comandos de detecção para cada componente de hardware e um sistema de novas tentativas (`retries`) para conexões instáveis.

---

## Instalação e Configuração

Siga os passos abaixo para preparar o ambiente e executar o projeto.

### Pré-requisitos

1.  **Python 3.8+**: [Instalar Python](https://www.python.org/downloads/)
2.  **Oracle Instant Client**: A biblioteca `oracledb` necessita do client do Oracle. Faça o download no [site oficial](https://www.oracle.com/database/technologies/instant-client/downloads.html) e adicione o diretório ao `PATH` do seu sistema.
3.  **Acesso de Rede**: A máquina que executa o script precisa de acesso de rede ao banco de dados Oracle e aos PDVs (via porta SSH, padrão 22).

### Passos de Instalação

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/lucaswotta/pdv-hardware-inspector.git
    cd pdv-hardware-inspector
    ```

2.  **Instale as dependências a partir do `requirements.txt`:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure as variáveis de ambiente:**
    Crie um arquivo chamado `.env` na raiz do projeto e preencha-o com as informações do seu ambiente.

    **Arquivo `.env`:**
    ```ini
    # --- Credenciais do Banco de Dados Oracle ---
    ORACLE_USER=seu_usuario_oracle
    ORACLE_PASSWORD=sua_senha_oracle
    ORACLE_HOST=host.do.banco.oracle
    ORACLE_PORT=porta_do_servico_oracle
    ORACLE_SERVICE=nome_do_servico_oracle

    # --- Credenciais SSH para os PDVs ---
    SSH_USERNAME=usuario_ssh_nos_pdvs
    SSH_PASSWORD=senha_ssh_nos_pdvs

    # --- Configurações de Performance e Conexão ---
    CONNECTION_TIMEOUT=8      # Timeout (segundos) para estabelecer a conexão SSH
    COMMAND_TIMEOUT=10        # Timeout (segundos) para a execução de um comando remoto
    MAX_WORKERS=20            # Número máximo de PDVs a serem processados em paralelo
    MAX_RETRIES=2             # Tentativas de reconexão em caso de falha
    SAVE_INTERVAL=10          # Quantidade de resultados a acumular antes de salvar no banco/CSV
    ```

## Estrutura do Projeto

O repositório está organizado da seguinte forma:
````
pdv-hardware-inspector/
├── .env                  # Arquivo de configuração local com credenciais
├── .gitignore            # Arquivos e pastas a serem ignorados pelo Git
├── coletaPDV.py          # Módulo responsável pela coleta de hardware via SSH
├── hardwarePDV.log       # Arquivo de log
├── hardwarePDV.py        # Script principal que orquestra a execução
├── README.md             # Documentação do projeto
└── requirements.txt      # Lista de dependências Python para o projeto
````

---

## Como Usar

Com o arquivo `.env` corretamente configurado, execute o script principal:

```bash
python hardwarePDV.py
````

## Saída dos Dados

Os dados coletados são armazenados na tabela `CONSINCO.BAR_HARDWARE_PDV` no Oracle. A estrutura da tabela é a seguinte:

| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| **IP** | VARCHAR2(45) | Endereço IP do PDV na última verificação. |
| **NROEMPRESA** | NUMBER(5) | (Chave Primária) Número da empresa/loja. |
| **NROCHECKOUT** | NUMBER(5) | (Chave Primária) Número do checkout/PDV. |
| **SEGMENTO** | VARCHAR2(100) | Segmento de rede ou descrição do grupo de PDVs. |
| **OPERACAO** | VARCHAR2(50) | Modo de operação do PDV (ex: Venda, Pré-venda). |
| **PLACA_MAE** | VARCHAR2(255) | Fabricante e modelo da placa-mãe. |
| **PROCESSADOR** | VARCHAR2(255) | Modelo da CPU. |
| **CORES_THREADS** | VARCHAR2(50) | Formato "Núcleos Físicos / Total de Threads". |
| **RAM** | VARCHAR2(50) | Capacidade e tipo (ex: "8GB DDR4"). |
| **DISCO** | VARCHAR2(50) | Tipo de armazenamento principal (SSD ou HD). |
| **ARMAZENAMENTO** | VARCHAR2(50) | Capacidade total do disco principal. |
| **RELEASE** | VARCHAR2(100) | Versão do Kernel Linux. |
| **STATUS** | VARCHAR2(10) | Status da última coleta: `ONLINE`, `OFFLINE`, `Inativo`. |
| **DTAINCLUSAO** | DATE | Data em que os dados de hardware foram coletados pela primeira vez. |
| **DTAATUALIZACAO** | DATE | Data da última atualização de qualquer informação do PDV. |

---

## Solução de Problemas

-   **Erros de Conexão com Oracle**:
    -   Verifique se as credenciais, host, porta e service name no `.env` estão corretos.
    -   Confirme se o **Oracle Instant Client** está instalado e configurado no `PATH` do sistema.
    -   Verifique se não há firewalls bloqueando a conexão com o banco.

-   **Falhas de Conexão SSH**:
    -   Confirme que o usuário e senha SSH no `.env` estão corretos.
    -   Assegure que a rede permite a comunicação da máquina executora com os PDVs na porta 22.

-   **Campos de Hardware como "Não detectado"**:
    -   Algumas distribuições Linux muito antigas ou customizadas podem não ter os utilitários necessários instalados.

Para erros detalhados, sempre consulte o arquivo de log `hardwarePDV.log`.

## Autor

| ![Lucas Ribeiro](https://github.com/lucaswotta.png?size=120) |
| :---: |
| **Lucas Ribeiro** |
| [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/lucaswotta) |