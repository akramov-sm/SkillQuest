# SkillQuest — production image. Standard library only: no pip, no build stage needed.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    SKILLQUEST_DB=/data/skillquest.db

WORKDIR /app
COPY backend ./backend
COPY frontend ./frontend
COPY run.py .

# Unprivileged user; /data is created *before* VOLUME so a fresh named volume inherits this ownership.
RUN useradd --system --uid 10001 --no-create-home skillquest \
    && mkdir /data /backups \
    && chown skillquest /data /backups
USER skillquest
VOLUME ["/data"]
EXPOSE 8000

# /api/health is intentionally exempt from authentication.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" || exit 1

CMD ["python", "run.py", "--quiet"]
