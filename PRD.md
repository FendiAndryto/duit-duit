# Product Requirements Document (PRD) - Turnitin Slayer (Production-Ready)

## 1. Executive Summary
Turnitin Slayer adalah aplikasi internal berbasis web untuk otomatisasi penulisan ulang (parafrase) dokumen akademik yang terindikasi plagiat berdasarkan dokumen PDF hasil cek Turnitin. Sistem mendeteksi warna highlight (visual marker) menggunakan Multimodal LLM, memperbaikinya, dan mengembalikan file yang bersih tanpa mengubah struktur dokumen asli.

## 2. Technical Stack
- **Backend/Frontend UI:** Streamlit (Python 3.11-slim)
- **AI Core SDK:** Google GenAI SDK (`google-genai`)
- **Core Model:** `gemini-2.5-flash` (Fast, Cost-effective Multimodal) / `gemini-2.5-pro` (High Reasoning)
- **Document Exporter:** `python-docx` & `PyPDF2`/`pdfplumber` (Untuk fallback parsing jika diperlukan)
- **Environment Management:** `python-dotenv`
- **Deployment:** Docker (Multi-stage build) + Nginx Reverse Proxy (Opsional di sisi server)

## 3. Directory Structure (Best Practice)
Aplikasi harus dibangun dengan pemisahan komponen yang jelas:
```text
turnitin-slayer/
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── app.py            # Entry point & Streamlit UI Components
│   ├── config.py         # Validasi & Load Environment Variables
│   ├── core/
│   │   ├── __init__.py
│   │   └── slayer.py     # Logika bisnis & Integrasi Gemini SDK
│   └── utils/
│       ├── __init__.py
│       └── doc_handler.py # Ekspor hasil ke .docx / .txt

## Functional Requirements
F-01: Secure Authentication
Sistem membaca GEMINI_API_KEY dari file .env di server.

Menyediakan UI input di Sidebar sebagai override jika user ingin menggunakan API Key lain secara temporer.

F-02: Robust File Ingestion
Membatasi upload file hanya untuk format .pdf.

Maksimal ukuran file: 15MB.

State management (st.session_state) harus menjaga file tetap tersimpan saat terjadi re-render halaman Streamlit.

F-03: Multimodal Processing Engine
Mengirimkan file PDF utuh ke Gemini API menggunakan object-based payload (bukan read text biasa).

Sistem Perintah AI (Strict Instruction):

Identifikasi secara visual teks yang memiliki highlight warna (merah, biru, hijau, ungu, dll.) sebagai tanda plagiasi Turnitin.

Lakukan rekonstruksi kalimat (parafrase) menggunakan gaya bahasa akademis formal berbahasa Indonesia.

Kewajiban Mutlak: Jangan pernah mengubah teks, angka, tabel, atau sitasi (format Harvard/APA) yang tidak diberi warna highlight.

Output harus berupa dokumen teks utuh dari halaman pertama sampai terakhir.

F-04: Multi-format Export
Menyediakan preview teks hasil parafrase di UI.

Menyediakan tombol download untuk format .txt dan .docx (terformat rapi menggunakan python-docx).

## Non-Functional & Security Requirements
Security: API Key dilarang keras di-hardcode di kode program atau disimpan di client-side cookies tanpa enkripsi.

Performance: Menggunakan st.spinner dan progress bar untuk operasi asynchronous berdurasi panjang (>10 detik).

Dockerization: Menggunakan user non-root di dalam container untuk mencegah celah keamanan (privilege escalation) di VPS.