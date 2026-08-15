# SIVS SECCOL 2.2 — Gestão Integrada, segura e auditável

Sistema local, multiusuário e multiempresa para a operação administrativa, comercial, técnica, metrológica, da qualidade, fiscal e financeira da SECCOL.

## Principais entregas

- 48 módulos de negócio, além das visões Mobile e Portfólio SECCOL, com formulários especializados por assunto, identidade visual uniforme, agrupamentos próprios, obrigatoriedade coerente, indicador de preenchimento, pesquisa, filtros, Kanban e lixeira recuperável;
- identidade premium em grafite e laranja SECCOL (`#171717` e `#C85D23`);
- central inicial inspirada no SIVS original, com Administrativo, Vendas, Mobile, Serviço, Calibração, Qualidade, Normas, Gestão, Financeiro, Caixa e Configurações;
- menus recolhíveis, atalhos operacionais e telas específicas para XML NF-e, Calibração, Mobile, Editais, Fontes, Fiscal/Manager e Normas;
- catálogo oficial com 7 produtos/soluções, 12 instrumentos próprios e 29 serviços/ensaios, cada item com ficha, fonte e base normativa inicial;
- relacionamento obrigatório de assunto em todos os cadastros, assuntos adicionais e múltiplos vínculos entre módulos;
- Central de Assuntos para acompanhar cliente, proposta, contrato, O.S., certificado, financeiro e evidências no mesmo contexto;
- multiempresa real, com dados, fontes, normas, usuários, permissões, notificações e auditoria isolados por empresa;
- perfis administrador, gestor, operador, consulta, técnico, qualidade, fiscal/financeiro e aprovador;
- anexos verificados por assinatura de arquivo e SHA-256, histórico de versões, aprovações segregadas e notificações;
- validação integral no servidor, permissões distintas para leitura, escrita e exportação, limites de requisição e proteção contra gravações concorrentes;
- banco SQLite persistente, exportação portátil `SIVS-3`, backup de desastre integral criptografado `SIVS-BACKUP-2`, restauração offline segura e trilha de auditoria;
- PWA responsiva em Python 3.10+, com `cryptography` para backup AES-256-GCM e `reportlab` para documentos técnicos PDF.

## Base normativa vinculante

Na primeira inicialização de cada empresa, o SIVS cadastra 18 referências técnicas e regulatórias:

- ISO 14644-1:2015, ISO 14644-2:2015, ISO 14644-3:2019, ISO 14644-4:2022, ISO 14644-5:2025 e ISO 14644-7:2004;
- ISO/IEC 17025:2017;
- ISO 21501-4:2018 + Emenda 1:2023;
- NSF/ANSI 49-2022;
- IEST-RP-CC006.4, IEST-RP-CC019.1 e IEST-RP-CC034.5;
- ANSI/ASHRAE 110-2016 (reafirmada em 2025) e ANSI/ASHRAE 111-2024;
- ANVISA RDC 50/2002, RDC 67/2007, RDC 658/2022 e IN 138/2022.

Cada cadastro contém código, edição, organismo, situação, escopo resumido, aplicação SECCOL, ensaios relacionados, fonte oficial, controle de licença e uma ficha de referência anexada.

Certificados, laudos técnicos e estudos técnicos não podem ser salvos sem vínculo com ao menos uma norma não obsoleta. Uma norma vinculada a documento ativo não pode ser excluída.

Esses três módulos geram uma prévia PDF marcada como não controlada. A emissão final só ocorre quando há aprovação válida para a revisão atual, normas vigentes e, nas referências comerciais, cópia licenciada anexada com confirmação expressa. O PDF final é arquivado no próprio registro, recebe SHA-256 e produz evento de auditoria com revisão, aprovação e normas utilizadas.

As fichas são material autoral de controle e não substituem a íntegra. Normas ISO, NSF, IEST e ASHRAE são comerciais/licenciadas; a SECCOL deve anexar sua cópia licenciada ao cadastro correspondente. O responsável técnico deve confirmar edição, emendas, escopo, método, evidências, regra de decisão e requisitos contratuais antes da emissão.

## Portfólio oficial SECCOL

O sistema separa três naturezas que não devem ser confundidas:

- **Produtos e soluções:** área/sala limpa, cabine de segurança biológica, capela de exaustão, fluxo unidirecional, unidade de descontaminação/ventilação, filtros HEPA/ULPA e motores de reposição;
- **Instrumentos próprios:** contador de partículas, fotômetro/gerador PAO, balometer, luxímetro, decibelímetro, termoanemômetro, manômetro, alicate amperímetro, ampola de fumaça, termohigrômetro, radiômetro UVC e VHP;
- **Serviços e ensaios:** 29 escopos oficiais de manutenção, reforma, certificação, engenharia, TAB/HVAC e ensaios em equipamentos e áreas limpas.

Cada item recebe assunto, ficha anexada, página oficial e relacionamentos iniciais com as normas aplicáveis. A premissa de que todo item publicado integra a produção, o fornecimento ou o patrimônio técnico da SECCOL foi confirmada pela direção em 15/08/2026. Modelo, número de série, configuração, preço, NCM e escopo devem ser completados no cadastro operacional.

## Busca de editais

- 38 fontes nacionais, estaduais, de plataforma e de prospecção privada pré-cadastradas por empresa;
- botão explícito **Pesquisar agora**, com trabalho persistente, progresso real, etapa atual, cronômetro e situação de cada fonte;
- consulta automática ao PNCP e contingência pela API oficial de Dados Abertos do Compras.gov.br;
- demais fontes abrem para pesquisa manual em um clique, sem prometer automação inexistente;
- vocabulário SECCOL para áreas limpas, cabines, HEPA/ULPA, fluxo laminar, qualificação, certificação, HVAC, partículas, PAO, VHP e ensaios ambientais;
- pontuação de aderência, deduplicação, histórico, triagem e conversão em Licitação;
- planos diários e semanais são executados pelo agendador interno enquanto o servidor estiver ativo; após reinicialização, execuções interrompidas ficam registradas e o ciclo volta a ser programado.

## Fluxos especiais

### Administrativo e XML NF-e

O importador valida chave e documento do emitente, bloqueia DTD/entidades externas, preserva o XML com SHA-256, cria ou vincula fornecedor e produtos e gera parcelas em Contas a pagar. Toda a operação é atômica: uma falha cancela o conjunto completo.

### Calibração

A Central metrológica mantém a leitura rápida do sistema original e acrescenta:

- alertas de padrões vencidos e a vencer em 30 dias;
- totais de padrões, pendências, certificados e conclusões;
- acesso direto a padrões, calibrações e certificados;
- vínculos, anexos, aprovação e rastreabilidade.

### Mobile

O técnico consulta O.S. em execução, pausadas e agendadas e pode iniciar, pausar, retomar ou concluir. Cada transição atualiza a mesma O.S. e acrescenta evento de execução ao histórico do registro.

### Fiscal / Manager

O módulo organiza documentos e eventos fiscais por empresa. Sem conector homologado, o SIVS registra apenas eventos locais ou coloca solicitações em **Aguardando conector**; nunca afirma transmissão à SEFAZ.

## Executar no Windows

1. Instale o Python 3.10 ou superior em <https://www.python.org/downloads/> e marque `Add Python to PATH`.
2. Extraia a pasta `SIVS`.
3. Dê dois cliques em `INSTALAR_WINDOWS.bat` para criar o atalho **SIVS** na Área de Trabalho.
4. Se necessário, acesse <http://127.0.0.1:8844>.
5. No primeiro acesso, cadastre a empresa e o administrador.

## Executar no macOS ou Linux

```bash
chmod +x start.sh
./start.sh
```

O sistema abre em <http://127.0.0.1:8844>.

## Multiusuário em rede

Por padrão, o servidor escuta apenas `127.0.0.1`. Para acesso simultâneo em vários computadores, execute-o em uma máquina central e publique-o por proxy reverso HTTPS. Configure `SIVS_TRUST_PROXY=1` e `SIVS_SECURE_COOKIE=1` somente quando o proxy for controlado e enviar `X-Forwarded-Proto`. O servidor recusa interface de rede sem essa configuração; `--allow-insecure-network` existe apenas para uma exceção consciente e temporária. Não compartilhe o arquivo SQLite em pasta de rede.

## Dados e backup

O banco operacional fica em `data/sivs.db`.

- **Backup integral criptografado:** inclui todas as empresas, usuários, registros, anexos, versões, aprovações, pesquisas e auditoria. Sessões ativas são removidas da cópia para impedir replay após restauração. Exige administração em todas as empresas e uma senha de pelo menos 12 caracteres.
- **Exportar dados da empresa:** gera JSON `SIVS-3` para portabilidade e não deve ser confundido com backup de desastre.
- **Restaurar:** pare o servidor e execute `python3 restore_backup.py arquivo.sivsbackup --database data/sivs.db --force`. Antes da troca, o utilitário verifica autenticação AES-GCM, integridade SQLite e tabelas obrigatórias, e preserva uma cópia do banco anterior.
- **Somente verificar:** `python3 restore_backup.py arquivo.sivsbackup --verify-only`.

Guarde a senha fora do computador e mantenha pelo menos uma cópia externa testada. O pacote distribuído não contém dados reais nem credenciais.

## Instalação manual das dependências

```bash
python3 -m pip install -r requirements.txt
```

## Testes

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py launcher.py restore_backup.py
node --check static/app.js
```

Consulte `AUDITORIA_COMPLETA_SIVS_SECCOL_2.1_2026-08-15.md` para o diagnóstico de origem e `RELATORIO_EXECUCAO_SIVS_2.2_2026-08-15.md` para a matriz de correções, testes e riscos residuais.
