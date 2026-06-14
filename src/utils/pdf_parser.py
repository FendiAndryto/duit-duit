import io
import PyPDF2
import logging

logger = logging.getLogger(__name__)

def count_pdf_words(file_bytes: bytes) -> int:
    """
    Menghitung total kata dari dokumen PDF.
    Jika PDF berupa scan/gambar, fungsi ini akan mengembalikan 0.
    """
    total_words = 0
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            text = page.extract_text()
            if text:
                total_words += len(text.split())
    except Exception as e:
        logger.error(f"Gagal memparsing teks PDF: {e}")
        return 0
    return total_words
