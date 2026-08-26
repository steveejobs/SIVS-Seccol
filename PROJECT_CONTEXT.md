# SIVS SECCOL — contexto vivo do projeto

> Documento de continuidade para desenvolvimento humano e assistido por IA. Atualize a seção
> **Diário de evolução** sempre que arquitetura, comportamento, deploy, segurança ou UX mudarem.

## 1. Propósito

O SIVS SECCOL é um sistema de gestão multiempresa para rotinas administrativas, comerciais,
técnicas, metrológicas, de qualidade, fiscais e financeiras. O sistema prioriza rastreabilidade,
segregação de funções, documentos técnicos, vínculos por assunto e operação auditável.

Versão atual da aplicação: `2.2.0`.

## 2. Stack e execução

- Backend: Python 3.12 em produção, biblioteca HTTP nativa e SQLite.
- Frontend: HTML, CSS e JavaScript sem framework e sem etapa de compilação.
- PWA: manifest e service worker próprios.
- Produção: Dokploy via Nixpacks ou Dockerfile.
- Porta interna: `8844`.
- Persistência atual: `/data/sivs.db` em volume persistente.
- PostgreSQL no Dokploy: existe como recurso, mas o SIVS ainda não o utiliza.

Arquivos centrais:

- `sivs_2_2/server.py`: API, permissões, persistência, documentos e integrações.
- `sivs_2_2/static/index.html`: estrutura permanente da interface e diálogos.
- `sivs_2_2/static/app.js`: aplicação legada, schemas e renderizadores.
- `sivs_2_2/static/styles.css`: estilos legados em migração gradual.
- `sivs_2_2/static/theme/`: fonte canônica de tokens, ergonomia e motion.
- `sivs_2_2/static/js/`: componentes comportamentais reutilizáveis.
- `tools/`: ferramentas Python de desenvolvimento e otimização de ativos.

## 3. Princípios não negociáveis

1. Segurança e integridade prevalecem sobre conveniência visual.
2. Toda gravação continua validada no servidor; o frontend não é fonte de verdade.
3. Dados, usuários e permissões permanecem isolados por empresa.
4. Movimento deve orientar, nunca atrasar, distrair ou impedir interação.
5. A interface deve funcionar com teclado, toque, mouse e movimento reduzido.
6. Componentes devem usar tokens; valores visuais soltos são dívida técnica.
7. Refatorações grandes serão incrementais, com contratos e testes antes de remoções.
8. SQLite exige uma réplica. Migrar para PostgreSQL é um projeto separado e explícito.

## 4. Arquitetura visual e de componentes

Estrutura-alvo incremental:

```text
sivs_2_2/static/
├── theme/
│   ├── tokens.css       # cores, tipografia, espaço, raio, sombra e duração
│   ├── foundations.css  # reset ergonômico, foco, toque e acessibilidade
│   ├── responsive.css   # navegação, densidade e ergonomia por viewport
│   ├── components.css   # scrollbars, selects, listas e formulários progressivos
│   └── motion.css       # entrada, saída, diálogos e redução de movimento
├── js/
│   ├── core/
│   │   ├── platform.js   # capacidades do dispositivo e namespace compartilhado
│   │   ├── state.js      # estado mutável da sessão e da tela
│   │   ├── formatters.js # moeda, datas e saídas seguras para HTML/URL
│   │   └── http.js       # cliente de API, CSRF, erros e sessão expirada
│   └── ui/
│       ├── motion.js     # entrada/saída de telas e anúncios acessíveis
│       ├── dialogs.js    # fechamento animado, Escape e cancelamento
│       ├── pointer.js    # profundidade sutil para mouse compatível
│       ├── navigation.js # menu móvel, scrim, Escape e estado ARIA
│       ├── record-disclosure.js # criação essencial e edição completa
│       └── experience.js # composição dos componentes transversais
├── index.html
├── styles.css            # legado; reduzir progressivamente
└── app.js                # legado; extrair por domínio progressivamente
```

Convenções:

- componentes visuais consomem variáveis `--color-*`, `--space-*`, `--radius-*` e `--motion-*`;
- interações de mouse só são ativadas em dispositivos com ponteiro preciso;
- elementos interativos têm foco visível e alvo mínimo adequado para toque;
- entrada de página usa deslocamento e opacidade sutis; saída é mais curta;
- `prefers-reduced-motion: reduce` desativa deslocamentos e suavização de rolagem;
- módulos novos devem ser extraídos de `app.js` por responsabilidade, sem reescrita total.

## 5. Auditoria inicial — 15/08/2026

### Pontos fortes

- identidade consistente em verde profundo, grafite, ouro e laranja SECCOL;
- boa densidade de informação para contexto administrativo;
- formulários especializados, vínculos, governança e feedback de completude;
- responsividade já prevista para dashboards, tabelas, modais e navegação;
- proteção de saída HTML e validação robusta no backend;
- contratos automatizados para schemas, IDs e formulários.

### Achados e prioridade

| Prioridade | Área | Achado | Direção |
|---|---|---|---|
| P0 | Deploy/dados | SQLite depende de volume e réplica única | Mantido e documentado |
| P1 | Arquitetura | `app.js` concentra aproximadamente 144 KB | Extrair componentes gradualmente |
| P1 | Tema | tokens estavam no início do CSS legado | Centralizar em `theme/tokens.css` |
| P1 | Motion | telas trocavam sem entrada/saída | Orquestrar no componente de experiência |
| P1 | Acessibilidade | não havia política global de movimento reduzido | Criar fallback obrigatório |
| P1 | Mobile | menu não tinha scrim, Escape ou estado ARIA completo | Criar componente de navegação |
| P2 | Ergonomia | textos técnicos de 7–10 px em formulários | Elevar legibilidade sem perder densidade |
| P2 | Mouse | hover inconsistente e pouco feedback de pressão | Unificar estados e profundidade sutil |
| P2 | CSS | aproximadamente 64 KB em poucas linhas extensas | Migrar por camadas, sem formatação arriscada |
| P2 | PWA | cache precisava conhecer novos ativos modulares | Atualizar lista e versão do cache |
| P3 | Ferramentas | não existia pipeline de otimização de imagens | Criar utilitário seguro em `tools/` |

### Resultado da primeira rodada

- concluído: tema, foundations e motion separados do CSS legado;
- concluído: estado, formatadores e cliente HTTP extraídos para `js/core/`;
- concluído: navegação móvel com scrim, Escape, bloqueio de rolagem e `aria-expanded`;
- concluído: navegação compacta em tablets até 900 px, com `inert` quando o drawer está fechado;
- concluído: entrada/saída de telas e diálogos, feedback de mouse e suporte a movimento reduzido;
- concluído: skip link, região viva, foco visível e alvos de toque mais ergonômicos;
- concluído: primeira ferramenta Python segura para otimização de imagens;
- validado: autenticação renderizada em navegador real e ativos servidos pelo backend;
- pendente: decompor regras de domínio ainda concentradas em `app.js` nas etapas incrementais abaixo;
- pendente: executar a suíte do servidor em Python 3.12/Linux para eliminar o falso negativo de limpeza
  de arquivos SQLite observado no Python 3.14/Windows.

### Matriz responsiva vigente

| Faixa | Navegação | Conteúdo e interação |
|---|---|---|
| acima de 900 px | sidebar persistente | densidade desktop e tabelas com rolagem local |
| 761–900 px | drawer com scrim e Escape | conteúdo em largura total e padding intermediário |
| 341–760 px | drawer com foco isolado | empilhamento mobile, controles de pelo menos 44 px e diálogos em `dvh` |
| 320–340 px | drawer | indicadores passam para uma coluna quando necessário |

O auditor percorre automaticamente os 54 destinos de navegação disponíveis ao administrador nas
quatro viewports de referência: desktop `1440×1000`, tablet `834×1112`, mobile `390×844` e
mobile compacto `360×800`.

## 6. Plano de modularização

### Etapa atual

- separar tokens, foundations, motion e experiência transversal;
- introduzir contratos de estrutura para impedir regressões;
- manter `app.js` como orquestrador enquanto módulos são extraídos.

### Próximas extrações recomendadas

1. ampliar `js/core/http.js` com downloads tipados e cancelamento de requisições;
2. extrair troca de empresa e capacidades para um controlador de sessão;
3. evoluir `js/ui/dialogs.js` com restauração explícita de foco;
4. criar `js/components/data-table.js`: tabelas, vazio, loading e ações;
5. criar `js/modules/records/`: formulário especializado e relacionamentos;
6. criar `js/modules/tenders/`: fontes, pesquisa, progresso e resultados;
7. criar `js/modules/settings/`: empresa, usuários, backup e auditoria.

Cada extração deve manter os contratos públicos existentes até os chamadores migrarem.

## 7. Critérios de qualidade UI/UX

- foco visível com contraste suficiente;
- alvo de toque preferencial de 44 × 44 px;
- mensagem de carregamento, vazio, sucesso e erro em todo fluxo assíncrono;
- ações destrutivas com confirmação e descrição da consequência;
- nenhuma informação disponível apenas por cor ou hover;
- títulos e landmarks coerentes para leitores de tela;
- tabelas continuam utilizáveis em telas pequenas por rolagem horizontal indicada;
- animações em `transform` e `opacity`, evitando custo de layout;
- estados pressionado, hover e foco coerentes em botões e cartões.

## 8. Ferramentas

`tools/optimize_images.py` otimiza imagens raster para publicação. O padrão é não sobrescrever
originais, preservando segurança. Consulte `tools/README.md`.

`tools/responsive_audit.mjs` cria banco e usuário descartáveis, abre navegador Chromium, percorre
todo o menu em quatro viewports, mede overflow, registra controles pequenos e testa formulário,
modo essencial, picker de opções, rascunho recuperável, busca global, drawer, Escape, ARIA e
bloqueio de rolagem. Os resultados ignorados pelo Git ficam em `.artifacts/`.

Ferramentas futuras sugeridas:

- auditor de tamanho e dimensões de imagens;
- verificador de contraste dos tokens;
- relatório de seletores CSS não utilizados;
- validador de links e fontes normativas;
- smoke test de deploy e endpoint `/api/status`.

## 9. Validação obrigatória

```bash
python -m unittest discover -s sivs_2_2/tests -p "test_frontend_contract.py" -v
python -m py_compile sivs_2_2/server.py sivs_2_2/launcher.py sivs_2_2/restore_backup.py
node --check sivs_2_2/static/app.js
node --check sivs_2_2/static/service-worker.js
# Execute node --check também para cada arquivo em sivs_2_2/static/js/.
python tools/optimize_images.py sivs_2_2/static --dry-run
node tools/responsive_audit.mjs
```

As conexões SQLite devem ser encerradas pela mesma thread que as abriu. O servidor aplica esse
contrato ao fim de cada requisição, pesquisa assíncrona e ciclo do agendador.

## 10. Diário de evolução

### 26/08/2026 — leitura assistida de editais com custo e qualidade equilibrados

- a interface, o payload persistido e a auditoria funcional deixaram de revelar fornecedor ou modelo
  da IA na leitura de editais;
- a leitura inicia em uma camada de custo e qualidade equilibrados e só usa a camada de maior capacidade quando a validação
  local identificar estrutura ou citações insuficientes, mantendo conferência humana obrigatória;
- a pesquisa oficial de oportunidades continua sem IA: a chamada assistida ocorre apenas ao solicitar
  a leitura dos documentos de um edital.

### 26/08/2026 — trilha de auditoria mais legível

- a tela de Configurações passou a resumir exclusões, alterações/criações e o último evento;
- a trilha agora permite buscar por usuário, ação, registro ou detalhe e filtrar por tipo de ação,
  mantendo os 100 eventos devolvidos pelo servidor, o isolamento por empresa e a permissão de auditoria;
- cada evento mostra ação em linguagem funcional, usuário, entidade, ID, horário e detalhe em texto,
  com layout responsivo e alvos acessíveis; o cache PWA foi atualizado para `sivs-v2.2.0-audit-trail-81`.

### 15/08/2026 — base de continuidade e auditoria

- criado este documento vivo e `AGENTS.md` para futuros contextos;
- documentada a arquitetura atual, os riscos e a estratégia incremental;
- centralizados tokens, foundations e motion em `static/theme/`;
- extraídos estado, formatadores, cliente HTTP e componentes transversais de UI;
- adicionados skip link, região de status, foco consistente, alvos de toque e menu móvel acessível;
- integradas transições de entrada/saída às trocas de tela e ao fechamento de diálogos;
- atualizado o cache da PWA para incluir os novos ativos;
- criados contratos automatizados para ordem dos ativos, tema, acessibilidade e componentes;
- criada a ferramenta `tools/optimize_images.py`, com saída não destrutiva por padrão;
- validados 6 contratos de frontend, 11 arquivos JavaScript, compilação Python e 15 rotas estáticas;
- auditada visualmente a primeira configuração em navegador Chromium desktop e layout responsivo;
- criada camada `theme/responsive.css` e movido o breakpoint da navegação compacta para 900 px;
- garantidos controles de 44 px em tablet/mobile sem depender da detecção de tipo de ponteiro;
- corrigido o diálogo mobile para respeitar `100dvh`, mantendo cabeçalho e rodapé alcançáveis;
- impedido foco no drawer fechado com `inert` e `aria-hidden`, preservando abertura, scrim e Escape;
- criado `tools/responsive_audit.mjs`, sem dependências externas, com modo completo e `--quick`;
- auditados 54 destinos em cada viewport, totalizando 162 combinações sem overflow de documento;
- aprovados cinco fluxos interativos: três formulários responsivos e drawers tablet/mobile;
- executados 23 testes completos: os fluxos funcionais responderam, mas 15 encerraram com erro de
  limpeza de arquivos SQLite exclusivo do Python 3.14/Windows já documentado acima;
- adotado o nome padrão `tools/` para a pasta de ferramentas solicitada como “tous”.

### 15/08/2026 — produtividade sem romper a familiaridade

- preservados sidebar, grupos, módulos, painel executivo e formulários conhecidos pelos usuários;
- criada a seção `Meu trabalho`, combinando aprovações, prazos e registros do próprio usuário,
  sempre filtrados no servidor pelas permissões e pela empresa ativa;
- criada busca global por `Ctrl/Cmd + K`, com áreas, registros, teclado e cancelamento de busca;
- adicionados favoritos, acessos recentes e rascunhos isolados por usuário e empresa;
- os rascunhos usam `sessionStorage`, expiram em sete dias e exigem restauração explícita;
- adicionados `theme/productivity.css`, `core/preferences.js`, `core/drafts.js` e
  `ui/command-palette.js` à arquitetura modular e ao cache da PWA;
- adicionada `GET /api/search`, que devolve somente campos enxutos de módulos permitidos;
- corrigido o ciclo de vida das conexões SQLite por thread; o registro anterior do problema de
  limpeza no Python 3.14/Windows fica superado por esta correção;
- auditadas 216 combinações (54 telas em quatro viewports) e 15 fluxos interativos sem falhas:
  desktop `1440×1000`, tablet `834×1112`, mobile `390×844` e `360×800`;
- aprovados 25 de 25 testes automatizados no Python 3.14/Windows;
- a nova seção usa entrada e saída simétricas de 600 ms e respeita movimento reduzido.

### 15/08/2026 — componentes modernos e cadastro progressivo

- auditadas scrollbars, listas, tabelas, selects e a jornada completa de novo registro;
- criada `theme/components.css` como camada central de componentes transversais;
- substituída a aparência antiga das barras de rolagem por indicadores finos, arredondados e sem
  botões de extremidade, preservando rolagem nativa e contraste em fundos escuros;
- modernizados agrupamento, hover e hierarquia de listas, notificações e tabelas extensas;
- aplicado picker moderno a selects compatíveis com `appearance: base-select`, mantendo fallback
  nativo e sem recriar comportamento de teclado em JavaScript;
- criado `ui/record-disclosure.js`: novos registros mostram primeiro o essencial e edições abrem
  completas; detalhes, navegação lateral, validação e restauração de rascunho permanecem integrados;
- mantidos todos os campos, payloads, permissões, validações do servidor e contratos de IDs;
- corrigido o alvo de toque da busca global para 44 px no mobile;
- criado `sivs_2_2/AUDITORIA_UI_UX_2.2_2026-08-15.md` com diagnóstico, decisões e próximos passos;
- adicionada alternância entre primeira configuração e login para quem já possui acesso;
- empresa e nome só são exigidos no modo de configuração, e essa configuração deixa de ser oferecida
  assim que o servidor registra o administrador inicial;
- o auditor agora valida os dois modos de acesso, o retorno à configuração e o login exclusivo após
  a configuração, mantendo relatórios rápidos separados dos relatórios completos;
- aprovados 27 de 27 testes, 216 combinações responsivas e 25 fluxos interativos sem falhas,
  incluindo os estados de primeira configuração e login após o servidor estar configurado.

### 15/08/2026 — proteção local de credenciais do Dokploy

- adicionado `chaves_dokploy` ao `.gitignore` para impedir commit acidental do arquivo local de
  credenciais usado na configuração do MCP;
- nenhuma credencial foi copiada para arquivos versionados do projeto.

### 15/08/2026 — persistência obrigatória do SQLite no Dokploy

- diagnosticado no Dokploy que a aplicação estava sem mounts, embora gravasse em `/data/sivs.db`;
- criado o volume nomeado `sivs-seccol-data`, montado em `/data`, para preservar cadastros e
  registros entre recriações do contêiner;
- adicionada `SIVS_REQUIRE_PERSISTENT_DB=1` aos builds Dockerfile e Nixpacks;
- o servidor agora recusa a inicialização de produção quando o diretório do SQLite não é um
  ponto de montagem, evitando que uma configuração aparentemente válida seja perdida;
- adicionados testes da trava e da persistência de usuário e senha após reabrir o arquivo SQLite;
- o banco efêmero anterior já estava vazio (`configured:false`) no momento da correção, portanto
  não havia cadastro recuperável para migrar ao volume novo.

### 15/08/2026 — busca textual de editais no índice oficial do PNCP

- diagnosticado que a API cronológica respondia, mas possuía centenas de páginas por modalidade;
  o limite de nove requisições examinava uma fração arbitrária e retornava zero aderências;
- em amostra real de 350 contratações das primeiras páginas, nenhuma continha literalmente as
  frases especializadas, confirmando que ampliar apenas o filtro local não resolveria a cobertura;
- adotada como rota principal a busca textual usada pelo portal oficial do PNCP, com frases entre
  aspas, editais recebendo propostas, recorte local por período/UF e deduplicação pelo controle PNCP;
- mantidas a API oficial por publicação e a API Compras.gov como contingências em cascata;
- o vocabulário padrão agora consulta oito expressões representativas, limitado a cinquenta
  resultados por expressão e duas tentativas, equilibrando cobertura, latência e limites da fonte;
- buscas reais encontraram 11 oportunidades em sete dias; entre elas, certificação de cabine de
  segurança biológica/capela de exaustão para a EBSERH e instalação de capelas para a EPAMIG;
- o fluxo HTTP assíncrono foi validado com duas expressões: quatro resultados, quatro novos,
  deduplicados, com prazos, órgãos, UFs, pontuação e links oficiais persistidos corretamente;
- risco restante: o índice textual do portal não faz parte do Swagger público de consulta e pode
  mudar; por isso a contingência documentada permanece obrigatória e falhas parciais são exibidas.

### 15/08/2026 — busca de editais resiliente aos limites das fontes oficiais

- auditado o fluxo completo de Inteligência Comercial, incluindo permissões, jobs, polling,
  histórico, deduplicação e consultas reais ao PNCP e ao Compras.gov.br;
- identificada a causa principal da intermitência: até 20 chamadas em rajada ao PNCP geravam
  respostas HTTP 429, mas a execução era apresentada incorretamente como concluída;
- substituído o paralelismo por consultas sequenciais, limitadas a nove páginas por execução,
  com repetição e espera progressiva para HTTP 429 e falhas transitórias das fontes;
- pesquisas com páginas indisponíveis agora registram e exibem estado parcial e cobertura real;
- o catálogo interno usado pelo painel passou a exigir somente leitura em `editais`, sem bloquear
  perfis comerciais que não podem administrar o módulo separado de fontes;
- validada pesquisa real: 8 de 9 consultas responderam durante instabilidade pontual do PNCP e
  16 oportunidades foram filtradas, deduplicadas e persistidas corretamente;
- aprovados 29 de 29 testes automatizados, incluindo retry de rate limit e contrato de permissão.

### 15/08/2026 — consulta oficial, recursos e documentos de editais

- criada a atualização individual de cada oportunidade pelo PNCP, com persistência isolada por empresa de dados oficiais, itens e metadados dos documentos;
- o valor estimado passa a ser atualizado somente quando publicado pelo PNCP ou quando a soma dos itens publicados é inequívoca; orçamento sigiloso jamais é convertido em valor zero;
- a tela de detalhes passa a expor a fonte de recurso orçamentário publicada, o amparo legal, prazo, itens e a lista de documentos oficiais;
- documentos do PNCP podem ser visualizados ou baixados pelo SIVS após validação de origem HTTPS oficial, sem redirecionamento, com limite de tamanho e auditoria de download;
- a orientação de conferência deixa explícito que o SIVS não substitui a leitura do edital e anexos nos termos da Lei nº 14.133/2021;
- corrigido o recorte de datas da busca para o fuso UTC do PNCP, evitando descartar publicação válida na virada entre o horário local e UTC.
- corrigida a rolagem com mouse sobre a tabela de oportunidades: a área passou a manter somente a rolagem horizontal da tabela, liberando a rolagem vertical da página.
- corrigido o uso do vocabulário de 77 palavras-chave: o PNCP é consultado em lotes rotativos de até oito termos por execução, em vez de ignorar silenciosamente os termos após o primeiro lote; a interface passou a explicar esse limite da fonte oficial.

### 15/08/2026 — leitura assistida de editais pelo OpenRouter

- validada a credencial OpenRouter e ajustada a integração para o roteamento disponível na conta, preservando a auditoria de cada análise;
- adicionada extração limitada de texto de PDFs oficiais do PNCP com `pypdf`, sem armazenar o texto integral do edital;
- criada a ação “Ler documentos com IA” nos detalhes da oportunidade: a IA produz resumo, prazos, habilitação, requisitos técnicos, julgamento, riscos, recomendação e citações por documento/página;
- a origem de cada arquivo continua validada como HTTPS do PNCP, sem redirecionamentos, com limite de tamanho; PDFs digitalizados sem camada de texto são apontados como pendência de OCR;
- a análise é apoio à decisão e não declaração automática de conformidade jurídica, permanecendo obrigatória a conferência humana do edital e anexos.
- validado em execução ponta a ponta no edital PNCP `15126437000305-1-003219/2026`: cinco documentos atualizados, 24 páginas de texto lidas e 12 citações estruturadas retornadas pela IA.

### 15/08/2026 — preparação segura da credencial OpenRouter

- criado `.env` local com a variável `OPENROUTER_API_KEY`, sem valor preenchido;
- criado `.env.example` versionável para documentar o contrato da futura integração;
- arquivos `.env` reais foram adicionados ao `.gitignore`, preservando apenas o exemplo público;
- o servidor ainda não consome essa variável; o carregamento será implementado junto da função de IA.

### 15/08/2026 — assistente interno com contexto autorizado

- criado painel lateral acessível para perguntas sobre prazos, propostas, licitações, ordens de
  serviço, clientes e calibrações;
- adicionados planejador de intenções e consultas SQL controladas, sempre limitadas à empresa ativa
  e aos módulos que o usuário pode ler;
- a IA recebe somente contexto mínimo serializado, nunca acesso ao SQLite ou ao executor SQL;
- integrado OpenRouter por HTTP nativo, com JSON Schema estrito, ZDR, bloqueio de coleta de dados,
  fallback explícito e fallback determinístico quando a chave estiver ausente/indisponível;
- consultas, modelo, fontes autorizadas e resposta são registrados na auditoria;
- adicionadas sugestões para histórico de cliente, próximo passo CRM e rascunho comercial; preços,
  impostos e condições permanecem exclusivamente sob validação do servidor;
- validada a consulta de propostas e a auditoria do assistente, além dos contratos de frontend.

### 15/08/2026 — identidade do Sistema Seccol e cadastro unificado de parceiros

- ajustada a identidade exibida na interface para **Sistema Seccol**;
- criada a aba única **Clientes e fornecedores**, mantendo os módulos físicos legados para não quebrar referências existentes;
- cada novo cadastro exige a identificação `C` (cliente), `F` (fornecedor) ou `A` (ambos); o servidor converte a seleção para o módulo físico adequado e gera código `C-0001`, `F-0001` ou `A-0001` por empresa;
- a natureza da pessoa é derivada e conferida pelo documento: CPF = pessoa física, CNPJ = pessoa jurídica; a interface mostra os papéis por extenso e mantém C/F/A apenas como código curto;
- a leitura e exportação da aba unificada consultam apenas os módulos físicos autorizados ao usuário;
- preservados os cadastros e contratos anteriores de `clientes` e `fornecedores`, com identificação automática no formulário de edição.

### 15/08/2026 — modalidade na tabela de oportunidades

- a tabela de oportunidades da inteligência de editais agora exibe **Modalidade** entre Aderência e Oportunidade;
- o título da oportunidade fica separado da modalidade, preservando órgão/UF, prazo, valor, situação e ações;
- o valor continua vindo do campo oficial persistido pelo PNCP/Compras.gov.

### 15/08/2026 — avaliação de concorrentes e referência de preços

- substituída a tela genérica de concorrentes por um workspace de avaliação competitiva com cards legíveis e hierarquia visual explícita;
- adicionada classificação interna, evidências e observações de avaliação ao cadastro de concorrentes;
- criado benchmark agregado de preço médio das últimas licitações/pregões com valor informado, limitado à empresa e às permissões do usuário;
- incluída tabela com modalidade, objeto, órgão/UF, valor, prazo e situação, deixando claro que a média é referência e não preço comercial aprovado.

### 15/08/2026 — classificação curta de parceiros e menu comercial

- consolidada a identificação do cadastro unificado em `C` (cliente), `F` (fornecedor) e `A` (ambos);
- gerados códigos sequenciais por empresa (`C-0001`, `F-0001`, `A-0001`) no servidor, sem confiar no frontend;
- reorganizado o menu em **Comercial** e **Inteligência Comercial**, conectando fontes, editais, concorrentes/preços e licitações.

### 15/08/2026 — vínculo financeiro com o cadastro unificado

- contas a pagar passam a identificar explicitamente `Fornecedor (F)` ou `Cliente e fornecedor (A)`;
- contas a receber passam a identificar `Cliente (C)` ou `Cliente e fornecedor (A)`;
- o servidor aplica a regra mesmo quando o frontend é contornado, preservando compatibilidade com registros antigos sem a classificação.

### 15/08/2026 — cadastro progressivo por CPF/CNPJ

- a primeira etapa do cadastro unificado exige CPF ou CNPJ;
- o servidor deriva e valida Pessoa física/Pessoa jurídica pelo tamanho e validade do documento;
- a interface só libera papel comercial, identificação e demais dados após documento válido, reduzindo ambiguidade e erros de classificação.

### 15/08/2026 — preenchimento progressivo de documento e endereço

- o cadastro de cliente/fornecedor começa pelo CPF ou CNPJ;
- após documento válido, a natureza da pessoa é identificada e os demais campos são liberados;
- CEP válido consulta ViaCEP e preenche logradouro, bairro, cidade e UF, sempre permitindo conferência e edição antes de salvar;
- CPF/CNPJ não são consultados em bases públicas sem provedor autorizado e contrato de tratamento de dados.

### 15/08/2026 — primeira etapa obrigatória do cadastro de parceiros

- o diálogo de Cliente e fornecedor foi reordenado para começar visualmente pelo CPF/CNPJ;
- nome, assunto e demais seções ficam bloqueados até o documento possuir 11 ou 14 dígitos;
- após a identificação, Pessoa física/jurídica e os demais campos são liberados em sequência;
- mensagens de progresso e validação deixam de listar campos secundários antes do documento inicial.

### Como atualizar

Acrescente data, objetivo, arquivos impactados, decisões, testes executados e riscos restantes.
Não apague histórico relevante; marque itens substituídos e explique a nova decisão.

### 15/08/2026 — correção de inclusão no cadastro unificado

- auditada a rejeição de novos clientes/fornecedores no endpoint de registros;
- fornecedor unificado sem avaliação agora nasce com estado operacional `Pendente`, em vez de falhar
  na validação específica do módulo físico;
- o servidor passou a aceitar também `C e F`/`A` para compatibilidade com rascunhos e clientes
  anteriores à padronização dos rótulos;
- adicionados testes de fornecedor sem avaliação e parceiro com os dois papéis; os três testes
  direcionados passaram, assim como compilação Python e `git diff --check`.

### 15/08/2026 — comando global de novo registro

- o botão global agora declara explicitamente `type="button"` e não depende de submissão implícita;
- quando a tela atual não é gravável, o comando escolhe o primeiro módulo gravável do usuário ou
  exibe uma mensagem clara, em vez de falhar silenciosamente;
- cache da PWA atualizado para `sivs-v2.2.0-ux-refinement-5-new-record`.

### 15/08/2026 — correção bloqueante do diálogo de novo cadastro

- auditado o clique em **Novo registro** no cadastro relacional;
- corrigido `form.id.value`, que acessava a propriedade nativa `id` do `<form>` em vez do campo
  oculto de identificador e lançava `TypeError` antes de abrir o diálogo;
- todas as leituras e escritas do identificador agora usam `form.elements.id`;
- cache da PWA atualizado para `sivs-v2.2.0-ux-refinement-6-record-form-id`.

### 15/08/2026 — atualização imediata da PWA para a correção de cadastro

- a PWA agora chama `skipWaiting` na instalação e `clients.claim` na ativação, para evitar que uma
  aba continue controlada pelo service worker anterior após uma correção bloqueante;
- criado contrato de frontend que impede o retorno de `form.id.value` e verifica o botão de novo
  registro e a atualização imediata do service worker;
- o servidor local em `127.0.0.1:8844` foi conferido e entrega o `app.js` com `form.elements.id`.

### 15/08/2026 — seções contextuais e integridade relacional

- diagnosticado que 33 áreas usavam o mesmo carregador e a mesma tabela genérica, fazendo a
  navegação trocar somente o título, sem expor os dados que caracterizam cada operação;
- criado contrato de visualização por módulo: texto operacional, nome de ação e colunas principais
  para parceiros, CRM, propostas, contratos, licitações, compras, financeiro, serviço técnico,
  qualidade, estoque, vendas, pessoas e frota; os demais usam os campos do schema correspondente;
- a tabela relacional agora apresenta os dados do cadastro escolhido em vez de repetir apenas
  Registro/Assunto/Status;
- adicionados índices compostos por empresa, módulo, situação, prazo e assunto, acompanhando os
  filtros reais do SIVS;
- adicionadas travas SQLite que recusam relacionamentos ou assuntos entre empresas diferentes;
- validados 39 testes completos (API, banco e frontend), com aprovação integral; cache PWA atualizado
  para `sivs-v2.2.0-ux-refinement-8-contextual-modules`.

### 15/08/2026 — auditoria de usuários, senha e login

- o banco local foi auditado sem expor credenciais: havia somente um usuário ativo, um vínculo de
  empresa e nenhum evento de criação de usuário adicional; os logins bem-sucedidos eram somente da
  conta existente;
- o cadastro de usuário agora diferencia uma conta nova de um e-mail que já possui acesso na empresa,
  impedindo a impressão incorreta de que uma nova senha foi gravada para uma conta existente;
- criado fluxo administrativo de redefinição de senha, com confirmação, encerramento das sessões
  anteriores e evento de auditoria, sem retornar senha ou hash ao cliente;
- validado o ciclo completo por API: criação, login com a senha inicial, redefinição, rejeição da
  senha anterior e login com a nova; cache PWA atualizado para `sivs-v2.2.0-ux-refinement-9-user-access`.

### 15/08/2026 — correção de cache para as telas contextuais

- a captura do usuário confirmou que uma aba ativa ainda executava o `app.js` anterior, pois exibia a
  descrição e filtros genéricos removidos da versão contextual;
- o `app.js` passou a usar URL versionada no HTML e no precache da PWA, impedindo reaproveitamento da
  resposta antiga; cache atualizado para `sivs-v2.2.0-ux-refinement-10-contextual-modules`.

### 15/08/2026 — auditoria real das interações do menu

- criado `tools/audit_interactions.py`, que inicia servidor e SQLite descartáveis, abre Chrome
  headless e percorre as telas sem tocar no banco real;
- o primeiro percurso encontrou exceção DOM ao abrir Clientes e fornecedores: as seções do
  formulário eram reordenadas pelo elemento-pai incorreto, impedindo a abertura do diálogo;
- corrigida a ordenação entre identificação e campos específicos e também a restauração da ordem ao
  trocar para outro módulo;
- o logout agora limpa e focaliza o formulário de acesso, evitando reaproveitar ou concatenar as
  credenciais do usuário anterior;
- validação final aprovada: 53 telas navegadas, diálogos de cadastro abertos com o módulo correto,
  Clientes e fornecedores com 20 controles especializados, zero erros JavaScript acionáveis e ciclo
  de criação/login de usuário concluído;
- relatório descartável gerado em `.artifacts/interaction-audit.json`; cache PWA atualizado para
  `sivs-v2.2.0-ux-refinement-13-interactions`.

### 15/08/2026 — eliminação do JavaScript intermediário em cache

- diagnosticado que o servidor aplicava `public, max-age=3600` ao `app.js`; por isso o navegador
  podia exibir o rótulo contextual novo e ainda executar por uma hora a versão intermediária que
  quebrava o clique em Cadastrar parceiro;
- HTML, JavaScript e service worker agora usam `no-cache, no-store, must-revalidate` e `Pragma:
  no-cache`; CSS e demais ativos estáveis preservam cache de uma hora;
- adicionado teste HTTP de regressão para os cabeçalhos de `app.js` e `service-worker.js`.

### 15/08/2026 — aderência rígida de editais e visualizador interno

- a busca deixou de aceitar uma palavra-chave global como prova suficiente: resultados novos só são
  gravados quando correspondem a produto ou serviço ativo cadastrado na empresa corrente;
- a comparação usa títulos e descrições do catálogo, elimina palavras genéricas e exige duas
  características técnicas ou uma sigla distintiva (como HEPA, ULPA, PAO, UVC, CSB ou HVAC);
- resultados já armazenados são reclassificados sem exclusão, usando também os itens oficiais do
  PNCP quando disponíveis; a tela mostra somente os aderentes por padrão e permite consultar todos;
- filtros passaram a pesquisar objeto, órgão, cidade, UF, modalidade, termos e itens do catálogo;
  os cartões de situação agora funcionam como filtros e a quantidade filtrada fica visível;
- a leitura por IA continua estritamente manual, acionada somente em **Ler documentos com IA**;
- **Ver no sistema** agora abre um diálogo próprio com zoom entre 50% e 250%, ajuste, download,
  nova aba, teclado e fechamento por `Esc`, sem substituir ou deslocar os detalhes do edital;
- cache da PWA atualizado para `sivs-v2.2.0-ux-refinement-14-tenders`;
- validados 42 testes completos e dois testes focados de busca, incluindo a rejeição de manutenção
  predial recuperada por termo genérico; a auditoria headless percorreu 53 telas sem erro acionável;
  compilação Python e `git diff --check` aprovados.

### 15/08/2026 — workspace compacto para todos os cadastros

- os formulários especializados passaram a usar largura útil maior e altura adaptativa ao conteúdo,
  eliminando a altura mínima que criava grandes áreas vazias nos cadastros curtos;
- cabeçalho, progresso, navegação lateral, seções e rodapé foram compactados sem remover contexto,
  status de preenchimento, etapas ou ações principais;
- campos gerais usam até três colunas e grupos específicos usam duas colunas no desktop, com retorno
  ao fluxo de uma coluna nos tamanhos móveis; CPF/CNPJ permanece destacado como primeira decisão no
  cadastro progressivo de clientes e fornecedores;
- tipografia de rótulos e títulos internos foi reforçada para dar prioridade às informações do
  cadastro, e formulários longos continuam limitados à janela com rolagem interna;
- CSS e JavaScript agora são entregues sem cache persistente pelo servidor, e o componente recebeu
  URL versionada no HTML e no precache `sivs-v2.2.0-ux-refinement-15-forms`;
- o auditor de interações ganhou captura opcional de formulários; foram conferidos visualmente
  clientes/fornecedores, propostas, ordens de serviço e contas a pagar, com criação e login aprovados;
  os 42 testes automatizados e `git diff --check` passaram integralmente.

### 15/08/2026 — formulários em painel lateral e papel padrão por documento

- os 46 formulários especializados passaram a abrir como um painel lateral preso às bordas superior,
  direita e inferior, começando exatamente após o menu de 258 px no desktop;
- o fundo modal foi suavizado: o menu continua visível e reconhecível sob leve ofuscamento, enquanto
  o formulário ocupa integralmente a área operacional; no mobile, o painel usa toda a tela;
- a abertura e o fechamento usam movimento horizontal a partir da direita, preservando a regra de
  `prefers-reduced-motion`;
- cadastro de usuário, dados da empresa, nova empresa e redefinição de senha também adotam o painel;
  confirmações, notificações, detalhes de edital e visualizadores permanecem centralizados;
- no cadastro unificado, CPF define Pessoa física e Cliente (C) como padrão; CNPJ define Pessoa
  jurídica e Fornecedor (F) como padrão. O usuário ainda pode alterar o papel para ambos depois;
- a mesma derivação foi implementada no servidor quando `tipo_cadastro` não for enviado, impedindo
  divergência entre interface e banco;
- cache PWA atualizado para `sivs-v2.2.0-ux-refinement-16-drawers`; 44 testes automatizados,
  `git diff --check`, auditoria de quatro perfis visuais, criação/login e os dois padrões de parceiro
  em navegador real foram aprovados.

### 16/08/2026 — campos contextuais de cliente e fornecedor

- o cadastro unificado agora adapta rótulos e campos ao documento e ao papel comercial selecionado;
- CPF usa “Nome completo”, oculta Nome fantasia e apresenta somente política comercial do cliente:
  vendedor responsável, tabela de preços e aprovação para faturamento;
- CNPJ usa Razão social e Nome fantasia e, como fornecedor padrão, apresenta avaliação, categoria e
  aprovação para compras, ocultando os campos exclusivos de cliente;
- parceiros do tipo A exibem os dois conjuntos, permitindo operar o mesmo registro em vendas e compras;
- Tipo de pessoa é derivado do documento e Código do parceiro ficou somente leitura, com geração
  sequencial pelo servidor ao salvar;
- a auditoria em navegador passou a verificar rótulos e visibilidade dos conjuntos para CPF e CNPJ;
  cache PWA atualizado para `sivs-v2.2.0-ux-refinement-17-party-context` e 44 testes passaram.

### 16/08/2026 — identidade visual com logotipo SECCOL

- a imagem fornecida pela direção foi restaurada em alta resolução, com fundo transparente e sem a
  linha de texto inferior, preservando somente o símbolo e o nome `Seccol`;
- foram criados dois ativos: logotipo completo para a tela de entrada e símbolo quadrado para menu,
  favicon e instalação PWA, ambos com bordas limpas e transparência validada;
- o antigo bloco com a letra `S` foi substituído pela marca, mantendo texto alternativo na entrada e
  evitando leitura duplicada pelo leitor de tela no menu, que já possui o nome do sistema ao lado;
- a paleta de detalhes passou a usar laranja SECCOL mais vivo em estados ativos, foco e destaques;
  botões principais preservam uma base mais escura para manter legibilidade do texto branco;
- a aplicação foi conferida em Chrome headless a 1440 × 1000 e o resultado visual foi registrado em
  `.artifacts/brand-identity.png`; cache PWA atualizado para `sivs-v2.2.0-ux-refinement-19-brand`;
  os 45 testes automatizados, validação de transparência/manifesto e `git diff --check` passaram.

### 16/08/2026 — CPF/CNPJ como chave única de parceiro

- CPF de cliente e CNPJ de fornecedor passaram a ser normalizados sem pontuação antes da gravação;
- a combinação empresa ativa + documento possui índice único no SQLite para parceiros ativos, cobrindo
  clientes, fornecedores e registros do tipo A sem permitir duplicação entre as classificações;
- criação e edição consultam a chave no servidor e retornam conflito 409 com o cadastro existente,
  sem depender de validação no navegador;
- registros excluídos não bloqueiam a chave, permitindo recuperação operacional sem manter uma
  restrição permanente sobre cadastros que saíram da base ativa;
- o formulário identifica o campo como “CPF do cliente” ou “CNPJ do fornecedor” e informa que ele
  será usado como chave única;
- cache atualizado para `sivs-v2.2.0-ux-refinement-18-party-key`; 45 testes, incluindo
  repetição com e sem pontuação e tentativa de duplicação por edição, passaram integralmente.

### 16/08/2026 — consulta cadastral rápida de parceiros

- criado `GET /api/partner-lookup`, autenticado e limitado à permissão de escrita de Clientes e
  fornecedores; a interface não acessa diretamente fornecedores externos;
- CNPJ válido consulta CNPJá Comercial somente quando `CNPJA_API_KEY` estiver configurada no
  ambiente, preenchendo razão social, fantasia, contato e endereço sugeridos, sempre editáveis;
- CEP consulta exclusivamente o ViaCEP, sem token ou contrato adicional, preenchendo o endereço
  sugerido sem interromper o cadastro quando a fonte estiver indisponível;
- respostas de CNPJ e CEP usam cache somente em memória por 15 minutos e auditoria sem registrar o
  documento consultado; não há persistência de credenciais nem novo compartilhamento entre empresas;
- adicionados testes direcionados para fonte CNPJ configurada, ViaCEP e cache;
  a execução local foi concluída posteriormente pelo ambiente descartável de auditoria.
- CEP passou a usar máscara `00000-000`, teclado numérico e preenchimento automático após os oito
  dígitos; cache PWA atualizado para `sivs-v2.2.0-partner-cep-24` para evitar JavaScript antigo.

### 16/08/2026 — experiência mobile e instalação como aplicativo

- o sistema passou por auditoria real em Chrome com emulação móvel de 390 × 844 px, toque habilitado
  e percurso autenticado pelas 53 telas; nenhuma tela ou formulário apresentou estouro horizontal;
- topbar, títulos, filtros, ações, tabelas, cards e áreas seguras foram ajustados para priorizar
  leitura e alvos de toque no celular; as ações de telas com muitos comandos usam grade de duas
  colunas e tabelas largas mantêm rolagem interna contida;
- os formulários continuam entrando pela direita, mas no celular terminam alinhados às quatro bordas,
  usam uma coluna, rolagem interna e ações fixas no rodapé; a animação respeita
  `prefers-reduced-motion`;
- Concorrentes recebeu contraste específico no hero mobile, preservando legibilidade de descrição,
  botão principal e situação;
- a opção **Baixar aplicativo** fica na tela de entrada e no rodapé do menu lateral; navegadores com
  `beforeinstallprompt` recebem instalação nativa e iPhone/iPad recebem instruções para adicionar à
  Tela de Início pelo Safari;
- o manifesto PWA agora declara identidade, modo `standalone`, escopo, cores, atalhos e ícones oficiais
  de 192 e 512 px derivados da marca SECCOL; o servidor evita cache persistente do manifesto;
- o auditor passou a validar instalação, largura do documento, largura interna dos formulários e
  alinhamento final das bordas; relatório em `.artifacts/interaction-audit.json` e capturas mobile em
  `.artifacts/mobile-*.png`;
- cache PWA atualizado para `sivs-v2.2.0-ux-refinement-22-mobile`; 48 testes automatizados, auditoria
  móvel das 53 telas e login de usuário passaram integralmente.

### 16/08/2026 — atualização automática e estado do sistema

- o rodapé do menu agora informa volume persistente, base de trabalho no OneDrive e o estado das
  atualizações automáticas;
- a PWA verifica uma nova versão ao abrir, ao retornar à aba e a cada quinze minutos; quando o novo
  service worker assume o controle, o usuário recebe aviso e a página é recarregada automaticamente;
- rodapé reduzido ao indicador, estado online e OneDrive; detalhes de atualização aparecem apenas
  durante uma atualização ou falha. Cache PWA atualizado para `sivs-v2.2.0-online-status-27`.
- a identificação permanente foi corrigida para mostrar dinamicamente o host real de acesso (por
  exemplo, o domínio Dokploy), pois OneDrive é apenas o diretório local de desenvolvimento; cache
  atualizado para `sivs-v2.2.0-server-address-30`.
- o painel executivo usa saudação contextual pelo horário local do navegador: Bom dia (05h–11h),
  Boa tarde (12h–17h) ou Boa noite (18h–04h); cache atualizado para
  `sivs-v2.2.0-time-greeting-33`.

### 16/08/2026 — máscaras de CPF e CNPJ

- o documento do cadastro unificado recebe máscara progressiva durante digitação e colagem:
  `000.000.000-00` para CPF e `00.000.000/0000-00` para CNPJ;
- o campo usa teclado numérico no celular, limita o tamanho visual e preserva a posição do cursor;
- registros existentes e a coluna Documento da listagem também são apresentados com pontuação;
- antes do envio, a interface remove a máscara e o servidor mantém sua normalização, preservando a
  chave única multiempresa e a comparação de duplicidade somente por dígitos;
- cache PWA atualizado para `sivs-v2.2.0-ux-refinement-23-party-mask`; digitação real de CPF/CNPJ em
  navegador e os 48 testes automatizados passaram.

### 16/08/2026 — data local no estado do sistema

- o rodapé do menu mostra, abaixo de **Sistema online / OneDrive**, a data completa do dispositivo
  com dia da semana em português, no formato `Domingo, 16 de agosto de 2026`;
- o elemento usa semântica `<time>` com data ISO e é atualizado automaticamente na primeira
  renderização e logo após a virada de cada dia, sem recarregar a página;
- comportamento mantido em `static/js/ui/system-date.js`, apresentação em `theme/components.css` e
  cache PWA atualizado para `sivs-v2.2.0-system-date-28`.

### 16/08/2026 — compartilhamento relacional de cadastros mestres

- campos operacionais de cliente, fornecedor, parceiro, equipamento, O.S., solicitação, produto,
  colaborador, certificado, norma e veículo deixaram de depender de texto livre e passaram a oferecer
  seletores de registros autorizados da empresa ativa;
- cada seleção preserva o nome legível no payload, grava também `<campo>_id` e materializa uma chave
  estrangeira em `record_relationships`, mantendo compatibilidade com relatórios e dados antigos;
- o servidor ignora nomes enviados pelo navegador, resolve o título pelo ID, verifica empresa ativa,
  módulo permitido, exclusão e papel C/F/A antes de aceitar o vínculo;
- a leitura hidrata o nome diretamente do cadastro mestre, portanto alterações futuras no nome do
  cliente ou fornecedor aparecem nos registros vinculados sem duplicação manual;
- a migração `221-relational-master-record-links` recupera automaticamente registros antigos quando
  o nome identifica exatamente um único cadastro mestre na mesma empresa; casos ambíguos permanecem
  intactos para revisão humana;
- CRM, solicitações de compra, financeiro e caixa também ganharam vínculo opcional com parceiro;
  propostas, contratos, O.S., compras, contas, equipamentos e demais fluxos usam os campos já
  obrigatórios como seletores;
- cache PWA atualizado para `sivs-v2.2.0-reference-links-29`; 53 testes automatizados, auditoria real
  de compartilhamento em proposta/O.S./contas a pagar e percurso mobile das 53 telas passaram.
- clientes e fornecedores receberam uma fonte dedicada em `GET /api/partners/options`, separada da
  lista genérica de relacionamentos, com contagem explícita de C, F e A e limite próprio de 5.000;
- os formulários mostram quantos cadastros ativos compatíveis estão disponíveis; itens na lixeira não
  são oferecidos para novos vínculos. Cache PWA atualizado para `sivs-v2.2.0-partner-options-32`.

### 16/08/2026 — exclusão definitiva da lixeira

- a tela de Configurações permite restaurar registros, apagar um item definitivamente ou esvaziar a
  lixeira da empresa ativa; as ações destrutivas exigem digitar `EXCLUIR` ou `ESVAZIAR`;
- somente administradores podem fazer a exclusão definitiva, com nova validação no servidor; gestores
  com acesso à lixeira continuam limitados à restauração conforme a permissão do módulo;
- o servidor apaga versões históricas antes do registro principal, preserva itens ainda referenciados
  por cadastros ativos ou resultados de licitação e processa lotes grandes sem ultrapassar o limite de
  variáveis do SQLite;
- a operação é transacional, isolada pela empresa ativa e registrada na auditoria apenas com IDs e
  contagens, sem incluir conteúdo sensível; testes cobrem confirmação, bloqueio por vínculo, permissão,
  cascatas, auditoria e isolamento multiempresa;
- a auditoria em Chrome móvel percorreu as 53 telas e validou os dois diálogos da lixeira; os 55 testes
  automatizados passaram integralmente;
- cache PWA atualizado para `sivs-v2.2.0-trash-purge-34`.

### 17/08/2026 — Centro de Controle operacional e de segurança

- criada a área administrativa **Centro de Controle**, isolada pela empresa ativa e disponível somente
  para administradores, com pessoas online, sessões válidas, autoria e horário das últimas alterações;
- adicionada a rota amigável `/controle`, que abre diretamente a tela administrativa e preserva o
  acesso anterior por `?screen=control_center`;
- pessoas passaram a aparecer uma única vez no monitor de acessos; sessões simultâneas do mesmo
  usuário ficam agrupadas por dispositivo e origem, evitando a impressão de usuários duplicados;
- erros podem ser filtrados por situação ou severidade e a auditoria pode ser pesquisada por pessoa,
  ação ou registro, sempre sobre os dados reais retornados pela empresa ativa;
- sessões passaram a registrar identificador público aleatório, origem, navegador e última atividade,
  sem expor o hash do token; ociosidade de uma hora é encerrada no servidor e sessões remotas podem ser
  terminadas por administrador com evento de auditoria;
- criada `system_events`, separada da trilha de negócio, para erros de servidor, alertas de segurança e
  exceções JavaScript; senhas, cookies, tokens, documentos e conteúdo de formulários ficam excluídos;
- adicionadas métricas em memória de volume de requisições, respostas 4xx/5xx, média, p95 e rotas mais
  lentas, além de saúde do SQLite/WAL, disco, volume persistente, agendador, jobs, backup e integrações;
- eventos técnicos resolvidos usam retenção configurável por `SIVS_TELEMETRY_RETENTION_DAYS`, padrão de
  180 dias; eventos abertos e a trilha de negócio não são eliminados por essa rotina;
- o desenho seguiu OWASP Logging e Session Management, NIST SP 800-92 e os sinais de observabilidade do
  OpenTelemetry, mantendo auditoria de negócio, eventos técnicos e métricas com finalidades distintas;
- criada `static/js/modules/control-center.js` e `theme/control-center.css`; a seção reutiliza o motion
  existente em 620 ms, sem dependência nova, e respeita `prefers-reduced-motion`;
- cache PWA atualizado para `sivs-v2.2.0-control-center-38`; testes específicos cobrem autorização,
  sessões simultâneas, erro de navegador, resolução de evento e encerramento remoto;
- auditoria Chrome mobile percorreu 54 telas sem erro JavaScript e a amostra posterior de nove telas
  confirmou o Centro de Controle em 390 px sem overflow ou perda de contraste;
- corrigida uma corrida no auditor responsivo, que podia iniciar antes de o menu terminar de renderizar
  e produzir relatório vazio; a execução corrigida percorreu 216 combinações (54 telas em desktop,
  tablet, mobile 390 px e mobile 360 px), com zero overflow e zero falha de interação.

### 17/08/2026 — fundação do ERP próprio, hierarquia e ledger de estoque

- consolidada a diretriz de ERP próprio da holding: não existem referências, campos, tokens ou
  dependências conceituais de Bling, Tiny ou Omie; o SQLite do SIVS permanece fonte operacional;
- o mapa da base confirmou Python HTTP nativo + SQLite sem ORM, autenticação por sessão/CSRF, RBAC por
  vínculo empresarial, `records` como cadastro mestre incremental e frontend HTML/CSS/JS sem build;
- produtos, serviços, clientes e fornecedores existentes foram preservados como cadastros canônicos,
  evitando uma aplicação paralela ou duplicação de dados antes da próxima extração de domínio;
- criada a migração `223-erp-multicompany-inventory-fiscal-foundation`, com a hierarquia explícita
  `holdings -> companies -> branches`; empresas antigas e novas recebem unidade matriz e depósito
  principal por migração idempotente, e a tela de configurações passou a exibir holding e unidades;
- criado domínio próprio de depósitos, saldos, reservas e movimentos nas tabelas `warehouses`,
  `inventory_balances`, `inventory_reservations` e `inventory_movements`, sempre com `company_id` e
  travas de banco contra vínculos entre empresas, unidades, depósitos e produtos incompatíveis;
- quantidades são armazenadas como inteiros em micros, com até seis casas decimais; cada operação usa
  `BEGIN IMMEDIATE`, atualiza saldo e histórico na mesma transação e impede saldo físico negativo,
  reserva acima do físico ou saída acima do disponível, inclusive sob concorrência;
- o ledger cobre `PURCHASE_IN`, `SALE_OUT`, `SERVICE_ORDER_OUT`, `RESERVE`, `RELEASE_RESERVATION`,
  `TRANSFER_IN`, `TRANSFER_OUT`, `RETURN_IN`, `RETURN_OUT`, `ADJUSTMENT_IN` e `ADJUSTMENT_OUT`;
  transferências geram o par saída/entrada atômico e reservas podem ser liberadas ou consumidas;
- cada alteração exige tipo e identificador de origem, preserva produto, lote, depósito, responsável,
  referência e justificativa; movimentos são imutáveis por triggers e também geram evento na auditoria;
- a rota genérica de registros não aceita mais criação/edição de estoque; registros antigos são
  preservados para revisão, mas não compõem o novo saldo porque não possuem semântica suficiente para
  migração automática segura;
- a tela **Estoque e lotes** passou a usar `static/js/modules/inventory.js` e
  `theme/inventory.css`, exibindo físico, reservado, disponível, depósitos, reservas e histórico, com
  formulários acessíveis, responsivos, compatíveis com teclado e movimento reduzido;
- o módulo fiscal deixou de apresentar “Manager” ou fila para conector externo; ações SEFAZ não
  implementadas retornam erro explícito e somente o registro local continua disponível;
- preparada, sem emissão nem alíquotas presumidas, a fundação fiscal parametrizável com operações,
  perfis da empresa/produto, regras tributárias, versões de schema, documentos/itens, certificados e
  XML; a futura NF-e continua condicionada aos manuais e schemas oficiais vigentes e a testes
  determinísticos, sem LLM como autoridade tributária;
- testes direcionados cobrem migração idempotente, isolamento entre CNPJs, saldo físico/reservado,
  reserva/liberação, transferência pareada, imutabilidade, auditoria, bloqueio do estoque genérico,
  concorrência de saídas e recusa de simulação SEFAZ;
- a validação final aprovou os 61 testes automatizados, compilação Python, verificação sintática de
  todos os módulos JavaScript, integridade da base migrada e o dry-run de imagens sem alterações;
- a auditoria real em Chrome percorreu a amostra mobile de dez telas sem erro ou overflow, incluindo
  o novo estoque e seu formulário de movimentação; o auditor responsivo rápido também concluiu um
  viewport e oito interações sem falhas;
- próximo passo recomendado: estruturar itens de orçamento/pedido/OS e conectar suas transições às
  reservas e movimentos do ledger; depois, ampliar exportação empresarial e parametrização fiscal.

### 18/08/2026 — fluxos ERP estruturados, permissões e auditoria integral das telas

- a migração `224-commercial-service-purchase-document-items` criou `document_items` com isolamento por
  empresa, vínculo validado ao catálogo, quantidade em micros, valores em centavos, desconto, total,
  depósito, lote, revisão otimista e triggers contra referências entre CNPJs;
- propostas, vendas, solicitações e pedidos de compra e ordens de serviço compartilham agora a mesma
  composição estruturada de produtos e serviços; o valor do documento é recalculado no servidor e itens
  alterados invalidam aprovações pendentes da revisão anterior;
- pedidos de venda e O.S. reservam todos os produtos atomicamente; a baixa converte a reserva em
  `SALE_OUT` ou `SERVICE_ORDER_OUT`, reduz físico e reservado na mesma transação e torna a linha
  movimentada imutável; conclusão ou cancelamento é bloqueado enquanto existir reserva ativa;
- pedidos de compra emitidos recebem produtos por `PURCHASE_IN`, recusam recebimento repetido, impedem
  alteração da linha já recebida e não podem ser marcados como recebidos antes da entrada completa;
- reservas manuais com data vencida são liberadas pelo agendador, gerando `RELEASE_RESERVATION`, motivo
  explícito e auditoria sistêmica sem alterar o saldo físico;
- máquinas de estado determinísticas foram aplicadas a propostas, solicitações/pedidos de compra,
  vendas e O.S.; novos registros começam obrigatoriamente no estado inicial e saltos inválidos são
  recusados também no servidor;
- documentos operacionais usam cliente/fornecedor por ID validado; clientes bloqueados ou não aprovados
  para faturamento e fornecedores sem aprovação de compras não podem alimentar os respectivos fluxos;
- códigos e números operacionais relevantes passaram a ser únicos por empresa para produtos, serviços,
  propostas, pedidos, O.S., certificados, laudos, estudos e documentos da qualidade;
- a administração de usuários ganhou matriz granular por módulo para consultar, editar e exportar, mais
  capacidades separadas de auditoria, aprovações e lixeira; escrita/exportação sempre exigem leitura,
  o backend aplica a matriz e toda alteração é auditada;
- a decisão de aprovação é exposta somente ao responsável designado ou gestor/administrador autorizado;
  o solicitante nunca recebe os botões de decisão e continua bloqueado pelo servidor;
- listas passaram de consultas auxiliares por registro para hidratação em lote, mantendo relações,
  assuntos, anexos e aprovações em número limitado de consultas; buscas interrompem requisições antigas;
- a importação XML passou a exigir CNPJ na empresa ativa e a rejeitar NF-e cujo destinatário não seja o
  CNPJ atual; continua sendo importação rastreável, não validação fiscal nem autorização SEFAZ;
- a emissão de documento técnico revalida transacionalmente revisão, aprovação e base normativa depois
  da geração do PDF e antes de persistir o arquivo, abortando mudanças concorrentes;
- controles de toque da busca, fontes e referências receberam mínimo de 44 px; os novos componentes de
  itens e permissões possuem layout próprio para 360–700 px e respeitam `prefers-reduced-motion`;
- o auditor funcional percorreu as 54 telas no desktop e no celular, abriu 43 formulários principais e
  não encontrou erro JavaScript ou overflow; o auditor responsivo cobriu 216 combinações de tela em
  desktop, tablet, 390 px e 360 px, além de diálogos, navegação e comandos;
- a validação final de 18/08/2026 aprovou 71 testes automatizados; compilação Python, verificação
  sintática de todos os JavaScript, `git diff --check`, migration 224 em banco novo e
  `PRAGMA integrity_check = ok` também passaram. O frontend é nativo e não possui etapa de build;
- a varredura responsiva final percorreu 216 combinações (54 telas em desktop, tablet, 390 px e
  360 px) e 29 fluxos interativos com zero overflow e zero falha; o diálogo de permissões recebeu
  enquadramento integral e animação sem deslocamento no celular. A auditoria comportamental repetida
  percorreu as 54 telas em desktop e mobile, com login válido, zero erro e quatro verificações da
  experiência de instalação aprovadas;
- risco conhecido: o JSON empresarial `SIVS-3` continua voltado aos cadastros legados e ainda não
  transporta com fidelidade o ledger, `document_items` e toda a fundação fiscal. Para continuidade ou
  restauração use exclusivamente o `SIVS-BACKUP-2`, que copia o SQLite integral; criar um formato
  empresarial versionado com remapeamento dessas chaves é a próxima evolução de portabilidade;
- próximos domínios: recebimento parcial de compra, geração automática e desacoplada de contas a
  pagar/receber, parcelas/pagamentos/contas/categorias/centros de custo estruturados, atribuição de O.S.
  por usuário e motor fiscal determinístico. NF-e permanece fora desta etapa.

### 18/08/2026 — palavras-chave por chips, planilha e precisão mensurável de editais

- substituído o textarea de palavras-chave por editor acessível em chips laranja SECCOL, com inclusão
  por `Enter`, vírgula, ponto e vírgula, colagem de células, remoção individual e limite visível de 80;
- criada importação auditada de planilhas CSV e XLSX, com limite de 2 MB, leitura máxima de 5.000
  linhas, proteção contra expansão excessiva de XLSX, reconhecimento das colunas palavra-chave,
  categoria e ativa, deduplicação sem acentos e rejeição de linhas inativas;
- o modelo CSV pode ser baixado diretamente e aberto no Excel ou LibreOffice; a categoria importada
  acompanha o termo na interface e a pesquisa recebe somente a lista mínima necessária;
- adicionada avaliação humana de aderência por resultado; a tela calcula precisão observada apenas
  sobre editais efetivamente marcados como aderentes ou não aderentes e informa quando ainda não há
  amostra, sem apresentar o percentual de aderência estimado como taxa comprovada de acerto;
- conversões em licitação passam a registrar evidência positiva de aderência; feedback, responsável e
  horário permanecem isolados pela empresa e auditados no servidor;
- a rotação de até oito consultas do índice textual agora avança por lista exata de palavras-chave,
  evitando que pesquisas diferentes consumam o cursor umas das outras; cada execução informa termos
  consultados, total e percentual de cobertura, sem fingir varredura completa quando houve lote parcial;
- a busca, a planilha e a medição são determinísticas e não consomem tokens de IA; a leitura generativa
  dos documentos continua exclusivamente manual na ação **Ler documentos com IA**;
- confirmado em 18/08/2026 que o índice textual do portal ainda responde com resultados e links PNCP,
  mas ele continua fora do contrato público de consultas; a API documentada do PNCP e a API oficial de
  Dados Abertos do Compras.gov permanecem referências/contingência e falhas parciais seguem explícitas;
- adicionada dependência `openpyxl` somente no servidor para XLSX, além do módulo
  `static/js/modules/tender-keywords.js` e da camada `theme/tenders.css`; cache PWA atualizado para
  `sivs-v2.2.0-tender-quality-41`;
- testes direcionados de CSV, XLSX, deduplicação, API e precisão passaram; contratos de frontend
  passaram, e auditoria Chrome mobile validou 10 telas, 77 chips iniciais, inclusão por Enter,
  importação real de CSV, 79 chips finais, zero overflow e zero erro JavaScript;
- risco de qualidade: precisão pode ser calculada após triagem humana, mas recall (editais relevantes
  que nenhuma fonte recuperou) ainda não é mensurável; não declarar cobertura total nacional enquanto
  o índice textual não possuir contrato público estável e conjunto de referência revisado.
- risco de suíte não relacionado a editais: dois testes preexistentes de decisão de aprovação retornam
  403 onde esperavam 409/200; os 72 demais testes passaram e a regressão de permissões deve ser tratada
  separadamente antes de considerar a suíte integral verde.

### 18/08/2026 — cadastro funcional por pessoa, controladoria e estoque valorizado

- resolvido o risco de aprovação registrado na entrada anterior: gestor/administrador legado e operador
  com função individual de decisão voltaram a atender seus contratos, e a suíte integral ficou verde;
- o cadastro de funcionário passou a ocorrer em duas etapas atômicas: identidade, credencial e
  perfil-base primeiro; empresa, módulos, operações e capacidades transversais depois. Nenhum usuário
  parcial é persistido se o administrador cancelar antes de **Salvar permissões**;
- a matriz de acesso está organizada em oito categorias, permite pesquisar módulo ou função e aplicar
  **Só consulta**, **Acesso completo** ou **Sem acesso** por categoria, além de consultar, editar e
  exportar por módulo e liberar cada função operacional individualmente. O perfil-base é um modelo
  restaurável, não uma autorização que ignora as escolhas finais;
- o backend passou a calcular e validar `effectiveActions` por empresa. Operações como criar, excluir,
  transicionar, anexar, solicitar/decidir aprovação, importar XML, faturar, liquidar, reservar,
  transferir, ajustar e movimentar estoque exigem a função correspondente no servidor, sem confiar em
  botões ocultos no frontend;
- visualização monetária é independente da consulta operacional: valores comerciais, financeiros,
  fiscais, de licitações e de estoque são omitidos ou substituídos por estado restrito quando a pessoa
  não possui `view_values`. Funções que dependem de valor não podem ser concedidas sem essa permissão;
- clientes e fornecedores continuam domínios físicos separados para autorização; o cadastro unificado
  é somente uma composição da experiência e não amplia acesso. Um funcionário pode criar apenas
  cliente, apenas fornecedor ou ambos, conforme as permissões efetivas;
- aprovações agora aceitam operador especificamente autorizado a decidir, sem obrigá-lo a receber
  edição ampla do módulo. O servidor continua impedindo decisão pelo próprio solicitante e revalida
  empresa, revisão, responsável e capacidade;
- a migração `226-functional-access-costed-inventory-controllership` adicionou custo unitário, variação
  de valor e saldo valorizado ao ledger. Entradas calculam custo médio determinístico; transferências
  levam o valor exato; vendas e O.S. baixam custo médio proporcional; reservas não alteram valor físico;
- a tela **Estoque e lotes** exibe, quando autorizado, valor físico, reservado, disponível e custo médio,
  exige custo explícito em entrada manual e respeita permissões próprias para depósito, movimentação,
  ajuste, transferência, reserva, liberação e baixa;
- criada a área **Controladoria**, isolada pela empresa ativa, com faturamento, pedidos em aberto, fluxo
  de caixa realizado, contas a receber/pagar, vencidos, estoque valorizado, custo das saídas, margem de
  contribuição bruta e série mensal de seis meses. Cada bloco só usa fontes que o usuário pode consultar
  e visualizar; não há números fictícios ou dados de outro CNPJ;
- a controladoria é gerencial e ainda não constitui contabilidade ou DRE. O fluxo atual representa
  movimentos realizados; competência, conciliação, plano de contas, parcelas e pagamentos estruturados
  continuam como evolução financeira necessária;
- saldos positivos migrados sem histórico de custo permanecem explicitamente **sem valorização**, em vez
  de receber custo inventado. A correção futura deve ser feita por entrada/ajuste documentado e auditado;
- a interface de permissões recebeu layout integral para 360–700 px, alvos de toque, navegação por
  teclado, pesquisa, resumo das escolhas, superfícies opacas e suporte a `prefers-reduced-motion`;
- a auditoria responsiva integral percorreu 220 combinações (55 telas em desktop, tablet, 390 px e
  360 px) e 29 interações sem overflow ou falha. A repetição móvel após o polimento do diálogo passou em
  duas telas e nove interações; o cadastro descartável confirmou oito categorias, 407 combinações de
  função renderizadas e login do novo funcionário;
- a validação final aprovou 80 testes automatizados, compilação Python, sintaxe de 24 JavaScript,
  `git diff --check`, migration 226 em SQLite novo e `PRAGMA integrity_check = ok`. O frontend continua
  nativo e não possui etapa de build; cache PWA atualizado para `sivs-v2.2.0-functional-control-43`;
- não foi implementada emissão de NF-e nesta etapa. A fundação fiscal permanece desacoplada e a emissão
  futura deverá usar documentação e schemas oficiais vigentes, certificado A1 e cálculos determinísticos.

### 18/08/2026 — homologação SEFAZ/GO, cofre A1 e pacote contábil

- a documentação foi novamente verificada no Portal Nacional da NF-e e na Secretaria da Economia de
  Goiás em 18/08/2026. A integração usa o contrato NF-e 4.00, o método oficial
  `NFeStatusServico4/nfeStatusServicoNF`, código de UF 52 e os endpoints publicados para homologação e
  produção; as URLs ficam versionadas por unidade e ambiente, com fonte e data de verificação;
- o Portal Nacional já lista pacotes de schema 010e e Notas Técnicas de 2025/2026 para RTC, IBS/CBS e
  CNPJ alfanumérico. Nenhum XSD foi copiado de memória nem alíquota foi embutida no código; a emissão
  permanece bloqueada enquanto o pacote oficial aplicável não for importado, versionado e testado;
- a migração `227-sefaz-readiness-a1-vault-accounting-export` adicionou configuração SEFAZ por empresa,
  unidade e ambiente, metadados de exportação contábil e dados fiscais estruturados da empresa/unidade:
  razão social, inscrições, UF, código IBGE e regime tributário;
- criada a tela de prontidão fiscal com dez verificações independentes: CNPJ, inscrição estadual, UF,
  município, regime, endpoint de homologação, chave do cofre, A1, schema e regras/perfil tributário. A
  tela nunca apresenta conexão de status como autorização para emitir;
- o certificado A1 em PFX/P12 é aberto uma única vez no servidor; a senha não é persistida, auditada ou
  devolvida. Chave privada, certificado e cadeia são convertidos para um pacote interno e cifrados com
  AES-256-GCM usando `SIVS_FISCAL_MASTER_KEY`, AAD por empresa/unidade/fingerprint e arquivos PEM
  temporários com menor privilégio somente durante a conexão mTLS;
- importação, substituição, uso e remoção do A1 possuem permissões funcionais próprias e auditoria sem
  material secreto. Perder a chave mestra torna o pacote indecifrável e exige nova importação do A1;
- implementada consulta real de disponibilidade da SEFAZ por SOAP 1.2/mTLS, com limite de resposta,
  TLS 1.2 mínimo, validação de domínio governamental HTTPS, parsing seguro do XML, código/motivo, versão
  do autorizador, tempo médio e evento técnico em falha. Certificado vencido ou com validade ilegível é
  recusado antes da abertura da conexão. A produção exige também a trava explícita
  `SIVS_ALLOW_SEFAZ_PRODUCTION=1`;
- a conexão externa não foi executada contra a SEFAZ porque o repositório não contém — e não deve conter
  — certificado real da empresa. O contrato de transporte e a resposta 107 foram testados de forma
  determinística; a homologação real deverá ser feita com o A1 e o credenciamento da SECCOL;
- o pacote `SIVS-ACCOUNTING-1` gera ZIP mensal, isolado pelo CNPJ ativo, com empresa/unidades, CSV geral,
  lançamentos financeiros, documentos fiscais/comerciais, itens estruturados, movimentos valorizados
  de estoque, XML disponíveis, instruções e manifesto de arquivos com SHA-256. Valores usam centavos e
  quantidades usam micros; geração, período, contagens e hash final ficam na auditoria;
- a seleção do pacote contábil considera registros criados, atualizados, vencidos, emitidos ou liquidados
  na competência e movimentos/XML ocorridos no intervalo. O arquivo apoia o escritório, mas não declara
  SPED, livro fiscal, conciliação ou escrituração concluídos;
- adicionadas funções independentes para configurar fiscal, gerenciar A1, consultar SEFAZ e exportar para
  a contabilidade. Exportação continua exigindo permissão de exportar o módulo e visualizar valores;
- a UI fiscal está em `static/js/modules/fiscal-integration.js` e
  `theme/fiscal-integration.css`, funciona em tela cheia no celular, usa ações de no mínimo 44 px,
  teclado e `prefers-reduced-motion`; cache PWA atualizado para
  `sivs-v2.2.0-fiscal-readiness-44`;
- validação final: 84 testes, migration 227 em banco novo, `PRAGMA integrity_check = ok`, compilação
  Python, sintaxe de 24 JavaScript e `git diff --check`. A auditoria responsiva percorreu 220 combinações
  (55 telas × desktop/tablet/390/360) e 33 interações, sem overflow ou falha; a auditoria comportamental
  percorreu as 55 telas, confirmou 411 combinações funcionais, novo login e zero erro JavaScript;
- próximos bloqueios para emissão: receber o A1 real de forma segura, confirmar CNPJ/IE/regime/código
  IBGE com o contador, credenciar os CNPJs na SEFAZ/GO, importar os schemas oficiais vigentes, cadastrar
  operações/perfis/regras e homologar matriz de cenários, rejeições, cancelamento e contingência. A
  futura adequação ao CNPJ alfanumérico deve seguir a NT oficial antes de sua vigência aplicável.

### 18/08/2026 — trava contra base zerada e snapshot anterior ao deploy

- a investigação de produção confirmou `SIVS_DB=/data/sivs.db`, `SIVS_REQUIRE_PERSISTENT_DB=1` e o
  volume nomeado `sivs-seccol-data` montado corretamente; o SQLite persistente estava íntegro e
  configurado, mas continha três usuários, sem outro volume ou contêiner remanescente com base distinta;
- a validação antiga garantia apenas que `/data` era um mount e ainda aceitaria um volume novo vazio;
  a inicialização agora falha fechada quando o arquivo estiver ausente, vazio, corrompido, sem schema
  essencial, sem administrador ou marcado como não configurado;
- bootstrap vazio exige `SIVS_ALLOW_EMPTY_DB_INITIALIZATION=1`, permitido somente na primeira
  instalação e removido imediatamente depois do administrador inicial; a variável não integra os
  builds nem a configuração permanente;
- antes de inicializar e migrar uma base persistente válida, o servidor cria snapshot SQLite
  consistente em `/data/prestart-backups/`, valida `PRAGMA quick_check`, aplica permissão `0600` e
  mantém sete cópias por padrão, configuráveis entre duas e trinta;
- snapshots no próprio volume cobrem regressão de aplicação/migração, não perda do host ou do volume;
  o Dokploy não possuía destino nem rotina de backup externo no momento da auditoria, portanto backup
  diário S3/compatível e teste de restauração permanecem ação operacional P0;
- adicionados testes para recusa de banco ausente/não configurado, bootstrap explícito e snapshot
  íntegro com preservação de usuário.

### 18/08/2026 — recuperação de senha e acesso emergencial

- o login do SIVS e o login do Dokploy são identidades independentes; redefinir a senha do painel de
  infraestrutura não modifica `users.password_hash` no SQLite do SIVS;
- a migração 228 adiciona tokens de recuperação de uso único, armazenados apenas por SHA-256, com
  validade de 30 minutos e invalidação dos tokens anteriores da mesma conta;
- a tela pública ganhou **Esqueci minha senha**. A solicitação sempre responde com texto genérico para
  não revelar contas cadastradas, possui limitação por IP e depende de SMTP configurado somente por
  variáveis de ambiente;
- a redefinição valida o token dentro de transação imediata, atualiza o hash PBKDF2, reativa a conta,
  encerra todas as sessões do usuário, inutiliza os tokens remanescentes e registra auditoria;
- `tools/reset_sivs_password.py` oferece recuperação administrativa offline, em simulação por padrão.
  Com `--apply`, cria snapshot íntegro, gera senha aleatória, altera apenas o e-mail informado, revoga
  sessões e registra a intervenção; a senha provisória aparece uma única vez no terminal;
- o fluxo de e-mail só fica operacional após configurar `SIVS_PUBLIC_URL`, remetente e credenciais SMTP
  no Dokploy. Falha de entrega não expõe token nem existência da conta e gera evento técnico interno.
- validação concluída com 89 testes automatizados, compilação Python, sintaxe JavaScript, contrato do
  frontend, `git diff --check` e ensaio integral do utilitário (snapshot, hash e auditoria); cache PWA
  atualizado para `sivs-v2.2.0-password-recovery-45`.

### 18/08/2026 — visualização e leitura de documentos de editais

- o PNCP pode responder PDFs como `application/octet-stream`, fazendo o navegador baixar um edital
  mesmo quando a resposta usa `Content-Disposition: inline`; o servidor agora reconhece PDF, PNG,
  JPEG e GIF pela assinatura dos bytes e informa explicitamente se o formato é visualizável;
- o visualizador interno passou a buscar o documento autenticado como `Blob`, abrir uma URL local e
  apresentar estado de carregamento ou incompatibilidade. Isso impede que a ação **Ver no sistema**
  seja convertida silenciosamente em download pelo navegador;
- formatos sem visualização segura permanecem disponíveis em **Baixar** e não são renderizados como
  HTML ativo na origem do SIVS;
- os emojis de avaliação positiva/negativa foram substituídos por setas `↑` e `↓`, com `aria-label`,
  estado `aria-pressed` e destaque visual para a escolha registrada;
- a produção retornou HTTP 502 em duas tentativas de leitura por IA porque não possuía
  `OPENROUTER_API_KEY`. Falhas de extração, configuração ou provedor agora são persistidas no dossiê e
  exibidas abaixo da ação, incluindo páginas extraídas e documentos pendentes, sem expor segredos;
- para concluir relatórios de IA em produção, configurar `OPENROUTER_API_KEY` e opcionalmente
  `OPENROUTER_TENDER_MODEL` nos segredos do Dokploy. O cache PWA foi atualizado para
  `sivs-v2.2.0-tender-viewer-46`.
- validação final aprovada com 91 testes automatizados, compilação Python, sintaxe dos JavaScript
  alterados e `git diff --check`.

### 18/08/2026 — modelo compacto para leitura de editais

- o modelo padrão de **Ler documentos com IA** passou de `openai/gpt-5.4-mini` para
  `openai/gpt-5-mini`, reduzindo o custo operacional sem adotar a linha Nano, cuja economia adicional
  traz risco maior de perda de fidelidade na extração jurídica estruturada;
- `OPENROUTER_TENDER_MODEL` continua podendo substituir o padrão no ambiente, e
  `OPENROUTER_API_KEY` permanece obrigatória e armazenada somente nos segredos do Dokploy;
- a mudança não altera o modelo do assistente geral nem envia chave para o repositório.
- para preservar o contrato funcional, toda saída passa por uma barreira de qualidade que exige as
  seções do dossiê, situação e justificativa de participação e ao menos uma citação quando houver texto
  extraído; saídas incompletas não são persistidas como relatório concluído;
- quando o Mini não passa nessa validação, o servidor tenta `openai/gpt-5.4-mini` como contingência,
  configurável ou desativável por `OPENROUTER_TENDER_FALLBACK_MODEL`. A equivalência semântica entre
  modelos ainda deve ser aferida com editais reais após a inclusão da chave.

### 18/08/2026 — refinamento de layout, orientação e segurança de interação

- a revisão preservou endpoints, IDs, permissões, isolamento multiempresa e contratos de cadastro;
  as mudanças são progressivas e usam os componentes e tokens existentes;
- estados genéricos de carregamento foram substituídos por feedback acessível com contexto da operação,
  skeleton discreto, `aria-live` e animação desativada em `prefers-reduced-motion`;
- o formulário de registro agora remove o erro visual conforme o campo é corrigido, anuncia falhas com
  `role="alert"`, bloqueia envio duplicado e informa **Criando registro** ou **Salvando alterações**
  enquanto aguarda a validação do servidor;
- no celular, as 80 palavras-chave de editais ficam resumidas em um controle expansível que mostra a
  quantidade selecionada; UF, período e **Pesquisar agora** permanecem na primeira dobra. Importação,
  remoção, colagem, planos salvos e o textarea de compatibilidade mantêm os mesmos contratos;
- a hero de editais foi compactada no celular e o painel executivo passou a usar atalhos em duas colunas
  quando houver largura, reduzindo espaço vazio sem ocultar prioridades;
- o auditor comportamental passou a aguardar o término real de `.loading-state`, abrir explicitamente o
  editor compacto antes de interagir e capturar também seu estado inicial recolhido;
- cache PWA atualizado para `sivs-v2.2.0-ux-guidance-47`. Validação final: 94 testes, sintaxe de todos os
  JavaScript, compilação Python e `git diff --check`; auditoria responsiva aprovou 220 combinações e 33
  interações sem overflow ou falha, e a amostra móvel percorreu dez telas com login aprovado e zero erro.
- o deploy dessa versão revelou que o Nixpacks gerava `ARG`/`ENV` para `OPENROUTER_API_KEY`; antes da
  inclusão da chave, produção foi padronizada em Dockerfile para manter segredos somente no runtime;
- o entrypoint do Dockerfile corrige a propriedade do volume `/data` criado anteriormente como root e
  reduz privilégios com `gosu` para UID 10001. A trava de volume, banco configurado e snapshot pre-start
  continua sendo executada pelo servidor depois dessa transição.

### 21/08/2026 — entrada assinada de leads do site no CRM

- criado `POST /api/integrations/website/leads`, fora da autenticação por sessão somente para permitir a integração servidor a servidor; o endpoint exige HMAC-SHA256, timestamp com janela de cinco minutos, JSON limitado, rate limit e empresa fixa por `SIVS_WEBSITE_LEADS_COMPANY_ID`;
- `SIVS_WEBSITE_LEADS_SECRET` deve possuir ao menos 32 caracteres e ser igual ao segredo server-side configurado na Vercel do `lp-seccol`; ele nunca é enviado ao navegador nem salvo no banco;
- eventos `lead.created` válidos criam registros do módulo `crm` em `Novo lead`, preservando contato, empresa informada, telefone, e-mail, localização, necessidade, contexto, origem, URL e UTMs, sem converter automaticamente a pessoa em cliente cadastrado;
- a tabela `website_lead_receipts`, migration 229, guarda somente identificador externo, hash do evento e vínculo opcional ao CRM para impedir duplicidade mesmo quando a entrega é repetida; o vínculo usa `ON DELETE SET NULL`, preservando a idempotência sem bloquear a exclusão definitiva de um lead na lixeira; a criação gera auditoria sistêmica e notificação interna;
- o CRM ganhou campos visíveis de contato e uma visualização rápida `Novos leads`, mantendo tabela, Kanban, permissões e validação no servidor;
- cache PWA atualizado para `sivs-v2.2.0-website-leads-48`; o teste focado confirmou criação única, repetição idempotente, notificação e rejeição de corpo adulterado;
- validação final da integração: compilação Python, teste focado do webhook, 25 contratos de frontend, sintaxe dos 24 JavaScript, auditoria responsiva de 220 telas e 33 interações e otimizador em `dry-run` aprovados; na suíte completa, 96 de 97 testes passaram, restando somente o caso anterior e sensível à data `test_internal_assistant_filters_context_and_audits_query`, cuja proposta fixa de 20/08/2026 já não pertence à semana corrente em 21/08/2026;
- pendência operacional: configurar as duas variáveis no Dokploy, configurar URL/segredo correspondentes na Vercel, publicar os dois repositórios e realizar um envio real de homologação antes de liberar o formulário em produção.

### 22/08/2026 — auditoria integral, legibilidade e ferramentas repetíveis

- concluída nova auditoria do escopo implementado, documentada em
  `sivs_2_2/AUDITORIA_COMPLETA_SIVS_2.2_2026-08-22.md`; o inventário confirmou 50 módulos, 55 telas,
  254 funções/métodos Python e aproximadamente 200 declarações funcionais no frontend principal;
- o teste do assistente deixou de depender da data fixa de 20/08/2026 e usa um prazo relativo ao dia
  corrente; a suíte integral passou em 22/08/2026 com 97 de 97 testes;
- o otimizador de imagens deixou de usar um símbolo incompatível com o console CP1252 do Windows e o
  `dry-run` obrigatório voltou a encerrar com sucesso;
- o auditor responsivo passou a usar perfil e portas exclusivos por execução, timeout em chamadas CDP,
  encerramento da árvore do servidor e limpeza tardia do runtime quando o Edge demora a liberar arquivos;
  a validação final percorreu 220 telas e 33 interações sem overflow ou falha e encerrou com código 0;
- a auditoria comportamental percorreu as 55 telas, abriu os principais cadastros, confirmou 411 funções
  de permissão, criação/login de funcionário e zero erro JavaScript acionável;
- corrigida a microtipografia crítica anulada pela compactação desktop: instruções de 7–9 px, rótulos,
  navegação do cadastro, tabelas e cartões centrais passaram a usar tokens de 11/12 px. O resultado mantém
  cores vivas SECCOL, superfícies limpas e densidade adequada ao ERP; cache atualizado para
  `sivs-v2.2.0-audit-legibility-49`;
- adicionada `defusedxml>=0.7,<1`, recomendada oficialmente pelo openpyxl para endurecer o parsing de
  planilhas XLSX não confiáveis contra ataques XML; os limites existentes de ZIP, 2 MB, 5.000 linhas e
  20 colunas foram preservados;
- riscos restantes: backup externo continua P0; webhook do site ainda exige homologação publicada;
  recebimento parcial, financeiro estruturado, portabilidade integral e NF-e continuam evoluções, não
  funções concluídas; integrações externas reais dependem das credenciais e autorizações correspondentes.

### 22/08/2026 — cofre e checklist documental para participação em licitações

- a pesquisa de fluxo foi baseada nos arts. 62 a 70 da Lei 14.133/2021 e na IN SEGES/ME 73/2022:
  habilitação abrange capacidade jurídica, técnica, fiscal/social/trabalhista e econômico-financeira;
  em regra, os documentos de habilitação são exigidos somente do vencedor depois do julgamento, mas
  acompanham a proposta inicial quando houver inversão de fases. SICAF ou outro registro cadastral pode
  substituir arquivos se o edital permitir, e proposta ajustada/documentos complementares são enviados
  após convocação no prazo fixado pelo agente de contratação;
- a migration 230 criou `company_tender_documents`, `tender_participation_profiles` e
  `tender_document_requirements`. Arquivos, metadados, validade, hash SHA-256, checklist e perfil ficam
  isolados por empresa, com FKs, triggers contra vínculo cruzado e auditoria de upload, alteração,
  download, confirmação e geração;
- Configurações ganhou o **Cofre de documentos da empresa**, com catálogo recorrente, emissor, emissão,
  validade e escopo (`ALL`, bens, serviços ou engenharia). Upload reutiliza a detecção de assinatura e o
  limite seguro de 10 MB; executáveis e tipos incompatíveis continuam recusados; não existe exclusão
  silenciosa, apenas arquivamento reversível;
- cada detalhe de edital agora recebe um checklist próprio. Nenhum item nasce marcado como obrigatório:
  o operador precisa ler o edital, marcar a exigência, indicar fase, escolher um arquivo compatível e
  registrar item/página. Declarações normalmente preenchidas no portal são identificadas sem inventar
  um PDF; a inversão de fases precisa ser declarada explicitamente;
- checklist confirmado é bloqueado quando falta referência, arquivo aplicável ou quando o arquivo está
  vencido/inativo. A geração de pacote também revalida empresa, tipo, escopo, validade e fase no servidor;
  o ZIP contém somente os arquivos marcados para a fase, além de `MANIFESTO.json` com edital, referências
  e hashes. Portanto o sistema não junta automaticamente todo o cofre à proposta;
- esta entrega prepara e governa os documentos, mas não transmite proposta, declarações ou lances a
  portais externos. Automação de protocolo depende de API/autorização específica de cada plataforma e
  deve preservar convocação, confirmação humana e limites do edital;
- UI comportamental em `static/js/modules/tender-documents.js`, tema em
  `static/theme/tender-documents.css`, animação de 620 ms apenas com opacidade/transform, layout móvel
  de uma coluna, alvos de 44 px e desligamento em `prefers-reduced-motion`; cache PWA atualizado para
  `sivs-v2.2.0-tender-documents-50`;
- validação final: 99 testes aprovados, incluindo migração, catálogo, upload, ausência de conteúdo binário
  nas listagens, bloqueio de checklist sem referência, declaração de portal, ZIP com hash e bloqueio após
  arquivamento; compilação Python, sintaxe JavaScript e `git diff --check` também aprovados. A auditoria
  responsiva percorreu 220 combinações em desktop, tablet, 390 px e 360 px e 33 interações, sem overflow
  nem falha de interação.

### 22/08/2026 — múltiplos anexos, exigências específicas e alertas de licitação

- a migration 231 acrescentou `tender_requirement_documents` e `notification_alerts`, preservando o
  campo legado de documento selecionado durante a transição. Triggers impedem que requisito, edital ou
  arquivo de empresas diferentes sejam vinculados, inclusive quando há vários documentos na exigência;
- cada exigência do edital aceita agora mais de um arquivo do cofre. Exigências particulares de anexos,
  modelos e declarações podem ser criadas no próprio checklist, com título, fase, referência e indicação
  explícita de preenchimento no portal; os arquivos usam o tipo controlado
  `other_edital_document`, sem permitir categorias arbitrárias no cofre;
- o pacote por fase inclui todos os documentos marcados e identifica a exigência específica no
  `MANIFESTO.json`. A geração continua bloqueada e revalidada no servidor se o checklist não estiver
  confirmado, se faltar referência/arquivo, ou se houver arquivo vencido, arquivado, incompatível ou de
  outra empresa;
- o agendador materializa alertas idempotentes de documentos a vencer em até 60 dias e prazos de edital
  em até 15 dias, mantendo somente atrasos recentes para evitar ruído histórico. As notificações seguem
  permissão de leitura de `editais` e levam à área correspondente; quando um arquivo usado vence, o
  checklist confirmado volta automaticamente a rascunho e a invalidação fica auditada por empresa;
- a cobertura do cofre não conta o recipiente genérico de documento específico como obrigação fixa. A
  migração também preserva corretamente declarações de portal salvas antes desta evolução;
- a interface permite seleção múltipla por teclado e toque, remoção de exigências específicas e motion
  discreto apenas em `opacity`/`transform`, desligado por `prefers-reduced-motion`; cache PWA atualizado
  para `sivs-v2.2.0-tender-documents-51`;
- validação final: 100 de 100 testes aprovados, compilação Python, sintaxe de todos os JavaScript,
  `git diff --check` e otimizador de imagens em `dry-run` aprovados. O auditor responsivo aguarda o fim do
  motion antes de medir alvos de toque, evitando falso negativo sob carga no Windows; a execução final
  aprovou 220 telas e 33 interações, sem overflow ou falha.

### 22/08/2026 — proposta comercial versionada e aprovação independente

- a migration 232 criou `tender_proposals`, `tender_proposal_versions`,
  `tender_proposal_version_items` e `tender_proposal_decisions`. Propostas, versões, itens e decisões
  ficam isolados por empresa; triggers rejeitam vínculo cruzado com edital ou catálogo, e versões,
  itens e decisões passadas são imutáveis;
- o detalhe do edital ganhou a composição comercial por item, com quantidade em micros e valores em
  centavos. Cada linha registra custo validado, piso unitário, preço proposto, referência publicada e
  item/página de origem; o servidor rejeita preço abaixo do piso e piso abaixo do custo. Custo, margem
  e preços exigem `view_values` e nunca são enviados no payload para perfis sem essa permissão;
- itens oficiais do PNCP são sugeridos primeiro. Na ausência deles, a leitura por IA pode sugerir
  `itens_comerciais`, sempre marcada como `AI_REVIEW_REQUIRED`; descrição, quantidade, unidade,
  referência, correspondência com o catálogo e todos os valores continuam exigindo conferência
  humana. A barreira de qualidade da IA passou a exigir essa seção estruturada, ainda que vazia;
- salvar cria uma versão nova e usa bloqueio otimista. Uma versão só segue para aprovação quando
  possui itens válidos, condições de entrega e pagamento e checklist documental confirmado. Quem criou
  ou enviou a versão não pode aprová-la; a decisão exige parecer, permissão funcional independente,
  notificação e auditoria. Reabrir uma proposta aprovada preserva integralmente a versão anterior;
- somente uma versão aprovada, com checklist ainda confirmado, pode gerar o pacote comercial. A
  exportação exige `triage_tenders` e `view_values` e entrega ZIP com `PROPOSTA-COMERCIAL.pdf`,
  `ITENS.csv` sem custos internos e `MANIFESTO.json` com versão, aprovação e hashes SHA-256. O pacote
  declara explicitamente que não comprova protocolo ou recebimento pelo órgão;
- a interface comportamental está em `static/js/modules/tender-proposal.js` e o tema em
  `static/theme/tender-proposal.css`. O layout usa uma coluna nas menores larguras, controles de no
  mínimo 44 px, navegação por teclado, motion discreto de 620 ms somente com opacidade/transform e
  remoção imediata da animação em `prefers-reduced-motion`; cache PWA atualizado para
  `sivs-v2.2.0-tender-proposal-52`;
- no cofre, tipos sujeitos a vencimento passaram a exigir validade no navegador e no servidor; arquivar
  avisa que checklists dependentes voltarão a rascunho. Alertas cuja validade/prazo deixou de corresponder
  ao documento ou edital são removidos, e consultar notificações não executa mais varredura com escrita;
- o detalhe pode ser recarregado dentro do diálogo sem `InvalidStateError`, e checklist/proposta permanecem
  acessíveis antes da primeira atualização oficial do PNCP. O auditor responsivo aceita
  `--viewport=<desktop|tablet|mobile|mobile-360>` para isolar o Edge quando o Windows acumula carga;
- esta entrega prepara, calcula, governa, aprova e empacota a proposta, mas não transmite ao portal e
  não oferece lance automático. Antes dessa etapa ainda são necessários adaptadores homologados por
  portal, regras por lote, impostos/frete/BDI, limites de alçada e margem, reserva de estoque/capacidade,
  assinatura quando exigida, registro de recibo e uma confirmação humana de envio. Formatos e campos
  específicos continuam sujeitos ao edital e à plataforma usada pela disputa;
- validação final: 102 de 102 testes aprovados, incluindo piso, checklist, segregação, permissão de
  exportação, sugestão oficial, imutabilidade, revisão e ZIP; compilação Python, sintaxe JavaScript,
  `git diff --check` e otimizador de imagens em `dry-run` aprovados. A auditoria responsiva percorreu
  220 telas e 39 interações em desktop, tablet, 390 px e 360 px, sem overflow ou falha.

### 22/08/2026 — viabilidade da proposta conectada ao ERP e à Licitação operacional

- a migration 233 acrescentou à fotografia imutável dos itens da proposta o módulo e código do
  catálogo, custo interno vigente e sua origem, disponibilidade, forma e plano de atendimento e a
  justificativa de exceção. O backend continua revalidando empresa, catálogo, custo, piso e preço;
  um custo digitado abaixo do custo médio real do estoque ou do custo interno de referência é rejeitado;
- o catálogo comercial deixou de tratar produto e serviço como se usassem o mesmo campo. Produtos usam
  `preco_venda` e custo médio ponderado do estoque; serviços usam o valor financeiro do cadastro como
  preço de referência e o novo `custo_referencia` como custo direto interno estimado. Produtos também
  expõem ao compositor o saldo físico menos reservas, sempre sob `view_values`;
- antes de solicitar aprovação, cada item precisa estar ligado a produto/serviço da empresa ou possuir
  justificativa explícita de exceção. Produto exige atendimento por estoque, compra, fabricação ou modo
  misto; estoque insuficiente bloqueia a opção de atendimento somente por saldo, e compra/fabricação
  exige plano. Serviço exige confirmação de capacidade. A UI mostra a origem do custo, disponibilidade
  e forma de atendimento sem substituir a conferência humana;
- a proposta não pode seguir para aprovação enquanto a oportunidade não tiver sido convertida no módulo
  `licitacoes`. Conversão, salvamento de nova versão, envio para aprovação, devolução, retirada,
  aprovação e reabertura sincronizam versão e situação comercial no payload do registro operacional,
  com versão anterior do registro e auditoria. Na aprovação, o valor aprovado também atualiza `amount`;
  a etapa operacional permanece intacta, pois aprovação interna não significa envio ao portal;
- não foi criado automaticamente um registro genérico em `propostas`: esse fluxo exige cliente
  cadastrado, enquanto o órgão público captado pode ainda não ser uma contraparte validada. A proposta
  especializada de licitação permanece canônica e se liga diretamente à Licitação operacional, evitando
  duplicidade sem dono ou cliente fictício;
- continuam pendentes para automação externa: impostos, frete e BDI configuráveis e validados pela
  contabilidade; alçadas por margem/valor; calendário real de capacidade técnica e equipamentos; reserva
  de estoque no marco operacional adequado; cadastro estruturado do órgão/contraparte; adaptadores
  homologados por portal, assinatura, protocolo/recibo e regras seguras de lance com teto e parada.
  O sistema ainda não envia proposta nem dá lance automaticamente;
- cache PWA atualizado para `sivs-v2.2.0-tender-feasibility-53`. Validação final: 102 de 102 testes,
  compilação Python, sintaxe de todos os JavaScript e `git diff --check` aprovados; auditoria
  comportamental aprovou 55 telas e login, e auditoria responsiva rápida aprovou 3 telas e 10 interações
  em 390 px, sem overflow ou falha de interação.

### 22/08/2026 — captação autônoma sem filtro de preço e limite real dos portais

- a política `tenderAutonomy`, isolada em `company_settings`, deixa explícitos três comportamentos:
  agente ativo, captação independentemente de o valor estimado existir e conversão automática de
  oportunidades tecnicamente compatíveis. O servidor ignora tentativas de habilitar
  `externalSubmission` ou `externalBidding` e mantém o conector em
  `NO_OFFICIAL_SUPPLIER_API` até existir integração oficial comprovável;
- toda pesquisa manual ou agendada passa pelo mesmo pipeline. Um resultado novo somente entra na
  Licitação operacional quando veio de correspondência estrita com o portfólio real da empresa; preço
  baixo, alto ou ausente não o exclui. A conversão registra origem do agente, vínculo com o resultado,
  ausência eventual de valor e estado `AGUARDANDO_CONECTOR_OFICIAL`, sem declarar proposta ou lance
  enviado;
- para empresas ativas sem nenhuma agenda diária/semanal, o próprio agendador cria uma única agenda
  diária com primeiro ciclo nos próximos cinco minutos, usando o vocabulário técnico padrão e uma identidade ativa com as permissões
  necessárias. A operação é idempotente, não duplica uma agenda já existente e desativa somente a
  agenda gerada pelo agente quando a política é pausada;
- antes da conversão, identificadores PNCP válidos são enriquecidos automaticamente pelas consultas
  públicas oficiais de detalhe, itens e arquivos. Valor sigiloso continua nulo e identificado como tal;
  indisponibilidade temporária do PNCP aparece como pendência do ciclo, mas não faz o sistema descartar
  uma oportunidade já confirmada pelo portfólio;
- o agente revalida, no momento de cada execução, se sua identidade auditável ainda está ativa na
  empresa e possui `convert_tender` em editais e `create` em licitações. Revogação, desativação ou
  mudança de empresa bloqueia a conversão, preservando autorização funcional, auditoria e isolamento
  multiempresa mesmo em agendamentos antigos;
- Configurações ganhou o painel **Agente autônomo de licitações**, com controles persistidos para a
  política interna e indicação inequívoca do limite externo. A seção herda o motion discreto e o
  desligamento por `prefers-reduced-motion` já aplicados às seções diretas da tela, além de campos
  navegáveis por teclado e retorno em `aria-live`; cache PWA atualizado para
  `sivs-v2.2.0-tender-autonomy-54`, posteriormente supersedido pelo cache atual
  `sivs-v2.2.0-tender-handoff-55`;
- a verificação oficial vigente não encontrou API pública de fornecedor para cadastrar proposta ou
  enviar lances: as APIs de manutenção do PNCP destinam-se a plataformas credenciadas que publicam em
  nome de órgãos contratantes; o fluxo do fornecedor no Compras.gov.br ocorre em ambiente autenticado;
  e o Serpro documenta bloqueio de robôs de lance. Portanto não foi implementada simulação de clique,
  captura de credencial pessoal, burla de CAPTCHA/antirrobô nem recibo inventado;
- o sistema agora executa sem operador a descoberta, filtragem técnica e criação da oportunidade
  operacional. A entrada externa continua condicionada a um adaptador oficialmente autorizado pelo
  portal, credencial corporativa delegável, ambiente de homologação, regras de preço/lance e recibo
  verificável. Sem esses contratos externos, prometer participação e lance integralmente autônomos seria
  tecnicamente falso e operacionalmente inseguro.
- validação final: 106 de 106 testes aprovados, incluindo agenda diária idempotente sem operador,
  busca de detalhes/itens/anexos oficiais,
  preservação de valor sigiloso, conversão sem valor e revogação de permissão; compilação Python,
  sintaxe JavaScript e `git diff --check` aprovados. A auditoria comportamental percorreu 55 telas com
  login e a auditoria responsiva rápida aprovou 3 telas e 10 interações em 390 px sem overflow.

### 22/08/2026 — homologação convertida em contrato, execução, suprimento e financeiro

- a migration 234 criou `tender_operational_handoffs` e `financial_document_origins`. O primeiro
  registra, de forma idempotente e imutável, a passagem da proposta aprovada para a Licitação,
  cliente, contrato, venda ou ordem de serviço e eventual solicitação de compra; o segundo identifica
  a origem exata de cada título financeiro. Triggers validam empresa, módulo e relacionamentos no banco,
  além das validações e permissões aplicadas pelo servidor;
- `POST /api/tenders/results/{id}/operational-handoff` somente materializa uma proposta cuja versão
  vigente esteja aprovada, ligada à Licitação convertida e na etapa `Homologada`. A operação exige a
  nova permissão `materialize_tender`, permissões dos módulos de destino, cliente ativo, desbloqueado e
  aprovado para faturamento, itens sem exceção pendente e dados oficiais do instrumento. Repetir a
  chamada devolve o handoff existente sem duplicar registros;
- a Licitação passou a obedecer no servidor e na interface ao fluxo `Captação -> Análise ->
  Documentação -> Proposta enviada -> Disputa -> Habilitação -> Homologada`, com saída para
  `Perdida` nas etapas aplicáveis. O servidor mantém `payload.etapa` igual ao status, impedindo que a
  tela indique uma etapa diferente da efetivamente persistida;
- a materialização cria um contrato e copia exatamente os itens da versão aprovada para uma venda
  quando todos são produtos, ou para uma ordem de serviço quando existe serviço. Produtos atendidos por
  estoque recebem depósito e lote reais, podendo ser divididos entre lotes, e a transação falha inteira
  se o saldo atual não for suficiente. Itens de compra e a parcela faltante dos itens mistos geram uma
  solicitação de compra conectada; o sistema não inventa fornecedor nem transforma a solicitação em
  pedido antes da seleção e aprovação da contraparte;
- venda faturada e ordem de serviço concluída geram uma conta a receber idempotente, vinculada ao
  cliente e ao documento de origem, com valor recalculado a partir dos itens. Pedido de compra recebido
  gera conta a pagar somente quando a opção **Gerar conta a pagar ao receber (somente sem XML)** foi
  marcada; isso evita duplicidade com a entrada de NF-e XML, que já possui seu próprio fluxo financeiro.
  Cliente e fornecedor são revalidados no servidor conforme o papel e a situação cadastral;
- documentos com itens agora sempre recalculam o valor no servidor durante atualizações de status.
  Venda ou ordem de serviço não pode ser concluída enquanto existir produto sem baixa integral de
  estoque. Depois do handoff, proposta, origem financeira e vínculos essenciais ficam protegidos contra
  reabertura, troca de contraparte e exclusão silenciosa; mudanças comerciais posteriores devem seguir
  um futuro fluxo de aditivo, e não alterar a fotografia aprovada;
- o encerramento do servidor passou a aguardar as requisições HTTP ativas, garantindo que cada worker
  feche sua conexão SQLite antes da desmontagem, substituição ou limpeza do banco. Isso removeu a janela
  em que um arquivo temporário podia permanecer bloqueado no Windows;
- o detalhe da proposta ganhou uma seção de implantação operacional com bloqueios visíveis, seleção
  de cliente validado, instrumento, vigência, vencimento, local e responsável técnico quando aplicável.
  O formulário evita envio duplicado, informa o resultado conectado e preserva navegação por teclado,
  layout de uma coluna nas menores larguras e `prefers-reduced-motion`; cache PWA atualizado para
  `sivs-v2.2.0-tender-handoff-55`;
- limites ainda assumidos explicitamente: o título automático nasce em parcela única, sem substituir
  parcelamento, conciliação bancária ou recebimento/pagamento estruturado; solicitação de compra ainda
  requer cotação e fornecedor aprovado; impostos, frete, BDI, alçadas de margem, calendário real de
  capacidade, ordem de produção, aditivos, assinatura e adaptadores oficiais de protocolo/lance/NF-e
  permanecem evoluções separadas. Backup externo continua sendo risco operacional P0;
- validação final: 78 testes de servidor e 28 contratos de frontend (106 no total) aprovados, cobrindo o percurso
  proposta aprovada -> homologação -> contrato -> ordem de serviço -> reserva/baixa -> conclusão ->
  conta a receber, além de venda/conta a receber, pedido/conta a pagar, idempotência, permissões e
  proteções de exclusão. Compilação dos três pontos de entrada Python, sintaxe dos 26 JavaScript,
  `git diff --check` e otimizador de imagens em `dry-run` foram aprovados; a auditoria responsiva rápida
  percorreu 3 telas e 10 interações em 390 px sem overflow nem falha de interação.

### 23/08/2026 — cobertura por item oficial e prioridade secundária

- a busca textual do PNCP agora completa cada lote rotativo com os títulos dos produtos e serviços
  ativos da empresa. Assim, a cobertura acompanha o catálogo real de cada tenant e não depende somente
  da lista técnica fixa ou das palavras digitadas por um operador;
- quando o índice oficial encontra um edital por um termo do catálogo, mas o objeto geral é genérico,
  o resultado é preservado como `Analisar` e `PENDING_OFFICIAL_ITEM`. Ele não é tratado como aderência
  confirmada nem convertido apenas pela ocorrência no índice;
- o agente consulta os itens oficiais do PNCP e testa cada item separadamente contra o catálogo. Isso
  evita fabricar uma correspondência combinando palavras que pertencem a itens diferentes. Com ao
  menos um item confirmado, o edital entra no funil independentemente do valor; com exatamente um item,
  recebe prioridade `LOW`, sem ser descartado;
- `captureSingleCatalogItem` e `minimumCatalogMatches=1` são diretrizes fixas da política: a interface
  as mostra, mas não permite aumentar o corte e esconder oportunidades. O payload da Licitação registra
  prioridade, itens do catálogo e números/descrições dos itens oficiais compatíveis para rastreabilidade;
- a preparação autônoma reprocessa até 500 oportunidades abertas do backlog, não apenas as criadas no
  ciclo corrente, e ignora prazos já encerrados. Falha temporária ao obter detalhes oficiais mantém o
  candidato pendente para nova tentativa; conversão continua condicionada a permissão ativa, isolamento
  multiempresa e evidência técnica verificável;
- a agenda gerada pelo sistema executa a cada duas horas. Com oito consultas por ciclo e janela móvel de
  sete dias, o vocabulário é distribuído para respeitar o PNCP e revisitado continuamente sem depender
  de operador. Protocolo de proposta e lance externo continuam bloqueados até existir conector oficial
  de fornecedor com credencial corporativa e recibo verificável;
- a garantia implementada é de **não descarte interno por baixa quantidade de itens**: um item oficial
  compatível basta para entrar, embora permaneça com prioridade secundária. Cobertura absoluta de todos
  os editais ainda não pode ser afirmada, porque depende da indexação, disponibilidade e limites do
  PNCP e de conectores ainda inexistentes para outros portais. Permanecem P0 um indicador de cobertura
  e atraso por fonte, alerta de ciclo incompleto ou estagnado, retentativa com fila persistente,
  conectores oficiais adicionais e backup externo testado;
- para reduzir a intervenção humana sem perder precisão, os próximos gates operacionais são OCR de
  anexos digitalizados, extração determinística de prazos e exigências com fila somente de exceções,
  impostos/frete/BDI e alçadas parametrizadas, capacidade e produção reais, cotação de fornecedores,
  parcelamento e conciliação financeira, aditivos e protocolo externo verificável;
- validação final: 108 de 108 testes aprovados, incluindo descoberta de objeto genérico, retenção como
  candidato, comprovação de um único item oficial, prioridade baixa, conversão autônoma, backlog,
  permissões e contratos do frontend; compilação dos três pontos de entrada Python, sintaxe dos 26
  JavaScript, `git diff --check` e otimizador de imagens em `dry-run` aprovados. O cache PWA foi
  atualizado para `sivs-v2.2.0-tender-coverage-56`; a auditoria responsiva rápida percorreu 3 telas e
  10 interações em 390 px, sem overflow ou falha de interação.

### 23/08/2026 — monitor de cobertura e retentativa persistente sem perda de rotação

- a migration 235 criou `tender_retry_queue`, isolada por empresa e ligada aos jobs de origem e de
  retomada. Triggers impedem associar uma fila a jobs de outra empresa, o reinício do servidor devolve
  retentativas interrompidas ao estado pendente e o histórico terminal permanece auditável;
- cada termo textual que não recebeu resposta do PNCP é preservado exatamente como pendência. O
  agendador repete somente os termos incompletos em 5, 15, 45, 120 e 360 minutos, limita o processo a
  cinco tentativas e marca a exceção como `ABANDONED` quando a fonte ou a autorização não permite
  continuar. Retentativas não contam como avanço da rotação normal;
- antes de enfileirar uma retomada, o servidor revalida empresa, usuário ativo e a operação
  `search_tenders`. Uma identidade revogada não continua pesquisando em segundo plano. A conversão
  autônoma mantém a revalidação adicional de `convert_tender` e criação em `licitacoes`;
- retentativas têm precedência sobre novos lotes. Quando existe outro job ativo, a agenda vencida não
  avança artificialmente: ela permanece devida e roda no primeiro ciclo livre, evitando que uma
  recuperação faça oito termos do catálogo desaparecerem da varredura;
- `GET /api/tenders/coverage`, sob a mesma permissão de leitura de editais, informa saúde, último ciclo
  oficial, próxima execução, fila pendente, falhas terminais, tamanho do vocabulário e duração estimada
  da volta completa. O painel de Editais apresenta esses dados, inclusive o termo em recuperação, em
  layout responsivo e sem expor dados de outra empresa;
- cobertura parcial gera aviso e retentativa esgotada ou ciclo oficial sem sucesso por mais de seis
  horas gera alerta crítico no sistema. O alerta é idempotente, aponta para Editais e é removido quando
  a saúde correspondente se recupera;
- esta entrega fecha monitoramento e recuperação da captura oficial; ela não declara prontos OCR,
  conectores de outros portais, regras tributárias/comerciais parametrizadas, capacidade/produção,
  cotação automática, conciliação, backup externo ou protocolo/lance. Esses blocos continuam
  separados porque dependem de documentos, regras, credenciais e destinos reais da empresa;
- cache PWA atualizado para `sivs-v2.2.0-tender-coverage-57`. Validação final: 111 de 111 testes
  aprovados; compilação dos três pontos de entrada Python, sintaxe dos 26 JavaScript,
  `git diff --check` e otimizador de imagens em `dry-run` aprovados. A auditoria responsiva rápida
  percorreu 3 telas e 10 interações em 390 px, sem overflow ou falha de interação.

### 23/08/2026 — OCR, extração determinística e operação por exceção

- a migration 236 criou `tender_analysis_exceptions` e `tender_details.extraction_json`, ambos
  isolados por empresa. Triggers impedem relacionar uma exceção ao edital de outro tenant; a
  resolução registra responsável, data, justificativa e evento de auditoria;
- a leitura documental não depende mais da IA: regras determinísticas extraem prazos e exigências
  recorrentes da Lei 14.133 com evidência por documento e página. Os achados alimentam o checklist
  como sugestão a confirmar no edital, nunca como marcação automática de conformidade;
- PDFs com página-imagem e documentos de imagem passam por Tesseract em português/inglês. O processo
  não usa shell, valida o executável e os idiomas, limita imagem a 12 MB, encerra em 45 segundos,
  processa no máximo 40 páginas de OCR e três imagens por página. A imagem de produção instala
  `tesseract-ocr`, `tesseract-ocr-por` e `tesseract-ocr-eng`; Pillow atende à extração segura das
  imagens incorporadas pelo `pypdf`;
- falha de download, documento sem texto, OCR indisponível ou OCR inconclusivo entra na Central de
  Exceções, ordenada por criticidade e prazo. Exceção crítica gera notificação idempotente e bloqueia
  a confirmação do checklist e o envio da proposta comercial até conferência humana justificada;
- nova extração completa encerra automaticamente pendências que desapareceram. Uma exceção resolvida
  por pessoa não reabre ao reler a mesma versão; se a lista oficial de anexos mudar, extração,
  análise, alertas e resoluções anteriores são invalidados para impedir decisão baseada em edital
  desatualizado;
- a análise opcional por IA reutiliza as mesmas páginas e indica quais foram complementadas por OCR.
  Ausência da chave do provedor não impede a extração determinística nem oculta seu resultado;
- validação final: 116 de 116 testes aprovados, incluindo limites do subprocesso OCR, evidências,
  sugestões do checklist, bloqueios, alertas, resolução auditada, invalidação e isolamento
  multiempresa. Compilação dos três pontos de entrada Python, sintaxe dos 26 JavaScript,
  `git diff --check`, imagens em `dry-run`, auditoria responsiva de 3 telas/10 interações e auditoria
  funcional de 55 telas sem erros foram aprovadas. Cache PWA atualizado para
  `sivs-v2.2.0-tender-extraction-58`;
- limite de aceitação: esta estação Windows não possui Docker nem Tesseract. A invocação, limites e
  tratamento de falhas foram testados com processo controlado, e o contêiner de produção foi
  configurado, mas ainda é obrigatório executar um ensaio de aceitação no ambiente implantado com
  PDFs escaneados representativos da SECCOL antes de declarar o OCR real homologado;
- permanecem como próximos blocos: impostos, frete, BDI, margem e alçadas parametrizadas; agenda real
  de capacidade e produção; cotação e aprovação de fornecedores; parcelamento e conciliação
  financeira; aditivos; backup externo restaurado em ensaio; e conectores oficiais adicionais para
  protocolo, lance e portais além do PNCP. Nenhum desses fluxos é simulado pela interface atual.

### 23/08/2026 — abas de trabalho e simulação operacional integral

- a navegação principal passou a abrir abas de trabalho reais e conectadas ao mesmo `navigate()` do
  sistema. O Painel permanece fixo, a tela ativa recebe `aria-current`, cada aba pode ser retomada ou
  fechada e fechar a aba ativa retorna à anterior sem deixar uma rota órfã;
- as abas são persistidas por usuário e empresa, filtradas novamente pelas permissões efetivas a cada
  renderização e limitadas a sete telas de trabalho mais o Painel. Troca de empresa não reaproveita
  contexto de outro tenant. Há navegação por setas, Home e End, foco visível, rótulo acessível no botão
  de fechar e rolagem automática da aba ativa;
- em telas móveis, a faixa usa rolagem horizontal contida, mantém o documento dentro do viewport e
  apresenta alvos de toque de 44 px. O comportamento ficou em `static/js/ui/workspace-tabs.js`, as
  preferências em `static/js/core/preferences.js` e a aparência em `static/theme/productivity.css`;
  o cache PWA foi atualizado para `sivs-v2.2.0-workspace-tabs-59`;
- `tools/simulate_full_operation.py` criou uma simulação segura e repetível do uso integral já
  implementado. Ela nunca toca no banco configurado: cada cenário inicia servidor e banco temporários,
  persiste efeitos e percorre acesso/multiempresa, cadastros, edital com um único item, extração e
  exceção, documentos, proposta/aprovação, homologação, contrato, ordem de serviço, estoque, contas a
  receber, compras/recebimento/contas a pagar, controladoria, fiscal, contabilidade, backup e centro de
  controle. O relatório estruturado fica em `.artifacts/full-operation-simulation.json`;
- resultado da simulação: 18 de 18 cenários aprovados em seis etapas. A auditoria funcional real no
  navegador percorreu as 55 telas disponíveis, criou usuário, autenticou, abriu oito abas, retomou e
  fechou a aba ativa, sem erro fatal. A auditoria responsiva integral percorreu 220 combinações
  tela/viewport e 33 interações em desktop, tablet, 390 px e 360 px, sem overflow ou falha;
- validação final: 117 de 117 testes aprovados; cinco arquivos Python compilados; sintaxe dos 27
  JavaScript aprovada; `git diff --check` sem erro; imagens verificadas em `dry-run`. Os testes incluem
  isolamento multiempresa, permissões no servidor, auditoria, idempotência e os contratos de IDs do
  frontend;
- limite de aceitação: “simulação integral” significa cobertura do que existe dentro do SIVS com dados
  temporários e transportes externos controlados. OCR real no contêiner com documentos da SECCOL,
  SEFAZ real com certificado A1, protocolo/lance em portal externo e restauração de backup no destino
  externo continuam exigindo homologação com infraestrutura e credenciais reais; o simulador os marca
  explicitamente como não homologados, em vez de produzir um falso sucesso.

### 23/08/2026 — jornada única ponta a ponta e liquidação financeira conectada

- a auditoria diferenciou cobertura por cenários de uma jornada transacional contínua. A versão 2 de
  `tools/simulate_full_operation.py` agora começa por um único servidor, empresa e banco temporário e
  percorre setup, segregação da aprovadora, edital, proposta, checklist, aprovação, homologação,
  contrato, ordem de serviço, reserva/baixa de estoque, conta a receber, recebimento, compra, entrada de
  estoque, conta a pagar, pagamento, caixa, controladoria e isolamento em segunda empresa;
- a jornada revelou que os estados terminais `Recebido` e `Pago` não geravam movimento de caixa. A
  migration 237 criou `financial_settlements`: cada baixa integral agora materializa uma entrada ou
  saída em `caixa`, herda parte, conta, categoria, meio e data, registra centavos e origem, e produz
  auditoria. Título, movimento e vínculo ficam imutáveis; exclusão e alteração posterior exigirão um
  futuro fluxo explícito de estorno, não manipulação da trilha histórica;
- contas a receber continuam aceitando apenas Cliente (C) ou Ambos (A); contas a pagar, Fornecedor (F)
  ou Ambos (A). A baixa usa permissão funcional `settle_financial`, valida no servidor e permanece
  isolada por empresa. Se a data não for informada, o servidor registra a data corrente; os formulários
  agora expõem conta, meio e data e explicam o reflexo automático no caixa;
- a mesma auditoria encontrou um caminho financeiro antes não exercitado: parcelas `dup` de XML NF-e
  possuíam SQL inválido, valor negativo e não levavam o ID relacional do fornecedor. A importação agora
  cria obrigação positiva, associa fornecedor e documento fiscal por
  `financial_document_origins`, preserva a avaliação pendente do fornecedor sem confundi-la com
  aprovação de compra e permite liquidar a obrigação fiscal em saída de caixa rastreável;
- evidência da jornada contínua: proposta final de R$ 820,00, contrato/OS e recebível de R$ 820,00,
  entrada de caixa de R$ 820,00; pedido e obrigação de R$ 50,00, saída de caixa de R$ 50,00; saldo da
  controladoria de R$ 770,00 e contas abertas a pagar/receber zeradas. A segunda empresa não enxerga os
  registros nem os valores da primeira;
- a ausência atual do A1 é condição esperada e testada: `certificate=null`, consulta de status e emissão
  permanecem bloqueadas e nenhuma chamada real à SEFAZ é feita. Isso não impede os fluxos comercial,
  operacional, estoque, compras, financeiro, caixa ou contábil local;
- validação final: simulador `SIVS_FULL_OPERATION_2` com 20 de 20 cenários em sete etapas; 119 de 119
  testes da suíte; navegador com 55 telas, zero erro, criação/login e abas aprovados; auditoria
  responsiva com 220 combinações e 33 interações em quatro viewports, sem overflow ou falha; cinco
  Python e 27 JavaScript validados, imagens em `dry-run` e `git diff --check` sem erro. Cache PWA
  atualizado para `sivs-v2.2.0-financial-settlement-60`;
- limite ainda explícito: esta entrega valida liquidação integral. Como não existe motor de múltiplas
  baixas, juros, descontos, tarifas e saldo residual, novas transições para `Parcial` foram removidas da
  interface e bloqueadas no servidor; títulos legados nesse estado ainda podem ser concluídos
  integralmente. Esses recursos não são declarados como simulados nem prontos. Certificado/SEFAZ, OCR
  real, protocolo/lance externo e restauração em destino externo dependem de infraestrutura real.

### 23/08/2026 — ledger financeiro completo, estorno e conciliação confirmada

- a migration 238 substitui de forma idempotente o vínculo integral 1:1 por um ledger multi-evento.
  Bases v237 são migradas preservando título, caixa, valor, data, conta, forma de pagamento e IDs; a
  rotina tolera reinício intermediário, recompõe índices e foi validada reabrindo uma base legada com
  baixa existente;
- `POST /api/financial/titles/{id}/settlements` registra principal parcial ou integral, desconto,
  juros/multa, tarifa, conta, meio, data e observação em uma única transação. O caixa líquido é
  calculado em centavos conforme entrada/saída, o saldo é derivado do ledger e o título muda para
  `Parcial`, `Recebido` ou `Pago` sem edição manual de status. Revisão otimista impede duas pessoas de
  baixarem o mesmo saldo simultaneamente;
- `POST /api/financial/settlements/{id}/reverse` nunca altera o evento original: cria movimento oposto
  no caixa, evento `REVERSAL`, recompõe saldo/status e exige justificativa. Uma baixa conciliada não
  pode ser estornada até a desconciliação; segundo estorno, edição e exclusão do ledger são recusados;
- `bank_statement_entries` recebe extrato CSV real e limitado com `id,data,tipo,valor,descricao`,
  deduplica por empresa/ID externo e sugere somente caixas com mesmo valor, mesma direção e data em até
  três dias. A pessoa confirma ou desfaz a correspondência; ambas as ações são auditadas. Não há
  alegação de API bancária ou CNAB homologado sem banco, convênio e layout reais;
- a controladoria agora usa o saldo principal remanescente de títulos parciais, em vez de somar o valor
  cheio. Entradas/saídas de caixa incluem os ajustes líquidos e os movimentos opostos de estorno;
- a ficha de contas a pagar/receber ganhou um componente próprio em
  `static/js/modules/financial-ledger.js` e `static/theme/financial-ledger.css`: resumo do título,
  principal liquidado, saldo, histórico, baixa, estorno e conciliação. Permissões separadas
  `settle_financial`, `reverse_financial` e `reconcile_cash` são validadas novamente no servidor;
- a pesquisa oficial desta etapa confirmou que a Lei 14.133 exige orçamento/preço detalhado e análise
  de exequibilidade, enquanto orientações do TCU não sustentam percentuais universais de BDI. Por isso
  o motor comercial existente — custo interno, piso por item, preço, margem versionada e aprovação
  independente — foi preservado, sem introduzir alíquota ou BDI fictício. Parametrização tributária e
  composição empresarial continuam condicionadas às regras reais validadas pela SECCOL/contabilidade;
- `tools/simulate_full_operation.py` passou a incluir baixa parcial, ajustes, extrato, conciliação,
  desconciliação e estorno. `tools/audit_interactions.py` agora cria um recebível descartável no
  navegador, baixa R$ 40,00 de R$ 100,00, confere saldo de R$ 60,00, importa/concilia o extrato e
  confirma que estorno conciliado fica bloqueado;
- validação final desta etapa: 121 testes de servidor/frontend aprovados; simulador integral com 21 de
  21 cenários; navegador real com 55 telas, `errors=[]`, baixa parcial e conciliação aprovadas;
  auditoria responsiva com 220 telas e 33 interações em quatro viewports, sem overflow ou falha;
  compilação Python, sintaxe JavaScript e `git diff --check` aprovados. Cache PWA atualizado para
  `sivs-v2.2.0-financial-ledger-61`;
- permanecem dependentes de infraestrutura ou decisão empresarial: certificado A1/SEFAZ real, OCR no
  contêiner com documentos representativos, conectores oficiais de portais/lances, restauração de
  backup em destino externo e parâmetros tributários/BDI aprovados. Esses limites continuam visíveis e
  não são convertidos em sucesso simulado.

### 23/08/2026 — agente de portal governado, shadow real e contrato de navegador

- a migration 239 criou `tender_agent_policies`, `tender_agent_runs`,
  `tender_agent_commands` e `tender_agent_receipts`. Chaves estrangeiras, índices e triggers validam a
  empresa do edital, da proposta, da versão, da execução e de cada comando. A fotografia financeira da
  política, o conteúdo autorizado do comando e os recibos são imutáveis;
- a aprovação independente da proposta agora prepara automaticamente uma política `SHADOW` vinculada à
  versão aprovada. O valor total e o piso consolidado são derivados dos itens imutáveis da proposta,
  nunca de texto da IA. Reabrir a proposta encerra a política e cancela execuções ativas; aprovar nova
  versão cria uma nova fotografia, sem reaproveitar limites antigos;
- foram adicionadas permissões funcionais separadas para configurar, armar e operar o agente. Os modos
  são `SHADOW`, `SUPERVISED` e `AUTONOMOUS`. Shadow executa todo o contrato sem efeito externo;
  supervisionado pode preparar/navegar com confirmação humana; autônomo exige autorização escrita,
  portal operacional homologado, flags explícitas de protocolo/lance e
  `SIVS_ALLOW_TENDER_AGENT_PRODUCTION=1`;
- cada sugestão de lance passa novamente pelo servidor: disputa aberta, proposta ainda aprovada e na
  mesma versão, janela autorizada, passo mínimo, redução máxima, quantidade máxima de tentativas,
  competitividade, piso absoluto e chave idempotente. Abaixo do piso não gera comando. Um comando
  anterior sem recibo impede outro lance. Em produção, o valor só se torna o último lance da empresa
  depois de o portal devolver sucesso, protocolo e hash da evidência;
- `POST /api/integrations/tender-agent/lease` e `/result` formam o contrato HMAC do navegador. Timestamp,
  assinatura, empresa fixa, lease curto, worker identificado, comando autorizado e recibo imutável
  impedem acesso direto ao banco e replay entre empresas. Somente comandos produzidos pelo guardrail
  entram na fila;
- `tools/tender_portal_worker.py` é um executor de referência seguro por padrão. Sem `--execute`, não
  chama o servidor nem abre navegador. Com Selenium e perfil dedicado, executa navegação e verificação
  sem efeito externo. Envio e lance permanecem em `MANUAL_REQUIRED` enquanto o adaptador específico do
  portal não estiver homologado, mesmo que a flag local seja fornecida;
- a ficha do edital ganhou o componente `static/js/modules/tender-portal-agent.js` e o tema
  `static/theme/tender-portal-agent.css`: valor aprovado, piso, margem de disputa, portal, URL oficial,
  modo, janela, limites, autorização, estado, simulação de evento e trilha imutável. Há alvos de 44 px,
  layouts responsivos, `aria-live`, teclado nativo e `prefers-reduced-motion`. O cache PWA passou a
  `sivs-v2.2.0-portal-agent-62`;
- evidência automatizada: proposta de R$ 800,00 com piso consolidado de R$ 590,00 criou shadow; lance de
  R$ 789,00 foi autorizado uma vez; repetição retornou o mesmo comando; lance abaixo de R$ 590,00 foi
  recusado sem criar comando; worker HMAC recebeu somente R$ 780,00 já autorizado e o estado real só
  avançou após protocolo e hash. Inserção cruzada de execução em segunda empresa foi recusada pelo
  SQLite;
- validação final: 121 de 121 testes aprovados; simulador integral com 21 de 21 cenários; auditoria de
  navegador com 55 telas, login e `errors=[]`; auditoria responsiva com 220 combinações e 33
  interações em quatro viewports, sem overflow ou falha; compilação Python, sintaxe JavaScript e
  `git diff --check` aprovados;
- limite de aceitação: não houve lance em portal real porque este repositório não possui credencial
  corporativa, autorização escrita nem ambiente de homologação dos portais. Para produção ainda é
  obrigatório implementar e homologar os seletores/contratos de cada portal aceito, testar com conta
  corporativa, tratar mudanças de DOM e manter CAPTCHA/MFA como parada manual. O núcleo, a simulação e
  o protocolo do worker estão funcionais; declarar lance externo concluído antes desses ensaios seria
  falso sucesso.

### 24/08/2026 — caixa de entrada WhatsApp vinculada ao CRM e acesso por função

- a pesquisa oficial consolidada em `sivs_2_2/PLANO_CRM_WHATSAPP_2026-08-24.md` confirmou Cloud API,
  webhook, janela de atendimento de 24 horas, templates aprovados fora da janela, opt-in/opt-out,
  transparência LGPD e autorização com menor privilégio e validação em cada requisição;
- a migration 240 criou `whatsapp_conversations`, `whatsapp_messages` e `whatsapp_quick_replies`, com
  empresa obrigatória, identificadores externos idempotentes, vínculo ao CRM, responsável, equipe,
  janela do cliente, recibos de estado e triggers contra atribuição ou relacionamento cruzado;
- criado o perfil-base `seller` (Vendedor). Vendedores recebem CRM/WhatsApp e veem conversas próprias
  ou sem responsável; precisam assumir antes de responder. Gestores veem e distribuem todas; somente
  administradores gerenciam a integração. Financeiro e demais perfis não recebem acesso automático e
  podem ser liberados individualmente pela matriz já existente;
- o webhook público valida desafio e `X-Hub-Signature-256`, limita o corpo, fixa empresa e
  `phone_number_id`, ignora duplicatas e transforma o primeiro contato em `Novo lead` do CRM. A
  auditoria guarda IDs e contagens, não o conteúdo das mensagens; notificações respeitam o novo módulo;
- mensagem livre é bloqueada no servidor após 24 horas. Respostas rápidas internas aceitam somente
  `{{nome}}`, `{{vendedor}}` e `{{referencia}}` e não são apresentadas como templates Meta. O envio
  oficial exige token, número e versão Graph explícita nos segredos de runtime; timeout fica `UNKNOWN`
  e orienta não repetir antes da conferência;
- criada a tela **Atendimento WhatsApp** em `static/js/modules/whatsapp.js` e
  `theme/whatsapp.css`, com fila, histórico, contexto CRM, atribuição, biblioteca de respostas e estado
  inequívoco da integração. O layout usa alvos de 44 px, desktop/tablet/mobile, motion uniforme de
  620 ms em opacidade/transform e desligamento em `prefers-reduced-motion`;
- cache PWA atualizado para `sivs-v2.2.0-crm-whatsapp-63`; 123 de 123 testes foram aprovados, incluindo
  vínculo CRM, assinatura, idempotência, perfil de vendedor, fila e atribuição. Compilação Python,
  sintaxe de todos os JavaScript, `git diff --check` e imagens em `dry-run` passaram; a auditoria
  responsiva percorreu 224 combinações (56 telas em quatro viewports) e 33 interações sem overflow ou
  falha;
- limite de aceitação: credenciais Meta não existem no repositório, portanto envio/recebimento real não
  foi homologado. Templates oficiais, opt-out por finalidade, mídia, campanhas, coexistência/migração
  do número e política empresarial de retenção continuam etapas obrigatórias antes de produção ampla.

### 24/08/2026 — conexão WhatsApp por uazapi, QR e instância multiempresa

- por decisão posterior, a implementação operacional do canal passou a usar a uazapi por QR Code. O
  núcleo anterior de CRM, fila, atribuição e permissões foi preservado; apenas ciclo de instância,
  webhook, status e envio foram adaptados. O plano atualizado está em
  `sivs_2_2/PLANO_CRM_WHATSAPP_2026-08-24.md`;
- a migration 241 criou `whatsapp_instances`, limitada a uma instância por empresa. Token individual é
  cifrado com AES-256-GCM e chave `SIVS_WHATSAPP_MASTER_KEY`; token mestre de criação permanece somente
  no runtime. O frontend não recebe token, `server_url`, URL secreta do webhook ou material cifrado;
- criação usa o proxy indicado com somente `Content-Type`, corpo `token`/`name`/`deviceName` e validação
  estrita do host/path. Servidores de instância precisam ser HTTPS em subdomínio `uazapi.com`, evitando
  que uma resposta externa transforme o backend em cliente SSRF arbitrário;
- o painel administrativo cria/reutiliza a instância, registra webhook, gera QR, consulta status a
  cada 15 segundos enquanto pendente, chama desconexão real e remove externamente antes de apagar o
  registro. Essas operações exigem `manage_whatsapp_integration`; vendedores continuam restritos à
  fila, tomada e resposta de conversas;
- o endpoint atual de envio é `/send/text` com `number`/`text`, `track_source=sivs` e chave idempotente
  em `track_id`; instalações legadas recebem fallback apenas após 404/405 para
  `/message/send-text`. Entrada individual cria lead do CRM, grupos/saídas são ignorados e IDs externos
  deduplicam mensagens;
- risco residual explícito: a documentação do provedor não oferece assinatura HMAC para webhooks. O
  SIVS usa um path aleatório de 256 bits por empresa, rate limit, limite de corpo e empresa derivada do
  próprio registro, mas isso não equivale a autenticidade criptográfica. A tela identifica a uazapi
  como provedor intermediário, não como Cloud API oficial da Meta;
- o token publicado na conversa não foi copiado nem usado e deve ser revogado. Conexão real permanece
  dependente de novo token, `SIVS_PUBLIC_URL` HTTPS, chave de cofre e leitura do QR com número WhatsApp
  Business dedicado. Campanhas, grupos e chatbot automático permanecem fora do escopo;
- validação final: 124 de 124 testes aprovados. O teste dedicado simula criação sem headers extras,
  criptografia do token, isolamento de segunda empresa, QR, atualização de status, entrada idempotente,
  criação do lead CRM, envio atual e exclusão externa. Compilação Python e sintaxe do módulo JavaScript
  passaram; o cache PWA foi atualizado para `sivs-v2.2.0-uazapi-whatsapp-64`.

### 25/08/2026 — follow-up comercial 30/60/90 e validação empresarial do A1

- a migration 242 criou `customer_followups`, sempre vinculada à empresa, ao cadastro físico do
  cliente e, quando existente, à última venda. Triggers recusam cliente, venda ou vendedor de outra
  empresa. A chave única por cliente, marco de compra e estágio torna os alertas idempotentes;
- o marco de inatividade é `data_confirmacao` da última venda em `Confirmado`, `Separação`, `Faturado`
  ou `Concluído`; vendas novas passam a persistir esse instante na primeira transição comercial
  válida. Para clientes sem compra, usa-se a criação do cadastro. Rascunho e venda cancelada não
  reiniciam a contagem;
- o agendador mantém somente o estágio corrente acionável: 30 dias gera revisão comercial, 60 dias
  escalona e 90 dias exige registrar contato. Estágios anteriores permanecem no histórico como
  `ESCALATED`; nova compra torna pendências anteriores `OBSOLETE` e remove suas notificações. Contato
  e dispensa exigem permissão de edição no CRM, são auditados e não podem ser repetidos;
- o vendedor do cadastro recebe a tarefa quando o nome coincide com uma associação ativa da empresa.
  Gestores veem a fila completa; vendedor não pode concluir tarefa atribuída a outro. Sem
  correspondência, o alerta fica disponível à equipe autorizada, evitando perda silenciosa;
- a tela CRM ganhou painel responsivo em `static/theme/crm-followups.css`, contadores 30/60/90, canal,
  resultado/observação e ações com alvos de toque. Não existe disparo automático no estágio de 90
  dias: WhatsApp continua exigindo decisão humana, finalidade e consentimento/base legal aplicáveis;
- a pesquisa oficial atualizada confirmou que, em Goiás, a empresa precisa de inscrição estadual
  regular, e-CNPJ, credenciamento no DT-e, credenciamento específico para NF-e e software emissor. O
  A1 sozinho não autoriza emissão. O Portal NF-e também já publica leiautes/regras RTC da Reforma
  Tributária, incluindo NT 2025.002 v1.50 e notas de 2026, que precisam integrar a homologação. O
  roteiro e os critérios formais ficaram em `sivs_2_2/PLANO_HOMOLOGACAO_NFE_A1_2026-08-25.md`;
- o cofre A1 agora extrai o CNPJ exclusivamente do `otherName` ICP-Brasil OID `2.16.76.1.3.3`, valida
  vigência inicial/final, correspondência entre chave privada e certificado, assinatura digital,
  autenticação TLS quando a extensão existe e igualdade da raiz de oito dígitos com a unidade. Um A1
  válido de outra empresa é recusado e o CNPJ validado aparece apenas como metadado público;
- a prontidão fiscal passou a declarar o credenciamento estadual como verificação externa obrigatória
  e continua com `canIssue=false`. Mesmo após importar o A1, ainda faltam motor XML NF-e 4.00/RTC,
  XSD, assinatura XML, autorização e retorno, rejeições, protocolo, DANFE, numeração/série,
  cancelamento, inutilização, contingência, distribuição e armazenamento homologados. A consulta de
  status mTLS permanece implementada e só será comprovada com certificado/credenciamento reais;
- validação final desta etapa: 125 testes descobertos e aprovados após a atualização dos contratos de
  cache; simulador integral com 22 cenários; navegador com 56 telas e login aprovado; auditoria
  responsiva com 224 telas e 33 interações em desktop, tablet, 390 px e 360 px, sem overflow ou falha;
  compilação Python, sintaxe JavaScript e `git diff --check` aprovados. Cache PWA atualizado para
  `sivs-v2.2.0-crm-followups-65`;
- limites de aceitação permanecem objetivos: não houve transmissão NF-e, assinatura XML, autorização,
  rejeição, cancelamento ou inutilização reais, pois não há A1, credenciamento nem configuração
  tributária homologada neste ambiente. Também não houve contato WhatsApp real de reativação; o fluxo
  cria tarefa humana auditável e não simula consentimento nem sucesso externo.

### 25/08/2026 — prioridades do painel com ação necessária explícita

- cada item de **Prioridades para agora** passou a declarar **O que fazer agora**, diferenciando
  decisão de aprovação, acompanhamento pelo solicitante, prazo próximo, prazo vencido e revisão de
  registro em andamento;
- a orientação considera a permissão efetiva: quem pode alterar recebe instrução de concluir ou
  atualizar; quem possui somente leitura recebe orientação para conferir e acionar o responsável;
- datas deixaram de aparecer sem contexto e agora são identificadas como **Até** ou **Venceu em**;
  o estado vazio informa inequivocamente que nenhuma ação é necessária naquele momento;
- preservados isolamento multiempresa, segregação de aprovações, contratos de IDs, navegação por
  teclado, layout responsivo e movimento reduzido. Cache PWA atualizado para
  `sivs-v2.2.0-dashboard-actions-66`.
- validação final: 126 testes aprovados; compilações Python, sintaxe de `app.js` e service worker,
  `git diff --check` e imagens em `dry-run` aprovados; auditoria responsiva rápida percorreu três
  telas e dez interações em 390 px, sem overflow ou falha.

### 25/08/2026 — validação antecipada de CPF/CNPJ em clientes e fornecedores

- ao completar um CPF ou CNPJ válido, o cadastro consulta a empresa ativa após uma espera curta de
  180 ms e antes de liberar os demais campos. Documento inválido mantém o formulário bloqueado e
  apresenta a correção necessária no próprio fluxo;
- quando o documento já pertence a um cliente ou fornecedor, a interface informa imediatamente o
  nome, código, tipo e situação permitidos ao usuário e oferece **Abrir cadastro existente**. Se o
  usuário não puder ler o módulo encontrado, a existência é informada sem expor seus dados;
- somente um documento disponível libera o restante do formulário e, no caso de CNPJ, autoriza a
  consulta externa de dados empresariais. Falha de rede não substitui a validação autoritativa no
  salvamento, que continua recusando duplicidade normalizada no servidor;
- a consulta `/api/partners/lookup` respeita empresa ativa, permissão de escrita e leitura por módulo;
  na edição, `excludeId` ignora somente o próprio cadastro. As opções de tipo do parceiro também foram
  alinhadas aos valores canônicos Cliente, Fornecedor e Cliente e fornecedor;
- a auditoria real em 390 × 844 confirmou digitação, aviso, identificação e abertura do registro sem
  erros de navegador. Contratos do frontend e teste dedicado do servidor passaram; cache PWA atualizado
  para `sivs-v2.2.0-party-live-lookup-67`;
- a suíte integral executou 127 testes: 126 passaram. A única falha permanece fora deste fluxo, em
  `test_accounting_export_is_audited_exact_and_company_scoped`, cuja fixture tenta criar um lançamento
  sem `parceiro` e `categoria_id`, hoje obrigatórios no contrato financeiro. A pendência foi mantida
  explícita para não ampliar esta alteração para o domínio contábil.

### 25/08/2026 — financeiro orientado a clientes/fornecedores e central fiscal unificada

- contas a pagar aceitam somente fornecedor ou parceiro do tipo ambos; contas a receber aceitam
  somente cliente ou parceiro do tipo ambos. O servidor deriva nome, relacionamento e `tipo_parte`
  do cadastro escolhido, sem confiar em texto ou classificação enviados pelo navegador;
- lançamentos financeiros seguem a mesma regra: Receita filtra e valida cliente; Despesa filtra e
  valida fornecedor. A troca do tipo limpa opções incompatíveis e substitui o relacionamento anterior.
  Movimentos de caixa também exigem um parceiro cadastrado, e oficina de manutenção de frota passou a
  apontar para fornecedor da empresa ativa;
- categorias financeiras deixaram de ser texto livre. A migration 243 criou catálogo isolado por
  empresa, com natureza Receita, Despesa ou Ambos, opções iniciais, ativação controlada e validação
  autoritativa do ID e da natureza no servidor. Os formulários carregam e filtram esse catálogo;
- despesas exibem a área de nota/comprovante no fluxo e salvam registro e evidência na mesma operação.
  Valor e vencimento permanecem visíveis desde o início; quando os campos essenciais são concluídos,
  o disclosure abre automaticamente as informações complementares, preservando toggle manual,
  teclado e `prefers-reduced-motion`;
- **Fiscal** ganhou grupo próprio no menu para Central fiscal e Importar XML NF-e. A importação não
  aparece mais como Administrativo, o painel fiscal oferece atalho direto para XML e concentra
  documentos, SEFAZ, certificado e exportação contábil sem sugerir emissão já homologada;
- cache PWA atualizado para `sivs-v2.2.0-financial-categories-68`. A pendência contábil anterior foi
  corrigida com parceiro e categoria canônicos; 131 testes foram aprovados, incluindo isolamento de
  categorias, evidência atômica e rejeição das combinações cliente/fornecedor incorretas.

### 25/08/2026 — categorias financeiras administráveis e nota anexada à despesa

- a migration 243 criou `financial_categories`, isolada por empresa e com nome normalizado único,
  aplicação em despesa, receita ou ambos, estado ativo/inativo e autoria. Empresas existentes e novas
  recebem uma base operacional inicial; categorias textuais legadas são migradas para IDs sem perder
  o nome histórico;
- administradores passaram a cadastrar, editar, inativar e reativar categorias em Configurações.
  Perfis financeiros podem consultar as opções, mas não alterá-las. Inativação retira a categoria de
  novos lançamentos e preserva a edição de registros históricos que já a utilizavam;
- contas a pagar, contas a receber, lançamentos financeiros e caixa deixaram de aceitar categoria
  digitada como fonte de verdade. A interface usa seleção compatível com a direção do movimento e o
  servidor exige `categoria_id`, confirma empresa, atividade e tipo, e sempre materializa o nome
  canônico, recusando IDs cruzados ou categorias de receita em despesa e vice-versa;
- geração automática por venda, ordem de serviço, pedido de compra, baixa, estorno e importação XML
  também passou a usar categorias estruturadas. Estornos usam a categoria bilateral de ajustes para
  manter a direção financeira coerente;
- o formulário fiscal e os fluxos de despesa exibem um seletor de nota, cupom, recibo ou comprovante
  em PDF, imagem ou XML de até 10 MB. Em criação ou edição, registro e arquivo são validados e gravados
  na mesma transação; falha no MIME, permissão ou persistência não deixa despesa parcialmente criada.
  O anexo reutiliza detecção por assinatura, SHA-256, auditoria e isolamento multiempresa já existentes;
- o cache PWA foi atualizado para `sivs-v2.2.0-financial-categories-68`. Os contratos automatizados
  cobrem IDs da interface, seleção estruturada, acesso administrativo, duplicidade normalizada,
  compatibilidade receita/despesa, inativação histórica, anexo atômico e isolamento entre empresas.
- validação final: 131 testes aprovados, incluindo a fixture contábil que antes estava pendente;
  compilação Python, sintaxe de `app.js` e do service worker e `git diff --check` aprovados.

### 25/08/2026 — copiloto interno contextual com acesso lateral

- o assistente ganhou um botão lateral persistente, além do acesso no cabeçalho, com painel responsivo
  em formato de diálogo, fundo de foco, fechamento por Escape, retorno de foco, navegação por teclado,
  Enter para enviar, Shift+Enter para quebrar linha e alvos de toque de pelo menos 44 px;
- a janela mostra a empresa ativa, tela/cadastro em contexto e perguntas rápidas,
  nova conversa, fontes utilizadas e abertura direta do registro retornado. O contexto enviado pelo navegador
  é revalidado no servidor por empresa, módulo legível e ID existente;
- perguntas livres agora inferem módulos, status e até seis termos reais de busca, em vez de carregar
  registros sem relação. A base interna versionada orienta navegação, cadastro de parceiros, prioridades,
  permissões, aprovações e limites do assistente. Histórico curto é sanitizado e limitado a seis mensagens;
- a consulta possui limite de 30 perguntas por usuário/empresa em cinco minutos. A IA generativa recebe
  somente contexto autorizado e usa resposta JSON Schema estrita, `require_parameters`, `data_collection=deny`
  e `zdr=true` no roteamento OpenRouter. Resposta inválida, indisponibilidade ou chave ausente retornam ao
  modo determinístico seguro, sem interromper o trabalho;
- contratos do servidor e frontend passaram (39 testes selecionados), incluindo isolamento, busca, registro
  aberto, fallback da IA e privacidade. Auditoria móvel em 390 px confirmou abertura, resposta, fonte acionável,
  abertura do cadastro, nova conversa, fechamento e ausência de overflow. Cache PWA atualizado para
  `sivs-v2.2.0-assistant-copilot-70`. A auditoria desktop automatizada ainda possui uma limitação de interação
  nativa do Chrome durante a transição do painel; o cenário touch equivalente foi aprovado.

### 25/08/2026 — assistente unificado para todo o sistema autorizado

- removido da experiência o rótulo técnico que diferenciava “modo seguro” e “IA ativa”; para o usuário
  existe somente o Assistente do sistema, com a mesma interface e a mesma responsabilidade de orientar;
- a consulta passou a incluir todos os módulos de leitura efetivamente liberados ao perfil, não apenas os
  módulos comerciais iniciais. A busca também percorre editais armazenados por título, objeto, órgão, UF,
  prazo, situação e aderência, respeitando operações sensíveis como valores e triagem;
- o contexto de registros passou a materializar campos operacionais seguros do payload — situação, etapa,
  observações, próximo passo, cliente, fornecedor e demais valores simples — bloqueando tokens, segredos,
  senhas, chaves privadas e anexos. Acesso continua limitado à empresa ativa e às permissões do usuário;
- a base de orientação agora lista os módulos disponíveis ao perfil e ensina navegação, cadastros, prioridades,
  aprovações, permissões e limites do sistema. Cache PWA atualizado para `sivs-v2.2.0-assistant-copilot-70`.

### 25/08/2026 — correção de orientação e clareza do Copilot

- perguntas como “como cadastrar novo serviço?” passaram a ser reconhecidas como orientação de uso e
  respondem com o passo a passo do Catálogo de serviços, em vez de serem tratadas como busca sem resultados;
- mensagens internas sobre IA/fallback deixaram de aparecer para o usuário. A resposta informa apenas a
  orientação disponível e as fontes consultadas;
- controles do cabeçalho foram trocados por rótulos claros **Nova** e **Fechar**, reduzindo dependência de
  símbolos que poderiam aparecer vazios em determinadas fontes. Teste específico de orientação foi incluído.

### 25/08/2026 — recuperação de senha via SMTP Hostinger

- corrigido o modelo de ambiente para o e-mail `sac@oziresmoreira.online`, usando
  `smtp.hostinger.com`, porta 587 e STARTTLS; removida uma segunda declaração vazia de
  `SIVS_PUBLIC_URL` que poderia anular a URL pública ao copiar o exemplo;
- o envio de recuperação agora exige host, URL pública, remetente, usuário e senha SMTP,
  evitando relay anônimo e falhas silenciosas de autenticação. A senha do e-mail permanece
  somente no segredo de runtime da hospedagem;
- a validação real ainda depende de preencher os segredos no Dokploy/Hostinger e solicitar um
  link para uma conta cadastrada. O token continua de uso único, expira em 30 minutos e invalida
  as sessões anteriores ao redefinir a senha.

### 25/08/2026 — acesso sutil ao assistente

- o botão lateral do assistente agora permanece dentro da viewport, compacto e visualmente discreto;
  nome e status são revelados ao passar o mouse ou ao receber foco, mantendo abertura por toque,
  teclado, foco visível e alvos mínimos responsivos.

### 25/08/2026 — base de ajuda resiliente para o assistente

- perguntas de orientação de uso e cadastro, como “como cadastrar novo serviço?”, são classificadas
  explicitamente como ajuda e respondidas pela base interna verificada, sem depender da IA externa;
- a IA generativa permanece reservada a consultas com dados autorizados e contexto dinâmico; falhas
  continuam retornando ao modo determinístico, preservando empresa ativa, permissões e auditoria;
- criado `sivs_2_2/ASSISTENTE_SISTEMA.md` como documento vivo de fontes, limites, testes e histórico
  do recurso. `AGENTS.md` agora exige atualizá-lo em toda mudança futura do assistente;
- validação final desta correção: 97 testes do servidor e 38 contratos combinados aprovados. A chamada
  real ao OpenRouter permanece dependente de credencial externa de produção.

### 25/08/2026 — política de acesso, fontes e histórico do assistente

- adicionada política efetiva do assistente com módulos legíveis, operações autorizadas, valores e
  dados pessoais; o modelo recebe somente esse escopo e o contexto já filtrado pelo servidor;
- CPF, CNPJ, documentos, contatos e endereços exigem `view_sensitive`, enquanto preços e valores
  continuam condicionados a `view_values`. Segredos, tokens, senhas, chaves privadas e anexos nunca
  entram no contexto;
- respostas da IA passaram a exigir `source_ids` existentes no contexto autorizado; fontes inválidas
  ou ausência de fonte acionam o fallback determinístico;
- histórico passou a ser persistido e isolado em `assistant_conversations`/`assistant_messages`,
  vinculado ao usuário e à empresa. O navegador não envia mais histórico de mensagens como autoridade;
- o servidor mantém somente as seis mensagens mais recentes por conversa e responde explicitamente quando
  a pergunta pede um módulo sem leitura ou uma criação sem escrita autorizada;
- validação direcionada: proteção de campos, histórico, fontes e contratos do assistente aprovados.

### 25/08/2026 — data e hora sutis no cabeçalho global

- removida a data do bloco lateral “Sistema online”, reduzindo seu espaço vertical sem perder o indicador
  de conectividade e o endereço do servidor;
- dia, data e hora passaram a aparecer de forma discreta no topbar sticky, com a data completa no desktop e
  apenas a hora em telas estreitas para preservar a hierarquia visual;
- o relógio atualiza a cada minuto e a virada do dia continua sendo recalculada, com `datetime` e rótulo
  acessível para leitores de tela. Cache PWA atualizado para `sivs-v2.2.0-partners-75`.

### 25/08/2026 — parceiros e contatos com jornada unificada

- o menu Administrativo passou a usar “Parceiros” como entrada única para clientes, fornecedores ou ambos;
- o botão principal do cadastro unificado permanece “Cadastrar parceiro”, eliminando a divergência com rótulos de cliente/fornecedor;
- contatos agora selecionam um parceiro existente por ID, com validação no servidor, isolamento por empresa e vínculo auditável “Contato de”;
- o nome textual do parceiro continua materializado no payload apenas para leitura e compatibilidade, enquanto o ID e `record_relationships` são a fonte relacional;
- adicionada validação automatizada do vínculo relacional de contatos e atualizado o cache PWA para a versão `partners-73`.

### 25/08/2026 — navegação principal sem ícones

- os títulos dos grupos principais do menu ficaram somente textuais, com tipografia levemente maior e mais
  legível;
- os ícones foram preservados nos itens dos submenus, onde ajudam na identificação de cada tela, sem alterar
  os destinos, permissões ou a navegação por teclado.

### 25/08/2026 — jornada intuitiva de 1 a 8 no painel

- grupos do menu foram renomeados por tarefa (“Cadastros e compras”, “Clientes e vendas”, “Editais e mercado”
  e “Serviços e campo”), mantendo as chaves técnicas, rotas e permissões;
- a tela inicial passou a sugerir atalhos de próximo passo e acessos rápidos conforme o perfil do usuário,
  sem expor funções que ele não pode executar;
- módulos transacionais passaram a exibir claramente “Edição permitida” ou “Somente consulta”; estados vazios
  agora explicam o que falta e oferecem criação direta quando autorizada;
- a busca global continua agrupando áreas e registros, respeitando a empresa ativa e permissões, enquanto a
  validação instantânea existente de CPF/CNPJ, duplicidade, CEP e completude foi preservada;
- cache PWA atualizado para `sivs-v2.2.0-partners-75`.

### 25/08/2026 — linguagem pública sem sigla técnica

- removida da interface a sigla técnica que aparecia em títulos, busca, Assistente, Mobile, Editais,
  Configurações, mensagens do servidor e documentos gerados;
- os textos públicos agora usam “sistema”, “Sistema Seccol” ou descrições funcionais, mantendo nomes de
  APIs, namespaces JavaScript, variáveis de ambiente, cabeçalhos e formatos de backup porque são contratos
  técnicos e não são exibidos como identidade para o usuário;
- preservados permissões, isolamento multiempresa, contratos de IDs, acessibilidade, navegação por teclado
  e movimento reduzido. O rótulo da central foi simplificado para **MÓDULOS**.

### 25/08/2026 — menu direto sem segunda camada obrigatória

- os agrupamentos do menu passaram a ser títulos visuais, não accordions clicáveis;
- todos os destinos autorizados ficam visíveis dentro do grupo correspondente, permitindo chegar à tela em
  um único clique e mantendo a barra lateral rolável para conjuntos maiores;
- a filtragem por leitura continua removendo módulos sem acesso, enquanto ações de criação, edição, exclusão
  e exportação permanecem condicionadas às permissões específicas do usuário.

### 25/08/2026 — grupos do menu mais fáceis de percorrer

- os grupos do menu permanecem abertos por padrão e os destinos autorizados continuam acessíveis em um clique;
  cada grupo agora pode ser recolhido para reduzir a rolagem, especialmente em **Serviços e campo**;
- a preferência de recolhimento é persistida e isolada por usuário e empresa. Quando uma tela é aberta por
  atalho, favorito, aba ou busca global, seu grupo é revelado automaticamente para não ocultar o destino ativo;
- os títulos ganharam controles semânticos com `aria-expanded`, `aria-controls`, foco visível e alvo mínimo
  de toque. O comportamento não depende de animação e continua compatível com teclado e movimento reduzido;
- rótulos internos no menu foram substituídos por termos de tarefa: **Portfólio técnico**, **Operação em campo**,
  **Instrumentos próprios**, **Visão financeira** e **Operação e segurança**. Chaves, rotas e permissões foram
  preservadas;
- a auditoria responsiva passou a contar resultados reais da busca global, em vez de depender do contêiner
  auxiliar de favoritos. Cache PWA atualizado para `sivs-v2.2.0-menu-ux-76`.

### 25/08/2026 — central de notificações acionável, auditável e configurável

- a migration 245 ampliou `notifications` com categoria, descarte e resolução e criou preferências isoladas
  por empresa/usuário, além dos registros idempotentes de entrega imediata e resumo diário. A origem,
  empresa, permissão do módulo e auditoria continuam sendo validadas exclusivamente no servidor;
- a central deixou de depender de “marcar todas como lidas”: cada item pode ser lido individualmente e, quando
  houver vínculo, abre diretamente o registro autorizado. Alertas apenas informativos podem ser dispensados;
  itens críticos e pendências operacionais não podem ser dispensados e permanecem ativos até a resolução;
- notificações históricas não são mais apagadas quando uma regra deixa de valer. A pendência ativa é encerrada
  com data e motivo de resolução, enquanto o evento original fica disponível na aba de histórico para auditoria;
- preferências permitem escolher categorias, severidade mínima, resumo diário, lembretes imediatos para itens
  críticos e horário silencioso. Alertas críticos continuam visíveis mesmo quando filtros pessoais ocultariam uma
  categoria ou severidade menor. Horas de resumo e silêncio são explicitamente tratadas como UTC;
- e-mails são estritamente opt-in e só são enviados quando a configuração SMTP já segura do ambiente estiver
  completa. Eles trazem apenas títulos e link geral do sistema, nunca conteúdo sensível, anexos ou credenciais.
  A rotina é executada junto ao ciclo de atualização do servidor e não substitui a central como fonte de verdade;
- cache PWA atualizado para `sivs-v2.2.0-notification-center-77`. Contratos e testes do servidor cobrem ações
  individuais, preservação de histórico, preferência por usuário/empresa, invariância de alertas críticos e
  auditoria. Validação final: 139 testes aprovados, compilação Python, sintaxe JavaScript, verificação de diff,
  simulação de imagens e auditoria responsiva mobile sem falhas de overflow ou interação.

### 25/08/2026 — controle operacional de licitações e ambiente isolado do futuro robô

- a migration 246 criou `tender_control_profiles`, `tender_control_versions`, `tender_milestones`,
  `tender_risks` e `tender_protocol_evidence`. Decisão GO/NO-GO, responsável, justificativa, agenda
  crítica e matriz de probabilidade x impacto ficam isoladas pela empresa, validadas no servidor,
  fotografadas em versões imutáveis e protegidas por revisão otimista para impedir sobrescrita silenciosa;
- uma decisão GO exige justificativa e, quando houver risco aberto com escore a partir de 15, mitigação
  registrada. Marcos e riscos aceitam responsáveis somente entre membros ativos da empresa. Triggers
  adicionais bloqueiam vínculos cruzados mesmo por acesso direto ao SQLite;
- comprovantes de proposta, esclarecimento, recurso, habilitação, contrato ou lance armazenam arquivo,
  portal, protocolo, horário, SHA-256 e autor. São append-only: atualização e exclusão são recusadas pelo
  banco; upload e download entram na auditoria, e o arquivo permanece limitado a 10 MB e aos formatos
  seguros já reconhecidos pelo servidor;
- o detalhe do edital ganhou `static/js/modules/tender-control.js` e
  `static/theme/tender-control.css`, mantendo edição conforme `triage_tenders`, alvos de 44 px, layout de
  uma coluna no celular e `prefers-reduced-motion`. O cache PWA passou para
  `sivs-v2.2.0-tender-control-78`;
- para o futuro robô de lances foi escolhida VPS Linux AMD64 separada, com worker Python e Chrome oficial
  do Selenium em contêineres distintos. A imagem está fixada por versão, usa 2 GB de `/dev/shm`, uma única
  sessão, perfil persistente exclusivo, WebDriver não publicado e noVNC restrito a localhost/túnel SSH;
- `tools/tender_portal_worker.py` agora aceita Selenium remoto e fila contínua, trata indisponibilidade de
  rede e impede dois processos de usarem o mesmo perfil. O `compose.yaml` inicia sem
  `--allow-external-effects`; `PLACE_BID` e `SUBMIT_PROPOSAL` continuam recusados até existir adaptador de
  portal homologado, política armada, autorização escrita e liberação explícita também no servidor;
- Windows é contingência somente se um portal provar dependência exclusiva. A aplicação web continua no
  Dokploy e o navegador não compartilha processo, rede pública ou armazenamento do SQLite. Procedimento e
  requisitos estão documentados em `tools/tender-agent/README.md` e `DOKPLOY.md`;
- validação final aprovada: 141 de 141 testes, incluindo migration, conflito de revisão, isolamento
  multiempresa, risco crítico, comprovante imutável e download com hash; simulação operacional integral
  com 22 cenários; auditoria mobile em 390 px com 3 telas e 10 interações sem overflow ou falha;
  compilação Python, sintaxe JavaScript, YAML e `git diff --check`. A composição Docker foi revisada
  estaticamente; Docker não está instalado no ambiente Windows atual, portanto o pull e o smoke test dos
  contêineres ficam para a VPS de homologação.

### 25/08/2026 — centro administrativo de equipe e prioridades operacionais

- o Centro de Controle, acessível somente a administradores, passou a reunir uma fila operacional formada por
  aprovações pendentes, prazos vencidos ou dos próximos sete dias e itens sem responsável informado. Cada
  entrada abre diretamente o registro, sem duplicar dados ou criar uma lista paralela de tarefas;
- a visão de equipe mostra todas as associações ativas e inativas da empresa, perfil, quantidade efetiva de
  módulos para consulta e edição, atividade recente e caminho direto para a gestão de usuários. A base
  continua uma única unidade operacional: permissões são por empresa, usuário, módulo e função;
- os dados são agregados exclusivamente no servidor a partir de `company_memberships`, sessões, auditoria,
  aprovações e registros existentes. Nomes de responsável vindos de cadastros são explicitamente apresentados
  como “responsável informado”, pois ainda não são um vínculo relacional de pessoa; isso evita alegar uma
  atribuição que o banco não comprovou;
- cache PWA atualizado para `sivs-v2.2.0-admin-operations-79`. Testes cobrem o escopo administrativo,
  equipe, prazo vencido, aprovação pendente, abertura direta e contrato responsivo/acessível do painel.
  Validação final: 141 testes aprovados, checagem de sintaxe Python/JavaScript, simulação de imagens e
  auditoria mobile rápida com zero falhas de overflow ou interação.
### 25/08/2026 — acompanhamento visual protegido do agente de portal

- o detalhe da licitação passou a oferecer **Assistir sessão ao vivo**, permitindo que operadores acompanhem
  o navegador da VPS sem usar terminal Linux; a tela é responsiva, acessível por teclado e pode ser fechada
  sem interromper a execução;
- o SIVS nunca monta URL a partir de entrada do usuário. O viewer só é habilitado quando
  `SIVS_TENDER_AGENT_VIEWER_URL` aponta para HTTPS sem credenciais, fragmento ou porta não-padrão. Cada
  abertura é verificada pela empresa da licitação, exige permissão de visualizar valores e entra na auditoria;
- a URL precisa ser de um gateway protegido por autenticação corporativa e em modo somente-leitura. A porta
  noVNC `:7900` continua ligada somente a `127.0.0.1`; ela não pode ser colocada nessa variável, exposta
  diretamente na internet ou usada como forma de controle remoto por observadores;
- enquanto o gateway não existir, a interface informa que a visualização ainda está sendo configurada e a
  operação permanece segura. O procedimento de infraestrutura foi documentado em `DOKPLOY.md` e
  `tools/tender-agent/README.md`.

### 25/08/2026 — viewer read-only pronto para a VPS do agente

- a composição do agente agora inclui `viewer`, que serve somente a última captura PNG gravada pelo worker,
  e `viewer-proxy`, que publica apenas HTTPS por Caddy. O noVNC e o WebDriver continuam sem exposição pública;
- o SIVS gera ticket HMAC de cinco minutos por usuário, empresa e licitação antes de abrir o iframe. O viewer
  verifica a assinatura com `SIVS_TENDER_AGENT_VIEWER_SECRET`, não oferece qualquer rota de comando e não
  recebe teclado ou mouse; assim, assistir não interfere no robô;
- para ativar após montar a VPS basta apontar o DNS de `SIVS_TENDER_AGENT_VIEWER_DOMAIN`, manter o mesmo
  segredo do viewer no Dokploy e na VPS, e configurar `SIVS_TENDER_AGENT_VIEWER_URL=https://<domínio>/` no
  Dokploy. A confirmação de pausa e a futura sessão manual permanecem fluxos separados e auditáveis.
### 26/08/2026 — catálogo documental ampliado e independente por edital

- o catálogo corporativo de documentos de licitações foi ampliado para abranger habilitação jurídica,
  fiscal/social/trabalhista, econômico-financeira, garantias, qualificação técnica, sustentabilidade,
  declarações, proposta, cronograma e contratação;
- o catálogo serve como biblioteca reutilizável, mas não presume que tudo seja exigido. A checklist do edital
  continua selecionando apenas os documentos aplicáveis e aceita exigências customizadas sem alteração de código;
- a capacidade da checklist foi ampliada para 160 itens por edital, preservando validação de empresa, tipo,
  escopo, validade, hash, permissão e auditoria no servidor.
## 26/08/2026 — aba do edital personalizada e leitura interna

O detalhe de cada resultado de licitação passou a usar somente os dados oficiais do resultado atual (objeto, órgão, localização, identificador, prazos, valor, amparo legal, documentos e itens), com rótulos de fonte e data da última sincronização para evitar mistura entre editais. A lista de documentos agora é um hub primário do edital, com cartões individualizados e a ação `Ver no sistema`.

O visualizador usa o endpoint já protegido por `company_id`, validação de URL oficial PNCP, limite de tamanho e `X-SIVS-Previewable`; o navegador recebe um Blob same-origin em diálogo acessível, mantendo download e abertura em nova aba apenas como alternativas. Formatos não visualizáveis continuam com fallback de download. O layout foi responsivado para telas estreitas e respeita os controles existentes de teclado e `prefers-reduced-motion`.

### 26/08/2026 — pendências do painel com causa e próxima ação

- os itens de **Meu trabalho** passaram a separar visualmente a **Pendência identificada** da **Próxima ação**, evitando que um prazo crítico seja apresentado como se explicasse por si só o trabalho pendente;
- em licitações, a orientação agora considera a etapa registrada (captação, análise, documentação, proposta enviada, disputa ou habilitação), com instrução concreta para avançar, acompanhar ou encerrar o certame;
- o prazo passa a ser nomeado como **prazo crítico** e a etapa atual continua visível. Dados, permissões, isolamento por empresa, abertura direta do registro, teclado, toque e movimento reduzido foram preservados.
