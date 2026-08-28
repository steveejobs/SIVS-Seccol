(function initializeHR(global) {
  const hr = global.SIVSHR ||= {};
  const now = new Date();
  let period = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const scrollBehavior = global.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";

  const currency = (cents) => new Intl.NumberFormat("pt-BR", {
    style: "currency", currency: "BRL",
  }).format(Number(cents || 0) / 100);
  const minutes = (value) => {
    const total = Math.max(0, Number(value || 0));
    return `${Math.floor(total / 60)}h${String(total % 60).padStart(2, "0")}`;
  };
  const option = (item, selected = false) => `<option value="${item.id}" ${selected ? "selected" : ""}>${hr.escape(item.employee_name || item.title || item.name)}${item.registration ? ` · ${hr.escape(item.registration)}` : ""}</option>`;

  function employmentPanel(data) {
    const canManage = data.abilities.manage_hr_employments;
    const candidates = [
      ...data.employments.map((item) => ({ id: item.employee_record_id, title: item.employee_name })),
      ...data.candidates,
    ].map((item) => option(item)).join("");
    const rows = data.employments.length ? data.employments.map((item) => `
      <article class="hr-person-row">
        <span class="hr-avatar" aria-hidden="true">${hr.escape(item.employee_name.slice(0, 1))}</span>
        <div><strong>${hr.escape(item.employee_name)}</strong><small>${hr.escape(item.registration)} · ${hr.escape(item.job_title)} · ${hr.escape(item.branch_name)}</small></div>
        <div class="hr-person-money"><strong>${currency(item.monthly_salary_cents)}</strong><small>${item.weekly_minutes / 60}h semanais</small></div>
        ${canManage ? `<button type="button" class="secondary" data-hr-edit-employment="${item.id}">Editar</button>` : ""}
      </article>`).join("") : '<div class="hr-empty">Nenhum vínculo trabalhista cadastrado.</div>';
    return `<section class="panel hr-panel" data-hr-section="people">
      <div class="panel-head"><div><h3>Vínculos trabalhistas</h3><small class="muted">Matrícula única, salário, jornada, unidade e categoria eSocial.</small></div><span class="status">${data.employments.length}</span></div>
      <div class="panel-body">${rows}${canManage ? `<details class="hr-editor"><summary>Novo ou editar vínculo</summary>
        <form id="hrEmploymentForm" class="hr-form-grid">
          <input name="employmentId" type="hidden">
          <label class="field full"><span>Colaborador cadastrado *</span><select name="employeeRecordId" required><option value="">Selecione</option>${candidates}</select></label>
          <label class="field"><span>Unidade *</span><select name="branchId" required>${data.branches.map((item) => option(item)).join("")}</select></label>
          <label class="field"><span>Matrícula eSocial *</span><input name="registration" maxlength="30" required></label>
          <label class="field"><span>Admissão *</span><input name="admissionDate" type="date" required></label>
          <label class="field"><span>Situação</span><select name="status"><option value="ACTIVE">Ativo</option><option value="ON_LEAVE">Afastado</option><option value="TERMINATED">Desligado</option></select></label>
          <label class="field"><span>Tipo de vínculo</span><select name="employmentType"><option value="CLT">CLT</option><option value="APPRENTICE">Aprendiz</option><option value="TEMPORARY">Temporário</option></select></label>
          <label class="field"><span>Categoria eSocial *</span><input name="esocialCategory" value="101" maxlength="3" required></label>
          <label class="field"><span>Cargo *</span><input name="jobTitle" maxlength="120" required></label>
          <label class="field"><span>Setor *</span><input name="department" maxlength="120" required></label>
          <label class="field"><span>Salário mensal *</span><input name="monthlySalary" inputmode="decimal" placeholder="0,00" required></label>
          <label class="field"><span>Divisor mensal *</span><input name="monthlyDivisor" type="number" min="1" max="400" value="220" required></label>
          <label class="field"><span>Minutos semanais *</span><input name="weeklyMinutes" type="number" min="5" max="3600" step="5" value="2640" required><small class="field-help">44 horas = 2.640 minutos.</small></label>
          <label class="field"><span>Dependentes IRRF</span><input name="dependentsIr" type="number" min="0" max="99" value="0"></label>
          <label class="field"><span>Adicional de hora extra (%)</span><input name="overtimeRate" type="number" min="0" max="300" step="0.01" value="50"></label>
          <label class="field"><span>Código do horário</span><input name="scheduleCode" value="PADRAO" maxlength="30"></label>
          <label class="hr-check full"><input name="deductAbsence" type="checkbox" checked><span>Levar faltas e atrasos apurados para a prévia da folha</span></label>
          <div class="hr-form-actions full"><button type="button" class="secondary" data-hr-reset-employment>Limpar</button><button class="primary" type="submit">Salvar vínculo</button></div>
        </form><p id="hrEmploymentError" class="form-error hidden" role="alert"></p>
      </details>` : ""}</div></section>`;
  }

  function timePanel(data) {
    const canImport = data.abilities.import_time_clock;
    const canAdjust = data.abilities.adjust_time_clock;
    const rows = data.timesheets.map((item) => `<tr>
      <td><strong>${hr.escape(item.employeeName)}</strong></td><td>${minutes(item.totals.expectedMinutes)}</td>
      <td>${minutes(item.totals.workedMinutes)}</td><td>${minutes(item.totals.overtimeMinutes)}</td>
      <td>${minutes(item.totals.absenceMinutes)}</td><td><span class="status ${item.ready ? "concluído" : "pendente"}">${item.ready ? "Conferível" : `${item.totals.issueCount} pendência(s)`}</span></td>
    </tr>`).join("");
    const employmentOptions = data.employments.map((item) => option(item)).join("");
    return `<section class="panel hr-panel" data-hr-section="time">
      <div class="panel-head"><div><h3>Ponto eletrônico</h3><small class="muted">AFD 004 oficial ou CSV do relógio; fatos originais nunca são alterados.</small></div><span class="status">${data.imports.length} lote(s)</span></div>
      <div class="panel-body">
        <div class="table-wrap borderless"><table class="data-table"><thead><tr><th>Colaborador</th><th>Previsto</th><th>Trabalhado</th><th>Extras</th><th>Faltas</th><th>Conferência</th></tr></thead><tbody>${rows || '<tr><td colspan="6">Sem vínculos para apurar.</td></tr>'}</tbody></table></div>
        <div class="hr-action-grid">
          ${canImport ? `<form id="hrTimeImportForm" class="hr-compact-form"><h4>Importar relógio</h4><label class="field"><span>Unidade *</span><select name="branchId" required>${data.branches.map((item) => option(item)).join("")}</select></label><label class="field"><span>Formato</span><select name="format"><option value="AUTO">Detectar automaticamente</option><option value="AFD">AFD 004</option><option value="CSV">CSV</option></select></label><label class="field"><span>Tecnologia do REP *</span><select name="repType" required><option value="1">REP-C (equipamento)</option><option value="2">REP-A (alternativo)</option><option value="3">REP-P (programa)</option></select></label><label class="field full"><span>Arquivo AFD/CSV *</span><input name="file" type="file" accept=".txt,.afd,.csv,text/plain,text/csv" required></label><button class="primary" type="submit">Verificar e importar</button><p id="hrTimeImportError" class="form-error hidden full" role="alert"></p></form>` : ""}
          ${canAdjust ? `<form id="hrTimeAdjustmentForm" class="hr-compact-form"><h4>Ajuste justificado</h4><label class="field full"><span>Vínculo *</span><select name="employmentId" required><option value="">Selecione</option>${employmentOptions}</select></label><label class="field"><span>Data e hora *</span><input name="occurredAt" type="datetime-local" required></label><label class="field full"><span>Justificativa *</span><textarea name="reason" minlength="10" maxlength="500" required></textarea></label><button class="secondary" type="submit">Incluir marcação auditada</button><p id="hrTimeAdjustmentError" class="form-error hidden full" role="alert"></p></form>` : ""}
        </div>
        <div class="hr-export-actions">${data.abilities.export_hr ? `<a class="secondary" href="/api/hr/time/export?period=${data.period}&format=csv">Exportar horas CSV</a><a class="secondary" href="/api/hr/time/export?period=${data.period}&format=aej">AEJ 002 para validação</a>` : ""}<small>O AEJ ainda requer P7S do desenvolvedor do PTRP para uso fiscal. AFD importado: ${data.imports.reduce((sum, item) => sum + item.imported_count, 0)} marcações · não vinculadas: ${data.imports.reduce((sum, item) => sum + item.unmatched_count, 0)}</small></div>
      </div></section>`;
  }

  function payrollPanel(data) {
    const run = data.payroll[0];
    const employmentOptions = data.employments.map((item) => option(item)).join("");
    const items = run?.items?.map((item) => `<article class="hr-payroll-person"><div><strong>${hr.escape(item.employee.name)}</strong><small>${hr.escape(item.employee.registration)} · ${minutes(item.timesheet.totals.overtimeMinutes)} extras</small></div><span><small>Proventos</small><strong>${currency(item.gross_cents)}</strong></span><span><small>Descontos</small><strong>${currency(item.deductions_cents)}</strong></span><span><small>Líquido</small><strong>${currency(item.net_cents)}</strong></span><a class="secondary" href="/api/hr/payroll/items/${item.id}/payslip" target="_blank" rel="noopener">Holerite</a></article>`).join("") || '<div class="hr-empty">Calcule a prévia para formar a folha desta competência.</div>';
    return `<section class="panel hr-panel" data-hr-section="payroll">
      <div class="panel-head"><div><h3>Folha mensal</h3><small class="muted">INSS e IRRF progressivos 2026, FGTS, horas extras, faltas e eventos manuais.</small></div><span class="status ${run?.status === "CLOSED" ? "concluído" : "pendente"}">${run?.status === "CLOSED" ? "Fechada" : "Prévia"}</span></div>
      <div class="panel-body">
        ${run ? `<div class="hr-payroll-totals"><span><small>Bruto</small><strong>${currency(run.gross_cents)}</strong></span><span><small>Descontos</small><strong>${currency(run.deductions_cents)}</strong></span><span><small>Líquido</small><strong>${currency(run.net_cents)}</strong></span><span><small>FGTS</small><strong>${currency(run.employer_fgts_cents)}</strong></span></div>` : ""}
        ${items}${run && data.abilities.export_hr ? `<div class="hr-export-actions"><a class="secondary" href="/api/hr/payroll/export?period=${data.period}">Exportar folha para conferência contábil</a><small>CSV auditado com matrícula, bases, INSS, IRRF, FGTS e líquido.</small></div>` : ""}
        ${data.abilities.process_payroll && run?.status !== "CLOSED" ? `<div class="hr-action-grid"><form id="hrPayrollEventForm" class="hr-compact-form"><h4>Evento avulso</h4><label class="field full"><span>Vínculo *</span><select name="employmentId" required><option value="">Selecione</option>${employmentOptions}</select></label><label class="field"><span>Código *</span><input name="code" maxlength="20" required placeholder="BONUS"></label><label class="field"><span>Tipo *</span><select name="kind"><option value="EARNING">Provento</option><option value="DEDUCTION">Desconto</option></select></label><label class="field full"><span>Descrição *</span><input name="description" maxlength="120" required></label><label class="field"><span>Valor *</span><input name="amount" inputmode="decimal" required></label><label class="hr-check"><input name="incidenceInss" type="checkbox" checked><span>Incide INSS/IRRF</span></label><label class="hr-check"><input name="incidenceFgts" type="checkbox" checked><span>Incide FGTS</span></label><label class="field full"><span>Justificativa *</span><textarea name="reason" minlength="10" maxlength="500" required></textarea></label><button class="secondary" type="submit">Adicionar evento</button><p id="hrPayrollEventError" class="form-error hidden full" role="alert"></p></form><div class="hr-payroll-actions"><button class="primary" type="button" id="hrCalculatePayroll">Calcular/recalcular prévia</button><small>A competência só fecha se todas as jornadas estiverem consistentes.</small>${run && data.abilities.close_payroll ? `<form id="hrClosePayrollForm"><label class="field"><span>Justificativa do fechamento *</span><textarea name="reason" minlength="10" required></textarea></label><button class="primary" type="submit">Fechar folha revisionada</button></form>` : ""}</div></div>` : ""}
        <p class="compliance-note compact"><strong>Parâmetros ${hr.escape(data.legalTable.version)}:</strong> ${hr.escape(data.legalTable.sources.inss)} · ${hr.escape(data.legalTable.sources.irrf)}. O SIVS bloqueia outras competências até existir tabela versionada.</p>
      </div></section>`;
  }

  function render(data) {
    const active = data.employments.filter((item) => item.status === "ACTIVE").length;
    const issueCount = data.timesheets.reduce((sum, item) => sum + Number(item.totals.issueCount || 0), 0);
    const latest = data.payroll[0];
    return `<section class="hr-hero"><div><p class="eyebrow gold">CENTRAL DE RH</p><h2>Pessoas, jornada e folha em uma trilha única.</h2><p>O relógio entra como evidência imutável, a jornada vira apuração conferível e a folha fecha somente com parâmetros legais versionados.</p></div><label class="field hr-period"><span>Competência</span><input id="hrPeriod" type="month" value="${data.period}"></label></section>
      <section class="hr-summary"><article><span>Vínculos ativos</span><strong>${active}</strong></article><article><span>Marcações importadas</span><strong>${data.imports.reduce((sum, item) => sum + item.imported_count, 0)}</strong></article><article class="${issueCount ? "warning" : ""}"><span>Pendências de ponto</span><strong>${issueCount}</strong></article><article><span>Folha</span><strong>${latest?.status === "CLOSED" ? "Fechada" : latest ? "Prévia" : "Não calculada"}</strong></article></section>
      <nav class="hr-jump" aria-label="Áreas do RH"><a href="#" data-hr-jump="people">Vínculos</a><a href="#" data-hr-jump="time">Ponto e horas</a><a href="#" data-hr-jump="payroll">Folha</a></nav>
      ${employmentPanel(data)}${timePanel(data)}${payrollPanel(data)}`;
  }

  function formError(form, error) {
    const output = form.querySelector(".form-error");
    if (output) { output.textContent = error.message; output.classList.remove("hidden"); }
  }
  async function submit(form, callback) {
    const button = form.querySelector('[type="submit"]');
    form.querySelector(".form-error")?.classList.add("hidden");
    if (button) button.disabled = true;
    try { await callback(new FormData(form)); }
    catch (error) { formError(form, error); }
    finally { if (button) button.disabled = false; }
  }
  function base64(arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer); let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 0x8000) binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    return btoa(binary);
  }
  function timeValue(totalMinutes) {
    const value = Math.max(0, Math.min(23 * 60 + 59, totalMinutes));
    return `${String(Math.floor(value / 60)).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
  }

  function bind(data) {
    document.querySelector("#hrPeriod")?.addEventListener("change", (event) => { period = event.target.value; hr.load(hr.context); });
    document.querySelectorAll("[data-hr-jump]").forEach((link) => link.addEventListener("click", (event) => {
      event.preventDefault(); document.querySelector(`[data-hr-section="${link.dataset.hrJump}"]`)?.scrollIntoView({ behavior: scrollBehavior, block: "start" });
    }));
    const employmentForm = document.querySelector("#hrEmploymentForm");
    document.querySelector("[data-hr-reset-employment]")?.addEventListener("click", () => { employmentForm.reset(); employmentForm.elements.employmentId.value = ""; });
    document.querySelectorAll("[data-hr-edit-employment]").forEach((button) => button.addEventListener("click", () => {
      const item = data.employments.find((row) => row.id === Number(button.dataset.hrEditEmployment)); if (!item) return;
      const values = { employmentId: item.id, employeeRecordId: item.employee_record_id, branchId: item.branch_id, registration: item.registration, admissionDate: item.admission_date, status: item.status, employmentType: item.employment_type, esocialCategory: item.esocial_category, jobTitle: item.job_title, department: item.department, monthlySalary: (item.monthly_salary_cents / 100).toFixed(2).replace(".", ","), monthlyDivisor: item.monthly_divisor, weeklyMinutes: item.weekly_minutes, dependentsIr: item.dependents_ir, overtimeRate: item.overtime_rate_bp / 100, scheduleCode: item.schedule_code };
      Object.entries(values).forEach(([name, value]) => { if (employmentForm.elements[name]) employmentForm.elements[name].value = value; });
      employmentForm.elements.deductAbsence.checked = Boolean(item.deduct_absence); employmentForm.closest("details").open = true; employmentForm.scrollIntoView({ behavior: scrollBehavior });
    }));
    employmentForm?.addEventListener("submit", (event) => { event.preventDefault(); submit(employmentForm, async (values) => {
      const weekly = Number(values.get("weeklyMinutes")); if (weekly % 5) throw new Error("Os minutos semanais precisam ser divisíveis por 5 nesta jornada padrão.");
      const daily = weekly / 5; const pairs = daily > 240 ? [["08:00", "12:00"], ["13:00", timeValue(13 * 60 + daily - 240)]] : [["08:00", timeValue(8 * 60 + daily)]];
      const schedule = { "1": daily, "2": daily, "3": daily, "4": daily, "5": daily, "6": 0, "7": 0, pairs };
      const id = Number(values.get("employmentId") || 0); await hr.api(id ? `/api/hr/employments/${id}` : "/api/hr/employments", { method: id ? "PUT" : "POST", body: JSON.stringify({ employeeRecordId: Number(values.get("employeeRecordId")), branchId: Number(values.get("branchId")), registration: values.get("registration"), admissionDate: values.get("admissionDate"), status: values.get("status"), employmentType: values.get("employmentType"), esocialCategory: values.get("esocialCategory"), jobTitle: values.get("jobTitle"), department: values.get("department"), monthlySalary: values.get("monthlySalary"), monthlyDivisor: Number(values.get("monthlyDivisor")), weeklyMinutes: weekly, dependentsIr: Number(values.get("dependentsIr")), overtimeRateBp: Math.round(Number(values.get("overtimeRate")) * 100), deductAbsence: values.get("deductAbsence") === "on", scheduleCode: values.get("scheduleCode"), schedule }) }); hr.toast("Vínculo trabalhista salvo e auditado."); await hr.load(hr.context);
    }); });
    const importForm = document.querySelector("#hrTimeImportForm");
    importForm?.addEventListener("submit", (event) => { event.preventDefault(); submit(importForm, async (values) => { const file = values.get("file"); if (!(file instanceof File) || !file.size || file.size > 8 * 1024 * 1024) throw new Error("Selecione AFD ou CSV com até 8 MB."); const result = await hr.api("/api/hr/time/import", { method: "POST", body: JSON.stringify({ branchId: Number(values.get("branchId")), format: values.get("format"), repType: Number(values.get("repType")), filename: file.name, contentBase64: base64(await file.arrayBuffer()) }) }); hr.toast(`${result.imported} marcações importadas; ${result.unmatched} sem vínculo.`); await hr.load(hr.context); }); });
    const adjustmentForm = document.querySelector("#hrTimeAdjustmentForm");
    adjustmentForm?.addEventListener("submit", (event) => { event.preventDefault(); submit(adjustmentForm, async (values) => { const local = values.get("occurredAt"); const offset = -new Date(local).getTimezoneOffset(); const sign = offset >= 0 ? "+" : "-"; const absolute = Math.abs(offset); const occurredAt = `${local}:00${sign}${String(Math.floor(absolute / 60)).padStart(2, "0")}:${String(absolute % 60).padStart(2, "0")}`; await hr.api("/api/hr/time/adjustments", { method: "POST", body: JSON.stringify({ employmentId: Number(values.get("employmentId")), occurredAt, reason: values.get("reason") }) }); hr.toast("Marcação complementar incluída sem alterar o relógio."); await hr.load(hr.context); }); });
    const eventForm = document.querySelector("#hrPayrollEventForm");
    eventForm?.addEventListener("submit", (event) => { event.preventDefault(); submit(eventForm, async (values) => { const socialIncidence = values.get("incidenceInss") === "on"; await hr.api("/api/hr/payroll/events", { method: "POST", body: JSON.stringify({ period: data.period, employmentId: Number(values.get("employmentId")), code: values.get("code"), kind: values.get("kind"), description: values.get("description"), amount: values.get("amount"), incidenceInss: socialIncidence, incidenceIrrf: socialIncidence, incidenceFgts: values.get("incidenceFgts") === "on", reason: values.get("reason") }) }); hr.toast("Evento adicionado; recalcule a prévia."); await hr.load(hr.context); }); });
    document.querySelector("#hrCalculatePayroll")?.addEventListener("click", async (event) => { event.currentTarget.disabled = true; try { const result = await hr.api("/api/hr/payroll/preview", { method: "POST", body: JSON.stringify({ period: data.period }) }); hr.toast(result.readyToClose ? "Prévia calculada e pronta para conferência." : "Prévia calculada com pendências de ponto."); await hr.load(hr.context); } catch (error) { hr.toast(error.message); } finally { event.currentTarget.disabled = false; } });
    const closeForm = document.querySelector("#hrClosePayrollForm");
    closeForm?.addEventListener("submit", (event) => { event.preventDefault(); submit(closeForm, async (values) => { await hr.api("/api/hr/payroll/close", { method: "POST", body: JSON.stringify({ period: data.period, revision: data.payroll[0].revision, reason: values.get("reason") }) }); hr.toast("Folha fechada e tornada imutável."); await hr.load(hr.context); }); });
  }

  hr.load = async function load(context) {
    hr.context = context; hr.api = context.api; hr.escape = context.escapeHTML; hr.toast = context.toast;
    context.content.innerHTML = '<div class="empty">Conferindo vínculos, relógio e folha…</div>';
    const data = await context.api(`/api/hr/workspace?period=${encodeURIComponent(period)}`);
    period = data.period; context.content.innerHTML = render(data); bind(data);
  };
})(window);
