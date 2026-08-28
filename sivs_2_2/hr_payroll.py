"""Núcleo determinístico de ponto, AEJ e folha mensal brasileira.

Valores monetários usam centavos inteiros. Marcações são importadas como fatos
imutáveis; ajustes devem entrar como novos fatos com motivo e autoria no servidor.
"""

from __future__ import annotations

import csv
import calendar
import hashlib
import io
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


class HRError(ValueError):
    pass


LEGAL_TABLE_VERSION = "BR-2026.1"
LEGAL_TABLE_SOURCE = {
    "inss": "Portaria Interministerial MPS/MF nº 13, de 09/01/2026",
    "irrf": "Receita Federal — Tributação de 2026, atualizada em 27/04/2026",
}
INSS_BRACKETS_2026 = (
    (162_100, 750),
    (290_284, 900),
    (435_427, 1_200),
    (847_555, 1_400),
)
IRRF_BRACKETS_2026 = (
    (242_880, 0, 0),
    (282_665, 750, 18_216),
    (375_105, 1_500, 39_416),
    (466_468, 2_250, 67_549),
    (None, 2_750, 90_873),
)
IRRF_DEPENDENT_DEDUCTION_CENTS = 18_959
IRRF_SIMPLIFIED_DEDUCTION_CENTS = 60_720


def _money(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _parse_datetime(value: str, default_offset="-0300") -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise HRError("Data e hora da marcação não informadas")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}", raw):
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?", raw):
        normalized = raw.replace(" ", "T")
        if len(normalized) == 16:
            normalized += ":00"
        return datetime.strptime(normalized + default_offset, "%Y-%m-%dT%H:%M:%S%z")
    for pattern in ("%d/%m/%Y %H:%M:%S%z", "%d/%m/%Y %H:%M%z"):
        try:
            candidate = raw if re.search(r"[+-]\d{4}$", raw) else raw + default_offset
            return datetime.strptime(candidate, pattern)
        except ValueError:
            continue
    raise HRError(f"Data e hora inválidas: {raw}")


def crc16_kermit(content: bytes) -> str:
    crc = 0
    for byte in content:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return f"{crc & 0xFFFF:04X}"


def parse_afd(content: bytes, rep_type: int | None = None) -> dict:
    """Lê AFD leiaute 004 (Portaria 671), preservando fatos e alertas."""
    if not isinstance(content, (bytes, bytearray)) or not content:
        raise HRError("Arquivo AFD vazio")
    try:
        text = bytes(content).decode("iso-8859-1")
    except UnicodeDecodeError as exc:
        raise HRError("AFD deve estar codificado em ISO-8859-1") from exc
    if re.search(r"(?<!\r)\n|\r(?!\n)", text):
        raise HRError("AFD deve usar terminação de linha CRLF (ISO-8859-1)")
    lines = text.splitlines()
    if not lines or any(not line for line in lines):
        raise HRError("AFD não pode conter linhas vazias")
    header = lines[0]
    if len(header) < 302 or header[:9] != "000000000" or header[9:10] != "1":
        raise HRError("Cabeçalho AFD inválido")
    version = header[250:253]
    if version != "004":
        raise HRError(f"Leiaute AFD {version or 'desconhecido'} não suportado; esperado 004")
    employer_document = _digits(header[11:25]).lstrip("0") or "0"
    rep_identifier = header[189:206].strip()
    if not re.fullmatch(r"\d{17}", rep_identifier):
        raise HRError("Identificador do REP no cabeçalho AFD é inválido")
    if rep_type not in {None, 1, 2, 3}:
        raise HRError("Tipo de REP inválido; informe REP-C, REP-A ou REP-P")
    warnings = []
    if header[-4:].upper() != crc16_kermit(header[:-4].encode("iso-8859-1")):
        warnings.append({"line": 1, "code": "CRC_MISMATCH", "nsr": 0})
    punches = []
    counts = Counter()
    seen_nsr = set()
    previous_rep_p_hash = ""
    trailer = None
    previous_nsr = 0
    trailer_position = None
    for line_number, line in enumerate(lines[1:], start=2):
        if line.startswith("999999999") and len(line) >= 64 and line[63:64] == "9":
            if trailer is not None:
                raise HRError("AFD possui mais de um trailer")
            trailer = line
            trailer_position = line_number
            continue
        if line.startswith("ASSINATURA_DIGITAL_EM_ARQUIVO_P7S") and len(line) == 100:
            continue
        if trailer is not None:
            raise HRError("Registro encontrado após o trailer do AFD")
        if len(line) < 10 or not line[:9].isdigit():
            raise HRError(f"Registro inválido na linha {line_number}")
        record_type = line[9:10]
        if record_type not in {"2", "3", "4", "5", "6", "7"}:
            raise HRError(f"Tipo de registro AFD inválido na linha {line_number}")
        nsr = int(line[:9])
        if nsr in seen_nsr:
            raise HRError(f"NSR duplicado no AFD: {nsr}")
        if nsr <= previous_nsr:
            raise HRError(f"NSR fora de ordem no AFD: {nsr}")
        seen_nsr.add(nsr)
        previous_nsr = nsr
        counts[record_type] += 1
        if record_type in {"2", "3", "4", "5"}:
            expected_crc = line[-4:].upper()
            actual_crc = crc16_kermit(line[:-4].encode("iso-8859-1"))
            if expected_crc != actual_crc:
                warnings.append({"line": line_number, "code": "CRC_MISMATCH", "nsr": nsr})
        if record_type == "3":
            if len(line) != 50:
                raise HRError(f"Marcação AFD tipo 3 incompleta na linha {line_number}")
            occurred = _parse_datetime(line[10:34])
            cpf = _digits(line[34:46])[-11:]
            punches.append({
                "nsr": nsr, "cpf": cpf, "occurredAt": occurred.isoformat(),
                "source": "AFD_REP_C_A", "collector": None, "offline": False,
                "sourceHash": hashlib.sha256(line.encode("iso-8859-1")).hexdigest(),
            })
        elif record_type == "7":
            if len(line) != 137:
                raise HRError(f"Marcação AFD tipo 7 incompleta na linha {line_number}")
            occurred = _parse_datetime(line[10:34])
            cpf = _digits(line[34:46])[-11:]
            stored_hash = line[73:137].strip().lower()
            hash_material = line[:73] + previous_rep_p_hash
            calculated_hash = hashlib.sha256(hash_material.encode("iso-8859-1")).hexdigest()
            if not re.fullmatch(r"[0-9a-f]{64}", stored_hash) or stored_hash != calculated_hash:
                warnings.append({"line": line_number, "code": "HASH_CHAIN_MISMATCH", "nsr": nsr})
            previous_rep_p_hash = stored_hash
            punches.append({
                "nsr": nsr, "cpf": cpf, "occurredAt": occurred.isoformat(),
                "recordedAt": _parse_datetime(line[46:70]).isoformat(),
                "source": "AFD_REP_P", "collector": line[70:72],
                "offline": line[72:73] == "1", "sourceHash": stored_hash,
            })
    if trailer is None:
        raise HRError("Trailer AFD não encontrado")
    detected_rep_type = 3 if counts["7"] else (rep_type or 1)
    if counts["7"] and detected_rep_type != 3:
        raise HRError("AFD com registro tipo 7 deve ser identificado como REP-P")
    if counts["3"] and detected_rep_type == 3:
        raise HRError("AFD de REP-P deve usar marcações do registro tipo 7")
    trailer_counts = {str(kind): int(trailer[start:start + 9]) for kind, start in zip(range(2, 8), range(9, 63, 9))}
    for kind in range(2, 8):
        if trailer_counts[str(kind)] != counts[str(kind)]:
            raise HRError(f"Quantidade do registro tipo {kind} diverge do trailer")
    return {
        "format": "AFD004", "employerDocument": employer_document,
        "repIdentifier": rep_identifier,
        "repType": detected_rep_type,
        "periodStart": header[206:216], "periodEnd": header[216:226],
        "generatedAt": _parse_datetime(header[226:250]).isoformat(),
        "punches": punches, "warnings": warnings, "recordCounts": dict(counts),
    }


def parse_clock_csv(content: bytes, default_offset="-0300") -> dict:
    if not isinstance(content, (bytes, bytearray)) or not content:
        raise HRError("Arquivo CSV vazio")
    raw = bytes(content)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("iso-8859-1")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise HRError("CSV sem cabeçalho")
    normalize = lambda value: re.sub(r"[^a-z0-9]", "", str(value).lower().translate(
        str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")))
    fields = {normalize(name): name for name in reader.fieldnames}
    cpf_field = next((fields[key] for key in ("cpf", "documento", "pis", "empregado") if key in fields), None)
    timestamp_field = next((fields[key] for key in ("datahora", "datetime", "timestamp", "marcacao") if key in fields), None)
    date_field = next((fields[key] for key in ("data", "date") if key in fields), None)
    time_field = next((fields[key] for key in ("hora", "horario", "time") if key in fields), None)
    nsr_field = next((fields[key] for key in ("nsr", "id", "sequencial") if key in fields), None)
    if not cpf_field or (not timestamp_field and not (date_field and time_field)):
        raise HRError("CSV deve conter CPF e Data/Hora, ou colunas Data e Hora")
    punches = []
    for index, row in enumerate(reader, start=2):
        cpf = _digits(row.get(cpf_field))[-11:]
        if len(cpf) != 11:
            raise HRError(f"CPF inválido na linha {index}")
        stamp = row.get(timestamp_field) if timestamp_field else f"{row.get(date_field, '')} {row.get(time_field, '')}"
        occurred = _parse_datetime(stamp, default_offset)
        external = str(row.get(nsr_field) or "").strip() if nsr_field else ""
        if not external:
            external = hashlib.sha256(f"{cpf}|{occurred.isoformat()}|{index}".encode()).hexdigest()[:24]
        punches.append({
            "nsr": external, "cpf": cpf, "occurredAt": occurred.isoformat(),
            "source": "CLOCK_CSV", "collector": None, "offline": False,
            "sourceHash": hashlib.sha256(json_row(row).encode()).hexdigest(),
        })
    if not punches:
        raise HRError("CSV não contém marcações")
    return {"format": "CSV", "punches": punches, "warnings": [], "recordCounts": {"punches": len(punches)}}


def json_row(row: dict) -> str:
    return "|".join(f"{key}={row.get(key, '')}" for key in sorted(row))


def summarize_timesheet(punches: list[dict], period: str, schedule: dict,
                        through_date=None) -> dict:
    if not re.fullmatch(r"20\d{2}-(?:0[1-9]|1[0-2])", str(period)):
        raise HRError("Competência inválida")
    by_day = defaultdict(list)
    for punch in punches:
        occurred = datetime.fromisoformat(str(punch["occurredAt"]))
        if occurred.strftime("%Y-%m") == period:
            by_day[occurred.date().isoformat()].append(occurred)
    year, month = (int(value) for value in period.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    natural_end = datetime(year, month, last_day).date()
    if through_date is None:
        through = natural_end
    elif isinstance(through_date, datetime):
        through = through_date.date()
    else:
        through = through_date
    through = min(through, natural_end)
    for day_number in range(1, through.day + 1):
        current = datetime(year, month, day_number).date()
        expected = int((schedule or {}).get(str(current.isoweekday()), 0) or 0)
        if expected:
            by_day.setdefault(current.isoformat(), [])
    days = []
    totals = Counter()
    for day, values in sorted(by_day.items()):
        values.sort()
        current_date = datetime.fromisoformat(day).date()
        weekday = str(current_date.isoweekday())
        expected = int((schedule or {}).get(weekday, 0) or 0)
        worked = 0
        issues = []
        if len(values) % 2:
            issues.append("ODD_PUNCH_COUNT")
        for index in range(0, len(values) - 1, 2):
            minutes = int((values[index + 1] - values[index]).total_seconds() // 60)
            if minutes <= 0 or minutes > 16 * 60:
                issues.append("INVALID_INTERVAL")
            else:
                worked += minutes
        overtime = max(0, worked - expected)
        absence = max(0, expected - worked) if expected and not issues else 0
        days.append({
            "date": day, "expectedMinutes": expected, "workedMinutes": worked,
            "overtimeMinutes": overtime, "absenceMinutes": absence,
            "punches": [value.isoformat() for value in values], "issues": issues,
        })
        totals.update({"expectedMinutes": expected, "workedMinutes": worked,
                       "overtimeMinutes": overtime, "absenceMinutes": absence,
                       "issueCount": len(issues)})
    global_issues = []
    if totals["expectedMinutes"] and not any(day["punches"] for day in days):
        global_issues.append("NO_PUNCHES")
        totals["issueCount"] += 1
    return {"period": period, "days": days, "totals": dict(totals),
            "issues": global_issues, "ready": totals["issueCount"] == 0}


def calculate_inss_2026(base_cents: int) -> int:
    base = max(0, min(int(base_cents), INSS_BRACKETS_2026[-1][0]))
    previous = 0
    contribution = Decimal(0)
    for ceiling, rate_bp in INSS_BRACKETS_2026:
        portion = max(0, min(base, ceiling) - previous)
        contribution += Decimal(portion) * Decimal(rate_bp) / Decimal(10_000)
        previous = ceiling
        if base <= ceiling:
            break
    return _money(contribution)


def calculate_irrf_2026(taxable_cents: int, inss_cents: int, dependents=0) -> dict:
    taxable = max(0, int(taxable_cents))
    legal_deduction = max(0, int(inss_cents)) + max(0, int(dependents)) * IRRF_DEPENDENT_DEDUCTION_CENTS
    chosen_deduction = max(legal_deduction, IRRF_SIMPLIFIED_DEDUCTION_CENTS)
    method = "SIMPLIFIED" if chosen_deduction == IRRF_SIMPLIFIED_DEDUCTION_CENTS else "LEGAL"
    base = max(0, taxable - chosen_deduction)
    raw_tax = 0
    for ceiling, rate_bp, deduction in IRRF_BRACKETS_2026:
        if ceiling is None or base <= ceiling:
            raw_tax = max(0, _money(Decimal(base) * Decimal(rate_bp) / Decimal(10_000)) - deduction)
            break
    reduction = 0
    if taxable <= 500_000:
        reduction = raw_tax
    elif taxable <= 735_000:
        reduction = min(raw_tax, max(0, _money(Decimal(97_862) - Decimal("0.133145") * Decimal(taxable))))
    return {"taxCents": max(0, raw_tax - reduction), "baseCents": base,
            "deductionCents": chosen_deduction, "deductionMethod": method,
            "reductionCents": reduction}


def calculate_monthly_payroll(*, salary_cents: int, monthly_divisor: int, dependents: int,
                              overtime_minutes=0, absence_minutes=0, overtime_rate_bp=5_000,
                              deduct_absence=True, events=None) -> dict:
    if salary_cents <= 0 or not 1 <= int(monthly_divisor) <= 400:
        raise HRError("Salário e divisor mensal válidos são obrigatórios")
    hourly = Decimal(salary_cents) / Decimal(monthly_divisor)
    overtime_cents = _money(hourly * Decimal(max(0, int(overtime_minutes))) / Decimal(60)
                            * (Decimal(1) + Decimal(overtime_rate_bp) / Decimal(10_000)))
    absence_cents = (_money(hourly * Decimal(max(0, int(absence_minutes))) / Decimal(60))
                     if deduct_absence else 0)
    earnings = int(salary_cents) + overtime_cents
    deductions_before_tax = absence_cents
    inss_base = int(salary_cents) + overtime_cents - absence_cents
    irrf_taxable = inss_base
    fgts_base = inss_base
    event_rows = []
    for event in events or []:
        amount = max(0, int(event.get("amountCents") or 0))
        kind = str(event.get("kind") or "").upper()
        if kind not in {"EARNING", "DEDUCTION"} or not amount:
            raise HRError("Evento de folha inválido")
        if kind == "EARNING":
            earnings += amount
            if event.get("incidenceInss", True):
                inss_base += amount
            if event.get("incidenceIrrf", True):
                irrf_taxable += amount
            if event.get("incidenceFgts", True):
                fgts_base += amount
        else:
            deductions_before_tax += amount
            if event.get("deductibleIrrf", False):
                irrf_taxable = max(0, irrf_taxable - amount)
        event_rows.append({**event, "amountCents": amount, "kind": kind})
    inss = calculate_inss_2026(inss_base)
    irrf = calculate_irrf_2026(irrf_taxable, inss, dependents)
    fgts = _money(Decimal(max(0, fgts_base)) * Decimal("0.08"))
    deductions = deductions_before_tax + inss + irrf["taxCents"]
    net = earnings - deductions
    if net < 0:
        raise HRError("Descontos excedem os proventos da folha")
    return {
        "tableVersion": LEGAL_TABLE_VERSION, "salaryCents": int(salary_cents),
        "overtimeMinutes": int(overtime_minutes), "overtimeCents": overtime_cents,
        "absenceMinutes": int(absence_minutes), "absenceCents": absence_cents,
        "earningsCents": earnings, "taxableCents": irrf_taxable,
        "inssBaseCents": max(0, inss_base), "inssCents": inss,
        "irrfCents": irrf["taxCents"], "irrfBaseCents": irrf["baseCents"],
        "irrfDeductionMethod": irrf["deductionMethod"], "irrfReductionCents": irrf["reductionCents"],
        "fgtsBaseCents": max(0, fgts_base), "fgtsCents": fgts,
        "deductionsCents": deductions, "netCents": net, "events": event_rows,
    }


def build_aej(*, employer: dict, employments: list[dict], schedules: dict,
              punches: list[dict], period_start: str, period_end: str,
              generated_at: datetime | None = None, reps=None) -> bytes:
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        raise HRError("Data de geração do AEJ deve conter fuso horário")
    document = _digits(employer.get("document"))
    if len(document) not in {11, 14}:
        raise HRError("CPF/CNPJ do empregador inválido para AEJ")
    counts = Counter()
    lines = []
    def add(kind, *fields):
        lines.append("|".join((kind, *(str(value or "") for value in fields))))
        counts[kind] += 1
    add("01", "1" if len(document) == 14 else "2", document, employer.get("caepf", ""),
        employer.get("cno", ""), employer.get("name", ""), period_start, period_end,
        generated.strftime("%Y-%m-%dT%H:%M:00%z"), "002")
    for rep in reps or []:
        add("02", rep["id"], rep["type"], rep["identifier"])
    employment_by_id = {}
    for index, employment in enumerate(employments, start=1):
        employment_by_id[int(employment["id"])] = index
        add("03", index, _digits(employment["cpf"])[-11:], employment["name"])
        add("06", index, employment["registration"])
    for code, schedule in sorted((schedules or {}).items()):
        pairs = schedule.get("pairs") or []
        fields = [code, int(schedule.get("durationMinutes") or 0)]
        for pair in pairs:
            fields.extend([str(pair[0]).replace(":", ""), str(pair[1]).replace(":", "")])
        add("04", *fields)
    sequence_by_day = Counter()
    ordered = sorted(punches, key=lambda row: (row["employmentId"], row["occurredAt"]))
    for punch in ordered:
        link = employment_by_id.get(int(punch["employmentId"]))
        if not link:
            raise HRError("Marcação sem vínculo no AEJ")
        occurred = datetime.fromisoformat(punch["occurredAt"])
        day_key = (link, occurred.date().isoformat())
        sequence_by_day[day_key] += 1
        position = sequence_by_day[day_key]
        kind = "E" if position % 2 else "S"
        pair = (position + 1) // 2
        source = "I" if punch.get("source") == "MANUAL" else (
            "T" if punch.get("source") == "CLOCK_CSV" else "O"
        )
        schedule_code = punch.get("scheduleCode", "") if kind == "E" and pair == 1 else ""
        reason = punch.get("reason", "") if source == "I" else ""
        add("05", link, occurred.strftime("%Y-%m-%dT%H:%M:00%z"), punch.get("repId", ""),
            kind, f"{pair:03d}", source, schedule_code, reason)
    add("08", "SIVS SECCOL", "2.2", "1", employer.get("developerDocument", document),
        employer.get("developerName", employer.get("name", "")), employer.get("developerEmail", "rh@sivs.local"))
    trailer_fields = [counts[f"{kind:02d}"] for kind in range(1, 9)]
    lines.append("|".join(("99", *(str(value) for value in trailer_fields))))
    lines.append("ASSINATURA_DIGITAL_EM_ARQUIVO_P7S".ljust(100))
    try:
        return ("\r\n".join(lines) + "\r\n").encode("iso-8859-1")
    except UnicodeEncodeError as exc:
        raise HRError("AEJ contém caractere incompatível com ISO-8859-1") from exc
