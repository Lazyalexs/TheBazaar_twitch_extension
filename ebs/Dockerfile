FROM python:3.12-slim

WORKDIR /app

COPY ebs/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ebs/app /app/ebs/app
COPY ebs/__init__.py /app/ebs/__init__.py

RUN useradd --no-create-home --shell /bin/false app && \
    chown -R app:app /app

ENV PYTHONPATH=/app

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

USER app
CMD ["uvicorn", "ebs.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
