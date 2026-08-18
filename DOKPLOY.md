# Deploy no Dokploy

O repositório aceita os dois modos de build do Dokploy:

- **Nixpacks:** detectado pelo `nixpacks.toml` e pelo `requirements.txt` da raiz;
- **Dockerfile:** usa o `Dockerfile` da raiz e inclui healthcheck.

## Configuração da aplicação

Use a raiz do repositório como diretório de build e configure a porta interna como `8844`.
O domínio deve apontar para essa mesma porta e usar HTTPS.

Variáveis recomendadas:

```env
SIVS_HOST=0.0.0.0
SIVS_PORT=8844
SIVS_DB=/data/sivs.db
SIVS_REQUIRE_PERSISTENT_DB=1
SIVS_TRUST_PROXY=1
SIVS_SECURE_COOKIE=1
SIVS_TELEMETRY_RETENTION_DAYS=180
SIVS_FISCAL_MASTER_KEY=<BASE64_DE_32_BYTES>
SIVS_ALLOW_SEFAZ_PRODUCTION=0
PYTHONUNBUFFERED=1
```

Se o Dokploy fornecer `PORT`, ela terá precedência sobre `SIVS_PORT`.

Gere `SIVS_FISCAL_MASTER_KEY` uma única vez com `openssl rand -base64 32`, salve-a como segredo e
mantenha uma cópia no cofre da empresa. Ela cifra o material privado do certificado A1 com
AES-256-GCM. Se a chave for perdida, o A1 armazenado não poderá ser recuperado e deverá ser
importado novamente. Não reutilize a senha do certificado como chave do cofre.

Mantenha `SIVS_ALLOW_SEFAZ_PRODUCTION=0` durante toda a homologação. A alteração para `1` apenas
remove uma trava operacional; ela não substitui credenciamento, revisão contábil, schemas oficiais,
testes de rejeição ou autorização formal para emitir NF-e com validade jurídica.

## Persistência obrigatória

Crie um volume persistente e monte-o em `/data`. Sem esse volume, o banco SQLite será
perdido quando o contêiner for recriado.

O servidor valida esse contrato quando `SIVS_REQUIRE_PERSISTENT_DB=1` e se recusa a iniciar se
`/data` for apenas um diretório do contêiner. No Dokploy, confirme em **Advanced > Mounts** que
um volume nomeado está montado exatamente em `/data` antes do primeiro cadastro.

Use apenas uma réplica da aplicação. O SQLite não deve ser compartilhado entre réplicas
nem colocado em um volume de rede.

## Verificação

Depois do deploy, acesse `https://SEU-DOMINIO/api/status`. A resposta deve ter HTTP 200
e conter `{"ok": true}`. Em seguida, abra o domínio e faça o cadastro inicial.

O proxy do Dokploy precisa encaminhar `X-Forwarded-Proto: https`; isso é necessário para
os cookies seguros de sessão.

Depois do primeiro acesso, abra **Gestão > Centro de Controle** e confirme: volume persistente
verificado, agendador executando, espaço livre, último backup e ausência de erros HTTP 5xx.
