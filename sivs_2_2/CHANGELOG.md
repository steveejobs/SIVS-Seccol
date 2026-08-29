# SIVS 2.2 — execução da auditoria integral

## Automação empresarial supervisionada — 29/08/2026

- Busca automática de editais às 7h, de segunda a sábado, com aviso diário de oportunidades encontradas.
- Central multiempresa de achados para Financeiro, Compras, Estoque, Fiscal/contábil, RH e Qualidade/técnico.
- Execuções idempotentes, evidências auditáveis, filtro por permissão e resumo de IA limitado a contagens agregadas.
- Guardrails impedem pagamentos, transferências, ajustes físicos, transmissões, decisões trabalhistas, lances e assinaturas autônomas.

## Segurança, integridade e concorrência — 15/08/2026

- primeira configuração protegida por transação imediata, estado persistente e teste de corrida concorrente;
- limites de tentativa em login/configuração, JSON estrito, limites por tipo de corpo e tratamento global de falhas com código de referência;
- permissões independentes de leitura, escrita e exportação, aplicadas na API e refletidas no menu;
- validação de servidor para obrigatoriedade, CPF/CNPJ, datas, horas, números finitos, URL, e-mail, status, relacionamentos e base normativa;
- gravação atômica e revisão otimista para impedir sobrescrita silenciosa entre usuários;
- anexos com detecção de formato, bloqueio de executáveis, SHA-256, autorização por módulo e confirmação de licença normativa;
- exposição em rede recusada por padrão sem proxy HTTPS seguro ou exceção explícita.

## Continuidade, aprovação e documentos técnicos

- backup SQLite integral, verificado e criptografado com AES-256-GCM no formato `SIVS-BACKUP-2`;
- utilitário offline de verificação/restauração com cópia recuperável do banco anterior;
- exportação JSON diferenciada do backup de desastre e auditada;
- aprovações com solicitante separado do aprovador, destinatário elegível, unicidade pendente e vínculo à revisão do registro;
- solicitações expiram quando o conteúdo muda ou é excluído;
- prévia e emissão PDF de certificados, laudos e estudos com base normativa, aprovação vigente, licença, SHA-256 e arquivamento automático.

## Editais, operação e qualidade de dados

- pesquisa transformada em trabalho persistente assíncrono com progresso real consultável;
- bloqueio de pesquisas simultâneas por empresa e histórico de falhas/interrupções;
- agendador interno para planos diários e semanais;
- correção da edição da ISO 14644-4 para a 2ª edição de 2022;
- fonte Portal da Transparência reclassificada como consulta manual/API planejada;
- painel financeiro deixa de somar o mesmo fato em módulos sobrepostos;
- importação NF-e atômica, com chave/documento verificados, XML hasheado e cadastros derivados completos;
- suíte ampliada de 13 para 21 testes, incluindo concorrência, RBAC de leitura, JSON hostil, conflito de revisão, aprovação, backup, PDF e trabalhos de edital.

# SIVS 2.1 — portfólio oficial SECCOL

## Cadastros especializados — 15/08/2026

- substituído o modal genérico por ficha operacional premium com identidade própria por módulo;
- criados 46 perfis de cadastro, cobrindo integralmente os esquemas persistentes;
- rótulos, textos orientadores, campos visíveis, campos obrigatórios e agrupamentos agora variam conforme a lógica do módulo;
- Cliente, Licitação, O.S., Laudo, Norma, Frota, Financeiro e demais cadastros preservam o mesmo padrão visual sem compartilhar uma ficha semanticamente genérica;
- relacionamento por Assunto permanece obrigatório e ganhou seção própria com vínculos transversais;
- certificados, laudos e estudos continuam exigindo base normativa vigente;
- incluído indicador real de completude e validação que conduz o usuário ao primeiro campo obrigatório pendente;
- interface adaptada para desktop, tablet e celular e cache instalável renovado.

## Novo

- Central premium **Portfólio SECCOL** com pesquisa integrada.
- 7 produtos e soluções fabricados ou fornecidos pela SECCOL.
- 12 instrumentos técnicos próprios separados dos equipamentos de clientes.
- 29 serviços e ensaios separados das execuções reais de O.S.
- 48 fichas de portfólio anexadas automaticamente por empresa.
- 92 relacionamentos iniciais entre portfólio e normas técnicas.

## Melhorado

- Menu comercial reorganizado em Produtos, Serviços/Ensaios e Portfólio.
- Tela Serviço Técnico distingue instrumentos SECCOL de equipamentos de clientes.
- Indicador operacional do painel não contabiliza os cadastros fixos de catálogo.
- Página oficial, classificação e verificação registradas em cada item.

# SIVS 2.0 — operação integrada, multiempresa e base normativa

## Novo

- 46 módulos persistentes e visão Mobile integrada à Ordem de Serviço.
- Multiempresa com isolamento de registros, assuntos, anexos, editais, usuários, configurações e auditoria.
- Perfis técnico, qualidade, fiscal/financeiro e aprovador.
- Central inicial inspirada no SIVS original, com cartões operacionais e grupos laterais recolhíveis.
- Telas específicas para Calibração, Mobile, XML NF-e, Fiscal/Manager, Normas técnicas, Fontes e Editais.
- 18 referências normativas pré-cadastradas por empresa, cada uma com ficha anexada e fonte oficial.
- Módulos Laudos técnicos e Estudos técnicos.
- Base normativa obrigatória para certificados, laudos e estudos.
- Anexos, aprovações, notificações, planos de busca e eventos fiscais.
- Importador NF-e com fornecedor, itens/produtos, parcelas e XML preservado.
- Backup `SIVS-3` com anexos, aprovações, editais, eventos fiscais e planos de pesquisa.

## Melhorado

- Identidade premium SECCOL em grafite e laranja.
- Menu, hierarquia, contexto de telas, atalhos e responsividade.
- Busca de editais com disparo explícito, barra de execução, cronômetro e diagnóstico por fonte.
- Central metrológica com padrões vencidos e a vencer.
- Relacionamentos com assuntos adicionais e múltiplos vínculos.
- Fluxo fiscal honesto: registro local ou fila, sem simular autorização da SEFAZ.

## Corrigido e endurecido

- Sessão exige associação ativa à empresa e é encerrada ao desativar o usuário naquela empresa.
- Aprovação sem destinatário exige perfil aprovador, gestor ou administrador.
- XML com DTD/entidade externa é rejeitado.
- URLs externas aceitam somente HTTP/HTTPS.
- Nome de anexo é saneado antes do cabeçalho de download.
- Norma em uso não pode ser excluída; norma obsoleta não valida documento novo.
- Registro existente não pode ser transferido de módulo pela API.
- Testes cobrem banco, API, multiempresa, normas, relacionamentos, autenticação e XML.

# SIVS 1.9 — auditoria, integridade e Central de Assuntos

- assuntos migrados de campos JSON para tabela relacional própria;
- registros passam a possuir chave estrangeira para o assunto;
- múltiplos vínculos estruturados entre registros, com deduplicação e bloqueio de autorrelacionamento;
- migração automática e idempotente dos assuntos existentes;
- nova Central de Assuntos com pesquisa, contagem e visão consolidada;
- backup `SIVS-2` com restauração testada entre bancos distintos e remapeamento de identificadores;
- configuração, importação e backup completo restritos ao administrador;
- proteção contra desativação ou despromoção do último administrador;
- novos cabeçalhos de segurança para arquivos estáticos;
- suíte ampliada para assuntos, relações e migrações;
- busca real do PNCP novamente validada nesta versão.

# SIVS 1.8 — relacionamento de assuntos

- bloco de relacionamento incluído em todos os formulários de cadastro;
- campo obrigatório de assunto principal;
- seleção de vínculo com qualquer outro registro ativo do sistema;
- classificação do vínculo: relacionado, originado, continuação, dependência ou parte de;
- assunto exibido diretamente nas tabelas de todos os módulos;
- proteção contra autorrelacionamento durante a edição.

# SIVS 1.7 — identidade premium SECCOL

- aplicação do laranja institucional oficial `#C85D23`;
- menu grafite premium, estados ativos com assinatura laranja e hierarquia visual refinada;
- atualização de cabeçalho, botões, cards, tabelas, formulários, dashboards e busca de editais;
- reorganização das fontes de busca dentro do grupo Comercial;
- preservação das cores semânticas de sucesso, alerta e erro;
- atualização da cor do aplicativo instalável e do cache PWA.

# SIVS 1.6.1 — acesso manual em um clique

- filtros rápidos para fontes automáticas, consulta manual e prospecção privada;
- botão explícito **Abrir e buscar manualmente** em cada portal sem integração automática;
- abertura segura do endereço oficial em nova aba;
- distinção visual entre fonte automática, manual e prospecção privada.

# SIVS 1.6 — contingência oficial e diagnóstico por fonte

- PNCP mantido como fonte automática principal;
- acionamento automático da API oficial de Dados Abertos do Compras.gov.br quando o PNCP não responde;
- painel mostra separadamente o estado de PNCP e Compras.gov;
- paginação do PNCP passou a ser dinâmica, evitando esperar dezenas de páginas quando a fonte está indisponível;
- histórico registra as fontes efetivamente acionadas e seus erros técnicos;
- resultados permanecem deduplicados pelo identificador oficial do PNCP, independentemente da API que os recuperou.

# SIVS 1.5 — acompanhamento da pesquisa

- revisão 1.5.1: reconhecimento de plurais como filtros HEPA/ULPA, troca de filtros e certificação ISO 5, validado contra objetos reais do PNCP;
- painel gráfico exibido imediatamente após o clique em **Pesquisar agora**;
- barra de atividade animada e indicador pulsante;
- tempo decorrido e descrição da etapa atual;
- sequência visual: conexão, consulta PNCP, filtro SECCOL e gravação;
- bloqueio do botão enquanto a pesquisa está ativa;
- estado visual de conclusão ou falha e total de páginas verificadas.

# SIVS 1.4 — inteligência técnica SECCOL

- leitura e incorporação de todas as páginas públicas do site oficial da SECCOL;
- inclusão do catálogo detalhado de ensaios em equipamentos e áreas limpas;
- ranking contextual por setor, instrumento técnico e norma aplicável;
- termos contextuais aumentam a relevância, mas não geram oportunidades sozinhos;
- inclusão de estanqueidade, inflow, perda de carga, vazamento HEPA, fumaça, alarmes CSB, vibração, ruído, lâmpada germicida, selos e componentes eletromecânicos.

# SIVS 1.3 — perfil comercial SECCOL

- vocabulário de busca reconstruído a partir do portfólio oficial da SECCOL;
- remoção de termos hospitalares genéricos que geravam falsos positivos;
- inclusão de áreas e salas limpas, cabines de segurança biológica, fluxo laminar, capelas, filtros HEPA/ULPA, testes PAO, partículas, HVAC, VHP e ISO 14644;
- atalho **Buscar editais agora** em destaque no painel executivo;
- identidade textual da tela de busca ajustada para controle de contaminação ambiental.

# SIVS 1.2 — editais inteligentes

- motor de busca integrado à tela **Busca de Editais**;
- conexão real com a API oficial do PNCP;
- pesquisa paralela por modalidades, período e UF;
- catálogo inicial com 38 fontes verificadas e modo de coleta identificado;
- vocabulário inicial especializado em equipamentos médico-hospitalares, calibração, manutenção e serviços técnicos;
- ranking de relevância por termos encontrados;
- triagem de oportunidades e conversão direta para o funil de Licitações;
- histórico de pesquisas, deduplicação por identificador PNCP e preservação do link original;
- separação explícita entre automação oficial e consulta manual em portais com restrições.

# SIVS 1.1 — melhorias

- formulários adaptados aos dados de cada um dos 18 módulos;
- visão Kanban para CRM, propostas e licitações;
- quatro perfis de acesso: administrador, gestor, operador e consulta;
- cadastro e gestão de usuários pelo administrador;
- lixeira recuperável em substituição à exclusão definitiva;
- snapshots automáticos antes de edição e exclusão;
- inicializador com diagnóstico da porta e abertura automática do navegador;
- atualização do cache da versão instalável;
- reforço dos testes de autorização, histórico e restauração.
