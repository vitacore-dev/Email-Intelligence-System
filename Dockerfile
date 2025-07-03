FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY src/ ./src/
COPY data/ ./data/

# Создание директорий для логов и данных
RUN mkdir -p data/logs src/database && \
    chmod 755 data/ && \
    chmod 755 src/database/

# Открытие порта
EXPOSE 5001

# Переменные окружения
ENV FLASK_ENV=production
ENV FLASK_DEBUG=False
ENV PYTHONPATH=/app

# Команда запуска
CMD ["python", "src/main.py"]

