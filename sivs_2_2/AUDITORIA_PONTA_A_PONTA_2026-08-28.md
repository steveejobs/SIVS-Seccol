# Auditoria ponta a ponta do SIVS SECCOL 2.2

Data: 28/08/2026  
Escopo: código, banco, APIs, permissões, multiempresa, auditoria, domínios funcionais, PWA,
responsividade, dependências e operação de produção.

## Parecer executivo

O SIVS possui uma base interna acima da média para um sistema em evolução: 185 testes automatizados
passam, o banco novo apresenta integridade referencial, os fluxos críticos são transacionais, as
consultas de relatórios são isoladas por empresa e a matriz visual passou em 232 telas. Não foi
reproduzido vazamento multiempresa, bypass de autorização, divergência de centavos nos relatórios ou
falha funcional nos 22 cenários da simulação operacional.

O parecer, porém, é **aprovação condicionada**, não aprovação integral de produção. Há dois riscos de
engenharia que precisam de correção antes da liberação ampla: o servidor processa PDFs externos com
`pypdf 5.9.0`, versão afetada por vulnerabilidades de indisponibilidade, e os perfis-base Operador e
Consulta concedem acesso muito mais amplo que o princípio do menor privilégio. Há ainda bloqueios de
homologação que não podem ser substituídos por testes locais: A1/SEFAZ real, restauração de backup
externo, portais de licitação, canais públicos e obrigações trabalhistas.

## Dimensão real inspecionada

- 53 módulos funcionais e 455 ações granulares;
- 9 perfis-base de acesso;
- 55 despachos principais de rota, 119 caminhos literais de API e 409 métodos no `SIVSHandler`;
- 479 funções e métodos Python no servidor completo;
- 99 tabelas, 101 gatilhos, 96 índices e migrações até a versão 260;
- `server.py` com 26.819 linhas/1,53 MB e `static/app.js` com 4.220 linhas/326 KB;
- 185 testes automatizados;
- 232 combinações de tela e 41 interações em navegador real.

## Evidências executadas

| Verificação | Resultado |
|---|---|
| suíte Python integral | 185/185 testes aprovados em 106,47 s |
| simulação operacional | 22/22 cenários aprovados em 33,52 s |
| integridade SQLite | `integrity_check=ok`; zero violações de chave estrangeira |
| relatório de carga | 120 mil linhas; consultas em 398,8 ms; oito leitores em 2,44 s |
| navegador responsivo | 232 telas, 41 interações, zero overflow/falha |
| sintaxe | Python e 33 arquivos JavaScript aprovados |
| dependências instaladas | `pip check` sem conflitos |
| auditor de interações completo | bloqueado por contrato antigo de categoria no próprio utilitário |

O último item é um defeito da ferramenta `tools/audit_interactions.py`: ela ainda envia o texto
legado `categoria`, enquanto a API exige corretamente `categoria_id`. A navegação pelas 58 telas
ocorreu antes da interrupção, e o modo reduzido do auditor passou, mas o percurso completo precisa ser
atualizado e reexecutado.

## Matriz ponta a ponta

| Área | Parecer | Evidência | Limite restante |
|---|---|---|---|
| autenticação e sessões | aprovado localmente | PBKDF2-SHA256, comparação constante, CSRF, cookie HttpOnly/Strict, expiração e rate limit | não existe MFA para contas administrativas |
| recuperação de senha | aprovado localmente | token único com hash, expiração de 30 min e revogação de sessões | SMTP real depende do ambiente |
| empresas e isolamento | aprovado | escopo por `company_id`, vínculos indiretos protegidos e testes cruzados | manter testes obrigatórios em toda nova tabela |
| permissões | mecanismo aprovado, padrão reprovado | validação no servidor e 455 ações configuráveis | Operador e Consulta partem de acesso amplo demais |
| auditoria e observabilidade | aprovado | ações críticas, eventos sanitizados, sessões e falhas registradas | ausência de alerta externo/SIEM e política operacional comprovada |
| cadastros e relacionamentos | aprovado | documentos únicos, assuntos, anexos, versões e vínculos multiempresa | conferência da qualidade dos dados continua operacional |
| CRM, site e WhatsApp | aprovado em teste | HMAC, idempotência, segregação e webhooks testados | publicar e homologar canais e templates reais |
| comercial, vendas, compras e O.S. | aprovado no escopo | itens, revisão, aprovação, execução e reflexos testados | cenários empresariais avançados ainda exigem parametrização |
| estoque | aprovado | ledger, concorrência, reserva, transferência, baixa e custo médio | inventário físico real precisa de homologação operacional |
| financeiro e contabilidade | aprovado no escopo atual | baixas parciais, rateios, competência, partidas e fechamento testados | banco/CNAB/conciliação externa não homologados |
| qualidade e normas | aprovado | vigência, licença, revisão, base normativa e emissão controlada | validação técnica e licença permanecem responsabilidade humana |
| licitações e IA | aprovado localmente | coleta, documentos, citações, proposta, aprovação, agente governado e falhas explícitas | PDFs vulneráveis; portais, OCR e IA precisam de teste real |
| Fiscal/NF-e | homologação técnica parcial | XML 4.00, XSD, assinatura, numeração, SOAP e autorização simulada/testada | produção, A1 real, CC-e, cancelamento, inutilização, contingência e grupos IBS/CBS não liberados |
| RH, ponto e folha | núcleo parcial confiável | AFD/CSV, marcações imutáveis, jornada, prévia, folha 2026 e exportações testados | sem P7S no AEJ, eSocial, DCTFWeb, FGTS Digital, férias, 13º, rescisão, adicionais e CCT |
| relatórios | aprovado | oito fontes, totais exatos, permissões, exportação e carga concorrente | catálogo governado; não é consulta SQL arbitrária |
| backup e restauração | aprovado localmente | snapshot, backup cifrado e arquivo restaurado com integridade | restauração a partir de destino externo continua P0 operacional |
| deploy | desenho aprovado | contêiner sem segredos no build, usuário sem privilégio e volume obrigatório | confirmar HTTPS, HSTS no proxy, uma réplica e backups no ambiente real |
| PWA e acessibilidade | aprovado na automação | teclado, toque, movimento reduzido e quatro larguras | requer validação humana com leitor de tela e zoom |

## Achados priorizados

### P0 operacional — restauração externa não comprovada

O backup cifrado e o snapshot local são válidos, mas ambos podem ser perdidos junto com o host ou
volume. Produção não deve ser considerada recuperável sem backup externo automatizado e pelo menos um
ensaio documentado de restauração completa.

### P1 segurança — `pypdf 5.9.0` processa conteúdo externo vulnerável

O sistema baixa até 20 MB por documento de domínios PNCP permitidos e chama `PdfReader(...,
strict=False)` para extrair texto e imagens. A versão instalada, 5.9.0, é afetada por várias falhas de
consumo excessivo de CPU/memória. A faixa atual `pypdf>=5,<6` impede instalar qualquer versão corrigida:
as correções relevantes começaram na linha 6.6/6.7 e novas correções foram publicadas em agosto de
2026. Limitar bytes, páginas e imagens reduz impacto, mas não limita o custo interno do parser.

Correção requerida: migrar para a linha 6 atual corrigida, adaptar contratos, adicionar PDFs
malformados de regressão e executar a extração fora do processo HTTP com limites de tempo e memória.
Até lá, desabilitar a análise automática de PDF externo em produção reduz a exposição.

Referências primárias:

- <https://github.com/py-pdf/pypdf/security/advisories/GHSA-4f6g-68pf-7vhv>
- <https://github.com/py-pdf/pypdf/security/advisories/GHSA-wgvp-vg3v-2xq3>
- <https://github.com/py-pdf/pypdf/security/advisories>

### P1 governança — perfis-base não seguem menor privilégio

O perfil Operador escreve em 45 dos 53 módulos. O perfil Consulta lê 52 dos 53 e recebe, por padrão,
`view_values` em áreas financeiras e fiscais. As permissões personalizadas conseguem restringir isso e
o servidor as aplica corretamente, mas um cadastro que aceite o perfil-base sem revisão nasce amplo.

Correção requerida: criar presets por função empresarial, negar valores sensíveis por padrão, exibir
uma revisão obrigatória antes de ativar a conta e adicionar teste de snapshot para cada preset.

### P1 qualidade — contratos de API sem teste dedicado

Dos 119 caminhos literais internos/externos identificados, 101 aparecem diretamente nos testes. Entre
os contratos internos sem teste dedicado estão exportação genérica, eventos Fiscal/RH, logout,
notificações em lote, assuntos, restauração, histórico de editais e operações de instância/respostas
rápidas do WhatsApp. Parte da lógica subjacente é testada indiretamente; isso não substitui o teste do
contrato HTTP, CSRF, permissão, empresa e auditoria de cada rota.

### P1 qualidade — auditor de navegador desatualizado

O utilitário de auditoria integral não acompanha a migração da categoria financeira textual para
`categoria_id`. Isso impede que a própria evidência de navegador seja reproduzida em uma única
execução limpa e deve ser corrigido antes do próximo aceite.

### P1 cadeia de fornecimento — ambiente sem verificador de CVEs e sem CI

`pip check` comprova consistência, não ausência de vulnerabilidades. Não há workflow de CI versionado
nem evidência de `pip-audit`/OSV no pipeline. As dependências usam intervalos, sem lock reproduzível ou
hashes. O Pillow instalado é 12.2.0 e possui correções de segurança na 12.3.0; no SIVS seu uso direto
está restrito ao utilitário de otimização de imagens, reduzindo a exposição do servidor, mas o ambiente
de desenvolvimento ainda deve ser atualizado.

### P2 manutenção — backend e frontend monolíticos

`server.py` concentra 1,53 MB e 409 métodos do handler; `app.js` ainda possui 326 KB apesar dos novos
módulos extraídos. O desenho funciona, mas aumenta o custo de revisão função por função, risco de
conflito e chance de uma rota nova omitir autorização/auditoria. A decomposição deve ser incremental,
por domínio, preservando os contratos de IDs e a suíte atual.

### P2 defesa em profundidade — cabeçalhos dependem do proxy

O aplicativo envia CSP, anti-frame, no-sniff, referrer e permissions policy. HSTS não é enviado pelo
servidor e precisa ser garantido no proxy HTTPS. A CSP ainda permite estilo inline, compatível com a
interface atual, mas deve ser reduzida progressivamente.

## Dependências

| Pacote instalado | Parecer |
|---|---|
| cryptography 46.0.7 | corrigido para a falha que afetava versões anteriores a 46.0.7 |
| pypdf 5.9.0 | reprovado para conteúdo não confiável; faixa do projeto impede correções atuais |
| ReportLab 4.5.1 | geração interna de PDF; acompanhar correções e planejar migração para 5 |
| Pillow 12.2.0 | atualizar ambiente para 12.3.0; uso direto atual é ferramenta de desenvolvimento |
| lxml/openpyxl/defusedxml | sem conflito instalado; XML externo usa validação defensiva |

## Critério de aceite recomendado

Antes de liberar o sistema como plataforma empresarial integral:

1. corrigir `pypdf`, isolar o parser e rodar regressões de PDFs hostis;
2. substituir os perfis-base amplos por presets aprovados pelo responsável de cada área;
3. corrigir e aprovar o auditor integral de navegador;
4. adicionar CI com suíte, sintaxe, contratos, auditoria de dependências e artefatos de resultado;
5. executar restauração real de backup externo;
6. homologar separadamente cada integração externa e cada obrigação Fiscal/RH ainda declarada como
   limite;
7. manter produção NF-e bloqueada até assinatura formal fiscal/contábil e matriz real de rejeições.

## Nota final

- qualidade do núcleo implementado: **8,4/10**;
- segurança interna e isolamento: **8,2/10**;
- confiabilidade dos testes locais: **8,7/10**;
- prontidão operacional externa: **5,8/10**;
- completude como ERP Fiscal/RH integral: **5,5/10**;
- parecer global atual: **7,4/10 — bom sistema, aprovação condicionada**.

As notas distinguem qualidade de código de completude legal e operacional. Nenhum teste local pode
certificar sozinho conformidade tributária, trabalhista, disponibilidade de terceiros ou capacidade
de recuperação após desastre.
