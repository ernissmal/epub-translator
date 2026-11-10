FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
COPY epub_translator ./epub_translator
COPY web ./web
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .
EXPOSE 8080
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8080"]
