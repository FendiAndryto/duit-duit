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

def process_turnitin_pdf(file_bytes: bytes, api_key: str) -> str:
    """
    Memproses file PDF Turnitin utuh menggunakan Gemini Multimodal.
    
    Args:
        file_bytes (bytes): Konten file PDF dalam bentuk biner.
        api_key (str): API Key untuk Google GenAI SDK.
        
    Returns:
        str: Hasil teks yang sudah direkonstruksi (parafrase pada bagian highlight saja).
        
    Raises:
        Exception: Jika terjadi kesalahan saat pemanggilan API atau kuota habis.
    """
    try:
        # Inisialisasi client resmi terbaru
        client = genai.Client(api_key=api_key)
        model_name = "gemini-2.5-flash"
        
        # Siapkan multimodal payload
        pdf_part = types.Part.from_bytes(
            data=file_bytes,
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
                    contents=[pdf_part, prompt],
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
