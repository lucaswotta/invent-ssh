"""Cross-distro hardware parsing tests using anonymized command-output fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from i18n import get_language, set_language
import inspector


class HardwareParserTests(unittest.TestCase):
    def test_os_release_unquotes_values(self):
        parsed = inspector._parse_os_release(
            'NAME="Example Linux"\nID=example\nVERSION_ID="42"\nPRETTY_NAME="Example Linux 42 (Stone)"\n'
        )
        self.assertEqual(parsed["ID"], "example")
        self.assertEqual(parsed["PRETTY_NAME"], "Example Linux 42 (Stone)")

    def test_lscpu_parses_sockets_cores_threads_and_frequency(self):
        parsed = inspector._parse_lscpu(
            "CPU(s):                          16\n"
            "Socket(s):                       2\n"
            "Core(s) per socket:               4\n"
            "Thread(s) per core:                2\n"
            "CPU max MHz:                 4200.0000\n"
        )
        self.assertEqual(parsed["cpu(s)"], "16")
        self.assertEqual(parsed["socket(s)"], "2")
        self.assertEqual(parsed["core(s) per socket"], "4")
        self.assertEqual(parsed["cpu max mhz"], "4200.0000")

    def test_meminfo_uses_byte_units_and_available_memory(self):
        parsed = inspector._parse_meminfo(
            "MemTotal:       16384000 kB\n"
            "MemFree:         1024000 kB\n"
            "MemAvailable:    8192000 kB\n"
        )
        self.assertEqual(parsed["MemTotal"], 16384000 * 1024)
        self.assertEqual(parsed["MemAvailable"], 8192000 * 1024)

    def test_memory_device_parser_ignores_empty_slots(self):
        parsed = inspector._parse_memory_devices(
            "Memory Device\n\tSize: 16 GB\n\tType: DDR4\n\tSpeed: 3200 MT/s\n"
            "Memory Device\n\tSize: No Module Installed\n\tType: Unknown\n"
        )
        self.assertEqual(parsed["ram_type"], "DDR4")
        self.assertEqual(parsed["ram_speed"], "3200 MT/s")
        self.assertEqual(parsed["ram_slots"], "1 populated")
        self.assertEqual(int(parsed["ram_module_total_bytes"]), 16_000_000_000)

    def test_lsblk_preserves_each_physical_drive_and_detects_medium(self):
        parsed = inspector._parse_lsblk(json.dumps({
            "blockdevices": [
                {"name": "nvme0n1", "type": "disk", "size": 512_000_000_000,
                 "rota": False, "model": "Example NVMe", "tran": "nvme", "rm": False},
                {"name": "sda", "type": "disk", "size": 1_000_000_000_000,
                 "rota": "1", "model": "Archive Drive", "tran": "sata", "rm": "0"},
                {"name": "sda1", "type": "part", "size": 100_000_000_000,
                 "rota": "1", "model": "Archive Drive", "tran": "sata", "rm": "0"},
                {"name": "loop0", "type": "loop", "size": 1_000_000, "rota": 0},
            ]
        }))
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["kind"], "NVMe")
        self.assertEqual(parsed[0]["capacity"], "512 GB")
        self.assertEqual(parsed[1]["kind"], "HDD")
        self.assertEqual(parsed[1]["capacity"], "1 TB")

    def test_network_parser_excludes_loopback_and_macos_colon_suffixes(self):
        parsed = inspector._parse_network_interfaces(
            "2: enp1s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP mode DEFAULT\n"
            "3: wlp2s0: <BROADCAST,MULTICAST> mtu 1500 state DOWN mode DORMANT\n"
            "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 state UNKNOWN mode DEFAULT\n"
        )
        self.assertEqual(parsed, ["enp1s0 (up)", "wlp2s0 (down)"])

    def test_gpu_parser_recognizes_vga_and_3d_adapters(self):
        parsed = inspector._parse_gpus(
            "00:02.0 VGA compatible controller: Example Graphics Inc. Integrated GPU (rev 01)\n"
            "03:00.0 3D controller: Example Compute Ltd. Accelerator\n"
            "05:00.0 Ethernet controller: Example Network Inc. NIC\n"
        )
        self.assertEqual(len(parsed), 2)
        self.assertIn("Integrated GPU", parsed[0])
        self.assertIn("Accelerator", parsed[1])

    def test_cpu_list_counts_single_cpus_as_one(self):
        self.assertEqual(inspector._count_cpu_list("0-3,8,10-11"), 7)
        self.assertEqual(inspector._count_cpu_list("0-3,x"), 0)

    def test_tofu_keys_from_parallel_workers_are_all_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            known_hosts = Path(tmp) / "known_hosts"
            first, second = inspector.paramiko.ECDSAKey.generate(), inspector.paramiko.ECDSAKey.generate()
            inspector._remember_host_key(known_hosts, "10.0.0.1", first)
            inspector._remember_host_key(known_hosts, "10.0.0.2", second)
            stored = inspector.paramiko.HostKeys(str(known_hosts))
            self.assertTrue(stored.check("10.0.0.1", first))
            self.assertTrue(stored.check("10.0.0.2", second))

    def test_connection_failures_name_the_network_cause(self):
        import errno
        import socket

        def wrapped(code):
            return inspector.paramiko.ssh_exception.NoValidConnectionsError(
                {("10.0.0.9", 22): OSError(code, "synthetic")}
            )

        previous = get_language()
        set_language("pt-br")
        self.addCleanup(set_language, previous)
        self.assertIn("desligada", inspector._connection_failure(wrapped(errno.EHOSTUNREACH), "10.0.0.9", 15))
        self.assertIn("recusada", inspector._connection_failure(wrapped(errno.ECONNREFUSED), "10.0.0.9", 15))
        self.assertIn("15 s", inspector._connection_failure(socket.timeout(), "10.0.0.9", 15))
        self.assertIsNone(inspector._connection_failure(PermissionError(13, "denied"), "10.0.0.9", 15))

    def test_uptime_format_and_unknown_value(self):
        self.assertEqual(inspector._format_uptime("90061.32 123.00"), "1d 1h 1m")
        self.assertEqual(inspector._format_uptime("not-a-number"), "N/A")

    def test_collector_returns_multi_device_hardware_and_serial_is_opt_in(self):
        section_data = {
            "os_release": 'PRETTY_NAME="Example Linux 42"\nNAME="Example Linux"\n',
            "hostname": "example-host",
            "kernel": "6.8.0-example",
            "architecture": "x86_64",
            "lscpu": (
                "Model name: Example Processor\nCPU(s): 8\nSocket(s): 1\n"
                "Core(s) per socket: 4\nThread(s) per core: 2\nCPU max MHz: 3600.0000\n"
                "Virtualization: VT-x\nVendor ID: GenuineExample\nCPU family: 6\n"
            ),
            "cpuinfo": "Model name: Example Processor\nCPU(s): 8\nVirtualization: VT-x\n",
            "meminfo": "MemTotal: 16384000 kB\nMemAvailable: 8192000 kB\nMemFree: 1000000 kB\n",
            "memory_devices": (
                "Memory Device\n\tSize: 16 GB\n\tType: DDR4\n\tSpeed: 3200 MT/s\n"
            ),
            "lsblk": json.dumps({"blockdevices": [
                {"name": "nvme0n1", "type": "disk", "size": 512_000_000_000, "rota": 0,
                 "model": "Example NVMe", "tran": "nvme", "rm": False, "fstype": None,
                 "mountpoints": [None], "children": [
                     {"name": "nvme0n1p1", "type": "part", "size": 511_000_000_000,
                      "fstype": "ext4", "mountpoints": ["/"]},
                 ]},
                {"name": "sda", "type": "disk", "size": 1_000_000_000_000, "rota": 1,
                 "model": "Example Archive", "tran": "sata", "rm": False, "fstype": None,
                 "mountpoints": [None]},
            ]}),
            "lspci": "00:02.0 VGA compatible controller [0300]: Example GPU [1234:5678]\n",
            "drm": "PCI_ID=1234:5678\n",
            "netlink": "2: enp1s0: <BROADCAST,MULTICAST,UP> mtu 1500 state UP mode DEFAULT\n",
            "netdetails": "enp1s0|up|1000|e1000e\n",
            "uptime": "90061.32 123.00",
            "virtualization": "kvm",
            "dmi": "",
        }
        dmi_lines = (
            "__DMI__sys_vendor=Example Systems\n"
            "__DMI__product_name=Model A\n"
            "__DMI__product_version=Rev 2\n"
            "__DMI__board_vendor=Example Systems\n"
            "__DMI__board_name=Board A\n"
            "__DMI__bios_vendor=Example Firmware\n"
            "__DMI__bios_version=1.2.3\n"
            "__DMI__bios_date=2026-02-01\n"
        )
        dmi_with_serial = dmi_lines + "__DMI__product_serial=SECRET-SERIAL-123\n"

        def make_probe(include_serial: bool) -> str:
            output = []
            for name, value in section_data.items():
                if name == "dmi":
                    value = dmi_with_serial if include_serial else dmi_lines
                output.append(
                    f"__INVENT_SSH_BEGIN_{name}__\n{value.strip()}\n"
                    f"__INVENT_SSH_END_{name}__"
                )
            return "\n".join(output)

        def fake_command(_client, command, tolerant=False, timeout=12):
            return make_probe("product_serial" in command)

        with patch.object(inspector, "_run_command", side_effect=fake_command) as mocked:
            details = inspector._collect_linux_hardware(Mock(), include_sensitive_identifiers=False)
            details_with_serial = inspector._collect_linux_hardware(Mock(), include_sensitive_identifiers=True)

        self.assertEqual(mocked.call_count, 2)  # One probe / SSH round trip per target.
        self.assertEqual(details["status"], "SUCESSO")
        self.assertEqual(details["distro"], "Example Linux 42")
        self.assertEqual(details["processador"], "Example Processor")
        self.assertEqual(details["cores_threads"], "4/8")
        self.assertEqual(details["disk_type"], "NVMe + HDD")
        self.assertIn("2 physical block devices", details["disk_size"])
        self.assertEqual(details["hardware_details"]["manufacturer"], "Example Systems")
        self.assertEqual(details["hardware_details"]["model"], "Model A")
        self.assertIn("nvme0n1", details["hardware_details"]["storage_devices"])
        self.assertIn("nvme0n1p1", details["hardware_details"]["storage_devices"])
        self.assertIn("ext4 · /", details["hardware_details"]["storage_devices"])
        self.assertIn("sda", details["hardware_details"]["storage_devices"])
        self.assertIn("Example GPU", details["hardware_details"]["gpu"])
        self.assertIn("enp1s0", details["hardware_details"]["network_adapters"])
        self.assertIn("1000 Mbps", details["hardware_details"]["network_adapters"])
        self.assertEqual(details["hardware_details"]["uptime"], "1d 1h 1m")
        self.assertEqual(details["hardware_details"]["virtualization"], "kvm")
        self.assertEqual(details["hardware_details"]["system_serial"], "Not collected (opt-in)")
        self.assertEqual(details_with_serial["hardware_details"]["system_serial"], "SECRET-SERIAL-123")
        self.assertEqual(details["hardware_details"]["coverage_percent"], "100%")


if __name__ == "__main__":
    unittest.main()
