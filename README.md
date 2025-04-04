## Hardware Scanner para PDV

Projetado para escanear informações de hardware de sistemas Linux via SSH, coletando dados detalhados sobre componentes. O aplicativo conecta-se a múltiplas máquinas em paralelo, processa os dados e gera um relatório completo em uma planilha de retorno.

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

## Pré-requisitos

### Pacotes Python Necessários

Instale as dependências usando o comando abaixo:

```bash
pip install pandas paramiko tqdm openpyxl xlrd
```

- **pandas**: Para manipulação de dados e E/S do Excel.
- **paramiko**: Para conexões SSH.
- **tqdm**: Para barras de progresso.
- **openpyxl**: Para manipulação de arquivos Excel.
- **xlrd**: Para leitura de arquivos Excel.

### Acesso SSH aos Sistemas Alvo

- Os sistemas Linux alvo devem ter o SSH habilitado.
- São necessárias credenciais SSH válidas com permissões suficientes para executar comandos de detecção de hardware.

---

## Formato do Arquivo de Entrada

A ferramenta requer uma planilha Excel (`lista ip.xlsx`) com a seguinte estrutura mínima:

| IP         | DESCRICAO                     | Outras colunas... |
|------------|-------------------------------|-------------------|
| 10.24.3.12 | SJ DA BA - PDV 12 SUPERMERCADO | ...               |
| 10.24.3.13 | SJ DA BA - PDV 13 SUPERMERCADO | ...               |

No mínimo, a planilha deve incluir uma coluna `"IP"`. A coluna `"DESCRICAO"` é usada para extrair informações do PDV, mas é opcional.

**Nota**: O arquivo de entrada deve estar no mesmo diretório que o script.

---

## Como Usar

1. Coloque o arquivo Excel de entrada (`lista ip.xlsx`) no **mesmo diretório onde o script está localizado**.
2. Execute o script:

   ```bash
   python hardwarePDV.py
   ```

3. Insira as credenciais SSH quando solicitado:
   - Usuário (padrão: `"root"` se deixado em branco).
   - Senha.

4. O script iniciará o escaneamento de todos os IPs em paralelo e exibirá uma barra de progresso.
5. Os resultados são salvos periodicamente em `lista ip retorno.xlsx` no **mesmo diretório do script**.

---

## Formato da Saída

A planilha de saída conterá todas as colunas originais mais as seguintes novas colunas:

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

## Personalização

Você pode modificar essas variáveis no início do script para ajustar o desempenho:

```python
CONNECTION_TIMEOUT = 8  # Tempo limite de conexão SSH em segundos
COMMAND_TIMEOUT = 10    # Tempo limite para execução de comandos
MAX_WORKERS = 20        # Número máximo de threads paralelas
MAX_RETRIES = 2         # Número de tentativas por IP
```

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

Lucas Ribeiro

---