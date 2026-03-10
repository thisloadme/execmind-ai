# ExecMind AI

ExecMind adalah asisten AI (Artificial Intelligence) dirancang secara spesifik untuk membantu pejabat eksekutif lembaga/organisasi dalam mencari, merangkum, dan menganalisis informasi dari dokumen internal maupun internet.

Sistem ini didesain mengutamakan privasi dan kontrol penuh terhadap aliran data dengan menggunakan mesin AI lokal (Ollama) serta mekanisme *Retrieval-Augmented Generation* (RAG).

## Fitur Utama

- **Chat Pintar Berbasis RAG**: Mencari dan menjawab pertanyaan pengguna berdasarkan konteks dari dokumen internal (Knowledge Base) yang diunggah ke *Vector Database* dengan akurasi tinggi.
- **Dukungan Pencarian Internet (Web Search)**: Jika informasi tidak tersedia di basis pengetahuan lokal, ExecMind otomatis melakukan pencarian internet untuk menyajikan informasi terbaru.
- **Vision Support**: Mendukung pengunggahan dan pembacaan gambar dalam riwayat percakapan (mendukung pemrosesan via LLaVA atau Gemma3 vision-models).
- **Long Context Window**: Mampu mengingat rentetan histori percakapan sebelumnya secara dinamis hingga *context-window* 128k token.
- **Session & History Management**: Sistem manajemen percakapan terpusat dengan dukungan penyimpanan sesi *chat* di dalam *database* relasional.

## Teknologi yang Digunakan

Aplikasi ini dibagi menjadi tumpukan teknologi modern:

- **Backend Daya-Tinggi**: FastAPI (Python), menggunakan _asynchronous routines_.
- **Database Relasional**: PostgreSQL dengan SQLAlchemy ORM dan Asyncpg.
- **Vector Database**: Qdrant untuk pencarian kemiripan dokumen berkecepatan tinggi.
- **AI / LLM Engine**: Ollama (menjalankan model open-source seperti `qwen2.5-coder:14b` dan text-embedding `nomic-embed-text` secara *on-premise*).
- **Frontend**: Vite SPA untuk pengalaman antarmuka (User Interface) interaktif nan responsif.

## Prasyarat Lingkungan (Prerequisites)

- Python 3.10+
- Node.js & npm (untuk frontend)
- PostgreSQL
- Ollama (harus sudah _running_ dengan model yang dikonfigurasi tersedia)
- Qdrant (berjalan via Docker)

## Struktur Direktori Utama

- `/backend` - Kode sumber Python FastAPI (API endpoints, RAG Engine, Services).
- `/frontend` - Kode sumber antarmuka pengguna Web.
- `docker-compose.yml` - Disediakan untuk kemudahan instalasi environment Qdrant & database.
- `.env` - Environment Variables (Anda dapat menyalin konfigurasi dari berkas instalasi bawaan).

## Panduan Memulai Cepat (Quick Start)

**1. Menyalakan Servis Pendukung (Database & Vector DB)**
```bash
docker-compose up -d
```

**2. Setup Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # atau venv\Scripts\activate pada Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```
*(Gunakan skrip `runapp.sh` jika tersedia)*

**3. Setup Frontend**
```bash
cd frontend
npm install
npm run dev
```

Aplikasi backend akan bekerja pada port `8002` sedangkan frontend secara *default* dapat diakses via port `5173`. Pastikan variabel CORS pada `.env` telah disesuaikan terhadap port frontend.
