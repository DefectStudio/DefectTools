import subprocess
import unittest
from unittest.mock import patch

from portable_pipe_tools.render_farm import gpu_inventory


class GpuInventoryTests(unittest.TestCase):
    def test_nvidia_smi_parses_multiple_adapters_and_skips_bad_rows(self):
        output = (
            "NVIDIA GeForce RTX 5090, 32607\n"
            '"unclosed name, 12288\n'
            '"GeForce RTX 4080 Laptop GPU", 12282\n'
            "NVIDIA GeForce RTX 3090, [N/A]\n"
            "NVIDIA GeForce RTX 5080, 0\n"
            "NVIDIA GeForce RTX 4090, 9999999\n"
            ", 12288\n"
        )
        with patch.object(gpu_inventory, "_nvidia_smi_path", return_value="nvidia-smi.exe"), patch.object(
            gpu_inventory.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output)
        ) as run:
            self.assertEqual([
                {"model": "RTX 5090", "vram_mib": 32607},
                {"model": "RTX 4080 Laptop GPU", "vram_mib": 12282},
            ], gpu_inventory._nvidia_adapters())
        self.assertEqual(5, run.call_args.kwargs["timeout"])
        self.assertTrue(run.call_args.kwargs["check"])
        self.assertEqual(getattr(subprocess, "CREATE_NO_WINDOW", 0), run.call_args.kwargs["creationflags"])

    def test_nvidia_smi_missing_or_failing_yields_empty_inventory(self):
        with patch.object(gpu_inventory, "_nvidia_smi_path", return_value=None):
            self.assertEqual([], gpu_inventory._nvidia_adapters())
        for error in (OSError(), subprocess.TimeoutExpired("nvidia-smi.exe", 5), subprocess.CalledProcessError(1, [])):
            with self.subTest(error=type(error).__name__), patch.object(
                gpu_inventory, "_nvidia_smi_path", return_value="nvidia-smi.exe"
            ), patch.object(gpu_inventory.subprocess, "run", side_effect=error):
                self.assertEqual([], gpu_inventory._nvidia_adapters())

    def test_reports_non_nvidia_dxgi_adapters_and_prefers_nvidia_smi(self):
        nvidia = [{"model": "RTX 5090", "vram_mib": 32607}]
        amd = {"model": "AMD Radeon(TM) Graphics", "vram_mib": 2021}
        dxgi = [
            (0x10DE, "NVIDIA GeForce RTX 5090", 32187),
            (0x1002, "AMD Radeon(TM) Graphics", 2021),
            (0x10DE, "NVIDIA GeForce RTX 5090", 32187),
            (0x8086, "Intel Integrated Graphics", 0),
        ]
        with patch.object(gpu_inventory.sys, "platform", "win32"), patch.object(
            gpu_inventory, "_dxgi_adapters", return_value=dxgi
        ), patch.object(gpu_inventory, "_nvidia_adapters", return_value=nvidia) as smi:
            self.assertEqual([*nvidia, amd], gpu_inventory.detect_gpus())
            smi.return_value = []
            fallback = {"model": "RTX 5090", "vram_mib": 32187}
            self.assertEqual([fallback, amd, fallback], gpu_inventory.detect_gpus())

    def test_native_dxgi_failure_keeps_nvidia_telemetry(self):
        nvidia = [{"model": "RTX 5090", "vram_mib": 32607}]
        for error in (OSError(), ValueError()):
            with self.subTest(error=type(error).__name__), patch.object(
                gpu_inventory.sys, "platform", "win32"
            ), patch.object(gpu_inventory, "_dxgi_adapters", side_effect=error), patch.object(
                gpu_inventory, "_nvidia_adapters", return_value=nvidia
            ):
                self.assertEqual(nvidia, gpu_inventory.detect_gpus())
