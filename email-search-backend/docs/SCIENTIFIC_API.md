# Документация по научным API (Scopus и ORCID)

Этот документ описывает интеграцию с научными API Scopus и ORCID для поиска информации о научных публикациях и исследователях.

## Обзор

Система интегрирована с двумя основными научными базами данных:

- **Scopus API** - для поиска научных публикаций и метрик авторов
- **ORCID API** - для получения профилей исследователей и их работ

## Настройка API ключей

### Scopus API

1. Зарегистрируйтесь на [Elsevier Developer Portal](https://dev.elsevier.com/)
2. Создайте новое приложение
3. Получите API ключ
4. Добавьте в `.env` файл:
   ```
   SCOPUS_API_KEY=your_scopus_api_key_here
   ```

### ORCID API

1. Зарегистрируйтесь на [ORCID Developer Tools](https://orcid.org/developer-tools)
2. Создайте новое приложение
3. Получите Client ID и Client Secret
4. Добавьте в `.env` файл:
   ```
   ORCID_CLIENT_ID=your_orcid_client_id_here
   ORCID_CLIENT_SECRET=your_orcid_client_secret_here
   ```

## API Endpoints

### Scopus API

#### 1. Поиск по email адресу
```http
POST /api/scientific/scopus/search-by-email
```

**Тело запроса:**
```json
{
  "email": "researcher@university.edu"
}
```

**Ответ:**
```json
{
  "message": "Данные успешно получены из Scopus",
  "author_info": {
    "author_id": "12345678900",
    "given_name": "John",
    "surname": "Doe",
    "affiliation": "University of Science",
    "document_count": 45,
    "cited_by_count": 1250,
    "h_index": 18
  },
  "publications": [...],
  "total_publications": 45,
  "status": "success"
}
```

#### 2. Поиск публикаций по запросу
```http
POST /api/scientific/scopus/search-publications
```

**Тело запроса:**
```json
{
  "query": "artificial intelligence machine learning",
  "limit": 20
}
```

#### 3. Детали публикации
```http
GET /api/scientific/scopus/publication/{scopus_id}
```

#### 4. Метрики автора
```http
GET /api/scientific/scopus/author-metrics/{author_id}
```

### ORCID API

#### 1. Поиск по email адресу
```http
POST /api/scientific/orcid/search-by-email
```

**Тело запроса:**
```json
{
  "email": "researcher@university.edu"
}
```

#### 2. Поиск по имени
```http
POST /api/scientific/orcid/search-by-name
```

**Тело запроса:**
```json
{
  "given_name": "John",
  "family_name": "Doe"
}
```

#### 3. Профиль исследователя
```http
GET /api/scientific/orcid/profile/{orcid_id}
```

#### 4. Работы исследователя
```http
GET /api/scientific/orcid/works/{orcid_id}?limit=20
```

### Комбинированный поиск

#### Поиск по обеим базам данных
```http
POST /api/scientific/combined-search
```

**Тело запроса:**
```json
{
  "email": "researcher@university.edu"
}
```

**Ответ содержит данные из обеих систем:**
```json
{
  "email": "researcher@university.edu",
  "scopus_data": {
    "author_info": {...},
    "publications": [...],
    "total_publications": 45
  },
  "orcid_data": {
    "researchers": [...],
    "main_researcher": {...},
    "works": [...],
    "total_works": 42
  },
  "combined_analysis": {
    "data_sources": ["scopus", "orcid"],
    "publication_count_comparison": {
      "scopus": 45,
      "orcid": 42
    },
    "research_profile": {...},
    "recommendations": [...]
  },
  "status": "success"
}
```

## Примеры использования

### Python client

```python
import requests

# Авторизация
auth_response = requests.post('http://localhost:5001/api/auth/login', json={
    'username': 'admin',
    'password': 'admin_password'
})
token = auth_response.json()['access_token']

headers = {'Authorization': f'Bearer {token}'}

# Поиск в Scopus
scopus_response = requests.post(
    'http://localhost:5001/api/scientific/scopus/search-by-email',
    json={'email': 'researcher@university.edu'},
    headers=headers
)
print(scopus_response.json())

# Поиск в ORCID
orcid_response = requests.post(
    'http://localhost:5001/api/scientific/orcid/search-by-email',
    json={'email': 'researcher@university.edu'},
    headers=headers
)
print(orcid_response.json())

# Комбинированный поиск
combined_response = requests.post(
    'http://localhost:5001/api/scientific/combined-search',
    json={'email': 'researcher@university.edu'},
    headers=headers
)
print(combined_response.json())
```

### JavaScript client

```javascript
// Авторизация
const authResponse = await fetch('/api/auth/login', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    username: 'admin',
    password: 'admin_password'
  })
});
const {access_token} = await authResponse.json();

// Комбинированный поиск
const searchResponse = await fetch('/api/scientific/combined-search', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${access_token}`
  },
  body: JSON.stringify({
    email: 'researcher@university.edu'
  })
});
const data = await searchResponse.json();
console.log(data);
```

## Структура данных

### Информация об авторе Scopus
```json
{
  "author_id": "12345678900",
  "given_name": "John",
  "surname": "Doe",
  "affiliation": "University of Science",
  "document_count": 45,
  "cited_by_count": 1250,
  "h_index": 18,
  "scopus_profile_url": "https://..."
}
```

### Публикация Scopus
```json
{
  "scopus_id": "2-s2.0-12345678901",
  "title": "Article Title",
  "publication_name": "Journal Name",
  "cover_date": "2023-01-15",
  "doi": "10.1000/journal.2023.123456",
  "cited_by_count": 25,
  "authors": [...],
  "abstract": "Article abstract...",
  "keywords": "keyword1, keyword2",
  "type": "Article",
  "open_access": true,
  "scopus_url": "https://..."
}
```

### Профиль исследователя ORCID
```json
{
  "orcid_id": "0000-0000-0000-0000",
  "orcid_url": "https://orcid.org/0000-0000-0000-0000",
  "personal_info": {
    "given_names": "John",
    "family_name": "Doe",
    "credit_name": "John A. Doe",
    "other_names": [],
    "researcher_urls": [...]
  },
  "biography": "Researcher biography...",
  "keywords": ["artificial intelligence", "machine learning"],
  "external_identifiers": [...],
  "addresses": [...],
  "educations": [...],
  "employments": [...],
  "works": {...}
}
```

## Ограничения и лимиты

### Scopus API
- **Rate Limits**: 20,000 запросов в неделю (бесплатный план)
- **Quota Reset**: Еженедельно
- **Максимум результатов**: 5000 за запрос

### ORCID API
- **Rate Limits**: 12 запросов в секунду (public API)
- **Максимум результатов**: 1000 за запрос
- **Формат ORCID ID**: 0000-0000-0000-0000

## Обработка ошибок

Система обрабатывает следующие типы ошибок:

1. **Отсутствие API ключей** - возвращается пустой результат
2. **Превышение лимитов** - HTTP 429 с сообщением об ошибке
3. **Неверный формат данных** - HTTP 400 с описанием ошибки
4. **Недоступность сервиса** - HTTP 503 с информацией о проблеме

## Безопасность

- Все запросы требуют JWT токен авторизации
- API ключи хранятся в переменных окружения
- Логирование всех запросов для аудита
- Rate limiting на уровне приложения

## Мониторинг

Система предоставляет следующие метрики:

- Количество запросов к каждому API
- Время ответа
- Количество ошибок
- Использование quota

Доступ к метрикам: `GET /api/monitoring/metrics`

## Статус API

Проверка доступности API:
```http
GET /api/scientific/api-status
```

**Ответ:**
```json
{
  "api_status": {
    "scopus": {
      "available": true,
      "base_url": "https://api.elsevier.com/content"
    },
    "orcid": {
      "available": true,
      "base_url": "https://pub.orcid.org/v3.0"
    }
  },
  "status": "success"
}
```
