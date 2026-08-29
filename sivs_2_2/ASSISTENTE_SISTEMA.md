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
- regras tributárias, vigência e prévia fiscal bloqueante;
- classificação fiscal de produto e rascunho fiscal de venda;
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

## Leitura assistida de editais

A leitura de documentos de edital usa uma camada de custo e qualidade equilibrados como primeira tentativa e só aceita a
resposta depois de validar estrutura e citações no servidor. Se a entrega estiver incompleta, o
servidor repete a solicitação em uma camada de maior capacidade. Os nomes de provedores e modelos
não são enviados ao navegador, exibidos no dossiê nem registrados na auditoria funcional; ela
preserva apenas o modo de leitura, a quantidade de páginas e os documentos processados.

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

### 28/08/2026 — conversa orientada à decisão e recuperável

- a abertura passou a oferecer três caminhos claros (prioridades, cadastro em foco e orientação da área), mantendo pergunta livre para situações específicas;
- a orientação determinística exibe primeiro o guia diretamente relacionado à pergunta e um próximo passo, em vez de listar toda a base de ajuda;
- consultas que excedem 50 segundos ou falham preservam o texto, mostram a causa em linguagem clara e oferecem **Tentar novamente**; fechar ou reiniciar a conversa cancela a requisição pendente;
- o escopo, a filtragem por empresa, permissões, auditoria e a validação no servidor permanecem inalterados. O cache PWA foi atualizado para `sivs-v2.2.0-assistant-recovery-108`.

### 27/08/2026 — emissão NF-e 4.00 em homologação

- a base agora orienta que o rascunho fiscal conferido pode ser emitido somente em homologação por pessoa com `issue_nfe_homologation`, mediante confirmação literal `HOMOLOGAR`;
- explica que o servidor reserva série/número por empresa e unidade, forma a chave de 44 dígitos, assina com o A1, confere a assinatura, valida o XSD oficial versionado e transmite por mTLS;
- somente retorno de autorização com protocolo e chave correspondentes produz `nfeProc`, XML para download e DANFE marcado **Homologação — sem valor fiscal**; rejeições e falhas permanecem visíveis e auditáveis;
- produção continua bloqueada. O assistente não deve afirmar que “basta o A1”: também são obrigatórios cadastro fiscal e endereço completos, destinatário apto, regras/classificações revisadas, credenciamento e homologação formal antes de qualquer liberação produtiva.

### 27/08/2026 — orientação para rascunho fiscal integrado

- a base explica que a classificação vigente do produto exige perfil, NCM, CFOP, origem e fonte revisada; não sugere nem preenche esses dados;
- orienta que o rascunho parte de uma venda confirmada, cliente e unidade com UF, itens exclusivamente de produto e cobertura tributária completa;
- deixa explícito que o resultado é uma fotografia auditável, sem XML, numeração, assinatura ou transmissão, e que a substituição é uma ação explícita que preserva histórico.

### 27/08/2026 — orientação para regras tributárias determinísticas

- a base orienta a cadastrar operação, perfil fiscal vinculado e regras revisadas por empresa, sem sugerir alíquota, CST, CSOSN, CFOP, NCM ou fonte normativa;
- explica que a prévia exige cobertura única para cada tributo do perfil e bloqueia conflito ou regra ausente;
- deixa explícito que a prévia não gera XML, não reserva numeração, não transmite à SEFAZ e não libera emissão NF-e.

### 26/08/2026 — orientação fiscal e financeira segura

- a base determinística explica baixas, parcelamento e o bloqueio do título original após o desdobramento;
- perguntas sobre NF-e, A1 e SEFAZ distinguem prontidão, consulta em homologação e emissão em produção. O assistente não afirma autorização fiscal sem evidência externa e validações do servidor.

### 26/08/2026 — orientação sobre razão contábil

- a base orienta que competência e data de registro são distintas, que partidas exigem débitos e créditos iguais e que somente contas analíticas ativas podem receber novo lançamento;
- correções são explicadas como estorno rastreável, sem sugerir edição ou exclusão de lançamento já postado.

### 26/08/2026 — orientação sobre mapeamento financeiro-contábil

- o assistente explica que o mapeamento por categoria define contas de débito e crédito e que o sistema não deve inferi-las;
- enquanto o mapeamento não estiver revisado, baixas financeiras não devem ser tratadas como lançamento contábil automático.

### 26/08/2026 — baixa conectada ao razão

- a orientação informa que a baixa gera partida dobrada apenas quando há mapeamento ativo e sem ajustes financeiros sem conta própria;
- estornos de baixas mapeadas também geram a partida inversa, preservando a trilha contábil e financeira.

### 26/08/2026 — contas bancárias e conciliação

- orientar o usuário a cadastrar a conta bancária na área financeira antes de registrar baixas;
- explicar que o sistema armazena somente os quatro últimos dígitos e uma impressão digital segura, rejeitando duplicidade dentro da empresa ativa;
- informar que `bank_account_id` é validado no servidor, preservado em estornos e nunca permite acesso a contas de outra empresa;
- manter claro que a descrição manual continua disponível para histórico legado, sem inventar conta cadastrada.

### 26/08/2026 — lançamento e relatórios contábeis

- orientar que o lançamento manual exige duas ou mais partidas, contas analíticas ativas e débitos exatamente iguais aos créditos;
- explicar a diferença entre competência e caixa sem tratar uma visão como substituta da outra;
- informar que diário, razão, balancete, DRE e balanço são calculados apenas de partidas registradas e que o balanço inclui o resultado acumulado não encerrado;
- nunca afirmar que um demonstrativo substitui fechamento, ECD/ECF, SPED ou revisão de contador responsável.

### 26/08/2026 — saldo inicial e fechamento de competência

- explicar que saldo inicial é uma partida balanceada de abertura, registrada uma única vez para a data inicial da competência;
- orientar que encerrar uma competência bloqueia novos lançamentos nela e que reabertura exige justificativa auditada;
- nunca orientar edição do lançamento para contornar fechamento: a correção deve seguir o estorno, a reabertura formal ou a orientação do responsável contábil.

### 26/08/2026 — rateio financeiro-contábil por centro de custo

- orientar que rateio é uma regra explícita do mapeamento financeiro-contábil: requer dois ou mais centros distintos, percentuais positivos que totalizem exatamente 100,00% e a escolha consciente do lado de débito ou crédito;
- explicar que o sistema preserva a divisão exata em centavos e a reproduz invertida no estorno, sem permitir centro padrão junto com rateio;
- nunca sugerir percentuais, contas ou lado contábil sem validação do responsável contábil.

### 26/08/2026 — descontos, juros e tarifas na baixa

- orientar que desconto, juros/multa e tarifa exigem contas analíticas próprias no mapeamento da categoria somente quando o respectivo valor for informado; o sistema não deve escolher essas contas, natureza ou centro de custo;
- explicar que uma baixa mapeada com regra de ajuste ausente ou inativa é recusada por inteiro para não separar financeiro, caixa e razão, e que o estorno mantém as linhas contábeis invertidas;
- nunca recomendar uma classificação de ajuste sem validação do responsável contábil. Se a conta ou o centro de custo estiver inativo, orientar a revisar o mapeamento antes da baixa.

### 26/08/2026 — leitura de edital econômica e sem exposição técnica

- a leitura assistida passou a iniciar pela camada de custo e qualidade equilibrados e manter a camada de maior capacidade
  somente como fallback quando a validação local rejeitar a resposta;
- o dossiê, a resposta da API persistida e a auditoria funcional deixaram de expor nome de modelo ou
  provedor; páginas lidas, documentos e revisão humana obrigatória permanecem visíveis.

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

### 27/08/2026 — orientação de RH, ponto e folha

- o assistente passa a explicar a sequência correta: colaborador com CPF válido, vínculo e matrícula eSocial, jornada, importação AFD/CSV, conferência das marcações, prévia e fechamento;
- nunca deve sugerir edição ou exclusão do ponto original. Correções são novas marcações justificadas e auditadas;
- deve informar que somente competências com tabela legal versionada podem ser calculadas e que marcação ímpar, intervalo inválido ou ausência total de ponto bloqueiam o fechamento;
- pode orientar as exportações AEJ, CSV de horas, CSV de folha e holerite, respeitando `rh`, `view_values` e `export_hr`; deve avisar que o AEJ atual é para validação e exige o P7S do desenvolvedor do PTRP antes de uso fiscal;
- não deve afirmar que o módulo transmite eSocial, substitui FGTS Digital/DCTFWeb, aplica convenção coletiva ou calcula férias, 13º, rescisão e adicionais ainda não implementados.

### 28/08/2026 — orientação da Central de relatórios

- orientar a escolher uma das fontes autorizadas e combinar dimensões, métricas, período, pesquisa e ordenação; indicadores, gráfico, tabela e totais derivam da mesma definição;
- filtros de módulo mostram apenas áreas permitidas; os filtros exatos aceitam até vinte valores separados por ponto e vírgula para cada dimensão, sem alterar a fonte ou ampliar o acesso;
- explicar que modelos pessoais podem ser salvos e que somente gestores podem compartilhá-los com toda a empresa;
- exportação CSV/PDF exige permissão tanto na Central quanto na fonte de origem; relatório nunca amplia acesso a valores, RH, auditoria ou dados de outra empresa;
- nunca sugerir SQL, consulta livre ao banco ou contorno de permissão. O catálogo do servidor é a única fonte de campos e cada execução retorna no máximo 500 agrupamentos auditados.
### 29/08/2026 — perfis genéricos mínimos e recusa por escopo efetivo

- o Assistente deve usar somente a matriz efetiva retornada pelo servidor; o nome do perfil nunca autoriza ampliar leitura, escrita, valores ou dados sensíveis;
- **Operador** nasce somente com Arquivos, Contatos, Ramais e Produtividade; **Consulta** nasce somente com leitura de Arquivos e Produtividade. Acesso adicional exige perfil especializado ou concessão explícita por empresa;
- quando o módulo não puder ser lido, a recusa de leitura tem precedência. Quando houver leitura explícita, mas não escrita, o Assistente pode explicar o processo e deve informar que a gravação continuará bloqueada pelo servidor;
- nenhuma orientação pode sugerir troca de perfil, concessão automática ou uso de outra empresa para contornar a matriz efetiva.

### 29/08/2026 — automação empresarial supervisionada

- o Assistente pode explicar e priorizar os achados da Central de automação somente quando a sessão puder ler `controladoria` e o módulo de destino do achado; um achado nunca amplia permissão nem autoriza expor valores ou dados pessoais;
- a execução diária ocorre às 7h no fuso `America/Sao_Paulo`, de segunda a sábado. A busca de editais informa quantas oportunidades foram encontradas e quantas são novas, mas deve exigir revisão de aderência, go/no-go, preço e documentos finais;
- a IA usada no resumo operacional recebe exclusivamente contagens agregadas por área e severidade. Não recebe nomes, CPF/CNPJ, documentos, valores, evidências ou textos dos achados e não é fonte da classificação determinística;
- nunca sugerir que a automação pague, transfira, troque conta bancária, escolha fornecedor por conta própria, ajuste saldo físico, invente tributação, transmita fechamento, contrate, demita, puna, avalie trabalhador, feche folha, envie proposta/lance ou emita resultado técnico sem o responsável qualificado;
- ciência e resolução encerram apenas o acompanhamento do achado. O Assistente deve encaminhar a pessoa ao fluxo operacional e à aprovação adequada, sem afirmar que a causa foi corrigida apenas porque o alerta foi resolvido;
- se a IA externa falhar, explicar o resumo determinístico existente. Nunca tratar indisponibilidade do modelo como permissão para omitir evidência, reduzir validação ou executar uma ação protegida.
