# Auditoria de prontidão do RH — 29/08/2026

## Parecer

O RH passa a ter controles internos compatíveis com uso empresarial assistido em cadastro de vínculos,
ponto, folha mensal de 2026, rubricas, férias/afastamentos e preparação documental. A nota operacional
não é fixa: a tela calcula quatro dimensões por empresa e competência e somente mostra 90 ou mais quando
os dados e as evidências daquela empresa sustentam o resultado.

Não é correto tratar o módulo como substituto integral de um sistema trabalhista homologado. Permanecem
externos: transmissão e recibos do eSocial, FGTS Digital e DCTFWeb; assinatura P7S do AEJ; cálculo integral
de rescisão, 13º, adicionais, múltiplos vínculos e todas as cláusulas econômicas de CCT/ACT. Esses itens
ficam explícitos na interface e não são simulados.

## Controles implementados

- catálogo multiempresa de rubricas efetivas por competência, com natureza eSocial, códigos de incidência
  CP/IRRF/FGTS, efeito no cálculo, fonte oficial, revisão humana e versões imutáveis;
- eventos variáveis não aceitam mais incidências livres. O servidor exige rubrica vigente e grava uma
  fotografia integral dela no lançamento;
- eventos legados só são governados automaticamente quando existe correspondência inequívoca de empresa,
  código, tipo e vigência; sem isso, o fechamento permanece bloqueado;
- registro imutável de admissão, alteração contratual, afastamento/retorno, férias, desligamento, 13º e SST,
  com código de preparação eSocial, responsável, data, justificativa e prazo conhecido;
- férias validam período aquisitivo, aviso mínimo de 30 dias, pagamento até dois dias antes, mínimo de cinco
  dias por fração, limite de três frações, presença de uma fração de 14 dias ao completar três e ausência de
  sobreposição. A verificação de feriado/DSR continua marcada como pendência por depender de calendário e
  repouso contratual configurados;
- férias e afastamentos revisados zeram a expectativa de ponto nos dias abrangidos, sem alterar marcações,
  evitando que sejam convertidos em faltas ou descontos;
- desligamento e afastamento atualizam a situação do vínculo na mesma transação; eventos que alterariam folha
  já fechada são recusados;
- registros vigentes de instrumento coletivo, cadastro eSocial, SST e saúde ocupacional aceitam evidência
  oficial ou declaração de não aplicabilidade detalhada, sempre com autoria e imutabilidade;
- painel de prontidão separa cadastros, jornada, folha e conformidade, lista bloqueios e avisos e não transforma
  ausência de integração externa em conformidade fictícia.

## Base oficial consultada

- [Documentação técnica do eSocial](https://www.gov.br/esocial/pt-br/documentacao-tecnica), incluindo leiautes
  S-1.3 e eventos S-1010, S-1200, S-1210, S-1298/S-1299, S-2200, S-2206, S-2210, S-2220, S-2230,
  S-2240 e S-2299;
- [Tabelas do eSocial S-1.3](https://www.gov.br/esocial/pt-br/documentacao-tecnica/leiautes-esocial-versao-s-1-3-nt-06-2026/tabelas.html)
  e [regras de validação](https://www.gov.br/esocial/pt-br/documentacao-tecnica/leiautes-esocial-versao-s-1-3-nt-06-2026-rev-09-04-2026/regras.html);
- [Manual do FGTS Digital](https://www.gov.br/trabalho-e-emprego/pt-br/servicos/empregador/fgtsdigital/manual-e-documentacao-tecnica/manual/);
- [Integração com a DCTFWeb](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/perguntas-frequentes/sped/efd-reinf/efdr/7-integracao-da-efd-reinf-com-a-dctfweb/7-4-como-e-feita);
- [Registro de convenções e acordos coletivos no Sistema Mediador](https://www.gov.br/trabalho-e-emprego/pt-br/servicos/empregador/mediacao/registro-de-convencoes-e-acordo-coletivo-de-trabalho);
- [CLT compilada](https://www.planalto.gov.br/ccivil_03/decreto-lei/del5452compilado.htm), especialmente regras
  de concessão e fracionamento de férias;
- [Lei 4.090/1962](https://www.planalto.gov.br/ccivil_03/leis/l4090.htm), sobre gratificação natalina.

## Critério para chegar a 90

O software oferece o caminho e os bloqueios, mas cada empresa precisa preencher evidências reais. Uma
competência alcança pelo menos 90 em cada dimensão quando há vínculos completos, jornada sem inconsistência,
tabela legal suportada, eventos variáveis governados e os quatro temas de conformidade revisados ou marcados
como não aplicáveis com justificativa. A pontuação não atesta transmissão nem homologação externa.

## Próximas liberações condicionadas

1. cálculo homologado de férias, 13º e rescisão, inclusive médias, incidências, adiantamentos e motivos;
2. calendário de feriados/DSR por vínculo e motor de cláusulas de CCT/ACT versionado;
3. múltiplos vínculos, adicionais noturno/periculosidade/insalubridade e benefícios;
4. geração XML, assinatura, filas, retificação, fechamento/reabertura e recibos reais do eSocial;
5. conciliação de retornos do eSocial com FGTS Digital e DCTFWeb;
6. homologação jurídica, contábil e trabalhista com casos reais anonimizados antes de produção integral.
