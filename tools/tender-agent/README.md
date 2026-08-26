# Agente de portal em VPS Linux

Arquitetura recomendada para homologacao e futura operacao: uma VPS Linux AMD64
separada do servidor SIVS, com um worker sem navegador embutido e um Chrome oficial
do Selenium em outro container. A fila, as autorizacoes e todos os limites financeiros
continuam no servidor SIVS.

O `compose.yaml` nao publica o WebDriver. O noVNC fica ligado somente em
`127.0.0.1` para acesso por tunel SSH durante login, MFA, CAPTCHA ou intervencao
manual. O perfil autenticado reside em volume exclusivo, com apenas uma sessao por
container. O worker inicia sem `--allow-external-effects`: portanto, envio de proposta
e lance permanecem bloqueados mesmo que o servico esteja ligado.

## Acompanhamento visual no SIVS

O detalhe da licitacao possui o botao **Assistir sessao ao vivo**. Ele abre uma URL
HTTPS configurada no servidor SIVS por `SIVS_TENDER_AGENT_VIEWER_URL` e registra o
acesso na auditoria. O SIVS inclui um ticket HMAC de cinco minutos, validado pelo
servico `viewer`; use o mesmo `SIVS_TENDER_AGENT_VIEWER_SECRET` no Dokploy e no
arquivo `.env` desta VPS. O `viewer` entrega somente a ultima imagem PNG do navegador:
nao possui VNC, WebDriver, teclado, mouse ou rota de comando. O Caddy do compose emite
HTTPS para `SIVS_TENDER_AGENT_VIEWER_DOMAIN`. Essa URL **nao** deve apontar diretamente
para `:7900`, para uma URL HTTP, nem expor a porta noVNC.

Enquanto esse gateway nao estiver configurado, o SIVS mostra o estado da sessao e
mantem o botao indisponivel; a administracao tecnica continua usando o tunel SSH.

## Recursos minimos

- VPS Linux AMD64 com 2 vCPU, 4 GB de RAM e 30 GB SSD;
- Docker Engine 26+ e Docker Compose v2.34+;
- saida HTTPS para o dominio do SIVS e para os portais homologados;
- entrada publica bloqueada por firewall; acesso administrativo somente por SSH com chave.

Use Windows somente se a homologacao de um portal demonstrar dependencia real de
componente, certificado ou navegador exclusivo do Windows. Para os portais web usuais,
Linux reduz custo e superficie de manutencao e permite fixar navegador e driver juntos.

## Preparacao segura

1. Copie `.env.example` para `.env` na VPS e preencha segredos exclusivos.
2. No servidor SIVS, configure o mesmo `SIVS_TENDER_AGENT_SECRET`, o
   `SIVS_TENDER_AGENT_COMPANY_ID` e mantenha
   `SIVS_ALLOW_TENDER_AGENT_PRODUCTION=0` ou ausente.
3. Valide a composicao sem iniciar o navegador:

   ```bash
   docker compose --env-file .env config --quiet
   ```

4. Inicie a pilha:

   ```bash
   docker compose --env-file .env up -d --build
   docker compose logs -f worker
   ```

5. Para acessar a tela do navegador sem publicar a porta, crie um tunel local:

   ```bash
   ssh -L 7900:127.0.0.1:7900 usuario@ip-da-vps
   ```

   Depois abra `http://127.0.0.1:7900/?autoconnect=1&resize=scale` e use a senha
   definida em `SIVS_TENDER_AGENT_VNC_PASSWORD`.

## Etapas antes de qualquer lance real

1. executar somente em `SHADOW` e comparar decisoes com um operador;
2. homologar seletores e recibos separadamente para cada portal e versao visual;
3. testar MFA, CAPTCHA, queda de rede, sessao expirada e alteracao do edital;
4. passar para `SUPERVISED`, mantendo confirmacao humana;
5. autorizar producao somente por janela curta, com piso, passo, quantidade maxima e
   autorizacao escrita;
6. adicionar `--allow-external-effects` apenas ao comando do worker depois da
   homologacao formal e configurar `SIVS_ALLOW_TENDER_AGENT_PRODUCTION=1` no servidor.

Essa ultima etapa ainda nao deve ser realizada: o worker de referencia recusa
`PLACE_BID` e `SUBMIT_PROPOSAL` enquanto nao existir adaptador de portal homologado.
