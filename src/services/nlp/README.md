# NLP Модуль для анализа веб-страниц

Модульная система NLP для контекстного извлечения информации вокруг email адресов в веб-страницах и PDF документах.

## Возможности

### Основные модули:

1. **Named Entity Recognition (NER)** - Распознавание именованных сущностей
   - Поддержка русского и английского языков
   - Использует spaCy и Natasha
   - Извлекает имена людей, организации, локации

2. **Professional Role Analysis** - Анализ профессиональных ролей
   - Академические роли (профессор, доцент, студент)
   - Медицинские роли (врач, хирург, медсестра)
   - Управленческие роли (директор, менеджер, руководитель)
   - Технические роли (инженер, программист, аналитик)

3. **Email Owner Identification** - Идентификация владельцев email
   - Анализ контекста вокруг email адреса
   - Определение наиболее вероятного владельца
   - Поддержка различных паттернов связи email-владелец

## Установка

### 1. Установка базовых зависимостей

```bash
pip install -r src/services/nlp/requirements.txt
```

### 2. Установка языковых моделей spaCy

```bash
# Русская модель
python -m spacy download ru_core_news_sm

# Английская модель  
python -m spacy download en_core_web_sm
```

Для лучшего качества можно установить большие модели:

```bash
# Большие модели (требуют больше ресурсов)
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
```

### 3. Проверка установки

```python
from src.services.nlp import nlp_manager

# Инициализация
success = nlp_manager.initialize()
print(f"NLP система инициализирована: {success}")

# Проверка статуса
status = nlp_manager.get_status()
print(status)
```

## Конфигурация

### Основная конфигурация

Файл: `src/services/nlp/config.py`

```python
from src.services.nlp.config import nlp_config

# Включение/отключение всей NLP системы
nlp_config.enabled = True

# Включение/отключение отдельных модулей
nlp_config.enable_module('named_entity_recognition')
nlp_config.disable_module('professional_role_analysis')

# Настройка производительности
nlp_config.performance['max_text_length'] = 100000
nlp_config.performance['timeout_seconds'] = 60
```

### Конфигурация модулей

```python
# NER модуль
nlp_config.modules['named_entity_recognition'].update({
    'confidence_threshold': 0.8,
    'use_natasha': True,
    'use_spacy_ru': True
})

# Модуль анализа ролей
nlp_config.modules['professional_role_analysis'].update({
    'role_confidence_threshold': 0.7,
    'include_academic_roles': True,
    'include_medical_roles': True
})

# Модуль идентификации владельцев email
nlp_config.modules['email_owner_identification'].update({
    'context_window': 400,
    'min_confidence': 0.6
})
```

## Использование

### Базовое использование

```python
from src.services.nlp import nlp_manager

# Инициализация
nlp_manager.initialize()

# Анализ текста с email
text = """
Профессор Иванов Иван Иванович - заведующий кафедрой хирургии.
Для связи: surgery-89@yandex.ru
"""

result = nlp_manager.analyze_text(text, email="surgery-89@yandex.ru")

print(f"Язык: {result.language}")
print(f"Найдено сущностей: {len(result.entities)}")
print(f"Найдено ролей: {len(result.professional_roles)}")
```

### Отдельное использование модулей

```python
# Только извлечение сущностей
entities = nlp_manager.extract_entities(text)
for entity in entities:
    print(f"{entity.text} ({entity.label}, {entity.confidence:.2f})")

# Только профессиональные роли
roles = nlp_manager.extract_professional_roles(text)
for role in roles:
    print(f"{role.title} ({role.category}, {role.confidence:.2f})")

# Только идентификация владельца email
owner_info = nlp_manager.identify_email_owner(text, "surgery-89@yandex.ru")
if owner_info.get('best_owner'):
    print(f"Владелец: {owner_info['best_owner']}")
```

### Интеграция с существующим анализатором

```python
from src.services.nlp.integration_example import EnhancedWebPageAnalyzer

analyzer = EnhancedWebPageAnalyzer()
analyzer.initialize_nlp()

# Анализ веб-страницы
result = analyzer.analyze_with_nlp(
    url="https://example.com/page",
    text_content=page_text,
    email="contact@example.com"
)

# Получение ключевой информации
enhanced_info = result['enhanced_info']
print(f"Обнаруженные персоны: {enhanced_info['detected_persons']}")
print(f"Наиболее вероятный владелец: {enhanced_info['most_likely_owner']}")
```

## Структура результатов

### NLPResult

```python
@dataclass
class NLPResult:
    entities: List[ExtractedEntity]           # Именованные сущности
    email_contexts: List[EmailContext]        # Контексты email адресов
    professional_roles: List[ProfessionalRole] # Профессиональные роли
    language: str                             # Определенный язык
    processing_time: float                    # Время обработки
    metadata: Dict[str, Any]                  # Дополнительные данные
```

### ExtractedEntity

```python
@dataclass
class ExtractedEntity:
    text: str              # Текст сущности
    label: str             # Тип (person, organization, location)
    confidence: float      # Уверенность (0-1)
    start_pos: int         # Начальная позиция в тексте
    end_pos: int           # Конечная позиция в тексте
    metadata: Dict[str, Any] # Дополнительная информация
```

### ProfessionalRole

```python
@dataclass
class ProfessionalRole:
    title: str             # Название роли
    category: str          # Категория (academic, medical, management, technical)
    confidence: float      # Уверенность (0-1)
    context: str           # Контекст вокруг роли
    metadata: Dict[str, Any] # Дополнительная информация
```

## Производительность

### Рекомендации по оптимизации

1. **Ограничение длины текста**:
   ```python
   nlp_config.performance['max_text_length'] = 50000
   ```

2. **Отключение неиспользуемых модулей**:
   ```python
   nlp_config.disable_module('professional_role_analysis')
   ```

3. **Использование меньших моделей spaCy**:
   ```python
   nlp_config.models['spacy_ru_model'] = 'ru_core_news_sm'  # вместо _lg
   ```

4. **Настройка timeout**:
   ```python
   nlp_config.performance['timeout_seconds'] = 30
   ```

### Типичная производительность

- Текст 1000 символов: ~0.1-0.3 сек
- Текст 10000 символов: ~0.5-1.5 сек  
- Текст 50000 символов: ~2-5 сек

## Расширение функциональности

### Добавление новых типов ролей

В файле `role_analysis_module.py`:

```python
# Добавление новых паттернов
self.role_patterns['custom_category'] = {
    'ru': [r'новая_роль[а-я]*'],
    'en': [r'new_role']
}
```

### Добавление новых паттернов владения email

В файле `email_owner_module.py`:

```python
# Добавление паттернов в _init_patterns
self.ownership_patterns['direct']['ru'].append(r'контакт:\s*{email}')
```

### Создание собственного модуля

```python
from src.services.nlp.base import BaseNLPModule

class CustomModule(BaseNLPModule):
    def initialize(self) -> bool:
        # Инициализация модуля
        return True
    
    def process(self, text: str, **kwargs):
        # Обработка текста
        return results
```

## Отладка и логирование

```python
import logging

# Включение отладочных сообщений
logging.getLogger('src.services.nlp').setLevel(logging.DEBUG)

# Проверка состояния модулей
status = nlp_manager.get_status()
print("Статус модулей:", status['modules'])
```

## Известные ограничения

1. **Языковая поддержка**: Пока поддерживаются только русский и английский языки
2. **Производительность**: Большие тексты (>100K символов) могут обрабатываться медленно
3. **Точность**: Качество извлечения зависит от качества исходного текста
4. **Модели**: Требуется установка языковых моделей spaCy

## Устранение неполадок

### Ошибка "Model not found"
```bash
python -m spacy download ru_core_news_sm
python -m spacy download en_core_web_sm
```

### Медленная работа
- Уменьшите `max_text_length`
- Используйте меньшие модели (_sm вместо _lg)
- Отключите неиспользуемые модули

### Низкая точность
- Увеличьте `context_window` для анализа email
- Понизьте пороги confidence
- Проверьте качество входного текста
