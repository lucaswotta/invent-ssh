"""
app.py: A Interface Gráfica Principal (GUI) do invent-ssh.

Este módulo contém a classe `App`, que orquestra a interface do usuário
construída com CustomTkinter. Ele gerencia as diferentes abas de operação
(Planilha, Oracle), coleta as configurações do usuário e inicia o motor
de inventário (`InventoryEngine`).
"""
# --- Módulos Padrão e de Terceiros ---
import sys
import subprocess
import threading
import queue
import json
import os
import glob
import platform
import traceback
import re
import webbrowser
import logging
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Optional, Dict, Any

# i18n depende apenas da stdlib, então pode ser importado incondicionalmente
# mesmo antes da checagem de dependências de terceiros.
from i18n import t, set_language, get_language, DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, LANGUAGE_DISPLAY_NAMES

# --- Importações condicionais para dependências ---
# Esta estrutura garante que a verificação de dependências ocorra
# antes de tentar importar os módulos necessários para a GUI.
try:
    import customtkinter as ctk
    import pandas as pd
    from core import InventoryEngine, is_select_only_query, is_valid_oracle_identifier
except ImportError:
    # As importações serão tratadas pelo verificador de dependências.
    # Se falhar, a aplicação não continuará.
    ctk = None
    pd = None
    InventoryEngine = None
    is_select_only_query = None
    is_valid_oracle_identifier = None

# --- Constantes da Aplicação ---
APP_VERSION = "0.2" # Versão Beta
APP_NAME = "invent-ssh"
CONFIG_FILE = "config.json"
ICON_FILE = "app.ico"

# --- Constantes de Configuração Padrão ---
DEFAULT_ORACLE_QUERY = "SELECT IP, NROEMPRESA, NROCHECKOUT FROM CONSINCOMONITOR.TB_CHECKOUT WHERE ATIVO = 'S' AND SO = 'L'"
DEFAULT_ORACLE_TABLE = "CONSINCO.BAR_HARDWARE_PDV"

# --- Tema e Estilo da Aplicação ---
THEME = {
    "font_family": "Segoe UI",
    "font_h1": ("Segoe UI", 22, "bold"),
    "font_h2": ("Segoe UI", 16, "bold"),
    "font_body": ("Segoe UI", 13),
    "font_label": ("Segoe UI", 13, "bold"),
    "font_mono": ("Consolas", 12),
    "padding": 15,
    "padding_sm": 10,
    "link_color": "#60a5fa"
}

# --- Funções Auxiliares ---

def resource_path(relative_path: str) -> str:
    """
    Obtém o caminho absoluto para um recurso, garantindo compatibilidade
    com o ambiente de desenvolvimento e o executável do PyInstaller.

    Args:
        relative_path: O caminho relativo do recurso a partir da raiz.

    Returns:
        O caminho absoluto para o recurso.
    """
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Em ambiente de desenvolvimento, o caminho base é o diretório atual
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def check_and_install_dependencies():
    """
    Verifica se as dependências necessárias estão instaladas e, se não,
    pergunta ao usuário se deseja instalá-las via pip.
    """
    required_packages = {
        'customtkinter': 'customtkinter',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl',
        'paramiko': 'paramiko',
        'oracledb': 'oracledb'
    }
    try:
        from importlib import util
        missing_packages = [pkg for pkg, mod in required_packages.items() if not util.find_spec(mod)]
    except ImportError:
        # Fallback para ambientes mais antigos
        import pkgutil
        missing_packages = [pkg for pkg, mod in required_packages.items() if not pkgutil.find_loader(mod)]

    if not missing_packages:
        return True

    # Usa o Tkinter nativo para o diálogo, pois o customtkinter pode não estar instalado
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()

    msg = t("missing_deps_body", packages=', '.join(missing_packages))

    if messagebox.askyesno(t("missing_deps_title"), msg):
        try:
            # Tenta instalar os pacotes ausentes usando pip
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
            messagebox.showinfo(t("deps_install_success_title"), t("deps_install_success_body"))
        except Exception as e:
            messagebox.showerror(t("deps_install_error_title"), t("deps_install_error_body", error=e, packages=' '.join(missing_packages)))
        return False  # Requer reinicialização
    else:
        messagebox.showwarning(t("deps_skip_warning_title"), t("deps_skip_warning_body"))
        return True # Permite continuar, mas pode falhar

# --- Classes da UI ---

class BaseModal(ctk.CTkToplevel):
    """Classe base para janelas modais, garantindo consistência visual e comportamento."""
    def __init__(self, master, title: str, geometry: str, resizable: bool = False):
        super().__init__(master)
        self.title(title)
        self.geometry(geometry)
        self.resizable(resizable, resizable)
        self.transient(master)  # Mantém o modal sempre à frente da janela principal
        self.grab_set()         # Captura o foco, impedindo interação com a janela principal

        icon_path = resource_path(ICON_FILE)
        if os.path.exists(icon_path):
            self.after(200, lambda: self.iconbitmap(icon_path))

        self.grid_columnconfigure(0, weight=1)

class WelcomeModal(BaseModal):
    """Modal de boas-vindas com foco na proposta de valor, segurança e usabilidade."""
    def __init__(self, master, config: dict):
        super().__init__(master, t("welcome_title", app_name=APP_NAME), "750x550")
        self.master = master
        self.config = config

        self.protocol("WM_DELETE_WINDOW", self.on_closing_attempt)
        self.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=THEME["padding"], pady=THEME["padding"], sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)

        def create_section(parent, title, content):
            ctk.CTkLabel(parent, text=title, font=THEME["font_h2"], anchor="w").pack(fill="x", pady=(15, 5), padx=10)
            ctk.CTkLabel(parent, text=content, font=THEME["font_body"], anchor="w", justify="left", wraplength=680).pack(fill="x", padx=10, pady=(0, 10))

        create_section(main_frame, t("welcome_section1_title"), t("welcome_section1_body"))
        create_section(main_frame, t("welcome_section2_title"), t("welcome_section2_body"))
        create_section(main_frame, t("welcome_section3_title"), t("welcome_section3_body"))

        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.grid(row=1, column=0, padx=THEME["padding"], pady=(0, THEME["padding"]), sticky="ew")
        footer_frame.grid_columnconfigure(0, weight=1)

        self.show_again_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(footer_frame, text=t("welcome_checkbox_dont_show"), variable=self.show_again_var, onvalue=False, offvalue=True, font=THEME["font_body"]).grid(row=0, column=0, padx=5, sticky="w")
        ctk.CTkButton(footer_frame, text=t("welcome_button_start"), command=self.close_modal).grid(row=0, column=1, padx=5, sticky="e")

    def on_closing_attempt(self):
        """Impede o fechamento acidental da janela de boas-vindas."""
        pass

    def close_modal(self):
        """Fecha o modal e salva a preferência do usuário sobre exibi-lo novamente."""
        self.master.config["show_welcome_modal"] = self.show_again_var.get()
        self.destroy()

class Tooltip:
    """Tooltip aprimorado para fornecer ajuda contextual instantânea sobre os widgets."""
    def __init__(self, widget, text: str, delay_ms: int = 800):
        self.widget = widget
        self.text = text
        self.delay = delay_ms
        self.tooltip_window = None
        self.after_id = None
        self.widget.bind("<Enter>", self.schedule_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
        self.widget.bind("<Button-1>", self.hide_tooltip)

    def schedule_tooltip(self, event=None):
        """Agenda a exibição do tooltip após um certo delay."""
        self.hide_tooltip()
        if self.text:
            self.after_id = self.widget.after(self.delay, self._show_tooltip)

    def _show_tooltip(self):
        """Cria e exibe a janela do tooltip próximo ao widget."""
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(self.tooltip_window, text=self.text, corner_radius=4, fg_color=("#333333", "#444444"), font=("Segoe UI", 11))
        label.pack(ipadx=5, ipady=3)

    def hide_tooltip(self, event=None):
        """Esconde e destrói o tooltip."""
        if self.after_id:
            self.widget.after_cancel(self.after_id)
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.after_id = None
        self.tooltip_window = None

class LogModal(BaseModal):
    """
    Modal de progresso que exibe logs em tempo real, uma barra de progresso
    e controla a interação do usuário durante a execução do inventário.
    """
    def __init__(self, master):
        super().__init__(master, t("log_modal_title_running"), "700x400")
        self.master = master
        self.log_queue = master.log_queue

        self.grid_rowconfigure(1, weight=1)
        self.progress_bar = ctk.CTkProgressBar(self, height=12)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, padx=THEME["padding_sm"], pady=(THEME["padding_sm"], 5), sticky="ew")

        self.log_textbox = ctk.CTkTextbox(self, font=THEME["font_mono"], state="disabled")
        self.log_textbox.grid(row=1, column=0, padx=THEME["padding_sm"], pady=(0, THEME["padding_sm"]), sticky="nsew")

        self.close_button = ctk.CTkButton(self, text=t("log_modal_close_button"), command=self.destroy, state="disabled")
        self.close_button.grid(row=2, column=0, padx=THEME["padding_sm"], pady=(5, THEME["padding_sm"]), sticky="ew")

        self.protocol("WM_DELETE_WINDOW", self.on_closing_attempt)
        self.process_log_queue()

    def process_log_queue(self):
        """Processa mensagens da fila de logs e atualiza a UI periodicamente."""
        try:
            while not self.log_queue.empty():
                level, message, value = self.log_queue.get_nowait()
                if level != "PROGRESS":
                    self.add_log(level, message)

                if level == "PROGRESS" and value is not None:
                    self.progress_bar.set(value / 100)
                elif level == "FINISH":
                    self.finish_process(message)
                elif level == "OPEN_FILE":
                    self.master.open_file(value)
        finally:
            self.after(150, self.process_log_queue)

    def add_log(self, level, message):
        """Adiciona uma nova linha de log ao textbox."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"[{timestamp}] [{level}] {message}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def finish_process(self, final_message):
        """Finaliza o modal, habilitando o botão de fechar e exibindo um pop-up."""
        self.title(t("log_modal_title_finished"))
        self.progress_bar.set(1.0)
        self.master.reset_ui()
        self.close_button.configure(state="normal")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        messagebox.showinfo(t("log_modal_finished_title"), final_message, parent=self)
        self.grab_set()

    def on_closing_attempt(self):
        """Impede que o usuário feche o modal enquanto o processo está rodando."""
        messagebox.showwarning(t("log_modal_close_warning_title"), t("log_modal_close_warning_body"), parent=self)
        self.grab_set()

class SSHCredentialsFrame(ctk.CTkFrame):
    """Componente reutilizável para entrada de credenciais SSH, focado em clareza e usabilidade."""
    def __init__(self, master, config: dict):
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=t("ssh_credentials_title"), font=THEME["font_h2"]).grid(row=0, column=0, columnspan=3, sticky="w", pady=(THEME["padding_sm"], 5))

        ctk.CTkLabel(self, text=t("ssh_user_label"), font=THEME["font_body"]).grid(row=1, column=0, sticky="w")
        self.ssh_user_entry = ctk.CTkEntry(self, font=THEME["font_body"])
        self.ssh_user_entry.insert(0, self.config.get("last_ssh_user", ""))
        self.ssh_user_entry.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, THEME["padding_sm"]))
        Tooltip(self.ssh_user_entry, t("ssh_user_tooltip"))

        self.ssh_pass_entry = ctk.CTkEntry(self, show="*", placeholder_text=t("ssh_pass_placeholder"), font=THEME["font_body"])
        self.ssh_pass_entry.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, THEME["padding_sm"]))
        Tooltip(self.ssh_pass_entry, t("ssh_pass_tooltip"))

        key_frame = ctk.CTkFrame(self, fg_color="transparent")
        key_frame.grid(row=4, column=0, columnspan=3, sticky="ew")
        key_frame.grid_columnconfigure(0, weight=1)

        self.ssh_key_entry = ctk.CTkEntry(key_frame, placeholder_text=t("ssh_key_placeholder"), font=THEME["font_body"])
        self.ssh_key_entry.insert(0, self.config.get("last_ssh_key_path", ""))
        self.ssh_key_entry.grid(row=0, column=0, sticky="ew")
        Tooltip(self.ssh_key_entry, t("ssh_key_tooltip"))

        self.browse_key_button = ctk.CTkButton(key_frame, text=t("browse_button"), width=120, command=self.browse_key_file)
        self.browse_key_button.grid(row=0, column=1, padx=(10, 0))

    def browse_key_file(self):
        """Abre uma janela para o usuário selecionar o arquivo da chave SSH privada."""
        filepath = filedialog.askopenfilename(title=t("select_ssh_key_title"))
        if filepath:
            self.ssh_key_entry.delete(0, "end")
            self.ssh_key_entry.insert(0, filepath)

    def get_credentials(self) -> Dict[str, str]:
        """
        Coleta e retorna as credenciais SSH preenchidas nos campos.

        Returns:
            Um dicionário com as credenciais 'user', 'pass' e 'key_path'.
        """
        return {
            "user": self.ssh_user_entry.get().strip(),
            "pass": self.ssh_pass_entry.get(),
            "key_path": self.ssh_key_entry.get().strip()
        }

class App(ctk.CTk):
    """
    Classe principal da aplicação que gerencia a janela, widgets e eventos.

    Orquestra a experiência do usuário, desde a tela de boas-vindas até o início
    do processo de inventário e o feedback visual através do modal de logs.
    """
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("820x680")
        self.minsize(820, 680)
        self.resizable(True, True)

        icon_path = resource_path(ICON_FILE)
        if os.path.exists(icon_path):
            self.iconbitmap(icon_path)

        self.is_running = False
        self.current_engine: Optional[InventoryEngine] = None
        self.log_queue = queue.Queue()
        self.config = self.load_config()
        set_language(self.config.get("language", DEFAULT_LANGUAGE))

        self.create_widgets()
        self.center_window()
        self.setup_real_time_validation()
        self.after(100, self.on_tab_change) # Garante que a UI seja atualizada na primeira exibição
        self.after(200, self.show_welcome_modal_if_needed)

    def center_window(self):
        """Centraliza a janela principal na tela do usuário."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def show_welcome_modal_if_needed(self):
        """Exibe o modal de boas-vindas se o usuário não o desativou."""
        if self.config.get("show_welcome_modal", True):
            welcome = WelcomeModal(self, self.config)
            self.wait_window(welcome) # Pausa a execução até o modal ser fechado

    def create_widgets(self):
        """Cria e organiza todos os widgets da janela principal."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=THEME["padding"], pady=(THEME["padding"], 6), sticky="ew")
        ctk.CTkLabel(header_frame, text=t("app_title"), font=THEME["font_h1"]).pack(pady=5)

        # Os rótulos das abas são traduzidos, mas a lógica interna nunca compara contra
        # esse texto diretamente: usamos `self.tab_labels`/`self.tab_key_by_label` para
        # mapear de volta a uma chave estável ("home", "spreadsheet", ...), independente
        # do idioma ativo.
        self.tab_labels = {
            "home": t("tab_home"),
            "spreadsheet": t("tab_spreadsheet"),
            "oracle": t("tab_oracle"),
            "settings": t("tab_settings"),
            "about": t("tab_about"),
        }
        self.tab_key_by_label = {label: key for key, label in self.tab_labels.items()}

        self.tab_view = ctk.CTkTabview(self, command=self.on_tab_change)
        self.tab_view.grid(row=1, column=0, padx=THEME["padding"], pady=6, sticky="nsew")
        for label in self.tab_labels.values():
            self.tab_view.add(label)

        self.create_inicio_tab()
        self.create_spreadsheet_tab()
        self.create_oracle_tab()
        self.create_config_tab()
        self.create_sobre_tab()

        self.run_button = ctk.CTkButton(self, text=t("run_button_default"), height=45, font=("Segoe UI", 18, "bold"), command=self.start_inventory_thread)
        self.run_button.grid(row=2, column=0, padx=THEME["padding"], pady=(12, THEME["padding"]), sticky="ew")
        Tooltip(self.run_button, t("run_button_tooltip"))

    def get_active_tab_key(self) -> str:
        """Retorna a chave estável ('home', 'spreadsheet', ...) da aba atualmente selecionada."""
        return self.tab_key_by_label.get(self.tab_view.get())

    def on_tab_change(self, tab_name=None):
        """Chamado quando o usuário troca de aba para atualizar a UI."""
        # 'after_idle' garante que a aba tenha sido totalmente renderizada antes de fazer alterações
        self.after_idle(self._update_ui_for_tab)

    def _update_ui_for_tab(self):
        """Atualiza o texto do botão principal e sua visibilidade com base na aba selecionada."""
        try:
            selected_key = self.get_active_tab_key()
            if selected_key == "spreadsheet":
                self.run_button.configure(text=t("run_button_spreadsheet"))
                self.run_button.grid()
            elif selected_key == "oracle":
                self.run_button.configure(text=t("run_button_oracle"))
                self.run_button.grid()
            else:
                self.run_button.grid_remove() # Oculta o botão em abas não executáveis
        except Exception:
            # Garante que o botão seja oculto em caso de erro
            self.run_button.grid_remove()

    def create_inicio_tab(self):
        """Cria os widgets da aba 'Início'."""
        tab = self.tab_view.tab(self.tab_labels["home"])
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=30, pady=30, sticky="nsew")

        textbox = ctk.CTkTextbox(main_frame, font=THEME["font_body"], wrap="word", fg_color="transparent")
        textbox.insert("1.0", t("home_welcome_text"))
        textbox.configure(state="disabled")
        textbox.pack(expand=True, fill="both", pady=10)

    def create_spreadsheet_tab(self):
        """Cria os widgets da aba 'Modo Planilha'."""
        tab = self.tab_view.tab(self.tab_labels["spreadsheet"])
        tab.grid_columnconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, padx=THEME["padding"], pady=THEME["padding"], sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1)

        file_header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        file_header_frame.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))
        ctk.CTkLabel(file_header_frame, text=t("spreadsheet_file_label"), font=THEME["font_h2"]).pack(side="left")
        help_button = ctk.CTkButton(file_header_frame, text="?", width=28, height=28, command=self.create_template_spreadsheet)
        help_button.pack(side="left", padx=(10, 0))
        Tooltip(help_button, t("spreadsheet_help_tooltip"))

        self.file_entry = ctk.CTkEntry(main_frame, placeholder_text=t("spreadsheet_file_placeholder"), font=THEME["font_body"])
        self.file_entry.insert(0, self.config.get("last_file_path", ""))
        self.file_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, THEME["padding"]))
        Tooltip(self.file_entry, t("spreadsheet_file_tooltip"))

        browse_button = ctk.CTkButton(main_frame, text=t("browse_button"), width=120, command=self.browse_file)
        browse_button.grid(row=1, column=2, padx=(10, 0), pady=(0, THEME["padding"]))

        self.ssh_widgets_planilha = SSHCredentialsFrame(main_frame, self.config)
        self.ssh_widgets_planilha.grid(row=2, column=0, columnspan=3, sticky="ew")

        ctk.CTkLabel(main_frame, text=t("output_destination_label"), font=THEME["font_h2"]).grid(row=3, column=0, columnspan=3, sticky="w", pady=(THEME["padding"], 5))
        ctk.CTkLabel(main_frame, text=t("output_format_label"), font=THEME["font_body"]).grid(row=4, column=0, sticky="w")
        self.spreadsheet_output_format_var = ctk.StringVar(value=self.config.get("spreadsheet_format", "XLSX"))
        spreadsheet_output_menu = ctk.CTkOptionMenu(main_frame, variable=self.spreadsheet_output_format_var, values=["XLSX", "CSV"])
        spreadsheet_output_menu.grid(row=4, column=1, sticky="w", columnspan=2)
        Tooltip(spreadsheet_output_menu, t("spreadsheet_output_format_tooltip"))

    def create_oracle_tab(self):
        """Cria os widgets da aba 'Modo Oracle'."""
        tab = self.tab_view.tab(self.tab_labels["oracle"])
        tab.grid_columnconfigure((0, 1), weight=1, uniform="group1")

        connections_frame = ctk.CTkFrame(tab)
        connections_frame.grid(row=0, column=0, padx=(THEME["padding"], 7), pady=THEME["padding"], sticky="nsew")
        connections_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(connections_frame, text=t("oracle_connection_title"), font=THEME["font_h2"]).grid(row=0, column=0, columnspan=2, padx=THEME["padding_sm"], pady=(THEME["padding_sm"],5), sticky="w")

        self.oracle_entries = {}
        oracle_fields = [("USER", t("oracle_field_user")), ("PASSWORD", t("oracle_field_password")), ("HOST", t("oracle_field_host")), ("PORT", t("oracle_field_port")), ("SERVICE", t("oracle_field_service"))]
        for i, (key, label) in enumerate(oracle_fields):
            ctk.CTkLabel(connections_frame, text=f"{label}:", font=THEME["font_body"]).grid(row=i+1, column=0, padx=THEME["padding_sm"], pady=5, sticky="w")
            entry = ctk.CTkEntry(connections_frame, show="*" if key == "PASSWORD" else None, font=THEME["font_body"])
            default_val = self.config.get(f"oracle_{key.lower()}", "1521" if key == "PORT" else "")
            if key != "PASSWORD": entry.insert(0, default_val)
            entry.grid(row=i+1, column=1, padx=THEME["padding_sm"], pady=5, sticky="ew")
            self.oracle_entries[key.lower()] = entry
            Tooltip(entry, t("oracle_field_tooltip", label=label.replace('*', '')))

        ssh_dest_frame = ctk.CTkFrame(tab)
        ssh_dest_frame.grid(row=0, column=1, padx=(7, THEME["padding"]), pady=THEME["padding"], sticky="nsew")
        ssh_dest_frame.grid_columnconfigure(0, weight=1)

        self.ssh_widgets_oracle = SSHCredentialsFrame(ssh_dest_frame, self.config)
        self.ssh_widgets_oracle.grid(row=0, column=0, sticky="ew", padx=THEME["padding_sm"])

        ctk.CTkLabel(ssh_dest_frame, text=t("output_destination_label"), font=THEME["font_h2"]).grid(row=1, column=0, padx=THEME["padding_sm"], pady=(15,5), sticky="w")
        self.oracle_save_to_db_var = ctk.BooleanVar(value=self.config.get("save_to_db", True))
        oracle_db_checkbox = ctk.CTkCheckBox(ssh_dest_frame, text=t("oracle_save_to_db_checkbox"), variable=self.oracle_save_to_db_var, command=self.toggle_oracle_output_format, font=THEME["font_body"])
        oracle_db_checkbox.grid(row=2, column=0, padx=THEME["padding_sm"], pady=5, sticky="w")
        Tooltip(oracle_db_checkbox, t("oracle_save_to_db_tooltip"))

        self.oracle_output_format_label = ctk.CTkLabel(ssh_dest_frame, text=t("output_format_label"), font=THEME["font_body"])
        self.oracle_output_format_var = ctk.StringVar(value=self.config.get("oracle_output_format", "XLSX"))
        self.oracle_output_menu = ctk.CTkOptionMenu(ssh_dest_frame, variable=self.oracle_output_format_var, values=["XLSX", "CSV"])
        self.toggle_oracle_output_format()

    def create_config_tab(self):
        """Cria os widgets da aba 'Configurações'."""
        tab = self.tab_view.tab(self.tab_labels["settings"])
        tab.grid_columnconfigure(0, weight=1)
        main_frame = ctk.CTkFrame(tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=THEME["padding"], pady=THEME["padding"])
        main_frame.grid_columnconfigure(0, weight=1)

        perf_frame = ctk.CTkFrame(main_frame)
        perf_frame.grid(row=0, column=0, sticky="ew", pady=(0, THEME["padding"]))
        perf_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(perf_frame, text=t("settings_performance_title"), font=THEME["font_h2"]).grid(row=0, column=0, columnspan=3, pady=THEME["padding_sm"], padx=THEME["padding_sm"], sticky="w")

        ctk.CTkLabel(perf_frame, text=t("settings_workers_label"), font=THEME["font_body"]).grid(row=1, column=0, sticky="w", padx=(15,10))
        self.workers_slider = ctk.CTkSlider(perf_frame, from_=1, to=50, number_of_steps=49)
        self.workers_slider.set(self.config.get("max_workers", 15))
        self.workers_slider.grid(row=1, column=1, sticky="ew")
        self.workers_label = ctk.CTkLabel(perf_frame, text=f"{int(self.workers_slider.get())}", width=40, font=THEME["font_body"])
        self.workers_label.grid(row=1, column=2, padx=(10, 15))
        self.workers_slider.configure(command=lambda v: self.workers_label.configure(text=f"{int(v)}"))
        Tooltip(self.workers_slider, t("settings_workers_tooltip"))

        ctk.CTkLabel(perf_frame, text=t("settings_timeout_label"), font=THEME["font_body"]).grid(row=2, column=0, sticky="w", padx=(15,10), pady=(15, 15))
        self.timeout_slider = ctk.CTkSlider(perf_frame, from_=5, to=60, number_of_steps=11)
        self.timeout_slider.set(self.config.get("ssh_timeout", 30))
        self.timeout_slider.grid(row=2, column=1, sticky="ew", pady=(15, 15))
        self.timeout_label = ctk.CTkLabel(perf_frame, text=f"{int(self.timeout_slider.get())}s", width=40, font=THEME["font_body"])
        self.timeout_label.grid(row=2, column=2, padx=(10, 15), pady=(15, 15))
        self.timeout_slider.configure(command=lambda v: self.timeout_label.configure(text=f"{int(v)}s"))
        Tooltip(self.timeout_slider, t("settings_timeout_tooltip"))

        oracle_defaults_frame = ctk.CTkFrame(main_frame)
        oracle_defaults_frame.grid(row=1, column=0, sticky="ew", pady=(0, THEME["padding"]))
        oracle_defaults_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(oracle_defaults_frame, text=t("settings_oracle_defaults_title"), font=THEME["font_h2"]).grid(row=0, column=0, columnspan=2, pady=THEME["padding_sm"], padx=THEME["padding_sm"], sticky="w")

        ctk.CTkLabel(oracle_defaults_frame, text=t("settings_oracle_table_label"), font=THEME["font_body"]).grid(row=1, column=0, sticky="w", padx=15)
        self.config_oracle_table_entry = ctk.CTkEntry(oracle_defaults_frame, placeholder_text=t("settings_oracle_table_placeholder"), font=THEME["font_body"])
        self.config_oracle_table_entry.insert(0, self.config.get("oracle_table", DEFAULT_ORACLE_TABLE))
        self.config_oracle_table_entry.grid(row=1, column=1, sticky="ew", padx=(10, 15))
        Tooltip(self.config_oracle_table_entry, t("settings_oracle_table_tooltip"))

        ctk.CTkLabel(oracle_defaults_frame, text=t("settings_oracle_query_label"), font=THEME["font_body"]).grid(row=2, column=0, sticky="w", pady=(10, 0), padx=15)
        self.config_oracle_query_textbox = ctk.CTkTextbox(oracle_defaults_frame, height=80, font=THEME["font_mono"])
        self.config_oracle_query_textbox.insert("1.0", self.config.get("oracle_query", DEFAULT_ORACLE_QUERY))
        self.config_oracle_query_textbox.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))
        Tooltip(self.config_oracle_query_textbox, t("settings_oracle_query_tooltip"))

        language_frame = ctk.CTkFrame(main_frame)
        language_frame.grid(row=2, column=0, sticky="ew")
        language_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(language_frame, text=t("settings_language_title"), font=THEME["font_h2"]).grid(row=0, column=0, columnspan=2, pady=THEME["padding_sm"], padx=THEME["padding_sm"], sticky="w")
        ctk.CTkLabel(language_frame, text=t("settings_language_label"), font=THEME["font_body"]).grid(row=1, column=0, sticky="w", padx=(15, 10), pady=(0, 15))
        current_language = self.config.get("language", DEFAULT_LANGUAGE)
        self.language_var = ctk.StringVar(value=LANGUAGE_DISPLAY_NAMES.get(current_language, LANGUAGE_DISPLAY_NAMES[DEFAULT_LANGUAGE]))
        language_menu = ctk.CTkOptionMenu(language_frame, variable=self.language_var, values=list(LANGUAGE_DISPLAY_NAMES.values()), command=self.on_language_change)
        language_menu.grid(row=1, column=1, sticky="w", padx=(0, 15), pady=(0, 15))
        Tooltip(language_menu, t("settings_language_tooltip"))

    def on_language_change(self, _selected_display_name: str = None):
        """Persiste a preferência de idioma e avisa que é necessário reiniciar para aplicá-la."""
        self.save_config()
        messagebox.showinfo(t("settings_language_title"), t("settings_language_tooltip"), parent=self)

    def create_sobre_tab(self):
        """Cria os widgets da aba 'Sobre'."""
        tab = self.tab_view.tab(self.tab_labels["about"])
        main_frame = ctk.CTkFrame(tab, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        main_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(main_frame, text=APP_NAME, font=THEME["font_h1"]).grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky="w")

        fields = {t("about_version"): APP_VERSION, t("about_developed_by"): "Lucas Motta", t("about_license"): "MIT License", t("about_github"): "https://github.com/lucaswotta/invent-ssh", t("about_linkedin"): "https://www.linkedin.com/in/lucaswotta"}
        link_font = ctk.CTkFont(family=THEME["font_family"], size=13, underline=True)
        row_index = 1
        for label_text, value_text in fields.items():
            ctk.CTkLabel(main_frame, text=label_text, font=THEME["font_label"]).grid(row=row_index, column=0, sticky="w", pady=5, padx=(0, 10))
            if "github.com" in value_text or "linkedin.com" in value_text:
                link_label = ctk.CTkLabel(main_frame, text=value_text, text_color=THEME["link_color"], font=link_font, cursor="hand2")
                link_label.grid(row=row_index, column=1, sticky="w", pady=5)
                link_label.bind("<Button-1>", lambda e, url=value_text: webbrowser.open_new_tab(url))
            else:
                ctk.CTkLabel(main_frame, text=value_text, font=THEME["font_body"]).grid(row=row_index, column=1, sticky="w", pady=5)
            row_index += 1

        help_button = ctk.CTkButton(main_frame, text=t("about_help_button"), command=self.open_help_modal)
        help_button.grid(row=row_index, column=0, columnspan=2, pady=(30, 0), sticky="ew")

    def open_help_modal(self):
        """Abre um modal com informações sobre a precisão da coleta de dados."""
        modal = BaseModal(self, t("help_modal_title"), "650x500")
        modal.grid_rowconfigure(0, weight=1)

        textbox = ctk.CTkTextbox(modal, wrap="word", font=THEME["font_body"])
        textbox.grid(row=0, column=0, padx=THEME["padding"], pady=THEME["padding"], sticky="nsew")

        textbox.insert("1.0", t("help_modal_body"))
        textbox.configure(state="disabled")

        close_button = ctk.CTkButton(modal, text=t("help_modal_close_button"), command=modal.destroy)
        close_button.grid(row=1, column=0, padx=THEME["padding"], pady=(0, THEME["padding"]), sticky="ew")

    def create_template_spreadsheet(self):
        """Cria e salva um arquivo de planilha modelo para o usuário."""
        try:
            filepath = filedialog.asksaveasfilename(title=t("save_template_title"), defaultextension=".xlsx", initialfile="modelo_inventario.xlsx", filetypes=[(t("excel_filetype_label"), "*.xlsx")])
            if not filepath: return

            df = pd.DataFrame({"IP": ["192.168.1.10", "192.168.1.11"], "NROEMPRESA": [1, 1], "NROCHECKOUT": [101, 102]})
            df.to_excel(filepath, index=False)
            messagebox.showinfo(t("template_created_title"), t("template_created_body", filepath=filepath))
        except Exception as e:
            messagebox.showerror(t("template_error_title"), t("template_error_body", error=e))

    def toggle_oracle_output_format(self):
        """Alterna a visibilidade das opções de formato de saída na aba Oracle."""
        if self.oracle_save_to_db_var.get():
            self.oracle_output_format_label.grid_remove()
            self.oracle_output_menu.grid_remove()
        else:
            self.oracle_output_format_label.grid(row=3, column=0, sticky="w", padx=10, pady=5)
            self.oracle_output_menu.grid(row=4, column=0, sticky="w", padx=10, pady=5)

    def setup_real_time_validation(self):
        """Configura a validação em tempo real para o campo de host do Oracle."""
        def is_valid_ip(s: str) -> bool:
            # Valida um endereço IPv4.
            return re.fullmatch(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$", s) is not None

        def validate(widget):
            # Altera a cor da borda do widget com base na validação.
            if widget.get():
                border_color = "green" if is_valid_ip(widget.get()) else "red"
                widget.configure(border_color=border_color)
            else:
                # Restaura a cor padrão se o campo estiver vazio
                widget.configure(border_color=ctk.ThemeManager.theme["CTkEntry"]["border_color"])

        self.oracle_entries['host'].bind('<KeyRelease>', lambda e: validate(e.widget))

    def browse_file(self):
        """Abre uma janela para o usuário selecionar o arquivo de planilha de entrada."""
        filepath = filedialog.askopenfilename(title=t("select_spreadsheet_title"), filetypes=[(t("spreadsheet_filetype_label"), "*.xlsx;*.csv"), (t("all_files_label"), "*.*")])
        if filepath:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, filepath)

    def start_inventory_thread(self):
        """
        Valida as configurações, inicia o processo de inventário em uma nova thread
        e abre o modal de logs.
        """
        if self.is_running: return

        active_key = self.get_active_tab_key()
        if active_key == "oracle":
            msg = t("confirm_oracle_body",
                    table=self.config_oracle_table_entry.get().strip(),
                    query=self.config_oracle_query_textbox.get('1.0', 'end-1c').strip())
            if not messagebox.askyesno(t("confirm_oracle_title"), msg, icon='question', parent=self):
                return
        try:
            engine_config = self.gather_config_from_ui()
            self.save_config() # Salva as configurações para a próxima sessão
            self.is_running = True
            self.run_button.configure(state="disabled", text=t("run_button_running"))
            LogModal(self)
            # Guardamos a referência do engine para poder sinalizar cancelamento
            # caso a janela seja fechada com a coleta ainda em andamento.
            self.current_engine = InventoryEngine(engine_config, self.log_queue)
            threading.Thread(target=self.current_engine.run_inventory, daemon=True).start()
        except ValueError as e:
            messagebox.showerror(t("config_error_title"), str(e), parent=self)
            self.reset_ui()
        except Exception as e:
            messagebox.showerror(t("unexpected_error_title"), t("unexpected_error_body", error=e), parent=self)
            logging.critical("Erro inesperado ao iniciar", exc_info=True)
            self.reset_ui()

    def _gather_spreadsheet_config(self) -> Dict[str, Any]:
        """Coleta as configurações específicas da aba 'Modo Planilha'."""
        filepath = self.file_entry.get().strip()
        if not filepath or not os.path.exists(filepath):
            raise ValueError(t("error_invalid_spreadsheet"))
        return {
            "mode": "Planilha",
            "filepath": filepath,
            "output_format": self.spreadsheet_output_format_var.get()
        }

    def _gather_oracle_config(self) -> Dict[str, Any]:
        """Coleta as configurações específicas da aba 'Modo Oracle'."""
        oracle_config = {k: v.get().strip() for k, v in self.oracle_entries.items() if k != 'password'}
        oracle_config["password"] = self.oracle_entries["password"].get()
        if not all(oracle_config.values()):
            raise ValueError(t("error_oracle_fields_required"))

        oracle_query = self.config_oracle_query_textbox.get("1.0", "end-1c").strip()
        if not oracle_query:
            raise ValueError(t("error_oracle_query_empty"))
        if not is_select_only_query(oracle_query):
            raise ValueError(t("error_oracle_query_not_select"))

        save_to_db = self.oracle_save_to_db_var.get()
        oracle_table = self.config_oracle_table_entry.get().strip()
        if save_to_db:
            if not oracle_table:
                raise ValueError(t("error_oracle_table_required"))
            if not is_valid_oracle_identifier(oracle_table):
                raise ValueError(t("error_oracle_table_invalid"))

        return {
            "mode": "Oracle",
            "oracle_config": oracle_config,
            "oracle_query": oracle_query,
            "save_to_db": save_to_db,
            "oracle_table": oracle_table,
            "output_format": self.oracle_output_format_var.get()
        }

    def _get_active_ssh_credentials(self) -> Dict[str, str]:
        """Obtém as credenciais SSH da aba atualmente selecionada."""
        widgets = self.ssh_widgets_planilha if self.get_active_tab_key() == "spreadsheet" else self.ssh_widgets_oracle
        return widgets.get_credentials()

    def _validate_ssh_credentials(self, ssh_creds: Dict[str, str]):
        """Valida se as credenciais SSH essenciais foram fornecidas."""
        if not ssh_creds.get("user"):
            raise ValueError(t("error_ssh_user_required"))
        if not ssh_creds.get("pass") and not ssh_creds.get("key_path"):
            raise ValueError(t("error_ssh_auth_required"))

    def gather_config_from_ui(self) -> Dict[str, Any]:
        """
        Orquestra a coleta de todas as configurações da UI, valida os dados
        e retorna um dicionário de configuração para o InventoryEngine.

        Returns:
            O dicionário de configuração completo.

        Raises:
            ValueError: Se alguma configuração obrigatória estiver faltando ou for inválida.
        """
        # 1. Coleta configurações gerais
        config = {
            "max_workers": int(self.workers_slider.get()),
            "ssh_timeout": int(self.timeout_slider.get())
        }

        # 2. Coleta configurações específicas do modo (Planilha ou Oracle)
        active_key = self.get_active_tab_key()
        if active_key == "spreadsheet":
            config.update(self._gather_spreadsheet_config())
        elif active_key == "oracle":
            config.update(self._gather_oracle_config())
        else:
            raise ValueError(t("error_invalid_tab"))

        # 3. Coleta e valida as credenciais SSH
        ssh_creds = self._get_active_ssh_credentials()
        self._validate_ssh_credentials(ssh_creds)
        config.update({
            "ssh_user": ssh_creds["user"],
            "ssh_pass": ssh_creds["pass"],
            "ssh_key_path": ssh_creds["key_path"],
        })

        return config

    def _language_code_from_display_name(self, display_name: str) -> str:
        """Converte o nome exibido no seletor de idioma (ex: 'English') de volta ao código ('en')."""
        for code, name in LANGUAGE_DISPLAY_NAMES.items():
            if name == display_name:
                return code
        return DEFAULT_LANGUAGE

    def reset_ui(self):
        """Restaura o estado da UI para 'não executando'."""
        self.is_running = False
        self.current_engine = None
        self.run_button.configure(state="normal", text=t("run_button_default"))
        self.on_tab_change() # Restaura o texto dinâmico do botão

    def open_file(self, filepath: str):
        """Abre um arquivo (como o relatório final) com o programa padrão do SO."""
        try:
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin": # macOS
                subprocess.run(["open", filepath], check=True)
            else: # Linux
                subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showwarning(t("open_file_warning_title"), t("open_file_warning_body", filename=os.path.basename(filepath), filepath=filepath, error=e), parent=self)

    def load_config(self) -> Dict[str, Any]:
        """
        Carrega as configurações do usuário do arquivo config.json.
        Retorna um dicionário vazio se o arquivo não existir ou for inválido.
        """
        if not os.path.exists(CONFIG_FILE):
            return {}
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def save_config(self):
        """Salva as configurações atuais da UI no arquivo config.json."""
        # Usa as credenciais da aba Planilha como padrão para salvar 'last_user' e 'last_key'
        ssh_creds = self.ssh_widgets_planilha.get_credentials()
        config_to_save = {
            "last_file_path": self.file_entry.get(),
            "spreadsheet_format": self.spreadsheet_output_format_var.get(),
            "oracle_output_format": self.oracle_output_format_var.get(),
            "oracle_user": self.oracle_entries["user"].get(),
            "oracle_host": self.oracle_entries["host"].get(),
            "oracle_port": self.oracle_entries["port"].get(),
            "oracle_service": self.oracle_entries["service"].get(),
            "last_ssh_user": ssh_creds["user"],
            "last_ssh_key_path": ssh_creds["key_path"],
            "max_workers": int(self.workers_slider.get()),
            "ssh_timeout": int(self.timeout_slider.get()),
            "save_to_db": self.oracle_save_to_db_var.get(),
            "oracle_table": self.config_oracle_table_entry.get(),
            "oracle_query": self.config_oracle_query_textbox.get("1.0", "end-1c").strip(),
            "show_welcome_modal": self.config.get("show_welcome_modal", True),
            "language": self._language_code_from_display_name(self.language_var.get())
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4)
        except Exception as e:
            logging.error(f"Erro ao salvar configurações: {e}")

    def on_closing(self):
        """Lida com o evento de fechamento da janela principal."""
        if self.is_running:
            if messagebox.askyesno(t("exit_confirm_title"), t("exit_confirm_body")):
                # Sinaliza cancelamento ao motor antes de destruir a janela: sem isso, as
                # threads do ThreadPoolExecutor continuam processando TODOS os terminais
                # pendentes em segundo plano (não são daemon), e o processo Python só
                # encerra de fato após elas terminarem — mesmo com a janela já fechada.
                if self.current_engine:
                    self.current_engine.cancel()
                self.destroy()
        else:
            self.save_config()
            self.destroy()

# --- Funções de Tratamento de Erro e Logging ---

def sanitize_traceback(text: str) -> str:
    """
    Remove informações sensíveis (senhas) de um traceback para
    registro seguro em logs.
    """
    # Padrões de regex para encontrar e censurar senhas e chaves
    patterns = [
        r"(password\s*=\s*['\"]).+?(['\"])",
        r"(ssh_pass\s*=\s*['\"]).+?(['\"])",
        r"(pkey\s*=\s*<paramiko\.).+?(>)"
    ]
    for p in patterns:
        text = re.sub(p, r"\1[REDACTED]\2", text, flags=re.IGNORECASE)
    return text

def _cleanup_old_files(directory: str, pattern: str, max_files: int) -> None:
    """
    Remove os arquivos mais antigos de `directory` que excedam `max_files`.
    Evita que `logs/` e `reports/` cresçam indefinidamente, já que cada
    execução gera um arquivo novo e nada os limpava antes.
    """
    if not os.path.isdir(directory):
        return
    files = sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getmtime, reverse=True)
    for old_file in files[max_files:]:
        try:
            os.remove(old_file)
        except OSError as e:
            logging.warning(f"Não foi possível remover o arquivo antigo '{old_file}': {e}")

def setup_logging():
    """Configura o sistema de logging para salvar logs detalhados em arquivos."""
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    _cleanup_old_files(log_dir, f"{APP_NAME}_*.log", max_files=20)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{APP_NAME}_{timestamp}.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s',
        handlers=[logging.FileHandler(log_file, encoding='utf-8')]
    )
    logging.info(f"Aplicação {APP_NAME} v{APP_VERSION} iniciada.")

def main():
    """Função principal que inicializa e executa a aplicação."""
    try:
        setup_logging()
        _cleanup_old_files("reports", "inventario_hardware_*.*", max_files=30)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        app = App()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        app.mainloop()
    except Exception:
        # Mecanismo de "último recurso" para capturar erros fatais
        sanitized_error = sanitize_traceback(traceback.format_exc())
        log_file = "crash_log.txt"
        with open(log_file, "w", encoding='utf-8') as f:
            f.write(f"{t('fatal_error_title')}\n\n{t('fatal_error_body', log_file=log_file)}\n\n"
                    f"{'='*20} REDACTED {'='*20}\n{sanitized_error}")

        logging.critical("Erro fatal não tratado na aplicação:", exc_info=True)

        # Tenta exibir uma caixa de diálogo de erro nativa
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(t("fatal_error_title"), t("fatal_error_body", log_file=log_file))
        except Exception as inner_e:
            print(f"Erro fatal. Não foi possível exibir a caixa de diálogo de erro: {inner_e}")


if __name__ == "__main__":
    if check_and_install_dependencies():
        if ctk is not None:
            main()
        else:
            # Caso o usuário tenha recusado a instalação, mas as libs não existiam
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(t("import_error_title"), t("import_error_body"))
    sys.exit(0)