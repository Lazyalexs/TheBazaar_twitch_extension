FROM python:3.12-slim

WORKDIR /app

COPY ebs/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ebs/app /app/ebs/app
COPY ebs/__init__.py /app/ebs/__init__.py

ENV PYTHONPATH=/app
CMD ["uvicorn", "ebs.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

