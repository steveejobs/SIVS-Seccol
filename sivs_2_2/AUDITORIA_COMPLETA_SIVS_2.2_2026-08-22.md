# Auditoria completa do SIVS SECCOL 2.2

Data de conclusão: 22/08/2026.

## Resultado executivo

O escopo já implementado está funcional e consistente com os contratos de segurança do projeto. A
validação final aprovou 97 testes automatizados, 55 telas em navegador real, 220 combinações
responsivas e 33 interações transversais. Não foram encontrados vazamento entre empresas, bypass de
permissão, overflow de documento ou erro JavaScript acionável nos percursos automatizados.

Isso não significa que todo o ERP futuro esteja implementado. Emissão de NF-e, recebimento parcial,
financeiro por competência e portabilidade integral continuam evoluções explícitas. Integrações com
SEFAZ, SMTP, OpenRouter, PNCP, CNPJá, ViaCEP e o site dependem também de credenciais, disponibilidade
externa e homologação operacional.

## Escopo levantado

- 50 módulos de domínio e 8 perfis-base de acesso;
- 55 destinos de navegação para o administrador;
- 254 funções e métodos Python no backend;
- aproximadamente 200 declarações funcionais no frontend principal;
- 97 testes de API, banco, segurança, concorrência e contratos de frontend;
- 24 arquivos JavaScript verificados sintaticamente;
- banco SQLite multiempresa com migrações até a versão 229.

## Matriz funcional

| Área | Situação | Evidência principal | Limite ou risco restante |
|---|---|---|---|
| Primeiro acesso, login e recuperação | Aprovado | setup atômico, login, token único, revogação de sessões e recuperação administrativa testados | SMTP precisa ser configurado e homologado em produção |
| Empresas, usuários e permissões | Aprovado | isolamento por empresa, troca de empresa, 411 funções renderizadas e autorização efetiva no servidor | revisar periodicamente privilégios reais por função |
| Clientes e fornecedores | Aprovado | CPF/CNPJ único, papéis C/F/A, vínculos por ID, CEP/CNPJ assistidos e regras financeiras testadas | consulta CNPJá depende de contrato e chave |
| CRM e leads do site | Aprovado localmente | HMAC, janela temporal, idempotência, rate limit, notificação e rejeição de adulteração testados | falta publicação e envio real de homologação Vercel → Dokploy |
| Propostas, vendas, compras e O.S. | Aprovado no fluxo atual | itens estruturados, estados, aprovação, reserva, baixa e recebimento integral testados | recebimento parcial e geração automática de títulos ainda não existem |
| Estoque e custeio | Aprovado | concorrência, micros, custo médio, reserva, transferência, baixa e isolamento testados | saldos históricos sem custo continuam sem valorização até ajuste documentado |
| Financeiro e controladoria | Parcial por desenho | valores, privacidade e consolidação gerencial testados | faltam parcelas/pagamentos estruturados, competência, conciliação, contas e centros de custo |
| Qualidade e documentos técnicos | Aprovado | base normativa, revisão, aprovação, prévia e emissão controlada testadas | conferência técnica e licenças normativas continuam humanas |
| Editais e IA | Aprovado de forma determinística | fontes, rate limit, precisão, documentos, qualidade de IA e falhas visíveis testados | índice textual PNCP não é contrato público; recall não é mensurado; OpenRouter exige chave |
| Fiscal e contabilidade | Fundação aprovada | cofre A1, prontidão, contrato SOAP, bloqueio de produção e pacote contábil testados | NF-e não implementada; exige A1 real, credenciamento, schemas e homologação tributária |
| Backup, restauração e lixeira | Aprovado localmente | snapshot pre-start, backup integral, persistência, restauração e exclusão confirmada testados | backup externo diário e ensaio de restauração fora do host permanecem P0 |
| PWA, responsividade e acessibilidade | Aprovado na automação | 220 telas, 33 interações, teclado, foco, drawer, toque e movimento reduzido | leitor de tela humano e auditoria periódica de contraste ainda são recomendados |

## Problemas encontrados e corrigidos

1. O teste do assistente usava a data fixa `20/08/2026` para uma consulta de sete dias e passou a
   falhar conforme o calendário avançou. O dado agora é relativo ao dia de execução.
2. `tools/optimize_images.py` falhava no console CP1252 do Windows ao imprimir `→`. A saída passou a
   usar `->`, preservando o modo de simulação e a compatibilidade entre plataformas.
3. `tools/responsive_audit.mjs` reutilizava perfil e portas fixos; uma execução interrompida podia
   bloquear a seguinte com `EPERM`. Cada rodada agora usa diretório e portas exclusivos, encerra a
   árvore do servidor, possui timeout CDP e agenda a limpeza tardia quando o Edge demora a liberar o
   perfil.
4. A camada de componentes anulava a proteção tipográfica das fundações e reduzia instruções de
   cadastro a 7–9 px. Rótulos, ajuda, navegação, tabelas e cartões centrais agora usam os tokens de
   11/12 px, mantendo a composição compacta, limpa e responsiva.
5. A PWA recebeu cache `sivs-v2.2.0-audit-legibility-49`, evitando CSS antigo após a correção visual.
6. O SIVS recebe XLSX não confiável. O próprio openpyxl informa que a proteção contra ataques XML
   exige `defusedxml`; a dependência foi incluída e protegida por teste. Fonte oficial:
   <https://pypi.org/project/openpyxl/>.
7. Tokens duplicados de texto foram consolidados sem alterar os valores resultantes.

## Direção visual adotada

A preferência registrada é por cores vivas e linguagem limpa inspirada em produtos Apple e Google.
O SIVS já segue boa parte dessa direção: Inter/system fonts, superfícies claras, cartões com raio
consistente, foco visível e laranja SECCOL como cor viva de ação. A auditoria preservou essa identidade
e melhorou a hierarquia textual, sem transformar o ERP em uma interface espaçada demais.

Próximos refinamentos visuais seguros:

1. substituir gradualmente ícones Unicode por um conjunto SVG interno consistente e acessível;
2. elevar a microtipografia restante de telas legadas por domínio, sempre com auditoria responsiva;
3. criar verificador automatizado de contraste dos tokens e estados;
4. extrair tabela, estados vazios e carregamento para componentes únicos;
5. reduzir o CSS e o JavaScript legados incrementalmente, sem reescrita ampla.

## Riscos priorizados

### P0 — operação

- implantar backup diário externo S3/compatível, com retenção e restauração ensaiada;
- homologar o webhook do site de ponta a ponta antes de liberar o formulário público;
- confirmar que `defusedxml` foi instalado no próximo build/deploy.

### P1 — produto e engenharia

- implementar recebimento parcial e financeiro estruturado antes de tratar o fluxo como ERP completo;
- criar sucessor do formato empresarial SIVS-3 que transporte ledger, itens e fundação fiscal;
- decompor `server.py` (aprox. 650 KB) e `app.js` (aprox. 245 KB) por domínio;
- planejar e testar migrações de versão: em 22/08/2026, PyPI já publicava cryptography 50,
  ReportLab 5 e pypdf 6, enquanto o projeto mantém majors anteriores por compatibilidade;
- homologar integrações reais apenas com segredos no runtime e dados de teste controlados.

### P2 — experiência

- completar a revisão de textos abaixo de 11 px ainda presentes em módulos legados;
- validar leitor de tela e zoom de 200% com pessoas reais;
- acompanhar tempo de carregamento por tela e orçamento de tamanho de ativos.

## Validações executadas

```text
python -m unittest discover -s sivs_2_2/tests -v        97/97 OK
python -m py_compile ...                                OK
node --check (24 JavaScript da aplicação + auditor)     OK
python tools/optimize_images.py ... --dry-run           OK
python tools/audit_interactions.py                      55 telas, login OK, errors=[]
node tools/responsive_audit.mjs                         220 telas, 33 interações, 0 falha
python -m pip check                                     OK
git diff --check                                        OK
```

Os testes externos reais que exigem A1, credenciamento SEFAZ, SMTP, OpenRouter, CNPJá ou publicação
Vercel/Dokploy não foram simulados como sucesso. Permanecem bloqueios operacionais explícitos.
