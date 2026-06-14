import logging
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
Dilarang keras melakukan halusinasi konteks dengan menuliskan ulang kalimat yang tidak memiliki highlight warna di PDF. Jika melanggar, output lu tidak akan bisa di-parse oleh sistem!

Kamu adalah AI asisten akademik profesional berbahasa Indonesia. Tugas utamamu adalah "Turnitin Slayer".
Pengguna akan memberikan dokumen PDF hasil pemeriksaan Turnitin. Dokumen ini berisi teks asli dan teks yang ditandai dengan sorotan warna (highlight seperti merah, biru, hijau, ungu, dll.) yang menunjukkan indikasi plagiarisme.

Aturan Emas (Golden Rules) yang WAJIB kamu ikuti secara absolut:
1. ISOLASI MUTLAK: Lu wajib melakukan ekstraksi secara presisi. Ambil HANYA kata yang ber-highlight. Teks Asli yang lu cantumkan di list MAKSIMAL berisi 10-15 kata saja! Jangan bawa satu paragraf utuh! Jika dalam satu paragraf cuma ada 1 baris yang berwarna, maka 'Teks Asli' yang lu ambil HANYA 1 baris itu saja!
2. LARANGAN BORONGAN: Dilarang keras menyertakan kalimat tetangga di dalam paragraf yang sama jika kalimat tersebut tidak berwarna. Jangan pernah mengambil satu paragraf utuh kalau yang plagiat cuma beberapa kata di dalamnya.
3. REKONSTRUKSI EKSTREM (HARAM STRUKTUR SAMA): Wajib membalikkan struktur kalimat secara total. Jika kalimat asli berbentuk AKTIF, ubah menjadi PASIF (dan sebaliknya). Gunakan teknik inversi klausa: pindahkan anak kalimat atau bagian akhir kalimat asli ke bagian paling depan di kalimat baru. DILARANG KERAS menggunakan lebih dari 3 kata berurutan yang sama persis dengan teks asli. Targetkan hasil memiliki tingkat kemiripan struktur (lexical similarity) DI BAWAH 30%.
4. KOSAKATA & SUBSTANSI ILMIAH: Gunakan kosakata akademis formal tingkat lanjut yang setara, tapi bentuk kalimatnya harus berubah total. PENTING: Istilah teknis, nama algoritma, data angka, rumus, dan format sitasi (seperti: Nama, Tahun) HARUS tetap dipertahankan dengan akurat dan jangan diubah maknanya.
5. KONSISTENSI LIST OUTPUT: Tampilkan di output Markdown bener-bener hanya potongan teks yang ber-highlight tersebut beserta hasil parafrase radikalnya. Wajib menggunakan format Markdown persis seperti contoh di bawah ini untuk setiap temuan:

### Halaman [Nomor Halaman]
* **Teks Asli (Plagiat):** "[kalimat asli yang kena stabilo di pdf]"
* **Hasil Parafrase:** "**[kalimat baru yang sudah rapi dan lolos turnitin]**"

6. KETEGASAN: Jangan tambahkan basa-basi, salam, atau komentar apapun di luar format di atas. Pastikan hasil parafrase di-bold menggunakan double asterisk.
"""

def process_turnitin_pdf(file_bytes: bytes, api_key: str, model_name: str = "gemini-2.5-flash") -> str:
    """
    Memproses file PDF Turnitin utuh menggunakan Gemini Multimodal.
    
    Args:
        file_bytes (bytes): Konten file PDF dalam bentuk biner.
        api_key (str): API Key untuk Google GenAI SDK.
        model_name (str): Nama model Gemini yang digunakan (default: gemini-2.5-flash).
        
    Returns:
        str: Hasil teks yang sudah direkonstruksi (parafrase pada bagian highlight saja).
        
    Raises:
        Exception: Jika terjadi kesalahan saat pemanggilan API atau kuota habis.
    """
    import tempfile
    import os
    import io
    from PyPDF2 import PdfReader, PdfWriter
    
    tmp_path = ""
    uploaded_file = None
    client = None
    
    try:
        # Inisialisasi client resmi terbaru
        client = genai.Client(api_key=api_key)
        
        # Siasat Jitu: File PDF dari Turnitin seringkali memiliki meta-struktur rumit, 
        # DRM, atau objek XFA/watermark yang ditolak mentah-mentah oleh Google API 
        # (sehingga muncul pesan 'Request contains an invalid argument').
        # Solusi: Kita cuci (sanitize) PDF-nya dengan PyPDF2 dengan cara merekonstruksi
        # halamannya dari awal sebelum dikirim ke Google.
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            writer = PdfWriter()
            
            # Pindahkan seluruh halaman ke writer baru untuk membuang anomali struktur
            for page in reader.pages:
                writer.add_page(page)
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                writer.write(tmp_file)
                tmp_path = tmp_file.name
        except Exception as e:
            logger.warning(f"PyPDF2 gagal membersihkan PDF, mencoba mode mentah (raw): {e}")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_bytes)
                tmp_path = tmp_file.name
            
        uploaded_file = client.files.upload(file=tmp_path, config={'mime_type': 'application/pdf'})
        
        # Tunggu hingga status file ACTIVE (selesai diproses oleh Google)
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = client.files.get(name=uploaded_file.name)
            
        if uploaded_file.state.name == "FAILED":
            raise ValueError("Gagal memproses file PDF di server Google API.")
            
        # Beri jeda tambahan 4 detik agar file benar-benar siap dan tersinkronisasi di backend Google
        # sebelum dikirim ke inference model untuk menghindari error 400 INVALID_ARGUMENT
        time.sleep(4)
        
        # Gunakan types.Part.from_uri secara eksplisit agar payload JSON API valid
        file_part = types.Part.from_uri(
            file_uri=uploaded_file.uri,
            mime_type='application/pdf'
        )
        
        prompt = (
            "Berikut adalah dokumen PDF Turnitin. Silakan analisis warna highlight-nya "
            "dan hasilkan teks dokumen penuh sesuai dengan aturan sistem yang telah diberikan."
        )
        
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
        )
        
        max_retries = 4
        base_delay = 5
        
        for attempt in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[file_part, prompt],
                    config=config
                )
                
                if not response.text:
                    raise ValueError("API mengembalikan respon kosong.")
                    
                return response.text
                
            except APIError as e:
                error_msg = str(e)
                # Cek jika error 429 atau 503
                if ("429" in error_msg or "503" in error_msg) and attempt < max_retries:
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning(f"Google API Error (429/503). Retrying in {sleep_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Google GenAI API Error: {e}")
                    raise RuntimeError(f"Terjadi kesalahan pada layanan Google API: {error_msg}")
            except Exception as e:
                logger.error(f"Unexpected error in generate_content: {e}")
                raise
    except Exception as e:
        logger.error(f"Unexpected error in process_turnitin_pdf: {e}")
        raise
    finally:
        # Selalu bersihkan file dari storage Google API setelah selesai (Storage Limit: 20GB gratis)
        if client and uploaded_file:
            try:
                client.files.delete(name=uploaded_file.name)
            except Exception as cleanup_e:
                logger.error(f"Gagal membersihkan file dari Google API: {cleanup_e}")
                
        # Hapus temporary file dari server lokal
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
