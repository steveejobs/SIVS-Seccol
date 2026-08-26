#!/usr/bin/env python3
"""Worker assinado do agente de portal do SIVS.

Seguro por padrao: sem ``--execute`` apenas valida a configuracao local. O worker
nao conhece custos nem decide valores; ele recebe comandos previamente autorizados
pelo servidor. Acoes de envio/lance exigem tambem ``--allow-external-effects`` e um
adaptador homologado do portal.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
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
    except urllib.error.URLError as exc:
        return 0, {"message": f"Servidor indisponivel: {str(exc.reason)[:300]}"}


def evidence_hash(driver, snapshot_dir=None):
    screenshot = driver.get_screenshot_as_png()
    if snapshot_dir:
        target = Path(snapshot_dir).expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        temporary = target / ".latest.png.tmp"
        temporary.write_bytes(screenshot)
        os.replace(temporary, target / "latest.png")
    return hashlib.sha256(screenshot).hexdigest()


def execute_browser_command(command, profile_dir, allow_external_effects,
                            remote_webdriver_url=None, headless=False, snapshot_dir=None):
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
    options.add_argument("--window-size=1440,1000")
    if headless:
        options.add_argument("--headless=new")
    driver = None
    try:
        driver = (
            webdriver.Remote(command_executor=remote_webdriver_url, options=options)
            if remote_webdriver_url else webdriver.Chrome(options=options)
        )
        driver.set_page_load_timeout(45)
        if action == "NAVIGATE":
            driver.get(command["portalUrl"])
        elif action == "VERIFY_CONTEXT":
            driver.get(command["portalUrl"])
            expected = command.get("externalTenderId") or ""
            if expected and expected not in driver.page_source:
                return "MANUAL_REQUIRED", False, evidence_hash(driver, snapshot_dir), {
                    "message": "Identificador do certame nao foi localizado na pagina atual.",
                    "url": driver.current_url,
                }
        elif action in {"PREPARE_PROPOSAL", "MONITOR_SESSION", "CAPTURE_RECEIPT"}:
            if not driver.current_url.startswith("https://"):
                driver.get(command["portalUrl"])
        else:
            return "MANUAL_REQUIRED", False, evidence_hash(driver, snapshot_dir), {
                "message": f"Acao {action} requer adaptador especifico do portal.",
            }
        return "COMPLETED", False, evidence_hash(driver, snapshot_dir), {
            "message": f"Etapa {action} verificada pelo navegador sem efeito externo.",
            "url": driver.current_url,
            "title": driver.title[:240],
        }
    except Exception as exc:  # o recibo precisa capturar falhas do driver/portal
        return "FAILED", False, None, {"message": str(exc)[:1000]}
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


@contextlib.contextmanager
def exclusive_profile(profile):
    """Impede dois workers de reutilizarem a mesma sessao autenticada."""
    lock_path = profile / ".sivs-worker.lock"
    lock = lock_path.open("a+b")
    lock.seek(0)
    if lock.tell() == 0:
        lock.write(b"0")
        lock.flush()
    try:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        lock.close()
        raise RuntimeError("O perfil ja esta em uso por outro worker") from None
    try:
        yield
    finally:
        try:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        finally:
            lock.close()


def process_one(args, secret, profile):
    status, leased = signed_request(args.base_url, "/api/integrations/tender-agent/lease", {
        "version": "1.0", "workerId": args.worker_id,
    }, secret)
    if status != 200:
        print(leased.get("message", leased), file=sys.stderr, flush=True)
        return False, False
    command = leased.get("command")
    if not command:
        return False, True
    outcome, external_effect, evidence, detail = execute_browser_command(
        command, profile, args.allow_external_effects,
        remote_webdriver_url=args.remote_webdriver_url or None,
        headless=args.headless,
        snapshot_dir=args.snapshot_dir or None,
    )
    result_status, result = signed_request(args.base_url, "/api/integrations/tender-agent/result", {
        "version": "1.0", "workerId": args.worker_id, "commandId": command["id"],
        "outcome": outcome, "externalEffect": external_effect,
        "evidenceSha256": evidence, "detail": detail,
    }, secret)
    print(json.dumps({"command": command["id"], "outcome": outcome,
                      "receiptAccepted": result_status == 200}, ensure_ascii=False), flush=True)
    if result_status != 200:
        print(result.get("message", result), file=sys.stderr, flush=True)
    return True, result_status == 200


def main():
    parser = argparse.ArgumentParser(description="Worker governado do agente de portal SIVS")
    parser.add_argument("--base-url", default=os.environ.get("SIVS_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--worker-id", default=f"sivs-worker-{socket.gethostname()}")
    parser.add_argument("--execute", action="store_true", help="Consulta e processa um comando")
    parser.add_argument("--loop", action="store_true",
                        help="Mantem o worker consultando a fila; exige --execute")
    parser.add_argument("--poll-seconds", type=float, default=float(
        os.environ.get("SIVS_TENDER_AGENT_POLL_SECONDS", "5")
    ), help="Intervalo da fila vazia no modo --loop (2 a 300 segundos)")
    parser.add_argument("--allow-external-effects", action="store_true",
                        help="Libera acoes externas somente quando servidor e politica autorizarem")
    parser.add_argument("--profile-dir", default=os.environ.get("SIVS_TENDER_AGENT_PROFILE_DIR", ""))
    parser.add_argument("--remote-webdriver-url", default=os.environ.get(
        "SIVS_TENDER_AGENT_WEBDRIVER_URL", "",
    ), help="Selenium remoto privado, por exemplo http://browser:4444")
    parser.add_argument("--headless", action="store_true",
                        help="Executa sem tela; nao recomendado durante login/MFA ou homologacao")
    parser.add_argument("--snapshot-dir", default=os.environ.get("SIVS_TENDER_AGENT_SNAPSHOT_DIR", ""),
                        help="Diretorio privado de imagem para o viewer somente-leitura")
    args = parser.parse_args()
    secret = os.environ.get("SIVS_TENDER_AGENT_SECRET", "").strip()
    problems = []
    if len(secret) < 32:
        problems.append("SIVS_TENDER_AGENT_SECRET deve possuir ao menos 32 caracteres")
    if args.execute and not args.profile_dir:
        problems.append("SIVS_TENDER_AGENT_PROFILE_DIR deve apontar para um perfil dedicado")
    if args.loop and not args.execute:
        problems.append("--loop exige --execute")
    if not 2 <= args.poll_seconds <= 300:
        problems.append("--poll-seconds deve estar entre 2 e 300")
    if args.remote_webdriver_url and not args.remote_webdriver_url.startswith(("http://", "https://")):
        problems.append("SIVS_TENDER_AGENT_WEBDRIVER_URL deve usar http:// ou https://")
    server_url = urllib.parse.urlparse(args.base_url)
    if server_url.hostname not in {"127.0.0.1", "localhost", "::1"} and server_url.scheme != "https":
        problems.append("SIVS_URL deve usar HTTPS fora do ambiente local")
    if not args.execute:
        print("DRY-RUN: nenhum endpoint foi chamado e nenhum navegador foi aberto.")
        print(f"Servidor: {args.base_url}")
        print(f"Worker: {args.worker_id}")
        print(f"WebDriver: {args.remote_webdriver_url or 'Chrome local'}")
        print("Efeitos externos: " + ("solicitados" if args.allow_external_effects else "bloqueados"))
        print("Configuracao: " + ("pronta" if not problems else "; ".join(problems)))
        return 0 if not problems else 2
    if problems:
        print("Configuracao invalida: " + "; ".join(problems), file=sys.stderr)
        return 2
    profile = Path(args.profile_dir).expanduser().resolve()
    profile.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_profile(profile):
            if not args.loop:
                processed, healthy = process_one(args, secret, profile)
                if not processed and healthy:
                    print("Fila vazia.")
                return 0 if healthy else 1
            print("Worker continuo iniciado; efeitos externos " + (
                "solicitados (ainda sujeitos aos guardrails do servidor e ao adaptador)"
                if args.allow_external_effects else "bloqueados"
            ), flush=True)
            while True:
                processed, healthy = process_one(args, secret, profile)
                if not healthy:
                    time.sleep(args.poll_seconds)
                    continue
                if not processed:
                    time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("Worker encerrado pelo operador.")
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
