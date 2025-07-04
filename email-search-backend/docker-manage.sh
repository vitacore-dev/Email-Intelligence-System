#!/bin/bash

# Docker Management Script for Email Search Backend
# Использование: ./docker-manage.sh [command]

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Настройка PATH для Docker
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"

# Функция для проверки Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker не найден. Убедитесь, что Docker Desktop установлен и запущен.${NC}"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker daemon не запущен. Запустите Docker Desktop.${NC}"
        exit 1
    fi
}

# Функция для отображения статуса
show_status() {
    echo -e "${BLUE}📊 СТАТУС КОНТЕЙНЕРА${NC}"
    echo "=================================="
    
    if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -q "email-search-backend"; then
        echo -e "${GREEN}✅ Контейнер запущен${NC}"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep "email-search-backend"
        
        echo -e "\n${BLUE}🌐 Доступные адреса:${NC}"
        echo "📧 Основной API: http://localhost:5003"
        echo "🔧 Backup API: http://localhost:5001"
        echo "📱 Web интерфейс: http://localhost:5003/"
        echo "❤️ Health check: http://localhost:5003/api/email/health"
        
        # Проверяем health check
        echo -e "\n${BLUE}❤️ Проверка здоровья:${NC}"
        if curl -s "http://localhost:5003/api/email/health" | grep -q "healthy"; then
            echo -e "${GREEN}✅ Сервис здоров${NC}"
        else
            echo -e "${YELLOW}⚠️ Проблемы с сервисом${NC}"
        fi
    else
        echo -e "${RED}❌ Контейнер не запущен${NC}"
    fi
}

# Функция для сборки образа
build_image() {
    echo -e "${BLUE}🔨 СБОРКА ОБРАЗА${NC}"
    echo "=================================="
    
    echo "Сборка образа email-search-backend:v3.0-enhanced..."
    if docker build -t email-search-backend:v3.0-enhanced .; then
        echo -e "${GREEN}✅ Образ собран успешно${NC}"
    else
        echo -e "${RED}❌ Ошибка сборки образа${NC}"
        exit 1
    fi
}

# Функция для запуска контейнера
start_container() {
    echo -e "${BLUE}🚀 ЗАПУСК КОНТЕЙНЕРА${NC}"
    echo "=================================="
    
    # Останавливаем старые контейнеры
    if docker ps -q --filter "name=email-search-backend" | grep -q .; then
        echo "Остановка старого контейнера..."
        docker stop email-search-backend
        docker rm email-search-backend
    fi
    
    echo "Запуск нового контейнера..."
    if docker compose up -d; then
        echo -e "${GREEN}✅ Контейнер запущен${NC}"
        
        # Ждем инициализации
        echo "Ожидание инициализации сервиса..."
        sleep 10
        
        show_status
    else
        echo -e "${RED}❌ Ошибка запуска контейнера${NC}"
        exit 1
    fi
}

# Функция для остановки контейнера
stop_container() {
    echo -e "${BLUE}🛑 ОСТАНОВКА КОНТЕЙНЕРА${NC}"
    echo "=================================="
    
    if docker compose down; then
        echo -e "${GREEN}✅ Контейнер остановлен${NC}"
    else
        echo -e "${RED}❌ Ошибка остановки контейнера${NC}"
        exit 1
    fi
}

# Функция для перезапуска
restart_container() {
    echo -e "${BLUE}🔄 ПЕРЕЗАПУСК КОНТЕЙНЕРА${NC}"
    echo "=================================="
    
    stop_container
    start_container
}

# Функция для показа логов
show_logs() {
    echo -e "${BLUE}📋 ЛОГИ КОНТЕЙНЕРА${NC}"
    echo "=================================="
    
    if docker ps -q --filter "name=email-search-backend" | grep -q .; then
        docker logs -f email-search-backend
    else
        echo -e "${RED}❌ Контейнер не запущен${NC}"
    fi
}

# Функция для тестирования
test_container() {
    echo -e "${BLUE}🧪 ТЕСТИРОВАНИЕ КОНТЕЙНЕРА${NC}"
    echo "=================================="
    
    if ! docker ps -q --filter "name=email-search-backend" | grep -q .; then
        echo -e "${RED}❌ Контейнер не запущен${NC}"
        exit 1
    fi
    
    echo "1. Проверка health check..."
    if curl -s "http://localhost:5003/api/email/health" | grep -q "healthy"; then
        echo -e "${GREEN}✅ Health check прошел${NC}"
    else
        echo -e "${RED}❌ Health check не прошел${NC}"
        return 1
    fi
    
    echo "2. Проверка веб-интерфейса..."
    if curl -s "http://localhost:5003/" | grep -q "Email Search Backend"; then
        echo -e "${GREEN}✅ Веб-интерфейс доступен${NC}"
    else
        echo -e "${YELLOW}⚠️ Проблемы с веб-интерфейсом${NC}"
    fi
    
    echo "3. Тестирование API с демо данными..."
    test_response=$(curl -s -X POST "http://localhost:5003/api/email/search" \
        -H "Content-Type: application/json" \
        -d '{"email": "ya.kristi89@yandex.ru"}' \
        --max-time 30)
    
    if echo "$test_response" | grep -q "owner_name"; then
        echo -e "${GREEN}✅ API тестирование прошло успешно${NC}"
        echo "Найденное имя: $(echo "$test_response" | grep -o '"owner_name":"[^"]*"' | cut -d'"' -f4)"
    else
        echo -e "${YELLOW}⚠️ API работает, но есть проблемы с данными${NC}"
    fi
}

# Функция для полной переустановки
reinstall() {
    echo -e "${BLUE}🔄 ПОЛНАЯ ПЕРЕУСТАНОВКА${NC}"
    echo "=================================="
    
    stop_container
    
    echo "Удаление старых образов..."
    docker rmi email-search-backend:v3.0-enhanced 2>/dev/null || true
    docker rmi email-search-backend-email-search-service 2>/dev/null || true
    
    build_image
    start_container
}

# Функция помощи
show_help() {
    echo -e "${BLUE}🔧 УПРАВЛЕНИЕ EMAIL SEARCH BACKEND DOCKER${NC}"
    echo "=========================================="
    echo ""
    echo "Использование: $0 [команда]"
    echo ""
    echo "Команды:"
    echo "  status      - Показать статус контейнера"
    echo "  build       - Собрать Docker образ"
    echo "  start       - Запустить контейнер"
    echo "  stop        - Остановить контейнер"
    echo "  restart     - Перезапустить контейнер"
    echo "  logs        - Показать логи контейнера"
    echo "  test        - Протестировать контейнер"
    echo "  reinstall   - Полная переустановка"
    echo "  help        - Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0 status"
    echo "  $0 start"
    echo "  $0 test"
}

# Основная логика
main() {
    check_docker
    
    case "${1:-help}" in
        "status")
            show_status
            ;;
        "build")
            build_image
            ;;
        "start")
            start_container
            ;;
        "stop")
            stop_container
            ;;
        "restart")
            restart_container
            ;;
        "logs")
            show_logs
            ;;
        "test")
            test_container
            ;;
        "reinstall")
            reinstall
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Запуск основной функции
main "$@"
