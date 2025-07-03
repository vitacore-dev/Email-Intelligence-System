# Email Search Service API - Quick Start Guide

## 🚀 Быстрый старт

### 1. Базовый URL
```
https://kkh7ikcgj3ee.manus.space
```

### 2. Демо запрос (без аутентификации)
```bash
curl -X GET "https://kkh7ikcgj3ee.manus.space/api/email/demo"
```

### 3. Проверка статуса сервиса
```bash
curl -X GET "https://kkh7ikcgj3ee.manus.space/api/email/health"
```

## 🔐 Аутентификация

### Регистрация пользователя
```bash
curl -X POST "https://kkh7ikcgj3ee.manus.space/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com", 
    "password": "securepassword123",
    "user_type": "free"
  }'
```

### Вход в систему
```bash
curl -X POST "https://kkh7ikcgj3ee.manus.space/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "securepassword123"
  }'
```

## 🔍 Поиск по email

### С JWT токеном
```bash
curl -X POST "https://kkh7ikcgj3ee.manus.space/api/email/search" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "email": "example@domain.com"
  }'
```

### С API ключом
```bash
curl -X POST "https://kkh7ikcgj3ee.manus.space/api/email/search" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "email": "example@domain.com"
  }'
```

### Анонимный запрос (ограниченный)
```bash
curl -X POST "https://kkh7ikcgj3ee.manus.space/api/email/search" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "example@domain.com"
  }'
```

## 📊 Мониторинг

### Проверка лимитов
```bash
curl -X GET "https://kkh7ikcgj3ee.manus.space/api/rate-limit/status" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Статистика кэша
```bash
curl -X GET "https://kkh7ikcgj3ee.manus.space/api/cache/stats" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## 🛡️ Rate Limits

| Тип пользователя | Запросов/мин | Запросов/час |
|------------------|--------------|--------------|
| Анонимный        | 5            | 50           |
| Бесплатный       | 10           | 100          |
| Премиум          | 30           | 500          |
| Корпоративный    | 100          | 2000         |

## 📝 Примеры ответов

### Успешный поиск
```json
{
  "email": "tynrik@yandex.ru",
  "basic_info": {
    "owner_name": "Наталья Владимировна Грязева",
    "status": "identified"
  },
  "professional_info": {
    "position": "Кандидат медицинских наук, доцент",
    "workplace": "Центральная государственная медицинская академия",
    "specialization": "Дерматовенерология и косметология"
  },
  "search_metadata": {
    "timestamp": 1719734400,
    "status": "completed",
    "results_count": 15
  }
}
```

### Ошибка rate limit
```json
{
  "error": "Rate limit exceeded",
  "message": "Превышен лимит запросов. Попробуйте позже.",
  "retry_after": 60
}
```

## 🔧 Коды ошибок

| Код | Описание |
|-----|----------|
| 200 | Успешный запрос |
| 400 | Неверный запрос |
| 401 | Не авторизован |
| 403 | Доступ запрещен |
| 429 | Превышен лимит запросов |
| 500 | Внутренняя ошибка сервера |

## 📚 Дополнительные ресурсы

- **Полная документация:** [email-search-service-v2-documentation.md]
- **Веб-интерфейс:** https://kkh7ikcgj3ee.manus.space
- **Поддержка:** support@email-search-service.com

