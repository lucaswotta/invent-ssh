"""
build.py: O Construtor Simplificado para o invent-ssh.

Este script é uma ferramenta de conveniência para o DESENVOLVEDOR. Ele
automatiza todo o processo de criação do executável (.exe) da aplicação
usando o PyInstaller.

Funções principais:
- Instala as dependências a partir do `requirements.txt`.
- Limpa os diretórios de build anteriores.
- Executa o PyInstaller com as configurações corretas para uma aplicação
  de janela única, incluindo o ícone e os assets do customtkinter.
- Move o executável final para a pasta raiz do projeto.
- Limpa os arquivos temporários gerados pelo processo.
"""
import sys
import subprocess
import os
import shutil

# --- Configurações do Projeto ---
APP_NAME = "invent-ssh"
SCRIPT_NAME = "app.py"
ICON_NAME = "app.ico"
TEMP_BUILD_DIR = "build"
TEMP_DIST_DIR = "dist"
REQUIREMENTS_FILE = "requirements.txt"

def run_command(command: list[str]) -> bool:
    """
    Executa um comando no console, imprime a saída em tempo real e retorna
    True se for bem-sucedido.

    Args:
        command: Uma lista de strings representando o comando e seus argumentos.

    Returns:
        True para sucesso, False para falha.
    """
    print(f"\n> Executando: {' '.join(command)}")
    try:
        # Usa Popen para capturar e imprimir a saída em tempo real
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        for line in process.stdout:
            print(f"   {line}", end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
        return True
    except subprocess.CalledProcessError:
        print(f"\n[ERRO] O comando falhou. Verifique o log de saída acima.")
        return False
    except FileNotFoundError:
        print(f"\n[ERRO] Comando não encontrado: {command[0]}. Verifique se está no PATH do sistema.")
        return False
    except Exception as e:
        print(f"\n[ERRO] Uma exceção inesperada ocorreu: {e}")
        return False

def clean_directory(dir_path: str):
    """
    Remove um diretório de forma segura, se ele existir.

    Args:
        dir_path: O caminho do diretório a ser removido.

    Raises:
        OSError: Se houver um erro de permissão ao remover o diretório.
    """
    if not os.path.exists(dir_path):
        return
    try:
        shutil.rmtree(dir_path)
        print(f"   - Diretório '{dir_path}' removido com sucesso.")
    except OSError as e:
        print(f"[ERRO DE PERMISSÃO] Não foi possível apagar o diretório '{dir_path}'. Erro: {e}")
        raise

def get_app_version() -> str:
    """
    Lê a versão diretamente do `app.py` para manter a consistência
    no nome do arquivo do executável.

    Returns:
        A string da versão ou "DEV" em caso de falha.
    """
    try:
        with open(SCRIPT_NAME, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip().startswith("APP_VERSION"):
                    # Pega a parte depois do '=' e remove aspas e espaços
                    version_part = line.split('=')[1].split('#')[0]
                    return version_part.strip().replace('"', '').replace("'", "")
    except Exception:
        return "DEV"
    return "DEV"

def main() -> int:
    """
    Orquestra o processo de build completo, passo a passo.

    Returns:
        0 para sucesso, 1 para falha.
    """
    app_version = get_app_version()
    exe_name_with_version = f"{APP_NAME}-v{app_version}"

    print("=" * 60)
    print(f"    INICIANDO PROCESSO DE BUILD PARA '{exe_name_with_version.upper()}'")
    print("=" * 60)

    python_exe = sys.executable

    # --- PASSO 1: Instalar Dependências ---
    print(f"\n[PASSO 1/5] Verificando e instalando dependências de '{REQUIREMENTS_FILE}'...")
    if not os.path.exists(REQUIREMENTS_FILE):
        print(f"[ERRO FATAL] Arquivo '{REQUIREMENTS_FILE}' não encontrado.")
        return 1
    if not run_command([python_exe, "-m", "pip", "install", "-r", REQUIREMENTS_FILE]):
        print("\n[ERRO FATAL] Falha ao instalar as dependências do projeto.")
        return 1
    print("[INFO] Dependências instaladas/atualizadas com sucesso.")

    # --- PASSO 2: Limpar Builds Anteriores ---
    print("\n[PASSO 2/5] Limpando artefatos de builds anteriores...")
    try:
        clean_directory(TEMP_BUILD_DIR)
        clean_directory(TEMP_DIST_DIR)
        spec_file = f'{exe_name_with_version}.spec'
        if os.path.exists(spec_file):
            os.remove(spec_file)
            print(f"   - Arquivo de especificação '{spec_file}' removido.")
    except OSError:
        return 1

    # --- PASSO 3: Compilar com PyInstaller ---
    print("\n[PASSO 3/5] Iniciando a compilação (isso pode levar alguns minutos)...")
    try:
        # Importa para encontrar o caminho dos assets do customtkinter
        import customtkinter
        customtkinter_path = os.path.dirname(customtkinter.__file__)
        add_data_arg = f"{customtkinter_path}{os.pathsep}customtkinter"
    except ImportError as e:
        print(f"[ERRO FATAL] A dependência 'customtkinter' não foi encontrada. Erro: {e}")
        return 1

    build_command = [
        python_exe, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--name", exe_name_with_version,
        "--distpath", TEMP_DIST_DIR,
        "--workpath", TEMP_BUILD_DIR,
        "--add-data", add_data_arg,
    ]

    # Adiciona o ícone se ele existir na pasta
    if os.path.exists(ICON_NAME):
        print(f"[INFO] Ícone '{ICON_NAME}' encontrado e será adicionado ao executável.")
        build_command.extend(["--icon", ICON_NAME])
        # O ícone também precisa ser adicionado como 'data' para ser encontrado pelo app
        build_command.extend(["--add-data", f"{ICON_NAME}{os.pathsep}."])
    else:
        print(f"[AVISO] Ícone '{ICON_NAME}' não encontrado. O executável será criado sem ícone.")

    build_command.append(SCRIPT_NAME)

    if not run_command(build_command):
        print("\n[ERRO FATAL] Falha durante o processo de build com PyInstaller.")
        return 1

    # --- PASSO 4: Mover o Executável ---
    print("\n[PASSO 4/5] Movendo o executável para a pasta raiz do projeto...")
    exe_filename = f"{exe_name_with_version}.exe"
    src_path = os.path.join(TEMP_DIST_DIR, exe_filename)
    dest_path = os.path.join(os.getcwd(), exe_filename)

    if not os.path.exists(src_path):
        print(f"[ERRO] O executável '{exe_filename}' não foi encontrado após o build. Processo falhou.")
        return 1

    try:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        shutil.move(src_path, dest_path)
    except Exception as e:
        print(f"[ERRO] Falha ao mover o executável final: {e}")
        return 1

    # --- PASSO 5: Limpeza Final ---
    print("\n[PASSO 5/5] Limpando diretórios e arquivos temporários de build...")
    try:
        clean_directory(TEMP_BUILD_DIR)
        clean_directory(TEMP_DIST_DIR)
        spec_file_to_remove = f'{exe_name_with_version}.spec'
        if os.path.exists(spec_file_to_remove):
            os.remove(spec_file_to_remove)
            print(f"   - Arquivo de especificação '{spec_file_to_remove}' removido.")
    except OSError:
        print("[AVISO] Não foi possível remover todos os arquivos temporários.")

    print(f"\n[SUCESSO] Build concluído! O executável '{exe_filename}' está na pasta raiz do projeto.")
    return 0

if __name__ == "__main__":
    result_code = 1
    try:
        result_code = main()
    except Exception as e:
        print(f"\n[ERRO INESPERADO] Ocorreu um erro não tratado durante o build: {e}")
    finally:
        print("-" * 60)
        if result_code == 0:
            print("O processo de build foi concluído com sucesso.")
        else:
            print("O processo de build falhou. Verifique as mensagens de erro acima.")
        input("Pressione Enter para fechar o terminal...")
