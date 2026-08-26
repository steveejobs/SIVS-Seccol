# Deploy no Dokploy

O repositório aceita os dois modos de build do Dokploy:

- **Nixpacks:** detectado pelo `nixpacks.toml` e pelo `requirements.txt` da raiz;
- **Dockerfile:** usa o `Dockerfile` da raiz e inclui healthcheck.

Em produção, use **Dockerfile**. O Nixpacks transforma variáveis da aplicação em `ARG`/`ENV` durante
o build e não deve ser usado quando houver SMTP, OpenRouter, chave fiscal ou qualquer outro segredo.
O Dockerfile não recebe esses valores durante o build: o Dokploy deve injetá-los somente no contêiner.
Seu entrypoint ajusta a propriedade do volume `/data` herdado de builds antigos e reduz privilégios
para o usuário `sivs` antes de iniciar o servidor.

## Configuração da aplicação

Use a raiz do repositório como diretório de build e configure a porta interna como `8844`.
O domínio deve apontar para essa mesma porta e usar HTTPS.

Variáveis recomendadas:

```env
SIVS_HOST=0.0.0.0
SIVS_PORT=8844
SIVS_DB=/data/sivs.db
SIVS_REQUIRE_PERSISTENT_DB=1
SIVS_PRESTART_BACKUP_RETENTION=7
SIVS_PUBLIC_URL=https://oziresmoreira.online
SIVS_WEBSITE_LEADS_COMPANY_ID=<id da empresa SECCOL>
SIVS_WEBSITE_LEADS_SECRET=<segredo aleatório com pelo menos 32 caracteres>
SIVS_SMTP_HOST=<HOST_SMTP>
SIVS_SMTP_PORT=587
SIVS_SMTP_USERNAME=<USUARIO_SMTP>
SIVS_SMTP_PASSWORD=<SEGREDO_SMTP>
SIVS_SMTP_FROM=<REMETENTE_VALIDADO>
SIVS_SMTP_STARTTLS=1
SIVS_SMTP_SSL=0
SIVS_TRUST_PROXY=1
SIVS_SECURE_COOKIE=1
SIVS_TELEMETRY_RETENTION_DAYS=180
SIVS_FISCAL_MASTER_KEY=<BASE64_DE_32_BYTES>
SIVS_ALLOW_SEFAZ_PRODUCTION=0
SIVS_TENDER_AGENT_COMPANY_ID=<id da empresa que usara o agente>
SIVS_TENDER_AGENT_SECRET=<segredo HMAC aleatorio com pelo menos 32 caracteres>
SIVS_ALLOW_TENDER_AGENT_PRODUCTION=0
# URL HTTPS de gateway protegido e somente-leitura; nao use a porta noVNC diretamente.
SIVS_TENDER_AGENT_VIEWER_URL=https://viewer.exemplo.com.br/sessao
SIVS_TENDER_AGENT_VIEWER_SECRET=<SEGREDO_ALEATORIO_EXCLUSIVO_COM_32_OU_MAIS_CARACTERES>
OPENROUTER_API_KEY=<SEGREDO_OPENROUTER>
OPENROUTER_TENDER_MODEL=openai/gpt-5.4-mini
OPENROUTER_TENDER_FALLBACK_MODEL=openai/gpt-5.4
PYTHONUNBUFFERED=1
```

`OPENROUTER_API_KEY` é obrigatória apenas para **Ler documentos com IA**. Sem ela, o SIVS ainda
permite visualizar e baixar os documentos, mas registra e exibe a análise como não configurada em vez
de manter o botão indefinidamente sem relatório. O modelo Mini é usado primeiro; o modelo de fallback
só é chamado quando a saída não passa pela validação de completude e citações. Mantenha a chave somente
nos segredos do Dokploy.

As variáveis SMTP habilitam **Esqueci minha senha**. O token expira em 30 minutos, funciona uma
única vez e é armazenado somente como hash. Para provedores que usam TLS implícito, normalmente na
porta 465, configure `SIVS_SMTP_SSL=1` e `SIVS_SMTP_STARTTLS=0`. Nunca coloque a senha SMTP no
repositório.

Em uma emergência, gere uma senha provisória aleatória dentro do contêiner. O comando cria antes
uma cópia íntegra em `/data/admin-backups`, reativa somente a conta indicada, encerra suas sessões e
registra a intervenção na auditoria:

```bash
python tools/reset_sivs_password.py bandeira.rgabriel@gmail.com --apply
```

Sem `--apply`, o utilitário apenas confirma a conta e não altera o banco.

Se o Dokploy fornecer `PORT`, ela terá precedência sobre `SIVS_PORT`.

Gere `SIVS_FISCAL_MASTER_KEY` uma única vez com `openssl rand -base64 32`, salve-a como segredo e
mantenha uma cópia no cofre da empresa. Ela cifra o material privado do certificado A1 com
AES-256-GCM. Se a chave for perdida, o A1 armazenado não poderá ser recuperado e deverá ser
importado novamente. Não reutilize a senha do certificado como chave do cofre.

Mantenha `SIVS_ALLOW_SEFAZ_PRODUCTION=0` durante toda a homologação. A alteração para `1` apenas
remove uma trava operacional; ela não substitui credenciamento, revisão contábil, schemas oficiais,
testes de rejeição ou autorização formal para emitir NF-e com validade jurídica.

## Agente de portal em servidor separado

Não instale Chrome/Selenium no mesmo contêiner da aplicação e não publique a porta 4444. A arquitetura
adotada usa uma VPS Linux AMD64 separada, executando `tools/tender-agent/compose.yaml`. O servidor SIVS
mantém fila, política, piso, passo, janela e auditoria; a VPS mantém somente o navegador e o executor.

Use o mesmo `SIVS_TENDER_AGENT_SECRET` nos dois ambientes, mantenha
`SIVS_ALLOW_TENDER_AGENT_PRODUCTION=0` no Dokploy e não adicione `--allow-external-effects` ao worker
durante preparação e homologação. O acesso visual ao navegador deve ocorrer pelo noVNC ligado a
`127.0.0.1` e por túnel SSH. O procedimento integral, requisitos e sequência de homologação estão em
`tools/tender-agent/README.md`.

Para o acompanhamento por usuarios nao tecnicos, configure
`SIVS_TENDER_AGENT_VIEWER_URL` com a URL HTTPS de um gateway protegido, com acesso
somente-leitura e autenticacao corporativa. O SIVS registra cada abertura da tela. Nao
configure `http://`, IP publico ou a porta `7900`: o noVNC bruto permanece em localhost.

Windows fica reservado como contingência caso um portal específico comprove dependência exclusiva de
componente ou certificado Windows. Para portais web, Linux conteinerizado reduz custo, fixa conjuntamente
navegador e driver e mantém a automação fora do processo que atende usuários e grava o SQLite.

## Persistência obrigatória

Crie um volume persistente e monte-o em `/data`. Sem esse volume, o banco SQLite será
perdido quando o contêiner for recriado.

O servidor valida esse contrato quando `SIVS_REQUIRE_PERSISTENT_DB=1` e se recusa a iniciar se
`/data` for apenas um diretório do contêiner. No Dokploy, confirme em **Advanced > Mounts** que
um volume nomeado está montado exatamente em `/data` antes do primeiro cadastro.

Use apenas uma réplica da aplicação. O SQLite não deve ser compartilhado entre réplicas
nem colocado em um volume de rede.

Além de validar o mount, o servidor recusa banco ausente, vazio, corrompido, sem administrador ou
marcado como não configurado. Isso impede que um deploy sobre um volume novo apresente uma instalação
zerada como se fosse válida. Não contorne essa trava durante atualização ou recuperação: remonte o
volume correto.

Somente na primeira instalação de um volume comprovadamente novo:

1. defina temporariamente `SIVS_ALLOW_EMPTY_DB_INITIALIZATION=1`;
2. faça o deploy e conclua o cadastro do administrador inicial;
3. remova a variável imediatamente;
4. faça novo deploy e confirme nos logs `Snapshot pre-start verificado`.

Antes de migrações e da abertura normal, cada inicialização persistente cria um snapshot consistente
em `/data/prestart-backups/`. O padrão mantém sete cópias e pode ser ajustado entre 2 e 30 por
`SIVS_PRESTART_BACKUP_RETENTION`. Essas cópias ficam no mesmo volume e protegem contra falha de
migração, mas não contra remoção do volume ou perda do servidor.

Configure também um **Volume Backup** do `sivs-seccol-data` para um destino S3/compatível externo,
com execução diária e retenção mínima de 14 cópias. Um deploy não deve ser considerado protegido sem
ao menos uma execução externa concluída e uma restauração testada.

Se o servidor bloquear com “banco persistente ausente ou vazio”, não habilite bootstrap para fazê-lo
subir. Interrompa o deploy, identifique o volume anterior e restaure uma cópia integral antes de iniciar.

## Verificação

Depois do deploy, acesse `https://SEU-DOMINIO/api/status`. A resposta deve ter HTTP 200
e conter `{"ok": true}`. Em seguida, abra o domínio e faça o cadastro inicial.

O proxy do Dokploy precisa encaminhar `X-Forwarded-Proto: https`; isso é necessário para
os cookies seguros de sessão.

Depois do primeiro acesso, abra **Gestão > Centro de Controle** e confirme: volume persistente
verificado, agendador executando, espaço livre, último backup e ausência de erros HTTP 5xx.
