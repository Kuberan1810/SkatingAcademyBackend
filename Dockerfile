FROM python:3.12-slim

# =========================================================
# OS DEPENDENCIES
# =========================================================

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# =========================================================
# APP
# =========================================================

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# =========================================================
# SERVER
# =========================================================

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]