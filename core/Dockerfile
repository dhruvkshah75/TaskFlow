FROM python:3.11-slim
WORKDIR /app

# Install build dependencies (cached layer - only rebuilds if Dockerfile changes)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
       gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create directory for uploaded task files
RUN mkdir -p /app/worker/tasks

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "core.queue_manager"]

