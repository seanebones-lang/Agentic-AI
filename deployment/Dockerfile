# Multi-stage Docker build for optimized image size and security

# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.0

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Export dependencies to requirements.txt
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# Install dependencies to a target directory
RUN pip install --no-cache-dir --target=/app/packages -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Copy installed packages from builder
COPY --from=builder --chown=appuser:appuser /app/packages /app/packages

# Set Python path to include packages
ENV PYTHONPATH=/app/packages:$PYTHONPATH

# Copy application code
COPY --chown=appuser:appuser agents ./agents
COPY --chown=appuser:appuser tools ./tools
COPY --chown=appuser:appuser hitl ./hitl
COPY --chown=appuser:appuser memory ./memory
COPY --chown=appuser:appuser api ./api
COPY --chown=appuser:appuser config ./config
COPY --chown=appuser:appuser observability ./observability
COPY --chown=appuser:appuser security ./security

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run the application
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

