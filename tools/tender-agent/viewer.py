#!/usr/bin/env python3
"""Viewer somente-leitura do navegador do agente.

Recebe tickets curtos assinados pelo SIVS e serve apenas a ultima captura PNG.
Nao possui rota de VNC, WebDriver, teclado, mouse ou execucao de comandos.
Um proxy HTTPS externo deve encaminhar somente para esta porta interna.
"""
import base64
import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SECRET = os.environ.get("SIVS_TENDER_AGENT_VIEWER_SECRET", "").encode("utf-8")
SNAPSHOT_DIR = Path(os.environ.get("SIVS_TENDER_AGENT_SNAPSHOT_DIR", "/viewer-snapshots"))


def valid_ticket(value):
    try:
        version, payload64, signature64 = value.split(".")
        if version != "v1": return False
        signed = f"v1.{payload64}".encode("ascii")
        padding = "=" * (-len(signature64) % 4)
        signature = base64.urlsafe_b64decode(signature64 + padding)
        expected = hmac.new(SECRET, signed, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected): return False
        padding = "=" * (-len(payload64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload64 + padding))
        return payload.get("v") == 1 and int(payload.get("e", 0)) >= int(time.time())
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


class ViewerHandler(BaseHTTPRequestHandler):
    server_version = "SIVSReadOnlyViewer/1.0"
    def log_message(self, *_args): pass
    def authorized(self):
        ticket = (parse_qs(urlparse(self.path).query).get("ticket") or [""])[0]
        return len(SECRET) >= 32 and valid_ticket(ticket)
    def reply(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors https:")
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if not self.authorized(): return self.reply(403, "text/plain; charset=utf-8", b"Acesso negado")
        path = urlparse(self.path).path
        if path == "/frame.png":
            image = SNAPSHOT_DIR / "latest.png"
            if not image.is_file(): return self.reply(404, "text/plain; charset=utf-8", b"Aguardando primeira captura")
            return self.reply(200, "image/png", image.read_bytes())
        if path not in {"/", "/index.html"}: return self.reply(404, "text/plain; charset=utf-8", b"Nao encontrado")
        ticket = (parse_qs(urlparse(self.path).query).get("ticket") or [""])[0]
        html = f'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sessão ao vivo</title><style>body{{margin:0;background:#111;color:#eee;font:14px system-ui}}header{{padding:10px 14px}}img{{display:block;width:100%;min-height:260px;object-fit:contain;background:#000}}</style><header>Visualização somente leitura · atualização automática</header><img id="frame" alt="Última imagem do navegador do agente"><script>const i=document.querySelector('#frame'),u='/frame.png?ticket={ticket}';function r(){{i.src=u+'&_='+Date.now()}}r();setInterval(r,2000)</script>'''.encode("utf-8")
        return self.reply(200, "text/html; charset=utf-8", html)


if __name__ == "__main__":
    if len(SECRET) < 32: raise SystemExit("SIVS_TENDER_AGENT_VIEWER_SECRET deve possuir 32+ caracteres")
    ThreadingHTTPServer(("0.0.0.0", 7800), ViewerHandler).serve_forever()
