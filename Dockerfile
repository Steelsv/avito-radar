FROM python:3.11-slim

WORKDIR /app

# Install minimal build deps for C-extensions (curl-cffi)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure data and output directories exist and are writable by any user
RUN mkdir -p data output && chmod -R 777 /app

ENV PYTHONUNBUFFERED=1
ENV PORT=7860

EXPOSE 7860

CMD ["python", "-u", "run.py", "bot"]
