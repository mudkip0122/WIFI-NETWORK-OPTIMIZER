"""Windows IPv4 configuration and language-independent PowerShell JSON bridge."""
import json
import os
import subprocess


def powershell_json(script: str, settings: dict, timeout: float = 15):
    env = os.environ.copy()
    env["WIFI_MEASURE_ARGS"] = json.dumps(settings, ensure_ascii=True)
    prefix = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$p = $env:WIFI_MEASURE_ARGS | ConvertFrom-Json
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", prefix + script],
        capture_output=True, timeout=timeout, env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise OSError("Windows network query failed: " +
                      result.stderr.decode("utf-8", errors="replace").strip()[:500])
    return json.loads(result.stdout.decode("utf-8-sig"))


def interface_network(interface: str) -> dict:
    return powershell_json("""
$cfg = Get-NetIPConfiguration | Where-Object { $_.InterfaceAlias -eq $p.interface }
if (@($cfg).Count -ne 1) { throw 'Interface not found or ambiguous' }
$address = @($cfg.IPv4Address | Where-Object {
    $_.IPAddress -notlike '169.254.*'
} | Select-Object -ExpandProperty IPAddress)
if ($address.Count -ne 1) { throw 'One usable IPv4 address is required' }
$gateway = @($cfg.IPv4DefaultGateway | Select-Object -ExpandProperty NextHop)
[pscustomobject]@{
    interface = $cfg.InterfaceAlias
    index = $cfg.InterfaceIndex
    source_ip = $address[0]
    gateway = if ($gateway.Count) { $gateway[0] } else { $null }
} | ConvertTo-Json -Compress
""", {"interface": interface})
