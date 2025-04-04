import pandas as pd
import os
import paramiko
import time
import re
import logging
from tqdm import tqdm
import concurrent.futures
from openpyxl.styles import PatternFill

# Configuração de logging
logging.basicConfig(
    filename="hardware_scan.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Adicionar logger específico para validação de dados
validation_logger = logging.getLogger('validation')
validation_logger.setLevel(logging.INFO)
# Garantir que os logs de validação também vão para o arquivo principal
validation_logger.addHandler(logging.FileHandler("hardware_scan.log"))

# Configurações globais
CONNECTION_TIMEOUT = 8  # Timeout reduzido para acelerar falhas
COMMAND_TIMEOUT = 10    # Timeout para execução de comandos
MAX_WORKERS = 20        # Número máximo de threads paralelas
MAX_RETRIES = 2         # Número de tentativas para cada IP

class SSHClient:
    def __init__(self, ip, username, password, timeout=CONNECTION_TIMEOUT):
        self.ip = ip
        self.username = username
        self.password = password
        self.timeout = timeout
        self.client = None

    def connect(self):
        """Estabelece a conexão SSH"""
        if self.client is not None:
            return True
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.connect(
                self.ip, 
                username=self.username, 
                password=self.password, 
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False
            )
            return True
        except Exception as e:
            logging.error(f"Erro conectando a {self.ip}: {str(e)}")
            self.close()
            return False

    def execute_command(self, command, timeout=COMMAND_TIMEOUT):
        """Executa um comando SSH com timeout"""
        if self.client is None and not self.connect():
            return None
        try:
            # Verificar se self.client ainda é None após tentativa de conexão
            if self.client is None:
                return None
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error = stderr.read().decode("utf-8", errors="ignore").strip()
            if error and "command not found" in error:
                return None
            return output
        except Exception as e:
            logging.error(f"Erro executando comando em {self.ip}: {str(e)}")
            return None

    def close(self):
        """Fecha a conexão SSH"""
        if self.client:
            try:
                self.client.close()
                self.client = None
            except Exception as e:
                logging.warning(f"Erro fechando conexão com {self.ip}: {str(e)}")

def obter_iso_release(cliente):
    """
    Obtém a versão do kernel usando o comando 'uname -r'.
    Retorna apenas a parte principal da versão (ex.: 3.15, 4.15, 5.3).
    Ignora sufixos como "-generic".
    """
    comando = "uname -r"
    resultado = cliente.execute_command(comando)
    if resultado:
        resultado = resultado.strip()
        try:
            # Remover sufixos como "-generic"
            versao_base = resultado.split('-')[0]
            # Extrair até o segundo número (ex.: "3.15")
            partes = versao_base.split('.')
            if len(partes) >= 2:
                return f"{partes[0]}.{partes[1]}"
            return versao_base  # Caso não tenha formato esperado
        except Exception as e:
            logging.error(f"Erro ao processar versão do kernel '{resultado}': {str(e)}")
            return "Versão desconhecida"
    return "Não detectado"

def obter_fabricante_placa_mae(cliente):
    """
    Obtém o fabricante da placa-mãe.
    """
    comandos = [
        "dmidecode -t baseboard | grep 'Manufacturer' | cut -d ':' -f2 | tr -s ' '",
        "cat /sys/devices/virtual/dmi/id/board_vendor",
        "lshw -c motherboard | grep 'vendor:' | cut -d ':' -f2 | tr -s ' '",
        "inxi -M | grep 'Mobo:' | cut -d ':' -f2 | cut -d ' ' -f2"
    ]
    for comando in comandos:
        resultado = cliente.execute_command(comando)
        if resultado:
            return resultado.strip()
    return "Não detectado"

def obter_modelo_placa_mae(cliente):
    """
    Obtém o modelo da placa-mãe.
    """
    comandos = [
        "dmidecode -t baseboard | grep 'Product' | cut -d ':' -f2 | tr -s ' '",
        "cat /sys/devices/virtual/dmi/id/board_name",
        "lshw -c motherboard | grep 'product:' | cut -d ':' -f2 | tr -s ' '",
        "inxi -M | grep 'Model:' | cut -d ':' -f2 | tr -s ' '"
    ]
    for comando in comandos:
        resultado = cliente.execute_command(comando)
        if resultado:
            return resultado.strip()
    return "Não detectado"

def obter_info_processador(cliente):
    """
    Obtém informações detalhadas do processador com detecção melhorada de núcleos/threads.
    """
    # Modelo do processador
    comandos_modelo = [
        "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d ':' -f2 | tr -s ' '",
        "lscpu | grep 'Model name' | cut -d ':' -f2 | tr -s ' '",
        "inxi -C | grep 'model name' | cut -d ':' -f2 | tr -s ' '"
    ]
    modelo = "Não detectado"
    for comando in comandos_modelo:
        resultado = cliente.execute_command(comando)
        if resultado:
            modelo = resultado.strip()
            break

    # Método melhorado para obter núcleos físicos e threads
    comandos_nucleos_fisicos = [
        "lscpu | grep 'Core(s) per socket' | awk '{print $4}'",
        "grep 'cpu cores' /proc/cpuinfo | uniq | awk '{print $4}'",
        "cat /sys/devices/system/cpu/cpu*/topology/core_id | sort -u | wc -l"
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

    # Obter núcleos físicos por socket
    nucleos_por_socket = "1"  # valor padrão
    for comando in comandos_nucleos_fisicos:
        resultado = cliente.execute_command(comando)
        if resultado and resultado.strip().isdigit():
            nucleos_por_socket = resultado.strip()
            break

    # Obter número de sockets
    sockets = "1"  # valor padrão
    for comando in comandos_sockets:
        resultado = cliente.execute_command(comando)
        if resultado and resultado.strip().isdigit():
            sockets = resultado.strip()
            break

    # Calcular núcleos físicos totais
    nucleos_fisicos = (
        str(int(nucleos_por_socket) * int(sockets))
        if nucleos_por_socket.isdigit() and sockets.isdigit()
        else "1"
    )

    # Obter threads totais
    threads_total = "Não detectado"
    for comando in comandos_threads_totais:
        resultado = cliente.execute_command(comando)
        if resultado and resultado.strip().isdigit():
            threads_total = resultado.strip()
            break

    # Cálculo final de núcleos/threads
    nucleos_threads = (
        f"{nucleos_fisicos}/{threads_total}" 
        if nucleos_fisicos.isdigit() and threads_total.isdigit() 
        else "Não detectado"
    )
    return {
        "modelo": modelo,
        "nucleos_threads": nucleos_threads
    }

def obter_info_ram(cliente):
    """
    Obtém informações sobre a memória RAM, incluindo tipo (DDR3/DDR4), com detecção melhorada.
    """
    # Comandos para obter quantidade de RAM
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

    # Normalizar formato da quantidade de RAM
    if ram_quantidade != "Não detectado":
        try:
            match = re.search(r"(\d+\.?\d*)([GMK]i?B?)", ram_quantidade)
            if match:
                valor = float(match.group(1))
                unidade = match.group(2)[0].upper()  # G ou M
                if unidade == "M":
                    valor /= 1024
                    unidade = "G"
                # Arredondar para valores comerciais
                if valor <= 1.1:
                    ram_quantidade = "1GB"
                elif valor <= 2.1:
                    ram_quantidade = "2GB"
                elif valor <= 4.1:
                    ram_quantidade = "4GB"
                elif valor <= 8.1:
                    ram_quantidade = "8GB"
                elif valor <= 16.1:
                    ram_quantidade = "16GB"
                elif valor <= 32.1:
                    ram_quantidade = "32GB"
                else:
                    ram_quantidade = f"{int(valor)}GB"
        except Exception:
            pass

    # Tipo de RAM - Método significativamente melhorado para detectar o tipo de memória
    ram_tipo = "Não detectado"
    # Primeiro método: comandos diretos com grep extensivo
    comandos_tipo_ram = [
        "dmidecode -t memory | grep -i 'Type:' | grep -v 'Type Detail' | head -1",
        "dmidecode -t memory | grep -A20 'Memory Device' | grep -i 'Type:' | grep -v 'Type Detail' | head -1",
        "lshw -c memory | grep -i 'description:' | grep -i 'DDR' | head -1",
        "dmidecode -t memory | grep -i 'DDR' | head -1",
        "lspci | grep -i memory | grep -i 'DDR'"
    ]
    for comando in comandos_tipo_ram:
        resultado = cliente.execute_command(comando)
        if resultado:
            resultado = resultado.lower()
            if "ddr5" in resultado:
                ram_tipo = "DDR5"
                break
            elif "ddr4" in resultado:
                ram_tipo = "DDR4"
                break
            elif "ddr3" in resultado:
                ram_tipo = "DDR3"
                break
            elif "ddr2" in resultado:
                ram_tipo = "DDR2"
                break
            elif "ddr" in resultado:
                ram_tipo = "DDR"
                break

    # Segundo método: verificação mais aprofundada com dmidecode
    if ram_tipo == "Não detectado":
        cmd_detalhado = "dmidecode -t memory | grep -A40 'Memory Device' | grep -v 'Unknown'"
        resultado = cliente.execute_command(cmd_detalhado)
        if resultado:
            resultado = resultado.lower()
            if "ddr5" in resultado:
                ram_tipo = "DDR5"
            elif "ddr4" in resultado:
                ram_tipo = "DDR4"
            elif "ddr3" in resultado:
                ram_tipo = "DDR3"
            elif "ddr2" in resultado:
                ram_tipo = "DDR2"
            elif "ddr" in resultado:
                ram_tipo = "DDR"

    # Terceiro método: usar detecção da placa-mãe e idade do processador para inferir RAM
    if ram_tipo == "Não detectado":
        # Obter informações do processador
        cmd_cpu = "cat /proc/cpuinfo | grep 'model name' | head -1"
        resultado_cpu = cliente.execute_command(cmd_cpu)
        # Obter ano do BIOS para estimar idade
        cmd_bios = "dmidecode -s bios-release-date"
        resultado_bios = cliente.execute_command(cmd_bios)
        # Lógica para inferir tipo de RAM com base em CPU e ano
        if resultado_cpu:
            cpu_info = resultado_cpu.lower()
            # Processadores mais recentes normalmente usam DDR4
            if any(x in cpu_info for x in ["i3-9", "i5-9", "i7-9", "i3-8", "i5-8", "i7-8", 
                                          "ryzen 3", "ryzen 5", "ryzen 7", "i3-7", "i5-7", "i7-7"]):
                ram_tipo = "DDR4"
            # Processadores mais antigos normalmente usam DDR3
            elif any(x in cpu_info for x in ["i3-2", "i3-3", "i3-4", "i3-5", "i3-6",
                                            "i5-2", "i5-3", "i5-4", "i5-5", "i5-6",
                                            "i7-2", "i7-3", "i7-4", "i7-5", "i7-6",
                                            "pentium", "celeron"]):
                ram_tipo = "DDR3"
        # Se temos a data do BIOS, podemos usar para refinar a estimativa
        if resultado_bios and ram_tipo == "Não detectado":
            try:
                bios_year = int(resultado_bios.strip()[-4:])  # Extrair o ano
                if bios_year >= 2017:
                    ram_tipo = "DDR4"
                elif bios_year >= 2010:
                    ram_tipo = "DDR3"
                else:
                    ram_tipo = "DDR2"
            except:
                pass

    # Combinar quantidade e tipo
    if ram_quantidade != "Não detectado" and ram_tipo != "Não detectado":
        return f"{ram_quantidade} {ram_tipo}"
    elif ram_quantidade != "Não detectado":
        # Se ainda não detectou o tipo, tenta deduzir pela idade do sistema
        cmd_lsb = "lsb_release -d | grep -i 'Description'"
        resultado_lsb = cliente.execute_command(cmd_lsb)
        if resultado_lsb and ("16.04" in resultado_lsb or "18.04" in resultado_lsb):
            return f"{ram_quantidade} DDR4"
        elif resultado_lsb and ("14.04" in resultado_lsb or "12.04" in resultado_lsb):
            return f"{ram_quantidade} DDR3"
        else:
            return ram_quantidade
    else:
        return "Não detectado"

def obter_info_disco(cliente):
    """
    Obtém informações sobre o disco (tipo e capacidade).
    """
    # Primeiro, identificar discos principais
    cmd_listar_discos = "lsblk -d | grep -v loop | grep -v sr | awk '{print $1}' | head -3"
    resultado_discos = cliente.execute_command(cmd_listar_discos)
    discos = resultado_discos.strip().split('\n') if resultado_discos else ["sda"]

    # Tipo de disco - Tentando em múltiplos discos possíveis
    tipo_disco = "Não detectado"
    for disco in discos:
        # Corrigindo a sintaxe do lsblk
        comandos_tipo_disco = [
            f"lsblk -d -o name,rota /dev/{disco} 2>/dev/null | grep {disco} | awk '{{print $2}}'",
            f"cat /sys/block/{disco}/queue/rotational 2>/dev/null",
            f"smartctl -a /dev/{disco} 2>/dev/null | grep -i 'rotation rate\\|solid state device'",
            f"lshw -class disk | grep -i 'logical name.*{disco}' -A5 | grep -i 'solid\\|ssd\\|rotation'",
            # Método alternativo com hdparm
            f"hdparm -I /dev/{disco} 2>/dev/null | grep -i 'nominal media rotation rate\\|solid state'",
            # Verificar nome do modelo que frequentemente indica SSD
            f"smartctl -i /dev/{disco} 2>/dev/null | grep -i 'device model' | grep -i 'ssd'"
        ]
        for comando in comandos_tipo_disco:
            resultado = cliente.execute_command(comando)
            if resultado:
                resultado = resultado.lower()
                if "0" in resultado or "solid" in resultado or "ssd" in resultado or "not a rotating device" in resultado:
                    tipo_disco = "SSD"
                    break
                elif "1" in resultado or "rpm" in resultado or "rotational" in resultado:
                    tipo_disco = "HD"
                    break
        if tipo_disco != "Não detectado":
            break

    # Método alternativo baseado na velocidade de leitura (SSDs são mais rápidos)
    if tipo_disco == "Não detectado":
        for disco in discos:
            cmd_velocidade = f"hdparm -t /dev/{disco} 2>/dev/null | grep 'Timing buffered' || echo ''"
            resultado = cliente.execute_command(cmd_velocidade)
            if resultado and "MB/sec" in resultado:
                try:
                    # Extrair a velocidade
                    search_result = re.search(r'(\d+\.\d+) MB/sec', resultado)
                    if search_result is not None:
                        velocidade = float(search_result.group(1))
                        # SSDs tipicamente têm velocidades maiores que 100 MB/sec
                        if velocidade > 100:
                            tipo_disco = "SSD"
                        else:
                            tipo_disco = "HD"
                        break
                except:
                    pass

    # Último recurso: inferir pelo nome do dispositivo ou tamanho
    if tipo_disco == "Não detectado":
        cmd_info_discos = "lsblk -d -b"
        resultado = cliente.execute_command(cmd_info_discos)
        if resultado:
            # SSDs comerciais pequenos comuns (até 256GB), HDs raramente abaixo de 320GB
            for linha in resultado.splitlines():
                if "loop" in linha or "sr" in linha:
                    continue
                partes = linha.split()
                if len(partes) >= 4:
                    try:
                        tamanho = int(partes[3])
                        if "nvme" in partes[0]:  # NVMe são sempre SSDs
                            tipo_disco = "SSD"
                            break
                        # Inferência por tamanho (SSDs pequenos são comuns)
                        if tamanho <= 256_000_000_000:  # ~256GB
                            tipo_disco = "SSD"
                            break
                        if tamanho >= 1_000_000_000_000:  # ~1TB
                            tipo_disco = "HD"  # Mais provável ser HD para discos grandes
                    except:
                        pass

    # Capacidade de armazenamento - Comando melhorado para obter o tamanho total do disco físico
    comandos_armazenamento = [
        # Comandos específicos para tamanho físico do disco
        "lsblk -dbn -o SIZE /dev/sda 2>/dev/null || echo 'Não identificado'",
        "fdisk -l 2>/dev/null | grep 'Disk /dev/sda' | awk '{print $5}'",
        "smartctl -i /dev/sda 2>/dev/null | grep 'User Capacity' | cut -d '[' -f2 | cut -d ']' -f1",
        # Comandos de backup
        "lsblk -b -d -o size | head -2 | tail -1",
        "df -B1 --total | grep total | awk '{print $2}'"
    ]
    armazenamento = "Não detectado"
    for comando in comandos_armazenamento:
        resultado = cliente.execute_command(comando)
        if resultado:
            try:
                # Se o resultado for numérico (bytes)
                if resultado.isdigit():
                    tamanho_bytes = int(resultado)
                    if tamanho_bytes > 0:  # Ignorar valores zero
                        if tamanho_bytes >= 1_000_000_000_000:  # 1TB ou mais
                            armazenamento = f"{tamanho_bytes / 1_000_000_000_000:.1f}TB"
                        else:
                            armazenamento = f"{tamanho_bytes / 1_000_000_000:.0f}GB"
                        break
                else:
                    # Procurar padrões como "120GB" ou "500 GB" ou "1TB"
                    match = re.search(r"(\d+\.?\d*)([GMKTP]i?B?)", resultado)
                    if match is not None:
                        valor = float(match.group(1))
                        unidade = match.group(2)[0].upper()  # G, T, etc.
                        if unidade == "T":
                            armazenamento = f"{valor}TB"
                        elif unidade == "G":
                            armazenamento = f"{valor}GB"
                        elif unidade == "M":
                            armazenamento = f"{valor / 1000:.1f}GB"
                        break
            except Exception as e:
                logging.error(f"Erro ao processar tamanho do disco: {str(e)}")
                continue

    # Se não conseguiu detectar o tamanho, tenta um último método mais agressivo
    if armazenamento == "Não detectado" or armazenamento == "0GB":
        try:
            # Listar todos os dispositivos de bloco e somar seus tamanhos
            cmd = "lsblk -dbn -o NAME,SIZE | grep -v loop | grep -v sr | awk '{sum += $2} END {print sum}'"
            resultado = cliente.execute_command(cmd)
            if resultado and resultado.isdigit() and int(resultado) > 0:
                tamanho_bytes = int(resultado)
                if tamanho_bytes >= 1_000_000_000_000:  # 1TB ou mais
                    armazenamento = f"{tamanho_bytes / 1_000_000_000_000:.1f}TB"
                else:
                    armazenamento = f"{tamanho_bytes / 1_000_000_000:.0f}GB"
        except Exception as e:
            logging.error(f"Erro no método alternativo de detecção de disco: {str(e)}")
    
    return {"tipo": tipo_disco, "capacidade": armazenamento}

def get_hardware_info(ip, username, password, retry=0):
    """
    Coleta todas as informações de hardware de um único PDV
    """
    try:
        # Criar cliente SSH e conectar
        client = SSHClient(ip, username, password)
        if not client.connect():
            return {"erro": "Falha na conexão SSH"}

        # Coletar informações usando métodos da versão original
        fabricante_placa_mae = obter_fabricante_placa_mae(client)
        modelo_placa_mae = obter_modelo_placa_mae(client)
        info_processador = obter_info_processador(client)
        info_ram = obter_info_ram(client)
        info_disco = obter_info_disco(client)
        iso_release = obter_iso_release(client)

        # Fechar conexão
        client.close()

        # Combinar fabricante e modelo da placa-mãe
        placa_mae = "Não detectado"
        if fabricante_placa_mae != "Não detectado" and modelo_placa_mae != "Não detectado":
            placa_mae = f"{fabricante_placa_mae} - {modelo_placa_mae}"
        elif fabricante_placa_mae != "Não detectado":
            placa_mae = fabricante_placa_mae
        elif modelo_placa_mae != "Não detectado":
            placa_mae = modelo_placa_mae

        return {
            "placa-mãe": placa_mae,
            "processador": info_processador["modelo"],
            "cores/threads": info_processador["nucleos_threads"],
            "ram": info_ram,
            "disco": info_disco["tipo"],
            "armazenamento": info_disco["capacidade"],
            "release": iso_release
        }
    except Exception as e:
        if retry < MAX_RETRIES:
            time.sleep(1)
            return get_hardware_info(ip, username, password, retry + 1)
        logging.error(f"Erro processando hardware para IP {ip}: {str(e)}")
        return {"erro": f"Erro: {str(e)}"}

def extrair_info_pdv(descricao):
    """
    Extrai o número do PDV a partir da string de descrição.
    """
    if not isinstance(descricao, str):
        return "Desconhecido"
    # Procurar por padrões como "PDV X" ou "PDV-X" na descrição
    match = re.search(r'PDV[\s-]*(\d+)', descricao)
    if match is not None:
        return f"PDV {match.group(1)}"
    # Se não encontrar o padrão PDV, verificar por SelfCheckout
    if "SelfCheckout" in descricao:
        return "SelfCheckout"
    # Caso não encontre nada específico
    return descricao

def process_ip(args):
    """Função para processar um único IP (usada na thread pool)"""
    ip, username, password, info_pdv = args
    print(f"Coletando informações do {info_pdv} (IP: {ip})...")
    info_hardware = get_hardware_info(ip, username, password)
    # Adicionar status
    if "erro" in info_hardware:
        info_hardware["STATUS"] = info_hardware["erro"]
        del info_hardware["erro"]
    else:
        info_hardware["STATUS"] = "Sucesso"
    return ip, info_hardware

# Lista de processadores obsoletos
PROCESSADORES_OBSOLETOS = [
    "Intel(R) Celeron(R) CPU G1820",
    "Intel(R) Celeron(R) CPU J1800",
    "Intel(R) Celeron(R) CPU G3900",
    "Intel(R) Atom(TM) CPU D2550",
    "Intel(R) Atom(TM) CPU D2500",
    "Intel(R) Celeron(R) CPU G3930",
    "Intel(R) Pentium(R) CPU G620",
    "Pentium(R) Dual-Core CPU E5300",
    "Pentium(R) Dual-Core CPU E5800",
    "Intel(R) Celeron(R) CPU 847",
    "Intel(R) Core(TM) i5-2400 CPU @ 3.10GHz"
]

# Função para verificar se o processador é obsoleto
def is_processador_obsoleto(processador):
    if pd.isna(processador) or str(processador).strip() == "":
        return False
    return any(proc in str(processador) for proc in PROCESSADORES_OBSOLETOS)

# Função para verificar se a RAM está abaixo do ideal (menos de 4GB)
def is_ram_baixa(ram):
    if pd.isna(ram) or str(ram).strip() == "":
        return False
    try:
        ram_str = str(ram)
        if "GB" not in ram_str:
            return False
        # Extrai apenas os números antes de "GB"
        capacidade_str = ''.join(c for c in ram_str.split("GB")[0] if c.isdigit())
        if not capacidade_str:
            return False
        capacidade_gb = int(capacidade_str)
        return capacidade_gb < 4
    except (AttributeError, ValueError):
        return False

# Função para verificar se o disco é HD
def is_hd_lento(disco):
    if pd.isna(disco):
        return False
    return "HD" in str(disco)

# Função para determinar a prioridade
def determinar_prioridade(row):
    if pd.isna(row["PROCESSADOR"]) or str(row["PROCESSADOR"]).strip() == "":
        return "Offline"
    
    processador_obsoleto = is_processador_obsoleto(row["PROCESSADOR"])
    ram_baixa = is_ram_baixa(row["RAM"])
    hd_lento = is_hd_lento(row["DISCO"])

    if processador_obsoleto:
        return "Alta"
    elif ram_baixa and hd_lento:
        return "Alta"
    elif ram_baixa or hd_lento:
        return "Média"
    else:
        return ""  # Prioridade baixa fica em branco

# Função para determinar o motivo do upgrade
def determinar_motivo(row):
    motivos = []

    if pd.isna(row["PROCESSADOR"]) or str(row["PROCESSADOR"]).strip() == "":
        return ""
    
    if is_processador_obsoleto(row["PROCESSADOR"]):
        motivos.append("Processador em obsolência")
    if is_ram_baixa(row["RAM"]):
        motivos.append("RAM abaixo do ideal")
    if is_hd_lento(row["DISCO"]):
        motivos.append("HD lento")

    return "; ".join(motivos) if motivos else ""

def main():
    # Obter o diretório onde o script está localizado
    caminho_base = os.path.dirname(os.path.abspath(__file__))
    arquivo_entrada = os.path.join(caminho_base, "lista ip.xlsx")
    arquivo_saida = os.path.join(caminho_base, "lista ip retorno.xlsx")
    
    try:
        # Ler planilha de entrada
        print(f"Lendo arquivo: {arquivo_entrada}")
        df_pdvs = pd.read_excel(arquivo_entrada)
        
        # Verificar se a coluna IP existe
        if "IP" not in df_pdvs.columns:
            raise ValueError("A coluna 'IP' não foi encontrada na planilha")
        
        # Mapeamento de colunas antigas para novas
        mapeamento_colunas = {
            "FABRICANTE_PLACA_MAE": "PLACA-MÃE",  # Alterado de "MOTHERBOARD" para "PLACA-MÃE"
            "MODELO_PLACA_MAE": None,  # Será removida pois será combinada
            "NUCLEOS_THREADS": "CORES/THREADS",
            "TIPO_DISCO": "DISCO",
            "ISO_RELEASE": "RELEASE"
        }
        
        # Adicionar colunas para as informações de hardware
        colunas_hardware = [
            "PLACA-MÃE", "PROCESSADOR", "CORES/THREADS",  # Alterado de "MOTHERBOARD" para "PLACA-MÃE"
            "RAM", "DISCO", "ARMAZENAMENTO", "RELEASE", "STATUS"
        ]
        for coluna in colunas_hardware:
            if coluna not in df_pdvs.columns:
                df_pdvs[coluna] = ""
        
        # Solicitar credenciais
        username = input("Digite o nome de usuário para SSH (padrão: root): ") or "root"
        password = input("Digite a senha para SSH: ")
        
        # Criar lista de IPs com informações PDV para processamento
        ips_to_process = []
        for indice, linha in df_pdvs.iterrows():
            ip = linha["IP"]
            # Obter informação do PDV a partir das novas colunas
            if "DESCRICAO" in df_pdvs.columns:
                info_pdv = extrair_info_pdv(linha["DESCRICAO"])
            else:
                info_pdv = f"IP {ip}"  # Fallback se não existir coluna DESCRICAO
            ips_to_process.append((ip, username, password, info_pdv))
        
        # Número de threads a usar (ajustar conforme hardware disponível)
        num_workers = min(MAX_WORKERS, len(ips_to_process))
        print(f"Processando {len(ips_to_process)} IPs com {num_workers} threads paralelas...")
        
        # Dicionário para armazenar resultados
        results = {}
        progress_bar = tqdm(total=len(ips_to_process), desc="Escaneando PDVs")
        
        # Processar IPs em paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_ip = {executor.submit(process_ip, args): args for args in ips_to_process}
            # Salvar progresso parcial a cada N IPs processados
            save_interval = max(5, min(20, len(ips_to_process) // 10))  # Ajuste dinâmico
            completed = 0
            for future in concurrent.futures.as_completed(future_to_ip):
                ip, info = future.result()
                results[ip] = info
                # Atualizar barra de progresso
                progress_bar.update(1)
                completed += 1
                # Salvar progresso parcial
                if completed % save_interval == 0 or completed == len(ips_to_process):
                    # Atualizar DataFrame com resultados obtidos até agora, aplicando regras de validação
                    for idx, row in df_pdvs.iterrows():
                        ip = row["IP"]
                        if ip in results:
                            for key, value in results[ip].items():
                                column_key = key.upper()
                                # Determinar a coluna correta para atualização
                                target_column = None
                                if column_key in mapeamento_colunas and mapeamento_colunas[column_key]:
                                    # Caso seja uma coluna que foi renomeada
                                    target_column = mapeamento_colunas[column_key]
                                elif column_key in df_pdvs.columns:
                                    # Caso seja uma coluna que manteve o nome
                                    target_column = column_key
                                
                                # Aplicar regras de validação se a coluna existe
                                if target_column:
                                    current_value = df_pdvs.at[idx, target_column]
                                    # Regra 1: Se a célula estiver vazia, preencher com os novos dados
                                    if pd.isna(current_value) or current_value == "" or current_value == "Não detectado":
                                        df_pdvs.at[idx, target_column] = value
                                    # Regra 2: Se os valores forem diferentes, substituir os dados existentes
                                    elif str(current_value).strip() != str(value).strip():
                                        df_pdvs.at[idx, target_column] = value
                                    # Se os valores forem iguais, manter os dados existentes (não faz nada)
                    # Salvar arquivo temporário
                    try:
                        temp_file = f"{arquivo_saida}.temp"
                        df_pdvs.to_excel(temp_file, index=False)
                        if os.path.exists(arquivo_saida):
                            os.replace(temp_file, arquivo_saida)
                        else:
                            os.rename(temp_file, arquivo_saida)
                        print(f"Progresso salvo: {completed}/{len(ips_to_process)} PDVs processados")
                    except Exception as e:
                        print(f"Erro ao salvar progresso: {str(e)}")
        
        progress_bar.close()
        
        # Atualizar DataFrame com todos os resultados, aplicando regras de validação
        for idx, row in df_pdvs.iterrows():
            ip = row["IP"]
            if ip in results:
                for key, value in results[ip].items():
                    column_key = key.upper()
                    # Verificar se existe mapeamento para essa coluna
                    mapped_column = None
                    for old_col, new_col in mapeamento_colunas.items():
                        if old_col.lower() == key.lower():
                            mapped_column = new_col
                            break
                    
                    # Determinar a coluna correta para atualização
                    target_column = None
                    if mapped_column and mapped_column in df_pdvs.columns:
                        target_column = mapped_column
                    elif column_key in df_pdvs.columns:
                        target_column = column_key
                    
                    # Aplicar regras de validação se a coluna existe
                    if target_column:
                        current_value = df_pdvs.at[idx, target_column]
                        # Regra 1: Se a célula estiver vazia, preencher com os novos dados
                        if pd.isna(current_value) or current_value == "" or current_value == "Não detectado":
                            df_pdvs.at[idx, target_column] = value
                            logging.info(f"IP {ip}, coluna {target_column}: Célula vazia preenchida com '{value}'")
                        # Regra 2: Se os valores forem diferentes, substituir os dados existentes
                        elif str(current_value).strip() != str(value).strip():
                            old_value = current_value
                            df_pdvs.at[idx, target_column] = value
                            logging.info(f"IP {ip}, coluna {target_column}: Valor atualizado de '{old_value}' para '{value}'")
                        # Se os valores forem iguais, manter os dados existentes (não faz nada)
        
        # Remover a coluna MODELO_PLACA_MAE já que foi combinada com FABRICANTE_PLACA_MAE
        if "MODELO_PLACA_MAE" in df_pdvs.columns:
            df_pdvs = df_pdvs.drop(columns=["MODELO_PLACA_MAE"])
        
        # Adicionar colunas de prioridade e motivo do upgrade
        if "PRIORIDADE" not in df_pdvs.columns:
            df_pdvs["PRIORIDADE"] = ""
        if "MOTIVO DO UPGRADE" not in df_pdvs.columns:
            df_pdvs["MOTIVO DO UPGRADE"] = ""
        
        # Aplicar funções para determinar prioridade e motivo
        print("Analisando prioridades de upgrade...")
        df_pdvs["PRIORIDADE"] = df_pdvs.apply(determinar_prioridade, axis=1)
        df_pdvs["MOTIVO DO UPGRADE"] = df_pdvs.apply(determinar_motivo, axis=1)
        
        # Salvar resultados finais com formatação de cores
        print(f"\nSalvando resultados em: {arquivo_saida}")
        
        with pd.ExcelWriter(arquivo_saida, engine="openpyxl") as writer:
            # Salvar o DataFrame no Excel
            df_pdvs.to_excel(writer, index=False, sheet_name="Sheet1")
            
            # Acessar a planilha para aplicar formatação
            workbook = writer.book
            worksheet = writer.sheets["Sheet1"]
            
            # Definir cores para a coluna PRIORIDADE
            fill_alta = PatternFill(start_color="ec6f50", end_color="ec6f50", fill_type="solid")  # Vermelho
            fill_media = PatternFill(start_color="ffe994", end_color="ffe994", fill_type="solid")  # Amarelo
            fill_baixa = PatternFill(start_color="77bc65", end_color="77bc65", fill_type="solid")  # Verde
            fill_offline = PatternFill(start_color="cccccc", end_color="cccccc", fill_type="solid")  # Cinza
            
            # Encontrar a coluna PRIORIDADE
            prioridade_col_idx = None
            for idx, col in enumerate(df_pdvs.columns, start=1):  # +1 porque openpyxl começa do 1, não do 0
                if col == "PRIORIDADE":
                    prioridade_col_idx = idx
                    break
            
            # Aplicar cores na coluna PRIORIDADE
            if prioridade_col_idx:
                for idx, row in enumerate(df_pdvs["PRIORIDADE"], start=2):  # Começa na linha 2 (cabeçalho está na linha 1)
                    cell = worksheet.cell(row=idx, column=prioridade_col_idx)
                    if row == "Alta":
                        cell.fill = fill_alta
                    elif row == "Média":
                        cell.fill = fill_media
                    elif row == "Offline":
                        cell.fill = fill_offline
                    elif row == "":
                        cell.fill = fill_baixa  # Células vazias (baixa prioridade) recebem cor verde
        
        # Estatísticas de sucesso
        sucessos = len([r for r in results.values() if r.get("STATUS") == "Sucesso"])
        print("\nProcesso concluído!")
        print(f"Total de PDVs processados: {len(df_pdvs)}")
        print(f"PDVs com sucesso: {sucessos}")
        print(f"PDVs com erro: {len(df_pdvs) - sucessos}")
        print(f"Verifique o arquivo: {arquivo_saida}")
    
    except Exception as e:
        logging.critical(f"Erro no processamento principal: {str(e)}")
        print(f"Ocorreu um erro: {str(e)}")
        print("Verifique o arquivo de log para mais detalhes.")

if __name__ == "__main__":
    main()