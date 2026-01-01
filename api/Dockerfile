FROM python:3.14-slim
WORKDIR /app

# Install build dependencies (cached layer - only rebuilds if Dockerfile changes)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
       gcc \
       curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files (for build-time packaging). Development mounts will overlay this during dev runs.
COPY . .

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

