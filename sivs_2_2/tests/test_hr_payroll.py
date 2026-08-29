import unittest
from datetime import datetime, timezone

from hr_payroll import (
    HRError, build_aej, calculate_inss_2026, calculate_irrf_2026,
    calculate_monthly_payroll, crc16_kermit, parse_afd, parse_clock_csv,
    summarize_timesheet,
)


def fixed_record(prefix, length):
    row = list(" " * (length - 4))
    row[:len(prefix)] = prefix
    body = "".join(row)
    return body + crc16_kermit(body.encode("iso-8859-1"))


def afd_fixture():
    header = list(" " * 298)
    header[0:10] = "0000000001"
    header[10] = "1"
    header[11:25] = "12345678000199"
    header[39:45] = "SECCOL"
    header[189:206] = "99999999999999999"
    header[206:216] = "2026-08-01"
    header[216:226] = "2026-08-31"
    header[226:250] = "2026-08-31T20:00:00-0300"
    header[250:253] = "004"
    body = "".join(header)
    line1 = body + crc16_kermit(body.encode("iso-8859-1"))
    line3 = fixed_record("0000000013" + "2026-08-03T08:00:00-0300" + "012345678901", 50)
    trailer = "999999999" + "000000000" + "000000001" + "000000000" * 4 + "9"
    return ("\r\n".join((line1, line3, trailer)) + "\r\n").encode("iso-8859-1")


class HRPayrollTests(unittest.TestCase):
    def test_crc_kermit_matches_official_vector(self):
        self.assertEqual(crc16_kermit(b"123456789"), "2189")

    def test_parses_afd_004_and_preserves_nsr(self):
        parsed = parse_afd(afd_fixture())
        self.assertEqual(parsed["format"], "AFD004")
        self.assertEqual(parsed["punches"][0]["nsr"], 1)
        self.assertEqual(parsed["punches"][0]["cpf"], "12345678901")
        self.assertEqual(parsed["warnings"], [])

    def test_afd_rejects_trailer_count_divergence(self):
        content = afd_fixture().replace(b"000000001", b"000000002", 1)
        with self.assertRaises(HRError):
            parse_afd(content)

    def test_clock_csv_accepts_common_export_columns(self):
        parsed = parse_clock_csv("CPF;Data;Hora;NSR\n12345678901;03/08/2026;08:00;15\n".encode())
        self.assertEqual(parsed["punches"][0]["nsr"], "15")
        self.assertTrue(parsed["punches"][0]["occurredAt"].endswith("-03:00"))

    def test_timesheet_pairs_punches_and_blocks_odd_day(self):
        even = [{"occurredAt": f"2026-08-03T{value}:00-03:00"} for value in ("08:00", "12:00", "13:00", "18:00")]
        result = summarize_timesheet(even, "2026-08", {"1": 480})
        self.assertEqual(result["totals"]["workedMinutes"], 540)
        self.assertEqual(result["totals"]["overtimeMinutes"], 60)
        self.assertTrue(result["ready"])
        result = summarize_timesheet(even[:-1], "2026-08", {"1": 480})
        self.assertFalse(result["ready"])
        self.assertIn("ODD_PUNCH_COUNT", result["days"][0]["issues"])

    def test_timesheet_without_any_clock_data_is_not_ready_to_close(self):
        result = summarize_timesheet([], "2026-08", {"1": 480})
        self.assertFalse(result["ready"])
        self.assertIn("NO_PUNCHES", result["issues"])

    def test_reviewed_leave_date_does_not_become_payroll_absence(self):
        punches = [{"occurredAt": f"2026-08-03T{value}:00-03:00"}
                   for value in ("08:00", "12:00", "13:00", "17:00")]
        result = summarize_timesheet(
            punches, "2026-08", {"1": 480}, through_date=datetime(2026, 8, 17).date(),
            excused_dates={"2026-08-10", "2026-08-17"},
        )
        self.assertEqual(result["totals"]["absenceMinutes"], 0)
        excused = [day for day in result["days"] if day["excused"]]
        self.assertEqual(len(excused), 2)
        self.assertTrue(all(day["contractualExpectedMinutes"] == 480 for day in excused))

    def test_inss_2026_is_progressive_and_capped(self):
        self.assertEqual(calculate_inss_2026(500_000), 50_151)
        self.assertEqual(calculate_inss_2026(2_000_000), calculate_inss_2026(847_555))

    def test_irrf_2026_applies_zero_reduction_up_to_five_thousand(self):
        tax = calculate_irrf_2026(500_000, calculate_inss_2026(500_000), 0)
        self.assertEqual(tax["taxCents"], 0)
        self.assertIn(tax["deductionMethod"], {"LEGAL", "SIMPLIFIED"})

    def test_monthly_payroll_calculates_overtime_taxes_fgts_and_net(self):
        payroll = calculate_monthly_payroll(
            salary_cents=500_000, monthly_divisor=220, dependents=0,
            overtime_minutes=60, absence_minutes=0,
        )
        self.assertEqual(payroll["overtimeCents"], 3_409)
        self.assertGreater(payroll["inssCents"], 0)
        self.assertGreater(payroll["fgtsCents"], 0)
        self.assertEqual(payroll["earningsCents"] - payroll["deductionsCents"], payroll["netCents"])

    def test_aej_002_contains_links_marks_schedule_and_trailer(self):
        content = build_aej(
            employer={"document": "12345678000199", "name": "SECCOL"},
            employments=[{"id": 10, "cpf": "12345678901", "name": "Pessoa", "registration": "MAT-1"}],
            schedules={"PADRAO": {"durationMinutes": 480, "pairs": [["08:00", "12:00"], ["13:00", "17:00"]]}},
            punches=[
                {"employmentId": 10, "occurredAt": "2026-08-03T08:00:00-03:00", "scheduleCode": "PADRAO"},
                {"employmentId": 10, "occurredAt": "2026-08-03T17:00:00-03:00"},
            ], period_start="2026-08-01", period_end="2026-08-31",
            generated_at=datetime(2026, 8, 31, 20, tzinfo=timezone.utc),
        ).decode("iso-8859-1")
        self.assertIn("01|1|12345678000199", content)
        self.assertIn("03|1|12345678901|Pessoa", content)
        self.assertIn("05|1|2026-08-03T08:00:00-0300||E|001|O|PADRAO|", content)
        self.assertIn("99|1|0|1|1|2|1|0|1", content)


if __name__ == "__main__":
    unittest.main()
