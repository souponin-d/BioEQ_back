import unittest

from be_system.agents.pdf_downloader_agent import PdfDownloaderAgent, MIN_PDF_BYTES


class PdfValidationSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = PdfDownloaderAgent()

    def test_valid_pdf_signature_and_size(self) -> None:
        content = b"%PDF-1.7\n" + (b"0" * MIN_PDF_BYTES)
        reason = self.agent._validate_pdf(200, "application/pdf", content)
        self.assertIsNone(reason)

    def test_html_is_not_treated_as_pdf(self) -> None:
        html = b"<html><head></head><body>error</body></html>"
        reason = self.agent._validate_pdf(200, "text/html", html)
        self.assertEqual(reason, "not_pdf_html")


if __name__ == "__main__":
    unittest.main()
