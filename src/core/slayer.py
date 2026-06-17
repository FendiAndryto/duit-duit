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

def process_turnitin_pdf(file_bytes: bytes, model_name: str = "gemini-2.5-flash") -> str:
    """
    Memproses file PDF Turnitin utuh menggunakan Gemini Multimodal dengan Smart Rotator.
    
    Args:
        file_bytes (bytes): Konten file PDF dalam bentuk biner.
        model_name (str): Nama model Gemini yang digunakan (default: gemini-2.5-flash).
        
    Returns:
        str: Hasil teks yang sudah direkonstruksi (parafrase pada bagian highlight saja).
        
    Raises:
        Exception: Jika terjadi kesalahan saat pemanggilan API atau semua token habis.
    """
    import tempfile
    import os
    import io
    from PyPDF2 import PdfReader, PdfWriter
    from src.core.database import get_available_key, update_key_success, update_key_exhausted
    
    tmp_path = ""
    client = None
    uploaded_file = None
    
    try:
        # Siasat Jitu: File PDF dari Turnitin seringkali memiliki meta-struktur rumit.
        # Kita cuci (sanitize) PDF-nya dengan PyPDF2
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            writer = PdfWriter()
            
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
        
        prompt = (
            "Berikut adalah dokumen PDF Turnitin. Silakan analisis HANYA pada bagian teks yang memiliki warna highlight/sorotan plagiasi. "
            "Abaikan teks yang bersih (tanpa warna). Hasilkan output berupa daftar teks asli dan hasil parafrasenya sesuai aturan format Markdown yang telah ditetapkan."
        )
        
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.7,
        )
        
        max_retries = 3
        
        for attempt in range(max_retries + 1):
            key_data = get_available_key()
            if not key_data:
                raise RuntimeError("❌ Tidak ada API Key yang aktif atau semua key telah limit. Hubungi Admin!")
            
            api_key_str = key_data['key_string']
            key_id = key_data['id']
            
            try:
                # Inisialisasi client resmi terbaru dengan key yang didapat
                client = genai.Client(api_key=api_key_str)
                
                # Upload file (kita lakukan di dalam loop jika client berganti)
                # (Catatan: jika upload gagal karena kuota, kita ganti key)
                uploaded_file = client.files.upload(file=tmp_path, config={'mime_type': 'application/pdf'})
                
                # Tunggu hingga status file ACTIVE
                while uploaded_file.state.name == "PROCESSING":
                    time.sleep(2)
                    uploaded_file = client.files.get(name=uploaded_file.name)
                    
                if uploaded_file.state.name == "FAILED":
                    raise ValueError("Gagal memproses file PDF di server Google API.")
                    
                time.sleep(4)
                
                file_part = types.Part.from_uri(
                    file_uri=uploaded_file.uri,
                    mime_type='application/pdf'
                )
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=[file_part, prompt],
                    config=config
                )
                
                if not response.text:
                    raise ValueError("API mengembalikan respon kosong.")
                
                # Berhasil! Update token usage.
                update_key_success(key_id)
                return response.text
                
            except APIError as e:
                error_msg = str(e)
                # Bersihkan file dari key yang gagal ini
                if client and uploaded_file:
                    try:
                        client.files.delete(name=uploaded_file.name)
                    except Exception:
                        pass
                
                if ("429" in error_msg or "503" in error_msg or "RESOURCE_EXHAUSTED" in error_msg):
                    logger.warning(f"Google API Error (429/503) pada Key ID {key_id}. Retrying... (Attempt {attempt + 1}/{max_retries})")
                    # Tandai key ini exhausted (usage = 20)
                    update_key_exhausted(key_id)
                    if attempt >= max_retries:
                        raise RuntimeError(f"Gagal setelah {max_retries} percobaan ganti token.")
                    continue # Coba lagi dengan token baru di loop berikutnya
                else:
                    logger.error(f"Google GenAI API Error: {e}")
                    raise RuntimeError(f"Terjadi kesalahan pada layanan Google API: {error_msg}")
                    
            except Exception as e:
                logger.error(f"Unexpected error in generate_content: {e}")
                raise
                
            finally:
                # Bersihkan file dari key yang berhasil ini jika belum dihapus
                if client and uploaded_file:
                    try:
                        client.files.delete(name=uploaded_file.name)
                        uploaded_file = None # reset agar tak didelete dua kali
                    except Exception:
                        pass

    except Exception as e:
        logger.error(f"Unexpected error in process_turnitin_pdf: {e}")
        raise
    finally:
        # Hapus temporary file dari server lokal
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
