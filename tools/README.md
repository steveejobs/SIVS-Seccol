# Ferramentas de desenvolvimento

## Agente de portal governado

`tender_portal_worker.py` implementa o contrato assinado entre o SIVS e um
navegador dedicado. Ele e seguro por padrao: sem `--execute`, apenas valida a
configuracao e nao chama o servidor. Acoes externas continuam bloqueadas sem a
flag explicita, sem politica autonoma armada e sem autorizacao no servidor.
Para producao, use a arquitetura Linux isolada descrita em
[`tender-agent/README.md`](tender-agent/README.md), com Selenium remoto privado,
perfil exclusivo, fila continua e acesso visual apenas por tunel SSH.

```powershell
python tools/tender_portal_worker.py
python tools/tender_portal_worker.py --execute
python tools/tender_portal_worker.py --execute --loop
```

Variaveis necessarias: `SIVS_TENDER_AGENT_SECRET` (32+ caracteres),
`SIVS_TENDER_AGENT_COMPANY_ID`, `SIVS_TENDER_AGENT_PROFILE_DIR` e, apenas apos
homologacao, `SIVS_ALLOW_TENDER_AGENT_PRODUCTION=1`.

Utilitários locais do SIVS. Eles não fazem parte do processo do servidor em produção.

## Preparação

```bash
python -m pip install -r tools/requirements.txt
```

## Otimização de imagens

O `optimize_images.py` percorre um arquivo ou diretório, corrige orientação EXIF, redimensiona
proporcionalmente e gera uma versão WebP, JPEG, PNG ou AVIF. Originais nunca são sobrescritos:
o resultado vai para uma pasta separada.

Simular:

```bash
python tools/optimize_images.py caminho/das/imagens --dry-run
```

Otimizar para WebP:

```bash
python tools/optimize_images.py caminho/das/imagens --output optimized --quality 82 --max-size 2200
```

Use `--force` apenas para substituir arquivos já gerados dentro da pasta de saída. A ferramenta
descarta automaticamente resultados maiores que o original, salvo quando `--keep-larger` for usado.

## Auditoria responsiva

`node tools/responsive_audit.mjs` inicia uma instância descartável do SIVS, abre o Edge em modo
headless e percorre todos os itens de navegação disponíveis ao administrador em desktop, tablet e
mobile. O diagnóstico cobre todas as telas; capturas ficam restritas aos layouts estruturalmente
distintos. Resultados são gravados em `.artifacts/responsive-audit/`, que não entra no Git.
Use `node tools/responsive_audit.mjs --quick` para validar rapidamente a tela e o diálogo mobile.

## Simulação operacional integral

`python tools/simulate_full_operation.py` executa os fluxos críticos em bancos e servidores
descartáveis: acesso e isolamento, parceiros, edital, documentos, proposta, aprovação, contrato,
execução, estoque, compras, contas a pagar/receber, fiscal, pacote contábil, backup, observabilidade
e abas. A primeira etapa usa um único banco temporário do setup à entrada e saída de caixa; as
demais ampliam a cobertura em cenários isolados. Certificado A1 ausente é validado como bloqueio
esperado, sem chamada à SEFAZ. O utilitário nunca aponta para o banco configurado e registra o resultado em
`.artifacts/full-operation-simulation.json`.

## Auditoria de interações

`python tools/audit_interactions.py` inicia servidor, banco SQLite e Chrome headless descartáveis.
Ele percorre o menu, abre os principais cadastros e valida criação e login de usuário sem tocar no
banco real. O relatório fica em `.artifacts/interaction-audit.json`.

Para testar somente criação e login de usuário:

```bash
python tools/audit_interactions.py --auth-only
```
