"""
Базовые классы и интерфейсы для NLP модулей
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

@dataclass
class ExtractedEntity:
    """Извлеченная сущность"""
    text: str
    label: str
    confidence: float
    start_pos: int
    end_pos: int
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class EmailContext:
    """Контекст вокруг email адреса"""
    email: str
    before_text: str
    after_text: str
    full_sentence: str
    position: int
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ProfessionalRole:
    """Профессиональная роль"""
    title: str
    category: str  # academic, medical, management, technical, etc.
    confidence: float
    context: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class NLPResult:
    """Результат NLP анализа"""
    entities: List[ExtractedEntity]
    email_contexts: List[EmailContext]
    professional_roles: List[ProfessionalRole]
    language: str
    processing_time: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class BaseNLPModule(ABC):
    """Базовый класс для всех NLP модулей"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_initialized = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def initialize(self) -> bool:
        """Инициализация модуля (загрузка моделей и т.д.)"""
        pass
    
    @abstractmethod
    def process(self, text: str, **kwargs) -> Any:
        """Основная обработка текста"""
        pass
    
    def is_ready(self) -> bool:
        """Проверка готовности модуля к работе"""
        return self.is_initialized
    
    def cleanup(self):
        """Очистка ресурсов"""
        pass
    
    def get_config_value(self, key: str, default=None):
        """Получение значения конфигурации"""
        return self.config.get(key, default)

class TextPreprocessor:
    """Предобработка текста перед NLP анализом"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Базовая очистка текста"""
        if not text:
            return ""
        
        # Удаляем лишние пробелы и переносы
        text = ' '.join(text.split())
        
        # Убираем HTML entities если остались
        import html
        text = html.unescape(text)
        
        return text.strip()
    
    @staticmethod
    def extract_sentences(text: str, max_length: int = 1000) -> List[str]:
        """Разбивка на предложения с ограничением длины"""
        import re
        
        # Простая разбивка по предложениям
        sentences = re.split(r'[.!?]+\s+', text)
        
        result = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(sentence) <= max_length:
                result.append(sentence)
            else:
                # Разбиваем длинные предложения по запятым или точкам с запятой
                parts = re.split(r'[,;]\s+', sentence)
                for part in parts:
                    if len(part.strip()) > 0:
                        result.append(part.strip())
        
        return result
    
    @staticmethod
    def get_email_context(text: str, email: str, context_window: int = 300) -> EmailContext:
        """Извлечение контекста вокруг email адреса"""
        import re
        
        # Находим позицию email в тексте
        email_pattern = re.escape(email)
        match = re.search(email_pattern, text, re.IGNORECASE)
        
        if not match:
            return EmailContext(
                email=email,
                before_text="",
                after_text="",
                full_sentence="",
                position=-1
            )
        
        start_pos = match.start()
        end_pos = match.end()
        
        # Извлекаем контекст до и после
        before_start = max(0, start_pos - context_window)
        after_end = min(len(text), end_pos + context_window)
        
        before_text = text[before_start:start_pos].strip()
        after_text = text[end_pos:after_end].strip()
        
        # Пытаемся найти полное предложение
        sentence_start = before_start
        sentence_end = after_end
        
        # Ищем начало предложения
        for i in range(start_pos - 1, max(0, start_pos - context_window * 2), -1):
            if text[i] in '.!?':
                sentence_start = i + 1
                break
        
        # Ищем конец предложения
        for i in range(end_pos, min(len(text), end_pos + context_window * 2)):
            if text[i] in '.!?':
                sentence_end = i
                break
        
        full_sentence = text[sentence_start:sentence_end].strip()
        
        return EmailContext(
            email=email,
            before_text=before_text,
            after_text=after_text,
            full_sentence=full_sentence,
            position=start_pos
        )

class NLPUtils:
    """Утилиты для NLP обработки"""
    
    @staticmethod
    def detect_language(text: str) -> str:
        """Определение языка текста"""
        try:
            from langdetect import detect
            lang = detect(text[:1000])  # Используем первые 1000 символов
            return lang if lang in ['ru', 'en'] else 'en'
        except:
            # Простая эвристика по символам
            russian_chars = len([c for c in text if 'а' <= c.lower() <= 'я'])
            total_chars = len([c for c in text if c.isalpha()])
            
            if total_chars > 0 and russian_chars / total_chars > 0.3:
                return 'ru'
            return 'en'
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Нормализация имени"""
        if not name:
            return ""
        
        # Убираем лишние пробелы и приводим к правильному регистру
        parts = name.strip().split()
        normalized_parts = []
        
        for part in parts:
            if len(part) > 1:
                normalized_parts.append(part[0].upper() + part[1:].lower())
            elif len(part) == 1:
                normalized_parts.append(part.upper())
        
        return " ".join(normalized_parts)
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """Простой расчет схожести текстов"""
        if not text1 or not text2:
            return 0.0
        
        # Простая мера на основе общих слов
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
