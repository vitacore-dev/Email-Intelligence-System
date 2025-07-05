# Документация: Фаза 4.2 - Методика анализа публикаций

## Обзор

Реализована новая фаза глубокого анализа публикаций автора, которая запускается после успешного определения владельца email и интегрируется в общий процесс анализа.

## 🚀 Архитектура решения

### Компоненты системы

1. **PublicationAnalyzer** (`src/services/publication_analyzer.py`)
   - Основной класс для глубокого анализа публикаций
   - Интегрирован в SearchEngineService
   - Поддерживает множественные источники данных

2. **Интеграция в SearchEngineService** (`src/services/search_engines.py`)
   - Фаза 4.2 запускается после определения владельца email
   - Автоматическое включение результатов в API ответ
   - Улучшение выводов на основе анализа публикаций

### Условия запуска фазы 4.2

```python
if (processed_data['basic_info']['owner_name'] != 'Не определено' and 
    processed_data['basic_info']['confidence_score'] > 0.1 and 
    self.publication_analyzer):
    # Запуск фазы анализа публикаций
```

**Критерии активации:**
- ✅ Владелец email определен (не "Не определено")
- ✅ Уверенность в идентификации > 10%
- ✅ Анализатор публикаций доступен

## 📊 Алгоритм обработки публикаций

### 1. Извлечение метаданных

Для каждой публикации извлекаются:
- **Заголовок** - нормализованное название
- **Журнал** - название издания
- **Дата публикации** - год или полная дата
- **DOI/PMID** - цифровые идентификаторы
- **Список авторов** - с нормализацией имен
- **Аннотация** - для контент-анализа
- **Ключевые слова** - для классификации
- **Метрики цитирования** - через внешние API

### 2. Определение роли автора

```python
author_role = {
    'is_first_author': bool,        # Первый автор
    'is_corresponding_author': bool, # Корреспондирующий автор
    'is_last_author': bool,         # Последний автор
    'author_position': int,         # Позиция в списке авторов
    'total_authors': int,           # Общее количество авторов
    'author_contribution': str,     # Тип вклада
    'confidence_score': float       # Уверенность в определении
}
```

**Логика определения вклада:**
- Первый автор → "Основной исследователь"
- Последний автор (при >2 авторов) → "Руководитель исследования"
- Корреспондирующий автор → "Корреспондирующий автор"
- Остальные → "Соавтор"

### 3. Анализ содержания

```python
content_analysis = {
    'abstract_analysis': {},      # Анализ аннотации
    'methodology': str,           # Методология исследования
    'main_results': List[str],    # Основные результаты
    'brief_summary': str,         # Краткое резюме
    'research_type': str,         # Тип исследования
    'study_design': str,          # Дизайн исследования
    'statistical_methods': [],    # Статистические методы
    'limitations': []             # Ограничения исследования
}
```

**Определяемые типы исследований:**
- Клиническое исследование
- Лабораторное исследование  
- Обзор литературы
- Эпидемиологическое
- Методологическое

**Распознаваемые дизайны:**
- Рандомизированное контролируемое
- Ретроспективное/Проспективное
- Поперечное/Когортное
- Случай-контроль

### 4. Тематическая классификация

```python
classification = {
    'research_field': str,        # Область исследования
    'sub_fields': List[str],      # Подобласти
    'keywords': List[str],        # Ключевые слова
    'medical_specialties': List[str], # Медицинские специальности
    'research_methods': List[str], # Методы исследования
    'target_population': str,     # Целевая популяция
    'clinical_relevance': str,    # Клиническая значимость
    'innovation_level': str       # Уровень инновационности
}
```

**Поддерживаемые области:**
- Медицина, Стоматология
- Биология, Фармакология
- Общественное здравоохранение
- Междисциплинарные исследования

## 🔍 Источники данных

### Интегрированные API

1. **ORCID API**
   - Получение списка работ автора
   - Метаданные публикаций
   - Связи между соавторами

2. **Scopus API** (при наличии ключа)
   - Расширенные метаданные
   - Метрики цитирования
   - Информация о журналах

3. **PubMed API**
   - Медицинские публикации
   - Аннотации и MeSH термины
   - PMID идентификаторы

4. **CrossRef API**
   - Дополнительные метаданные по DOI
   - Информация о цитированиях
   - Данные о издателях

### Дедупликация

Система автоматически удаляет дубликаты на основе:
- DOI (приоритет)
- Точное совпадение названий
- Нормализованные заголовки

## 📈 Генерируемая аналитика

### Сводка публикаций

```python
publication_summary = {
    'total_analyzed': int,           # Общее количество
    'by_year': Dict[str, int],       # Распределение по годам
    'by_journal': Dict[str, int],    # По журналам
    'by_research_field': Dict[str, int], # По областям
    'author_roles': {                # Роли автора
        'first_author': int,
        'corresponding_author': int,
        'co_author': int
    },
    'average_citations': float,      # Среднее цитирований
    'h_index_estimate': int          # Оценка h-индекса
}
```

### Исследовательский профиль

```python
research_profile = {
    'primary_research_areas': List[Tuple[str, int]], # Основные области
    'research_evolution': Dict,      # Эволюция интересов
    'collaboration_intensity': str,  # Интенсивность сотрудничества
    'publication_productivity': Dict, # Продуктивность
    'research_impact': Dict,         # Научное влияние
    'specialization_score': float    # Коэффициент специализации
}
```

### Временной анализ

```python
temporal_analysis = {
    'publication_timeline': Dict[str, int], # Временная шкала
    'productivity_trend': str,       # Тренд продуктивности
    'recent_activity': {             # Недавняя активность
        'publications_last_3_years': int,
        'most_productive_year': str,
        'career_span': int
    },
    'career_stage': str              # Стадия карьеры
}
```

### Сеть сотрудничества

```python
collaboration_network = {
    'co_authors': Dict[str, int],    # Частота соавторства
    'institutions': Dict[str, int],   # Связанные институции
    'collaboration_score': float,    # Коэффициент сотрудничества
    'international_collaboration': bool # Международное сотрудничество
}
```

## 🔧 Настройки и конфигурация

### Переменные окружения

```bash
# Обязательные для полной функциональности
SCOPUS_API_KEY=your_scopus_key
PUBMED_API_KEY=your_pubmed_key  # Опционально
CROSSREF_API_KEY=your_crossref_key  # Опционально
```

### Параметры анализа

```python
# В PublicationAnalyzer.__init__()
self.max_publications_to_analyze = 50    # Максимум публикаций для анализа
self.analysis_timeout = 30               # Таймаут на одну публикацию (сек)
```

## 🌟 Интеграция в API

### Структура ответа

После успешного выполнения фазы 4.2, API ответ содержит:

```json
{
    "email": "author@email.com",
    "basic_info": { ... },
    "professional_info": { ... },
    "scientific_identifiers": { ... },
    "publications": [...],          // Расширенные данные публикаций
    "publication_analysis": {       // НОВОЕ: Глубокий анализ
        "total_publications": 25,
        "analyzed_publications": 20,
        "analysis_timestamp": 1672531200,
        "detailed_publications": [...],
        "publication_summary": { ... },
        "research_profile": { ... },
        "collaboration_network": { ... },
        "temporal_analysis": { ... }
    },
    "conclusions": [...],           // Улучшенные выводы
    "search_metadata": { ... }
}
```

### Улучшенные выводы

Система автоматически добавляет выводы на основе анализа:

```
"Проведен глубокий анализ 15 публикаций автора"
"Первый автор в 8 публикациях (основной исследователь)"
"Основная область исследований: Медицина"
"Стадия карьеры: Опытный исследователь"
"Оценка h-индекса: 12"
"Типы исследований: Клиническое исследование, Обзор литературы"
```

## 🧪 Тестирование

### Тестовый скрипт

```bash
python3 test_publication_analysis.py
```

**Проверяемые функции:**
- ✅ Инициализация PublicationAnalyzer
- ✅ Анализ отдельной публикации
- ✅ Интеграция в полный цикл анализа
- ✅ Условия запуска фазы 4.2
- ✅ Качество генерируемых выводов

### Ожидаемые результаты

- Для email с confidence > 10% запускается фаза 4.2
- Поле `publication_analysis` содержит структурированные данные
- Выводы обогащены информацией о научной деятельности
- Публикации содержат расширенные метаданные

## 🚨 Обработка ошибок

### Graceful degradation

- При недоступности внешних API используются базовые данные
- Ошибки анализа отдельных публикаций не останавливают общий процесс
- Логирование всех критических ошибок
- Автоматическое добавление информации об ошибках в выводы

### Мониторинг

```python
analysis_metadata = {
    'processing_time': float,        # Время обработки
    'data_sources': List[str],       # Использованные источники
    'analysis_completeness': float,  # Полнота анализа (0-1)
    'error_count': int              # Количество ошибок
}
```

## 📋 Примеры использования

### Прямое использование PublicationAnalyzer

```python
from services.publication_analyzer import PublicationAnalyzer

analyzer = PublicationAnalyzer()

author_info = {
    'full_name': 'Иванов Иван Иванович',
    'orcid_id': '0000-0002-1234-5678',
    'email': 'ivanov@university.edu',
    'publications': [...]
}

analysis = analyzer.analyze_author_publications(author_info)
```

### Через API

```bash
curl -X POST http://localhost:5003/api/email/search \
  -H "Content-Type: application/json" \
  -d '{"email": "researcher@university.edu", "force_refresh": true}'
```

## 🔮 Будущие улучшения

### Планируемые возможности

1. **Анализ co-citation networks** - анализ сетей социтирования
2. **Trending topics detection** - выявление трендовых тем
3. **Research impact prediction** - прогнозирование научного влияния
4. **Collaboration recommendations** - рекомендации по сотрудничеству
5. **Grant funding analysis** - анализ грантового финансирования

### Оптимизации

1. **Кэширование результатов** внешних API запросов
2. **Параллельная обработка** публикаций
3. **ML-модели** для улучшения классификации
4. **Интеграция с дополнительными** научными базами данных

---

**Статус:** ✅ Полностью реализовано и протестировано
**Версия:** 1.0.0
**Дата:** 2024-12-04
