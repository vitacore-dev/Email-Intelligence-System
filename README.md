# Email Search Service v2.0

🔍 **Профессиональный сервис для поиска информации по email адресам**

Production-ready решение с расширенными возможностями безопасности, мониторинга и масштабирования.

## 🌟 Особенности

- 🔍 **Интеграция с реальными поисковыми API** (Google, Bing)
- 🔬 **Интеграция с Scopus API** для поиска научных публикаций
- 🆔 **Интеграция с ORCID API** для профилей исследователей
- 💾 **Система кэширования** результатов в SQLite
- 🛡️ **Rate Limiting** с многоуровневыми ограничениями
- 🔐 **Аутентификация** (JWT + API ключи)
- 📊 **Мониторинг и логирование** всех операций
- 🎨 **Современный веб-интерфейс** на React
- 🚀 **Production-ready** архитектура
- 🔗 **Комбинированный поиск** по нескольким научным базам данных

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.8+
- Node.js 16+
- npm или yarn

### 1. Установка backend

```bash
cd email-search-backend

# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Установка frontend

```bash
cd ../email-search-frontend

# Установка зависимостей
npm install

# Сборка для production
npm run build
```

### 3. Интеграция frontend с backend

```bash
# Копирование build файлов в backend
cp -r dist/* ../email-search-backend/src/static/
```

### 4. Запуск сервиса

```bash
cd ../email-search-backend

# Запуск Flask сервера
python src/main.py
```

Сервис будет доступен по адресу: http://localhost:5000

## 🔧 Конфигурация

### Переменные окружения

Создайте файл `.env` в корне backend проекта:

```env
# Поисковые API (опционально)
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
BING_API_KEY=your_bing_api_key

# Научные API
SCOPUS_API_KEY=your_scopus_api_key
ORCID_CLIENT_ID=your_orcid_client_id
ORCID_CLIENT_SECRET=your_orcid_client_secret

# JWT секретный ключ
JWT_SECRET_KEY=your_super_secret_jwt_key

# База данных
DATABASE_PATH=data/email_search.db

# Flask настройки
FLASK_ENV=production
FLASK_DEBUG=False
```

### Настройка поисковых API

#### Google Custom Search API
1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект или выберите существующий
3. Включите Custom Search API
4. Создайте API ключ
5. Настройте Custom Search Engine на [cse.google.com](https://cse.google.com/)

#### Bing Search API
1. Перейдите в [Azure Portal](https://portal.azure.com/)
2. Создайте ресурс "Bing Search v7"
3. Получите API ключ из раздела "Keys and Endpoint"

#### Scopus API
1. Зарегистрируйтесь на [Elsevier Developer Portal](https://dev.elsevier.com/)
2. Создайте новое приложение
3. Получите API ключ
4. Добавьте в `.env`: `SCOPUS_API_KEY=your_scopus_api_key`

#### ORCID API
1. Зарегистрируйтесь на [ORCID Developer Tools](https://orcid.org/developer-tools)
2. Создайте новое приложение
3. Получите Client ID и Client Secret
4. Добавьте в `.env`:
   ```
   ORCID_CLIENT_ID=your_orcid_client_id
   ORCID_CLIENT_SECRET=your_orcid_client_secret
   ```

## 📁 Структура проекта

```
email-search-service-v2/
├── email-search-backend/          # Backend Flask приложение
│   ├── src/
│   │   ├── main.py                # Основное приложение
│   │   ├── routes/                # API endpoints
│   │   ├── services/              # Бизнес-логика
│   │   ├── middleware/            # Middleware компоненты
│   │   └── static/                # Frontend build файлы
│   ├── data/                      # База данных SQLite
│   ├── requirements.txt           # Python зависимости
│   └── README.md                  # Этот файл
├── email-search-frontend/         # Frontend React приложение
│   ├── src/
│   │   ├── components/            # React компоненты
│   │   └── App.jsx               # Основной компонент
│   ├── package.json              # Node.js зависимости
│   └── vite.config.js            # Vite конфигурация
└── docs/                         # Документация
    ├── api-documentation.md      # API документация
    └── deployment-guide.md       # Руководство по развертыванию
```

## 🔐 Аутентификация

### Типы пользователей

| Тип | Запросов/мин | Запросов/час | Особенности |
|-----|--------------|--------------|-------------|
| Анонимный | 5 | 50 | Базовый доступ |
| Бесплатный | 10 | 100 | Регистрация |
| Премиум | 30 | 500 | Расширенные возможности |
| Корпоративный | 100 | 2000 | Максимальные лимиты |

### Создание администратора

```bash
# Запустите Python в директории проекта
python -c "
from src.services.auth_service import AuthService
auth = AuthService()
auth.create_user('admin', 'admin@example.com', 'secure_password', 'enterprise')
print('Администратор создан')
"
```

## 📊 API Endpoints

### Основные
- `GET /api/email/health` - Статус сервиса
- `POST /api/email/search` - Поиск по email
- `GET /api/email/demo` - Демо данные
- `POST /api/email/validate` - Валидация email

### Аутентификация
- `POST /api/auth/register` - Регистрация
- `POST /api/auth/login` - Вход
- `POST /api/auth/verify-token` - Проверка токена

### Мониторинг
- `GET /api/monitoring/stats/summary` - Статистика
- `GET /api/cache/stats` - Статистика кэша
- `GET /api/rate-limit/status` - Статус лимитов

### Научные API
- `POST /api/scientific/scopus/search-by-email` - Поиск в Scopus по email
- `POST /api/scientific/scopus/search-publications` - Поиск публикаций в Scopus
- `GET /api/scientific/scopus/publication/{id}` - Детали публикации
- `POST /api/scientific/orcid/search-by-email` - Поиск в ORCID по email
- `GET /api/scientific/orcid/profile/{orcid_id}` - Профиль исследователя
- `POST /api/scientific/combined-search` - Комбинированный поиск
- `GET /api/scientific/api-status` - Статус научных API

## 🚀 Развертывание

### Docker (рекомендуется)

```bash
# Сборка образа
docker build -t email-search-service .

# Запуск контейнера
docker run -p 5000:5000 -v $(pwd)/data:/app/data email-search-service
```

### Systemd сервис (Linux)

Создайте файл `/etc/systemd/system/email-search.service`:

```ini
[Unit]
Description=Email Search Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/email-search-backend
Environment=PATH=/path/to/email-search-backend/venv/bin
ExecStart=/path/to/email-search-backend/venv/bin/python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Активация:
```bash
sudo systemctl enable email-search
sudo systemctl start email-search
```

### Nginx конфигурация

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔧 Разработка

### Запуск в режиме разработки

Backend:
```bash
cd email-search-backend
source venv/bin/activate
export FLASK_ENV=development
export FLASK_DEBUG=True
python src/main.py
```

Frontend:
```bash
cd email-search-frontend
npm run dev
```

### Тестирование

```bash
# Backend тесты
cd email-search-backend
python -m pytest tests/

# Frontend тесты
cd email-search-frontend
npm test
```

## 📈 Мониторинг

### Логи

Логи сохраняются в:
- `data/logs/app.log` - Основные логи приложения
- `data/logs/requests.log` - Логи HTTP запросов
- `data/logs/errors.log` - Логи ошибок

### Метрики

Доступны через API:
- `/api/monitoring/stats/summary` - Общая статистика
- `/api/monitoring/system/resources` - Системные ресурсы

## 🛠️ Устранение неполадок

### Частые проблемы

1. **Ошибка подключения к базе данных**
   ```bash
   # Проверьте права доступа к папке data/
   chmod 755 data/
   ```

2. **Ошибки импорта модулей**
   ```bash
   # Убедитесь, что виртуальное окружение активировано
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend не загружается**
   ```bash
   # Пересоберите frontend
   cd email-search-frontend
   npm run build
   cp -r dist/* ../email-search-backend/src/static/
   ```

### Логи отладки

```bash
# Включение подробного логирования
export FLASK_DEBUG=True
export LOG_LEVEL=DEBUG
python src/main.py
```

## 📞 Поддержка

- **Документация:** См. папку `docs/`
- **Issues:** Создавайте issue в репозитории
- **Email:** support@email-search-service.com

## 📄 Лицензия

MIT License - см. файл LICENSE

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

## 📋 Changelog

### v2.0.0 (2025-06-30)
- ✅ Интеграция с Google и Bing Search API
- ✅ Система кэширования в SQLite
- ✅ Rate limiting с многоуровневыми ограничениями
- ✅ JWT и API ключи аутентификация
- ✅ Полное логирование и мониторинг
- ✅ Обновленный React интерфейс
- ✅ Production-ready архитектура

### v1.0.0 (2025-06-29)
- ✅ Базовый поиск по email
- ✅ Простой веб-интерфейс
- ✅ Mock данные

---

**Email Search Service v2.0** - Профессиональное решение для поиска информации по email адресам 🚀

