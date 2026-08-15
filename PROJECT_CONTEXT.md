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

### Como atualizar

Acrescente data, objetivo, arquivos impactados, decisões, testes executados e riscos restantes.
Não apague histórico relevante; marque itens substituídos e explique a nova decisão.
