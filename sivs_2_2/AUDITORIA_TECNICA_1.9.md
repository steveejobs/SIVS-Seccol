# Auditoria técnica do SIVS 1.9

Data: 15/08/2026  
Escopo: arquitetura local, banco, autenticação, permissões, relacionamentos, backup, fontes de editais e interface.

## Resumo executivo

A versão anterior funcionava como aplicação local multiusuário, mas o relacionamento de assuntos estava armazenado somente dentro do JSON dos registros. Isso não garantia integridade referencial. A versão 1.9 cria tabelas próprias para assuntos e vínculos, migra os dados existentes e introduz uma Central de Assuntos.

Também foram corrigidas permissões excessivas em configurações, importação e backup completo. O backup passou a remapear os identificadores durante a restauração, preservando os vínculos entre módulos.

## Matriz de constatações

| Prioridade | Constatação | Situação final | Evidência |
|---|---|---|---|
| Alta | Relacionamentos existiam apenas em JSON | Corrigido | `subjects`, `records.subject_id` e `record_relationships` |
| Alta | Backup anterior não reconstruía relações com IDs diferentes | Corrigido | restauração entre dois bancos distintos aprovada |
| Alta | Operadores podiam alterar configurações e importar backup | Corrigido | proteção administrativa no servidor |
| Alta | Era possível comprometer o último administrador | Corrigido | bloqueio de desativação e despromoção |
| Média | Não existia visão consolidada por assunto | Corrigido | Central de Assuntos e endpoints dedicados |
| Média | Exportação completa permitia perfil não administrativo | Corrigido | teste HTTP retornou 403 para consulta |
| Média | Cabeçalhos de segurança estavam incompletos nos arquivos estáticos | Corrigido | CSP, X-Frame-Options e Referrer-Policy |
| Média | Testes não cobriam relações e migração | Corrigido | suíte ampliada para 6 testes automatizados |
| Média | Ciclos indiretos entre relações ainda não são bloqueados | Pendente | autorrelacionamento é bloqueado; ciclos complexos exigem grafo |
| Média | Isolamento por empresa/workspace não existe | Pendente | multiusuário atual utiliza uma única empresa/banco |
| Baixa | Renderização automatizada não pôde ser executada neste ambiente | Pendente | navegador Playwright não instalado |
| Baixa | Instalação Windows não foi executada em Windows real | Pendente | scripts revisados; validação real ainda necessária |

## Testes executados

### Automatizados

- compilação de `server.py` e `launcher.py`: aprovada;
- validação sintática de `static/app.js`: aprovada;
- 6 testes unitários: aprovados;
- persistência SQLite e catálogo de fontes: aprovados;
- hash de senha: aprovado;
- vocabulário técnico SECCOL: aprovado;
- criação e deduplicação de assunto: aprovada;
- vínculo Cliente → Frota: aprovado;
- autorrelacionamento: rejeitado corretamente;
- migração executada duas vezes: aprovada sem duplicação.

### Integração HTTP

- configuração inicial e sessão administrativa: aprovadas;
- criação de usuário de consulta: aprovada;
- tentativa de escrita pelo perfil consulta: bloqueada com HTTP 403;
- tentativa de backup completo pelo perfil consulta: bloqueada com HTTP 403;
- criação de assunto e vínculo entre módulos: aprovada;
- listagem e detalhe da Central de Assuntos: aprovados;
- exportação `SIVS-2`: aprovada;
- restauração em banco distinto: aprovada;
- configurações, assuntos e relacionamentos restaurados: aprovados.

### Pesquisa externa real

Consulta executada para GO, últimos 3 dias, modalidade de dispensa e termos de cabine de segurança biológica, filtros HEPA e fluxo laminar:

- duração: 16 segundos;
- PNCP: concluído;
- Compras.gov: não acionado, pois a fonte principal respondeu;
- páginas verificadas: 4 de 4;
- oportunidades aderentes: 0;
- classificação: busca aprovada, sem aderência no recorte testado.

Zero oportunidade não foi interpretado como falha, porque a fonte respondeu e as páginas foram efetivamente processadas.

## Limitações confirmadas

1. O sistema é multiusuário em uma única empresa, mas ainda não é multiempresa ou multitenant.
2. PNCP e Compras.gov são os conectores automáticos; as demais fontes permanecem manuais ou de prospecção.
3. Assuntos podem receber múltiplos vínculos, mas união, separação e detecção de ciclos indiretos ainda não possuem interface completa.
4. A instalação Windows deve ser validada em computador Windows real.
5. A inspeção visual automatizada deve ser repetida quando houver navegador de testes disponível.

## Próxima etapa recomendada

Implementar o ciclo de vida completo do assunto: renomear, arquivar, unir duplicados, separar vínculos e apresentar cronologia de eventos. Depois, acrescentar isolamento por empresa/workspace com migração compatível.
