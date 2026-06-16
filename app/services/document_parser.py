"""
GNONE — Multi-Format Document Parser

Supports PDF (via PyPDF2), TXT, MD, and CSV parsing with metadata extraction.
"""

import csv
import logging
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ParsedDocument:
    filename: str
    content: str
    metadata: dict = field(default_factory=dict)
    chunks: list[str] = field(default_factory=list)
    page_count: int = 0
    char_count: int = 0
    word_count: int = 0


class DocumentParser:
    """
    Parses multiple document formats and extracts text content with metadata.
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}

    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/vnd.ms-excel",
    }

    def parse_file(self, filepath: str | Path) -> ParsedDocument:
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Document not found: {filepath}")

        ext = filepath.suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            mime_type, _ = mimetypes.guess_type(str(filepath))
            if mime_type not in self.SUPPORTED_MIME_TYPES:
                raise ValueError(
                    f"Unsupported file format: {ext} (detected MIME: {mime_type})"
                )

        content = ""
        metadata: dict = {
            "filename": filepath.name,
            "filepath": str(filepath),
            "extension": ext,
            "file_size_bytes": filepath.stat().st_size,
        }
        page_count = 0

        try:
            if ext == ".pdf":
                content, page_count = self._parse_pdf(filepath)
            elif ext == ".txt":
                content = self._parse_txt(filepath)
            elif ext == ".md":
                content = self._parse_md(filepath)
            elif ext == ".csv":
                content = self._parse_csv(filepath)
        except Exception as exc:
            logger.error("Failed to parse %s: %s", filepath, exc)
            raise

        metadata["page_count"] = page_count
        metadata["char_count"] = len(content)
        metadata["word_count"] = len(content.split())

        return ParsedDocument(
            filename=filepath.name,
            content=content,
            metadata=metadata,
            page_count=page_count,
            char_count=metadata["char_count"],
            word_count=metadata["word_count"],
        )

    def parse_bytes(self, data: bytes, filename: str) -> ParsedDocument:
        ext = Path(filename).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {ext}")

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            return self.parse_file(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _parse_pdf(self, filepath: Path) -> tuple[str, int]:
        try:
            import PyPDF2
        except ImportError:
            raise ImportError(
                "PyPDF2 is required for PDF parsing. Install with: pip install PyPDF2"
            )

        text_parts = []
        page_count = 0

        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            page_count = len(reader.pages)

            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(
                        f"\n--- Page {page_num + 1} ---\n{page_text.strip()}"
                    )

        content = "\n".join(text_parts)
        return content, page_count

    def _parse_txt(self, filepath: Path) -> str:
        encodings = ["utf-8", "latin-1", "cp1252", "ascii"]
        for encoding in encodings:
            try:
                with open(filepath, encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Unable to decode text file with any supported encoding: {filepath}")

    def _parse_md(self, filepath: Path) -> str:
        return self._parse_txt(filepath)

    def _parse_csv(self, filepath: Path) -> str:
        encodings = ["utf-8", "latin-1", "cp1252"]
        for encoding in encodings:
            try:
                with open(filepath, encoding=encoding, newline="") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if not rows:
                        return ""

                    headers = rows[0].keys()
                    text_parts = []
                    for i, row in enumerate(rows):
                        row_text = " | ".join(
                            f"{h}: {row.get(h, '')}" for h in headers
                        )
                        text_parts.append(f"Row {i + 1}: {row_text}")

                    return "\n".join(text_parts)
            except UnicodeDecodeError:
                continue
            except csv.Error as exc:
                raise ValueError(f"CSV parsing error: {exc}")

        raise ValueError(f"Unable to decode CSV file: {filepath}")


document_parser = DocumentParser()
