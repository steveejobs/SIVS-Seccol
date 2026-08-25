#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");
const QUICK = process.argv.includes("--quick");
const CDP_CALL_TIMEOUT_MS = 30_000;
const viewportArgument = process.argv.find((argument) => argument.startsWith("--viewport="));
const SELECTED_VIEWPORT = viewportArgument?.split("=", 2)[1] || "";
const outputArgument = process.argv.slice(2).find((argument) => !argument.startsWith("--"));
const OUTPUT = resolve(outputArgument || join(ROOT, ".artifacts", QUICK ? "responsive-audit-quick" : "responsive-audit"));
const availablePort = () => new Promise((resolvePort, rejectPort) => {
  const listener = createServer();
  listener.once("error", rejectPort);
  listener.listen(0, "127.0.0.1", () => {
    const { port } = listener.address();
    listener.close((error) => error ? rejectPort(error) : resolvePort(port));
  });
});
const SERVER_PORT = await availablePort();
let DEBUG_PORT = await availablePort();
while (DEBUG_PORT === SERVER_PORT) DEBUG_PORT = await availablePort();
const BASE_URL = `http://127.0.0.1:${SERVER_PORT}`;
const CAPTURE_SCREENS = new Set(["dashboard", "portfolio", "clientes", "editais", "mobile", "estoque", "fiscal", "controladoria", "normas_tecnicas", "settings"]);
const ALL_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 1000, mobile: false },
  { name: "tablet", width: 834, height: 1112, mobile: false },
  { name: "mobile", width: 390, height: 844, mobile: true },
  { name: "mobile-360", width: 360, height: 800, mobile: true },
];
if (SELECTED_VIEWPORT && !ALL_VIEWPORTS.some(({ name }) => name === SELECTED_VIEWPORT)) {
  throw new Error(`Viewport desconhecido: ${SELECTED_VIEWPORT}`);
}
const VIEWPORTS = SELECTED_VIEWPORT
  ? ALL_VIEWPORTS.filter(({ name }) => name === SELECTED_VIEWPORT)
  : (QUICK ? ALL_VIEWPORTS.filter(({ name }) => name === "mobile") : ALL_VIEWPORTS);

function browserPath() {
  return process.env.SIVS_BROWSER || (process.platform === "win32"
    ? "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    : "microsoft-edge");
}

async function waitFor(url, attempts = 80) {
  for (let index = 0; index < attempts; index += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return response;
    } catch {}
    await new Promise((resolveWait) => setTimeout(resolveWait, 200));
  }
  throw new Error(`Tempo esgotado aguardando ${url}`);
}

async function removeTemporary(path) {
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      rmSync(path, { recursive: true, force: true });
      return;
    } catch (error) {
      if (attempt === 5) {
        const cleanup = spawn(process.execPath, [
          "-e",
          `const {rmSync}=require("node:fs");let tries=0;const path=process.argv[1];const timer=setInterval(()=>{try{rmSync(path,{recursive:true,force:true});clearInterval(timer)}catch{if(++tries>=30)clearInterval(timer)}},1000);`,
          path,
        ], { cwd: ROOT, detached: true, stdio: "ignore", windowsHide: true });
        cleanup.unref();
        console.warn(`Limpeza do runtime agendada após a liberação do navegador: ${path} (${error.code})`);
        return;
      }
      await new Promise((resolveWait) => setTimeout(resolveWait, 1000));
    }
  }
}

class CDP {
  constructor(url) {
    this.id = 0;
    this.pending = new Map();
    this.socket = new WebSocket(url);
  }

  async open() {
    await new Promise((resolveOpen, reject) => {
      this.socket.addEventListener("open", resolveOpen, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", ({ data }) => {
      const message = JSON.parse(data);
      if (!message.id || !this.pending.has(message.id)) return;
      const { resolveCall, rejectCall, timeout } = this.pending.get(message.id);
      this.pending.delete(message.id);
      clearTimeout(timeout);
      if (message.error) rejectCall(new Error(message.error.message));
      else resolveCall(message.result || {});
    });
    this.socket.addEventListener("close", () => {
      for (const { rejectCall, timeout } of this.pending.values()) {
        clearTimeout(timeout);
        rejectCall(new Error("Conexão com o navegador encerrada durante a auditoria"));
      }
      this.pending.clear();
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolveCall, rejectCall) => {
      const timeout = setTimeout(() => {
        if (!this.pending.has(id)) return;
        this.pending.delete(id);
        rejectCall(new Error(`Tempo esgotado na chamada CDP: ${method}`));
      }, CDP_CALL_TIMEOUT_MS);
      this.pending.set(id, { resolveCall, rejectCall, timeout });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression, awaitPromise = true) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result?.value;
  }

  close() { this.socket.close(); }
}

async function waitUntil(cdp, expression, attempts = 80) {
  for (let index = 0; index < attempts; index += 1) {
    if (await cdp.evaluate(expression)) return;
    await new Promise((resolveWait) => setTimeout(resolveWait, 150));
  }
  throw new Error(`Condição não alcançada: ${expression}`);
}

mkdirSync(OUTPUT, { recursive: true });
const temporary = mkdtempSync(join(OUTPUT, ".runtime-"));
const server = spawn(process.env.PYTHON || "python", [
  join(ROOT, "sivs_2_2", "server.py"), "--host", "127.0.0.1", "--port", String(SERVER_PORT),
  "--db", join(temporary, "audit.db"),
], { cwd: ROOT, stdio: "ignore", windowsHide: true });
let browser;
let cdp;

try {
  await waitFor(`${BASE_URL}/api/status`);
  browser = spawn(browserPath(), [
    "--headless=new", "--disable-gpu", "--disable-background-networking", "--no-first-run",
    "--disable-extensions", `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${join(temporary, "browser-profile")}`, "about:blank",
  ], { stdio: "ignore", windowsHide: true });
  const targetsResponse = await waitFor(`http://127.0.0.1:${DEBUG_PORT}/json/list`);
  const targets = await targetsResponse.json();
  cdp = new CDP(targets.find((target) => target.type === "page").webSocketDebuggerUrl);
  await cdp.open();
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Page.navigate", { url: BASE_URL });
  await waitUntil(cdp, "document.readyState === 'complete'");
  await waitUntil(cdp, "document.querySelector('#auth:not(.hidden)') !== null");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 390, height: 844, deviceScaleFactor: 1, mobile: true,
    screenWidth: 390, screenHeight: 844,
  });
  await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  const authInteractions = [];
  const initialSetup = await cdp.evaluate(`(() => ({
    interaction:'auth-mode-switch',
    initialSetup:document.querySelector('#authForm').dataset.mode === 'setup',
    loginOptionVisible:!document.querySelector('#authModeSwitch').classList.contains('hidden')
  }))()`);
  const authSetupImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  writeFileSync(join(OUTPUT, "auth-setup.png"), Buffer.from(authSetupImage.data, "base64"));
  await cdp.evaluate("document.querySelector('#authModeToggle').click()");
  const loginAlternative = await cdp.evaluate(`(() => ({
    loginMode:document.querySelector('#authForm').dataset.mode === 'login',
    setupFieldsHidden:document.querySelector('#companyField').classList.contains('hidden') && document.querySelector('#nameField').classList.contains('hidden'),
    setupAlternativeVisible:document.querySelector('#authModeToggle').textContent.includes('Configurar')
  }))()`);
  const authLoginImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
  writeFileSync(join(OUTPUT, "auth-login.png"), Buffer.from(authLoginImage.data, "base64"));
  await cdp.evaluate("document.querySelector('#authModeToggle').click()");
  const setupRestored = await cdp.evaluate(`(() => ({
    setupRestored:document.querySelector('#authForm').dataset.mode === 'setup',
    setupFieldsRequired:document.querySelector('#authForm [name=company]').required && document.querySelector('#authForm [name=name]').required
  }))()`);
  authInteractions.push({...initialSetup, ...loginAlternative, ...setupRestored});
  await cdp.evaluate(`(async () => {
    const response = await fetch('/api/setup', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({company:'Auditoria Responsiva', name:'Auditor UI', email:'audit@sivs.local', password:'AuditSivs#2026'})
    });
    if (!response.ok) throw new Error(await response.text());
    location.reload();
  })()`);
  await waitUntil(cdp, "document.querySelector('#app:not(.hidden)') !== null", 120);
  await waitUntil(cdp, "document.querySelectorAll('[data-nav]').length > 0", 120);
  const screens = QUICK ? ["clientes", "controladoria", "fiscal"] : await cdp.evaluate("[...new Set([...document.querySelectorAll('[data-nav]')].map((element) => element.dataset.nav))]");

  const report = [];
  const interactions = [...authInteractions];
  for (const viewport of VIEWPORTS) {
    console.log(`[auditoria] ${viewport.name}: ${viewport.width}x${viewport.height}`);
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: viewport.mobile,
      screenWidth: viewport.width, screenHeight: viewport.height,
    });
    for (const screen of screens) {
      await cdp.evaluate(`navigate(${JSON.stringify(screen)})`);
      await new Promise((resolveWait) => setTimeout(resolveWait, 280));
      const diagnostics = await cdp.evaluate(`(() => {
        const visible = (element) => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 &&
            rect.right > 0 && rect.bottom > 0 && rect.left < innerWidth && rect.top < innerHeight;
        };
        const allowedOverflow = (element) => element.closest('.table-wrap,.kanban-wrap,.tender-results,.legacy-alert-panel>div,.workspace-tabs');
        const overflow = [...document.querySelectorAll('body *')].filter(visible).filter((element) => {
          const rect = element.getBoundingClientRect();
          return !allowedOverflow(element) && (rect.right > innerWidth + 2 || rect.left < -2);
        }).slice(0, 15).map((element) => ({tag:element.tagName, className:String(element.className).slice(0,100), right:Math.round(element.getBoundingClientRect().right)}));
        const crampedElements = [...document.querySelectorAll('button,a,input,select,textarea')].filter(visible).filter((element) => {
          const rect = element.getBoundingClientRect();
          return rect.width < 40 || rect.height < 40;
        });
        const crampedControlDetails = crampedElements.slice(0, 12).map((element) => {
          const rect = element.getBoundingClientRect();
          return {tag:element.tagName,id:element.id,className:String(element.className).slice(0,80),width:Math.round(rect.width),height:Math.round(rect.height),text:String(element.textContent || element.value || '').trim().slice(0,40)};
        });
        return {screen:${JSON.stringify(screen)}, viewport:{width:innerWidth,height:innerHeight}, documentWidth:document.documentElement.scrollWidth, overflow, crampedControls:crampedElements.length, crampedControlDetails,
          workCenterPresent:${JSON.stringify(screen)} !== 'dashboard' || Boolean(document.querySelector('.work-center'))};
      })()`);
      if (CAPTURE_SCREENS.has(screen)) {
        const image = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
        writeFileSync(join(OUTPUT, `${viewport.name}-${screen}.png`), Buffer.from(image.data, "base64"));
      }
      report.push({ device: viewport.name, ...diagnostics });
    }
    console.log(`[auditoria] ${viewport.name}: telas concluÃ­das; validando interaÃ§Ãµes`);

    await cdp.evaluate("navigate('clientes')");
    await cdp.evaluate("document.querySelector('#newButton').click()");
    await waitUntil(cdp, "document.querySelector('#recordDialog[open]') !== null");
    await waitUntil(cdp, `(() => {
      const element = document.querySelector('#recordDialog');
      const rect = element.getBoundingClientRect();
      const matrix = new DOMMatrix(getComputedStyle(element).transform);
      return Math.abs(matrix.a - 1) < .001 && Math.abs(matrix.d - 1) < .001 &&
        rect.left >= -1 && rect.right <= innerWidth + 1 && rect.top >= -1 && rect.bottom <= innerHeight + 1;
    })()`);
    const dialog = await cdp.evaluate(`(() => {
      const element = document.querySelector('#recordDialog');
      const form = document.querySelector('#recordForm');
      const rect = element.getBoundingClientRect();
      const footer = element.querySelector('.record-actions').getBoundingClientRect();
      const computed = getComputedStyle(element);
      const governance = document.querySelector('#recordGovernance');
      const statusSelect = form.elements.status;
      const supportsBaseSelect = CSS.supports('appearance', 'base-select');
      return {
        device:${JSON.stringify(viewport.name)}, interaction:'record-dialog', open:element.open,
        insideViewport:rect.left >= -1 && rect.right <= innerWidth + 1 && rect.top >= -1 && rect.bottom <= innerHeight + 1,
        footerReachable:footer.top < rect.bottom && footer.bottom <= rect.bottom + 1,
        essentialMode:form.classList.contains('is-essential-mode'),
        optionalContentHidden:getComputedStyle(governance).display === 'none',
        baseSelectSupported:supportsBaseSelect,
        selectAppearance:getComputedStyle(statusSelect).appearance,
        bounds:{left:Math.round(rect.left),top:Math.round(rect.top),right:Math.round(rect.right),bottom:Math.round(rect.bottom),width:Math.round(rect.width),height:Math.round(rect.height)},
        computed:{position:computed.position,top:computed.top,bottom:computed.bottom,marginTop:computed.marginTop,height:computed.height,maxHeight:computed.maxHeight,transform:computed.transform},
        visualViewport:{height:Math.round(visualViewport.height),offsetTop:Math.round(visualViewport.offsetTop)},
      };
    })()`);
    const dialogImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(join(OUTPUT, `${viewport.name}-record-dialog.png`), Buffer.from(dialogImage.data, "base64"));
    interactions.push(dialog);
    if (dialog.baseSelectSupported) {
      const selectPoint = await cdp.evaluate(`(() => {
        const rect = document.querySelector('#recordForm [name=status]').getBoundingClientRect();
        return {x:rect.left + rect.width / 2, y:rect.top + rect.height / 2};
      })()`);
      await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: selectPoint.x, y: selectPoint.y, button: "left", clickCount: 1 });
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: selectPoint.x, y: selectPoint.y, button: "left", clickCount: 1 });
      await new Promise((resolveWait) => setTimeout(resolveWait, 180));
      const selectPicker = await cdp.evaluate(`(() => ({
        device:${JSON.stringify(viewport.name)}, interaction:'select-picker',
        opened:document.querySelector('#recordForm [name=status]').matches(':open')
      }))()`);
      interactions.push(selectPicker);
      const pickerImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
      writeFileSync(join(OUTPUT, `${viewport.name}-select-picker.png`), Buffer.from(pickerImage.data, "base64"));
      await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape" });
      await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: "Escape", code: "Escape" });
    }
    await cdp.evaluate("document.querySelector('#recordOptionalToggle').click()");
    const disclosure = await cdp.evaluate(`(() => ({
      device:${JSON.stringify(viewport.name)}, interaction:'record-disclosure',
      expanded:document.querySelector('#recordOptionalToggle').getAttribute('aria-expanded') === 'true',
      optionalContentVisible:getComputedStyle(document.querySelector('#recordGovernance')).display !== 'none'
    }))()`);
    interactions.push(disclosure);
    await cdp.evaluate("document.querySelector('#recordDialog').dispatchEvent(new Event('cancel', {cancelable:true}))");
    await waitUntil(cdp, "document.querySelector('#recordDialog[open]') === null");

    await cdp.evaluate("document.querySelector('#newButton').click()");
    await waitUntil(cdp, "document.querySelector('#recordDialog[open]') !== null");
    await cdp.evaluate(`(() => {
      const form = document.querySelector('#recordForm');
      form.title.value = 'Rascunho responsivo ${viewport.name}';
      form.assunto.value = 'Teste de recuperaÃ§Ã£o local';
      form.title.dispatchEvent(new Event('input', {bubbles:true}));
    })()`);
    await new Promise((resolveWait) => setTimeout(resolveWait, 750));
    await cdp.evaluate("document.querySelector('#recordDialog').dispatchEvent(new Event('cancel', {cancelable:true}))");
    await waitUntil(cdp, "document.querySelector('#recordDialog[open]') === null");
    await cdp.evaluate("document.querySelector('#newButton').click()");
    await waitUntil(cdp, "document.querySelector('#recordDialog[open]') !== null && !document.querySelector('#draftNotice').classList.contains('hidden')");
    await cdp.evaluate("document.querySelector('#restoreDraft').click()");
    const draft = await cdp.evaluate(`(() => ({
      device:${JSON.stringify(viewport.name)}, interaction:'record-draft',
      restored:document.querySelector('#recordForm').title.value === 'Rascunho responsivo ${viewport.name}',
      noticeDismissed:document.querySelector('#draftNotice').classList.contains('hidden'),
      detailsExpanded:document.querySelector('#recordOptionalToggle').getAttribute('aria-expanded') === 'true'
    }))()`);
    interactions.push(draft);
    await cdp.evaluate("sessionStorage.clear(); document.querySelector('#recordForm').reset(); state.formBaseline = JSON.stringify({values:{},relationships:[]}); document.querySelector('#recordDialog').close() ");

    await cdp.evaluate("navigate('dashboard')");
    await cdp.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key:'k', ctrlKey:true, bubbles:true}))");
    await waitUntil(cdp, "document.querySelector('#commandDialog[open]') !== null");
    await cdp.evaluate(`(() => {
      const input = document.querySelector('#commandInput');
      input.value = 'Clientes';
      input.dispatchEvent(new Event('input', {bubbles:true}));
    })()`);
    await waitUntil(cdp, "[...document.querySelectorAll('#commandResults .command-group-label')].some((element) => element.textContent.includes('Registros')) && document.querySelectorAll('#commandResults .command-row').length > 0 && document.querySelectorAll('#commandResults .command-row').length <= 2");
    await cdp.evaluate(`(() => {
      const input = document.querySelector('#commandInput');
      input.value = 'Contador';
      input.dispatchEvent(new Event('input', {bubbles:true}));
    })()`);
    await waitUntil(cdp, "[...document.querySelectorAll('#commandResults strong')].some((element) => element.textContent.includes('Contador'))");
    const command = await cdp.evaluate(`(() => {
      const element = document.querySelector('#commandDialog');
      const rect = element.getBoundingClientRect();
      return {device:${JSON.stringify(viewport.name)}, interaction:'command-palette', open:element.open,
        insideViewport:rect.left >= -1 && rect.right <= innerWidth + 1 && rect.top >= -1 && rect.bottom <= innerHeight + 1,
        hasResults:Boolean(element.querySelector('[data-command-index]')), focused:document.activeElement === document.querySelector('#commandInput')};
    })()`);
    const commandImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(join(OUTPUT, `${viewport.name}-command-palette.png`), Buffer.from(commandImage.data, "base64"));
    interactions.push(command);
    await cdp.evaluate("document.querySelector('#commandDialog').dispatchEvent(new Event('cancel', {cancelable:true}))");
    await waitUntil(cdp, "document.querySelector('#commandDialog[open]') === null");

    await cdp.evaluate("navigate('settings')");
    await waitUntil(cdp, "document.querySelector('[data-user-permissions]') !== null");
    await cdp.evaluate("document.querySelector('[data-user-permissions]').click()");
    await waitUntil(cdp, "document.querySelector('#permissionsDialog[open]') !== null && document.querySelectorAll('#permissionsModuleList .permission-module-row').length > 0");
    await cdp.evaluate(`(() => {
      const input = document.querySelector('#permissionsSearch');
      input.value = 'Estoque e lotes';
      input.dispatchEvent(new Event('input', {bubbles:true}));
    })()`);
    await waitUntil(cdp, "document.querySelectorAll('#permissionsModuleList .permission-module-row').length === 1");
    const permissions = await cdp.evaluate(`(() => {
      const element = document.querySelector('#permissionsDialog');
      const rect = element.getBoundingClientRect();
      const row = document.querySelector('#permissionsModuleList .permission-module-row');
      const read = row.querySelector('[data-permission-action=read]');
      read.checked = false;
      read.dispatchEvent(new Event('change', {bubbles:true}));
      const updatedRow = document.querySelector('#permissionsModuleList .permission-module-row');
      return {
        device:${JSON.stringify(viewport.name)}, interaction:'permissions-dialog', open:element.open,
        insideViewport:rect.left >= -1 && rect.right <= innerWidth + 1 && rect.top >= -1 && rect.bottom <= innerHeight + 1,
        dialogRect:{left:rect.left, right:rect.right, top:rect.top, bottom:rect.bottom, viewportWidth:innerWidth, viewportHeight:innerHeight},
        filteredToInventory:row.dataset.permissionModuleRow === 'estoque',
        dependenciesCleared:![...updatedRow.querySelectorAll('[data-permission-action]')].some((checkbox) => checkbox.checked),
        touchTarget:Math.round(updatedRow.getBoundingClientRect().height) >= 44,
        capabilities:element.querySelectorAll('[data-permission-capability]').length === 3,
      };
    })()`);
    await new Promise((resolveWait) => setTimeout(resolveWait, 260));
    const permissionsImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(join(OUTPUT, `${viewport.name}-permissions-dialog.png`), Buffer.from(permissionsImage.data, "base64"));
    interactions.push(permissions);
    await cdp.evaluate("document.querySelector('#permissionsDialog').dispatchEvent(new Event('cancel', {cancelable:true}))");
    await waitUntil(cdp, "document.querySelector('#permissionsDialog[open]') === null");

    await cdp.evaluate("navigate('fiscal')");
    await waitUntil(cdp, "document.querySelector('#openFiscalConfiguration') !== null");
    await cdp.evaluate("document.querySelector('#openFiscalConfiguration').click()");
    await waitUntil(cdp, "document.querySelector('#fiscalConfigurationDialog[open]') !== null");
    // A medição deve ocorrer depois dos 220 ms de motion, inclusive sob carga no Windows.
    await new Promise((resolveWait) => setTimeout(resolveWait, 360));
    const fiscalSetup = await cdp.evaluate(`(() => {
      const element = document.querySelector('#fiscalConfigurationDialog');
      const rect = element.getBoundingClientRect();
      const submit = element.querySelector('[type=submit]');
      return {
        device:${JSON.stringify(viewport.name)}, interaction:'fiscal-setup-dialog', open:element.open,
        insideViewport:rect.left >= -1 && rect.right <= innerWidth + 1 && rect.top >= -1 && rect.bottom <= innerHeight + 1,
        hasFiscalIdentity:['legalName','cnpj','stateRegistration','municipalityCode','taxRegime'].every((name) => element.querySelector('[name=' + name + ']')),
        productionUnavailable:![...element.querySelector('[name=environment]').options].some((option) => option.value === 'PRODUCTION'),
        touchTarget:Math.round(submit.getBoundingClientRect().height) >= 44,
      };
    })()`);
    const fiscalSetupImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(join(OUTPUT, `${viewport.name}-fiscal-setup-dialog.png`), Buffer.from(fiscalSetupImage.data, "base64"));
    interactions.push(fiscalSetup);
    await cdp.evaluate("document.querySelector('#fiscalConfigurationDialog').close()");
    await waitUntil(cdp, "document.querySelector('#fiscalConfigurationDialog[open]') === null");

    if (viewport.width <= 900) {
      await cdp.evaluate("document.querySelector('#menuButton').click()");
      await waitUntil(cdp, "document.querySelector('#sidebar').classList.contains('open')");
      await new Promise((resolveWait) => setTimeout(resolveWait, 300));
      const navigation = await cdp.evaluate(`(() => ({
        device:${JSON.stringify(viewport.name)}, interaction:'navigation-drawer',
        expanded:document.querySelector('#menuButton').getAttribute('aria-expanded') === 'true',
        sidebarExposed:document.querySelector('#sidebar').getAttribute('aria-hidden') === 'false' && !document.querySelector('#sidebar').inert,
        scrollLocked:document.body.classList.contains('has-mobile-navigation')
      }))()`);
      const navigationImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
      writeFileSync(join(OUTPUT, `${viewport.name}-navigation-open.png`), Buffer.from(navigationImage.data, "base64"));
      interactions.push(navigation);
      await cdp.evaluate("document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape'}))");
      await waitUntil(cdp, "!document.querySelector('#sidebar').classList.contains('open')");
    }
  }
  await cdp.evaluate("logout()");
  await waitUntil(cdp, "document.querySelector('#auth:not(.hidden)') !== null");
  interactions.push(await cdp.evaluate(`(() => ({
    interaction:'configured-login',
    loginMode:document.querySelector('#authForm').dataset.mode === 'login',
    setupOptionHidden:document.querySelector('#authModeSwitch').classList.contains('hidden')
  }))()`));
  writeFileSync(join(OUTPUT, "report.json"), JSON.stringify(report, null, 2));
  writeFileSync(join(OUTPUT, "interactions.json"), JSON.stringify(interactions, null, 2));
  const failures = report.filter((item) => item.documentWidth > item.viewport.width + 2 || item.overflow.length || !item.workCenterPresent);
  const interactionFailures = interactions.filter((item) => {
    if (item.interaction === "auth-mode-switch") return !item.initialSetup || !item.loginOptionVisible || !item.loginMode || !item.setupFieldsHidden || !item.setupAlternativeVisible || !item.setupRestored || !item.setupFieldsRequired;
    if (item.interaction === "configured-login") return !item.loginMode || !item.setupOptionHidden;
    if (item.interaction === "record-dialog") return !item.open || !item.insideViewport || !item.footerReachable || !item.essentialMode || !item.optionalContentHidden || (item.baseSelectSupported && item.selectAppearance !== "base-select");
    if (item.interaction === "select-picker") return !item.opened;
    if (item.interaction === "record-disclosure") return !item.expanded || !item.optionalContentVisible;
    if (item.interaction === "record-draft") return !item.restored || !item.noticeDismissed || !item.detailsExpanded;
    if (item.interaction === "command-palette") return !item.open || !item.insideViewport || !item.hasResults || !item.focused;
    if (item.interaction === "permissions-dialog") return !item.open || !item.insideViewport || !item.filteredToInventory || !item.dependenciesCleared || !item.touchTarget || !item.capabilities;
    if (item.interaction === "fiscal-setup-dialog") return !item.open || !item.insideViewport || !item.hasFiscalIdentity || !item.productionUnavailable || !item.touchTarget;
    return !item.expanded || !item.sidebarExposed || !item.scrollLocked;
  });
  console.log(JSON.stringify({ output: OUTPUT, screens: report.length, interactions: interactions.length, overflowFailures: failures, interactionFailures }, null, 2));
  process.exitCode = failures.length || interactionFailures.length ? 2 : 0;
} finally {
  cdp?.send("Browser.close").catch(() => {});
  await new Promise((resolveWait) => setTimeout(resolveWait, 300));
  cdp?.close();
  if (browser?.pid && process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(browser.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
  } else {
    browser?.kill();
  }
  browser?.unref();
  if (server.pid && process.platform === "win32") {
    spawnSync("taskkill", ["/PID", String(server.pid), "/T", "/F"], { stdio: "ignore", windowsHide: true });
  } else {
    server.kill();
  }
  server.unref();
  await new Promise((resolveWait) => setTimeout(resolveWait, 1800));
  await removeTemporary(temporary);
}
