FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY editorshub_aura/ ./editorshub_aura/

WORKDIR /app/editorshub_aura
CMD ["python", "bot.py"]
