# backend/services/file_parser.py
"""
file_parser.py - File Parsing Service
Hỗ trợ: PDF, DOCX, DOC, CSV, XLSX, XLS
Trích xuất text để AI phân tích và trả lời câu hỏi
"""

import io
import csv
from typing import Optional

# Max characters to keep (tránh quá tải LLM context)
MAX_TEXT_LENGTH = 50000

# Supported extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".csv", ".xlsx", ".xls"}


def get_supported_extensions() -> list[str]:
    """Trả về danh sách extensions hỗ trợ."""
    return sorted(SUPPORTED_EXTENSIONS)


def _parse_pdf(file_bytes: bytes) -> str:
    """Trích xuất text từ file PDF."""
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append(f"--- Trang {i + 1} ---\n{text.strip()}")
    return "\n\n".join(pages)


def _parse_docx(file_bytes: bytes) -> str:
    """Trích xuất text từ file DOCX."""
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    paragraphs: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text.strip())

    # Cũng đọc tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)

    return "\n".join(paragraphs)


def _parse_csv(file_bytes: bytes) -> str:
    """Trích xuất text từ file CSV."""
    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))

    rows: list[str] = []
    for i, row in enumerate(reader):
        if i == 0:
            # Header row
            rows.append("Cột: " + " | ".join(row))
        else:
            rows.append(" | ".join(row))
        if i > 5000:  # Giới hạn số dòng
            rows.append(f"... (đã cắt, tổng cộng hơn {i} dòng)")
            break

    return "\n".join(rows)


def _parse_xlsx(file_bytes: bytes) -> str:
    """Trích xuất text từ file XLSX/XLS."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    sheets: list[str] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows: list[str] = []
        row_count = 0

        for row in ws.iter_rows(values_only=True):
            cell_values = [str(c) if c is not None else "" for c in row]
            if any(v.strip() for v in cell_values):
                rows.append(" | ".join(cell_values))
                row_count += 1
            if row_count > 5000:
                rows.append(f"... (đã cắt, hơn {row_count} dòng)")
                break

        if rows:
            sheets.append(f"=== Sheet: {sheet_name} ===\n" + "\n".join(rows))

    wb.close()
    return "\n\n".join(sheets)


def parse_file(filename: str, file_bytes: bytes) -> dict:
    """
    Parse file và trích xuất text.

    Args:
        filename: Tên file (dùng để xác định format)
        file_bytes: Nội dung file dạng bytes

    Returns:
        dict: {
            "text": str,         # Nội dung text đã trích xuất
            "filename": str,     # Tên file
            "format": str,       # Extension
            "char_count": int,   # Số ký tự
            "truncated": bool,   # Đã cắt hay chưa
        }
    """
    # Xác định extension
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Định dạng '{ext}' không được hỗ trợ. "
            f"Hỗ trợ: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if not file_bytes:
        raise ValueError("File rỗng")

    # Parse theo format
    try:
        if ext == ".pdf":
            text = _parse_pdf(file_bytes)
        elif ext in (".docx", ".doc"):
            text = _parse_docx(file_bytes)
        elif ext == ".csv":
            text = _parse_csv(file_bytes)
        elif ext in (".xlsx", ".xls"):
            text = _parse_xlsx(file_bytes)
        else:
            text = ""
    except Exception as e:
        raise ValueError(f"Không thể đọc file: {str(e)}")

    if not text.strip():
        raise ValueError("Không trích xuất được nội dung từ file")

    # Truncate nếu quá dài
    truncated = False
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "\n\n... (nội dung đã được cắt bớt do quá dài)"
        truncated = True

    return {
        "text": text.strip(),
        "filename": filename,
        "format": ext,
        "char_count": len(text),
        "truncated": truncated,
    }
