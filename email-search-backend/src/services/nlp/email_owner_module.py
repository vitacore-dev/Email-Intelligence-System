"""
Модуль идентификации владельцев email адресов
Анализирует контекст вокруг email для определения наиболее вероятного владельца
"""

import re
from typing import List, Dict, Any, Tuple, Optional
import logging

from .base import BaseNLPModule, EmailContext, ExtractedEntity, TextPreprocessor, NLPUtils
from .specialized_name_extractor import SpecializedNameExtractor

logger = logging.getLogger(__name__)

class EmailOwnerModule(BaseNLPModule):
    """Модуль идентификации владельцев email"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.ownership_patterns = {}
        self.semantic_markers = {}
        self.specialized_extractor = None
        self._init_patterns()
    
    def _init_patterns(self):
        """Инициализация паттернов для определения владельца email"""
        
        # Прямые указания на владельца
        self.ownership_patterns = {
            'direct': {
                'ru': [
                    r'email:\s*{email}',
                    r'e-mail:\s*{email}',
                    r'почта:\s*{email}',
                    r'адрес:\s*{email}',
                    r'эл\.?\s*почта:\s*{email}',
                    r'электронная\s+почта:\s*{email}',
                    r'контакт:\s*{email}',
                    r'связаться:\s*{email}',
                    r'писать:\s*{email}',
                    r'обращаться:\s*{email}'
                ],
                'en': [
                    r'email:\s*{email}',
                    r'e-mail:\s*{email}',
                    r'contact:\s*{email}',
                    r'reach:\s*{email}',
                    r'write\s+to:\s*{email}',
                    r'contact\s+at:\s*{email}',
                    r'available\s+at:\s*{email}'
                ]
            },
            
            # Семантические маркеры близости
            'proximity': {
                'ru': [
                    # Полные русские ФИО в различных форматах
                    r'(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)',
                    
                    # Сокращенные формы (Фамилия И.О.)
                    r'(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)',
                    
                    # Инициалы + фамилия (И.О. Фамилия)
                    r'(?P<name>[А-ЯЁ]\.[А-ЯЁ]\.\s+[А-ЯЁ][а-яё]+)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[А-ЯЁ]\.[А-ЯЁ]\.\s+[А-ЯЁ][а-яё]+)',
                    
                    # Имя + фамилия
                    r'(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)',
                    
                    # С ролями и должностями
                    r'(?P<role>профессор|доцент|врач|директор|доктор|кандидат|заведующий|руководитель)[,\s]+(?P<name>[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]*)*)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<role>профессор|доцент|врач|директор|доктор|кандидат|заведующий|руководитель)[,\s]+(?P<name>[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]*)*)',
                    
                    # Авторство в научных статьях
                    r'[Aa]втор[ы]?[:\s]*(?P<name>[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]*)*)[,\s\-\(\)]*{email}',
                    r'[Kk]орреспондирующий\s+автор[:\s]*(?P<name>[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]*)*)[,\s\-\(\)]*{email}',
                    
                    # Контактная информация
                    r'[Kk]онтакт[ы]?[:\s]*(?P<name>[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]*)*)[,\s\-\(\)]*{email}',
                    r'[Дд]ля\s+связи[:\s]*(?P<name>[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]*)*)[,\s\-\(\)]*{email}'
                ],
                'en': [
                    # Full English names
                    r'(?P<name>[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+)',
                    
                    # First + Last name
                    r'(?P<name>[A-Z][a-z]+\s+[A-Z][a-z]+)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[A-Z][a-z]+\s+[A-Z][a-z]+)',
                    
                    # Initials + Last name (F.M. Smith)
                    r'(?P<name>[A-Z]\.[A-Z]\.\s+[A-Z][a-z]+)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[A-Z]\.[A-Z]\.\s+[A-Z][a-z]+)',
                    
                    # Last name + Initials (Smith, F.M.)
                    r'(?P<name>[A-Z][a-z]+,\s+[A-Z]\.[A-Z]\.)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<name>[A-Z][a-z]+,\s+[A-Z]\.[A-Z]\.)',
                    
                    # With roles and titles
                    r'(?P<role>Professor|Doctor|Director|Manager|PhD|MD|Dr)[,\s]+(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)[,\s\-\(\)]*{email}',
                    r'{email}[,\s\-\(\)]*(?P<role>Professor|Doctor|Director|Manager|PhD|MD|Dr)[,\s]+(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)',
                    
                    # Authorship patterns
                    r'[Aa]uthor[s]?[:\s]*(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)[,\s\-\(\)]*{email}',
                    r'[Cc]orresponding\s+author[:\s]*(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)[,\s\-\(\)]*{email}',
                    
                    # Contact information
                    r'[Cc]ontact[:\s]*(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)[,\s\-\(\)]*{email}',
                    r'[Rr]each\s+out\s+to[:\s]*(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)[,\s\-\(\)]*{email}'
                ]
            }
        }
        
        # Семантические маркеры владения
        self.semantic_markers = {
            'ownership': {
                'ru': [
                    'автор', 'ответственный', 'руководитель', 'заведующий', 'главный',
                    'контакт', 'связь', 'обращение', 'корреспонденция'
                ],
                'en': [
                    'author', 'responsible', 'head', 'chief', 'leader', 'manager',
                    'contact', 'correspondence', 'reach', 'write'
                ]
            },
            
            'personal_indicators': {
                'ru': [
                    'мой', 'моя', 'мои', 'личный', 'персональный', 'рабочий'
                ],
                'en': [
                    'my', 'personal', 'work', 'office', 'direct'
                ]
            }
        }
    
    def initialize(self) -> bool:
        """Инициализация модуля"""
        try:
            # Инициализируем специализированный экстрактор
            self.specialized_extractor = SpecializedNameExtractor()
            self.is_initialized = True
            self.logger.info("Модуль идентификации владельцев email успешно инициализирован")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации модуля владельцев email: {e}")
            return False
    
    def process(self, text: str, email: str, entities: List[ExtractedEntity] = None, 
                language: str = None, **kwargs) -> Dict[str, Any]:
        """
        Определение владельца email адреса
        
        Args:
            text: Исходный текст
            email: Email адрес для анализа
            entities: Предварительно извлеченные сущности
            language: Язык текста
            
        Returns:
            Словарь с информацией о владельце
        """
        if not self.is_ready():
            self.logger.warning("Модуль идентификации владельцев email не инициализирован")
            return {}
        
        if not text or not email:
            return {}
        
        # Очистка текста
        clean_text = TextPreprocessor.clean_text(text)
        
        # Определение языка если не указан
        if not language:
            language = NLPUtils.detect_language(clean_text)
        
        # Извлечение контекста вокруг email
        context_window = self.get_config_value('context_window', 300)
        email_context = TextPreprocessor.get_email_context(clean_text, email, context_window)
        
        if email_context.position == -1:
            return {}
        
        # Попытка использования специализированного экстрактора для русскоязычных научных текстов
        specialized_result = None
        if (self.specialized_extractor and 
            self.specialized_extractor.is_applicable(clean_text, language)):
            try:
                specialized_result = self.specialized_extractor.extract_precise_owner_name(clean_text, email)
                if specialized_result:
                    self.logger.info(f"Специализированный экстрактор нашел владельца: {specialized_result['owner_name']}")
            except Exception as e:
                self.logger.warning(f"Ошибка в специализированном экстракторе: {e}")
        
        # Анализ владельца
        owner_info = self._analyze_ownership(email_context, entities or [], language)
        
        # Интеграция результатов специализированного экстрактора
        if specialized_result:
            owner_info['specialized_extraction'] = specialized_result
            # Если специализированный экстрактор нашел результат с высокой уверенностью,
            # используем его как лучший кандидат
            if specialized_result.get('confidence', 0) > 0.9:
                owner_info['best_owner'] = {
                    'source': 'specialized_extractor',
                    'confidence': specialized_result['confidence'],
                    'data': specialized_result
                }
        
        # Добавляем контекстную информацию
        owner_info['email_context'] = email_context
        owner_info['analysis_confidence'] = self._calculate_overall_confidence(owner_info)
        
        return owner_info
    
    def _analyze_ownership(self, email_context: EmailContext, entities: List[ExtractedEntity], 
                          language: str) -> Dict[str, Any]:
        """Анализ владельца email на основе контекста"""
        
        result = {
            'potential_owners': [],
            'direct_indicators': [],
            'semantic_indicators': [],
            'proximity_matches': []
        }
        
        # Прямые указания на владельца
        direct_matches = self._find_direct_ownership(email_context, language)
        result['direct_indicators'] = direct_matches
        
        # Семантические индикаторы
        semantic_matches = self._find_semantic_indicators(email_context, language)
        result['semantic_indicators'] = semantic_matches
        
        # Анализ близости к именам из сущностей
        proximity_matches = self._analyze_entity_proximity(email_context, entities, language)
        result['proximity_matches'] = proximity_matches
        
        # Паттерн-анализ
        pattern_matches = self._analyze_patterns(email_context, language)
        result['pattern_matches'] = pattern_matches
        
        # Определение наиболее вероятного владельца
        best_owner = self._determine_best_owner(result, language)
        result['best_owner'] = best_owner
        
        return result
    
    def _find_direct_ownership(self, email_context: EmailContext, language: str) -> List[Dict[str, Any]]:
        """Поиск прямых указаний на владельца email"""
        matches = []
        
        patterns = self.ownership_patterns.get('direct', {}).get(language, [])
        
        for pattern_template in patterns:
            # Заменяем {email} на реальный email
            pattern = pattern_template.format(email=re.escape(email_context.email))
            
            # Ищем в полном предложении
            match = re.search(pattern, email_context.full_sentence, re.IGNORECASE)
            if match:
                matches.append({
                    'type': 'direct',
                    'pattern': pattern_template,
                    'matched_text': match.group(),
                    'confidence': 0.9
                })
        
        return matches
    
    def _find_semantic_indicators(self, email_context: EmailContext, language: str) -> List[Dict[str, Any]]:
        """Поиск семантических индикаторов владения"""
        indicators = []
        
        context_text = email_context.full_sentence.lower()
        
        # Проверяем маркеры владения
        ownership_markers = self.semantic_markers.get('ownership', {}).get(language, [])
        personal_markers = self.semantic_markers.get('personal_indicators', {}).get(language, [])
        
        for marker in ownership_markers:
            if marker in context_text:
                indicators.append({
                    'type': 'ownership_marker',
                    'marker': marker,
                    'confidence': 0.7
                })
        
        for marker in personal_markers:
            if marker in context_text:
                indicators.append({
                    'type': 'personal_marker',
                    'marker': marker,
                    'confidence': 0.8
                })
        
        return indicators
    
    def _analyze_entity_proximity(self, email_context: EmailContext, entities: List[ExtractedEntity], 
                                 language: str) -> List[Dict[str, Any]]:
        """Анализ близости email к именованным сущностям"""
        proximity_matches = []
        
        # Фильтруем только персоны
        person_entities = [e for e in entities if e.label == 'person']
        
        for entity in person_entities:
            # Проверяем, находится ли сущность в контексте email
            if self._is_entity_in_context(entity, email_context):
                distance = self._calculate_distance(entity, email_context)
                confidence = self._calculate_proximity_confidence(distance)
                
                proximity_matches.append({
                    'entity': entity,
                    'distance': distance,
                    'confidence': confidence,
                    'type': 'person_proximity'
                })
        
        # Сортируем по близости
        proximity_matches.sort(key=lambda x: x['distance'])
        
        return proximity_matches
    
    def _analyze_patterns(self, email_context: EmailContext, language: str) -> List[Dict[str, Any]]:
        """Анализ специальных паттернов владения"""
        pattern_matches = []
        
        patterns = self.ownership_patterns.get('proximity', {}).get(language, [])
        
        for pattern_template in patterns:
            # Заменяем {email} на реальный email
            pattern = pattern_template.format(email=re.escape(email_context.email))
            
            match = re.search(pattern, email_context.full_sentence, re.IGNORECASE)
            if match:
                match_info = {
                    'type': 'pattern_match',
                    'pattern': pattern_template,
                    'matched_text': match.group(),
                    'confidence': 0.8
                }
                
                # Извлекаем именованные группы
                if match.groupdict():
                    match_info['extracted_data'] = match.groupdict()
                
                pattern_matches.append(match_info)
        
        return pattern_matches
    
    def _is_entity_in_context(self, entity: ExtractedEntity, email_context: EmailContext) -> bool:
        """Проверка, находится ли сущность в контексте email"""
        # Проверяем пересечение позиций
        context_start = email_context.position - len(email_context.before_text)
        context_end = email_context.position + len(email_context.email) + len(email_context.after_text)
        
        return not (entity.end_pos <= context_start or entity.start_pos >= context_end)
    
    def _calculate_distance(self, entity: ExtractedEntity, email_context: EmailContext) -> int:
        """Расчет расстояния между сущностью и email"""
        email_start = email_context.position
        email_end = email_context.position + len(email_context.email)
        
        # Расстояние до ближайшей точки
        if entity.end_pos <= email_start:
            return email_start - entity.end_pos
        elif entity.start_pos >= email_end:
            return entity.start_pos - email_end
        else:
            return 0  # Пересекаются
    
    def _calculate_proximity_confidence(self, distance: int) -> float:
        """Расчет уверенности на основе расстояния"""
        if distance == 0:
            return 1.0
        elif distance <= 10:
            return 0.9
        elif distance <= 50:
            return 0.7
        elif distance <= 100:
            return 0.5
        elif distance <= 200:
            return 0.3
        else:
            return 0.1
    
    def _determine_best_owner(self, analysis_result: Dict[str, Any], language: str) -> Optional[Dict[str, Any]]:
        """Определение наиболее вероятного владельца"""
        candidates = []
        
        # Прямые указания имеют высший приоритет
        for direct in analysis_result.get('direct_indicators', []):
            candidates.append({
                'source': 'direct',
                'confidence': direct['confidence'],
                'data': direct
            })
        
        # Паттерны с извлеченными данными
        for pattern in analysis_result.get('pattern_matches', []):
            if 'extracted_data' in pattern:
                confidence = pattern['confidence']
                
                # Увеличиваем уверенность если есть и имя и роль
                if 'name' in pattern['extracted_data'] and 'role' in pattern['extracted_data']:
                    confidence += 0.1
                
                candidates.append({
                    'source': 'pattern',
                    'confidence': confidence,
                    'data': pattern
                })
        
        # Близость к персонам
        for proximity in analysis_result.get('proximity_matches', []):
            # Корректируем уверенность на основе семантических индикаторов
            adjusted_confidence = proximity['confidence']
            
            if analysis_result.get('semantic_indicators'):
                adjusted_confidence += 0.1
            
            candidates.append({
                'source': 'proximity',
                'confidence': adjusted_confidence,
                'data': proximity
            })
        
        # Выбираем лучшего кандидата
        if candidates:
            candidates.sort(key=lambda x: x['confidence'], reverse=True)
            best = candidates[0]
            
            # Проверяем минимальный порог уверенности
            min_confidence = self.get_config_value('min_confidence', 0.5)
            if best['confidence'] >= min_confidence:
                return best
        
        return None
    
    def _calculate_overall_confidence(self, owner_info: Dict[str, Any]) -> float:
        """Расчет общей уверенности в определении владельца"""
        if not owner_info.get('best_owner'):
            return 0.0
        
        base_confidence = owner_info['best_owner']['confidence']
        
        # Бонусы за дополнительные индикаторы
        if owner_info.get('semantic_indicators'):
            base_confidence += 0.05 * len(owner_info['semantic_indicators'])
        
        if owner_info.get('direct_indicators'):
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.logger.info("Модуль идентификации владельцев email очищен")
