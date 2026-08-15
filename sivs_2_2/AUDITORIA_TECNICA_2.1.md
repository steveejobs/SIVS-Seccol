# Auditoria técnica e funcional — SIVS SECCOL 2.1

Data de consolidação: 15/08/2026  
Versão auditada: 2.1.0

## 1. Escopo e referências analisadas

A auditoria considerou:

- a aplicação SIVS existente e seu banco SQLite;
- a imagem da página inicial do SIVS original fornecida pela SECCOL;
- o manual administrativo público do SIVS, incluindo Arquivos, Clientes/Fornecedores, XML NF-e, Solicitações de compra e Configurações;
- as categorias públicas de ajuda do SIVS para Administrativo, Vendas, Serviço, Calibração, Qualidade, Mobile, Financeiro e Manager;
- o site institucional da SECCOL, em especial serviços de certificação, manutenção e ensaios de equipamentos e áreas limpas;
- catálogos oficiais ISO, NSF, IEST e ASHRAE, além das informações regulatórias da ANVISA disponíveis na data acima.

O objetivo foi preservar o reconhecimento do original sem copiar suas limitações: central por módulos, navegação lateral, alertas de calibração, execução Mobile, importação XML e Manager foram mantidos como conceitos, mas reorganizados com menos ambiguidade e maior integridade.

## 2. Resultado executivo

O SIVS 2.1 passou de um cadastro local generalista para uma plataforma multiempresa com 48 módulos persistentes, visões Mobile e Portfólio, assuntos relacionais, arquivos, aprovações, notificações, inteligência de editais, importação real de NF-e e base normativa vinculante.

Não existe medição objetiva que sustente um número literal de “100 vezes melhor”. A evolução é demonstrada por controles verificáveis: isolamento por empresa, referências estrangeiras bloqueadas, histórico de versões, vínculo normativo obrigatório, proteção de sessão, fluxos especializados, testes automatizados e limites explícitos para integrações externas.

## 3. Correspondência com o sistema original

| Referência original | Implementação SIVS 2.1 | Evolução aplicada |
|---|---|---|
| Página inicial com grandes módulos | Central operacional com 12 cartões coloridos | Contagem de registros, descrição do fluxo e atalhos diretos |
| Menu administrativo lateral | Grupos laterais recolhíveis | 48 módulos, estado ativo, responsividade e menor poluição visual |
| Arquivos | Arquivos administrativos e documentos controlados | Revisão, qualidade, anexos, assunto e auditoria |
| Clientes/Fornecedores | Cadastros próprios | Aprovação comercial, avaliação, contatos e vínculos transversais |
| XML NF-e | Importador XML específico | Duplicidade, fornecedor, itens/produtos, parcelas e XML anexado |
| Solicitação de compra | Solicitações, pedidos e aprovações | Prioridade, centro de custo, anexos, notificação e decisão auditada |
| Calibração com tabelas de alertas | Central metrológica | Vencidos, próximos 30 dias, padrões, calibrações e certificados |
| Mobile com serviços em execução/pausa | Visão Mobile integrada à O.S. | Iniciar, pausar, retomar, concluir e registrar evento com usuário/data |
| Manager | Fiscal / Manager | Empresa ativa, documentos, eventos e fila de conector sem simular SEFAZ |
| Categorias financeiras | Pagar, receber, boletos, financeiro e caixa | Relação com XML, cliente, fornecedor, pedido, contrato e assunto |

### 3.1 Portfólio oficial SECCOL

A direção confirmou que tudo o que consta no site oficial integra a produção, o fornecimento ou o patrimônio técnico da empresa. A implementação transformou essa premissa em três conjuntos distintos:

| Natureza | Quantidade | Controle aplicado |
|---|---:|---|
| Produtos e soluções | 7 | Código, família, natureza, descrição, fonte, ficha e normas relacionadas |
| Instrumentos técnicos próprios | 12 | Propriedade, uso, controle metrológico, fonte, ficha e normas relacionadas |
| Serviços e ensaios | 29 | Categoria, escopo, fonte, ficha e normas relacionadas |

Essa separação impede três erros lógicos: tratar instrumento da equipe como mercadoria, tratar produto como O.S. executada e tratar um escopo comercial como evidência de que o ensaio já foi realizado. O sistema cria 92 vínculos normativos iniciais, preservando a obrigação de revisão pelo responsável técnico.

## 4. Fluxos auditados

### 4.1 Cadastro e assunto

Fluxo: módulo → registro → assunto principal → assuntos adicionais → registros relacionados → arquivos/aprovação.

Controles:

- assunto principal obrigatório na interface;
- ficha visual e semântica especializada para cada um dos 46 módulos que utilizam o motor persistente de registros;
- campos, rótulos, visibilidade, agrupamentos e obrigatoriedade definidos conforme a natureza de cada módulo, sem reutilizar a mesma ficha genérica para Cliente, Licitação, Laudo, Frota ou Financeiro;
- indicador de completude calculado apenas a partir dos requisitos efetivamente obrigatórios daquele cadastro;
- validação conduz o usuário à primeira seção incompleta antes do envio;
- assunto normalizado e isolado por empresa;
- vínculo N:N entre registros e assuntos;
- relacionamento impedido com o próprio registro, excluído ou pertencente a outra empresa;
- mudança de módulo de um registro existente bloqueada;
- exclusão lógica e restauração;
- snapshot antes de atualização e exclusão.

### 4.2 Certificado, laudo e estudo

Fluxo: serviço/O.S. → equipamento/local → método → norma(s) → evidências → revisão → aprovação → emissão.

Controles:

- ao menos uma referência de `Normas técnicas` é obrigatória;
- norma obsoleta ou cancelada não atende a validação de um novo documento;
- norma que fundamenta documento ativo não pode ser excluída;
- anexos guardam evidências, métodos, planilhas e cópia licenciada;
- aprovação é registrada separadamente e vinculada ao documento.

### 4.3 Editais

Fluxo: fontes → clique `Pesquisar agora` → PNCP → contingência Compras.gov → filtro SECCOL → deduplicação → ranking → triagem → licitação.

Controles:

- a abertura do catálogo não dispara busca silenciosa;
- barra de execução, cronômetro, etapas e situação por fonte;
- histórico de pesquisa, erros e fonte utilizada;
- links manuais para fontes sem conector público seguro;
- resultados e históricos isolados por empresa;
- conversão preserva objeto, órgão, modalidade, valor, prazo e URL.

### 4.4 XML NF-e

Fluxo: selecionar XML → validar estrutura/duplicidade → gravar nota e anexo → vincular/criar fornecedor → vincular/criar produtos → gerar parcelas.

Controles:

- limite de tamanho;
- rejeição explícita de DTD e entidades externas;
- chave da NF-e usada para impedir duplicidade;
- nome de arquivo saneado;
- transações e relacionamentos dentro da empresa ativa.

### 4.5 Mobile

Fluxo: O.S. agendada → iniciar → pausar/retomar → concluir.

Controles:

- nenhuma cópia paralela da O.S.;
- transições persistidas no cadastro original;
- histórico limitado de eventos com status, data e usuário;
- permissão de escrita validada no servidor.

### 4.6 Fiscal / Manager

Fluxo: documento local → evento → fila de conector → retorno/protocolo quando integrado.

Controles:

- sem conector: somente `Registrado localmente`;
- com fila habilitada: solicitação fica `Aguardando conector`;
- o sistema não cria protocolo nem afirma autorização da SEFAZ;
- eventos, configurações e documentos são isolados por empresa.

## 5. Base normativa instalada

| Referência | Uso principal cadastrado | Documento no SIVS |
|---|---|---|
| ISO 14644-1:2015 | Classificação por partículas | Ficha de referência + link oficial + espaço para cópia licenciada |
| ISO 14644-2:2015 | Plano de monitoramento | Ficha de referência + link oficial + espaço para cópia licenciada |
| ISO 14644-3:2019 | Métodos de ensaio | Ficha de referência + link oficial + espaço para cópia licenciada |
| ISO 14644-4:2022 | Projeto, construção e partida | Ficha de referência + link oficial + espaço para cópia licenciada |
| ISO 14644-5:2025 | Controle operacional | Ficha de referência + link oficial + espaço para cópia licenciada |
| ISO 14644-7:2004 | Dispositivos separativos | Ficha de referência + aviso de revisão em desenvolvimento |
| ISO/IEC 17025:2017 | Competência e validade de resultados | Ficha de referência + link oficial + espaço para cópia licenciada |
| ISO 21501-4:2018 + Amd 1:2023 | Calibração e verificação de contadores ópticos de partículas | Ficha de referência + link oficial + espaço para cópia licenciada |
| NSF/ANSI 49-2022 | Cabines de segurança biológica Classe II | Ficha de referência + link oficial + espaço para cópia licenciada |
| IEST-RP-CC006.4 | Ensaios e caracterização de salas limpas | Ficha de referência + link oficial + espaço para cópia licenciada |
| IEST-RP-CC019.1 | Competência de organizações e profissionais de certificação | Ficha de referência + link oficial + espaço para cópia licenciada |
| IEST-RP-CC034.5 | Ensaios de vazamento em filtros HEPA/ULPA | Ficha de referência + link oficial + espaço para cópia licenciada |
| ANSI/ASHRAE 110-2016 (RA 2025) | Contenção de capelas laboratoriais | Ficha de referência + link oficial + espaço para cópia licenciada |
| ANSI/ASHRAE 111-2024 | Medição, ajuste e balanceamento de HVAC | Ficha de referência + link oficial + espaço para cópia licenciada |
| ANVISA RDC 50/2002 | Projetos físicos de EAS | Ficha de referência + endereço público |
| ANVISA RDC 67/2007 | Boas práticas de manipulação | Ficha de referência + endereço público |
| ANVISA RDC 658/2022 | BPF de medicamentos | Ficha de referência + endereço público |
| ANVISA IN 138/2022 | Qualificação e validação | Ficha de referência + endereço público |

As referências são um ponto de partida controlado, não uma determinação automática de aplicabilidade. A matriz normativa deve ser validada pelo responsável técnico e pela Qualidade para cada contrato, instalação, equipamento, método e órgão regulador.

## 6. Segurança e integridade

Correções confirmadas nesta versão:

- associação ativa à empresa passou a ser requisito da sessão; desativação encerra as sessões daquela empresa;
- CSRF obrigatório em todas as alterações autenticadas;
- cookie HttpOnly e SameSite Strict;
- permissões de escrita verificadas por módulo no servidor;
- decisão de aprovação limitada ao destinatário ou aos perfis aprovador/gestor/administrador;
- leituras, anexos, lixeira, assuntos, resultados de edital e auditoria filtrados por empresa;
- caminhos estáticos protegidos contra travessia de diretório;
- CSP, `X-Frame-Options`, `nosniff` e política de referência;
- cabeçalho de anexo saneado contra quebra de linha;
- URLs externas renderizadas apenas para protocolos HTTP/HTTPS;
- normas em uso protegidas contra exclusão.

## 7. Limites e riscos residuais declarados

- O servidor padrão é local. Para vários computadores, é obrigatório implantar HTTPS e proteger a máquina central.
- SQLite suporta a carga normal de uma pequena/média operação; crescimento expressivo ou múltiplas filiais com alta concorrência pode justificar PostgreSQL.
- O conector fiscal não está incluído. Credenciais, certificados digitais, homologação e tratamento de retornos são projeto separado.
- Os planos de editais não executam com o servidor desligado; recorrência autônoma exige serviço agendador.
- Textos integrais ISO, NSF, IEST e ASHRAE não estão redistribuídos. A SECCOL deve anexar cópias licenciadas.
- A lista normativa deve passar por revisão técnica e jurídica periódica. Edição “publicada” não significa aplicabilidade universal.
- Notificações são internas. E-mail, WhatsApp, push e Certweb dependem de conectores externos.

## 8. Evidências de verificação

Comandos executados no pacote:

```text
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py launcher.py
node --check static/app.js
```

Resultado consolidado: 10 testes automatizados aprovados, incluindo criação inicial, autenticação, CSRF, catálogos por empresa, isolamento multiempresa, portfólio idempotente, relacionamentos normativos, exigência normativa, rejeição de XML com DTD e API ponta a ponta.

Também foram validados:

- HTML sem identificadores duplicados;
- chaves CSS balanceadas;
- presença das telas e controles críticos;
- inicialização de banco limpo com 38 fontes, 18 normas, 18 fichas normativas, 48 itens de portfólio e 48 fichas de portfólio anexadas por empresa;
- 92 relacionamentos iniciais entre produtos, instrumentos, serviços e referências normativas.

Teste ao vivo da busca oficial em 15/08/2026:

- PNCP respondeu com sucesso em 4 de 4 páginas planejadas, sem erro e sem acionar a contingência;
- a consulta estrita com seis termos técnicos SECCOL retornou zero aderências no recorte testado, resultado tratado corretamente como pesquisa concluída;
- uma consulta de controle com o termo amplo `manutenção` retornou e persistiu 38 oportunidades, comprovando conexão, filtro, gravação e leitura dos resultados;
- os dados desse teste foram criados em banco temporário e não acompanham a distribuição.

## 9. Critérios de aceite operacional

Antes de produção, a SECCOL deve:

1. cadastrar dados oficiais da empresa e usuários;
2. revisar perfis por função;
3. anexar normas comerciais licenciadas e procedimentos internos aprovados;
4. homologar modelos de certificado, laudo e estudo com o responsável técnico;
5. testar um ciclo completo de O.S. e aprovação;
6. importar XMLs de homologação e conferir fornecedores, produtos e parcelas;
7. testar a busca de editais com internet disponível;
8. configurar rotina de backup externo;
9. implantar HTTPS antes de liberar o acesso em rede;
10. manter registro de revisão da matriz normativa;
11. completar modelos, séries, configurações, NCM, custos e preços dos itens do portfólio antes do uso comercial.
