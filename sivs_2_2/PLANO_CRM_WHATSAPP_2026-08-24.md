# CRM e WhatsApp por uazapi

Decisão atualizada em 24/08/2026.

## Resultado adotado

O SIVS usa a uazapi como ponte de conexão por QR Code, sem importar React ou Supabase para a
aplicação. O frontend continua JavaScript nativo, o backend continua Python e a persistência continua
SQLite. Cada empresa possui no máximo uma instância, um webhook e uma fila totalmente isolados.

A uazapi não é apresentada como WhatsApp Business Platform Cloud API oficial. A documentação atual do
provedor (v2.1.1) recomenda WhatsApp Business e documenta estados `disconnected`, `connecting`,
`connected` e `hibernated`, header `token`, `POST /instance/connect`, `GET /instance/status`,
`POST /instance/disconnect`, `DELETE /instance`, `POST /webhook` e `POST /send/text`:
https://docs.uazapi.com/

O envio implementa o endpoint atual `/send/text` com `number`/`text`. Somente em resposta 404 ou 405
há fallback para o contrato legado fornecido, `/message/send-text` com `phone`/`message`.

## Segurança e multiempresa

- `whatsapp_instances.company_id` é único e referencia a empresa com exclusão em cascata;
- o token mestre de criação fica apenas em `SIVS_UAZAPI_API_TOKEN`, nunca no banco ou no navegador;
- o token individual devolvido pelo provedor é cifrado com AES-256-GCM e chave dedicada
  `SIVS_WHATSAPP_MASTER_KEY`; empresa é usada como dado autenticado da cifra;
- `server_url` só aceita HTTPS em subdomínio de `uazapi.com`, sem porta, credenciais, query ou fragmento;
- o proxy de criação só aceita o path esperado e hosts de `SIVS_UAZAPI_CREATE_HOSTS`;
- a chamada ao proxy envia somente `Content-Type: application/json`; o token mestre segue no corpo,
  conforme o contrato entregue;
- criação, QR, status remoto, webhook, desconexão e exclusão exigem
  `manage_whatsapp_integration`; vendedores não recebem essa permissão;
- respostas, atribuições e leitura continuam revalidadas no servidor e filtradas por empresa;
- auditoria não copia o corpo das mensagens nem tokens.

O provedor não documenta assinatura HMAC de webhook. Por isso o SIVS registra uma URL diferente e
aleatória por empresa, com 256 bits de entropia, limita corpo e taxa, rejeita grupos/saídas, deduplica
por ID externo e nunca aceita `company_id` enviado no payload. Isso reduz exposição, mas não equivale a
autenticidade criptográfica. Se a uazapi passar a oferecer assinatura, ela deve ser exigida antes de
classificar o webhook como fortemente autenticado.

## Matriz de acesso

| Função | Fila | Responder | Assumir | Distribuir | Respostas rápidas | Integração/QR |
|---|---|---:|---:|---:|---:|---:|
| Vendedor | próprias e disponíveis | sim | sim | não | usar | não |
| Gestor | todas | sim | sim | sim | gerenciar | não |
| Administrador | todas | sim | sim | sim | gerenciar | sim |
| Financeiro | somente quando liberado | configurável | configurável | não | usar | não |
| Demais | nenhuma por padrão | não | não | não | não | não |

## Fluxo operacional

1. Administrador abre **Atendimento WhatsApp** e seleciona **Criar conexão**.
2. O servidor cria a instância pelo proxy, cifra o token retornado, gera a URL aleatória do webhook e
   registra eventos `connection`, `messages` e `messages_update`.
3. **Gerar ou atualizar QR** chama `POST /instance/connect`; o QR é transitório e não é persistido.
4. O administrador lê o QR no WhatsApp Business. O painel consulta `GET /instance/status` a cada 15 s
   somente enquanto um administrador está na tela e a conexão está pendente.
5. O webhook atualiza o estado e transforma a primeira mensagem individual em oportunidade `Novo lead`
   vinculada a uma conversa do CRM.
6. Vendedor assume a conversa antes de responder. O envio usa chave idempotente e `track_id` quando o
   endpoint atual está disponível.
7. **Desconectar** chama o provedor de verdade; não altera apenas uma flag local.
8. **Remover instância** só apaga a cópia local após confirmação da exclusão externa (404/410 também
   são aceitos como ausência já efetivada).

## Respostas rápidas

As respostas são modelos internos, com variáveis limitadas a `{{nome}}`, `{{vendedor}}` e
`{{referencia}}`. Exemplos:

- `Olá, {{nome}}! Sou {{vendedor}} da SECCOL. Recebemos seu contato e gostaria de entender melhor como podemos ajudar.`
- `Olá, {{nome}}! Passando para acompanhar a proposta {{referencia}}. Posso esclarecer algum ponto?`
- `Olá, {{nome}}! Encaminhei sua solicitação ao nosso financeiro. A equipe responsável dará continuidade por este canal.`

Elas não são templates aprovados da Meta e não autorizam disparo em massa. A política do WhatsApp exige
número fornecido pelo titular, opt-in compatível com a finalidade, respeito ao descadastro e proíbe
spam ou surpresa. A Meta pode limitar ou remover acesso por violações:
https://whatsappbusiness.com/policy/

## Variáveis de runtime

```env
SIVS_UAZAPI_API_TOKEN=<token novo e não exposto>
SIVS_UAZAPI_CREATE_URL=https://grlwciflaotripbumhve.supabase.co/functions/v1/create-instance-url
SIVS_UAZAPI_CREATE_HOSTS=grlwciflaotripbumhve.supabase.co
SIVS_UAZAPI_DEVICE_NAME=SIVS SECCOL
SIVS_WHATSAPP_MASTER_KEY=<32 bytes aleatórios em Base64>
SIVS_PUBLIC_URL=https://sivs.seudominio.com.br
```

O token publicado na conversa deve ser revogado e substituído. Para gerar a chave de cofre sem exibi-la
em logs compartilhados, use o gerenciador de segredos da infraestrutura ou, em terminal privado:

```powershell
[Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

## Homologação real obrigatória

- confirmar que o novo token possui saldo e cria instância pelo proxy;
- confirmar que `SIVS_PUBLIC_URL` chega ao contêiner por HTTPS e sem reescrita do path;
- ler QR com um número WhatsApp Business dedicado, não o número pessoal de funcionário;
- testar conexão, reinício do SIVS, desconexão, reconexão e exclusão;
- testar mensagem recebida, duplicada, grupo ignorado, envio, entrega, leitura e falha;
- verificar no Network do navegador que nenhum token ou URL secreta de webhook aparece;
- obter aceite empresarial sobre risco do provedor intermediário, retenção, opt-in/opt-out e plano de
  migração para Cloud API oficial caso estabilidade ou conformidade exijam.

## Limite de aceitação

O código e os contratos locais são testados com respostas simuladas do provedor. Uma conexão real não
é declarada concluída sem token rotacionado, URL pública, número dedicado e leitura do QR no ambiente de
produção. O SIVS não realiza campanhas, grupos ou chatbot automático nesta etapa.
