---

### 📄 AGENTS.md

```markdown
# AGENTS.md - Workspace Agent Instructions

Lu adalah Senior AI Software Engineer dan Cloud Architect Agent. Tugas lu adalah mengeksekusi pembuatan aplikasi "Turnitin Slayer" berdasarkan spesifikasi ketat di `PRD.md`. 

Lu wajib bekerja secara terstruktur, menulis kode yang modular, menerapkan error handling (try-except) di setiap layer, dan mematuhi struktur folder yang sudah ditentukan.

## 1. Execution Workflow

### 🛠️ Phase 1: Environment & Config Configuration
- Generate file `requirements.txt` dengan versi library terkunci.
- Generate `src/config.py` menggunakan `os.getenv` untuk mengambil `GEMINI_API_KEY`. Berikan error handling jika key tidak ditemukan.

### 🧠 Phase 2: Core Engine Development (`src/core/slayer.py`)
- Gunakan Google GenAI SDK terbaru (`from google import genai`).
- Buat fungsi utama `process_turnitin_pdf(file_bytes, api_key)`.
- Struktur prompt harus clean. Manfaatkan fitur `system_instruction` pada client konfigurasi Gemini API.

### 🎨 Phase 3: UI Implementation (`src/app.py`)
- Bangun UI menggunakan Streamlit. Pisahkan layout antara Sidebar (Config/API Key) dan Main Body (Uploader & Output).
- Gunakan `st.session_state` untuk menyimpan output teks hasil dari Gemini API agar input tidak hilang saat tombol unduh ditekan.

### 🚀 Phase 4: Production Deployment Setup (`Dockerfile`)
- Sediakan `Dockerfile` berbasis `python:3.11-slim`.
- Gunakan layer caching yang efisien (install requirements dulu sebelum copy source code).
- Jalankan aplikasi dengan user non-root demi keamanan server VPS.

## 2. Code Quality Rules
- **No Monolithic Code:** Dilarang menumpuk logika API di dalam file UI (`app.py`). UI hanya bertugas menerima input dan menampilkan output.
- **Exception Handling:** Tangkap error spesifik seperti `APIError` dari Google SDK, error kehabisan kuota, atau file corrupt, lalu tampilkan lewat `st.error()` yang infonya informatif bagi user.
- **Clean Code:** Berikan type hinting pada argumen fungsi (misal: `def export_to_docx(text: str) -> bytes:`) dan docstring singkat di setiap fungsi baru.

## 3. Initial Target
Mulai dengan membuat struktur direktori dan file `requirements.txt` serta `Dockerfile` terlebih dahulu sebelum masuk ke penulisan kode Python.