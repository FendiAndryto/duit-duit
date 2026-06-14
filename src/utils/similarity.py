import difflib
from typing import Tuple

def add_similarity_badges(markdown_text: str) -> Tuple[str, int, int]:
    """
    Mem-parsing teks keluaran Gemini baris per baris, menghitung persentase kemiripan 
    antara Teks Asli dan Hasil Parafrase menggunakan difflib.SequenceMatcher,
    lalu menyisipkan teks/badge indikator warna.
    
    Mengembalikan:
        - Teks markdown akhir dengan badge.
        - Jumlah kata dari teks asli yang GAGAL (merah, >50%).
        - Jumlah total kata dari teks asli yang diproses Gemini.
    """
    lines = markdown_text.split('\n')
    output_lines = []
    
    asli_text = None
    para_text = None
    red_badge_words = 0
    total_processed_words = 0
    
    for line in lines:
        output_lines.append(line)
        
        # Ekstrak Teks Asli (Plagiat)
        if "Teks Asli" in line:
            parts = line.split(":**", 1)
            if len(parts) > 1:
                # Hapus spasi dan tanda kutip di awal/akhir teks
                asli_text = parts[1].strip(' "')
                
        # Ekstrak Hasil Parafrase
        elif "Hasil Parafrase" in line:
            parts = line.split(":**", 1)
            if len(parts) > 1:
                # Hapus spasi, bintang (bold), dan kutip di awal/akhir teks
                para_text = parts[1].strip(' *"')
                
            # Hitung skor jika pasangan teks sudah lengkap ditemukan
            if asli_text and para_text:
                words_count = len(asli_text.split())
                total_processed_words += words_count
                
                # difflib mengembalikan rasio 0.0 - 1.0. Kalikan 100 agar jadi persentase.
                ratio = difflib.SequenceMatcher(None, asli_text.lower(), para_text.lower()).ratio()
                pct = int(ratio * 100)
                
                # Evaluasi dan buat Badge
                if pct > 50:
                    badge = f"🔴 **{pct}%** (Bahaya, masih mirip!)"
                    red_badge_words += words_count
                elif pct >= 30:
                    badge = f"🟡 **{pct}%** (Riskan, mending putar lagi)"
                else:
                    badge = f"🟢 **{pct}%** (Aman Bos, gaspol!)"
                
                # Sisipkan baris baru setelah "Hasil Parafrase"
                output_lines.append(f"* **Similarity Score:** {badge}\n")
                
                # Reset variabel untuk menangkap pasangan di blok / halaman selanjutnya
                asli_text = None
                para_text = None
                
    return '\n'.join(output_lines), red_badge_words, total_processed_words
