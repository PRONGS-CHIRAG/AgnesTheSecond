FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure writable directories for SQLite and PDFs
RUN chmod -R 777 /app/hackathon-tumai && \
    mkdir -p /app/taim/orders/pdfs && chmod -R 777 /app/taim/orders/pdfs

WORKDIR /app/taim

EXPOSE 8080

CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8080}
