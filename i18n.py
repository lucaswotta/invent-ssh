# -*- coding: utf-8 -*-
"""
i18n.py: Suporte a múltiplos idiomas para o invent-ssh.

Centraliza todos os textos exibidos ao usuário (interface e mensagens de log
enviadas à interface) em um único dicionário por idioma. O idioma ativo é
lido do `config.json` na inicialização e pode ser trocado pela aba
'Configurações' (requer reiniciar a aplicação para ser aplicado por completo).
"""
import json
import locale
import os
import re
from typing import Dict

from paths import get_config_path

CONFIG_FILE = str(get_config_path())
DEFAULT_LANGUAGE = "pt-br"
SUPPORTED_LANGUAGES = ("pt-br", "en")
LANGUAGE_DISPLAY_NAMES = {"pt-br": "Português (Brasil)", "en": "English"}

STRINGS: Dict[str, Dict[str, str]] = {
    "pt-br": {
        "include_sensitive_identifiers_label": "Incluir número de série do equipamento (dado sensível)",
        "include_sensitive_identifiers_tooltip": "Desativado por padrão. O número de série pode identificar fisicamente um equipamento; habilite apenas quando precisar dele no inventário e proteja o relatório exportado.",
        "hw_host_key_mismatch": "A chave SSH do host não corresponde à chave conhecida para {ip}. A conexão foi recusada.",
        # --- Geral / Janela Principal ---
        "app_title": "Invent-SSH",
        "app_subtitle": "Inventário de hardware Linux em escala",
        "home_eyebrow": "INVENTÁRIO LOCAL · LINUX",
        "home_hero_title": "Descubra o que existe em cada máquina.",
        "home_hero_body": "Transforme uma lista de endereços em um inventário de hardware claro, organizado e pronto para orientar decisões.",
        "home_primary_cta": "Começar inventário",
        "home_step1_title": "Escolha sua lista",
        "home_step1_body": "Abra um CSV ou Excel com IP ou hostname. Colunas de patrimônio, local e responsável também entram no relatório.",
        "home_step2_title": "Conecte com segurança",
        "home_step2_body": "Use SSH com sua conta de leitura e, preferencialmente, uma chave privada.",
        "home_step3_title": "Receba a visão completa",
        "home_step3_body": "Acompanhe cada máquina e exporte uma planilha organizada ou um relatório HTML para compartilhar.",
        "home_reports_heading": "Um formato para cada próximo passo",
        "home_reports_xlsx_title": "Excel para analisar",
        "home_reports_xlsx_body": "Resumo, filtros e colunas preparadas para comparar o parque.",
        "home_reports_html_title": "HTML para apresentar",
        "home_reports_html_body": "Relatório interativo que abre no navegador, mesmo sem internet.",
        "home_reports_csv_title": "CSV para integrar",
        "home_reports_csv_body": "Dados tabulares para importar em outras ferramentas.",
        "home_privacy_note": "Sem agente nas máquinas · Sem banco de dados · Relatórios gerados localmente",
        "inventory_intro_title": "Preparar inventário",
        "inventory_intro_body": "Você só precisa de uma lista de máquinas e uma conta SSH autorizada. O Invent-SSH não instala nada nos destinos.",
        "inventory_file_section": "01  Lista de máquinas",
        "inventory_file_hint": "Uma máquina por linha. Use IP, HOST, HOSTNAME ou ADDRESS; as demais colunas são preservadas.",
        "inventory_credentials_section": "02  Acesso SSH",
        "inventory_credentials_hint": "Use uma conta de leitura e uma chave SSH sempre que possível. A senha não é gravada.",
        "inventory_output_section": "03  Relatório",
        "inventory_output_hint": "Os relatórios são salvos na pasta Documentos / Invent-SSH Reports.",
        "status_available": "Acessível",
        "status_unavailable": "Inacessível",
        "coverage_label": "Cobertura dos dados",
        "tab_home": "Início",
        "tab_spreadsheet": "Lista de ativos",
        "tab_settings": "Configurações",
        "tab_about": "Sobre",
        "run_button_default": "Iniciar Inventário",
        "run_button_spreadsheet": "▶ Iniciar Inventário",
        "run_button_running": "Executando...",
        "run_button_tooltip": "Inicia a coleta de hardware usando a lista de ativos e as credenciais SSH.",

        # --- Modal de Boas-vindas ---
        "welcome_title": "Bem-vindo ao {app_name}!",
        "welcome_section1_title": "A Origem e o Código Aberto",
        "welcome_section1_body": "O Invent-SSH surgiu da necessidade de descobrir o hardware de um parque Linux sem depender de registros manuais. Agora evolui como ferramenta open-source e genérica para equipes de infraestrutura, profissionais de TI e a comunidade.",
        "welcome_section2_title": "Conectividade de Rede: Como Funciona?",
        "welcome_section2_body": "Para que a mágica aconteça, seu computador precisa se comunicar com as máquinas Linux na rede via SSH (porta 22). Garanta que não haja um firewall bloqueando esta porta e que você esteja conectado na mesma rede que os terminais (seja via cabo, Wi-Fi ou VPN).",
        "welcome_section3_title": "Segurança é Inegociável",
        "welcome_section3_body": ("•  A senha SSH não é salva; o usuário e o caminho da chave privada podem ser lembrados na configuração local.\n"
                                   "•  Dê preferência ao uso de Chaves SSH. É o padrão da indústria e exponencialmente mais seguro que senhas.\n"
                                   "•  Execute o Invent-SSH apenas em redes nas quais você tenha autorização e confiança. Evite redes públicas.\n"
                                   "•  Você é o guardião das suas credenciais. Use-as de acordo com as políticas da sua empresa."),
        "welcome_checkbox_dont_show": "Não mostrar esta mensagem novamente",
        "welcome_button_start": "Entendi, vamos começar!",

        # --- Log Modal ---
        "log_modal_title_running": "Executando Inventário...",
        "log_modal_title_finished": "Processo Concluído",
        "log_modal_close_button": "Fechar",
        "log_modal_close_warning_title": "Atenção",
        "log_modal_close_warning_body": "O inventário está em execução. Por favor, aguarde a finalização.",
        "log_modal_finished_title": "Concluído",

        # --- Credenciais SSH ---
        "ssh_credentials_title": "Credenciais de Acesso SSH",
        "ssh_user_label": "Usuário SSH*",
        "ssh_user_tooltip": "Usuário para a conexão SSH (ex: root, admin). Campo obrigatório.",
        "ssh_pass_placeholder": "Senha SSH (se não usar chave)",
        "ssh_pass_tooltip": "Senha do usuário SSH. Deixe em branco para usar uma Chave Privada.",
        "ssh_key_placeholder": "Caminho para a Chave SSH Privada (recomendado)",
        "ssh_key_tooltip": "Caminho completo para sua chave SSH privada (ex: C:/Users/Você/.ssh/id_rsa).\nÉ o método de autenticação mais seguro.",
        "browse_button": "Procurar...",
        "select_ssh_key_title": "Selecionar Chave SSH Privada",

        # --- Aba Início ---
        "home_welcome_text": ("Bem-vindo ao Invent-SSH!\n\n"
                               "Automatize o inventário de hardware de seus computadores Linux de forma simples e segura.\n\n"
                               "Como Começar:\n\n"
                               "1. Selecione a lista de ativos (CSV ou Excel).\n"
                               ""
                               "   •  Endereços podem ser IPs ou hostnames. Colunas adicionais serão preservadas no relatório.\n\n"
                               "2. Forneça as credenciais de acesso SSH.\n\n"
                               "3. Clique no botão 'Iniciar Inventário' e acompanhe o progresso em tempo real.\n\n"
                               "Dica: na aba 'Lista de ativos', use o botão [?] para gerar um modelo com hostname, etiqueta, localização e responsável."),

        # --- Asset list and report settings ---
        "spreadsheet_file_label": "Lista de máquinas (.xlsx, .xlsm ou .csv)*",
        "spreadsheet_help_tooltip": "Clique para criar um arquivo de planilha modelo (.xlsx).",
        "spreadsheet_file_placeholder": "Colunas aceitas: IP, HOST, HOSTNAME ou ADDRESS",
        "spreadsheet_file_tooltip": "Caminho da lista de ativos. Use IP, HOST, HOSTNAME ou ADDRESS como destino. Outras colunas são preservadas no relatório.",
        "output_destination_label": "Relatório de saída",
        "output_format_label": "Formato do relatório:",
        "spreadsheet_output_format_tooltip": "Excel formatado para análise, CSV para integração ou HTML interativo para compartilhar.",
        "trust_unknown_hosts_label": "Confiar em chaves SSH desconhecidas (menos seguro)",
        "trust_unknown_hosts_tooltip": "Por padrão, o SSH verifica as chaves em known_hosts. Marque esta opção apenas em redes confiáveis quando ainda não tiver cadastrado as chaves; isso reduz a proteção contra ataques man-in-the-middle.",
        "select_spreadsheet_title": "Selecionar planilha",
        "spreadsheet_filetype_label": "CSV ou Excel",
        "all_files_label": "Todos os arquivos",


        # --- Aba Configurações ---
        "settings_performance_title": "Performance e Execução",
        "settings_workers_label": "Processos Paralelos:",
        "settings_workers_tooltip": "Número máximo de computadores a serem processados simultaneamente.\nValores mais altos são mais rápidos, mas consomem mais recursos.",
        "settings_timeout_label": "Timeout SSH (segundos):",
        "settings_timeout_tooltip": "Tempo máximo em segundos para aguardar uma resposta de cada computador antes de desistir.",
        "settings_language_title": "Idioma",
        "settings_language_label": "Idioma da Interface:",
        "settings_language_tooltip": "Define o idioma da interface e das mensagens. É necessário reiniciar a aplicação para aplicar a troca.",

        # --- Aba Sobre ---
        "about_version": "Versão:",
        "about_developed_by": "Desenvolvido por:",
        "about_license": "Licença:",
        "about_github": "GitHub:",
        "about_linkedin": "LinkedIn:",
        "about_help_button": "Ajuda: Por que alguns dados de hardware não são coletados?",
        "help_modal_title": "Guia de Coleta de Dados",
        "help_modal_body": ("A cobertura depende do sistema Linux, das ferramentas disponíveis e das permissões da conta SSH.\\n\\n"
                             "A coleta é somente de leitura e não instala agente ou pacotes no destino. O programa agrupa a descoberta em uma chamada SSH limitada por timeout.\\n\\n"
                             "FONTES CONSULTADAS\\n\\n"
                             "• Sistema operacional e kernel: /etc/os-release e uname.\\n"
                             "• CPU e topologia: lscpu e /proc/cpuinfo.\\n"
                             "• Memória: /proc/meminfo; dmidecode pode acrescentar tipo, velocidade e módulos quando autorizado.\\n"
                             "• Armazenamento: lsblk em JSON, com alternativa para versões antigas do util-linux.\\n"
                             "• Fabricante, placa e firmware: sysfs DMI; alguns detalhes dependem de privilégios.\\n"
                             "• GPU, rede e virtualização: lspci, sysfs, ip e systemd-detect-virt quando disponíveis.\\n\\n"
                             "DADOS AUSENTES\\n\\n"
                             "Se uma fonte não existir, não tiver permissão ou não fornecer o campo, o relatório marca o dado como indisponível. A classificação de HDD/flash usa indicadores do kernel e pode variar em máquinas virtuais."),
        "help_modal_close_button": "Entendi",

        # --- Planilha Modelo ---
        "save_template_title": "Salvar Planilha Modelo",
        "excel_filetype_label": "Planilha Excel",
        "template_created_title": "Modelo Criado",
        "template_created_body": "A planilha modelo foi salva com sucesso em:\n{filepath}",
        "template_error_title": "Erro ao Criar Modelo",
        "template_error_body": "Ocorreu um erro:\n{error}",

        # --- Confirmação e Erros de Execução ---
        "config_error_title": "Erro de Configuração",
        "unexpected_error_title": "Erro Inesperado",
        "unexpected_error_body": "Ocorreu um erro ao iniciar: {error}",
        "error_invalid_spreadsheet": "Por favor, selecione um arquivo de planilha válido. O caminho não foi encontrado.",
        "error_ssh_user_required": "O campo 'Usuário SSH' é obrigatório.",
        "error_ssh_auth_required": "É obrigatório fornecer uma Senha SSH ou o caminho para uma Chave Privada.",
        "error_invalid_tab": "Selecione a aba de lista de ativos para iniciar o inventário.",
        "open_file_warning_title": "Aviso",
        "open_file_warning_body": "Não foi possível abrir o arquivo '{filename}' automaticamente.\n\nEle está localizado em:\n{filepath}\n\nErro: {error}",
        "exit_confirm_title": "Sair",
        "exit_confirm_body": "O inventário ainda está em execução. Deseja realmente sair? A coleta pendente será cancelada.",

        # --- Dependências e Erros Fatais ---
        "missing_deps_title": "Dependências Ausentes",
        "missing_deps_body": "As seguintes dependências não foram encontradas:\n\n{packages}\n\nDeseja instalá-las agora? (Requer conexão com a internet)",
        "deps_install_success_title": "Sucesso",
        "deps_install_success_body": "Dependências instaladas com sucesso!\nPor favor, reinicie a aplicação.",
        "deps_install_error_title": "Erro na Instalação",
        "deps_install_error_body": "Não foi possível instalar as dependências.\nErro: {error}\n\nInstale-as manualmente: pip install {packages}",
        "deps_skip_warning_title": "Aviso",
        "deps_skip_warning_body": "A aplicação pode não funcionar corretamente sem as dependências.",
        "fatal_error_title": "Erro Fatal",
        "fatal_error_body": "A aplicação encontrou um erro e precisa ser fechada.\n\nUm log de erro CENSURADO foi salvo em '{log_file}'.\nUm log DETALHADO foi salvo na pasta 'logs'.",
        "import_error_title": "Erro de Importação",
        "import_error_body": "Não foi possível importar as bibliotecas necessárias. A aplicação será encerrada.",

        # --- Mensagens de Log do Motor (core.py / inspector.py) ---
        "mode_spreadsheet": "Planilha",
        "log_starting": "Iniciando inventário de hardware...",
        "log_no_terminals": "Nenhum destino válido encontrado na lista de ativos. Processo abortado.",
        "log_terminals_loaded": "{count} destinos carregados. Iniciando coleta...",
        "log_no_data_collected": "Nenhum dado de hardware foi coletado; não foi gerado relatório.",
        "log_process_cancelled_no_results": "Inventário cancelado antes de coletar resultados.",
        "log_process_cancelled_with_results": "Inventário cancelado. O relatório contém os resultados coletados até aqui ({count} máquinas).",
        "log_process_failed": "Falha ao concluir o inventário: {error}",
        "log_collection_finished": "Coleta finalizada: {count} resultados. Gerando relatório...",
        "log_critical_engine_error": "Erro crítico no motor da aplicação: {error}",
        "log_process_finished": "Inventário concluído: {online} acessíveis, {failed} com falha. Relatório salvo.",
        "log_cancelled_by_user": "Cancelamento solicitado pelo usuário. Interrompendo terminais pendentes...",
        "log_unknown_mode": "Modo de operação desconhecido: {mode}",
        "log_missing_ip_column": "O arquivo deve conter a coluna 'IP'",
        "log_file_not_found": "Arquivo não encontrado: {filepath}",
        "log_spreadsheet_format_error": "Erro de formatação na planilha: {error}",
        "log_spreadsheet_read_error": "Falha ao ler planilha '{filename}': {error}",
        "log_circuit_breaker_tripped": "Circuit Breaker: 10/10 conexões iniciais falharam. Abortando.",
        "log_circuit_breaker_hint": "Verifique credenciais SSH, rede ou firewall.",
        "log_processing_exception": "Exceção ao processar {ip}: {error}",
        "log_terminal_no_ip": "Terminal ignorado por não possuir IP: {terminal}",
        "log_collection_success": "Sucesso na coleta de {ip}",
        "log_collection_failure": "Falha em {ip}: {error}",
        "generic_failure": "Falha geral",
        "log_results_saved": "Resultados salvos com sucesso em '{filename}'",
        "log_opening_result_file": "Abrindo arquivo de resultado...",
        "log_spreadsheet_save_error": "Falha ao salvar planilha de resultados: {error}",

        # --- Mensagens de Coleta de Hardware (inspector.py) ---
        "hw_info_unavailable": "Não foi possível obter",
        "hw_auth_failed": "Falha na autenticação",
        "hw_connection_timeout": "Timeout ao conectar no IP {ip}",
        "hw_ssh_error": "Erro SSH: {error}",
        "hw_key_not_found": "Chave SSH não encontrada: {key_path}",
        "hw_unknown_error": "Erro inesperado: {error}",
    },
    "en": {
        "include_sensitive_identifiers_label": "Include hardware serial number (sensitive data)",
        "include_sensitive_identifiers_tooltip": "Off by default. A serial number can uniquely identify a physical device; enable only when needed and protect the exported report.",
        "hw_host_key_mismatch": "The SSH host key does not match the known key for {ip}. The connection was rejected.",
        # --- General / Main Window ---
        "app_title": "Invent-SSH",
        "app_subtitle": "Linux hardware inventory at scale",
        "home_eyebrow": "LOCAL INVENTORY · LINUX",
        "home_hero_title": "Know what is inside every machine.",
        "home_hero_body": "Turn a list of addresses into a clear, structured hardware inventory that helps you make better infrastructure decisions.",
        "home_primary_cta": "Start an inventory",
        "home_step1_title": "Choose your list",
        "home_step1_body": "Open a CSV or Excel file with IPs or hostnames. Asset tags, location, owner, and other columns stay in the report.",
        "home_step2_title": "Connect securely",
        "home_step2_body": "Use SSH with an authorized read-only account and, preferably, a private key.",
        "home_step3_title": "See the full picture",
        "home_step3_body": "Review each machine and export a well-structured spreadsheet or a shareable HTML report.",
        "home_reports_heading": "A format for the next step",
        "home_reports_xlsx_title": "Excel to analyze",
        "home_reports_xlsx_body": "Summary, filters, and columns prepared for fleet comparisons.",
        "home_reports_html_title": "HTML to present",
        "home_reports_html_body": "An interactive report that opens in a browser, even offline.",
        "home_reports_csv_title": "CSV to integrate",
        "home_reports_csv_body": "Tabular data ready for other tools.",
        "home_privacy_note": "No endpoint agent · No database · Reports generated locally",
        "inventory_intro_title": "Prepare inventory",
        "inventory_intro_body": "You only need a machine list and an authorized SSH account. Invent-SSH does not install anything on your targets.",
        "inventory_file_section": "01  Machine list",
        "inventory_file_hint": "One machine per row. Use IP, HOST, HOSTNAME, or ADDRESS; all other columns are preserved.",
        "inventory_credentials_section": "02  SSH access",
        "inventory_credentials_hint": "Use a read-only account and an SSH key whenever possible. Passwords are not saved.",
        "inventory_output_section": "03  Report",
        "inventory_output_hint": "Reports are saved to Documents / Invent-SSH Reports.",
        "status_available": "Reachable",
        "status_unavailable": "Unreachable",
        "coverage_label": "Data coverage",
        "tab_home": "Home",
        "tab_spreadsheet": "Asset list",
        "tab_settings": "Settings",
        "tab_about": "About",
        "run_button_default": "Start Inventory",
        "run_button_spreadsheet": "▶ Start Inventory",
        "run_button_running": "Running...",
        "run_button_tooltip": "Starts hardware collection using the asset list and SSH settings.",

        # --- Welcome Modal ---
        "welcome_title": "Welcome to {app_name}!",
        "welcome_section1_title": "Origin and Open Source",
        "welcome_section1_body": "Invent-SSH grew from the need to discover hardware across a Linux fleet without relying on manual records. It is evolving as a generic open-source tool for infrastructure teams, IT professionals, and the wider community.",
        "welcome_section2_title": "Network Connectivity: How It Works",
        "welcome_section2_body": "For everything to work, your computer needs to communicate with the Linux machines on the network via SSH (port 22). Make sure no firewall is blocking this port and that you're connected to the same network as the terminals (cable, Wi-Fi, or VPN).",
        "welcome_section3_title": "Security Is Non-Negotiable",
        "welcome_section3_body": ("•  The SSH password is not saved; the username and private-key path may be remembered in local configuration.\n"
                                   "•  Prefer using SSH Keys. It's the industry standard and exponentially safer than passwords.\n"
                                   "•  Run Invent-SSH only on networks you are authorized to assess and trust. Avoid public networks.\n"
                                   "•  You are the guardian of your credentials. Use them according to your company's policies."),
        "welcome_checkbox_dont_show": "Don't show this message again",
        "welcome_button_start": "Got it, let's start!",

        # --- Log Modal ---
        "log_modal_title_running": "Running Inventory...",
        "log_modal_title_finished": "Process Completed",
        "log_modal_close_button": "Close",
        "log_modal_close_warning_title": "Warning",
        "log_modal_close_warning_body": "The inventory is running. Please wait for it to finish.",
        "log_modal_finished_title": "Completed",

        # --- SSH Credentials ---
        "ssh_credentials_title": "SSH Access Credentials",
        "ssh_user_label": "SSH User*",
        "ssh_user_tooltip": "User for the SSH connection (e.g.: root, admin). Required field.",
        "ssh_pass_placeholder": "SSH Password (if not using a key)",
        "ssh_pass_tooltip": "SSH user password. Leave blank to use a Private Key.",
        "ssh_key_placeholder": "Path to the SSH Private Key (recommended)",
        "ssh_key_tooltip": "Full path to your SSH private key (e.g.: C:/Users/You/.ssh/id_rsa).\nThis is the most secure authentication method.",
        "browse_button": "Browse...",
        "select_ssh_key_title": "Select SSH Private Key",

        # --- Home Tab ---
        "home_welcome_text": ("Welcome to Invent-SSH!\n\n"
                               "Automate the hardware inventory of your Linux computers, simply and securely.\n\n"
                               "Getting Started:\n\n"
                               "1. Select your asset list (CSV or Excel).\n"
                               ""
                               "   •  Targets can be IP addresses or hostnames. Extra columns are preserved in the report.\n\n"
                               "2. Provide the SSH access credentials.\n\n"
                               "3. Click the 'Start Inventory' button and follow the progress in real time.\n\n"
                               "Tip: on the 'Asset list' tab, use the [?] button to generate a template with hostname, asset tag, location, and owner."),

        # --- Asset list and report settings ---
        "spreadsheet_file_label": "Machine list (.xlsx, .xlsm, or .csv)*",
        "spreadsheet_help_tooltip": "Click to create a template spreadsheet file (.xlsx).",
        "spreadsheet_file_placeholder": "Accepted target columns: IP, HOST, HOSTNAME, or ADDRESS",
        "spreadsheet_file_tooltip": "Path to the asset list. Use IP, HOST, HOSTNAME, or ADDRESS as the target. Other columns are preserved in the report.",
        "output_destination_label": "Report export",
        "output_format_label": "Report format:",
        "spreadsheet_output_format_tooltip": "Choose styled Excel for analysis, CSV for data exchange, or interactive HTML for sharing.",
        "trust_unknown_hosts_label": "Trust unknown SSH host keys (less secure)",
        "trust_unknown_hosts_tooltip": "By default, SSH verifies host keys against known_hosts. Enable only on trusted networks when keys have not been enrolled yet; this weakens protection against man-in-the-middle attacks.",
        "select_spreadsheet_title": "Select spreadsheet",
        "spreadsheet_filetype_label": "CSV or Excel",
        "all_files_label": "All files",


        # --- Settings Tab ---
        "settings_performance_title": "Performance and Execution",
        "settings_workers_label": "Parallel Processes:",
        "settings_workers_tooltip": "Maximum number of computers to be processed simultaneously.\nHigher values are faster but consume more resources.",
        "settings_timeout_label": "SSH Timeout (seconds):",
        "settings_timeout_tooltip": "Maximum time in seconds to wait for a response from each computer before giving up.",
        "settings_language_title": "Language",
        "settings_language_label": "Interface Language:",
        "settings_language_tooltip": "Sets the interface and message language. Restarting the application is required to fully apply the change.",

        # --- About Tab ---
        "about_version": "Version:",
        "about_developed_by": "Developed by:",
        "about_license": "License:",
        "about_github": "GitHub:",
        "about_linkedin": "LinkedIn:",
        "about_help_button": "Help: Why isn't some hardware data collected?",
        "help_modal_title": "Data Collection Guide",
        "help_modal_body": ("Coverage depends on the Linux system, available utilities, and the SSH account permissions.\\n\\n"
                             "Collection is read-only and does not install an agent or packages on the target. Discovery is grouped into one SSH call bounded by a timeout.\\n\\n"
                             "DATA SOURCES\\n\\n"
                             "• Operating system and kernel: /etc/os-release and uname.\\n"
                             "• CPU and topology: lscpu and /proc/cpuinfo.\\n"
                             "• Memory: /proc/meminfo; dmidecode can add module type, speed and slot details when permitted.\\n"
                             "• Storage: lsblk JSON, with a fallback for older util-linux versions.\\n"
                             "• System vendor, board and firmware: DMI sysfs; some details require privileges.\\n"
                             "• Graphics, network and virtualization: lspci, sysfs, ip and systemd-detect-virt when available.\\n\\n"
                             "MISSING DATA\\n\\n"
                             "If a source is missing, inaccessible or does not return a field, the report marks it unavailable. HDD/flash classification uses kernel indicators and can vary on virtual machines."),
        "help_modal_close_button": "Got it",

        # --- Template Spreadsheet ---
        "save_template_title": "Save Template Spreadsheet",
        "excel_filetype_label": "Excel Spreadsheet",
        "template_created_title": "Template Created",
        "template_created_body": "The template spreadsheet was saved successfully at:\n{filepath}",
        "template_error_title": "Error Creating Template",
        "template_error_body": "An error occurred:\n{error}",

        # --- Confirmation and Execution Errors ---
        "config_error_title": "Configuration Error",
        "unexpected_error_title": "Unexpected Error",
        "unexpected_error_body": "An error occurred while starting: {error}",
        "error_invalid_spreadsheet": "Please select a valid spreadsheet file. The path was not found.",
        "error_ssh_user_required": "The 'SSH User' field is required.",
        "error_ssh_auth_required": "You must provide either an SSH Password or the path to a Private Key.",
        "error_invalid_tab": "Select the asset list tab to start the inventory.",
        "open_file_warning_title": "Warning",
        "open_file_warning_body": "Could not automatically open the file '{filename}'.\n\nIt is located at:\n{filepath}\n\nError: {error}",
        "exit_confirm_title": "Exit",
        "exit_confirm_body": "The inventory is still running. Do you really want to exit? The pending collection will be cancelled.",

        # --- Dependencies and Fatal Errors ---
        "missing_deps_title": "Missing Dependencies",
        "missing_deps_body": "The following dependencies were not found:\n\n{packages}\n\nDo you want to install them now? (Requires an internet connection)",
        "deps_install_success_title": "Success",
        "deps_install_success_body": "Dependencies installed successfully!\nPlease restart the application.",
        "deps_install_error_title": "Installation Error",
        "deps_install_error_body": "Could not install dependencies.\nError: {error}\n\nInstall them manually: pip install {packages}",
        "deps_skip_warning_title": "Warning",
        "deps_skip_warning_body": "The application may not work correctly without the dependencies.",
        "fatal_error_title": "Fatal Error",
        "fatal_error_body": "The application encountered an error and needs to be closed.\n\nA REDACTED error log was saved to '{log_file}'.\nA DETAILED log was saved in the 'logs' folder.",
        "import_error_title": "Import Error",
        "import_error_body": "Could not import the required libraries. The application will be closed.",

        # --- Engine Log Messages (core.py / inspector.py) ---
        "mode_spreadsheet": "Spreadsheet",
        "log_starting": "Starting hardware inventory...",
        "log_no_terminals": "No valid targets found in the asset list. Process aborted.",
        "log_terminals_loaded": "{count} targets loaded. Starting collection...",
        "log_no_data_collected": "No hardware data was collected; no report was generated.",
        "log_process_cancelled_no_results": "Inventory cancelled before any results were collected.",
        "log_process_cancelled_with_results": "Inventory cancelled. The report contains the results collected so far ({count} devices).",
        "log_process_failed": "The inventory failed: {error}",
        "log_collection_finished": "Collection finished: {count} results. Building report...",
        "log_critical_engine_error": "Critical error in the application engine: {error}",
        "log_process_finished": "Inventory finished: {online} online, {failed} with errors. Report saved.",
        "log_cancelled_by_user": "Cancellation requested by the user. Stopping pending terminals...",
        "log_unknown_mode": "Unknown operation mode: {mode}",
        "log_missing_ip_column": "The file must contain the 'IP' column",
        "log_file_not_found": "File not found: {filepath}",
        "log_spreadsheet_format_error": "Spreadsheet formatting error: {error}",
        "log_spreadsheet_read_error": "Failed to read spreadsheet '{filename}': {error}",
        "log_circuit_breaker_tripped": "Circuit Breaker: 10/10 initial connections failed. Aborting.",
        "log_circuit_breaker_hint": "Check SSH credentials, network, or firewall.",
        "log_processing_exception": "Exception while processing {ip}: {error}",
        "log_terminal_no_ip": "Terminal skipped for not having an IP: {terminal}",
        "log_collection_success": "Successfully collected data from {ip}",
        "log_collection_failure": "Failure on {ip}: {error}",
        "generic_failure": "General failure",
        "log_results_saved": "Results saved successfully to '{filename}'",
        "log_opening_result_file": "Opening result file...",
        "log_spreadsheet_save_error": "Failed to save results spreadsheet: {error}",

        # --- Hardware Collection Messages (inspector.py) ---
        "hw_info_unavailable": "Could not be obtained",
        "hw_auth_failed": "Authentication failed",
        "hw_connection_timeout": "Timeout connecting to IP {ip}",
        "hw_ssh_error": "SSH error: {error}",
        "hw_key_not_found": "SSH key not found: {key_path}",
        "hw_unknown_error": "Unexpected error: {error}",
    },
}


def _language_from_locale(candidate: str | None) -> str | None:
    if not candidate:
        return None
    token = re.split(r"[-_.:@]", candidate.strip().replace(":", "-"), maxsplit=1)[0].casefold()
    if token in {"pt", "portuguese", "português"}:
        return "pt-br"
    if token in {"en", "english"}:
        return "en"
    return None


def _system_language() -> str:
    """Resolve a supported language from environment or the OS locale."""
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        raw = os.environ.get(variable, "")
        for candidate in raw.split(":"):
            language = _language_from_locale(candidate)
            if language:
                return language
    try:
        language = _language_from_locale(locale.getlocale()[0])
        if language:
            return language
    except (ValueError, TypeError, AttributeError):
        pass
    return DEFAULT_LANGUAGE


def _load_saved_language() -> str:
    """Use the explicit app preference; on first launch inherit the OS language."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
        if isinstance(config, dict) and "language" in config:
            saved = config.get("language")
            if saved in SUPPORTED_LANGUAGES:
                return saved
            return _system_language()
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        pass
    return _system_language()


def set_language(lang: str) -> None:
    """Define o idioma ativo para as próximas chamadas a `t()`."""
    global _current_language
    _current_language = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def get_language() -> str:
    """Retorna o código do idioma ativo no momento."""
    return _current_language


def t(key: str, **kwargs) -> str:
    """
    Traduz `key` para o idioma ativo, formatando com `kwargs` quando fornecidos.
    Cai para pt-br e, em último caso, para a própria chave, caso a tradução falte.
    """
    template = STRINGS.get(_current_language, {}).get(key)
    if template is None:
        template = STRINGS[DEFAULT_LANGUAGE].get(key, key)
    return template.format(**kwargs) if kwargs else template


_current_language = _load_saved_language()
