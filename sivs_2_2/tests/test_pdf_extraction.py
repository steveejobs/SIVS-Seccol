import os
import subprocess
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pdf_extraction import PDFSandboxError, _minimal_environment, extract_pdf_pages


class PDFExtractionSandboxTests(unittest.TestCase):
    @staticmethod
    def sample_pdf():
        output = BytesIO()
        document = canvas.Canvas(output)
        document.drawString(72, 760, "Edital seguro para teste")
        document.save()
        return output.getvalue()

    def test_extracts_text_in_an_isolated_worker(self):
        pages = extract_pdf_pages(self.sample_pdf(), "edital-teste.pdf")
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["document"], "edital-teste.pdf")
        self.assertIn("Edital seguro", pages[0]["text"])
        self.assertNotIn("_images", pages[0])

    def test_rejects_non_pdf_before_starting_worker(self):
        with self.assertRaises(PDFSandboxError):
            extract_pdf_pages(b"arquivo arbitrario", "arquivo.pdf")

    def test_timeout_fails_closed(self):
        with patch("pdf_extraction.subprocess.run", side_effect=subprocess.TimeoutExpired("pdf", 1)):
            with self.assertRaisesRegex(PDFSandboxError, "tempo seguro"):
                extract_pdf_pages(self.sample_pdf(), "lento.pdf", timeout=1)

    def test_worker_environment_does_not_inherit_application_secrets(self):
        with patch.dict(os.environ, {
            "OPENROUTER_API_KEY": "segredo",
            "SIVS_FISCAL_MASTER_KEY": "segredo",
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        }):
            environment = _minimal_environment(os.getcwd())
        self.assertNotIn("OPENROUTER_API_KEY", environment)
        self.assertNotIn("SIVS_FISCAL_MASTER_KEY", environment)


if __name__ == "__main__":
    unittest.main()
