#!/usr/bin/env python3
"""Worker assinado do agente de portal do SIVS.

Seguro por padrao: sem ``--execute`` apenas valida a configuracao local. O worker
nao conhece custos nem decide valores; ele recebe comandos previamente autorizados
pelo servidor. Acoes de envio/lance exigem tambem ``--allow-external-effects`` e um
adaptador homologado do portal.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def signed_request(base_url, endpoint, payload, secret):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = "sha256=" + hmac.new(
        secret.encode("utf-8"), timestamp.encode("ascii") + b"." + raw, hashlib.sha256,
    ).hexdigest()
    request = urllib.request.Request(
        base_url.rstrip("/") + endpoint, data=raw, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-SIVS-Agent-Timestamp": timestamp,
            "X-SIVS-Agent-Signature": signature,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = {"message": body[:500]}
        return exc.code, detail


def evidence_hash(driver):
    return hashlib.sha256(driver.get_screenshot_as_png()).hexdigest()


def execute_browser_command(command, profile_dir, allow_external_effects):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError as exc:
        return "MANUAL_REQUIRED", False, None, {
            "message": "Selenium ausente. Instale tools/requirements.txt no ambiente do worker.",
            "error": str(exc),
        }

    action = command["action"]
    if action in {"PLACE_BID", "SUBMIT_PROPOSAL"}:
        if not allow_external_effects:
            return "MANUAL_REQUIRED", False, None, {
                "message": "Efeito externo bloqueado: inicie com --allow-external-effects apos homologacao.",
            }
        return "MANUAL_REQUIRED", False, None, {
            "message": (
                f"O portal {command['portalKey']} ainda nao possui adaptador de seletores "
                "homologado neste worker. Nenhum clique foi executado."
            ),
        }

    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--disable-background-networking")
    options.add_argument("--no-default-browser-check")
    driver = webdriver.Chrome(options=options)
    try:
        if action == "NAVIGATE":
            driver.get(command["portalUrl"])
        elif action == "VERIFY_CONTEXT":
            expected = command.get("externalTenderId") or ""
            if expected and expected not in driver.page_source:
                return "MANUAL_REQUIRED", False, evidence_hash(driver), {
                    "message": "Identificador do certame nao foi localizado na pagina atual.",
                    "url": driver.current_url,
                }
        elif action in {"PREPARE_PROPOSAL", "MONITOR_SESSION", "CAPTURE_RECEIPT"}:
            if not driver.current_url.startswith("https://"):
                driver.get(command["portalUrl"])
        else:
            return "MANUAL_REQUIRED", False, evidence_hash(driver), {
                "message": f"Acao {action} requer adaptador especifico do portal.",
            }
        return "COMPLETED", False, evidence_hash(driver), {
            "message": f"Etapa {action} verificada pelo navegador sem efeito externo.",
            "url": driver.current_url,
            "title": driver.title[:240],
        }
    except Exception as exc:  # o recibo precisa capturar falhas do driver/portal
        return "FAILED", False, None, {"message": str(exc)[:1000]}
    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Worker governado do agente de portal SIVS")
    parser.add_argument("--base-url", default=os.environ.get("SIVS_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--worker-id", default=f"sivs-worker-{socket.gethostname()}")
    parser.add_argument("--execute", action="store_true", help="Consulta e processa um comando")
    parser.add_argument("--allow-external-effects", action="store_true",
                        help="Libera acoes externas somente quando servidor e politica autorizarem")
    parser.add_argument("--profile-dir", default=os.environ.get("SIVS_TENDER_AGENT_PROFILE_DIR", ""))
    args = parser.parse_args()
    secret = os.environ.get("SIVS_TENDER_AGENT_SECRET", "").strip()
    problems = []
    if len(secret) < 32:
        problems.append("SIVS_TENDER_AGENT_SECRET deve possuir ao menos 32 caracteres")
    if args.execute and not args.profile_dir:
        problems.append("SIVS_TENDER_AGENT_PROFILE_DIR deve apontar para um perfil dedicado")
    if not args.execute:
        print("DRY-RUN: nenhum endpoint foi chamado e nenhum navegador foi aberto.")
        print(f"Servidor: {args.base_url}")
        print(f"Worker: {args.worker_id}")
        print("Configuracao: " + ("pronta" if not problems else "; ".join(problems)))
        return 0 if not problems else 2
    if problems:
        print("Configuracao invalida: " + "; ".join(problems), file=sys.stderr)
        return 2
    profile = Path(args.profile_dir).expanduser().resolve()
    profile.mkdir(parents=True, exist_ok=True)
    status, leased = signed_request(args.base_url, "/api/integrations/tender-agent/lease", {
        "version": "1.0", "workerId": args.worker_id,
    }, secret)
    if status != 200:
        print(leased.get("message", leased), file=sys.stderr)
        return 1
    command = leased.get("command")
    if not command:
        print("Fila vazia.")
        return 0
    outcome, external_effect, evidence, detail = execute_browser_command(
        command, profile, args.allow_external_effects,
    )
    result_status, result = signed_request(args.base_url, "/api/integrations/tender-agent/result", {
        "version": "1.0", "workerId": args.worker_id, "commandId": command["id"],
        "outcome": outcome, "externalEffect": external_effect,
        "evidenceSha256": evidence, "detail": detail,
    }, secret)
    print(json.dumps({"command": command["id"], "outcome": outcome,
                      "receiptAccepted": result_status == 200}, ensure_ascii=False))
    return 0 if result_status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
