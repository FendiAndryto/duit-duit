# Gunakan base image python slim yang ringan
FROM python:3.11-slim as builder

# Set working directory di dalam container
WORKDIR /app

# Menghindari penulisan file bytecode dan buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependency sistem yang mungkin dibutuhkan oleh python-docx atau utilitas lain
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt lebih dulu untuk layer caching yang efisien
COPY requirements.txt .

# Install dependencies Python
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Production ---
FROM python:3.11-slim

# Tambahkan user non-root untuk keamanan server VPS
RUN useradd -m -r appuser

WORKDIR /app

# Salin dependencies terinstall dari builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy kode aplikasi
COPY . .

# Set kepemilikan file ke non-root user
RUN chown -R appuser:appuser /app

# Ganti pengguna ke non-root
USER appuser

# Ekspos port default Streamlit
EXPOSE 8501

# Command untuk menjalankan aplikasi
CMD ["streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
