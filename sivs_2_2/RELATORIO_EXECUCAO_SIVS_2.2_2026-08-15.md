# Relatório de execução da auditoria — SIVS SECCOL 2.2

**Data da execução:** 15/08/2026  
**Base preservada:** SIVS 2.1  
**Versão resultante:** SIVS 2.2.0  
**Escopo:** segurança, multiusuário, integridade, continuidade, editais, cadastros relacionais, normas, laudos/estudos/certificados, interface e testes.

## 1. Resultado executivo

A versão 2.2 transforma os principais achados críticos da auditoria em controles executáveis. A versão 2.1 não foi sobrescrita: a implementação foi feita em uma cópia independente.

O sistema agora possui:

- autorização separada para leitura, escrita e exportação;
- validação real no servidor para os 46 formulários especializados;
- transações atômicas nos fluxos críticos e bloqueio de sobrescrita concorrente;
- backup de desastre integral, verificado e criptografado;
- aprovação com segregação de função e vínculo à revisão exata do registro;
- trabalhos persistentes e progresso real na busca de editais;
- execução automática dos planos diários e semanais enquanto o servidor está ativo;
- emissão PDF controlada de certificados, laudos e estudos, fundamentada em normas vinculadas;
- anexos com verificação de formato, licença e SHA-256;
- 21 testes automatizados, incluindo cenários hostis e concorrentes.

Não se declara uma melhora numérica de “100 vezes”, pois não existe métrica-base capaz de sustentar essa afirmação. A melhora é demonstrada por controles implementados, testes reproduzíveis e redução objetiva das classes de falha listadas abaixo.

## 2. Matriz de execução dos achados

| Tema auditado | Situação anterior | Implementação 2.2 | Estado |
|---|---|---|---|
| Primeira configuração | Verificação e criação separadas, vulneráveis a corrida | `BEGIN IMMEDIATE`, `setup_state`, nova verificação dentro da transação e teste simultâneo | Resolvido |
| Autorização de leitura | Perfil podia alcançar dados fora do menu | `ROLE_READ_MODULES`, permissões por empresa e verificação em registros, anexos, editais, painel e relações | Resolvido |
| Escrita e exportação | Regras parcialmente acopladas ao front-end | matrizes independentes de leitura/escrita/exportação e capacidades administrativas | Resolvido |
| Validação | Obrigatoriedade concentrada no navegador | validação no servidor de campos, assunto, tipos, datas, horas, finitos, CPF/CNPJ, URL, e-mail, status e relações | Resolvido |
| JSON não finito | `Infinity`/`NaN` podiam chegar ao banco/resposta | parser e serializador JSON estritos, com erro controlado | Resolvido |
| Falha não tratada | Conexão podia terminar sem resposta coerente | despachante global com resposta sanitizada e identificador de suporte | Resolvido |
| Tamanho de requisição | Limite único e insuficiente | limites distintos para registros, anexos, importação e backup | Resolvido |
| Concorrência de edição | Última gravação sobrescrevia a anterior | campo `revision`, atualização condicional e erro `write_conflict` | Resolvido |
| Gravação parcial | Registro e relações podiam divergir | transações atômicas em cadastros, restauração, aprovações, usuários, empresas, configurações e conversão de edital | Resolvido |
| Importação NF-e | Podia deixar cadastros derivados parciais | transação longa controlada, validação de chave/documento, XML com hash e rollback integral | Resolvido |
| Relacionamentos | Prefixo do módulo não era conferido contra o alvo | validação de módulo, ID, empresa, exclusão e autorrelacionamento | Resolvido |
| Financeiro no painel | Risco de somar o mesmo fato em módulos sobrepostos | razão principal em Financeiro; Caixa usado somente como fallback | Resolvido |
| Aprovações duplicadas | Mais de uma pendência equivalente | índice único parcial e resposta de conflito | Resolvido |
| Autoaprovação | Solicitante podia participar da própria decisão | solicitante e aprovador obrigatoriamente distintos | Resolvido |
| Aprovação obsoleta | Decisão não vinculada ao conteúdo aprovado | `record_revision`; alteração/exclusão expira pendências | Resolvido |
| Anexos | Confiança no MIME informado e download pouco auditado | detecção por conteúdo, bloqueio de executáveis, SHA-256, permissão por módulo e auditoria de download | Resolvido |
| Normas comerciais | Confirmação apenas visual | confirmação obrigatória no servidor para “Cópia normativa licenciada” | Resolvido |
| Metadado ISO 14644-4 | Edição incorreta no catálogo | corrigido para 2ª edição, 2022 | Resolvido |
| Fonte Transparência | Integração descrita de forma ambígua | classificada como consulta manual, com API apenas planejada | Resolvido |
| Backup | Exportação JSON incompleta e em texto claro | snapshot SQLite completo, `integrity_check`, PBKDF2 e AES-256-GCM | Resolvido |
| Restauração | Sem procedimento seguro de desastre | utilitário offline, autenticação, integridade, tabelas obrigatórias e cópia anterior recuperável | Resolvido |
| Sessões em backup | Risco de replay após restauração | sessões ativas removidas do artefato criptografado | Resolvido |
| Busca de editais | Requisição síncrona e progresso estimado | trabalho persistente, progresso registrado, polling, deduplicação e bloqueio de simultaneidade | Resolvido |
| Planos de busca | Guardavam a próxima data, mas não executavam | agendador interno diário/semanal e registro de interrupção | Resolvido enquanto servidor ativo |
| Conversão em licitação | Operações separadas e dados possivelmente incompletos | validação especializada e transação única | Resolvido |
| Laudos e estudos | Cadastro estruturado, sem geração documental | prévia PDF, emissão controlada, base normativa, aprovação, licença, hash e arquivamento | Resolvido no escopo documental local |
| Erro de recurso estático | Caminho inexistente devolvia a aplicação | arquivos inexistentes devolvem 404 | Resolvido |
| Exposição de versão | Cabeçalho revelava o runtime Python | cabeçalho reduzido a SIVS/versão | Resolvido |
| Rede sem TLS | Possibilidade de publicar HTTP diretamente | bind não local recusado sem proxy seguro ou exceção explícita | Mitigado por configuração |

## 3. Segurança e multiusuário

### 3.1 Perfis e isolamento

Os oito perfis permanecem disponíveis: administrador, gestor, operador, consulta, técnico, qualidade, fiscal/financeiro e aprovador. A associação continua sendo feita por empresa, e a coluna `permissions` permite ampliações ou negações explícitas de `read`, `write`, `export`, `deny_read`, `deny_write` e `deny_export`.

O front-end recebe somente os módulos legíveis e oculta telas, atalhos e exportações sem autorização. A API continua sendo a autoridade: ocultar o menu não é tratado como mecanismo de segurança.

### 3.2 Sessão e rede

- cookie `HttpOnly`, `SameSite=Strict` e `Secure` quando HTTPS é declarado;
- CSRF obrigatório em operações de alteração;
- rate limit em login e configuração inicial;
- confiança em `X-Forwarded-For` e `X-Forwarded-Proto` somente com `SIVS_TRUST_PROXY=1`;
- recusa de interface não local sem proxy HTTPS configurado ou `--allow-insecure-network` explícito;
- cabeçalhos de cache, frame, MIME, referência, permissões e isolamento de janela.

## 4. Integridade cadastral e relacional

Os 46 esquemas de cadastro mantêm o desenho especializado, porém a obrigatoriedade deixou de depender do navegador. Assunto principal, campos específicos, dados fiscais, documentos, datas, números e relações são conferidos novamente no servidor.

Cada alteração preserva uma versão anterior e incrementa `revision`. Se dois usuários editarem a mesma revisão, apenas a primeira atualização é aceita. A segunda recebe conflito e deve recarregar o registro.

## 5. Editais e fontes

O catálogo continua com 38 fontes. O escopo automático declarado permanece limitado às integrações oficiais implementadas:

- PNCP como fonte principal;
- Dados Abertos do Compras.gov.br como contingência;
- demais portais como consulta manual em um clique;
- CNES e ANAHP como prospecção privada, não como editais.

A pesquisa manual agora retorna `202 Accepted`, cria um registro em `tender_jobs` e continua fora da conexão HTTP. A interface consulta o progresso persistido. Um índice parcial impede duas pesquisas ativas na mesma empresa.

Planos diários e semanais são processados pelo agendador interno a cada ciclo. Se o processo do servidor estiver desligado, nenhuma pesquisa ocorre naquele período; quando ele volta, o plano é reavaliado e novamente programado.

## 6. Normas, certificados, laudos e estudos

O catálogo inicial contém 18 referências e fichas autorais de controle. Os arquivos incorporados não reproduzem textos integrais protegidos.

O fluxo documental implementado é:

1. cadastrar certificado, laudo ou estudo com assunto e campos técnicos;
2. relacionar ao menos uma norma vigente;
3. anexar a cópia licenciada quando a referência for comercial;
4. solicitar aprovação;
5. um usuário diferente, elegível, aprova a revisão atual;
6. gerar o PDF controlado;
7. arquivar o PDF com revisão, SHA-256, aprovação e normas na auditoria.

A prévia possui marca d’água e não pode ser confundida com emissão final. O PDF final é um documento técnico local e ainda depende das responsabilidades profissionais, assinatura aplicável, ART/RRT quando exigida, contrato, método, incerteza e regra de decisão definidos pela SECCOL.

## 7. Backup e recuperação

### Formato

`SIVS-BACKUP-2` contém um snapshot SQLite consistente, precedido por cabeçalho autenticado. A chave é derivada da senha com PBKDF2-HMAC-SHA256 (600.000 iterações) e o conteúdo é cifrado/autenticado com AES-256-GCM.

### Restauração

Com o servidor parado:

```bash
python3 restore_backup.py backup.sivsbackup --database data/sivs.db --verify-only
python3 restore_backup.py backup.sivsbackup --database data/sivs.db --force
```

A segunda operação preserva o banco anterior com sufixo `before-restore-AAAAMMDD-HHMMSS`.

## 8. Evidência de testes

Comando executado:

```bash
python3 -m unittest discover -s tests -v
```

Resultado: **21 testes aprovados**.

Cobertura funcional verificada:

- inicialização e catálogos por empresa;
- senha e persistência;
- relações isoladas e migração de assuntos;
- base normativa obrigatória;
- portfólio SECCOL;
- API multiempresa e segurança XML;
- corrida de configuração inicial;
- autorização de leitura;
- rejeição de `Infinity` e sobrevivência da conexão;
- conflito otimista de edição;
- importação transacional malformada;
- segregação, duplicidade e expiração de aprovação;
- backup criptografado, descriptografia e `integrity_check`;
- trabalho persistente de edital e progresso;
- prévia e emissão PDF controlada;
- 404 de arquivo estático;
- contrato dos 46 formulários e ausência de IDs HTML duplicados.

Validações adicionais executadas:

```bash
python3 -m py_compile server.py launcher.py restore_backup.py
node --check static/app.js
```

## 9. Riscos residuais e próximos blocos

Estes itens não devem ser apresentados como concluídos:

1. **HTTPS:** o pacote impede exposição acidental, mas certificado, domínio e proxy reverso pertencem ao ambiente de implantação.
2. **Normas integrais:** cópias comerciais não são distribuídas; a SECCOL deve anexar arquivos obtidos por licença válida.
3. **Assinatura qualificada:** aprovação SIVS e SHA-256 não equivalem a assinatura ICP-Brasil nem substituem responsabilidade profissional.
4. **Modelo técnico:** o template PDF é parametrizado, mas deve ser homologado pelo responsável técnico e pela qualidade antes de uso oficial.
5. **Fiscal/SEFAZ:** permanece fila local até existir conector homologado, credenciais, certificados e testes externos.
6. **Mobile offline:** a tela móvel é responsiva e atualiza a mesma O.S., porém não possui fila offline, captura geográfica ou assinatura de cliente.
7. **MFA e recuperação de senha:** ainda não implementados.
8. **Escala horizontal:** SQLite atende uma instalação central de pequeno/médio porte; múltiplas instâncias simultâneas exigem migração para banco servidor e coordenação de trabalhos.
9. **Privacidade/LGPD:** controles técnicos existem, mas política, base legal, retenção, atendimento ao titular e governança organizacional continuam sendo obrigações da empresa.
10. **Fontes manuais:** não foram convertidas em scraping; qualquer automação futura deve respeitar API, autenticação, termos de uso e estabilidade da fonte.

## 10. Critério de liberação recomendado

Antes da produção:

- instalar dependências com `pip install -r requirements.txt`;
- homologar o template de laudo/certificado/estudo;
- anexar as normas licenciadas usadas nas emissões;
- configurar HTTPS e cookies seguros;
- criar usuários por função e revisar permissões;
- executar um backup, verificar e restaurar em ambiente separado;
- testar PNCP/Compras.gov a partir da rede de produção;
- executar os 21 testes e registrar a evidência;
- realizar piloto com dados não sensíveis antes da migração oficial.
