FROM python:3.11-slim AS builder

WORKDIR /build 

COPY requirements.txt .
 
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt
 
FROM python:3.11-slim
 
ENV PYTHONDONTWRITEBYTECODE=1
 
ENV PYTHONUNBUFFERED=1
 
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
 
WORKDIR /app
 
COPY --from=builder /install /usr/local
COPY app.py .
COPY scripts/ scripts/
COPY templates/ templates/
 
RUN mkdir -p instance && chown -R appuser:appgroup /app
 
USER appuser
 
EXPOSE 5000
 
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"
 
CMD ["sh", "-c", "python scripts/init_db.py && gunicorn -w 1 -b 0.0.0.0:5000 app:app"]