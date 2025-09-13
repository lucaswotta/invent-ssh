# -*- coding: utf-8 -*-
"""
core.py: O motor de negócio da aplicação invent-ssh (Versão de Produção).

Este módulo contém a lógica principal para carregar os dados dos terminais,
orquestrar a coleta de informações de hardware em paralelo e salvar os
resultados na fonte de destino (planilha ou banco de dados Oracle).
"""
import pandas as pd
import concurrent.futures
from datetime import datetime
import os
from queue import Queue
from typing import List, Dict, Any, Optional
import csv
import logging
from dataclasses import dataclass, asdict

from inspector import get_hardware_info

try:
    import oracledb
except ImportError:
    oracledb = None

@dataclass
class Terminal:
    """Representa um único terminal (PDV) a ser inventariado."""
    ip: str
    nro_empresa: Optional[int] = None
    nro_checkout: Optional[int] = None
    status: Optional[str] = None
    placa_mae: Optional[str] = None
    processador: Optional[str] = None
    cores_threads: Optional[str] = None
    ram: Optional[str] = None
    disk_type: Optional[str] = None
    disk_size: Optional[str] = None
    distro: Optional[str] = None
    kernel: Optional[str] = None
    dta_atualizacao: Optional[datetime] = None

class InventoryEngine:
    """
    Orquestra todo o processo de inventário em segundo plano, comunicando o
    progresso para a interface gráfica através de uma fila (queue).
    """
    def __init__(self, config: Dict[str, Any], log_queue: Queue):
        self.config = config
        self.log_queue = log_queue
        self.terminals: List[Terminal] = []
        self.logger = logging.getLogger(__name__)

    def log(self, level: str, message: str, value: Any = None):
        """Envia uma mensagem de log para a fila da UI e para o arquivo de log."""
        self.log_queue.put((level, message, value))
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, f"{message} | Valor: {value if value is not None else 'N/A'}")

    def run_inventory(self):
        """Ponto de entrada principal para iniciar o processo de inventário."""
        try:
            self.log("INFO", f"Iniciando inventário em 'Modo {self.config['mode']}'")
            self._load_terminals()
            if not self.terminals:
                self.log("ERROR", "Nenhum terminal encontrado. Processo abortado."); return
            self.log("INFO", f"{len(self.terminals)} terminais carregados. Iniciando coleta...")
            results = self._execute_collection()
            if not results:
                self.log("WARNING", "Nenhum dado de hardware foi coletado.")
            else:
                self.log("INFO", f"Coleta finalizada. {len(results)} resultados. Salvando...")
                self._save_results(results)
        except Exception as e:
            self.log("ERROR", f"Erro crítico no motor da aplicação: {e}")
            self.logger.critical("Erro crítico no InventoryEngine", exc_info=True)
        finally:
            self.log("FINISH", "Processo concluído!")

    def _load_terminals(self):
        """Direciona o carregamento dos terminais com base no modo de operação."""
        mode = self.config.get('mode')
        if mode == 'Planilha': self.terminals = self._load_from_spreadsheet()
        elif mode == 'Oracle': self.terminals = self._load_from_oracle()
        else: raise ValueError(f"Modo de operação desconhecido: {mode}")

    def _load_from_spreadsheet(self) -> List[Terminal]:
        """Carrega a lista de terminais de um arquivo .xlsx ou .csv."""
        filepath = self.config['filepath']
        try:
            df = pd.read_excel(filepath) if filepath.endswith(('.xlsx', '.xls')) else pd.read_csv(filepath, sep=None, engine='python')
            df.columns = [str(col).upper() for col in df.columns]
            if 'IP' not in df.columns: raise ValueError("O arquivo deve conter a coluna 'IP'")
            df.dropna(subset=['IP'], inplace=True)
            df = df[df['IP'].astype(str).str.strip() != '']
            return [Terminal(ip=r['IP'], nro_empresa=pd.to_numeric(r.get('NROEMPRESA'), errors='coerce'), nro_checkout=pd.to_numeric(r.get('NROCHECKOUT'), errors='coerce')) for _, r in df.iterrows()]
        except FileNotFoundError: self.log("ERROR", f"Arquivo não encontrado: {filepath}"); return []
        except ValueError as ve: self.log("ERROR", f"Erro de formatação na planilha: {ve}"); return []
        except Exception as e: self.log("ERROR", f"Falha ao ler planilha '{os.path.basename(filepath)}': {e}"); return []

    def _load_from_oracle(self) -> List[Terminal]:
        """Carrega a lista de terminais executando uma query em um banco de dados Oracle."""
        if oracledb is None: self.log("ERROR", "'oracledb' não está instalado. Modo Oracle desativado."); return []
        db_config = self.config['oracle_config']
        dsn = f"{db_config['host']}:{db_config['port']}/{db_config['service']}"
        try:
            self.log("INFO", f"Conectando ao Oracle em {db_config['host']}...")
            with oracledb.connect(user=db_config['user'], password=db_config['password'], dsn=dsn) as conn:
                with conn.cursor() as cursor:
                    self.log("INFO", "Executando query para buscar terminais...")
                    cursor.execute(self.config['oracle_query'])
                    cols = [d[0].upper() for d in cursor.description]
                    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
                    return [Terminal(ip=r['IP'], nro_empresa=r['NROEMPRESA'], nro_checkout=r['NROCHECKOUT']) for r in rows]
        except Exception as e: self.log("ERROR", f"Falha na conexão ou consulta ao Oracle: {e}"); return []

    def _execute_collection(self) -> List[Terminal]:
        """Executa a coleta de dados de hardware em paralelo para todos os terminais."""
        results: List[Terminal] = []
        total = len(self.terminals)
        conn_failures, processed, circuit_tripped = 0, 0, False
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
            future_map = {executor.submit(self._process_single_terminal, t): t for t in self.terminals}
            for i, future in enumerate(concurrent.futures.as_completed(future_map)):
                processed += 1
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        if result.status == "FALHA_CONEXAO": conn_failures += 1
                except Exception as exc: self.log("ERROR", f"Exceção ao processar {future_map[future].ip}: {exc}")
                if not circuit_tripped and processed >= 10 and conn_failures == processed:
                    self.log("ERROR", "Circuit Breaker: 10/10 conexões iniciais falharam. Abortando.")
                    self.log("ERROR", "Verifique credenciais SSH, rede ou firewall.")
                    circuit_tripped = True
                    [f.cancel() for f in future_map]; break
                self.log("PROGRESS", f"Processado: {future_map[future].ip}", (i + 1) / total * 100)
        return results

    def _process_single_terminal(self, terminal: Terminal) -> Optional[Terminal]:
        """Processa um único terminal, conectando via SSH e coletando os dados de hardware."""
        if not terminal.ip:
            terminal.status = "ERRO_SEM_IP"; terminal.dta_atualizacao = datetime.now()
            self.log("WARNING", f"Terminal ignorado por não possuir IP: {terminal}"); return terminal
        hw_info = get_hardware_info(ip=terminal.ip, username=self.config['ssh_user'], password=self.config.get('ssh_pass'), key_path=self.config.get('ssh_key_path'), timeout=self.config['ssh_timeout'])
        status = hw_info.get("status")
        if status == "SUCESSO":
            terminal.status = "ONLINE"; self.log("INFO", f"Sucesso na coleta de {terminal.ip}")
        else:
            terminal.status = "OFFLINE" if status == "FALHA_CONEXAO" else status
            self.log("WARNING", f"Falha em {terminal.ip}: {hw_info.get('erro', 'Falha geral')}")
        for key, value in hw_info.items(): setattr(terminal, key, value)
        terminal.dta_atualizacao = datetime.now()
        return terminal

    def _save_results(self, results: List[Terminal]):
        """Direciona o salvamento dos resultados com base na configuração."""
        if self.config.get('mode') == 'Oracle' and self.config.get('save_to_db', False):
            self._save_to_oracle(results)
        else:
            self._save_to_spreadsheet(results)

    def _save_to_spreadsheet(self, results: List[Terminal]):
        """Salva os resultados em um arquivo, garantindo a formatação correta."""
        try:
            df = pd.DataFrame([asdict(r) for r in results])
            df['dta_atualizacao'] = pd.to_datetime(df['dta_atualizacao']).dt.strftime('%Y-%m-%d %H:%M:%S')
            df.rename(columns=lambda c: c.upper(), inplace=True)
            df.rename(columns={'NRO_EMPRESA': 'NROEMPRESA', 'NRO_CHECKOUT': 'NROCHECKOUT', 'DTA_ATUALIZACAO': 'DTAATUALIZACAO', 'PLACA_MAE': 'PLACA_MAE', 'CORES_THREADS': 'CORES_THREADS', 'DISK_TYPE': 'TIPO_DISCO', 'DISK_SIZE': 'TAMANHO_DISCO'}, inplace=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = "reports"
            os.makedirs(output_dir, exist_ok=True)
            filename_suffix = self.config.get('output_format', 'XLSX').lower()
            filename = os.path.join(output_dir, f"inventario_hardware_{timestamp}.{filename_suffix}")
            if filename_suffix == 'csv':
                df.to_csv(filename, index=False, sep=';', encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
            else:
                df.to_excel(filename, index=False, engine='openpyxl')
            self.log("INFO", f"Resultados salvos com sucesso em '{filename}'")
            self.log("OPEN_FILE", "Abrindo arquivo de resultado...", os.path.abspath(filename))
        except Exception as e:
            self.log("ERROR", f"Falha ao salvar planilha de resultados: {e}")

    def _check_and_create_table(self, cursor: Any, table_name: str) -> bool:
        """Verifica se a tabela de destino existe no Oracle e, se não, tenta criá-la."""
        try:
            cursor.execute(f"SELECT 1 FROM {table_name} WHERE 1=0")
            self.log("INFO", f"Tabela '{table_name}' encontrada."); return True
        except oracledb.DatabaseError as e:
            if "ORA-00942" in str(e):
                self.log("WARNING", f"Tabela '{table_name}' não encontrada. Tentando criar...")
                pk_name = f"PK_{table_name.replace('.', '_')}"[:30]
                create_sql = (f"CREATE TABLE {table_name} (NROEMPRESA NUMBER(4), NROCHECKOUT NUMBER(4), IP VARCHAR2(15), STATUS VARCHAR2(20), PLACA_MAE VARCHAR2(100), PROCESSADOR VARCHAR2(100), CORES_THREADS VARCHAR2(10), RAM VARCHAR2(20), TIPO_DISCO VARCHAR2(10), TAMANHO_DISCO VARCHAR2(20), DISTRO VARCHAR2(100), KERNEL VARCHAR2(20), DTAINCLUSAO DATE, DTAATUALIZACAO DATE, CONSTRAINT {pk_name} PRIMARY KEY (NROEMPRESA, NROCHECKOUT))")
                try: cursor.execute(create_sql); self.log("INFO", f"Tabela '{table_name}' criada com sucesso."); return True
                except Exception as ce: self.log("ERROR", f"Falha ao criar a tabela '{table_name}': {ce}"); return False
            else: self.log("ERROR", f"Erro ao verificar a tabela '{table_name}': {e}"); raise e

    def _save_to_oracle(self, results: List[Terminal]):
        """Salva os resultados em uma tabela Oracle usando um comando MERGE."""
        if any(r.nro_empresa is None or r.nro_checkout is None for r in results):
            self.log("WARNING", "Oracle: Registros sem NROEMPRESA/NROCHECKOUT. Salvando em planilha."); self._save_to_spreadsheet(results); return
        db_config, table_name = self.config['oracle_config'], self.config['oracle_table']
        dsn = f"{db_config['host']}:{db_config['port']}/{db_config['service']}"
        merge_sql = (f"MERGE INTO {table_name} t USING (SELECT :nro_empresa AS NROEMPRESA, :nro_checkout AS NROCHECKOUT FROM DUAL) s ON (t.NROEMPRESA = s.NROEMPRESA AND t.NROCHECKOUT = s.NROCHECKOUT) WHEN MATCHED THEN UPDATE SET IP=:ip, STATUS=:status, PLACA_MAE=:placa_mae, PROCESSADOR=:processador, CORES_THREADS=:cores_threads, RAM=:ram, TIPO_DISCO=:disk_type, TAMANHO_DISCO=:disk_size, DISTRO=:distro, KERNEL=:kernel, DTAATUALIZACAO=:dta_atualizacao WHEN NOT MATCHED THEN INSERT (NROEMPRESA, NROCHECKOUT, IP, STATUS, PLACA_MAE, PROCESSADOR, CORES_THREADS, RAM, TIPO_DISCO, TAMANHO_DISCO, DISTRO, KERNEL, DTAINCLUSAO, DTAATUALIZACAO) VALUES (:nro_empresa, :nro_checkout, :ip, :status, :placa_mae, :processador, :cores_threads, :ram, :disk_type, :disk_size, :distro, :kernel, :dta_atualizacao, :dta_atualizacao)")
        try:
            with oracledb.connect(user=db_config['user'], password=db_config['password'], dsn=dsn) as conn:
                with conn.cursor() as cursor:
                    if not self._check_and_create_table(cursor, table_name): self.log("ERROR", "Abortado: tabela não pôde ser criada/encontrada."); return
                    cursor.executemany(merge_sql, [asdict(r) for r in results], batcherrors=True)
                    conn.commit(); self.log("INFO", f"{cursor.rowcount} registros salvos/atualizados em '{table_name}'.")
        except Exception as e: self.log("ERROR", f"Erro crítico ao salvar no Oracle: {e}")