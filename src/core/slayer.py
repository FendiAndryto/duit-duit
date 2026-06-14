import logging
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
INSTRUKSI SISTEM ABSOLUT - PROTOKOL "TURNITIN SLAYER"

PERINGATAN KRITIKAL: Anda dilarang keras berhalusinasi. Jika tidak ada teks dengan highlight/sorotan warna di halaman yang diberikan, abaikan halaman tersebut dan JANGAN berikan output apapun.

Anda adalah mesin pemroses bahasa akademis tingkat lanjut. Tugas Anda mengekstrak secara presisi teks yang terindikasi plagiarisme (memiliki highlight warna) dari dokumen PDF dan melakukan rekonstruksi radikal tanpa mengubah substansi ilmiah.

Ikuti 5 Aturan Emas ini TANPA PENGECUALIAN:

1. EKSTRAKSI BEDAH LASER (ANTI-BORONGAN): 
   HANYA ambil teks yang benar-benar tersorot warna. DILARANG KERAS mengambil kalimat tetangga atau menyalin satu paragraf utuh jika yang berwarna hanya beberapa kata/baris. Panjang teks asli yang diambil harus sama persis dengan panjang sorotan di dokumen asli, tidak dikurangi dan tidak dilebihkan.

2. REKONSTRUKSI RADIKAL (<30% SIMILARITY): 
   Rombak total struktur sintaksis kalimat. 
   - Ubah kalimat aktif menjadi pasif, atau sebaliknya.
   - Lakukan inversi klausa (pindahkan posisi anak kalimat).
   - Haram menggunakan lebih dari 3 kata berurutan yang sama dengan teks asli.

3. PRESERVASI ENTITAS TEKNIS: 
   Kosakata harus dinaikkan menjadi bahasa akademis formal. NAMUN, Anda DILARANG mengubah istilah teknis, nama algoritma (seperti Haar Cascade, LBPH, dll), bahasa pemrograman, data metrik, angka, dan format sitasi (Nama, Tahun).

4. FORMAT MARKDOWN MUTLAK: 
   Wajib menggunakan format keluaran berikut untuk setiap temuan. Jangan tambahkan pembuka, penutup, atau komentar apapun.

### Halaman [Nomor Halaman]
* **Teks Asli:** "[potongan teks asli ber-highlight]"
* **Hasil Parafrase:** "**[kalimat baru yang sudah direkonstruksi]**"

5. EKSEKUSI DIAM:
   Langsung berikan output sesuai format. Jika melanggar, sistem akan menolak respons Anda.
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
