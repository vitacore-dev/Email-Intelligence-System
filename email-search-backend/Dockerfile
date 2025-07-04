FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    wget \
    git \
    pkg-config \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Обновляем pip
RUN pip install --upgrade pip setuptools wheel

# Создание рабочей директории
WORKDIR /app

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей с оптимизациями
RUN pip install --no-cache-dir --timeout=300 -r requirements.txt

# Загрузка spaCy моделей
RUN python -m spacy download en_core_web_sm || echo "English model download failed" && \
    python -m spacy download ru_core_news_sm || echo "Russian model download failed"

# Копирование исходного кода
COPY src/ ./src/
COPY data/ ./data/
COPY .env.example ./.env

# Создание необходимых директорий
RUN mkdir -p data/logs data/cache src/static && \
    chmod -R 755 data/ src/

# Создание пользователя для безопасности
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Открытие портов
EXPOSE 5001 5003

# Переменные окружения
ENV FLASK_ENV=production
ENV FLASK_DEBUG=False
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5003
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5003/api/email/health || exit 1

# Команда запуска
CMD ["python", "src/main.py", "--host", "0.0.0.0", "--port", "5003"]

