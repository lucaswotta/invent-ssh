# PDV Hardware Inspector 🕵️‍♂️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Ferramenta de automação em Python para coletar e inventariar remotamente o hardware de terminais de Ponto de Venda (PDV) baseados em Linux. O script é flexível, operando tanto conectado a um banco de dados Oracle quanto de forma autônoma, lendo dados de uma planilha local.

---

## ✨ Funcionalidades Principais

-   **Dois Modos de Operação**:
    -   **Modo Oracle**: Conecta-se a um banco de dados Oracle para buscar a lista de PDVs e salvar os resultados.
    -   **Modo Planilha**: Funciona offline, lendo a lista de PDVs de um arquivo `lista_pdvs.xlsx` ou `.csv` e salvando um relatório em `resultado_hardware.xlsx` e `.csv`.

-   **Menu Interativo**: Ao iniciar, a aplicação pergunta qual modo de operação você deseja usar, sugerindo o padrão definido no arquivo `.env`.

-   **Coleta Remota e Paralela**: Acessa múltiplos PDVs simultaneamente via SSH para otimizar drasticamente o tempo de coleta.

-   **Execução Sequencial para Depuração**: Permite rodar a coleta um PDV por vez, facilitando a identificação de problemas em hosts específicos.

-   **Estabilidade e Resiliência**:
    -   **Timeout por PDV**: Cada tentativa de conexão tem um tempo limite, evitando que um único PDV offline trave toda a execução.
    -   **Fallbacks de Comandos**: Utiliza múltiplos comandos alternativos para detectar cada peça de hardware, aumentando a compatibilidade com diferentes sistemas Linux.

-   **Configuração Centralizada**: Todas as credenciais e parâmetros são gerenciados de forma simples através de um arquivo `.env`.

---

## 🔧 Instalação e Configuração

### Pré-requisitos

1.  **Python 3.8+**: [Instalar Python](https://www.python.org/downloads/)
2.  **Oracle Instant Client**: **(Apenas para o Modo Oracle)** A biblioteca `oracledb` necessita do client. Faça o download no [site oficial](https://www.oracle.com/database/technologies/instant-client/downloads.html).
3.  **Acesso de Rede**: A máquina que executa o script precisa de acesso de rede aos PDVs (via porta SSH, padrão 22).

### Passos de Instalação

1.  **Clone o repositório:**
    ```bash
    git clone https://github.com/lucaswotta/pdv-hardware-inspector.git
    cd pdv-hardware-inspector
    ```

2.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure o arquivo `.env`:**
    Crie um arquivo `.env` na raiz do projeto e preencha-o com as suas informações.

    **Arquivo `.env` (Exemplo completo):**
    ```ini
    # --- MODO DE OPERAÇÃO PADRÃO ---
    # Opções: ORACLE ou PLANILHA
    MODE=ORACLE

    # --- MODO DE EXECUÇÃO ---
    # Opções: PARALLEL (rápido, padrão) ou SEQUENTIAL (lento, para depuração)
    EXECUTION_MODE=PARALLEL

    # --- CREDENCIAIS ORACLE (Obrigatório apenas para MODE=ORACLE) ---
    ORACLE_USER=seu_usuario_oracle
    ORACLE_PASSWORD=sua_senha_oracle
    ORACLE_HOST=host.do.banco.oracle
    ORACLE_PORT=1521
    ORACLE_SERVICE=nome_do_servico_oracle

    # --- CREDENCIAIS SSH (Sempre obrigatório) ---
    SSH_USERNAME=usuario_ssh_nos_pdvs
    SSH_PASSWORD=senha_ssh_nos_pdvs

    # --- CONFIGURAÇÕES DE PERFORMANCE ---
    MAX_WORKERS=15            # Máximo de PDVs a serem processados em paralelo
    SSH_TIMEOUT=30            # Segundos até desistir de um PDV que não responde
    ```

---

## Estrutura do Projeto

O repositório está organizado da seguinte forma:
````
pdv-hardware-inspector/
├── .env                  # Arquivo de configuração local com credenciais
├── .gitignore            # Arquivos e pastas a serem ignorados pelo Git
├── coletaPDV.py          # Módulo responsável pela coleta de hardware via SSH
├── hardwarePDV.log       # Arquivo de log
├── hardwarePDV.py        # Script principal que orquestra a execução
├── lista_pdvs.xlsx/csv   # Planilha com a lista dos PDVs (Opcional)
├── README.md             # Documentação do projeto
└── requirements.txt      # Lista de dependências Python para o projeto
````

---

## 🚀 Como Usar

Com o arquivo `.env` corretamente configurado e/ou planilha na pasta raíz do projeto, execute o script principal:

```bash
python hardwarePDV.py
```

1. Um menu interativo será exibido, permitindo que você escolha entre o modo Oracle ou Planilha.

2. A coleta será iniciada com uma barra de progresso.

3. Ao final, os resultados serão salvos no destino correspondente (Oracle ou arquivo Excel) e toda a operação é salva no arquivo hardwarePDV.log.

---

## Detalhes do Modo Planilha
**Planilha de Entrada:** Para usar este modo, crie um arquivo chamado lista_pdvs.xlsx ou lista_pdvs.csv na raiz do projeto.

**Colunas Obrigatórias:** O arquivo precisa conter, no mínimo, as colunas IP, NROEMPRESA, e NROCHECKOUT.

**Planilha de Saída:** O relatório será salvo no arquivo resultado_hardware.xlsx.

---

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