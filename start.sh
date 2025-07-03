#!/bin/bash

# Email Search Service v2.0 - Quick Start Script
# Этот скрипт поможет быстро запустить сервис

set -e

echo "🚀 Email Search Service v2.0 - Quick Start"
echo "=========================================="

# Проверка зависимостей
check_dependencies() {
    echo "📋 Проверка зависимостей..."
    
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 не найден. Установите Python 3.8+"
        exit 1
    fi
    
    if ! command -v pip3 &> /dev/null; then
        echo "❌ pip3 не найден. Установите pip"
        exit 1
    fi
    
    echo "✅ Зависимости проверены"
}

# Настройка backend
setup_backend() {
    echo "🔧 Настройка backend..."
    
    cd email-search-backend
    
    # Создание виртуального окружения
    if [ ! -d "venv" ]; then
        echo "📦 Создание виртуального окружения..."
        python3 -m venv venv
    fi
    
    # Активация виртуального окружения
    source venv/bin/activate
    
    # Установка зависимостей
    echo "📦 Установка зависимостей..."
    pip install -r requirements.txt
    
    # Создание конфигурации
    if [ ! -f ".env" ]; then
        echo "⚙️ Создание конфигурации..."
        cp .env.example .env
        echo "📝 Отредактируйте файл .env для настройки API ключей"
    fi
    
    # Создание директорий
    mkdir -p data/logs
    chmod 755 data/
    
    cd ..
    echo "✅ Backend настроен"
}

# Настройка frontend (если нужно)
setup_frontend() {
    echo "🎨 Проверка frontend..."
    
    if [ ! -d "email-search-backend/src/static" ] || [ -z "$(ls -A email-search-backend/src/static)" ]; then
        echo "🔧 Frontend не найден, проверяем Node.js..."
        
        if command -v npm &> /dev/null; then
            echo "📦 Сборка frontend..."
            cd email-search-frontend
            npm install
            npm run build
            cp -r dist/* ../email-search-backend/src/static/
            cd ..
            echo "✅ Frontend собран"
        else
            echo "⚠️ Node.js не найден. Frontend уже собран и включен в пакет."
        fi
    else
        echo "✅ Frontend уже готов"
    fi
}

# Запуск сервиса
start_service() {
    echo "🚀 Запуск сервиса..."
    
    cd email-search-backend
    source venv/bin/activate
    
    echo "🌐 Сервис будет доступен по адресу: http://localhost:5000"
    echo "📊 API документация: http://localhost:5000/api/email/health"
    echo "🔍 Демо: http://localhost:5000/api/email/demo"
    echo ""
    echo "Для остановки нажмите Ctrl+C"
    echo ""
    
    python src/main.py
}

# Docker вариант
start_with_docker() {
    echo "🐳 Запуск с Docker..."
    
    cd email-search-backend
    
    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo "📝 Создан файл .env. Отредактируйте его при необходимости."
    fi
    
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
        echo "✅ Сервис запущен с Docker Compose"
        echo "🌐 Доступен по адресу: http://localhost:5000"
    elif command -v docker &> /dev/null; then
        docker build -t email-search-service:v2.0 .
        docker run -d --name email-search-service -p 5000:5000 -v $(pwd)/data:/app/data email-search-service:v2.0
        echo "✅ Сервис запущен с Docker"
        echo "🌐 Доступен по адресу: http://localhost:5000"
    else
        echo "❌ Docker не найден. Используйте обычный запуск."
        return 1
    fi
}

# Главное меню
main_menu() {
    echo ""
    echo "Выберите способ запуска:"
    echo "1) 🐳 Docker (рекомендуется)"
    echo "2) 🔧 Ручная установка"
    echo "3) ❓ Помощь"
    echo "4) 🚪 Выход"
    echo ""
    read -p "Ваш выбор (1-4): " choice
    
    case $choice in
        1)
            if start_with_docker; then
                echo "✅ Сервис успешно запущен с Docker!"
                echo "📖 Для просмотра логов: docker-compose logs -f"
                echo "🛑 Для остановки: docker-compose down"
            else
                echo "⚠️ Переключаемся на ручную установку..."
                manual_setup
            fi
            ;;
        2)
            manual_setup
            ;;
        3)
            show_help
            main_menu
            ;;
        4)
            echo "👋 До свидания!"
            exit 0
            ;;
        *)
            echo "❌ Неверный выбор. Попробуйте снова."
            main_menu
            ;;
    esac
}

# Ручная установка
manual_setup() {
    check_dependencies
    setup_backend
    setup_frontend
    start_service
}

# Помощь
show_help() {
    echo ""
    echo "📖 Справка по Email Search Service v2.0"
    echo "======================================"
    echo ""
    echo "🐳 Docker запуск:"
    echo "   - Автоматическая настройка"
    echo "   - Изолированная среда"
    echo "   - Простое управление"
    echo ""
    echo "🔧 Ручная установка:"
    echo "   - Полный контроль"
    echo "   - Настройка под ваши нужды"
    echo "   - Возможность разработки"
    echo ""
    echo "📁 Структура проекта:"
    echo "   email-search-backend/  - Backend Flask приложение"
    echo "   email-search-frontend/ - Frontend React приложение"
    echo "   docs/                  - Документация"
    echo ""
    echo "🔧 Конфигурация:"
    echo "   Отредактируйте файл email-search-backend/.env"
    echo "   Добавьте API ключи для Google и Bing (опционально)"
    echo ""
    echo "📚 Документация:"
    echo "   README.md              - Основная документация"
    echo "   docs/                  - Подробные руководства"
    echo ""
}

# Проверка аргументов командной строки
case "${1:-}" in
    --docker)
        start_with_docker
        ;;
    --manual)
        manual_setup
        ;;
    --help)
        show_help
        ;;
    *)
        main_menu
        ;;
esac

