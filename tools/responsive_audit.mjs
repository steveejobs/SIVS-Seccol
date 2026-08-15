#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..");
const outputArgument = process.argv.slice(2).find((argument) => !argument.startsWith("--"));
const OUTPUT = resolve(outputArgument || join(ROOT, ".artifacts", "responsive-audit"));
const SERVER_PORT = 18948;
const DEBUG_PORT = 18949;
const BASE_URL = `http://127.0.0.1:${SERVER_PORT}`;
const QUICK = process.argv.includes("--quick");
const CAPTURE_SCREENS = new Set(["dashboard", "portfolio", "clientes", "editais", "mobile", "fiscal", "normas_tecnicas", "settings"]);
const ALL_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 1000, mobile: false },
  { name: "tablet", width: 834, height: 1112, mobile: false },
  { name: "mobile", width: 390, height: 844, mobile: true },
  { name: "mobile-360", width: 360, height: 800, mobile: true },
];
const VIEWPORTS = QUICK ? ALL_VIEWPORTS.filter(({ name }) => name === "mobile") : ALL_VIEWPORTS;

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
      const { resolveCall, rejectCall } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) rejectCall(new Error(message.error.message));
      else resolveCall(message.result || {});
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolveCall, rejectCall) => {
      this.pending.set(id, { resolveCall, rejectCall });
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
const temporary = join(OUTPUT, ".runtime");
rmSync(temporary, { recursive: true, force: true, maxRetries: 4, retryDelay: 250 });
mkdirSync(temporary, { recursive: true });
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
  await cdp.evaluate(`(async () => {
    const response = await fetch('/api/setup', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({company:'Auditoria Responsiva', name:'Auditor UI', email:'audit@sivs.local', password:'AuditSivs#2026'})
    });
    if (!response.ok) throw new Error(await response.text());
    location.reload();
  })()`);
  await waitUntil(cdp, "document.querySelector('#app:not(.hidden)') !== null", 120);
  const screens = QUICK ? ["clientes"] : await cdp.evaluate("[...new Set([...document.querySelectorAll('[data-nav]')].map((element) => element.dataset.nav))]");

  const report = [];
  const interactions = [];
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
        const allowedOverflow = (element) => element.closest('.table-wrap,.kanban-wrap,.tender-results,.legacy-alert-panel>div');
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
    await new Promise((resolveWait) => setTimeout(resolveWait, 350));
    const dialog = await cdp.evaluate(`(() => {
      const element = document.querySelector('#recordDialog');
      const rect = element.getBoundingClientRect();
      const footer = element.querySelector('.record-actions').getBoundingClientRect();
      const computed = getComputedStyle(element);
      return {
        device:${JSON.stringify(viewport.name)}, interaction:'record-dialog', open:element.open,
        insideViewport:rect.left >= -1 && rect.right <= innerWidth + 1 && rect.top >= -1 && rect.bottom <= innerHeight + 1,
        footerReachable:footer.top < rect.bottom && footer.bottom <= rect.bottom + 1,
        bounds:{left:Math.round(rect.left),top:Math.round(rect.top),right:Math.round(rect.right),bottom:Math.round(rect.bottom),width:Math.round(rect.width),height:Math.round(rect.height)},
        computed:{position:computed.position,top:computed.top,bottom:computed.bottom,marginTop:computed.marginTop,height:computed.height,maxHeight:computed.maxHeight,transform:computed.transform},
        visualViewport:{height:Math.round(visualViewport.height),offsetTop:Math.round(visualViewport.offsetTop)},
      };
    })()`);
    const dialogImage = await cdp.send("Page.captureScreenshot", { format: "png", fromSurface: true });
    writeFileSync(join(OUTPUT, `${viewport.name}-record-dialog.png`), Buffer.from(dialogImage.data, "base64"));
    interactions.push(dialog);
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
      noticeDismissed:document.querySelector('#draftNotice').classList.contains('hidden')
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
  writeFileSync(join(OUTPUT, "report.json"), JSON.stringify(report, null, 2));
  writeFileSync(join(OUTPUT, "interactions.json"), JSON.stringify(interactions, null, 2));
  const failures = report.filter((item) => item.documentWidth > item.viewport.width + 2 || item.overflow.length || !item.workCenterPresent);
  const interactionFailures = interactions.filter((item) => {
    if (item.interaction === "record-dialog") return !item.open || !item.insideViewport || !item.footerReachable;
    if (item.interaction === "record-draft") return !item.restored || !item.noticeDismissed;
    if (item.interaction === "command-palette") return !item.open || !item.insideViewport || !item.hasResults || !item.focused;
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
  server.kill();
  await new Promise((resolveWait) => setTimeout(resolveWait, 1800));
  try {
    rmSync(temporary, { recursive: true, force: true, maxRetries: 4, retryDelay: 250 });
  } catch (error) {
    console.warn(`Runtime será limpo no início da próxima auditoria: ${temporary} (${error.code})`);
  }
}
