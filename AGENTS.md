# Orientação para futuros contextos

Antes de alterar este repositório, leia integralmente `PROJECT_CONTEXT.md`. Ele é o documento vivo
de arquitetura, UI/UX, decisões, riscos, validações e próximos passos do SIVS SECCOL.

Regras locais essenciais:

- preservar isolamento multiempresa, permissões, auditoria e validação no servidor;
- não remover contratos de IDs usados por `tests/test_frontend_contract.py`;
- manter tema e motion em `sivs_2_2/static/theme/`;
- manter componentes comportamentais em `sivs_2_2/static/js/`;
- colocar utilitários de desenvolvimento em `tools/`, seguros por padrão e com modo de simulação;
- atualizar `PROJECT_CONTEXT.md` ao concluir mudanças materiais ou descobrir riscos novos;
- atualizar `sivs_2_2/ASSISTENTE_SISTEMA.md` na mesma alteração sempre que o Assistente do sistema,
  sua base de orientações, IA, permissões, limites ou experiência de uso forem modificados;
- respeitar `prefers-reduced-motion`, navegação por teclado e alvos de toque.
