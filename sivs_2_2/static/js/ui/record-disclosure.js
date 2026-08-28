(function createRecordDisclosure(global) {
  "use strict";

  const ui = global.SIVSUI;
  let expanded = true;
  let editing = false;
  let listenersReady = false;
  let detailsReleased = false;

  const elements = () => ({
    form: document.getElementById("recordForm"),
    toggle: document.getElementById("recordOptionalToggle"),
    toggleText: document.getElementById("recordOptionalToggleText"),
    title: document.getElementById("recordDisclosureTitle"),
    hint: document.getElementById("recordDisclosureHint"),
  });

  function markStaticOptionalContent() {
    const { form } = elements();
    ["responsibleField", "contactField", "recordGovernance"]
      .forEach((id) => document.getElementById(id)?.classList.add(
        id === "recordGovernance" ? "record-optional-section" : "record-optional",
      ));
    [form.assuntos_adicionais, form.tipo_relacao, form.registro_relacionado]
      .filter(Boolean)
      .forEach((control) => control.closest(".field")?.classList.add("record-optional"));
    document.getElementById("relationshipList")?.classList.add("record-optional");
  }

  function apply(nextExpanded, announce = true) {
    const { form, toggle, toggleText, title, hint } = elements();
    expanded = Boolean(nextExpanded);
    form.classList.toggle("is-essential-mode", !expanded);
    form.classList.toggle("is-record-editing", editing);
    toggle.setAttribute("aria-expanded", String(expanded));
    toggleText.textContent = expanded ? "Ocultar detalhes" : "Ver detalhes";
    toggle.querySelector("b").textContent = expanded ? "\u2212" : "+";
    title.textContent = expanded
      ? "Detalhes complementares"
      : "Dados obrigatórios";
    hint.textContent = expanded
      ? (editing ? "Revise os dados obrigatórios e complemente o que for necessário." : "Campos complementares disponíveis para revisão ou preenchimento.")
      : "Preencha os campos obrigatórios para liberar os detalhes automaticamente.";
    if (announce) ui.announce?.(expanded ? "Campos complementares exibidos" : "Somente campos essenciais exibidos");
  }

  ui.recordDisclosure = Object.freeze({
    configure({ isEditing = false } = {}) {
      editing = Boolean(isEditing);
      detailsReleased = editing;
      markStaticOptionalContent();
      if (!listenersReady) {
        listenersReady = true;
        elements().toggle.onclick = () => {
          detailsReleased = true;
          apply(!expanded);
        };
      }
      apply(editing, false);
    },
    expand() { apply(true); },
    ensureVisible(control) {
      if (!expanded && control?.closest(".record-optional,.record-optional-group,.record-optional-section")) {
        apply(true);
      }
    },
    setPending(count) {
      if (expanded) return;
      const pending = Number(count || 0);
      if (pending === 0) {
        if (!detailsReleased) {
          detailsReleased = true;
          apply(true);
        } else {
          elements().hint.textContent = "Campos obrigatórios concluídos. Os detalhes permanecem recolhidos.";
        }
        return;
      }
      elements().hint.textContent = pending
        ? `${pending} campo${pending === 1 ? "" : "s"} obrigat\u00f3rio${pending === 1 ? "" : "s"} ainda precisa${pending === 1 ? "" : "m"} de aten\u00e7\u00e3o.`
        : "O essencial est\u00e1 completo. Voc\u00ea j\u00e1 pode salvar ou adicionar detalhes.";
    },
    isExpanded() { return expanded; },
  });
})(window);
