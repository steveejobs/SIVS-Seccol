# Plano de homologação NF-e / certificado A1

Data de referência: 25/08/2026  
Escopo atual: NF-e modelo 55, empresa emitente em Goiás.

## Conclusão executiva

O certificado A1 é necessário, mas não torna o SIVS emissor de NF-e por si só. No estado atual, o
SIVS guarda o A1 cifrado, valida CNPJ/vigência/chave e consulta o status do serviço da SEFAZ por mTLS.
A emissão continua deliberadamente bloqueada (`canIssue=false`) porque o ciclo fiscal completo ainda
não foi implementado nem homologado externamente.

## Pré-requisitos externos da empresa

1. Inscrição estadual ativa e situação fiscal regular em Goiás.
2. Certificado ICP-Brasil de pessoa jurídica A1 (`.pfx`/`.p12`) e senha, com CNPJ da mesma raiz da
   unidade emitente.
3. Credenciamento da empresa no Domicílio Tributário Eletrônico (DT-e).
4. Credenciamento específico para emissão de NF-e.
5. Responsável fiscal/contábil para aprovar CRT, CFOP, CST/CSOSN, NCM, benefícios, operações,
   alíquotas e tratamento IBS/CBS/IS da Reforma Tributária.
6. Ambiente de homologação da SEFAZ disponível e dados de teste aprovados.

Fontes oficiais:

- Secretaria da Economia de Goiás — NF-e e preparação da empresa:
  https://goias.gov.br/economia/nf-e-nota-fiscal-eletronica/
- Secretaria da Economia de Goiás — DT-e:
  https://goias.gov.br/economia/domicilio-tributario-eletronico-dte-perguntas-e-respostas/
- Portal Nacional NF-e — serviços autorizadores:
  https://www.nfe.fazenda.gov.br/portal/webservices.aspx
- Portal Nacional NF-e — notas técnicas e leiautes:
  https://www.nfe.fazenda.gov.br/Portal/listaConteudo.aspx?tipoConteudo=04BIflQt1aY=
- ITI — certificação digital ICP-Brasil:
  https://www.gov.br/iti/pt-br/acesso-a-informacao/perguntas-frequentes/certificacao-digital

## O que já está implementado

- cofre AES-256-GCM com chave externa `SIVS_FISCAL_MASTER_KEY`;
- senha do PFX nunca persistida, auditada ou devolvida ao navegador;
- validação de vigência, chave privada correspondente, uso de assinatura e autenticação TLS;
- extração do CNPJ pelo OID ICP-Brasil `2.16.76.1.3.3` e comparação da raiz empresarial;
- configuração multiempresa/unidade, endpoints oficiais HTTPS e bloqueio de produção por flag;
- consulta `NFeStatusServico4` SOAP 1.2 com certificado cliente e registro auditável do `cStat`;
- schemas locais para documentos, itens, regras, perfis, XML e eventos;
- importação segura de XML recebido e exportação contábil local.

## Implementação ainda obrigatória

1. Congelar pacote oficial de XSD e Notas Técnicas vigentes, incluindo RTC/IBS/CBS/IS, com hash,
   vigência e trilha de atualização.
2. Implementar cálculo tributário determinístico por operação e item, sem valores padrão fictícios;
   toda regra deve ser aprovada pela contabilidade e versionada.
3. Gerar chave de acesso, número/série, `ide`, emitente, destinatário, itens, totais, transporte,
   cobrança/pagamento e informações adicionais da NF-e 4.00.
4. Validar XML contra XSD antes de qualquer transmissão.
5. Assinar `infNFe` com XMLDSig conforme o MOC e validar localmente a assinatura.
6. Implementar autorização síncrona/assíncrona, recibo, consulta de retorno e união de `protNFe` ao XML.
7. Tratar rejeições por código sem avançar estoque/financeiro indevidamente; reenvio deve ser
   idempotente e preservar número, lote, recibo e tentativa.
8. Gerar DANFE somente de XML autorizado.
9. Implementar consulta de protocolo, distribuição/armazenamento, cancelamento por evento,
   inutilização de faixa e contingência autorizada para Goiás.
10. Definir retenção, backup externo, monitoramento de validade do A1, renovação e plano de revogação.

## Critérios para homologação

- A1 real importado com CNPJ correto e consulta de status retornando serviço em operação;
- emissão em homologação de todos os cenários tributários representativos da SECCOL;
- rejeições intencionais tratadas sem duplicidade ou efeito financeiro/estoque;
- autorização, retorno, XML protocolado e DANFE conferidos pela contabilidade;
- cancelamento, inutilização, consulta e indisponibilidade/retomada ensaiados;
- numeração concorrente testada com duas requisições simultâneas;
- restauração de XML, protocolo e auditoria em ambiente separado;
- aprovação formal da contabilidade e da direção antes de habilitar produção;
- produção liberada apenas com `SIVS_ALLOW_SEFAZ_PRODUCTION=1`, janela de mudança, monitoramento e
  procedimento de retorno.

## Teste seguro quando o A1 chegar

1. Configurar `SIVS_FISCAL_MASTER_KEY` com 32 bytes aleatórios em Base64 no runtime.
2. Manter ambiente `HOMOLOGATION` e produção bloqueada.
3. Conferir CNPJ, IE, município IBGE, CRT e endpoints oficiais no painel Fiscal.
4. Importar o PFX pelo painel; o SIVS deve recusar certificado de outra raiz ou fora da vigência.
5. Executar somente **Consultar status da SEFAZ**. Resultado esperado em operação: `cStat=107`.
6. Se houver falha, revisar cadeia ICP-Brasil, credenciamento, senha, validade, relógio do servidor,
   firewall/TLS e endpoint estadual. Não habilitar produção para “testar”.

Esse teste comprova cofre, mTLS e disponibilidade do autorizador. Ele não comprova emissão de NF-e;
os critérios anteriores continuam obrigatórios.
