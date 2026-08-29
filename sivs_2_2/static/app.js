const state = window.SIVSState;

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const ui = window.SIVSUI || {};
const dismissDialog = (dialog) => ui.closeDialog ? ui.closeDialog(dialog) : dialog?.close();
const { money, dateBR, documentBR, escapeHTML, safeExternalURL, statusClass } = window.SIVSCore;
const preferences = window.SIVSPreferences;
const drafts = window.SIVSDrafts;
let tenderKeywordEditor = null;

const financialCategoryModules = new Set(["contas_pagar", "contas_receber", "financeiro", "caixa"]);
const financialEvidenceModules = new Set(["fiscal", "contas_pagar", "financeiro", "caixa"]);

const roleLabels = {
  admin: "Administrador",
  manager: "Gestor",
  seller: "Vendedor",
  operator: "Operador",
  viewer: "Consulta",
  technician: "Técnico de campo",
  quality: "Qualidade",
  fiscal: "Fiscal / financeiro",
  approver: "Aprovador",
};

const icons = {
  relatorios: "\u25eb",
  dashboard: "◫", portfolio: "◆", assuntos: "◈", aprovacoes: "✓", arquivos: "▤", clientes_fornecedores: "◉",
  fornecedores: "◎", contatos: "☎", importacoes_xml: "⤓", solicitacoes_compra: "✎",
  pedidos_compra: "⇣", ramais: "☏", crm: "◐", whatsapp: "◌", propostas: "◇", contratos: "≡",
  licitacoes: "⚖", editais: "⌕", fontes: "⊛", concorrentes: "♜", equipamentos: "◨",
  chamados: "!", agendamentos: "◷", ordens_servico: "⚑", servicos: "⚒", calibracoes: "⊕",
  mobile: "▯", certificados: "▣", padroes: "⬡", planilhas_calibracao: "▦",
  laudos_tecnicos: "⎘", estudos_tecnicos: "⌬", normas_tecnicas: "§", qualidade: "✦",
  documentos_qualidade: "≣", reclamacoes: "‼", nao_conformidades: "△", colaboradores: "♙", rh: "◷",
  treinamentos: "☑", frota: "▰", manutencao_frota: "∿", produtos: "▧",
  catalogo_servicos: "▩", instrumentos_seccol: "⌂", estoque: "▨",
  vendas: "↑", fiscal: "⎙", contas_pagar: "↓", contas_receber: "⇡", boletos: "▭",
  financeiro: "R$", caixa: "▥", controladoria: "◩", produtividade: "↗", metas: "⌖", control_center: "◉", settings: "⚙",
};

const sections = [
  ["RELAT\u00d3RIOS", [["relatorios", "Central de relat\u00f3rios"]]],
  ["COMEÇAR", [["dashboard", "Painel executivo"], ["assuntos", "Central de assuntos"], ["aprovacoes", "Aprovações"]]],
  ["CADASTROS E COMPRAS", [["arquivos", "Arquivos"], ["clientes_fornecedores", "Parceiros"], ["contatos", "Contatos"], ["solicitacoes_compra", "Solicitar compra"], ["pedidos_compra", "Pedidos de compra"], ["ramais", "Ramais"]]],
  ["CLIENTES E VENDAS", [["portfolio", "Portfólio técnico"], ["produtos", "Produtos e soluções"], ["catalogo_servicos", "Serviços e ensaios"], ["crm", "Relacionamento com clientes"], ["whatsapp", "Atendimento WhatsApp"], ["propostas", "Propostas"], ["contratos", "Contratos"]]],
  ["EDITAIS E MERCADO", [["fontes", "Fontes de busca"], ["editais", "Buscar editais"], ["concorrentes", "Concorrentes e preços"], ["licitacoes", "Licitações"]]],
  ["SERVIÇOS E CAMPO", [["mobile", "Operação em campo"], ["instrumentos_seccol", "Instrumentos próprios"], ["equipamentos", "Equipamentos de clientes"], ["chamados", "Chamados"], ["agendamentos", "Agendamentos"], ["ordens_servico", "Ordens de Serviço"], ["servicos", "Serviços executados"], ["calibracoes", "Calibrações"], ["certificados", "Certificados"], ["laudos_tecnicos", "Laudos técnicos"], ["estudos_tecnicos", "Estudos técnicos"], ["padroes", "Padrões metrológicos"], ["planilhas_calibracao", "Planilhas de calibração"]]],
  ["QUALIDADE E EQUIPE", [["rh", "RH, ponto e folha"], ["colaboradores", "Colaboradores"], ["treinamentos", "Treinamentos"], ["normas_tecnicas", "Normas técnicas"], ["qualidade", "Qualidade"], ["documentos_qualidade", "Documentos controlados"], ["reclamacoes", "Reclamações"], ["nao_conformidades", "Não conformidades"]]],
  ["ATIVOS E FROTA", [["frota", "Frota"], ["manutencao_frota", "Controle veicular"]]],
  ["FISCAL", [["fiscal", "Central fiscal"], ["importacoes_xml", "Importar XML NF-e"]]],
  ["VENDAS E FINANCEIRO", [["estoque", "Estoque e lotes"], ["vendas", "Vendas"], ["contas_pagar", "Contas a pagar"], ["contas_receber", "Contas a receber"], ["boletos", "Boletos e remessas"], ["financeiro", "Lançamentos financeiros"], ["caixa", "Caixa"], ["controladoria", "Visão financeira"]]],
  ["GESTÃO", [["produtividade", "Produtividade"], ["metas", "Metas"], ["control_center", "Operação e segurança"], ["settings", "Configurações"]]],
];

const roleShortcutDefaults = {
  admin: ["clientes_fornecedores", "editais", "aprovacoes", "financeiro", "settings"],
  manager: ["clientes_fornecedores", "editais", "aprovacoes", "crm", "financeiro"],
  seller: ["clientes_fornecedores", "crm", "propostas", "editais", "contratos"],
  operator: ["clientes_fornecedores", "solicitacoes_compra", "pedidos_compra", "ordens_servico", "chamados"],
  technician: ["ordens_servico", "mobile", "calibracoes", "certificados", "equipamentos"],
  quality: ["normas_tecnicas", "qualidade", "nao_conformidades", "documentos_qualidade", "calibracoes"],
  fiscal: ["importacoes_xml", "fiscal", "contas_pagar", "contas_receber", "financeiro"],
  approver: ["aprovacoes", "solicitacoes_compra", "pedidos_compra", "documentos_qualidade"],
  viewer: ["clientes_fornecedores", "editais", "portfolio", "normas_tecnicas"],
};

function screenCatalog() {
  return sections.flatMap(([group, links]) => links.map(([key, label]) => ({ key, label, group })));
}

function screenLabel(screen) {
  return screenCatalog().find((item) => item.key === screen)?.label || state.modules[screen] || screen;
}

const F = (key, label, type = "text", options = [], full = false) => ({ key, label, type, options, full });
const schemas = {
  arquivos: [F("identificador", "Identificador"), F("categoria", "Categoria"), F("revisao", "Revisão"), F("aprovado_qualidade", "Aprovado pela qualidade", "checkbox")],
  clientes: [F("tipo_cadastro", "Identificação", "select", ["C", "C e F"]), F("tipo_pessoa", "Tipo de pessoa", "select", ["Pessoa jurídica", "Pessoa física"]), F("documento", "CPF/CNPJ"), F("razao_social", "Razão social"), F("nome_fantasia", "Nome fantasia"), F("telefone", "Telefone", "tel"), F("email", "E-mail", "email"), F("cep", "CEP"), F("cidade", "Cidade/UF"), F("categoria", "Categoria"), F("vendedor", "Vendedor"), F("tabela_preco", "Tabela de preços"), F("aprovado_faturamento", "Aprovado para faturamento", "checkbox"), F("bloqueado", "Cadastro bloqueado", "checkbox")],
  fornecedores: [F("tipo_cadastro", "Identificação", "select", ["F", "C e F"]), F("tipo_pessoa", "Tipo de pessoa", "select", ["Pessoa jurídica", "Pessoa física"]), F("documento", "CPF/CNPJ"), F("razao_social", "Razão social"), F("nome_fantasia", "Nome fantasia"), F("telefone", "Telefone", "tel"), F("email", "E-mail", "email"), F("categoria", "Categoria"), F("avaliacao", "Avaliação do fornecedor", "select", ["Pendente", "Aprovado", "Com ressalvas", "Reprovado"]), F("aprovado_compras", "Aprovado para compras", "checkbox")],
  contatos: [F("cliente_fornecedor", "Parceiro vinculado"), F("tipo_contato", "Tipo de contato"), F("cargo", "Cargo"), F("telefone", "Telefone", "tel"), F("email", "E-mail", "email"), F("principal", "Contato principal", "checkbox")],
  importacoes_xml: [F("chave", "Chave NF-e"), F("numero", "Número"), F("fornecedor", "Fornecedor"), F("data_emissao", "Emissão", "date")],
  solicitacoes_compra: [F("numero", "Número da solicitação"), F("fornecedor", "Fornecedor sugerido"), F("solicitante", "Solicitante"), F("centro_custo", "Centro de custo"), F("prioridade", "Prioridade", "select", ["Baixa", "Normal", "Alta", "Urgente"]), F("justificativa", "Justificativa", "textarea", [], true)],
  pedidos_compra: [F("numero", "Número do pedido"), F("fornecedor", "Fornecedor"), F("solicitacao", "Solicitação de origem"), F("condicao_pagamento", "Condição de pagamento"), F("centro_custo", "Centro de custo"), F("gerar_conta_pagar_ao_receber", "Gerar conta a pagar ao receber (somente sem XML)", "checkbox"), F("avaliacao_fornecedor", "Avaliação do fornecedor")],
  ramais: [F("nome_ramal", "Nome/local"), F("ramal", "Ramal"), F("setor", "Setor")],
  crm: [F("cliente", "Cliente cadastrado"), F("empresa_informada", "Empresa informada"), F("telefone", "Telefone", "tel"), F("email", "E-mail", "email"), F("localizacao", "Cidade/UF"), F("etapa", "Etapa do funil", "select", ["Novo lead", "Contato realizado", "Qualificado", "Proposta", "Negociação", "Ganho", "Perdido"]), F("origem", "Origem"), F("proximo_passo", "Próximo passo"), F("probabilidade", "Probabilidade (%)", "number")],
  propostas: [F("numero", "Número da proposta"), F("cliente", "Cliente"), F("validade", "Validade", "date"), F("etapa", "Etapa", "select", ["Rascunho", "Enviada", "Em negociação", "Aprovada", "Recusada"]), F("condicao_pagamento", "Condição de pagamento"), F("local_execucao", "Local de execução")],
  contratos: [F("numero", "Número do contrato"), F("cliente", "Cliente"), F("gestor", "Gestor do contrato"), F("inicio", "Início", "date"), F("fim", "Término", "date"), F("renovacao", "Renovação automática", "checkbox")],
  licitacoes: [F("cliente", "Órgão/cliente cadastrado"), F("orgao", "Órgão publicado"), F("edital", "Número do edital"), F("portal", "Portal/link", "url"), F("modalidade", "Modalidade"), F("data_abertura", "Data de abertura", "date"), F("etapa", "Etapa", "select", ["Captação", "Análise", "Documentação", "Proposta enviada", "Disputa", "Habilitação", "Homologada", "Perdida"])],
  concorrentes: [F("cnpj", "CNPJ"), F("especialidade", "Especialidade"), F("regiao", "Região"), F("classificacao", "Avaliação interna", "select", ["Estratégico", "Forte", "Monitorar", "Baixa aderência"]), F("fonte", "Fonte pública", "url"), F("pontos_fortes", "Pontos fortes", "textarea", [], true), F("observacao_avaliacao", "Observações da avaliação", "textarea", [], true)],
  instrumentos_seccol: [F("codigo", "Código do catálogo"), F("tipo", "Tipo"), F("propriedade", "Propriedade"), F("fabricante", "Fabricante"), F("modelo", "Modelo"), F("numero_serie", "Número de série"), F("patrimonio", "Patrimônio"), F("uso_tecnico", "Uso técnico", "textarea", [], true), F("controle_metrologico", "Controle metrológico", "textarea", [], true), F("proxima_calibracao", "Próxima calibração", "date"), F("fonte_oficial", "Página oficial", "url"), F("catalogo_seccol", "Exibir no portfólio", "checkbox")],
  equipamentos: [F("cliente", "Cliente"), F("tipo", "Tipo de equipamento"), F("fabricante", "Fabricante"), F("modelo", "Modelo"), F("numero_serie", "Número de série"), F("patrimonio", "Patrimônio"), F("localizacao", "Localização"), F("proxima_calibracao", "Próxima calibração", "date")],
  chamados: [F("cliente", "Cliente"), F("solicitante", "Solicitante"), F("tipo", "Tipo"), F("prioridade", "Prioridade", "select", ["Baixa", "Normal", "Alta", "Crítica"]), F("equipamento", "Equipamento"), F("resposta", "Resposta/andamento", "textarea", [], true)],
  agendamentos: [F("cliente", "Cliente"), F("tecnico", "Técnico"), F("data", "Data", "date"), F("hora", "Hora", "time"), F("local", "Local"), F("tipo_servico", "Tipo de serviço")],
  ordens_servico: [F("numero", "Número da O.S."), F("cliente", "Cliente"), F("tecnico", "Técnico responsável"), F("tipo_os", "Tipo de O.S."), F("local_execucao", "Local de execução"), F("inicio", "Início", "datetime-local"), F("fim", "Fim", "datetime-local"), F("tempo_minutos", "Tempo de serviço (min)", "number")],
  servicos: [F("cliente", "Cliente"), F("equipamento", "Equipamento"), F("numero_serie", "Número de série"), F("tecnico", "Técnico"), F("tipo_servico", "Tipo de serviço"), F("certificado", "Certificado")],
  calibracoes: [F("os", "Ordem de Serviço"), F("equipamento", "Equipamento"), F("tecnico", "Técnico"), F("data_calibracao", "Data da calibração", "date"), F("proxima_calibracao", "Próxima calibração", "date"), F("regra_decisao", "Regra de decisão")],
  certificados: [F("numero", "Número do certificado"), F("os", "Ordem de Serviço"), F("equipamento", "Equipamento"), F("data_emissao", "Emissão", "date"), F("revisao", "Revisão"), F("aprovador", "Aprovador"), F("publicar_certweb", "Disponibilizar no Certweb", "checkbox")],
  laudos_tecnicos: [F("numero", "Número do laudo"), F("os", "Ordem de Serviço"), F("cliente", "Cliente"), F("local_avaliado", "Local avaliado"), F("responsavel_tecnico", "Responsável técnico"), F("data_emissao", "Emissão", "date"), F("metodo", "Método aprovado"), F("regra_decisao", "Regra de decisão"), F("conclusao", "Conclusão técnica", "textarea", [], true)],
  estudos_tecnicos: [F("numero", "Número do estudo"), F("cliente", "Cliente"), F("objeto", "Objeto do estudo"), F("responsavel_tecnico", "Responsável técnico"), F("data_emissao", "Emissão", "date"), F("premissas", "Premissas", "textarea", [], true), F("metodologia", "Metodologia", "textarea", [], true), F("recomendacoes", "Recomendações", "textarea", [], true)],
  normas_tecnicas: [F("codigo", "Código"), F("titulo_publicado", "Título publicado", "text", [], true), F("tipo_referencia", "Natureza", "select", ["Norma técnica", "Regulamento", "Método", "Guia técnico"]), F("organismo", "Organismo"), F("edicao", "Edição"), F("emenda", "Emenda, corrigenda ou errata", "text", [], true), F("data_publicacao", "Data de publicação", "date"), F("vigencia_em", "Vigência aplicável", "date"), F("escopo_resumido", "Escopo resumido", "textarea", [], true), F("aplicabilidade_seccol", "Aplicabilidade SECCOL", "textarea", [], true), F("ensaios_base", "Ensaios/controles relacionados", "textarea", [], true), F("referencia_oficial", "Referência oficial", "url", [], true), F("licenciamento", "Licenciamento"), F("titular_licenca", "Titular / área autorizada"), F("proxima_revisao", "Próxima revisão", "date"), F("verificado_em", "Última verificação", "date"), F("norma_substituta", "Substituída por", "select"), F("documento_status", "Observação documental", "textarea", [], true)],
  padroes: [F("codigo", "Código"), F("tipo", "Tipo de padrão"), F("fabricante", "Fabricante"), F("numero_serie", "Número de série"), F("faixa_medicao", "Faixa de medição"), F("proxima_calibracao", "Próxima calibração", "date"), F("rastreabilidade", "Rastreabilidade")],
  planilhas_calibracao: [F("codigo", "Código da planilha"), F("grandeza", "Grandeza"), F("versao", "Versão"), F("criterio_aceitacao", "Critério de aceitação"), F("aprovada", "Planilha aprovada", "checkbox")],
  qualidade: [F("tipo", "Tipo"), F("norma", "Norma/requisito"), F("responsavel_qualidade", "Responsável"), F("acao_corretiva", "Ação corretiva", "textarea", [], true)],
  documentos_qualidade: [F("codigo", "Código do documento"), F("tipo", "Tipo"), F("revisao", "Revisão"), F("elaborador", "Elaborador"), F("aprovador", "Aprovador"), F("data_vigencia", "Vigência", "date")],
  reclamacoes: [F("cliente", "Cliente"), F("canal", "Canal"), F("procedente", "Procedência", "select", ["Em análise", "Procedente", "Improcedente"]), F("causa", "Causa", "textarea", [], true), F("tratativa", "Tratativa", "textarea", [], true)],
  nao_conformidades: [F("origem", "Origem"), F("requisito", "Requisito afetado"), F("causa_raiz", "Causa raiz", "textarea", [], true), F("correcao", "Correção", "textarea", [], true), F("acao_corretiva", "Ação corretiva", "textarea", [], true)],
  colaboradores: [F("cpf", "CPF"), F("cargo", "Cargo"), F("setor", "Setor"), F("email", "E-mail", "email"), F("telefone", "Telefone", "tel"), F("tecnico", "Técnico de campo", "checkbox"), F("vendedor", "Vendedor", "checkbox")],
  treinamentos: [F("colaborador", "Colaborador"), F("competencia", "Competência/treinamento"), F("data", "Data", "date"), F("validade", "Validade", "date"), F("carga_horaria", "Carga horária"), F("resultado", "Resultado")],
  frota: [F("placa", "Placa"), F("veiculo", "Veículo"), F("renavam", "RENAVAM"), F("chassi", "Chassi"), F("quilometragem", "Quilometragem", "number"), F("responsavel_veiculo", "Responsável"), F("seguro_vencimento", "Vencimento do seguro", "date")],
  manutencao_frota: [F("placa", "Placa"), F("tipo", "Tipo de manutenção"), F("quilometragem", "Quilometragem", "number"), F("oficina", "Oficina / fornecedor"), F("proxima_km", "Próxima revisão (km)", "number"), F("data_servico", "Data", "date")],
  produtos: [F("codigo", "Código"), F("familia", "Família"), F("tipo_item", "Natureza do item"), F("origem_operacional", "Origem operacional"), F("descricao", "Descrição", "textarea", [], true), F("ncm", "NCM"), F("cfop", "CFOP"), F("unidade", "Unidade"), F("preco_venda", "Preço de venda", "number"), F("custo_referencia", "Custo interno de referência", "number"), F("fonte_oficial", "Página oficial", "url"), F("catalogo_seccol", "Exibir no portfólio", "checkbox")],
  catalogo_servicos: [F("codigo", "Código"), F("categoria", "Categoria"), F("tipo_servico", "Serviço/ensaio"), F("origem_operacional", "Origem operacional"), F("descricao", "Descrição", "textarea", [], true), F("custo_referencia", "Custo direto interno estimado", "number"), F("fonte_oficial", "Página oficial", "url"), F("verificado_em", "Verificado em", "date"), F("catalogo_seccol", "Exibir no portfólio", "checkbox")],
  estoque: [F("produto", "Produto"), F("lote", "Lote"), F("validade", "Validade", "date"), F("quantidade", "Quantidade", "number"), F("localizacao", "Localização"), F("movimento", "Movimento", "select", ["Entrada", "Saída", "Ajuste"])],
  vendas: [F("cliente", "Cliente"), F("documento", "NF/pedido"), F("vendedor", "Vendedor"), F("forma_pagamento", "Forma de pagamento"), F("condicao_pagamento", "Condição de pagamento")],
  fiscal: [F("tipo_nota", "Tipo de nota", "select", ["NF-e", "NFS-e", "NFC-e", "Devolução"]), F("numero", "Número"), F("serie", "Série"), F("chave", "Chave de acesso"), F("destinatario", "Destinatário"), F("cfop", "CFOP"), F("finalidade", "Finalidade")],
  contas_pagar: [F("fornecedor", "Fornecedor"), F("documento", "Documento"), F("parcela", "Parcela"), F("categoria", "Categoria", "financial-category"), F("centro_custo", "Centro de custo"), F("conta", "Conta de saída"), F("forma_pagamento", "Forma de pagamento"), F("data_pagamento", "Data do pagamento", "date")],
  contas_receber: [F("cliente", "Cliente"), F("documento", "Documento"), F("parcela", "Parcela"), F("categoria", "Categoria", "financial-category"), F("centro_custo", "Centro de custo"), F("conta", "Conta de entrada"), F("forma_pagamento", "Forma de recebimento"), F("data_recebimento", "Data do recebimento", "date")],
  boletos: [F("cliente", "Cliente"), F("nosso_numero", "Nosso número"), F("banco", "Banco"), F("conta", "Conta/plano"), F("remessa", "Arquivo de remessa"), F("vencimento_original", "Vencimento original", "date")],
  financeiro: [F("tipo_lancamento", "Tipo", "select", ["Receita", "Despesa"]), F("parceiro", "Cliente ou fornecedor"), F("categoria", "Categoria", "financial-category"), F("documento", "Documento"), F("conta", "Conta"), F("centro_custo", "Centro de custo"), F("pago", "Baixado", "checkbox")],
  caixa: [F("tipo_movimento", "Movimento", "select", ["Entrada", "Saída"]), F("parceiro", "Cliente ou fornecedor"), F("categoria", "Categoria", "financial-category"), F("conta", "Conta"), F("operador", "Operador"), F("forma_pagamento", "Forma de pagamento")],
  produtividade: [F("colaborador", "Colaborador"), F("periodo", "Período"), F("indicador", "Indicador"), F("resultado", "Resultado", "number"), F("horas", "Horas", "number")],
  metas: [F("responsavel_meta", "Responsável"), F("indicador", "Indicador"), F("periodo", "Período"), F("meta", "Meta", "number"), F("realizado", "Realizado", "number")],
};

const recordReferenceRules = {
  cliente: { modules: ["clientes", "fornecedores"], partyRole: "C", relation: "Cliente" },
  fornecedor: { modules: ["clientes", "fornecedores"], partyRole: "F", relation: "Fornecedor" },
  oficina: { modules: ["clientes", "fornecedores"], partyRole: "F", relation: "Fornecedor" },
  cliente_fornecedor: { modules: ["clientes", "fornecedores"], partyRole: "P", relation: "Contato de", fieldLabel: "Parceiro vinculado" },
  destinatario: { modules: ["clientes", "fornecedores"], partyRole: "A", relation: "Destinatário" },
  parceiro: { modules: ["clientes", "fornecedores"], partyRole: "A", relation: "Parceiro" },
  equipamento: { modules: ["equipamentos"], relation: "Equipamento" },
  os: { modules: ["ordens_servico"], relation: "Ordem de Serviço" },
  solicitacao: { modules: ["solicitacoes_compra"], relation: "Solicitação de origem" },
  produto: { modules: ["produtos"], relation: "Produto" },
  colaborador: { modules: ["colaboradores"], relation: "Colaborador" },
  certificado: { modules: ["certificados"], relation: "Certificado" },
  norma: { modules: ["normas_tecnicas"], relation: "Norma técnica" },
  norma_substituta: { modules: ["normas_tecnicas"], relation: "Substituída por", fieldLabel: "Substituída por" },
  placa: { modules: ["frota"], sourceModules: ["manutencao_frota"], relation: "Veículo" },
};

function recordReferenceRule(module, key, payload = null) {
  const rule = recordReferenceRules[key];
  if (!rule || (rule.sourceModules && !rule.sourceModules.includes(module))) return null;
  if (key !== "parceiro" || module !== "financeiro") return rule;
  const form = $("#recordForm");
  const movement = String(payload?.tipo_lancamento || form?.elements.extra_tipo_lancamento?.value || "");
  if (movement === "Despesa") {
    return { ...rule, partyRole: "F", relation: "Fornecedor", fieldLabel: "Fornecedor / favorecido" };
  }
  if (movement === "Receita") {
    return { ...rule, partyRole: "C", relation: "Cliente", fieldLabel: "Cliente / pagador" };
  }
  return rule;
}

const formDomains = {
  administrativo: { eyebrow: "ADMINISTRATIVO", accent: "#53636c", tint: "#eef2f4" },
  comercial: { eyebrow: "COMERCIAL", accent: "#c85d23", tint: "#fff1e9" },
  tecnico: { eyebrow: "SERVIÇO TÉCNICO", accent: "#167a74", tint: "#e8f5f2" },
  qualidade: { eyebrow: "QUALIDADE E CONFORMIDADE", accent: "#9b7628", tint: "#fbf4df" },
  ativos: { eyebrow: "ATIVOS E FROTA", accent: "#4f7549", tint: "#edf5eb" },
  financeiro: { eyebrow: "FISCAL E FINANCEIRO", accent: "#69507d", tint: "#f2edf6" },
  gestao: { eyebrow: "GESTÃO", accent: "#46576d", tint: "#edf1f6" },
};

const G = (title, hint, keys) => ({ title, hint, keys });
const P = (domain, singular, description, fieldsTitle, required = [], config = {}) => ({
  domain, singular, description, fieldsTitle, required,
  fieldsHint: `Informações próprias do cadastro de ${singular.toLowerCase()}.`,
  titleLabel: `Identificação de ${singular}`,
  titlePlaceholder: `Informe a identificação principal de ${singular.toLowerCase()}`,
  responsibleLabel: "Responsável interno",
  contactLabel: "Parte relacionada",
  contactPlaceholder: "Cliente, fornecedor, órgão ou contato",
  amountLabel: "Valor relacionado",
  dueLabel: "Prazo de acompanhamento",
  showAmount: false,
  showDue: true,
  showResponsible: true,
  showContact: true,
  notesLabel: "Descrição, decisões e observações",
  notesPlaceholder: "Registre fatos, critérios, decisões, pendências e próximos passos",
  ...config,
});

const registrationProfiles = {
  arquivos: P("administrativo", "Arquivo", "Controle documental com categoria, revisão, evidência e aprovação da qualidade.", "Classificação documental", ["identificador", "categoria"], { showDue: false, showContact: false }),
  clientes: P("administrativo", "Cliente", "Ficha cadastral, comercial e de faturamento da pessoa atendida pela SECCOL.", "Dados do cliente", ["tipo_pessoa", "documento", "razao_social"], { showDue: false, titleLabel: "Nome de exibição do cliente", titlePlaceholder: "Razão social ou nome do cliente", contactLabel: "Contato de referência", groups: [G("Identificação legal", "Dados utilizados em contratos, propostas e faturamento.", ["tipo_pessoa", "documento", "razao_social", "nome_fantasia"]), G("Contato e localização", "Canais e base geográfica do atendimento.", ["telefone", "email", "cep", "cidade"]), G("Política comercial", "Responsabilidade, preços e bloqueios.", ["categoria", "vendedor", "tabela_preco", "aprovado_faturamento", "bloqueado"])] }),
  fornecedores: P("administrativo", "Fornecedor", "Cadastro, avaliação e habilitação de fornecedores para o processo de compras.", "Dados do fornecedor", ["tipo_pessoa", "documento", "razao_social", "avaliacao"], { showDue: false, titleLabel: "Nome de exibição do fornecedor", titlePlaceholder: "Razão social ou nome do fornecedor", groups: [G("Identificação e contato", "Dados legais e canais do fornecedor.", ["tipo_pessoa", "documento", "razao_social", "telefone", "email"]), G("Qualificação de compras", "Categoria, avaliação e liberação operacional.", ["categoria", "avaliacao", "aprovado_compras"])] }),
  contatos: P("administrativo", "Contato", "Pessoa vinculada a um parceiro, com função e canais de comunicação.", "Dados do contato", ["cliente_fornecedor", "tipo_contato", "cargo"], { showDue: false, showResponsible: false, showContact: false, titleLabel: "Nome completo do contato", titlePlaceholder: "Informe o nome da pessoa" }),
  importacoes_xml: P("financeiro", "Importação fiscal", "Registro rastreável do XML recebido e da origem de seus lançamentos.", "Identificação da NF-e", ["chave", "numero", "fornecedor", "data_emissao"], { showDue: false, showAmount: true, amountLabel: "Valor total da NF-e", contactLabel: "Fornecedor / emitente" }),
  solicitacoes_compra: P("administrativo", "Solicitação de compra", "Demanda interna com justificativa, prioridade, centro de custo e aprovação.", "Demanda de compra", ["numero", "solicitante", "prioridade", "justificativa"], { showAmount: true, amountLabel: "Valor estimado", dueLabel: "Data necessária", contactLabel: "Fornecedor sugerido" }),
  pedidos_compra: P("administrativo", "Pedido de compra", "Pedido emitido a fornecedor e conectado à solicitação que o originou.", "Condições do pedido", ["numero", "fornecedor", "condicao_pagamento", "centro_custo"], { showAmount: true, amountLabel: "Valor do pedido", dueLabel: "Previsão de entrega", contactLabel: "Contato do fornecedor" }),
  ramais: P("administrativo", "Ramal", "Lista operacional de ramais por pessoa, local e setor.", "Localização do ramal", ["nome_ramal", "ramal", "setor"], { showDue: false, showResponsible: false, showContact: false, titleLabel: "Identificação do ramal", titlePlaceholder: "Ex.: Laboratório — Recepção" }),

  crm: P("comercial", "Oportunidade", "Oportunidade comercial acompanhada do primeiro contato ao ganho ou perda.", "Qualificação comercial", ["etapa", "origem", "proximo_passo", "probabilidade"], { showAmount: true, amountLabel: "Valor potencial", dueLabel: "Data do próximo passo", contactLabel: "Cliente / lead", notesLabel: "Necessidade, objeções e próximos passos" }),
  propostas: P("comercial", "Proposta", "Proposta técnico-comercial com validade, condição de pagamento e local de execução.", "Condições da proposta", ["numero", "cliente", "validade", "etapa", "local_execucao"], { showAmount: true, amountLabel: "Valor proposto", dueLabel: "Prazo interno de retorno", contactLabel: "Contato do cliente" }),
  contratos: P("comercial", "Contrato", "Instrumento contratual com vigência, gestor e controle de renovação.", "Vigência e gestão contratual", ["numero", "cliente", "gestor", "inicio", "fim"], { showAmount: true, amountLabel: "Valor contratado", dueLabel: "Alerta de renovação", contactLabel: "Contratante / fiscal do contrato" }),
  licitacoes: P("comercial", "Licitação", "Processo licitatório convertido da busca oficial e acompanhado até seu resultado.", "Dados do certame", ["cliente", "orgao", "edital", "portal", "modalidade", "data_abertura", "etapa"], { showAmount: true, amountLabel: "Valor estimado / homologado", dueLabel: "Próximo prazo crítico", contactLabel: "Órgão / agente de contratação", titleLabel: "Objeto resumido da licitação", titlePlaceholder: "Descreva o objeto principal do certame", notesLabel: "Requisitos, riscos e decisão de participação", groups: [G("Contraparte operacional", "Vincule o órgão ao cadastro validado antes de gerar contrato, execução e financeiro.", ["cliente"]), G("Identificação pública", "Dados que permitem conferir a oportunidade na fonte oficial.", ["orgao", "edital", "portal", "modalidade"]), G("Agenda e decisão", "Marco de abertura e posição atual no fluxo.", ["data_abertura", "etapa"])] }),
  concorrentes: P("comercial", "Concorrente", "Avalie empresas concorrentes com evidências públicas e compare preços médios recentes de licitações e pregões.", "Avaliação competitiva", ["cnpj", "especialidade", "regiao", "classificacao", "fonte"], { showDue: false, showAmount: false, contactLabel: "Contato público / representante", titleLabel: "Razão social do concorrente", titlePlaceholder: "Informe a empresa concorrente", notesLabel: "Evidências, fragilidades e estratégia competitiva", groups: [G("Identificação e alcance", "Quem é e onde atua.", ["cnpj", "especialidade", "regiao", "classificacao"]), G("Evidência e avaliação", "Fonte auditável, diferenciais e observações internas.", ["fonte", "pontos_fortes", "observacao_avaliacao"])] }),

  instrumentos_seccol: P("tecnico", "Instrumento SECCOL", "Instrumento técnico próprio com identidade, uso e situação metrológica.", "Identificação e controle metrológico", ["codigo", "tipo", "fabricante", "modelo", "numero_serie", "proxima_calibracao"], { showDue: false, showContact: false, groups: [G("Identificação patrimonial", "Catálogo, fabricante e rastreabilidade física.", ["codigo", "tipo", "propriedade", "fabricante", "modelo", "numero_serie", "patrimonio"]), G("Aptidão para uso", "Finalidade, controle metrológico e vencimento.", ["uso_tecnico", "controle_metrologico", "proxima_calibracao", "fonte_oficial"])] }),
  equipamentos: P("tecnico", "Equipamento de cliente", "Equipamento instalado no cliente e vinculado ao histórico técnico completo.", "Identificação do equipamento", ["cliente", "tipo", "fabricante", "modelo", "numero_serie", "localizacao"], { showDue: false, contactLabel: "Contato técnico do cliente", groups: [G("Propriedade e identidade", "Cliente, tipo e identificação inequívoca do ativo.", ["cliente", "tipo", "fabricante", "modelo", "numero_serie", "patrimonio"]), G("Localização e controle", "Local de instalação e próxima calibração.", ["localizacao", "proxima_calibracao"])] }),
  chamados: P("tecnico", "Chamado", "Solicitação técnica triada por prioridade, equipamento e andamento.", "Triagem do chamado", ["cliente", "solicitante", "tipo", "prioridade"], { showAmount: true, amountLabel: "Valor estimado", dueLabel: "SLA / prazo de resposta", contactLabel: "Solicitante / contato", notesLabel: "Sintoma, diagnóstico e ações" }),
  agendamentos: P("tecnico", "Agendamento", "Reserva operacional de técnico, data, horário, local e serviço.", "Agenda de execução", ["cliente", "tecnico", "data", "hora", "local", "tipo_servico"], { showDue: false, showAmount: false, contactLabel: "Contato no local" }),
  ordens_servico: P("tecnico", "Ordem de Serviço", "Núcleo da execução técnica, conectado ao cliente, equipamento, contrato e documentos finais.", "Planejamento e execução da O.S.", ["numero", "cliente", "tecnico", "tipo_os", "local_execucao"], { showAmount: true, amountLabel: "Valor da O.S.", dueLabel: "Prazo contratual", contactLabel: "Contato no local", titleLabel: "Descrição resumida da O.S.", titlePlaceholder: "Ex.: Certificação de cabines — Hospital X", groups: [G("Identificação operacional", "Número, cliente, equipe e natureza do atendimento.", ["numero", "cliente", "tecnico", "tipo_os", "local_execucao"]), G("Apontamento de tempo", "Início, fim e duração registrada.", ["inicio", "fim", "tempo_minutos"])] }),
  servicos: P("tecnico", "Serviço executado", "Execução individual ligada à O.S., equipamento, técnico e certificado correspondente.", "Rastreabilidade do serviço", ["cliente", "equipamento", "tecnico", "tipo_servico"], { showAmount: true, amountLabel: "Valor do serviço", dueLabel: "Prazo de entrega técnica", contactLabel: "Contato do cliente" }),
  calibracoes: P("tecnico", "Calibração", "Execução metrológica vinculada à O.S., equipamento, técnico e regra de decisão.", "Dados da calibração", ["os", "equipamento", "tecnico", "data_calibracao", "regra_decisao"], { showDue: false, showAmount: true, amountLabel: "Valor da calibração", contactLabel: "Cliente / laboratório" }),
  certificados: P("tecnico", "Certificado", "Documento técnico controlado, revisado e fundamentado em norma vigente.", "Identificação do certificado", ["numero", "os", "equipamento", "data_emissao", "revisao", "aprovador"], { showDue: false, showAmount: false, contactLabel: "Cliente do certificado", notesLabel: "Escopo, resultados e ressalvas" }),
  laudos_tecnicos: P("tecnico", "Laudo técnico", "Documento conclusivo com método, regra de decisão, responsável e base normativa.", "Elementos técnicos do laudo", ["numero", "os", "cliente", "local_avaliado", "responsavel_tecnico", "data_emissao", "metodo", "regra_decisao", "conclusao"], { showDue: true, dueLabel: "Prazo de emissão", showAmount: false, contactLabel: "Solicitante / cliente", groups: [G("Identificação e responsabilidade", "Documento, origem, local e autoria técnica.", ["numero", "os", "cliente", "local_avaliado", "responsavel_tecnico", "data_emissao"]), G("Fundamentação e conclusão", "Método, decisão de conformidade e conclusão assinável.", ["metodo", "regra_decisao", "conclusao"])] }),
  estudos_tecnicos: P("tecnico", "Estudo técnico", "Estudo fundamentado com objeto, premissas, metodologia e recomendações.", "Estrutura do estudo", ["numero", "cliente", "objeto", "responsavel_tecnico", "data_emissao", "premissas", "metodologia", "recomendacoes"], { showDue: true, dueLabel: "Prazo de entrega", showAmount: false, contactLabel: "Solicitante / cliente", groups: [G("Objeto e responsabilidade", "Identificação, cliente, objeto e autoria técnica.", ["numero", "cliente", "objeto", "responsavel_tecnico", "data_emissao"]), G("Desenvolvimento técnico", "Premissas, método e recomendações resultantes.", ["premissas", "metodologia", "recomendacoes"])] }),
  padroes: P("tecnico", "Padrão metrológico", "Padrão de referência com faixa, validade e cadeia de rastreabilidade.", "Controle do padrão", ["codigo", "tipo", "fabricante", "numero_serie", "faixa_medicao", "proxima_calibracao", "rastreabilidade"], { showDue: false, showContact: false }),
  planilhas_calibracao: P("tecnico", "Planilha de calibração", "Modelo controlado de cálculo e aceitação para uma grandeza e versão definidas.", "Parâmetros da planilha", ["codigo", "grandeza", "versao", "criterio_aceitacao"], { showDue: false, showContact: false, notesLabel: "Fórmulas, validações e restrições de uso" }),

  normas_tecnicas: P("qualidade", "Norma técnica", "Controle a edição aplicável, a licença, a revisão programada e onde cada referência sustenta o trabalho da SECCOL.", "Controle normativo", ["codigo", "organismo", "edicao", "escopo_resumido", "aplicabilidade_seccol", "referencia_oficial", "licenciamento", "verificado_em", "proxima_revisao"], { showDue: false, showContact: false, titleLabel: "Referência normativa", titlePlaceholder: "Ex.: ABNT NBR ISO 14644-1:2015", responsibleLabel: "Responsável pelo controle normativo", groups: [G("Identificação e edição", "Identifique a publicação exata, inclusive emendas e vigência.", ["codigo", "titulo_publicado", "tipo_referencia", "organismo", "edicao", "emenda", "data_publicacao", "vigencia_em"]), G("Aplicabilidade e impacto", "Explique o uso e conecte serviços, ensaios, métodos e documentos no campo de vínculos.", ["escopo_resumido", "aplicabilidade_seccol", "ensaios_base"]), G("Fonte, licença e revisão", "Registre fonte, titularidade, última conferência e próxima revisão.", ["referencia_oficial", "licenciamento", "titular_licenca", "verificado_em", "proxima_revisao", "norma_substituta", "documento_status"])] }),
  qualidade: P("qualidade", "Registro de qualidade", "Controle de requisito, responsável e ação corretiva no sistema de gestão.", "Requisito e tratamento", ["tipo", "norma", "responsavel_qualidade", "acao_corretiva"], { showAmount: false, dueLabel: "Prazo da ação", contactLabel: "Área / processo afetado" }),
  documentos_qualidade: P("qualidade", "Documento controlado", "Documento do sistema de gestão com revisão, elaboração, aprovação e vigência.", "Controle do documento", ["codigo", "tipo", "revisao", "elaborador", "aprovador", "data_vigencia"], { showDue: false, showContact: false }),
  reclamacoes: P("qualidade", "Reclamação", "Manifestação do cliente investigada quanto à procedência, causa e tratativa.", "Análise da reclamação", ["cliente", "canal", "procedente", "causa", "tratativa"], { showAmount: true, amountLabel: "Impacto financeiro", dueLabel: "Prazo de resposta", contactLabel: "Reclamante / contato" }),
  nao_conformidades: P("qualidade", "Não conformidade", "Desvio tratado pela origem, requisito, causa raiz, correção e ação corretiva.", "Tratamento da não conformidade", ["origem", "requisito", "causa_raiz", "correcao", "acao_corretiva"], { showAmount: true, amountLabel: "Custo da não conformidade", dueLabel: "Prazo da ação corretiva", contactLabel: "Área / cliente afetado" }),
  colaboradores: P("qualidade", "Colaborador", "Cadastro funcional, contatos e habilitação para funções técnicas ou comerciais.", "Dados funcionais", ["cpf", "cargo", "setor", "email"], { showDue: false, showContact: false, titleLabel: "Nome completo do colaborador", titlePlaceholder: "Informe o nome completo" }),
  treinamentos: P("qualidade", "Treinamento", "Competência registrada por colaborador, data, validade, carga horária e resultado.", "Evidência de competência", ["colaborador", "competencia", "data", "validade", "resultado"], { showDue: false, showContact: false }),

  frota: P("ativos", "Veículo", "Ficha do veículo com identidade, quilometragem, responsável e vencimento de seguro.", "Identificação e guarda do veículo", ["placa", "veiculo", "renavam", "chassi", "responsavel_veiculo"], { showAmount: true, amountLabel: "Valor do ativo", dueLabel: "Próximo alerta", contactLabel: "Condutor / contato", groups: [G("Identificação veicular", "Placa, modelo e registros oficiais.", ["placa", "veiculo", "renavam", "chassi"]), G("Uso e responsabilidade", "Quilometragem, responsável e seguro.", ["quilometragem", "responsavel_veiculo", "seguro_vencimento"])] }),
  manutencao_frota: P("ativos", "Manutenção de frota", "Intervenção do veículo vinculada a uma oficina cadastrada como fornecedor, com quilometragem e próxima revisão.", "Execução da manutenção", ["placa", "tipo", "quilometragem", "oficina", "data_servico"], { showAmount: true, amountLabel: "Custo da manutenção", dueLabel: "Prazo / próxima revisão", contactLabel: "Responsável na oficina" }),
  produtos: P("ativos", "Produto", "Item comercial com família, origem, classificação fiscal, unidade e preço.", "Ficha técnica e comercial", ["codigo", "familia", "tipo_item", "descricao", "ncm", "unidade", "preco_venda"], { showDue: false, showAmount: false, contactLabel: "Fabricante / fornecedor", groups: [G("Identificação do portfólio", "Código, família, natureza e origem operacional.", ["codigo", "familia", "tipo_item", "origem_operacional", "descricao"]), G("Classificação, preço e custo", "Dados fiscais, unidade, preço comercial e custo interno usado na viabilidade.", ["ncm", "cfop", "unidade", "preco_venda", "custo_referencia", "fonte_oficial"])] }),
  catalogo_servicos: P("ativos", "Serviço de catálogo", "Serviço ou ensaio ofertado pela SECCOL com origem e fonte oficial.", "Ficha do serviço ou ensaio", ["codigo", "categoria", "tipo_servico", "descricao", "fonte_oficial", "verificado_em"], { showDue: false, showAmount: true, amountLabel: "Preço de referência", contactLabel: "Área responsável", groups: [G("Escopo controlado", "Identidade, categoria, descrição e origem do serviço.", ["codigo", "categoria", "tipo_servico", "origem_operacional", "descricao"]), G("Viabilidade e evidência", "Custo direto interno estimado, fonte e data de verificação.", ["custo_referencia", "fonte_oficial", "verificado_em"])] }),
  estoque: P("ativos", "Movimento de estoque", "Movimentação por produto, lote, validade, quantidade e localização.", "Lote e movimentação", ["produto", "lote", "quantidade", "localizacao", "movimento"], { showAmount: true, amountLabel: "Valor do movimento", dueLabel: "Data de validade", contactLabel: "Fornecedor / solicitante" }),

  vendas: P("financeiro", "Venda", "Venda ligada ao cliente, documento, vendedor e condição de pagamento.", "Condições da venda", ["cliente", "documento", "vendedor", "forma_pagamento", "condicao_pagamento"], { showAmount: true, amountLabel: "Valor da venda", dueLabel: "Entrega / vencimento", contactLabel: "Comprador / contato" }),
  fiscal: P("financeiro", "Documento fiscal", "Documento fiscal controlado localmente e preparado para integração homologada.", "Identificação fiscal", ["tipo_nota", "numero", "serie", "chave", "destinatario", "cfop", "finalidade"], { showAmount: true, amountLabel: "Valor da nota", dueLabel: "Data de emissão", contactLabel: "Destinatário / tomador" }),
  contas_pagar: P("financeiro", "Conta a pagar", "Obrigação vinculada a fornecedor. Ao marcar como paga, o sistema gera uma saída de caixa rastreável.", "Classificação e baixa da obrigação", ["fornecedor", "documento", "parcela", "categoria", "centro_custo", "conta", "forma_pagamento", "data_pagamento"], { showAmount: true, amountLabel: "Valor a pagar", dueLabel: "Vencimento", contactLabel: "Fornecedor / beneficiário" }),
  contas_receber: P("financeiro", "Conta a receber", "Crédito vinculado a cliente. Ao marcar como recebido, o sistema gera uma entrada de caixa rastreável.", "Classificação e baixa do recebível", ["cliente", "documento", "parcela", "categoria", "centro_custo", "conta", "forma_pagamento", "data_recebimento"], { showAmount: true, amountLabel: "Valor a receber", dueLabel: "Vencimento", contactLabel: "Cliente / pagador" }),
  boletos: P("financeiro", "Boleto", "Título bancário identificado por cliente, nosso número, conta e remessa.", "Dados bancários do título", ["cliente", "nosso_numero", "banco", "conta", "vencimento_original"], { showAmount: true, amountLabel: "Valor do boleto", dueLabel: "Vencimento atual", contactLabel: "Cliente / pagador" }),
  financeiro: P("financeiro", "Lançamento financeiro", "Receita vinculada a cliente ou despesa vinculada a fornecedor, com conta, categoria, documento e centro de custo.", "Classificação financeira", ["tipo_lancamento", "parceiro", "categoria", "documento", "conta", "centro_custo"], { showAmount: true, amountLabel: "Valor do lançamento", dueLabel: "Vencimento / competência", contactLabel: "Contato da parte relacionada" }),
  caixa: P("financeiro", "Movimento de caixa", "Entrada ou saída vinculada a um cliente ou fornecedor cadastrado, com conta, operador, categoria e forma de pagamento.", "Dados do movimento", ["tipo_movimento", "parceiro", "categoria", "conta", "operador", "forma_pagamento"], { showAmount: true, amountLabel: "Valor movimentado", dueLabel: "Data do movimento", contactLabel: "Contato do pagador / favorecido" }),

  produtividade: P("gestao", "Indicador de produtividade", "Resultado de colaborador em período, indicador e horas registradas.", "Medição de produtividade", ["colaborador", "periodo", "indicador", "resultado"], { showDue: false, showAmount: false, showContact: false }),
  metas: P("gestao", "Meta", "Objetivo mensurável associado a responsável, período, valor-alvo e realizado.", "Parâmetros da meta", ["responsavel_meta", "indicador", "periodo", "meta"], { showDue: false, showAmount: false, showContact: false }),
};

registrationProfiles.clientes_fornecedores = P("administrativo", "Parceiro", "Cadastro único da empresa ou pessoa que se relaciona comercialmente com a SECCOL.", "Identificação do parceiro", ["tipo_cadastro", "tipo_pessoa", "documento", "razao_social"], { showDue: false, titleLabel: "Nome de exibição", titlePlaceholder: "Razão social ou nome do parceiro", contactLabel: "Contato de referência", groups: [G("Identificação e classificação", "Defina se o parceiro é cliente, fornecedor ou os dois.", ["tipo_cadastro", "tipo_pessoa", "documento", "razao_social", "nome_fantasia"]), G("Contato e localização", "Canais e base geográfica do atendimento.", ["telefone", "email", "cep", "cidade"]), G("Comercial e compras", "Políticas, avaliação e liberações operacionais.", ["categoria", "vendedor", "tabela_preco", "avaliacao", "aprovado_faturamento", "aprovado_compras", "bloqueado"])] });

schemas.clientes_fornecedores = [F("tipo_cadastro", "Tipo de cadastro", "select", ["C", "F", "C e F"]), F("tipo_pessoa", "Tipo de pessoa", "select", ["Pessoa jurídica", "Pessoa física"]), F("documento", "CPF/CNPJ"), F("razao_social", "Razão social"), F("nome_fantasia", "Nome fantasia"), F("telefone", "Telefone", "tel"), F("email", "E-mail", "email"), F("cep", "CEP"), F("cidade", "Cidade/UF"), F("categoria", "Categoria"), F("vendedor", "Vendedor"), F("tabela_preco", "Tabela de preços"), F("avaliacao", "Avaliação do fornecedor", "select", ["Pendente", "Aprovado", "Com ressalvas", "Reprovado"]), F("aprovado_faturamento", "Aprovado para faturamento", "checkbox"), F("aprovado_compras", "Aprovado para compras", "checkbox"), F("bloqueado", "Cadastro bloqueado", "checkbox")];

const partyTypeField = schemas.clientes_fornecedores.find((field) => field.key === "tipo_cadastro");
if (partyTypeField) partyTypeField.options = ["Cliente (C)", "Fornecedor (F)", "Cliente e fornecedor (A)"];
schemas.clientes.find((field) => field.key === "tipo_cadastro").options = ["C", "A"];
schemas.fornecedores.find((field) => field.key === "tipo_cadastro").options = ["F", "A"];
if (!schemas.clientes_fornecedores.some((field) => field.key === "codigo_cadastro")) {
  schemas.clientes_fornecedores.splice(1, 0, F("codigo_cadastro", "Código", "text"));
}
registrationProfiles.clientes_fornecedores.description = "Cadastro único de parceiros: cliente, fornecedor ou ambos.";
registrationProfiles.contas_pagar.description = "Obrigação financeira vinculada a fornecedor (F) ou parceiro que também é fornecedor (A).";
registrationProfiles.contas_receber.description = "Crédito financeiro vinculado a cliente (C) ou parceiro que também é cliente (A).";
registrationProfiles.clientes_fornecedores.groups[0].keys = ["documento", "tipo_pessoa", "tipo_cadastro", "codigo_cadastro", "razao_social", "nome_fantasia"];

if (!schemas.clientes_fornecedores.some((field) => field.key === "logradouro")) {
  const cepIndex = schemas.clientes_fornecedores.findIndex((field) => field.key === "cep");
  schemas.clientes_fornecedores.splice(cepIndex + 1, 0,
    F("logradouro", "Logradouro"), F("numero_endereco", "Número"),
    F("complemento_endereco", "Complemento"), F("bairro", "Bairro"),
    F("codigo_ibge", "Código IBGE do município"), F("uf", "UF"),
    F("indicador_ie", "Situação da inscrição estadual", "select", [
      "Selecione", "1 - Contribuinte com IE", "2 - Contribuinte isento", "9 - Não contribuinte",
    ]), F("inscricao_estadual", "Inscrição estadual"));
}
registrationProfiles.clientes_fornecedores.groups[1].keys = ["telefone", "email", "cep", "logradouro", "numero_endereco", "complemento_endereco", "bairro", "cidade", "codigo_ibge", "uf", "indicador_ie", "inscricao_estadual"];

function getRecordProfile(module) {
  const base = registrationProfiles[module] || P("gestao", state.modules[module] || "Registro", "Cadastro operacional conectado ao fluxo da empresa.", "Dados específicos");
  return { ...formDomains[base.domain], ...base };
}

const kanbanModules = new Set(["crm", "propostas", "licitacoes", "chamados", "ordens_servico"]);
const specialScreens = new Set(["dashboard", "portfolio", "settings", "control_center", "whatsapp", "editais", "fontes", "assuntos", "aprovacoes", "importacoes_xml", "estoque", "fiscal", "rh", "relatorios", "calibracoes", "mobile", "normas_tecnicas", "concorrentes"]);
const normativeModules = new Set(["certificados", "laudos_tecnicos", "estudos_tecnicos"]);
// A tabela deixa de ser uma lista genérica: cada domínio escolhe os dados que
// orientam sua decisão. Os módulos sem regra explícita usam os primeiros campos
// próprios do schema, mantendo a interface útil quando novos cadastros surgirem.
const moduleViewSpecs = {
  clientes_fornecedores: { columns: ["codigo_cadastro", "tipo_cadastro", "documento", "cidade"], description: "Base única de parceiros. Identifique CPF/CNPJ, papel comercial e localização antes de usar o cadastro em vendas, compras ou financeiro.", action: "Cadastrar parceiro" },
  contatos: { columns: ["cliente_fornecedor", "tipo_contato", "cargo", "telefone"], description: "Pessoas vinculadas a um parceiro, com cargo e canais de comunicação." },
  crm: { columns: ["origem", "telefone", "localizacao", "proximo_passo"], description: "Oportunidades em acompanhamento, incluindo os novos leads recebidos pelo site.", action: "Nova oportunidade" },
  propostas: { columns: ["numero", "cliente", "validade", "etapa"], description: "Propostas comerciais controladas por cliente, validade e etapa de negociação.", action: "Nova proposta" },
  contratos: { columns: ["numero", "cliente", "gestor", "fim"], description: "Contratos ativos, responsáveis e datas de vigência para renovação e execução." },
  licitacoes: { columns: ["edital", "orgao", "modalidade", "data_abertura"], description: "Processos licitatórios em análise, proposta, disputa ou homologação.", action: "Nova licitação" },
  solicitacoes_compra: { columns: ["numero", "solicitante", "prioridade", "centro_custo"], description: "Demandas internas aguardando análise e aprovação de compra." },
  pedidos_compra: { columns: ["numero", "fornecedor", "condicao_pagamento", "centro_custo"], description: "Pedidos emitidos para fornecedores, com recebimento e condição de pagamento." },
  contas_pagar: { columns: ["tipo_parte", "fornecedor", "categoria", "centro_custo"], description: "Obrigações financeiras vinculadas somente a fornecedor ou parceiro do tipo ambos.", action: "Nova conta a pagar" },
  contas_receber: { columns: ["tipo_parte", "cliente", "categoria", "centro_custo"], description: "Recebíveis vinculados somente a cliente ou parceiro do tipo ambos.", action: "Nova conta a receber" },
  equipamentos: { columns: ["cliente", "tipo", "fabricante", "numero_serie"], description: "Equipamentos de clientes, identificados para atendimento, serviço e rastreabilidade." },
  chamados: { columns: ["cliente", "tipo", "prioridade", "equipamento"], description: "Chamados de atendimento classificados por cliente, prioridade e equipamento." },
  agendamentos: { columns: ["cliente", "tecnico", "data", "hora"], description: "Agenda operacional com cliente, técnico, data, horário e local." },
  ordens_servico: { columns: ["numero", "cliente", "tecnico", "tipo_os"], description: "Ordens de serviço que conectam execução em campo, responsável e situação operacional.", action: "Nova ordem de serviço" },
  servicos: { columns: ["cliente", "equipamento", "tecnico", "tipo_servico"], description: "Serviços executados e vinculados ao equipamento, técnico e evidências." },
  calibracoes: { columns: ["os", "equipamento", "tecnico", "proxima_calibracao"], description: "Controle metrológico por equipamento, ordem de serviço, técnico e próxima calibração." },
  certificados: { columns: ["numero", "os", "equipamento", "data_emissao"], description: "Certificados controlados com vínculo obrigatório à base normativa e aprovação." },
  produtos: { columns: ["codigo", "familia", "unidade", "preco_venda"], description: "Produtos aprovados para catálogo, estoque e composição comercial." },
  catalogo_servicos: { columns: ["codigo", "categoria", "tipo_servico", "verificado_em"], description: "Serviços e ensaios aprovados para propostas, contratos e execução." },
  estoque: { columns: ["produto", "lote", "quantidade", "localizacao"], description: "Saldos e lotes para disponibilidade operacional e rastreabilidade." },
  vendas: { columns: ["documento", "cliente", "vendedor", "condicao_pagamento"], description: "Vendas vinculadas a cliente, vendedor e condição comercial aprovada." },
  fiscal: { columns: ["tipo_nota", "numero", "chave", "destinatario"], description: "Documentos fiscais locais preparados para o futuro motor fiscal próprio e versionado." },
  colaboradores: { columns: ["cpf", "cargo", "setor", "telefone"], description: "Colaboradores, cargo, setor e contato para atribuições internas." },
  treinamentos: { columns: ["colaborador", "competencia", "data", "validade"], description: "Capacitações e vencimentos para competência da equipe." },
  frota: { columns: ["placa", "veiculo", "responsavel_veiculo", "seguro_vencimento"], description: "Veículos e prazos de manutenção da operação." },
  manutencao_frota: { columns: ["placa", "tipo", "proxima_km", "data_servico"], description: "Manutenções da frota por veículo, tipo e próximo controle." },
};
const defaultStatuses = ["Ativo", "Em andamento", "Pendente", "A revisar", "Aprovado", "Pago", "Concluído", "Cancelado"];
const moduleStatuses = {
  crm: ["Novo lead", "Contato realizado", "Qualificado", "Proposta", "Negociação", "Ganho", "Perdido"],
  propostas: ["Rascunho", "Enviada", "Em negociação", "Aprovada", "Recusada"],
  licitacoes: ["Captação", "Análise", "Documentação", "Proposta enviada", "Disputa", "Habilitação", "Homologada", "Perdida"],
  chamados: ["Aberto", "Em atendimento", "Aguardando cliente", "Concluído", "Cancelado"],
  ordens_servico: ["Aberta", "Agendada", "Em execução", "Pausada", "Aguardando aprovação", "Concluída", "Cancelada"],
  solicitacoes_compra: ["Rascunho", "Pendente de aprovação", "Aprovada", "Rejeitada", "Convertida em pedido"],
  pedidos_compra: ["Rascunho", "Emitido", "Aguardando fornecedor", "Recebido parcial", "Recebido", "Cancelado"],
  vendas: ["Rascunho", "Confirmado", "Separação", "Faturado", "Concluído", "Cancelado"],
  contas_pagar: ["Em aberto", "Parcial", "Parcelado", "Pago", "Vencido", "Cancelado"],
  contas_receber: ["Em aberto", "Parcial", "Parcelado", "Recebido", "Vencido", "Cancelado"],
  certificados: ["Rascunho", "Em revisão", "Aguardando aprovação", "Aprovado", "Publicado", "Obsoleto"],
  laudos_tecnicos: ["Rascunho", "Em revisão", "Aguardando aprovação", "Aprovado", "Emitido", "Obsoleto"],
  estudos_tecnicos: ["Rascunho", "Em revisão", "Aguardando aprovação", "Aprovado", "Emitido", "Obsoleto"],
  normas_tecnicas: ["Publicada", "Publicada — em revisão sistemática", "Publicada — revisão em desenvolvimento", "Vigente", "Substituída", "Obsoleta"],
  documentos_qualidade: ["Rascunho", "Em revisão", "Aguardando aprovação", "Vigente", "Obsoleto"],
  fiscal: ["Rascunho", "Registrado localmente", "Aguardando processamento fiscal", "Autorizado", "Rejeitado", "Cancelado"],
  importacoes_xml: ["Importada", "Validada", "Rejeitada"],
};

// Ajuda contextual curta: explica o propósito do campo no momento da decisão,
// sem obrigar quem já domina o processo a ler instruções desnecessárias.
const fieldHelp = {
  // Ajuda compartilhada pelos formulários: termos técnicos recorrentes ganham
  // uma explicação curta no ponto em que a pessoa precisa tomar uma decisão.
  status: "Mostra em que ponto este registro está. Atualize-o somente quando a etapa realmente mudar, para que as próximas ações e os avisos permaneçam corretos.",
  situacao: "Indica se o cadastro pode ser usado agora. Use uma situação estruturada em vez de explicar o estado apenas nas observações.",
  responsavel: "Escolha quem acompanha ou executa esta atividade. Isso não amplia permissões de acesso da pessoa escolhida.",
  prazo: "Informe a data combinada ou publicada. Se ela mudar, atualize o prazo e registre o motivo para evitar alertas incorretos.",
  prioridade: "Use para ordenar o trabalho pelo impacto e urgência. Não substitui um prazo ou uma decisão registrada.",
  justificativa: "Explique o motivo da escolha de forma objetiva. Evite inserir senhas, chaves, documentos pessoais ou outros dados sensíveis.",
  ncm: "Código fiscal que identifica a mercadoria. Use a classificação validada pela área fiscal; não escolha por aproximação.",
  cfop: "Código que descreve a operação fiscal de entrada ou saída. Confirme-o com a operação real e a orientação fiscal da empresa.",
  cst: "Código de situação tributária. Ele define como o imposto será tratado e deve vir da regra fiscal vigente.",
  csosn: "Código tributário usado por empresas do Simples Nacional. Confirme a regra aplicável antes de salvar.",
  "normas_tecnicas.codigo": "Use o código oficial do organismo emissor. Não crie um código interno para substituir a referência publicada.",
  "normas_tecnicas.titulo_publicado": "Informe o título oficial quando ele acrescentar informação ao código. Se o código já trouxer o título completo, não repita o texto.",
  "normas_tecnicas.tipo_referencia": "Classifique a origem: norma, regulamento, método ou guia. Isso evita tratar uma obrigação legal como se fosse uma norma técnica.",
  "normas_tecnicas.edicao": "Informe a edição aplicável exatamente como publicada. Emendas, erratas e corrigendas ficam no próximo campo.",
  "normas_tecnicas.emenda": "Registre somente a emenda, errata ou corrigenda que realmente altere a edição em uso. Deixe em branco quando não houver.",
  "normas_tecnicas.vigencia_em": "Preencha quando a própria referência ou contrato determinar uma data de vigência. Não confunda com a data em que ela foi verificada.",
  "normas_tecnicas.escopo_resumido": "Escreva um resumo autoral do que a referência cobre. Não copie conteúdo protegido sem autorização.",
  "normas_tecnicas.aplicabilidade_seccol": "Explique onde a SECCOL usa a referência. Depois conecte os serviços, ensaios ou documentos na seção de vínculos.",
  "normas_tecnicas.ensaios_base": "Liste ensaios ou controles em linguagem de trabalho. Para rastreabilidade, relacione também os cadastros correspondentes.",
  "normas_tecnicas.referencia_oficial": "Cole a página oficial do organismo emissor para conferir edição, alterações e situação editorial.",
  "normas_tecnicas.licenciamento": "Indique se o acesso é público ou comercial/licenciado. Referência comercial exige cópia licenciada confirmada antes da emissão final.",
  "normas_tecnicas.titular_licenca": "Informe empresa, área ou contrato que autoriza o acesso. Nunca coloque senha, chave ou outro dado sensível.",
  "normas_tecnicas.verificado_em": "É a data da última conferência na fonte oficial. Ela registra o passado; programe a próxima revisão separadamente.",
  "normas_tecnicas.proxima_revisao": "Defina quando a vigência deve ser conferida novamente. A aba sinaliza a revisão vencida.",
  "normas_tecnicas.norma_substituta": "Use apenas quando esta edição deixou de ser aplicável. Selecione a nova referência e marque a atual como Substituída para manter o histórico.",
};

function fieldHelpMarkup(key, label, module) {
  const message = fieldHelp[`${module}.${key}`] || fieldHelp[key];
  if (!message) return label;
  const id = `fieldHelp-${module}-${key}`.replace(/[^a-zA-Z0-9_-]/g, "");
  return `${label}<button type="button" class="field-help-trigger" aria-label="Como preencher este campo" aria-expanded="false" aria-controls="${id}" data-field-help="${id}">!</button><small id="${id}" class="field-help hidden">${escapeHTML(message)}</small>`;
}

function bindFieldHelp() {
  $$('[data-field-help]').forEach((button) => {
    if (button.dataset.boundHelp) return;
    button.dataset.boundHelp = "true";
    button.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      const detail = document.getElementById(button.dataset.fieldHelp);
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      detail?.classList.toggle("hidden", expanded);
    };
  });
}
const moduleStatusTransitions = {
  licitacoes: {
    "Captação": ["Análise", "Perdida"], Análise: ["Documentação", "Perdida"],
    Documentação: ["Proposta enviada", "Perdida"],
    "Proposta enviada": ["Disputa", "Habilitação", "Perdida"],
    Disputa: ["Habilitação", "Perdida"], Habilitação: ["Homologada", "Perdida"],
    Homologada: [], Perdida: [],
  },
  propostas: {
    Rascunho: ["Enviada", "Recusada"], Enviada: ["Rascunho", "Em negociação", "Aprovada", "Recusada"],
    "Em negociação": ["Enviada", "Aprovada", "Recusada"], Aprovada: [], Recusada: ["Rascunho"],
  },
  solicitacoes_compra: {
    Rascunho: ["Pendente de aprovação"], "Pendente de aprovação": ["Aprovada", "Rejeitada"],
    Aprovada: ["Convertida em pedido"], Rejeitada: ["Rascunho"], "Convertida em pedido": [],
  },
  pedidos_compra: {
    Rascunho: ["Emitido", "Cancelado"], Emitido: ["Aguardando fornecedor", "Recebido parcial", "Recebido", "Cancelado"],
    "Aguardando fornecedor": ["Recebido parcial", "Recebido", "Cancelado"], "Recebido parcial": ["Recebido"], Recebido: [], Cancelado: [],
  },
  vendas: {
    Rascunho: ["Confirmado", "Cancelado"], Confirmado: ["Separação", "Cancelado"],
    Separação: ["Faturado", "Cancelado"], Faturado: ["Concluído"], Concluído: [], Cancelado: [],
  },
  ordens_servico: {
    Aberta: ["Agendada", "Em execução", "Cancelada"], Agendada: ["Em execução", "Cancelada"],
    "Em execução": ["Pausada", "Aguardando aprovação", "Concluída"], Pausada: ["Em execução", "Cancelada"],
    "Aguardando aprovação": ["Em execução", "Concluída"], Concluída: [], Cancelada: [],
  },
  contas_pagar: {
    "Em aberto": ["Pago", "Vencido", "Cancelado"],
    Parcial: ["Pago", "Vencido", "Cancelado"],
    Vencido: ["Pago", "Cancelado"], Parcelado: [], Pago: [], Cancelado: [],
  },
  contas_receber: {
    "Em aberto": ["Recebido", "Vencido", "Cancelado"],
    Parcial: ["Recebido", "Vencido", "Cancelado"],
    Vencido: ["Recebido", "Cancelado"], Parcelado: [], Recebido: [], Cancelado: [],
  },
};

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.remove("hidden");
  clearTimeout(element.timer);
  element.timer = setTimeout(() => element.classList.add("hidden"), 3400);
}

const PWA_UPDATE_CHECK_MS = 15 * 60 * 1000;

function setSystemUpdateStatus(message, visible = false) {
  const status = $("#systemUpdateStatus");
  if (!status) return;
  status.title = message;
  if (visible) status.textContent = message;
}

function setSystemServerAddress() {
  const address = $("#systemServerAddress");
  if (!address) return;
  address.textContent = `Servidor: ${window.location.host || "local"}`;
  address.title = window.location.origin || "Servidor local";
}

async function registerAutomaticUpdates() {
  if (!("serviceWorker" in navigator)) {
    setSystemUpdateStatus("Atualização automática indisponível neste navegador", true);
    return;
  }
  let reloadingForUpdate = false;
  const hadController = Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloadingForUpdate || !hadController) return;
    reloadingForUpdate = true;
    setSystemUpdateStatus("Nova versão instalada; atualizando…", true);
    toast("Nova versão instalada. O sistema será atualizado agora.");
    window.setTimeout(() => window.location.reload(), 1200);
  });
  try {
    const registration = await navigator.serviceWorker.register("/service-worker.js");
    const checkForUpdate = () => registration.update().catch(() => {});
    checkForUpdate();
    window.setInterval(checkForUpdate, PWA_UPDATE_CHECK_MS);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") checkForUpdate();
    });
    setSystemUpdateStatus("Atualização automática ativa");
  } catch {
    setSystemUpdateStatus("Não foi possível verificar atualizações", true);
  }
}

let assistantHistory = [];
let assistantConversationId = null;
let assistantReturnFocus = null;
let assistantPending = false;
let assistantRequestController = null;
let assistantLastQuestion = "";
let assistantCapabilities = { aiConfigured: false };

function assistantContextSnapshot() {
  const dialog = $("#recordDialog");
  if (dialog?.open && state.currentRecord) {
    return {
      module: state.currentRecord.module,
      recordId: Number(state.currentRecord.id),
      title: state.currentRecord.title,
    };
  }
  return state.readableModules.has(state.screen) ? { module: state.screen } : {};
}

function updateAssistantContextUI() {
  const context = assistantContextSnapshot();
  const label = context.recordId ? context.title : screenLabel(context.module || state.screen || "dashboard");
  $("#assistantContextLabel").textContent = label || "Painel executivo";
  $("#assistantContextDetail").textContent = context.recordId
    ? `Cadastro aberto · ${screenLabel(context.module)}`
    : "A resposta considerará esta área e suas permissões.";
  $("#assistantScope").textContent = `Empresa ativa · ${label || "dados autorizados"}`;
}

function setAssistantOpen(open, trigger = null) {
  const panel = $("#assistantPanel");
  if (!panel) return;
  const wasOpen = panel.classList.contains("open");
  if (open && !wasOpen) assistantReturnFocus = trigger || document.activeElement;
  panel.classList.toggle("open", open);
  panel.setAttribute("aria-hidden", String(!open));
  panel.inert = !open;
  $("#assistantScrim").classList.toggle("open", open);
  $("#assistantScrim").setAttribute("aria-hidden", String(!open));
  document.body.classList.toggle("assistant-is-open", open);
  [$("#assistantButton"), $("#assistantRailButton")].forEach((button) => {
    button?.setAttribute("aria-expanded", String(open));
  });
  if (open) {
    updateAssistantContextUI();
    requestAnimationFrame(() => $("#assistantInput")?.focus());
  } else if (wasOpen) {
    assistantRequestController?.abort();
    if (assistantReturnFocus?.isConnected) requestAnimationFrame(() => assistantReturnFocus.focus());
  }
}

function assistantWelcomeElement() {
  const welcome = document.createElement("div");
  welcome.className = "assistant-welcome";
  welcome.innerHTML = '<span class="assistant-welcome-icon" aria-hidden="true">✦</span><div><strong>Qual é a próxima decisão?</strong><p>Use uma opção abaixo ou descreva a situação. A resposta considera somente a empresa e as permissões ativas.</p></div>';
  return welcome;
}

function assistantStartGridElement() {
  const grid = document.createElement("div");
  grid.className = "assistant-start-grid";
  grid.setAttribute("aria-label", "Atalhos para começar");
  [
    ["Quais são minhas prioridades agora?", "1", "Ver prioridades", "O que exige atenção agora"],
    ["Resuma este registro e diga o que preciso fazer em seguida.", "2", "Entender este cadastro", "Resumo e próximo passo"],
    ["Como usar esta área do sistema?", "3", "Aprender esta área", "Orientação objetiva de uso"],
  ].forEach(([question, number, title, detail]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.innerHTML = `<span aria-hidden="true">${number}</span><strong>${title}</strong><small>${detail}</small>`;
    button.onclick = () => void askAssistant(question);
    grid.appendChild(button);
  });
  return grid;
}

function resetAssistantConversation(announce = true) {
  assistantRequestController?.abort();
  assistantHistory = [];
  assistantConversationId = null;
  assistantLastQuestion = "";
  const messages = $("#assistantMessages");
  messages.replaceChildren(assistantWelcomeElement(), assistantStartGridElement());
  if (announce) $("#assistantNotice").textContent = "Nova conversa iniciada. A IA sugere; o servidor valida.";
  $("#assistantInput").value = "";
  updateAssistantContextUI();
}

function setAssistantPending(pending) {
  assistantPending = pending;
  const panel = $("#assistantPanel");
  const button = $("#assistantForm button[type=submit]");
  panel?.setAttribute("aria-busy", String(pending));
  button.disabled = pending;
  $("#assistantSendLabel").textContent = pending ? "Analisando" : "Enviar";
  $("#assistantRailStatus").textContent = pending ? "Analisando…" : "Pronto para ajudar";
}

async function openAssistantSource(source) {
  if (source.module === "ajuda") return;
  setAssistantOpen(false);
  if (String(source.id).startsWith("tender:")) {
    await navigate("editais");
    return;
  }
  const recordId = Number(source.id);
  if (recordId > 0) await openRecordById(recordId);
}

function assistantSourceElement(source) {
  const actionable = source.module !== "ajuda";
  const element = document.createElement(actionable ? "button" : "div");
  element.className = "assistant-source";
  if (actionable) element.type = "button";
  const icon = document.createElement("span");
  icon.className = "assistant-source-icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = source.module === "ajuda" ? "?" : (icons[source.module] || "◆");
  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = source.title;
  const module = document.createElement("small");
  module.textContent = source.module === "ajuda" ? "Orientação do sistema" : screenLabel(source.module);
  copy.append(title, module);
  element.append(icon, copy);
  if (actionable) {
    const arrow = document.createElement("span");
    arrow.className = "assistant-source-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";
    element.appendChild(arrow);
    element.onclick = () => void openAssistantSource(source);
  }
  return element;
}

function appendAssistantMessage(text, kind = "assistant", options = {}) {
  const messages = $("#assistantMessages");
  const element = document.createElement("div");
  element.className = `assistant-message ${kind}${options.error ? " is-error" : ""}`;
  const copy = document.createElement("div");
  copy.textContent = text;
  element.appendChild(copy);
  if (options.meta) {
    const detail = document.createElement("small");
    detail.className = "assistant-meta";
    detail.textContent = options.meta;
    element.appendChild(detail);
  }
  if (options.sources?.length) {
    const sourceArea = document.createElement("div");
    sourceArea.className = "assistant-message-sources";
    const label = document.createElement("span");
    label.textContent = options.sources.length === 1 ? "Fonte utilizada" : "Fontes utilizadas";
    sourceArea.appendChild(label);
    options.sources.slice(0, 5).forEach((source) => sourceArea.appendChild(assistantSourceElement(source)));
    element.appendChild(sourceArea);
  }
  if (options.suggestions?.length) {
    const followups = document.createElement("div");
    followups.className = "assistant-followups";
    options.suggestions.slice(0, 3).forEach((suggestion) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "assistant-followup";
      button.textContent = suggestion;
      button.onclick = () => void askAssistant(suggestion);
      followups.appendChild(button);
    });
    element.appendChild(followups);
  }
  if (options.retryQuestion) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "assistant-retry";
    retry.textContent = "Tentar novamente";
    retry.onclick = () => void askAssistant(options.retryQuestion);
    element.appendChild(retry);
  }
  messages.appendChild(element);
  while (messages.children.length > 40) messages.children[0].remove();
  messages.scrollTop = messages.scrollHeight;
  return element;
}

function appendAssistantLoading() {
  const element = document.createElement("div");
  element.className = "assistant-message assistant-loading";
  element.setAttribute("role", "status");
  element.setAttribute("aria-label", "Assistente analisando");
  element.innerHTML = '<i aria-hidden="true"></i><i aria-hidden="true"></i><i aria-hidden="true"></i>';
  $("#assistantMessages").appendChild(element);
  $("#assistantMessages").scrollTop = $("#assistantMessages").scrollHeight;
  return element;
}

async function askAssistant(question) {
  const trimmed = String(question || "").trim();
  if (!trimmed || assistantPending) return;
  const input = $("#assistantInput");
  appendAssistantMessage(trimmed, "user");
  assistantHistory.push({ role: "user", content: trimmed });
  assistantLastQuestion = trimmed;
  input.value = "";
  input.style.height = "";
  setAssistantPending(true);
  $("#assistantNotice").textContent = "Consultando somente dados autorizados…";
  const loading = appendAssistantLoading();
  const controller = new AbortController();
  assistantRequestController = controller;
  const timeout = window.setTimeout(() => controller.abort(), 50000);
  try {
    const result = await api("/api/assistant/query", {
      method: "POST",
      signal: controller.signal,
      body: JSON.stringify({
        question: trimmed,
        context: assistantContextSnapshot(),
        conversation_id: assistantConversationId,
      }),
    });
    loading.remove();
    assistantConversationId = result.conversationId || assistantConversationId;
    const answer = result.answer || "Não encontrei dados suficientes.";
    assistantHistory.push({ role: "assistant", content: answer });
    const sourceCount = result.sources?.length || 0;
    appendAssistantMessage(answer, "assistant", {
      meta: result.notice || `${sourceCount} fonte(s) verificadas · confiança ${result.confidence || "não informada"}`,
      sources: result.sources || [],
      suggestions: result.suggestions || [],
    });
    $("#assistantNotice").textContent = result.notice || "Resposta baseada nos dados e orientações autorizados do sistema.";
  } catch (failure) {
    loading.remove();
    const wasTimeout = failure?.name === "AbortError";
    const message = wasTimeout
      ? "A consulta demorou mais do que o esperado. Sua pergunta foi preservada para uma nova tentativa."
      : (failure.message || "Não foi possível concluir a consulta.");
    appendAssistantMessage(message, "assistant", { error: true, retryQuestion: assistantLastQuestion });
    input.value = assistantLastQuestion;
    input.style.height = "";
    $("#assistantNotice").textContent = wasTimeout ? "Tempo de resposta excedido. Tente novamente." : "A consulta falhou. Revise a conexão e tente novamente.";
  } finally {
    window.clearTimeout(timeout);
    if (assistantRequestController === controller) assistantRequestController = null;
    setAssistantPending(false);
    if ($("#assistantPanel")?.classList.contains("open")) input.focus();
  }
}

async function refreshAssistantCapabilities() {
  try {
    assistantCapabilities = await api("/api/assistant/capabilities");
  } catch {
    assistantCapabilities = { aiConfigured: false };
  }
}

function initializeAssistant() {
  const openFrom = (event) => setAssistantOpen(true, event.currentTarget);
  $("#assistantButton").onclick = openFrom;
  $("#assistantRailButton").onclick = openFrom;
  $("#assistantClose").onclick = () => setAssistantOpen(false);
  $("#assistantScrim").onclick = () => setAssistantOpen(false);
  $("#assistantReset").onclick = () => { resetAssistantConversation(); $("#assistantInput").focus(); };
  $("#assistantForm").onsubmit = (event) => { event.preventDefault(); void askAssistant($("#assistantInput").value); };
  $("#assistantInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      $("#assistantForm").requestSubmit();
    }
  });
  $("#assistantInput").addEventListener("input", (event) => {
    const input = event.currentTarget;
    input.style.height = "";
    input.style.height = `${Math.min(input.scrollHeight, 130)}px`;
  });
  $$('[data-assistant-question]').forEach((button) => {
    button.onclick = () => { setAssistantOpen(true, button); void askAssistant(button.dataset.assistantQuestion); };
  });
  $("#recordDialog")?.addEventListener("close", updateAssistantContextUI);
  document.addEventListener("keydown", (event) => {
    const panel = $("#assistantPanel");
    if (!panel?.classList.contains("open")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      setAssistantOpen(false);
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = $$('button:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])')
      .filter((element) => panel.contains(element) && !element.hidden);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

const api = window.SIVSCore.createApiClient({
  getCsrf: () => state.csrf,
  onUnauthorized: () => showAuth(false),
});

function isWritable(module) {
  return state.writableModules.has(module);
}

function loadingStateHTML(message, detail = "Isso deve levar apenas alguns instantes.") {
  return `<div class="loading-state" role="status" aria-live="polite"><span class="loading-spinner" aria-hidden="true"></span><div><strong>${escapeHTML(message)}</strong><small>${escapeHTML(detail)}</small></div><div class="loading-lines" aria-hidden="true"><i></i><i></i><i></i></div></div>`;
}

function canAction(module, action) {
  return (state.actionPermissions[module] || []).includes(action);
}

async function bootstrap() {
  setSystemServerAddress();
  const status = await api("/api/status");
  state.authSetupAvailable = !status.configured;
  try {
    const me = await api("/api/me");
    await startApp(me);
  } catch {
    showAuth(!status.configured);
  }
  const resetToken = new URLSearchParams(window.location.search).get("reset_token");
  if (resetToken) openPasswordRecovery(resetToken);
  void registerAutomaticUpdates();
}

function showAuth(setup) {
  const setupMode = Boolean(setup && state.authSetupAvailable);
  document.body.classList.remove("is-authenticated");
  $("#app").classList.add("hidden");
  $("#auth").classList.remove("hidden");
  $("#authForm").dataset.mode = setupMode ? "setup" : "login";
  $("#companyField").classList.toggle("hidden", !setupMode);
  $("#nameField").classList.toggle("hidden", !setupMode);
  $("#authForm [name=company]").required = setupMode;
  $("#authForm [name=name]").required = setupMode;
  $("#authEyebrow").textContent = setupMode ? "PRIMEIRA CONFIGURAÇÃO" : "ACESSO SEGURO";
  $("#authTitle").textContent = setupMode ? "Prepare o Sistema Seccol" : "Entrar no Sistema Seccol";
  $("#authSubtitle").textContent = setupMode ? "Crie a empresa e o administrador inicial." : "Use seu e-mail e sua senha cadastrados.";
  $("#authButtonText").textContent = setupMode ? "Criar sistema" : "Entrar";
  $("#authForm [name=password]").autocomplete = setupMode ? "new-password" : "current-password";
  $("#authError").classList.add("hidden");
  $("#forgotPasswordButton").classList.toggle("hidden", setupMode);
  $("#authModeSwitch").classList.toggle("hidden", !state.authSetupAvailable);
  $("#authModePrompt").textContent = setupMode ? "Já possui um acesso?" : "Primeiro acesso neste servidor?";
  $("#authModeToggle").textContent = setupMode ? "Entrar" : "Configurar agora";
}

async function submitAuth(event) {
  event.preventDefault();
  const mode = event.currentTarget.dataset.mode;
  const body = Object.fromEntries(new FormData(event.currentTarget));
  const error = $("#authError");
  error.classList.add("hidden");
  try {
    const data = await api(mode === "setup" ? "/api/setup" : "/api/login", {
      method: "POST", body: JSON.stringify(body),
    });
    if (mode === "setup") state.authSetupAvailable = false;
    await startApp(data);
  } catch (failure) {
    if (failure.code === "already_configured") {
      state.authSetupAvailable = false;
      showAuth(false);
      error.textContent = "Este sistema já foi configurado. Entre com seu e-mail e senha.";
      error.classList.remove("hidden");
      return;
    }
    error.textContent = failure.message;
    error.classList.remove("hidden");
  }
}

async function startApp(data) {
  state.user = data.user;
  state.csrf = data.csrfToken;
  state.relationOptions = [];
  state.partyOptions = [];
  state.financialCategories = [];
  state.capabilities = data.capabilities || {};
  document.body.classList.add("is-authenticated");
  $("#auth").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#userName").textContent = state.user.name;
  $("#userRole").textContent = roleLabels[state.user.role] || state.user.role;
  $("#userInitials").textContent = state.user.name.split(/\s+/).slice(0, 2).map((item) => item[0]).join("").toUpperCase();
  renderCompanySelector();
  const [moduleData] = await Promise.all([api("/api/modules"), refreshNotifications()]);
  state.modules = moduleData.modules;
  state.readableModules = new Set(moduleData.readableModules || Object.keys(moduleData.modules || {}));
  state.writableModules = new Set(moduleData.writableModules || []);
  state.exportableModules = new Set(moduleData.exportableModules || []);
  state.actionPermissions = moduleData.actionPermissions || {};
  state.capabilities = moduleData.capabilities || state.capabilities;
  const assistantHidden = state.readableModules.size === 0;
  $("#assistantButton")?.classList.toggle("hidden", assistantHidden);
  $("#assistantRailButton")?.classList.toggle("hidden", assistantHidden);
  resetAssistantConversation(false);
  void refreshAssistantCapabilities();
  preferences.configure(state.user.id, state.user.companyId);
  drafts.configure(state.user.id, state.user.companyId);
  renderNav();
  ui.workspaceTabs?.configure({
    container: $("#workspaceTabs"), preferences, navigate, canAccess: canAccessScreen,
    label: screenLabel, icon: (screen) => icons[screen] || "•", escape: escapeHTML,
  });
  ui.commandPalette?.configure({
    screens: screenCatalog,
    canAccess: canAccessScreen,
    icon: (screen) => icons[screen] || "•",
    label: screenLabel,
    navigate,
    openRecord: openRecordById,
    search: async (query, signal) => (await api(`/api/search?q=${encodeURIComponent(query)}`, { signal })).items,
    onPreferencesChanged: refreshQuickAccess,
  });
  const directScreenRoutes = { "/controle": "control_center" };
  const requestedScreen = directScreenRoutes[window.location.pathname.replace(/\/$/, "") || "/"]
    || new URLSearchParams(window.location.search).get("screen");
  await navigate(requestedScreen && canAccessScreen(requestedScreen) ? requestedScreen : "dashboard");
}

function renderCompanySelector() {
  const select = $("#companySelect");
  select.innerHTML = (state.user.companies || []).map((company) =>
    `<option value="${company.id}" ${company.id === state.user.companyId ? "selected" : ""}>${escapeHTML(company.name)}</option>`
  ).join("");
  $(".company-switch").classList.toggle("single-company", (state.user.companies || []).length < 2);
}

async function switchCompany(companyId) {
  if (Number(companyId) === state.user.companyId) return;
  try {
    await api("/api/company/switch", { method: "POST", body: JSON.stringify({ company_id: Number(companyId) }) });
    const me = await api("/api/me");
    toast("Empresa alterada com isolamento de dados aplicado.");
    await startApp(me);
  } catch (failure) {
    toast(failure.message);
    renderCompanySelector();
  }
}

function renderNav() {
  const collapsedGroups = new Set(preferences.collapsedNavGroups?.() || []);
  $("#nav").innerHTML = sections.map(([title, links], groupId) => ({
    title, groupId, links: links.filter(([key]) => canAccessScreen(key)),
  }))
    .filter(({ links }) => links.length)
    .map(({ title, links, groupId }) => `
    <section class="nav-group" aria-labelledby="nav-group-${groupId}">
      <h2 class="nav-group-heading" id="nav-group-${groupId}"><button type="button" class="nav-group-toggle" data-nav-group-toggle="${groupId}" aria-expanded="${!collapsedGroups.has(String(groupId))}" aria-controls="nav-group-links-${groupId}"><span class="nav-group-title">${title}</span><span class="nav-group-chevron" aria-hidden="true">⌄</span></button></h2>
      <div class="nav-group-links" id="nav-group-links-${groupId}"${collapsedGroups.has(String(groupId)) ? " hidden" : ""}>${links.map(([key, label]) => `<button class="nav-button" data-nav="${key}"><span class="nav-icon">${icons[key] || "•"}</span><span>${label}</span></button>`).join("")}</div>
    </section>`).join("");
  $$('[data-nav-group-toggle]').forEach((button) => {
    button.onclick = () => {
      const expanded = button.getAttribute("aria-expanded") === "true";
      const links = document.getElementById(button.getAttribute("aria-controls"));
      button.setAttribute("aria-expanded", String(!expanded));
      links.hidden = expanded;
      preferences.setNavGroupCollapsed?.(button.dataset.navGroupToggle, expanded);
    };
  });
  $$('[data-nav]').forEach((button) => { button.onclick = () => navigate(button.dataset.nav); });
}

function revealNavigationGroup(screen) {
  const button = $(`[data-nav="${screen}"]`);
  const group = button?.closest(".nav-group");
  const toggle = group?.querySelector("[data-nav-group-toggle]");
  const links = group?.querySelector(".nav-group-links");
  if (!toggle || !links || toggle.getAttribute("aria-expanded") === "true") return;
  toggle.setAttribute("aria-expanded", "true");
  links.hidden = false;
  preferences.setNavGroupCollapsed?.(toggle.dataset.navGroupToggle, false);
}

function canAccessScreen(screen) {
  if (screen === "dashboard") return true;
  if (screen === "settings") return Boolean(state.capabilities.settings);
  if (screen === "control_center") return Boolean(state.capabilities.control_center);
  if (screen === "assuntos") return state.readableModules.size > 0;
  if (screen === "aprovacoes") return Boolean(state.capabilities.approvals);
  if (screen === "portfolio") return ["produtos", "instrumentos_seccol", "catalogo_servicos"]
    .some((module) => state.readableModules.has(module));
  if (screen === "mobile") return state.readableModules.has("ordens_servico");
  return state.readableModules.has(screen);
}

async function navigate(screen) {
  if (!canAccessScreen(screen)) {
    toast("Seu perfil não possui acesso a esta área.");
    screen = "dashboard";
  }
  const content = $("#content");
  await ui.transitionOut?.(content);
  state.screen = screen;
  revealNavigationGroup(screen);
  updateAssistantContextUI();
  preferences.remember(screen);
  ui.workspaceTabs?.activate(screen);
  state.currentSubjectId = null;
  if (ui.setNavigation) ui.setNavigation(false);
  else $("#sidebar").classList.remove("open");
  $$('[data-nav]').forEach((button) => {
    const active = button.dataset.nav === screen;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  // Cada tela gravável expõe sua ação contextual. Manter a ação global oculta
  // evita abrir um cadastro de outro módulo quando a tela atual é somente leitura.
  $("#newButton").classList.add("hidden");
  try {
    if (screen === "dashboard") return await loadDashboard();
    if (screen === "portfolio") return await loadPortfolio();
    if (screen === "settings") return await loadSettings();
    if (screen === "control_center") return await loadControlCenter();
    if (screen === "whatsapp") return await loadWhatsApp();
    if (screen === "editais") return await loadTenderSearch();
    if (screen === "fontes") return await loadSources();
    if (screen === "assuntos") return await loadSubjects();
    if (screen === "aprovacoes") return await loadApprovals();
    if (screen === "importacoes_xml") return await loadXmlImports();
    if (screen === "estoque") return await loadInventory();
    if (screen === "controladoria") return await loadManagementOverview();
    if (screen === "fiscal") return await loadFiscal();
    if (screen === "rh") return await loadHR();
    if (screen === "relatorios") return await loadReporting();
    if (screen === "calibracoes") return await loadCalibrationHub();
    if (screen === "mobile") return await loadMobile();
    if (screen === "normas_tecnicas") return await loadNorms();
    if (screen === "concorrentes") return await loadCompetitors();
    return await loadModule(screen);
  } catch (failure) {
    $("#content").innerHTML = `<div class="empty"><div class="empty-icon">!</div><strong>Não foi possível abrir esta área.</strong><br>${escapeHTML(failure.message)}</div>`;
  } finally {
    ui.transitionIn?.(content);
  }
}

function setHeader(eyebrow, title) {
  $("#sectionEyebrow").textContent = eyebrow;
  $("#sectionTitle").textContent = title;
}

function openPasswordRecovery(resetToken = "") {
  const dialog = $("#passwordRecoveryDialog");
  const requestForm = $("#passwordRecoveryRequestForm");
  const resetForm = $("#passwordRecoveryResetForm");
  requestForm.classList.toggle("hidden", Boolean(resetToken));
  resetForm.classList.toggle("hidden", !resetToken);
  if (resetToken) resetForm.elements.token.value = resetToken;
  $("#passwordRecoveryRequestStatus").classList.add("hidden");
  $("#passwordRecoveryResetError").classList.add("hidden");
  dialog.showModal();
  requestAnimationFrame(() => {
    const target = resetToken ? resetForm.elements.password : requestForm.elements.email;
    target?.focus();
  });
}

async function requestPasswordRecovery(event) {
  event.preventDefault();
  // currentTarget só é garantido durante a chamada síncrona do listener;
  // depois do await o navegador pode limpá-lo.
  const form = event.currentTarget;
  const status = $("#passwordRecoveryRequestStatus");
  status.classList.add("hidden");
  try {
    const data = await api("/api/password/forgot", {
      method: "POST",
      body: JSON.stringify({ email: form.elements.email.value }),
    });
    status.textContent = data.message;
    status.classList.remove("hidden");
    form.elements.email.value = "";
  } catch (failure) {
    status.textContent = failure.message;
    status.classList.remove("hidden");
  }
}

async function resetRecoveredPassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = $("#passwordRecoveryResetError");
  error.classList.add("hidden");
  if (form.elements.password.value !== form.elements.password_confirmation.value) {
    error.textContent = "A confirmação não corresponde à nova senha.";
    error.classList.remove("hidden");
    form.elements.password_confirmation.focus();
    return;
  }
  try {
    await api("/api/password/reset", {
      method: "POST",
      body: JSON.stringify({
        token: form.elements.token.value,
        password: form.elements.password.value,
      }),
    });
    window.history.replaceState({}, "", window.location.pathname);
    form.reset();
    $("#passwordRecoveryDialog").close();
    toast("Senha redefinida. Entre com a nova senha.");
    $("#authForm [name=email]").focus();
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove("hidden");
  }
}

async function loadControlCenter() {
  if (!window.SIVSControlCenter) throw new Error("O componente do Centro de Controle não foi carregado.");
  return window.SIVSControlCenter.render({ api, state, setHeader, dateBR, toast,
    navigate, openRecord: openRecordById });
}

async function loadWhatsApp() {
  if (!window.SIVSWhatsApp) throw new Error("O componente de atendimento do WhatsApp não foi carregado.");
  return window.SIVSWhatsApp.render({ api, state, setHeader, dateBR, toast });
}

function normalizeNotificationView(view) {
  const normalized = String(view || "active").trim().toLowerCase();
  if (["active", "pending", "unread"].includes(normalized)) return "active";
  if (["history", "resolved", "archived"].includes(normalized)) return "history";
  return normalized === "all" ? "all" : "active";
}

async function refreshNotifications(view = state.notificationView || "active") {
  if (!state.user) return;
  view = normalizeNotificationView(view);
  const data = await api(`/api/notifications?view=${encodeURIComponent(view)}`);
  state.notifications = data.items || [];
  state.notificationView = normalizeNotificationView(data.view || view);
  const unread = Number(data.unreadCount || 0);
  $("#notificationBadge").textContent = unread > 99 ? "99+" : unread;
  $("#notificationBadge").classList.toggle("hidden", unread === 0);
}

function notificationDestination(item) {
  const alertType = String(item.alert_entity_type || "");
  const alertId = Number(item.alert_entity_id || 0);
  if (alertType === "tender_result" && alertId && canAccessScreen("editais")) {
    return { kind: "tender", id: alertId, label: "Abrir edital" };
  }
  if (alertType === "company_tender_document" && canAccessScreen("settings")) {
    return { kind: "screen", screen: "settings", label: "Abrir documentos de licitação" };
  }
  if (alertType === "tender_coverage" && canAccessScreen("editais")) {
    return { kind: "screen", screen: "editais", label: "Abrir cobertura de editais" };
  }
  const module = item.module || item.target;
  if (item.record_id && module && canAccessScreen(module)) {
    return { kind: "record", id: Number(item.record_id), module, label: `Abrir ${screenLabel(module)}` };
  }
  if (item.target && canAccessScreen(item.target)) {
    return { kind: "screen", screen: item.target, label: `Abrir ${screenLabel(item.target)}` };
  }
  return null;
}

function notificationDestinationHTML(item) {
  const destination = notificationDestination(item);
  if (!destination) return "";
  const id = Number(item.id);
  const attributes = destination.kind === "tender"
    ? `data-notification-tender="${destination.id}"`
    : destination.kind === "record"
      ? `data-notification-record="${destination.id}" data-notification-module="${escapeHTML(destination.module)}"`
      : `data-notification-target="${escapeHTML(destination.screen)}"`;
  return `<button class="text-button" type="button" ${attributes} data-notification-id="${id}">${escapeHTML(destination.label)}</button>`;
}

async function openNotifications(view = state.notificationView || "active") {
  view = normalizeNotificationView(view);
  try {
    await refreshNotifications(view);
  } catch (failure) {
    toast(failure.message);
    return;
  }
  $("#notificationActiveTab").classList.toggle("active", view === "active");
  $("#notificationActiveTab").setAttribute("aria-selected", String(view === "active"));
  $("#notificationHistoryTab").classList.toggle("active", view === "history");
  $("#notificationHistoryTab").setAttribute("aria-selected", String(view === "history"));
  const activeAlerts = state.notifications.filter((item) => item.activeAlert).length;
  const unread = state.notifications.filter((item) => !item.read_at).length;
  const summary = view === "active"
    ? `${state.notifications.length} pendência(s)${activeAlerts ? ` · ${activeAlerts} alerta(s) ativo(s)` : ""}${unread ? ` · ${unread} não lida(s)` : ""}`
    : `${state.notifications.length} notificação(ões) no histórico`;
  $("#notificationSummary").textContent = summary;
  $("#notificationList").setAttribute("aria-labelledby", view === "active" ? "notificationActiveTab" : "notificationHistoryTab");
  $("#notificationList").innerHTML = state.notifications.length ? state.notifications.map((item) => `
    <article class="notification-item ${item.read_at ? "" : "unread"} ${item.activeAlert ? "active-alert" : ""}">
      <span class="notification-level ${escapeHTML(item.level)}"></span>
      <div><strong>${escapeHTML(item.title)}</strong><p>${escapeHTML(item.message || "")}</p><small>${dateBR(item.created_at, true)}${item.resolved_at ? ` · Resolvida em ${dateBR(item.resolved_at, true)}` : ""}</small><div class="notification-item-actions">${notificationDestinationHTML(item)}${!item.read_at ? `<button class="text-button" type="button" data-notification-read="${Number(item.id)}">Marcar como lida</button>` : ""}${item.level === "info" && !item.activeAlert && !item.dismissed_at ? `<button class="text-button" type="button" data-notification-dismiss="${Number(item.id)}">Dispensar</button>` : ""}</div></div>
    </article>`).join("") : '<div class="empty">Nenhuma notificação.</div>';
  $("#notificationList").querySelectorAll("[data-notification-target]").forEach((button) => {
    button.onclick = async () => {
      await notificationItemAction(button.dataset.notificationId, "read", true);
      $("#notificationDialog").close();
      await navigate(button.dataset.notificationTarget);
    };
  });
  $("#notificationList").querySelectorAll("[data-notification-record]").forEach((button) => {
    button.onclick = async () => {
      const module = button.dataset.notificationModule;
      await notificationItemAction(button.dataset.notificationId, "read", true);
      if (module) await navigate(module);
      $("#notificationDialog").close();
      await openRecordById(Number(button.dataset.notificationRecord));
    };
  });
  $("#notificationList").querySelectorAll("[data-notification-tender]").forEach((button) => {
    button.onclick = async () => {
      await notificationItemAction(button.dataset.notificationId, "read", true);
      $("#notificationDialog").close();
      await showTenderDetail(Number(button.dataset.notificationTender));
    };
  });
  $("#notificationList").querySelectorAll("[data-notification-read]").forEach((button) => {
    button.onclick = () => notificationItemAction(button.dataset.notificationRead, "read");
  });
  $("#notificationList").querySelectorAll("[data-notification-dismiss]").forEach((button) => {
    button.onclick = () => notificationItemAction(button.dataset.notificationDismiss, "dismiss");
  });
  $("#notificationDialog").showModal();
}

async function notificationItemAction(id, action, silent = false) {
  if (!id) return;
  try {
    await api(`/api/notifications/${Number(id)}/${action}`, { method: "POST", body: "{}" });
    await refreshNotifications(state.notificationView || "active");
    if ($("#notificationDialog").open) await openNotifications(state.notificationView || "active");
    if (!silent) toast(action === "dismiss" ? "Notificação dispensada." : "Notificação marcada como lida.");
  } catch (failure) { if (!silent) toast(failure.message); }
}

async function openNotificationPreferences() {
  const form = $("#notificationPreferencesForm");
  const error = $("#notificationPreferencesError");
  error.classList.add("hidden");
  try {
    const data = await api("/api/notification-preferences");
    const preferences = data.preferences || {};
    Object.entries(preferences.categories || {}).forEach(([category, enabled]) => {
      const field = form.elements[`category_${category}`];
      if (field) field.checked = Boolean(enabled);
    });
    form.elements.minimumLevel.value = preferences.minimumLevel || "info";
    form.elements.dailyEmail.checked = Boolean(preferences.dailyEmail);
    form.elements.criticalEmail.checked = Boolean(preferences.criticalEmail);
    form.elements.dailyDigestHour.value = preferences.dailyDigestHour ?? 8;
    form.elements.quietEnabled.checked = Boolean(preferences.quietHours?.enabled);
    form.elements.quietStart.value = preferences.quietHours?.start || "18:00";
    form.elements.quietEnd.value = preferences.quietHours?.end || "08:00";
    $("#notificationDialog").close();
    $("#notificationPreferencesDialog").showModal();
  } catch (failure) { toast(failure.message); }
}

async function saveNotificationPreferences(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const error = $("#notificationPreferencesError");
  const categories = ["approvals", "crm", "tenders", "whatsapp", "system"].reduce((result, category) => {
    result[category] = Boolean(form.elements[`category_${category}`].checked);
    return result;
  }, {});
  try {
    await api("/api/notification-preferences", { method: "PUT", body: JSON.stringify({
      categories, minimumLevel: form.elements.minimumLevel.value,
      dailyEmail: form.elements.dailyEmail.checked, criticalEmail: form.elements.criticalEmail.checked,
      dailyDigestHour: Number(form.elements.dailyDigestHour.value),
      quietHours: { enabled: form.elements.quietEnabled.checked,
        start: form.elements.quietStart.value, end: form.elements.quietEnd.value },
    }) });
    error.classList.add("hidden");
    $("#notificationPreferencesDialog").close();
    await refreshNotifications();
    toast("Preferências de notificação salvas.");
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove("hidden");
  }
}

function pickWithoutRepeat(key, options) {
  if (!options.length) return "";
  const storageKey = `sivs:greeting:${key}`;
  let last = -1;
  try { last = Number(sessionStorage.getItem(storageKey)); } catch {}
  let index = Math.floor(Math.random() * options.length);
  if (options.length > 1 && index === last) index = (index + 1) % options.length;
  try { sessionStorage.setItem(storageKey, String(index)); } catch {}
  return options[index];
}

function dashboardGreeting(date, pendingCount) {
  const hour = date.getHours();
  const weekday = date.getDay();
  const isWeekend = weekday === 0 || weekday === 6;
  const isMonday = weekday === 1;
  const period = hour < 5 ? "madrugada" : hour < 12 ? "manha" : hour < 18 ? "tarde" : "noite";
  const openers = {
    madrugada: ["Boa madrugada", "Sessão noturna", "Trabalho de madrugada"],
    manha: isMonday ? ["Bom começo de semana", "Boa semana", "Bom dia"] : ["Bom dia", "Ótima manhã", "Manhã produtiva"],
    tarde: ["Boa tarde", "Bom ritmo de tarde", "Tarde produtiva"],
    noite: ["Boa noite", "Reta final do dia", "Fechando o dia por aqui"],
  }[period];
  if (isWeekend) openers.push("Bom fim de semana");
  const subtitles = pendingCount === 0
    ? [
        "Nenhuma pendência urgente agora — ótimo momento para se adiantar.",
        "Tudo em dia por aqui. Aproveite para organizar o que vem a seguir.",
        "Fluxo tranquilo hoje. Bom momento para revisar o que já está pronto.",
      ]
    : pendingCount <= 5
      ? [
          `${pendingCount} ${pendingCount === 1 ? "pendência" : "pendências"} esperando por você. Vamos em frente.`,
          `${pendingCount} ${pendingCount === 1 ? "item" : "itens"} no radar para hoje — um de cada vez.`,
          `${pendingCount} ${pendingCount === 1 ? "prioridade" : "prioridades"} para hoje. Você já sabe o caminho.`,
        ]
      : [
          `${pendingCount} pendências no radar. Foco no que importa primeiro.`,
          `Dia cheio — ${pendingCount} pendências. Um passo de cada vez.`,
          `${pendingCount} pendências à espera. Vamos organizar as prioridades juntos.`,
        ];
  return {
    opener: pickWithoutRepeat("opener", openers),
    subtitle: pickWithoutRepeat("subtitle", subtitles),
  };
}

function dashboardActionsHTML() {
  const actions = [
    ["clientes_fornecedores", "Cadastrar cliente ou fornecedor", "Comece pelo CPF/CNPJ", canAccessScreen("clientes_fornecedores") && (canAction("clientes", "create") || canAction("fornecedores", "create"))],
    ["editais", "Buscar um edital", "Encontrar oportunidades compatíveis", canAccessScreen("editais")],
    ["ordens_servico", "Abrir uma O.S.", "Registrar execução ou atendimento", canAction("ordens_servico", "create")],
    ["aprovacoes", "Ver aprovações", "Resolver decisões pendentes", canAccessScreen("aprovacoes")],
  ].filter(([, , , visible]) => visible).slice(0, 3);
  if (!actions.length) return "";
  return `<section class="dashboard-actions" aria-labelledby="dashboardActionsTitle"><header><div><p class="eyebrow gold">PRÓXIMO PASSO</p><h3 id="dashboardActionsTitle">O que você precisa fazer?</h3></div><small>Atalhos liberados para o seu perfil.</small></header><div>${actions.map(([module, title, hint]) => `<button class="dashboard-action" type="button" data-new-module="${module}"><span><strong>${title}</strong><small>${hint}</small></span><b aria-hidden="true">→</b></button>`).join("")}</div></section>`;
}

async function loadDashboard() {
  setHeader("VISÃO GERAL", "Painel executivo");
  $("#content").innerHTML = loadingStateHTML("Carregando indicadores", "Organizando prioridades, acessos rápidos e visão operacional.");
  const data = await api("/api/dashboard");
  const total = Number(data.operationalTotal || 0);
  const balance = Number(data.income || 0) - Number(data.expense || 0);
  const financialMetrics = data.financialVisible ? `
      ${metric("Entradas", money(data.income), "↑", "Valores cadastrados")}
      ${metric("Saldo operacional", money(balance), "R$", balance >= 0 ? "Resultado positivo" : "Exige atenção")}` : "";
  const greeting = dashboardGreeting(new Date(), (data.workItems || []).length);
  $("#content").innerHTML = `
    <section class="hero"><div><p class="eyebrow gold">${escapeHTML(state.user.companyName || "EMPRESA ATIVA")}</p><h2>${escapeHTML(greeting.opener)}, ${escapeHTML(state.user.name.split(" ")[0])}.</h2><p>${escapeHTML(greeting.subtitle)}</p></div><div class="hero-actions"><div class="hero-date">${new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" })}</div>${state.readableModules.has("editais") ? '<button class="hero-search-button" data-go="editais">⌕ Buscar editais agora</button>' : ""}</div></section>
    ${dashboardActionsHTML()}
    ${workCenterHTML(data.workItems || [])}
    ${originalHubHTML(data.counts)}
    <section class="metric-grid executive-metrics">
      ${metric("Registros operacionais", total, "◫", "Sem contar catálogos de fontes e normas")}
      ${metric("Aprovações pendentes", data.pendingApprovals || 0, "✓", "Solicitações e documentos", "aprovacoes")}
      ${metric("Prazos em até 7 dias", data.alerts.length, "◷", "Agenda operacional")}
      ${metric("Notificações não lidas", data.unreadNotifications || 0, "◇", "Central da empresa")}
      ${financialMetrics}
    </section>
    <section class="dashboard-grid"><div class="panel"><div class="panel-head"><h3>Atividade recente</h3><span class="status">Empresa isolada</span></div><div class="panel-body">${recentHTML(data.recent)}</div></div><div class="panel"><div class="panel-head"><h3>Próximos prazos</h3><span class="status">${data.alerts.length} alerta(s)</span></div><div class="panel-body">${alertsHTML(data.alerts)}</div></div></section>`;
  bindDashboardActions();
}

function preferredScreens() {
  const defaults = roleShortcutDefaults[state.user?.role] || ["clientes_fornecedores", "ordens_servico", "editais", "financeiro", "normas_tecnicas"];
  return [...preferences.favorites(), ...preferences.recent(), ...defaults]
    .filter((screen, index, items) => items.indexOf(screen) === index && canAccessScreen(screen))
    .slice(0, 5);
}

function quickLinksHTML() {
  const screens = preferredScreens();
  return screens.length ? screens.map((screen) => `<button class="quick-link" data-go="${escapeHTML(screen)}"><span>${escapeHTML(icons[screen] || "•")}</span><strong>${escapeHTML(screenLabel(screen))}</strong><b>→</b></button>`).join("") : '<div class="work-empty">Use a busca geral para favoritar as áreas mais usadas.</div>';
}

function workCenterHTML(items) {
  const list = items.slice(0, 6).map((item) => {
    const due = item.dueDate
      ? `${item.kind === "overdue" ? "Prazo crítico vencido em" : "Prazo crítico: até"} ${dateBR(item.dueDate)}`
      : (item.timingLabel || "Abrir");
    const datetime = item.dueDate ? ` datetime="${escapeHTML(item.dueDate)}"` : "";
    const reason = item.pendingReason || "Este registro requer acompanhamento.";
    const status = item.status ? ` · Etapa atual: ${escapeHTML(item.status)}` : "";
    const tenderTarget = Number(item.tenderResultId) > 0 ? ` data-work-tender="${Number(item.tenderResultId)}"` : "";
    return `<button class="work-item priority-${escapeHTML(item.priority)}" data-work-record="${Number(item.recordId)}" data-work-target="${escapeHTML(item.target)}"${tenderTarget}><span class="work-priority" aria-hidden="true"></span><span class="work-item-copy"><strong class="work-item-title">${escapeHTML(item.title)}</strong><span class="work-pending-reason"><b>O que precisa de atenção:</b> ${escapeHTML(reason)}</span><span class="work-required-action"><b>${escapeHTML(item.actionLabel || "O que fazer agora")}:</b> ${escapeHTML(item.requiredAction || "Abra o registro e confira o próximo passo.")}</span><small>${escapeHTML(screenLabel(item.module))} · ${escapeHTML(item.meta)}${status}</small></span><time class="work-timing"${datetime}>${escapeHTML(due)}</time></button>`;
  }).join("");
  return `<section class="work-center" aria-labelledby="workCenterTitle"><header class="work-center-head"><div><p class="eyebrow gold">MEU TRABALHO</p><h3 id="workCenterTitle">Prioridades para agora</h3></div><p>Cada item informa o que precisa de atenção, o que fazer em seguida e até quando. Abra-o para concluir ou atualizar o andamento.</p></header><div class="work-layout"><div class="work-list">${list || '<div class="work-empty"><strong>Nenhuma ação necessária agora.</strong><br>Novas pendências e prazos aparecerão aqui com o próximo passo indicado.</div>'}</div><aside class="quick-access"><header><h4>Acessos rápidos</h4><button type="button" class="text-button" id="customizeShortcuts">Personalizar</button></header><small>Favoritos e áreas abertas recentemente.</small><div class="quick-links" id="quickLinks">${quickLinksHTML()}</div></aside></div></section>`;
}

function refreshQuickAccess() {
  const area = $("#quickLinks");
  if (!area) return;
  area.innerHTML = quickLinksHTML();
  area.querySelectorAll("[data-go]").forEach((button) => { button.onclick = () => navigate(button.dataset.go); });
}

function bindDashboardActions() {
  $$('[data-go]').forEach((button) => { button.onclick = () => navigate(button.dataset.go); });
  $$('[data-new-module]').forEach((button) => {
    button.onclick = () => {
      const module = button.dataset.newModule;
      if (module === "editais" || module === "aprovacoes") return navigate(module);
      if (module === "clientes_fornecedores") return openRecord(null, module);
      return canAction(module, "create") ? openRecord(null, module) : toast("Seu perfil pode consultar esta área, mas não criar registros.");
    };
  });
  $$('[data-work-record]').forEach((button) => {
    button.onclick = () => {
      const tenderResultId = Number(button.dataset.workTender || 0);
      if (tenderResultId) return showTenderDetail(tenderResultId);
      return openRecordById(Number(button.dataset.workRecord));
    };
  });
  if ($("#customizeShortcuts")) $("#customizeShortcuts").onclick = () => ui.commandPalette?.open();
}

function originalHubHTML(counts) {
  const hubs = [
    ["Administrativo", "arquivos", "▤", "red", ["arquivos", "clientes_fornecedores"], "Cadastros, arquivos e compras"],
    ["Fiscal", "fiscal", "⎙", "gold", ["fiscal", "importacoes_xml"], "Documentos, XML, SEFAZ e contabilidade"],
    ["Vendas e portfólio", "portfolio", "◆", "violet", ["produtos", "catalogo_servicos", "crm", "propostas", "contratos", "vendas"], "Produtos, ensaios, propostas e vendas"],
    ["Mobile", "mobile", "▯", "blue", ["ordens_servico", "servicos"], "Execução técnica no campo"],
    ["Manual e documentos", "documentos_qualidade", "▤", "amber", ["documentos_qualidade", "treinamentos"], "Procedimentos e competências"],
    ["Serviço", "ordens_servico", "⚒", "teal", ["chamados", "agendamentos", "ordens_servico", "servicos"], "Chamados, agenda e O.S."],
    ["Calibração", "calibracoes", "⌖", "cyan", ["calibracoes", "padroes", "certificados"], "Padrões, calibrações e certificados"],
    ["Qualidade", "qualidade", "✓", "green", ["qualidade", "reclamacoes", "nao_conformidades"], "SGQ, reclamações e não conformidades"],
    ["Normas técnicas", "normas_tecnicas", "§", "orange", ["normas_tecnicas", "laudos_tecnicos", "estudos_tecnicos"], "Base obrigatória de laudos e estudos"],
    ["Análise e gestão", "produtividade", "↗", "lime", ["produtividade", "metas", "licitacoes"], "Indicadores, metas e inteligência"],
    ["Financeiro", "financeiro", "R$", "gold", ["contas_pagar", "contas_receber", "financeiro"], "Pagar, receber e resultado"],
    ["Caixa", "caixa", "▣", "yellow", ["caixa", "boletos"], "Movimentos, boletos e remessas"],
    ["Configurações", "settings", "⚙", "graphite", [], "Empresa, usuários e auditoria"],
  ];
  return `<section class="sivs-hub"><div class="hub-head"><div><p class="eyebrow gold">MÓDULOS</p><h3>Central operacional</h3></div><small>Inspirada no fluxo original, reorganizada para reduzir cliques e ambiguidades.</small></div><div class="hub-grid">${hubs.filter(([, target]) => canAccessScreen(target)).map(([title, target, icon, tone, modules, description]) => {
    const count = modules.reduce((sum, module) => sum + Number(counts[module] || 0), 0);
    return `<button class="hub-card tone-${tone}" data-go="${target}"><span class="hub-icon">${icon}</span><span><strong>${title}</strong><small>${description}</small></span><b>${count || "→"}</b></button>`;
  }).join("")}</div></section>`;
}

function metric(label, value, icon, subtitle, target = "") {
  return `<article class="metric-card ${target ? "clickable" : ""}" ${target ? `data-go="${target}"` : ""}><div class="metric-head"><span>${label}</span><span class="metric-icon">${icon}</span></div><strong>${value}</strong><small>${subtitle}</small></article>`;
}

function recentHTML(items) {
  return items.length ? items.map((item) => `<div class="record-line"><span class="record-line-icon">${icons[item.module] || "•"}</span><span><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(state.modules[item.module] || item.module)} · ${escapeHTML(item.status)}</small></span><time>${dateBR(item.updated_at)}</time></div>`).join("") : '<div class="empty">Nenhuma atividade registrada.</div>';
}

function alertsHTML(items) {
  return items.length ? items.map((item) => `<div class="alert-item"><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(state.modules[item.module] || item.module)} · ${dateBR(item.due_date)}</small></div>`).join("") : '<div class="empty"><div class="empty-icon">✓</div>Nenhum prazo crítico.</div>';
}

async function loadPortfolio() {
  setHeader("COMERCIAL E ENGENHARIA", "Portfólio SECCOL");
  $("#content").innerHTML = loadingStateHTML("Organizando o portfólio", "Separando produtos, instrumentos, serviços e bases normativas.");
  const readCatalog = (module) => state.readableModules.has(module)
    ? api(`/api/records?module=${module}`) : Promise.resolve({ items: [] });
  const [products, instruments, services] = await Promise.all([
    readCatalog("produtos"),
    readCatalog("instrumentos_seccol"),
    readCatalog("catalogo_servicos"),
  ]);
  const onlyCatalog = (items) => items.filter((item) => item.payload?.catalogo_seccol);
  const groups = [
    { key: "produtos", title: "Produtos e soluções", subtitle: "Produção e fornecimento SECCOL", icon: "◆", items: onlyCatalog(products.items) },
    { key: "instrumentos_seccol", title: "Instrumentos técnicos próprios", subtitle: "Patrimônio usado em certificação e manutenção", icon: "⌖", items: onlyCatalog(instruments.items) },
    { key: "catalogo_servicos", title: "Serviços e ensaios", subtitle: "Escopos executados pela equipe SECCOL", icon: "⚒", items: onlyCatalog(services.items) },
  ];
  state.items = groups.flatMap((group) => group.items);
  const linked = state.items.filter((item) => (item.payload?.normas_aplicaveis || []).length).length;
  $("#content").innerHTML = `
    <section class="portfolio-hero"><div><p class="eyebrow gold">CATÁLOGO OPERACIONAL CONTROLADO</p><h2>O que a SECCOL produz, fornece, possui e executa.</h2><p>O portfólio oficial foi separado por natureza para impedir que produto, instrumento de ensaio e serviço executado sejam tratados como a mesma coisa.</p></div><div class="portfolio-total"><strong>${state.items.length}</strong><small>itens oficiais</small></div></section>
    <section class="summary-strip portfolio-summary"><div class="summary-item"><span>Produtos e soluções</span><strong>${groups[0].items.length}</strong></div><div class="summary-item"><span>Instrumentos próprios</span><strong>${groups[1].items.length}</strong></div><div class="summary-item"><span>Serviços e ensaios</span><strong>${groups[2].items.length}</strong></div><div class="summary-item"><span>Com base normativa inicial</span><strong>${linked}</strong></div></section>
    <section class="portfolio-notice"><span>✓</span><div><strong>Premissa confirmada pela direção</strong><p>Todo item apresentado no site oficial integra a produção, o fornecimento ou o patrimônio técnico da SECCOL. Modelo, série, configuração, preço e escopo continuam sujeitos à confirmação no cadastro operacional.</p></div></section>
    <div class="module-toolbar"><div class="toolbar-filters"><input id="portfolioFilter" class="filter-input" placeholder="Pesquisar produto, instrumento, ensaio ou norma"></div><div class="toolbar-actions">${[["produtos", "Produtos"], ["instrumentos_seccol", "Instrumentos"], ["catalogo_servicos", "Serviços"]].filter(([module]) => state.readableModules.has(module)).map(([module, label]) => `<button class="secondary" data-go="${module}">${label}</button>`).join("")}</div></div>
    <div id="portfolioGroups">${portfolioGroupsHTML(groups, "")}</div>`;
  $("#portfolioFilter").oninput = (event) => {
    $("#portfolioGroups").innerHTML = portfolioGroupsHTML(groups, event.target.value);
    bindRows();
  };
  $$('[data-go]').forEach((button) => { button.onclick = () => navigate(button.dataset.go); });
  bindRows();
}

function portfolioGroupsHTML(groups, search) {
  const query = String(search || "").trim().toLowerCase();
  return groups.map((group) => {
    const items = group.items.filter((item) => {
      const payload = item.payload || {};
      return `${item.title} ${payload.codigo || ""} ${payload.familia || ""} ${payload.categoria || ""} ${payload.descricao || ""} ${payload.uso_tecnico || ""} ${(payload.normas_aplicaveis || []).join(" ")}`.toLowerCase().includes(query);
    });
    if (query && !items.length) return "";
    return `<section class="portfolio-group"><header><span>${group.icon}</span><div><h3>${group.title}</h3><small>${group.subtitle}</small></div><b>${items.length}</b></header><div class="portfolio-grid">${items.map(portfolioCardHTML).join("") || '<div class="empty">Nenhum item nesta categoria.</div>'}</div></section>`;
  }).join("") || '<div class="empty"><div class="empty-icon">⌕</div>Nenhum item corresponde à pesquisa.</div>';
}

function portfolioCardHTML(item) {
  const payload = item.payload || {};
  const norms = Array.isArray(payload.normas_aplicaveis) ? payload.normas_aplicaveis : [];
  const description = payload.descricao || payload.uso_tecnico || "Detalhamento técnico a completar.";
  return `<article class="portfolio-card ${item.module}"><header><span>${escapeHTML(payload.codigo || "SECCOL")}</span><span class="status ${statusClass(item.status)}">${escapeHTML(item.status)}</span></header><h4>${escapeHTML(item.title)}</h4><small>${escapeHTML(payload.familia || payload.categoria || payload.classificacao_catalogo || "Portfólio SECCOL")}</small><p>${escapeHTML(description)}</p><div class="portfolio-norms"><b>Base técnica</b><span>${norms.length ? escapeHTML(norms.slice(0, 3).join(" · ")) + (norms.length > 3 ? ` +${norms.length - 3}` : "") : "Definir conforme aplicação"}</span></div><footer><a href="${escapeHTML(safeExternalURL(payload.fonte_oficial))}" target="_blank" rel="noopener noreferrer">Fonte oficial ↗</a><button class="secondary" data-edit="${item.id}">Abrir ficha</button></footer></article>`;
}

async function loadCalibrationHub() {
  setHeader("CALIBRAÇÃO", "Central metrológica");
  $("#content").innerHTML = loadingStateHTML("Conferindo padrões e calibrações");
  const [standards, calibrations, certificates] = await Promise.all([
    api("/api/records?module=padroes"), api("/api/records?module=calibracoes"), api("/api/records?module=certificados"),
  ]);
  state.items = calibrations.items;
  const today = new Date();
  const deadline = new Date(today.valueOf() + 30 * 86400000);
  const dueValue = (item) => item.payload?.proxima_calibracao || item.due_date;
  const expired = standards.items.filter((item) => dueValue(item) && new Date(`${String(dueValue(item)).slice(0, 10)}T23:59:59`) < today);
  const upcoming = standards.items.filter((item) => {
    const value = dueValue(item);
    if (!value) return false;
    const date = new Date(`${String(value).slice(0, 10)}T23:59:59`);
    return date >= today && date <= deadline;
  });
  const pending = calibrations.items.filter((item) => !["Concluído", "Concluída", "Aprovado", "Publicado"].includes(item.status));
  $("#content").innerHTML = `<section class="module-context calibration-context"><div><p class="eyebrow gold">CONTROLE METROLÓGICO</p><h2>Padrões, calibrações e certificados</h2><p>A tela mantém os alertas tabulares do fluxo original e acrescenta prioridade, rastreabilidade e acesso direto às evidências.</p></div><div class="context-actions">${canAction("calibracoes", "create") ? '<button class="primary" id="newCalibration">＋ Nova calibração</button>' : ""}<button class="secondary" data-go="padroes">Abrir padrões</button><button class="secondary" data-go="certificados">Certificados</button></div></section>
  <section class="calibration-alert-grid">${calibrationAlertPanel("Padrões vencidos", expired, "critical", "Nenhum padrão vencido.")}${calibrationAlertPanel("Padrões a vencer em 30 dias", upcoming, "warning", "Nenhum vencimento próximo.")}</section>
  <section class="calibration-summary"><article><span>⌖</span><strong>${standards.items.length}</strong><small>Padrões cadastrados</small></article><article><span>▦</span><strong>${pending.length}</strong><small>Calibrações pendentes</small></article><article><span>▣</span><strong>${certificates.items.length}</strong><small>Certificados</small></article><article><span>✓</span><strong>${Math.max(calibrations.items.length - pending.length, 0)}</strong><small>Calibrações concluídas</small></article></section>
  <section class="panel"><div class="panel-head"><div><h3>Calibrações e verificações</h3><small class="muted">Clique no registro para consultar vínculos, certificados e anexos.</small></div><span class="status">${calibrations.items.length} registro(s)</span></div><div class="table-wrap borderless">${tableHTML(calibrations.items)}</div></section>`;
  if ($("#newCalibration")) $("#newCalibration").onclick = () => openRecord(null, "calibracoes");
  $$('[data-go]').forEach((button) => { button.onclick = () => navigate(button.dataset.go); });
  bindRows();
}

function calibrationAlertPanel(title, items, tone, emptyText) {
  return `<section class="legacy-alert-panel ${tone}"><header><span>${tone === "critical" ? "!" : "◷"}</span><h3>${title}</h3><b>${items.length}</b></header><div>${items.length ? `<table><thead><tr><th>Padrão</th><th>Identificação</th><th>Vencimento</th><th>Situação</th></tr></thead><tbody>${items.slice(0, 12).map((item) => `<tr><td><button data-edit="${item.id}">${escapeHTML(item.title)}</button></td><td>${escapeHTML(item.payload?.codigo || item.payload?.numero_serie || "—")}</td><td>${dateBR(item.payload?.proxima_calibracao || item.due_date)}</td><td><span class="status ${tone}">${tone === "critical" ? "Vencido" : "A vencer"}</span></td></tr>`).join("")}</tbody></table>` : `<p>${emptyText}</p>`}</div></section>`;
}

async function loadMobile() {
  setHeader("MOBILE", "Execução de serviços");
  $("#content").innerHTML = loadingStateHTML("Sincronizando Ordens de Serviço");
  const data = await api("/api/records?module=ordens_servico");
  state.items = data.items;
  const groups = [
    ["Em execução", data.items.filter((item) => item.status === "Em execução"), "running"],
    ["Serviço em pausa", data.items.filter((item) => item.status === "Pausada"), "paused"],
    ["Próximos serviços", data.items.filter((item) => ["Aberta", "Agendada", "Pendente"].includes(item.status)), "scheduled"],
  ];
  $("#content").innerHTML = `<section class="mobile-intro"><div><p class="eyebrow gold">CAMPO CONECTADO</p><h2>O.S. com execução simples e auditável</h2><p>Iniciar, pausar e concluir atualiza a mesma Ordem de Serviço do administrativo — sem duplicar cadastros.</p></div><button class="secondary" data-go="ordens_servico">Abrir gestão completa</button></section><section class="mobile-workbench"><header><div class="mobile-logo">Mobile <span>Campo</span></div><nav><b>Abrir O.S.</b><b class="active">Meus Serviços</b></nav></header><div class="mobile-filter"><span>⌕</span><input id="mobileFilter" placeholder="Filtrar cliente, O.S. ou local"><b>${data.items.length}</b></div><div id="mobileServiceGroups">${mobileGroupsHTML(groups)}</div></section>`;
  $("#mobileFilter").oninput = (event) => {
    const query = event.target.value.toLowerCase();
    const filtered = data.items.filter((item) => `${item.title} ${item.payload?.cliente || ""} ${item.payload?.local_execucao || ""}`.toLowerCase().includes(query));
    $("#mobileServiceGroups").innerHTML = mobileGroupsHTML([
      ["Em execução", filtered.filter((item) => item.status === "Em execução"), "running"],
      ["Serviço em pausa", filtered.filter((item) => item.status === "Pausada"), "paused"],
      ["Próximos serviços", filtered.filter((item) => ["Aberta", "Agendada", "Pendente"].includes(item.status)), "scheduled"],
    ]);
    bindMobileActions();
  };
  $$('[data-go]').forEach((button) => { button.onclick = () => navigate(button.dataset.go); });
  bindMobileActions();
}

function mobileGroupsHTML(groups) {
  return groups.map(([label, items, tone]) => `<section class="mobile-service-group"><header><h3>${label}</h3><span>${items.length}</span></header>${items.length ? items.map((item) => `<article class="mobile-service-card ${tone}"><div class="mobile-service-state"></div><div><small>${escapeHTML(item.payload?.numero || `O.S. #${item.id}`)} · ${dateBR(item.due_date)}</small><h4>${escapeHTML(item.title)}</h4><p>${escapeHTML(item.payload?.cliente || item.payload?.contato || "Cliente não informado")} · ${escapeHTML(item.payload?.local_execucao || "Local a confirmar")}</p><span>${escapeHTML(item.payload?.tecnico || item.payload?.responsavel || "Equipe técnica")}</span></div><div class="mobile-service-actions"><button class="icon-button" data-mobile-open="${item.id}" title="Abrir detalhes">◉</button>${canAction("ordens_servico", "transition") ? mobileActionButtons(item) : ""}</div></article>`).join("") : '<div class="mobile-empty">Nenhum serviço neste grupo.</div>'}</section>`).join("");
}

function mobileActionButtons(item) {
  if (item.status === "Em execução") return `<button class="secondary" data-mobile-action="${item.id}:Pausada">Pausar</button><button class="primary" data-mobile-action="${item.id}:Concluída">Concluir</button>`;
  if (item.status === "Pausada") return `<button class="primary" data-mobile-action="${item.id}:Em execução">Retomar</button>`;
  return `<button class="primary" data-mobile-action="${item.id}:Em execução">Iniciar</button>`;
}

function bindMobileActions() {
  $$('[data-mobile-open]').forEach((button) => { button.onclick = () => openRecordById(Number(button.dataset.mobileOpen)); });
  $$('[data-mobile-action]').forEach((button) => { button.onclick = () => {
    const [id, status] = button.dataset.mobileAction.split(":");
    mobileUpdate(Number(id), status);
  }; });
}

async function mobileUpdate(id, status) {
  try {
    const data = await api(`/api/records/${id}`);
    const item = data.item;
    const payload = { ...(item.payload || {}) };
    const log = Array.isArray(payload.execucao_mobile) ? payload.execucao_mobile : [];
    log.push({ status, at: new Date().toISOString(), by: state.user.name });
    payload.execucao_mobile = log.slice(-100);
    if (status === "Em execução" && !payload.inicio_campo) payload.inicio_campo = new Date().toISOString();
    if (status === "Concluída") payload.fim_campo = new Date().toISOString();
    await api(`/api/records/${id}`, { method: "PUT", body: JSON.stringify({ module: item.module, title: item.title, status, amount: item.amount, due_date: item.due_date, payload, revision: item.revision }) });
    toast(`O.S. atualizada para ${status}.`);
    loadMobile();
  } catch (failure) { toast(failure.message); }
}

async function loadNorms() {
  setHeader("QUALIDADE", "Normas técnicas");
  $("#content").innerHTML = loadingStateHTML("Carregando a base normativa");
  const data = await api("/api/records?module=normas_tecnicas");
  state.items = data.items;
  const licensed = data.items.filter((item) => String(item.payload?.licenciamento || "").includes("Comercial")).length;
  const publicCount = data.items.length - licensed;
  const today = new Date().toISOString().slice(0, 10);
  const reviewDue = data.items.filter((item) => item.payload?.proxima_revisao && item.payload.proxima_revisao <= today).length;
  const missingLicensed = data.items.filter((item) => String(item.payload?.licenciamento || "").includes("Comercial") && !item.attachments?.some((attachment) => attachment.category === "Cópia normativa licenciada" && attachment.license_confirmed)).length;
  const obsolete = data.items.filter((item) => ["Obsoleta", "Cancelada", "Substituída"].includes(item.status)).length;
  $("#content").innerHTML = `<section class="norms-hero"><div><p class="eyebrow gold">BASE TÉCNICA CONTROLADA</p><h2>Normas que fundamentam certificados, laudos e estudos</h2><p>Controle a edição aplicável, a licença, a revisão e os vínculos que demonstram onde cada referência é usada.</p></div><div class="norms-score"><strong>${data.items.length}</strong><small>referências cadastradas</small></div></section><section class="norms-notice"><span>§</span><div><strong>Controle de licença e vigência</strong><p>Fichas de referência não substituem a íntegra. Em referências comerciais, registre a cópia licenciada e sua titularidade; antes do uso, confirme edição, emendas, escopo, contrato e método aprovado.</p></div></section><section class="summary-strip norms-summary"><div class="summary-item"><span>Comercial/licenciada</span><strong>${licensed}</strong><small>${missingLicensed} sem cópia confirmada</small></div><div class="summary-item"><span>Revisar agora</span><strong>${reviewDue}</strong><small>prazo de revisão vencido</small></div><div class="summary-item"><span>Substituídas/obsoletas</span><strong>${obsolete}</strong><small>preservadas para rastreabilidade</small></div><div class="summary-item"><span>Com evidência</span><strong>${data.items.filter((item) => item.attachments?.length).length}</strong><small>ficha, licença ou documento oficial</small></div></section><div class="module-toolbar"><div class="toolbar-filters"><input id="normFilter" class="filter-input" placeholder="Filtrar referência, organismo, escopo ou ensaio"></div><div class="toolbar-actions">${canAction("normas_tecnicas", "create") ? '<button id="newNorm" class="primary">＋ Nova referência</button>' : ""}</div></div><section id="normGrid" class="norm-grid">${normsHTML(data.items)}</section>`;
  $("#normFilter").oninput = (event) => {
    const query = event.target.value.toLowerCase();
    $("#normGrid").innerHTML = normsHTML(data.items.filter((item) => `${item.title} ${item.payload?.codigo || ""} ${item.payload?.organismo || ""} ${item.payload?.escopo_resumido || ""} ${item.payload?.ensaios_base || ""}`.toLowerCase().includes(query)));
    bindRows();
  };
  if ($("#newNorm")) $("#newNorm").onclick = () => openRecord(null, "normas_tecnicas");
  bindRows();
}

function normsHTML(items) {
  return items.map((item) => {
    const licensedCopy = item.attachments?.some((attachment) => attachment.category === "Cópia normativa licenciada" && attachment.license_confirmed);
    const review = item.payload?.proxima_revisao ? `Revisar até ${dateBR(item.payload.proxima_revisao)}` : "Revisão a programar";
    const replacement = item.payload?.norma_substituta ? `Substituída por ${item.payload.norma_substituta}` : "";
    return `<article class="norm-card"><header><span class="norm-organization">${escapeHTML(item.payload?.organismo || "NORMA")}</span><span class="status ${statusClass(item.status)}">${escapeHTML(item.status)}</span></header><h3>${escapeHTML(item.payload?.codigo || item.title)}</h3><small>${escapeHTML(item.payload?.titulo_publicado || item.payload?.edicao || "Edição a confirmar")}</small><p>${escapeHTML(item.payload?.escopo_resumido || "Escopo não informado.")}</p><div class="norm-application"><b>Aplicação SECCOL</b><span>${escapeHTML(item.payload?.aplicabilidade_seccol || "A definir")}</span></div><div class="norm-control-meta"><span>${escapeHTML(review)}</span>${replacement ? `<span>${escapeHTML(replacement)}</span>` : ""}</div><footer><span>${licensedCopy ? "Cópia licenciada confirmada" : `${item.attachments?.length || 0} evidência(s)`} · ${escapeHTML(item.payload?.licenciamento || "Licença a classificar")}</span><div><a class="icon-button" href="${escapeHTML(safeExternalURL(item.payload?.referencia_oficial))}" target="_blank" rel="noopener noreferrer" title="Abrir fonte oficial" aria-label="Abrir fonte oficial">↗</a><button class="secondary" data-edit="${item.id}">Abrir controle</button></div></footer></article>`;
  }).join("") || '<div class="empty">Nenhuma norma encontrada.</div>';
}

async function loadModule(module) {
  const profile = getRecordProfile(module);
  const view = moduleViewSpecs[module] || {};
  setHeader("CADASTRO RELACIONAL", state.modules[module] || module);
  $("#content").innerHTML = loadingStateHTML("Carregando registros", "Aplicando seus filtros e permissões de acesso.");
  const query = String(state.moduleQueries[module] || "").trim();
  state.moduleRequest?.abort();
  const request = new AbortController();
  state.moduleRequest = request;
  let data;
  let followupData = null;
  try {
    [data, followupData] = await Promise.all([
      api(`/api/records?module=${encodeURIComponent(module)}&q=${encodeURIComponent(query)}`, {
        signal: request.signal,
      }),
      module === "crm" ? api("/api/crm/followups", { signal: request.signal }) : Promise.resolve(null),
    ]);
  } catch (failure) {
    if (failure.name === "AbortError") return;
    throw failure;
  }
  if (state.moduleRequest !== request || state.screen !== module) return;
  state.items = data.items;
  const statusCounts = {};
  state.items.forEach((item) => { statusCounts[item.status] = (statusCounts[item.status] || 0) + 1; });
  const canKanban = kanbanModules.has(module);
  const newLeadCount = module === "crm" ? (statusCounts["Novo lead"] || 0) : 0;
  const followups = followupData?.items || [];
  $("#content").innerHTML = `
  <section class="module-context"><div><p class="eyebrow gold">${escapeHTML(profile.eyebrow || state.user.companyName || "EMPRESA")}</p><h2>${escapeHTML(state.modules[module] || module)}</h2><p>${escapeHTML(view.description || profile.description)}</p></div><span class="status ${canAction(module, "update") ? "" : "readonly"}">${state.items.length} registro(s) · ${canAction(module, "update") ? "Edição permitida" : "Somente consulta"}</span></section>
    ${module === "crm" ? customerFollowupsHTML(followups, followupData?.counts || {}) : ""}
    <div class="module-toolbar"><div class="toolbar-filters"><input id="moduleFilter" class="filter-input" placeholder="Pesquisar por dados deste cadastro" value="${escapeHTML(query)}"><select id="moduleStatus" class="filter-select"><option value="">Todas as situações</option>${Object.keys(statusCounts).map((status) => `<option>${escapeHTML(status)}</option>`).join("")}</select></div><div class="toolbar-actions">${module === "crm" ? `<button id="newLeadsView" class="secondary" type="button" aria-pressed="false">Novos leads <span class="status">${newLeadCount}</span></button>` : ""}${canKanban ? '<button id="tableView" class="secondary">Tabela</button><button id="kanbanView" class="secondary">Kanban</button>' : ""}${state.exportableModules.has(module) ? `<a class="secondary export-link" href="/api/export?module=${encodeURIComponent(module)}">Exportar</a>` : ""}${canAction(module, "create") ? `<button id="moduleNew" class="primary">＋ ${escapeHTML(view.action || `Novo ${profile.singular.toLowerCase()}`)}</button>` : ""}</div></div>
    <div id="moduleData">${renderModuleData(state.items, module)}</div>`;
  $("#moduleFilter").oninput = (event) => {
    clearTimeout(state.searchTimer);
    state.searchTimer = setTimeout(() => { state.moduleQueries[module] = event.target.value; loadModule(module); }, 280);
  };
  $("#moduleStatus").onchange = filterModuleStatus;
  if ($("#newLeadsView")) $("#newLeadsView").onclick = toggleNewLeadsView;
  if ($("#moduleNew")) $("#moduleNew").onclick = () => openRecord(null, module);
  if ($("#tableView")) $("#tableView").onclick = () => { state.viewMode = "table"; rerenderModuleData(module); };
  if ($("#kanbanView")) $("#kanbanView").onclick = () => { state.viewMode = "kanban"; rerenderModuleData(module); };
  if (module === "crm") bindCustomerFollowups();
  bindRows();
}

function customerFollowupsHTML(items, counts) {
  if (!items.length) return `<section class="crm-followups is-clear" aria-labelledby="crmFollowupTitle"><div><p class="eyebrow gold">RETENÇÃO COMERCIAL</p><h3 id="crmFollowupTitle">Follow-up 30 · 60 · 90</h3><p>Nenhum cliente exige acompanhamento por inatividade agora.</p></div><span class="status">Em dia</span></section>`;
  return `<section class="crm-followups" aria-labelledby="crmFollowupTitle"><header><div><p class="eyebrow gold">RETENÇÃO COMERCIAL</p><h3 id="crmFollowupTitle">Clientes sem nova compra</h3><p>30 e 60 dias pedem revisão; aos 90 dias, registre um contato humano e seu resultado.</p></div><div class="crm-followup-counts"><span>30 dias <b>${counts["30"] || 0}</b></span><span>60 dias <b>${counts["60"] || 0}</b></span><span>90 dias <b>${counts["90"] || 0}</b></span></div></header><div class="crm-followup-grid">${items.map((item) => `<article class="crm-followup-card stage-${item.stage_days}"><div><span class="status">${item.stage_days} dias</span><h4>${escapeHTML(item.customer_name)}</h4><p>${item.last_sale_record_id ? `Última compra confirmada em ${dateBR(item.purchase_anchor_at)}.` : `Cliente cadastrado em ${dateBR(item.purchase_anchor_at)}, ainda sem compra confirmada.`}</p><small>${escapeHTML(item.assigned_user_name || item.seller_name || "Equipe comercial")} · tarefa desde ${dateBR(item.due_at)}</small></div>${canAction("crm", "update") ? `<div class="crm-followup-action"><label>Canal<select data-followup-channel="${item.id}"><option value="">Selecione</option><option value="WHATSAPP">WhatsApp</option><option value="PHONE">Telefone</option><option value="EMAIL">E-mail</option><option value="IN_PERSON">Presencial</option><option value="OTHER">Outro</option></select></label><label>Resultado / observação<input data-followup-notes="${item.id}" maxlength="2000" placeholder="Ex.: pediu retorno na próxima semana"></label><div><button class="primary" type="button" data-followup-contact="${item.id}">Registrar contato</button><button class="text-button" type="button" data-followup-dismiss="${item.id}">Dispensar etapa</button></div></div>` : ""}</article>`).join("")}</div></section>`;
}

function bindCustomerFollowups() {
  $$('[data-followup-contact]').forEach((button) => { button.onclick = async () => {
    const id = button.dataset.followupContact;
    const channel = $(`[data-followup-channel="${id}"]`).value;
    const notes = $(`[data-followup-notes="${id}"]`).value.trim();
    if (!channel) return toast("Selecione o canal usado no contato.");
    button.disabled = true;
    try {
      await api(`/api/crm/followups/${id}/contact`, { method: "POST", body: JSON.stringify({ channel, notes, outcome: notes || "Contato realizado" }) });
      toast("Contato registrado no histórico do cliente.");
      await loadModule("crm");
      refreshNotifications().catch(() => {});
    } catch (failure) { button.disabled = false; toast(failure.message); }
  }; });
  $$('[data-followup-dismiss]').forEach((button) => { button.onclick = async () => {
    const id = button.dataset.followupDismiss;
    const notes = $(`[data-followup-notes="${id}"]`).value.trim();
    if (!notes) return toast("Informe o motivo para dispensar esta etapa.");
    button.disabled = true;
    try {
      await api(`/api/crm/followups/${id}/dismiss`, { method: "POST", body: JSON.stringify({ notes, outcome: "Etapa dispensada" }) });
      toast("Etapa dispensada e registrada na auditoria.");
      await loadModule("crm");
      refreshNotifications().catch(() => {});
    } catch (failure) { button.disabled = false; toast(failure.message); }
  }; });
}

async function loadCompetitors() {
  setHeader("INTELIGÊNCIA COMERCIAL", "Concorrentes");
  $("#content").innerHTML = loadingStateHTML("Organizando a avaliação competitiva");
  const [records, insight] = await Promise.all([
    api("/api/records?module=concorrentes"),
    api("/api/competitors/insights"),
  ]);
  state.items = records.items;
  const writable = canAction("concorrentes", "create");
  $("#content").innerHTML = `<section class="competitor-hero"><div><p class="eyebrow gold">INTELIGÊNCIA COMERCIAL</p><h2>Avalie concorrentes com referência de mercado</h2><p>Cadastre evidências públicas, classifique a força competitiva e use os valores das últimas licitações e pregões como benchmark. O preço médio é informativo; a decisão comercial continua sob validação da equipe.</p></div><div class="competitor-hero-actions">${writable ? '<button id="competitorNew" class="primary">＋ Novo concorrente</button>' : ''}<span class="status">${records.items.length} cadastrado(s)</span></div></section>
    <section class="competitor-insight-grid"><article class="competitor-price-card"><span class="eyebrow">BENCHMARK RECENTE</span><strong>${insight.average == null ? "—" : money(insight.average)}</strong><p>Preço médio estimado das últimas ${insight.count || 0} licitações/pregões com valor informado.</p>${insight.available ? '<small>Base oficial persistida no Sistema Seccol</small>' : '<small>Sem valores de editais autorizados para comparação</small>'}</article><article class="competitor-method-card"><strong>Como interpretar</strong><p>Compare modalidade, objeto, órgão e região antes de usar a média. Valores estimados não substituem composição de custos, escopo ou condições do edital.</p></article></section>
    <section class="competitor-workspace"><header class="competitor-section-head"><div><p class="eyebrow gold">MAPA COMPETITIVO</p><h3>Concorrentes cadastrados</h3></div><input id="competitorFilter" class="filter-input" placeholder="Filtrar empresa, especialidade ou região"></header><div id="competitorCards" class="competitor-cards">${competitorCardsHTML(records.items)}</div></section>
    <section class="competitor-workspace competitor-latest"><header class="competitor-section-head"><div><p class="eyebrow gold">REFERÊNCIA DE PREÇO</p><h3>Últimas licitações e pregões com valor</h3></div><span class="status">${insight.latest?.length || 0} registros</span></header>${competitorLatestHTML(insight.latest || [])}</section>`;
  if ($("#competitorNew")) $("#competitorNew").onclick = () => openRecord(null, "concorrentes");
  $("#competitorFilter").oninput = (event) => {
    const query = event.target.value.trim().toLowerCase();
    $("#competitorCards").innerHTML = competitorCardsHTML(records.items.filter((item) => `${item.title} ${item.payload?.especialidade || ""} ${item.payload?.regiao || ""}`.toLowerCase().includes(query)));
    bindRows();
  };
  bindRows();
}

function competitorCardsHTML(items) {
  if (!items.length) return '<div class="empty">Nenhum concorrente encontrado. Cadastre o primeiro para iniciar a avaliação.</div>';
  return items.map((item) => {
    const payload = item.payload || {};
    const classification = payload.classificacao || "Sem avaliação";
    return `<article class="competitor-card"><header><div><span class="competitor-kicker">${escapeHTML(payload.especialidade || "Especialidade não informada")}</span><h4>${escapeHTML(item.title)}</h4></div><span class="competitor-rating">${escapeHTML(classification)}</span></header><div class="competitor-card-meta"><span><b>Região</b>${escapeHTML(payload.regiao || "Não informada")}</span><span><b>CNPJ</b>${escapeHTML(payload.cnpj || "Não informado")}</span><span><b>Status</b>${escapeHTML(item.status)}</span></div><p>${escapeHTML(payload.pontos_fortes || payload.observacao_avaliacao || "Adicione evidências, pontos fortes e observações para avaliar este concorrente.")}</p><footer><small>${payload.fonte ? "Fonte pública cadastrada" : "Fonte pública pendente"}</small><button class="secondary" data-edit="${item.id}">Abrir avaliação</button></footer></article>`;
  }).join("");
}

function competitorLatestHTML(items) {
  if (!items.length) return '<div class="empty">Nenhuma licitação ou pregão com valor informado foi encontrado.</div>';
  return `<div class="table-wrap borderless"><table class="data-table competitor-price-table"><thead><tr><th>Modalidade</th><th>Objeto</th><th>Órgão/UF</th><th>Valor estimado</th><th>Prazo</th><th>Situação</th></tr></thead><tbody>${items.map((item) => `<tr><td>${escapeHTML(item.modality || "Contratação")}</td><td class="title-cell"><strong>${escapeHTML(item.title || "Oportunidade")}</strong><small>${escapeHTML(item.object || "")}</small></td><td>${escapeHTML(item.agency || "—")}<br><small class="muted">${escapeHTML([item.uf].filter(Boolean).join("/"))}</small></td><td><strong>${money(item.value)}</strong></td><td>${dateBR(item.deadline)}</td><td><span class="status ${statusClass(item.status)}">${escapeHTML(item.status || "Novo")}</span></td></tr>`).join("")}</tbody></table></div>`;
}

function filterModuleStatus() {
  const status = $("#moduleStatus").value;
  const filtered = status ? state.items.filter((item) => item.status === status) : state.items;
  const leadButton = $("#newLeadsView");
  if (leadButton) leadButton.setAttribute("aria-pressed", String(status === "Novo lead"));
  $("#moduleData").innerHTML = renderModuleData(filtered, state.screen);
  bindRows();
}

function toggleNewLeadsView() {
  const select = $("#moduleStatus");
  const active = select.value === "Novo lead";
  select.value = active ? "" : "Novo lead";
  if (!active) state.viewMode = "table";
  filterModuleStatus();
}

function rerenderModuleData(module) {
  $("#moduleData").innerHTML = renderModuleData(state.items, module);
  bindRows();
}

function renderModuleData(items, module) {
  return kanbanModules.has(module) && state.viewMode === "kanban" ? kanbanHTML(items, module) : `<div class="table-wrap">${tableHTML(items, module)}</div>`;
}

function moduleTableColumns(module) {
  const fields = new Map((schemas[module] || []).map((field) => [field.key, field]));
  const preferred = moduleViewSpecs[module]?.columns || (schemas[module] || [])
    .filter((field) => field.type !== "checkbox" && !["tipo_pessoa", "tipo_cadastro"].includes(field.key))
    .slice(0, 4).map((field) => field.key);
  return preferred.map((key) => fields.get(key) || { key, label: key.replaceAll("_", " ") }).slice(0, 4);
}

function moduleCellValue(item, field) {
  const value = item.payload?.[field.key];
  if (value === true) return "Sim";
  if (value === false) return "Não";
  if (value == null || value === "") return "—";
  if (item.module === "clientes_fornecedores" && field.key === "documento") return documentBR(value);
  if (field.type === "date" || /(^|_)(data|validade|vencimento|fim|inicio|abertura|calibracao)$/.test(field.key)) return dateBR(value);
  if (field.type === "number" || /^(quantidade|probabilidade|preco_venda|preco_base|proxima_km)$/.test(field.key)) return String(value);
  return String(value);
}

function emptyStateHTML(module = "", message = "Nenhum registro encontrado.") {
  const canCreate = module && canAction(module, "create");
  const label = module ? (state.modules[module] || screenLabel(module) || "este módulo") : "";
  return `<div class="empty empty-actionable"><div class="empty-icon" aria-hidden="true">◇</div><strong>${escapeHTML(message)}</strong><p>${module ? `Ainda não há dados em ${escapeHTML(label.toLowerCase())} nesta empresa.` : "Tente ajustar os filtros ou use a busca global."}</p>${canCreate ? `<button type="button" class="secondary" data-empty-create="${escapeHTML(module)}">＋ ${escapeHTML(getRecordProfile(module).singular || "Novo registro")}</button>` : ""}</div>`;
}

function tableHTML(items, module = "") {
  if (!items.length) return emptyStateHTML(module);
  const columns = module ? moduleTableColumns(module) : [];
  const profile = module ? getRecordProfile(module) : null;
  const titleLabel = profile?.titleLabel || "Registro";
  return `<table class="data-table"><thead><tr><th>${escapeHTML(titleLabel)}</th>${columns.map((field) => `<th>${escapeHTML(field.label)}</th>`).join("")}<th>Situação</th><th>Prazo</th><th>Valor</th><th>Atualização</th><th>Ações</th></tr></thead><tbody>${items.map((item) => {
    const subject = item.payload?.assunto || item.subject?.name || "Sem assunto";
    const relationship = (item.payload?.relacionamentos || [])[0];
    const canUpdate = canAction(item.module, "update");
    const canDelete = canAction(item.module, "delete");
    return `<tr><td class="title-cell"><strong>${escapeHTML(item.title)}</strong><small>${module ? escapeHTML(subject) : `${escapeHTML(state.modules[item.module] || item.module)}${item.attachments?.length ? ` · ${item.attachments.length} arquivo(s)` : ""}`}</small></td>${columns.map((field) => `<td>${escapeHTML(moduleCellValue(item, field))}</td>`).join("")}<td><span class="status ${statusClass(item.status)}">${escapeHTML(item.status)}</span></td><td>${dateBR(item.due_date)}</td><td>${item.amount == null ? "—" : money(item.amount)}</td><td>${dateBR(item.updated_at)}</td><td><div class="row-actions"><button class="icon-button" data-edit="${item.id}" title="${canUpdate ? "Editar" : "Visualizar"}">${canUpdate ? "✎" : "◉"}</button>${canDelete ? `<button class="icon-button" data-delete="${item.id}" title="Mover para lixeira">×</button>` : ""}</div></td></tr>`;
  }).join("")}</tbody></table>`;
}

function kanbanHTML(items, module) {
  const stages = moduleStatuses[module] || [...new Set(items.map((item) => item.status))];
  return `<div class="kanban-wrap"><div class="kanban-board">${stages.map((stage) => {
    const cards = items.filter((item) => item.status === stage);
    return `<section class="kanban-column"><header><strong>${escapeHTML(stage)}</strong><span>${cards.length}</span></header>${cards.length ? cards.map((item) => `<button class="kanban-card" data-edit="${item.id}"><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.payload?.assunto || "Sem assunto")}</small><b>${item.amount == null ? "" : money(item.amount)}</b></button>`).join("") : '<div class="kanban-empty">Sem registros</div>'}</section>`;
  }).join("")}</div></div>`;
}

function bindRows() {
  $$('[data-edit]').forEach((button) => { button.onclick = () => openRecordById(Number(button.dataset.edit)); });
  $$('[data-delete]').forEach((button) => { button.onclick = () => confirmDelete(Number(button.dataset.delete)); });
  $$('[data-empty-create]').forEach((button) => { button.onclick = () => openRecord(null, button.dataset.emptyCreate); });
}

async function openRecordById(id) {
  try {
    const data = await api(`/api/records/${id}`);
    await openRecord(data.item, data.item.module);
  } catch (failure) { toast(failure.message); }
}

function applyRecordProfile(module, item = null) {
  const profile = getRecordProfile(module);
  state.currentFormProfile = profile;
  const dialog = $("#recordDialog");
  const form = $("#recordForm");
  const specifics = $("#recordSpecifics");
  const identification = $("#recordIdentification");
  if (specifics && identification && specifics.parentElement === identification.parentElement) {
    const sectionContainer = identification.parentElement;
    if (module === "clientes_fornecedores") {
      sectionContainer.insertBefore(specifics, identification);
      specifics.querySelector(".section-number")?.replaceChildren("01");
      identification.querySelector(".section-number")?.replaceChildren("02");
    } else {
      sectionContainer.insertBefore(identification, specifics);
      identification.querySelector(".section-number")?.replaceChildren("01");
      specifics.querySelector(".section-number")?.replaceChildren("02");
    }
  }
  dialog.style.setProperty("--record-accent", profile.accent);
  dialog.style.setProperty("--record-tint", profile.tint);
  dialog.dataset.recordModule = module;
  $("#recordProfileIcon").textContent = icons[module] || "◆";
  $("#recordEyebrow").textContent = module === "normas_tecnicas"
    ? profile.eyebrow
    : `${profile.eyebrow} · CADASTRO ESPECIALIZADO`;
  $("#recordModeBadge").textContent = item ? (canAction(module, "update") ? "EDIÇÃO" : "CONSULTA") : "NOVO";
  $("#recordDescription").textContent = profile.description;
  $("#dialogTitle").textContent = item
    ? `${canAction(module, "update") ? "Editar" : "Visualizar"} · ${profile.singular}`
    : `Novo · ${profile.singular}`;
  $("#identificationTitle").textContent = `Identificação e controle · ${profile.singular}`;
  $("#identificationHint").textContent = "Dados gerais para localização, situação, responsabilidade e prazo do registro.";
  $("#recordFieldsTitle").textContent = profile.fieldsTitle;
  $("#recordFieldsHint").textContent = profile.fieldsHint;
  if (module === "clientes_fornecedores") {
    $("#recordFieldsTitle").textContent = "Primeiro, informe o CPF ou CNPJ";
    $("#recordFieldsHint").textContent = "O documento identifica a natureza da pessoa e libera o restante do cadastro.";
  }
  $("#recordSpecificNav").innerHTML = `${escapeHTML(profile.fieldsTitle)}<small>${escapeHTML(profile.fieldsHint)}</small>`;
  $("#titleFieldLabel").textContent = `${profile.titleLabel} *`;
  form.title.placeholder = profile.titlePlaceholder;
  $("#amountFieldLabel").textContent = profile.amountLabel;
  $("#dueFieldLabel").textContent = profile.dueLabel;
  $("#responsibleFieldLabel").textContent = profile.responsibleLabel;
  form.responsavel.placeholder = `Informe ${profile.responsibleLabel.toLowerCase()}`;
  $("#contactFieldLabel").textContent = profile.contactLabel;
  form.contato.placeholder = profile.contactPlaceholder;
  $("#notesFieldLabel").textContent = profile.notesLabel;
  $("#statusFieldLabel").textContent = "Situação do fluxo *";
  $("#subjectFieldLabel").textContent = "Assunto principal *";
  form.notes.placeholder = profile.notesPlaceholder;
  form.assunto.placeholder = profile.subjectPlaceholder || `Ex.: ${profile.singular} · cliente / projeto · ano`;
  $("#saveRecordLabel").textContent = item ? `Salvar alterações de ${profile.singular.toLowerCase()}` : `Criar ${profile.singular.toLowerCase()}`;
  $("#amountField").classList.toggle("hidden", !profile.showAmount || !canAction(module, "view_values"));
  $("#dueField").classList.toggle("hidden", !profile.showDue);
  $("#responsibleField").classList.toggle("hidden", !profile.showResponsible);
  $("#contactField").classList.toggle("hidden", !profile.showContact);
  $("#recordSpecifics").classList.toggle("hidden", !(schemas[module] || []).length);
  bindFieldHelp();
  return profile;
}

async function openRecord(item = null, module = state.screen) {
  if (!item && !canAction(module, "create")) return toast("Seu acesso não permite criar neste módulo.");
  if (financialCategoryModules.has(module)) {
    try {
      const categories = await api("/api/financial/categories");
      state.financialCategories = categories.items || [];
    } catch (failure) {
      return toast(failure.message || "Não foi possível carregar as categorias financeiras.");
    }
  }
  state.currentRecord = item;
  updateAssistantContextUI();
  state.currentRelationships = item?.payload?.relacionamentos ? [...item.payload.relacionamentos] : [];
  const form = $("#recordForm");
  form.reset();
  applyRecordProfile(module, item);
  form.elements.id.value = item?.id || "";
  form.module.value = module;
  form.title.value = item?.title || "";
  form.amount.value = item?.amount == null ? "" : Number(item.amount).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
  form.due_date.value = item?.due_date?.slice(0, 10) || "";
  form.responsavel.value = item?.payload?.responsavel || "";
  form.contato.value = item?.payload?.contato || "";
  form.assunto.value = item?.payload?.assunto || "";
  if (form.assuntos_adicionais) form.assuntos_adicionais.value = (item?.payload?.assuntos_adicionais || []).join(", ");
  form.notes.value = item?.payload?.notes || "";
  $("#relationshipSearch").value = "";
  updateStatusOptions(module, item?.status || "");
  renderDynamicFields(module, item?.payload || {});
  updateFinancialEvidenceSection(form);
  $("#financialDocumentFile").value = "";
  $("#financialDocumentFileName").textContent = "PDF, imagem ou XML · até 10 MB";
  resetPartyDocumentLookup(form, item);
  configureNewPartyRoleAccess();
  if (item && !canAction(module, "update")) {
    form.querySelectorAll("input, select, textarea").forEach((field) => {
      if (field.type !== "hidden") field.disabled = true;
    });
  }
  if (!item && ["produtos", "instrumentos_seccol", "catalogo_servicos"].includes(module)) {
    const portfolioField = form.elements.extra_catalogo_seccol;
    if (portfolioField) portfolioField.checked = true;
  }
  syncPartyDocumentType(form);
  if (["clientes", "fornecedores"].includes(module) && !item?.payload?.tipo_cadastro) {
    const typeField = form.elements["extra_tipo_cadastro"];
    if (typeField) typeField.value = module === "fornecedores" ? "F" : "C";
  }
  renderRelationshipList();
  ui.recordDisclosure?.configure({ isEditing: Boolean(item) });
  state.formBaseline = draftSignature(drafts.capture(form, state.currentRelationships));
  offerRecordDraft(module, item?.id || "new");
  $("#normativeBlock").classList.toggle("hidden", !normativeModules.has(module));
  renderRecordResources(item);
  $("#recordForm button[type=submit]").classList.toggle("hidden", item ? !canAction(module, "update") : false);
  $("#formError").classList.add("hidden");
  if (!$("#recordDialog").open) $("#recordDialog").showModal();
  updateAssistantContextUI();
  updateRecordCompleteness();
  try {
    const [relations, partners] = await Promise.all([
      api("/api/relations/options"),
      api("/api/partners/options"),
    ]);
    state.relationOptions = relations.items.filter((record) => record.id !== item?.id);
    state.partyOptions = partners.items.filter((record) => record.id !== item?.id);
    populateRelationOptions();
    populateRecordReferenceFields(form, item?.payload || {});
    $("#relationshipSearch").oninput = (event) => populateRelationOptions(event.target.value);
    renderNormativeOptions();
    updateRecordCompleteness();
  } catch {
    state.relationOptions = [];
    state.partyOptions = [];
    form.registro_relacionado.innerHTML = '<option value="">Não foi possível carregar os vínculos</option>';
    renderNormativeOptions();
    updateRecordCompleteness();
  }
}

function draftSignature(draft) {
  return JSON.stringify({ values: draft?.values || {}, relationships: draft?.relationships || [] });
}

function currentDraftIdentity() {
  const form = $("#recordForm");
  return { module: form.module.value, id: form.elements.id.value || "new" };
}

function saveRecordDraftNow() {
  const dialog = $("#recordDialog");
  const form = $("#recordForm");
  if (!dialog.open || !form.module.value || !isWritable(form.module.value)) return false;
  const identity = currentDraftIdentity();
  const draft = drafts.capture(form, state.currentRelationships);
  if (draftSignature(draft) === state.formBaseline) {
    drafts.remove(identity.module, identity.id);
    return false;
  }
  return drafts.save(identity.module, identity.id, draft);
}

function scheduleRecordDraft() {
  clearTimeout(state.draftTimer);
  state.draftTimer = setTimeout(() => {
    if (saveRecordDraftNow()) ui.announce?.("Rascunho salvo nesta sessão");
  }, 600);
}

function offerRecordDraft(module, id) {
  const notice = $("#draftNotice");
  const draft = drafts.load(module, id);
  state.pendingDraft = draft;
  const different = draft && draftSignature(draft) !== state.formBaseline;
  notice.classList.toggle("hidden", !different);
  if (!different) return;
  $("#draftNoticeTime").textContent = `Salvo ${dateBR(draft.savedAt, true)} nesta sessão do navegador.`;
}

function restoreRecordDraft() {
  const draft = state.pendingDraft;
  if (!draft) return;
  ui.recordDisclosure?.expand();
  drafts.restore($("#recordForm"), draft);
  state.currentRelationships = Array.isArray(draft.relationships) ? [...draft.relationships] : [];
  renderRelationshipList();
  $("#draftNotice").classList.add("hidden");
  updateRecordCompleteness();
  toast("Rascunho restaurado. Revise antes de salvar.");
}

function discardRecordDraft() {
  const identity = currentDraftIdentity();
  drafts.remove(identity.module, identity.id);
  state.pendingDraft = null;
  $("#draftNotice").classList.add("hidden");
  toast("Rascunho descartado; o cadastro original foi mantido.");
}

function clearRecordDraftAfterSave() {
  clearTimeout(state.draftTimer);
  const identity = currentDraftIdentity();
  drafts.remove(identity.module, identity.id);
  state.pendingDraft = null;
  state.formBaseline = draftSignature(drafts.capture($("#recordForm"), state.currentRelationships));
  $("#draftNotice").classList.add("hidden");
}

function populateRelationOptions(query = "") {
  const form = $("#recordForm");
  const normalized = String(query || "").trim().toLowerCase();
  const items = (normalized ? state.relationOptions.filter((record) =>
    `${state.modules[record.module] || record.module} ${record.title}`.toLowerCase().includes(normalized)
  ) : state.relationOptions).slice(0, normalized ? 500 : 250);
  form.registro_relacionado.innerHTML = '<option value="">Selecione outro cadastro</option>' + items.map((record) =>
    `<option value="${record.module}:${record.id}">${escapeHTML(state.modules[record.module] || record.module)} — ${escapeHTML(record.title)}</option>`
  ).join("");
}

function updateStatusOptions(module, selected = "") {
  const allOptions = [...(moduleStatuses[module] || defaultStatuses)];
  const transitions = moduleStatusTransitions[module];
  let options = transitions
    ? (selected ? [selected, ...(transitions[selected] || [allOptions[0]])] : [allOptions[0]])
    : allOptions;
  if (selected && transitions && !canAction(module, "transition")) options = [selected];
  if (module === "vendas" && !canAction(module, "bill_sales")) {
    options = options.filter((status) => status !== "Faturado");
  }
  if (["contas_pagar", "contas_receber"].includes(module)) {
    if (!canAction(module, "settle_financial")) {
      options = options.filter((status) => !["Pago", "Recebido"].includes(status));
    }
    if (!canAction(module, "cancel_financial")) {
      options = options.filter((status) => status !== "Cancelado");
    }
  }
  if (selected && !options.includes(selected)) options.unshift(selected);
  const effectiveStatus = selected || options[0];
  $("#recordForm [name=status]").innerHTML = options.map((status) => `<option ${status === effectiveStatus ? "selected" : ""}>${escapeHTML(status)}</option>`).join("");
}

function canDecideApproval(approval) {
  if (approval.can_decide !== undefined) return Boolean(approval.can_decide);
  if (approval.status !== "Pendente" || !state.user) return false;
  if (Number(approval.requested_by) === Number(state.user.id)) return false;
  return Number(approval.requested_to) === Number(state.user.id)
    || ["admin", "manager"].includes(state.user.role);
}

function financialCategoryKind(module, source = {}) {
  const read = (name) => source?.elements
    ? source.elements[`extra_${name}`]?.value
    : source?.[name];
  if (module === "contas_pagar") return "EXPENSE";
  if (module === "contas_receber") return "INCOME";
  if (module === "financeiro") return { Receita: "INCOME", Despesa: "EXPENSE" }[read("tipo_lancamento")] || "";
  if (module === "caixa") return { Entrada: "INCOME", Saída: "EXPENSE" }[read("tipo_movimento")] || "";
  return "";
}

function financialCategoryOptions(module, selectedId = "", source = {}) {
  const kind = financialCategoryKind(module, source);
  const refreshingFromForm = Boolean(source?.elements);
  const compatible = (state.financialCategories || []).filter((category) => {
    const kindMatches = kind && [kind, "BOTH"].includes(category.kind);
    const selectedLegacy = !refreshingFromForm && String(category.id) === String(selectedId);
    return kindMatches && (category.active || selectedLegacy);
  });
  const prompt = kind ? "Selecione uma categoria cadastrada" : "Selecione primeiro o tipo do lançamento";
  return `<option value="">${prompt}</option>${compatible.map((category) => {
    const inactive = !category.active ? " · inativa" : "";
    return `<option value="${category.id}" ${String(category.id) === String(selectedId) ? "selected" : ""}>${escapeHTML(category.name)}${inactive}</option>`;
  }).join("")}`;
}

function refreshFinancialCategorySelect(form) {
  const select = form?.elements?.extra_categoria;
  const module = form?.module?.value;
  if (!select || !financialCategoryModules.has(module)) return;
  const selectedId = select.value;
  select.innerHTML = financialCategoryOptions(module, selectedId, form);
  if (![...select.options].some((option) => option.value === selectedId)) select.value = "";
}

function updateFinancialEvidenceSection(form = $("#recordForm")) {
  const section = $("#financialDocumentSection");
  if (!section || !form) return;
  const module = form.module.value;
  let visible = financialEvidenceModules.has(module);
  if (module === "financeiro") visible = form.elements.extra_tipo_lancamento?.value === "Despesa";
  if (module === "caixa") visible = form.elements.extra_tipo_movimento?.value === "Saída";
  visible = visible && canAction(module, "manage_attachments");
  section.classList.toggle("hidden", !visible);
  if (!visible) {
    const input = $("#financialDocumentFile");
    if (input) input.value = "";
    if ($("#financialDocumentFileName")) $("#financialDocumentFileName").textContent = "PDF, imagem ou XML · até 10 MB";
  }
}

function dynamicFieldHTML(field, payload, requiredFields, module) {
  const required = requiredFields.has(field.key);
  const fullClass = field.full || field.type === "textarea" ? "full" : "";
  const visibilityClass = required ? "record-essential" : "record-optional";
  const value = payload[field.key] ?? "";
  const referenceRule = recordReferenceRule(module, field.key, payload);
  const label = `${escapeHTML(referenceRule?.fieldLabel || field.label)}${required ? " *" : ""}`;
  const labelled = fieldHelpMarkup(field.key, label, module);
  const requiredAttribute = required ? 'required aria-required="true"' : "";
  if (referenceRule) {
    const selectedId = payload[`${field.key}_id`] || "";
    const legacy = !selectedId && value ? `<option value="" selected>Cadastro anterior: ${escapeHTML(value)}</option>` : "";
    return `<label class="field ${fullClass} ${visibilityClass} record-reference-field"><span>${labelled}</span><select name="extra_${field.key}" data-record-reference="${escapeHTML(field.key)}" data-selected-id="${escapeHTML(selectedId)}" ${requiredAttribute}>${legacy}<option value="">Carregando cadastros autorizados…</option></select><small class="field-reference-status">Selecione um cadastro da empresa para compartilhar os dados e o histórico.</small></label>`;
  }
  if (field.type === "financial-category") {
    const selectedId = payload.categoria_id || "";
    return `<label class="field ${fullClass} ${visibilityClass} financial-category-field"><span>${labelled}</span><select name="extra_${field.key}" data-financial-category ${requiredAttribute}>${financialCategoryOptions(module, selectedId, payload)}</select><small>As opções são cadastradas pelos administradores da empresa.</small></label>`;
  }
  if (field.type === "checkbox") return `<label class="check-field ${fullClass} ${visibilityClass}"><input name="extra_${field.key}" type="checkbox" ${value ? "checked" : ""}><span>${labelled}</span></label>`;
  if (field.type === "select") return `<label class="field ${fullClass} ${visibilityClass}"><span>${labelled}</span><select name="extra_${field.key}" ${requiredAttribute}><option value="">Selecione</option>${field.options.map((option) => `<option ${String(value) === option ? "selected" : ""}>${escapeHTML(option)}</option>`).join("")}</select></label>`;
  if (field.type === "textarea") return `<label class="field ${fullClass} ${visibilityClass}"><span>${labelled}</span><textarea name="extra_${field.key}" rows="4" ${requiredAttribute} placeholder="Descreva com informação suficiente para auditoria">${escapeHTML(value)}</textarea></label>`;
  const inputValue = ["date", "datetime-local"].includes(field.type) ? String(value).slice(0, field.type === "date" ? 10 : 16) : value;
  const placeholder = ["date", "datetime-local", "time"].includes(field.type) ? "" : `placeholder="Informe ${escapeHTML(field.label.toLowerCase())}"`;
  return `<label class="field ${fullClass} ${visibilityClass}"><span>${labelled}</span><input name="extra_${field.key}" type="${field.type}" ${field.type === "number" ? 'step="any"' : ""} ${requiredAttribute} ${placeholder} value="${escapeHTML(inputValue)}"></label>`;
}

function renderDynamicFields(module, payload) {
  const fields = schemas[module] || [];
  const profile = state.currentFormProfile || getRecordProfile(module);
  const requiredFields = new Set(profile.required || []);
  const fieldsByKey = new Map(fields.map((field) => [field.key, field]));
  const rendered = new Set();
  const groups = (profile.groups || [G(profile.fieldsTitle, profile.fieldsHint, fields.map((field) => field.key))]).map((group) => {
    const groupFields = group.keys.map((key) => fieldsByKey.get(key)).filter(Boolean);
    groupFields.forEach((field) => rendered.add(field.key));
    return { ...group, fields: groupFields };
  });
  const remaining = fields.filter((field) => !rendered.has(field.key));
  if (remaining.length) groups.push({ title: "Informações complementares", hint: "Dados adicionais próprios deste cadastro.", fields: remaining });
  const visibleGroups = groups.filter((group) => group.fields.length);
  $("#dynamicFields").innerHTML = visibleGroups.map((group, index) => {
    const optionalGroup = group.fields.every((field) => !requiredFields.has(field.key));
    return `<section class="dynamic-field-group ${visibleGroups.length === 1 ? "single" : ""} ${optionalGroup ? "record-optional-group" : ""}"><header><span>${String(index + 1).padStart(2, "0")}</span><div><h4>${escapeHTML(group.title)}</h4><p>${escapeHTML(group.hint || "")}</p></div></header><div class="dynamic-field-grid">${group.fields.map((field) => dynamicFieldHTML(field, payload, requiredFields, module)).join("")}</div></section>`;
  }).join("");
  if (module === "clientes_fornecedores") {
    const documentField = $("#recordForm").elements["extra_documento"];
    if (documentField) {
      documentField.value = documentBR(documentField.value);
      documentField.inputMode = "numeric";
      documentField.maxLength = 18;
      documentField.autocomplete = "off";
      documentField.setAttribute("aria-label", "CPF ou CNPJ");
    }
    const cepField = $("#recordForm").elements["extra_cep"];
    if (cepField) {
      cepField.value = cepBR(cepField.value);
      cepField.inputMode = "numeric";
      cepField.maxLength = 9;
      cepField.autocomplete = "postal-code";
      cepField.setAttribute("aria-label", "CEP");
    }
  }
  populateRecordReferenceFields($("#recordForm"), payload);
  bindFieldHelp();
  $("#recordSpecifics").classList.toggle("has-essential-fields", fields.some((field) => requiredFields.has(field.key)));
}

function configureNewPartyRoleAccess() {
  const form = $("#recordForm");
  if (form.module.value !== "clientes_fornecedores" || form.elements.id.value) return;
  const select = form.elements.extra_tipo_cadastro;
  if (!select) return;
  const canCreateClient = canAction("clientes", "create");
  const canCreateSupplier = canAction("fornecedores", "create");
  const roles = [
    ...(canCreateClient ? ["Cliente (C)"] : []),
    ...(canCreateSupplier ? ["Fornecedor (F)"] : []),
    ...(canCreateClient && canCreateSupplier ? ["Cliente e fornecedor (A)"] : []),
  ];
  select.innerHTML = roles.map((role) => `<option value="${role}">${role}</option>`).join("");
}

function referenceCandidateMatches(candidate, rule) {
  if (!rule.modules.includes(candidate.module)) return false;
  if (!rule.partyRole) return true;
  const role = String(candidate.party_type || (candidate.module === "fornecedores" ? "F" : "C"));
  if (rule.partyRole === "P") return ["C", "F", "A"].includes(role);
  if (rule.partyRole === "A") return ["C", "F", "A"].includes(role);
  return role === rule.partyRole || role === "A";
}

function recordReferenceOptionLabel(candidate) {
  const details = [candidate.code, candidate.document ? documentBR(candidate.document) : ""].filter(Boolean);
  return `${candidate.title}${details.length ? ` — ${details.join(" · ")}` : ""}`;
}

function populateRecordReferenceFields(form, payload = {}) {
  if (!form) return;
  form.querySelectorAll("[data-record-reference]").forEach((select) => {
    const field = select.dataset.recordReference;
    const rule = recordReferenceRule(form.module.value, field, payload);
    if (!rule) return;
    const source = rule.partyRole ? (state.partyOptions || []) : state.relationOptions;
    const candidates = source.filter((candidate) => referenceCandidateMatches(candidate, rule));
    const payloadSelectedId = payload[`${field}_id`];
    let selectedId = String(payloadSelectedId || select.value || select.dataset.selectedId || "");
    if (!selectedId && payload[field]) {
      const matches = candidates.filter((candidate) => candidate.title.localeCompare(String(payload[field]), "pt-BR", { sensitivity: "base" }) === 0);
      if (matches.length === 1) selectedId = String(matches[0].id);
    }
    const currentAvailable = candidates.some((candidate) => String(candidate.id) === selectedId);
    const legacy = selectedId && !currentAvailable && payloadSelectedId
      ? `<option value="${escapeHTML(selectedId)}" selected>${escapeHTML(payload[field] || "Cadastro indisponível")} — vínculo não autorizado</option>`
      : "";
    if (!currentAvailable && !legacy) selectedId = "";
    const emptyLabel = candidates.length
      ? `Selecione ${select.required ? "" : "(opcional)"}`.trim()
      : `Nenhum ${rule.partyRole === "F" ? "fornecedor" : rule.partyRole === "C" ? "cliente" : "cadastro"} disponível`;
    select.innerHTML = `${legacy}<option value="">${escapeHTML(emptyLabel)}</option>${candidates.map((candidate) => `<option value="${candidate.id}" ${String(candidate.id) === selectedId ? "selected" : ""}>${escapeHTML(recordReferenceOptionLabel(candidate))}</option>`).join("")}`;
    select.dataset.selectedId = selectedId;
    const helper = select.closest(".record-reference-field")?.querySelector(".field-reference-status");
    if (helper) helper.textContent = candidates.length
      ? `${candidates.length} cadastro(s) ativo(s) disponível(is) nesta empresa.`
      : "Nenhum cadastro ativo compatível. Cadastre ou restaure o parceiro antes de continuar.";
    const label = select.closest(".record-reference-field")?.querySelector("span");
    const schemaField = (schemas[form.module.value] || []).find((candidate) => candidate.key === field);
    if (label && schemaField) {
      label.textContent = `${rule.fieldLabel || schemaField.label}${select.required ? " *" : ""}`;
    }
  });
}

function refreshFinancialPartnerReference(form) {
  if (!form || form.module.value !== "financeiro") return;
  const select = form.elements.extra_parceiro;
  if (!select) return;
  select.dataset.selectedId = select.value || "";
  populateRecordReferenceFields(form);
}

function maskPartyDocumentField(field) {
  if (!field) return;
  const caret = field.selectionStart ?? field.value.length;
  const digitsBeforeCaret = field.value.slice(0, caret).replace(/\D/g, "").length;
  field.value = documentBR(field.value);
  if (document.activeElement !== field) return;
  let digitCount = 0;
  let nextCaret = 0;
  while (nextCaret < field.value.length && digitCount < digitsBeforeCaret) {
    if (/\d/.test(field.value[nextCaret])) digitCount += 1;
    nextCaret += 1;
  }
  field.setSelectionRange(nextCaret, nextCaret);
}

function cepBR(value) {
  const digits = String(value || "").replace(/\D/g, "").slice(0, 8);
  return digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
}

function maskPartyCepField(field) {
  if (!field) return;
  const caret = field.selectionStart ?? field.value.length;
  const digitsBeforeCaret = field.value.slice(0, caret).replace(/\D/g, "").length;
  field.value = cepBR(field.value);
  if (document.activeElement !== field) return;
  const nextCaret = digitsBeforeCaret > 5 ? digitsBeforeCaret + 1 : digitsBeforeCaret;
  field.setSelectionRange(Math.min(nextCaret, field.value.length), Math.min(nextCaret, field.value.length));
}

function updatePartyRegistrationStep(form) {
  if (!form || form.module.value !== "clientes_fornecedores") return;
  const documentField = form.elements["extra_documento"];
  if (!documentField) return;
  const digits = String(documentField.value || "").replace(/\D/g, "");
  const ready = digits.length === 11 || digits.length === 14;
  const lookupMatches = partyDocumentLookupState.document === digits;
  const lookupStatus = lookupMatches ? partyDocumentLookupState.status : "idle";
  const blocked = ["checking", "existing", "invalid"].includes(lookupStatus);
  const detailsReady = ready && !blocked;
  $("#recordIdentification")?.classList.toggle("hidden", !detailsReady);
  $("#recordRelationships")?.classList.toggle("hidden", !detailsReady);
  const groups = $$("#dynamicFields .dynamic-field-group");
  groups.forEach((group) => {
    const isIdentity = Boolean(group.querySelector('[name="extra_documento"]'));
    if (isIdentity) {
      group.classList.remove("hidden");
      group.querySelectorAll("input,select,textarea").forEach((field) => {
        const isDocument = field.name === "extra_documento";
        field.closest(".field,.check-field")?.classList.toggle("hidden", !isDocument && !detailsReady);
        field.disabled = !isDocument && !detailsReady;
      });
      return;
    }
    group.classList.toggle("hidden", !detailsReady);
    group.querySelectorAll("input,select,textarea").forEach((field) => { field.disabled = !detailsReady; });
  });
  if (ready) applyPartyFieldContext(form, digits);
  const hint = $("#recordFieldsHint");
  if (hint && !ready) hint.textContent = "Informe um CPF (11 dígitos) ou CNPJ (14 dígitos) para liberar o restante do cadastro.";
  if (hint && ready && lookupStatus === "checking") hint.textContent = "Verificando se este documento já pertence a um cadastro da empresa…";
  if (hint && ready && lookupStatus === "existing") hint.textContent = "Documento já cadastrado. Abra o cadastro encontrado em vez de preencher um novo.";
  if (hint && ready && lookupStatus === "invalid") hint.textContent = `${digits.length === 11 ? "CPF" : "CNPJ"} inválido. Corrija o documento para continuar.`;
  if (hint && ready && lookupStatus === "current") hint.textContent = "Cadastro existente carregado. Revise os dados antes de salvar alterações.";
  if (hint && ready && lookupStatus === "error") hint.textContent = "Formato válido; a consulta antecipada falhou e será repetida pelo servidor ao salvar.";
  if (hint && ready && lookupStatus === "available") hint.textContent = digits.length === 11
    ? "CPF válido e disponível: Pessoa física e Cliente (C)."
    : "CNPJ válido e disponível: Pessoa jurídica e Fornecedor (F).";
}

function setPartyFieldContext(form, key, { label, placeholder, visible = true, derived = false } = {}) {
  const control = form.elements["extra_" + key];
  if (!control) return;
  const wrapper = control.closest(".field,.check-field");
  wrapper?.classList.toggle("party-context-hidden", !visible);
  control.disabled = !visible;
  control.classList.toggle("party-derived-control", derived);
  if (derived) {
    control.setAttribute("aria-readonly", "true");
    control.tabIndex = -1;
  } else {
    control.removeAttribute("aria-readonly");
    control.removeAttribute("tabindex");
  }
  const labelElement = wrapper?.querySelector("span");
  if (labelElement && label) labelElement.textContent = label + (control.required ? " *" : "");
  if (placeholder != null && "placeholder" in control) control.placeholder = placeholder;
}

function applyPartyFieldContext(form, digits) {
  const isPhysical = digits.length === 11;
  const role = String(form.elements["extra_tipo_cadastro"]?.value || "");
  const isCustomer = role === "Cliente (C)" || role === "Cliente e fornecedor (A)";
  const isSupplier = role === "Fornecedor (F)" || role === "Cliente e fornecedor (A)";
  const isBoth = isCustomer && isSupplier;

  setPartyFieldContext(form, "documento", {
    label: isPhysical ? "CPF do cliente" : "CNPJ do fornecedor",
  });
  setPartyFieldContext(form, "tipo_pessoa", { derived: true });
  setPartyFieldContext(form, "codigo_cadastro", {
    label: "Código do parceiro",
    placeholder: "Gerado automaticamente ao salvar",
    derived: true,
  });
  const code = form.elements["extra_codigo_cadastro"];
  if (code) code.readOnly = true;
  setPartyFieldContext(form, "razao_social", {
    label: isPhysical ? "Nome completo" : "Razão social",
    placeholder: isPhysical ? "Informe o nome completo" : "Informe a razão social",
  });
  setPartyFieldContext(form, "nome_fantasia", {
    label: "Nome fantasia",
    placeholder: "Informe o nome fantasia",
    visible: !isPhysical,
  });

  setPartyFieldContext(form, "vendedor", { label: "Vendedor responsável", visible: isCustomer });
  setPartyFieldContext(form, "tabela_preco", { label: "Tabela de preços do cliente", visible: isCustomer });
  setPartyFieldContext(form, "aprovado_faturamento", { label: "Cliente aprovado para faturamento", visible: isCustomer });
  setPartyFieldContext(form, "avaliacao", { label: "Avaliação do fornecedor", visible: isSupplier });
  setPartyFieldContext(form, "aprovado_compras", { label: "Fornecedor aprovado para compras", visible: isSupplier });

  const identityGroup = form.elements["extra_documento"]?.closest(".dynamic-field-group");
  if (identityGroup) {
    const title = identityGroup.querySelector("h4");
    const hint = identityGroup.querySelector("header p");
    if (title) title.textContent = isBoth ? "Dados de cliente e fornecedor" : isSupplier ? "Dados do fornecedor" : "Dados do cliente";
    if (hint) hint.textContent = isPhysical
      ? "Identificação pessoal e classificação para atendimento comercial."
      : isBoth
        ? "Identificação empresarial válida para vendas e compras."
        : "Identificação empresarial e qualificação para fornecimento.";
  }

  const commercialGroup = form.elements["extra_categoria"]?.closest(".dynamic-field-group");
  if (commercialGroup) {
    const title = commercialGroup.querySelector("h4");
    const hint = commercialGroup.querySelector("header p");
    if (title) title.textContent = isBoth ? "Comercial e compras" : isSupplier ? "Qualificação do fornecedor" : "Política comercial do cliente";
    if (hint) hint.textContent = isBoth
      ? "Condições de venda, avaliação e liberações de compra."
      : isSupplier
        ? "Avaliação, categoria e liberação para compras."
        : "Responsabilidade comercial, preços e liberação para faturamento.";
  }
}

function syncPartyDocumentType(form) {
  if (!form || form.module.value !== "clientes_fornecedores") return;
  const documentField = form.elements["extra_documento"];
  const personField = form.elements["extra_tipo_pessoa"];
  const roleField = form.elements["extra_tipo_cadastro"];
  if (!documentField || !personField || !roleField) return;
  const digits = String(documentField.value || "").replace(/\D/g, "");
  if (digits.length === 11) {
    personField.value = "Pessoa física";
    if (!roleField.value) roleField.value = "Cliente (C)";
  }
  if (digits.length === 14) {
    personField.value = "Pessoa jurídica";
    if (!roleField.value) roleField.value = "Fornecedor (F)";
  }
  lookupExistingParty(form);
  updatePartyRegistrationStep(form);
}

let partyCepTimer = null;
let partyCepRequest = null;
let partyCnpjTimer = null;
let partyCnpjRequest = null;
let partyDocumentTimer = null;
let partyDocumentRequest = null;
let partyDocumentLookupState = { document: "", status: "idle", match: null, accessible: true };

function resetPartyDocumentLookup(form, item = null) {
  clearTimeout(partyDocumentTimer);
  partyDocumentRequest?.abort();
  partyDocumentRequest = null;
  const document = item && form?.module.value === "clientes_fornecedores"
    ? String(item.payload?.documento || "").replace(/\D/g, "")
    : "";
  partyDocumentLookupState = {
    document,
    status: document ? "current" : "idle",
    match: item ? { id: item.id, title: item.title } : null,
    accessible: true,
  };
  if (form) delete form.dataset.partyDuplicateId;
  renderPartyDocumentLookup(form);
}

function partyTypeLabel(value) {
  return { C: "Cliente (C)", F: "Fornecedor (F)", A: "Cliente e fornecedor (A)" }[value] || "Parceiro";
}

function renderPartyDocumentLookup(form) {
  const panel = $("#partyDocumentLookup");
  if (!panel) return;
  const state = partyDocumentLookupState;
  if (!form || form.module.value !== "clientes_fornecedores" || state.status === "idle") {
    panel.className = "party-document-lookup hidden";
    panel.replaceChildren();
    return;
  }
  panel.className = `party-document-lookup is-${state.status}`;
  if (state.status === "checking") {
    panel.innerHTML = '<span class="party-lookup-signal" aria-hidden="true"></span><div><strong>Verificando CPF/CNPJ…</strong><p>Procurando este documento nos clientes e fornecedores da empresa ativa.</p></div>';
    return;
  }
  if (state.status === "available") {
    panel.innerHTML = '<span class="party-lookup-mark" aria-hidden="true">✓</span><div><strong>Documento disponível para novo cadastro</strong><p>Nenhum cliente ou fornecedor ativo foi encontrado com este CPF/CNPJ.</p></div>';
    return;
  }
  if (state.status === "current") {
    panel.innerHTML = `<span class="party-lookup-mark" aria-hidden="true">✓</span><div><strong>Cadastro existente carregado</strong><p>${escapeHTML(state.match?.title || "Revise os dados do parceiro.")}</p></div>`;
    return;
  }
  if (state.status === "invalid") {
    panel.innerHTML = `<span class="party-lookup-mark" aria-hidden="true">!</span><div><strong>${escapeHTML(state.message || "Documento inválido")}</strong><p>Corrija o CPF/CNPJ antes de continuar.</p></div>`;
    return;
  }
  if (state.status === "error") {
    panel.innerHTML = '<span class="party-lookup-mark" aria-hidden="true">!</span><div><strong>Não foi possível antecipar a consulta</strong><p>Você pode continuar; o servidor verificará novamente antes de salvar.</p></div>';
    return;
  }
  if (!state.accessible || !state.match) {
    panel.innerHTML = '<span class="party-lookup-mark" aria-hidden="true">!</span><div><strong>CPF/CNPJ já cadastrado</strong><p>O cadastro pertence a uma área sem acesso para o seu perfil. Solicite ao responsável que abra ou atualize o parceiro existente.</p></div>';
    return;
  }
  const item = state.match;
  const details = [item.code, partyTypeLabel(item.partyType), item.status].filter(Boolean).join(" · ");
  panel.innerHTML = `<span class="party-lookup-mark" aria-hidden="true">!</span><div><strong>Cadastro já existente: ${escapeHTML(item.title)}</strong><p>${escapeHTML(details)}</p></div><button type="button" class="primary" data-open-existing-party="${Number(item.id)}">Abrir cadastro existente</button>`;
  panel.querySelector("[data-open-existing-party]").onclick = () => openRecordById(Number(item.id));
}

function lookupExistingParty(form) {
  if (!form || form.module.value !== "clientes_fornecedores") return;
  const digits = String(form.elements["extra_documento"]?.value || "").replace(/\D/g, "");
  clearTimeout(partyDocumentTimer);
  partyDocumentRequest?.abort();
  partyCnpjRequest?.abort();
  if (![11, 14].includes(digits.length)) {
    if (partyDocumentLookupState.status !== "idle" || partyDocumentLookupState.document) {
      partyDocumentLookupState = { document: digits, status: "idle", match: null, accessible: true };
      delete form.dataset.partyDuplicateId;
      renderPartyDocumentLookup(form);
    }
    return;
  }
  if (partyDocumentLookupState.document === digits &&
      ["checking", "available", "current", "existing", "invalid"].includes(partyDocumentLookupState.status)) return;
  partyDocumentLookupState = { document: digits, status: "checking", match: null, accessible: true };
  delete form.dataset.partyDuplicateId;
  renderPartyDocumentLookup(form);
  updatePartyRegistrationStep(form);
  partyDocumentTimer = setTimeout(async () => {
    partyDocumentRequest = new AbortController();
    const excludeId = Number(form.elements.id.value || 0);
    const query = new URLSearchParams({ document: digits });
    if (excludeId) query.set("excludeId", String(excludeId));
    try {
      const result = await api(`/api/partners/lookup?${query}`, { signal: partyDocumentRequest.signal });
      const currentDigits = String(form.elements["extra_documento"]?.value || "").replace(/\D/g, "");
      if (currentDigits !== digits) return;
      partyDocumentLookupState = result.exists
        ? { document: digits, status: "existing", match: result.item, accessible: result.accessible !== false }
        : { document: digits, status: "available", match: null, accessible: true };
      if (result.exists && result.item?.id) form.dataset.partyDuplicateId = String(result.item.id);
      if (!result.exists && digits.length === 14) lookupPartyCnpj(form);
    } catch (failure) {
      if (failure.name === "AbortError") return;
      partyDocumentLookupState = {
        document: digits,
        status: failure.code === "invalid_party_document" ? "invalid" : "error",
        match: null,
        accessible: true,
        message: failure.message,
      };
    }
    renderPartyDocumentLookup(form);
    updatePartyRegistrationStep(form);
    updateRecordCompleteness();
  }, 180);
}

function applyPartyLookupFields(form, fields) {
  Object.entries(fields || {}).forEach(([key, value]) => {
    const field = form.elements[`extra_${key}`];
    if (field && value) field.value = value;
  });
}

function lookupPartyCnpj(form) {
  if (!form || form.module.value !== "clientes_fornecedores") return;
  const documentField = form.elements["extra_documento"];
  const cnpj = String(documentField?.value || "").replace(/\D/g, "");
  clearTimeout(partyCnpjTimer);
  partyCnpjRequest?.abort();
  if (cnpj.length !== 14) return;
  partyCnpjTimer = setTimeout(async () => {
    partyCnpjRequest = new AbortController();
    try {
      const result = await api(`/api/partner-lookup?cnpj=${cnpj}`, { signal: partyCnpjRequest.signal });
      if (!result.configured) return;
      applyPartyLookupFields(form, result.fields);
      toast(`Dados preenchidos por ${result.source}. Confira antes de salvar.`);
      updateRecordCompleteness();
      scheduleRecordDraft();
    } catch (failure) {
      if (failure.name !== "AbortError" && failure.code !== "not_found") {
        toast("Não foi possível consultar o CNPJ; preencha os dados manualmente.");
      }
    }
  }, 450);
}

function lookupPartyCep(form) {
  if (!form || form.module.value !== "clientes_fornecedores") return;
  const cepField = form.elements["extra_cep"];
  if (!cepField) return;
  const cep = String(cepField.value || "").replace(/\D/g, "");
  clearTimeout(partyCepTimer);
  partyCepRequest?.abort();
  if (cep.length !== 8) return;
  partyCepTimer = setTimeout(async () => {
    partyCepRequest = new AbortController();
    try {
      const result = await api(`/api/partner-lookup?cep=${cep}`, { signal: partyCepRequest.signal });
      applyPartyLookupFields(form, result.fields);
      toast(`Endereço preenchido por ${result.source}. Confira antes de salvar.`);
      updateRecordCompleteness();
      scheduleRecordDraft();
    } catch (failure) {
      if (failure.name !== "AbortError") toast("Não foi possível consultar o CEP; preencha o endereço manualmente.");
    }
  }, 350);
}

function updateRecordCompleteness() {
  const form = $("#recordForm");
  const profile = state.currentFormProfile;
  if (!profile || !form.module.value) return;
  if (form.module.value === "clientes_fornecedores") {
    const digits = String(form.elements["extra_documento"]?.value || "").replace(/\D/g, "");
    if (![11, 14].includes(digits.length)) {
      $("#recordProgressValue").textContent = "0%";
      $("#recordProgressBar").style.width = "0%";
      $("#recordProgressHint").textContent = "Comece informando um CPF ou CNPJ válido.";
      $("#recordActionHint").textContent = "O restante do cadastro será liberado após identificar o documento.";
      $("#recordProfileHero").classList.remove("complete");
      ui.recordDisclosure?.setPending(true);
      return;
    }
    const lookupStatus = partyDocumentLookupState.document === digits
      ? partyDocumentLookupState.status : "idle";
    if (["checking", "existing", "invalid"].includes(lookupStatus)) {
      const messages = {
        checking: ["Verificando documento…", "Aguarde a consulta de duplicidade antes de continuar."],
        existing: ["Cadastro já existente", "Abra o cliente ou fornecedor encontrado; não crie outro cadastro."],
        invalid: ["Documento inválido", "Corrija o CPF/CNPJ para liberar o cadastro."],
      };
      $("#recordProgressValue").textContent = "0%";
      $("#recordProgressBar").style.width = "0%";
      $("#recordProgressHint").textContent = messages[lookupStatus][0];
      $("#recordActionHint").textContent = messages[lookupStatus][1];
      $("#recordProfileHero").classList.remove("complete");
      ui.recordDisclosure?.setPending(true);
      return;
    }
  }
  const checks = [
    { label: profile.titleLabel, complete: Boolean(form.title.value.trim()) },
    { label: "Assunto principal", complete: Boolean(form.assunto.value.trim()) },
    ...(profile.required || []).map((key) => {
      const field = (schemas[form.module.value] || []).find((candidate) => candidate.key === key);
      const control = form.elements[`extra_${key}`];
      return { label: field?.label || key, complete: field?.type === "checkbox" ? Boolean(control?.checked) : Boolean(String(control?.value || "").trim()) };
    }),
  ];
  if (normativeModules.has(form.module.value)) checks.push({ label: "Base normativa", complete: state.currentRelationships.some((relationship) => String(relationship.record || "").startsWith("normas_tecnicas:")) });
  const completed = checks.filter((check) => check.complete).length;
  const percent = checks.length ? Math.round((completed / checks.length) * 100) : 100;
  const missing = checks.filter((check) => !check.complete);
  $("#recordProgressValue").textContent = `${percent}%`;
  $("#recordProgressBar").style.width = `${percent}%`;
  $("#recordProgressHint").textContent = missing.length ? `Faltam ${missing.length}: ${missing.slice(0, 2).map((check) => check.label).join(" e ")}${missing.length > 2 ? "…" : "."}` : "Cadastro obrigatório completo e pronto para salvar.";
  $("#recordActionHint").textContent = missing.length ? `${missing.length} campo(s) obrigatório(s) ainda pendente(s).` : "Campos obrigatórios completos; revise os dados antes de salvar.";
  $("#recordProfileHero").classList.toggle("complete", percent === 100);
  ui.recordDisclosure?.setPending(missing.length);
}

function validateSpecializedRecord(form, module) {
  form.querySelectorAll(".field.invalid, .check-field.invalid").forEach((field) => field.classList.remove("invalid"));
  const missing = [];
  if (module === "clientes_fornecedores") {
    const documentControl = form.elements["extra_documento"];
    const digits = String(documentControl?.value || "").replace(/\D/g, "");
    if (![11, 14].includes(digits.length)) {
      $("#formError").textContent = "Informe um CPF (11 dígitos) ou CNPJ (14 dígitos) válido antes de continuar.";
      $("#formError").classList.remove("hidden");
      documentControl?.focus();
      return false;
    }
    const lookupStatus = partyDocumentLookupState.document === digits
      ? partyDocumentLookupState.status : "idle";
    if (lookupStatus === "checking") {
      $("#formError").textContent = "Aguarde a verificação deste CPF/CNPJ antes de continuar.";
      $("#formError").classList.remove("hidden");
      return false;
    }
    if (lookupStatus === "existing") {
      $("#formError").textContent = "Este CPF/CNPJ já possui cadastro. Abra o registro encontrado em vez de criar outro.";
      $("#formError").classList.remove("hidden");
      documentControl?.focus();
      return false;
    }
    if (lookupStatus === "invalid") {
      $("#formError").textContent = partyDocumentLookupState.message || "CPF/CNPJ inválido.";
      $("#formError").classList.remove("hidden");
      documentControl?.focus();
      return false;
    }
  }
  const controls = [form.title, form.assunto, ...(state.currentFormProfile?.required || []).map((key) => form.elements[`extra_${key}`])].filter(Boolean);
  controls.forEach((control) => {
    const complete = control.type === "checkbox" ? control.checked : Boolean(String(control.value || "").trim());
    if (!complete) {
      const wrapper = control.closest(".field, .check-field");
      wrapper?.classList.add("invalid");
      missing.push({ control, label: wrapper?.querySelector("span")?.textContent.replace("*", "").trim() || control.name });
    }
  });
  const hasNorm = !normativeModules.has(module) || state.currentRelationships.some((relationship) => String(relationship.record || "").startsWith("normas_tecnicas:"));
  if (!hasNorm) missing.push({ control: $("#normativeSelect"), label: "Base normativa vigente" });
  if (!missing.length) return true;
  $("#formError").textContent = `Complete os campos obrigatórios: ${missing.slice(0, 5).map((item) => item.label).join(", ")}${missing.length > 5 ? "…" : "."}`;
  $("#formError").classList.remove("hidden");
  ui.recordDisclosure?.ensureVisible(missing[0].control);
  missing[0].control?.closest(".record-form-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  missing[0].control?.focus({ preventScroll: true });
  return false;
}

function renderRelationshipList() {
  const area = $("#relationshipList");
  if (!area) return;
  area.innerHTML = state.currentRelationships.length ? state.currentRelationships.map((relationship, index) => {
    const id = Number(String(relationship.record || "").split(":").pop());
    const option = state.relationOptions.find((candidate) => candidate.id === id);
    const label = option ? `${state.modules[option.module] || option.module} — ${option.title}` : relationship.label || relationship.record;
    return `<span class="relationship-chip"><b>${escapeHTML(relationship.type || "Relacionado a")}</b>${escapeHTML(label || "Registro")}<button type="button" data-remove-relation="${index}" aria-label="Remover vínculo">×</button></span>`;
  }).join("") : '<small class="muted">Nenhum vínculo adicional.</small>';
  $$('[data-remove-relation]').forEach((button) => { button.onclick = () => {
    state.currentRelationships.splice(Number(button.dataset.removeRelation), 1);
    renderRelationshipList();
    scheduleRecordDraft();
  }; });
  updateRecordCompleteness();
}

function addRelationship() {
  const form = $("#recordForm");
  const record = form.registro_relacionado.value;
  if (!record) return toast("Selecione um registro para relacionar.");
  const type = form.tipo_relacao.value;
  if (!state.currentRelationships.some((relationship) => relationship.record === record && relationship.type === type)) state.currentRelationships.push({ record, type });
  form.registro_relacionado.value = "";
  renderRelationshipList();
  scheduleRecordDraft();
}

function renderNormativeOptions() {
  const select = $("#normativeSelect");
  if (!select) return;
  const norms = state.relationOptions.filter((record) =>
    record.module === "normas_tecnicas" && !["Obsoleta", "Cancelada", "Substituída"].includes(record.status)
  );
  select.innerHTML = '<option value="">Selecione a norma aplicável</option>' + norms.map((record) =>
    `<option value="normas_tecnicas:${record.id}">${escapeHTML(record.title)} · ${escapeHTML(record.status)}</option>`
  ).join("");
}

function addNormativeReference() {
  const record = $("#normativeSelect").value;
  if (!record) return toast("Selecione uma norma técnica.");
  if (!state.currentRelationships.some((relationship) => relationship.record === record)) {
    state.currentRelationships.push({ record, type: "Fundamentado em" });
  }
  $("#normativeSelect").value = "";
  renderRelationshipList();
  scheduleRecordDraft();
  toast("Base normativa vinculada ao documento.");
}

function renderRecordResources(item) {
  $("#recordResources").classList.toggle("hidden", !item);
  void window.SIVSWorkflowItems?.render(item, {
    api, state, money, escapeHTML, toast, dismissDialog,
  });
  void window.SIVSFinancialLedger?.render(item, {
    api, state, money, dateBR, escapeHTML, toast, dismissDialog, canAction,
  });
  if (!item) return;
  $("#attachmentList").innerHTML = item.attachments?.length ? item.attachments.map((attachment) => `<a class="resource-item" href="/api/attachments/${attachment.id}" target="_blank"><span>↓</span><div><strong>${escapeHTML(attachment.filename)}</strong><small>${escapeHTML(attachment.category || "Arquivo")} · ${Math.ceil(attachment.size / 1024)} KB</small></div></a>`).join("") : '<small class="muted">Nenhum arquivo anexado.</small>';
  $("#approvalList").innerHTML = item.approvals?.length ? item.approvals.map((approval) => `<div class="resource-item"><span class="status ${statusClass(approval.status)}">${escapeHTML(approval.status)}</span><div><strong>${escapeHTML(approval.approval_type)}</strong><small>${escapeHTML(approval.requested_to_name || "Qualquer aprovador")} · ${dateBR(approval.requested_at)}</small>${canDecideApproval(approval) ? `<div class="mini-actions"><button type="button" data-approval="${approval.id}" data-decision="Aprovado">✓ Aprovar</button><button type="button" data-approval="${approval.id}" data-decision="Rejeitado">× Rejeitar</button></div>` : approval.status === "Pendente" ? '<small class="muted">Aguardando decisão do responsável atribuído.</small>' : ""}</div></div>`).join("") : '<small class="muted">Nenhuma aprovação solicitada.</small>';
  $$('[data-approval]').forEach((button) => { button.onclick = () => decideApproval(Number(button.dataset.approval), button.dataset.decision); });
  $("#requestApproval").classList.toggle("hidden", !canAction(item.module, "request_approval"));
  $(".file-action").classList.toggle("hidden", !canAction(item.module, "manage_attachments"));
  $("#normAttachmentCategoryField").classList.toggle("hidden", item.module !== "normas_tecnicas");
  const reportActions = $("#technicalReportActions");
  if (reportActions) reportActions.remove();
  if (normativeModules.has(item.module)) {
    const actions = document.createElement("div");
    actions.id = "technicalReportActions";
    actions.className = "technical-report-actions";
    actions.innerHTML = `<a class="secondary" href="/api/reports/${item.id}/preview" target="_blank" rel="noopener">Visualizar prévia PDF</a>${canAction(item.module, "issue_report") ? '<button type="button" class="primary" id="issueTechnicalReport">Emitir versão controlada</button>' : ""}<small>A emissão final exige aprovação da revisão atual e cópias normativas licenciadas quando aplicável.</small>`;
    $("#recordResources").appendChild(actions);
    if ($("#issueTechnicalReport")) $("#issueTechnicalReport").onclick = issueTechnicalReport;
  }
}

async function issueTechnicalReport() {
  if (!state.currentRecord) return;
  if (!window.confirm("Emitir e arquivar a versão PDF controlada desta revisão?")) return;
  try {
    const result = await api(`/api/reports/${state.currentRecord.id}/issue`, {
      method: "POST", body: "{}",
    });
    const fresh = await api(`/api/records/${state.currentRecord.id}`);
    state.currentRecord = fresh.item;
    renderRecordResources(fresh.item);
    toast(`Documento emitido. SHA-256: ${result.sha256.slice(0, 12)}…`);
    window.open(result.downloadUrl, "_blank", "noopener");
  } catch (failure) {
    toast(failure.message);
  }
}

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Não foi possível ler o arquivo selecionado."));
    reader.readAsDataURL(file);
  });
}

async function saveRecord(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const id = formData.get("id");
  let amount = String(formData.get("amount") || "").trim();
  amount = amount.includes(",") ? amount.replace(/\./g, "").replace(",", ".") : amount;
  const module = formData.get("module");
  if (!validateSpecializedRecord(event.currentTarget, module)) return;
  if (normativeModules.has(module) && !state.currentRelationships.some((relationship) => {
    const target = state.relationOptions.find((record) => `normas_tecnicas:${record.id}` === relationship.record);
    return target?.module === "normas_tecnicas";
  })) {
    $("#formError").textContent = "Vincule ao menos uma norma técnica antes de salvar este documento.";
    $("#formError").classList.remove("hidden");
    return;
  }
  const payload = {
    responsavel: formData.get("responsavel"), contato: formData.get("contato"),
    assunto: formData.get("assunto"),
    assuntos_adicionais: String(formData.get("assuntos_adicionais") || "").split(",").map((item) => item.trim()).filter(Boolean),
    tipo_relacao: formData.get("tipo_relacao"), registro_relacionado: "",
    relacionamentos: state.currentRelationships, notes: formData.get("notes"),
  };
  for (const field of schemas[module] || []) {
    const element = event.currentTarget.elements[`extra_${field.key}`];
    const referenceRule = recordReferenceRule(module, field.key);
    if (referenceRule) {
      const selectedId = String(formData.get(`extra_${field.key}`) || "");
      const referenceSource = referenceRule.partyRole ? (state.partyOptions || []) : state.relationOptions;
      const selected = referenceSource.find((candidate) => String(candidate.id) === selectedId);
      payload[`${field.key}_id`] = selected ? Number(selected.id) : null;
      payload[field.key] = selected?.title || state.currentRecord?.payload?.[field.key] || "";
      if (module === "normas_tecnicas" && field.key === "norma_substituta" && selected) {
        payload.relacionamentos.push({ record: `normas_tecnicas:${selected.id}`, type: "Substituída por" });
      }
    } else if (field.type === "financial-category") {
      const selectedId = String(formData.get(`extra_${field.key}`) || "");
      const selected = (state.financialCategories || []).find((category) => String(category.id) === selectedId);
      payload.categoria_id = selected ? Number(selected.id) : null;
      payload.categoria = selected?.name || "";
    } else {
      payload[field.key] = field.type === "checkbox" ? Boolean(element?.checked) : formData.get(`extra_${field.key}`);
    }
  }
  if (module === "clientes_fornecedores") {
    payload.documento = String(payload.documento || "").replace(/\D/g, "");
  }
  const body = { module, title: formData.get("title"), status: formData.get("status"), amount: amount || null, due_date: formData.get("due_date") || null, payload, revision: state.currentRecord?.revision };
  const submitButton = event.currentTarget.querySelector('button[type="submit"]');
  const submitLabel = $("#saveRecordLabel");
  const originalSubmitLabel = submitLabel?.textContent || "Salvar registro";
  if (submitButton?.disabled) return;
  if (submitButton) {
    submitButton.disabled = true;
    submitButton.setAttribute("aria-busy", "true");
  }
  if (submitLabel) submitLabel.textContent = id ? "Salvando alterações…" : "Criando registro…";
  $("#recordActionHint").textContent = "Validando e salvando com segurança no servidor…";
  try {
    const evidence = $("#financialDocumentFile")?.files?.[0];
    if (evidence) {
      if (evidence.size > 10 * 1024 * 1024) throw new Error("O arquivo deve possuir até 10 MB.");
      body.attachment = {
        filename: evidence.name,
        mime_type: evidence.type || "application/octet-stream",
        content: await readFileAsDataURL(evidence),
        category: module === "fiscal" ? "Documento fiscal" : "Nota fiscal / comprovante de despesa",
      };
    }
    const result = await api(id ? `/api/records/${id}` : "/api/records", { method: id ? "PUT" : "POST", body: JSON.stringify(body) });
    clearRecordDraftAfterSave();
    dismissDialog($("#recordDialog"));
    if (result.financialRecordId) {
      const financialLabel = result.financialModule === "contas_pagar"
        ? "Conta a pagar" : "Conta a receber";
      toast(`${financialLabel} #${result.financialRecordId} gerada e vinculada à origem.`);
    } else {
      toast(id ? "Registro atualizado com histórico preservado." : "Registro criado e conectado ao assunto.");
    }
    if (state.currentSubjectId) return openSubject(state.currentSubjectId);
    return navigate(state.screen);
  } catch (failure) {
    $("#formError").textContent = failure.code === "write_conflict"
      ? `${failure.message} O formulário foi mantido aberto para você copiar os dados antes de recarregar.`
      : failure.message;
    $("#formError").classList.remove("hidden");
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
      submitButton.removeAttribute("aria-busy");
    }
    if (submitLabel) submitLabel.textContent = originalSubmitLabel;
    updateRecordCompleteness();
  }
}

async function uploadAttachment(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file || !state.currentRecord) return;
  if (file.size > 10 * 1024 * 1024) return toast("O arquivo deve possuir até 10 MB.");
  const category = state.currentRecord.module === "normas_tecnicas"
    ? $("#normAttachmentCategory")?.value || "Evidência"
    : "Evidência";
  const isLicensedCopy = category === "Cópia normativa licenciada";
  if (isLicensedCopy && !window.confirm(
    "Confirme que a SECCOL possui autorização ou licença para armazenar esta cópia normativa."
  )) return;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      await api(`/api/records/${state.currentRecord.id}/attachments`, { method: "POST", body: JSON.stringify({ filename: file.name, mime_type: file.type || "application/octet-stream", content: reader.result, category, version: state.currentRecord.payload?.edicao || "", license_confirmed: isLicensedCopy }) });
      const fresh = await api(`/api/records/${state.currentRecord.id}`);
      state.currentRecord = fresh.item;
      renderRecordResources(fresh.item);
      toast("Arquivo anexado.");
    } catch (failure) { toast(failure.message); }
  };
  reader.readAsDataURL(file);
}

async function requestApproval() {
  if (!state.currentRecord) return;
  const comment = window.prompt("Comentário para o aprovador (opcional):", "Revisar e aprovar este registro.");
  if (comment === null) return;
  try {
    await api(`/api/records/${state.currentRecord.id}/approval`, { method: "POST", body: JSON.stringify({ approval_type: "Aprovação do registro", comment }) });
    const fresh = await api(`/api/records/${state.currentRecord.id}`);
    state.currentRecord = fresh.item;
    renderRecordResources(fresh.item);
    await refreshNotifications();
    toast("Aprovação solicitada e notificada.");
  } catch (failure) { toast(failure.message); }
}

async function decideApproval(id, status) {
  const comment = window.prompt(`Comentário da decisão (${status}):`, "");
  if (comment === null) return;
  try {
    await api(`/api/approvals/${id}`, { method: "POST", body: JSON.stringify({ status, comment }) });
    toast(`Registro ${status.toLowerCase()}.`);
    if (state.currentRecord) {
      const fresh = await api(`/api/records/${state.currentRecord.id}`);
      state.currentRecord = fresh.item;
      renderRecordResources(fresh.item);
    } else {
      loadApprovals();
    }
  } catch (failure) { toast(failure.message); }
}

function confirmDelete(id) {
  state.deleteId = id;
  $("#confirmDialog").showModal();
}

async function deleteRecord() {
  try {
    await api(`/api/records/${state.deleteId}`, { method: "DELETE" });
    dismissDialog($("#confirmDialog"));
    toast("Registro movido para a lixeira recuperável.");
    if (state.currentSubjectId) return openSubject(state.currentSubjectId);
    return navigate(state.screen);
  } catch (failure) { toast(failure.message); }
}

async function loadSubjects(query = "") {
  setHeader("INTELIGÊNCIA RELACIONAL", "Central de assuntos");
  $("#content").innerHTML = loadingStateHTML("Carregando assuntos relacionados");
  const data = await api(`/api/subjects?q=${encodeURIComponent(query)}`);
  state.subjects = data.items;
  $("#content").innerHTML = `<section class="subject-hero"><div><p class="eyebrow gold">VISÃO INTEGRADA</p><h2>O assunto conecta toda a empresa.</h2><p>Clientes, propostas, licitações, O.S., qualidade, frota, documentos e financeiro na mesma linha de contexto.</p></div><strong>${data.items.filter((item) => item.status === "Ativo").length}<small>assuntos ativos</small></strong></section><div class="subject-toolbar"><input id="subjectSearch" class="filter-input" placeholder="Pesquisar assunto" value="${escapeHTML(query)}"></div><section class="subject-grid">${subjectsHTML(data.items)}</section>`;
  $("#subjectSearch").oninput = (event) => { clearTimeout(state.searchTimer); state.searchTimer = setTimeout(() => loadSubjects(event.target.value), 280); };
  $$('[data-subject]').forEach((button) => { button.onclick = () => openSubject(Number(button.dataset.subject)); });
}

function subjectsHTML(items) {
  if (!items.length) return '<div class="empty">Nenhum assunto criado.</div>';
  return items.map((item) => `<button class="subject-card ${item.status !== "Ativo" ? "archived" : ""}" data-subject="${item.id}"><span class="subject-card-icon">◈</span><span><strong>${escapeHTML(item.name)}</strong><small>${item.record_count} registro(s) · ${escapeHTML(item.status)} · ${dateBR(item.last_activity || item.updated_at)}</small></span><b>Abrir →</b></button>`).join("");
}

async function openSubject(id) {
  const data = await api(`/api/subjects/${id}`);
  state.currentSubjectId = id;
  state.items = data.records;
  const canManage = ["admin", "manager"].includes(state.user.role);
  const targets = state.subjects.filter((item) => item.id !== id && item.status === "Ativo");
  $("#content").innerHTML = `<button class="text-button subject-back" id="subjectBack">← Voltar aos assuntos</button><section class="subject-detail"><div><p class="eyebrow gold">ASSUNTO</p><h2>${escapeHTML(data.subject.name)}</h2><span class="status ${statusClass(data.subject.status)}">${escapeHTML(data.subject.status)}</span> <span class="status">${data.records.length} registro(s)</span></div>${canManage ? `<div class="subject-actions"><button class="secondary" id="renameSubject">Renomear</button><button class="secondary" id="archiveSubject">${data.subject.status === "Arquivado" ? "Reativar" : "Arquivar"}</button>${targets.length ? `<select id="mergeTarget"><option value="">Unificar com…</option>${targets.map((item) => `<option value="${item.id}">${escapeHTML(item.name)}</option>`).join("")}</select><button class="secondary" id="mergeSubject">Unificar</button>` : ""}</div>` : ""}</section><div class="table-wrap">${tableHTML(data.records)}</div>`;
  $("#subjectBack").onclick = () => loadSubjects();
  if ($("#renameSubject")) $("#renameSubject").onclick = () => renameSubject(data.subject);
  if ($("#archiveSubject")) $("#archiveSubject").onclick = () => subjectAction(id, "archive", { archived: data.subject.status !== "Arquivado" });
  if ($("#mergeSubject")) $("#mergeSubject").onclick = () => {
    const targetId = Number($("#mergeTarget").value);
    if (!targetId) return toast("Selecione o assunto de destino.");
    if (window.confirm("Unificar os dois assuntos? Os registros serão preservados.")) subjectAction(id, "merge", { target_id: targetId });
  };
  bindRows();
}

async function renameSubject(subject) {
  const name = window.prompt("Novo nome do assunto:", subject.name);
  if (!name || name === subject.name) return;
  return subjectAction(subject.id, "rename", { name });
}

async function subjectAction(id, action, body) {
  try {
    await api(`/api/subjects/${id}/${action}`, { method: "POST", body: JSON.stringify(body) });
    toast("Assunto atualizado sem perder os relacionamentos.");
    return loadSubjects();
  } catch (failure) { toast(failure.message); }
}

async function loadApprovals() {
  setHeader("GOVERNANÇA", "Aprovações");
  $("#content").innerHTML = loadingStateHTML("Carregando aprovações", "Conferindo decisões pendentes e seu nível de acesso.");
  const data = await api("/api/approvals?status=%20");
  const cards = data.items.map((item) => `<article class="approval-card">
    <div><span class="status ${statusClass(item.status)}">${escapeHTML(item.status)}</span><small>${escapeHTML(state.modules[item.module] || item.module)}</small></div>
    <h3>${escapeHTML(item.title)}</h3>
    <p>${escapeHTML(item.request_comment || item.comment || "Sem comentário")}</p>
    <small>Solicitado em ${dateBR(item.requested_at)} · ${escapeHTML(item.requested_to_name || "Fila geral")}</small>
    ${canDecideApproval(item) ? `<div class="approval-actions"><button class="primary" data-approval="${item.id}" data-decision="Aprovado">✓ Aprovar</button><button class="secondary" data-approval="${item.id}" data-decision="Rejeitado">Rejeitar</button></div>` : item.status === "Pendente" ? '<small class="muted">Somente o responsável atribuído, um gestor ou um administrador pode decidir.</small>' : ""}
  </article>`).join("");
  $("#content").innerHTML = `<section class="module-context"><div><p class="eyebrow gold">FLUXO CONTROLADO</p><h2>Aprovações e decisões</h2><p>Solicitações de compra, documentos, propostas e qualquer cadastro podem usar o mesmo fluxo auditável.</p></div><span class="status">${data.items.filter((item) => item.status === "Pendente").length} pendente(s)</span></section><section class="approval-grid">${cards || '<div class="empty">Nenhuma aprovação registrada.</div>'}</section>`;
  $$('[data-approval]').forEach((button) => { button.onclick = () => decideApproval(Number(button.dataset.approval), button.dataset.decision); });
}

async function loadXmlImports() {
  setHeader("FISCAL", "Importar XML NF-e");
  const data = await api("/api/records?module=importacoes_xml");
  state.items = data.items;
  $("#content").innerHTML = `<section class="module-context"><div><p class="eyebrow gold">IMPORTAÇÃO RASTREÁVEL</p><h2>XML NF-e de entrada ou devolução</h2><p>Confere chave, emitente e CNPJ destinatário, preserva o XML e relaciona fornecedor, produtos e parcelas. A importação não substitui a validação fiscal oficial do documento.</p></div><span class="status">${data.items.length} nota(s)</span></section>${canAction("importacoes_xml", "import_xml") ? `<section class="xml-drop panel"><div class="xml-icon">XML</div><div><h3>Selecione o XML da NF-e</h3><p>Antes de importar, confira o CNPJ da empresa ativa em Configurações. O sistema rejeita notas emitidas para outro CNPJ.</p><label class="field"><span>Assunto principal (opcional)</span><input id="xmlSubject" placeholder="Ex.: Compra de filtros HEPA — agosto/2026"></label><label class="file-action prominent">Escolher arquivo XML<input id="xmlFile" type="file" accept=".xml,application/xml,text/xml" hidden></label></div><div id="xmlResult" class="xml-result hidden"></div></section>` : ""}<section class="panel"><div class="panel-head"><h3>Histórico de importações</h3><span class="status">Sem duplicidade por chave</span></div><div class="table-wrap borderless">${tableHTML(data.items)}</div></section>`;
  if ($("#xmlFile")) $("#xmlFile").onchange = importXmlFile;
  bindRows();
}

async function importXmlFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  const result = $("#xmlResult");
  result.classList.remove("hidden");
  result.innerHTML = '<span class="search-pulse"></span> Lendo e conferindo a NF-e…';
  try {
    const data = await api("/api/xml/import", { method: "POST", body: JSON.stringify({ filename: file.name, xml: await file.text(), assunto: $("#xmlSubject").value.trim() }) });
    result.innerHTML = `<strong>✓ Importação concluída</strong><span>${data.items} item(ns), ${data.createdProducts} produto(s) novo(s), ${data.parcels} parcela(s) e fornecedor ${escapeHTML(data.supplier)}.</span>`;
    toast("NF-e importada e relacionada.");
    setTimeout(loadXmlImports, 900);
  } catch (failure) {
    result.innerHTML = `<strong>Importação não concluída</strong><span>${escapeHTML(failure.message)}</span>`;
  }
}

function sourceType(item) {
  const mode = String(item.payload?.modo_coleta || "").toLowerCase();
  if (String(item.payload?.categoria || "").toLowerCase().includes("mercado privado")) return "private";
  if (mode.includes("api automática")) return "automatic";
  return "manual";
}

async function loadSources(filter = "all") {
  setHeader("INTELIGÊNCIA COMERCIAL", "Fontes de busca");
  const data = await api("/api/tenders/sources");
  state.tenderSources = data.items;
  $("#content").innerHTML = `<section class="tender-hero"><div><p class="eyebrow gold">CATÁLOGO OPERACIONAL</p><h2>Fontes automáticas, manuais e privadas.</h2><p>O catálogo não pesquisa sozinho ao ser aberto: PNCP e Compras.gov são disparados pelo botão <strong>Pesquisar agora</strong>. Os demais portais abrem em um clique para consulta manual segura.</p></div><span class="source-count">${data.items.length}<small>fontes cadastradas</small></span></section><div class="source-command"><button class="primary" id="sourceRunNow">⌕ Executar busca oficial agora</button><span>Automáticas: PNCP + contingência Compras.gov · demais fontes: acesso manual</span></div><section class="panel"><div class="source-toolbar"><button class="source-filter ${filter === "all" ? "active" : ""}" data-source-filter="all">Todas</button><button class="source-filter ${filter === "automatic" ? "active" : ""}" data-source-filter="automatic">Automáticas</button><button class="source-filter ${filter === "manual" ? "active" : ""}" data-source-filter="manual">Consulta manual</button><button class="source-filter ${filter === "private" ? "active" : ""}" data-source-filter="private">Prospecção privada</button></div><div class="source-grid">${sourcesHTML(data.items.filter((item) => filter === "all" || sourceType(item) === filter))}</div></section>`;
  $("#sourceRunNow").onclick = () => navigate("editais");
  $$('[data-source-filter]').forEach((button) => { button.onclick = () => loadSources(button.dataset.sourceFilter); });
  $$('[data-go]').forEach((button) => { button.onclick = () => navigate(button.dataset.go); });
}

function sourcesHTML(items) {
  return items.map((item) => {
    const type = sourceType(item);
    const labels = { automatic: "Automática", manual: "Manual", private: "Prospecção" };
    const last = item.payload?.ultima_execucao ? `Última execução: ${dateBR(item.payload.ultima_execucao, true)}` : "Ainda não executada pelo sistema";
    return `<article class="source-card"><span class="source-badge ${type}">${labels[type]}</span><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.payload?.abrangencia || "")}</small><p>${escapeHTML(item.payload?.modo_coleta || "Consulta catalogada")}</p><small class="source-last">${escapeHTML(last)}${item.payload?.ultimo_estado ? ` · ${escapeHTML(item.payload.ultimo_estado)}` : ""}</small>${type === "automatic" ? '<button class="source-open" data-go="editais">Abrir painel e pesquisar</button>' : `<a class="source-open" href="${escapeHTML(safeExternalURL(item.payload?.url))}" target="_blank" rel="noopener noreferrer">Abrir e buscar manualmente ↗</a>`}</article>`;
  }).join("");
}

function tenderCoverageHTML(coverage) {
  const labels = {
    HEALTHY: "Cobertura saudável", RUNNING: "Atualizando agora",
    ATTENTION: "Recuperação automática", CRITICAL: "Intervenção necessária",
    INITIALIZING: "Primeiro ciclo pendente", PAUSED: "Agente pausado",
  };
  const tone = coverage.health === "CRITICAL" ? "error" : coverage.health === "ATTENTION" ? "warning" : "ok";
  const retry = coverage.retries?.find((item) => item.status === "ABANDONED") || coverage.retries?.[0];
  return `<section class="panel tender-coverage-panel ${tone}" aria-labelledby="tenderCoverageTitle">
    <div class="panel-head"><div><p class="eyebrow gold">CONTROLE DE COBERTURA</p><h3 id="tenderCoverageTitle">${escapeHTML(labels[coverage.health] || coverage.health)}</h3><small>${escapeHTML(coverage.message || "")}</small></div><span class="status ${tone === "error" ? "erro" : tone === "warning" ? "pendente" : "ativo"}">${coverage.pendingRetries || 0} retentativa(s)</span></div>
    <div class="tender-coverage-grid"><div><small>ÚLTIMO CICLO OFICIAL</small><strong>${coverage.lastSuccessfulAt ? dateBR(coverage.lastSuccessfulAt, true) : "Ainda não concluído"}</strong></div><div><small>PRÓXIMO CICLO</small><strong>${coverage.nextRunAt ? dateBR(coverage.nextRunAt, true) : "Sem agenda ativa"}</strong></div><div><small>VARREDURA DO CATÁLOGO</small><strong>${coverage.queryTotal || 0} termos · ${coverage.estimatedSweepHours || 0}h estimadas</strong></div><div><small>CONSULTAS POR CICLO</small><strong>${coverage.queriesPerCycle || 0}</strong></div></div>
    ${retry ? `<div class="coverage-exception ${retry.status === "ABANDONED" ? "error" : ""}" role="${retry.status === "ABANDONED" ? "alert" : "status"}"><strong>${retry.status === "ABANDONED" ? "Retentativas esgotadas" : "Lacuna sendo recuperada"}</strong><span>${escapeHTML((retry.failedQueries || []).join(" · ") || retry.last_error || "Nova tentativa do ciclo oficial")}</span><small>${retry.next_attempt_at ? `Próxima tentativa: ${dateBR(retry.next_attempt_at, true)}` : `${retry.attempt_count || 0} de 5 tentativas realizadas`}</small></div>` : ""}
  </section>`;
}

function tenderExceptionCenterHTML(items) {
  if (!items.length) return `<section class="panel tender-exception-center"><div class="panel-head"><div><p class="eyebrow gold">CENTRAL DE EXCEÇÕES</p><h3>Nenhuma leitura documental pendente</h3><small>Novas falhas de documento ou OCR aparecerão aqui automaticamente.</small></div><span class="status ativo">Em ordem</span></div></section>`;
  const critical = items.filter((item) => item.severity === "CRITICAL").length;
  return `<section class="panel tender-exception-center ${critical ? "has-critical" : ""}" aria-labelledby="tenderExceptionCenterTitle"><div class="panel-head"><div><p class="eyebrow gold">CENTRAL DE EXCEÇÕES</p><h3 id="tenderExceptionCenterTitle">${items.length} leitura(s) exigem conferência</h3><small>Ordenadas por criticidade e prazo do edital.</small></div><span class="status ${critical ? "erro" : "pendente"}">${critical} crítica(s)</span></div><div class="tender-exception-list">${items.slice(0, 20).map((item) => `<button type="button" data-tender-detail="${item.tender_result_id}"><span><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.agency || "Órgão não informado")} · prazo ${dateBR(item.deadline, true)}</small></span><span><b>${escapeHTML(item.document_name || "Documento oficial")}${item.page_number ? `, pág. ${item.page_number}` : ""}</b><small>${escapeHTML(item.message)}</small></span></button>`).join("")}</div></section>`;
}

async function loadTenderSearch() {
  setHeader("INTELIGÊNCIA COMERCIAL", "Busca de editais");
  $("#content").innerHTML = loadingStateHTML("Preparando a busca de editais", "Carregando fontes, filtros, planos e oportunidades já encontradas.");
  const [results, sources, history, schedules, coverageData, exceptionData] = await Promise.all([api("/api/tenders/results"), api("/api/tenders/sources"), api("/api/tenders/history"), api("/api/tenders/schedules"), api("/api/tenders/coverage"), api("/api/tenders/exceptions")]);
  state.tenderResults = results.items;
  state.tenderSources = sources.items;
  state.tenderHistory = history.items;
  state.tenderSchedules = schedules.items;
  state.tenderCoverage = coverageData.coverage;
  state.tenderExceptions = exceptionData.items;
  const strictItems = results.items.filter((item) => item.strict_match);
  const counts = Object.fromEntries(["Novo", "Analisar", "Aprovado", "Convertido", "Descartado"].map((status) => [status, strictItems.filter((item) => item.status === status).length]));
  const defaults = sources.defaultKeywords;
  const quality = results.quality || {};
  const precision = quality.precisionPercent == null ? "Ainda não medida" : `${quality.precisionPercent}%`;
  $("#content").innerHTML = `<section class="tender-hero"><div><p class="eyebrow gold">INTELIGÊNCIA SECCOL</p><h2>Fontes → pesquisa → triagem → licitação</h2><p>Vocabulário especializado em controle de contaminação ambiental, áreas limpas, cabines, HEPA/ULPA, qualificação, certificação e ensaios.</p></div><span class="source-count">${sources.items.length}<small>fontes prontas</small></span></section>
  <section class="tender-search-box"><div class="tender-search-head"><div><h3>Executar pesquisa oficial agora</h3><p>O PNCP aceita até oito consultas seguras por execução. O sistema alterna os lotes da mesma lista até cobrir todos os termos; se a fonte falhar, o Compras.gov é acionado como contingência.</p></div><span class="status">Ação manual e auditada</span></div><div class="tender-search-grid"><div id="tenderKeywordEditor" class="field keywords-field keyword-editor"><button id="tenderKeywordToggle" class="keyword-editor-toggle" type="button" aria-expanded="true"><span><b>Palavras-chave SECCOL</b><small>Toque para revisar ou alterar a lista</small></span><strong id="tenderKeywordSummary">0 termos</strong></button><span class="keyword-editor-label">Palavras-chave SECCOL</span><div id="tenderKeywordChips" class="keyword-chip-box" role="group" aria-label="Editor de palavras-chave"><input id="tenderKeywordInput" class="keyword-chip-input" autocomplete="off" placeholder="Digite e pressione Enter ou vírgula" aria-describedby="tenderKeywordHelp tenderKeywordReport"></div><textarea id="tenderKeywords" class="visually-hidden" tabindex="-1" aria-hidden="true"></textarea><div class="keyword-toolbar"><button id="importTenderKeywords" type="button" class="secondary">Importar planilha</button><button id="downloadTenderKeywordTemplate" type="button" class="secondary">Baixar modelo CSV</button><button id="clearTenderKeywords" type="button" class="secondary">Limpar</button><input id="tenderKeywordFile" type="file" accept=".xlsx,.csv,.txt,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv" hidden></div><div class="keyword-editor-meta"><span id="tenderKeywordHelp">Enter, vírgula, ponto e vírgula ou colagem de células adicionam termos.</span><strong id="tenderKeywordCount">0/80 palavras-chave</strong></div><output id="tenderKeywordReport" class="keyword-report" aria-live="polite"></output></div><label class="field"><span>UF</span><select id="tenderUf"><option value="">Brasil inteiro</option>${["TO", "PA", "MA", "GO", "MT", "DF", "SP", "MG", "RJ", "ES", "BA", "PE", "CE", "PR", "SC", "RS", "AM", "RO", "AC", "RR", "AP", "PI", "RN", "PB", "AL", "SE", "MS"].map((uf) => `<option>${uf}</option>`).join("")}</select></label><label class="field"><span>Publicados nos últimos</span><select id="tenderDays"><option value="3">3 dias</option><option value="7" selected>7 dias</option><option value="15">15 dias</option><option value="30">30 dias</option></select></label><button id="runTenderSearch" class="primary tender-run" ${canAction("editais", "search_tenders") ? "" : "disabled"}>⌕ Pesquisar agora</button></div><div id="tenderProgress" class="tender-progress hidden" role="status" aria-live="polite"><div class="progress-top"><span class="search-pulse"></span><strong id="progressStage">Preparando pesquisa…</strong><time id="progressTime">0s</time></div><div class="source-live-status"><span id="pncpSourceState">PNCP: aguardando</span><span id="comprasSourceState">Compras.gov: contingência</span></div><div class="progress-track"><span id="progressBar"></span></div><div class="progress-steps"><span class="active">Conexão</span><span>Fontes oficiais</span><span>Filtro SECCOL</span><span>Gravação</span></div></div><p id="tenderSearchMessage" class="search-message hidden"></p></section>
  ${tenderCoverageHTML(coverageData.coverage)}
  ${tenderExceptionCenterHTML(exceptionData.items)}
  <section class="tender-quality-grid" aria-label="Qualidade medida da busca"><div class="tender-quality-card"><span>Precisão validada</span><strong>${precision}</strong><small>${quality.evaluated || 0} edital(is) avaliados por pessoas${quality.minimumSampleReached ? "" : " · mínimo recomendado: 30"}</small></div><div class="tender-quality-card"><span>O que este número mede</span><strong>${quality.relevant || 0} aderentes</strong><small>Acertos entre resultados marcados como aderentes ou não aderentes. Cobertura externa absoluta depende da disponibilidade e indexação dos portais oficiais.</small></div></section>
  <section class="summary-strip tender-summary">${["Novo", "Analisar", "Aprovado", "Convertido", "Descartado"].map((status) => `<button type="button" class="summary-item" data-tender-summary="${status}"><span>${status}</span><strong>${counts[status]}</strong></button>`).join("")}</section>
  <section class="panel"><div class="panel-head"><div><h3>Oportunidades encontradas</h3><small class="muted">Por padrão, somente editais compatíveis com os ${results.portfolioCount || 0} produtos e serviços ativos da empresa. A IA só lê documentos quando você solicitar.</small></div><div class="toolbar-filters tender-toolbar-filters"><input id="tenderFilter" class="filter-input" type="search" placeholder="Objeto, órgão, cidade, UF ou termo"><select id="tenderCompatibility" class="filter-select"><option value="strict">Compatíveis com o catálogo</option><option value="all">Todos os armazenados</option></select><select id="tenderStatus" class="filter-select"><option value="">Todas as situações</option>${["Novo", "Analisar", "Aprovado", "Convertido", "Descartado"].map((status) => `<option>${status}</option>`).join("")}</select><output id="tenderFilteredCount" class="status">${strictItems.length} resultado(s)</output></div></div><div id="tenderResultsArea" class="tender-results">${tenderResultsHTML(strictItems)}</div></section>
  <section class="monitor-layout"><div class="panel"><div class="panel-head"><div><h3>Planos de pesquisa</h3><small class="muted">O agente principal pesquisa às 7h, de segunda a sábado. Planos adicionais seguem a recorrência escolhida enquanto o servidor estiver ligado.</small></div><span class="status">${schedules.items.length}</span></div><div class="panel-body">${schedulesHTML(schedules.items)}</div></div>${canAction("editais", "manage_tender_schedules") ? `<form id="scheduleForm" class="panel schedule-form"><div class="panel-head"><h3>Salvar plano</h3></div><div class="panel-body"><label class="field"><span>Nome</span><input name="name" value="Monitor SECCOL"></label><label class="field"><span>Recorrência</span><select name="frequency"><option value="manual">Manual</option><option value="daily">Diária</option><option value="weekly">Semanal</option></select></label><p class="muted mini-note">O agendador interno mantém histórico, progresso real e a próxima execução. Com o servidor desligado, a tarefa será retomada no próximo ciclo após a inicialização.</p><button class="primary wide" type="submit">Salvar filtros atuais</button></div></form>` : ""}</section>
  <section class="panel"><div class="panel-head"><h3>Histórico das pesquisas</h3><span class="status">Últimas ${history.items.length}</span></div><div class="panel-body">${searchHistoryHTML(history.items)}</div></section>`;
  tenderKeywordEditor = window.SIVSTenderKeywords?.mount({
    root: $("#tenderKeywordEditor"), initial: defaults, api, toast,
    companyName: state.user.companyName || "SECCOL",
  });
  $("#runTenderSearch").onclick = runTenderSearch;
  $("#tenderFilter").oninput = filterTenderResults;
  $("#tenderCompatibility").onchange = filterTenderResults;
  $("#tenderStatus").onchange = filterTenderResults;
  $$('[data-tender-summary]').forEach((button) => { button.onclick = () => {
    $("#tenderStatus").value = $("#tenderStatus").value === button.dataset.tenderSummary ? "" : button.dataset.tenderSummary;
    filterTenderResults();
  }; });
  if ($("#scheduleForm")) $("#scheduleForm").onsubmit = saveSearchSchedule;
  $$('[data-schedule]').forEach((button) => { button.onclick = () => useSchedule(Number(button.dataset.schedule)); });
  bindTenderActions();
}

function tenderResultsHTML(items) {
  if (!items.length) return '<div class="empty"><div class="empty-icon">⌕</div><strong>Nenhum edital atende aos filtros.</strong><br>Altere os filtros ou execute uma nova pesquisa.</div>';
  const rows = items.map((item) => {
    const priority = { HIGH: "Alta", NORMAL: "Normal", LOW: "Baixa" }[item.catalog_priority] || "Sem prioridade";
    const matchCount = item.catalog_match_count || (item.portfolio_matches || []).length;
    const triage = canAction("editais", "triage_tenders");
    const feedback = triage ? `<div class="result-feedback" aria-label="Validar aderência da busca"><button class="secondary" data-tender-feedback="${item.id}:relevant" aria-label="Marcar edital como aderente" aria-pressed="${item.relevance_feedback === "relevant"}" title="Aderente">↑</button><button class="secondary" data-tender-feedback="${item.id}:irrelevant" aria-label="Marcar edital como não aderente" aria-pressed="${item.relevance_feedback === "irrelevant"}" title="Não aderente">↓</button></div>` : "";
    const officialObject = escapeHTML(item.object_text || "Objeto não informado pelo PNCP");
    const catalogMatches = (item.portfolio_matches || []).map((match) => escapeHTML(match.title));
    const catalogRelation = item.strict_match
      ? `<div class="tender-catalog-relation"><b>Relação com o catálogo interno</b><span>${catalogMatches.join(" · ") || `${matchCount} item(ns) relacionado(s)`}</span></div>`
      : '<div class="tender-catalog-relation is-unmatched"><b>Relação com o catálogo interno</b><span>Nenhuma correspondência rígida identificada.</span></div>';
    const criteria = (item.matched_terms || []).map((term) => `#${escapeHTML(term)}`).join(" ");
    const objectCell = `<div class="tender-object-cell"><small class="tender-object-label">OBJETO PUBLICADO · PNCP</small><p class="tender-object-preview">${officialObject}</p><details class="tender-object-full"><summary>Ver texto completo do objeto</summary><p>${officialObject}</p></details>${catalogRelation}${criteria ? `<small class="tender-match-criteria">Critérios encontrados: ${criteria}</small>` : ""}</div>`;
    const adherence = item.strict_match
      ? `<div class="tender-adherence is-confirmed"><span class="score high" title="Aderência estimada contra o catálogo ativo da empresa.">${item.relevance_score}%</span><strong>Compatível</strong><small>${priority} prioridade · ${matchCount} item(ns)</small></div>`
      : `<div class="tender-adherence is-review"><span class="score" title="Aderência estimada contra o catálogo ativo da empresa.">${item.relevance_score}%</span><strong>Revisar aderência</strong><small>Sem coincidência rígida</small></div>`;
    const actions = `<div class="result-actions"><button class="secondary tender-details-button" data-tender-detail="${item.id}">Ver edital</button><a class="icon-button" href="${escapeHTML(safeExternalURL(item.source_url))}" target="_blank" rel="noopener noreferrer" title="Abrir fonte oficial" aria-label="Abrir fonte oficial">↗</a>${item.status !== "Convertido" && triage ? `<button class="secondary tender-action" data-tender-status="${item.id}:Analisar" title="Colocar em análise" aria-label="Colocar edital em análise">◎ <span>Analisar</span></button>` : ""}${item.status !== "Convertido" && canAction("editais", "convert_tender") && canAction("licitacoes", "create") ? `<button class="secondary tender-action tender-action-convert" data-tender-convert="${item.id}" title="Converter esta oportunidade em licitação" aria-label="Converter esta oportunidade em licitação">✓ <span>Converter</span></button>` : ""}${item.status !== "Convertido" && triage ? `<button class="secondary tender-action tender-action-discard" data-tender-status="${item.id}:Descartado" title="Descartar esta oportunidade" aria-label="Descartar esta oportunidade">× <span>Descartar</span></button>` : ""}${item.status === "Convertido" ? '<span class="converted-label">Convertido</span>' : ""}</div>`;
    return `<tr><td>${adherence}</td><td>${escapeHTML(item.modality || "Contratação")}</td><td class="title-cell">${objectCell}</td><td><strong>${escapeHTML(item.agency || "—")}</strong><br><small class="muted">${escapeHTML([item.municipality, item.uf].filter(Boolean).join("/"))}</small></td><td>${dateBR(item.deadline, true)}</td><td>${item.estimated_value == null ? '<small class="muted">Verificar no PNCP</small>' : money(item.estimated_value)}</td><td><span class="status ${statusClass(item.status)}">${escapeHTML(item.status)}</span></td><td>${actions}${feedback}</td></tr>`;
  }).join("");
  return `<div class="table-wrap borderless"><table class="data-table tender-table"><thead><tr><th title="Aderência estimada contra o catálogo ativo da empresa.">Aderência</th><th>Modalidade</th><th>Objeto publicado</th><th>Órgão/UF</th><th>Prazo</th><th>Valor oficial</th><th>Situação</th><th>Ações e validação</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function bindTenderActions() {
  $$('[data-tender-detail]').forEach((button) => { button.onclick = () => showTenderDetail(Number(button.dataset.tenderDetail)); });
  $$('[data-tender-status]').forEach((button) => { button.onclick = async () => {
    const [id, status] = button.dataset.tenderStatus.split(":");
    if (status === "Descartado" && !window.confirm("Descartar esta oportunidade da triagem? Ela permanecerá no histórico, mas não será tratada como pendência ativa.")) return;
    button.disabled = true;
    try { await api(`/api/tenders/results/${id}`, { method: "PUT", body: JSON.stringify({ status }) }); toast(status === "Descartado" ? "Oportunidade descartada." : "Oportunidade colocada em análise."); loadTenderSearch(); } catch (failure) { button.disabled = false; toast(failure.message); }
  }; });
  $$('[data-tender-convert]').forEach((button) => { button.onclick = async () => {
    if (!window.confirm("Converter esta oportunidade em uma licitação? Os dados oficiais serão usados para iniciar o cadastro.")) return;
    button.disabled = true;
    try { await api(`/api/tenders/convert/${button.dataset.tenderConvert}`, { method: "POST", body: "{}" }); toast("Oportunidade convertida em licitação."); loadTenderSearch(); } catch (failure) { button.disabled = false; toast(failure.message); }
  }; });
  $$('[data-tender-feedback]').forEach((button) => { button.onclick = async () => {
    const [id, relevanceFeedback] = button.dataset.tenderFeedback.split(":");
    try {
      await api(`/api/tenders/results/${id}`, { method: "PUT", body: JSON.stringify({ relevanceFeedback }) });
      toast("Aderência registrada. A medição de precisão foi atualizada.");
      loadTenderSearch();
    } catch (failure) { toast(failure.message); }
  }; });
}

function tenderAIAnalysisHTML(analysis, id) {
  if (analysis?.status === "failed") return `<section class="tender-detail-section ai-analysis"><h3>Leitura assistida por IA</h3><div class="analysis-state error" role="alert"><strong>A análise não foi concluída</strong><p>${escapeHTML(analysis.message || "Não foi possível concluir a leitura.")}</p>${analysis.pagesRead ? `<small>${analysis.pagesRead} página(s) tiveram texto extraído antes da falha.</small>` : ""}${analysis.skipped?.length ? `<small>Documentos pendentes: ${escapeHTML(analysis.skipped.join(" · "))}</small>` : ""}</div><button class="primary" data-tender-analyze="${id}">Tentar novamente</button><p id="tenderAnalysisStatus" class="muted" role="status" aria-live="polite"></p></section>`;
  if (!analysis?.result) return `<section class="tender-detail-section ai-analysis"><h3>Leitura assistida por IA</h3><p class="muted">A IA lê o texto extraível dos documentos oficiais, aponta exigências e cita páginas. A validação final continua sendo humana.</p><button class="primary" data-tender-analyze="${id}">Ler documentos com IA</button><p id="tenderAnalysisStatus" class="muted" role="status" aria-live="polite"></p></section>`;
  const result = analysis.result;
  // Metadados do provedor não fazem parte da experiência de leitura do edital.
  analysis.model = "";
  const text = (value) => typeof value === "string" ? value : value?.achado || value?.evento || JSON.stringify(value || "");
  const list = (label, values) => Array.isArray(values) && values.length ? `<div class="analysis-block"><strong>${label}</strong><ul>${values.map((value) => `<li>${escapeHTML(text(value))}</li>`).join("")}</ul></div>` : "";
  const participation = result.participacao || {};
  const draft = (label, value, kind) => value ? `<section class="analysis-draft"><div><strong>${label}</strong><small>Rascunho para revisão jurídica antes de qualquer protocolo.</small></div><textarea readonly id="${kind}-${id}">${escapeHTML(value)}</textarea><button class="secondary" data-copy-draft="${kind}-${id}">Copiar rascunho</button></section>` : "";
  return `<section class="tender-detail-section ai-analysis"><div class="panel-head"><div><h3>Dossiê de participação — leitura por IA</h3><small class="muted">${escapeHTML(analysis.model || "IA")} · ${analysis.pagesRead || 0} página(s) lida(s) · revisão humana obrigatória</small></div><button class="secondary" data-tender-analyze="${id}">Atualizar leitura</button></div><p>${escapeHTML(result.resumo || "Sem resumo retornado.")}</p><div class="participation-status"><strong>Compatibilidade para participar: ${escapeHTML(participation.situacao || "não verificada")}</strong><p>${escapeHTML(participation.justificativa || "Confirme os documentos e requisitos antes de decidir.")}</p>${list("Checklist de participação", participation.itens)}</div>${list("Prazos e marcos", result.prazos)}${list("Habilitação", result.habilitacao)}${list("Requisitos técnicos", result.requisitos_tecnicos)}${list("Obrigações do contrato", result.obrigacoes_contratadas)}${list("Critérios de julgamento", result.criterios_julgamento)}${list("Riscos, dúvidas e pendências", result.riscos_pendencias)}<div class="analysis-block"><strong>Recomendação operacional</strong><p>${escapeHTML(result.recomendacao || "Validar os documentos oficiais.")}</p></div>${draft("Minuta de pedido de esclarecimento", result.minuta_esclarecimento, "esclarecimento")}${draft("Minuta de impugnação", result.minuta_impugnacao, "impugnacao")}${Array.isArray(result.citacoes) && result.citacoes.length ? `<div class="analysis-block"><strong>Referências no edital</strong><ul>${result.citacoes.map((citation) => `<li>${escapeHTML(`${citation.document || "Documento"}, pág. ${citation.pagina || "?"}: ${citation.achado || ""}`)}</li>`).join("")}</ul></div>` : ""}${analysis.skipped?.length ? `<p class="muted">Pendências de leitura: ${escapeHTML(analysis.skipped.join(" · "))}</p>` : ""}${analysis.imagePages?.length ? `<p class="muted">Páginas com imagem ou tabela em imagem — a IA não leu o conteúdo visual, consulte o PDF: ${escapeHTML(analysis.imagePages.map((entry) => `${entry.document}, pág. ${entry.page}`).join(" · "))}</p>` : ""}</section>`;
}

function tenderExtractionHTML(extraction, exceptions, id) {
  const open = (exceptions || []).filter((item) => item.status === "OPEN");
  const critical = open.filter((item) => item.severity === "CRITICAL");
  const deadlines = extraction?.deadlines || [];
  const requirements = extraction?.suggestedRequirements || [];
  const list = (items, formatter) => items.length ? `<ul>${items.slice(0, 20).map((item) => `<li>${formatter(item)}</li>`).join("")}</ul>` : '<p class="muted">Nenhum achado determinístico nesta categoria.</p>';
  return `<section class="tender-detail-section deterministic-extraction ${critical.length ? "has-critical" : ""}" aria-labelledby="tenderExtractionTitle"><div class="panel-head"><div><p class="eyebrow gold">LEITURA VERIFICÁVEL</p><h3 id="tenderExtractionTitle">Extração determinística e OCR</h3><small class="muted">Regras locais com documento e página; funciona mesmo sem conclusão da IA.</small></div><button class="secondary" data-tender-extract="${id}">${extraction?.generatedAt ? "Atualizar extração" : "Extrair prazos e exigências"}</button></div>${extraction?.generatedAt ? `<div class="extraction-summary"><span class="status ${critical.length ? "erro" : extraction.status === "PARTIAL" ? "pendente" : "ativo"}">${escapeHTML(extraction.status || "CONCLUÍDA")}</span><span>${extraction.pagesRead || 0} página(s)</span><span>${extraction.ocrPages?.length || 0} por OCR</span><span>OCR: ${escapeHTML(extraction.ocrEngine || "não informado")}</span></div><div class="extraction-grid"><div><strong>Prazos encontrados</strong>${list(deadlines, (item) => `<b>${escapeHTML(item.value)}</b> <small>${escapeHTML(item.reference)}</small><span>${escapeHTML(item.evidence)}</span>`)}</div><div><strong>Exigências sugeridas ao checklist</strong>${list(requirements, (item) => `<b>${escapeHTML(item.title || item.documentType)}</b> <small>${escapeHTML(item.reference)}</small><span>${escapeHTML(item.evidence)}</span>`)}</div></div>` : '<p class="muted">Execute antes de confirmar o checklist. PDFs textuais são locais; páginas escaneadas usam o Tesseract do servidor.</p>'}${open.length ? `<div class="extraction-exceptions" role="${critical.length ? "alert" : "status"}"><strong>${critical.length ? "Exceções críticas bloqueiam checklist e proposta" : "Pendências de leitura"}</strong>${open.map((item) => `<article><div><b>${escapeHTML(item.document_name || "Documento oficial")}${item.page_number ? `, pág. ${item.page_number}` : ""}</b><span>${escapeHTML(item.message)}</span></div>${canAction("editais", "triage_tenders") ? `<button class="secondary" data-resolve-tender-exception="${id}:${item.id}">Registrar conferência</button>` : ""}</article>`).join("")}</div>` : ""}<p id="tenderExtractionStatus" class="muted" role="status" aria-live="polite"></p></section>`;
}

function tenderDocumentCardHTML(document, index, resultId) {
  const title = document.titulo || document.tipoDocumentoNome || "Documento oficial PNCP";
  const kind = document.tipoDocumentoNome || "Documento oficial";
  const published = dateBR(document.dataPublicacaoPncp, true);
  const meta = [kind, published && published !== "Não informado" ? `publicado em ${published}` : "data não informada"].join(" · ");
  return `<li class="tender-document-card"><div class="tender-document-card-main"><span class="eyebrow">DOCUMENTO OFICIAL</span><strong>${escapeHTML(title)}</strong><span>${escapeHTML(meta)}</span></div><div class="tender-document-card-actions"><button type="button" class="primary" data-tender-preview="${resultId}:${index}" data-tender-title="${escapeHTML(title)}">Ver no sistema</button><a class="secondary" download href="/api/tenders/results/${resultId}/documentos/${index}">Baixar</a></div></li>`;
}

async function showTenderDetail(id) {
  const dialog = $("#tenderDetailDialog");
  const content = $("#tenderDetailContent");
  content.innerHTML = loadingStateHTML("Consultando dados oficiais do PNCP", "Buscando documentos, itens e histórico da contratação.");
  if (!dialog.open) dialog.showModal();
  try {
    const response = await api(`/api/tenders/results/${id}`);
    const item = response.item;
    const official = item.official;
    const participationDocuments = window.SIVSTenderDocuments?.detailHTML(item.participationDocuments, item.id, {
      escapeHTML,
      editable: canAction("editais", "triage_tenders"),
    }) || "";
    const commercialProposal = window.SIVSTenderProposal?.detailHTML(
      item.commercialProposal, item.id, { escapeHTML },
    ) || "";
    const portalAgent = window.SIVSTenderPortalAgent?.detailHTML(
      item.portalAgent, item.id, { escapeHTML },
    ) || "";
    const tenderControl = window.SIVSTenderControl?.detailHTML(
      item.control, item.id, { escapeHTML },
    ) || "";
    if (!official) {
      content.innerHTML = `<div class="empty"><strong>Dados oficiais ainda não atualizados.</strong><br>Atualize para consultar valor, fonte de recurso, itens e documentos publicados no PNCP.<br><button class="primary" data-tender-refresh="${item.id}">Atualizar dados oficiais</button></div>${tenderControl}${commercialProposal}${portalAgent}${participationDocuments}`;
      content.querySelector("[data-tender-refresh]").onclick = () => refreshTenderOfficialData(id);
      window.SIVSTenderControl?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id), controlData: item.control, escapeHTML });
      window.SIVSTenderProposal?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id) });
      window.SIVSTenderPortalAgent?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id) });
      window.SIVSTenderDocuments?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id) });
      return;
    }
    const data = official.data || {};
    const resources = Array.isArray(data.fontesOrcamentarias) ? data.fontesOrcamentarias : [];
    const documents = official.documents || [];
    const items = official.items || [];
    const value = official.valueSource === "sigiloso" ? '<strong>Orçamento sigiloso no PNCP</strong><p class="muted">Não há valor público para esta etapa.</p>' : item.estimated_value != null ? `<strong>${money(item.estimated_value)}</strong><p class="muted">${official.valueSource === "soma_itens_pncp" ? "Soma dos itens publicados no PNCP." : "Valor total estimado publicado no PNCP."}</p>` : '<strong>Não publicado</strong>';
    const location = [item.municipality, item.uf].filter(Boolean).join("/") || "Local não informado";
    const deadline = data.dataEncerramentoProposta || item.deadline;
    const sourceLabel = official.refreshedAt ? `Atualizado em ${dateBR(official.refreshedAt, true)}` : "Dados oficiais do PNCP";
    content.innerHTML = `<section class="tender-detail-hero"><div class="tender-detail-hero-copy"><span class="status ${statusClass(item.status)}">${escapeHTML(item.status)}</span><p class="eyebrow gold">EDITAL PERSONALIZADO · ${escapeHTML(item.external_id || `ID ${item.id}`)}</p><h3>${escapeHTML(item.object_text || "Objeto não informado")}</h3><p>${escapeHTML(item.agency || "Órgão não informado")} · ${escapeHTML(location)}</p><small class="muted">${escapeHTML(sourceLabel)} · fonte: PNCP</small></div><a class="secondary" target="_blank" rel="noopener noreferrer" href="${escapeHTML(safeExternalURL(item.source_url))}">Página oficial ↗</a></section><section class="tender-detail-context" aria-label="Resumo do edital"><div><small>VALOR / ORÇAMENTO</small>${value}</div><div><small>ENCERRAMENTO DE PROPOSTAS</small><strong>${dateBR(deadline, true)}</strong><p class="muted">Publicado: ${dateBR(data.dataPublicacaoPncp || item.published_at, true)}</p></div><div><small>AMPARO LEGAL</small><strong>${escapeHTML(data.amparoLegal?.nome || "Consultar edital")}</strong><p class="muted">${escapeHTML(data.amparoLegal?.descricao || "Não informado no PNCP")}</p></div><div><small>CONTEÚDO PUBLICADO</small><strong>${documents.length} documento(s) · ${items.length} item(ns)</strong><p class="muted">Use “Ver no sistema” para ler sem baixar.</p></div></section><section class="tender-detail-section"><h3>Recurso para a contratação</h3>${resources.length ? `<ul class="tender-document-list">${resources.map((resource) => `<li><div><strong>${escapeHTML(resource.nome || "Recurso informado pelo PNCP")}</strong><span>${escapeHTML(resource.descricao || "Sem descrição complementar")}</span></div></li>`).join("")}</ul>` : '<p class="muted">A fonte orçamentária não foi publicada no PNCP; confira o edital e seus anexos.</p>'}</section><section class="tender-detail-section tender-document-hub"><div class="panel-head"><div><p class="eyebrow gold">FONTE PRIMÁRIA</p><h3>Edital e documentos oficiais</h3><small class="muted">Lista exclusiva deste edital, sincronizada com a última atualização do PNCP.</small></div><span class="status">${documents.length}</span></div>${documents.length ? `<ul class="tender-document-list">${documents.map((document, index) => tenderDocumentCardHTML(document, index, item.id)).join("")}</ul>` : '<p class="muted">Nenhum documento retornado pelo PNCP nesta atualização.</p>'}</section>${tenderAIAnalysisHTML(official.analysis, item.id)}${participationDocuments}<section class="tender-detail-section"><div class="panel-head"><h3>Itens publicados</h3><span class="status">${items.length}</span></div><ul class="tender-items">${items.length ? items.slice(0, 20).map((entry) => `<li><strong>Item ${escapeHTML(entry.numeroItem)}</strong> ${escapeHTML(entry.descricao || "Sem descrição")} ${entry.orcamentoSigiloso ? '<span class="status">Orçamento sigiloso</span>' : ""}</li>`).join("") : '<li class="muted">Nenhum item publicado no PNCP.</li>'}</ul></section><section class="legal-guidance"><strong>Conferência obrigatória — Lei nº 14.133/2021</strong><span>O sistema organiza dados do PNCP, mas não substitui a leitura do edital, anexos, habilitação, critérios, recursos, prazos e condições de execução.</span></section>`;
    content.querySelector(".tender-detail-grid")?.insertAdjacentHTML("afterend", tenderControl);
    const proposalAnchor = content.querySelector(".ai-analysis");
    proposalAnchor?.insertAdjacentHTML(
      "beforebegin", tenderExtractionHTML(official.extraction, item.analysisExceptions, item.id),
    );
    if (proposalAnchor && commercialProposal) {
      proposalAnchor.insertAdjacentHTML("afterend", `${commercialProposal}${portalAgent}`);
    }
    window.SIVSTenderControl?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id), controlData: item.control, escapeHTML });
    window.SIVSTenderProposal?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id) });
    window.SIVSTenderPortalAgent?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id) });
    window.SIVSTenderDocuments?.bindDetail({ api, toast, reload: () => showTenderDetail(item.id) });
    content.querySelectorAll("[data-tender-analyze]").forEach((button) => { button.onclick = () => analyzeTenderDocuments(item.id); });
    content.querySelectorAll("[data-tender-extract]").forEach((button) => { button.onclick = () => extractTenderDocuments(item.id); });
    content.querySelectorAll("[data-resolve-tender-exception]").forEach((button) => { button.onclick = () => resolveTenderException(button.dataset.resolveTenderException); });
    content.querySelectorAll("[data-tender-preview]").forEach((button) => {
      button.onclick = () => {
        const [resultId, index] = String(button.dataset.tenderPreview).split(":");
        previewTenderDocument(`/api/tenders/results/${resultId}/documentos/${index}`, button.dataset.tenderTitle || "Documento oficial");
      };
    });
    content.querySelectorAll("[data-copy-draft]").forEach((button) => { button.onclick = () => copyTenderDraft(button.dataset.copyDraft); });
  } catch (failure) { content.innerHTML = `<div class="empty">${escapeHTML(failure.message)}</div>`; }
}

async function refreshTenderOfficialData(id) {
  const button = $("#tenderDetailContent [data-tender-refresh]");
  if (button) { button.disabled = true; button.textContent = "Atualizando…"; }
  try { await api(`/api/tenders/results/${id}/refresh`, { method: "POST", body: "{}" }); toast("Dados oficiais atualizados."); await showTenderDetail(id); loadTenderSearch(); } catch (failure) { toast(failure.message); if (button) { button.disabled = false; button.textContent = "Atualizar dados oficiais"; } }
}

async function analyzeTenderDocuments(id) {
  const button = $("#tenderDetailContent [data-tender-analyze]");
  const status = $("#tenderAnalysisStatus");
  if (button) { button.disabled = true; button.textContent = "Lendo documentos…"; }
  if (status) status.textContent = "Extraindo o texto e preparando o relatório. Isso pode levar até dois minutos…";
  try {
    await api(`/api/tenders/results/${id}/analyze`, { method: "POST", body: "{}" });
    toast("Leitura do edital concluída.");
    await showTenderDetail(id);
  } catch (failure) {
    toast(failure.message);
    await showTenderDetail(id);
  }
}

async function extractTenderDocuments(id) {
  const button = $("#tenderDetailContent [data-tender-extract]");
  const status = $("#tenderExtractionStatus");
  if (button) { button.disabled = true; button.textContent = "Extraindo…"; }
  if (status) status.textContent = "Lendo documentos, executando OCR quando necessário e conferindo referências…";
  try {
    await api(`/api/tenders/results/${id}/extract`, { method: "POST", body: "{}" });
    toast("Extração documental concluída.");
  } catch (failure) { toast(failure.message); }
  await showTenderDetail(id);
}

async function resolveTenderException(reference) {
  const [tenderId, exceptionId] = String(reference).split(":");
  const note = window.prompt("Descreva como o documento e a página foram conferidos:");
  if (note == null) return;
  if (note.trim().length < 10) return toast("A conferência precisa ter ao menos 10 caracteres.");
  try {
    await api(`/api/tenders/results/${tenderId}/exceptions/${exceptionId}/resolve`, {
      method: "POST", body: JSON.stringify({ note: note.trim() }),
    });
    toast("Exceção documental resolvida e auditada.");
    await showTenderDetail(Number(tenderId));
  } catch (failure) { toast(failure.message); }
}

function previewTenderDocument(url, title) {
  window.SIVSTenderViewer?.open(url, title);
}

async function copyTenderDraft(id) {
  const field = document.getElementById(id);
  if (!field) return;
  try { await navigator.clipboard.writeText(field.value); toast("Rascunho copiado para revisão."); } catch { field.select(); document.execCommand("copy"); toast("Rascunho copiado para revisão."); }
}

function filterTenderResults() {
  const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const query = normalize($("#tenderFilter").value);
  const status = $("#tenderStatus").value;
  const compatibility = $("#tenderCompatibility").value;
  const filtered = state.tenderResults.filter((item) => {
    const searchable = normalize(`${item.object_text} ${item.agency} ${item.municipality} ${item.uf} ${item.modality} ${(item.matched_terms || []).join(" ")} ${(item.portfolio_matches || []).map((match) => match.title).join(" ")}`);
    return (compatibility === "all" || item.strict_match) && (!status || item.status === status) && (!query || searchable.includes(query));
  });
  $("#tenderResultsArea").innerHTML = tenderResultsHTML(filtered);
  $("#tenderFilteredCount").textContent = `${filtered.length} resultado(s)`;
  bindTenderActions();
}

async function runTenderSearch() {
  const button = $("#runTenderSearch");
  const progress = $("#tenderProgress");
  const message = $("#tenderSearchMessage");
  button.disabled = true;
  progress.className = "tender-progress";
  message.classList.add("hidden");
  $("#pncpSourceState").textContent = "PNCP: conectando";
  $("#pncpSourceState").className = "checking";
  $("#comprasSourceState").textContent = "Compras.gov: em contingência";
  $("#comprasSourceState").className = "standby";
  const started = Date.now();
  $("#progressStage").textContent = "Enfileirando pesquisa…";
  $("#progressBar").style.width = "2%";
  const timer = setInterval(() => {
    if ($("#progressTime")) $("#progressTime").textContent = `${Math.floor((Date.now() - started) / 1000)}s`;
  }, 500);
  try {
    const keywords = tenderKeywordEditor?.getKeywords() || window.SIVSTenderKeywords?.splitKeywords($("#tenderKeywords").value) || [];
    if (!keywords.length) throw new Error("Adicione ao menos uma palavra-chave antes de pesquisar.");
    const queued = await api("/api/tenders/search", { method: "POST", body: JSON.stringify({ keywords, uf: $("#tenderUf").value, days: Number($("#tenderDays").value) }) });
    let job;
    const deadline = Date.now() + 5 * 60 * 1000;
    do {
      if (Date.now() > deadline) throw new Error("A pesquisa continua no servidor. Reabra o painel para consultar o histórico.");
      await new Promise((resolve) => setTimeout(resolve, 700));
      const status = await api(`/api/tenders/jobs/${queued.jobId}`);
      job = status.job;
      if (!$("#tenderProgress")) {
        clearInterval(timer);
        return;
      }
      $("#progressStage").textContent = job.stage || "Pesquisa em execução";
      $("#progressBar").style.width = `${Math.max(2, Number(job.progress || 0))}%`;
      const step = Math.min(3, Math.floor(Number(job.progress || 0) / 25));
      $$(".progress-steps span").forEach((element, index) => element.classList.toggle("active", index <= step));
      if (job.status === "failed") throw new Error(job.error_detail || "A pesquisa não foi concluída.");
    } while (job.status !== "completed");
    const data = job.result;
    clearInterval(timer);
    progress.classList.add("done");
    $("#progressBar").style.width = "100%";
    $("#progressStage").textContent = `Concluída · ${data.pagesChecked}/${data.pagesPlanned} consulta(s) responderam`;
    $("#progressTime").textContent = `${Math.floor((Date.now() - started) / 1000)}s`;
    $("#pncpSourceState").textContent = `PNCP: ${data.sourceStatus.pncp}`;
    $("#pncpSourceState").className = data.sourceStatus.pncp === "concluído" ? "source-ok" : "source-warning";
    $("#comprasSourceState").textContent = `Compras.gov: ${data.sourceStatus.comprasgov}`;
    $("#comprasSourceState").className = data.sourceStatus.comprasgov === "concluído" ? "source-ok" : "standby";
    message.textContent = `${data.message} Cobertura desta execução: ${data.queryCount || 0}/${data.keywordTotal || 0} termos (${data.coveragePercent || 0}%).`;
    message.classList.remove("hidden");
    setTimeout(loadTenderSearch, 1800);
  } catch (failure) {
    clearInterval(timer);
    progress.classList.add("failed");
    $("#progressStage").textContent = "Pesquisa não concluída";
    message.textContent = failure.message;
    message.classList.remove("hidden");
    button.disabled = false;
  }
}

function schedulesHTML(items) {
  if (!items.length) return '<div class="empty">Nenhum plano salvo.</div>';
  const labels = { business_daily: "7h, segunda a sábado", every_2_hours: "legado: a cada 2 horas", daily: "diária", weekly: "semanal", manual: "manual" };
  return items.map((item) => `<div class="schedule-row"><div><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.uf || "Brasil")} · janela ${item.days} dias · ${escapeHTML(labels[item.frequency] || item.frequency)}${item.next_run_at ? ` · próxima: ${dateBR(item.next_run_at, true)}` : ""}${item.last_run_at ? ` · última: ${dateBR(item.last_run_at, true)}` : ""}</small></div><button class="secondary" data-schedule="${item.id}">Usar filtros</button></div>`).join("");
}

function useSchedule(id) {
  const schedule = state.tenderSchedules.find((item) => item.id === id);
  if (!schedule) return;
  let keywords = [];
  try { keywords = JSON.parse(schedule.keywords || "[]"); } catch { keywords = []; }
  tenderKeywordEditor?.setKeywords(keywords);
  $("#tenderUf").value = schedule.uf || "";
  $("#tenderDays").value = String(schedule.days || 7);
  $("#tenderKeywordEditor").scrollIntoView({ behavior: "smooth", block: "center" });
  tenderKeywordEditor?.focus();
  toast("Filtros carregados. Clique em Pesquisar agora.");
}

async function saveSearchSchedule(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    await api("/api/tenders/schedules", { method: "POST", body: JSON.stringify({ name: form.get("name"), frequency: form.get("frequency"), keywords: tenderKeywordEditor?.getKeywords() || [], uf: $("#tenderUf").value, days: Number($("#tenderDays").value) }) });
    toast("Plano de pesquisa salvo.");
    loadTenderSearch();
  } catch (failure) { toast(failure.message); }
}

function searchHistoryHTML(items) {
  if (!items.length) return '<div class="empty">Nenhuma pesquisa executada.</div>';
  return items.map((item) => `<div class="search-history-row"><span>${dateBR(item.created_at, true)}</span><strong>${escapeHTML(item.uf || "Brasil")}</strong><span>${item.found_count} aderente(s) · ${item.new_count} nova(s)</span><span class="${item.error_detail ? "history-warning" : "history-ok"}">${item.error_detail ? "Com avisos" : "Concluída"}</span></div>`).join("");
}

async function loadInventory() {
  setHeader("ESTOQUE", "Estoque, depósitos e reservas");
  if (!window.SIVSInventory?.load) {
    $("#content").innerHTML = '<div class="empty">O módulo transacional de estoque não foi carregado.</div>';
    return;
  }
  await window.SIVSInventory.load({
    api, state, writable: isWritable("estoque"), canAction, escapeHTML, dateBR, toast,
  });
}

async function loadManagementOverview() {
  setHeader("GESTÃO FINANCEIRA", "Controladoria");
  if (!window.SIVSManagementControl?.load) {
    throw new Error("O componente de controladoria não foi carregado.");
  }
  await window.SIVSManagementControl.load({ api, escapeHTML, dateBR });
}

async function loadReporting() {
  setHeader("ANÁLISE E DECISÃO", "Central de relatórios");
  if (!window.SIVSReporting?.load) throw new Error("O componente de relatórios não foi carregado.");
  await window.SIVSReporting.load({
    api, state, content: $("#content"), escapeHTML, dateBR, toast,
  });
}

async function loadFiscal() {
  setHeader("FISCAL", "Fiscal");
  if (!window.SIVSFiscalIntegration?.render || !window.SIVSFiscalIntegration?.bind) {
    throw new Error("O componente de integração fiscal não foi carregado.");
  }
  const [records, events, readiness, branches, foundation, mappings, categories, taxSetup, drafts] = await Promise.all([
    api("/api/records?module=fiscal"),
    api("/api/fiscal/events"),
    api("/api/fiscal/readiness"),
    api("/api/branches"),
    api("/api/accounting/foundation"),
    api("/api/accounting/financial-mappings"),
    api("/api/financial/categories"),
    api("/api/fiscal/tax-setup"),
    api("/api/fiscal/drafts"),
  ]);
  state.items = records.items;
  const abilities = {
    configuration: canAction("fiscal", "manage_fiscal_config"),
    certificate: canAction("fiscal", "manage_fiscal_certificate"),
    status: canAction("fiscal", "check_sefaz_status"),
    accounting: canAction("fiscal", "export_accounting") && canAction("fiscal", "view_values") && state.exportableModules.has("fiscal"),
    accountingManagement: canAction("fiscal", "manage_accounting"),
    accountingPosting: canAction("fiscal", "post_accounting_entries"),
    accountingReports: canAction("fiscal", "view_values"),
    accountingPeriodManagement: canAction("fiscal", "close_accounting_period"),
    taxManagement: canAction("fiscal", "manage_tax_rules"),
    issueNfe: canAction("fiscal", "issue_nfe_homologation") && readiness.canIssue,
  };
  const integration = window.SIVSFiscalIntegration.render({
    readiness, branches: branches.items, abilities, escapeHTML, dateBR,
    foundation, mappings: mappings.items, categories: categories.items, taxSetup, drafts,
  });
  $("#content").innerHTML = `<section class="fiscal-hero"><div><p class="eyebrow gold">CENTRAL FISCAL</p><h2>Documentos, XML, SEFAZ e contabilidade</h2><p>Importação de NF-e, homologação por CNPJ, certificado A1 criptografado, endpoints oficiais e exportação mensal rastreável.</p></div><span class="status pendente">Em homologação</span></section><div class="compliance-note"><strong>Limite atual:</strong> a consulta de disponibilidade da SEFAZ é real, mas emissão e produção continuam bloqueadas até os schemas e cálculos tributários da empresa serem homologados.</div>${integration}<div class="module-toolbar"><div>${canAccessScreen("importacoes_xml") ? '<button id="openFiscalXmlImport" class="secondary">⤓ Importar XML NF-e</button>' : ""}</div>${canAction("fiscal", "create") ? '<button id="newFiscal" class="primary">＋ Novo documento fiscal local</button>' : ""}</div><section class="panel"><div class="panel-head"><h3>Documentos fiscais locais</h3><span class="status">${records.items.length}</span></div><div class="table-wrap borderless">${fiscalTableHTML(records.items)}</div></section><section class="panel" style="margin-top:18px"><div class="panel-head"><h3>Histórico de eventos</h3><span class="status">${events.items.length}</span></div><div class="panel-body">${events.items.length ? events.items.map((item) => `<div class="audit-row"><span>${dateBR(item.created_at, true)}</span><strong>${escapeHTML(item.event_type.toUpperCase())}</strong><span>${escapeHTML(item.title)} · ${escapeHTML(item.status)}${item.protocol ? ` · protocolo ${escapeHTML(item.protocol)}` : ""}</span></div>`).join("") : '<div class="empty">Nenhum evento fiscal registrado.</div>'}</div></section>`;
  window.SIVSFiscalIntegration.bind({ readiness, foundation, mappings: mappings.items, categories: categories.items, taxSetup, drafts, branches: branches.items, abilities, escapeHTML, dateBR, api, toast, reload: loadFiscal });
  if ($("#openFiscalXmlImport")) $("#openFiscalXmlImport").onclick = () => navigate("importacoes_xml");
  if ($("#newFiscal")) $("#newFiscal").onclick = () => openRecord(null, "fiscal");
  $$('[data-fiscal]').forEach((button) => { button.onclick = () => fiscalAction(Number(button.dataset.fiscal), button.dataset.action); });
  bindRows();
}

function fiscalTableHTML(items) {
  if (!items.length) return '<div class="empty">Nenhum documento fiscal cadastrado.</div>';
  return `<table class="data-table fiscal-table"><thead><tr><th>Documento</th><th>Destinatário</th><th>Status</th><th>Valor</th><th>Ações locais</th></tr></thead><tbody>${items.map((item) => `<tr><td class="title-cell"><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.payload?.tipo_nota || "Documento")} ${escapeHTML(item.payload?.numero || "")}</small></td><td>${escapeHTML(item.payload?.destinatario || "—")}</td><td><span class="status ${statusClass(item.status)}">${escapeHTML(item.status)}</span></td><td>${item.amount == null ? "—" : money(item.amount)}</td><td><div class="fiscal-actions">${canAction("fiscal", "register_fiscal") ? `<button data-fiscal="${item.id}" data-action="registrar">Registrar localmente</button>` : ""}<button class="icon-button" data-edit="${item.id}" aria-label="${canAction("fiscal", "update") ? "Editar" : "Visualizar"} documento local">${canAction("fiscal", "update") ? "✎" : "◉"}</button></div></td></tr>`).join("")}</tbody></table>`;
}

async function fiscalAction(recordId, action) {
  const detail = window.prompt(`Detalhes para ${action} (a solicitação será auditada):`, "");
  if (detail === null) return;
  try {
    const data = await api(`/api/fiscal/${recordId}/${action}`, { method: "POST", body: JSON.stringify({ detail }) });
    toast(`Evento fiscal registrado: ${data.status}.`);
    loadFiscal();
  } catch (failure) { toast(failure.message); }
}

async function loadSettings() {
  setHeader("ADMINISTRAÇÃO", "Configurações e segurança");
  const requests = [api("/api/settings"), api("/api/audit"), api("/api/trash"), api("/api/companies"), api("/api/tender-documents"), api("/api/financial/categories")];
  if (state.user.role === "admin") requests.push(api("/api/users"));
  const [settings, audit, trash, companies, tenderDocuments, financialCategories, users] = await Promise.all(requests);
  state.settings = settings.settings;
  state.settingsUsers = users?.items || [];
  state.financialCategories = financialCategories?.items || [];
  state.accessControl = users?.accessControl || state.accessControl;
  const company = settings.settings.company || {};
  const branches = settings.settings.branches || [];
  const tenderAutonomy = settings.settings.tenderAutonomy || {};
  const hierarchyPanel = `<section class="panel hierarchy-panel"><div class="panel-head"><div><h3>Holding e unidades</h3><small class="muted">Holding → CNPJ/empresa → unidade operacional</small></div><span class="status">${branches.length} unidade(s)</span></div><div class="panel-body"><p class="hierarchy-holding"><strong>${escapeHTML(company.holding_name || "Holding principal")}</strong><span>Holding</span></p><div class="branch-list">${branches.map((branch) => `<div class="branch-row"><span><strong>${escapeHTML(branch.name)}</strong><small>${escapeHTML(branch.code)}${branch.is_headquarters ? " · Matriz" : ""}</small></span><span>${escapeHTML(branch.cnpj || "CNPJ da empresa")}</span></div>`).join("")}</div>${state.user.role === "admin" ? '<form id="branchForm" class="branch-form"><label class="field"><span>Código *</span><input name="code" maxlength="40" required placeholder="FILIAL-SP"></label><label class="field"><span>Nome da unidade *</span><input name="name" maxlength="160" required></label><label class="field"><span>CNPJ</span><input name="cnpj" inputmode="numeric"></label><label class="field"><span>Endereço</span><input name="address" maxlength="240"></label><button class="secondary" type="submit">＋ Adicionar unidade</button></form>' : ""}</div></section>`;
  $("#content").innerHTML = `<section class="settings-layout"><div class="panel"><div class="panel-head"><h3>Empresa ativa</h3>${state.user.role === "admin" ? '<button class="text-button" id="editCompany">Editar</button>' : ""}</div><div class="panel-body company-card"><strong>${escapeHTML(company.name || "Sistema Seccol")}</strong><span>${escapeHTML(company.cnpj || "CNPJ não informado")}</span><span>${escapeHTML(company.email || "E-mail não informado")}</span><span>${escapeHTML(company.phone || "Telefone não informado")}</span><span>${escapeHTML(company.address || "Endereço não informado")}</span>${state.user.role === "admin" ? '<button id="newCompany" class="secondary">＋ Cadastrar outra empresa</button>' : ""}</div></div><div class="panel"><div class="panel-head"><h3>Dados e continuidade</h3></div><div class="panel-body action-list">${state.user.role === "admin" ? '<button id="backupAll"><span><strong>Backup integral criptografado</strong><br><small class="muted">Banco completo, usuários, anexos, histórico e auditoria · AES-256-GCM</small></span><span>↓</span></button><button id="exportBusiness"><span><strong>Exportar dados da empresa</strong><br><small class="muted">Arquivo JSON para portabilidade</small></span><span>↓</span></button><button id="importButton"><span><strong>Importar dados de portabilidade</strong><br><small class="muted">Importação transacional na empresa ativa</small></span><span>↑</span></button><input id="importFile" type="file" accept="application/json" hidden>' : ""}<button id="logoutButton"><span><strong>Encerrar sessão</strong><br><small class="muted">Exige novo login</small></span><span>→</span></button></div></div></section>${hierarchyPanel}
  <section class="panel tender-autonomy-panel" aria-labelledby="tenderAutonomyTitle"><div class="panel-head"><div><h3 id="tenderAutonomyTitle">Agente autônomo de licitações</h3><small class="muted">Captação e preparação contínuas, sem filtro de valor</small></div><span class="status ${tenderAutonomy.enabled ? "ativo" : "pendente"}">${tenderAutonomy.enabled ? "Ativo" : "Pausado"}</span></div><form id="tenderAutonomyForm" class="panel-body"><label class="check-row"><input name="enabled" type="checkbox" ${tenderAutonomy.enabled ? "checked" : ""}><span><strong>Executar automaticamente</strong><small>Processa novas oportunidades quando a pesquisa manual ou agendada terminar.</small></span></label><label class="check-row"><input name="captureRegardlessOfValue" type="checkbox" ${tenderAutonomy.captureRegardlessOfValue !== false ? "checked" : ""}><span><strong>Captar independentemente do preço publicado</strong><small>Valor ausente, sigiloso, baixo ou alto não impede a captação.</small></span></label><label class="check-row"><input name="captureSingleCatalogItem" type="checkbox" ${tenderAutonomy.captureSingleCatalogItem !== false ? "checked" : ""}><span><strong>Entrar mesmo com apenas 1 item compatível</strong><small>Confirma o item nos dados oficiais e mantém o edital com prioridade secundária.</small></span></label><label class="check-row"><input name="autoFetchOfficialDetails" type="checkbox" ${tenderAutonomy.autoFetchOfficialDetails !== false ? "checked" : ""}><span><strong>Buscar edital, itens e anexos oficiais</strong><small>Enriquece automaticamente cada oportunidade aderente usando as APIs públicas do PNCP.</small></span></label><label class="check-row"><input name="autoConvertCompatible" type="checkbox" ${tenderAutonomy.autoConvertCompatible !== false ? "checked" : ""}><span><strong>Converter aderentes em Licitação</strong><small>Exige correspondência técnica rígida com produto ou serviço ativo da empresa.</small></span></label><div class="compliance-note compact"><strong>Execução no portal aguardando conector oficial</strong><p>O agente não simula cliques, não contorna CAPTCHA e não envia lances por interface protegida. Proposta e lance externos permanecem bloqueados até existir API de fornecedor homologada, credencial corporativa e recibo verificável.</p></div><button class="primary" type="submit">Salvar autonomia</button><p id="tenderAutonomyStatus" class="muted" role="status" aria-live="polite"></p></form></section>
  <section class="panel" style="margin-top:18px"><div class="panel-head"><div><h3>Motor fiscal próprio</h3><small class="muted">Domínio independente, parametrizável e versionável</small></div><span class="status pendente">Em preparação</span></div><div class="panel-body"><p class="compliance-note compact">A fundação possui operações, perfis tributários, regras, schemas, documentos, itens, eventos, certificados e XML próprios. Nenhuma emissão ou alíquota presumida está habilitada nesta etapa.</p></div></section>
  ${financialCategoriesPanel(state.financialCategories)}${window.SIVSTenderDocuments?.settingsHTML(tenderDocuments, { escapeHTML, dateBR }) || ""}${state.user.role === "admin" ? usersPanel(users.items) : ""}${trashPanel(trash.items)}${auditPanel(audit.items)}`;
  const settingsPanels = $("#content").querySelectorAll(".settings-layout > .panel");
  if (settingsPanels[0]) settingsPanels[0].id = "settingsCompanyPanel";
  if (settingsPanels[1]) settingsPanels[1].id = "settingsDataPanel";
  const settingsUnits = $("#content .hierarchy-panel");
  if (settingsUnits) settingsUnits.id = "settingsUnitsPanel";
  const settingsAutonomy = $("#content .tender-autonomy-panel");
  if (settingsAutonomy) settingsAutonomy.id = "tenderAutonomyPanel";
  const settingsFiscal = $("#content > section.panel[style]");
  if (settingsFiscal) settingsFiscal.id = "fiscalPreparationPanel";
  const settingsAudit = $("#content .audit-panel");
  if (settingsAudit) settingsAudit.id = "auditPanel";
  $("#content").insertAdjacentHTML("afterbegin", '<nav class="settings-section-nav" aria-label="Seções de configurações"><a href="#settingsCompanyPanel">Empresa</a><a href="#settingsDataPanel">Dados e backup</a><a href="#settingsUnitsPanel">Unidades</a><a href="#tenderAutonomyPanel">Editais</a><a href="#fiscalPreparationPanel">Fiscal</a><a href="#auditPanel">Auditoria</a></nav>');
  window.SIVSTenderDocuments?.bindSettings({ api, toast, reload: loadSettings });
  const singleItemPolicy = $('#tenderAutonomyForm [name="captureSingleCatalogItem"]');
  if (singleItemPolicy) {
    singleItemPolicy.checked = true;
    singleItemPolicy.disabled = true;
    singleItemPolicy.setAttribute("aria-disabled", "true");
  }
  const autonomyNote = $('#tenderAutonomyForm .compliance-note');
  if (autonomyNote) {
    autonomyNote.insertAdjacentHTML("beforebegin", `<label class="check-row"><input name="portalAgentEnabled" type="checkbox" ${tenderAutonomy.portalAgentEnabled !== false ? "checked" : ""}><span><strong>Preparar acompanhamento do portal após aprovação</strong><small>Cria os limites vinculados à proposta aprovada, ao valor e ao menor valor permitido.</small></span></label><label class="check-row"><input name="autoStartShadowRun" type="checkbox" ${tenderAutonomy.autoStartShadowRun !== false ? "checked" : ""}><span><strong>Iniciar simulação segura automaticamente</strong><small>Confere a navegação e os limites sem enviar proposta ou lance ao portal.</small></span></label>`);
    autonomyNote.innerHTML = '<strong>Navegador governado disponível em simulação</strong><p>O agente prepara comandos e avalia lances contra o piso aprovado. Produção exige portal homologado, credencial corporativa, autorização escrita e chave de ambiente; CAPTCHA e MFA sempre interrompem para intervenção.</p>';
  }
  if ($("#tenderAutonomyForm")) $("#tenderAutonomyForm").onsubmit = saveTenderAutonomy;
  if ($("#editCompany")) $("#editCompany").onclick = () => openSettings(company);
  if ($("#newCompany")) $("#newCompany").onclick = () => { $("#companyForm").reset(); $("#companyDialog").showModal(); };
  if ($("#backupAll")) $("#backupAll").onclick = downloadDatabaseBackup;
  if ($("#exportBusiness")) $("#exportBusiness").onclick = () => { location.href = "/api/export"; };
  if ($("#importButton")) { $("#importButton").onclick = () => $("#importFile").click(); $("#importFile").onchange = importBackup; }
  $("#logoutButton").onclick = logout;
  if ($("#newUser")) $("#newUser").onclick = () => {
    state.pendingUser = null;
    $("#userForm").reset();
    $("#userDialog").showModal();
  };
  $$('[data-user-toggle]').forEach((button) => { button.onclick = () => updateUser(button); });
  $$('[data-user-password]').forEach((button) => { button.onclick = () => openUserPasswordReset(button); });
  $$('[data-user-permissions]').forEach((button) => { button.onclick = () => openUserPermissions(Number(button.dataset.userPermissions)); });
  $$('[data-role-for]').forEach((select) => { select.onchange = () => updateUserRole(select); });
  $$('[data-restore]').forEach((button) => { button.onclick = () => restoreRecord(button.dataset.restore); });
  $$('[data-trash-purge]').forEach((button) => { button.onclick = () => openTrashPurge(button.dataset.trashPurge, button.dataset.trashTitle); });
  if ($("#emptyTrash")) $("#emptyTrash").onclick = () => openTrashPurge();
  if ($("#branchForm")) $("#branchForm").onsubmit = saveBranch;
  if ($("#financialCategoryForm")) $("#financialCategoryForm").onsubmit = saveFinancialCategory;
  bindAuditPanel();
  $$('[data-financial-category-edit]').forEach((button) => { button.onclick = () => editFinancialCategory(Number(button.dataset.financialCategoryEdit)); });
  $$('[data-financial-category-toggle]').forEach((button) => { button.onclick = () => toggleFinancialCategory(Number(button.dataset.financialCategoryToggle)); });
  if ($("#cancelFinancialCategoryEdit")) $("#cancelFinancialCategoryEdit").onclick = resetFinancialCategoryForm;
  void companies;
}

async function loadHR() {
  setHeader("PESSOAS", "RH, ponto e folha");
  if (!window.SIVSHR?.load) throw new Error("O ambiente operacional de RH não foi carregado.");
  await window.SIVSHR.load({
    api, state, canAction, escapeHTML, dateBR, toast,
    content: $("#content"), reload: loadHR,
  });
}

function financialCategoriesPanel(items) {
  const kindLabels = { EXPENSE: "Despesa", INCOME: "Receita", BOTH: "Receita e despesa" };
  return `<section class="panel financial-categories-panel" aria-labelledby="financialCategoriesTitle"><div class="panel-head"><div><h3 id="financialCategoriesTitle">Categorias financeiras</h3><small class="muted">Classificação padronizada por empresa para despesas, receitas e caixa.</small></div><span class="status">${items.filter((item) => item.active).length} ativa(s)</span></div><div class="panel-body"><form id="financialCategoryForm" class="financial-category-form"><input type="hidden" name="id"><label class="field"><span>Nome da categoria *</span><input name="name" required minlength="2" maxlength="80" placeholder="Ex.: Material de escritório"></label><label class="field"><span>Aplicação *</span><select name="kind" required><option value="EXPENSE">Despesa</option><option value="INCOME">Receita</option><option value="BOTH">Receita e despesa</option></select></label><div class="financial-category-form-actions"><button class="primary" type="submit"><span id="financialCategorySubmitLabel">＋ Cadastrar categoria</span></button><button id="cancelFinancialCategoryEdit" class="secondary hidden" type="button">Cancelar edição</button></div><p id="financialCategoryFeedback" class="muted" role="status" aria-live="polite"></p></form><div class="financial-category-list">${items.map((item) => `<article class="financial-category-row ${item.active ? "" : "is-inactive"}"><span><strong>${escapeHTML(item.name)}</strong><small>${kindLabels[item.kind] || item.kind} · ${item.usage_count || 0} lançamento(s)</small></span><span class="status ${item.active ? "ativo" : ""}">${item.active ? "Ativa" : "Inativa"}</span><div class="mini-actions"><button type="button" class="secondary" data-financial-category-edit="${item.id}">Editar</button><button type="button" class="secondary" data-financial-category-toggle="${item.id}">${item.active ? "Inativar" : "Reativar"}</button></div></article>`).join("")}</div><p class="compliance-note compact"><strong>Histórico preservado:</strong> categorias inativadas deixam de aparecer em novos lançamentos, mas continuam identificando registros antigos.</p></div></section>`;
}

function resetFinancialCategoryForm() {
  const form = $("#financialCategoryForm");
  if (!form) return;
  form.reset();
  form.elements.id.value = "";
  $("#financialCategorySubmitLabel").textContent = "＋ Cadastrar categoria";
  $("#cancelFinancialCategoryEdit").classList.add("hidden");
  $("#financialCategoryFeedback").textContent = "";
}

function editFinancialCategory(id) {
  const category = state.financialCategories.find((item) => Number(item.id) === Number(id));
  const form = $("#financialCategoryForm");
  if (!category || !form) return;
  form.elements.id.value = category.id;
  form.elements.name.value = category.name;
  form.elements.kind.value = category.kind;
  $("#financialCategorySubmitLabel").textContent = "Salvar categoria";
  $("#cancelFinancialCategoryEdit").classList.remove("hidden");
  form.elements.name.focus();
}

async function saveFinancialCategory(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const id = form.elements.id.value;
  const body = { name: form.elements.name.value, kind: form.elements.kind.value, active: true };
  if (id) body.active = Boolean(state.financialCategories.find((item) => String(item.id) === id)?.active);
  const feedback = $("#financialCategoryFeedback");
  try {
    await api(id ? `/api/financial/categories/${id}` : "/api/financial/categories", {
      method: id ? "PUT" : "POST", body: JSON.stringify(body),
    });
    toast(id ? "Categoria financeira atualizada." : "Categoria financeira cadastrada.");
    await loadSettings();
  } catch (failure) { feedback.textContent = failure.message; }
}

async function toggleFinancialCategory(id) {
  const category = state.financialCategories.find((item) => Number(item.id) === Number(id));
  if (!category) return;
  try {
    await api(`/api/financial/categories/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name: category.name, kind: category.kind, active: !category.active }),
    });
    toast(category.active ? "Categoria inativada; o histórico foi preservado." : "Categoria reativada.");
    await loadSettings();
  } catch (failure) { toast(failure.message); }
}

function usersPanel(items) {
  const roleOptions = Object.entries(roleLabels);
  return `<section class="panel" style="margin-top:18px"><div class="panel-head"><div><h3>Usuários e permissões</h3><small class="muted">Perfil-base e exceções por módulo, sempre aplicados no servidor e na empresa ativa.</small></div><button class="primary" id="newUser">＋ Novo usuário</button></div><div class="panel-body user-list">${items.map((item) => `<div class="user-row"><span class="user-avatar">${escapeHTML(item.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase())}</span><span><strong>${escapeHTML(item.name)}</strong><small>${escapeHTML(item.email)} · ${item.active ? "Ativo" : "Desativado"}</small></span><select data-role-for="${item.id}" aria-label="Perfil de ${escapeHTML(item.name)}">${roleOptions.map(([key, label]) => `<option value="${key}" ${item.role === key ? "selected" : ""}>${label}</option>`).join("")}</select><div class="mini-actions"><button class="secondary" data-user-permissions="${item.id}">Acessos</button><button class="secondary" data-user-password="${item.id}" data-user-name="${escapeHTML(item.name)}">Senha</button><button class="secondary" data-user-toggle="${item.id}" data-active="${item.active ? 1 : 0}">${item.active ? "Desativar" : "Ativar"}</button></div></div>`).join("")}</div></section>`;
}

async function saveTenderAutonomy(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = $("#tenderAutonomyStatus");
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ tenderAutonomy: {
      enabled: form.elements.enabled.checked,
      captureRegardlessOfValue: form.elements.captureRegardlessOfValue.checked,
      captureSingleCatalogItem: form.elements.captureSingleCatalogItem.checked,
      autoFetchOfficialDetails: form.elements.autoFetchOfficialDetails.checked,
      autoConvertCompatible: form.elements.autoConvertCompatible.checked,
      portalAgentEnabled: form.elements.portalAgentEnabled.checked,
      autoPrepareApprovedProposal: form.elements.portalAgentEnabled.checked,
      autoStartShadowRun: form.elements.autoStartShadowRun.checked,
    } }) });
    status.textContent = "Configuração salva e aplicada aos próximos ciclos.";
    toast("Autonomia de licitações atualizada.");
    await loadSettings();
  } catch (failure) { status.textContent = failure.message; }
}

function trashPanel(items) {
  const canPurge = state.user.role === "admin";
  const actions = items.length && canPurge ? '<button class="danger-button" id="emptyTrash">Esvaziar lixeira</button>' : "";
  const rows = items.slice(0, 30).map((item) => `<div class="trash-row"><span><strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(state.modules[item.module] || item.module)} · ${dateBR(item.deleted_at)}</small></span><div class="trash-actions">${canAction(item.module, "restore") ? `<button class="secondary" data-restore="${item.id}">Restaurar</button>` : ""}${canPurge ? `<button class="danger-button" data-trash-purge="${item.id}" data-trash-title="${escapeHTML(item.title)}">Apagar</button>` : ""}</div></div>`).join("");
  const remainder = items.length > 30 ? `<p class="muted trash-remainder">Mais ${items.length - 30} item(ns). Use “Esvaziar lixeira” para apagar todos os itens permitidos.</p>` : "";
  return `<section class="panel trash-panel" style="margin-top:18px"><div class="panel-head"><div><h3>Lixeira</h3><small class="muted">Restaure ou apague definitivamente os registros excluídos.</small></div><div class="trash-panel-actions"><span class="status">${items.length} registro(s)</span>${actions}</div></div><div class="panel-body">${items.length ? rows + remainder : '<div class="empty">A lixeira está vazia.</div>'}</div></section>`;
}

const auditActionLabels = { create: "Criou", update: "Editou", delete: "Enviou para a lixeira", restore: "Restaurou", purge: "Apagou definitivamente", login: "Entrou no sistema", logout: "Saiu do sistema" };
function auditDetailText(detail) {
  if (!detail) return "";
  try { const parsed = typeof detail === "string" ? JSON.parse(detail) : detail; return Object.entries(parsed || {}).map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join(" · "); }
  catch (_) { return String(detail); }
}
function auditPanel(items) {
  const deletes = items.filter((item) => ["delete", "purge"].includes(item.action)).length;
  const changes = items.filter((item) => ["create", "update", "restore"].includes(item.action)).length;
  return `<section class="panel audit-panel" style="margin-top:18px" aria-labelledby="auditTitle"><div class="panel-head"><div><h3 id="auditTitle">Trilha de auditoria</h3><small class="muted">Quem fez o quê, em qual registro e quando. A empresa ativa é aplicada no servidor.</small></div><span class="status">${items.length} de 100 eventos</span></div><div class="audit-summary"><div><span>Exclusões</span><strong>${deletes}</strong></div><div><span>Alterações e criações</span><strong>${changes}</strong></div><div><span>Último evento</span><strong>${items[0] ? dateBR(items[0].created_at, true) : "—"}</strong></div></div><div class="audit-toolbar"><label class="field"><span>Buscar na trilha</span><input id="auditSearch" type="search" placeholder="Usuário, ação, registro ou detalhe" autocomplete="off"></label><label class="field"><span>Tipo de ação</span><select id="auditActionFilter"><option value="">Todas</option><option value="delete">Exclusões</option><option value="update">Edições</option><option value="create">Criações</option><option value="restore">Restaurações</option></select></label></div><div id="auditList" class="audit-list">${auditHTML(items)}</div></section>`;
}
function auditHTML(items) {
  return items.length ? items.map((item) => { const detail = auditDetailText(item.detail); const searchable = `${item.user_name || "Sistema"} ${item.action} ${item.entity_type} ${item.entity_id || ""} ${detail}`.toLowerCase(); return `<article class="audit-row" data-audit-action="${escapeHTML(item.action)}" data-audit-search="${escapeHTML(searchable)}"><time datetime="${escapeHTML(item.created_at)}">${dateBR(item.created_at, true)}</time><strong>${escapeHTML(auditActionLabels[item.action] || item.action)}</strong><div><span>${escapeHTML(item.user_name || "Sistema")} · ${escapeHTML(item.entity_type)}${item.entity_id ? ` #${escapeHTML(item.entity_id)}` : ""}</span>${detail ? `<small>${escapeHTML(detail)}</small>` : ""}</div></article>`; }).join("") : '<div class="empty">Nenhum evento de auditoria.</div>';
}
function bindAuditPanel() {
  const search = $("#auditSearch"), filter = $("#auditActionFilter");
  if (!search || !filter) return;
  const apply = () => { const query = search.value.trim().toLowerCase(); const action = filter.value; let visible = 0; $$("#auditList .audit-row").forEach((row) => { const show = (!action || row.dataset.auditAction === action) && (!query || row.dataset.auditSearch.includes(query)); row.hidden = !show; if (show) visible += 1; }); let empty = $("#auditList .audit-filter-empty"); if (!visible && !empty) { $("#auditList").insertAdjacentHTML("beforeend", '<div class="empty audit-filter-empty">Nenhum evento corresponde ao filtro.</div>'); empty = $("#auditList .audit-filter-empty"); } if (empty) empty.hidden = visible !== 0; };
  search.oninput = apply; filter.onchange = apply;
}

function openSettings(company) {
  const form = $("#settingsForm");
  form.companyName.value = company.name || "";
  form.cnpj.value = company.cnpj || "";
  form.phone.value = company.phone || "";
  form.email.value = company.email || "";
  form.address.value = company.address || "";
  $("#settingsDialog").showModal();
}

async function saveSettings(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify({ company: { name: form.get("companyName"), cnpj: form.get("cnpj"), phone: form.get("phone"), email: form.get("email"), address: form.get("address") } }) });
    dismissDialog($("#settingsDialog"));
    const me = await api("/api/me");
    state.user = me.user;
    renderCompanySelector();
    toast("Dados da empresa salvos.");
    loadSettings();
  } catch (failure) { toast(failure.message); }
}

async function saveBranch(event) {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.currentTarget));
  try {
    await api("/api/branches", { method: "POST", body: JSON.stringify(body) });
    toast("Unidade adicionada à empresa ativa.");
    await loadSettings();
  } catch (failure) { toast(failure.message); }
}

async function saveCompany(event) {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const data = await api("/api/companies", { method: "POST", body: JSON.stringify(body) });
    dismissDialog($("#companyDialog"));
    await api("/api/company/switch", { method: "POST", body: JSON.stringify({ company_id: data.id }) });
    const me = await api("/api/me");
    toast("Nova empresa criada com base isolada e fontes cadastradas.");
    await startApp(me);
  } catch (failure) { toast(failure.message); }
}

async function updateUser(button) {
  const id = button.dataset.userToggle;
  const role = $(`[data-role-for="${id}"]`).value;
  const active = button.dataset.active !== "1";
  try { await api(`/api/users/${id}`, { method: "PUT", body: JSON.stringify({ role, active }) }); toast("Permissão atualizada."); loadSettings(); } catch (failure) { toast(failure.message); }
}

async function updateUserRole(select) {
  const id = Number(select.dataset.roleFor);
  const item = state.settingsUsers.find((candidate) => candidate.id === id);
  if (!item || item.role === select.value) return;
  try {
    await api(`/api/users/${id}`, {
      method: "PUT", body: JSON.stringify({ role: select.value, active: Boolean(item.active) }),
    });
    toast("Perfil-base atualizado e aplicado no servidor.");
    await loadSettings();
  } catch (failure) {
    select.value = item.role;
    toast(failure.message);
  }
}

function accessCategories() {
  return state.accessControl?.categories || [];
}

function accessModule(moduleKey) {
  return accessCategories().flatMap((category) => category.modules)
    .find((module) => module.key === moduleKey);
}

function permissionFunctionIsReadOnly(action) {
  return action === "view_values" || action === "decide_approval" || action.startsWith("view_");
}

const permissionValueDependentActions = new Set([
  "create", "update", "manage_items", "bill_sales", "settle_financial",
  "receive_stock", "register_fiscal", "convert_tender",
]);

function permissionDraftFromTemplate(template = {}) {
  const permissions = template.permissions || {};
  const actions = template.actions || {};
  const moduleKeys = new Set([
    ...accessCategories().flatMap((category) => category.modules.map((module) => module.key)),
    ...Object.keys(actions),
  ]);
  return {
    read: new Set(permissions.read || []),
    write: new Set(permissions.write || []),
    export: new Set(permissions.export || []),
    actions: Object.fromEntries([...moduleKeys]
      .map((moduleKey) => [moduleKey, new Set(actions[moduleKey] || [])])),
  };
}

function permissionTemplateForRole(role) {
  return state.accessControl?.roleDefaults?.[role] || {
    permissions: { read: [], write: [], export: [] }, actions: {}, capabilities: {},
  };
}

function normalizePermissionModule(moduleKey) {
  const draft = state.permissionDraft;
  const module = accessModule(moduleKey);
  if (!draft || !module) return;
  const actions = draft.actions[moduleKey] ||= new Set();
  if (!draft.read.has(moduleKey)) {
    draft.write.delete(moduleKey);
    draft.export.delete(moduleKey);
    actions.clear();
    return;
  }
  if (module.readOnly) draft.write.delete(moduleKey);
  if (!draft.write.has(moduleKey)) {
    [...actions].forEach((action) => {
      if (!permissionFunctionIsReadOnly(action)) actions.delete(action);
    });
  }
  const actionKeys = new Set(module.actions.map((action) => action.key));
  if (draft.export.has(moduleKey) && actionKeys.has("view_values")) actions.add("view_values");
  if (!actions.has("view_values")) {
    permissionValueDependentActions.forEach((action) => actions.delete(action));
  }
}

function permissionSelectionSummary() {
  const draft = state.permissionDraft;
  if (!draft) return;
  const functions = Object.values(draft.actions).reduce((total, actions) => total + actions.size, 0);
  $("#permissionsSelectionSummary").textContent = `${draft.read.size} módulo(s) consultáveis · ${draft.write.size} editáveis · ${functions} função(ões) liberadas`;
}

function renderPermissionModules(_item, query = "") {
  const normalized = String(query || "").trim().toLocaleLowerCase("pt-BR");
  const selected = state.permissionDraft;
  const categories = accessCategories().map((category) => ({
    ...category,
    modules: category.modules.filter((module) => {
      const text = `${module.key} ${module.label} ${module.actions.map((action) => action.label).join(" ")}`
        .toLocaleLowerCase("pt-BR");
      return !normalized || text.includes(normalized);
    }),
  })).filter((category) => category.modules.length);
  $("#permissionsModuleList").innerHTML = categories.map((category) => `
    <section class="permission-category" data-permission-category="${escapeHTML(category.key)}">
      <header class="permission-category-head"><div><h3>${escapeHTML(category.label)}</h3><small>${category.modules.length} módulo(s) nesta visualização</small></div><div class="permission-category-actions"><button class="secondary" type="button" data-permission-category-mode="read" data-category-key="${escapeHTML(category.key)}">Só consulta</button><button class="secondary" type="button" data-permission-category-mode="all" data-category-key="${escapeHTML(category.key)}">Acesso completo</button><button class="secondary" type="button" data-permission-category-mode="none" data-category-key="${escapeHTML(category.key)}">Sem acesso</button></div></header>
      <div>${category.modules.map((module) => {
        const functional = selected.actions[module.key] || new Set();
        const matchingAction = normalized && module.actions.some((action) => action.label.toLocaleLowerCase("pt-BR").includes(normalized));
        return `<article class="permission-module-row" data-permission-module-row="${escapeHTML(module.key)}">
          <div class="permission-module-main"><span class="permission-module-title"><strong>${escapeHTML(module.label)}</strong><small>${escapeHTML(module.key)}${module.readOnly ? " · visão gerencial" : ""}</small></span>${["read", "write", "export"].map((action) => `<label title="${action === "read" ? "Consultar" : action === "write" ? "Editar" : "Exportar"} ${escapeHTML(module.label)}"><input type="checkbox" data-permission-action="${action}" data-permission-module="${escapeHTML(module.key)}" ${selected[action].has(module.key) ? "checked" : ""} ${module.readOnly && action === "write" ? "disabled" : ""} aria-label="${action === "read" ? "Consultar" : action === "write" ? "Editar" : "Exportar"} ${escapeHTML(module.label)}"></label>`).join("")}</div>
          ${module.actions.length ? `<details class="permission-functions" ${matchingAction ? "open" : ""}><summary>Funções individuais <span class="permission-function-count">${functional.size}/${module.actions.length}</span></summary><div class="permission-function-grid">${module.actions.map((action) => `<label><input type="checkbox" data-permission-functional-action="${escapeHTML(action.key)}" data-permission-module="${escapeHTML(module.key)}" ${functional.has(action.key) ? "checked" : ""}><span>${escapeHTML(action.label)}</span></label>`).join("")}</div></details>` : ""}
        </article>`;
      }).join("")}</div>
    </section>`).join("") || '<div class="empty">Nenhum módulo ou função corresponde ao filtro.</div>';

  $("#permissionsModuleList").querySelectorAll('[data-permission-action]').forEach((checkbox) => {
    checkbox.onchange = () => {
      const moduleKey = checkbox.dataset.permissionModule;
      const action = checkbox.dataset.permissionAction;
      selected[action][checkbox.checked ? "add" : "delete"](moduleKey);
      if (checkbox.checked && action !== "read") selected.read.add(moduleKey);
      if (checkbox.checked && action === "write") {
        const module = accessModule(moduleKey);
        module.actions.forEach((item) => selected.actions[moduleKey].add(item.key));
      }
      normalizePermissionModule(moduleKey);
      renderPermissionModules(null, $("#permissionsSearch").value);
    };
  });
  $("#permissionsModuleList").querySelectorAll('[data-permission-functional-action]').forEach((checkbox) => {
    checkbox.onchange = () => {
      const moduleKey = checkbox.dataset.permissionModule;
      const action = checkbox.dataset.permissionFunctionalAction;
      selected.actions[moduleKey][checkbox.checked ? "add" : "delete"](action);
      if (checkbox.checked) {
        selected.read.add(moduleKey);
        if (!permissionFunctionIsReadOnly(action)) selected.write.add(moduleKey);
        if (permissionValueDependentActions.has(action)) selected.actions[moduleKey].add("view_values");
      }
      normalizePermissionModule(moduleKey);
      renderPermissionModules(null, $("#permissionsSearch").value);
    };
  });
  $("#permissionsModuleList").querySelectorAll('[data-permission-category-mode]').forEach((button) => {
    button.onclick = () => {
      const category = accessCategories().find((item) => item.key === button.dataset.categoryKey);
      category.modules.forEach((module) => {
        if (button.dataset.permissionCategoryMode === "none") {
          selected.read.delete(module.key);
          selected.write.delete(module.key);
          selected.export.delete(module.key);
          selected.actions[module.key].clear();
        } else if (button.dataset.permissionCategoryMode === "read") {
          selected.read.add(module.key);
          selected.write.delete(module.key);
          selected.export.delete(module.key);
          selected.actions[module.key].clear();
        } else {
          selected.read.add(module.key);
          if (!module.readOnly) selected.write.add(module.key);
          selected.export.add(module.key);
          selected.actions[module.key] = new Set(module.actions.map((action) => action.key));
        }
        normalizePermissionModule(module.key);
      });
      renderPermissionModules(null, $("#permissionsSearch").value);
    };
  });
  permissionSelectionSummary();
}

function applyRolePermissionTemplate(role) {
  const template = permissionTemplateForRole(role);
  state.permissionDraft = permissionDraftFromTemplate(template);
  $("#permissionsForm").querySelectorAll('[data-permission-capability]').forEach((checkbox) => {
    checkbox.checked = Boolean(template.capabilities?.[checkbox.dataset.permissionCapability]);
  });
  renderPermissionModules(null, $("#permissionsSearch").value);
}

function openUserPermissions(userId) {
  const item = state.settingsUsers.find((candidate) => candidate.id === userId);
  if (!item) return toast("Usuário não encontrado na empresa ativa.");
  const form = $("#permissionsForm");
  const role = $(`[data-role-for="${item.id}"]`)?.value || item.role;
  form.elements.user_id.value = item.id;
  form.elements.role.value = role;
  state.pendingUser = null;
  state.permissionDraft = permissionDraftFromTemplate({
    permissions: item.effective_permissions || {}, actions: item.effective_actions || {},
  });
  $("#permissionsDialogTitle").textContent = `Acessos · ${item.name}`;
  $("#permissionsUserSummary").textContent = `${item.email} · perfil-base ${roleLabels[role] || role}`;
  $("#permissionsSubmit").textContent = "Salvar permissões";
  $("#permissionsSearch").value = "";
  form.querySelectorAll('[data-permission-capability]').forEach((checkbox) => {
    checkbox.checked = Boolean(item.effective_capabilities?.[checkbox.dataset.permissionCapability]);
  });
  renderPermissionModules(item);
  $("#permissionsSearch").oninput = (event) => renderPermissionModules(item, event.target.value);
  $("#permissionsApplyRole").onclick = () => applyRolePermissionTemplate(role);
  $("#permissionsError").classList.add("hidden");
  $("#permissionsDialog").showModal();
}

function openNewUserPermissions(user) {
  const form = $("#permissionsForm");
  state.pendingUser = user;
  form.elements.user_id.value = "";
  form.elements.role.value = user.role;
  $("#permissionsDialogTitle").textContent = `Acessos · ${user.name}`;
  $("#permissionsUserSummary").textContent = `${user.email} · perfil-base ${roleLabels[user.role] || user.role} · nenhum acesso é salvo antes da confirmação`;
  $("#permissionsSubmit").textContent = "Criar funcionário e aplicar acessos";
  $("#permissionsSearch").value = "";
  applyRolePermissionTemplate(user.role);
  $("#permissionsSearch").oninput = (event) => renderPermissionModules(null, event.target.value);
  $("#permissionsApplyRole").onclick = () => applyRolePermissionTemplate(user.role);
  $("#permissionsError").classList.add("hidden");
  $("#permissionsDialog").showModal();
}

async function saveUserPermissions(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const userId = Number(form.elements.user_id.value || 0);
  const item = state.settingsUsers.find((candidate) => candidate.id === userId);
  const effectivePermissions = Object.fromEntries(
    ["read", "write", "export"].map((action) => [action, [...state.permissionDraft[action]].sort()])
  );
  const effectiveActions = Object.fromEntries(
    Object.entries(state.permissionDraft.actions).map(([module, actions]) => [module, [...actions].sort()])
  );
  const effectiveCapabilities = {};
  form.querySelectorAll('[data-permission-capability]').forEach((checkbox) => {
    effectiveCapabilities[checkbox.dataset.permissionCapability] = checkbox.checked;
  });
  const error = $("#permissionsError");
  error.classList.add("hidden");
  try {
    const body = {
      ...(state.pendingUser || {}), role: form.elements.role.value,
      effectivePermissions, effectiveActions, effectiveCapabilities,
    };
    let result;
    if (state.pendingUser) {
      result = await api("/api/users", { method: "POST", body: JSON.stringify(body) });
    } else {
      result = await api(`/api/users/${userId}`, {
        method: "PUT", body: JSON.stringify({ ...body, active: Boolean(item?.active) }),
      });
    }
    dismissDialog($("#permissionsDialog"));
    if (state.pendingUser) {
      toast(result.existingAccount ? "Conta existente vinculada com os acessos definidos." : "Funcionário criado com acessos funcionais auditados.");
      $("#userForm").reset();
      state.pendingUser = null;
    } else {
      toast("Permissões funcionais salvas e auditadas.");
    }
    await loadSettings();
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove("hidden");
  }
}

function saveUser(event) {
  event.preventDefault();
  if (!state.accessControl) return toast("O catálogo de acessos ainda não foi carregado.");
  const user = Object.fromEntries(new FormData(event.currentTarget));
  dismissDialog($("#userDialog"));
  openNewUserPermissions(user);
}

function openUserPasswordReset(button) {
  const form = $("#passwordForm");
  form.reset();
  form.elements.user_id.value = button.dataset.userPassword;
  $("#passwordUserName").textContent = `Defina uma nova senha para ${button.dataset.userName}. As sessões anteriores serão encerradas.`;
  $("#passwordFormError").classList.add("hidden");
  $("#passwordDialog").showModal();
}

async function saveUserPassword(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const password = form.elements.password.value;
  const confirmation = form.elements.password_confirmation.value;
  const error = $("#passwordFormError");
  if (password !== confirmation) {
    error.textContent = "A confirmação não corresponde à nova senha.";
    error.classList.remove("hidden");
    form.elements.password_confirmation.focus();
    return;
  }
  try {
    await api(`/api/users/${form.elements.user_id.value}/password`, { method: "POST", body: JSON.stringify({ password }) });
    dismissDialog($("#passwordDialog"));
    toast("Senha redefinida. O usuário já pode entrar com a nova senha.");
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove("hidden");
  }
}

async function restoreRecord(id) {
  try { await api(`/api/restore/${id}`, { method: "POST", body: "{}" }); toast("Registro restaurado."); loadSettings(); } catch (failure) { toast(failure.message); }
}

function openTrashPurge(recordId = "", title = "") {
  const dialog = $("#trashPurgeDialog");
  const form = $("#trashPurgeForm");
  const bulk = !recordId;
  const expected = bulk ? "ESVAZIAR" : "EXCLUIR";
  form.reset();
  form.elements.record_id.value = recordId;
  dialog.dataset.expected = expected;
  $("#trashPurgeTitle").textContent = bulk ? "Esvaziar a lixeira?" : "Apagar este item definitivamente?";
  $("#trashPurgeMessage").textContent = bulk
    ? "Todos os itens permitidos da empresa ativa serão apagados. Itens usados por cadastros ativos permanecerão na lixeira."
    : `“${title || "Este registro"}” será apagado e não poderá ser restaurado.`;
  $("#trashPurgeConfirmationLabel").textContent = `Digite ${expected} para confirmar`;
  $("#trashPurgeSubmit").textContent = bulk ? "Esvaziar lixeira" : "Apagar definitivamente";
  $("#trashPurgeError").classList.add("hidden");
  form.elements.confirmation.setCustomValidity("");
  dialog.showModal();
  requestAnimationFrame(() => form.elements.confirmation.focus());
}

async function purgeTrash(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const dialog = $("#trashPurgeDialog");
  const confirmation = form.elements.confirmation.value.trim().toUpperCase();
  const expected = dialog.dataset.expected;
  const error = $("#trashPurgeError");
  if (confirmation !== expected) {
    form.elements.confirmation.setCustomValidity(`Digite ${expected} para confirmar.`);
    form.elements.confirmation.reportValidity();
    return;
  }
  form.elements.confirmation.setCustomValidity("");
  error.classList.add("hidden");
  const recordId = form.elements.record_id.value;
  try {
    const result = await api(recordId ? `/api/trash/${recordId}` : "/api/trash", {
      method: "DELETE",
      body: JSON.stringify({ confirmation }),
    });
    dismissDialog(dialog);
    if (result.blocked) {
      toast(`${result.purged} item(ns) apagado(s). ${result.blocked} permaneceram por estarem em uso.`);
    } else {
      toast(recordId ? "Item apagado definitivamente." : `${result.purged} item(ns) apagado(s) definitivamente.`);
    }
    await loadSettings();
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove("hidden");
  }
}

async function importBackup(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  if (!window.confirm(`Importar ${file.name} para a empresa ativa?`)) return;
  try { const result = await api("/api/import", { method: "POST", body: await file.text() }); toast(`${result.imported} registro(s) importado(s).`); loadSettings(); } catch (failure) { toast(`Falha na importação: ${failure.message}`); }
}

async function downloadDatabaseBackup() {
  const passphrase = window.prompt(
    "Crie uma senha forte (mínimo 12 caracteres). Ela será indispensável para restaurar o backup:"
  );
  if (passphrase === null) return;
  if (passphrase.length < 12) return toast("A senha do backup deve possuir ao menos 12 caracteres.");
  try {
    const response = await fetch("/api/backup", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": state.csrf },
      body: JSON.stringify({ passphrase }),
    });
    if (!response.ok) {
      const failure = await response.json().catch(() => ({}));
      throw new Error(failure.message || "Não foi possível gerar o backup");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const filename = disposition.match(/filename="([^"]+)"/)?.[1] || "backup-seccol.sivsbackup";
    const link = document.createElement("a");
    const downloadUrl = URL.createObjectURL(blob);
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
    toast("Backup integral verificado, criptografado e baixado.");
  } catch (failure) {
    toast(failure.message);
  }
}

async function logout() {
  try { await api("/api/logout", { method: "POST", body: "{}" }); } finally {
    state.user = null;
    state.csrf = null;
    $("#authForm").reset();
    showAuth(false);
    $("#authForm [name=email]").focus();
  }
}

$("#authForm").addEventListener("submit", submitAuth);
$("#forgotPasswordButton").onclick = () => openPasswordRecovery();
$("#passwordRecoveryRequestForm").addEventListener("submit", requestPasswordRecovery);
$("#passwordRecoveryResetForm").addEventListener("submit", resetRecoveredPassword);
initializeAssistant();
$("#authModeToggle").onclick = () => {
  const showSetup = $("#authForm").dataset.mode !== "setup";
  showAuth(showSetup);
  const focusTarget = showSetup ? $("#authForm [name=company]") : $("#authForm [name=email]");
  requestAnimationFrame(() => focusTarget.focus());
};
$("#recordForm").addEventListener("submit", saveRecord);
$("#recordForm").addEventListener("input", (event) => {
  const form = $("#recordForm");
  event.target?.closest(".field, .check-field")?.classList.remove("invalid");
  $("#formError").classList.add("hidden");
  if (event.target?.name === "extra_documento") {
    maskPartyDocumentField(event.target);
    const roleField = form.elements["extra_tipo_cadastro"];
    if (roleField) roleField.value = "";
  }
  if (event.target?.name === "extra_cep") maskPartyCepField(event.target);
  syncPartyDocumentType(form);
  lookupPartyCep(form);
  updateRecordCompleteness();
  scheduleRecordDraft();
});
$("#recordForm").addEventListener("change", (event) => {
  const form = $("#recordForm");
  syncPartyDocumentType(form);
  if (event.target?.name === "extra_tipo_lancamento") refreshFinancialPartnerReference(form);
  if (["extra_tipo_lancamento", "extra_tipo_movimento"].includes(event.target?.name)) {
    refreshFinancialCategorySelect(form);
    updateFinancialEvidenceSection(form);
  }
  updateRecordCompleteness();
  scheduleRecordDraft();
});
$("#settingsForm").addEventListener("submit", saveSettings);
$("#trashPurgeForm").addEventListener("submit", purgeTrash);
$("#userForm").addEventListener("submit", saveUser);
$("#permissionsForm").addEventListener("submit", saveUserPermissions);
$("#passwordForm").addEventListener("submit", saveUserPassword);
$("#companyForm").addEventListener("submit", saveCompany);
$("#newButton").onclick = () => {
  const current = canAction(state.screen, "create")
    ? state.screen
    : Object.keys(state.actionPermissions).find((module) => canAction(module, "create"));
  if (!current) return toast("Seu perfil não possui nenhum módulo disponível para novo registro.");
  void openRecord(null, current);
};
$("#menuButton").onclick = () => ui.toggleNavigation ? ui.toggleNavigation() : $("#sidebar").classList.toggle("open");
$("#userButton").onclick = () => state.capabilities.settings ? navigate("settings") : openNotifications();
$("#notificationButton").onclick = openNotifications;
$("#notificationActiveTab").onclick = () => openNotifications("active");
$("#notificationHistoryTab").onclick = () => openNotifications("history");
$("#notificationPreferencesButton").onclick = openNotificationPreferences;
$("#notificationPreferencesForm").onsubmit = saveNotificationPreferences;
$("#companySelect").onchange = (event) => switchCompany(event.target.value);
$("#recordAttachment").onchange = uploadAttachment;
$("#financialDocumentFile").onchange = (event) => {
  const file = event.target.files?.[0];
  $("#financialDocumentFileName").textContent = file
    ? `${file.name} · ${(file.size / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`
    : "PDF, imagem ou XML · até 10 MB";
};
$("#requestApproval").onclick = requestApproval;
$("#addRelationship").onclick = addRelationship;
$("#addNormativeReference").onclick = addNormativeReference;
$("#restoreDraft").onclick = restoreRecordDraft;
$("#discardDraft").onclick = discardRecordDraft;
ui.setDialogGuard?.($("#recordDialog"), () => { saveRecordDraftNow(); return true; });
window.addEventListener("pagehide", saveRecordDraftNow);
$$('[data-form-jump]').forEach((button) => { button.onclick = () => {
  const section = document.getElementById(button.dataset.formJump);
  if (section?.id === "recordSpecifics" && !section.classList.contains("has-essential-fields")) ui.recordDisclosure?.expand();
  else ui.recordDisclosure?.ensureVisible(section);
  requestAnimationFrame(() => section?.scrollIntoView({ behavior: "smooth", block: "start" }));
}; });
$$('[data-close]').forEach((button) => { button.onclick = () => dismissDialog(button.closest("dialog")); });
$("#confirmCancel").onclick = () => dismissDialog($("#confirmDialog"));
$("#confirmDelete").onclick = deleteRecord;

bootstrap().catch((failure) => {
  console.error(failure);
  showAuth(false);
});
