import io
from docx import Document

def export_to_docx(text: str) -> bytes:
    """
    Mengonversi teks plain string menjadi file format .docx dan mengembalikannya sebagai bytes.
    Sangat berguna untuk proses download secara langsung dari Streamlit (in-memory)
    tanpa harus menyimpan file secara fisik di storage.
    
    Args:
        text (str): Teks hasil pemrosesan (parafrase).
        
    Returns:
        bytes: Data biner dari file .docx
    """
    document = Document()
    
    # Tambahkan teks ke dokumen. Untuk penanganan yang lebih presisi, kita bisa memisahkan per paragraf.
    paragraphs = text.split('\n')
    for para in paragraphs:
        # Hanya tambahkan paragraf jika ada isinya untuk menghindari baris kosong berlebih
        if para.strip():
            document.add_paragraph(para.strip())
            
    # Simpan ke byte stream (in-memory)
    file_stream = io.BytesIO()
    document.save(file_stream)
    
    # Reset pointer ke awal stream
    file_stream.seek(0)
    
    return file_stream.getvalue()
