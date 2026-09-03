FROM python:3.12-slim

# =========================================================
# SYSTEM / OCR DEPENDENCIES
# =========================================================

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TESSERACT_CMD=/usr/bin/tesseract

# =========================================================
# APPLICATION WORKDIR & DEPENDENCIES
# =========================================================

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# =========================================================
# VERIFY TESSERACT INSTALLATION DURING BUILD
# =========================================================

RUN which tesseract && tesseract --version

# =========================================================
# SERVER ENTRYPOINT
# =========================================================

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]