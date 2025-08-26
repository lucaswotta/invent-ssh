import oracledb
import pandas as pd
import os
import logging
import concurrent.futures
from dotenv import load_dotenv 
from datetime import datetime
from tqdm import tqdm
import csv

# --- Configuração Colorama ---
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    CYAN = Fore.CYAN
    MAGENTA = Fore.MAGENTA
    RESET = Style.RESET_ALL
except ImportError:
    print("Colorama não encontrado. Saída colorida desativada.")
    GREEN = YELLOW = RED = CYAN = MAGENTA = RESET = ""

# --- Constantes ---
LOG_FILE = "hardwarePDV.log" 
TABLE_NAME = "CONSINCO.BAR_HARDWARE_PDV"
CSV_FILE = "hardwarePDV_output.csv"
HARDWARE_FIELDS = ["PLACA_MAE", "PROCESSADOR", "CORES_THREADS", "RAM", "DISCO", "ARMAZENAMENTO", "RELEASE"]
PDV_INFO_FIELDS = ["IP", "SEGMENTO", "OPERACAO"]

# --- Configuração de Logging Principal ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s"
)
logger = logging.getLogger("SCRIPT_PRINCIPAL") 

# --- Funções de Configuração ---
def load_env_configs():
    """Carrega e valida as configurações do .env para o script principal."""
    load_dotenv() 
    required_vars = {
        "ORACLE_USER": "seu_usuario_oracle",
        "ORACLE_PASSWORD": "sua_senha_oracle",
        "ORACLE_HOST": "host_oracle",
        "ORACLE_PORT": "porta_oracle",
        "ORACLE_SERVICE": "service_name_oracle",
        "SSH_USERNAME": "seu_usuario_ssh",
        "SSH_PASSWORD": "sua_senha_ssh"
    }
    
    missing_vars = [key for key in required_vars if not os.getenv(key)]
    if missing_vars:
        error_msg = f"Variáveis ausentes no .env: {', '.join(missing_vars)}"
        logger.critical(error_msg)
        print(f"{RED}Erro: {error_msg}")
        print(f"{YELLOW}Adicione ao .env na raiz do projeto:")
        for var in missing_vars:
            print(f"{CYAN}  {var}=<{required_vars[var]}>")
        exit(1)

    configs = {key: os.getenv(key) for key in required_vars}
    configs["DSN"] = f"{configs['ORACLE_HOST']}:{configs['ORACLE_PORT']}/{configs['ORACLE_SERVICE']}"

    try:
        configs["MAX_WORKERS"] = int(os.getenv("MAX_WORKERS", "20"))
        configs["SAVE_INTERVAL"] = int(os.getenv("SAVE_INTERVAL", "10"))
    except ValueError as e:
        logger.warning(f"Erro ao ler MAX_WORKERS/SAVE_INTERVAL do .env: {e}. Usando padrões.")
        configs["MAX_WORKERS"] = 20
        configs["SAVE_INTERVAL"] = 10
        print(f"{YELLOW}Aviso: Erro ao ler MAX_WORKERS/SAVE_INTERVAL. Usando padrões.")

    logger.info(f"Configurações para script principal: MAX_WORKERS={configs['MAX_WORKERS']}, SAVE_INTERVAL={configs['SAVE_INTERVAL']}")
    return configs

# --- Funções de Banco ---
def check_table_exists(cursor):
    """Verifica se a tabela de hardware existe no banco."""
    try:
        cursor.execute(f"SELECT 1 FROM {TABLE_NAME} WHERE 1=0")
        logger.info(f"Tabela {TABLE_NAME} encontrada.")
        return "TABLE_EXISTS"
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        if error_obj.code == 942: 
            logger.info(f"Tabela {TABLE_NAME} não encontrada.")
            return "TABLE_NOT_FOUND"
        logger.error(f"Erro DB ao verificar tabela {TABLE_NAME}: {str(e)} (Código: {error_obj.code})", exc_info=True)
        return "DB_ERROR"
    except Exception as e: 
        logger.error(f"Erro inesperado ao verificar tabela {TABLE_NAME}: {str(e)}", exc_info=True)
        return "DB_ERROR"

def create_oracle_table(cursor):
    """Cria a tabela de hardware no banco de dados Oracle."""
    create_table_sql = f"""
    CREATE TABLE {TABLE_NAME} (
        IP VARCHAR2(45), NROEMPRESA NUMBER(5) NOT NULL, NROCHECKOUT NUMBER(5) NOT NULL,
        SEGMENTO VARCHAR2(100), OPERACAO VARCHAR2(50), PLACA_MAE VARCHAR2(255),
        PROCESSADOR VARCHAR2(255), CORES_THREADS VARCHAR2(50), RAM VARCHAR2(50),
        DISCO VARCHAR2(50), ARMAZENAMENTO VARCHAR2(50), RELEASE VARCHAR2(100),
        STATUS VARCHAR2(10), DTAINCLUSAO DATE, DTAATUALIZACAO DATE,
        CONSTRAINT PK_BAR_HARDWARE_PDV PRIMARY KEY (NROEMPRESA, NROCHECKOUT)
    )"""
    try:
        cursor.execute(create_table_sql)
        logger.info(f"Tabela {TABLE_NAME} criada com sucesso.")
        print(f"{GREEN}Tabela {TABLE_NAME} criada com sucesso.")
        return True
    except Exception as e: 
        logger.error(f"Erro ao criar tabela {TABLE_NAME}: {str(e)}", exc_info=True)
        print(f"{RED}Erro ao criar tabela {TABLE_NAME}: {str(e)}")
        return False

def get_existing_data(cursor, nroempresa, nrocheckout):
    """Busca dados de hardware existentes para um PDV específico."""
    try:
        cursor.execute(
            f"SELECT IP, NROEMPRESA, NROCHECKOUT, SEGMENTO, OPERACAO, PLACA_MAE, PROCESSADOR, CORES_THREADS, RAM, DISCO, ARMAZENAMENTO, RELEASE, STATUS, DTAINCLUSAO, DTAATUALIZACAO FROM {TABLE_NAME} WHERE NROEMPRESA = :1 AND NROCHECKOUT = :2",
            (nroempresa, nrocheckout)
        )
        result = cursor.fetchone()
        if result:
            columns = [desc[0].upper() for desc in cursor.description]
            return dict(zip(columns, result))
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar dados existentes para PDV {nroempresa}-{nrocheckout}: {str(e)}", exc_info=True)
        return None

def has_relevant_data_changes(new_data_dict, existing_data_db_dict):
    """Verifica alterações nos campos de dados (IP, Info PDV, Hardware)."""
    if not existing_data_db_dict: 
        return True 
    
    fields_to_compare = PDV_INFO_FIELDS + HARDWARE_FIELDS
    for field in fields_to_compare:
        new_value = str(new_data_dict.get(field, "Não detectado")).strip()
        existing_value = str(existing_data_db_dict.get(field, "Não detectado")).strip()
        if new_value != existing_value:
            logger.info(f"Mudança de DADOS no PDV {new_data_dict.get('NROEMPRESA')}-{new_data_dict.get('NROCHECKOUT')}: Campo '{field}': Antigo='{existing_value}', Novo='{new_value}'")
            return True
    return False

def save_pdv_data(cursor, connection, batch_results):
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
            dest.DTAINCLUSAO = src.DTAINCLUSAO_VAL, dest.DTAATUALIZACAO = src.DTAATUALIZACAO_VAL
            WHERE DECODE(NVL(dest.IP, '#NULL#'), NVL(src.IP, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.SEGMENTO, '#NULL#'), NVL(src.SEGMENTO, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.OPERACAO, '#NULL#'), NVL(src.OPERACAO, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.PLACA_MAE, '#NULL#'), NVL(src.PLACA_MAE, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.PROCESSADOR, '#NULL#'), NVL(src.PROCESSADOR, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.CORES_THREADS, '#NULL#'), NVL(src.CORES_THREADS, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.RAM, '#NULL#'), NVL(src.RAM, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.DISCO, '#NULL#'), NVL(src.DISCO, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.ARMAZENAMENTO, '#NULL#'), NVL(src.ARMAZENAMENTO, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.RELEASE, '#NULL#'), NVL(src.RELEASE, '#NULL#'), 0, 1) = 1 OR
                  DECODE(NVL(dest.STATUS, '#NULL#'), NVL(src.STATUS, '#NULL#'), 0, 1) = 1 OR
                  dest.DTAINCLUSAO <> src.DTAINCLUSAO_VAL OR
                  dest.DTAATUALIZACAO <> src.DTAATUALIZACAO_VAL
        WHEN NOT MATCHED THEN INSERT (IP, NROEMPRESA, NROCHECKOUT, SEGMENTO, OPERACAO, PLACA_MAE, PROCESSADOR, CORES_THREADS, RAM, DISCO, ARMAZENAMENTO, RELEASE, STATUS, DTAINCLUSAO, DTAATUALIZACAO)
            VALUES (src.IP, src.NROEMPRESA, src.NROCHECKOUT, src.SEGMENTO, src.OPERACAO, src.PLACA_MAE, src.PROCESSADOR, src.CORES_THREADS, src.RAM, src.DISCO, src.ARMAZENAMENTO, src.RELEASE, src.STATUS, src.DTAINCLUSAO_VAL, src.DTAATUALIZACAO_VAL)
    """
    try:
        cursor.executemany(sql_merge, batch_results, batcherrors=True)
        connection.commit()
        rows_affected_count = cursor.rowcount
        batch_size = len(batch_results)
        for error in cursor.getbatcherrors(): 
            logger.error(f"Erro no batch Oracle na linha {error.offset}: {error.message}")
        logger.info(f"Lote de {batch_size} registros enviado ao Oracle (afetados: {rows_affected_count}).")
        return rows_affected_count, batch_size
    except Exception as e:
        logger.error(f"Erro crítico ao salvar dados no Oracle: {str(e)}", exc_info=True)
        tqdm.write(f"{RED}Erro DB/desconhecido ao salvar no Oracle: {str(e)}")
        if isinstance(e, oracledb.DatabaseError): 
            try: connection.rollback(); logger.info("Rollback da transação Oracle realizado.")
            except Exception as rb_e: logger.error(f"Erro ao tentar rollback: {rb_e}")
        return 0, len(batch_results) 

def mark_inactive_pdvs(cursor, connection, df_pdvs_ativos):
    """Marca PDVs como 'Inativo' se não estiverem mais na lista de PDVs ativos."""
    try:
        cursor.execute(f"SELECT NROEMPRESA, NROCHECKOUT FROM {TABLE_NAME} WHERE STATUS <> 'Inativo'")
        existing_pdvs_in_table = {(int(row[0]), int(row[1])) for row in cursor.fetchall()}
        
        active_pdvs_from_query = set()
        if not df_pdvs_ativos.empty:
            active_pdvs_from_query = {(int(row["NROEMPRESA"]), int(row["NROCHECKOUT"])) for _, row in df_pdvs_ativos.iterrows()}
        
        pdvs_to_mark_inactive = existing_pdvs_in_table - active_pdvs_from_query
        
        if pdvs_to_mark_inactive:
            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            update_payload = [{'new_status': 'Inativo', 'dtaatualizacao': current_time_str, 'nroempresa': ne, 'nrocheckout': nc} for ne, nc in pdvs_to_mark_inactive]
            
            cursor.executemany(
                f"UPDATE {TABLE_NAME} SET STATUS = :new_status, DTAATUALIZACAO = TO_DATE(:dtaatualizacao, 'YYYY-MM-DD HH24:MI:SS') WHERE NROEMPRESA = :nroempresa AND NROCHECKOUT = :nrocheckout",
                update_payload
            )
            connection.commit()
            logger.info(f"{len(pdvs_to_mark_inactive)} PDVs candidatos a 'Inativo'. Afetados no DB: {cursor.rowcount}.")
            # tqdm.write(f"{YELLOW}{cursor.rowcount} de {len(pdvs_to_mark_inactive)} PDVs marcados como 'Inativo'.") # Removido do terminal
        else:
            logger.info("Nenhum PDV encontrado para marcar como 'Inativo' nesta execução.")
            # tqdm.write(f"{GREEN}Nenhum PDV para marcar como 'Inativo'.") # Removido do terminal
            
    except Exception as e:
        logger.error(f"Erro ao marcar PDVs inativos: {str(e)}", exc_info=True)
        # tqdm.write(f"{RED}Erro ao marcar PDVs inativos: {str(e)}") # Opcional: remover ou manter para erros no terminal

def save_to_csv(batch_results_raw):
    """Salva um lote de dados de PDVs em um arquivo CSV."""
    if not batch_results_raw: return 0
    
    batch_results_for_csv = []
    for record_raw in batch_results_raw:
        record_csv = {key.replace('v_', ''): value for key, value in record_raw.items()}
        if 'DTAINCLUSAO_STR' in record_csv: record_csv['DTAINCLUSAO'] = record_csv.pop('DTAINCLUSAO_STR')
        if 'DTAATUALIZACAO_STR' in record_csv: record_csv['DTAATUALIZACAO'] = record_csv.pop('DTAATUALIZACAO_STR')
        batch_results_for_csv.append(record_csv)
        
    try:
        fieldnames = ["IP", "NROEMPRESA", "NROCHECKOUT", "SEGMENTO", "OPERACAO", "PLACA_MAE", 
                      "PROCESSADOR", "CORES_THREADS", "RAM", "DISCO", "ARMAZENAMENTO", 
                      "RELEASE", "STATUS", "DTAINCLUSAO", "DTAATUALIZACAO"]
        file_exists = os.path.exists(CSV_FILE)
        with open(CSV_FILE, mode='a' if file_exists else 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists: writer.writeheader()
            writer.writerows(batch_results_for_csv)
        logger.info(f"Salvos {len(batch_results_for_csv)} registros no CSV {CSV_FILE}.")
        return len(batch_results_for_csv)
    except Exception as e:
        logger.error(f"Erro ao salvar dados no CSV {CSV_FILE}: {str(e)}", exc_info=True)
        tqdm.write(f"{RED}Erro ao salvar dados no CSV: {str(e)}")
        return 0

def handle_table_not_found(cursor):
    """Interage com o usuário quando a tabela de hardware não é encontrada."""
    print(f"{YELLOW}Tabela {TABLE_NAME} não encontrada no banco de dados.")
    while True:
        print(f"{CYAN}Escolha uma opção:\n  1. Criar tabela {TABLE_NAME}\n  2. Exportar dados apenas para CSV ({CSV_FILE})\n  3. Sair")
        choice = input(f"{CYAN}Digite 1, 2 ou 3: {RESET}").strip()
        if choice == '1':
            if create_oracle_table(cursor): return "ORACLE"
            else: print(f"{RED}Falha ao criar tabela. Verifique logs e permissões. Tente novamente ou escolha outra opção.")
        elif choice == '2':
            print(f"{GREEN}Dados coletados serão salvos apenas em {CSV_FILE}."); return "CSV"
        elif choice == '3':
            print(f"{MAGENTA}Script encerrado pelo usuário."); exit(0)
        else: print(f"{YELLOW}Opção inválida. Por favor, digite 1, 2 ou 3.")

# --- Lógica Principal ---
def main():
    """Função principal para orquestrar a coleta e salvamento de dados de hardware dos PDVs."""
    try:
        from coletaPDV import get_hardware_info 
    except ImportError:
        logger.critical("ERRO FATAL: coletaPDV.py não encontrado ou função get_hardware_info não definida.")
        print(f"{RED}ERRO FATAL: coletaPDV.py não encontrado ou get_hardware_info não definida nele. Verifique o arquivo.")
        exit(1)

    db_connection = None; db_cursor = None; batch_buffer = []; processed_pdvs_count = 0
    output_mode = "ORACLE"; sucessos_coleta_efetiva = 0; total_registros_enviados_db = 0
    total_registros_afetados_db = 0; total_registros_salvos_csv = 0

    print(f"{MAGENTA}=== Iniciando Coleta de Hardware de PDVs ===")
    logger.info("=== INÍCIO DA EXECUÇÃO DO SCRIPT DE COLETA DE HARDWARE ===")

    try:
        configs = load_env_configs()
        
        print(f"{CYAN}Conectando ao Oracle ({configs['DSN']})...")
        db_connection = oracledb.connect(user=configs["ORACLE_USER"], password=configs["ORACLE_PASSWORD"], dsn=configs["DSN"])
        db_cursor = db_connection.cursor()
        print(f"{GREEN}Conexão Oracle estabelecida.")

        table_status = check_table_exists(db_cursor)
        if table_status == "TABLE_EXISTS": print(f"{GREEN}Tabela {TABLE_NAME} encontrada e pronta para uso.")
        elif table_status == "TABLE_NOT_FOUND": output_mode = handle_table_not_found(db_cursor)
        else: print(f"{RED}Erro crítico ao verificar tabela {TABLE_NAME}. Verifique os logs. Saindo."); return

        print(f"{CYAN}Buscando PDVs ativos da fonte de dados...")
        query_pdvs_ativos = """
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
        db_cursor.execute(query_pdvs_ativos)
        pdv_data_from_db = db_cursor.fetchall()
        df_pdvs = pd.DataFrame(pdv_data_from_db, columns=[d[0].upper() for d in db_cursor.description]) if pdv_data_from_db else pd.DataFrame()

        if df_pdvs.empty:
            logger.warning("Nenhum PDV ativo encontrado na consulta à TB_CHECKOUT.")
            print(f"{YELLOW}Nenhum PDV ativo encontrado para processar.")
            if output_mode == "ORACLE":
                logger.info("Verificando PDVs para marcar como 'Inativo' (nenhum PDV ativo encontrado).")
                mark_inactive_pdvs(db_cursor, db_connection, df_pdvs)
            print(f"{CYAN}Processo concluído."); return

        df_pdvs["NROEMPRESA"] = pd.to_numeric(df_pdvs["NROEMPRESA"])
        df_pdvs["NROCHECKOUT"] = pd.to_numeric(df_pdvs["NROCHECKOUT"])
        logger.info(f"Encontrados {len(df_pdvs)} PDVs ativos para processar.")
        print(f"{GREEN}Encontrados {len(df_pdvs)} PDVs ativos.")

        pdvs_args_list = [
            ({"IP": r["IP"], "NROEMPRESA": int(r["NROEMPRESA"]), 
              "NROCHECKOUT": int(r["NROCHECKOUT"]), "SEGMENTO": r["SEGMENTO"], 
              "OPERACAO": r["OPERACAO"]}, 
             configs["SSH_USERNAME"], configs["SSH_PASSWORD"]) 
            for _, r in df_pdvs.iterrows()
        ]
        total_pdvs_to_scan = len(pdvs_args_list)
        num_workers = min(configs["MAX_WORKERS"], total_pdvs_to_scan if total_pdvs_to_scan > 0 else 1)
        print(f"{CYAN}Iniciando coleta de {total_pdvs_to_scan} PDVs com {num_workers} workers...")
        
        with tqdm(total=total_pdvs_to_scan, desc=f"{CYAN}Escaneando PDVs", 
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
                  ncols=100) as progress_bar:
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                future_to_pdv_map = {
                    executor.submit(get_hardware_info, pa[0]["IP"], pa[1], pa[2]): pa[0] 
                    for pa in pdvs_args_list
                }

                for future in concurrent.futures.as_completed(future_to_pdv_map):
                    pdv_initial_info = future_to_pdv_map[future]
                    ip = pdv_initial_info["IP"]; nroempresa = pdv_initial_info["NROEMPRESA"]; nrocheckout = pdv_initial_info["NROCHECKOUT"]
                    current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    data_for_db = {
                        "IP": ip, "NROEMPRESA": nroempresa, "NROCHECKOUT": nrocheckout,
                        "SEGMENTO": pdv_initial_info["SEGMENTO"], "OPERACAO": pdv_initial_info["OPERACAO"]
                    }
                    for fld in HARDWARE_FIELDS: data_for_db[fld] = "Não detectado"

                    coleta_online = False 
                    hw_collection_result = None
                    status_retornado_coleta_debug = "Coleta não iniciada"

                    try:
                        hw_collection_result = future.result() 
                        logger.info(f"PDV {nroempresa}-{nrocheckout} (IP: {ip}): Resultado bruto da coleta: {hw_collection_result}")
                        
                        status_retornado_coleta_debug = hw_collection_result.get("status") # Chave "status" do coletaPDV.py
                        logger.info(f"PDV {nroempresa}-{nrocheckout} (IP: {ip}): 'status' de coletaPDV.py: '{status_retornado_coleta_debug}'")

                        if status_retornado_coleta_debug == "SUCESSO" or status_retornado_coleta_debug == "FALHA COMANDOS":
                            coleta_online = True
                            if status_retornado_coleta_debug == "FALHA COMANDOS":
                                logger.warning(f"PDV {nroempresa}-{nrocheckout} (IP: {ip}): Coleta retornou '{status_retornado_coleta_debug}'. PDV será ONLINE, hardware pode estar incompleto. Raw: {hw_collection_result}")
                    
                    except Exception as e_collect_thread:
                        logger.error(f"PDV {nroempresa}-{nrocheckout} (IP: {ip}): EXCEÇÃO na thread de coleta: {type(e_collect_thread).__name__} - {str(e_collect_thread)}", exc_info=True)
                        tqdm.write(f"{RED}Exceção na coleta do PDV {nroempresa}-{nrocheckout} (IP: {ip}): {type(e_collect_thread).__name__}")
                        status_retornado_coleta_debug = f"Exceção na thread: {type(e_collect_thread).__name__}"
                    
                    if coleta_online and hw_collection_result:
                        data_for_db["STATUS"] = "ONLINE"
                        for fld_key_db in HARDWARE_FIELDS: 
                            data_for_db[fld_key_db] = hw_collection_result.get(fld_key_db.lower(), "Não detectado")
                    else:
                        data_for_db["STATUS"] = "OFFLINE"
                        logger.warning(f"PDV {nroempresa}-{nrocheckout} (IP: {ip}) MARCADO COMO OFFLINE. Causa/Status da coleta: '{status_retornado_coleta_debug}'. Resultado bruto (se houver): {hw_collection_result}")
                    
                    existing_data_from_db = get_existing_data(db_cursor, nroempresa, nrocheckout) if output_mode == "ORACLE" else None
                    needs_db_write = False
                    dados_realmente_mudaram = False

                    if existing_data_from_db:
                        if data_for_db["STATUS"] == "OFFLINE":
                            for fld in HARDWARE_FIELDS: 
                                data_for_db[fld] = existing_data_from_db.get(fld, "Não detectado")
                        
                        dados_realmente_mudaram = has_relevant_data_changes(data_for_db, existing_data_from_db)

                        if data_for_db["STATUS"] == "ONLINE":
                            data_for_db["DTAATUALIZACAO"] = current_time_str
                            if dados_realmente_mudaram:
                                data_for_db["DTAINCLUSAO"] = current_time_str 
                            else: 
                                data_for_db["DTAINCLUSAO"] = existing_data_from_db["DTAINCLUSAO"].strftime('%Y-%m-%d %H:%M:%S')
                        else: # STATUS == "OFFLINE"
                            data_for_db["DTAINCLUSAO"] = existing_data_from_db["DTAINCLUSAO"].strftime('%Y-%m-%d %H:%M:%S')
                            data_for_db["DTAATUALIZACAO"] = current_time_str
                        
                        needs_db_write = True 
                    
                    else: # Novo PDV
                        data_for_db["DTAINCLUSAO"] = current_time_str
                        data_for_db["DTAATUALIZACAO"] = current_time_str
                        needs_db_write = True
                        dados_realmente_mudaram = True 
                    
                    if needs_db_write:
                        batch_entry = {
                            'v_IP': data_for_db.get("IP"), 'v_NROEMPRESA': data_for_db.get("NROEMPRESA"),
                            'v_NROCHECKOUT': data_for_db.get("NROCHECKOUT"), 'v_SEGMENTO': data_for_db.get("SEGMENTO"),
                            'v_OPERACAO': data_for_db.get("OPERACAO"),
                            'v_PLACA_MAE': data_for_db.get("PLACA_MAE", "Não detectado"),
                            'v_PROCESSADOR': data_for_db.get("PROCESSADOR", "Não detectado"),
                            'v_CORES_THREADS': data_for_db.get("CORES_THREADS", "Não detectado"),
                            'v_RAM': data_for_db.get("RAM", "Não detectado"),
                            'v_DISCO': data_for_db.get("DISCO", "Não detectado"),
                            'v_ARMAZENAMENTO': data_for_db.get("ARMAZENAMENTO", "Não detectado"),
                            'v_RELEASE': data_for_db.get("RELEASE", "Não detectado"),
                            'v_STATUS': data_for_db.get("STATUS"),
                            'v_DTAINCLUSAO_STR': data_for_db.get("DTAINCLUSAO"), 
                            'v_DTAATUALIZACAO_STR': data_for_db.get("DTAATUALIZACAO") 
                        }
                        batch_buffer.append(batch_entry)
                        
                        if data_for_db["STATUS"] == "ONLINE":
                            if not existing_data_from_db or dados_realmente_mudaram or \
                               (existing_data_from_db and existing_data_from_db.get("STATUS") != "ONLINE"):
                                sucessos_coleta_efetiva += 1

                        if len(batch_buffer) >= configs["SAVE_INTERVAL"]:
                            if output_mode == "ORACLE":
                                afetados, enviados = save_pdv_data(db_cursor, db_connection, batch_buffer)
                                total_registros_afetados_db += afetados; total_registros_enviados_db += enviados
                            else: total_registros_salvos_csv += save_to_csv(batch_buffer)
                            batch_buffer = []
                    
                    processed_pdvs_count +=1
                    progress_bar.update(1)
                    progress_bar.set_postfix_str(f"Último: {ip} ({data_for_db.get('STATUS', 'N/A')})")

        if batch_buffer:
            if output_mode == "ORACLE":
                afetados, enviados = save_pdv_data(db_cursor, db_connection, batch_buffer)
                total_registros_afetados_db += afetados; total_registros_enviados_db += enviados
            else: total_registros_salvos_csv += save_to_csv(batch_buffer)

        if output_mode == "ORACLE": 
            logger.info("Verificando PDVs para marcar como 'Inativo'...")
            mark_inactive_pdvs(db_cursor, db_connection, df_pdvs)

        print(f"\n{GREEN}=== Processo de Coleta Concluído ===")
        print(f"{CYAN}Total de PDVs na consulta de ativos: {total_pdvs_to_scan}")
        print(f"{CYAN}PDVs processados nesta execução: {processed_pdvs_count}")
        print(f"{GREEN}PDVs 'ONLINE' com escrita significativa: {sucessos_coleta_efetiva}")
        pdvs_outros_resultados = processed_pdvs_count - sucessos_coleta_efetiva
        if pdvs_outros_resultados >= 0: 
            print(f"{YELLOW}PDVs 'OFFLINE' ou 'ONLINE' sem mudanças de dados que contassem como 'sucesso': {pdvs_outros_resultados}")
        
        if output_mode == "ORACLE":
            print(f"{CYAN}Registros enviados para processamento no Oracle: {total_registros_enviados_db}")
            print(f"{CYAN}Registros efetivamente inseridos/atualizados no Oracle: {total_registros_afetados_db}")
        elif output_mode == "CSV": 
            print(f"{CYAN}Registros salvos no arquivo CSV: {total_registros_salvos_csv}")

    except oracledb.DatabaseError as oe: 
        error_obj, = oe.args
        logger.critical(f"Erro crítico de banco de dados Oracle: {str(oe)} (Código: {error_obj.code})", exc_info=True)
        print(f"{RED}Erro crítico de banco de dados Oracle: {str(oe)}")
        print(f"{YELLOW}Verifique credenciais, DSN, listener e permissões.")
    except ImportError as imp_err: 
        logger.critical(f"Erro de importação não tratado anteriormente: {str(imp_err)}", exc_info=True)
        print(f"{RED}Erro de Importação Crítico: {str(imp_err)}")
    except Exception as e_main: 
        logger.critical(f"Erro INESPERADO e crítico na execução principal: {str(e_main)}", exc_info=True)
        print(f"{RED}Erro Crítico Inesperado na Aplicação: {str(e_main)}")
    finally:
        if db_cursor:
            try: db_cursor.close(); print(f"{CYAN}Cursor Oracle fechado.")
            except Exception as e: logger.warning(f"Erro ao fechar cursor Oracle: {str(e)}", exc_info=True)
        if db_connection:
            try: db_connection.close(); print(f"{CYAN}Conexão Oracle fechada.")
            except Exception as e: logger.warning(f"Erro ao fechar conexão Oracle: {str(e)}", exc_info=True)
        
        print(f"{CYAN}Detalhes completos da execução no arquivo de log: {YELLOW}{LOG_FILE}{CYAN}.")
        if output_mode == "CSV": 
             print(f"{CYAN}Os dados (se houver) foram exportados para: {YELLOW}{CSV_FILE}{CYAN}.")
        logger.info("=== FIM DA EXECUÇÃO DO SCRIPT DE COLETA DE HARDWARE ===")

if __name__ == "__main__":
    main()