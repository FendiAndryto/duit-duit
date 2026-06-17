import sys
import os
import streamlit as st
import logging
import random
import string

# Menambahkan root folder project ke sys.path untuk mencegah ModuleNotFoundError
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.slayer import process_turnitin_pdf
from src.utils.doc_handler import export_to_docx
from src.utils.similarity import add_similarity_badges
from src.core.database import (verify_user, create_user, deduct_quota, 
                               add_api_key, get_all_keys, get_all_users, update_user)
from datetime import datetime, timedelta

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
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def admin_dashboard():
    st.title("🧙‍♂️ Ruang Kendali Bos Pendi")
    st.warning("Halaman Khusus Admin!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.header("🔑 Management Token")
        new_key = st.text_input("Masukkan API Key Gemini Baru", type="password")
        if st.button("Simpan Key"):
            if new_key:
                success = add_api_key(new_key)
                if success:
                    st.success("✅ API Key berhasil ditambahkan ke kolam!")
                else:
                    st.error("❌ Key sudah ada di database.")
            else:
                st.warning("Masukkan key terlebih dahulu.")
                
        st.subheader("Daftar Token")
        keys = get_all_keys()
        for k in keys:
            st.write(f"ID: {k['id']} | Usage: {k['usage_today']}/20 | Active: {k['is_active']} | Last Used: {k['last_used']}")
            
    with col2:
        st.header("👤 Cetak Akun User")
        paket_options = {
            "Paket 1: 1x Submit (2 Hari)": {"quota": 1, "days": 2},
            "Paket 2: 3x Submit (7 Hari)": {"quota": 3, "days": 7},
            "Paket 3: 7x Submit (14 Hari)": {"quota": 7, "days": 14}
        }
        selected_paket = st.selectbox("Pilih Paket Kuota", options=list(paket_options.keys()))
        paket_data = paket_options[selected_paket]
        
        auto_exp_date = datetime.now() + timedelta(days=paket_data["days"])
        expired_date_input = st.date_input("Masa Aktif Sampai", value=auto_exp_date)
        
        if st.button("Generate Akun", type="primary"):
            quota = paket_data["quota"]
            username = f"slayer_{random.randint(1000, 9999)}"
            password = generate_random_string(8)
            exp_str = expired_date_input.strftime('%Y-%m-%d')
            
            success = create_user(username, password, quota, exp_str)
            if success:
                st.success("✅ Akun berhasil dibuat!")
                wa_text = f"""💸 *PEMBAYARAN VERIFIED!*
Ini akun login Turnitin Slayer lu, Bos. Gunakan dengan bijak buat ngebantai revisian:

👤 *Username:* {username}
🔑 *Password:* {password}
📊 *Sisa Kuota:* {quota}x Submit PDF
⏳ *Masa Aktif:* {exp_str}

🔗 *Link Aplikasi:* [URL Aplikasi Lu]"""
                st.text_area("Copy Text WhatsApp:", value=wa_text, height=200)
            else:
                st.error("❌ Gagal membuat akun. Silakan coba lagi.")
                
        st.divider()
        st.subheader("🛠️ Update Kuota & Expired User")
        users = get_all_users()
        if users:
            user_options = {u['username']: u for u in users}
            selected_user_to_update = st.selectbox("Pilih Username", options=list(user_options.keys()))
            sel_u = user_options[selected_user_to_update]
            
            st.write(f"**Sisa Kuota:** {sel_u['quota']} | **Masa Aktif Saat Ini:** {sel_u['expired_date']}")
            
            update_paket = st.selectbox("Pilih Paket Tambahan", options=list(paket_options.keys()), key="update_paket")
            paket_data_update = paket_options[update_paket]
            
            auto_new_quota = sel_u['quota'] + paket_data_update['quota']
            
            # Parsing current expired date
            try:
                curr_exp = datetime.strptime(sel_u['expired_date'], '%Y-%m-%d').date() if sel_u['expired_date'] else datetime.now().date()
            except:
                curr_exp = datetime.now().date()
                
            base_date = curr_exp if curr_exp >= datetime.now().date() else datetime.now().date()
            auto_new_exp = base_date + timedelta(days=paket_data_update['days'])
            
            new_quota = st.number_input("Update Kuota Akhir", value=auto_new_quota, min_value=0)
            new_exp = st.date_input("Update Masa Aktif Akhir", value=auto_new_exp)
            
            if st.button("Update User"):
                if update_user(sel_u['id'], new_quota, new_exp.strftime('%Y-%m-%d')):
                    st.success(f"✅ Akun {sel_u['username']} berhasil diupdate!")
                else:
                    st.error("❌ Gagal update akun.")
        else:
            st.info("Belum ada user terdaftar.")

        st.divider()
        st.subheader("Daftar Akun User")
        for u in users:
            st.write(f"ID: {u['id']} | User: {u['username']} | Kuota: {u['quota']} | Expired: {u['expired_date']}")

def user_app():
    if not st.session_state.logged_in_user:
        st.title("🛡️ Turnitin Slayer")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("🔑 Login Akses")
            st.markdown("Silakan login dengan akun yang diberikan admin.")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    user_data = verify_user(username, password)
                    if user_data:
                        # Cek expired date
                        today_str = datetime.now().strftime('%Y-%m-%d')
                        exp_date = user_data.get('expired_date')
                        if exp_date and today_str > exp_date:
                            st.error("⚠️ Masa aktif akun lu udah abis, Bos! Silakan hubungi admin di WA buat isi ulang/perpanjang.")
                        else:
                            st.session_state.logged_in_user = user_data
                            st.rerun()
                    else:
                        st.error("❌ Username atau password salah!")

        with col2:
            st.subheader("🛒 Beli / Perpanjang Paket")
            st.markdown("""
Belum punya akun atau kuota habis? Pilih paket di bawah ini:

- 🥉 **Paket 1:** 1x Submit (Aktif 2 Hari)
- 🥈 **Paket 2:** 3x Submit (Aktif 7 Hari)
- 🥇 **Paket 3:** 7x Submit (Aktif 14 Hari)

**Langsung chat admin untuk aktivasi instan:**
            """)
            st.link_button("💬 Chat Admin 1 (0881010290185)", "https://wa.me/62881010290185?text=Halo%20Admin%201,%20saya%20mau%20beli/perpanjang%20paket%20Turnitin%20Slayer")
            st.link_button("💬 Chat Admin 2 (085881705459)", "https://wa.me/6285881705459?text=Halo%20Admin%202,%20saya%20mau%20beli/perpanjang%20paket%20Turnitin%20Slayer")
            
        return

    # User is logged in
    user = st.session_state.logged_in_user
    
    st.title("🛡️ Turnitin Slayer")
    st.markdown(
        "Aplikasi otomasi parafrase dokumen akademik dari PDF Turnitin. "
        "Sistem ini hanya akan mengubah bagian yang ter-*highlight* warna tanpa mengubah format, "
        "sitasi, atau teks asli yang bersih."
    )
    
    # --- Sidebar Configuration ---
    with st.sidebar:
        st.header(f"👤 {user['username']}")
        st.metric("Sisa Kuota Submit", f"{user['quota']}x")
        if st.button("Logout"):
            st.session_state.logged_in_user = None
            st.session_state.processed_text = None
            st.session_state.prediction_info = None
            st.rerun()
            
        st.divider()
        st.header("⚙️ Konfigurasi")
        
        st.divider()
        st.subheader("📉 Plagiarism Predictor")
        initial_plagiarism_pct = st.number_input("Persentase Plagiasi Awal (%)", min_value=0, max_value=100, value=20)
        
        st.divider()
        st.info("Batas Maksimal File: 15MB\n\nFormat: Hanya PDF")

    # --- Main Area: Uploader ---
    uploaded_file = st.file_uploader("Upload Dokumen PDF Turnitin Anda", type=["pdf"])
    
    if uploaded_file is not None:
        # Validasi ukuran
        file_size_mb = uploaded_file.size / (1024 * 1024)
        if file_size_mb > 15:
            st.error(f"❌ Ukuran file terlalu besar! ({file_size_mb:.2f} MB). Maksimal 15 MB.")
            return
            
        st.success(f"File **{uploaded_file.name}** ({file_size_mb:.2f} MB) siap diproses!")
        
        # Cek Kuota
        if user['quota'] <= 0:
            st.error("❌ Jatah submit lu udah abis, Bos! Hubungi admin di WA buat isi ulang slot revisi.")
            st.button("🚀 Mulai Proses Parafrase", type="primary", disabled=True)
        else:
            if st.button("🚀 Mulai Proses Parafrase", type="primary"):
                try:
                    file_bytes = uploaded_file.getvalue()
                    
                    with st.spinner("Sistem sedang menganalisis warna... (Ini mungkin memakan waktu puluhan detik)"):
                        result_text = process_turnitin_pdf(file_bytes=file_bytes, model_name="gemini-2.5-flash")
                        final_result, red_badge_words, total_processed_words = add_similarity_badges(result_text)
                        
                        st.warning(f"🛠️ DEBUG INFO: Total Kata Diproses = {total_processed_words} | Kata Gagal (Merah) = {red_badge_words}")
                        
                        if total_processed_words > 0:
                            predicted_plagiarism = initial_plagiarism_pct * (red_badge_words / total_processed_words)
                            predicted_plagiarism = max(0, predicted_plagiarism)
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
                        
                        st.session_state.processed_text = final_result
                        
                        # Deduct quota on success
                        if deduct_quota(user['id']):
                            user['quota'] -= 1
                            st.session_state.logged_in_user = user
                            st.toast("✅ Proses selesai, kuota telah dikurangi 1.")
                        
                except Exception as e:
                    logger.error(f"Error: {e}", exc_info=True)
                    st.error(f"🐞 {e}")

    # --- Output & Export Area ---
    if st.session_state.processed_text:
        st.divider()
        st.subheader("📄 Hasil Rekonstruksi Dokumen")
        
        if st.session_state.prediction_info:
            if st.session_state.prediction_info["show"]:
                new_score = st.session_state.prediction_info["new_score"]
                old_score = st.session_state.prediction_info["old_score"]
                drop = st.session_state.prediction_info["drop"]
                st.info(f"📊 **Prediksi Skor Turnitin Baru:** {new_score:.1f}% (Turun {drop:.1f}% dari skor awal {old_score:.1f}%)")
            else:
                st.warning(f"⚠️ {st.session_state.prediction_info['warning']}")
                
        st.markdown("#### Preview Hasil Analisis & Parafrase")
        st.markdown(st.session_state.processed_text)
        
        with st.expander("Lihat & Edit Teks Mentah (Markdown)"):
            st.text_area(
                "Edit Teks Markdown sebelum didownload:", 
                value=st.session_state.processed_text, 
                height=300,
                key="editable_output"
            )
            
        final_text = st.session_state.editable_output
        
        st.write("### ⬇️ Export File")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="Unduh sebagai .txt",
                data=final_text.encode("utf-8"),
                file_name="turnitin_slayer_result.txt",
                mime="text/plain",
                use_container_width=True
            )
            
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

def main():
    query_params = st.query_params
    if query_params.get("mode") == "bosgila":
        admin_dashboard()
    else:
        user_app()

if __name__ == "__main__":
    main()
