# Ferramentas de desenvolvimento

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
