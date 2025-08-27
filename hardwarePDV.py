import logging
import os
import concurrent.futures
from datetime import datetime
import oracledb
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm
import csv
import signal
import time

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN, YELLOW, RED, CYAN, MAGENTA, RESET = Fore.GREEN, Fore.YELLOW, Fore.RED, Fore.CYAN, Fore.MAGENTA, Style.RESET_ALL
except ImportError:
    print("Biblioteca 'colorama' não encontrada. A saída não será colorida.")
    GREEN = YELLOW = RED = CYAN = MAGENTA = RESET = ""

try:
    from coletaPDV import get_hardware_info
except ImportError:
    print(f"{RED}ERRO FATAL: O arquivo 'coletaPDV.py' não foi encontrado.{RESET}")
    exit(1)


# --- CONSTANTES E CONFIGURAÇÕES GLOBAIS ---
load_dotenv()

LOG_FILE = "hardwarePDV.log"
INPUT_FILE_BASE = "lista_pdvs"
OUTPUT_XLSX_FILE = "resultado_hardware.xlsx"
OUTPUT_CSV_FILE = "resultado_hardware.csv"
TABLE_NAME = "CONSINCO.BAR_HARDWARE_PDV"
HARDWARE_FIELDS = ["PLACA_MAE", "PROCESSADOR", "CORES_THREADS", "RAM", "DISCO", "ARMAZENAMENTO", "RELEASE"]
PDV_INFO_FIELDS = ["IP", "SEGMENTO", "OPERACAO"]


# --- CONFIGURAÇÃO DE LOGGING ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s",
    encoding='utf-8'
)
logger = logging.getLogger(__name__)


# --- FUNÇÃO DE TIMEOUT PARA SSH ---
def get_hardware_with_timeout(ip, username, password, timeout=30):
    """Versão com timeout da função de coleta de hardware."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Timeout de {timeout}s na coleta do IP {ip}")
    
    # Configurar timeout apenas em sistemas Unix
    if os.name != 'nt':  # Não é Windows
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
    
    try:
        start_time = time.time()
        result = get_hardware_info(ip, username, password)
        elapsed = time.time() - start_time
        
        if os.name != 'nt':
            signal.alarm(0)  # Cancelar alarm
            
        logger.info(f"Coleta do IP {ip} concluída em {elapsed:.2f}s")
        return result
        
    except TimeoutError as e:
        logger.warning(f"Timeout na coleta do IP {ip}: {e}")
        return {"status": "TIMEOUT", "error": str(e)}
    except Exception as e:
        if os.name != 'nt':
            signal.alarm(0)
        logger.error(f"Erro na coleta do IP {ip}: {e}")
        return {"status": "ERROR", "error": str(e)}


# --- FUNÇÕES DE CONFIGURAÇÃO E MODO ---
def choose_operation_mode():
    """Menu interativo para o usuário escolher o modo de operação."""
    default_mode = os.getenv("MODE", "ORACLE").upper()
    
    print(f"{CYAN}--------------------------------------------------{RESET}")
    print(f"{CYAN} Escolha o Modo de Operação para esta execução:{RESET}")
    print(f"{CYAN}--------------------------------------------------{RESET}")
    
    options = {'1': 'ORACLE', '2': 'PLANILHA', '3': 'SAIR'}
    default_choice = [key for key, value in options.items() if value == default_mode][0] if default_mode in options.values() else '1'

    print(f"  {YELLOW}1.{RESET} Modo Oracle (Conectar ao banco de dados)")
    print(f"  {YELLOW}2.{RESET} Modo Planilha (Ler de '{INPUT_FILE_BASE}.xlsx/.csv')")
    print(f"  {YELLOW}3.{RESET} Sair")
    print("-" * 50)
    print(f"O modo padrão (do .env) é: {GREEN}{default_mode}{RESET}")

    while True:
        choice = input(f"Digite sua escolha [{default_choice}] ou pressione Enter para o padrão: ").strip()
        
        if not choice:
            choice = default_choice

        if choice in options:
            chosen_mode = options[choice]
            if chosen_mode == 'SAIR':
                print(f"{MAGENTA}Operação cancelada pelo usuário.{RESET}")
                return None
            
            logger.info(f"Modo de operação selecionado pelo usuário: {chosen_mode}")
            return chosen_mode
        else:
            print(f"{RED}Opção inválida. Por favor, digite 1, 2 ou 3.{RESET}")

def load_configurations(mode):
    """Carrega e valida as configurações do .env com base no modo de operação."""
    configs = {}
    
    # Configurações SSH sempre necessárias
    ssh_vars = {
        "SSH_USERNAME": "seu_usuario_ssh", 
        "SSH_PASSWORD": "sua_senha_ssh"
    }
    required_vars = ssh_vars.copy()

    # Configurações Oracle apenas para modo ORACLE
    if mode == 'ORACLE':
        oracle_vars = {
            "ORACLE_USER": "seu_usuario_oracle", 
            "ORACLE_PASSWORD": "sua_senha_oracle",
            "ORACLE_HOST": "host_oracle", 
            "ORACLE_PORT": "porta_oracle",
            "ORACLE_SERVICE": "service_name_oracle"
        }
        required_vars.update(oracle_vars)

    # Verificar variáveis ausentes
    missing = [key for key in required_vars if not os.getenv(key)]
    if missing:
        error_msg = f"Variáveis ausentes no .env para o modo {mode}: {', '.join(missing)}"
        logger.critical(error_msg)
        print(f"{RED}Erro: {error_msg}{RESET}")
        print(f"{YELLOW}Adicione ao .env na raiz do projeto:")
        for var in missing:
            print(f"{CYAN}  {var}={required_vars[var]}")
        exit(1)

    # Carregar configurações
    configs = {key.lower(): os.getenv(key) for key in required_vars.keys()}

    # Configurações específicas do Oracle
    if mode == 'ORACLE':
        configs["dsn"] = f"{configs['oracle_host']}:{configs['oracle_port']}/{configs['oracle_service']}"

    # Configurações numéricas com valores mais conservadores
    try:
        configs["max_workers"] = min(int(os.getenv("MAX_WORKERS", "8")), 15)
        configs["save_interval"] = int(os.getenv("SAVE_INTERVAL", "20"))
        configs["ssh_timeout"] = int(os.getenv("SSH_TIMEOUT", "30"))
    except ValueError:
        configs["max_workers"] = 8
        configs["save_interval"] = 20
        configs["ssh_timeout"] =30
        logger.warning("Configurações numéricas inválidas no .env, usando padrões.")

    logger.info(f"Configurações carregadas para modo {mode}: MAX_WORKERS={configs['max_workers']}, SAVE_INTERVAL={configs['save_interval']}, SSH_TIMEOUT={configs['ssh_timeout']}")
    return configs


# --- FUNÇÕES DE ENTRADA DE DADOS ---
def get_pdvs_from_file():
    """Lê a lista de PDVs de um arquivo local (.xlsx ou .csv) e retorna um DataFrame."""
    filepath_xlsx = f"{INPUT_FILE_BASE}.xlsx"
    filepath_csv = f"{INPUT_FILE_BASE}.csv"

    try:
        if os.path.exists(filepath_xlsx):
            df = pd.read_excel(filepath_xlsx)
            logger.info(f"Arquivo de entrada '{filepath_xlsx}' lido com sucesso.")
        elif os.path.exists(filepath_csv):
            df = pd.read_csv(filepath_csv)
            logger.info(f"Arquivo de entrada '{filepath_csv}' lido com sucesso.")
        else:
            raise FileNotFoundError(f"Nenhum arquivo encontrado: '{filepath_xlsx}' ou '{filepath_csv}'")

        # Normalizar nomes das colunas
        df.columns = [str(col).upper().strip() for col in df.columns]
        
        # Verificar colunas obrigatórias
        required_cols = ['IP', 'NROEMPRESA', 'NROCHECKOUT']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise KeyError(f"Colunas essenciais ausentes na planilha: {missing_cols}")

        # Adicionar colunas opcionais se não existirem
        for col in ['SEGMENTO', 'OPERACAO']:
            if col not in df.columns:
                df[col] = 'N/A'

        # Converter tipos de dados
        df['NROEMPRESA'] = pd.to_numeric(df['NROEMPRESA'])
        df['NROCHECKOUT'] = pd.to_numeric(df['NROCHECKOUT'])
        df['IP'] = df['IP'].astype(str).str.strip()

        logger.info(f"Encontrados {len(df)} PDVs na planilha.")
        return df

    except FileNotFoundError as e:
        error_msg = f"Arquivo de entrada não encontrado. Crie '{filepath_xlsx}' ou '{filepath_csv}' com as colunas: IP, NROEMPRESA, NROCHECKOUT"
        logger.critical(error_msg)
        print(f"{RED}Erro Crítico: {error_msg}{RESET}")
        exit(1)
    except KeyError as e:
        logger.critical(str(e))
        print(f"{RED}Erro Crítico: {str(e)}{RESET}")
        exit(1)
    except Exception as e:
        logger.critical(f"Erro inesperado ao ler a planilha: {e}", exc_info=True)
        print(f"{RED}Erro inesperado ao ler a planilha: {e}{RESET}")
        exit(1)

def get_pdvs_from_oracle(connection):
    """Busca a lista de PDVs ativos do banco de dados Oracle e retorna um DataFrame."""
    query = """
        WITH PARAMPDV AS (
            SELECT NROEMPRESA, NROCHECKOUT, COALESCE(TO_CHAR(VALOR), 'VendaCupomNota') AS VALOR
            FROM CONSINCOMONITOR.TB_PARAMPDVVALOR WHERE PARAMPDV = 'ModoOperacao'
        ), PDV_ATIVO AS (
            SELECT IP, NROEMPRESA, NROCHECKOUT, NROSEGMENTO FROM CONSINCOMONITOR.TB_CHECKOUT
            WHERE ATIVO = 'S' AND NROCHECKOUT <> 100
        )
        SELECT A.IP, A.NROEMPRESA, A.NROCHECKOUT, S.SEGMENTO, COALESCE(B.VALOR, 'PDV') AS OPERACAO
        FROM PDV_ATIVO A
        LEFT JOIN PARAMPDV B ON A.NROEMPRESA = B.NROEMPRESA AND A.NROCHECKOUT = B.NROCHECKOUT
        JOIN CONSINCOMONITOR.TB_SEGMENTO S ON S.NROSEGMENTO = A.NROSEGMENTO
        ORDER BY A.NROEMPRESA, A.NROCHECKOUT
    """
    
    logger.info("Executando query para buscar PDVs ativos no Oracle...")
    try:
        df = pd.read_sql(query, connection)
        df.columns = [col.upper() for col in df.columns]
        df['NROEMPRESA'] = pd.to_numeric(df['NROEMPRESA'])
        df['NROCHECKOUT'] = pd.to_numeric(df['NROCHECKOUT'])
        logger.info(f"Encontrados {len(df)} PDVs no Oracle.")
        return df
    except Exception as e:
        logger.error(f"Erro ao executar query de PDVs: {e}", exc_info=True)
        raise


# --- FUNÇÕES DE PRÉ-CARREGAMENTO (SOLUÇÃO PARA TRAVAMENTO) ---
def preload_existing_data(cursor):
    """Pré-carrega todos os dados existentes do Oracle para evitar consultas durante threading."""
    try:
        query = f"""
            SELECT IP, NROEMPRESA, NROCHECKOUT, SEGMENTO, OPERACAO, PLACA_MAE, PROCESSADOR, 
                   CORES_THREADS, RAM, DISCO, ARMAZENAMENTO, RELEASE, STATUS, DTAINCLUSAO, DTAATUALIZACAO
            FROM {TABLE_NAME}
        """
        cursor.execute(query)
        
        existing_data_map = {}
        for row in cursor.fetchall():
            columns = [desc[0].upper() for desc in cursor.description]
            data_dict = dict(zip(columns, row))
            key = (int(data_dict['NROEMPRESA']), int(data_dict['NROCHECKOUT']))
            existing_data_map[key] = data_dict
            
        logger.info(f"Pré-carregados {len(existing_data_map)} registros existentes do Oracle.")
        return existing_data_map
        
    except Exception as e:
        logger.error(f"Erro ao pré-carregar dados existentes: {e}", exc_info=True)
        return {}


# --- FUNÇÕES DE BANCO DE DADOS ---
def check_and_create_oracle_table(cursor):
    """Verifica se a tabela existe e oferece para criá-la se não existir."""
    try:
        cursor.execute(f"SELECT 1 FROM {TABLE_NAME} WHERE 1=0")
        logger.info(f"Tabela {TABLE_NAME} encontrada.")
        return True
    except oracledb.DatabaseError as e:
        if e.args[0].code == 942:  # ORA-00942: table or view does not exist
            logger.warning(f"Tabela {TABLE_NAME} não encontrada.")
            print(f"{YELLOW}Aviso: Tabela {TABLE_NAME} não encontrada no banco de dados.{RESET}")
            choice = input(f"{CYAN}Deseja tentar criá-la agora? (s/n): {RESET}").lower()
            if choice == 's':
                return create_oracle_table(cursor)
            else:
                return False
        else:
            logger.error(f"Erro ao verificar tabela: {e}", exc_info=True)
            raise e

def create_oracle_table(cursor):
    """Cria a tabela de hardware no banco de dados Oracle."""
    create_sql = f"""
        CREATE TABLE {TABLE_NAME} (
            IP VARCHAR2(45), NROEMPRESA NUMBER(5) NOT NULL, NROCHECKOUT NUMBER(5) NOT NULL,
            SEGMENTO VARCHAR2(100), OPERACAO VARCHAR2(50), PLACA_MAE VARCHAR2(255),
            PROCESSADOR VARCHAR2(255), CORES_THREADS VARCHAR2(50), RAM VARCHAR2(50),
            DISCO VARCHAR2(50), ARMAZENAMENTO VARCHAR2(50), RELEASE VARCHAR2(100),
            STATUS VARCHAR2(20), DTAINCLUSAO DATE, DTAATUALIZACAO DATE,
            CONSTRAINT PK_BAR_HARDWARE_PDV PRIMARY KEY (NROEMPRESA, NROCHECKOUT)
        )"""
    try:
        cursor.execute(create_sql)
        logger.info(f"Tabela {TABLE_NAME} criada com sucesso.")
        print(f"{GREEN}Tabela criada com sucesso!{RESET}")
        return True
    except Exception as e:
        logger.error(f"Falha ao criar a tabela: {e}", exc_info=True)
        print(f"{RED}Erro ao criar a tabela: {e}{RESET}")
        return False

def has_relevant_data_changes(new_data, existing_data):
    """Verifica alterações nos campos de dados (IP, Info PDV, Hardware)."""
    if not existing_data:
        return True
   
    fields_to_compare = PDV_INFO_FIELDS + HARDWARE_FIELDS
    for field in fields_to_compare:
        new_value = str(new_data.get(field, "Não detectado")).strip()
        existing_value = str(existing_data.get(field, "Não detectado")).strip()
        if new_value != existing_value:
            logger.info(f"Mudança no PDV {new_data.get('NROEMPRESA')}-{new_data.get('NROCHECKOUT')}: Campo '{field}': '{existing_value}' -> '{new_value}'")
            return True
    return False

def mark_inactive_pdvs(cursor, connection, df_pdvs_ativos):
    """Marca PDVs como 'Inativo' se não estiverem mais na lista de PDVs ativos."""
    try:
        cursor.execute(f"SELECT NROEMPRESA, NROCHECKOUT FROM {TABLE_NAME} WHERE STATUS <> 'Inativo'")
        existing_pdvs = {(int(row[0]), int(row[1])) for row in cursor.fetchall()}
       
        active_pdvs = set()
        if not df_pdvs_ativos.empty:
            active_pdvs = {(int(row["NROEMPRESA"]), int(row["NROCHECKOUT"])) for _, row in df_pdvs_ativos.iterrows()}
       
        pdvs_to_inactivate = existing_pdvs - active_pdvs
       
        if pdvs_to_inactivate:
            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            update_data = [
                {'status': 'Inativo', 'dtaatualizacao': current_time_str, 'nroempresa': ne, 'nrocheckout': nc} 
                for ne, nc in pdvs_to_inactivate
            ]
           
            cursor.executemany(
                f"UPDATE {TABLE_NAME} SET STATUS = :status, DTAATUALIZACAO = TO_DATE(:dtaatualizacao, 'YYYY-MM-DD HH24:MI:SS') WHERE NROEMPRESA = :nroempresa AND NROCHECKOUT = :nrocheckout",
                update_data
            )
            connection.commit()
            logger.info(f"{cursor.rowcount} PDVs marcados como 'Inativo'.")
        else:
            logger.info("Nenhum PDV para marcar como 'Inativo'.")
           
    except Exception as e:
        logger.error(f"Erro ao marcar PDVs inativos: {e}", exc_info=True)


# --- FUNÇÕES DE PROCESSAMENTO DE RESULTADOS ---
def process_pdv_result(pdv_info, hw_result, existing_data):
    """Processa o resultado da coleta de um PDV específico."""
    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Dados base do PDV
    data_for_processing = pdv_info.copy()
    for field in HARDWARE_FIELDS:
        data_for_processing[field] = "Não detectado"
    
    # Determinar status
    status = "OFFLINE"
    if hw_result and hw_result.get("status") in ["SUCESSO", "FALHA COMANDOS"]:
        status = "ONLINE"
        # Atualizar dados de hardware
        for field in HARDWARE_FIELDS:
            data_for_processing[field] = hw_result.get(field.lower(), "Não detectado")
    elif hw_result and hw_result.get("status") in ["TIMEOUT", "ERROR"]:
        logger.warning(f"PDV {pdv_info['NROEMPRESA']}-{pdv_info['NROCHECKOUT']} ({pdv_info['IP']}): {hw_result.get('status')} - {hw_result.get('error', 'Erro desconhecido')}")
    
    data_for_processing["STATUS"] = status
    
    # Verificar dados existentes e mudanças
    data_changed = True
    if existing_data:
        # Se PDV está OFFLINE, preservar dados de hardware existentes
        if status == "OFFLINE":
            for field in HARDWARE_FIELDS:
                data_for_processing[field] = existing_data.get(field, "Não detectado")
        
        # Verificar se houve mudanças significativas
        data_changed = has_relevant_data_changes(data_for_processing, existing_data)
        
        if status == "ONLINE":
            data_for_processing["DTAATUALIZACAO"] = current_time_str
            if data_changed:
                data_for_processing["DTAINCLUSAO"] = current_time_str
            else:
                data_for_processing["DTAINCLUSAO"] = existing_data["DTAINCLUSAO"].strftime('%Y-%m-%d %H:%M:%S')
        else:  # OFFLINE
            data_for_processing["DTAINCLUSAO"] = existing_data["DTAINCLUSAO"].strftime('%Y-%m-%d %H:%M:%S')
            data_for_processing["DTAATUALIZACAO"] = current_time_str
    else:
        # Novo PDV
        data_for_processing["DTAINCLUSAO"] = current_time_str
        data_for_processing["DTAATUALIZACAO"] = current_time_str
        data_changed = True
    
    return data_for_processing, data_changed


# --- FUNÇÕES DE SAÍDA DE DADOS ---
def save_results_to_oracle(cursor, connection, batch_results):
    """Salva ou atualiza um lote de dados de PDVs no Oracle usando MERGE."""
    if not batch_results:
        logger.info("Nenhum dado no batch para salvar no Oracle.")
        return 0, 0
        
    sql_merge = f"""
        MERGE INTO {TABLE_NAME} dest
        USING (
            SELECT :v_IP AS IP, :v_NROEMPRESA AS NROEMPRESA, :v_NROCHECKOUT AS NROCHECKOUT,
                   :v_SEGMENTO AS SEGMENTO, :v_OPERACAO AS OPERACAO, :v_PLACA_MAE AS PLACA_MAE,
                   :v_PROCESSADOR AS PROCESSADOR, :v_CORES_THREADS AS CORES_THREADS,
                   :v_RAM AS RAM, :v_DISCO AS DISCO, :v_ARMAZENAMENTO AS ARMAZENAMENTO,
                   :v_RELEASE AS RELEASE, :v_STATUS AS STATUS,
                   TO_DATE(:v_DTAINCLUSAO_STR, 'YYYY-MM-DD HH24:MI:SS') AS DTAINCLUSAO_VAL,
                   TO_DATE(:v_DTAATUALIZACAO_STR, 'YYYY-MM-DD HH24:MI:SS') AS DTAATUALIZACAO_VAL
            FROM dual
        ) src ON (dest.NROEMPRESA = src.NROEMPRESA AND dest.NROCHECKOUT = src.NROCHECKOUT)
        WHEN MATCHED THEN UPDATE SET
            dest.IP = src.IP, dest.SEGMENTO = src.SEGMENTO, dest.OPERACAO = src.OPERACAO,
            dest.PLACA_MAE = src.PLACA_MAE, dest.PROCESSADOR = src.PROCESSADOR,
            dest.CORES_THREADS = src.CORES_THREADS, dest.RAM = src.RAM, dest.DISCO = src.DISCO,
            dest.ARMAZENAMENTO = src.ARMAZENAMENTO, dest.RELEASE = src.RELEASE, dest.STATUS = src.STATUS,
            dest.DTAATUALIZACAO = src.DTAATUALIZACAO_VAL
        WHEN NOT MATCHED THEN INSERT (IP, NROEMPRESA, NROCHECKOUT, SEGMENTO, OPERACAO, PLACA_MAE, PROCESSADOR, CORES_THREADS, RAM, DISCO, ARMAZENAMENTO, RELEASE, STATUS, DTAINCLUSAO, DTAATUALIZACAO)
            VALUES (src.IP, src.NROEMPRESA, src.NROCHECKOUT, src.SEGMENTO, src.OPERACAO, src.PLACA_MAE, src.PROCESSADOR, src.CORES_THREADS, src.RAM, src.DISCO, src.ARMAZENAMENTO, src.RELEASE, src.STATUS, src.DTAINCLUSAO_VAL, src.DTAATUALIZACAO_VAL)
    """
    try:
        cursor.executemany(sql_merge, batch_results, batcherrors=True)
        connection.commit()
        rows_affected = cursor.rowcount
        batch_size = len(batch_results)
        
        # Log de erros em batch, se houver
        for error in cursor.getbatcherrors():
            logger.error(f"Erro no batch Oracle na linha {error.offset}: {error.message}")
        
        logger.info(f"Lote de {batch_size} registros processado no Oracle (afetados: {rows_affected}).")
        return rows_affected, batch_size
    except Exception as e:
        logger.error(f"Erro crítico ao salvar dados no Oracle: {e}", exc_info=True)
        print(f"{RED}Erro ao salvar dados no Oracle: {e}{RESET}")
        try:
            connection.rollback()
            logger.info("Rollback realizado.")
        except Exception as rb_e:
            logger.error(f"Erro ao fazer rollback: {rb_e}")
        return 0, len(batch_results)

def save_results_to_excel(all_results, filename=OUTPUT_XLSX_FILE):
    """Salva a lista final de resultados em um arquivo Excel."""
    if not all_results:
        logger.warning("Nenhum resultado para salvar no arquivo Excel.")
        return 0
    try:
        df = pd.DataFrame(all_results)
        
        # Organizar colunas na ordem desejada
        ordered_cols = ['NROEMPRESA', 'NROCHECKOUT', 'IP', 'STATUS', 'SEGMENTO', 'OPERACAO'] + HARDWARE_FIELDS
        remaining_cols = [col for col in df.columns if col not in ordered_cols]
        final_cols = [col for col in ordered_cols if col in df.columns] + remaining_cols
        df = df[final_cols]

        df.to_excel(filename, index=False)
        print(f"\n{GREEN}Resultados salvos com sucesso em: {YELLOW}{filename}{RESET}")
        logger.info(f"{len(all_results)} resultados salvos em '{filename}'.")
        return len(all_results)
    except Exception as e:
        logger.error(f"Falha ao salvar o arquivo Excel: {e}", exc_info=True)
        print(f"{RED}Erro ao salvar resultados no Excel: {e}{RESET}")
        return 0

def save_results_to_csv(batch_results, filename=OUTPUT_CSV_FILE):
    """Salva um lote de dados de PDVs em um arquivo CSV."""
    if not batch_results:
        return 0

    try:
        fieldnames = ["IP", "NROEMPRESA", "NROCHECKOUT", "SEGMENTO", "OPERACAO", "PLACA_MAE",
                      "PROCESSADOR", "CORES_THREADS", "RAM", "DISCO", "ARMAZENAMENTO",
                      "RELEASE", "STATUS", "DTAINCLUSAO", "DTAATUALIZACAO"]
        
        file_exists = os.path.exists(filename)
        with open(filename, mode='a' if file_exists else 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            writer.writerows(batch_results)
        
        logger.info(f"Salvos {len(batch_results)} registros no CSV {filename}.")
        return len(batch_results)
    except Exception as e:
        logger.error(f"Erro ao salvar dados no CSV {filename}: {e}", exc_info=True)
        print(f"{RED}Erro ao salvar dados no CSV: {e}{RESET}")
        return 0


# --- FUNÇÃO PRINCIPAL ---
def main():
    """Função principal que orquestra todo o processo de coleta e salvamento."""
    logger.info("=== INICIANDO EXECUÇÃO DO SCRIPT DE COLETA DE HARDWARE ===")
    print(f"{MAGENTA}=== PDV Hardware Inspector (Versão Corrigida) ===")
    
    # Escolher modo de operação
    mode = choose_operation_mode()
    if not mode:
        return

    print(f"{CYAN}Modo selecionado: {mode}{RESET}")
    
    # Carregar configurações
    configs = load_configurations(mode)
    
    # Variáveis de controle
    db_connection = None
    db_cursor = None
    existing_data_map = {}
    ssh_results = []
    all_results = []
    processed_count = 0
    success_count = 0
    total_db_affected = 0
    total_db_sent = 0
    
    try:
        # ETAPA 1: Configurar conexão Oracle e pré-carregar dados (se necessário)
        if mode == 'ORACLE':
            print(f"{CYAN}Conectando ao Oracle...{RESET}")
            db_connection = oracledb.connect(
                user=configs["oracle_user"], 
                password=configs["oracle_password"], 
                dsn=configs["dsn"]
            )
            db_cursor = db_connection.cursor()
            print(f"{GREEN}Conexão Oracle estabelecida.{RESET}")
            
            if not check_and_create_oracle_table(db_cursor):
                print(f"{RED}Tabela Oracle não está disponível. Encerrando.{RESET}")
                return
            
            print(f"{CYAN}Pré-carregando dados existentes do Oracle...{RESET}")
            existing_data_map = preload_existing_data(db_cursor)
            
            df_pdvs = get_pdvs_from_oracle(db_connection)
        else:  # Modo PLANILHA
            df_pdvs = get_pdvs_from_file()

        if df_pdvs.empty:
            print(f"{YELLOW}Nenhum PDV encontrado para processar.{RESET}")
            if mode == 'ORACLE' and db_cursor:
                logger.info("Verificando PDVs para marcar como 'Inativo'...")
                mark_inactive_pdvs(db_cursor, db_connection, df_pdvs)
            return
        
        # ETAPA 2: THREADING apenas para coleta SSH (SEM operações Oracle)
        pdvs_to_process = [
            {
                "IP": row["IP"], 
                "NROEMPRESA": int(row["NROEMPRESA"]),
                "NROCHECKOUT": int(row["NROCHECKOUT"]), 
                "SEGMENTO": row["SEGMENTO"],
                "OPERACAO": row["OPERACAO"]
            }
            for _, row in df_pdvs.iterrows()
        ]
        
        total_pdvs = len(pdvs_to_process)
        print(f"{CYAN}Iniciando coleta SSH de {total_pdvs} PDVs com {configs['max_workers']} workers...{RESET}")
        print(f"{YELLOW}Timeout SSH configurado para {configs['ssh_timeout']} segundos por PDV.{RESET}")

        # Threading APENAS para SSH - sem operações Oracle
        with tqdm(total=total_pdvs, desc=f"{CYAN}Coletando via SSH", ncols=100,
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=configs["max_workers"]) as executor:
                future_to_pdv = {
                    executor.submit(get_hardware_with_timeout, 
                                  pdv["IP"], 
                                  configs["ssh_username"], 
                                  configs["ssh_password"], 
                                  configs["ssh_timeout"]): pdv
                    for pdv in pdvs_to_process
                }
                
                for future in concurrent.futures.as_completed(future_to_pdv):
                    pdv_info = future_to_pdv[future]
                    ip = pdv_info["IP"]
                    
                    try:
                        hw_result = future.result()
                        ssh_results.append((pdv_info, hw_result))
                        
                    except Exception as e:
                        logger.error(f"Exceção crítica na thread SSH para {ip}: {e}", exc_info=True)
                        ssh_results.append((pdv_info, {"status": "THREAD_ERROR", "error": str(e)}))
                    
                    pbar.update(1)
                    pbar.set_postfix_str(f"Último: {ip}")

        print(f"\n{GREEN}Coleta SSH concluída. Processando resultados...{RESET}")
        
        # ETAPA 3: Processar resultados SEQUENCIALMENTE (com operações Oracle se necessário)
        batch_buffer = []
        
        with tqdm(total=len(ssh_results), desc=f"{CYAN}Processando resultados", ncols=100) as pbar:
            for pdv_info, hw_result in ssh_results:
                nroempresa = pdv_info["NROEMPRESA"]
                nrocheckout = pdv_info["NROCHECKOUT"]
                
                # Usar dados pré-carregados (sem consulta Oracle individual)
                existing_data = existing_data_map.get((nroempresa, nrocheckout))
                
                # Processar resultado
                processed_data, data_changed = process_pdv_result(pdv_info, hw_result, existing_data)
                all_results.append(processed_data)
                
                # Contadores
                processed_count += 1
                if (processed_data["STATUS"] == "ONLINE" and 
                    (not existing_data or data_changed or 
                     (existing_data and existing_data.get("STATUS") != "ONLINE"))):
                    success_count += 1
                
                # Para modo Oracle: preparar batch
                if mode == 'ORACLE':
                    batch_entry = {
                        'v_IP': processed_data.get("IP"),
                        'v_NROEMPRESA': processed_data.get("NROEMPRESA"),
                        'v_NROCHECKOUT': processed_data.get("NROCHECKOUT"),
                        'v_SEGMENTO': processed_data.get("SEGMENTO"),
                        'v_OPERACAO': processed_data.get("OPERACAO"),
                        'v_PLACA_MAE': processed_data.get("PLACA_MAE", "Não detectado"),
                        'v_PROCESSADOR': processed_data.get("PROCESSADOR", "Não detectado"),
                        'v_CORES_THREADS': processed_data.get("CORES_THREADS", "Não detectado"),
                        'v_RAM': processed_data.get("RAM", "Não detectado"),
                        'v_DISCO': processed_data.get("DISCO", "Não detectado"),
                        'v_ARMAZENAMENTO': processed_data.get("ARMAZENAMENTO", "Não detectado"),
                        'v_RELEASE': processed_data.get("RELEASE", "Não detectado"),
                        'v_STATUS': processed_data.get("STATUS"),
                        'v_DTAINCLUSAO_STR': processed_data.get("DTAINCLUSAO"),
                        'v_DTAATUALIZACAO_STR': processed_data.get("DTAATUALIZACAO")
                    }
                    batch_buffer.append(batch_entry)
                    
                    # Salvar batch quando atingir o limite
                    if len(batch_buffer) >= configs["save_interval"]:
                        affected, sent = save_results_to_oracle(db_cursor, db_connection, batch_buffer)
                        total_db_affected += affected
                        total_db_sent += sent
                        batch_buffer = []
                
                pbar.update(1)

        # Salvar batch restante
        if mode == 'ORACLE' and batch_buffer:
            affected, sent = save_results_to_oracle(db_cursor, db_connection, batch_buffer)
            total_db_affected += affected
            total_db_sent += sent

        # ETAPA 4: Finalizar
        if mode == 'ORACLE':
            print(f"{CYAN}Marcando PDVs inativos...{RESET}")
            mark_inactive_pdvs(db_cursor, db_connection, df_pdvs)
            
            # Salvar cópia em Excel para backup
            print(f"{CYAN}Salvando backup em Excel...{RESET}")
            save_results_to_excel(all_results, f"backup_{OUTPUT_XLSX_FILE}")
        else:
            # Modo PLANILHA: salvar em Excel e CSV
            print(f"{CYAN}Salvando resultados...{RESET}")
            save_results_to_excel(all_results)
            save_results_to_csv(all_results)

        # ETAPA 5: Relatório final
        print(f"\n{GREEN}=== Processo de Coleta Concluído ==={RESET}")
        print(f"{CYAN}Total de PDVs encontrados: {total_pdvs}{RESET}")
        print(f"{CYAN}PDVs processados: {processed_count}{RESET}")
        print(f"{GREEN}PDVs 'ONLINE' com dados válidos/alterados: {success_count}{RESET}")
        
        offline_count = processed_count - success_count
        if offline_count > 0:
            print(f"{YELLOW}PDVs 'OFFLINE' ou sem mudanças significativas: {offline_count}{RESET}")
        
        if mode == 'ORACLE':
            print(f"{CYAN}Registros enviados ao Oracle: {total_db_sent}{RESET}")
            print(f"{CYAN}Registros processados no Oracle: {total_db_affected}{RESET}")
        else:
            print(f"{CYAN}Resultados salvos em arquivos de saída.{RESET}")

    except oracledb.DatabaseError as oe:
        error_obj, = oe.args
        logger.critical(f"Erro crítico de banco Oracle: {oe} (Código: {error_obj.code})", exc_info=True)
        print(f"{RED}Erro crítico de banco Oracle: {oe}{RESET}")
        print(f"{YELLOW}Verifique credenciais, DSN, listener e permissões.{RESET}")
    
    except Exception as e:
        logger.critical(f"Erro crítico inesperado: {e}", exc_info=True)
        print(f"{RED}Erro crítico inesperado: {e}{RESET}")
    
    finally:
        # Limpeza de recursos
        if db_cursor:
            try:
                db_cursor.close()
                logger.info("Cursor Oracle fechado.")
            except Exception as e:
                logger.warning(f"Erro ao fechar cursor: {e}")
        
        if db_connection:
            try:
                db_connection.close()
                logger.info("Conexão Oracle fechada.")
            except Exception as e:
                logger.warning(f"Erro ao fechar conexão: {e}")
        
        print(f"\n{MAGENTA}=== Processo Finalizado ==={RESET}")
        print(f"{CYAN}Logs detalhados disponíveis em: {YELLOW}{LOG_FILE}{RESET}")
        
        if mode == 'PLANILHA':
            print(f"{CYAN}Arquivos de saída:{RESET}")
            print(f"  {YELLOW}- {OUTPUT_XLSX_FILE}{RESET}")
            print(f"  {YELLOW}- {OUTPUT_CSV_FILE}{RESET}")
        else:
            print(f"{CYAN}Backup disponível em: {YELLOW}backup_{OUTPUT_XLSX_FILE}{RESET}")
        
        logger.info("=== EXECUÇÃO FINALIZADA ===")


if __name__ == "__main__":
    main()