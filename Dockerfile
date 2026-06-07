# ─── Stage 1: Build dependencies ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ─── Stage 2: Production image ────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY app.py .

# Switch to non-root user
USER appuser

ENV PORT=5000
ENV APP_ENV=production

EXPOSE 5000

# Use gunicorn for production (not Flask dev server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
