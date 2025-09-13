# -*- coding: utf-8 -*-
"""
inspector.py: Coletor de Dados de Hardware para o invent-ssh (The Definitive Edition).

Esta é a versão final e consolidada, incorporando todas as lições aprendidas
com os cenários de produção. A lógica foi reestruturada para máxima robustez
e para eliminar regressões.

Melhorias Definitivas:
- Lógica de RAM reconstruída para somar precisamente módulos de tamanhos
  diferentes e reportar o total real, sem arredondamentos falhos.
- Inferência de tipo de RAM baseada em velocidade (DDR2/DDR3) para hardware legado.
- Lógica de Armazenamento que previne o retorno 'N/A' e detecta NVMe.
"""
import paramiko
import re
import socket
import os
import json
from typing import Dict, Any, Optional

# --- Funções de Baixo Nível ---

def _clean_string(text: str) -> str:
    if not isinstance(text, str): return ""
    return " ".join(text.strip().split())

def _run_command(client: paramiko.SSHClient, command: str, tolerant: bool = False) -> Optional[str]:
    try:
        _, stdout, stderr = client.exec_command(command, timeout=20)
        output = stdout.read().decode('utf-8', errors='ignore').strip()
        exit_code = stderr.channel.recv_exit_status()
        if tolerant and output: return output
        if exit_code == 0: return output
        return None
    except Exception:
        return None

# --- Funções Auxiliares de Lógica ---

def _map_gib_to_commercial_gb(gib_value: float) -> str:
    if gib_value <= 0: return "N/A"
    commercial_sizes = [60, 120, 128, 240, 250, 256, 320, 480, 500, 512, 960, 1000, 2000, 4000, 8000]
    for size in commercial_sizes:
        commercial_gib_equivalent = size * (10**9) / (1024**3)
        if gib_value <= commercial_gib_equivalent + (commercial_gib_equivalent * 0.05):
            return f"{size}GB"
    return f"{int(round(gib_value * (1024**3) / (10**9)))}GB"

# --- Estratégia de Coleta Principal: INXI (JSON) ---

def _collect_with_inxi(client: paramiko.SSHClient) -> Optional[Dict[str, Any]]:
    inxi_output = _run_command(client, "inxi -FzJc0")
    if not inxi_output: return None
    try:
        data = json.loads(inxi_output)
        results = {}
        cpu = data.get('cpu', [{}])[0]; cores = cpu.get('cores', 0); threads = cpu.get('threads', 0)
        results['processador'] = cpu.get('model', 'N/A')
        results['cores_threads'] = f"{cores}/{threads}" if cores and threads else "N/A"
        results['placa_mae'] = data.get('machine', {}).get('mobo', 'N/A')
        mem = data.get('memory', {}); total_gb = mem.get('total-gb', 0)
        mem_type = next((d.get('type', '') for d in mem.get('arrays', [{}])[0].get('devices', []) if d.get('type')), '')
        results['ram'] = f"{int(round(total_gb))}GB {mem_type}".strip() if total_gb > 0 else "N/A"
        drives = data.get('drives', [])
        if drives:
            drive = drives[0]; disk_size_gib = drive.get('size-gb', 0)
            results['disk_type'] = "NVMe" if 'nvme' in drive.get('name', '').lower() else "SSD" if drive.get('is-ssd', False) else "HDD"
            results['disk_size'] = _map_gib_to_commercial_gb(disk_size_gib)
        system = data.get('system', {}); kernel = system.get('kernel', '').split(' ')[0]
        results['distro'] = system.get('distro', 'N/A')
        match = re.match(r"(\d+\.\d+)", kernel)
        results['kernel'] = match.group(1) if match else kernel
        if results.get('processador') != 'N/A' and results.get('ram') != 'N/A': return results
    except (json.JSONDecodeError, IndexError, KeyError): return None
    return None

# --- Estratégia de Fallback: Coleta Manual ---

def _collect_manually(client: paramiko.SSHClient) -> Dict[str, Any]:
    results = {}; results.update(_get_distro_info_manual(client)); results.update(_get_cpu_info_manual(client)); results.update(_get_motherboard_info_manual(client)); results.update(_get_memory_info_manual(client)); results.update(_get_storage_info_manual(client)); return results

def _get_distro_info_manual(client: paramiko.SSHClient) -> Dict[str, str]:
    info = {'distro': "Não foi possível obter", 'kernel': "N/A"}
    kernel_output = _run_command(client, "uname -r")
    if kernel_output:
        match = re.match(r"(\d+\.\d+)", kernel_output)
        info['kernel'] = match.group(1) if match else kernel_output
    output = _run_command(client, "lsb_release -ds") or _run_command(client, "cat /etc/os-release")
    if output:
        match = re.search(r'PRETTY_NAME="([^"]+)"', output) or re.search(r'DISTRIB_DESCRIPTION="([^"]+)"', output)
        if match: info['distro'] = _clean_string(match.group(1))
        elif "No LSB modules" not in output: info['distro'] = _clean_string(output.split('\n')[0])
    return info

def _get_cpu_info_manual(client: paramiko.SSHClient) -> Dict[str, str]:
    info = {'processador': "N/A", 'cores_threads': "N/A"}
    lscpu_output = _run_command(client, "lscpu")
    if lscpu_output:
        model_match = re.search(r"Model name:\s+(.+)", lscpu_output)
        if model_match: info['processador'] = _clean_string(model_match.group(1))
        try:
            cores_str = re.search(r"Core\(s\) per socket:\s+(\d+)", lscpu_output).group(1)
            sockets_str = re.search(r"Socket\(s\):\s+(\d+)", lscpu_output).group(1)
            threads_per_core_str = re.search(r"Thread\(s\) per core:\s+(\d+)", lscpu_output).group(1)
            total_cores = int(cores_str) * int(sockets_str)
            total_threads = total_cores * int(threads_per_core_str)
            info['cores_threads'] = f"{total_cores}/{total_threads}"
        except (AttributeError, ValueError): pass
    if info['processador'] == "N/A" or info['cores_threads'] == "N/A":
        cpuinfo_output = _run_command(client, "cat /proc/cpuinfo")
        if cpuinfo_output:
            if info['processador'] == "N/A":
                model_match = re.search(r"model name\s*:\s*(.+)", cpuinfo_output, re.IGNORECASE)
                if model_match: info['processador'] = _clean_string(model_match.group(1))
            if info['cores_threads'] == "N/A":
                threads = len(re.findall(r"^processor\s+:", cpuinfo_output, re.MULTILINE))
                cores = len(set(re.findall(r"core id\s+:\s+(\d+)", cpuinfo_output))) or threads
                if cores > 0 and threads > 0: info['cores_threads'] = f"{cores}/{threads}"
    return info

def _get_motherboard_info_manual(client: paramiko.SSHClient) -> Dict[str, str]:
    output = _run_command(client, "dmidecode -t baseboard", tolerant=True)
    if output:
        mfr = re.search(r"Manufacturer:\s+(.+)", output); prod = re.search(r"Product Name:\s+(.+)", output)
        vendor = _clean_string(mfr.group(1)) if mfr else ""; model = _clean_string(prod.group(1)) if prod else ""
        if "Not Spec" not in vendor and "Not Spec" not in model and (vendor or model): return {'placa_mae': f"{vendor} - {model}".strip(' -')}
    vendor = _run_command(client, "cat /sys/devices/virtual/dmi/id/board_vendor"); model = _run_command(client, "cat /sys/devices/virtual/dmi/id/board_name")
    if vendor or model:
        vendor, model = _clean_string(vendor), _clean_string(model)
        if "Not Spec" not in vendor and "Not Spec" not in model and (vendor or model): return {'placa_mae': f"{vendor} - {model}".strip(' -')}
    vendor = _run_command(client, "cat /sys/class/dmi/id/board_vendor"); model = _run_command(client, "cat /sys/class/dmi/id/board_name")
    if vendor or model:
        vendor, model = _clean_string(vendor), _clean_string(model)
        if (vendor and "empty" not in vendor.lower()) or (model and "empty" not in model.lower()): return {'placa_mae': f"{vendor} - {model}".strip(' -')}
    return {'placa_mae': "Não foi possível obter"}

def _get_memory_info_manual(client: paramiko.SSHClient) -> Dict[str, str]:
    info = {'ram': "N/A"}; mem_type = ""
    output = _run_command(client, "dmidecode -t memory", tolerant=True)
    if output:
        total_mb = 0; speed_mhz = 0
        device_blocks = output.split("Memory Device\n")
        for block in device_blocks[1:]:
            if "Not Installed" not in block and "No Module Installed" not in block:
                size_match = re.search(r"(?:Installed Size|Size):\s*(\d+)\s*(MB|GB)", block)
                if size_match:
                    size, unit = int(size_match.group(1)), size_match.group(2)
                    total_mb += size * 1024 if unit == "GB" else size
                if not mem_type:
                    type_line_match = re.search(r"Type:\s*(\S+)", block)
                    if type_line_match:
                        type_str = type_line_match.group(1).upper()
                        if "DDR5" in type_str: mem_type = " DDR5"
                        elif "DDR4" in type_str: mem_type = " DDR4"
                        elif "DDR3" in type_str: mem_type = " DDR3"
                        elif "DDR2" in type_str: mem_type = " DDR2"
                        elif "DDR" in type_str: mem_type = " DDR"
                if speed_mhz == 0:
                    speed_match = re.search(r"Speed:\s*(\d+)\s*MHz", block)
                    if speed_match: speed_mhz = int(speed_match.group(1))
        
        if not mem_type and speed_mhz > 0:
            if speed_mhz >= 2133: mem_type = " DDR4"
            elif speed_mhz > 1000: mem_type = " DDR3"
            elif speed_mhz <= 1000: mem_type = " DDR2"

        if total_mb > 0:
            info['ram'] = f"{int(round(total_mb / 1024))}GB" + mem_type
            return info
            
    output = _run_command(client, "cat /proc/meminfo")
    if output:
        mem_total_match = re.search(r"MemTotal:\s*(\d+)\s*kB", output)
        if mem_total_match:
            gb = int(mem_total_match.group(1)) / 1024**2
            info['ram'] = f"{int(round(gb))}GB"; return info
            
    return info

def _get_storage_info_manual(client: paramiko.SSHClient) -> Dict[str, str]:
    info = {'disk_type': "N/A", 'disk_size': "N/A"}
    primary_disk = _run_command(client, "lsblk -dno NAME,TYPE | grep -E 'disk|rom' | head -n 1 | awk '{print $1}'")
    if not primary_disk: return info

    if 'nvme' in primary_disk: info['disk_type'] = "NVMe"
    else:
        rotational = _run_command(client, f"cat /sys/block/{primary_disk}/queue/rotational")
        if rotational:
            if rotational.strip() == '0': info['disk_type'] = "SSD"
            elif rotational.strip() == '1': info['disk_type'] = "HDD"
    
    output = _run_command(client, f"hdparm -I /dev/{primary_disk}")
    if output:
        size_match = re.search(r"device size with M = 1000\*1000:.*?\((\d+)\s*GB\)", output)
        if size_match:
            info['disk_size'] = f"{size_match.group(1)}GB"
            if info['disk_type'] == "N/A" and "Nominal Media Rotation Rate" in output:
                rate_match = re.search(r"Nominal Media Rotation Rate:\s*(.+)", output)
                if rate_match and "Solid State" in rate_match.group(1): info['disk_type'] = "SSD"
            return info
            
    output = _run_command(client, f"fdisk -l /dev/{primary_disk}")
    if output:
        size_match = re.search(r"Disk /dev/[a-z\d]+:\s*([\d\.]+)\s*(GB|GiB|TB|TiB)", output)
        if size_match:
            val, unit = float(size_match.group(1)), size_match.group(2).upper().replace("I", "")
            gib_value = val if "G" in unit else (val * 1024)
            info['disk_size'] = _map_gib_to_commercial_gb(gib_value); return info
            
    output = _run_command(client, f"lsblk -d -b -o SIZE /dev/{primary_disk} | tail -n 1")
    if output and output.isdigit():
        gib = int(output) / 1024**3
        info['disk_size'] = _map_gib_to_commercial_gb(gib); return info
    
    return info

# --- Função Principal de Orquestração ---

def get_hardware_info(ip: str, username: str, password: Optional[str], key_path: Optional[str], timeout: int = 30) -> Dict[str, Any]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        pkey = None
        if key_path and os.path.exists(key_path):
            try: pkey = paramiko.Ed25519Key.from_private_key_file(key_path)
            except paramiko.SSHException: pkey = paramiko.RSAKey.from_private_key_file(key_path)
        client.connect(hostname=ip, username=username, password=password, pkey=pkey, timeout=timeout, auth_timeout=timeout, allow_agent=False, look_for_keys=False)
        
        inxi_results = _collect_with_inxi(client)
        if inxi_results:
            inxi_results['status'] = "SUCESSO"; return inxi_results
            
        manual_results = _collect_manually(client)
        manual_results['status'] = "SUCESSO"; return manual_results

    except paramiko.AuthenticationException: return {'status': "FALHA_AUTH", 'erro': "Falha na autenticação"}
    except (socket.timeout, paramiko.ssh_exception.NoValidConnectionsError, TimeoutError): return {'status': "FALHA_CONEXAO", 'erro': f"Timeout ao conectar no IP {ip}"}
    except paramiko.SSHException as e: return {'status': "ERRO_SSH", 'erro': f"Erro SSH: {e}"}
    except FileNotFoundError: return {'status': "FALHA_AUTH", 'erro': f"Chave SSH não encontrada: {key_path}"}
    except Exception as e: return {'status': "ERRO_DESCONHECIDO", 'erro': f"Erro inesperado: {e}"}
    finally: client.close()