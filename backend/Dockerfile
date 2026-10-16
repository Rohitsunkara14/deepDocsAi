FROM python:3.11.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PORT=8000 HF_HOME=/home/appuser/.cache/huggingface APP_ENV=production DEBUG=false
WORKDIR /app
COPY requirements-linux.lock ./requirements-linux.lock
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements-linux.lock \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /home/appuser/.cache
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser start.py ./start.py
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health',timeout=3)" || exit 1
CMD ["python", "start.py"]
