import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
TOKENS = (ROOT / "static" / "theme" / "tokens.css").read_text(encoding="utf-8")
FOUNDATIONS = (ROOT / "static" / "theme" / "foundations.css").read_text(encoding="utf-8")
RESPONSIVE = (ROOT / "static" / "theme" / "responsive.css").read_text(encoding="utf-8")
COMPONENTS = (ROOT / "static" / "theme" / "components.css").read_text(encoding="utf-8")
MOTION = (ROOT / "static" / "theme" / "motion.css").read_text(encoding="utf-8")
PRODUCTIVITY = (ROOT / "static" / "theme" / "productivity.css").read_text(encoding="utf-8")
EXPERIENCE = (ROOT / "static" / "js" / "ui" / "experience.js").read_text(encoding="utf-8")
MOTION_JS = (ROOT / "static" / "js" / "ui" / "motion.js").read_text(encoding="utf-8")
DIALOGS_JS = (ROOT / "static" / "js" / "ui" / "dialogs.js").read_text(encoding="utf-8")
NAVIGATION_JS = (ROOT / "static" / "js" / "ui" / "navigation.js").read_text(encoding="utf-8")
STATE_JS = (ROOT / "static" / "js" / "core" / "state.js").read_text(encoding="utf-8")
FORMATTERS_JS = (ROOT / "static" / "js" / "core" / "formatters.js").read_text(encoding="utf-8")
HTTP_JS = (ROOT / "static" / "js" / "core" / "http.js").read_text(encoding="utf-8")
PREFERENCES_JS = (ROOT / "static" / "js" / "core" / "preferences.js").read_text(encoding="utf-8")
DRAFTS_JS = (ROOT / "static" / "js" / "core" / "drafts.js").read_text(encoding="utf-8")
COMMAND_JS = (ROOT / "static" / "js" / "ui" / "command-palette.js").read_text(encoding="utf-8")
RECORD_DISCLOSURE_JS = (ROOT / "static" / "js" / "ui" / "record-disclosure.js").read_text(encoding="utf-8")
INSTALL_APP_JS = (ROOT / "static" / "js" / "ui" / "install-app.js").read_text(encoding="utf-8")
SYSTEM_DATE_JS = (ROOT / "static" / "js" / "ui" / "system-date.js").read_text(encoding="utf-8")
SERVICE_WORKER = (ROOT / "static" / "service-worker.js").read_text(encoding="utf-8")
MANIFEST = (ROOT / "static" / "manifest.json").read_text(encoding="utf-8")


class FrontendContractTests(unittest.TestCase):
    def test_every_schema_has_a_specialized_registration_profile(self):
        schema_block = APP.split("const schemas = {", 1)[1].split("\n};\n\nconst formDomains", 1)[0]
        profile_block = APP.split("const registrationProfiles = {", 1)[1].split(
            "\n};\n\nfunction getRecordProfile", 1
        )[0]
        schemas = set(re.findall(r"^  ([a-z_]+): \[", schema_block, re.MULTILINE))
        profiles = set(re.findall(r"^  ([a-z_]+): P\(", profile_block, re.MULTILINE))
        self.assertEqual(46, len(schemas))
        self.assertEqual(schemas, profiles)

    def test_specialized_form_keeps_subject_and_governance_contract(self):
        required_ids = {
            "recordProfileHero", "recordProgressValue", "recordIdentification",
            "recordSpecifics", "recordRelationships", "recordGovernance",
            "dynamicFields", "relationshipList", "recordResources",
        }
        ids = set(re.findall(r'id="([A-Za-z][A-Za-z0-9_-]+)"', INDEX))
        self.assertTrue(required_ids.issubset(ids))
        self.assertIn('name="assunto" required', INDEX)
        self.assertIn("function validateSpecializedRecord", APP)
        self.assertIn("function updateRecordCompleteness", APP)

    def test_new_record_uses_the_hidden_id_control_not_the_form_id_property(self):
        self.assertIn("form.elements.id.value", APP)
        self.assertNotIn("form.id.value", APP)
        self.assertIn('id="newButton" class="primary" type="button"', INDEX)
        self.assertIn("self.skipWaiting()", SERVICE_WORKER)
        self.assertIn("self.clients.claim()", SERVICE_WORKER)

    def test_static_html_has_no_duplicate_ids(self):
        ids = re.findall(r'id="([A-Za-z][A-Za-z0-9_-]+)"', INDEX)
        self.assertEqual(len(ids), len(set(ids)))

    def test_theme_and_experience_layers_are_loaded_in_order(self):
        assets = [
            "/theme/tokens.css", "/styles.css", "/theme/foundations.css",
            "/theme/responsive.css", "/theme/components.css", "/theme/productivity.css", "/theme/motion.css",
            "/js/core/platform.js", "/js/core/state.js", "/js/core/formatters.js", "/js/core/http.js",
            "/js/core/preferences.js", "/js/core/drafts.js", "/js/ui/motion.js",
            "/js/ui/dialogs.js", "/js/ui/pointer.js", "/js/ui/navigation.js",
            "/js/ui/command-palette.js", "/js/ui/record-disclosure.js", "/js/ui/experience.js", "/app.js",
        ]
        positions = [INDEX.index(asset) for asset in assets]
        self.assertEqual(positions, sorted(positions))
        for asset in assets:
            self.assertIn(asset, SERVICE_WORKER)
        self.assertIn("--color-seccol", TOKENS)
        self.assertIn(":focus-visible", FOUNDATIONS)
        self.assertIn("prefers-reduced-motion: reduce", MOTION)
        self.assertNotIn("--motion-duration-", MOTION)
        self.assertNotIn("--motion-ease-", MOTION)
        theme = "\n".join((TOKENS, FOUNDATIONS, RESPONSIVE, COMPONENTS, PRODUCTIVITY, MOTION))
        defined_tokens = set(re.findall(r"(--[a-z0-9-]+)\s*:", theme))
        used_tokens = set(re.findall(r"var\((--[a-z0-9-]+)", theme))
        self.assertFalse(used_tokens - defined_tokens)

    def test_navigation_and_motion_keep_accessibility_contract(self):
        self.assertIn('class="skip-link"', INDEX)
        self.assertIn('id="pageStatus"', INDEX)
        self.assertIn('id="sidebarScrim"', INDEX)
        self.assertIn('aria-controls="sidebar"', INDEX)
        self.assertIn("transitionOut", MOTION_JS)
        self.assertIn("transitionIn", MOTION_JS)
        self.assertIn("closeDialog", DIALOGS_JS)
        self.assertIn("setNavigation", NAVIGATION_JS)
        self.assertIn("compactNavigation", NAVIGATION_JS)
        self.assertIn("sidebar.inert", NAVIGATION_JS)
        self.assertIn("@media (max-width: 900px)", RESPONSIVE)
        self.assertIn("min-height: 44px", RESPONSIVE)
        self.assertIn("100dvh", RESPONSIVE)
        self.assertIn("MutationObserver", EXPERIENCE)
        self.assertIn("await ui.transitionOut?.(content)", APP)
        self.assertIn('document.body.classList.add("is-authenticated")', APP)
        self.assertIn("body:not(.is-authenticated) .skip-link", FOUNDATIONS)

    def test_core_state_formatters_and_http_are_extracted(self):
        self.assertIn("global.SIVSState", STATE_JS)
        self.assertIn("core.escapeHTML", FORMATTERS_JS)
        self.assertIn("core.safeExternalURL", FORMATTERS_JS)
        self.assertIn("core.documentBR", FORMATTERS_JS)
        self.assertIn('documentField.inputMode = "numeric"', APP)
        self.assertIn('documentField.maxLength = 18', APP)
        self.assertIn('payload.documento = String(payload.documento || "").replace(/\\D/g, "")', APP)
        self.assertIn("core.createApiClient", HTTP_JS)
        self.assertIn("X-CSRF-Token", HTTP_JS)
        self.assertIn("const state = window.SIVSState", APP)
        self.assertIn("window.SIVSCore.createApiClient", APP)

    def test_productivity_layer_keeps_familiar_navigation_and_adds_real_tools(self):
        self.assertIn('id="commandButton"', INDEX)
        self.assertIn('id="commandDialog"', INDEX)
        self.assertIn('id="draftNotice"', INDEX)
        self.assertNotIn('id="globalSearch"', INDEX)
        self.assertIn("global.SIVSPreferences", PREFERENCES_JS)
        self.assertIn("global.SIVSDrafts", DRAFTS_JS)
        self.assertIn("sessionStorage", DRAFTS_JS)
        self.assertIn("Ctrl", INDEX)
        self.assertIn("commandPalette", COMMAND_JS)
        self.assertIn("/api/search", APP)
        self.assertIn("workCenterHTML", APP)
        self.assertIn("saveRecordDraftNow", APP)
        self.assertIn("prefers-reduced-motion: reduce", PRODUCTIVITY)

    def test_operational_forms_share_master_records_by_validated_id(self):
        self.assertIn("const recordReferenceRules", APP)
        self.assertIn("data-record-reference", APP)
        self.assertIn("function populateRecordReferenceFields", APP)
        self.assertIn('payload[`${field.key}_id`]', APP)
        self.assertIn(".record-reference-field", COMPONENTS)
        self.assertIn("RECORD_REFERENCE_RULES", (ROOT / "server.py").read_text(encoding="utf-8"))

    def test_modern_components_and_progressive_record_keep_accessible_fallbacks(self):
        self.assertIn('id="recordDisclosure"', INDEX)
        self.assertIn('id="recordOptionalToggle"', INDEX)
        self.assertIn("recordDisclosure", RECORD_DISCLOSURE_JS)
        self.assertIn("ensureVisible", RECORD_DISCLOSURE_JS)
        self.assertIn("is-essential-mode", RECORD_DISCLOSURE_JS)
        self.assertIn("record-optional", APP)
        self.assertIn("::-webkit-scrollbar-thumb", COMPONENTS)
        self.assertIn("scrollbar-width: thin", COMPONENTS)
        self.assertIn("appearance: base-select", COMPONENTS)
        self.assertIn("@supports (appearance: base-select)", COMPONENTS)
        self.assertNotIn("Ã", RECORD_DISCLOSURE_JS)

    def test_registration_forms_use_the_right_drawer_and_party_defaults(self):
        self.assertIn("inset: 0 0 0 258px", COMPONENTS)
        self.assertIn(".form-drawer", COMPONENTS)
        self.assertIn("sivs-drawer-in", MOTION)
        for dialog_id in ("userDialog", "settingsDialog", "companyDialog", "passwordDialog"):
            self.assertRegex(INDEX, rf'id="{dialog_id}" class="[^"]*form-drawer')
        self.assertIn('roleField.value = "Cliente (C)"', APP)
        self.assertIn('roleField.value = "Fornecedor (F)"', APP)
        self.assertIn("function applyPartyFieldContext", APP)
        self.assertIn('"Nome completo"', APP)
        self.assertIn('"Qualificação do fornecedor"', APP)
        self.assertIn(".party-context-hidden", COMPONENTS)

    def test_mobile_install_experience_has_manifest_icons_and_ios_fallback(self):
        self.assertIn('data-install-app', INDEX)
        self.assertIn('id="installDialog"', INDEX)
        self.assertIn("/js/ui/install-app.js", INDEX)
        self.assertIn("beforeinstallprompt", INSTALL_APP_JS)
        self.assertIn("Adicionar à Tela de Início", INSTALL_APP_JS)
        self.assertIn("(display-mode: standalone)", INSTALL_APP_JS)
        self.assertIn('"sizes": "192x192"', MANIFEST)
        self.assertIn('"sizes": "512x512"', MANIFEST)
        self.assertIn('"display": "standalone"', MANIFEST)
        self.assertIn("/assets/brand/seccol-app-192.png", SERVICE_WORKER)
        self.assertIn("/assets/brand/seccol-app-512.png", SERVICE_WORKER)
        self.assertIn("/api/partner-lookup?cnpj=", APP)
        self.assertIn("/api/partner-lookup?cep=", APP)
        self.assertIn("function maskPartyCepField", APP)
        self.assertIn("autocomplete = \"postal-code\"", APP)

    def test_initial_access_offers_login_without_reopening_completed_setup(self):
        self.assertIn('id="authModeSwitch"', INDEX)
        self.assertIn('id="authModeToggle"', INDEX)
        self.assertIn("authSetupAvailable", STATE_JS)
        self.assertIn('setup && state.authSetupAvailable', APP)
        self.assertIn('failure.code === "already_configured"', APP)
        self.assertIn('$("#authModeToggle").onclick', APP)
        self.assertIn("Já possui um acesso?", APP)

    def test_sidebar_displays_local_date_with_weekday_and_daily_refresh(self):
        self.assertIn('id="systemDate"', INDEX)
        self.assertIn('/js/ui/system-date.js', INDEX)
        self.assertIn('weekday: "long"', SYSTEM_DATE_JS)
        self.assertIn('month: "long"', SYSTEM_DATE_JS)
        self.assertIn('scheduleNextDay', SYSTEM_DATE_JS)
        self.assertIn('/js/ui/system-date.js', SERVICE_WORKER)


if __name__ == "__main__":
    unittest.main()
