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
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "sivs_2_2" / "server.py"
REPORT = ROOT / ".artifacts" / "interaction-audit.json"
FORM_CAPTURES = {"clientes_fornecedores", "propostas", "ordens_servico", "contas_pagar"}
MOBILE_CAPTURES = {
    "dashboard", "clientes_fornecedores", "propostas", "editais",
    "concorrentes", "ordens_servico", "financeiro", "settings",
}


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def base_python() -> str:
    """Interpretador fora do venv de ferramentas, onde as dependências do servidor estão instaladas."""
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
    with tempfile.TemporaryDirectory(prefix="sivs-interaction-audit-") as temporary:
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
                wait.until(lambda current: visible_text(current, "#content") not in {"", "Carregando registros…"})
                screen = {
                    "key": key,
                    "title": driver.find_element(By.ID, "sectionTitle").text,
                    "primaryButtons": visible_text(driver, "#content button.primary"),
                    "dialogModule": None,
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
                            document.clear()
                            document.send_keys(value)
                            wait.until(lambda current, role=expected[1]:
                                       current.find_element(By.NAME, "extra_tipo_cadastro").get_attribute("value") == role)
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
                    close = driver.find_element(By.CSS_SELECTOR, "#recordDialog [data-close]")
                    driver.execute_script("arguments[0].click()", close)
                    wait.until(lambda current: current.find_element(By.ID, "recordDialog").get_attribute("open") is None)
                results["screens"].append(screen)

            # Gestão de usuário: cria uma conta real apenas no banco temporário e valida o login.
            if driver.execute_script("return window.SIVSState.screen") != "settings":
                driver.execute_script("arguments[0].click()", driver.find_element(By.CSS_SELECTOR, '[data-nav="settings"]'))
            results["current"] = {"screen": "settings", "phase": "wait-new-user"}
            wait.until(lambda current: current.find_elements(By.ID, "newUser"))
            driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "newUser"))
            results["current"] = {"screen": "settings", "phase": "open-user-dialog"}
            wait.until(lambda current: current.find_element(By.ID, "userDialog").get_attribute("open") is not None)
            user_form = driver.find_element(By.ID, "userForm")
            user_form.find_element(By.NAME, "name").send_keys("Usuário Auditor")
            user_form.find_element(By.NAME, "email").send_keys("usuario.audit@example.test")
            user_form.find_element(By.NAME, "password").send_keys("Senha-Usuario-123")
            driver.execute_script("arguments[0].click()", user_form.find_element(By.CSS_SELECTOR, "button[type=submit]"))
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
