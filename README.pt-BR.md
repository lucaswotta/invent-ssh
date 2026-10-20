<div align="center">

<img src="brand/invent-ssh-mark-128.png" alt="Símbolo pinguim do Invent-SSH" width="88">

# Invent-SSH

**Inventário de hardware Linux em escala.**

Colete informações de hardware de máquinas Linux via SSH e transforme os resultados em relatórios úteis — sem agente, banco de dados ou sistema de inventário de um fornecedor específico.

[Início rápido](#início-rápido) · [Relatórios](#relatórios) · [Segurança](#segurança) · [Visão do produto](docs/PRODUCT_VISION.md)

[English](README.md)

</div>

---

## Por que Invent-SSH?

Equipes de infraestrutura frequentemente recebem centenas ou milhares de máquinas com registros incompletos de hardware. O Invent-SSH ajuda a responder perguntas práticas: quais dispositivos estão acessíveis, quais processadores e memórias possuem, quais ainda usam HDD e onde uma atualização pode fazer mais diferença?

O contrato público é simples: **forneça uma lista de destinos autorizados e receba um relatório para inspecionar, filtrar, compartilhar ou processar em outras ferramentas.**

## O que ele coleta

| Área | Exemplos |
| --- | --- |
| Sistema operacional | Distribuição Linux e kernel |
| Processador | Modelo, núcleos físicos / threads lógicas quando disponíveis |
| Memória | Capacidade total e tipo quando disponível |
| Armazenamento | Tipo (NVMe, SSD, HDD) e capacidade |
| Placa-mãe | Fabricante e modelo quando disponíveis |
| Conectividade | Online, offline, falha de autenticação ou erro SSH |
| Contexto dos ativos | Hostname, etiqueta, local, responsável, departamento, observações e demais colunas do arquivo de entrada |

Os campos disponíveis dependem do sistema-alvo, das ferramentas instaladas e das permissões da conta SSH. Dados indisponíveis são identificados como tal, sem inventar valores.

## Início rápido

### 1. Prepare a lista de destinos

Crie um arquivo Excel (.xlsx/.xlsm) ou CSV (.csv) com uma coluna que identifique a máquina. Nomes de coluna aceitos:

`IP`, `HOST`, `HOSTNAME`, `ADDRESS`, `IP_ADDRESS`, `ENDPOINT` ou `TARGET`.

As demais colunas são preservadas como metadados e incluídas no relatório. Por exemplo:

| IP | HOSTNAME | ASSET_TAG | LOCATION | OWNER |
| --- | --- | --- | --- | --- |
| 192.0.2.10 | lab-node-01 | ASSET-001 | Laboratório | Infraestrutura |
| 192.0.2.11 | lab-node-02 | ASSET-002 | Filial | Operações |

Os IPs do exemplo são reservados para documentação; use os endereços da sua própria rede no arquivo de entrada.

### 2. Conecte via SSH

- Use uma conta com o menor privilégio necessário para ler as informações de hardware.
- Prefira chaves SSH a senhas.
- Por padrão, o Invent-SSH valida as chaves de host usando a base local do SSH de hosts conhecidos. Hosts desconhecidos são rejeitados. Sempre que possível, cadastre as chaves esperadas antes da coleta.
- Existe uma opção de compatibilidade que confia em chaves desconhecidas. Ela é **menos segura** e só deve ser habilitada conscientemente em uma rede confiável; reduz a proteção contra ataques de intermediário (machine-in-the-middle).

### 3. Execute o inventário

**Windows:** use um pacote compatível publicado em [GitHub Releases](https://github.com/lucaswotta/invent-ssh/releases) quando estiver disponível, ou gere um pacote nativo a partir do código.

**Linux / macOS:** recomendamos Python 3.11 ou superior. A interface gráfica exige suporte a Tcl/Tk na instalação do Python escolhida.

No Debian/Ubuntu, instale o módulo Tk correspondente antes de criar o ambiente virtual:

```bash
sudo apt install python3-tk
```

No Fedora, use `sudo dnf install python3-tkinter`. No macOS, use uma distribuição Python que inclua Tcl/Tk.

```bash
git clone https://github.com/lucaswotta/invent-ssh.git
cd invent-ssh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

No Windows PowerShell, use `.venv\Scripts\Activate.ps1` no lugar do comando `source`.

## Relatórios

Escolha o formato adequado:

- **Excel (.xlsx)** — resumo executivo e aba de inventário com filtros, cabeçalhos congelados, larguras legíveis, status destacados e configuração para impressão.
- **HTML (.html)** — relatório independente, com métricas, tabela pesquisável e filtrável, layout responsivo e sem servidor nem recursos externos.
- **CSV (.csv)** — UTF-8 com BOM e delimitador ponto e vírgula para compatibilidade com planilhas e outras ferramentas.

Os relatórios são salvos localmente na pasta Documentos, em `Invent-SSH Reports`. O caminho não depende do diretório em que o programa foi iniciado. Trate-os como dados de infraestrutura: podem conter nomes de host, endereços, identificadores de ativos e metadados de localização/responsabilidade.

## Escala e modo de operação

- A quantidade de conexões SSH simultâneas é limitada pela configuração de workers. O motor não cria uma tarefa pendente para cada destino de uma só vez, reduzindo o uso de memória em listas grandes.
- Cada máquina recebe um status individual. Uma máquina inacessível não invalida os resultados das demais.
- Ajuste concorrência e timeouts à capacidade do computador, rede e alvos; mais workers nem sempre significam mais velocidade.
- O coletor é voltado a máquinas Linux e à inspeção de leitura. Não instala agente nem altera a configuração dos destinos.

## Segurança

- Execute inventários somente em sistemas que você administra ou para os quais tenha autorização explícita.
- As credenciais SSH são fornecidas para a sessão. A senha não é persistida; o programa pode lembrar o usuário e o **caminho** da chave privada na configuração local. O arquivo da chave não é copiado para a configuração.
- Evite publicar logs ou relatórios sem sanitização: eles podem conter identificadores da infraestrutura e mensagens de erro.
- A confiança em chaves desconhecidas fica desabilitada por padrão; habilitar essa opção reduz a verificação da identidade do host.
- O Invent-SSH é uma ferramenta de inventário, não um atestado de integridade de hardware nem um scanner de segurança.

Veja [SECURITY.md](SECURITY.md) para reportar vulnerabilidades e consultar limitações atuais.

## Identidade visual e interface redimensionável

A interface usa um pinguim criado para o produto, superfícies azul-marinho e amarelo como cor de ação principal. A janela abre maximizada, continua redimensionável e reorganiza os cartões quando a largura diminui; telas com muitos campos permanecem roláveis. HTML e Excel seguem a mesma identidade visual, e o HTML incorpora o logo para funcionar offline.

Na primeira execução, o aplicativo herda o idioma do sistema quando ele é português brasileiro ou inglês. Uma preferência de idioma escolhida e salva no aplicativo tem prioridade nos usos seguintes.

## Gerar um pacote nativo

O build deve ser feito no sistema operacional de destino; PyInstaller não compila pacotes Windows, macOS e Linux de forma cruzada a partir de uma única máquina.

```bash
python -m pip install -r requirements-build.txt
python build.py
```

O pacote é salvo em `dist/`, enquanto arquivos intermediários ficam isolados em `build/`. Use `python build.py --console` para builds de diagnóstico.

## Qualidade e documentação

A suíte cobre parsers de hardware Linux, política SSH, coleta concorrente limitada, migração de configuração/caminhos, idioma, segurança dos relatórios e layout responsivo. O GitHub Actions testa Windows, macOS e Linux e gera um pacote nativo em cada sistema.

- [Visão do produto e roadmap](docs/PRODUCT_VISION.md)
- [Arquitetura](docs/ARCHITECTURE.md)
- [Histórico de alterações](CHANGELOG.md)
- [Como contribuir](CONTRIBUTING.md)

## Licença

MIT. Consulte [LICENSE](LICENSE).
