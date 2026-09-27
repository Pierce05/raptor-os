FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY fixtures.json ./fixtures.json

EXPOSE 8000

CMD ["sh", "-c", "python -m app.entrypoint"]
