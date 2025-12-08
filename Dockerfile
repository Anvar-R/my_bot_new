FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required to build some Python packages (dlib, pillow, psycopg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential cmake git wget curl pkg-config \
       libopenblas-dev liblapack-dev libx11-dev libjpeg-dev libpng-dev \
       libbz2-dev libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Create images folder used by the app (IMAGE_PATH)
RUN mkdir -p /app/images

EXPOSE 8080

CMD ["python", "main.py"]
