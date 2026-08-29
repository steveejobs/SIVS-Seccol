#!/usr/bin/env python3
"""Audita navegação e ações principais do SIVS em banco e navegador descartáveis.

O script nunca aponta para o banco real. Ele inicia um servidor em porta livre,
usa um SQLite temporário, percorre o menu com Chrome headless e grava apenas um
relatório JSON em .artifacts/interaction-audit.json.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "sivs_2_2" / "server.py"
REPORT = ROOT / ".artifacts" / "interaction-audit.json"
FORM_CAPTURES = {"clientes_fornecedores", "propostas", "ordens_servico", "contas_pagar"}
MOBILE_CAPTURES = {
    "dashboard", "clientes_fornecedores", "propostas", "editais",
    "concorrentes", "ordens_servico", "estoque", "financeiro", "control_center", "settings",
}


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def base_python() -> str:
    """Interpretador fora do venv de ferramentas, onde as dependências do servidor estão instaladas."""
    override = os.environ.get("SIVS_SERVER_PYTHON", "").strip()
    if override:
        return override
    if sys.prefix == sys.base_prefix:
        return sys.executable
    candidate = Path(sys.base_prefix, "python.exe") if os.name == "nt" else Path(sys.base_prefix, "bin", "python3")
    return str(candidate) if candidate.exists() else sys.executable


def wait_server(url: str) -> None:
    for _ in range(80):
        try:
            with urllib.request.urlopen(f"{url}/api/status", timeout=0.25) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Servidor temporário não iniciou")


def visible_text(driver, selector: str) -> str:
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        return " | ".join(element.text.strip() for element in elements if element.is_displayed())
    except StaleElementReferenceException:
        return ""


def actionable_browser_errors(driver) -> list[dict[str, object]]:
    return [
        entry for entry in driver.get_log("browser")
        if entry.get("level") == "SEVERE"
        and not (entry.get("source") == "network" and (
            "/api/me" in str(entry.get("message")) or "/favicon.ico" in str(entry.get("message"))
        ))
    ]


def run() -> int:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {"baseUrl": base_url, "screens": [], "errors": []}
    server = None
    driver = None
    # No Windows, o SQLite pode permanecer bloqueado por alguns milissegundos
    # depois do encerramento do processo filho; isso não deve transformar uma
    # auditoria aprovada em falha apenas durante a limpeza do diretório temporário.
    with tempfile.TemporaryDirectory(
        prefix="sivs-interaction-audit-", ignore_cleanup_errors=True,
    ) as temporary:
        database = Path(temporary) / "audit.db"
        server = subprocess.Popen(
            [base_python(), str(SERVER), "--host", "127.0.0.1", "--port", str(port), "--db", str(database)],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_server(base_url)
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--window-size=390,844" if "--mobile" in sys.argv else "--window-size=1440,1000")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
            driver = webdriver.Chrome(options=options)
            if "--mobile" in sys.argv:
                driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": 390, "height": 844, "deviceScaleFactor": 1,
                    "mobile": True,
                })
                driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {
                    "enabled": True, "maxTouchPoints": 5,
                })
            wait = WebDriverWait(driver, 10)
            driver.get(f"{base_url}/?audit=interactions")
            wait.until(lambda current: current.find_element(By.ID, "authForm").is_displayed())
            if "--mobile" in sys.argv:
                install_button = driver.find_element(By.CSS_SELECTOR, "#authForm [data-install-app]")
                wait.until(lambda current: install_button.is_displayed())
                driver.execute_script("arguments[0].click()", install_button)
                wait.until(lambda current: current.find_element(By.ID, "installDialog").get_attribute("open") is not None)
                results["installExperience"] = {
                    "button": install_button.text,
                    "title": driver.find_element(By.ID, "installDialogTitle").text,
                    "steps": driver.find_element(By.ID, "installSteps").text,
                }
                if "--capture-mobile" in sys.argv:
                    capture = REPORT.parent / "mobile-install.png"
                    driver.save_screenshot(str(capture))
                    results["installExperience"]["screenshot"] = str(capture.relative_to(ROOT))
                close_install = driver.find_element(By.CSS_SELECTOR, "#installDialog [data-close]")
                driver.execute_script("arguments[0].click()", close_install)
                wait.until(lambda current: current.find_element(By.ID, "installDialog").get_attribute("open") is None)
            form = driver.find_element(By.ID, "authForm")
            form.find_element(By.NAME, "company").send_keys("Empresa de Auditoria")
            form.find_element(By.NAME, "name").send_keys("Administrador Auditor")
            form.find_element(By.NAME, "email").send_keys("admin.audit@example.test")
            form.find_element(By.NAME, "password").send_keys("Senha-Auditoria-123")
            form.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
            wait.until(lambda current: "is-authenticated" in current.find_element(By.TAG_NAME, "body").get_attribute("class"))

            if "--assistant-copilot" in sys.argv:
                results["current"] = {"screen": "assistant", "phase": "seed-context"}
                assistant_record = driver.execute_async_script("""
                    const done = arguments[0];
                    fetch('/api/records', {
                      method: 'POST',
                      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.SIVSState.csrf},
                      body: JSON.stringify({
                        module: 'clientes_fornecedores', title: 'Cliente do assistente', status: 'Ativo',
                        payload: {assunto: 'Cliente do assistente', tipo_cadastro: 'C',
                          documento: '11144477735', tipo_pessoa: 'Pessoa física',
                          razao_social: 'Cliente do assistente'}
                      })
                    }).then(async response => {
                      const data = await response.json();
                      done(response.ok ? {id: data.item.id} : {error: data.message});
                    }).catch(error => done({error: error.message}));
                """)
                if assistant_record.get("error"):
                    raise AssertionError(assistant_record["error"])
                rail = driver.find_element(By.ID, "assistantRailButton")
                wait.until(lambda current: rail.is_displayed() and rail.is_enabled())
                results["current"] = {"screen": "assistant", "phase": "open-panel"}
                driver.execute_script("arguments[0].click()", rail)
                wait.until(lambda current: "open" in current.find_element(
                    By.ID, "assistantPanel"
                ).get_attribute("class").split())
                assistant_input = driver.find_element(By.ID, "assistantInput")
                wait.until(lambda current: current.execute_script("""
                    const input = document.getElementById('assistantInput');
                    return input && !input.disabled && input.getClientRects().length > 0 &&
                      !document.getElementById('assistantPanel').inert;
                """))
                results["current"] = {"screen": "assistant", "phase": "ask"}
                assistant_result = driver.execute_async_script("""
                    const done = arguments[0];
                    window.askAssistant('Mostre clientes Cliente do assistente');
                    const deadline = Date.now() + 10000;
                    const poll = () => {
                      const message = document.querySelector('#assistantMessages .assistant-message.assistant');
                      const source = document.querySelector('#assistantMessages button.assistant-source');
                      if (message && source) {
                        const panel = document.getElementById('assistantPanel');
                        const rail = document.getElementById('assistantRailButton');
                        const rect = panel.getBoundingClientRect();
                        done({
                          railText: rail.innerText,
                          panelRole: panel.getAttribute('role'),
                          panelModal: panel.getAttribute('aria-modal'),
                          panelWidth: Math.round(rect.width),
                          viewportWidth: window.innerWidth,
                          context: document.getElementById('assistantContextLabel').innerText,
                          mode: document.getElementById('assistantModeBadge').textContent.trim(),
                          answer: message.innerText || '', source: source.innerText || '',
                          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1
                        });
                        return;
                      }
                      if (Date.now() > deadline) { done({error: 'timeout-assistant-answer'}); return; }
                      setTimeout(poll, 100);
                    };
                    poll();
                """)
                if assistant_result.get("error"):
                    raise AssertionError(assistant_result["error"])
                if assistant_result["horizontalOverflow"]:
                    raise AssertionError("Assistente causou overflow horizontal")
                if assistant_result["panelRole"] != "dialog" or assistant_result["panelModal"] != "true":
                    raise AssertionError(f"Contrato modal do assistente divergente: {assistant_result}")
                if "Cliente do assistente" not in assistant_result["answer"]:
                    raise AssertionError(f"Busca do assistente não encontrou o cadastro: {assistant_result}")
                if "Cliente do assistente" not in assistant_result["source"]:
                    raise AssertionError(f"Fonte do assistente incompleta: {assistant_result}")
                if "--capture-mobile" in sys.argv:
                    capture = REPORT.parent / "mobile-assistant.png"
                    driver.save_screenshot(str(capture))
                    assistant_result["screenshot"] = str(capture.relative_to(ROOT))
                driver.execute_script("document.querySelector('#assistantMessages button.assistant-source')?.click()")
                wait.until(lambda current: current.find_element(
                    By.CSS_SELECTOR, '#recordForm [name="id"]'
                ).get_attribute("value") == str(assistant_record["id"]))
                assistant_result["openedRecordId"] = driver.find_element(
                    By.CSS_SELECTOR, '#recordForm [name="id"]'
                ).get_attribute("value")
                driver.execute_script(
                    "arguments[0].click()",
                    driver.find_element(By.CSS_SELECTOR, "#recordDialog [data-close]"),
                )
                wait.until(lambda current: current.find_element(
                    By.ID, "recordDialog"
                ).get_attribute("open") is None)
                driver.execute_script("arguments[0].click()", rail)
                wait.until(lambda current: "open" in current.find_element(
                    By.ID, "assistantPanel"
                ).get_attribute("class").split())
                driver.find_element(By.ID, "assistantReset").click()
                if driver.find_elements(By.CSS_SELECTOR, "#assistantMessages .assistant-message"):
                    raise AssertionError("Nova conversa não limpou as mensagens anteriores")
                driver.execute_script("""
                    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
                """)
                wait.until(lambda current: "open" not in current.find_element(
                    By.ID, "assistantPanel"
                ).get_attribute("class").split())
                assistant_result["focusReturnedTo"] = driver.execute_script(
                    "return document.activeElement?.id || ''"
                )
                results["assistantCopilot"] = assistant_result

            shared_records = None
            if "--reference-sharing" in sys.argv:
                shared_records = driver.execute_async_script("""
                    const done = arguments[0];
                    const create = async (title, type, document, person) => {
                      const response = await fetch('/api/records', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.SIVSState.csrf},
                        body: JSON.stringify({module: 'clientes_fornecedores', title, status: 'Ativo', payload: {
                          assunto: title, tipo_cadastro: type, documento: document,
                          tipo_pessoa: person, razao_social: title, avaliacao: type === 'F' ? 'Pendente' : undefined
                        }})
                      });
                      const data = await response.json();
                      if (!response.ok) throw new Error(data.message || 'Falha ao criar parceiro de auditoria');
                      return data.item;
                    };
                    Promise.all([
                      create('Cliente compartilhado', 'C', '52998224725', 'Pessoa física'),
                      create('Fornecedor compartilhado', 'F', '04252011000110', 'Pessoa jurídica')
                    ]).then(([client, supplier]) => done({client, supplier})).catch(error => done({error: error.message}));
                """)
                if shared_records.get("error"):
                    raise AssertionError(shared_records["error"])
                results["sharedRecords"] = {
                    "clientId": shared_records["client"]["id"],
                    "supplierId": shared_records["supplier"]["id"],
                }

            navigation = driver.find_elements(By.CSS_SELECTOR, "[data-nav]")
            screen_keys = [] if "--auth-only" in sys.argv else [item.get_attribute("data-nav") for item in navigation]
            if "--capture-only" in sys.argv:
                screen_keys = [key for key in screen_keys if key in FORM_CAPTURES]
            if "--mobile-sample" in sys.argv:
                screen_keys = [key for key in screen_keys if key in MOBILE_CAPTURES]
            if "--reference-sharing" in sys.argv:
                screen_keys = [key for key in screen_keys if key in {"propostas", "ordens_servico", "contas_pagar"}]
            for key in screen_keys:
                results["current"] = {"screen": key, "phase": "navigate"}
                button = driver.find_element(By.CSS_SELECTOR, f'[data-nav="{key}"]')
                driver.execute_script("arguments[0].click()", button)
                wait.until(lambda current, expected=key: current.execute_script("return window.SIVSState.screen") == expected)
                wait.until(lambda current: (
                    visible_text(current, "#content") != ""
                    and not current.find_elements(By.CSS_SELECTOR, "#content .loading-state")
                ))
                screen = {
                    "key": key,
                    "title": driver.find_element(By.ID, "sectionTitle").text,
                    "primaryButtons": visible_text(driver, "#content button.primary"),
                    "dialogModule": None,
                }
                if key == "editais":
                    keyword_editor = driver.find_element(By.ID, "tenderKeywordEditor")
                    if "--capture-mobile" in sys.argv and "is-collapsed" in keyword_editor.get_attribute("class").split():
                        collapsed_capture = REPORT.parent / "mobile-editais-collapsed.png"
                        driver.save_screenshot(str(collapsed_capture))
                        screen["collapsedKeywordScreenshot"] = str(collapsed_capture.relative_to(ROOT))
                    if "is-collapsed" in keyword_editor.get_attribute("class").split():
                        driver.find_element(By.ID, "tenderKeywordToggle").click()
                        wait.until(lambda current: "is-collapsed" not in current.find_element(
                            By.ID, "tenderKeywordEditor"
                        ).get_attribute("class").split())
                    keyword_input = driver.find_element(By.ID, "tenderKeywordInput")
                    initial_chips = len(driver.find_elements(By.CSS_SELECTOR, "#tenderKeywordChips .keyword-chip"))
                    keyword_input.send_keys("ensaio fotométrico de auditoria", Keys.ENTER)
                    wait.until(lambda current: len(current.find_elements(
                        By.CSS_SELECTOR, "#tenderKeywordChips .keyword-chip"
                    )) == initial_chips + 1)
                    spreadsheet = Path(temporary) / "palavras-chave-auditoria.csv"
                    spreadsheet.write_text(
                        "palavra_chave;categoria;ativa\n"
                        "teste de integridade de auditoria;Ensaios;sim\n",
                        encoding="utf-8",
                    )
                    driver.find_element(By.ID, "tenderKeywordFile").send_keys(str(spreadsheet))
                    wait.until(lambda current: "importado" in current.find_element(
                        By.ID, "tenderKeywordReport"
                    ).text.lower())
                    screen["keywordEditor"] = {
                        "initial": initial_chips,
                        "afterEnterAndSpreadsheet": len(driver.find_elements(
                            By.CSS_SELECTOR, "#tenderKeywordChips .keyword-chip"
                        )),
                        "report": driver.find_element(By.ID, "tenderKeywordReport").text,
                    }
                if "--mobile" in sys.argv:
                    screen["mobileLayout"] = driver.execute_script("""
                        return {
                          viewport: window.innerWidth,
                          documentWidth: document.documentElement.scrollWidth,
                          contentWidth: document.getElementById('content')?.scrollWidth || 0,
                          horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1
                        };
                    """)
                    if screen["mobileLayout"]["horizontalOverflow"]:
                        raise AssertionError(f"{key}: a página excede a largura do viewport móvel")
                    if "--capture-mobile" in sys.argv and key in MOBILE_CAPTURES:
                        time.sleep(0.2)
                        capture = REPORT.parent / f"mobile-{key}.png"
                        driver.save_screenshot(str(capture))
                        screen["mobileScreenshot"] = str(capture.relative_to(ROOT))
                new_buttons = [element for element in driver.find_elements(
                    By.CSS_SELECTOR,
                    "#moduleNew,#competitorNew,#newCalibration,#newNorm,#newFiscal",
                ) if element.is_displayed() and element.is_enabled()]
                if new_buttons:
                    results["current"] = {"screen": key, "phase": "open-primary"}
                    driver.execute_script("arguments[0].click()", new_buttons[0])
                    wait.until(lambda current: current.find_element(By.ID, "recordDialog").get_attribute("open") is not None)
                    screen["dialogModule"] = driver.find_element(By.CSS_SELECTOR, "#recordForm [name=module]").get_attribute("value")
                    screen["dialogTitle"] = driver.find_element(By.ID, "dialogTitle").text
                    screen["dynamicFields"] = len(driver.find_elements(By.CSS_SELECTOR, "#dynamicFields [name^=extra_]"))
                    if shared_records:
                        expected_reference = {
                            "propostas": ("cliente", shared_records["client"]["id"], "Cliente compartilhado"),
                            "ordens_servico": ("cliente", shared_records["client"]["id"], "Cliente compartilhado"),
                            "contas_pagar": ("fornecedor", shared_records["supplier"]["id"], "Fornecedor compartilhado"),
                        }.get(key)
                        if expected_reference:
                            field, expected_id, expected_title = expected_reference
                            selector = f'[name="extra_{field}"]'
                            wait.until(lambda current: any(
                                option.get_attribute("value") == str(expected_id) and expected_title in option.text
                                for option in current.find_element(By.CSS_SELECTOR, selector).find_elements(By.TAG_NAME, "option")
                            ))
                            screen["sharedReference"] = {
                                "field": field, "id": expected_id, "title": expected_title,
                            }
                    if "--mobile" in sys.argv:
                        # Aguarda o painel terminar a entrada pela direita antes de validar suas bordas finais.
                        time.sleep(0.4)
                        screen["mobileDialog"] = driver.execute_script("""
                            const dialog = document.getElementById('recordDialog');
                            const rect = dialog.getBoundingClientRect();
                            return {
                              left: Math.round(rect.left), top: Math.round(rect.top),
                              right: Math.round(window.innerWidth - rect.right),
                              bottom: Math.round(window.innerHeight - rect.bottom),
                              width: Math.round(rect.width), viewport: window.innerWidth,
                              contentOverflow: document.querySelector('.record-form-content')?.scrollWidth >
                                document.querySelector('.record-form-content')?.clientWidth + 1
                            };
                        """)
                        if screen["mobileDialog"]["contentOverflow"]:
                            raise AssertionError(f"{key}: o formulário excede a largura disponível")
                        if abs(screen["mobileDialog"]["left"]) > 1 or abs(screen["mobileDialog"]["right"]) > 1:
                            raise AssertionError(f"{key}: o formulário não está alinhado às bordas do celular")
                    if "--capture-forms" in sys.argv and key in FORM_CAPTURES:
                        time.sleep(0.35)
                        capture = REPORT.parent / f"form-{key}.png"
                        driver.save_screenshot(str(capture))
                        screen["screenshot"] = str(capture.relative_to(ROOT))
                    if "--party-defaults" in sys.argv and key == "clientes_fornecedores":
                        document = driver.find_element(By.NAME, "extra_documento")
                        defaults = {}
                        for label, value, expected in (
                            ("cpf", "52998224725", ("Pessoa física", "Cliente (C)", "529.982.247-25")),
                            ("cnpj", "12345678000195", ("Pessoa jurídica", "Fornecedor (F)", "12.345.678/0001-95")),
                        ):
                            results["current"] = {
                                "screen": key, "phase": f"party-default-{label}",
                            }
                            document.clear()
                            document.send_keys(value)
                            wait.until(lambda current, role=expected[1]:
                                       current.find_element(By.NAME, "extra_tipo_cadastro").get_attribute("value") == role)
                            wait.until(lambda current:
                                       "is-available" in current.find_element(
                                           By.ID, "partyDocumentLookup"
                                       ).get_attribute("class"))
                            defaults[label] = {
                                "document": document.get_attribute("value"),
                                "person": driver.find_element(By.NAME, "extra_tipo_pessoa").get_attribute("value"),
                                "role": driver.find_element(By.NAME, "extra_tipo_cadastro").get_attribute("value"),
                                "nameLabel": driver.find_element(
                                    By.CSS_SELECTOR, '[name="extra_razao_social"]'
                                ).find_element(By.XPATH, "..").find_element(By.TAG_NAME, "span").text,
                                "fantasyHidden": "party-context-hidden" in driver.find_element(
                                    By.NAME, "extra_nome_fantasia"
                                ).find_element(By.XPATH, "..").get_attribute("class"),
                                "customerFieldsHidden": "party-context-hidden" in driver.find_element(
                                    By.NAME, "extra_vendedor"
                                ).find_element(By.XPATH, "..").get_attribute("class"),
                                "supplierFieldsHidden": "party-context-hidden" in driver.find_element(
                                    By.NAME, "extra_avaliacao"
                                ).find_element(By.XPATH, "..").get_attribute("class"),
                            }
                        expected_defaults = {
                            "cpf": {
                                "document": "529.982.247-25",
                                "person": "Pessoa física", "role": "Cliente (C)", "nameLabel": "Nome completo *",
                                "fantasyHidden": True, "customerFieldsHidden": False, "supplierFieldsHidden": True,
                            },
                            "cnpj": {
                                "document": "12.345.678/0001-95",
                                "person": "Pessoa jurídica", "role": "Fornecedor (F)", "nameLabel": "Razão social *",
                                "fantasyHidden": False, "customerFieldsHidden": True, "supplierFieldsHidden": False,
                            },
                        }
                        if defaults != expected_defaults:
                            raise AssertionError(f"Contexto de parceiro divergente: {defaults}")
                        screen["partyDefaults"] = defaults
                        if "--party-live-lookup" in sys.argv:
                            results["current"] = {
                                "screen": key, "phase": "party-live-seed",
                            }
                            existing = driver.execute_async_script("""
                                const done = arguments[0];
                                fetch('/api/records', {
                                  method: 'POST',
                                  headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.SIVSState.csrf},
                                  body: JSON.stringify({
                                    module: 'clientes_fornecedores', title: 'Cliente existente da auditoria',
                                    status: 'Ativo', payload: {
                                      assunto: 'Cliente existente da auditoria', tipo_cadastro: 'C',
                                      documento: '11144477735', tipo_pessoa: 'Pessoa física',
                                      razao_social: 'Cliente existente da auditoria'
                                    }
                                  })
                                }).then(async response => {
                                  const data = await response.json();
                                  done(response.ok ? {id: data.item.id} : {error: data.message});
                                }).catch(error => done({error: error.message}));
                            """)
                            if existing.get("error"):
                                raise AssertionError(existing["error"])
                            document.clear()
                            document.send_keys("11144477735")
                            results["current"] = {
                                "screen": key, "phase": "party-live-wait-existing",
                            }
                            lookup = wait.until(lambda current: (
                                current.find_element(By.ID, "partyDocumentLookup")
                                if "is-existing" in current.find_element(
                                    By.ID, "partyDocumentLookup"
                                ).get_attribute("class") else False
                            ))
                            open_existing = lookup.find_element(
                                By.CSS_SELECTOR, "[data-open-existing-party]"
                            )
                            lookup_result = {
                                "text": lookup.text,
                                "recordId": open_existing.get_attribute("data-open-existing-party"),
                            }
                            driver.execute_script("arguments[0].click()", open_existing)
                            results["current"] = {
                                "screen": key, "phase": "party-live-open-existing",
                            }
                            wait.until(lambda current: current.find_element(
                                By.CSS_SELECTOR, '#recordForm [name="id"]'
                            ).get_attribute("value") == str(existing["id"]))
                            lookup_result["openedTitle"] = driver.find_element(By.ID, "dialogTitle").text
                            if lookup_result["recordId"] != str(existing["id"]):
                                raise AssertionError(f"Cadastro existente incorreto: {lookup_result}")
                            if "Cliente existente da auditoria" not in lookup_result["text"]:
                                raise AssertionError(f"Retorno antecipado incompleto: {lookup_result}")
                            screen["partyLiveLookup"] = lookup_result
                    close = driver.find_element(By.CSS_SELECTOR, "#recordDialog [data-close]")
                    driver.execute_script("arguments[0].click()", close)
                    wait.until(lambda current: current.find_element(By.ID, "recordDialog").get_attribute("open") is None)
                if key == "estoque":
                    results["current"] = {"screen": key, "phase": "open-inventory-ledger"}
                    movement_button = driver.find_element(By.ID, "inventoryNewMovement")
                    driver.execute_script("arguments[0].click()", movement_button)
                    wait.until(lambda current: current.find_element(
                        By.ID, "inventoryMovementDialog"
                    ).get_attribute("open") is not None)
                    screen["inventoryLedger"] = {
                        "dialogTitle": driver.find_element(By.ID, "inventoryMovementTitle").text,
                        "quantityStep": driver.find_element(
                            By.CSS_SELECTOR, '#inventoryMovementForm [name="quantity"]'
                        ).get_attribute("step"),
                        "hasOrigin": bool(driver.find_elements(
                            By.CSS_SELECTOR, '#inventoryMovementForm [name="originType"]'
                        )),
                    }
                    close = driver.find_element(
                        By.CSS_SELECTOR, "#inventoryMovementDialog [data-inventory-close]"
                    )
                    driver.execute_script("arguments[0].click()", close)
                    wait.until(lambda current: current.find_element(
                        By.ID, "inventoryMovementDialog"
                    ).get_attribute("open") is None)
                results["screens"].append(screen)

            if "--auth-only" not in sys.argv and "--capture-only" not in sys.argv:
                results["current"] = {"screen": "contas_receber", "phase": "financial-ledger"}
                financial = driver.execute_async_script("""
                    const done = arguments[0];
                    const headers = {'Content-Type': 'application/json', 'X-CSRF-Token': window.SIVSState.csrf};
                    const post = async (body) => {
                      const response = await fetch('/api/records', {method: 'POST', headers, body: JSON.stringify(body)});
                      const data = await response.json();
                      if (!response.ok) throw new Error(data.message || 'Falha ao preparar título financeiro');
                      return data.item;
                    };
                    (async () => {
                      const categoryResponse = await fetch('/api/financial/categories');
                      const categoryData = await categoryResponse.json();
                      if (!categoryResponse.ok) throw new Error(categoryData.message || 'Falha ao carregar categorias');
                      const revenueCategory = (categoryData.items || []).find(item =>
                        item.active && (item.kind === 'REVENUE' || item.kind === 'BOTH'));
                      if (!revenueCategory) throw new Error('Categoria de receita não encontrada para a auditoria');
                      const client = await post({module: 'clientes_fornecedores', title: 'Cliente ledger navegador', status: 'Ativo', payload: {
                        assunto: 'Cliente ledger navegador', tipo_cadastro: 'C', tipo_pessoa: 'Pessoa jurídica',
                        documento: '12345678000195', razao_social: 'Cliente ledger navegador',
                        aprovado_faturamento: true, bloqueado: false
                      }});
                      const title = await post({module: 'contas_receber', title: 'Receber — auditoria visual', status: 'Em aberto', amount: 100,
                        due_date: '2026-12-20', payload: {assunto: 'Receber auditoria visual', cliente: client.title,
                          cliente_id: client.id, documento: 'AUD-LEDGER-001', parcela: '1/1',
                          categoria_id: revenueCategory.id, centro_custo: 'Operações'}});
                      done({title});
                    })().catch(error => done({error: error.message}));
                """)
                if financial.get("error"):
                    raise AssertionError(financial["error"])
                title_id = financial["title"]["id"]
                driver.execute_script(
                    "arguments[0].click()",
                    driver.find_element(By.CSS_SELECTOR, '[data-nav="contas_receber"]'),
                )
                wait.until(lambda current: current.execute_script(
                    "return window.SIVSState.screen",
                ) == "contas_receber")
                wait.until(lambda current: current.find_elements(
                    By.CSS_SELECTOR, f'[data-edit="{title_id}"]',
                ))
                driver.execute_script(
                    "arguments[0].click()",
                    driver.find_element(By.CSS_SELECTOR, f'[data-edit="{title_id}"]'),
                )
                wait.until(lambda current: current.find_element(
                    By.ID, "recordFinancialLedger",
                ).is_displayed() and "R$ 100,00" in current.find_element(
                    By.ID, "recordFinancialLedger",
                ).text)
                driver.execute_script(
                    "arguments[0].click()",
                    driver.find_element(By.CSS_SELECTOR, "[data-open-settlement]"),
                )
                wait.until(lambda current: current.find_element(
                    By.ID, "financialSettlementDialog",
                ).get_attribute("open") is not None)
                settlement_form = driver.find_element(By.ID, "financialSettlementForm")
                principal = settlement_form.find_element(By.NAME, "principal")
                principal.clear()
                principal.send_keys("40,00")
                driver.execute_script(
                    "arguments[0].click()",
                    settlement_form.find_element(By.CSS_SELECTOR, 'button[type="submit"]'),
                )
                wait.until(lambda current: current.find_element(
                    By.ID, "financialSettlementDialog",
                ).get_attribute("open") is None)
                wait.until(lambda current: "R$ 60,00" in current.find_element(
                    By.ID, "recordFinancialLedger",
                ).text)
                driver.execute_script(
                    "arguments[0].click()",
                    driver.find_element(By.CSS_SELECTOR, "[data-open-reconciliation]"),
                )
                wait.until(lambda current: current.find_element(
                    By.ID, "bankReconciliationDialog",
                ).get_attribute("open") is not None)
                statement = Path(temporary) / "extrato-ledger.csv"
                statement.write_text(
                    f"id;data;tipo;valor;descricao\nBROWSER-001;{datetime.now().strftime('%d/%m/%Y')};credito;40,00;Recebimento visual\n",
                    encoding="utf-8",
                )
                driver.find_element(By.ID, "bankStatementFile").send_keys(str(statement))
                wait.until(lambda current: current.find_elements(
                    By.CSS_SELECTOR, "[data-match-statement]",
                ))
                match_button = driver.find_element(By.CSS_SELECTOR, "[data-match-statement]")
                Select(match_button.find_element(By.XPATH, "..").find_element(By.TAG_NAME, "select")).select_by_index(1)
                driver.execute_script("arguments[0].click()", match_button)
                wait.until(lambda current: current.find_elements(
                    By.CSS_SELECTOR, "[data-unmatch-statement]",
                ))
                driver.execute_script(
                    "arguments[0].click()",
                    driver.find_element(By.CSS_SELECTOR, "#bankReconciliationDialog [data-close]"),
                )
                wait.until(lambda current: current.find_element(
                    By.ID, "bankReconciliationDialog",
                ).get_attribute("open") is None)
                wait.until(lambda current: "Conciliado" in current.find_element(
                    By.ID, "recordFinancialLedger",
                ).text)
                results["financialLedger"] = {
                    "titleId": title_id, "partialBalance": "R$ 60,00",
                    "cashMovement": "R$ 40,00", "bankReconciliation": "confirmed",
                    "reversalBlockedWhileReconciled": driver.find_element(
                        By.CSS_SELECTOR, "[data-reverse-settlement]",
                    ).get_attribute("disabled") is not None,
                }
                driver.execute_script(
                    "arguments[0].click()",
                    driver.find_element(By.CSS_SELECTOR, "#recordDialog [data-close]"),
                )
                wait.until(lambda current: current.find_element(
                    By.ID, "recordDialog",
                ).get_attribute("open") is None)

            # Abas de trabalho: valida estado ativo, limite, retorno a uma área anterior e fechamento.
            if len(screen_keys) >= 2:
                results["current"] = {"screen": screen_keys[-1], "phase": "workspace-tabs"}
                tab_buttons = driver.find_elements(By.CSS_SELECTOR, "#workspaceTabs [data-workspace-tab]")
                active_tabs = driver.find_elements(
                    By.CSS_SELECTOR, '#workspaceTabs [data-workspace-tab][aria-current="page"]',
                )
                if len(active_tabs) != 1:
                    raise AssertionError("As abas devem ter exatamente uma área ativa")
                if len(tab_buttons) > 8:
                    raise AssertionError("As abas excederam o limite operacional de oito áreas")
                target = next((item for item in reversed(tab_buttons[:-1])
                               if item.get_attribute("data-workspace-tab") != "dashboard"), None)
                if target:
                    target_key = target.get_attribute("data-workspace-tab")
                    driver.execute_script("arguments[0].click()", target)
                    wait.until(lambda current, expected=target_key: current.execute_script(
                        "return window.SIVSState.screen",
                    ) == expected)
                    close = driver.find_element(
                        By.CSS_SELECTOR, f'[data-workspace-tab-close="{target_key}"]',
                    )
                    driver.execute_script("arguments[0].click()", close)
                    wait.until(lambda current, closed=target_key: not current.find_elements(
                        By.CSS_SELECTOR, f'[data-workspace-tab="{closed}"]',
                    ))
                    results["workspaceTabs"] = {
                        "opened": len(tab_buttons), "returnedTo": target_key,
                        "closed": target_key, "activeCount": 1,
                        "keyboardNavigation": "ArrowLeft/ArrowRight/Home/End",
                    }

            # Gestão de usuário: cria uma conta real apenas no banco temporário e valida o login.
            if driver.execute_script("return window.SIVSState.screen") != "settings":
                driver.execute_script("arguments[0].click()", driver.find_element(By.CSS_SELECTOR, '[data-nav="settings"]'))
            results["current"] = {"screen": "settings", "phase": "wait-new-user"}
            wait.until(lambda current: current.find_elements(By.ID, "newUser"))

            # Lixeira: cria e exclui um registro somente no banco descartável, então valida as duas
            # confirmações destrutivas sem efetivar a exclusão permanente durante a auditoria visual.
            results["current"] = {"screen": "settings", "phase": "seed-trash"}
            trash_seed = driver.execute_async_script("""
                const done = arguments[0];
                const headers = {"Content-Type": "application/json", "X-CSRF-Token": window.SIVSState.csrf};
                const payload = {
                  module: "clientes", title: "Fornecedor na lixeira", status: "Ativo",
                  amount: null, due_date: null,
                  payload: {assunto: "Fornecedor na lixeira", relacionamentos: [],
                    tipo_pessoa: "Pessoa jurídica", tipo_cadastro: "Fornecedor (F)",
                    documento: "04252011000110", razao_social: "Fornecedor na lixeira"}
                };
                fetch("/api/records", {method: "POST", headers, body: JSON.stringify(payload)})
                  .then(async response => ({ok: response.ok, data: await response.json()}))
                  .then(created => {
                    if (!created.ok) throw new Error(created.data.message || "Falha ao criar item de auditoria");
                    return fetch(`/api/records/${created.data.item.id}`, {method: "DELETE", headers});
                  })
                  .then(async response => {
                    if (!response.ok) throw new Error((await response.json()).message || "Falha ao mover para lixeira");
                    return window.loadSettings();
                  })
                  .then(() => done({ok: true})).catch(error => done({ok: false, message: error.message}));
            """)
            if not trash_seed.get("ok"):
                raise AssertionError(f"Falha ao preparar lixeira: {trash_seed.get('message')}")
            wait.until(lambda current: current.find_elements(By.ID, "emptyTrash"))
            delete_button = driver.find_element(By.CSS_SELECTOR, "[data-trash-purge]")
            driver.execute_script("arguments[0].click()", delete_button)
            wait.until(lambda current: current.find_element(By.ID, "trashPurgeDialog").get_attribute("open") is not None)
            individual_label = driver.find_element(By.ID, "trashPurgeConfirmationLabel").text
            driver.execute_script(
                "arguments[0].click()",
                driver.find_element(By.CSS_SELECTOR, "#trashPurgeDialog [data-close]"),
            )
            wait.until(lambda current: current.find_element(By.ID, "trashPurgeDialog").get_attribute("open") is None)
            driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "emptyTrash"))
            wait.until(lambda current: current.find_element(By.ID, "trashPurgeDialog").get_attribute("open") is not None)
            bulk_label = driver.find_element(By.ID, "trashPurgeConfirmationLabel").text
            results["trash"] = {
                "itemAction": delete_button.text,
                "individualConfirmation": individual_label,
                "bulkConfirmation": bulk_label,
            }
            driver.execute_script(
                "arguments[0].click()",
                driver.find_element(By.CSS_SELECTOR, "#trashPurgeDialog [data-close]"),
            )
            wait.until(lambda current: current.find_element(By.ID, "trashPurgeDialog").get_attribute("open") is None)

            driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "newUser"))
            results["current"] = {"screen": "settings", "phase": "open-user-dialog"}
            wait.until(lambda current: current.find_element(By.ID, "userDialog").get_attribute("open") is not None)
            user_form = driver.find_element(By.ID, "userForm")
            user_form.find_element(By.NAME, "name").send_keys("Usuário Auditor")
            user_form.find_element(By.NAME, "email").send_keys("usuario.audit@example.test")
            user_form.find_element(By.NAME, "password").send_keys("Senha-Usuario-123")
            driver.execute_script("arguments[0].click()", user_form.find_element(By.CSS_SELECTOR, "button[type=submit]"))
            results["current"] = {"screen": "settings", "phase": "configure-user-access"}
            wait.until(lambda current: current.find_element(
                By.ID, "permissionsDialog"
            ).get_attribute("open") is not None)
            results["userAccess"] = {
                "categories": len(driver.find_elements(By.CSS_SELECTOR, ".permission-category")),
                "functions": len(driver.find_elements(
                    By.CSS_SELECTOR, "[data-permission-functional-action]"
                )),
                "mobileReady": bool(driver.find_elements(By.ID, "permissionsSearch")),
            }
            driver.execute_script(
                "arguments[0].click()", driver.find_element(By.ID, "permissionsSubmit")
            )
            results["current"] = {"screen": "settings", "phase": "save-user"}
            wait.until(lambda current: "usuario.audit@example.test" in visible_text(current, ".user-list"))
            driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "logoutButton"))
            results["current"] = {"screen": "settings", "phase": "logout"}
            wait.until(lambda current: current.find_element(By.ID, "authForm").is_displayed())
            login = driver.find_element(By.ID, "authForm")
            login.find_element(By.NAME, "email").clear()
            login.find_element(By.NAME, "email").send_keys("usuario.audit@example.test")
            login.find_element(By.NAME, "password").clear()
            login.find_element(By.NAME, "password").send_keys("Senha-Usuario-123")
            driver.execute_script("arguments[0].click()", login.find_element(By.CSS_SELECTOR, "button[type=submit]"))
            results["current"] = {"screen": "login", "phase": "user-login"}
            wait.until(lambda current: "is-authenticated" in current.find_element(By.TAG_NAME, "body").get_attribute("class"))
            results["userLogin"] = "ok"

            browser_errors = actionable_browser_errors(driver)
            results["errors"] = browser_errors
        except (AssertionError, TimeoutException, RuntimeError, Exception) as failure:  # noqa: BLE001
            results["fatal"] = f"{type(failure).__name__}: {failure}"
            if driver:
                results["snapshot"] = {
                    "toast": visible_text(driver, "#toast"),
                    "authError": visible_text(driver, "#authError"),
                    "passwordError": visible_text(driver, "#passwordFormError"),
                    "users": visible_text(driver, ".user-list"),
                    "recordDialogOpen": driver.find_element(
                        By.ID, "recordDialog"
                    ).get_attribute("open") is not None,
                    "recordModule": driver.find_element(
                        By.CSS_SELECTOR, '#recordForm [name="module"]'
                    ).get_attribute("value"),
                    "partyDocument": driver.find_element(
                        By.NAME, "extra_documento"
                    ).get_attribute("value") if driver.find_elements(
                        By.NAME, "extra_documento"
                    ) else "",
                    "partyRole": driver.find_element(
                        By.NAME, "extra_tipo_cadastro"
                    ).get_attribute("value") if driver.find_elements(
                        By.NAME, "extra_tipo_cadastro"
                    ) else "",
                    "partyLookupClass": driver.find_element(
                        By.ID, "partyDocumentLookup"
                    ).get_attribute("class"),
                    "partyLookupText": visible_text(driver, "#partyDocumentLookup"),
                }
        finally:
            if driver:
                try:
                    results["errors"] = actionable_browser_errors(driver)
                except Exception:  # noqa: BLE001
                    pass
                driver.quit()
            if server:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                if results.get("fatal") and server.stderr:
                    results["serverStderr"] = server.stderr.read()[-4000:]
            REPORT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(REPORT)
    if results.get("fatal") or results.get("errors"):
        print(f"Falha: {results.get('fatal')}; ponto: {results.get('current')}")
        return 1
    print(f"{len(results['screens'])} telas auditadas; login de usuário: {results.get('userLogin')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
