# Email Search Service v2.0 - Complete Package

🔍 **Профессиональный сервис для поиска информации по email адресам**

Полный production-ready пакет с расширенными возможностями безопасности, мониторинга и масштабирования.

## 📦 Содержимое пакета

```
email-search-service-v2-complete/
├── README.md                          # Этот файл
├── email-search-backend/              # Backend Flask приложение
│   ├── src/                           # Исходный код
│   ├── data/                          # База данных и кэш
│   ├── requirements.txt               # Python зависимости
│   ├── Dockerfile                     # Docker образ
│   ├── docker-compose.yml             # Docker Compose конфигурация
│   ├── nginx.conf                     # Nginx конфигурация
│   ├── .env.example                   # Пример конфигурации
│   └── README.md                      # Backend документация
├── email-search-frontend/             # Frontend React приложение
│   ├── src/                           # Исходный код React
│   ├── package.json                   # Node.js зависимости
│   ├── vite.config.js                 # Vite конфигурация
│   └── dist/                          # Production build
└── docs/                              # Документация
    ├── email-search-service-v2-documentation.md
    ├── api-quick-start-guide.md
    ├── deployment-guide.md
    └── email_research.md
```

## 🚀 Быстрый старт

### Вариант 1: Docker (Рекомендуется)

```bash
# Переход в директорию backend
cd email-search-backend

# Настройка конфигурации
cp .env.example .env
# Отредактируйте .env файл

# Запуск с Docker Compose
docker-compose up -d

# Проверка статуса
curl http://localhost:5000/api/email/health
```

### Вариант 2: Ручная установка

```bash
# Backend
cd email-search-backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Frontend (если нужна пересборка)
cd ../email-search-frontend
npm install
npm run build
cp -r dist/* ../email-search-backend/src/static/

# Запуск
cd ../email-search-backend
python src/main.py
```

## ✨ Основные возможности

### 🔍 **Поиск по email**
- Интеграция с Google Custom Search API
- Интеграция с Bing Search API
- Интеллектуальная обработка результатов
- Fallback на mock данные

### 💾 **Кэширование**
- SQLite база данных
- Настраиваемое время жизни кэша
- API управления кэшем
- Статистика эффективности

### 🛡️ **Безопасность**
- JWT токены для веб-интерфейса
- API ключи для программного доступа
- Rate limiting с многоуровневыми ограничениями
- Безопасное хранение паролей (bcrypt)

### 📊 **Мониторинг**
- Детальное логирование всех запросов
- Метрики производительности
- Статистика использования
- Мониторинг системных ресурсов

### 🎨 **Веб-интерфейс**
- Современный React интерфейс
- Система аутентификации
- Адаптивный дизайн
- Статистика для пользователей

## 🔧 Конфигурация

### Основные настройки (.env файл)

```env
# Flask
FLASK_ENV=production
JWT_SECRET_KEY=your-secret-key

# Поисковые API (опционально)
GOOGLE_API_KEY=your_google_api_key
BING_API_KEY=your_bing_api_key

# База данных
DATABASE_PATH=data/email_search.db
```

### Типы пользователей и лимиты

| Тип | Запросов/мин | Запросов/час | Особенности |
|-----|--------------|--------------|-------------|
| Анонимный | 5 | 50 | Базовый доступ |
| Бесплатный | 10 | 100 | Регистрация |
| Премиум | 30 | 500 | Расширенные возможности |
| Корпоративный | 100 | 2000 | Максимальные лимиты |

## 📚 Документация

- **[Backend README](email-search-backend/README.md)** - Подробная документация backend
- **[API Quick Start Guide](docs/api-quick-start-guide.md)** - Быстрое руководство по API
- **[Deployment Guide](docs/deployment-guide.md)** - Руководство по развертыванию
- **[Full Documentation](docs/email-search-service-v2-documentation.md)** - Полная техническая документация

## 🌐 API Endpoints

### Основные
- `POST /api/email/search` - Поиск по email
- `GET /api/email/health` - Статус сервиса
- `GET /api/email/demo` - Демо данные

### Аутентификация
- `POST /api/auth/register` - Регистрация
- `POST /api/auth/login` - Вход в систему

### Мониторинг
- `GET /api/monitoring/stats/summary` - Статистика
- `GET /api/cache/stats` - Статистика кэша
- `GET /api/rate-limit/status` - Статус лимитов

## 🔄 Примеры использования

### Демо запрос
```bash
curl -X GET "http://localhost:5000/api/email/demo"
```

### Поиск с аутентификацией
```bash
curl -X POST "http://localhost:5000/api/email/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"email": "example@domain.com"}'
```

### Регистрация пользователя
```bash
curl -X POST "http://localhost:5000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "securepassword123",
    "user_type": "free"
  }'
```

## 🚀 Production развертывание

### Docker Compose (Рекомендуется)
```bash
cd email-search-backend
docker-compose up -d
```

### Systemd сервис
```bash
# См. deployment-guide.md для подробных инструкций
sudo systemctl enable email-search
sudo systemctl start email-search
```

### Nginx Reverse Proxy
```bash
# Конфигурация включена в nginx.conf
sudo ln -s /path/to/nginx.conf /etc/nginx/sites-enabled/
sudo systemctl reload nginx
```

## 🔧 Разработка

### Структура backend
```
src/
├── main.py                    # Основное приложение
├── routes/                    # API endpoints
│   ├── email_search.py       # Поиск по email
│   ├── auth_management.py    # Аутентификация
│   ├── cache_management.py   # Управление кэшем
│   └── monitoring.py         # Мониторинг
├── services/                  # Бизнес-логика
│   ├── search_engines.py     # Поисковые системы
│   ├── database.py           # База данных
│   ├── auth_service.py       # Аутентификация
│   └── monitoring_service.py # Мониторинг
├── middleware/                # Middleware
│   ├── auth_middleware.py    # Аутентификация
│   ├── rate_limit_middleware.py # Rate limiting
│   └── logging_middleware.py # Логирование
└── static/                    # Frontend build
```

### Запуск в режиме разработки
```bash
# Backend
export FLASK_ENV=development
export FLASK_DEBUG=True
python src/main.py

# Frontend
cd email-search-frontend
npm run dev
```

## 🛠️ Устранение неполадок

### Частые проблемы

1. **Порт занят:**
   ```bash
   lsof -ti:5000 | xargs kill -9
   ```

2. **Ошибки базы данных:**
   ```bash
   chmod 755 data/
   ```

3. **Проблемы с зависимостями:**
   ```bash
   pip install -r requirements.txt
   ```

### Логи
```bash
# Логи приложения
tail -f data/logs/app.log

# Логи запросов
tail -f data/logs/requests.log
```

## 📈 Производительность

### Рекомендуемые системные требования

| Нагрузка | CPU | RAM | Диск | Сеть |
|----------|-----|-----|------|------|
| Малая (< 1000 req/day) | 1 vCPU | 1GB | 10GB | 100Mbps |
| Средняя (< 10k req/day) | 2 vCPU | 2GB | 20GB | 1Gbps |
| Высокая (< 100k req/day) | 4 vCPU | 4GB | 50GB | 1Gbps |

### Оптимизация
- Включите кэширование результатов
- Настройте rate limiting
- Используйте nginx для статических файлов
- Мониторьте использование ресурсов

## 🔒 Безопасность

### Рекомендации
- Измените JWT_SECRET_KEY в production
- Используйте HTTPS в production
- Настройте файрвол
- Регулярно обновляйте зависимости
- Мониторьте логи безопасности

### Аудит безопасности
```bash
# Проверка зависимостей
pip audit

# Проверка конфигурации
python -c "from src.services.auth_service import AuthService; print('Security check passed')"
```

## 📞 Поддержка

- **Email:** support@email-search-service.com
- **Документация:** См. папку `docs/`
- **Issues:** Создавайте issue в репозитории

## 📄 Лицензия

MIT License - см. файл LICENSE

---

## 🎯 Что дальше?

1. **Настройте конфигурацию** в `.env` файле
2. **Запустите сервис** с помощью Docker или вручную
3. **Протестируйте API** с помощью curl или веб-интерфейса
4. **Настройте мониторинг** для production
5. **Изучите документацию** для расширенных возможностей

**Email Search Service v2.0** готов к использованию! 🚀

