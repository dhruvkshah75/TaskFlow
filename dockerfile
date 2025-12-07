
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required for psycopg2 and build steps
RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential libpq-dev curl \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --upgrade pip \
	&& pip install --prefix=/opt/venv --no-cache-dir -r requirements.txt


# ============ Runtime stage ============
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy preinstalled Python packages
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY . .

# Ensure entrypoint script is executable
RUN chmod +x docker-entrypoint.sh

# Create unprivileged user
RUN addgroup --system taskflow && adduser --system --ingroup taskflow taskflow
USER taskflow

EXPOSE 8000

# Default service configuration
ENV SERVICE_TYPE=api \
	PORT=8000

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
