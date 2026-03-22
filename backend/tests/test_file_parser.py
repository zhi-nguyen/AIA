# backend/tests/test_file_parser.py
"""
Unit tests cho file_parser service.
Test parsing các format: PDF, DOCX, CSV, XLSX
"""

import io
import csv
import struct
import wave
import unittest
from unittest.mock import patch, MagicMock


class TestGetSupportedExtensions(unittest.TestCase):
    """Test danh sách extensions hỗ trợ."""

    def test_returns_sorted_list(self):
        from services.file_parser import get_supported_extensions
        exts = get_supported_extensions()
        self.assertIsInstance(exts, list)
        self.assertEqual(exts, sorted(exts))

    def test_contains_all_formats(self):
        from services.file_parser import get_supported_extensions
        exts = get_supported_extensions()
        for ext in [".pdf", ".docx", ".doc", ".csv", ".xlsx", ".xls"]:
            self.assertIn(ext, exts)


class TestParseFileValidation(unittest.TestCase):
    """Test input validation."""

    def test_unsupported_extension(self):
        from services.file_parser import parse_file
        with self.assertRaises(ValueError) as ctx:
            parse_file("test.txt", b"some content")
        self.assertIn("không được hỗ trợ", str(ctx.exception))

    def test_empty_file(self):
        from services.file_parser import parse_file
        with self.assertRaises(ValueError) as ctx:
            parse_file("test.pdf", b"")
        self.assertIn("rỗng", str(ctx.exception))

    def test_no_extension(self):
        from services.file_parser import parse_file
        with self.assertRaises(ValueError) as ctx:
            parse_file("noext", b"data")
        self.assertIn("không được hỗ trợ", str(ctx.exception))

    def test_returns_dict_structure(self):
        """Test cấu trúc output dict khi parse thành công."""
        from services.file_parser import parse_file

        # Tạo CSV đơn giản
        csv_content = "Name,Age\nAlice,30\nBob,25"
        result = parse_file("test.csv", csv_content.encode("utf-8"))

        self.assertIn("text", result)
        self.assertIn("filename", result)
        self.assertIn("format", result)
        self.assertIn("char_count", result)
        self.assertIn("truncated", result)
        self.assertEqual(result["filename"], "test.csv")
        self.assertEqual(result["format"], ".csv")
        self.assertFalse(result["truncated"])


class TestParseCSV(unittest.TestCase):
    """Test CSV parsing."""

    def test_basic_csv(self):
        from services.file_parser import parse_file
        content = "Name,Age,City\nAlice,30,Hanoi\nBob,25,HCMC"
        result = parse_file("data.csv", content.encode("utf-8"))

        self.assertIn("Name", result["text"])
        self.assertIn("Alice", result["text"])
        self.assertIn("Bob", result["text"])

    def test_csv_with_vietnamese(self):
        from services.file_parser import parse_file
        content = "Họ Tên,Tuổi\nNguyễn Văn A,25\nTrần Thị B,30"
        result = parse_file("test.csv", content.encode("utf-8"))

        self.assertIn("Nguyễn Văn A", result["text"])
        self.assertIn("Trần Thị B", result["text"])

    def test_single_column_csv(self):
        from services.file_parser import parse_file
        content = "Value\n100\n200\n300"
        result = parse_file("test.csv", content.encode("utf-8"))

        self.assertIn("100", result["text"])
        self.assertGreater(result["char_count"], 0)


class TestParsePDF(unittest.TestCase):
    """Test PDF parsing (mocked)."""

    @patch("services.file_parser.PdfReader")
    def test_pdf_with_text(self, mock_reader_cls):
        from services.file_parser import _parse_pdf

        # Mock pages
        page1 = MagicMock()
        page1.extract_text.return_value = "Trang 1 nội dung"
        page2 = MagicMock()
        page2.extract_text.return_value = "Trang 2 nội dung"

        mock_reader = MagicMock()
        mock_reader.pages = [page1, page2]
        mock_reader_cls.return_value = mock_reader

        result = _parse_pdf(b"fake_pdf_bytes")
        self.assertIn("Trang 1 nội dung", result)
        self.assertIn("Trang 2 nội dung", result)

    @patch("services.file_parser.PdfReader")
    def test_pdf_empty_pages(self, mock_reader_cls):
        from services.file_parser import _parse_pdf

        page = MagicMock()
        page.extract_text.return_value = ""

        mock_reader = MagicMock()
        mock_reader.pages = [page]
        mock_reader_cls.return_value = mock_reader

        result = _parse_pdf(b"fake")
        self.assertEqual(result, "")


class TestParseDOCX(unittest.TestCase):
    """Test DOCX parsing (mocked)."""

    @patch("services.file_parser.Document")
    def test_docx_paragraphs(self, mock_doc_cls):
        from services.file_parser import _parse_docx

        para1 = MagicMock()
        para1.text = "Đoạn 1"
        para2 = MagicMock()
        para2.text = "Đoạn 2"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2]
        mock_doc.tables = []
        mock_doc_cls.return_value = mock_doc

        result = _parse_docx(b"fake_docx")
        self.assertIn("Đoạn 1", result)
        self.assertIn("Đoạn 2", result)

    @patch("services.file_parser.Document")
    def test_docx_with_table(self, mock_doc_cls):
        from services.file_parser import _parse_docx

        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        # Mock table
        cell1 = MagicMock()
        cell1.text = "Cột A"
        cell2 = MagicMock()
        cell2.text = "Cột B"

        row = MagicMock()
        row.cells = [cell1, cell2]

        table = MagicMock()
        table.rows = [row]
        mock_doc.tables = [table]
        mock_doc_cls.return_value = mock_doc

        result = _parse_docx(b"fake")
        self.assertIn("Cột A", result)
        self.assertIn("Cột B", result)


class TestParseXLSX(unittest.TestCase):
    """Test XLSX parsing (mocked)."""

    @patch("services.file_parser.load_workbook")
    def test_xlsx_basic(self, mock_load):
        from services.file_parser import _parse_xlsx

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]

        mock_ws = MagicMock()
        mock_ws.iter_rows.return_value = [
            ("Name", "Age"),
            ("Alice", 30),
            ("Bob", 25),
        ]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        mock_load.return_value = mock_wb

        result = _parse_xlsx(b"fake_xlsx")
        self.assertIn("Sheet1", result)
        self.assertIn("Name", result)
        self.assertIn("Alice", result)

    @patch("services.file_parser.load_workbook")
    def test_xlsx_multiple_sheets(self, mock_load):
        from services.file_parser import _parse_xlsx

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Data", "Summary"]

        mock_ws1 = MagicMock()
        mock_ws1.iter_rows.return_value = [("A", "B")]
        mock_ws2 = MagicMock()
        mock_ws2.iter_rows.return_value = [("X", "Y")]

        def getitem(name):
            return mock_ws1 if name == "Data" else mock_ws2

        mock_wb.__getitem__ = MagicMock(side_effect=getitem)
        mock_load.return_value = mock_wb

        result = _parse_xlsx(b"fake")
        self.assertIn("Data", result)
        self.assertIn("Summary", result)


class TestTextTruncation(unittest.TestCase):
    """Test truncation behavior."""

    def test_long_csv_gets_truncated(self):
        from services.file_parser import parse_file, MAX_TEXT_LENGTH

        # Tạo CSV rất dài
        rows = ["Col1,Col2"]
        for i in range(10000):
            rows.append(f"value_{i}_{'x' * 50},data_{i}_{'y' * 50}")
        content = "\n".join(rows)

        result = parse_file("big.csv", content.encode("utf-8"))
        # Kiểm tra truncation xảy ra
        self.assertTrue(result["char_count"] <= MAX_TEXT_LENGTH + 100)  # buffer cho thông báo cắt


class TestParseFileIntegration(unittest.TestCase):
    """Test parse_file entry point."""

    def test_csv_via_parse_file(self):
        from services.file_parser import parse_file
        result = parse_file("test.csv", b"A,B\n1,2")
        self.assertEqual(result["format"], ".csv")
        self.assertGreater(len(result["text"]), 0)

    @patch("services.file_parser._parse_pdf")
    def test_pdf_via_parse_file(self, mock_parse):
        from services.file_parser import parse_file
        mock_parse.return_value = "PDF content here"
        result = parse_file("report.pdf", b"fake_pdf")
        self.assertEqual(result["format"], ".pdf")
        self.assertEqual(result["filename"], "report.pdf")
        self.assertIn("PDF content here", result["text"])

    @patch("services.file_parser._parse_docx")
    def test_docx_via_parse_file(self, mock_parse):
        from services.file_parser import parse_file
        mock_parse.return_value = "DOCX content here"
        result = parse_file("doc.docx", b"fake_docx")
        self.assertEqual(result["format"], ".docx")

    @patch("services.file_parser._parse_xlsx")
    def test_xlsx_via_parse_file(self, mock_parse):
        from services.file_parser import parse_file
        mock_parse.return_value = "XLSX content here"
        result = parse_file("data.xlsx", b"fake_xlsx")
        self.assertEqual(result["format"], ".xlsx")

    @patch("services.file_parser._parse_xlsx")
    def test_xls_via_parse_file(self, mock_parse):
        from services.file_parser import parse_file
        mock_parse.return_value = "XLS content"
        result = parse_file("old.xls", b"fake_xls")
        self.assertEqual(result["format"], ".xls")

    @patch("services.file_parser._parse_docx")
    def test_doc_via_parse_file(self, mock_parse):
        from services.file_parser import parse_file
        mock_parse.return_value = "DOC content"
        result = parse_file("old.doc", b"fake_doc")
        self.assertEqual(result["format"], ".doc")

    @patch("services.file_parser._parse_pdf")
    def test_parse_error_raises_valueerror(self, mock_parse):
        from services.file_parser import parse_file
        mock_parse.side_effect = Exception("corrupt file")
        with self.assertRaises(ValueError) as ctx:
            parse_file("bad.pdf", b"corrupt")
        self.assertIn("Không thể đọc file", str(ctx.exception))

    @patch("services.file_parser._parse_pdf")
    def test_empty_extraction_raises_valueerror(self, mock_parse):
        from services.file_parser import parse_file
        mock_parse.return_value = "   "
        with self.assertRaises(ValueError) as ctx:
            parse_file("empty.pdf", b"data")
        self.assertIn("Không trích xuất được", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
