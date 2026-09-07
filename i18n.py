# -*- coding: utf-8 -*-
"""
i18n.py: Suporte a múltiplos idiomas para o invent-ssh.

Centraliza todos os textos exibidos ao usuário (interface e mensagens de log
enviadas à interface) em um único dicionário por idioma. O idioma ativo é
lido do `config.json` na inicialização e pode ser trocado pela aba
'Configurações' (requer reiniciar a aplicação para ser aplicado por completo).
"""
import json
import os
from typing import Dict

CONFIG_FILE = "config.json"
DEFAULT_LANGUAGE = "pt-br"
SUPPORTED_LANGUAGES = ("pt-br", "en")
LANGUAGE_DISPLAY_NAMES = {"pt-br": "Português (Brasil)", "en": "English"}

STRINGS: Dict[str, Dict[str, str]] = {
    "pt-br": {
        # --- Geral / Janela Principal ---
        "app_title": "Inventário de Hardware Linux via SSH",
        "tab_home": "Início",
        "tab_spreadsheet": "Modo Planilha",
        "tab_oracle": "Modo Oracle",
        "tab_settings": "Configurações",
        "tab_about": "Sobre",
        "run_button_default": "Iniciar Inventário",
        "run_button_spreadsheet": "▶ Iniciar Inventário via Planilha",
        "run_button_oracle": "▶ Iniciar Inventário via Oracle",
        "run_button_running": "Executando...",
        "run_button_tooltip": "Inicia o processo de coleta de dados com as configurações da aba atual.",

        # --- Modal de Boas-vindas ---
        "welcome_title": "Bem-vindo ao {app_name}!",
        "welcome_section1_title": "A Origem e o Código Aberto",
        "welcome_section1_body": "Esta aplicação nasceu de uma necessidade real: inventariar centenas de terminais Linux de forma rápida e confiável. O que era um script pessoal evoluiu para esta ferramenta, agora open-source, para que toda a comunidade possa se beneficiar de um processo automatizado e seguro.",
        "welcome_section2_title": "Conectividade de Rede: Como Funciona?",
        "welcome_section2_body": "Para que a mágica aconteça, seu computador precisa se comunicar com as máquinas Linux na rede via SSH (porta 22). Garanta que não haja um firewall bloqueando esta porta e que você esteja conectado na mesma rede que os terminais (seja via cabo, Wi-Fi ou VPN).",
        "welcome_section3_title": "Segurança é Inegociável",
        "welcome_section3_body": ("•  Suas credenciais são usadas apenas em memória durante a execução e NUNCA são salvas.\n"
                                   "•  Dê preferência ao uso de Chaves SSH. É o padrão da indústria e exponencialmente mais seguro que senhas.\n"
                                   "•  Execute o invent-ssh apenas em redes corporativas confiáveis. Evite redes públicas.\n"
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
        "home_welcome_text": ("Bem-vindo ao invent-ssh!\n\n"
                               "Automatize o inventário de hardware de seus computadores Linux de forma simples e segura.\n\n"
                               "Como Começar:\n\n"
                               "1. Escolha sua fonte de dados:\n"
                               "   •  Modo Planilha: Se você tem uma lista de IPs em um arquivo .xlsx ou .csv.\n"
                               "   •  Modo Oracle: Se seus ativos estão registrados em um banco de dados Oracle.\n\n"
                               "2. Forneça as credenciais de acesso SSH na aba escolhida.\n\n"
                               "3. Clique no botão 'Iniciar Inventário' e acompanhe o progresso em tempo real.\n\n"
                               "Dica: Na aba 'Modo Planilha', use o botão [?] para gerar um arquivo modelo e garantir a formatação correta."),

        # --- Aba Modo Planilha ---
        "spreadsheet_file_label": "Arquivo de Entrada (.xlsx ou .csv)*",
        "spreadsheet_help_tooltip": "Clique para criar um arquivo de planilha modelo (.xlsx).",
        "spreadsheet_file_placeholder": "Selecione o arquivo com a coluna obrigatória: IP (NROEMPRESA e NROCHECKOUT são opcionais)",
        "spreadsheet_file_tooltip": "Caminho para o arquivo de planilha.\nA coluna 'IP' é obrigatória. 'NROEMPRESA' e 'NROCHECKOUT' são opcionais.",
        "output_destination_label": "Destino dos Dados",
        "output_format_label": "Formato de Saída:",
        "spreadsheet_output_format_tooltip": "Escolha o formato do arquivo de relatório final.",
        "select_spreadsheet_title": "Selecionar planilha",
        "spreadsheet_filetype_label": "Planilha",
        "all_files_label": "Todos os arquivos",

        # --- Aba Modo Oracle ---
        "oracle_connection_title": "Conexão Oracle",
        "oracle_field_user": "Usuário*",
        "oracle_field_password": "Senha*",
        "oracle_field_host": "Host/IP*",
        "oracle_field_port": "Porta*",
        "oracle_field_service": "Service Name*",
        "oracle_field_tooltip": "Informação de '{label}' para conectar ao banco Oracle.",
        "oracle_save_to_db_checkbox": "Salvar resultados no banco de dados",
        "oracle_save_to_db_tooltip": "Se marcado, os resultados serão inseridos na tabela Oracle.\nSe desmarcado, será gerado um arquivo de planilha.",

        # --- Aba Configurações ---
        "settings_performance_title": "Performance e Execução",
        "settings_workers_label": "Processos Paralelos:",
        "settings_workers_tooltip": "Número máximo de computadores a serem processados simultaneamente.\nValores mais altos são mais rápidos, mas consomem mais recursos.",
        "settings_timeout_label": "Timeout SSH (segundos):",
        "settings_timeout_tooltip": "Tempo máximo em segundos para aguardar uma resposta de cada computador antes de desistir.",
        "settings_oracle_defaults_title": "Padrões do Modo Oracle",
        "settings_oracle_table_label": "Tabela Destino:",
        "settings_oracle_table_placeholder": "OWNER.TABELA",
        "settings_oracle_table_tooltip": "Define a tabela padrão de destino para salvar os dados no Modo Oracle.",
        "settings_oracle_query_label": "Query de Busca:",
        "settings_oracle_query_tooltip": "Define a query padrão para buscar os terminais no Modo Oracle. Apenas comandos SELECT são permitidos.",
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
        "help_modal_body": ("A precisão da coleta de dados depende das ferramentas instaladas no computador Linux de destino.\n\n"
                             "Esta aplicação foi projetada para ser **segura e não-invasiva**. Ela apenas lê informações que o sistema operacional já disponibiliza e não instala nada.\n\n"
                             "----------------------------------------------------------------\n"
                             "**Como Melhorar a Acuracidade da Coleta:**\n\n"
                             "Para garantir 100% de sucesso, o ideal é que os terminais possuam as ferramentas de diagnóstico adequadas. A aplicação tenta usar os seguintes comandos, em ordem de preferência:\n\n"
                             "1. `inxi` (O mais completo e preferencial)\n"
                             "2. `dmidecode` e `lshw`\n"
                             "3. Comandos do `util-linux` (`lscpu`, `lsblk`)\n"
                             "4. Leitura de arquivos do sistema (`/proc`, `/sys`)\n\n"
                             "----------------------------------------------------------------\n"
                             "**Ação Recomendada:**\n\n"
                             "Converse com sua equipe de infraestrutura sobre a possibilidade de incluir o pacote `inxi` na imagem padrão dos seus terminais Linux. Isso garantirá a coleta de dados mais rica e precisa possível, sem esforço adicional."),
        "help_modal_close_button": "Entendi",

        # --- Planilha Modelo ---
        "save_template_title": "Salvar Planilha Modelo",
        "excel_filetype_label": "Planilha Excel",
        "template_created_title": "Modelo Criado",
        "template_created_body": "A planilha modelo foi salva com sucesso em:\n{filepath}",
        "template_error_title": "Erro ao Criar Modelo",
        "template_error_body": "Ocorreu um erro:\n{error}",

        # --- Confirmação e Erros de Execução ---
        "confirm_oracle_title": "Confirmar Configurações Oracle",
        "confirm_oracle_body": ("Você está prestes a iniciar o inventário usando o banco de dados Oracle.\n\n"
                                 "**Tabela de Destino:**\n{table}\n\n"
                                 "**Query de Origem:**\n{query}\n\n"
                                 "Atenção: se a tabela de destino não existir, ela será criada automaticamente.\n\n"
                                 "Confirma as configurações e deseja continuar?"),
        "config_error_title": "Erro de Configuração",
        "unexpected_error_title": "Erro Inesperado",
        "unexpected_error_body": "Ocorreu um erro ao iniciar: {error}",
        "error_invalid_spreadsheet": "Por favor, selecione um arquivo de planilha válido. O caminho não foi encontrado.",
        "error_oracle_fields_required": "Por favor, preencha todas as credenciais de conexão Oracle.",
        "error_oracle_query_empty": "A Query de Busca na aba de Configurações não pode estar vazia.",
        "error_oracle_query_not_select": "A Query de Busca deve ser um comando SELECT. Comandos de escrita (INSERT/UPDATE/DELETE/DROP) não são permitidos.",
        "error_oracle_table_required": "A Tabela de Destino é obrigatória para salvar no banco de dados. Verifique as Configurações.",
        "error_oracle_table_invalid": "A Tabela de Destino informada em Configurações não é um identificador Oracle válido (use o formato OWNER.TABELA, apenas letras, números, '_', '$' e '#').",
        "error_ssh_user_required": "O campo 'Usuário SSH' é obrigatório.",
        "error_ssh_auth_required": "É obrigatório fornecer uma Senha SSH ou o caminho para uma Chave Privada.",
        "error_invalid_tab": "Aba de execução inválida. Selecione 'Modo Planilha' ou 'Modo Oracle'.",
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
        "mode_oracle": "Oracle",
        "log_starting": "Iniciando inventário em 'Modo {mode}'",
        "log_no_terminals": "Nenhum terminal encontrado. Processo abortado.",
        "log_terminals_loaded": "{count} terminais carregados. Iniciando coleta...",
        "log_no_data_collected": "Nenhum dado de hardware foi coletado.",
        "log_collection_finished": "Coleta finalizada. {count} resultados. Salvando...",
        "log_critical_engine_error": "Erro crítico no motor da aplicação: {error}",
        "log_process_finished": "Processo concluído!",
        "log_cancelled_by_user": "Cancelamento solicitado pelo usuário. Interrompendo terminais pendentes...",
        "log_unknown_mode": "Modo de operação desconhecido: {mode}",
        "log_missing_ip_column": "O arquivo deve conter a coluna 'IP'",
        "log_file_not_found": "Arquivo não encontrado: {filepath}",
        "log_spreadsheet_format_error": "Erro de formatação na planilha: {error}",
        "log_spreadsheet_read_error": "Falha ao ler planilha '{filename}': {error}",
        "log_oracledb_not_installed": "'oracledb' não está instalado. Modo Oracle desativado.",
        "log_oracle_connecting": "Conectando ao Oracle em {host}...",
        "log_oracle_running_query": "Executando query para buscar terminais...",
        "log_oracle_query_failed": "Falha na conexão ou consulta ao Oracle: {error}",
        "log_invalid_query_rejected": "Query de busca rejeitada: apenas comandos SELECT são permitidos.",
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
        "log_table_found": "Tabela '{table}' encontrada.",
        "log_table_not_found_creating": "Tabela '{table}' não encontrada. Tentando criar...",
        "log_table_created": "Tabela '{table}' criada com sucesso.",
        "log_table_create_failed": "Falha ao criar a tabela '{table}': {error}",
        "log_table_check_error": "Erro ao verificar a tabela '{table}': {error}",
        "log_invalid_table_identifier": "Tabela de destino '{table}' inválida. Abortado por segurança.",
        "log_table_creation_aborted": "Abortado: tabela '{table}' não pôde ser criada/encontrada.",
        "log_oracle_missing_keys_fallback": "Oracle: Registros sem NROEMPRESA/NROCHECKOUT. Salvando em planilha.",
        "log_oracle_records_saved": "{count} registros salvos/atualizados em '{table}'.",
        "log_oracle_batch_row_error": "Erro ao salvar registro #{offset} no Oracle: {error}",
        "log_oracle_save_critical_error": "Erro crítico ao salvar no Oracle: {error}",

        # --- Mensagens de Coleta de Hardware (inspector.py) ---
        "hw_info_unavailable": "Não foi possível obter",
        "hw_auth_failed": "Falha na autenticação",
        "hw_connection_timeout": "Timeout ao conectar no IP {ip}",
        "hw_ssh_error": "Erro SSH: {error}",
        "hw_key_not_found": "Chave SSH não encontrada: {key_path}",
        "hw_unknown_error": "Erro inesperado: {error}",
    },
    "en": {
        # --- General / Main Window ---
        "app_title": "Linux Hardware Inventory via SSH",
        "tab_home": "Home",
        "tab_spreadsheet": "Spreadsheet Mode",
        "tab_oracle": "Oracle Mode",
        "tab_settings": "Settings",
        "tab_about": "About",
        "run_button_default": "Start Inventory",
        "run_button_spreadsheet": "▶ Start Inventory via Spreadsheet",
        "run_button_oracle": "▶ Start Inventory via Oracle",
        "run_button_running": "Running...",
        "run_button_tooltip": "Starts the data collection process using the settings from the current tab.",

        # --- Welcome Modal ---
        "welcome_title": "Welcome to {app_name}!",
        "welcome_section1_title": "Origin and Open Source",
        "welcome_section1_body": "This application was born from a real need: inventorying hundreds of Linux terminals quickly and reliably. What started as a personal script evolved into this tool, now open-source, so the whole community can benefit from an automated and secure process.",
        "welcome_section2_title": "Network Connectivity: How It Works",
        "welcome_section2_body": "For everything to work, your computer needs to communicate with the Linux machines on the network via SSH (port 22). Make sure no firewall is blocking this port and that you're connected to the same network as the terminals (cable, Wi-Fi, or VPN).",
        "welcome_section3_title": "Security Is Non-Negotiable",
        "welcome_section3_body": ("•  Your credentials are used only in memory during execution and are NEVER saved.\n"
                                   "•  Prefer using SSH Keys. It's the industry standard and exponentially safer than passwords.\n"
                                   "•  Run invent-ssh only on trusted corporate networks. Avoid public networks.\n"
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
        "home_welcome_text": ("Welcome to invent-ssh!\n\n"
                               "Automate the hardware inventory of your Linux computers, simply and securely.\n\n"
                               "Getting Started:\n\n"
                               "1. Choose your data source:\n"
                               "   •  Spreadsheet Mode: If you have a list of IPs in a .xlsx or .csv file.\n"
                               "   •  Oracle Mode: If your assets are registered in an Oracle database.\n\n"
                               "2. Provide the SSH access credentials in the chosen tab.\n\n"
                               "3. Click the 'Start Inventory' button and follow the progress in real time.\n\n"
                               "Tip: On the 'Spreadsheet Mode' tab, use the [?] button to generate a template file with the correct formatting."),

        # --- Spreadsheet Mode Tab ---
        "spreadsheet_file_label": "Input File (.xlsx or .csv)*",
        "spreadsheet_help_tooltip": "Click to create a template spreadsheet file (.xlsx).",
        "spreadsheet_file_placeholder": "Select the file with the required column: IP (NROEMPRESA and NROCHECKOUT are optional)",
        "spreadsheet_file_tooltip": "Path to the spreadsheet file.\nThe 'IP' column is required. 'NROEMPRESA' and 'NROCHECKOUT' are optional.",
        "output_destination_label": "Data Destination",
        "output_format_label": "Output Format:",
        "spreadsheet_output_format_tooltip": "Choose the format of the final report file.",
        "select_spreadsheet_title": "Select spreadsheet",
        "spreadsheet_filetype_label": "Spreadsheet",
        "all_files_label": "All files",

        # --- Oracle Mode Tab ---
        "oracle_connection_title": "Oracle Connection",
        "oracle_field_user": "User*",
        "oracle_field_password": "Password*",
        "oracle_field_host": "Host/IP*",
        "oracle_field_port": "Port*",
        "oracle_field_service": "Service Name*",
        "oracle_field_tooltip": "'{label}' information to connect to the Oracle database.",
        "oracle_save_to_db_checkbox": "Save results to the database",
        "oracle_save_to_db_tooltip": "If checked, results will be inserted into the Oracle table.\nIf unchecked, a spreadsheet file will be generated.",

        # --- Settings Tab ---
        "settings_performance_title": "Performance and Execution",
        "settings_workers_label": "Parallel Processes:",
        "settings_workers_tooltip": "Maximum number of computers to be processed simultaneously.\nHigher values are faster but consume more resources.",
        "settings_timeout_label": "SSH Timeout (seconds):",
        "settings_timeout_tooltip": "Maximum time in seconds to wait for a response from each computer before giving up.",
        "settings_oracle_defaults_title": "Oracle Mode Defaults",
        "settings_oracle_table_label": "Target Table:",
        "settings_oracle_table_placeholder": "OWNER.TABLE",
        "settings_oracle_table_tooltip": "Defines the default target table for saving data in Oracle Mode.",
        "settings_oracle_query_label": "Search Query:",
        "settings_oracle_query_tooltip": "Defines the default query used to look up terminals in Oracle Mode. Only SELECT statements are allowed.",
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
        "help_modal_body": ("Data collection accuracy depends on the tools installed on the target Linux computer.\n\n"
                             "This application is designed to be **safe and non-invasive**. It only reads information the operating system already makes available and installs nothing.\n\n"
                             "----------------------------------------------------------------\n"
                             "**How to Improve Collection Accuracy:**\n\n"
                             "To guarantee 100% success, terminals should ideally have the proper diagnostic tools installed. The application tries the following commands, in order of preference:\n\n"
                             "1. `inxi` (the most complete and preferred)\n"
                             "2. `dmidecode` and `lshw`\n"
                             "3. `util-linux` commands (`lscpu`, `lsblk`)\n"
                             "4. Reading system files (`/proc`, `/sys`)\n\n"
                             "----------------------------------------------------------------\n"
                             "**Recommended Action:**\n\n"
                             "Talk to your infrastructure team about including the `inxi` package in your Linux terminals' standard image. This will ensure the richest and most accurate data collection possible, with no extra effort."),
        "help_modal_close_button": "Got it",

        # --- Template Spreadsheet ---
        "save_template_title": "Save Template Spreadsheet",
        "excel_filetype_label": "Excel Spreadsheet",
        "template_created_title": "Template Created",
        "template_created_body": "The template spreadsheet was saved successfully at:\n{filepath}",
        "template_error_title": "Error Creating Template",
        "template_error_body": "An error occurred:\n{error}",

        # --- Confirmation and Execution Errors ---
        "confirm_oracle_title": "Confirm Oracle Settings",
        "confirm_oracle_body": ("You are about to start the inventory using the Oracle database.\n\n"
                                 "**Target Table:**\n{table}\n\n"
                                 "**Source Query:**\n{query}\n\n"
                                 "Note: if the target table doesn't exist, it will be created automatically.\n\n"
                                 "Do you confirm these settings and want to continue?"),
        "config_error_title": "Configuration Error",
        "unexpected_error_title": "Unexpected Error",
        "unexpected_error_body": "An error occurred while starting: {error}",
        "error_invalid_spreadsheet": "Please select a valid spreadsheet file. The path was not found.",
        "error_oracle_fields_required": "Please fill in all Oracle connection credentials.",
        "error_oracle_query_empty": "The Search Query in the Settings tab cannot be empty.",
        "error_oracle_query_not_select": "The Search Query must be a SELECT statement. Write commands (INSERT/UPDATE/DELETE/DROP) are not allowed.",
        "error_oracle_table_required": "The Target Table is required to save to the database. Check Settings.",
        "error_oracle_table_invalid": "The Target Table set in Settings is not a valid Oracle identifier (use the OWNER.TABLE format, only letters, digits, '_', '$' and '#').",
        "error_ssh_user_required": "The 'SSH User' field is required.",
        "error_ssh_auth_required": "You must provide either an SSH Password or the path to a Private Key.",
        "error_invalid_tab": "Invalid execution tab. Select 'Spreadsheet Mode' or 'Oracle Mode'.",
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
        "mode_oracle": "Oracle",
        "log_starting": "Starting inventory in '{mode} Mode'",
        "log_no_terminals": "No terminals found. Process aborted.",
        "log_terminals_loaded": "{count} terminals loaded. Starting collection...",
        "log_no_data_collected": "No hardware data was collected.",
        "log_collection_finished": "Collection finished. {count} results. Saving...",
        "log_critical_engine_error": "Critical error in the application engine: {error}",
        "log_process_finished": "Process completed!",
        "log_cancelled_by_user": "Cancellation requested by the user. Stopping pending terminals...",
        "log_unknown_mode": "Unknown operation mode: {mode}",
        "log_missing_ip_column": "The file must contain the 'IP' column",
        "log_file_not_found": "File not found: {filepath}",
        "log_spreadsheet_format_error": "Spreadsheet formatting error: {error}",
        "log_spreadsheet_read_error": "Failed to read spreadsheet '{filename}': {error}",
        "log_oracledb_not_installed": "'oracledb' is not installed. Oracle Mode disabled.",
        "log_oracle_connecting": "Connecting to Oracle at {host}...",
        "log_oracle_running_query": "Running query to fetch terminals...",
        "log_oracle_query_failed": "Failed to connect to or query Oracle: {error}",
        "log_invalid_query_rejected": "Search query rejected: only SELECT statements are allowed.",
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
        "log_table_found": "Table '{table}' found.",
        "log_table_not_found_creating": "Table '{table}' not found. Attempting to create it...",
        "log_table_created": "Table '{table}' created successfully.",
        "log_table_create_failed": "Failed to create table '{table}': {error}",
        "log_table_check_error": "Error checking table '{table}': {error}",
        "log_invalid_table_identifier": "Invalid target table '{table}'. Aborted for safety.",
        "log_table_creation_aborted": "Aborted: table '{table}' could not be created/found.",
        "log_oracle_missing_keys_fallback": "Oracle: Records without NROEMPRESA/NROCHECKOUT. Saving to spreadsheet instead.",
        "log_oracle_records_saved": "{count} records saved/updated in '{table}'.",
        "log_oracle_batch_row_error": "Error saving record #{offset} to Oracle: {error}",
        "log_oracle_save_critical_error": "Critical error saving to Oracle: {error}",

        # --- Hardware Collection Messages (inspector.py) ---
        "hw_info_unavailable": "Could not be obtained",
        "hw_auth_failed": "Authentication failed",
        "hw_connection_timeout": "Timeout connecting to IP {ip}",
        "hw_ssh_error": "SSH error: {error}",
        "hw_key_not_found": "SSH key not found: {key_path}",
        "hw_unknown_error": "Unexpected error: {error}",
    },
}


def _load_saved_language() -> str:
    """Lê a preferência de idioma diretamente do config.json, sem depender da GUI."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            lang = json.load(f).get("language", DEFAULT_LANGUAGE)
            return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return DEFAULT_LANGUAGE


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
