#!/usr/bin/env python3
"""Inicializador amigável do SIVS: valida a porta, inicia e abre o navegador."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8844"


def status():
    try:
        with urllib.request.urlopen(f"{URL}/api/status", timeout=0.5) as response:
            return json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return None


def main():
    current = status()
    if current and current.get("ok"):
        print("O SIVS já está em execução. Abrindo o navegador...")
        webbrowser.open(URL)
        return 0
    process = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "server.py"), "--host", "127.0.0.1", "--port", "8844"],
        cwd=BASE_DIR,
    )
    for _ in range(30):
        time.sleep(0.2)
        current = status()
        if current and current.get("ok"):
            print("SIVS iniciado com sucesso. Abrindo o navegador...")
            webbrowser.open(URL)
            try:
                return process.wait()
            except KeyboardInterrupt:
                process.terminate()
                return 0
        if process.poll() is not None:
            print("O servidor foi encerrado antes de iniciar. Verifique as mensagens acima.")
            return process.returncode or 1
    process.terminate()
    print("Não foi possível iniciar o SIVS na porta 8844. Verifique se outro programa está usando essa porta.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
