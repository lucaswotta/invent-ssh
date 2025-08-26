import paramiko
import re
import logging
import os
import time

logger = logging.getLogger(__name__) 

# Configurações operacionais lidas do ambiente
try:
    CONNECTION_TIMEOUT = int(os.getenv("CONNECTION_TIMEOUT", "8"))
    COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "10"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "2"))
except ValueError as e:
    logger.warning(f"Erro ao ler configuração numérica do .env para coletaPDV: {e}. Usando padrões.")
    CONNECTION_TIMEOUT = 8
    COMMAND_TIMEOUT = 10
    MAX_RETRIES = 2

logger.info(f"coletaPDV.py inicializado com: CONNECTION_TIMEOUT={CONNECTION_TIMEOUT}, COMMAND_TIMEOUT={COMMAND_TIMEOUT}, MAX_RETRIES={MAX_RETRIES}")

# -----------------------------------
# Classe Cliente SSH
# -----------------------------------
class SSHClient:
    """Um cliente SSH para conectar e executar comandos em hosts remotos."""
    def __init__(self, ip, username, password, timeout=CONNECTION_TIMEOUT):
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
        self.client = None
        logger.debug(f"SSHClient instanciado para {self.ip} com timeout {self.timeout}s.")

    def connect(self):
        """Estabelece a conexão SSH com o host."""
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            logger.debug(f"Reutilizando conexão SSH ativa para {self.ip}")
            return True
        
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            logger.debug(f"Tentando conectar SSH a {self.ip} como {self.username}...")
            self.client.connect(
                self.ip,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False
            )
            logger.info(f"Conexão SSH bem-sucedida para {self.ip}")
            return True
        except paramiko.AuthenticationException as auth_e:
            logger.error(f"Falha de AUTENTICAÇÃO SSH em {self.ip}: {str(auth_e)}")
            self.close() 
            return False 
        except Exception as e: 
            logger.error(f"Falha ao conectar SSH em {self.ip}: {type(e).__name__} - {str(e)}")
            self.close()
            return False

    def execute_command(self, command, timeout=COMMAND_TIMEOUT, use_sudo=False):
        """Executa um comando no host remoto e retorna a saída."""
        if not self.client or not self.client.get_transport() or not self.client.get_transport().is_active():
            logger.warning(f"Sem conexão SSH ativa para {self.ip} ao tentar executar '{command}'. Tentando reconectar.")
            if not self.connect(): 
                logger.error(f"Não foi possível reconectar a {self.ip} para executar '{command}'.")
                return None 
        
        if not self.client: 
             logger.error(f"Cliente SSH é None para {self.ip} mesmo após tentativa de reconexão.")
             return None

        cmd_to_exec = f"sudo -n {command}" if use_sudo and not command.strip().startswith("sudo") else command
        logger.debug(f"Executando comando em {self.ip}: '{cmd_to_exec}' com timeout {timeout}s")
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd_to_exec, timeout=timeout)
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error = stderr.read().decode("utf-8", errors="ignore").strip()
            
            logger.debug(f"Comando '{cmd_to_exec}' em {self.ip} STDOUT: '{output or "[vazio]"}'")
            
            if error:
                logger.warning(f"Comando '{cmd_to_exec}' em {self.ip} STDERR: '{error}'")
                if any(err_keyword in error.lower() for err_keyword in ["command not found", "não encontrado", "permission denied", "permissão negada", "sudo: a password is required"]):
                    logger.error(f"Falha crítica (permissão/comando não encontrado) ao executar '{cmd_to_exec}' em {self.ip}: {error}")
                    return None 
            return output
        except Exception as e: 
            logger.error(f"Erro ao executar comando '{cmd_to_exec}' em {self.ip}: {type(e).__name__} - {str(e)}")
            return None

    def close(self):
        """Fecha a conexão SSH, se estiver ativa."""
        if self.client:
            try:
                self.client.close()
                logger.info(f"Conexão SSH com {self.ip} fechada.")
            except Exception as e:
                logger.warning(f"Erro ao fechar conexão SSH com {self.ip}: {str(e)}")
            finally:
                self.client = None

# -----------------------------------------------------------------------------
# Funções de Coleta de Hardware
# -----------------------------------------------------------------------------
def obter_iso_release(cliente):
    comando = "uname -r"
    resultado = cliente.execute_command(comando)
    if resultado:
        resultado = resultado.strip()
        try:
            versao_base = resultado.split('-')[0]
            partes = versao_base.split('.')
            if len(partes) >= 2:
                return f"{partes[0]}.{partes[1]}"
            return versao_base
        except Exception as e:
            logger.error(f"Erro ao processar versão do kernel '{resultado}' para {cliente.ip}: {str(e)}")
            return "Não detectado"
    return "Não detectado"

def obter_fabricante_placa_mae(cliente):
    comandos = [
        "dmidecode -t baseboard | grep 'Manufacturer' | cut -d ':' -f2 | tr -s ' '",
        "cat /sys/devices/virtual/dmi/id/board_vendor",
        "lshw -c motherboard 2>/dev/null | grep 'vendor:' | cut -d ':' -f2 | tr -s ' '", 
        "inxi -M 2>/dev/null | grep 'Mobo:' | cut -d ':' -f2 | cut -d ' ' -f2" 
    ]
    for comando in comandos:
        for use_sudo in [True, False]: 
            resultado = cliente.execute_command(comando, use_sudo=use_sudo)
            if resultado:
                return resultado.strip()
    return "Não detectado"

def obter_modelo_placa_mae(cliente):
    comandos = [
        "dmidecode -t baseboard | grep 'Product' | cut -d ':' -f2 | tr -s ' '",
        "cat /sys/devices/virtual/dmi/id/board_name",
        "lshw -c motherboard 2>/dev/null | grep 'product:' | cut -d ':' -f2 | tr -s ' '", 
        "inxi -M 2>/dev/null | grep 'Model:' | cut -d ':' -f2 | tr -s ' '" 
    ]
    for comando in comandos:
        for use_sudo in [True, False]: 
            resultado = cliente.execute_command(comando, use_sudo=use_sudo)
            if resultado:
                return resultado.strip()
    return "Não detectado"

def obter_info_processador(cliente):
    comandos_modelo = [
        "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d ':' -f2 | tr -s ' '",
        "lscpu | grep 'Model name' | cut -d ':' -f2 | tr -s ' '",
        "inxi -C 2>/dev/null | grep 'model name' | cut -d ':' -f2 | tr -s ' '"
    ]
    modelo = "Não detectado"
    for comando in comandos_modelo:
        resultado = cliente.execute_command(comando) 
        if resultado:
            modelo = resultado.strip()
            break

    comandos_nucleos_fisicos = [
        "lscpu | grep 'Core(s) per socket' | awk '{print $4}'",
        "grep 'cpu cores' /proc/cpuinfo | uniq | awk '{print $4}'",
        "cat /sys/devices/system/cpu/cpu*/topology/core_id 2>/dev/null | sort -u | wc -l"
    ]
    comandos_sockets = [
        "lscpu | grep 'Socket(s)' | awk '{print $2}'",
        "dmidecode -t processor | grep 'Socket Designation' | wc -l"
    ]
    comandos_threads_totais = [
        "nproc",
        "grep -c ^processor /proc/cpuinfo",
        "lscpu | grep '^CPU(s):' | awk '{print $2}'"
    ]

    nucleos_por_socket = "1"
    for comando in comandos_nucleos_fisicos:
        resultado = cliente.execute_command(comando)
        if resultado and resultado.strip().isdigit():
            nucleos_por_socket = resultado.strip()
            break

    sockets = "1"
    for comando in comandos_sockets:
        for use_sudo in [True, False]: 
            resultado = cliente.execute_command(comando, use_sudo=use_sudo)
            if resultado and resultado.strip().isdigit():
                sockets = resultado.strip()
                break
        if sockets != "1" and sockets != "Não detectado": break

    nucleos_fisicos_calc = "1"
    if nucleos_por_socket.isdigit() and sockets.isdigit():
        try:
            nucleos_fisicos_calc = str(int(nucleos_por_socket) * int(sockets))
        except ValueError:
            logger.warning(f"Erro ao calcular nucleos físicos para {cliente.ip} com nucleos_por_socket='{nucleos_por_socket}', sockets='{sockets}'")


    threads_total = "Não detectado"
    for comando in comandos_threads_totais:
        resultado = cliente.execute_command(comando)
        if resultado and resultado.strip().isdigit():
            threads_total = resultado.strip()
            break

    nucleos_threads_str = "Não detectado"
    if nucleos_fisicos_calc != "Não detectado" and threads_total != "Não detectado":
        if nucleos_fisicos_calc.isdigit() and threads_total.isdigit():
             nucleos_threads_str = f"{nucleos_fisicos_calc}/{threads_total}"
    
    return {"modelo": modelo, "nucleos_threads": nucleos_threads_str}


def obter_info_ram(cliente):
    comandos_ram = [
        "free -h | grep Mem | awk '{print $2}'",
        "grep MemTotal /proc/meminfo | awk '{print $2/1024/1024 \"GB\"}'",
        "dmidecode -t memory | grep 'Size.*MB\\|Size.*GB' | head -1 | awk '{print $2$3}'"
    ]
    ram_quantidade = "Não detectado"
    for comando in comandos_ram:
        resultado = cliente.execute_command(comando)
        if resultado:
            ram_quantidade = resultado.strip()
            break

    if ram_quantidade != "Não detectado":
        try:
            match = re.search(r"(\d+\.?\d*)([GMK]i?B?)", ram_quantidade, re.IGNORECASE)
            if match:
                valor = float(match.group(1))
                unidade = match.group(2)[0].upper()
                if unidade == "M":
                    valor /= 1024
                    unidade = "G"
                if valor <= 1.1: ram_quantidade = "1GB"
                elif valor <= 2.1: ram_quantidade = "2GB"
                elif valor <= 4.1: ram_quantidade = "4GB"
                elif valor <= 8.1: ram_quantidade = "8GB"
                elif valor <= 16.1: ram_quantidade = "16GB"
                elif valor <= 32.1: ram_quantidade = "32GB"
                else: ram_quantidade = f"{int(round(valor))}GB"
        except Exception as e_ram_parse:
            logger.debug(f"Erro ao normalizar quantidade de RAM '{ram_quantidade}' para {cliente.ip}: {e_ram_parse}")


    ram_tipo = "Não detectado"
    comandos_tipo_ram = [
        "dmidecode -t memory | grep -i 'Type:' | grep -v 'Type Detail' | head -1",
        "dmidecode -t memory | grep -A20 'Memory Device' | grep -i 'Type:' | grep -v 'Type Detail' | head -1",
        "lshw -c memory 2>/dev/null | grep -i 'description:' | grep -i 'DDR' | head -1",
        "dmidecode -t memory | grep -i 'DDR' | head -1",
        "lspci 2>/dev/null | grep -i memory | grep -i 'DDR'"
    ]
    for comando in comandos_tipo_ram:
        for use_sudo in [True, False]:
            resultado = cliente.execute_command(comando, use_sudo=use_sudo)
            if resultado:
                res_lower = resultado.lower()
                if "ddr5" in res_lower: ram_tipo = "DDR5"; break
                elif "ddr4" in res_lower: ram_tipo = "DDR4"; break
                elif "ddr3" in res_lower: ram_tipo = "DDR3"; break
                elif "ddr2" in res_lower: ram_tipo = "DDR2"; break
                elif "ddr" in res_lower: ram_tipo = "DDR"; break
            if ram_tipo != "Não detectado": break
        if ram_tipo != "Não detectado": break
    
    if ram_tipo == "Não detectado": # Fallback com grep mais amplo em dmidecode
        cmd_detalhado = "dmidecode -t memory | grep -A40 'Memory Device' | grep -v 'Unknown'"
        resultado = cliente.execute_command(cmd_detalhado, use_sudo=True)
        if resultado:
            res_lower = resultado.lower()
            if "ddr5" in res_lower: ram_tipo = "DDR5"
            elif "ddr4" in res_lower: ram_tipo = "DDR4"
            elif "ddr3" in res_lower: ram_tipo = "DDR3"
            elif "ddr2" in res_lower: ram_tipo = "DDR2"
            elif "ddr" in res_lower: ram_tipo = "DDR"

    if ram_tipo == "Não detectado": # Fallback por CPU e BIOS date
        cmd_cpu = "cat /proc/cpuinfo | grep 'model name' | head -1"
        resultado_cpu = cliente.execute_command(cmd_cpu)
        cmd_bios = "dmidecode -s bios-release-date"
        resultado_bios = cliente.execute_command(cmd_bios, use_sudo=True)
        if resultado_cpu:
            cpu_info = resultado_cpu.lower()
            if any(x in cpu_info for x in ["i3-9", "i5-9", "i7-9", "i3-8", "i5-8", "i7-8", "ryzen 3", "ryzen 5", "ryzen 7", "i3-7", "i5-7", "i7-7"]): ram_tipo = "DDR4"
            elif any(x in cpu_info for x in ["i3-2", "i3-3", "i3-4", "i3-5", "i3-6", "i5-2", "i5-3", "i5-4", "i5-5", "i5-6", "i7-2", "i7-3", "i7-4", "i7-5", "i7-6", "pentium", "celeron"]): ram_tipo = "DDR3"
        if resultado_bios and ram_tipo == "Não detectado":
            try:
                bios_year_str = resultado_bios.strip()
                if bios_year_str and len(bios_year_str) >= 4 and bios_year_str[-4:].isdigit(): # Valida se os últimos 4 são dígitos
                    bios_year = int(bios_year_str[-4:])
                    if bios_year >= 2017: ram_tipo = "DDR4"
                    elif bios_year >= 2010: ram_tipo = "DDR3"
                    else: ram_tipo = "DDR2"
            except Exception as e_bios_year: 
                logger.debug(f"Erro ao parsear ano da BIOS '{resultado_bios}' para {cliente.ip}: {e_bios_year}")


    if ram_quantidade != "Não detectado" and ram_tipo != "Não detectado":
        return f"{ram_quantidade} {ram_tipo}"
    elif ram_quantidade != "Não detectado": # Fallback final com lsb_release
        cmd_lsb = "lsb_release -d 2>/dev/null | grep -i 'Description'"
        resultado_lsb = cliente.execute_command(cmd_lsb)
        if resultado_lsb:
            if any(ver in resultado_lsb for ver in ["16.04", "18.04", "20.04", "22.04"]): return f"{ram_quantidade} DDR4"
            elif any(ver in resultado_lsb for ver in ["14.04", "12.04"]): return f"{ram_quantidade} DDR3"
        return ram_quantidade
    return "Não detectado"

def obter_info_disco(cliente):
    cmd_listar_discos = "lsblk -d | grep -v loop | grep -v sr | awk '{print $1}' | head -3"
    resultado_discos = cliente.execute_command(cmd_listar_discos)
    discos = resultado_discos.strip().split('\n') if resultado_discos and resultado_discos.strip() else ["sda"]

    tipo_disco = "Não detectado"
    for disco_iter in discos:
        comandos_tipo_disco = [
            f"lsblk -d -o name,rota /dev/{disco_iter} 2>/dev/null | grep {disco_iter} | awk '{{print $2}}'",
            f"cat /sys/block/{disco_iter}/queue/rotational 2>/dev/null",
            f"smartctl -a /dev/{disco_iter} 2>/dev/null | grep -i 'rotation rate\\|solid state device'",
            f"lshw -class disk 2>/dev/null | grep -i 'logical name.*{disco_iter}' -A5 | grep -i 'solid\\|ssd\\|rotation'",
            f"hdparm -I /dev/{disco_iter} 2>/dev/null | grep -i 'nominal media rotation rate\\|solid state'",
            f"smartctl -i /dev/{disco_iter} 2>/dev/null | grep -i 'device model' | grep -i 'ssd'"
        ]
        for comando in comandos_tipo_disco:
            for use_sudo in [True, False]:
                resultado = cliente.execute_command(comando, use_sudo=use_sudo)
                if resultado:
                    resultado = resultado.lower()
                    if any(x in resultado for x in ["0", "solid", "ssd", "not a rotating device"]):
                        tipo_disco = "SSD"; break
                    elif any(x in resultado for x in ["1", "rpm", "rotational"]):
                        tipo_disco = "HD"; break
            if tipo_disco != "Não detectado": break
        if tipo_disco != "Não detectado": break
    
    if tipo_disco == "Não detectado":
        for disco_iter in discos:
            cmd_velocidade = f"hdparm -t /dev/{disco_iter} 2>/dev/null | grep 'Timing buffered' || echo ''"
            resultado = cliente.execute_command(cmd_velocidade, use_sudo=True)
            if resultado and "MB/sec" in resultado:
                try:
                    velocidade = float(re.search(r'(\d+\.\d+)\s*MB/sec', resultado).group(1)) # Adicionado \s*
                    tipo_disco = "SSD" if velocidade > 100 else "HD" # Seu threshold original
                    break
                except: pass # Ignora erros de regex ou float conversion
    
    if tipo_disco == "Não detectado":
        cmd_info_discos_lsblk = "lsblk -d -b"
        resultado = cliente.execute_command(cmd_info_discos_lsblk)
        if resultado:
            for linha in resultado.splitlines():
                if any(x in linha for x in ["loop", "sr"]): continue
                partes = linha.split()
                # Garante que a linha se refere a um dos discos identificados em `discos`
                if len(partes) >= 4 and partes[0] in discos: 
                    try:
                        tamanho = int(partes[3])
                        if "nvme" in partes[0].lower(): tipo_disco = "SSD"; break
                        if tamanho <= 256_000_000_000 : tipo_disco = "SSD"; break 
                        if tamanho >= 1_000_000_000_000: tipo_disco = "HD"; break
                    except: pass
            if tipo_disco != "Não detectado": pass

    disco_principal_para_capacidade = discos[0] if discos else "sda"

    comandos_armazenamento = [
        f"lsblk -dbn -o SIZE /dev/{disco_principal_para_capacidade} 2>/dev/null || echo 'Não identificado'", # Tenta com o disco principal primeiro
        "lsblk -dbn -o SIZE /dev/sda 2>/dev/null || echo 'Não identificado'", # Fallback para sda
        f"fdisk -l /dev/{disco_principal_para_capacidade} 2>/dev/null | grep 'Disk /dev/{disco_principal_para_capacidade}' | awk '{{print $5}}'",
        "fdisk -l /dev/sda 2>/dev/null | grep 'Disk /dev/sda' | awk '{print $5}'", 
        f"smartctl -i /dev/{disco_principal_para_capacidade} 2>/dev/null | grep 'User Capacity' | cut -d '[' -f2 | cut -d ']' -f1",
        "smartctl -i /dev/sda 2>/dev/null | grep 'User Capacity' | cut -d '[' -f2 | cut -d ']' -f1", 
        "lsblk -b -d -o size | head -2 | tail -1", # Pega o primeiro da lista geral de lsblk
        "df -B1 --total | grep total | awk '{print $2}'" # Total de todos os filesystems
    ]
    armazenamento = "Não detectado"
    for comando in comandos_armazenamento:
        for use_sudo in [True, False]: 
            resultado = cliente.execute_command(comando, use_sudo=use_sudo)
            if resultado and resultado.strip() and resultado.strip() != "Não identificado":
                try:
                    if resultado.isdigit(): 
                        tamanho_bytes = int(resultado)
                    else: 
                        match = re.search(r"(\d+\.?\d*)\s*([GMKTP]i?B?)", resultado.replace(",","."), re.IGNORECASE)
                        if not match: continue
                        
                        valor_num = float(match.group(1))
                        unidade_str = match.group(2).upper() if match.group(2) else "B"
                        
                        multiplicadores = {"B":1, "KB":1000, "MB":1000**2, "GB":1000**3, "TB":1000**4}
                        multiplicadores_iec = {"KIB":1024, "MIB":1024**2, "GIB":1024**3, "TIB":1024**4}
                        
                        mult = 1
                        if unidade_str in multiplicadores: mult = multiplicadores[unidade_str]
                        elif unidade_str in multiplicadores_iec: mult = multiplicadores_iec[unidade_str]
                        elif unidade_str: # Tenta K, M, G, T
                            first_char = unidade_str[0]
                            is_iec = "I" in unidade_str
                            if first_char == "K": mult = multiplicadores_iec["KIB"] if is_iec else multiplicadores["KB"]
                            elif first_char == "M": mult = multiplicadores_iec["MIB"] if is_iec else multiplicadores["MB"]
                            elif first_char == "G": mult = multiplicadores_iec["GIB"] if is_iec else multiplicadores["GB"]
                            elif first_char == "T": mult = multiplicadores_iec["TIB"] if is_iec else multiplicadores["TB"]
                        
                        tamanho_bytes = int(valor_num * mult)

                    if tamanho_bytes > 0:
                        
                        if tamanho_bytes >= 1_000_000_000_000: # TB (usando base 1000 para TB comercial)
                            armazenamento = f"{tamanho_bytes / (1000**4):.1f}TB".replace(".0TB", "TB") # Corrigido para 1000^4 para TB
                            if armazenamento == "0TB": # Se for menos de 0.05TB, mostrar em GB
                                armazenamento = f"{tamanho_bytes / (1000**3):.0f}GB"
                        else: # GB (usando base 1000 para GB comercial)
                            armazenamento = f"{tamanho_bytes / (1000**3):.0f}GB"
                        
                        logger.debug(f"PDV {cliente.ip}: Capacidade disco (bytes: {tamanho_bytes}, formatado: {armazenamento}) a partir de '{comando}'")
                        break 
                except ValueError as ve:
                    logger.debug(f"PDV {cliente.ip}: Erro de valor ao processar capacidade '{resultado}' de '{comando}': {ve}")
                except Exception as e:
                    logger.error(f"PDV {cliente.ip}: Erro geral ao processar capacidade '{resultado}' de '{comando}': {e}")
            if armazenamento not in ["Não detectado", "0GB", "0.0GB"]: break
        if armazenamento not in ["Não detectado", "0GB", "0.0GB"]: break

    if armazenamento == "Não detectado" or armazenamento == "0GB" or armazenamento == "0.0GB": # Fallback final (soma de discos)
        try:
            cmd_soma = "lsblk -dbn -o NAME,TYPE,SIZE | grep -v loop | grep -v rom | awk '$2==\"disk\" {sum += $3} END {if(sum>0){print sum}else{print \"\"}}'"
            resultado = cliente.execute_command(cmd_soma)
            if resultado and resultado.strip().isdigit() and int(resultado) > 0:
                tamanho_bytes = int(resultado)
                if tamanho_bytes >= 1_000_000_000_000:
                    armazenamento = f"{tamanho_bytes / (1000**4):.1f}TB".replace(".0TB", "TB")
                    if armazenamento == "0TB": armazenamento = f"{tamanho_bytes / (1000**3):.0f}GB"
                else:
                    armazenamento = f"{tamanho_bytes / (1000**3):.0f}GB"
                logger.info(f"PDV {cliente.ip}: Capacidade de disco (fallback soma lsblk): {armazenamento}")
        except Exception as e:
            logger.error(f"PDV {cliente.ip}: Erro no método alternativo de detecção de disco (soma lsblk): {e}")

    return {"tipo": tipo_disco, "capacidade": armazenamento}


# --- Função Principal de Coleta ---
def get_hardware_info(ip, username, password, retry=0):
    """
    Conecta a um PDV via SSH e coleta informações de hardware.
    """
    logger.info(f"Iniciando coleta de hardware para IP: {ip} (Tentativa: {retry + 1})")
    client = None 
    try:
        client = SSHClient(ip, username, password) 
        if not client.connect():
            return {"status": "FALHA SSH", "erro": f"Falha ao estabelecer conexão SSH com {ip}"}

        fabricante_placa_mae = obter_fabricante_placa_mae(client)
        modelo_placa_mae = obter_modelo_placa_mae(client)
        info_processador = obter_info_processador(client)
        info_ram = obter_info_ram(client)
        info_disco = obter_info_disco(client)
        iso_release = obter_iso_release(client)

        placa_mae_completa = "Não detectado"
        if fabricante_placa_mae != "Não detectado" and modelo_placa_mae != "Não detectado":
            placa_mae_completa = f"{fabricante_placa_mae.strip()} - {modelo_placa_mae.strip()}"
        elif fabricante_placa_mae != "Não detectado":
            placa_mae_completa = fabricante_placa_mae.strip()
        elif modelo_placa_mae != "Não detectado":
            placa_mae_completa = modelo_placa_mae.strip()
        
        hardware_info_dict = {
            "placa_mae": placa_mae_completa,
            "processador": info_processador["modelo"],
            "cores_threads": info_processador["nucleos_threads"],
            "ram": info_ram,
            "disco": info_disco["tipo"],
            "armazenamento": info_disco["capacidade"],
            "release": iso_release
        }
        
        dados_validos_cont = 0
        for key, value in hardware_info_dict.items():
            if value is not None and str(value).strip() not in ["", "Não detectado", "0/Não detectado", "1/1", "0GB", "0.0GB", "N/A/Não detectado", "N/A/N/A"]:
                dados_validos_cont+=1
        
        if dados_validos_cont >= 3: # Ajuste este threshold se necessário
            hardware_info_dict["status"] = "SUCESSO"
            logger.info(f"Coleta de hardware BEM-SUCEDIDA para {ip}. Dados: {hardware_info_dict}")
        else:
            hardware_info_dict["status"] = "FALHA COMANDOS" 
            logger.warning(f"Coleta para {ip} resultou em 'FALHA COMANDOS' (dados insuficientes ou não detectados). Dados: {hardware_info_dict}")

        return hardware_info_dict

    except paramiko.AuthenticationException as auth_e: 
        logger.error(f"Erro de AUTENTICAÇÃO SSH para IP {ip}: {str(auth_e)}")
        return {"status": "FALHA AUTENTICACAO", "erro": "Falha na autenticação SSH"}
    except Exception as e_main_get_hw: 
        if retry < MAX_RETRIES:
            logger.warning(f"Tentativa {retry+1}/{MAX_RETRIES+1} para {ip} falhou com erro: {type(e_main_get_hw).__name__} - {str(e_main_get_hw)}. Tentando novamente...")
            if client: client.close() 
            time.sleep(1) 
            return get_hardware_info(ip, username, password, retry + 1)
        
        logger.error(f"Erro FINAL processando hardware para IP {ip} após {MAX_RETRIES+1} tentativas: {type(e_main_get_hw).__name__} - {str(e_main_get_hw)}", exc_info=True)
        return {"status": "FALHA EXCECAO", "erro": f"Exceção final em {ip}: {type(e_main_get_hw).__name__} - {str(e_main_get_hw)}"}
    finally:
        if client: 
            client.close()