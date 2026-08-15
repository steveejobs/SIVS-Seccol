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
PYTHONUNBUFFERED=1
```

Se o Dokploy fornecer `PORT`, ela terá precedência sobre `SIVS_PORT`.

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
