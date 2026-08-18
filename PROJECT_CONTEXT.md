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
