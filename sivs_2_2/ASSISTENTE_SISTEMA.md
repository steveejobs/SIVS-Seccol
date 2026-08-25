# Assistente do sistema — base, IA e manutenção

Documento vivo do Assistente do sistema. Atualize-o na mesma alteração sempre que forem modificados
o comportamento, a base de orientações, o provedor/modelo de IA, os limites, as permissões ou a
experiência de uso do assistente.

## Objetivo

O assistente orienta o uso do sistema e consulta somente dados que o usuário pode ler na empresa
ativa. Ele não grava registros, não altera permissões e não substitui as validações do servidor.

## Fontes de resposta

| Tipo de pergunta | Fonte prioritária | Comportamento esperado |
|---|---|---|
| Como usar, cadastrar, criar ou localizar uma função | Base interna verificada | Responde mesmo sem IA externa; não faz busca vazia por registros. |
| Resumo do cadastro aberto | Contexto validado no servidor | Mostra somente o registro aberto e autorizado. |
| Prioridades, prazos, propostas e pesquisas | Dados filtrados por empresa e permissão | A IA pode organizar a resposta, mas não amplia o escopo da consulta. |
| Falha ou indisponibilidade da IA | Resposta determinística | Mantém a orientação/dados autorizados e informa que a análise não foi concluída. |

## Base de orientações atual

A base canônica fica em `ASSISTANT_KNOWLEDGE_BASE`, em `server.py`. Hoje inclui:

- navegação e busca global;
- cadastro de clientes e fornecedores;
- cadastro de serviços e ensaios pelo Catálogo de serviços;
- prioridades do painel executivo;
- empresa ativa e permissões;
- aprovações;
- limites do próprio assistente.

Perguntas como **“como cadastrar novo serviço?”** são classificadas como `assistant_help` e
respondidas de forma determinística pelo guia de **Cadastro de serviços técnicos**. Esta rota não
depende do OpenRouter, eliminando o erro de retorno “não encontrei registros autorizados” para uma
pergunta de ajuda.

## IA generativa

Quando `OPENROUTER_API_KEY` está configurada, a IA é usada para consultas que dependem de contexto
autorizado e dados operacionais. A chamada exige JSON Schema, limita o histórico a seis mensagens e
recebe apenas campos permitidos, sem senhas, tokens, chaves privadas ou anexos.

Se a resposta da IA for inválida, indisponível ou exceder o tempo de rede, o servidor retorna ao
modo determinístico. O usuário continua recebendo uma resposta útil e a consulta é auditada.

## Controle de acesso implementado

Antes de montar o contexto, o servidor materializa a política efetiva do usuário: módulos legíveis,
operações permitidas, módulos com valores liberados e módulos com dados pessoais. A IA recebe somente
essa política e o contexto filtrado; ela não recebe o perfil bruto nem pode ampliar permissões.

Campos pessoais e identificadores — CPF, CNPJ, documento, e-mail, telefone e endereço — exigem a
operação `view_sensitive`. Valores e preços continuam exigindo `view_values`. Segredos, tokens,
senhas, chaves privadas, anexos e conteúdo bruto nunca entram no contexto do assistente.

As fontes devolvidas ao navegador são um subconjunto validado dos itens realmente enviados ao modelo.
Respostas generativas precisam retornar `source_ids`; uma fonte inexistente ou uma resposta sem fonte
faz a consulta voltar ao modo determinístico.

O histórico curto fica em `assistant_conversations` e `assistant_messages`, vinculado ao usuário e à
empresa. O navegador envia somente o identificador da conversa; mensagens `assistant` inventadas no
cliente não são aceitas como histórico confiável. A troca de empresa inicia uma nova conversa.
Somente as seis mensagens mais recentes de cada conversa permanecem disponíveis para a próxima análise.

Quando a pergunta nomeia um módulo sem acesso de leitura, o servidor responde com recusa explícita e
sem fonte de dados. Perguntas de criação também verificam a permissão de escrita; a orientação pode
explicar o processo, mas nunca afirma que o cadastro será gravado se a operação não estiver liberada.

## Checklist obrigatório para mudanças futuras

1. Atualizar este documento e o diário em `PROJECT_CONTEXT.md`.
2. Preservar filtro por empresa, permissões de leitura, auditoria e validação no servidor.
3. Adicionar ou ajustar teste em `tests/test_server.py` para a pergunta ou cenário novo.
4. Para mudanças de ativos do assistente, atualizar a versão do cache PWA e os contratos de frontend.
5. Validar a resposta com IA indisponível e, se aplicável, com a IA configurada.

## Histórico

### 25/08/2026 — orientação determinística para ajuda de uso

- corrigida a classificação de perguntas de cadastro, incluindo “como cadastrar novo serviço?”;
- perguntas de ajuda agora usam sempre a base verificada do sistema, mesmo quando a IA externa está
  configurada ou indisponível;
- mantida IA generativa somente para respostas que dependem de dados autorizados e contexto dinâmico;
- incluído teste de regressão para confirmar que a orientação não chama o provedor generativo.
- validação concluída com 97 testes do servidor e 38 contratos combinados; a chamada real ao OpenRouter
  não foi executada neste ambiente por depender de credencial externa de produção.

### 25/08/2026 — política, fontes e histórico do assistente

- adicionada política central com módulos, operações, valores e dados pessoais efetivamente autorizados;
- CPF, CNPJ, documento, contato e endereço passaram a ser ocultados sem `view_sensitive`, e valores
  continuam condicionados a `view_values`;
- a IA passou a retornar fontes obrigatórias, validadas pelo servidor contra o contexto autorizado;
- histórico passou a ser persistido no servidor e isolado por usuário e empresa; o cliente não consegue
  fabricar mensagens de assistente;
- adicionados testes de proteção de campos, recusa por permissão, fontes, histórico, isolamento e contrato do novo identificador.
