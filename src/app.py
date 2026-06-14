import sys
import os
import streamlit as st
import logging

# Menambahkan root folder project ke sys.path untuk mencegah ModuleNotFoundError
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import get_api_key
from src.core.slayer import process_turnitin_pdf
from src.utils.doc_handler import export_to_docx
from src.utils.similarity import add_similarity_badges

# Setup dasar Streamlit
st.set_page_config(
    page_title="Turnitin Slayer",
    page_icon="🛡️",
    layout="wide"
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Inisialisasi State Management ---
if "processed_text" not in st.session_state:
    st.session_state.processed_text = None
if "prediction_info" not in st.session_state:
    st.session_state.prediction_info = None

def main():
    st.title("🛡️ Turnitin Slayer")
    st.markdown(
        "Aplikasi otomasi parafrase dokumen akademik dari PDF Turnitin. "
        "Sistem ini hanya akan mengubah bagian yang ter-*highlight* warna tanpa mengubah format, "
        "sitasi, atau teks asli yang bersih."
    )
    
    # --- Sidebar Configuration ---
    with st.sidebar:
        st.header("⚙️ Konfigurasi")
        
        st.subheader("🤖 Model Selector")
        model_options = {
            "Gemini 1.5 Flash (Hemat)": "gemini-1.5-flash",
            "Gemini 2.5 Flash (Cepat)": "gemini-2.5-flash",
            "Gemini 1.5 Pro (Paling Pintar)": "gemini-1.5-pro"
        }
        selected_model_display = st.selectbox(
            "Pilih Senjata AI", 
            options=list(model_options.keys()),
            index=1 # Default ke Gemini 2.5 Flash
        )
        selected_model = model_options[selected_model_display]
        
        st.divider()
        
        st.markdown("Masukkan API Key jika tidak menggunakan default `.env` server.")
        override_api_key = st.text_input(
            "API Key (Opsional)", 
            type="password", 
            help="Kosongkan jika server sudah di-setup dengan .env"
        )
        st.divider()
        st.subheader("📉 Plagiarism Predictor")
        initial_plagiarism_pct = st.number_input("Persentase Plagiasi Awal (%)", min_value=0, max_value=100, value=20)
        
        st.divider()
        st.info("Batas Maksimal File: 15MB\n\nFormat: Hanya PDF")

    # --- Main Area: Uploader ---
    uploaded_file = st.file_uploader("Upload Dokumen PDF Turnitin Anda", type=["pdf"])
    
    if uploaded_file is not None:
        # Validasi ukuran (contoh: 15MB = 15 * 1024 * 1024 bytes)
        file_size_mb = uploaded_file.size / (1024 * 1024)
        if file_size_mb > 15:
            st.error(f"❌ Ukuran file terlalu besar! ({file_size_mb:.2f} MB). Maksimal 15 MB.")
            return
            
        st.success(f"File **{uploaded_file.name}** ({file_size_mb:.2f} MB) siap diproses!")
        
        # Tombol Proses
        if st.button("🚀 Mulai Proses Parafrase", type="primary"):
            try:
                # Dapatkan API Key
                api_key = get_api_key(override_key=override_api_key if override_api_key else None)
                
                # Baca file sebagai bytes
                file_bytes = uploaded_file.getvalue()
                
                # Gunakan st.spinner untuk operasi asynchronous/blocking yang lama
                with st.spinner("Sistem sedang menganalisis warna... (Ini mungkin memakan waktu puluhan detik)"):
                    result_text = process_turnitin_pdf(file_bytes=file_bytes, api_key=api_key, model_name=selected_model)
                    final_result, red_badge_words, total_processed_words = add_similarity_badges(result_text)
                    
                    # Tampilkan DEBUG info sementara
                    st.warning(f"🛠️ DEBUG INFO: Total Kata Diproses = {total_processed_words} | Kata Gagal (Merah) = {red_badge_words}")
                    
                    # Kalkulasi Prediksi Turnitin
                    if total_processed_words > 0:
                        predicted_plagiarism = initial_plagiarism_pct * (red_badge_words / total_processed_words)
                        predicted_plagiarism = max(0, predicted_plagiarism) # Jangan sampai minus
                        st.session_state.prediction_info = {
                            "show": True,
                            "new_score": predicted_plagiarism,
                            "old_score": initial_plagiarism_pct,
                            "drop": initial_plagiarism_pct - predicted_plagiarism
                        }
                    else:
                        st.session_state.prediction_info = {
                            "show": False,
                            "warning": "Gagal memprediksi skor: Tidak ada teks yang diproses oleh Gemini."
                        }
                    
                    # Simpan hasil ke session_state agar tidak hilang
                    st.session_state.processed_text = final_result
                    
            except ValueError as ve:
                st.error(f"⚠️ Konfigurasi Error: {ve}")
            except RuntimeError as re:
                st.error(f"🔌 API Error: {re}")
            except Exception as e:
                logger.error(f"Error tidak terduga: {e}", exc_info=True)
                st.error(f"🐞 Terjadi kesalahan sistem: {e}")

    # --- Output & Export Area ---
    if st.session_state.processed_text:
        st.divider()
        st.subheader("📄 Hasil Rekonstruksi Dokumen")
        
        # --- Tampilkan Predictor ---
        if st.session_state.prediction_info:
            if st.session_state.prediction_info["show"]:
                new_score = st.session_state.prediction_info["new_score"]
                old_score = st.session_state.prediction_info["old_score"]
                drop = st.session_state.prediction_info["drop"]
                st.info(f"📊 **Prediksi Skor Turnitin Baru:** {new_score:.1f}% (Turun {drop:.1f}% dari skor awal {old_score:.1f}%)")
            else:
                st.warning(f"⚠️ {st.session_state.prediction_info['warning']}")
                
        # Preview Text
        st.markdown("#### Preview Hasil Analisis & Parafrase")
        st.markdown(st.session_state.processed_text)
        
        with st.expander("Lihat & Edit Teks Mentah (Markdown)"):
            st.text_area(
                "Edit Teks Markdown sebelum didownload:", 
                value=st.session_state.processed_text, 
                height=300,
                key="editable_output"
            )
            
        # Ambil nilai terbaru dari text area (jika user ngedit manual)
        final_text = st.session_state.editable_output
        
        st.write("### ⬇️ Export File")
        col1, col2 = st.columns(2)
        
        # Export as TXT
        with col1:
            st.download_button(
                label="Unduh sebagai .txt",
                data=final_text.encode("utf-8"),
                file_name="turnitin_slayer_result.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        # Export as DOCX
        with col2:
            try:
                docx_bytes = export_to_docx(final_text)
                st.download_button(
                    label="Unduh sebagai .docx",
                    data=docx_bytes,
                    file_name="turnitin_slayer_result.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Gagal menyiapkan file .docx: {e}")

if __name__ == "__main__":
    main()
