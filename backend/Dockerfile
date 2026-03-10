FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for python-magic and PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -v \
    --index-url https://pypi.org/simple \
    --extra-index-url https://pypi.python.org/simple \
    --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org \
    -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /data/documents

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
