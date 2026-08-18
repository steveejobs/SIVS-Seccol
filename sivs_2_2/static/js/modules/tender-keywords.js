(function createTenderKeywords(global) {
  const MAX_KEYWORDS = 80;

  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
  }

  function splitKeywords(value) {
    return String(value || "").split(/[\n,;\t]+/).map((item) => item.trim().replace(/^['"]|['"]$/g, "")).filter(Boolean);
  }

  function escapeCsv(value) {
    const text = String(value || "");
    return /[";,\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  }

  function mount({ root, initial = [], api, toast, companyName = "SECCOL" }) {
    if (!root) return null;
    const hidden = root.querySelector("#tenderKeywords");
    const input = root.querySelector("#tenderKeywordInput");
    const chips = root.querySelector("#tenderKeywordChips");
    const count = root.querySelector("#tenderKeywordCount");
    const report = root.querySelector("#tenderKeywordReport");
    const file = root.querySelector("#tenderKeywordFile");
    let values = [];
    let metadata = new Map();

    const announce = (message, kind = "") => {
      report.textContent = message;
      report.className = `keyword-report${kind ? ` ${kind}` : ""}`;
    };

    const sync = () => {
      hidden.value = values.join(", ");
      count.textContent = `${values.length}/${MAX_KEYWORDS} palavras-chave`;
      chips.querySelectorAll(".keyword-chip").forEach((chip) => chip.remove());
      values.forEach((keyword, index) => {
        const chip = document.createElement("span");
        chip.className = "keyword-chip";
        const details = metadata.get(normalize(keyword));
        if (details?.category) chip.title = `Categoria da planilha: ${details.category}`;
        const label = document.createElement("span");
        label.textContent = keyword;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.setAttribute("aria-label", `Remover ${keyword}`);
        remove.textContent = "×";
        remove.onclick = () => { values.splice(index, 1); sync(); input.focus(); };
        chip.append(label, remove);
        chips.insertBefore(chip, input);
      });
    };

    const add = (incoming, details = []) => {
      const seen = new Set(values.map(normalize));
      let added = 0;
      let duplicates = 0;
      let excess = 0;
      incoming.forEach((raw, index) => {
        const keyword = String(raw || "").trim().replace(/^['"]|['"]$/g, "").slice(0, 180);
        const key = normalize(keyword);
        if (key.length < 3) return;
        if (seen.has(key)) { duplicates += 1; return; }
        if (values.length >= MAX_KEYWORDS) { excess += 1; return; }
        values.push(keyword);
        seen.add(key);
        const detail = details[index];
        if (detail) metadata.set(key, detail);
        added += 1;
      });
      sync();
      return { added, duplicates, excess };
    };

    const commitInput = () => {
      const result = add(splitKeywords(input.value));
      input.value = "";
      if (result.excess) announce(`Limite de ${MAX_KEYWORDS} termos atingido. ${result.excess} não foi incluído.`, "warning");
    };

    input.addEventListener("keydown", (event) => {
      if ((event.key === "Enter" || event.key === "," || event.key === ";") && !event.isComposing) {
        event.preventDefault();
        commitInput();
      } else if (event.key === "Backspace" && !input.value && values.length) {
        values.pop();
        sync();
      }
    });
    input.addEventListener("blur", commitInput);
    input.addEventListener("paste", (event) => {
      const text = event.clipboardData?.getData("text") || "";
      if (!/[\n,;\t]/.test(text)) return;
      event.preventDefault();
      const result = add(splitKeywords(text));
      announce(`${result.added} termo(s) colado(s) · ${result.duplicates} duplicado(s) ignorado(s).`, "success");
    });
    chips.addEventListener("click", (event) => {
      if (event.target === chips) input.focus();
    });

    root.querySelector("#importTenderKeywords").onclick = () => file.click();
    root.querySelector("#clearTenderKeywords").onclick = () => {
      values = [];
      metadata = new Map();
      sync();
      announce("Lista limpa. Adicione termos ou importe uma planilha.");
      input.focus();
    };
    root.querySelector("#downloadTenderKeywordTemplate").onclick = () => {
      const rows = ["palavra_chave;categoria;ativa", ...values.map((keyword) => {
        const detail = metadata.get(normalize(keyword));
        return `${escapeCsv(keyword)};${escapeCsv(detail?.category || "Geral")};sim`;
      })];
      const blob = new Blob(["\ufeff" + rows.join("\r\n")], { type: "text/csv;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `palavras-chave-${normalize(companyName).replace(/[^a-z0-9]+/g, "-") || "seccol"}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    };
    file.onchange = async () => {
      const selected = file.files?.[0];
      file.value = "";
      if (!selected) return;
      if (selected.size > 2 * 1024 * 1024) {
        announce("A planilha deve possuir no máximo 2 MB.", "warning");
        return;
      }
      announce(`Lendo ${selected.name}…`);
      try {
        const bytes = new Uint8Array(await selected.arrayBuffer());
        let binary = "";
        for (let offset = 0; offset < bytes.length; offset += 0x8000) {
          binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
        }
        const response = await api("/api/tenders/keywords/import", {
          method: "POST",
          body: JSON.stringify({ filename: selected.name, content: btoa(binary) }),
        });
        const result = add(response.keywords, response.entries);
        announce(`${result.added} termo(s) importado(s) de ${response.sheet || selected.name} · ${response.duplicates + result.duplicates} duplicado(s) e ${response.ignored} linha(s) ignorada(s).`, "success");
        toast?.("Palavras-chave importadas da planilha.");
      } catch (failure) {
        announce(failure.message || "Não foi possível importar a planilha.", "warning");
      }
    };

    add(Array.isArray(initial) ? initial : splitKeywords(initial));
    return {
      getKeywords: () => [...values],
      setKeywords: (next) => { values = []; metadata = new Map(); add(next); },
      focus: () => input.focus(),
    };
  }

  global.SIVSTenderKeywords = { mount, splitKeywords };
})(window);
