#!/usr/bin/env python3
"""Gera o relatorio verificavel da auditoria de seguranca.

Uso isolado:
  python -m venv docs/security-audit/.venv
  docs/security-audit/.venv/Scripts/python -m pip install reportlab matplotlib
  docs/security-audit/.venv/Scripts/python docs/security-audit/generate_report.py
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, Preformatted, Spacer, Table, TableStyle, SimpleDocTemplate

OUT = Path(__file__).with_name("relatorio-auditoria-seguranca.pdf")
NAME = "Relatorio de Auditoria de Seguranca - SIVS SECCOL"
C = {"Critica": "#B91C1C", "Alta": "#EA580C", "Media": "#D97706", "Baixa": "#2563EB", "Ponto forte": "#059669", "Ink": "#1F2937", "Muted": "#4B5563", "Line": "#D1D5DB"}
FINDINGS = [
 {"id":"F-01","cat":"Banco sem tranca / IDOR","sev":"Alta","loc":"sivs_2_2/server.py:15137, 15146, 15150",
  "title":"Redefinicao de senha global permite tomada de conta entre empresas",
  "code":'membership = ... SELECT 1 FROM company_memberships WHERE company_id=? AND user_id=?\nUPDATE users SET password_hash=?,active=1,updated_at=? WHERE id=?\nDELETE FROM sessions WHERE user_id=?',
  "why":"A autorizacao confirma somente o vinculo com a empresa ativa. A senha pertence a users, que e global; o login aceita qualquer empresa ativa vinculada ao mesmo usuario (server.py:8917-8932). Um admin da Empresa A pode definir senha conhecida para uma conta compartilhada com a Empresa B, autenticar-se como ela e selecionar a Empresa B.",
  "condition":"A conta alvo precisa ter memberships ativos em duas ou mais empresas; o atacante precisa ser admin em uma delas.",
  "fix":"P1: separar credenciais por tenant ou, enquanto a identidade for global, exigir autorizacao administrativa em todas as empresas do alvo. Limitar a revogacao de sessoes ao tenant autorizado e adicionar teste multiempresa."},
 {"id":"F-02","cat":"Chaves expostas (historico Git)","sev":"Alta","loc":"Git 59fca305da6a631636f306af241d9e4d224b72ea, api_open_router:1",
  "title":"Chave de API OpenRouter foi commitada no historico",
  "code":"api_open_router:1 contem chave no formato sk-or-v1-[REDACTED] (73 caracteres).",
  "why":"O arquivo foi adicionado no commit 59fca30 e removido no 0327246, mas o objeto continua acessivel por git show e por clones, forks, caches e CI que receberam o historico. Se a chave estiver ativa, permite consumo indevido da conta/provedor e acesso aos recursos por ela autorizados.",
  "condition":"O impacto permanece enquanto a credencial historica nao tiver sido revogada no provedor.",
  "fix":"P1: revogar e recriar a chave imediatamente, revisar uso/faturamento e reescrever o historico com coordenacao dos clones. Adotar secret scanning em pre-commit e CI."},
]

class Chip(Flowable):
 def __init__(self,label):
  super().__init__(); self.label=label; self.width=max(48,len(label)*5.2+14); self.height=15
 def draw(self):
  self.canv.setFillColor(colors.HexColor(C[self.label])); self.canv.roundRect(0,1,self.width,13,3,0,1)
  self.canv.setFillColor(colors.white); self.canv.setFont("Helvetica-Bold",7.5); self.canv.drawCentredString(self.width/2,4.5,self.label.upper())

def esc(text):
 return str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def P(text,style):
 return Paragraph(esc(text).replace("\n","<br/>"),style)
def footer(canvas,doc):
 canvas.saveState(); canvas.setStrokeColor(colors.HexColor(C["Line"])); canvas.setLineWidth(.35)
 canvas.line(2*cm,A4[1]-1.35*cm,A4[0]-2*cm,A4[1]-1.35*cm); canvas.line(2*cm,1.35*cm,A4[0]-2*cm,1.35*cm)
 canvas.setFont("Helvetica",7.5); canvas.setFillColor(colors.HexColor(C["Muted"])); canvas.drawString(2*cm,A4[1]-1.05*cm,NAME); canvas.drawRightString(A4[0]-2*cm,1.05*cm,"Pagina %s" % doc.page); canvas.restoreState()
def charts(folder):
 plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9}); donut=folder/"severidade.png"; bar=folder/"categoria.png"
 fig,ax=plt.subplots(figsize=(4.5,3),dpi=180); ax.pie([2],colors=[C["Alta"]],startangle=90,wedgeprops={"width":.42,"edgecolor":"white"}); ax.text(0,.08,"2",ha="center",va="center",fontsize=23,fontweight="bold",color=C["Ink"]); ax.text(0,-.18,"achados\naltos",ha="center",va="center",fontsize=9,color=C["Muted"]); ax.legend(["Alta"],loc="lower center",bbox_to_anchor=(.5,-.13),frameon=False); fig.tight_layout(); fig.savefig(donut,facecolor="white"); plt.close(fig)
 fig,ax=plt.subplots(figsize=(5.2,3),dpi=180); ax.barh(["Isolamento / IDOR","Segredos"],[1,1],color=[C["Alta"],C["Alta"]],height=.48); ax.set_xlim(0,1.25); ax.set_xlabel("Achados"); ax.spines[["top","right","left"]].set_visible(False); ax.grid(axis="x",color="#E5E7EB",linewidth=.7); ax.set_axisbelow(True); ax.tick_params(axis="y",length=0); ax.set_xticks([0,1]); [ax.text(1.03,i,"1",va="center",fontweight="bold",color=C["Ink"]) for i in range(2)]; fig.tight_layout(); fig.savefig(bar,facecolor="white"); plt.close(fig)
 return donut,bar

ISSUE1="""--- ISSUE 1 ---
# [Seguranca] Impedir redefinicao global de senha por admin de um unico tenant

Labels sugeridas: security, alta

## Problema
user_password_reset confirma apenas o membership do alvo na empresa ativa, mas atualiza users.password_hash, que e global. Um admin da Empresa A pode redefinir a senha de um usuario que tambem participa da Empresa B, autenticar-se como ele e selecionar a Empresa B no login.

## Evidencia
sivs_2_2/server.py:15137-15150
    SELECT 1 FROM company_memberships WHERE company_id=? AND user_id=?
    UPDATE users SET password_hash=?,active=1,updated_at=? WHERE id=?
    DELETE FROM sessions WHERE user_id=?
O login aceita membership ativo solicitado em sivs_2_2/server.py:8925-8927.

## Impacto
Tomada de conta e acesso aos dados de outras empresas vinculadas ao mesmo usuario.

## Sugestao de correcao
Separar credenciais por empresa ou exigir autorizacao administrativa em todas as empresas ativas do usuario antes de alterar uma credencial global. Reavaliar a revogacao de sessoes para limitar o escopo ao tenant autorizado.

## Criterios de aceite
- [ ] Admin de uma empresa nao consegue redefinir a senha de usuario compartilhado sem autorizacao para todos os tenants afetados.
- [ ] O login apos a tentativa nao permite acesso a outro tenant por essa senha.
- [ ] Sessoes de tenants nao autorizados nao sao revogadas.
- [ ] Teste HTTP cobre duas empresas e uma conta compartilhada.
--- FIM ISSUE 1 ---"""
ISSUE2="""--- ISSUE 2 ---
# [Seguranca] Revogar chave OpenRouter exposta no historico Git

Labels sugeridas: security, alta

## Problema
Uma chave no formato OpenRouter foi adicionada ao arquivo api_open_router no commit 59fca305da6a631636f306af241d9e4d224b72ea. O arquivo foi removido depois, mas o segredo continua recuperavel no historico Git.

## Evidencia
api_open_router:1 no commit 59fca305da6a631636f306af241d9e4d224b72ea contem sk-or-v1-[REDACTED] (73 caracteres).

## Impacto
Enquanto ativa, a chave pode permitir consumo indevido da conta/provedor e acesso aos recursos autorizados por ela. O alcance inclui clones, forks, caches e CI que obtiveram o historico.

## Sugestao de correcao
Revogar a chave no OpenRouter, emitir uma substituta em segredo de runtime, revisar uso/faturamento e reescrever o historico com procedimento coordenado. Adicionar secret scanning no pre-commit e CI.

## Criterios de aceite
- [ ] A chave historica foi revogada e o evento registrado.
- [ ] Uma chave nova esta somente no cofre de segredos/runtime.
- [ ] Uso e faturamento foram revisados para o periodo de exposicao.
- [ ] O historico remoto e clones essenciais foram saneados conforme procedimento aprovado.
- [ ] CI ou pre-commit bloqueia novos segredos de alta confianca.
--- FIM ISSUE 2 ---"""

def build():
 base=getSampleStyleSheet()
 title=ParagraphStyle("title",parent=base["Title"],fontName="Helvetica-Bold",fontSize=23,leading=28,alignment=TA_CENTER,textColor=colors.HexColor(C["Ink"]),spaceAfter=10)
 sub=ParagraphStyle("sub",parent=base["Normal"],fontSize=10,leading=14,alignment=TA_CENTER,textColor=colors.HexColor(C["Muted"]))
 h1=ParagraphStyle("h1",parent=base["Heading1"],fontName="Helvetica-Bold",fontSize=15,leading=19,textColor=colors.HexColor(C["Ink"]),spaceBefore=8,spaceAfter=7)
 h2=ParagraphStyle("h2",parent=base["Heading2"],fontName="Helvetica-Bold",fontSize=11,leading=14,textColor=colors.HexColor(C["Ink"]),spaceBefore=7,spaceAfter=4)
 body=ParagraphStyle("body",parent=base["BodyText"],fontSize=8.6,leading=12,textColor=colors.HexColor(C["Ink"]),spaceAfter=5)
 small=ParagraphStyle("small",parent=body,fontSize=7.4,leading=9.5,textColor=colors.HexColor(C["Muted"]))
 code=ParagraphStyle("code",fontName="Courier",fontSize=6.8,leading=8.5,leftIndent=4,textColor=colors.HexColor("#111827"))
 issue=ParagraphStyle("issue",fontName="Courier",fontSize=6.45,leading=8.05,textColor=colors.HexColor("#111827"))
 with TemporaryDirectory() as temp:
  donut,bar=charts(Path(temp)); doc=SimpleDocTemplate(OUT,pagesize=A4,leftMargin=2*cm,rightMargin=2*cm,topMargin=2*cm,bottomMargin=2*cm,title=NAME,author="Auditoria de seguranca")
  story=[Spacer(1,48*mm),Paragraph("Relatorio de Auditoria de Seguranca",title),Paragraph("SIVS SECCOL",ParagraphStyle("project",parent=sub,fontName="Helvetica-Bold",fontSize=15,leading=19,textColor=colors.HexColor(C["Ponto forte"]))),Spacer(1,12*mm),Paragraph("Data: "+date.today().strftime("%d/%m/%Y"),sub),Spacer(1,8*mm)]
  cover=[[P("Escopo auditado",h2),P("Backend Python/HTTP nativo e SQLite; frontend HTML/CSS/JavaScript; PWA; Docker/Nixpacks/Dokploy; CI, scripts, configuracoes e historico Git.",body)],[P("Nota metodologica",h2),P("Isolamento foi mapeado para filtros manuais por company_id e memberships; autorizacao para funcoes de servidor; IDOR para IDs em rotas; segredos para arquivos atuais e historico Git; e XSS para sinks DOM, URLs, templates e e-mail/PDF.",body)]]
  tab=Table(cover,colWidths=[35*mm,130*mm]); tab.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#ECFDF5")),("BOX",(0,0),(-1,-1),.45,colors.HexColor(C["Line"])),("INNERGRID",(0,0),(-1,-1),.35,colors.HexColor(C["Line"])),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
  story += [tab,PageBreak(),Paragraph("Resumo executivo",h1),P("Foram confirmados dois achados de severidade alta. Nenhuma falha verificada foi encontrada em permissao definida apenas no navegador, IDOR convencional nas rotas revisadas ou XSS. A ausencia de achados nessas categorias nao substitui retestes apos mudancas futuras.",body)]
  st=Table([[Chip("Critica"),"0"],[Chip("Alta"),"2"],[Chip("Media"),"0"],[Chip("Baixa"),"0"],[P("Total",h2),P("2",h2)]],colWidths=[44*mm,16*mm],hAlign="LEFT"); st.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.35,colors.HexColor(C["Line"])),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(1,0),(1,-1),"CENTER"),("LEFTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
  graphs=Table([[st,Image(str(donut),width=61*mm,height=41*mm),Image(str(bar),width=76*mm,height=41*mm)]],colWidths=[63*mm,63*mm,72*mm]); graphs.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
  story += [Spacer(1,3*mm),graphs,Paragraph("Pontos fortes",h1)]
  strengths=["Isolamento: a sessao associa membership ativo e company_id (server.py:6004-6013); registros verificam id e company_id antes de escrever (server.py:14512-14518).","Backup integral: exige admin em todas as empresas ativas antes de copiar SQLite (server.py:26518-26529).","Permissoes: controles canAction do frontend possuem require_admin, require_module_* ou require_operation correspondentes no servidor (server.py:6041-6156 e 6780-7189).","XSS: escapeHTML codifica HTML e safeExternalURL aceita somente HTTP/HTTPS (static/js/core/formatters.js:15-29); datas sao validadas no servidor (server.py:14162-14166).","Segredos atuais: .env.example nao contem valores e .gitignore exclui .env; Dockerfile recebe segredos no runtime conforme DOKPLOY.md."]
  story += [P("• "+x,body) for x in strengths]; story += [Paragraph("Achados detalhados",h1)]
  rows=[[P("Severidade",small),P("Arquivo:linha",small),P("Descricao",small)]]
  for f in FINDINGS: rows.append([Chip(f["sev"]),P(f["loc"],small),P(f["id"]+" - "+f["title"]+"\n"+f["why"]+"\nCondicao: "+f["condition"],small)])
  ft=Table(rows,colWidths=[25*mm,55*mm,118*mm],repeatRows=1); ft.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F1F5F9")),("GRID",(0,0),(-1,-1),.35,colors.HexColor(C["Line"])),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)])); story.append(ft)
  for f in FINDINGS: story += [Paragraph(f["id"]+" - Evidencia e impacto",h2),P("Trecho: "+f["loc"],small),Preformatted(f["code"],code),P("Por que e exploravel: "+f["why"],body),P("Condicao: "+f["condition"],body),P("Recomendacao: "+f["fix"],body)]
  story += [Paragraph("Recomendacoes priorizadas",h1),P("P1. Corrigir F-01 e adicionar cobertura de duas empresas com conta compartilhada. P1. Revogar a chave exposta de F-02 e auditar seu uso. P2. Introduzir secret scanning em pre-commit/CI e uma regra que impeça mutacoes globais acionadas por administradores de um tenant. P3. Manter testes de isolamento por rota em cada novo handler.",body),PageBreak(),Paragraph("ISSUES PARA O GITHUB",h1),P("Texto completo, pronto para copiar e colar.",small),Spacer(1,2*mm),Preformatted(ISSUE1,issue),Spacer(1,4*mm),Preformatted(ISSUE2,issue)]
  doc.build(story,onFirstPage=footer,onLaterPages=footer)
 print(OUT)
if __name__ == "__main__": build()
