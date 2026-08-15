# Auditoria UI/UX — refinamento de componentes e novos registros

Data: 15/08/2026  
Versão analisada: SIVS SECCOL 2.2.0

## Resultado executivo

O SIVS preserva a navegação e a linguagem visual já reconhecidas pelos usuários, mas deixa de
apresentar controles com aparência antiga e reduz a carga cognitiva do cadastro. Nenhuma função,
campo, validação, permissão ou regra de auditoria foi removida.

O maior problema encontrado não era falta de recursos. Era a apresentação simultânea de muitos
campos opcionais, cartões aninhados e divisórias competindo pela atenção. A correção adotada foi
revelação progressiva, hierarquia mais leve e modernização dos componentes transversais.

## Achados e decisões

| Área | Diagnóstico | Solução aplicada | Garantia funcional |
|---|---|---|---|
| Rolagem | Barras largas, botões de extremidade e trilho com aparência antiga | Barra fina, arredondada, sem botões, com contraste no hover e variação para fundos escuros | Rolagem por mouse, touchpad, toque e teclado permanece nativa |
| Listas | Muitas linhas horizontais fragmentavam a leitura | Agrupamento por proximidade, fundo sutil no hover e destaque lateral para não lidos | Estrutura e ações das listas foram preservadas |
| Tabelas | Cabeçalho se perdia em listas longas | Cabeçalho local fixo e rolagem contida | A tabela continua horizontalmente rolável em telas estreitas |
| Selects | Picker dependia integralmente do visual do sistema operacional | Picker com cantos, sombra, seleção, checkmark e opções de 40 px quando `base-select` existe | Navegadores sem suporte recebem o select nativo com fallback visual; sem JavaScript customizado |
| Novo registro | Campos obrigatórios e opcionais apareciam juntos | Modo essencial por padrão e botão “Mostrar detalhes” | Todos os campos continuam no DOM, no payload e na validação |
| Edição | Ocultar detalhes poderia fazer dados existentes parecerem ausentes | Registros existentes abrem totalmente expandidos | Nenhum dado salvo fica escondido durante revisão |
| Rascunho | Rascunho pode conter valores opcionais | Restaurar rascunho expande os detalhes automaticamente | Conteúdo recuperado fica imediatamente visível |
| Validação | Um obrigatório futuramente oculto poderia ficar inacessível | A validação expande o bloco antes de rolar e focar o campo | Erro continua acionável por teclado e leitor de tela |
| Mobile | Cartões aninhados e controles pequenos aumentavam a densidade | Grupos internos são achatados no modo essencial e controles têm alvo mínimo de 44 px | Cabeçalho e rodapé do diálogo continuam alcançáveis |

## Contrato do cadastro progressivo

Ao criar um registro:

1. aparecem identificação, situação, assunto, base normativa quando exigida e campos específicos
   realmente obrigatórios;
2. valor, prazo, responsável, contato, vínculos adicionais, observações, arquivos e aprovações ficam
   em “Mostrar detalhes”;
3. o indicador informa quantos obrigatórios faltam sem exigir que o usuário conte campos;
4. abrir uma seção opcional pelo guia lateral expande os detalhes antes da rolagem;
5. salvar continua sujeito às mesmas validações do frontend e do servidor.

Ao editar um registro, todos os campos ficam visíveis. Essa assimetria é intencional: criação pede
foco e velocidade; edição pede conferência completa.

## Select moderno com fallback

A implementação usa melhoria progressiva com `appearance: base-select`. Isso mantém a semântica do
`<select>`, envio de formulário e navegação nativa por teclado, sem recriar um combobox frágil em
JavaScript. A direção segue a documentação do
[Chrome](https://developer.chrome.com/blog/a-customizable-select?hl=en), as notas do
[Microsoft Edge 134](https://learn.microsoft.com/en-us/microsoft-edge/web-platform/release-notes/134)
e o trabalho de padronização em [CSS Form Styling](https://drafts.csswg.org/css-forms/).

## Matriz validada em navegador real

| Perfil | Viewport | Resultado |
|---|---:|---|
| Desktop | 1440 × 1000 | aprovado |
| Tablet | 834 × 1112 | aprovado |
| Mobile | 390 × 844 | aprovado |
| Mobile compacto | 360 × 800 | aprovado |

O auditor percorreu 54 destinos em cada viewport: 216 combinações sem overflow de documento. Também
foram aprovados 23 fluxos reais, incluindo diálogo, modo essencial, abertura do picker, revelação de
detalhes, restauração de rascunho, busca global e drawer responsivo. As capturas e relatórios ficam em
`.artifacts/responsive-audit/` e não entram no pacote de produção.

## Validação técnica

- 26 de 26 testes Python aprovados;
- contratos de IDs, ordem de ativos, tokens e fallback do picker aprovados;
- sintaxe de todos os módulos JavaScript e do auditor aprovada;
- compilação dos módulos Python aprovada;
- verificação de espaços e conflitos de patch aprovada;
- auditor de imagens executado em modo seguro; não há raster compatível no pacote atual.

## Arquivos centrais desta rodada

- `static/theme/components.css`: scrollbars, selects, listas, tabelas e formulário progressivo;
- `static/js/ui/record-disclosure.js`: estado essencial/completo e integração acessível;
- `static/app.js`: classificação dinâmica de campos e integração com validação/rascunho;
- `static/index.html`: microcopy, controle de detalhes e semântica do diálogo;
- `tools/responsive_audit.mjs`: evidências de picker, detalhes e rascunho por viewport.

## Próximas melhorias recomendadas

1. transformar a busca + select de “Registro relacionado” em combobox acessível único;
2. conduzir teste moderado com usuários antigos para ajustar nomes e ordem dos campos por módulo;
3. criar preferência de densidade para tabelas extensas, mantendo a densidade atual como padrão;
4. extrair o formulário especializado de `app.js` para `js/modules/records/` sem alterar contratos.

