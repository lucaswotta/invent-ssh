<<<<<<< HEAD
# PDV Hardware Inspector

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
=======
## Hardware Scanner para PDV
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

Projetado para escanear informações de hardware de sistemas Linux via SSH, coletando dados detalhados sobre componentes. O aplicativo conecta-se a múltiplas máquinas em paralelo, processa os dados e gera um relatório completo em uma planilha de retorno.

<<<<<<< HEAD
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
=======
Além de coletar informações de hardware, o script também avalia a prioridade de upgrade dos sistemas com base em critérios como obsolescência do processador, capacidade de RAM e tipo de disco (HD/SSD).

---

## Funcionalidades

- **Escaneamento Paralelo**: Processa múltiplos sistemas simultaneamente para maior eficiência.
- **Detecção Detalhada de Hardware**:
  - Placa-mãe (fabricante e modelo combinados).
  - Processador (modelo e quantidade de núcleos/threads).
  - Memória RAM (capacidade e tipo: DDR3/DDR4/DDR5).
  - Armazenamento (tipo: SSD/HD e capacidade total).
  - Versão do kernel Linux.
- **Avaliação de Prioridade de Upgrade**:
  - Classifica os sistemas em três níveis de prioridade (`Alta`, `Média`, `Baixa`) com base em critérios específicos.
  - Inclui uma coluna explicativa com os motivos para upgrade (ex.: "Processador em obsolência", "RAM abaixo do ideal").
- **Tratamento de Erros Robusto**: Métodos múltiplos de detecção para maximizar a taxa de sucesso.
- **Acompanhamento de Progresso**: Barra de progresso em tempo real e salvamento periódico dos resultados.
- **Configurável**: Ajustes de timeout, número de threads e tentativas de reconexão.

---
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

---

## 🔧 Instalação e Configuração

<<<<<<< HEAD
Siga os passos abaixo para preparar o ambiente e executar o projeto.

### Pré-requisitos
=======
Instale as dependências usando o comando abaixo:

```bash
pip install pandas paramiko tqdm openpyxl xlrd
```

- **pandas**: Para manipulação de dados e E/S do Excel.
- **paramiko**: Para conexões SSH.
- **tqdm**: Para barras de progresso.
- **openpyxl**: Para manipulação de arquivos Excel.
- **xlrd**: Para leitura de arquivos Excel.
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

1.  **Python 3.8+**: [Instalar Python](https://www.python.org/downloads/)
2.  **Oracle Instant Client**: A biblioteca `oracledb` necessita do client do Oracle. Faça o download no [site oficial](https://www.oracle.com/database/technologies/instant-client/downloads.html) e adicione o diretório ao `PATH` do seu sistema.
3.  **Acesso de Rede**: A máquina que executa o script precisa de acesso de rede ao banco de dados Oracle e aos PDVs (via porta SSH, padrão 22).

<<<<<<< HEAD
### Passos de Instalação
=======
- Os sistemas Linux alvo devem ter o SSH habilitado.
- São necessárias credenciais SSH válidas com permissões suficientes para executar comandos de detecção de hardware.

---
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-seu-repositorio-aqui>
    cd pdv-hardware-inspector
    ```

<<<<<<< HEAD
2.  **Instale as dependências a partir do `requirements.txt`:**
    ```bash
    pip install -r requirements.txt
    ```
=======
A ferramenta requer uma planilha Excel (`lista ip.xlsx`) com a seguinte estrutura mínima:
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

3.  **Configure as variáveis de ambiente:**
    Crie um arquivo chamado `.env` na raiz do projeto e preencha-o com as informações do seu ambiente.

<<<<<<< HEAD
    **Arquivo `.env`:**
    ```ini
    # --- Credenciais do Banco de Dados Oracle ---
    ORACLE_USER=seu_usuario_oracle
    ORACLE_PASSWORD=sua_senha_oracle
    ORACLE_HOST=host.do.banco.oracle
    ORACLE_PORT=porta_do_servico_oracle
    ORACLE_SERVICE=nome_do_servico_oracle
=======
No mínimo, a planilha deve incluir uma coluna `"IP"`. A coluna `"DESCRICAO"` é usada para extrair informações do PDV, mas é opcional.
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

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
├── .env                  # Arquivo de configuração local com credenciais (NÃO versionar)
├── .gitignore            # Arquivos e pastas a serem ignorados pelo Git
├── README.md             # Documentação do projeto
├── coletaPDV.py          # Módulo responsável pela coleta de hardware via SSH
├── hardwarePDV.py        # Script principal que orquestra a execução
└── requirements.txt      # Lista de dependências Python para o projeto
````

---

## Como Usar

Com o arquivo `.env` corretamente configurado, execute o script principal:

<<<<<<< HEAD
```bash
python hardwarePDV.py
````

## Saída dos Dados

Os dados coletados são armazenados na tabela `CONSINCO.BAR_HARDWARE_PDV` no Oracle. A estrutura da tabela é a seguinte:
=======
   ```bash
   python hardwarePDV.py
   ```

3. Insira as credenciais SSH quando solicitado:
   - Usuário (padrão: `"root"` se deixado em branco).
   - Senha.

4. O script iniciará o escaneamento de todos os IPs em paralelo e exibirá uma barra de progresso.
5. Os resultados são salvos periodicamente em `lista ip retorno.xlsx` no **mesmo diretório do script**.

---
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

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

<<<<<<< HEAD
## 🛠️ Solução de Problemas
=======
| Coluna           | Descrição                                                                 |
|------------------|---------------------------------------------------------------------------|
| PLACA-MÃE        | Fabricante e modelo da placa-mãe combinados                               |
| PROCESSADOR      | Modelo da CPU                                                             |
| CORES/THREADS    | Número de núcleos físicos e threads lógicas                              |
| RAM              | Capacidade e tipo de memória (ex.: `"8GB DDR4"`)                          |
| DISCO            | Tipo de armazenamento (`SSD` ou `HD`)                                     |
| ARMAZENAMENTO    | Capacidade total do disco                                                 |
| RELEASE          | Versão do kernel Linux                                                    |
| STATUS           | Status do escaneamento (`"Sucesso"` ou mensagem de erro)                  |
| PRIORIDADE       | Prioridade de upgrade (`"Alta"`, `"Média"`, `"Baixa"` ou `"Offline"`)      |
| MOTIVO DO UPGRADE| Motivos para upgrade (ex.: `"Processador em obsolência; RAM abaixo do ideal"`) |

---

## Avaliação de Prioridade e Motivo de Upgrade

O script classifica os sistemas com base nos seguintes critérios:

- **Prioridade Alta**:
  - Processador obsoleto.
  - RAM abaixo de 4GB e disco HD.
- **Prioridade Média**:
  - RAM abaixo de 4GB ou disco HD.
- **Prioridade Baixa**:
  - Sistema atende aos requisitos mínimos.
- **Offline**:
  - Falha na conexão ou falta de informações de hardware.

Os motivos para upgrade são listados na coluna `"MOTIVO DO UPGRADE"`, separados por ponto-e-vírgula.

---
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

-   **Erros de Conexão com Oracle**:
    -   Verifique se as credenciais, host, porta e service name no `.env` estão corretos.
    -   Confirme se o **Oracle Instant Client** está instalado e configurado no `PATH` do sistema.
    -   Verifique se não há firewalls bloqueando a conexão com o banco.

-   **Falhas de Conexão SSH**:
    -   Confirme que o usuário e senha SSH no `.env` estão corretos.
    -   Assegure que a rede permite a comunicação da máquina executora com os PDVs na porta 22.

-   **Campos de Hardware como "Não detectado"**:
    -   Algumas distribuições Linux muito antigas ou customizadas podem não ter os utilitários necessários instalados.

<<<<<<< HEAD
Para erros detalhados, sempre consulte o arquivo de log `hardwarePDV.log`.

## Autor
=======
- Aumente `MAX_WORKERS` para processamento mais rápido (se sua rede/computador suportar).
- Diminua `CONNECTION_TIMEOUT` para falhar mais rápido em hosts inacessíveis.
- Aumente `MAX_RETRIES` para maior resiliência em redes instáveis.

---

## Caminhos dos Arquivos

Por padrão, o script usa o diretório onde o próprio script está localizado para buscar e salvar arquivos. Isso é feito automaticamente usando `os.path.dirname(os.path.abspath(__file__))`.

Se você deseja alterar isso manualmente, modifique a variável `caminho_base` na função `main()`.

---

## Solução de Problemas

### Problemas Comuns

1. **"Não detectado" em campos de hardware**:
   - Alguns métodos de detecção podem falhar em certas distribuições Linux.
   - O script tenta múltiplos métodos, mas pode não funcionar em todos os sistemas.
   - Verifique se os utilitários necessários (`dmidecode`, `lshw`, `smartctl`) estão instalados nos sistemas alvo.

2. **Falhas de conexão**:
   - Verifique se o SSH está habilitado nos sistemas alvo.
   - Confira se firewalls estão bloqueando conexões SSH.
   - Valide se os IPs e credenciais estão corretos.

3. **Erros no Excel**:
   - Garanta que o arquivo de entrada tenha a coluna `"IP"`.
   - Certifique-se de que o arquivo não está aberto em outro programa.

### Logs

O script cria um arquivo de log `hardware_scan.log` no diretório atual com detalhes sobre erros durante a execução.

---

## Como Funciona

1. O script lê a lista de IPs da planilha Excel.
2. Estabelece conexões SSH paralelas a cada IP.
3. Em cada sistema, executa comandos para detectar informações de hardware.
4. Tenta múltiplos métodos de detecção para cada componente.
5. Avalia a prioridade de upgrade com base nos critérios definidos.
6. Compila os resultados na planilha de saída.

---

## Licença

Este projeto foi desenvolvido para uso interno, mas sinta-se à vontade para contribuir.

---

## Autor

![Lucas Ribeiro](https://github.com/lucaswotta.png?size=120)
>>>>>>> bb3374c8ebbc2839fd2ae95848523d2e15acb503

| ![Lucas Ribeiro](https://github.com/lucaswotta.png?size=120) |
| :---: |
| **Lucas Ribeiro** |
| [![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/lucaswotta) |