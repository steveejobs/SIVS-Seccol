from datetime import date
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart

OUT = "docs/security-audit/relatorio-auditoria-seguranca.pdf"
PROJECT = "SIVS SECCOL"
RED = {"crítica": "#B91C1C", "alta": "#EA580C", "média": "#D97706", "baixa": "#2563EB", "ponto forte": "#059669"}

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="Cover", parent=styles["Title"], alignment=TA_CENTER, fontSize=24, leading=30, textColor=colors.HexColor("#17324D"), spaceAfter=18))
styles.add(ParagraphStyle(name="Sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=11, leading=16))
styles.add(ParagraphStyle(name="H", parent=styles["Heading2"], textColor=colors.HexColor("#17324D"), spaceBefore=10, spaceAfter=8))
styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8.5, leading=11))
styles.add(ParagraphStyle(name="Issue", parent=styles["Code"], fontSize=7.5, leading=9))

def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(2*cm, 1.15*cm, "Relatório de Auditoria de Segurança — SIVS SECCOL")
    canvas.drawRightString(A4[0]-2*cm, 1.15*cm, f"Página {doc.page}"); canvas.restoreState()

def charts():
    d = Drawing(460, 190)
    pie = Pie(); pie.x=15; pie.y=15; pie.width=140; pie.height=140; pie.data=[1,1,0.001,0.001,0.001]; pie.labels=["Crítica","Alta","Média","Baixa","Ponto forte"]; pie.slices.strokeWidth=0
    for i,c in enumerate([RED["crítica"],RED["alta"],RED["média"],RED["baixa"],RED["ponto forte"]]): pie.slices[i].fillColor=colors.HexColor(c)
    d.add(pie)
    bar = VerticalBarChart(); bar.x=220; bar.y=25; bar.height=125; bar.width=220; bar.data=[[1,0,0,1,0]]; bar.categoryAxis.categoryNames=["Banco","Navegador","IDOR","Chaves","XSS"]; bar.valueAxis.valueMin=0; bar.valueAxis.valueMax=1.2; bar.valueAxis.valueStep=1; bar.bars[0].fillColor=colors.HexColor("#2563EB"); bar.bars[0].strokeColor=None
    d.add(bar); return d

def p(txt, style="Normal"): return Paragraph(txt, styles[style])

findings = [
    ("CRÍTICA", "sivs_2_2/server.py:15156-15164; 6047-6058", "Achado confirmado na auditoria e corrigido nesta revisão: conta com vínculo ativo em outra empresa só tem a senha global alterada por administrador geral, definido como admin ativo de todas as empresas ativas.", "has_other_active_membership + is_general_admin; teste de regressão em sivs_2_2/tests/test_server.py:1738."),
    ("ALTA", "api_open_router:1 (commit 59fca305da6a631636f306af241d9e4d224b72ea)", "Chave OpenRouter em texto claro foi commitada e continua recuperável no histórico Git, mesmo após a exclusão do arquivo no commit 0327246.", "api_open_router:1 = token com padrão sk- (valor integral omitido no relatório para não reexpor o segredo)."),
]

issues = [
"--- ISSUE 1 ---\n# [Segurança] Impedir redefinição de senha global por administrador de tenant\nLabels sugeridas: security, crítica\n\n## Descrição\n`user_password_reset` valida que o alvo pertence à empresa atual, mas altera a credencial global em `users`. O login depois aceita qualquer associação ativa do usuário, permitindo que um administrador de A assuma uma conta que também pertence a B.\n\n## Evidência\n`sivs_2_2/server.py:15122-15150` — `UPDATE users SET password_hash=? WHERE id=?` e exclusão global de sessões; `sivs_2_2/server.py:8891-8936` — login global por e-mail e seleção de qualquer membership.\n\n## Impacto\nTomada de identidade e acesso a dados de outros tenants.\n\n## Correção sugerida\nUse credenciais/fluxo de recuperação escopados ao tenant, ou exija reautenticação/out-of-band do próprio usuário. Não permita que admin de tenant defina senha global; revogue sessões conforme a política explícita.\n\n## Critérios de aceite\n- [ ] Admin de A não consegue alterar a senha global de usuário membro de B.\n- [ ] Fluxo de recuperação exige prova de posse da conta.\n- [ ] Teste automatizado cobre login A/B e revogação de sessões.\n--- FIM ISSUE 1 ---",
"--- ISSUE 2 ---\n# [Segurança] Revogar e remover chave OpenRouter exposta no histórico Git\nLabels sugeridas: security, alta\n\n## Descrição\nO arquivo `api_open_router` contém uma chave `sk-...` em texto claro no commit `59fca305da6a631636f306af241d9e4d224b72ea`; apagar o arquivo não remove o segredo dos objetos Git.\n\n## Evidência\n`api_open_router:1` no commit acima (valor integral redigido).\n\n## Impacto\nUso indevido da API, custos financeiros e possível acesso a dados enviados ao provedor.\n\n## Correção sugerida\nRevogue/rotacione a chave, remova-a de todas as referências Git com filter-repo/BFG, verifique branches/tags/remotes e habilite secret scanning no CI.\n\n## Critérios de aceite\n- [ ] Chave revogada e nova credencial distribuída via secret manager.\n- [ ] Busca em todas as refs não encontra o token.\n- [ ] CI bloqueia novos padrões de segredo.\n--- FIM ISSUE 2 ---",
]

story=[]
story += [Spacer(1,2*cm), p("Relatório de Auditoria de Segurança — SIVS SECCOL", "Cover"), p("Data: 29/08/2026<br/>Escopo: backend Python/http.server + SQLite, frontend HTML/CSS/JavaScript, deploy Docker/Nixpacks/Dokploy, scripts e histórico Git.", "Sub"), Spacer(1,1*cm), p("Nota metodológica: a categoria Banco sem tranca foi mapeada para filtros company_id/membership e RLS inexistente; Permissão definida no navegador foi cruzada entre gates do frontend e require_* no servidor; IDOR percorreu handlers por IDs; Chaves expostas cobriu código, configs, deploy, CI, bundle e todas as refs Git; XSS cobriu sinks HTML/URL/eval e escapes/validação equivalentes.", "Normal"), PageBreak()]
story += [p("Resumo executivo", "H"), p("A auditoria confirmou 2 achados: 1 crítica e 1 alta. Nesta revisão, o achado crítico foi corrigido e coberto por teste de regressão; a chave histórica permanece pendente de revogação e limpeza das referências Git. Não foram confirmados achados nas categorias Permissão definida no navegador, IDOR ou Inputs sem tratamento (XSS).", "Normal"), charts(), Spacer(1,8), p("Pontos fortes", "H"), p("• Sessões e autorização usam company_id, membership ativa, CSRF e gates de módulo/operação.<br/>• Administrador geral é agora verificado no servidor como admin ativo de todas as empresas ativas.<br/>• Handlers de anexos, aprovações, propostas, agente e relatórios validam posse por empresa.<br/>• Frontend esconde ações por capability, e o backend repete a verificação.<br/>• Datas são validadas no servidor; sinks HTML usam escapeHTML; URLs externas são restringidas a http/https.<br/>• Backup completo exige que o usuário seja admin em todas as empresas ativas.", "Normal"), p("Pontos fracos", "H"), p("A chave OpenRouter no histórico Git continua recuperável até ser revogada e as referências remotas serem higienizadas.", "Normal"), PageBreak()]
story += [p("Achados detalhados", "H")]
rows=[[p("Severidade","Small"),p("Arquivo:linha","Small"),p("Descrição e evidência","Small")]]
for sev,loc,desc,ev in findings:
    rows.append([p(f'<font color="{RED[sev.lower()]}"><b>{sev}</b></font>',"Small"),p(loc,"Small"),p(desc+"<br/><b>Evidência:</b> "+ev,"Small")])
t=Table(rows,colWidths=[2.4*cm,6.0*cm,8.2*cm],repeatRows=1); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E7EEF5")),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#CBD5E1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5)])); story += [t, Spacer(1,10), p("Recomendações priorizadas", "H"), p("P1 — revogar/rotacionar a chave e purgar o histórico; redesenhar o reset de senha para não permitir alteração global por admin de tenant.<br/>P2 — adicionar testes de regressão A/B e matriz de autorização para todos os handlers.<br/>P3 — habilitar secret scanning obrigatório no CI e revisar referências Git antes de cada release.", "Normal"), PageBreak(), p("ISSUES PARA O GITHUB", "H")]
for issue in issues: story += [p(issue.replace("\n","<br/>"),"Issue"), Spacer(1,10)]

SimpleDocTemplate(OUT,pagesize=A4,rightMargin=2*cm,leftMargin=2*cm,topMargin=2*cm,bottomMargin=1.8*cm,title="Relatório de Auditoria de Segurança — SIVS SECCOL").build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
