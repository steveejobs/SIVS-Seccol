#!/usr/bin/env python3
"""SIVS — servidor local, API, persistência SQLite, backup e documentos técnicos."""

from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import csv
import hashlib
import hmac
import html
import io
import json
import math
import mimetypes
import os
import re
import secrets
import sqlite3
import tempfile
import threading
import time
import traceback
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DEFAULT_DB = BASE_DIR / "data" / "sivs.db"
SESSION_SECONDS = 12 * 60 * 60
PBKDF2_ITERATIONS = 310_000
MAX_BODY = 16 * 1024 * 1024
MAX_IMPORT_BODY = 128 * 1024 * 1024
MAX_ATTACHMENT = 10 * 1024 * 1024
MAX_RECORD_PAYLOAD = 1024 * 1024
VERSION = "2.2.0"


def mountinfo_has_path(contents: str, expected: str) -> bool:
    for line in contents.splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        mount_path = re.sub(
            r"\\([0-7]{3})",
            lambda match: chr(int(match.group(1), 8)),
            fields[4],
        )
        if mount_path == expected:
            return True
    return False


def database_directory_is_mount(path: Path) -> bool:
    """Detecta inclusive bind mounts Linux, que Path.is_mount pode nao reconhecer."""
    resolved = str(path.expanduser().resolve())
    mountinfo = Path("/proc/self/mountinfo")
    if mountinfo.exists():
        try:
            return mountinfo_has_path(mountinfo.read_text(encoding="utf-8"), resolved)
        except OSError:
            pass
    return path.is_mount()


def require_persistent_database(path: Path) -> bool:
    """Interrompe a producao se o SQLite apontar para um diretorio nao montado."""
    required = os.environ.get("SIVS_REQUIRE_PERSISTENT_DB") == "1"
    if not required:
        return False
    database_dir = path.expanduser().resolve().parent
    if not database_dir.exists():
        raise RuntimeError(
            f"Diretorio persistente do SQLite nao existe: {database_dir}"
        )
    if not database_directory_is_mount(database_dir):
        raise RuntimeError(
            "Persistencia obrigatoria ausente: monte um volume no diretorio "
            f"{database_dir} antes de iniciar o SIVS"
        )
    return True


PNCP_MAX_REQUESTS_PER_SEARCH = 9

DEFAULT_TENDER_KEYWORDS = [
    "controle de contaminação ambiental", "certificação de área limpa",
    "certificação de sala limpa", "qualificação de área limpa", "qualificação de sala limpa",
    "área limpa", "sala limpa", "ambiente controlado", "área classificada",
    "cabine de segurança biológica", "cabine de segurança microbiológica",
    "certificação de cabine", "manutenção de cabine de segurança biológica",
    "fluxo unidirecional", "módulo de fluxo unidirecional", "fluxo laminar",
    "capela de fluxo laminar", "manutenção de fluxo laminar", "capela de exaustão",
    "manutenção de capela de exaustão", "filtro HEPA", "filtros HEPA", "filtro ULPA", "filtros ULPA",
    "integridade de filtro HEPA", "teste de integridade HEPA", "teste PAO",
    "fotômetro de aerossol", "gerador de aerossol", "contagem de partículas",
    "contador de partículas", "partículas em suspensão", "qualificação de HVAC",
    "validação de HVAC", "balanceamento de insuflamento e exaustão",
    "pressão diferencial entre salas", "teste de recuperação", "trocas de ar por hora",
    "vazão de ar insuflado", "biodescontaminação", "descontaminação por VHP",
    "peróxido de hidrogênio vaporizado", "unidade de ventilação e descontaminação",
    "unidade de filtragem refrigerada", "rack isolador", "isolador farmacêutico",
    "difusor motorizado", "projeto de área limpa", "projeto de centro cirúrgico",
    "certificação de centro cirúrgico", "qualificação ISO 5", "certificação ISO 5", "ISO 14644",
    "velocidade e uniformidade do fluxo de ar", "ensaio de inflow",
    "perda de carga dos filtros", "detecção de vazamento HEPA", "ensaio de fumaça",
    "visualização do fluxo de ar", "avaliação de alarmes da CSB",
    "ensaio de intensidade de iluminação", "ensaio de vibração", "ensaio de ruído",
    "substituição de filtro HEPA", "troca de filtros HEPA", "reparo de filtro HEPA", "estanqueidade de filtro HEPA",
    "balanceamento de insuflamento e retorno", "radiação de lâmpada germicida",
    "saturação de filtro HEPA", "pressão diferencial do filtro", "selos de vedação",
    "componentes eletromecânicos", "certificação de fluxo laminar",
    "certificação de capela", "reforma de cabine", "reforma de capela"
]

# Termos que aumentam a aderência, mas não disparam oportunidades isoladamente.
SECCOL_CONTEXT_TERMS = [
    "reprodução assistida", "fertilização humana", "fertilização animal", "oncologia",
    "centro cirúrgico", "análises clínicas", "indústria farmacêutica", "nutrição parenteral",
    "nutrição enteral", "indústria de injetáveis", "indústria alimentícia", "cosmético",
    "indústria química", "indústria agropecuária", "biotecnologia", "instituto de pesquisa",
    "universidade", "laboratório P3", "laboratório NB3", "hospital", "life science",
    "contador de partículas", "fotômetro", "gerador de aerossol", "balometer", "luxímetro",
    "decibelímetro", "termo anemômetro", "manômetro digital", "termo higrômetro",
    "radiômetro", "ISO 21501-4", "ANVISA", "SBCC", "certificação", "qualificação",
    "manutenção", "reforma", "ensaio", "serviço técnico"
]

SOURCE_CATALOG = [
    ("pncp", "PNCP — Portal Nacional de Contratações Públicas", "https://pncp.gov.br/app/editais", "Nacional", "API automática", "Oficial"),
    ("comprasgov", "Compras.gov.br — Governo Federal", "https://www.gov.br/compras/pt-br", "Nacional/Federal", "API automática de contingência", "Oficial"),
    ("dou", "Diário Oficial da União — Imprensa Nacional", "https://www.in.gov.br/consulta", "Nacional", "Consulta manual/alerta oficial", "Oficial"),
    ("transparencia", "Portal da Transparência — Licitações", "https://portaldatransparencia.gov.br/licitacoes", "Federal", "Consulta manual — API planejada", "Oficial"),
    ("licitacoese", "Licitações-e — Banco do Brasil", "https://www.licitacoes-e.com.br/", "Nacional", "Consulta manual/autenticada", "Plataforma"),
    ("bll", "BLL Compras", "https://bll.org.br/editais/", "Nacional", "Consulta manual — sem scraping", "Plataforma"),
    ("pcp", "Portal de Compras Públicas", "https://www.portaldecompraspublicas.com.br/processos", "Nacional", "Consulta manual — automação externa vedada", "Plataforma"),
    ("licitanet", "Licitanet", "https://licitanet.com.br/", "Nacional", "Consulta manual", "Plataforma"),
    ("bnc", "Bolsa Nacional de Compras — BNC", "https://bnc.org.br/", "Nacional", "Consulta manual", "Plataforma"),
    ("sp", "Portal de Compras do Estado de São Paulo", "https://compras.sp.gov.br/", "SP", "Consulta manual", "Estadual"),
    ("mg", "Portal de Compras de Minas Gerais", "https://compras.mg.gov.br/", "MG", "Consulta manual", "Estadual"),
    ("rj", "Compras do Estado do Rio de Janeiro", "https://www.compras.rj.gov.br/", "RJ", "Consulta manual", "Estadual"),
    ("es", "Portal de Compras do Espírito Santo", "https://compras.es.gov.br/", "ES", "Consulta manual", "Estadual"),
    ("rs", "Compras Eletrônicas do Rio Grande do Sul", "https://www.compras.rs.gov.br/", "RS", "Consulta manual", "Estadual"),
    ("sc", "Portal de Compras de Santa Catarina", "https://compras.sc.gov.br/", "SC", "Consulta manual", "Estadual"),
    ("pr", "Compras Paraná", "https://www.comprasparana.pr.gov.br/", "PR", "Consulta manual", "Estadual"),
    ("ba", "ComprasNet Bahia", "https://www.comprasnet.ba.gov.br/", "BA", "Consulta manual", "Estadual"),
    ("ce", "Portal de Compras do Ceará", "https://www.portalcompras.ce.gov.br/", "CE", "Consulta manual", "Estadual"),
    ("pe", "Portal de Compras de Pernambuco", "https://www.peintegrado.pe.gov.br/", "PE", "Consulta manual/autenticada", "Estadual"),
    ("pb", "Central de Compras da Paraíba", "https://centraldecompras.pb.gov.br/", "PB", "Consulta manual", "Estadual"),
    ("rn", "Portal de Compras do Rio Grande do Norte", "https://portaldecompras.rn.gov.br/", "RN", "Consulta manual", "Estadual"),
    ("al", "Portal de Compras de Alagoas", "https://compras.al.gov.br/", "AL", "Consulta manual", "Estadual"),
    ("se", "ComprasNet Sergipe", "https://www.comprasnet.se.gov.br/", "SE", "Consulta manual", "Estadual"),
    ("go", "SISLOG — Compras de Goiás", "https://sislog.go.gov.br/", "GO", "Consulta manual", "Estadual"),
    ("to", "Central de Compras do Tocantins", "https://centraldecompras.to.gov.br/", "TO", "Consulta manual prioritária", "Estadual"),
    ("mt", "Portal de Aquisições de Mato Grosso", "https://aquisicoes.seplag.mt.gov.br/", "MT", "Consulta manual", "Estadual"),
    ("ms", "Portal de Compras de Mato Grosso do Sul", "https://www.compras.ms.gov.br/", "MS", "Consulta manual", "Estadual"),
    ("df", "Portal de Compras do Distrito Federal", "https://www.compras.df.gov.br/", "DF", "Consulta manual", "Distrital"),
    ("pa", "Portal de Compras do Pará", "https://www.compraspara.pa.gov.br/", "PA", "Consulta manual prioritária", "Estadual"),
    ("am", "e-Compras Amazonas", "https://www.e-compras.am.gov.br/publico/", "AM", "Consulta manual", "Estadual"),
    ("ro", "SUPEL — Licitações de Rondônia", "https://rondonia.ro.gov.br/supel/", "RO", "Consulta manual", "Estadual"),
    ("ac", "Portal de Licitações do Acre", "https://www.ac.gov.br/", "AC", "Consulta manual", "Estadual"),
    ("rr", "Portal de Compras de Roraima", "https://www.gov.br/compras/pt-br", "RR", "Cobertura PNCP/Compras.gov", "Estadual"),
    ("ap", "Central de Licitações do Amapá", "https://compras.portal.ap.gov.br/", "AP", "Consulta manual", "Estadual"),
    ("ma", "Portal de Compras do Maranhão", "https://www.compras.ma.gov.br/", "MA", "Consulta manual", "Estadual"),
    ("pi", "Portal de Compras do Piauí", "https://sistemas.tce.pi.gov.br/licitacoesweb/", "PI", "Consulta manual", "Estadual"),
    ("cnes", "CNES — Estabelecimentos de Saúde", "https://cnes.datasus.gov.br/", "Nacional", "Prospecção privada — não é edital", "Mercado privado"),
    ("anahp", "ANAHP — Hospitais Privados", "https://www.anahp.com.br/", "Nacional", "Prospecção privada — não é edital", "Mercado privado"),
]

# Catálogo curado em 15/08/2026. Para normas comerciais, a instalação inclui
# uma ficha autoral de referência e o link oficial; a íntegra licenciada deve
# ser anexada pela empresa que detém a licença de uso.
NORM_CATALOG = [
    {
        "key": "iso-14644-1-2015", "code": "ISO 14644-1:2015", "organization": "ISO",
        "edition": "2ª edição · 2015", "status": "Publicada — em revisão sistemática",
        "scope": "Classificação da limpeza do ar pela concentração de partículas em salas e zonas limpas.",
        "application": "Classificação ISO de áreas limpas e dispositivos separativos.",
        "tests": "Contagem de partículas; definição de classe de limpeza; plano de amostragem.",
        "url": "https://www.iso.org/standard/53394.html", "license": "Comercial/licenciada",
    },
    {
        "key": "iso-14644-2-2015", "code": "ISO 14644-2:2015", "organization": "ISO",
        "edition": "2ª edição · 2015", "status": "Publicada — em revisão sistemática",
        "scope": "Requisitos mínimos para o plano de monitoramento do desempenho de salas limpas.",
        "application": "Definição de frequência, parâmetros e evidências do monitoramento continuado.",
        "tests": "Monitoramento de partículas e parâmetros que afetam a concentração no ar.",
        "url": "https://www.iso.org/standard/53393.html", "license": "Comercial/licenciada",
    },
    {
        "key": "iso-14644-3-2019", "code": "ISO 14644-3:2019", "organization": "ISO",
        "edition": "2ª edição · 2019", "status": "Publicada",
        "scope": "Métodos de ensaio para caracterizar o desempenho de salas e zonas limpas.",
        "application": "Base técnica principal dos ensaios de qualificação e certificação de áreas limpas.",
        "tests": "Fluxo e velocidade do ar; diferencial de pressão; integridade HEPA; visualização; recuperação; partículas.",
        "url": "https://www.iso.org/standard/60598.html", "license": "Comercial/licenciada",
    },
    {
        "key": "iso-14644-4-2022", "code": "ISO 14644-4:2022", "organization": "ISO",
        "edition": "2ª edição · 2022", "status": "Publicada",
        "scope": "Projeto, construção e partida de salas limpas e ambientes controlados associados.",
        "application": "Projetos, reformas, comissionamento e critérios de aceitação de áreas limpas.",
        "tests": "Requisitos do usuário; projeto; construção; comissionamento; entrega documental.",
        "url": "https://www.iso.org/standard/72379.html", "license": "Comercial/licenciada",
    },
    {
        "key": "iso-14644-5-2025", "code": "ISO 14644-5:2025", "organization": "ISO",
        "edition": "2ª edição · 2025", "status": "Publicada",
        "scope": "Programa de controle operacional para salas limpas em funcionamento.",
        "application": "Operação, limpeza, manutenção, pessoal, materiais e acompanhamento de desempenho.",
        "tests": "Controles operacionais; procedimentos; treinamento; limpeza; manutenção e monitoramento.",
        "url": "https://www.iso.org/standard/88599.html", "license": "Comercial/licenciada",
    },
    {
        "key": "iso-14644-7-2004", "code": "ISO 14644-7:2004", "organization": "ISO",
        "edition": "1ª edição · 2004", "status": "Publicada — revisão em desenvolvimento",
        "scope": "Requisitos mínimos para dispositivos separativos, como cabines, isoladores e ambientes de luvas.",
        "application": "Cabines de segurança, fluxos unidirecionais, isoladores e equipamentos de contenção.",
        "tests": "Desempenho do dispositivo; contenção; fluxo de ar; integridade de barreiras e filtros.",
        "url": "https://www.iso.org/standard/38264.html", "license": "Comercial/licenciada",
    },
    {
        "key": "iso-iec-17025-2017", "code": "ISO/IEC 17025:2017", "organization": "ISO/IEC",
        "edition": "3ª edição · 2017", "status": "Publicada — confirmada em 2023",
        "scope": "Requisitos gerais para competência, imparcialidade e operação consistente de laboratórios.",
        "application": "Governança dos ensaios e calibrações, rastreabilidade, validade de resultados e laudos.",
        "tests": "Competência; métodos; equipamentos; rastreabilidade; incerteza; validade; relato de resultados.",
        "url": "https://www.iso.org/standard/66912.html", "license": "Comercial/licenciada",
    },
    {
        "key": "nsf-ansi-49-2022", "code": "NSF/ANSI 49-2022", "organization": "NSF/ANSI",
        "edition": "Edição 2022", "status": "Publicada",
        "scope": "Desempenho, construção e certificação em campo de cabines de segurança biológica Classe II.",
        "application": "Certificação de cabines de segurança biológica Classe II.",
        "tests": "Velocidade de inflow/downflow; integridade HEPA; fumaça; alarmes; iluminação; ruído e vibração.",
        "url": "https://www.nsf.org/lab-testing/biosafety-cabinetry/biosafety-cabinet-certification",
        "license": "Comercial/licenciada",
    },
    {
        "key": "anvisa-rdc-50-2002", "code": "ANVISA RDC 50/2002", "organization": "ANVISA",
        "edition": "RDC nº 50 · 2002", "status": "Referência regulatória — verificar alterações aplicáveis",
        "scope": "Regulamento técnico para planejamento, programação, elaboração e avaliação de projetos físicos de estabelecimentos de saúde.",
        "application": "Projetos e avaliações de ambientes assistenciais e áreas de apoio em saúde.",
        "tests": "Requisitos de projeto físico, fluxos, instalações e ambientes de estabelecimentos assistenciais.",
        "url": "https://bvsms.saude.gov.br/bvs/saudelegis/anvisa/2002/res0050_21_02_2002.html",
        "license": "Acesso público",
    },
    {
        "key": "anvisa-rdc-67-2007", "code": "ANVISA RDC 67/2007", "organization": "ANVISA",
        "edition": "RDC nº 67 · 2007", "status": "Vigente com alterações — confirmar escopo aplicável",
        "scope": "Boas práticas de manipulação de preparações magistrais e oficinais para uso humano.",
        "application": "Ambientes e equipamentos de farmácias de manipulação, conforme o processo e o risco.",
        "tests": "Controles ambientais, instalações, equipamentos, limpeza e qualificação aplicáveis.",
        "url": "https://www.gov.br/anvisa/pt-br/setorregulado/regularizacao/farmacias-e-drogarias/boas-praticas-farmaceuticas",
        "license": "Acesso público",
    },
    {
        "key": "anvisa-rdc-658-2022", "code": "ANVISA RDC 658/2022", "organization": "ANVISA",
        "edition": "RDC nº 658 · 2022", "status": "Vigente",
        "scope": "Diretrizes gerais de Boas Práticas de Fabricação de medicamentos.",
        "application": "Avaliação de sistemas, instalações e ambientes de fabricação farmacêutica.",
        "tests": "Sistema da qualidade; instalações; equipamentos; documentação; produção; controle e validação.",
        "url": "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2022/revisaco-entenda-como-ficaram-as-normas-da-area-de-fiscalizacao",
        "license": "Acesso público",
    },
    {
        "key": "anvisa-in-138-2022", "code": "ANVISA IN 138/2022", "organization": "ANVISA",
        "edition": "IN nº 138 · 2022", "status": "Vigente",
        "scope": "Diretrizes complementares sobre qualificação e validação na fabricação de medicamentos.",
        "application": "Planos, protocolos, execução e documentação de qualificação e validação.",
        "tests": "URS; qualificação de projeto, instalação, operação e desempenho; validação e controle de mudanças.",
        "url": "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2022/revisaco-entenda-como-ficaram-as-normas-da-area-de-fiscalizacao",
        "license": "Acesso público",
    },
    {
        "key": "iso-21501-4-2018-amd1-2023", "code": "ISO 21501-4:2018 + Amd 1:2023",
        "organization": "ISO", "edition": "2ª edição · 2018 + Emenda 1 · 2023",
        "status": "Publicada — revisão em desenvolvimento",
        "scope": "Calibração e verificação de contadores ópticos de partículas em suspensão no ar para espaços limpos.",
        "application": "Controle dos contadores usados na classificação e no monitoramento de partículas.",
        "tests": "Eficiência de detecção; resolução; falso contagem; vazão; resposta; calibração e verificação do LSAPC.",
        "url": "https://www.iso.org/standard/58073.html", "license": "Comercial/licenciada",
    },
    {
        "key": "iest-rp-cc006-4", "code": "IEST-RP-CC006.4", "organization": "IEST",
        "edition": "Revisão .4", "status": "Publicada",
        "scope": "Métodos para caracterização do desempenho de salas e zonas limpas em diferentes fases operacionais.",
        "application": "Especificação e ensaios complementares de conformidade operacional de áreas limpas.",
        "tests": "Desempenho de salas limpas; fases de ocupação; critérios e documentação de ensaios.",
        "url": "https://www.iest.org/Standards-RPs/Recommended-Practices/IEST-RP-CC006",
        "license": "Comercial/licenciada",
    },
    {
        "key": "iest-rp-cc019-1", "code": "IEST-RP-CC019.1", "organization": "IEST",
        "edition": "Revisão .1 · 2006", "status": "Publicada",
        "scope": "Qualificações recomendadas para organizações e profissionais que testam e certificam salas limpas e dispositivos de ar limpo.",
        "application": "Matriz de competência, escolaridade, treinamento e experiência da equipe de certificação.",
        "tests": "Categorias profissionais; requisitos de competência; treinamento; experiência e evidência de qualificação.",
        "url": "https://www.iest.org/Standards-RPs/Recommended-Practices/IEST-RP-CC019",
        "license": "Comercial/licenciada",
    },
    {
        "key": "iest-rp-cc034-5", "code": "IEST-RP-CC034.5", "organization": "IEST",
        "edition": "Revisão .5", "status": "Publicada",
        "scope": "Definições, equipamentos e procedimentos para ensaios de vazamento em filtros HEPA e ULPA.",
        "application": "Integridade de filtros na fábrica, antes da instalação e instalados em áreas/equipamentos.",
        "tests": "Geração e medição de aerossol; varredura; vazamento local; aceitação e registro de filtros HEPA/ULPA.",
        "url": "https://www.iest.org/Standards-RPs/Recommended-Practices/IEST-RP-CC034",
        "license": "Comercial/licenciada",
    },
    {
        "key": "ashrae-110-2016-ra2025", "code": "ANSI/ASHRAE 110-2016 (RA 2025)",
        "organization": "ASHRAE", "edition": "Edição 2016 · reafirmada em 2025", "status": "Publicada",
        "scope": "Métodos quantitativos e qualitativos para avaliar a contenção de capelas laboratoriais.",
        "application": "Ensaios de capelas de exaustão convencionais, bypass, ar auxiliar e VAV.",
        "tests": "Velocidade de face; visualização; contenção com gás traçador; condição como fabricada, instalada ou usada.",
        "url": "https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes",
        "license": "Comercial/licenciada",
    },
    {
        "key": "ashrae-111-2024", "code": "ANSI/ASHRAE 111-2024", "organization": "ASHRAE",
        "edition": "Edição 2024 · errata de 05/09/2025", "status": "Publicada",
        "scope": "Medição, ensaio, ajuste, balanceamento, avaliação e relato de desempenho de sistemas HVAC prediais.",
        "application": "Balanceamento, vazões, trocas de ar, pressurização e avaliação de contaminação cruzada.",
        "tests": "Vazão; balanceamento; taxa de renovação; pressão; ventilação externa; validação e relatório dos dados.",
        "url": "https://www.ashrae.org/technical-resources/standards-and-guidelines/titles-purposes-and-scopes",
        "license": "Comercial/licenciada",
    },
]

# Portfólio operacional confirmado pela direção em 15/08/2026: tudo o que é
# apresentado no site oficial integra a produção/fornecimento da SECCOL ou o
# seu patrimônio técnico. Os grupos abaixo mantêm essas naturezas separadas.
SECCOL_PRODUCT_CATALOG = [
    {
        "key": "produto-area-limpa", "code": "SEC-PRO-001", "title": "Área Limpa / Sala Limpa",
        "family": "Ambientes controlados", "kind": "Produção, projeto e fornecimento SECCOL",
        "description": "Solução de ambiente controlado para reduzir introdução, geração e retenção de contaminantes.",
        "source": "https://www.seccol.com.br/area-limpa.html",
        "norms": ["iso-14644-1-2015", "iso-14644-2-2015", "iso-14644-3-2019",
                  "iso-14644-4-2022", "iso-14644-5-2025", "ashrae-111-2024",
                  "anvisa-rdc-50-2002"],
    },
    {
        "key": "produto-cabine-seguranca-biologica", "code": "SEC-PRO-002",
        "title": "Cabine de Segurança Biológica", "family": "Contenção biológica",
        "kind": "Produção e fornecimento SECCOL",
        "description": "Equipamento de contenção primária para proteção do operador, produto e ambiente.",
        "source": "https://www.seccol.com.br/quem.html",
        "norms": ["nsf-ansi-49-2022", "iso-14644-3-2019", "iso-14644-7-2004",
                  "iest-rp-cc034-5"],
    },
    {
        "key": "produto-capela-exaustao", "code": "SEC-PRO-003", "title": "Capela de Exaustão",
        "family": "Proteção laboratorial", "kind": "Produção e fornecimento SECCOL",
        "description": "Barreira de proteção laboratorial com exaustão para contenção de emissões do processo.",
        "source": "https://www.seccol.com.br/quem.html",
        "norms": ["ashrae-110-2016-ra2025", "ashrae-111-2024", "iso-iec-17025-2017"],
    },
    {
        "key": "produto-fluxo-unidirecional", "code": "SEC-PRO-004",
        "title": "Equipamento de Fluxo Unidirecional (Laminar)", "family": "Ar limpo localizado",
        "kind": "Produção e fornecimento SECCOL",
        "description": "Equipamento para manipulação protegida de materiais biológicos ou estéreis.",
        "source": "https://www.seccol.com.br/quem.html",
        "norms": ["iso-14644-1-2015", "iso-14644-3-2019", "iso-14644-7-2004",
                  "iest-rp-cc034-5"],
    },
    {
        "key": "produto-unidade-descontaminacao", "code": "SEC-PRO-005",
        "title": "Unidade de Descontaminação / Ventilação", "family": "Tratamento de ar",
        "kind": "Produção e fornecimento SECCOL",
        "description": "Unidade para ventilação controlada e suporte a processos de descontaminação.",
        "source": "https://www.seccol.com.br/quem.html",
        "norms": ["iso-14644-3-2019", "iso-14644-5-2025", "ashrae-111-2024"],
    },
    {
        "key": "produto-filtro-hepa-ulpa", "code": "SEC-PRO-006", "title": "Filtro Absoluto HEPA / ULPA",
        "family": "Filtração absoluta", "kind": "Componente fornecido pela SECCOL",
        "description": "Elemento filtrante de reposição para sistemas e equipamentos de ar limpo.",
        "source": "https://www.seccol.com.br/teste-equipamento.html",
        "norms": ["iso-14644-3-2019", "iest-rp-cc034-5"],
    },
    {
        "key": "produto-motor-eletrico", "code": "SEC-PRO-007", "title": "Motor Elétrico de Reposição",
        "family": "Componentes eletromecânicos", "kind": "Componente fornecido pela SECCOL",
        "description": "Motor de reposição para manutenção e recuperação de equipamentos atendidos.",
        "source": "https://www.seccol.com.br/teste-equipamento.html", "norms": [],
    },
]

SECCOL_INSTRUMENT_CATALOG = [
    ("instrumento-contador-particulas", "SEC-INS-001", "Contador de Partículas", "Contagem e classificação de partículas no ar", ["iso-21501-4-2018-amd1-2023", "iso-14644-1-2015", "iso-14644-3-2019"]),
    ("instrumento-fotometro-pao", "SEC-INS-002", "Fotômetro e Gerador de Aerossol (PAO)", "Integridade de sistemas de filtragem HEPA/ULPA", ["iso-14644-3-2019", "iest-rp-cc034-5"]),
    ("instrumento-balometer", "SEC-INS-003", "Balometer", "Vazão, pressão, temperatura, umidade e velocidade do ar", ["iso-14644-3-2019", "ashrae-111-2024"]),
    ("instrumento-luximetro", "SEC-INS-004", "Luxímetro", "Medição de iluminância", ["iso-14644-3-2019", "iso-iec-17025-2017"]),
    ("instrumento-decibelimetro", "SEC-INS-005", "Decibelímetro", "Medição de nível de pressão sonora", ["iso-14644-3-2019", "iso-iec-17025-2017"]),
    ("instrumento-termoanemometro", "SEC-INS-006", "Termoanemômetro de Fio Quente", "Medição de velocidade em baixos fluxos de ar", ["iso-14644-3-2019", "ashrae-111-2024"]),
    ("instrumento-manometro", "SEC-INS-007", "Manômetro Digital", "Pressão diferencial de ambientes e saturação de filtros", ["iso-14644-3-2019", "ashrae-111-2024"]),
    ("instrumento-alicate-amperimetro", "SEC-INS-008", "Alicate Amperímetro", "Medição elétrica sem interrupção do circuito", ["iso-iec-17025-2017"]),
    ("instrumento-ampola-fumaca", "SEC-INS-009", "Ampola de Fumaça", "Visualização de movimentação e sentido do fluxo de ar", ["iso-14644-3-2019"]),
    ("instrumento-termohigrometro", "SEC-INS-010", "Termohigrômetro", "Medição de temperatura e umidade relativa", ["iso-14644-3-2019", "iso-iec-17025-2017"]),
    ("instrumento-radiometro-uvc", "SEC-INS-011", "Radiômetro UVC", "Medição da emissão de fontes ultravioleta germicidas", ["iso-iec-17025-2017"]),
    ("instrumento-vhp", "SEC-INS-012", "VHP — Vapor de Peróxido de Hidrogênio", "Biodescontaminação de ambientes, superfícies e equipamentos", ["iso-14644-5-2025"]),
]

SECCOL_SERVICE_CATALOG = [
    ("servico-manutencao-equipamento", "SEC-SRV-001", "Manutenção de Equipamentos", "Manutenção", "Prevenção e correção para reduzir paradas operacionais", ["iso-14644-5-2025"]),
    ("servico-reforma-equipamento", "SEC-SRV-002", "Reforma de Equipamentos", "Reforma", "Recuperação funcional, estrutural e eletromecânica", ["iso-14644-5-2025"]),
    ("servico-certificacao-equipamento", "SEC-SRV-003", "Certificação de Equipamentos", "Certificação", "Ensaios, avaliação e emissão de certificado técnico", ["iso-14644-3-2019", "iso-iec-17025-2017"]),
    ("servico-certificacao-area-limpa", "SEC-SRV-004", "Certificação de Área Limpa", "Certificação", "Classificação, qualificação e relatório técnico do ambiente", ["iso-14644-1-2015", "iso-14644-2-2015", "iso-14644-3-2019"]),
    ("servico-projeto-area-limpa", "SEC-SRV-005", "Projeto e Execução de Área Limpa", "Engenharia", "Levantamento, fluxos, projeto, execução e entrega controlada", ["iso-14644-4-2022", "anvisa-rdc-50-2002"]),
    ("servico-projeto-centro-cirurgico", "SEC-SRV-006", "Projeto e Execução de Centro Cirúrgico", "Engenharia", "Projeto técnico e execução de ambiente cirúrgico", ["anvisa-rdc-50-2002", "ashrae-111-2024"]),
    ("servico-monitoramento-descontaminacao", "SEC-SRV-007", "Monitoramento de Unidade de Descontaminação / Ventilação", "Monitoramento", "Acompanhamento de desempenho segundo normas aplicáveis", ["iso-14644-2-2015", "iso-14644-5-2025", "ashrae-111-2024"]),
    ("ensaio-velocidade-uniformidade", "SEC-SRV-008", "Velocidade e Uniformidade do Fluxo de Ar", "Ensaio de ar", "Medição e avaliação da uniformidade do fluxo", ["iso-14644-3-2019", "ashrae-111-2024"]),
    ("ensaio-inflow", "SEC-SRV-009", "Velocidade do Fluxo de Ar de Face (Inflow)", "Ensaio de contenção", "Medição da velocidade de entrada em cabine", ["nsf-ansi-49-2022"]),
    ("ensaio-perda-carga-filtro", "SEC-SRV-010", "Perda de Carga do Sistema HEPA / ULPA", "Ensaio de filtragem", "Diferença de pressão do sistema de filtragem", ["iso-14644-3-2019", "iest-rp-cc034-5"]),
    ("ensaio-integridade-hepa-pao", "SEC-SRV-011", "Integridade e Estanqueidade HEPA / ULPA (PAO)", "Ensaio de filtragem", "Detecção e localização de vazamentos no sistema instalado", ["iso-14644-3-2019", "iest-rp-cc034-5"]),
    ("ensaio-visualizacao-fumaca", "SEC-SRV-012", "Visualização do Fluxo de Ar (Fumaça)", "Ensaio de ar", "Avaliação visual do sentido e do padrão de fluxo", ["iso-14644-3-2019", "nsf-ansi-49-2022"]),
    ("ensaio-contagem-particulas", "SEC-SRV-013", "Contagem de Partículas em Suspensão", "Ensaio de partículas", "Contagem eletrônica e classificação de limpeza", ["iso-14644-1-2015", "iso-21501-4-2018-amd1-2023"]),
    ("ensaio-alarmes-csb", "SEC-SRV-014", "Avaliação dos Alarmes da CSB", "Ensaio de segurança", "Verificação funcional dos alarmes da cabine", ["nsf-ansi-49-2022"]),
    ("ensaio-iluminacao", "SEC-SRV-015", "Intensidade de Iluminação", "Ensaio ambiental", "Medição de iluminância em equipamento ou ambiente", ["iso-14644-3-2019", "iso-iec-17025-2017"]),
    ("ensaio-vibracao", "SEC-SRV-016", "Ensaio de Vibração", "Ensaio ambiental", "Medição e avaliação de vibração do equipamento", ["nsf-ansi-49-2022", "iso-iec-17025-2017"]),
    ("ensaio-ruido", "SEC-SRV-017", "Ensaio de Ruído", "Ensaio ambiental", "Medição de nível de pressão sonora", ["nsf-ansi-49-2022", "iso-iec-17025-2017"]),
    ("servico-filtros-inspecao-substituicao", "SEC-SRV-018", "Inspeção e Substituição de Filtros", "Manutenção", "Inspeção ou troca de filtros grossos e absolutos", ["iso-14644-5-2025", "iest-rp-cc034-5"]),
    ("servico-balanceamento", "SEC-SRV-019", "Balanceamento de Insuflamento, Exaustão e Retorno", "TAB/HVAC", "Ajuste e balanceamento dos sistemas de ar", ["ashrae-111-2024", "iso-14644-3-2019"]),
    ("servico-limpeza-interna", "SEC-SRV-020", "Limpeza Interna de Equipamento", "Manutenção", "Limpeza técnica da parte interna do equipamento", ["iso-14644-5-2025"]),
    ("ensaio-radiacao-uvc", "SEC-SRV-021", "Eficiência de Radiação UVC", "Ensaio de radiação", "Medição da eficiência de lâmpadas germicidas", ["iso-iec-17025-2017"]),
    ("ensaio-saturacao-filtro", "SEC-SRV-022", "Saturação de Filtros por Pressão Diferencial", "Ensaio de filtragem", "Medição da pressão diferencial para avaliar saturação", ["iso-14644-3-2019"]),
    ("ensaio-eletrico-motor", "SEC-SRV-023", "Tensão e Corrente Elétrica do Motor", "Ensaio elétrico", "Medição elétrica do conjunto motriz", ["iso-iec-17025-2017"]),
    ("servico-reparo-filtro", "SEC-SRV-024", "Reparo de Filtro HEPA", "Manutenção", "Reparo do meio filtrante ou da estrutura, quando tecnicamente admissível", ["iest-rp-cc034-5"]),
    ("servico-manometro-vedacao", "SEC-SRV-025", "Revisão de Manômetro e Selos de Vedação", "Manutenção", "Revisão do indicador de pressão e das vedações", ["iso-14644-5-2025"]),
    ("servico-componentes-eletromecanicos", "SEC-SRV-026", "Verificação de Componentes Eletromecânicos", "Manutenção", "Inspeção funcional dos componentes do equipamento", ["iso-14644-5-2025"]),
    ("ensaio-vazao-trocas-ar", "SEC-SRV-027", "Vazão e Número de Trocas de Ar", "Ensaio de área limpa", "Cálculo de vazão insuflada e renovações por hora", ["iso-14644-3-2019", "ashrae-111-2024"]),
    ("ensaio-recuperacao", "SEC-SRV-028", "Teste de Recuperação", "Ensaio de área limpa", "Determinação da capacidade de recuperação da limpeza do ambiente", ["iso-14644-3-2019"]),
    ("ensaio-pressao-entre-salas", "SEC-SRV-029", "Pressão Diferencial entre Salas", "Ensaio de área limpa", "Medição do diferencial e verificação da cascata de pressão", ["iso-14644-3-2019", "ashrae-111-2024"]),
]

NORMATIVE_REQUIRED_MODULES = {"certificados", "laudos_tecnicos", "estudos_tecnicos"}

MODULES = {
    # Administrativo
    "arquivos": "Arquivos administrativos",
    "clientes": "Clientes",
    "fornecedores": "Fornecedores",
    "contatos": "Contatos",
    "importacoes_xml": "Importação XML NF-e",
    "solicitacoes_compra": "Solicitações de compra",
    "pedidos_compra": "Pedidos de compra",
    "ramais": "Ramais",
    # Comercial e inteligência
    "crm": "CRM",
    "propostas": "Propostas",
    "contratos": "Contratos",
    "licitacoes": "Licitações",
    "editais": "Busca de editais",
    "fontes": "Fontes de busca",
    "concorrentes": "Concorrentes",
    # Operação técnica
    "equipamentos": "Equipamentos",
    "chamados": "Chamados",
    "agendamentos": "Agendamentos",
    "ordens_servico": "Ordens de Serviço",
    "servicos": "Serviços técnicos",
    "calibracoes": "Calibrações",
    "certificados": "Certificados",
    "padroes": "Padrões metrológicos",
    "planilhas_calibracao": "Planilhas de calibração",
    "laudos_tecnicos": "Laudos técnicos",
    "estudos_tecnicos": "Estudos técnicos",
    # Qualidade e pessoas
    "qualidade": "Qualidade",
    "normas_tecnicas": "Normas técnicas",
    "documentos_qualidade": "Documentos controlados",
    "reclamacoes": "Reclamações",
    "nao_conformidades": "Trabalhos não conformes",
    "colaboradores": "Colaboradores",
    "treinamentos": "Treinamentos e competências",
    # Ativos e frota
    "frota": "Frota",
    "manutencao_frota": "Controle veicular",
    # Vendas, estoque, financeiro e fiscal
    "produtos": "Produtos",
    "catalogo_servicos": "Catálogo de serviços e ensaios",
    "instrumentos_seccol": "Instrumentos técnicos SECCOL",
    "estoque": "Estoque e lotes",
    "vendas": "Vendas",
    "fiscal": "Fiscal / Manager",
    "contas_pagar": "Contas a pagar",
    "contas_receber": "Contas a receber",
    "boletos": "Boletos e remessas",
    "financeiro": "Financeiro",
    "caixa": "Caixa",
    # Gestão
    "produtividade": "Produtividade",
    "metas": "Metas",
}

ROLE_MODULES = {
    "admin": set(MODULES),
    "manager": set(MODULES),
    "operator": set(MODULES) - {
        "documentos_qualidade", "fiscal", "normas_tecnicas",
        "certificados", "laudos_tecnicos", "estudos_tecnicos",
    },
    "viewer": set(),
    "technician": {"equipamentos", "chamados", "agendamentos", "ordens_servico", "servicos",
                   "calibracoes", "certificados", "padroes", "laudos_tecnicos", "estudos_tecnicos",
                   "catalogo_servicos", "instrumentos_seccol", "frota", "manutencao_frota"},
    "quality": {"arquivos", "equipamentos", "calibracoes", "certificados", "padroes",
                "planilhas_calibracao", "laudos_tecnicos", "estudos_tecnicos", "normas_tecnicas",
                "qualidade", "documentos_qualidade", "reclamacoes",
                "nao_conformidades", "colaboradores", "treinamentos", "catalogo_servicos",
                "instrumentos_seccol"},
    "fiscal": {"clientes", "fornecedores", "contatos", "importacoes_xml", "pedidos_compra",
               "produtos", "catalogo_servicos", "estoque", "vendas", "fiscal", "contas_pagar", "contas_receber",
               "boletos", "financeiro", "caixa"},
    "approver": {"solicitacoes_compra", "pedidos_compra", "propostas", "contratos", "financeiro"},
}

# Leitura e exportação são permissões independentes da escrita. A coluna
# company_memberships.permissions pode ampliar ou restringir estes conjuntos
# com as chaves read/write/export/deny_read/deny_write/deny_export.
ROLE_READ_MODULES = {
    "admin": set(MODULES),
    "manager": set(MODULES),
    "operator": set(ROLE_MODULES["operator"]),
    "viewer": set(MODULES),
    "technician": set(ROLE_MODULES["technician"]) | {
        "clientes", "contatos", "normas_tecnicas", "documentos_qualidade",
    },
    "quality": set(ROLE_MODULES["quality"]) | {
        "clientes", "fornecedores", "chamados", "agendamentos", "ordens_servico", "servicos",
    },
    "fiscal": set(ROLE_MODULES["fiscal"]) | {"contratos", "solicitacoes_compra"},
    "approver": set(ROLE_MODULES["approver"]) | {
        "clientes", "fornecedores", "licitacoes", "contas_pagar", "contas_receber", "vendas",
    },
}

ROLE_EXPORT_MODULES = {
    "admin": set(MODULES),
    "manager": set(MODULES),
    "operator": set(),
    "viewer": set(),
    "technician": set(),
    "quality": set(),
    "fiscal": set(),
    "approver": set(),
}

DEFAULT_STATUSES = {
    "Ativo", "Em andamento", "Pendente", "A revisar", "Aprovado", "Pago",
    "Concluído", "Cancelado",
}

MODULE_STATUSES = {
    "crm": {"Novo lead", "Contato realizado", "Qualificado", "Proposta", "Negociação", "Ganho", "Perdido"},
    "propostas": {"Rascunho", "Enviada", "Em negociação", "Aprovada", "Recusada"},
    "licitacoes": {"Captação", "Análise", "Documentação", "Proposta enviada", "Disputa", "Habilitação", "Homologada", "Perdida"},
    "chamados": {"Aberto", "Em atendimento", "Aguardando cliente", "Concluído", "Cancelado"},
    "ordens_servico": {"Aberta", "Agendada", "Em execução", "Pausada", "Aguardando aprovação", "Concluída", "Cancelada"},
    "solicitacoes_compra": {"Rascunho", "Pendente de aprovação", "Aprovada", "Rejeitada", "Convertida em pedido"},
    "pedidos_compra": {"Rascunho", "Emitido", "Aguardando fornecedor", "Recebido parcial", "Recebido", "Cancelado"},
    "contas_pagar": {"Em aberto", "Parcial", "Pago", "Vencido", "Cancelado"},
    "contas_receber": {"Em aberto", "Parcial", "Recebido", "Vencido", "Cancelado"},
    "certificados": {"Rascunho", "Em revisão", "Aguardando aprovação", "Aprovado", "Publicado", "Obsoleto"},
    "laudos_tecnicos": {"Rascunho", "Em revisão", "Aguardando aprovação", "Aprovado", "Emitido", "Obsoleto"},
    "estudos_tecnicos": {"Rascunho", "Em revisão", "Aguardando aprovação", "Aprovado", "Emitido", "Obsoleto"},
    "normas_tecnicas": {"Publicada", "Publicada — em revisão sistemática", "Publicada — revisão em desenvolvimento", "Vigente", "Obsoleta"},
    "documentos_qualidade": {"Rascunho", "Em revisão", "Aguardando aprovação", "Vigente", "Obsoleto"},
    "fiscal": {"Rascunho", "Registrado localmente", "Aguardando conector", "Autorizado", "Rejeitado", "Cancelado"},
    "importacoes_xml": {"Importada", "Validada", "Rejeitada"},
}

# Contrato de obrigatoriedade espelhado dos 46 formulários especializados.
REQUIRED_PAYLOAD_FIELDS = {
    "arquivos": ("identificador", "categoria"),
    "clientes": ("tipo_pessoa", "documento", "razao_social"),
    "fornecedores": ("tipo_pessoa", "documento", "razao_social", "avaliacao"),
    "contatos": ("cliente_fornecedor", "tipo_contato", "cargo"),
    "importacoes_xml": ("chave", "numero", "fornecedor", "data_emissao"),
    "solicitacoes_compra": ("numero", "solicitante", "prioridade", "justificativa"),
    "pedidos_compra": ("numero", "fornecedor", "condicao_pagamento", "centro_custo"),
    "ramais": ("nome_ramal", "ramal", "setor"),
    "crm": ("etapa", "origem", "proximo_passo", "probabilidade"),
    "propostas": ("numero", "cliente", "validade", "etapa", "local_execucao"),
    "contratos": ("numero", "cliente", "gestor", "inicio", "fim"),
    "licitacoes": ("orgao", "edital", "portal", "modalidade", "data_abertura", "etapa"),
    "concorrentes": ("cnpj", "especialidade", "regiao", "fonte"),
    "instrumentos_seccol": ("codigo", "tipo", "fabricante", "modelo", "numero_serie", "proxima_calibracao"),
    "equipamentos": ("cliente", "tipo", "fabricante", "modelo", "numero_serie", "localizacao"),
    "chamados": ("cliente", "solicitante", "tipo", "prioridade"),
    "agendamentos": ("cliente", "tecnico", "data", "hora", "local", "tipo_servico"),
    "ordens_servico": ("numero", "cliente", "tecnico", "tipo_os", "local_execucao"),
    "servicos": ("cliente", "equipamento", "tecnico", "tipo_servico"),
    "calibracoes": ("os", "equipamento", "tecnico", "data_calibracao", "regra_decisao"),
    "certificados": ("numero", "os", "equipamento", "data_emissao", "revisao", "aprovador"),
    "laudos_tecnicos": ("numero", "os", "cliente", "local_avaliado", "responsavel_tecnico", "data_emissao", "metodo", "regra_decisao", "conclusao"),
    "estudos_tecnicos": ("numero", "cliente", "objeto", "responsavel_tecnico", "data_emissao", "premissas", "metodologia", "recomendacoes"),
    "padroes": ("codigo", "tipo", "fabricante", "numero_serie", "faixa_medicao", "proxima_calibracao", "rastreabilidade"),
    "planilhas_calibracao": ("codigo", "grandeza", "versao", "criterio_aceitacao"),
    "normas_tecnicas": ("codigo", "organismo", "edicao", "escopo_resumido", "aplicabilidade_seccol", "referencia_oficial", "licenciamento", "verificado_em"),
    "qualidade": ("tipo", "norma", "responsavel_qualidade", "acao_corretiva"),
    "documentos_qualidade": ("codigo", "tipo", "revisao", "elaborador", "aprovador", "data_vigencia"),
    "reclamacoes": ("cliente", "canal", "procedente", "causa", "tratativa"),
    "nao_conformidades": ("origem", "requisito", "causa_raiz", "correcao", "acao_corretiva"),
    "colaboradores": ("cpf", "cargo", "setor", "email"),
    "treinamentos": ("colaborador", "competencia", "data", "validade", "resultado"),
    "frota": ("placa", "veiculo", "renavam", "chassi", "responsavel_veiculo"),
    "manutencao_frota": ("placa", "tipo", "quilometragem", "oficina", "data_servico"),
    "produtos": ("codigo", "familia", "tipo_item", "descricao", "ncm", "unidade", "preco_venda"),
    "catalogo_servicos": ("codigo", "categoria", "tipo_servico", "descricao", "fonte_oficial", "verificado_em"),
    "estoque": ("produto", "lote", "quantidade", "localizacao", "movimento"),
    "vendas": ("cliente", "documento", "vendedor", "forma_pagamento", "condicao_pagamento"),
    "fiscal": ("tipo_nota", "numero", "serie", "chave", "destinatario", "cfop", "finalidade"),
    "contas_pagar": ("fornecedor", "documento", "parcela", "categoria", "centro_custo"),
    "contas_receber": ("cliente", "documento", "parcela", "categoria", "centro_custo"),
    "boletos": ("cliente", "nosso_numero", "banco", "conta", "vencimento_original"),
    "financeiro": ("tipo_lancamento", "categoria", "documento", "conta", "centro_custo"),
    "caixa": ("tipo_movimento", "categoria", "conta", "operador", "forma_pagamento"),
    "produtividade": ("colaborador", "periodo", "indicador", "resultado"),
    "metas": ("responsavel_meta", "indicador", "periodo", "meta"),
}

DATE_FIELDS = {
    "importacoes_xml": {"data_emissao"}, "propostas": {"validade"},
    "contratos": {"inicio", "fim"}, "licitacoes": {"data_abertura"},
    "instrumentos_seccol": {"proxima_calibracao"}, "equipamentos": {"proxima_calibracao"},
    "agendamentos": {"data"}, "calibracoes": {"data_calibracao", "proxima_calibracao"},
    "certificados": {"data_emissao"}, "laudos_tecnicos": {"data_emissao"},
    "estudos_tecnicos": {"data_emissao"}, "padroes": {"proxima_calibracao"},
    "normas_tecnicas": {"verificado_em"}, "documentos_qualidade": {"data_vigencia"},
    "treinamentos": {"data", "validade"}, "frota": {"seguro_vencimento"},
    "manutencao_frota": {"data_servico"}, "catalogo_servicos": {"verificado_em"},
    "estoque": {"validade"}, "boletos": {"vencimento_original"},
}

DATETIME_FIELDS = {"ordens_servico": {"inicio", "fim"}}
TIME_FIELDS = {"agendamentos": {"hora"}}
NUMBER_FIELDS = {
    "crm": {"probabilidade"}, "ordens_servico": {"tempo_minutos"},
    "frota": {"quilometragem"}, "manutencao_frota": {"quilometragem", "proxima_km"},
    "produtos": {"preco_venda"}, "estoque": {"quantidade"},
    "produtividade": {"resultado", "horas"}, "metas": {"meta", "realizado"},
}

EMAIL_FIELDS = {"clientes": {"email"}, "fornecedores": {"email"}, "contatos": {"email"}, "colaboradores": {"email"}}
URL_FIELDS = {
    "licitacoes": {"portal"}, "concorrentes": {"fonte"},
    "instrumentos_seccol": {"fonte_oficial"}, "produtos": {"fonte_oficial"},
    "catalogo_servicos": {"fonte_oficial"}, "normas_tecnicas": {"referencia_oficial"},
}


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _valid_cpf(value: str) -> bool:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        total = sum(int(digits[index]) * (size + 1 - index) for index in range(size))
        check = (total * 10 % 11) % 10
        if check != int(digits[size]):
            return False
    return True


def _valid_cnpj(value: str) -> bool:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    for weights, position in (((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), 12),
                              ((6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), 13)):
        remainder = sum(int(digits[index]) * weight for index, weight in enumerate(weights)) % 11
        check = 0 if remainder < 2 else 11 - remainder
        if check != int(digits[position]):
            return False
    return True


def _validate_document(value: str, label="CPF/CNPJ") -> None:
    digits = re.sub(r"\D", "", str(value or ""))
    valid = _valid_cpf(digits) if len(digits) == 11 else _valid_cnpj(digits) if len(digits) == 14 else False
    if not valid:
        raise ValueError(f"{label} inválido")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _reject_json_constant(value):
    raise ValueError(f"Constante numérica JSON inválida: {value}")


def json_loads_strict(value):
    return json.loads(value, parse_constant=_reject_json_constant)


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.local = threading.local()
        self.initialize()
        self.secure_files()

    def secure_files(self) -> None:
        """Aplica menor privilégio aos arquivos SQLite em plataformas POSIX."""
        for candidate in (self.path, Path(str(self.path) + "-wal"), Path(str(self.path) + "-shm")):
            if candidate.exists():
                try:
                    os.chmod(candidate, 0o600)
                except OSError:
                    pass

    def connection(self) -> sqlite3.Connection:
        connection = getattr(self.local, "connection", None)
        if connection is None:
            connection = sqlite3.connect(self.path, timeout=20)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 20000")
            connection.execute("PRAGMA synchronous = NORMAL")
            self.local.connection = connection
            self.secure_files()
        return connection

    def close_thread_connection(self) -> None:
        """Fecha a conexao pertencente a thread atual."""
        connection = getattr(self.local, "connection", None)
        if connection is None:
            return
        try:
            if connection.in_transaction:
                connection.rollback()
            connection.close()
        finally:
            del self.local.connection

    @contextlib.contextmanager
    def transaction(self, immediate=False):
        """Unidade de trabalho com suporte seguro a chamadas aninhadas."""
        db = self.connection()
        depth = int(getattr(self.local, "transaction_depth", 0))
        savepoint = f"sivs_sp_{depth}"
        if depth == 0:
            if db.in_transaction:
                db.commit()
            db.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        else:
            db.execute(f"SAVEPOINT {savepoint}")
        self.local.transaction_depth = depth + 1
        try:
            yield db
            self.local.transaction_depth = depth
            if depth == 0:
                db.commit()
            else:
                db.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            self.local.transaction_depth = depth
            if depth == 0:
                db.rollback()
            else:
                db.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                db.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise

    def commit_if_outer(self) -> None:
        if (int(getattr(self.local, "transaction_depth", 0)) == 0 and
                not bool(getattr(self.local, "manual_transaction", False))):
            self.connection().commit()

    def begin_manual_transaction(self, immediate=True) -> None:
        """Inicia unidade longa usada por importadores sem permitir commits intermediários."""
        if int(getattr(self.local, "transaction_depth", 0)) or getattr(
                self.local, "manual_transaction", False):
            raise RuntimeError("Já existe uma transação ativa")
        db = self.connection()
        if db.in_transaction:
            db.commit()
        db.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        self.local.manual_transaction = True

    def finish_manual_transaction(self, commit=True) -> None:
        if not getattr(self.local, "manual_transaction", False):
            return
        db = self.connection()
        try:
            db.commit() if commit else db.rollback()
        finally:
            self.local.manual_transaction = False

    def abort_manual_transaction(self) -> None:
        self.finish_manual_transaction(commit=False)

    def initialize(self) -> None:
        db = self.connection()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf_token TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Ativo',
                amount REAL,
                due_date TEXT,
                payload TEXT NOT NULL DEFAULT '{}',
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_records_module ON records(module);
            CREATE INDEX IF NOT EXISTS idx_records_status ON records(status);
            CREATE INDEX IF NOT EXISTS idx_records_due_date ON records(due_date);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                detail TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS record_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                snapshot TEXT NOT NULL,
                changed_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_record_versions_record ON record_versions(record_id);
            CREATE TABLE IF NOT EXISTS tender_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keywords TEXT NOT NULL,
                uf TEXT,
                days INTEGER NOT NULL,
                sources_searched TEXT NOT NULL,
                found_count INTEGER NOT NULL DEFAULT 0,
                new_count INTEGER NOT NULL DEFAULT 0,
                error_detail TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tender_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT NOT NULL,
                object_text TEXT NOT NULL,
                agency TEXT,
                uf TEXT,
                municipality TEXT,
                modality TEXT,
                estimated_value REAL,
                published_at TEXT,
                deadline TEXT,
                source_url TEXT,
                matched_terms TEXT NOT NULL DEFAULT '[]',
                relevance_score INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Novo',
                raw_json TEXT NOT NULL DEFAULT '{}',
                converted_record_id INTEGER REFERENCES records(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_key, external_id)
            );
            CREATE INDEX IF NOT EXISTS idx_tender_results_status ON tender_results(status);
            CREATE INDEX IF NOT EXISTS idx_tender_results_deadline ON tender_results(deadline);
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'Ativo',
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS record_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                to_record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                relationship_type TEXT NOT NULL,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                CHECK(from_record_id != to_record_id),
                UNIQUE(from_record_id,to_record_id,relationship_type)
            );
            CREATE INDEX IF NOT EXISTS idx_relationships_from ON record_relationships(from_record_id);
            CREATE INDEX IF NOT EXISTS idx_relationships_to ON record_relationships(to_record_id);
            """
        )
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cnpj TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS company_memberships (
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role TEXT NOT NULL DEFAULT 'operator',
                permissions TEXT NOT NULL DEFAULT '{}',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(company_id,user_id)
            );
            CREATE TABLE IF NOT EXISTS company_settings (
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(company_id,key)
            );
            CREATE TABLE IF NOT EXISTS record_subjects (
                record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                relationship_type TEXT NOT NULL DEFAULT 'Relacionado a',
                is_primary INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                PRIMARY KEY(record_id,subject_id,relationship_type)
            );
            CREATE INDEX IF NOT EXISTS idx_record_subjects_subject ON record_subjects(subject_id);
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                record_id INTEGER REFERENCES records(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                content BLOB NOT NULL,
                size INTEGER NOT NULL,
                category TEXT,
                version TEXT,
                uploaded_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_attachments_record ON attachments(record_id);
            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                approval_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendente',
                requested_to INTEGER REFERENCES users(id),
                decided_by INTEGER REFERENCES users(id),
                comment TEXT,
                requested_at TEXT NOT NULL,
                decided_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_approvals_record ON approvals(record_id);
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                message TEXT,
                record_id INTEGER REFERENCES records(id) ON DELETE CASCADE,
                level TEXT NOT NULL DEFAULT 'info',
                read_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(company_id,user_id,read_at);
            CREATE TABLE IF NOT EXISTS fiscal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                protocol TEXT,
                response_detail TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_fiscal_events_record ON fiscal_events(record_id);
            CREATE TABLE IF NOT EXISTS search_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                keywords TEXT NOT NULL,
                uf TEXT,
                days INTEGER NOT NULL DEFAULT 7,
                frequency TEXT NOT NULL DEFAULT 'manual',
                active INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT,
                next_run_at TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tender_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                schedule_id INTEGER REFERENCES search_schedules(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                request_json TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                stage TEXT NOT NULL DEFAULT 'Pesquisa enfileirada',
                result_json TEXT,
                error_detail TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TEXT NOT NULL,
                started_at TEXT,
                heartbeat_at TEXT,
                finished_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tender_jobs_company
              ON tender_jobs(company_id,created_at DESC);
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS setup_state (
                id INTEGER PRIMARY KEY CHECK(id=1),
                configured INTEGER NOT NULL DEFAULT 0,
                configured_at TEXT
            );
            """
        )

        def ensure_column(table, name, definition):
            columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
            if name not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

        ensure_column("records", "deleted_at", "TEXT")
        ensure_column("records", "subject_id", "INTEGER REFERENCES subjects(id)")
        ensure_column("records", "company_id", "INTEGER REFERENCES companies(id)")
        ensure_column("records", "revision", "INTEGER NOT NULL DEFAULT 1")
        ensure_column("subjects", "company_id", "INTEGER REFERENCES companies(id)")
        ensure_column("sessions", "company_id", "INTEGER REFERENCES companies(id)")
        ensure_column("audit_log", "company_id", "INTEGER REFERENCES companies(id)")
        ensure_column("tender_searches", "company_id", "INTEGER REFERENCES companies(id)")
        ensure_column("tender_results", "company_id", "INTEGER REFERENCES companies(id)")
        ensure_column("record_versions", "company_id", "INTEGER REFERENCES companies(id)")
        ensure_column("approvals", "requested_by", "INTEGER REFERENCES users(id)")
        ensure_column("approvals", "record_revision", "INTEGER NOT NULL DEFAULT 1")
        ensure_column("approvals", "request_comment", "TEXT")
        ensure_column("approvals", "decision_comment", "TEXT")
        ensure_column("attachments", "sha256", "TEXT")
        ensure_column("attachments", "license_confirmed", "INTEGER NOT NULL DEFAULT 0")

        now = utc_now()
        default_company = db.execute("SELECT id FROM companies ORDER BY id LIMIT 1").fetchone()
        if not default_company:
            legacy = db.execute("SELECT value FROM settings WHERE key='company'").fetchone()
            legacy_company = json.loads(legacy["value"] or "{}") if legacy else {}
            cursor = db.execute(
                "INSERT INTO companies(name,cnpj,phone,address,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (legacy_company.get("name") or "SECCOL", legacy_company.get("cnpj"),
                 legacy_company.get("phone"), legacy_company.get("address"), now, now),
            )
            default_company_id = cursor.lastrowid
        else:
            default_company_id = default_company["id"]

        for table in ("records", "subjects", "sessions", "audit_log", "tender_searches",
                      "tender_results", "record_versions"):
            db.execute(f"UPDATE {table} SET company_id=? WHERE company_id IS NULL", (default_company_id,))

        # A chave normalizada inclui a empresa para permitir assuntos iguais em empresas distintas.
        subject_rows = db.execute("SELECT id,company_id,normalized_name FROM subjects").fetchall()
        for subject in subject_rows:
            prefix = f'{subject["company_id"]}:'
            if not str(subject["normalized_name"] or "").startswith(prefix):
                db.execute("UPDATE subjects SET normalized_name=? WHERE id=?",
                           (prefix + str(subject["normalized_name"] or ""), subject["id"]))

        users = db.execute("SELECT id,role,created_at,updated_at FROM users").fetchall()
        for user in users:
            db.execute(
                """INSERT OR IGNORE INTO company_memberships
                   (company_id,user_id,role,permissions,active,created_at,updated_at)
                   VALUES(?,?,?,'{}',1,?,?)""",
                (default_company_id, user["id"], user["role"], user["created_at"], user["updated_at"]),
            )
        db.execute("CREATE INDEX IF NOT EXISTS idx_records_company_module ON records(company_id,module)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_subjects_company ON subjects(company_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_tender_results_company ON tender_results(company_id,status)")
        db.execute(
            """UPDATE approvals SET requested_by=COALESCE(requested_by,
                   (SELECT created_by FROM records WHERE records.id=approvals.record_id)),
                   request_comment=COALESCE(request_comment,comment),
                   record_revision=COALESCE(record_revision,1)"""
        )
        db.execute(
            """UPDATE approvals SET status='Cancelada por migração'
               WHERE status='Pendente' AND EXISTS (
                 SELECT 1 FROM approvals newer
                 WHERE newer.company_id=approvals.company_id
                   AND newer.record_id=approvals.record_id
                   AND newer.approval_type=approvals.approval_type
                   AND newer.status='Pendente' AND newer.id>approvals.id
               )"""
        )
        db.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_approvals_one_pending
               ON approvals(company_id,record_id,approval_type) WHERE status='Pendente'"""
        )
        db.execute(
            """UPDATE tender_jobs SET status='failed',finished_at=?,
               error_detail='Execução interrompida por reinicialização do servidor.'
               WHERE status IN ('queued','running')""",
            (utc_now(),),
        )
        db.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_tender_jobs_one_active
               ON tender_jobs(company_id) WHERE status IN ('queued','running')"""
        )
        db.execute("INSERT OR IGNORE INTO setup_state(id,configured) VALUES(1,0)")
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            db.execute(
                "UPDATE setup_state SET configured=1,configured_at=COALESCE(configured_at,?) WHERE id=1",
                (utc_now(),),
            )
        db.execute(
            """INSERT OR IGNORE INTO schema_migrations(version,name,applied_at)
               VALUES(220,'hardening-v2.2',?)""", (utc_now(),)
        )
        db.commit()
        self.seed_sources(default_company_id)
        self.seed_norms(default_company_id)
        self.seed_seccol_portfolio(default_company_id)
        self.migrate_subjects()
        missing_hashes = self.connection().execute(
            "SELECT id,content FROM attachments WHERE sha256 IS NULL OR sha256=''"
        ).fetchall()
        for attachment in missing_hashes:
            self.connection().execute(
                "UPDATE attachments SET sha256=? WHERE id=?",
                (hashlib.sha256(attachment["content"]).hexdigest(), attachment["id"]),
            )
        self.commit_if_outer()

    @staticmethod
    def normalize_subject(value):
        text = unicodedata.normalize("NFD", str(value or "").strip().lower())
        return "".join(char for char in text if unicodedata.category(char) != "Mn")

    def ensure_subject(self, name, user_id=None, company_id=None):
        name = str(name or "").strip()[:180]
        company_id = int(company_id or 1)
        normalized = self.normalize_subject(name)
        if not normalized:
            return None
        normalized_key = f"{company_id}:{normalized}"
        now = utc_now()
        self.connection().execute(
            """INSERT OR IGNORE INTO subjects
               (name,normalized_name,status,created_by,created_at,updated_at,company_id)
               VALUES(?,?,'Ativo',?,?,?,?)""",
            (name, normalized_key, user_id, now, now, company_id))
        row = self.connection().execute(
            "SELECT id FROM subjects WHERE company_id=? AND normalized_name=?",
            (company_id, normalized_key)).fetchone()
        return row["id"] if row else None

    def sync_relationships(self, record_id, payload, user_id=None, company_id=None):
        db = self.connection()
        record = db.execute("SELECT company_id FROM records WHERE id=?", (record_id,)).fetchone()
        company_id = int(company_id or (record["company_id"] if record else 1) or 1)
        subject_id = self.ensure_subject(payload.get("assunto"), user_id, company_id)
        db.execute("UPDATE records SET subject_id=? WHERE id=?", (subject_id, record_id))
        db.execute("DELETE FROM record_subjects WHERE record_id=?", (record_id,))
        if subject_id:
            db.execute(
                """INSERT OR IGNORE INTO record_subjects
                   (record_id,subject_id,relationship_type,is_primary,created_by,created_at)
                   VALUES(?,?,'Assunto principal',1,?,?)""",
                (record_id, subject_id, user_id, utc_now()))
        additional_subjects = payload.get("assuntos_adicionais") or []
        if isinstance(additional_subjects, str):
            additional_subjects = [item.strip() for item in additional_subjects.split(",") if item.strip()]
        if isinstance(additional_subjects, list):
            for additional_name in additional_subjects[:30]:
                additional_id = self.ensure_subject(additional_name, user_id, company_id)
                if additional_id and additional_id != subject_id:
                    db.execute(
                        """INSERT OR IGNORE INTO record_subjects
                           (record_id,subject_id,relationship_type,is_primary,created_by,created_at)
                           VALUES(?,?,'Relacionado a',0,?,?)""",
                        (record_id, additional_id, user_id, utc_now()))
        requested = []
        primary = str(payload.get("registro_relacionado") or "").strip()
        if primary:
            requested.append({"record": primary, "type": payload.get("tipo_relacao") or "Relacionado a"})
        if isinstance(payload.get("relacionamentos"), list):
            requested.extend(payload["relacionamentos"][:50])
        db.execute("DELETE FROM record_relationships WHERE from_record_id=?", (record_id,))
        for relation in requested:
            if not isinstance(relation, dict):
                continue
            reference = str(relation.get("record") or relation.get("registro") or "")
            match = re.fullmatch(r"([a-z_]+):(\d+)", reference)
            if not match or match.group(1) not in MODULES:
                raise ValueError("Referência de relacionamento inválida")
            target_module, target_id = match.group(1), int(match.group(2))
            if target_id == record_id:
                raise ValueError("Um registro não pode ser relacionado a ele próprio")
            exists = db.execute(
                """SELECT id FROM records
                   WHERE id=? AND module=? AND company_id=? AND deleted_at IS NULL""",
                (target_id, target_module, company_id)).fetchone()
            if not exists:
                raise ValueError(
                    "O registro relacionado não existe, pertence a outro módulo/empresa ou foi excluído"
                )
            relation_type = str(relation.get("type") or relation.get("tipo") or "Relacionado a").strip()[:80]
            db.execute(
                """INSERT OR IGNORE INTO record_relationships
                   (from_record_id,to_record_id,relationship_type,created_by,created_at) VALUES(?,?,?,?,?)""",
                (record_id, target_id, relation_type, user_id, utc_now()))
    def migrate_subjects(self):
        db = self.connection()
        rows = db.execute("SELECT id,payload,created_by,company_id FROM records WHERE subject_id IS NULL").fetchall()
        for row in rows:
            try:
                payload = json.loads(row["payload"] or "{}")
                if payload.get("assunto"):
                    self.sync_relationships(row["id"], payload, row["created_by"], row["company_id"])
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
        self.commit_if_outer()

    def seed_sources(self, company_id=None):
        db = self.connection()
        now = utc_now()
        company_ids = [company_id] if company_id else [row["id"] for row in db.execute(
            "SELECT id FROM companies WHERE active=1").fetchall()]
        for current_company_id in company_ids:
            for key, name, url, coverage, collection_mode, category in SOURCE_CATALOG:
                exists = db.execute(
                    """SELECT id,title,payload FROM records WHERE company_id=? AND module='fontes'
                       AND json_extract(payload,'$.source_key')=?""",
                    (current_company_id, key),
                ).fetchone()
                if exists:
                    try:
                        payload = json.loads(exists["payload"] or "{}")
                    except json.JSONDecodeError:
                        payload = {}
                    payload.update({
                        "source_key": key, "url": url, "abrangencia": coverage,
                        "modo_coleta": collection_mode, "categoria": category,
                        "verificado_em": "2026-08-15",
                        "assunto": f"Fonte de busca — {name}",
                    })
                    if not payload.get("palavra_chave"):
                        payload["palavra_chave"] = ", ".join(DEFAULT_TENDER_KEYWORDS)
                    encoded_payload = json_dumps(payload)
                    if exists["title"] != name or exists["payload"] != encoded_payload:
                        db.execute(
                            "UPDATE records SET title=?,payload=?,updated_at=? WHERE id=?",
                            (name, encoded_payload, now, exists["id"]),
                        )
                    self.sync_relationships(exists["id"], payload, None, current_company_id)
                    continue
                payload = {
                    "source_key": key, "url": url, "abrangencia": coverage,
                    "modo_coleta": collection_mode, "categoria": category,
                    "palavra_chave": ", ".join(DEFAULT_TENDER_KEYWORDS),
                    "verificado_em": "2026-08-15", "ativo": True,
                    "ultima_execucao": None, "ultimo_sucesso": None,
                    "assunto": f"Fonte de busca — {name}",
                }
                cursor = db.execute(
                    """INSERT INTO records
                       (module,title,status,payload,company_id,created_at,updated_at)
                       VALUES('fontes',?,'Ativo',?,?,?,?)""",
                    (name, json_dumps(payload), current_company_id, now, now),
                )
                self.sync_relationships(cursor.lastrowid, payload, None, current_company_id)
        self.commit_if_outer()

    def seed_norms(self, company_id=None):
        """Instala a base normativa sem redistribuir textos integrais protegidos."""
        db = self.connection()
        now = utc_now()
        company_ids = [company_id] if company_id else [row["id"] for row in db.execute(
            "SELECT id FROM companies WHERE active=1").fetchall()]
        for current_company_id in company_ids:
            for norm in NORM_CATALOG:
                row = db.execute(
                    """SELECT id FROM records WHERE company_id=? AND module='normas_tecnicas'
                       AND json_extract(payload,'$.norm_key')=? AND deleted_at IS NULL""",
                    (current_company_id, norm["key"]),
                ).fetchone()
                if row:
                    record_id = row["id"]
                else:
                    payload = {
                        "norm_key": norm["key"], "codigo": norm["code"],
                        "organismo": norm["organization"], "edicao": norm["edition"],
                        "escopo_resumido": norm["scope"],
                        "aplicabilidade_seccol": norm["application"],
                        "ensaios_base": norm["tests"], "referencia_oficial": norm["url"],
                        "licenciamento": norm["license"],
                        "documento_status": (
                            "Ficha de referência anexada; adicionar a cópia integral licenciada da SECCOL"
                            if norm["license"] == "Comercial/licenciada"
                            else "Ficha de referência anexada; texto oficial disponível no endereço público"
                        ),
                        "verificado_em": "2026-08-15",
                        "assunto": f'Base normativa — {norm["code"]}',
                        "notes": "Confirmar edição, emendas, escopo contratual e requisitos regulatórios antes da emissão.",
                    }
                    cursor = db.execute(
                        """INSERT INTO records
                           (module,title,status,payload,company_id,created_at,updated_at)
                           VALUES('normas_tecnicas',?,?,?,?,?,?)""",
                        (norm["code"], norm["status"], json_dumps(payload),
                         current_company_id, now, now),
                    )
                    record_id = cursor.lastrowid
                    self.sync_relationships(record_id, payload, None, current_company_id)
                attached = db.execute(
                    """SELECT id FROM attachments WHERE company_id=? AND record_id=?
                       AND category='Ficha de referência normativa' LIMIT 1""",
                    (current_company_id, record_id),
                ).fetchone()
                if attached:
                    continue
                warning = (
                    "Esta ficha NÃO substitui a norma integral. A cópia integral é comercial/licenciada "
                    "e deve ser anexada somente se a SECCOL possuir licença válida."
                    if norm["license"] == "Comercial/licenciada"
                    else "Esta ficha NÃO substitui a leitura do ato oficial e de suas alterações posteriores."
                )
                reference_sheet = (
                    f"FICHA DE REFERÊNCIA NORMATIVA — SIVS SECCOL 2.2\n\n"
                    f"Código: {norm['code']}\nOrganismo: {norm['organization']}\n"
                    f"Edição: {norm['edition']}\nSituação cadastrada: {norm['status']}\n"
                    f"Verificação do catálogo: 15/08/2026\n\nESCOPO RESUMIDO\n{norm['scope']}\n\n"
                    f"APLICABILIDADE SECCOL\n{norm['application']}\n\n"
                    f"ENSAIOS/CONTROLES RELACIONADOS\n{norm['tests']}\n\n"
                    f"REFERÊNCIA OFICIAL\n{norm['url']}\n\nCONTROLE DOCUMENTAL\n{warning}\n"
                    "Antes de assinar laudo, estudo ou certificado, o responsável técnico deve verificar "
                    "a edição vigente, emendas, erratas, requisitos do contrato, método aprovado, evidências, "
                    "incerteza quando aplicável e regra de decisão.\n"
                ).encode("utf-8")
                db.execute(
                    """INSERT INTO attachments
                       (company_id,record_id,filename,mime_type,content,size,category,version,
                        created_at,sha256,license_confirmed)
                       VALUES(?,?,?,?,?,?,?,?,?,?,0)""",
                    (current_company_id, record_id, f"ficha-{norm['key']}.txt", "text/plain; charset=utf-8",
                     reference_sheet, len(reference_sheet), "Ficha de referência normativa",
                     norm["edition"], now, hashlib.sha256(reference_sheet).hexdigest()),
                )
        self.commit_if_outer()

    def seed_seccol_portfolio(self, company_id=None):
        """Instala portfólio, instrumentos próprios e ensaios sem misturar execução operacional."""
        db = self.connection()
        now = utc_now()
        company_ids = [company_id] if company_id else [row["id"] for row in db.execute(
            "SELECT id FROM companies WHERE active=1").fetchall()]
        norm_codes = {item["key"]: item["code"] for item in NORM_CATALOG}

        for current_company_id in company_ids:
            norm_rows = db.execute(
                """SELECT id,json_extract(payload,'$.norm_key') norm_key FROM records
                   WHERE company_id=? AND module='normas_tecnicas' AND deleted_at IS NULL""",
                (current_company_id,),
            ).fetchall()
            norm_ids = {row["norm_key"]: row["id"] for row in norm_rows if row["norm_key"]}

            catalog_items = []
            for item in SECCOL_PRODUCT_CATALOG:
                catalog_items.append(("produtos", {
                    "catalog_key": item["key"], "codigo": item["code"], "title": item["title"],
                    "familia": item["family"], "tipo_item": item["kind"], "descricao": item["description"],
                    "unidade": "UN", "origem_operacional": "Produção/fornecimento SECCOL",
                    "fonte_oficial": item["source"], "norm_keys": item["norms"],
                }))
            for key, code, title, use, norms in SECCOL_INSTRUMENT_CATALOG:
                catalog_items.append(("instrumentos_seccol", {
                    "catalog_key": key, "codigo": code, "title": title,
                    "tipo": "Instrumento técnico próprio", "propriedade": "SECCOL",
                    "fabricante": "Conforme patrimônio e certificado", "uso_tecnico": use,
                    "controle_metrologico": "Controlar identificação, série, certificado e validade",
                    "fonte_oficial": "https://www.seccol.com.br/equipamentos.html", "norm_keys": norms,
                }))
            for key, code, title, category, description, norms in SECCOL_SERVICE_CATALOG:
                if key.startswith(("servico-projeto", "servico-monitoramento")):
                    source = "https://www.seccol.com.br/quem.html"
                elif key in {"servico-certificacao-area-limpa", "ensaio-vazao-trocas-ar",
                             "ensaio-recuperacao", "ensaio-pressao-entre-salas"}:
                    source = "https://www.seccol.com.br/area-limpa.html"
                else:
                    source = "https://www.seccol.com.br/teste-equipamento.html"
                catalog_items.append(("catalogo_servicos", {
                    "catalog_key": key, "codigo": code, "title": title, "categoria": category,
                    "tipo_servico": title, "descricao": description,
                    "origem_operacional": "Serviço/ensaio executado pela SECCOL",
                    "fonte_oficial": source, "norm_keys": norms,
                }))

            for module, item in catalog_items:
                row = db.execute(
                    """SELECT id,payload,deleted_at FROM records WHERE company_id=? AND module=?
                       AND json_extract(payload,'$.catalog_key')=? ORDER BY id LIMIT 1""",
                    (current_company_id, module, item["catalog_key"]),
                ).fetchone()
                if row and row["deleted_at"]:
                    continue
                norm_names = [norm_codes[key] for key in item["norm_keys"] if key in norm_codes]
                authoritative = {
                    key: value for key, value in item.items() if key not in {"title", "norm_keys"}
                }
                authoritative.update({
                    "catalogo_seccol": True,
                    "classificacao_catalogo": (
                        "Produto/solução" if module == "produtos"
                        else "Instrumento técnico próprio" if module == "instrumentos_seccol"
                        else "Serviço/ensaio"
                    ),
                    "normas_aplicaveis": norm_names,
                    "verificado_em": "2026-08-15",
                    "assunto": f'Portfólio SECCOL — {item["title"]}',
                    "notes": (
                        "Item confirmado pela direção como integrante da produção, fornecimento ou patrimônio "
                        "técnico da SECCOL. Confirmar configuração, modelo, série, escopo e normas aplicáveis "
                        "antes de proposta, fabricação, ensaio, laudo ou certificado."
                    ),
                })
                if row:
                    try:
                        payload = json.loads(row["payload"] or "{}")
                    except json.JSONDecodeError:
                        payload = {}
                    for key, value in authoritative.items():
                        if key in {"fonte_oficial", "verificado_em", "normas_aplicaveis",
                                   "catalogo_seccol", "classificacao_catalogo"} or not payload.get(key):
                            payload[key] = value
                    record_id = row["id"]
                    db.execute("UPDATE records SET payload=?,updated_at=? WHERE id=?",
                               (json_dumps(payload), now, record_id))
                else:
                    payload = authoritative
                    cursor = db.execute(
                        """INSERT INTO records
                           (module,title,status,payload,company_id,created_at,updated_at)
                           VALUES(?,?, 'Ativo',?,?,?,?)""",
                        (module, item["title"], json_dumps(payload), current_company_id, now, now),
                    )
                    record_id = cursor.lastrowid

                subject_id = self.ensure_subject(payload["assunto"], None, current_company_id)
                db.execute("UPDATE records SET subject_id=? WHERE id=?", (subject_id, record_id))
                if subject_id:
                    db.execute(
                        """INSERT OR IGNORE INTO record_subjects
                           (record_id,subject_id,relationship_type,is_primary,created_at)
                           VALUES(?,?,'Assunto principal',1,?)""",
                        (record_id, subject_id, now),
                    )
                for norm_key in item["norm_keys"]:
                    norm_id = norm_ids.get(norm_key)
                    if norm_id:
                        db.execute(
                            """INSERT OR IGNORE INTO record_relationships
                               (from_record_id,to_record_id,relationship_type,created_at)
                               VALUES(?,?,'Fundamentado em',?)""",
                            (record_id, norm_id, now),
                        )

                attached = db.execute(
                    """SELECT id FROM attachments WHERE company_id=? AND record_id=?
                       AND category='Ficha de portfólio SECCOL' LIMIT 1""",
                    (current_company_id, record_id),
                ).fetchone()
                if not attached:
                    reference_sheet = (
                        f"FICHA DE PORTFÓLIO SECCOL — SIVS 2.2\n\n"
                        f"Código: {item.get('codigo', '')}\nItem: {item['title']}\n"
                        f"Classificação: {authoritative['classificacao_catalogo']}\n"
                        f"Descrição/uso: {item.get('descricao') or item.get('uso_tecnico', '')}\n"
                        f"Origem operacional: {item.get('origem_operacional') or item.get('propriedade', 'SECCOL')}\n"
                        f"Normas inicialmente relacionadas: {', '.join(norm_names) or 'Definir por aplicação'}\n"
                        f"Fonte oficial: {item['fonte_oficial']}\nVerificação: 15/08/2026\n\n"
                        "CONTROLE\nA matriz normativa é inicial. O responsável técnico deve confirmar modelo, "
                        "configuração, escopo contratado, método, requisitos regulatórios e edição vigente.\n"
                    ).encode("utf-8")
                    db.execute(
                        """INSERT INTO attachments
                           (company_id,record_id,filename,mime_type,content,size,category,version,
                            created_at,sha256,license_confirmed)
                           VALUES(?,?,?,?,?,?,?,?,?,?,0)""",
                        (current_company_id, record_id, f'ficha-{item["catalog_key"]}.txt',
                         "text/plain; charset=utf-8", reference_sheet, len(reference_sheet),
                         "Ficha de portfólio SECCOL", "Catálogo 2026-08-15", now,
                         hashlib.sha256(reference_sheet).hexdigest()),
                    )
        self.commit_if_outer()

    def validate_normative_base(self, module, payload, company_id):
        if module not in NORMATIVE_REQUIRED_MODULES:
            return
        requested = []
        primary = str(payload.get("registro_relacionado") or "").strip()
        if primary:
            requested.append(primary)
        for relation in payload.get("relacionamentos") or []:
            if isinstance(relation, dict):
                requested.append(str(relation.get("record") or relation.get("registro") or ""))
        target_ids = []
        for reference in requested:
            try:
                target_ids.append(int(reference.rsplit(":", 1)[-1]))
            except (ValueError, TypeError):
                continue
        if target_ids:
            placeholders = ",".join("?" for _ in target_ids)
            exists = self.connection().execute(
                f"""SELECT 1 FROM records WHERE company_id=? AND module='normas_tecnicas'
                    AND deleted_at IS NULL AND status NOT IN ('Obsoleta','Cancelada')
                    AND id IN ({placeholders}) LIMIT 1""",
                (company_id, *target_ids),
            ).fetchone()
            if exists:
                return
        raise ValueError(
            "Base normativa obrigatória: relacione ao menos uma norma técnica vigente antes de salvar."
        )

    def scalar(self, sql: str, params=()):
        row = self.connection().execute(sql, params).fetchone()
        return row[0] if row else None

    def execute(self, sql: str, params=()) -> sqlite3.Cursor:
        db = self.connection()
        cursor = db.execute(sql, params)
        self.commit_if_outer()
        return cursor

    def audit(self, user_id, action, entity_type, entity_id=None, detail=None, company_id=None):
        if company_id is None and user_id is not None:
            membership = self.connection().execute(
                "SELECT company_id FROM company_memberships WHERE user_id=? AND active=1 ORDER BY company_id LIMIT 1",
                (user_id,)).fetchone()
            company_id = membership["company_id"] if membership else None
        self.execute(
            """INSERT INTO audit_log
               (user_id,action,entity_type,entity_id,detail,created_at,company_id)
               VALUES(?,?,?,?,?,?,?)""",
            (user_id, action, entity_type, str(entity_id) if entity_id is not None else None,
             json_dumps(detail) if detail is not None else None, utc_now(), company_id),
        )


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def password_verify(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_text)
        expected = base64.b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class SIVSHandler(BaseHTTPRequestHandler):
    server_version = f"SIVS/{VERSION}"

    def version_string(self):
        return self.server_version

    @property
    def db(self) -> Database:
        return self.server.db  # type: ignore[attr-defined]

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

    def security_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")

    def client_ip(self):
        if os.environ.get("SIVS_TRUST_PROXY") == "1":
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if forwarded:
                return forwarded[:80]
        return str(self.client_address[0])[:80]

    def allow_request(self, bucket, limit, window_seconds):
        allowed, retry_after = self.server.rate_limit(  # type: ignore[attr-defined]
            bucket, self.client_ip(), limit, window_seconds
        )
        if not allowed:
            self.send_json(
                {
                    "ok": False,
                    "error": "rate_limited",
                    "message": "Muitas tentativas. Aguarde antes de tentar novamente.",
                },
                429,
                headers={"Retry-After": str(retry_after)},
            )
        return allowed

    def session_cookie(self, value="", max_age=0):
        secure = os.environ.get("SIVS_SECURE_COOKIE") == "1"
        if os.environ.get("SIVS_TRUST_PROXY") == "1":
            secure = secure or self.headers.get("X-Forwarded-Proto", "").lower() == "https"
        attributes = [
            f"sivs_session={value}", "Path=/", "HttpOnly", "SameSite=Strict",
            f"Max-Age={int(max_age)}",
        ]
        if secure:
            attributes.append("Secure")
        return "; ".join(attributes)

    def _safe_dispatch(self, callback):
        self._response_started = False
        self._request_id = secrets.token_hex(8)
        try:
            return callback()
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception:
            self.db.abort_manual_transaction()
            print(f"[ERRO {self._request_id}] Falha não tratada em {self.command} {self.path}")
            traceback.print_exc()
            if not self._response_started:
                return self.error_json(
                    "Não foi possível concluir a operação. Informe o código de referência ao suporte.",
                    500, "internal_error", request_id=self._request_id,
                )
            return None

    def send_json(self, data, status=200, headers=None):
        try:
            body = json_dumps(data).encode("utf-8")
        except (ValueError, TypeError):
            status = 500
            body = json_dumps({
                "ok": False, "error": "invalid_server_data",
                "message": "O servidor recusou dados não compatíveis com JSON estrito.",
                "requestId": getattr(self, "_request_id", None),
            }).encode("utf-8")
        self._response_started = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.security_headers()
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def error_json(self, message, status=400, code="bad_request", request_id=None):
        payload = {"ok": False, "error": code, "message": message}
        if request_id:
            payload["requestId"] = request_id
        self.send_json(payload, status)

    def parse_json(self, max_bytes=MAX_BODY):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Tamanho inválido")
        if length < 0:
            raise ValueError("Tamanho inválido")
        if length > max_bytes:
            raise ValueError(f"Conteúdo excede o limite de {max_bytes // (1024 * 1024)} MB")
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if length and content_type != "application/json":
            raise ValueError("Envie o corpo como application/json")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            value = json_loads_strict(raw)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            raise ValueError(f"JSON inválido: {exc}") from None
        if not isinstance(value, dict):
            raise ValueError("O corpo deve ser um objeto JSON")
        return value

    def cookies(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        return cookie

    def session(self):
        cookie = self.cookies().get("sivs_session")
        if not cookie:
            return None
        token_hash = hashlib.sha256(cookie.value.encode()).hexdigest()
        row = self.db.connection().execute(
            """SELECT s.token_hash,s.csrf_token,s.expires_at,s.company_id,
                      u.id,u.name,u.email,u.active,cm.role,cm.permissions,c.name company_name
               FROM sessions s
               JOIN users u ON u.id=s.user_id
               JOIN company_memberships cm
                 ON cm.user_id=u.id AND cm.company_id=s.company_id AND cm.active=1
               JOIN companies c ON c.id=s.company_id AND c.active=1
               WHERE s.token_hash=?""",
            (token_hash,),
        ).fetchone()
        if not row or not row["active"] or not row["company_id"] or row["expires_at"] < int(time.time()):
            if row:
                self.db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
            return None
        return row

    def require_auth(self, csrf=False):
        session = self.session()
        if not session:
            self.error_json("Sessão ausente ou expirada", 401, "unauthorized")
            return None
        if csrf and not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), session["csrf_token"]):
            self.error_json("Token de segurança inválido", 403, "csrf_invalid")
            return None
        return session

    def require_admin(self, session):
        if session["role"] != "admin":
            self.error_json("Esta operação exige perfil de administrador", 403, "forbidden")
            return False
        return True

    @staticmethod
    def permission_spec(session):
        try:
            raw = session["permissions"] if "permissions" in session.keys() else "{}"
            value = json_loads_strict(raw or "{}")
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError, json.JSONDecodeError):
            return {}

    def allowed_modules(self, session, action):
        role = str(session["role"])
        base = {
            "read": ROLE_READ_MODULES,
            "write": ROLE_MODULES,
            "export": ROLE_EXPORT_MODULES,
        }.get(action, {}).get(role, set())
        allowed = set(base)
        permissions = self.permission_spec(session)
        additions = permissions.get(action, [])
        denials = permissions.get(f"deny_{action}", [])
        if isinstance(additions, list):
            allowed.update(module for module in additions if module in MODULES)
        if isinstance(denials, list):
            allowed.difference_update(module for module in denials if module in MODULES)
        return allowed

    def require_module_read(self, session, module):
        if module not in self.allowed_modules(session, "read"):
            self.error_json("Seu perfil não possui permissão para consultar este módulo", 403, "forbidden")
            return False
        return True

    def require_module_write(self, session, module):
        if module not in self.allowed_modules(session, "write"):
            self.error_json("Seu perfil não possui permissão para alterar este módulo", 403, "forbidden")
            return False
        return True

    def require_module_export(self, session, module):
        if module not in self.allowed_modules(session, "export"):
            self.error_json("Seu perfil não possui permissão para exportar este módulo", 403, "forbidden")
            return False
        return True

    def capabilities(self, session):
        role = str(session["role"])
        capabilities = {
            "settings": role == "admin",
            "users": role == "admin",
            "companies_create": role == "admin",
            "audit": role in {"admin", "manager"},
            "trash": role in {"admin", "manager"},
            "approvals": role in {"admin", "manager", "approver"} or bool(
                self.allowed_modules(session, "write")
            ),
            "full_backup": role == "admin",
            "import": role == "admin",
        }
        custom = self.permission_spec(session).get("capabilities")
        if isinstance(custom, dict):
            for key, value in custom.items():
                if key in capabilities and isinstance(value, bool):
                    capabilities[key] = value
        return capabilities

    def route(self):
        parsed = urlparse(self.path)
        return parsed.path.rstrip("/") or "/", parse_qs(parsed.query)

    def do_GET(self):
        return self._safe_dispatch(lambda: self._do_get())

    def _do_get(self):
        path, query = self.route()
        if path.startswith("/api/"):
            return self.api_get(path, query)
        return self.static_get(path)

    def do_POST(self):
        return self._safe_dispatch(lambda: self.api_write("POST", self.route()[0]))

    def do_PUT(self):
        return self._safe_dispatch(lambda: self.api_write("PUT", self.route()[0]))

    def do_DELETE(self):
        return self._safe_dispatch(lambda: self.api_write("DELETE", self.route()[0]))

    def api_get(self, path, query):
        if path == "/api/status":
            configured = bool(self.db.scalar("SELECT configured FROM setup_state WHERE id=1"))
            return self.send_json({"ok": True, "configured": configured, "version": VERSION})
        if path == "/api/me":
            session = self.require_auth()
            if not session:
                return
            return self.send_json({"ok": True, "user": self.user_json(session),
                                   "csrfToken": session["csrf_token"],
                                   "capabilities": self.capabilities(session)})
        session = self.require_auth()
        if not session:
            return
        company_id = session["company_id"]
        if path == "/api/companies":
            return self.companies_get(session)
        if path == "/api/notifications":
            rows = self.db.connection().execute(
                """SELECT * FROM notifications
                   WHERE company_id=? AND (user_id IS NULL OR user_id=?)
                   ORDER BY read_at IS NULL DESC,id DESC LIMIT 100""",
                (company_id, session["id"])).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path == "/api/approvals":
            readable = sorted(self.allowed_modules(session, "read"))
            if not readable:
                return self.send_json({"ok": True, "items": []})
            status = (query.get("status") or ["Pendente"])[0].strip()
            placeholders = ",".join("?" for _ in readable)
            sql = """SELECT a.*,r.module,r.title,u0.name requested_by_name,
                            u1.name requested_to_name,u2.name decided_by_name
                     FROM approvals a JOIN records r ON r.id=a.record_id
                     LEFT JOIN users u0 ON u0.id=a.requested_by
                     LEFT JOIN users u1 ON u1.id=a.requested_to
                     LEFT JOIN users u2 ON u2.id=a.decided_by
                     WHERE a.company_id=? AND r.deleted_at IS NULL
                     AND (r.module IN (""" + placeholders + ") OR a.requested_to=?)"
            params = [company_id, *readable, session["id"]]
            if session["role"] not in {"admin", "manager", "approver"}:
                sql += " AND (a.requested_by=? OR a.requested_to=?)"
                params.extend([session["id"], session["id"]])
            if status:
                sql += " AND a.status=?"
                params.append(status)
            sql += " ORDER BY CASE a.status WHEN 'Pendente' THEN 0 ELSE 1 END,a.id DESC LIMIT 300"
            rows = self.db.connection().execute(sql, params).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path == "/api/fiscal/events":
            if not self.require_module_read(session, "fiscal"):
                return
            record_id = (query.get("record_id") or [""])[0]
            sql = """SELECT f.*,r.title,u.name user_name FROM fiscal_events f
                     JOIN records r ON r.id=f.record_id LEFT JOIN users u ON u.id=f.created_by
                     WHERE f.company_id=?"""
            params = [company_id]
            if str(record_id).isdigit():
                sql += " AND f.record_id=?"
                params.append(int(record_id))
            sql += " ORDER BY f.id DESC LIMIT 300"
            rows = self.db.connection().execute(sql, params).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path.startswith("/api/attachments/") and path.rsplit("/", 1)[-1].isdigit():
            return self.attachment_download(int(path.rsplit("/", 1)[-1]), session)
        if (path.startswith("/api/reports/") and path.endswith("/preview") and
                path.split("/")[3].isdigit()):
            return self.technical_report_preview(int(path.split("/")[3]), session)
        if path == "/api/modules":
            readable = self.allowed_modules(session, "read")
            return self.send_json({
                "ok": True,
                "modules": {key: value for key, value in MODULES.items() if key in readable},
                "readableModules": sorted(readable),
                "writableModules": sorted(self.allowed_modules(session, "write")),
                "exportableModules": sorted(self.allowed_modules(session, "export")),
                "capabilities": self.capabilities(session),
            })
        if path == "/api/dashboard":
            return self.dashboard(session)
        if path == "/api/search":
            return self.global_search(query, session)
        if path == "/api/settings":
            if not self.require_admin(session):
                return
            company = self.db.connection().execute(
                "SELECT id,name,cnpj,phone,email,address,active FROM companies WHERE id=?", (company_id,)).fetchone()
            rows = self.db.connection().execute(
                "SELECT key,value FROM company_settings WHERE company_id=?", (company_id,)).fetchall()
            settings = {row["key"]: json.loads(row["value"]) for row in rows}
            settings["company"] = dict(company) if company else {}
            return self.send_json({"ok": True, "settings": settings})
        if path == "/api/audit":
            if not self.capabilities(session)["audit"]:
                return self.error_json("Seu perfil não consulta a trilha de auditoria", 403, "forbidden")
            rows = self.db.connection().execute(
                """SELECT a.*,u.name user_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
                   WHERE a.company_id=? ORDER BY a.id DESC LIMIT 100""", (company_id,)
            ).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path == "/api/users":
            if not self.require_admin(session):
                return
            rows = self.db.connection().execute(
                """SELECT u.id,u.name,u.email,cm.role,cm.active,u.created_at,u.updated_at,cm.permissions
                   FROM company_memberships cm JOIN users u ON u.id=cm.user_id
                   WHERE cm.company_id=? ORDER BY u.name""", (company_id,)
            ).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path == "/api/trash":
            if not self.capabilities(session)["trash"]:
                return self.error_json("Seu perfil não consulta a lixeira", 403, "forbidden")
            readable = sorted(self.allowed_modules(session, "read"))
            if not readable:
                return self.send_json({"ok": True, "items": []})
            placeholders = ",".join("?" for _ in readable)
            rows = self.db.connection().execute(
                f"""SELECT * FROM records WHERE company_id=? AND deleted_at IS NOT NULL
                   AND module IN ({placeholders}) ORDER BY deleted_at DESC LIMIT 200""",
                (company_id, *readable),
            ).fetchall()
            self.db.audit(session["id"], "read", "trash", detail={"count": len(rows)}, company_id=company_id)
            return self.send_json({"ok": True, "items": [self.record_json(row) for row in rows]})
        if path == "/api/tenders/sources":
            # O catálogo sustenta o painel de editais. Exigir também acesso ao
            # módulo administrativo "fontes" quebrava a tela para perfis
            # comerciais com permissão explícita apenas em editais.
            if not self.require_module_read(session, "editais"):
                return
            rows = self.db.connection().execute(
                """SELECT * FROM records WHERE company_id=? AND module='fontes'
                   AND deleted_at IS NULL ORDER BY title""", (company_id,)
            ).fetchall()
            return self.send_json({"ok": True, "items": [self.record_json(row) for row in rows],
                                   "defaultKeywords": DEFAULT_TENDER_KEYWORDS})
        if path == "/api/tenders/results":
            if not self.require_module_read(session, "editais"):
                return
            return self.tender_results_get(query, session)
        if path.startswith("/api/tenders/jobs/") and path.rsplit("/", 1)[-1].isdigit():
            if not self.require_module_read(session, "editais"):
                return
            return self.tender_job_get(int(path.rsplit("/", 1)[-1]), session)
        if path == "/api/tenders/history":
            if not self.require_module_read(session, "editais"):
                return
            rows = self.db.connection().execute(
                "SELECT * FROM tender_searches WHERE company_id=? ORDER BY id DESC LIMIT 50", (company_id,)
            ).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path == "/api/tenders/schedules":
            if not self.require_module_read(session, "editais"):
                return
            rows = self.db.connection().execute(
                "SELECT * FROM search_schedules WHERE company_id=? ORDER BY active DESC,name", (company_id,)
            ).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path == "/api/relations/options":
            readable = sorted(self.allowed_modules(session, "read") - {"fontes"})
            if not readable:
                return self.send_json({"ok": True, "items": []})
            placeholders = ",".join("?" for _ in readable)
            rows = self.db.connection().execute(
                f"""SELECT id,module,title,status FROM records
                   WHERE company_id=? AND deleted_at IS NULL AND module IN ({placeholders})
                   ORDER BY CASE WHEN module='normas_tecnicas' THEN 0 ELSE 1 END,
                            updated_at DESC LIMIT 3000""", (company_id, *readable)
            ).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path == "/api/subjects":
            readable = sorted(self.allowed_modules(session, "read"))
            if not readable:
                return self.send_json({"ok": True, "items": []})
            placeholders = ",".join("?" for _ in readable)
            search = (query.get("q") or [""])[0].strip()
            sql = f"""SELECT s.id,s.name,s.status,s.created_at,s.updated_at,COUNT(DISTINCT r.id) record_count,
                      MAX(r.updated_at) last_activity
                      FROM subjects s
                      LEFT JOIN record_subjects rs ON rs.subject_id=s.id
                      LEFT JOIN records r ON r.id=rs.record_id AND r.company_id=? AND r.deleted_at IS NULL
                       AND r.module IN ({placeholders})
                      WHERE s.company_id=?"""
            params = [company_id, *readable, company_id]
            if search:
                sql += " AND s.name LIKE ?"
                params.append(f"%{search}%")
            sql += " GROUP BY s.id ORDER BY COALESCE(MAX(r.updated_at),s.updated_at) DESC LIMIT 500"
            rows = self.db.connection().execute(sql, params).fetchall()
            return self.send_json({"ok": True, "items": [dict(row) for row in rows]})
        if path.startswith("/api/subjects/") and path.rsplit("/", 1)[-1].isdigit():
            subject_id = int(path.rsplit("/", 1)[-1])
            subject = self.db.connection().execute(
                "SELECT * FROM subjects WHERE id=? AND company_id=?", (subject_id, company_id)).fetchone()
            if not subject:
                return self.error_json("Assunto não encontrado", 404)
            readable = sorted(self.allowed_modules(session, "read"))
            if not readable:
                rows = []
            else:
                placeholders = ",".join("?" for _ in readable)
                rows = self.db.connection().execute(
                    f"""SELECT DISTINCT r.* FROM records r JOIN record_subjects rs ON rs.record_id=r.id
                       WHERE rs.subject_id=? AND r.company_id=? AND r.deleted_at IS NULL
                       AND r.module IN ({placeholders}) ORDER BY r.updated_at DESC""",
                    (subject_id, company_id, *readable)).fetchall()
            return self.send_json({"ok": True, "subject": dict(subject),
                                   "records": [self.record_json(row) for row in rows]})
        if path == "/api/backup":
            return self.error_json(
                "Use POST com uma senha de proteção para gerar o backup criptografado",
                405, "method_not_allowed",
            )
        if path == "/api/export":
            return self.export_data(query, session)
        if path.startswith("/api/records"):
            return self.records_get(path, query, session)
        return self.error_json("Rota não encontrada", 404, "not_found")

    def api_write(self, method, path):
        if method == "POST" and path == "/api/setup":
            return self.initial_setup()
        if method == "POST" and path == "/api/login":
            return self.login()
        session = self.require_auth(csrf=True)
        if not session:
            return
        read_only_allowed = {"/api/logout", "/api/company/switch", "/api/notifications/read"}
        if session["role"] == "viewer" and path not in read_only_allowed:
            return self.error_json("Perfil de consulta não pode alterar dados", 403, "read_only")
        if method == "POST" and path == "/api/logout":
            token = self.cookies().get("sivs_session")
            if token:
                self.db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.value.encode()).hexdigest(),))
            headers = {"Set-Cookie": self.session_cookie()}
            return self.send_json({"ok": True}, headers=headers)
        if method == "POST" and path == "/api/company/switch":
            return self.company_switch(session)
        if method == "POST" and path == "/api/companies":
            if not self.require_admin(session):
                return
            return self.company_create(session)
        if method == "POST" and path == "/api/notifications/read":
            return self.notifications_read(session)
        if method == "PUT" and path == "/api/settings":
            if not self.require_admin(session):
                return
            return self.settings_update(session)
        if method == "POST" and path == "/api/backup":
            if not self.capabilities(session)["full_backup"]:
                return self.error_json("O backup de desastre exige administrador", 403, "forbidden")
            return self.database_backup(session)
        if method == "POST" and path == "/api/users":
            return self.user_create(session)
        if method == "PUT" and path.startswith("/api/users/"):
            return self.user_update(path, session)
        if method == "POST" and path.startswith("/api/restore/"):
            return self.record_restore(path, session)
        if method == "POST" and path == "/api/tenders/search":
            if not self.require_module_write(session, "editais"):
                return
            return self.tender_search(session)
        if method == "POST" and path == "/api/tenders/schedules":
            if not self.require_module_write(session, "editais"):
                return
            return self.search_schedule_save(session)
        if method == "PUT" and path.startswith("/api/tenders/results/"):
            if not self.require_module_write(session, "editais"):
                return
            return self.tender_result_update(path, session)
        if method == "POST" and path.startswith("/api/tenders/convert/"):
            if (not self.require_module_write(session, "editais") or
                    not self.require_module_write(session, "licitacoes")):
                return
            return self.tender_convert(path, session)
        if method == "POST" and path == "/api/xml/import":
            if not self.require_module_write(session, "importacoes_xml"):
                return
            return self.xml_import(session)
        if method == "POST" and path.startswith("/api/records/") and path.endswith("/attachments"):
            return self.attachment_upload(path, session)
        if method == "POST" and path.startswith("/api/records/") and path.endswith("/approval"):
            return self.approval_create(path, session)
        if method == "POST" and path.startswith("/api/approvals/"):
            return self.approval_decide(path, session)
        if (method == "POST" and path.startswith("/api/reports/") and path.endswith("/issue") and
                path.split("/")[3].isdigit()):
            return self.technical_report_issue(int(path.split("/")[3]), session)
        if method == "POST" and path.startswith("/api/fiscal/"):
            if not self.require_module_write(session, "fiscal"):
                return
            return self.fiscal_action(path, session)
        if method == "POST" and path.startswith("/api/subjects/"):
            if session["role"] not in {"admin", "manager"}:
                return self.error_json(
                    "Somente administradores e gestores podem reorganizar assuntos", 403, "forbidden")
            return self.subject_action(path, session)
        if path.startswith("/api/records"):
            return self.records_write(method, path, session)
        if method == "POST" and path == "/api/import":
            if not self.require_admin(session):
                return
            return self.import_data(session)
        return self.error_json("Rota não encontrada", 404, "not_found")

    def user_json(self, row):
        keys = set(row.keys())
        company_id = row["company_id"] if "company_id" in keys else None
        memberships = self.db.connection().execute(
            """SELECT c.id,c.name,c.cnpj,cm.role
               FROM company_memberships cm JOIN companies c ON c.id=cm.company_id
               WHERE cm.user_id=? AND cm.active=1 AND c.active=1 ORDER BY c.name""",
            (row["id"],)).fetchall()
        current = next((item for item in memberships if item["id"] == company_id), None)
        return {
            "id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"],
            "companyId": company_id, "companyName": current["name"] if current else None,
            "companies": [dict(item) for item in memberships],
        }

    def initial_setup(self):
        if not self.allow_request("setup", 8, 10 * 60):
            return
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        company = str(data.get("company", "SIVS")).strip() or "SIVS"
        if len(name) < 2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(password) < 10:
            return self.error_json("Informe nome, e-mail válido e senha com pelo menos 10 caracteres")
        now = utc_now()
        try:
            with self.db.transaction(immediate=True):
                setup = self.db.connection().execute(
                    "SELECT configured FROM setup_state WHERE id=1"
                ).fetchone()
                if (setup and setup["configured"]) or self.db.scalar("SELECT COUNT(*) FROM users"):
                    return self.error_json(
                        "O administrador inicial já foi criado", 409, "already_configured"
                    )
                default_company = self.db.connection().execute(
                    "SELECT id FROM companies ORDER BY id LIMIT 1"
                ).fetchone()
                if not default_company:
                    raise sqlite3.IntegrityError("empresa base ausente")
                company_id = default_company["id"]
                self.db.execute(
                    "UPDATE companies SET name=?,updated_at=? WHERE id=?",
                    (company, now, company_id),
                )
                cursor = self.db.execute(
                    """INSERT INTO users(name,email,password_hash,role,created_at,updated_at)
                       VALUES(?,?,?,?,?,?)""",
                    (name, email, password_hash(password), "admin", now, now),
                )
                user_id = cursor.lastrowid
                self.db.execute(
                    """INSERT INTO company_memberships
                       (company_id,user_id,role,permissions,active,created_at,updated_at)
                       VALUES(?,?,'admin','{}',1,?,?)""",
                    (company_id, user_id, now, now),
                )
                updated = self.db.execute(
                    """UPDATE setup_state SET configured=1,configured_at=?
                       WHERE id=1 AND configured=0""",
                    (now,),
                )
                if updated.rowcount != 1:
                    raise sqlite3.IntegrityError("configuração concorrente")
                self.db.seed_sources(company_id)
                self.db.seed_norms(company_id)
                self.db.seed_seccol_portfolio(company_id)
                self.db.audit(
                    user_id, "setup", "system", detail={"company": company},
                    company_id=company_id,
                )
        except sqlite3.IntegrityError:
            return self.error_json(
                "O administrador inicial já foi criado", 409, "already_configured"
            )
        return self.create_session(user_id, company_id)

    def login(self):
        if not self.allow_request("login", 12, 5 * 60):
            return
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        row = self.db.connection().execute("SELECT * FROM users WHERE email=? AND active=1", (email,)).fetchone()
        if not row or not password_verify(password, row["password_hash"]):
            time.sleep(0.2)
            return self.error_json("E-mail ou senha incorretos", 401, "invalid_credentials")
        requested_company = data.get("company_id")
        membership = None
        if requested_company:
            try:
                requested_company = int(requested_company)
            except (ValueError, TypeError):
                return self.error_json("Empresa inválida")
            membership = self.db.connection().execute(
                """SELECT cm.company_id FROM company_memberships cm JOIN companies c ON c.id=cm.company_id
                   WHERE cm.user_id=? AND cm.company_id=? AND cm.active=1 AND c.active=1""",
                (row["id"], requested_company)).fetchone()
        if not membership:
            membership = self.db.connection().execute(
                """SELECT cm.company_id FROM company_memberships cm JOIN companies c ON c.id=cm.company_id
                   WHERE cm.user_id=? AND cm.active=1 AND c.active=1 ORDER BY cm.company_id LIMIT 1""",
                (row["id"],)).fetchone()
        if not membership:
            return self.error_json("Usuário sem empresa ativa vinculada", 403, "no_company")
        self.db.audit(row["id"], "login", "session", company_id=membership["company_id"])
        return self.create_session(row["id"], membership["company_id"])

    def create_session(self, user_id, company_id=None):
        if company_id is None:
            membership = self.db.connection().execute(
                "SELECT company_id FROM company_memberships WHERE user_id=? AND active=1 ORDER BY company_id LIMIT 1",
                (user_id,)).fetchone()
            if not membership:
                return self.error_json("Usuário sem empresa vinculada", 403, "no_company")
            company_id = membership["company_id"]
        raw_token = secrets.token_urlsafe(36)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        csrf_token = secrets.token_urlsafe(24)
        expires = int(time.time()) + SESSION_SECONDS
        self.db.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        self.db.execute(
            """INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at,created_at,company_id)
               VALUES(?,?,?,?,?,?)""",
            (token_hash, user_id, csrf_token, expires, utc_now(), company_id),
        )
        row = self.db.connection().execute(
            """SELECT u.id,u.name,u.email,u.active,s.company_id,cm.role,c.name company_name
               FROM users u JOIN sessions s ON s.user_id=u.id
               JOIN company_memberships cm ON cm.user_id=u.id AND cm.company_id=s.company_id
               JOIN companies c ON c.id=s.company_id
               WHERE u.id=? AND s.token_hash=?""", (user_id, token_hash)).fetchone()
        cookie = self.session_cookie(raw_token, SESSION_SECONDS)
        return self.send_json({"ok": True, "user": self.user_json(row), "csrfToken": csrf_token},
                              headers={"Set-Cookie": cookie})

    def companies_get(self, session):
        rows = self.db.connection().execute(
            """SELECT c.id,c.name,c.cnpj,c.phone,c.email,c.address,c.active,cm.role
               FROM company_memberships cm JOIN companies c ON c.id=cm.company_id
               WHERE cm.user_id=? AND cm.active=1 AND c.active=1 ORDER BY c.name""",
            (session["id"],)).fetchall()
        return self.send_json({"ok": True, "currentCompanyId": session["company_id"],
                               "items": [dict(row) for row in rows]})

    def company_create(self, session):
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        name = str(data.get("name", "")).strip()
        if len(name) < 2:
            return self.error_json("Informe o nome da empresa")
        cnpj = str(data.get("cnpj") or "").strip() or None
        email = str(data.get("email") or "").strip().lower() or None
        if cnpj and not _valid_cnpj(cnpj):
            return self.error_json("CNPJ da empresa inválido")
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            return self.error_json("E-mail da empresa inválido")
        now = utc_now()
        with self.db.transaction(immediate=True):
            cursor = self.db.execute(
                """INSERT INTO companies(name,cnpj,phone,email,address,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (name, cnpj, str(data.get("phone") or "").strip() or None, email,
                 str(data.get("address") or "").strip() or None, now, now),
            )
            company_id = cursor.lastrowid
            self.db.execute(
                """INSERT INTO company_memberships
                   (company_id,user_id,role,permissions,active,created_at,updated_at)
                   VALUES(?,?,'admin','{}',1,?,?)""", (company_id, session["id"], now, now))
            self.db.seed_sources(company_id)
            self.db.seed_norms(company_id)
            self.db.seed_seccol_portfolio(company_id)
            self.db.audit(session["id"], "create", "company", company_id,
                          {"name": name}, company_id=company_id)
        return self.send_json({"ok": True, "id": company_id}, 201)

    def company_switch(self, session):
        try:
            data = self.parse_json()
            company_id = int(data.get("company_id"))
        except (ValueError, TypeError):
            return self.error_json("Empresa inválida")
        membership = self.db.connection().execute(
            """SELECT 1 FROM company_memberships cm JOIN companies c ON c.id=cm.company_id
               WHERE cm.user_id=? AND cm.company_id=? AND cm.active=1 AND c.active=1""",
            (session["id"], company_id)).fetchone()
        if not membership:
            return self.error_json("Usuário não possui acesso a esta empresa", 403, "forbidden")
        self.db.execute("UPDATE sessions SET company_id=? WHERE token_hash=?", (company_id, session["token_hash"]))
        self.db.audit(session["id"], "switch", "company", company_id, company_id=company_id)
        return self.send_json({"ok": True, "companyId": company_id})

    def notifications_read(self, session):
        self.db.execute(
            """UPDATE notifications SET read_at=?
               WHERE company_id=? AND (user_id IS NULL OR user_id=?) AND read_at IS NULL""",
            (utc_now(), session["company_id"], session["id"]))
        return self.send_json({"ok": True})

    def dashboard(self, session):
        db = self.db.connection()
        company_id = session["company_id"]
        readable = sorted(self.allowed_modules(session, "read"))
        if not readable:
            return self.send_json({
                "ok": True, "counts": {}, "income": 0, "expense": 0, "alerts": [],
                "recent": [], "operationalTotal": 0, "pendingApprovals": 0,
                "unreadNotifications": 0, "financialVisible": False, "workItems": [],
            })
        placeholders = ",".join("?" for _ in readable)
        counts = {row["module"]: row["total"] for row in db.execute(
            f"""SELECT module,COUNT(*) total FROM records
               WHERE company_id=? AND deleted_at IS NULL AND module IN ({placeholders})
               GROUP BY module""", (company_id, *readable)).fetchall()}
        operational_total = self.db.scalar(
            f"""SELECT COUNT(*) FROM records WHERE company_id=? AND deleted_at IS NULL
               AND module IN ({placeholders})
               AND module NOT IN ('fontes','normas_tecnicas')
               AND COALESCE(json_extract(payload,'$.catalogo_seccol'),0)!=1""",
            (company_id, *readable),
        ) or 0
        financial_visible = bool({"financeiro", "caixa"} & set(readable))
        financial = {"income": 0, "expense": 0}
        if "financeiro" in readable and self.db.scalar(
            "SELECT COUNT(*) FROM records WHERE company_id=? AND module='financeiro' AND deleted_at IS NULL",
            (company_id,),
        ):
            financial = dict(db.execute(
                """SELECT
                   COALESCE(SUM(CASE WHEN json_extract(payload,'$.tipo_lancamento')='Receita'
                                     THEN ABS(COALESCE(amount,0)) ELSE 0 END),0) income,
                   COALESCE(SUM(CASE WHEN json_extract(payload,'$.tipo_lancamento')='Despesa'
                                     THEN ABS(COALESCE(amount,0)) ELSE 0 END),0) expense
                   FROM records WHERE company_id=? AND module='financeiro' AND deleted_at IS NULL""",
                (company_id,),
            ).fetchone())
        elif "caixa" in readable:
            financial = dict(db.execute(
                """SELECT
                   COALESCE(SUM(CASE WHEN json_extract(payload,'$.tipo_movimento')='Entrada'
                                     THEN ABS(COALESCE(amount,0)) ELSE 0 END),0) income,
                   COALESCE(SUM(CASE WHEN json_extract(payload,'$.tipo_movimento')='Saída'
                                     THEN ABS(COALESCE(amount,0)) ELSE 0 END),0) expense
                   FROM records WHERE company_id=? AND module='caixa' AND deleted_at IS NULL""",
                (company_id,),
            ).fetchone())
        alerts = [dict(row) for row in db.execute(
            f"""SELECT id,module,title,status,amount,due_date FROM records
               WHERE company_id=? AND deleted_at IS NULL AND due_date IS NOT NULL
               AND module IN ({placeholders})
               AND due_date <= date('now','+7 days')
               AND status NOT IN ('Concluído','Pago','Cancelado','Finalizado')
               ORDER BY due_date ASC LIMIT 8""", (company_id, *readable)
        ).fetchall()]
        recent = [self.record_json(row) for row in db.execute(
            f"""SELECT * FROM records WHERE company_id=? AND deleted_at IS NULL
               AND module IN ({placeholders})
               AND module NOT IN ('fontes','normas_tecnicas')
               AND COALESCE(json_extract(payload,'$.catalogo_seccol'),0)!=1
               ORDER BY updated_at DESC LIMIT 8""", (company_id, *readable)).fetchall()]
        approval_sql = f"""SELECT COUNT(*) FROM approvals a JOIN records r ON r.id=a.record_id
                            WHERE a.company_id=? AND a.status='Pendente'
                              AND r.module IN ({placeholders})"""
        approval_params = [company_id, *readable]
        if session["role"] not in {"admin", "manager", "approver"}:
            approval_sql += " AND (a.requested_by=? OR a.requested_to=?)"
            approval_params.extend([session["id"], session["id"]])
        pending_approvals = self.db.scalar(approval_sql, approval_params) or 0
        unread = self.db.scalar(
            """SELECT COUNT(*) FROM notifications WHERE company_id=? AND read_at IS NULL
               AND (user_id IS NULL OR user_id=?)""", (company_id, session["id"])) or 0
        approval_work_sql = f"""SELECT a.id approval_id,r.id record_id,r.module,r.title,
                                      a.approval_type,a.requested_at
                               FROM approvals a JOIN records r ON r.id=a.record_id
                               WHERE a.company_id=? AND a.status='Pendente' AND r.deleted_at IS NULL
                                 AND r.module IN ({placeholders})"""
        approval_work_params = [company_id, *readable]
        if session["role"] not in {"admin", "manager", "approver"}:
            approval_work_sql += " AND (a.requested_by=? OR a.requested_to=?)"
            approval_work_params.extend([session["id"], session["id"]])
        approval_work_sql += " ORDER BY a.requested_at ASC LIMIT 6"
        approval_work = db.execute(approval_work_sql, approval_work_params).fetchall()
        work_items = [{
            "kind": "approval", "priority": "high", "target": "aprovacoes",
            "recordId": row["record_id"], "module": row["module"], "title": row["title"],
            "meta": f'Aprovação: {row["approval_type"]}', "dueDate": None,
        } for row in approval_work]
        known_records = {item["recordId"] for item in work_items}
        today = datetime.now(timezone.utc).date().isoformat()
        for row in alerts:
            if row["id"] in known_records:
                continue
            overdue = str(row.get("due_date") or "") < today
            work_items.append({
                "kind": "overdue" if overdue else "deadline",
                "priority": "critical" if overdue else "normal",
                "target": row["module"], "recordId": row["id"], "module": row["module"],
                "title": row["title"],
                "meta": "Prazo vencido" if overdue else "Prazo próximo",
                "dueDate": row.get("due_date"),
            })
            known_records.add(row["id"])
        if len(work_items) < 10:
            own_rows = db.execute(
                f"""SELECT id,module,title,status,updated_at FROM records
                    WHERE company_id=? AND deleted_at IS NULL AND created_by=?
                      AND module IN ({placeholders})
                      AND status NOT IN ('Concluído','Pago','Cancelado','Finalizado','Obsoleto')
                      AND COALESCE(json_extract(payload,'$.catalogo_seccol'),0)!=1
                    ORDER BY updated_at DESC LIMIT 10""",
                (company_id, session["id"], *readable),
            ).fetchall()
            for row in own_rows:
                if row["id"] in known_records or len(work_items) >= 10:
                    continue
                work_items.append({
                    "kind": "followup", "priority": "low", "target": row["module"],
                    "recordId": row["id"], "module": row["module"], "title": row["title"],
                    "meta": f'Em acompanhamento · {row["status"]}', "dueDate": None,
                })
                known_records.add(row["id"])
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        work_items.sort(key=lambda item: (priority_order[item["priority"]], item.get("dueDate") or "9999"))
        return self.send_json({"ok": True, "counts": counts, "income": financial["income"],
                               "expense": financial["expense"], "alerts": alerts, "recent": recent,
                               "operationalTotal": operational_total,
                               "pendingApprovals": pending_approvals, "unreadNotifications": unread,
                               "financialVisible": financial_visible, "workItems": work_items[:10]})

    def global_search(self, query, session):
        term = (query.get("q") or [""])[0].strip()
        if len(term) < 2:
            return self.send_json({"ok": True, "query": term, "items": []})
        if len(term) > 120:
            return self.error_json("A busca deve possuir no máximo 120 caracteres", 400, "invalid_search")
        readable = sorted(self.allowed_modules(session, "read"))
        if not readable:
            return self.send_json({"ok": True, "query": term, "items": []})
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        placeholders = ",".join("?" for _ in readable)
        rows = self.db.connection().execute(
            f"""SELECT id,module,title,status,due_date,updated_at
                FROM records WHERE company_id=? AND deleted_at IS NULL
                  AND module IN ({placeholders})
                  AND (title LIKE ? ESCAPE '\\' OR status LIKE ? ESCAPE '\\'
                       OR (module!='fontes' AND payload LIKE ? ESCAPE '\\'))
                ORDER BY CASE WHEN title LIKE ? ESCAPE '\\' THEN 0 ELSE 1 END,
                         updated_at DESC LIMIT 40""",
            (session["company_id"], *readable, pattern, pattern, pattern, pattern),
        ).fetchall()
        return self.send_json({
            "ok": True, "query": term,
            "items": [{
                "id": row["id"], "module": row["module"], "title": row["title"],
                "status": row["status"], "dueDate": row["due_date"], "updatedAt": row["updated_at"],
            } for row in rows],
        })

    def records_get(self, path, query, session):
        company_id = session["company_id"]
        pieces = path.split("/")
        if len(pieces) == 4 and pieces[3].isdigit():
            row = self.db.connection().execute(
                "SELECT * FROM records WHERE id=? AND company_id=? AND deleted_at IS NULL",
                (int(pieces[3]), company_id)).fetchone()
            if not row:
                return self.error_json("Registro não encontrado", 404)
            if not self.require_module_read(session, row["module"]):
                return
            return self.send_json({"ok": True, "item": self.record_json(row)})
        module = (query.get("module") or [""])[0]
        if module not in MODULES:
            return self.error_json("Módulo inválido")
        if not self.require_module_read(session, module):
            return
        search = (query.get("q") or [""])[0].strip()
        status = (query.get("status") or [""])[0].strip()
        sql = "SELECT * FROM records WHERE company_id=? AND module=? AND deleted_at IS NULL"
        params = [company_id, module]
        if search:
            sql += " AND (title LIKE ? OR payload LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT 500"
        rows = self.db.connection().execute(sql, params).fetchall()
        return self.send_json({"ok": True, "items": [self.record_json(row) for row in rows]})

    def record_json(self, row):
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item["payload"] or "{}")
        subject = self.db.connection().execute(
            "SELECT id,name,status FROM subjects WHERE id=? AND company_id=?",
            (item.get("subject_id"), item.get("company_id"))
        ).fetchone() if item.get("subject_id") else None
        relations = self.db.connection().execute(
            """SELECT rr.to_record_id,rr.relationship_type,r.module,r.title
               FROM record_relationships rr JOIN records r ON r.id=rr.to_record_id
               WHERE rr.from_record_id=? AND r.company_id=? AND r.deleted_at IS NULL ORDER BY rr.id""",
            (item["id"], item.get("company_id"))
        ).fetchall()
        subject_rows = self.db.connection().execute(
            """SELECT s.id,s.name,rs.relationship_type,rs.is_primary
               FROM record_subjects rs JOIN subjects s ON s.id=rs.subject_id
               WHERE rs.record_id=? AND s.company_id=? ORDER BY rs.is_primary DESC,s.name""",
            (item["id"], item.get("company_id"))).fetchall()
        attachments = self.db.connection().execute(
            """SELECT id,filename,mime_type,size,category,version,sha256,license_confirmed,created_at
               FROM attachments WHERE record_id=? AND company_id=? ORDER BY id DESC""",
            (item["id"], item.get("company_id"))).fetchall()
        approvals = self.db.connection().execute(
            """SELECT a.*,u0.name requested_by_name,u1.name requested_to_name,u2.name decided_by_name
               FROM approvals a LEFT JOIN users u0 ON u0.id=a.requested_by
               LEFT JOIN users u1 ON u1.id=a.requested_to
               LEFT JOIN users u2 ON u2.id=a.decided_by
               WHERE a.record_id=? AND a.company_id=? ORDER BY a.id DESC""",
            (item["id"], item.get("company_id"))).fetchall()
        if subject:
            item["payload"]["assunto"] = subject["name"]
            item["subject"] = dict(subject)
        item["payload"]["relacionamentos"] = [
            {"record": f'{row["module"]}:{row["to_record_id"]}', "type": row["relationship_type"],
            "label": row["title"]} for row in relations]
        item["subjects"] = [dict(subject_row) for subject_row in subject_rows]
        item["attachments"] = [dict(attachment) for attachment in attachments]
        item["approvals"] = [dict(approval) for approval in approvals]
        return item

    @staticmethod
    def _validate_json_shape(value, path="payload", depth=0):
        if depth > 10:
            raise ValueError(f"{path}: estrutura excede 10 níveis")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{path}: número não finito")
        if isinstance(value, str) and len(value) > 20_000:
            raise ValueError(f"{path}: texto excede 20.000 caracteres")
        if isinstance(value, dict):
            if len(value) > 300:
                raise ValueError(f"{path}: campos em excesso")
            for key, child in value.items():
                if not isinstance(key, str) or len(key) > 120:
                    raise ValueError(f"{path}: nome de campo inválido")
                SIVSHandler._validate_json_shape(child, f"{path}.{key}", depth + 1)
        elif isinstance(value, list):
            if len(value) > 1_000:
                raise ValueError(f"{path}: itens em excesso")
            for index, child in enumerate(value):
                SIVSHandler._validate_json_shape(child, f"{path}[{index}]", depth + 1)

    def validate_record_payload(self, module, payload):
        self._validate_json_shape(payload)
        try:
            encoded = json_dumps(payload).encode("utf-8")
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Detalhes incompatíveis com JSON: {exc}") from None
        if len(encoded) > MAX_RECORD_PAYLOAD:
            raise ValueError("Detalhes do registro excedem 1 MB")

        subject = str(payload.get("assunto") or "").strip()
        if len(subject) < 3:
            raise ValueError("Assunto principal é obrigatório e deve possuir ao menos 3 caracteres")
        if len(subject) > 180:
            raise ValueError("Assunto principal excede 180 caracteres")

        missing = [key for key in REQUIRED_PAYLOAD_FIELDS.get(module, ()) if _blank(payload.get(key))]
        if missing:
            labels = ", ".join(key.replace("_", " ") for key in missing[:8])
            suffix = "…" if len(missing) > 8 else ""
            raise ValueError(f"Campos obrigatórios ausentes: {labels}{suffix}")

        for key in DATE_FIELDS.get(module, set()):
            value = payload.get(key)
            if _blank(value):
                continue
            try:
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"{key.replace('_', ' ').title()}: data inválida; use AAAA-MM-DD") from None
        for key in DATETIME_FIELDS.get(module, set()):
            value = payload.get(key)
            if _blank(value):
                continue
            try:
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"{key.replace('_', ' ').title()}: data e hora inválidas") from None
        for key in TIME_FIELDS.get(module, set()):
            value = payload.get(key)
            if _blank(value):
                continue
            try:
                datetime.strptime(str(value), "%H:%M")
            except ValueError:
                raise ValueError(f"{key.replace('_', ' ').title()}: hora inválida") from None
        for key in NUMBER_FIELDS.get(module, set()):
            value = payload.get(key)
            if _blank(value):
                continue
            try:
                numeric = float(value)
            except (ValueError, TypeError):
                raise ValueError(f"{key.replace('_', ' ').title()}: número inválido") from None
            if not math.isfinite(numeric) or abs(numeric) > 1_000_000_000_000_000:
                raise ValueError(f"{key.replace('_', ' ').title()}: número fora do limite")
            if key in {"probabilidade"} and not 0 <= numeric <= 100:
                raise ValueError("Probabilidade deve ficar entre 0 e 100")
            if key in {"tempo_minutos", "quilometragem", "proxima_km", "preco_venda", "quantidade", "horas"} and numeric < 0:
                raise ValueError(f"{key.replace('_', ' ').title()} não pode ser negativo")

        for key in EMAIL_FIELDS.get(module, set()):
            value = str(payload.get(key) or "").strip()
            if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
                raise ValueError(f"{key.replace('_', ' ').title()}: e-mail inválido")
        for key in URL_FIELDS.get(module, set()):
            value = str(payload.get(key) or "").strip()
            if not value:
                continue
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{key.replace('_', ' ').title()}: URL deve usar HTTP ou HTTPS")

        if module in {"clientes", "fornecedores"}:
            _validate_document(str(payload.get("documento") or ""))
        elif module == "colaboradores":
            if not _valid_cpf(str(payload.get("cpf") or "")):
                raise ValueError("CPF inválido")
        elif module == "concorrentes":
            if not _valid_cnpj(str(payload.get("cnpj") or "")):
                raise ValueError("CNPJ inválido")

        if module == "fiscal" and str(payload.get("tipo_nota") or "") == "NF-e":
            key = re.sub(r"\D", "", str(payload.get("chave") or ""))
            if len(key) != 44:
                raise ValueError("Chave de NF-e deve possuir 44 dígitos")

        date_pairs = {
            "contratos": ("inicio", "fim"),
            "treinamentos": ("data", "validade"),
            "calibracoes": ("data_calibracao", "proxima_calibracao"),
            "ordens_servico": ("inicio", "fim"),
        }
        if module in date_pairs:
            start_key, end_key = date_pairs[module]
            start, end = payload.get(start_key), payload.get(end_key)
            if start and end:
                try:
                    if datetime.fromisoformat(str(end)) < datetime.fromisoformat(str(start)):
                        raise ValueError(f"{end_key.replace('_', ' ').title()} não pode ser anterior a {start_key.replace('_', ' ')}")
                except ValueError as exc:
                    if "não pode" in str(exc):
                        raise

        relationships = payload.get("relacionamentos") or []
        if not isinstance(relationships, list) or len(relationships) > 50:
            raise ValueError("Relacionamentos devem ser uma lista de até 50 itens")
        for relation in relationships:
            if not isinstance(relation, dict):
                raise ValueError("Relacionamento inválido")
            reference = str(relation.get("record") or relation.get("registro") or "")
            match = re.fullmatch(r"([a-z_]+):(\d+)", reference)
            if not match or match.group(1) not in MODULES or int(match.group(2)) <= 0:
                raise ValueError("Referência de relacionamento inválida")
            relation_type = str(relation.get("type") or relation.get("tipo") or "Relacionado a").strip()
            if not relation_type or len(relation_type) > 80:
                raise ValueError("Tipo de relacionamento inválido")

    def normalized_record(self, data, existing_status=None):
        if not isinstance(data, dict):
            raise ValueError("Registro deve ser um objeto")
        module = str(data.get("module", "")).strip()
        title = str(data.get("title", "")).strip()
        status = str(data.get("status", "Ativo")).strip() or "Ativo"
        amount = data.get("amount")
        due_date = str(data.get("due_date") or "").strip() or None
        payload = data.get("payload") or {}
        if module not in MODULES or not title:
            raise ValueError("Módulo e título são obrigatórios")
        if len(title) > 240 or any(ord(char) < 32 and char not in "\t\n" for char in title):
            raise ValueError("Título inválido ou superior a 240 caracteres")
        allowed_statuses = MODULE_STATUSES.get(module, DEFAULT_STATUSES)
        if status not in allowed_statuses and status != existing_status:
            raise ValueError("Status inválido para este módulo")
        if amount in ("", None):
            amount = None
        else:
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                raise ValueError("Valor financeiro inválido") from None
            if not math.isfinite(amount) or abs(amount) > 1_000_000_000_000_000:
                raise ValueError("Valor financeiro fora do limite permitido")
        if due_date:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Prazo inválido; use AAAA-MM-DD") from None
        if not isinstance(payload, dict):
            raise ValueError("Detalhes inválidos")
        self.validate_record_payload(module, payload)
        return module, title[:240], status[:80], amount, due_date, json_dumps(payload)

    def records_write(self, method, path, session):
        try:
            data = self.parse_json() if method != "DELETE" else {}
        except ValueError as exc:
            return self.error_json(str(exc))
        pieces = path.split("/")
        record_id = int(pieces[3]) if len(pieces) == 4 and pieces[3].isdigit() else None
        if method == "POST" and path == "/api/records":
            try:
                values = self.normalized_record(data)
                self.db.validate_normative_base(values[0], json.loads(values[5]), session["company_id"])
            except (ValueError, TypeError) as exc:
                return self.error_json(str(exc))
            if not self.require_module_write(session, values[0]):
                return
            now = utc_now()
            try:
                with self.db.transaction(immediate=True):
                    cursor = self.db.execute(
                        """INSERT INTO records
                           (module,title,status,amount,due_date,payload,created_by,created_at,updated_at,
                            company_id,revision)
                           VALUES(?,?,?,?,?,?,?,?,?,?,1)""",
                        (*values, session["id"], now, now, session["company_id"]))
                    record_id = cursor.lastrowid
                    self.db.sync_relationships(
                        record_id, json.loads(values[5]), session["id"], session["company_id"]
                    )
                    self.db.audit(
                        session["id"], "create", values[0], record_id,
                        {"title": values[1], "revision": 1}, company_id=session["company_id"],
                    )
            except (ValueError, sqlite3.Error) as exc:
                return self.error_json(str(exc))
            row = self.db.connection().execute(
                "SELECT * FROM records WHERE id=? AND company_id=?", (record_id, session["company_id"])
            ).fetchone()
            return self.send_json({"ok": True, "item": self.record_json(row)}, 201)
        if not record_id:
            return self.error_json("Registro inválido", 404)
        existing = self.db.connection().execute(
            "SELECT * FROM records WHERE id=? AND company_id=? AND deleted_at IS NULL",
            (record_id, session["company_id"])).fetchone()
        if not existing:
            return self.error_json("Registro não encontrado", 404)
        if not self.require_module_write(session, existing["module"]):
            return
        if method == "DELETE":
            if existing["module"] == "normas_tecnicas":
                referenced = self.db.scalar(
                    """SELECT COUNT(*) FROM record_relationships rr
                       JOIN records r ON r.id=rr.from_record_id
                       WHERE rr.to_record_id=? AND r.company_id=? AND r.deleted_at IS NULL
                       AND r.module IN ('certificados','laudos_tecnicos','estudos_tecnicos')""",
                    (record_id, session["company_id"]),
                )
                if referenced:
                    return self.error_json(
                        "Esta norma fundamenta documento(s) ativo(s) e não pode ser excluída.",
                        409, "norm_in_use",
                    )
            now = utc_now()
            with self.db.transaction(immediate=True):
                current = self.db.connection().execute(
                    "SELECT * FROM records WHERE id=? AND company_id=? AND deleted_at IS NULL",
                    (record_id, session["company_id"]),
                ).fetchone()
                if not current:
                    return self.error_json("O registro já foi alterado ou excluído", 409, "write_conflict")
                self.save_record_version(current, session["id"])
                self.db.execute(
                    """UPDATE records SET deleted_at=?,updated_at=?,revision=revision+1
                       WHERE id=? AND company_id=?""",
                    (now, now, record_id, session["company_id"]),
                )
                self.db.execute(
                    """UPDATE approvals SET status='Expirada',decided_at=?,
                       decision_comment='Registro excluído após a solicitação.'
                       WHERE record_id=? AND company_id=? AND status='Pendente'""",
                    (now, record_id, session["company_id"]),
                )
                self.db.audit(
                    session["id"], "delete", current["module"], record_id,
                    {"title": current["title"], "revision": current["revision"] + 1},
                    company_id=session["company_id"],
                )
            return self.send_json({"ok": True})
        if method == "PUT":
            try:
                expected_revision = int(data.get("revision"))
                if expected_revision < 1:
                    raise ValueError
            except (ValueError, TypeError):
                return self.error_json(
                    "A revisão do registro é obrigatória para salvar alterações",
                    409, "revision_required",
                )
            try:
                values = self.normalized_record(data, existing_status=existing["status"])
                self.db.validate_normative_base(values[0], json.loads(values[5]), session["company_id"])
            except (ValueError, TypeError) as exc:
                return self.error_json(str(exc))
            if values[0] != existing["module"]:
                return self.error_json("O módulo de um registro existente não pode ser alterado")
            if not self.require_module_write(session, values[0]):
                return
            now = utc_now()
            try:
                with self.db.transaction(immediate=True):
                    current = self.db.connection().execute(
                        "SELECT * FROM records WHERE id=? AND company_id=? AND deleted_at IS NULL",
                        (record_id, session["company_id"]),
                    ).fetchone()
                    if not current or current["revision"] != expected_revision:
                        return self.error_json(
                            "Este registro foi alterado por outra pessoa. Recarregue antes de salvar.",
                            409, "write_conflict",
                        )
                    self.save_record_version(current, session["id"])
                    cursor = self.db.execute(
                        """UPDATE records
                           SET title=?,status=?,amount=?,due_date=?,payload=?,updated_at=?,revision=revision+1
                           WHERE id=? AND company_id=? AND revision=?""",
                        (values[1], values[2], values[3], values[4], values[5], now,
                         record_id, session["company_id"], expected_revision),
                    )
                    if cursor.rowcount != 1:
                        raise sqlite3.IntegrityError("conflito de gravação")
                    self.db.sync_relationships(
                        record_id, json.loads(values[5]), session["id"], session["company_id"]
                    )
                    self.db.execute(
                        """UPDATE approvals SET status='Expirada',decided_at=?,
                           decision_comment='Registro alterado após a solicitação.'
                           WHERE record_id=? AND company_id=? AND status='Pendente'""",
                        (now, record_id, session["company_id"]),
                    )
                    self.db.audit(
                        session["id"], "update", values[0], record_id,
                        {"title": values[1], "from_revision": expected_revision,
                         "to_revision": expected_revision + 1},
                        company_id=session["company_id"],
                    )
            except ValueError as exc:
                return self.error_json(str(exc))
            except sqlite3.IntegrityError:
                return self.error_json(
                    "Este registro foi alterado por outra pessoa. Recarregue antes de salvar.",
                    409, "write_conflict",
                )
            row = self.db.connection().execute(
                "SELECT * FROM records WHERE id=? AND company_id=?", (record_id, session["company_id"])
            ).fetchone()
            return self.send_json({"ok": True, "item": self.record_json(row)})
        return self.error_json("Método não permitido", 405)

    def save_record_version(self, row, user_id):
        snapshot = self.record_json(row)
        self.db.execute(
            """INSERT INTO record_versions
               (record_id,snapshot,changed_by,created_at,company_id) VALUES(?,?,?,?,?)""",
            (row["id"], json_dumps(snapshot), user_id, utc_now(), row["company_id"]),
        )

    def record_restore(self, path, session):
        pieces = path.split("/")
        if len(pieces) != 4 or not pieces[3].isdigit():
            return self.error_json("Registro inválido", 404)
        record_id = int(pieces[3])
        row = self.db.connection().execute(
            "SELECT * FROM records WHERE id=? AND company_id=? AND deleted_at IS NOT NULL",
            (record_id, session["company_id"])
        ).fetchone()
        if not row:
            return self.error_json("Registro excluído não encontrado", 404)
        if not self.require_module_write(session, row["module"]):
            return
        now = utc_now()
        with self.db.transaction(immediate=True):
            self.save_record_version(row, session["id"])
            updated = self.db.execute(
                """UPDATE records SET deleted_at=NULL,updated_at=?,revision=revision+1
                   WHERE id=? AND company_id=? AND deleted_at IS NOT NULL""",
                (now, record_id, session["company_id"]),
            )
            if updated.rowcount != 1:
                return self.error_json(
                    "O registro já foi restaurado por outra pessoa", 409, "write_conflict"
                )
            self.db.audit(
                session["id"], "restore", row["module"], record_id,
                {"title": row["title"], "revision": row["revision"] + 1},
                company_id=session["company_id"],
            )
        return self.send_json({"ok": True})

    def user_create(self, session):
        if not self.require_admin(session):
            return
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        role = str(data.get("role", "operator"))
        if role not in ROLE_MODULES:
            return self.error_json("Perfil inválido")
        if (len(name) < 2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
                or len(password) < 10):
            return self.error_json("Informe nome, e-mail válido e senha com pelo menos 10 caracteres")
        now = utc_now()
        try:
            with self.db.transaction(immediate=True):
                existing = self.db.connection().execute(
                    "SELECT id FROM users WHERE email=?", (email,)
                ).fetchone()
                if existing:
                    user_id = existing["id"]
                else:
                    cursor = self.db.execute(
                        """INSERT INTO users(name,email,password_hash,role,created_at,updated_at)
                           VALUES(?,?,?,?,?,?)""",
                        (name, email, password_hash(password), role, now, now),
                    )
                    user_id = cursor.lastrowid
                self.db.execute(
                    """INSERT INTO company_memberships
                       (company_id,user_id,role,permissions,active,created_at,updated_at)
                       VALUES(?,?,?,'{}',1,?,?)""",
                    (session["company_id"], user_id, role, now, now),
                )
                self.db.audit(
                    session["id"], "create", "user", user_id,
                    {"email": email, "role": role}, company_id=session["company_id"],
                )
        except sqlite3.IntegrityError:
            return self.error_json("Este usuário já pertence à empresa", 409, "duplicate_membership")
        return self.send_json({"ok": True, "id": user_id}, 201)

    def user_update(self, path, session):
        if not self.require_admin(session):
            return
        pieces = path.split("/")
        if len(pieces) != 4 or not pieces[3].isdigit():
            return self.error_json("Usuário inválido", 404)
        user_id = int(pieces[3])
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        role = str(data.get("role", "operator"))
        active = 1 if data.get("active", True) else 0
        if role not in ROLE_MODULES:
            return self.error_json("Perfil inválido")
        if user_id == session["id"] and not active:
            return self.error_json("O administrador não pode desativar a própria conta")
        if user_id == session["id"] and role != "admin":
            return self.error_json("O administrador não pode remover o próprio perfil administrativo")
        target = self.db.connection().execute(
            "SELECT role,active FROM company_memberships WHERE company_id=? AND user_id=?",
            (session["company_id"], user_id)).fetchone()
        if not target:
            return self.error_json("Usuário não encontrado", 404)
        if target["role"] == "admin" and target["active"] and (not active or role != "admin"):
            active_admins = self.db.scalar(
                """SELECT COUNT(*) FROM company_memberships
                   WHERE company_id=? AND role='admin' AND active=1""", (session["company_id"],))
            if active_admins <= 1:
                return self.error_json("O sistema deve manter ao menos um administrador ativo")
        with self.db.transaction(immediate=True):
            self.db.execute(
                """UPDATE company_memberships SET role=?,active=?,updated_at=?
                   WHERE company_id=? AND user_id=?""",
                (role, active, utc_now(), session["company_id"], user_id))
            if not active:
                self.db.execute(
                    "DELETE FROM sessions WHERE user_id=? AND company_id=?",
                    (user_id, session["company_id"]),
                )
            self.db.audit(
                session["id"], "update", "user", user_id,
                {"role": role, "active": bool(active)}, company_id=session["company_id"],
            )
        return self.send_json({"ok": True})

    @staticmethod
    def normalized_text(value):
        text = unicodedata.normalize("NFD", str(value or "").lower())
        return "".join(char for char in text if unicodedata.category(char) != "Mn")

    def tender_results_get(self, query, session):
        status = (query.get("status") or [""])[0].strip()
        search = (query.get("q") or [""])[0].strip()
        sql = "SELECT * FROM tender_results WHERE company_id=?"
        params = [session["company_id"]]
        if status:
            sql += " AND status=?"
            params.append(status)
        if search:
            sql += " AND (title LIKE ? OR object_text LIKE ? OR agency LIKE ?)"
            params.extend([f"%{search}%"] * 3)
        sql += " ORDER BY CASE status WHEN 'Novo' THEN 0 WHEN 'Analisar' THEN 1 ELSE 2 END, relevance_score DESC, deadline ASC LIMIT 1000"
        rows = self.db.connection().execute(sql, params).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["matched_terms"] = json.loads(item["matched_terms"] or "[]")
            items.append(item)
        return self.send_json({"ok": True, "items": items})

    def tender_search(self, session):
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        try:
            with self.db.transaction(immediate=True):
                active = self.db.connection().execute(
                    """SELECT id,status,progress,stage FROM tender_jobs
                       WHERE company_id=? AND status IN ('queued','running')
                       ORDER BY id DESC LIMIT 1""",
                    (session["company_id"],),
                ).fetchone()
                if active:
                    return self.send_json({
                        "ok": True, "jobId": active["id"], "status": active["status"],
                        "progress": active["progress"], "stage": active["stage"],
                        "alreadyRunning": True,
                    }, 202)
                cursor = self.db.execute(
                    """INSERT INTO tender_jobs
                       (company_id,status,request_json,progress,stage,created_by,created_at)
                       VALUES(?,'queued',?,0,'Pesquisa enfileirada',?,?)""",
                    (session["company_id"], json_dumps(data), session["id"], utc_now()),
                )
                job_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            active = self.db.connection().execute(
                """SELECT id,status,progress,stage FROM tender_jobs
                   WHERE company_id=? AND status IN ('queued','running') ORDER BY id DESC LIMIT 1""",
                (session["company_id"],),
            ).fetchone()
            if active:
                return self.send_json({"ok": True, "jobId": active["id"],
                                       "status": active["status"], "alreadyRunning": True}, 202)
            return self.error_json("Não foi possível enfileirar a pesquisa", 409, "job_conflict")
        worker = threading.Thread(
            target=self.server.run_tender_job,
            args=(self, job_id, dict(session), data),
            name=f"sivs-tender-{job_id}", daemon=True,
        )
        worker.start()
        return self.send_json({"ok": True, "jobId": job_id, "status": "queued"}, 202)

    def tender_job_get(self, job_id, session):
        row = self.db.connection().execute(
            """SELECT id,status,progress,stage,result_json,error_detail,
                      created_at,started_at,heartbeat_at,finished_at
               FROM tender_jobs WHERE id=? AND company_id=?""",
            (job_id, session["company_id"]),
        ).fetchone()
        if not row:
            return self.error_json("Pesquisa não encontrada", 404)
        item = dict(row)
        try:
            item["result"] = json_loads_strict(item.pop("result_json")) if item["result_json"] else None
        except (ValueError, json.JSONDecodeError):
            item["result"] = None
        return self.send_json({"ok": True, "job": item})

    def _run_tender_job(self, job_id, session, data):
        now = utc_now()
        self.db.execute(
            """UPDATE tender_jobs SET status='running',progress=2,stage='Conectando às fontes oficiais',
               started_at=?,heartbeat_at=? WHERE id=? AND status='queued'""",
            (now, now, job_id),
        )

        def progress(percent, stage):
            self.db.execute(
                """UPDATE tender_jobs SET progress=?,stage=?,heartbeat_at=?
                   WHERE id=? AND status='running'""",
                (max(0, min(int(percent), 99)), str(stage)[:240], utc_now(), job_id),
            )

        try:
            result = self.execute_tender_search(session, data, progress)
            finished = utc_now()
            self.db.execute(
                """UPDATE tender_jobs SET status='completed',progress=100,stage='Pesquisa concluída',
                   result_json=?,heartbeat_at=?,finished_at=? WHERE id=?""",
                (json_dumps(result), finished, finished, job_id),
            )
            job = self.db.connection().execute(
                "SELECT schedule_id FROM tender_jobs WHERE id=?", (job_id,)
            ).fetchone()
            if job and job["schedule_id"]:
                self.db.execute(
                    "UPDATE search_schedules SET last_run_at=?,updated_at=? WHERE id=?",
                    (finished, finished, job["schedule_id"]),
                )
        except Exception as exc:
            reference = secrets.token_hex(6)
            print(f"[ERRO PESQUISA {reference}] job={job_id}")
            traceback.print_exc()
            finished = utc_now()
            self.db.execute(
                """UPDATE tender_jobs SET status='failed',stage='Pesquisa não concluída',
                   error_detail=?,heartbeat_at=?,finished_at=? WHERE id=?""",
                (f"Falha interna; referência {reference}", finished, finished, job_id),
            )

    def execute_tender_search(self, session, data, progress=None):
        progress = progress or (lambda _percent, _stage: None)
        progress(5, "Validando parâmetros da pesquisa")
        raw_keywords = data.get("keywords") or DEFAULT_TENDER_KEYWORDS
        company_id = session["company_id"]
        if isinstance(raw_keywords, str):
            keywords = [item.strip() for item in raw_keywords.replace("\n", ",").split(",") if item.strip()]
        elif isinstance(raw_keywords, list):
            keywords = [str(item).strip() for item in raw_keywords if str(item).strip()]
        else:
            return self.error_json("Palavras-chave inválidas")
        keywords = keywords[:80]
        if not keywords:
            return self.error_json("Informe ao menos uma palavra-chave")
        uf = str(data.get("uf", "")).strip().upper()[:2]
        try:
            days = max(1, min(int(data.get("days", 7)), 30))
            modalities = data.get("modalities") or [4, 5, 6, 7, 8, 9, 12]
            modalities = [int(value) for value in modalities
                          if int(value) in {4, 5, 6, 7, 8, 9, 12}]
        except (ValueError, TypeError):
            return self.error_json("Período ou modalidade inválida")
        if not modalities:
            modalities = [4, 5, 6, 7, 8, 9, 12]
        end = datetime.now().date()
        start = end - timedelta(days=days)
        found = 0
        inserted = 0
        errors = []
        successful_pages = 0
        normalized_keywords = [(keyword, self.normalized_text(keyword)) for keyword in keywords]
        normalized_context = [(term, self.normalized_text(term)) for term in SECCOL_CONTEXT_TERMS]
        source_status = {"pncp": "indisponível", "comprasgov": "não acionado"}
        sources_used = ["pncp"]
        planned_pages = 0
        completed_jobs = 0

        def store_item(item, retrieved_via):
            nonlocal found, inserted
            haystack = self.normalized_text(f"{item.get('objetoCompra','')} {item.get('informacaoComplementar','')}")
            matched = [original for original, normalized in normalized_keywords if normalized and normalized in haystack]
            if not matched:
                return
            context_hits = [original for original, normalized in normalized_context if normalized in haystack]
            external_id = str(item.get("numeroControlePNCP") or "").strip()
            if not external_id:
                return
            found += 1
            agency_data = item.get("orgaoEntidade") or {}
            unit_data = item.get("unidadeOrgao") or {}
            agency = (agency_data.get("razaoSocial") or item.get("orgaoEntidadeRazaoSocial") or
                      item.get("nomeOrgao") or "Órgão não informado")
            item_uf = unit_data.get("ufSigla") or item.get("unidadeOrgaoUfSigla") or uf or None
            municipality = unit_data.get("municipioNome") or item.get("unidadeOrgaoMunicipioNome")
            modality_name = item.get("modalidadeNome") or "Contratação"
            object_text = str(item.get("objetoCompra") or "").strip()
            title = f"{modality_name} — {agency}"
            source_url = item.get("linkSistemaOrigem") or self.pncp_public_url(external_id)
            deadline = item.get("dataEncerramentoProposta") or item.get("dataEncerramentoPropostaPncp")
            raw_item = dict(item)
            raw_item["_recuperado_via"] = retrieved_via
            now = utc_now()
            stored_source_key = "pncp" if company_id == 1 else f"{company_id}:pncp"
            cursor = self.db.execute(
                """INSERT OR IGNORE INTO tender_results
                   (source_key,external_id,title,object_text,agency,uf,municipality,modality,estimated_value,
                    published_at,deadline,source_url,matched_terms,relevance_score,status,raw_json,created_at,updated_at,
                    company_id)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (stored_source_key, external_id, title[:500], object_text, agency, item_uf, municipality, modality_name,
                 item.get("valorTotalEstimado"), item.get("dataPublicacaoPncp"), deadline, source_url,
                 json_dumps(matched), min(100, 40 + len(matched) * 12 + min(4, len(context_hits)) * 4), "Novo",
                 json_dumps(raw_item), now, now, company_id),
            )
            inserted += cursor.rowcount

        def fetch_json(job, timeout=14):
            _modality, _page, url = job
            return self.fetch_tender_json(url, timeout=timeout)

        # Primeiro testa uma página de cada modalidade. Só amplia a paginação se a fonte responder.
        first_jobs = []
        for modality in modalities:
            params = {"dataInicial": start.strftime("%Y%m%d"), "dataFinal": end.strftime("%Y%m%d"),
                      "codigoModalidadeContratacao": modality, "pagina": 1, "tamanhoPagina": 50}
            if uf:
                params["uf"] = uf
            first_jobs.append((modality, 1, "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?" +
                               urllib.parse.urlencode(params)))
        planned_pages += len(first_jobs)
        progress(10, "Consultando primeiras páginas do PNCP")
        pncp_payloads = []
        # O PNCP limita rajadas. A execução paralela anterior provocava HTTP
        # 429 em parte das páginas e, mesmo assim, apresentava sucesso total.
        for job in first_jobs:
            try:
                payload = fetch_json(job)
                pncp_payloads.append((job, payload))
                successful_pages += 1
                for item in payload.get("data", []):
                    store_item(item, "PNCP")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                errors.append(f"PNCP modalidade {job[0]}, página 1: {exc}")
            completed_jobs += 1
            progress(10 + int(35 * completed_jobs / max(1, planned_pages)),
                     f"PNCP: {completed_jobs}/{planned_pages} consulta(s) processadas")

        if pncp_payloads:
            followups = []
            for (modality, _page, _url), payload in pncp_payloads:
                remaining = min(3 if modality in {4, 6, 8} else 1, int(payload.get("paginasRestantes", 0) or 0))
                for page in range(2, remaining + 2):
                    params = {"dataInicial": start.strftime("%Y%m%d"), "dataFinal": end.strftime("%Y%m%d"),
                              "codigoModalidadeContratacao": modality, "pagina": page, "tamanhoPagina": 50}
                    if uf:
                        params["uf"] = uf
                    followups.append((modality, page, "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?" +
                                      urllib.parse.urlencode(params)))
            # O serviço recusa rajadas a partir de aproximadamente dez
            # chamadas. Reservamos uma chamada da cota e priorizamos as
            # primeiras páginas de todas as modalidades antes de aprofundar.
            remaining_budget = max(0, PNCP_MAX_REQUESTS_PER_SEARCH - len(first_jobs))
            followups = followups[:remaining_budget]
            planned_pages += len(followups)
            progress(48, "Ampliando a paginação das modalidades aderentes")
            for job in followups:
                try:
                    payload = fetch_json(job)
                    successful_pages += 1
                    for item in payload.get("data", []):
                        store_item(item, "PNCP")
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                    errors.append(f"PNCP modalidade {job[0]}, página {job[1]}: {exc}")
                completed_jobs += 1
                progress(45 + int(35 * completed_jobs / max(1, planned_pages)),
                         f"PNCP: {completed_jobs}/{planned_pages} consulta(s) processadas")
            source_status["pncp"] = "concluído" if successful_pages == planned_pages else "parcial"
        else:
            # Fallback oficial: API de Dados Abertos do Compras.gov.br.
            sources_used.append("comprasgov")
            source_status["comprasgov"] = "consultando"
            modality_map = {4: 3, 6: 5, 8: 6, 9: 7}
            fallback_jobs = []
            for pncp_modality in modalities:
                compras_modality = modality_map.get(pncp_modality)
                if not compras_modality:
                    continue
                params = {"pagina": 1, "tamanhoPagina": 100,
                          "dataPublicacaoPncpInicial": start.isoformat(), "dataPublicacaoPncpFinal": end.isoformat(),
                          "codigoModalidade": compras_modality}
                if uf:
                    params["unidadeOrgaoUfSigla"] = uf
                url = ("https://dadosabertos.compras.gov.br/modulo-contratacoes/"
                       "1_consultarContratacoes_PNCP_14133?" + urllib.parse.urlencode(params))
                fallback_jobs.append((pncp_modality, 1, url))
            planned_pages += len(fallback_jobs)
            progress(48, "PNCP indisponível; acionando contingência Compras.gov.br")
            fallback_success = 0
            for job in fallback_jobs:
                try:
                    payload = fetch_json(job, 20)
                    fallback_success += 1
                    successful_pages += 1
                    for item in payload.get("resultado", []):
                        store_item(item, "Compras.gov.br")
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
                    errors.append(f"Compras.gov modalidade {job[0]}: {exc}")
                completed_jobs += 1
                progress(50 + int(30 * completed_jobs / max(1, planned_pages)),
                         f"Compras.gov.br: {completed_jobs}/{planned_pages} consulta(s) processadas")
            source_status["comprasgov"] = (
                "concluído" if fallback_success == len(fallback_jobs)
                else "parcial" if fallback_success else "indisponível"
            )
        progress(86, "Consolidando, deduplicando e registrando resultados")
        self.db.execute(
            """INSERT INTO tender_searches
               (keywords,uf,days,sources_searched,found_count,new_count,error_detail,created_by,created_at,company_id)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (json_dumps(keywords), uf or None, days, json_dumps(sources_used), found, inserted,
             "\n".join(errors) if errors else None, session["id"], utc_now(), company_id),
        )
        execution_time = utc_now()
        for source_key in ("pncp", "comprasgov"):
            source_state = source_status[source_key]
            succeeded = source_state == "concluído"
            self.db.execute(
                """UPDATE records SET
                     payload=json_set(payload,'$.ultima_execucao',?,'$.ultimo_sucesso',
                                      CASE WHEN ? THEN ? ELSE json_extract(payload,'$.ultimo_sucesso') END,
                                      '$.ultimo_estado',?),updated_at=?
                   WHERE company_id=? AND module='fontes'
                     AND json_extract(payload,'$.source_key')=?""",
                (execution_time, 1 if succeeded else 0, execution_time, source_state,
                 execution_time, company_id, source_key))
        self.db.audit(session["id"], "search", "tenders",
                      detail={"found": found, "new": inserted, "uf": uf, "days": days}, company_id=company_id)
        if successful_pages == 0:
            message = "PNCP e Compras.gov.br não responderam. Nenhum resultado foi descartado; tente novamente."
        elif source_status["pncp"] == "indisponível":
            message = (f"PNCP indisponível; fallback oficial do Compras.gov.br concluído: "
                       f"{found} oportunidade(s) aderente(s), {inserted} nova(s).")
        elif source_status["pncp"] == "parcial":
            message = (f"Pesquisa parcial no PNCP: {successful_pages}/{planned_pages} consulta(s) responderam, "
                       f"com {found} oportunidade(s) aderente(s) e {inserted} nova(s). "
                       "Tente novamente para completar.")
        else:
            message = f"Pesquisa concluída: {found} oportunidade(s) aderente(s), {inserted} nova(s)."
        progress(97, "Atualizando fontes, histórico e trilha de auditoria")
        return {"ok": True, "found": found, "new": inserted, "errors": errors,
                "pagesChecked": successful_pages, "pagesPlanned": planned_pages,
                "sourceStatus": source_status, "message": message}

    @staticmethod
    def fetch_tender_json(url, timeout=14, attempts=4):
        """Consulta uma fonte oficial e repete somente falhas transitórias."""
        transient_statuses = {429, 500, 502, 503, 504}
        for attempt in range(attempts):
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": f"SIVS/{VERSION}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    if response.status == 204:
                        return {}
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code not in transient_statuses or attempt + 1 >= attempts:
                    raise
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = float(retry_after)
                except (TypeError, ValueError):
                    delay = 1.5 * (2 ** attempt)
                time.sleep(max(0.5, min(delay, 12)))
            except TimeoutError:
                # Um segundo timeout já indica indisponibilidade daquela
                # página; quatro tentativas podiam reter o job por um minuto.
                if attempt >= 1 or attempt + 1 >= attempts:
                    raise
                time.sleep(0.75)
            except urllib.error.URLError:
                if attempt + 1 >= attempts:
                    raise
                time.sleep(min(1.5 * (2 ** attempt), 12))
        raise RuntimeError("Fonte oficial não respondeu")

    @staticmethod
    def pncp_public_url(external_id):
        try:
            left, year = external_id.split("/")
            cnpj, marker, sequence = left.split("-")
            return f"https://pncp.gov.br/app/editais/{cnpj}/{year}/{int(sequence)}"
        except (ValueError, TypeError):
            return "https://pncp.gov.br/app/editais"

    def tender_result_update(self, path, session):
        pieces = path.split("/")
        if len(pieces) != 5 or not pieces[4].isdigit():
            return self.error_json("Oportunidade inválida", 404)
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        status = str(data.get("status", "Analisar"))
        if status not in {"Novo", "Analisar", "Aprovado", "Descartado", "Convertido"}:
            return self.error_json("Situação inválida")
        result_id = int(pieces[4])
        cursor = self.db.execute(
            "UPDATE tender_results SET status=?,updated_at=? WHERE id=? AND company_id=?",
            (status, utc_now(), result_id, session["company_id"]))
        if not cursor.rowcount:
            return self.error_json("Oportunidade não encontrada", 404)
        self.db.audit(session["id"], "triage", "tender_result", result_id, {"status": status},
                      company_id=session["company_id"])
        return self.send_json({"ok": True})

    def tender_convert(self, path, session):
        pieces = path.split("/")
        if len(pieces) != 5 or not pieces[4].isdigit():
            return self.error_json("Oportunidade inválida", 404)
        result_id = int(pieces[4])
        row = self.db.connection().execute(
            "SELECT * FROM tender_results WHERE id=? AND company_id=?",
            (result_id, session["company_id"])).fetchone()
        if not row:
            return self.error_json("Oportunidade não encontrada", 404)
        if row["converted_record_id"]:
            return self.send_json({"ok": True, "recordId": row["converted_record_id"], "alreadyConverted": True})
        now = utc_now()
        opening_date = str(row["deadline"] or row["published_at"] or datetime.now().date().isoformat())[:10]
        record_payload = {
            "orgao": row["agency"], "edital": row["external_id"], "portal": row["source_url"],
            "modalidade": row["modality"], "data_abertura": opening_date,
            "fonte_resultado_id": row["id"], "notes": row["object_text"], "etapa": "Captação",
            "assunto": row["title"], "relacionamentos": []
        }
        try:
            values = self.normalized_record({
                "module": "licitacoes", "title": row["title"], "status": "Captação",
                "amount": row["estimated_value"], "due_date": opening_date,
                "payload": record_payload,
            })
        except ValueError as exc:
            return self.error_json(f"A oportunidade não possui dados suficientes para conversão: {exc}")
        with self.db.transaction(immediate=True):
            current = self.db.connection().execute(
                "SELECT converted_record_id FROM tender_results WHERE id=? AND company_id=?",
                (result_id, session["company_id"]),
            ).fetchone()
            if current and current["converted_record_id"]:
                return self.send_json({"ok": True, "recordId": current["converted_record_id"],
                                       "alreadyConverted": True})
            cursor = self.db.execute(
                """INSERT INTO records
                   (module,title,status,amount,due_date,payload,created_by,created_at,updated_at,
                    company_id,revision)
                   VALUES(?,?,?,?,?,?,?,?,?,?,1)""",
                (*values, session["id"], now, now, session["company_id"]),
            )
            record_id = cursor.lastrowid
            self.db.sync_relationships(
                record_id, record_payload, session["id"], session["company_id"]
            )
            updated = self.db.execute(
                """UPDATE tender_results SET status='Convertido',converted_record_id=?,updated_at=?
                   WHERE id=? AND company_id=? AND converted_record_id IS NULL""",
                (record_id, now, result_id, session["company_id"]),
            )
            if updated.rowcount != 1:
                raise sqlite3.IntegrityError("conversão concorrente")
            self.db.audit(
                session["id"], "convert", "tender_result", result_id,
                {"record_id": record_id}, company_id=session["company_id"],
            )
        return self.send_json({"ok": True, "recordId": record_id})

    def search_schedule_save(self, session):
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        name = str(data.get("name") or "Monitor diário de editais").strip()[:180]
        keywords = data.get("keywords") or DEFAULT_TENDER_KEYWORDS
        if isinstance(keywords, str):
            keywords = [item.strip() for item in keywords.replace("\n", ",").split(",") if item.strip()]
        if not isinstance(keywords, list) or not keywords:
            return self.error_json("Informe as palavras-chave do monitor")
        frequency = str(data.get("frequency") or "daily")
        if frequency not in {"manual", "daily", "weekly"}:
            return self.error_json("Frequência inválida")
        try:
            days = max(1, min(int(data.get("days") or 7), 30))
        except (ValueError, TypeError):
            return self.error_json("Período inválido")
        now = utc_now()
        next_run = None
        if frequency == "daily":
            next_run = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
        elif frequency == "weekly":
            next_run = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(timespec="seconds")
        cursor = self.db.execute(
            """INSERT INTO search_schedules
               (company_id,name,keywords,uf,days,frequency,active,next_run_at,created_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (session["company_id"], name, json_dumps(keywords[:100]),
             str(data.get("uf") or "").upper()[:2] or None,
             days, frequency,
             1 if data.get("active", True) else 0, next_run, session["id"], now, now))
        self.db.audit(session["id"], "create", "search_schedule", cursor.lastrowid,
                      {"frequency": frequency}, company_id=session["company_id"])
        return self.send_json({"ok": True, "id": cursor.lastrowid}, 201)

    def attachment_upload(self, path, session):
        parts = path.split("/")
        if len(parts) != 5 or not parts[3].isdigit():
            return self.error_json("Registro inválido", 404)
        record_id = int(parts[3])
        record = self.db.connection().execute(
            "SELECT module FROM records WHERE id=? AND company_id=? AND deleted_at IS NULL",
            (record_id, session["company_id"])).fetchone()
        if not record:
            return self.error_json("Registro não encontrado", 404)
        if not self.require_module_write(session, record["module"]):
            return
        try:
            data = self.parse_json()
            encoded = str(data.get("content") or "")
            if encoded.startswith("data:"):
                encoded = encoded.split(",", 1)[-1]
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError, binascii.Error) as exc:
            return self.error_json(f"Arquivo inválido: {exc}")
        if not content or len(content) > MAX_ATTACHMENT:
            return self.error_json("O arquivo deve possuir até 10 MB")
        filename = Path(str(data.get("filename") or "arquivo.bin")).name[:240]
        category = str(data.get("category") or "Evidência").strip()[:100]
        license_confirmed = bool(data.get("license_confirmed"))
        if category == "Cópia normativa licenciada" and not license_confirmed:
            return self.error_json(
                "Confirme que a empresa possui licença para anexar a íntegra da norma.",
                409, "license_confirmation_required",
            )
        try:
            mime_type = self.detect_attachment_mime(content, filename)
        except ValueError as exc:
            return self.error_json(str(exc))
        declared = str(data.get("mime_type") or "").split(";", 1)[0].strip().lower()
        compatible = {
            "application/zip": {
                "application/zip",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
            "text/plain": {"text/plain", "text/csv", "application/json", "application/xml", "text/xml"},
        }
        if declared and declared != "application/octet-stream" and declared != mime_type:
            if declared not in compatible.get(mime_type, set()):
                return self.error_json("O tipo declarado não corresponde ao conteúdo do arquivo")
        digest = hashlib.sha256(content).hexdigest()
        now = utc_now()
        with self.db.transaction(immediate=True):
            cursor = self.db.execute(
                """INSERT INTO attachments
                   (company_id,record_id,filename,mime_type,content,size,category,version,
                    uploaded_by,created_at,sha256,license_confirmed)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (session["company_id"], record_id, filename, mime_type, content, len(content),
                 category, str(data.get("version") or "")[:40] or None,
                 session["id"], now, digest, 1 if license_confirmed else 0),
            )
            self.db.audit(
                session["id"], "upload", "attachment", cursor.lastrowid,
                {"record_id": record_id, "filename": filename, "sha256": digest,
                 "size": len(content), "category": category},
                company_id=session["company_id"],
            )
        return self.send_json({"ok": True, "id": cursor.lastrowid, "filename": filename}, 201)

    @staticmethod
    def detect_attachment_mime(content, filename):
        extension = Path(filename).suffix.lower()
        if content.startswith(b"%PDF-"):
            return "application/pdf"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"PK\x03\x04") and extension in {".zip", ".docx", ".xlsx"}:
            return "application/zip"
        if content.startswith((b"MZ", b"\x7fELF")):
            raise ValueError("Arquivos executáveis não são permitidos")
        if extension in {".xml", ".txt", ".csv", ".json"}:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ValueError("O arquivo textual deve usar codificação UTF-8") from None
            if "\x00" in text:
                raise ValueError("Conteúdo binário incompatível com arquivo textual")
            if extension == ".json":
                try:
                    json_loads_strict(text)
                except (ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"JSON anexado é inválido: {exc}") from None
                return "application/json"
            if extension == ".xml":
                if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                    raise ValueError("XML com DTD ou entidade externa não é permitido")
                try:
                    ET.fromstring(text)
                except ET.ParseError as exc:
                    raise ValueError(f"XML anexado é inválido: {exc}") from None
                return "application/xml"
            return "text/plain"
        raise ValueError(
            "Formato não permitido. Use PDF, PNG, JPEG, ZIP/DOCX/XLSX ou texto XML/JSON/CSV/TXT."
        )

    def attachment_download(self, attachment_id, session):
        row = self.db.connection().execute(
            """SELECT a.*,r.module,r.deleted_at FROM attachments a
               JOIN records r ON r.id=a.record_id
               WHERE a.id=? AND a.company_id=?""",
            (attachment_id, session["company_id"])).fetchone()
        if not row or row["deleted_at"]:
            return self.error_json("Arquivo não encontrado", 404)
        if not self.require_module_read(session, row["module"]):
            return
        body = row["content"]
        safe_name = str(row["filename"]).replace('"', "").replace("\r", "").replace("\n", "")
        self.db.audit(
            session["id"], "download", "attachment", attachment_id,
            {"record_id": row["record_id"], "filename": safe_name, "sha256": row["sha256"]},
            company_id=session["company_id"],
        )
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", row["mime_type"] or "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-SHA256", row["sha256"] or hashlib.sha256(body).hexdigest())
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def approval_create(self, path, session):
        parts = path.split("/")
        if len(parts) != 5 or not parts[3].isdigit():
            return self.error_json("Registro inválido", 404)
        record_id = int(parts[3])
        record = self.db.connection().execute(
            """SELECT module,title,revision FROM records
               WHERE id=? AND company_id=? AND deleted_at IS NULL""",
            (record_id, session["company_id"])).fetchone()
        if not record:
            return self.error_json("Registro não encontrado", 404)
        if not self.require_module_write(session, record["module"]):
            return
        try:
            data = self.parse_json()
            requested_to = int(data.get("requested_to")) if data.get("requested_to") else None
        except (ValueError, TypeError):
            return self.error_json("Aprovador inválido")
        approval_type = str(data.get("approval_type") or "Aprovação").strip()[:100]
        request_comment = str(data.get("comment") or "").strip()[:1000] or None
        if not approval_type:
            return self.error_json("Informe o tipo de aprovação")
        if requested_to == session["id"]:
            return self.error_json(
                "Solicitante e aprovador devem ser pessoas diferentes", 409, "segregation_required"
            )
        if requested_to:
            membership = self.db.connection().execute(
                """SELECT role FROM company_memberships
                   WHERE company_id=? AND user_id=? AND active=1""",
                (session["company_id"], requested_to),
            ).fetchone()
            if not membership or membership["role"] not in {"admin", "manager", "approver"}:
                return self.error_json("Selecione um aprovador ativo com perfil habilitado")
        else:
            membership = self.db.connection().execute(
                """SELECT user_id FROM company_memberships
                   WHERE company_id=? AND user_id<>? AND active=1
                     AND role IN ('approver','manager','admin')
                   ORDER BY CASE role WHEN 'approver' THEN 0 WHEN 'manager' THEN 1 ELSE 2 END,user_id
                   LIMIT 1""",
                (session["company_id"], session["id"]),
            ).fetchone()
            requested_to = membership["user_id"] if membership else None
        if not requested_to:
            return self.error_json(
                "Cadastre outro usuário como aprovador, gestor ou administrador antes de solicitar.",
                409, "approver_unavailable",
            )
        now = utc_now()
        try:
            with self.db.transaction(immediate=True):
                current = self.db.connection().execute(
                    """SELECT title,revision FROM records
                       WHERE id=? AND company_id=? AND deleted_at IS NULL""",
                    (record_id, session["company_id"]),
                ).fetchone()
                if not current:
                    return self.error_json("Registro não encontrado", 404)
                cursor = self.db.execute(
                    """INSERT INTO approvals
                       (company_id,record_id,approval_type,status,requested_to,requested_by,
                        record_revision,comment,request_comment,requested_at)
                       VALUES(?,?,?,'Pendente',?,?,?,?,?,?)""",
                    (session["company_id"], record_id, approval_type, requested_to,
                     session["id"], current["revision"], request_comment, request_comment, now),
                )
                approval_id = cursor.lastrowid
                self.db.execute(
                    """INSERT INTO notifications
                       (company_id,user_id,title,message,record_id,level,created_at)
                       VALUES(?,?,?,?,?,'warning',?)""",
                    (session["company_id"], requested_to, "Aprovação pendente",
                     f'{current["title"]} aguarda sua análise.', record_id, now),
                )
                self.db.audit(
                    session["id"], "request", "approval", approval_id,
                    {"record_id": record_id, "record_revision": current["revision"],
                     "requested_to": requested_to}, company_id=session["company_id"],
                )
        except sqlite3.IntegrityError:
            return self.error_json(
                "Já existe uma solicitação pendente deste tipo para o registro.",
                409, "approval_already_pending",
            )
        return self.send_json({"ok": True, "id": approval_id, "requestedTo": requested_to}, 201)

    def approval_decide(self, path, session):
        parts = path.split("/")
        if len(parts) != 4 or not parts[3].isdigit():
            return self.error_json("Aprovação inválida", 404)
        approval_id = int(parts[3])
        approval = self.db.connection().execute(
            """SELECT a.*,r.module,r.title,r.revision current_revision,r.deleted_at
               FROM approvals a JOIN records r ON r.id=a.record_id
               WHERE a.id=? AND a.company_id=? AND a.status='Pendente'""",
            (approval_id, session["company_id"])).fetchone()
        if not approval:
            return self.error_json("Aprovação pendente não encontrada", 404)
        if approval["requested_to"] != session["id"]:
            if not self.require_module_read(session, approval["module"]):
                return
        if approval["requested_by"] == session["id"]:
            return self.error_json(
                "Quem solicitou não pode decidir a própria aprovação.",
                409, "segregation_required",
            )
        if approval["requested_to"] != session["id"] and session["role"] not in {"admin", "manager"}:
            return self.error_json("A aprovação pertence a outro responsável", 403, "forbidden")
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        status = str(data.get("status") or "")
        if status not in {"Aprovado", "Rejeitado"}:
            return self.error_json("Decisão inválida")
        decision_comment = str(data.get("comment") or "").strip()[:1000] or None
        if status == "Rejeitado" and not decision_comment:
            return self.error_json("Informe o motivo da rejeição")
        now = utc_now()
        stale = bool(
            approval["deleted_at"] or approval["record_revision"] != approval["current_revision"]
        )
        with self.db.transaction(immediate=True):
            if stale:
                self.db.execute(
                    """UPDATE approvals SET status='Expirada',decided_at=?,
                       decision_comment='O registro mudou após a solicitação.'
                       WHERE id=? AND company_id=? AND status='Pendente'""",
                    (now, approval_id, session["company_id"]),
                )
                self.db.audit(
                    session["id"], "expire", "approval", approval_id,
                    {"requested_revision": approval["record_revision"],
                     "current_revision": approval["current_revision"]},
                    company_id=session["company_id"],
                )
            else:
                updated = self.db.execute(
                    """UPDATE approvals
                       SET status=?,decided_by=?,decision_comment=?,decided_at=?
                       WHERE id=? AND company_id=? AND status='Pendente'""",
                    (status, session["id"], decision_comment, now,
                     approval_id, session["company_id"]),
                )
                if updated.rowcount != 1:
                    return self.error_json(
                        "Esta aprovação já foi decidida por outra pessoa.", 409, "approval_conflict"
                    )
                self.db.execute(
                    """INSERT INTO notifications
                       (company_id,user_id,title,message,record_id,level,created_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (session["company_id"], approval["requested_by"],
                     f"Solicitação {status.lower()}",
                     f'{approval["title"]}: {status}.', approval["record_id"],
                     "success" if status == "Aprovado" else "warning", now),
                )
                self.db.audit(
                    session["id"], "decide", "approval", approval_id,
                    {"status": status, "record_revision": approval["record_revision"]},
                    company_id=session["company_id"],
                )
        if stale:
            return self.error_json(
                "A solicitação expirou porque o registro foi alterado. Gere uma nova aprovação.",
                409, "approval_stale",
            )
        return self.send_json({"ok": True, "status": status})

    def technical_report_context(self, record_id, session, require_final=False):
        row = self.db.connection().execute(
            """SELECT * FROM records
               WHERE id=? AND company_id=? AND deleted_at IS NULL
                 AND module IN ('certificados','laudos_tecnicos','estudos_tecnicos')""",
            (record_id, session["company_id"]),
        ).fetchone()
        if not row:
            raise LookupError("Documento técnico não encontrado")
        if not self.require_module_read(session, row["module"]):
            return None
        norms = self.db.connection().execute(
            """SELECT n.id,n.title,n.status,n.payload,
                      SUM(CASE WHEN a.category='Cópia normativa licenciada'
                               AND a.license_confirmed=1 THEN 1 ELSE 0 END) licensed_copies,
                      COUNT(a.id) attachment_count
               FROM record_relationships rr JOIN records n ON n.id=rr.to_record_id
               LEFT JOIN attachments a ON a.record_id=n.id AND a.company_id=n.company_id
               WHERE rr.from_record_id=? AND n.company_id=? AND n.module='normas_tecnicas'
                 AND n.deleted_at IS NULL
               GROUP BY n.id ORDER BY n.title""",
            (record_id, session["company_id"]),
        ).fetchall()
        if not norms:
            raise ValueError("O documento não possui base normativa vinculada")
        parsed_norms = []
        for norm in norms:
            item = dict(norm)
            item["payload"] = json_loads_strict(item["payload"] or "{}")
            parsed_norms.append(item)
        if require_final:
            invalid = [norm["title"] for norm in parsed_norms
                       if norm["status"] in {"Obsoleta", "Cancelada"}]
            missing_licensed = [norm["title"] for norm in parsed_norms
                                if "Comercial" in str(norm["payload"].get("licenciamento") or "")
                                and not norm["licensed_copies"]]
            if invalid:
                raise ValueError(
                    "Base normativa obsoleta/cancelada: " + ", ".join(invalid[:5])
                )
            if missing_licensed:
                raise ValueError(
                    "Anexe e confirme a cópia licenciada antes da emissão final: " +
                    ", ".join(missing_licensed[:5])
                )
            approved = self.db.connection().execute(
                """SELECT id,decided_by,decided_at FROM approvals
                   WHERE company_id=? AND record_id=? AND status='Aprovado'
                     AND record_revision=? ORDER BY decided_at DESC,id DESC LIMIT 1""",
                (session["company_id"], record_id, row["revision"]),
            ).fetchone()
            if not approved:
                raise ValueError(
                    "A emissão final exige aprovação válida para a revisão atual do documento"
                )
        else:
            approved = None
        company = self.db.connection().execute(
            "SELECT name,cnpj,phone,email,address FROM companies WHERE id=?",
            (session["company_id"],),
        ).fetchone()
        return row, parsed_norms, approved, dict(company or {})

    @staticmethod
    def build_technical_report_pdf(record, norms, company, final=False, approval=None):
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
            )
        except ImportError as exc:
            raise RuntimeError(
                "O gerador PDF não está instalado. Execute: pip install reportlab"
            ) from exc

        payload = json_loads_strict(record["payload"] or "{}")
        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
            topMargin=20 * mm, bottomMargin=18 * mm,
            title=record["title"], author=company.get("name") or "SECCOL",
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="SIVSTitle", parent=styles["Title"], fontName="Helvetica-Bold",
            fontSize=17, leading=21, textColor=colors.HexColor("#171717"), spaceAfter=6,
        ))
        styles.add(ParagraphStyle(
            name="SIVSSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
            fontSize=10, leading=13, textColor=colors.HexColor("#A84718"),
            spaceBefore=10, spaceAfter=6, uppercase=True,
        ))
        styles.add(ParagraphStyle(
            name="SIVSSmall", parent=styles["BodyText"], fontSize=7.5, leading=10,
            textColor=colors.HexColor("#666666"),
        ))
        styles.add(ParagraphStyle(
            name="SIVSRight", parent=styles["SIVSSmall"], alignment=TA_RIGHT,
        ))
        styles.add(ParagraphStyle(
            name="SIVSCenter", parent=styles["BodyText"], alignment=TA_CENTER,
            fontSize=8, leading=11,
        ))

        module_titles = {
            "certificados": "CERTIFICADO TÉCNICO",
            "laudos_tecnicos": "LAUDO TÉCNICO",
            "estudos_tecnicos": "ESTUDO TÉCNICO",
        }
        code = payload.get("numero") or f"SIVS-{record['id']}"
        story = [
            Table([
                [Paragraph(f"<b>{html.escape(company.get('name') or 'SECCOL')}</b><br/>"
                           f"<font size='7'>{html.escape(company.get('cnpj') or 'CNPJ não informado')}</font>",
                           styles["BodyText"]),
                 Paragraph(f"<b>{module_titles[record['module']]}</b><br/>"
                           f"{html.escape(str(code))} · revisão {record['revision']}", styles["SIVSRight"])],
            ], colWidths=[105 * mm, 51 * mm], style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor("#C85D23")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ])),
            Spacer(1, 8),
            Paragraph(html.escape(record["title"]), styles["SIVSTitle"]),
            Paragraph(
                "EMISSÃO CONTROLADA" if final else "PRÉVIA — NÃO ASSINAR NEM UTILIZAR COMO DOCUMENTO FINAL",
                ParagraphStyle("State", parent=styles["SIVSCenter"], fontName="Helvetica-Bold",
                               textColor=colors.HexColor("#167A74" if final else "#B42318"),
                               backColor=colors.HexColor("#E8F5F2" if final else "#FDECEC"),
                               borderPadding=6, spaceAfter=10),
            ),
        ]

        core_fields = {
            "Cliente": payload.get("cliente") or payload.get("contato"),
            "Ordem de serviço": payload.get("os"),
            "Local avaliado": payload.get("local_avaliado"),
            "Equipamento": payload.get("equipamento"),
            "Objeto": payload.get("objeto"),
            "Responsável técnico": payload.get("responsavel_tecnico") or payload.get("aprovador"),
            "Data de emissão": payload.get("data_emissao"),
            "Assunto controlado": payload.get("assunto"),
        }
        rows = [[Paragraph(f"<b>{html.escape(label)}</b>", styles["SIVSSmall"]),
                 Paragraph(html.escape(str(value)), styles["BodyText"])]
                for label, value in core_fields.items() if value]
        story.extend([
            Paragraph("IDENTIFICAÇÃO E RASTREABILIDADE", styles["SIVSSection"]),
            Table(rows, colWidths=[45 * mm, 111 * mm], style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DDDDDD")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F6F7")),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])),
        ])

        narrative_fields = [
            ("OBJETO E PREMISSAS", payload.get("premissas") or payload.get("notes")),
            ("MÉTODO / METODOLOGIA", payload.get("metodo") or payload.get("metodologia")),
            ("REGRA DE DECISÃO", payload.get("regra_decisao")),
            ("CONCLUSÃO TÉCNICA", payload.get("conclusao")),
            ("RECOMENDAÇÕES", payload.get("recomendacoes")),
        ]
        for label, value in narrative_fields:
            if value:
                paragraphs = [Paragraph(html.escape(part), styles["BodyText"])
                              for part in str(value).splitlines() if part.strip()]
                story.append(KeepTogether([Paragraph(label, styles["SIVSSection"]), *paragraphs]))

        story.extend([Paragraph("BASE NORMATIVA CONTROLADA", styles["SIVSSection"])])
        norm_rows = [[Paragraph("Referência / edição", styles["SIVSSmall"]),
                      Paragraph("Aplicabilidade registrada", styles["SIVSSmall"])]]
        for norm in norms:
            norm_payload = norm["payload"]
            norm_rows.append([
                Paragraph(f"<b>{html.escape(norm['title'])}</b><br/>"
                          f"{html.escape(str(norm_payload.get('edicao') or 'Edição não informada'))} · "
                          f"{html.escape(norm['status'])}", styles["SIVSSmall"]),
                Paragraph(html.escape(str(norm_payload.get("aplicabilidade_seccol") or
                                          norm_payload.get("escopo_resumido") or "—")), styles["SIVSSmall"]),
            ])
        story.extend([
            Table(norm_rows, repeatRows=1, colWidths=[62 * mm, 94 * mm], style=TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D8D8D8")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#171717")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])),
            Spacer(1, 8),
            Paragraph(
                "As fichas e citações acima não substituem a íntegra licenciada. A execução e a assinatura "
                "devem observar edição, emendas, escopo contratado, método aprovado, rastreabilidade e "
                "competência do responsável técnico.", styles["SIVSSmall"],
            ),
            Paragraph("RESPONSABILIDADE E APROVAÇÃO", styles["SIVSSection"]),
            Paragraph(
                f"Responsável técnico: {html.escape(str(payload.get('responsavel_tecnico') or payload.get('aprovador') or 'A definir'))}<br/>"
                f"Aprovação eletrônica SIVS: {html.escape(str(approval['id'])) if approval else 'não aplicável à prévia'}<br/>"
                f"Revisão de dados: {record['revision']} · registro SIVS #{record['id']}", styles["BodyText"],
            ),
        ])

        def page_footer(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(colors.HexColor("#DDDDDD"))
            canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#666666"))
            canvas.drawString(18 * mm, 8.5 * mm, f"SIVS 2.2 · registro #{record['id']} · revisão {record['revision']}")
            canvas.drawRightString(192 * mm, 8.5 * mm, f"Página {doc.page}")
            if not final:
                canvas.setFont("Helvetica-Bold", 34)
                canvas.setFillColor(colors.Color(0.75, 0.1, 0.05, alpha=0.09))
                canvas.translate(105 * mm, 145 * mm)
                canvas.rotate(35)
                canvas.drawCentredString(0, 0, "PRÉVIA — NÃO CONTROLADA")
            canvas.restoreState()

        document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
        return buffer.getvalue()

    def technical_report_preview(self, record_id, session):
        try:
            context = self.technical_report_context(record_id, session, require_final=False)
            if context is None:
                return
            record, norms, approval, company = context
            body = self.build_technical_report_pdf(record, norms, company, final=False, approval=approval)
        except LookupError as exc:
            return self.error_json(str(exc), 404)
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            return self.error_json(str(exc))
        self.db.audit(
            session["id"], "preview", record["module"], record_id,
            {"revision": record["revision"], "norms": [norm["id"] for norm in norms]},
            company_id=session["company_id"],
        )
        filename = f"previa-{record['module']}-{record_id}-r{record['revision']}.pdf"
        return self.send_pdf(body, filename)

    def technical_report_issue(self, record_id, session):
        try:
            context = self.technical_report_context(record_id, session, require_final=True)
            if context is None:
                return
            record, norms, approval, company = context
            if not self.require_module_write(session, record["module"]):
                return
            body = self.build_technical_report_pdf(record, norms, company, final=True, approval=approval)
        except LookupError as exc:
            return self.error_json(str(exc), 404)
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            return self.error_json(str(exc), 409, "issuance_blocked")
        digest = hashlib.sha256(body).hexdigest()
        version = f"r{record['revision']}"
        filename = f"{record['module']}-{record_id}-{version}.pdf"
        now = utc_now()
        with self.db.transaction(immediate=True):
            existing = self.db.connection().execute(
                """SELECT id FROM attachments WHERE company_id=? AND record_id=?
                   AND category='Documento técnico emitido' AND version=? AND sha256=?""",
                (session["company_id"], record_id, version, digest),
            ).fetchone()
            if existing:
                attachment_id = existing["id"]
            else:
                cursor = self.db.execute(
                    """INSERT INTO attachments
                       (company_id,record_id,filename,mime_type,content,size,category,version,
                        uploaded_by,created_at,sha256,license_confirmed)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (session["company_id"], record_id, filename, "application/pdf", body, len(body),
                     "Documento técnico emitido", version, session["id"], now, digest),
                )
                attachment_id = cursor.lastrowid
            final_status = "Publicado" if record["module"] == "certificados" else "Emitido"
            self.db.execute(
                "UPDATE records SET status=?,updated_at=? WHERE id=? AND company_id=?",
                (final_status, now, record_id, session["company_id"]),
            )
            self.db.audit(
                session["id"], "issue", record["module"], record_id,
                {"revision": record["revision"], "attachment_id": attachment_id,
                 "sha256": digest, "approval_id": approval["id"],
                 "norms": [norm["id"] for norm in norms]},
                company_id=session["company_id"],
            )
        return self.send_json({
            "ok": True, "attachmentId": attachment_id,
            "downloadUrl": f"/api/attachments/{attachment_id}", "sha256": digest,
            "revision": record["revision"], "status": final_status,
        }, 201 if not existing else 200)

    def send_pdf(self, body, filename):
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-SHA256", hashlib.sha256(body).hexdigest())
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _xml_local(element, name):
        if element is None:
            return None
        for child in element.iter():
            if child.tag.rsplit("}", 1)[-1] == name:
                return child
        return None

    @classmethod
    def _xml_text(cls, element, name, default=""):
        child = cls._xml_local(element, name)
        return (child.text or default).strip() if child is not None else default

    def xml_import(self, session):
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        xml_text = str(data.get("xml") or "")
        if not xml_text or len(xml_text.encode("utf-8")) > 4 * 1024 * 1024:
            return self.error_json("Selecione um XML NF-e válido de até 4 MB")
        if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
            return self.error_json("XML com DTD ou entidade externa não é aceito por segurança")
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            return self.error_json(f"XML inválido: {exc}")
        inf = self._xml_local(root, "infNFe")
        if inf is None:
            return self.error_json("O arquivo não contém uma NF-e reconhecível")
        ide = self._xml_local(inf, "ide")
        emit = self._xml_local(inf, "emit")
        dest = self._xml_local(inf, "dest")
        chave = str(inf.attrib.get("Id") or "").replace("NFe", "")
        numero = self._xml_text(ide, "nNF")
        emit_cnpj = self._xml_text(emit, "CNPJ") or self._xml_text(emit, "CPF")
        emit_name = self._xml_text(emit, "xNome") or "Fornecedor não identificado"
        if not re.fullmatch(r"\d{44}", chave):
            return self.error_json("A chave de acesso da NF-e deve possuir 44 dígitos")
        try:
            _validate_document(emit_cnpj, "CPF/CNPJ do emitente")
        except ValueError as exc:
            return self.error_json(str(exc))
        existing = self.db.connection().execute(
            """SELECT id FROM records WHERE company_id=? AND module='importacoes_xml'
               AND json_extract(payload,'$.chave')=? AND deleted_at IS NULL""",
            (session["company_id"], chave)).fetchone() if chave else None
        if existing:
            return self.error_json("Esta NF-e já foi importada", 409, "duplicate_invoice")
        items = []
        for det in [node for node in inf.iter() if node.tag.rsplit("}", 1)[-1] == "det"]:
            prod = self._xml_local(det, "prod")
            items.append({
                "numero_item": det.attrib.get("nItem"), "codigo": self._xml_text(prod, "cProd"),
                "descricao": self._xml_text(prod, "xProd"), "ncm": self._xml_text(prod, "NCM"),
                "cfop": self._xml_text(prod, "CFOP"), "unidade": self._xml_text(prod, "uCom"),
                "quantidade": self._xml_text(prod, "qCom"), "valor_unitario": self._xml_text(prod, "vUnCom"),
                "valor_total": self._xml_text(prod, "vProd")
            })
        parcels = []
        for dup in [node for node in inf.iter() if node.tag.rsplit("}", 1)[-1] == "dup"]:
            parcels.append({"numero": self._xml_text(dup, "nDup"), "vencimento": self._xml_text(dup, "dVenc"),
                            "valor": self._xml_text(dup, "vDup")})
        total = self._xml_text(self._xml_local(inf, "ICMSTot"), "vNF")
        subject_name = str(data.get("assunto") or f"NF-e {numero or chave[-8:]} — {emit_name}")[:180]
        now = utc_now()
        payload = {
            "assunto": subject_name, "chave": chave, "numero": numero,
            "natureza_operacao": self._xml_text(ide, "natOp"),
            "data_emissao": (self._xml_text(ide, "dhEmi") or self._xml_text(ide, "dEmi"))[:10],
            "fornecedor": emit_name, "fornecedor_documento": emit_cnpj,
            "destinatario": self._xml_text(dest, "xNome"),
            "destinatario_documento": self._xml_text(dest, "CNPJ") or self._xml_text(dest, "CPF"),
            "itens": items, "parcelas": parcels, "valor_total": total,
            "status_importacao": "Importada",
            "assinatura_xml_presente": self._xml_local(root, "Signature") is not None,
            "relacionamentos": []
        }
        try:
            amount = float(total or 0)
        except ValueError:
            amount = None
        if amount is not None and not math.isfinite(amount):
            return self.error_json("Valor total da NF-e inválido")
        self.db.begin_manual_transaction(immediate=True)
        concurrent = self.db.connection().execute(
            """SELECT id FROM records WHERE company_id=? AND module='importacoes_xml'
               AND json_extract(payload,'$.chave')=? AND deleted_at IS NULL""",
            (session["company_id"], chave),
        ).fetchone()
        if concurrent:
            self.db.finish_manual_transaction(commit=False)
            return self.error_json("Esta NF-e já foi importada", 409, "duplicate_invoice")
        cursor = self.db.execute(
            """INSERT INTO records
               (module,title,status,amount,payload,created_by,created_at,updated_at,company_id)
               VALUES('importacoes_xml',?,'Importada',?,?,?,?,?,?)""",
            (f"NF-e {numero or chave[-8:]} — {emit_name}", amount, json_dumps(payload),
             session["id"], now, now, session["company_id"]))
        import_id = cursor.lastrowid
        self.db.sync_relationships(import_id, payload, session["id"], session["company_id"])
        xml_bytes = xml_text.encode("utf-8")
        attachment = self.db.execute(
            """INSERT INTO attachments
               (company_id,record_id,filename,mime_type,content,size,category,version,uploaded_by,
                created_at,sha256,license_confirmed)
               VALUES(?,?,?,'application/xml',?,?,?,'1',?,?,?,0)""",
            (session["company_id"], import_id, Path(str(data.get("filename") or f"nfe-{numero}.xml")).name,
             xml_bytes, len(xml_bytes), "XML NF-e", session["id"], now,
             hashlib.sha256(xml_bytes).hexdigest()))
        self.db.execute("UPDATE records SET payload=json_set(payload,'$.xml_attachment_id',?) WHERE id=?",
                        (attachment.lastrowid, import_id))

        supplier = self.db.connection().execute(
            """SELECT id FROM records WHERE company_id=? AND module='fornecedores'
               AND json_extract(payload,'$.documento')=? AND deleted_at IS NULL""",
            (session["company_id"], emit_cnpj)).fetchone() if emit_cnpj else None
        if not supplier:
            supplier_payload = {"assunto": subject_name, "documento": emit_cnpj, "razao_social": emit_name,
                                "tipo_pessoa": "Pessoa jurídica" if len(emit_cnpj) == 14 else "Pessoa física",
                                "avaliacao": "Pendente",
                                "relacionamentos": [{"record": f"importacoes_xml:{import_id}", "type": "Originado de"}]}
            supplier_cursor = self.db.execute(
                """INSERT INTO records(module,title,status,payload,created_by,created_at,updated_at,company_id)
                   VALUES('fornecedores',?,'Ativo',?,?,?,?,?)""",
                (emit_name, json_dumps(supplier_payload), session["id"], now, now, session["company_id"]))
            self.db.sync_relationships(supplier_cursor.lastrowid, supplier_payload, session["id"], session["company_id"])
        product_links = []
        created_products = 0
        for item in items:
            product = None
            if item.get("codigo"):
                product = self.db.connection().execute(
                    """SELECT id FROM records WHERE company_id=? AND module='produtos'
                       AND json_extract(payload,'$.codigo')=? AND deleted_at IS NULL""",
                    (session["company_id"], item["codigo"])).fetchone()
            if product:
                product_id = product["id"]
            else:
                product_payload = {
                    "assunto": subject_name, "codigo": item.get("codigo"),
                    "descricao": item.get("descricao"), "ncm": item.get("ncm"),
                    "cfop": item.get("cfop"), "unidade": item.get("unidade"),
                    "familia": "Importado de NF-e", "tipo_item": "Produto adquirido",
                    "preco_venda": 0,
                    "origem": "Importação XML NF-e",
                    "relacionamentos": [
                        {"record": f"importacoes_xml:{import_id}", "type": "Originado de"}
                    ]
                }
                product_cursor = self.db.execute(
                    """INSERT INTO records(module,title,status,payload,created_by,created_at,updated_at,company_id)
                       VALUES('produtos',?,'Ativo',?,?,?,?,?)""",
                    (item.get("descricao") or item.get("codigo") or "Produto da NF-e",
                     json_dumps(product_payload), session["id"], now, now, session["company_id"]))
                product_id = product_cursor.lastrowid
                self.db.sync_relationships(
                    product_id, product_payload, session["id"], session["company_id"])
                created_products += 1
            item["produto_id"] = product_id
            product_links.append({"record": f"produtos:{product_id}", "type": "Contém produto"})
        if product_links:
            payload["relacionamentos"] = product_links
            payload["itens"] = items
            self.db.execute("UPDATE records SET payload=?,updated_at=? WHERE id=?",
                            (json_dumps(payload), utc_now(), import_id))
            self.db.sync_relationships(
                import_id, payload, session["id"], session["company_id"])
        for parcel in parcels:
            try:
                parcel_value = -abs(float(parcel["valor"] or 0))
            except ValueError:
                parcel_value = None
            payable_payload = {
                "assunto": subject_name, "fornecedor": emit_name, "documento": numero,
                "parcela": parcel["numero"], "categoria": "Compras",
                "centro_custo": "A classificar", "origem": "Importação XML NF-e",
                "relacionamentos": [{"record": f"importacoes_xml:{import_id}", "type": "Originado de"}]
            }
            payable_cursor = self.db.execute(
                """INSERT INTO records
                   (module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id)
                   VALUES('contas_pagar',?,'Em aberto',?,?,?,?,?,?,?,?)""",
                (f"NF-e {numero} — parcela {parcel['numero'] or len(parcels)}", parcel_value,
                 parcel["vencimento"] or None, json_dumps(payable_payload), session["id"], now, now,
                 session["company_id"]))
            self.db.sync_relationships(payable_cursor.lastrowid, payable_payload, session["id"], session["company_id"])
        self.db.audit(session["id"], "import", "nfe_xml", import_id,
                      {"chave": chave, "items": len(items), "parcels": len(parcels),
                       "created_products": created_products},
                      company_id=session["company_id"])
        self.db.finish_manual_transaction(commit=True)
        return self.send_json({"ok": True, "recordId": import_id, "items": len(items),
                               "parcels": len(parcels), "supplier": emit_name,
                               "createdProducts": created_products}, 201)

    def fiscal_action(self, path, session):
        parts = path.split("/")
        if len(parts) != 5 or not parts[3].isdigit():
            return self.error_json("Documento fiscal inválido", 404)
        record_id, action = int(parts[3]), parts[4]
        allowed = {"registrar", "cce", "cancelar", "inutilizar", "reenviar", "email"}
        if action not in allowed:
            return self.error_json("Ação fiscal inválida")
        record = self.db.connection().execute(
            "SELECT id FROM records WHERE id=? AND company_id=? AND module='fiscal' AND deleted_at IS NULL",
            (record_id, session["company_id"])).fetchone()
        if not record:
            return self.error_json("Documento fiscal não encontrado", 404)
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        provider = self.db.connection().execute(
            "SELECT value FROM company_settings WHERE company_id=? AND key='fiscal_provider'",
            (session["company_id"],)).fetchone()
        provider_config = json.loads(provider["value"] or "{}") if provider else {}
        if action != "registrar" and not provider_config.get("enabled"):
            return self.error_json(
                "Integração fiscal não configurada. Nenhuma ação foi transmitida à SEFAZ.", 409,
                "fiscal_provider_required")
        status = "Registrado localmente" if action == "registrar" else "Aguardando conector"
        cursor = self.db.execute(
            """INSERT INTO fiscal_events
               (company_id,record_id,event_type,status,protocol,response_detail,created_by,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (session["company_id"], record_id, action, status,
             str(data.get("protocol") or "")[:120] or None,
             str(data.get("detail") or "")[:4000] or None, session["id"], utc_now()))
        self.db.audit(session["id"], "event", "fiscal", record_id,
                      {"event": action, "event_id": cursor.lastrowid}, company_id=session["company_id"])
        return self.send_json({"ok": True, "eventId": cursor.lastrowid, "status": status}, 201)

    def subject_action(self, path, session):
        parts = path.split("/")
        if len(parts) != 5 or not parts[3].isdigit():
            return self.error_json("Assunto inválido", 404)
        subject_id, action = int(parts[3]), parts[4]
        subject = self.db.connection().execute(
            "SELECT * FROM subjects WHERE id=? AND company_id=?", (subject_id, session["company_id"])).fetchone()
        if not subject:
            return self.error_json("Assunto não encontrado", 404)
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        if action == "rename":
            name = str(data.get("name") or "").strip()[:180]
            if not name:
                return self.error_json("Informe o novo nome")
            key = f'{session["company_id"]}:{self.db.normalize_subject(name)}'
        elif action == "merge":
            try:
                target_id = int(data.get("target_id"))
            except (ValueError, TypeError):
                return self.error_json("Informe o assunto de destino")
            if target_id == subject_id:
                return self.error_json("Selecione outro assunto para unificar")
            target = self.db.connection().execute(
                "SELECT id FROM subjects WHERE id=? AND company_id=?", (target_id, session["company_id"])).fetchone()
            if not target:
                return self.error_json("Assunto de destino não encontrado")
        elif action != "archive":
            return self.error_json("Ação de assunto inválida")
        try:
            with self.db.transaction(immediate=True):
                if action == "archive":
                    status = "Arquivado" if data.get("archived", True) else "Ativo"
                    self.db.execute(
                        "UPDATE subjects SET status=?,updated_at=? WHERE id=?",
                        (status, utc_now(), subject_id),
                    )
                elif action == "rename":
                    self.db.execute(
                        "UPDATE subjects SET name=?,normalized_name=?,updated_at=? WHERE id=?",
                        (name, key, utc_now(), subject_id),
                    )
                else:
                    db = self.db.connection()
                    rows = db.execute(
                        "SELECT * FROM record_subjects WHERE subject_id=?", (subject_id,)
                    ).fetchall()
                    for row in rows:
                        db.execute(
                            """INSERT OR IGNORE INTO record_subjects
                               (record_id,subject_id,relationship_type,is_primary,created_by,created_at)
                               VALUES(?,?,?,?,?,?)""",
                            (row["record_id"], target_id, row["relationship_type"], row["is_primary"],
                             session["id"], utc_now()),
                        )
                    db.execute(
                        "UPDATE records SET subject_id=? WHERE subject_id=? AND company_id=?",
                        (target_id, subject_id, session["company_id"]),
                    )
                    db.execute("DELETE FROM record_subjects WHERE subject_id=?", (subject_id,))
                    db.execute(
                        "UPDATE subjects SET status='Unificado',updated_at=? WHERE id=?",
                        (utc_now(), subject_id),
                    )
                self.db.audit(
                    session["id"], action, "subject", subject_id, data,
                    company_id=session["company_id"],
                )
        except sqlite3.IntegrityError:
            return self.error_json("Já existe um assunto com este nome", 409, "duplicate_subject")
        return self.send_json({"ok": True})

    def settings_update(self, session):
        try:
            data = self.parse_json()
        except ValueError as exc:
            return self.error_json(str(exc))
        now = utc_now()
        company = data.get("company")
        if isinstance(company, dict):
            name = str(company.get("name") or "").strip()
            if not name:
                return self.error_json("Informe o nome da empresa")
            cnpj = str(company.get("cnpj") or "").strip() or None
            email = str(company.get("email") or "").strip().lower() or None
            if cnpj and not _valid_cnpj(cnpj):
                return self.error_json("CNPJ da empresa inválido")
            if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                return self.error_json("E-mail da empresa inválido")
        with self.db.transaction(immediate=True):
            if isinstance(company, dict):
                self.db.execute(
                    """UPDATE companies SET name=?,cnpj=?,phone=?,email=?,address=?,updated_at=?
                       WHERE id=?""",
                    (name, cnpj, str(company.get("phone") or "").strip() or None, email,
                     str(company.get("address") or "").strip() or None,
                     now, session["company_id"]),
                )
            for key, value in data.items():
                if key not in {"preferences", "fiscal_provider", "email", "banking", "certweb"}:
                    continue
                self.db.execute(
                    """INSERT OR REPLACE INTO company_settings(company_id,key,value,updated_at)
                       VALUES(?,?,?,?)""", (session["company_id"], key, json_dumps(value), now))
            self.db.audit(session["id"], "update", "settings", company_id=session["company_id"])
        return self.send_json({"ok": True})

    def export_data(self, query, session):
        module = (query.get("module") or [""])[0]
        if module and module not in MODULES:
            return self.error_json("Módulo inválido")
        if module:
            if not self.require_module_export(session, module):
                return
        elif not self.capabilities(session)["full_backup"]:
            return self.error_json(
                "A exportação consolidada exige perfil de administrador", 403, "forbidden"
            )
        sql = "SELECT * FROM records WHERE company_id=? AND deleted_at IS NULL"
        params = [session["company_id"]]
        if module:
            sql += " AND module=?"
            params.append(module)
        sql += " ORDER BY module,id"
        rows = self.db.connection().execute(sql, params).fetchall()
        payload = {"format": "SIVS-3", "version": VERSION, "exported_at": utc_now(),
                   "scope": module or "business-data", "records": [self.record_json(r) for r in rows]}
        if not module:
            company = self.db.connection().execute("SELECT * FROM companies WHERE id=?",
                                                   (session["company_id"],)).fetchone()
            payload["company"] = dict(company) if company else {}
            settings = self.db.connection().execute(
                "SELECT key,value,updated_at FROM company_settings WHERE company_id=?",
                (session["company_id"],)).fetchall()
            payload["settings"] = [{"key": row["key"], "value": json.loads(row["value"]),
                                    "updated_at": row["updated_at"]} for row in settings]
            payload["tender_results"] = [dict(row) for row in self.db.connection().execute(
                "SELECT * FROM tender_results WHERE company_id=? ORDER BY id",
                (session["company_id"],)).fetchall()]
            payload["tender_searches"] = [dict(row) for row in self.db.connection().execute(
                "SELECT * FROM tender_searches WHERE company_id=? ORDER BY id",
                (session["company_id"],)).fetchall()]
            payload["attachments"] = [
                {**{key: row[key] for key in row.keys() if key != "content"},
                 "content": base64.b64encode(row["content"]).decode("ascii")}
                for row in self.db.connection().execute(
                    "SELECT * FROM attachments WHERE company_id=? ORDER BY id",
                    (session["company_id"],)).fetchall()
            ]
            payload["approvals"] = [dict(row) for row in self.db.connection().execute(
                "SELECT * FROM approvals WHERE company_id=? ORDER BY id",
                (session["company_id"],)).fetchall()]
            payload["fiscal_events"] = [dict(row) for row in self.db.connection().execute(
                "SELECT * FROM fiscal_events WHERE company_id=? ORDER BY id",
                (session["company_id"],)).fetchall()]
            payload["search_schedules"] = [dict(row) for row in self.db.connection().execute(
                "SELECT * FROM search_schedules WHERE company_id=? ORDER BY id",
                (session["company_id"],)).fetchall()]
        self.db.audit(
            session["id"], "export", module or "business-data",
            detail={"records": len(rows)}, company_id=session["company_id"],
        )
        body = json.dumps(
            payload, ensure_ascii=False, indent=2, allow_nan=False
        ).encode("utf-8")
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="sivs-dados-{module or "consolidados"}-{datetime.now():%Y%m%d}.json"',
        )
        self.send_header("Content-Length", str(len(body)))
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def database_backup(self, session):
        """Gera cópia SQLite íntegra e a cifra com AES-256-GCM."""
        try:
            data = self.parse_json(max_bytes=8 * 1024)
        except ValueError as exc:
            return self.error_json(str(exc))
        passphrase = str(data.get("passphrase") or "")
        if len(passphrase) < 12 or len(passphrase) > 256:
            return self.error_json(
                "A senha do backup deve possuir entre 12 e 256 caracteres"
            )
        inaccessible = self.db.scalar(
            """SELECT COUNT(*) FROM companies c WHERE c.active=1 AND NOT EXISTS (
                 SELECT 1 FROM company_memberships cm
                 WHERE cm.company_id=c.id AND cm.user_id=? AND cm.active=1 AND cm.role='admin'
               )""",
            (session["id"],),
        )
        if inaccessible:
            return self.error_json(
                "O backup integral contém todas as empresas e exige administração em cada uma delas.",
                403, "forbidden",
            )
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        except ImportError:
            return self.error_json(
                "O componente de criptografia não está instalado. Execute: pip install cryptography",
                503, "crypto_unavailable",
            )

        self.db.audit(
            session["id"], "backup", "database",
            detail={"format": "SIVS-BACKUP-2", "encrypted": True},
            company_id=session["company_id"],
        )
        temporary = tempfile.NamedTemporaryFile(prefix="sivs-backup-", suffix=".sqlite3", delete=False)
        temporary_path = Path(temporary.name)
        temporary.close()
        try:
            destination = sqlite3.connect(temporary_path)
            try:
                self.db.connection().backup(destination)
                # Sessões são deliberadamente invalidadas no artefato para impedir replay após restauração.
                destination.execute("DELETE FROM sessions")
                destination.commit()
                integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                destination.close()
            if integrity != "ok":
                raise sqlite3.DatabaseError(f"verificação de integridade: {integrity}")
            plaintext = temporary_path.read_bytes()
        except (OSError, sqlite3.Error) as exc:
            return self.error_json(f"Não foi possível gerar o backup íntegro: {exc}", 500, "backup_failed")
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

        magic = b"SIVSBKP2"
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(12)
        iterations = 600_000
        key = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations
        ).derive(passphrase.encode("utf-8"))
        header = magic + iterations.to_bytes(4, "big") + salt + nonce
        encrypted = header + AESGCM(key).encrypt(nonce, plaintext, header)
        checksum = hashlib.sha256(encrypted).hexdigest()
        filename = f"sivs-backup-{datetime.now():%Y%m%d-%H%M%S}.sivsbackup"
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.sivs.backup")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(encrypted)))
        self.send_header("X-SIVS-Format", "SIVS-BACKUP-2")
        self.send_header("X-Content-SHA256", checksum)
        self.security_headers()
        self.end_headers()
        self.wfile.write(encrypted)

    def import_data(self, session):
        try:
            data = self.parse_json(max_bytes=MAX_IMPORT_BODY)
        except ValueError as exc:
            return self.error_json(str(exc))
        records = data.get("records", [])
        if not isinstance(records, list) or len(records) > 10_000:
            return self.error_json("Arquivo de importação inválido ou excessivamente grande")
        count = 0
        now = utc_now()
        transaction_context = self.db.transaction(immediate=True)
        try:
            db = transaction_context.__enter__()
            id_map = {}
            staged = []
            for record in records:
                values = self.normalized_record(record)
                source_key = (record.get("payload") or {}).get("source_key") if isinstance(record, dict) else None
                existing = db.execute(
                    """SELECT id FROM records WHERE company_id=? AND module='fontes'
                       AND json_extract(payload,'$.source_key')=?""",
                    (session["company_id"], source_key)).fetchone() if values[0] == "fontes" and source_key else None
                if existing:
                    record_id = existing["id"]
                else:
                    cursor = db.execute(
                        """INSERT INTO records
                           (module,title,status,amount,due_date,payload,created_by,created_at,updated_at,company_id)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (*values, session["id"], now, now, session["company_id"]))
                    record_id = cursor.lastrowid
                    count += 1
                if isinstance(record, dict) and record.get("id") is not None:
                    id_map[int(record["id"])] = record_id
                staged.append((record_id, json.loads(values[5])))
            for record_id, payload in staged:
                rewritten = []
                relations = payload.get("relacionamentos") if isinstance(payload.get("relacionamentos"), list) else []
                primary = payload.get("registro_relacionado")
                if primary:
                    relations = relations + [{"record": primary, "type": payload.get("tipo_relacao") or "Relacionado a"}]
                for relation in relations:
                    if not isinstance(relation, dict):
                        continue
                    reference = str(relation.get("record") or relation.get("registro") or "")
                    try:
                        old_target = int(reference.rsplit(":", 1)[-1])
                    except ValueError:
                        continue
                    new_target = id_map.get(old_target)
                    if new_target:
                        target = db.execute(
                            "SELECT module FROM records WHERE id=? AND company_id=?",
                            (new_target, session["company_id"]),
                        ).fetchone()
                        if target:
                            rewritten.append({
                                "record": f'{target["module"]}:{new_target}',
                                "type": relation.get("type") or relation.get("tipo") or "Relacionado a",
                            })
                payload["registro_relacionado"] = ""
                payload["relacionamentos"] = rewritten
                module_row = db.execute("SELECT module FROM records WHERE id=?", (record_id,)).fetchone()
                self.db.validate_normative_base(
                    module_row["module"], payload, session["company_id"],
                )
                db.execute("UPDATE records SET payload=? WHERE id=?", (json_dumps(payload), record_id))
                self.db.sync_relationships(record_id, payload, session["id"], session["company_id"])
            if isinstance(data.get("company"), dict):
                company = data["company"]
                db.execute(
                    """UPDATE companies SET name=?,cnpj=?,phone=?,email=?,address=?,updated_at=? WHERE id=?""",
                    (str(company.get("name") or "SECCOL")[:200], company.get("cnpj"), company.get("phone"),
                     company.get("email"), company.get("address"), now, session["company_id"]))
            if isinstance(data.get("settings"), list):
                for setting in data["settings"][:100]:
                    if isinstance(setting, dict) and setting.get("key") in {
                        "preferences", "fiscal_provider", "email", "banking", "certweb"
                    }:
                        db.execute(
                            """INSERT OR REPLACE INTO company_settings(company_id,key,value,updated_at)
                               VALUES(?,?,?,?)""",
                            (session["company_id"], setting["key"], json_dumps(setting.get("value")), now))
            for result in data.get("tender_results", [])[:10000] if isinstance(data.get("tender_results"), list) else []:
                if not isinstance(result, dict):
                    continue
                converted = id_map.get(result.get("converted_record_id")) if result.get("converted_record_id") else None
                source_key = result.get("source_key") or "pncp"
                if session["company_id"] != 1 and not str(source_key).startswith(f'{session["company_id"]}:'):
                    source_key = f'{session["company_id"]}:{source_key}'
                db.execute(
                    """INSERT OR IGNORE INTO tender_results
                       (source_key,external_id,title,object_text,agency,uf,municipality,modality,estimated_value,
                        published_at,deadline,source_url,matched_terms,relevance_score,status,raw_json,
                        converted_record_id,created_at,updated_at,company_id)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (source_key, result.get("external_id"), result.get("title"),
                     result.get("object_text"), result.get("agency"), result.get("uf"), result.get("municipality"),
                     result.get("modality"), result.get("estimated_value"), result.get("published_at"),
                     result.get("deadline"), result.get("source_url"), result.get("matched_terms") or "[]",
                     result.get("relevance_score") or 0, result.get("status") or "Novo",
                     result.get("raw_json") or "{}", converted, result.get("created_at") or now,
                     result.get("updated_at") or now, session["company_id"]))
            for search in data.get("tender_searches", [])[:10000] if isinstance(data.get("tender_searches"), list) else []:
                if not isinstance(search, dict):
                    continue
                db.execute(
                    """INSERT INTO tender_searches
                       (keywords,uf,days,sources_searched,found_count,new_count,error_detail,created_by,created_at,company_id)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (search.get("keywords") or "[]", search.get("uf"), search.get("days") or 7,
                     search.get("sources_searched") or "[]", search.get("found_count") or 0,
                     search.get("new_count") or 0, search.get("error_detail"), session["id"],
                     search.get("created_at") or now, session["company_id"]))
            for attachment in data.get("attachments", [])[:10000] if isinstance(data.get("attachments"), list) else []:
                if not isinstance(attachment, dict):
                    continue
                mapped_record = id_map.get(attachment.get("record_id"))
                if not mapped_record or not attachment.get("content"):
                    continue
                try:
                    content = base64.b64decode(attachment["content"], validate=True)
                except (ValueError, TypeError, binascii.Error):
                    continue
                if len(content) > MAX_ATTACHMENT:
                    continue
                db.execute(
                    """INSERT INTO attachments
                       (company_id,record_id,filename,mime_type,content,size,category,version,
                        uploaded_by,created_at,sha256,license_confirmed)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (session["company_id"], mapped_record, Path(str(attachment.get("filename") or "arquivo.bin")).name,
                     attachment.get("mime_type") or "application/octet-stream", content, len(content),
                     attachment.get("category"), attachment.get("version"), session["id"],
                     attachment.get("created_at") or now, hashlib.sha256(content).hexdigest(),
                     1 if attachment.get("license_confirmed") else 0))
            for approval in data.get("approvals", [])[:10000] if isinstance(data.get("approvals"), list) else []:
                if not isinstance(approval, dict):
                    continue
                mapped_record = id_map.get(approval.get("record_id"))
                if not mapped_record:
                    continue
                db.execute(
                    """INSERT INTO approvals
                       (company_id,record_id,approval_type,status,comment,requested_at,decided_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (session["company_id"], mapped_record,
                     approval.get("approval_type") or "Aprovação",
                     approval.get("status") or "Pendente", approval.get("comment"),
                     approval.get("requested_at") or now, approval.get("decided_at")))
            for event in data.get("fiscal_events", [])[:10000] if isinstance(data.get("fiscal_events"), list) else []:
                if not isinstance(event, dict):
                    continue
                mapped_record = id_map.get(event.get("record_id"))
                if not mapped_record:
                    continue
                db.execute(
                    """INSERT INTO fiscal_events
                       (company_id,record_id,event_type,status,protocol,response_detail,created_by,created_at)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (session["company_id"], mapped_record,
                     event.get("event_type") or "registrar", event.get("status") or "Importado",
                     event.get("protocol"), event.get("response_detail"), session["id"],
                     event.get("created_at") or now))
            for schedule in data.get("search_schedules", [])[:1000] if isinstance(data.get("search_schedules"), list) else []:
                if not isinstance(schedule, dict):
                    continue
                db.execute(
                    """INSERT INTO search_schedules
                       (company_id,name,keywords,uf,days,frequency,active,last_run_at,next_run_at,
                        created_by,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (session["company_id"], schedule.get("name") or "Monitor importado",
                     schedule.get("keywords") or "[]", schedule.get("uf"), schedule.get("days") or 7,
                     schedule.get("frequency") or "manual", 1 if schedule.get("active", True) else 0,
                     schedule.get("last_run_at"), schedule.get("next_run_at"), session["id"],
                     schedule.get("created_at") or now, schedule.get("updated_at") or now))
            transaction_context.__exit__(None, None, None)
        except Exception as exc:
            transaction_context.__exit__(type(exc), exc, exc.__traceback__)
            if isinstance(exc, (ValueError, TypeError, KeyError, sqlite3.Error)):
                return self.error_json(f"Importação cancelada: {exc}")
            return self.error_json(
                "Importação cancelada porque o arquivo contém dados incompatíveis",
                400, "import_failed",
            )
        self.db.audit(session["id"], "import", "records", detail={"count": count},
                      company_id=session["company_id"])
        return self.send_json({"ok": True, "imported": count})

    def static_get(self, path):
        if path == "/":
            path = "/index.html"
        requested = (STATIC_DIR / path.lstrip("/")).resolve()
        if STATIC_DIR.resolve() not in requested.parents and requested != STATIC_DIR.resolve():
            return self.send_error(403)
        if not requested.exists() or not requested.is_file():
            if Path(path).suffix:
                return self.error_json("Arquivo não encontrado", 404, "not_found")
            requested = STATIC_DIR / "index.html"
        body = requested.read_bytes()
        content_type = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        self._response_started = True
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache" if requested.name == "index.html" else "public, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)


class SIVSServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler, db):
        super().__init__(address, handler)
        self.db = db
        self._rate_lock = threading.Lock()
        self._rate_buckets = {}
        self._stop_workers = threading.Event()
        self._scheduler = threading.Thread(
            target=self._scheduler_loop, name="sivs-scheduler", daemon=True
        )
        self._scheduler.start()

    def rate_limit(self, bucket, client, limit, window_seconds):
        now = time.monotonic()
        key = (str(bucket), str(client))
        with self._rate_lock:
            recent = [stamp for stamp in self._rate_buckets.get(key, []) if now - stamp < window_seconds]
            if len(recent) >= limit:
                retry_after = max(1, int(window_seconds - (now - recent[0])) + 1)
                self._rate_buckets[key] = recent
                return False, retry_after
            recent.append(now)
            self._rate_buckets[key] = recent
            if len(self._rate_buckets) > 10_000:
                self._rate_buckets = {key: recent}
            return True, 0

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.db.close_thread_connection()

    def run_tender_job(self, runner, job_id, session, request_data):
        try:
            runner._run_tender_job(job_id, session, request_data)
        finally:
            self.db.close_thread_connection()

    def _scheduler_loop(self):
        while not self._stop_workers.is_set():
            try:
                self._enqueue_due_tender_schedules()
            except Exception:
                print("[ERRO AGENDADOR] Não foi possível processar os planos de pesquisa")
                traceback.print_exc()
            self._stop_workers.wait(30)
        self.db.close_thread_connection()

    def _enqueue_due_tender_schedules(self):
        now = utc_now()
        queued = []
        with self.db.transaction(immediate=True):
            schedules = self.db.connection().execute(
                """SELECT * FROM search_schedules
                   WHERE active=1 AND frequency IN ('daily','weekly')
                     AND next_run_at IS NOT NULL AND next_run_at<=?
                   ORDER BY next_run_at,id LIMIT 20""",
                (now,),
            ).fetchall()
            for schedule in schedules:
                active = self.db.connection().execute(
                    """SELECT 1 FROM tender_jobs
                       WHERE company_id=? AND status IN ('queued','running') LIMIT 1""",
                    (schedule["company_id"],),
                ).fetchone()
                delta = timedelta(days=1 if schedule["frequency"] == "daily" else 7)
                next_run = (datetime.now(timezone.utc) + delta).isoformat(timespec="seconds")
                if active:
                    self.db.execute(
                        "UPDATE search_schedules SET next_run_at=?,updated_at=? WHERE id=?",
                        (next_run, now, schedule["id"]),
                    )
                    continue
                request_data = {
                    "keywords": json_loads_strict(schedule["keywords"] or "[]"),
                    "uf": schedule["uf"] or "",
                    "days": schedule["days"],
                }
                cursor = self.db.execute(
                    """INSERT INTO tender_jobs
                       (company_id,schedule_id,status,request_json,progress,stage,created_by,created_at)
                       VALUES(?,?,'queued',?,0,'Pesquisa agendada enfileirada',?,?)""",
                    (schedule["company_id"], schedule["id"], json_dumps(request_data),
                     schedule["created_by"], now),
                )
                self.db.execute(
                    "UPDATE search_schedules SET next_run_at=?,updated_at=? WHERE id=?",
                    (next_run, now, schedule["id"]),
                )
                queued.append((cursor.lastrowid, schedule["company_id"],
                               schedule["created_by"], request_data))
        for job_id, company_id, user_id, request_data in queued:
            runner = object.__new__(SIVSHandler)
            runner.server = self
            threading.Thread(
                target=self.run_tender_job,
                args=(runner, job_id, {"id": user_id, "company_id": company_id}, request_data),
                name=f"sivs-scheduled-tender-{job_id}", daemon=True,
            ).start()

    def server_close(self):
        self._stop_workers.set()
        if self._scheduler.is_alive() and threading.current_thread() is not self._scheduler:
            self._scheduler.join(timeout=2)
        super().server_close()
        self.db.close_thread_connection()


def main():
    parser = argparse.ArgumentParser(description="Servidor local do SIVS")
    parser.add_argument("--host", default=os.environ.get("SIVS_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT") or os.environ.get("SIVS_PORT", "8844")),
    )
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("SIVS_DB", DEFAULT_DB)))
    parser.add_argument(
        "--allow-insecure-network", action="store_true",
        default=os.environ.get("SIVS_ALLOW_INSECURE_NETWORK") == "1",
        help="permite HTTP em interface não local; use apenas em rede isolada e temporariamente",
    )
    args = parser.parse_args()
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    proxy_secure = (
        os.environ.get("SIVS_TRUST_PROXY") == "1" and
        os.environ.get("SIVS_SECURE_COOKIE") == "1"
    )
    if args.host not in local_hosts and not (args.allow_insecure_network or proxy_secure):
        parser.error(
            "acesso em rede exige proxy HTTPS. Mantenha --host 127.0.0.1 ou, assumindo o risco, "
            "use --allow-insecure-network"
        )
    if args.host not in local_hosts and args.allow_insecure_network and not proxy_secure:
        print("AVISO CRÍTICO: HTTP em rede foi liberado explicitamente; credenciais não terão proteção TLS.")
    persistent_storage = require_persistent_database(args.db)
    db = Database(args.db)
    server = SIVSServer((args.host, args.port), SIVSHandler, db)
    print(f"SIVS disponível em http://{args.host}:{args.port}")
    print(f"Banco de dados: {args.db.resolve()}")
    if persistent_storage:
        print("Persistencia do banco: volume montado e verificado")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSIVS encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
