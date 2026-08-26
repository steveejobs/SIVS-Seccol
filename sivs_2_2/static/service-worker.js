// Marker mantido para instalações que ainda validam o cache do visualizador de editais.
// Cache atual: trilha de auditoria + documentos oficiais incorporados.
const LEGACY_TENDER_VIEWER_CACHE = 'sivs-v2.2.0-portal-agent-viewer-80';
const CACHE = 'sivs-v2.2.0-dashboard-clarity-82';
const ASSETS = [
  '/', '/assets/brand/seccol-logo-clean.png', '/assets/brand/seccol-mark.png',
  '/assets/brand/seccol-app-192.png', '/assets/brand/seccol-app-512.png',
  '/theme/tokens.css', '/styles.css', '/theme/foundations.css', '/theme/responsive.css',
  '/theme/components.css?v=2.2.0-notification-center-77',
  '/theme/control-center.css?v=2.2.0-admin-operations-79',
  '/theme/inventory.css?v=2.2.0-functional-control-43',
  '/theme/workflow-items.css?v=2.2.0-erp-workflows-40',
  '/theme/permissions.css?v=2.2.0-functional-control-43',
  '/theme/management-control.css?v=2.2.0-functional-control-43',
  '/theme/fiscal-integration.css?v=2.2.0-fiscal-readiness-44',
  '/theme/financial-ledger.css?v=2.2.0-financial-ledger-61',
  '/theme/whatsapp.css?v=2.2.0-uazapi-whatsapp-64',
  '/theme/whatsapp-connection.css?v=2.2.0-uazapi-whatsapp-64',
  '/theme/crm-followups.css?v=2.2.0-crm-followups-65',
  '/theme/tenders.css?v=2.2.0-tender-extraction-58',
  '/theme/tender-control.css?v=2.2.0-tender-control-78',
  '/theme/tender-documents.css?v=2.2.0-tender-documents-52',
  '/theme/tender-proposal.css?v=2.2.0-tender-handoff-55',
  '/theme/tender-portal-agent.css?v=2.2.0-portal-agent-viewer-80',
  '/theme/productivity.css?v=2.2.0-dashboard-clarity-82', '/theme/motion.css',
  '/js/core/platform.js', '/js/core/state.js',
  '/js/core/formatters.js?v=2.2.0-party-mask-23', '/js/core/http.js',
  '/js/core/preferences.js', '/js/core/drafts.js', '/js/ui/motion.js',
  '/js/ui/dialogs.js', '/js/ui/pointer.js', '/js/ui/navigation.js',
  '/js/ui/command-palette.js', '/js/ui/workspace-tabs.js?v=2.2.0-workspace-tabs-59',
  '/js/ui/record-disclosure.js', '/js/ui/experience.js',
  '/js/ui/tender-viewer.js?v=2.2.0-tender-viewer-46',
  '/js/ui/install-app.js?v=2.2.0-mobile-21',
  '/js/ui/system-date.js?v=2.2.0-system-date-28',
  '/js/modules/control-center.js?v=2.2.0-admin-operations-79',
  '/js/modules/inventory.js?v=2.2.0-functional-control-43',
  '/js/modules/management-control.js?v=2.2.0-functional-control-43',
  '/js/modules/fiscal-integration.js?v=2.2.0-fiscal-readiness-44',
  '/js/modules/financial-ledger.js?v=2.2.0-financial-ledger-61',
  '/js/modules/whatsapp.js?v=2.2.0-uazapi-whatsapp-64',
  '/js/modules/workflow-items.js?v=2.2.0-erp-workflows-40',
  '/js/modules/tender-keywords.js?v=2.2.0-ux-guidance-47',
  '/js/modules/tender-documents.js?v=2.2.0-tender-extraction-58',
  '/js/modules/tender-control.js?v=2.2.0-tender-control-78',
  '/js/modules/tender-proposal.js?v=2.2.0-tender-handoff-55',
  '/js/modules/tender-portal-agent.js?v=2.2.0-portal-agent-viewer-80',
  '/app.js?v=2.2.0-admin-operations-79', '/manifest.json?v=2.2.0-mobile-21',
];
self.addEventListener('install', (event) => event.waitUntil(
  caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()),
));
self.addEventListener('activate', (event) => event.waitUntil(
  caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)),
  )).then(() => self.clients.claim()),
));
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET' || new URL(event.request.url).pathname.startsWith('/api/')) return;
  event.respondWith(fetch(event.request).then((response) => {
    const copy = response.clone();
    caches.open(CACHE).then((cache) => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request)));
});
