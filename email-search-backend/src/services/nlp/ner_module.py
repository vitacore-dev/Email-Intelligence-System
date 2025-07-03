"""
Модуль распознавания именованных сущностей (Named Entity Recognition)
Поддерживает spaCy для русского и английского языков, а также Natasha для русского
"""

import time
from typing import List, Dict, Any, Optional
import logging

from .base import BaseNLPModule, ExtractedEntity, TextPreprocessor, NLPUtils

logger = logging.getLogger(__name__)

class NERModule(BaseNLPModule):
    """Модуль распознавания именованных сущностей"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.spacy_ru = None
        self.spacy_en = None
        self.natasha_morph = None
        self.natasha_segmenter = None
        self.natasha_emb = None
        self.natasha_ner = None
        
        # Маппинг типов сущностей для разных библиотек
        self.entity_mapping = {
            'spacy': {
                'PERSON': 'person',
                'ORG': 'organization', 
                'GPE': 'location',
                'LOC': 'location',
                'MISC': 'misc'
            },
            'natasha': {
                'PER': 'person',
                'ORG': 'organization',
                'LOC': 'location'
            }
        }
    
    def initialize(self) -> bool:
        """Инициализация модулей NER"""
        try:
            success = True
            
            # Инициализация spaCy для русского языка
            if self.get_config_value('use_spacy_ru', True):
                success &= self._init_spacy_ru()
            
            # Инициализация spaCy для английского языка
            if self.get_config_value('use_spacy_en', True):
                success &= self._init_spacy_en()
            
            # Инициализация Natasha для русского языка
            if self.get_config_value('use_natasha', True):
                success &= self._init_natasha()
            
            self.is_initialized = success
            if success:
                self.logger.info("NER модуль успешно инициализирован")
            else:
                self.logger.warning("NER модуль инициализирован частично")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации NER модуля: {e}")
            return False
    
    def _init_spacy_ru(self) -> bool:
        """Инициализация spaCy для русского языка"""
        try:
            import spacy
            model_name = self.config.get('models', {}).get('spacy_ru_model', 'ru_core_news_sm')
            self.spacy_ru = spacy.load(model_name)
            self.logger.info(f"Загружена spaCy модель для русского: {model_name}")
            return True
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить spaCy для русского: {e}")
            return False
    
    def _init_spacy_en(self) -> bool:
        """Инициализация spaCy для английского языка"""
        try:
            import spacy
            model_name = self.config.get('models', {}).get('spacy_en_model', 'en_core_web_sm')
            self.spacy_en = spacy.load(model_name)
            self.logger.info(f"Загружена spaCy модель для английского: {model_name}")
            return True
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить spaCy для английского: {e}")
            return False
    
    def _init_natasha(self) -> bool:
        """Инициализация Natasha для русского языка"""
        try:
            from natasha import (
                Segmenter,
                MorphVocab, 
                NewsEmbedding,
                NewsNERTagger,
                Doc
            )
            
            self.natasha_segmenter = Segmenter()
            self.natasha_morph = MorphVocab()
            self.natasha_emb = NewsEmbedding()
            self.natasha_ner = NewsNERTagger(self.natasha_emb)
            
            self.logger.info("Загружена Natasha для русского языка")
            return True
        except Exception as e:
            self.logger.warning(f"Не удалось загрузить Natasha: {e}")
            return False
    
    def process(self, text: str, language: str = None, **kwargs) -> List[ExtractedEntity]:
        """Извлечение именованных сущностей из текста"""
        if not self.is_ready():
            self.logger.warning("NER модуль не инициализирован")
            return []
        
        if not text or not text.strip():
            return []
        
        # Очистка текста
        clean_text = TextPreprocessor.clean_text(text)
        
        # Определение языка если не указан
        if not language:
            language = NLPUtils.detect_language(clean_text)
        
        entities = []
        confidence_threshold = self.get_config_value('confidence_threshold', 0.7)
        
        # Обработка русского текста
        if language == 'ru':
            if self.spacy_ru:
                entities.extend(self._extract_with_spacy(clean_text, self.spacy_ru, 'spacy'))
            
            if self.natasha_ner:
                entities.extend(self._extract_with_natasha(clean_text))
        
        # Обработка английского текста
        elif language == 'en' and self.spacy_en:
            entities.extend(self._extract_with_spacy(clean_text, self.spacy_en, 'spacy'))
        
        # Фильтрация по confidence
        filtered_entities = [
            entity for entity in entities 
            if entity.confidence >= confidence_threshold
        ]
        
        # Удаление дубликатов
        unique_entities = self._remove_duplicates(filtered_entities)
        
        self.logger.debug(f"Извлечено {len(unique_entities)} именованных сущностей")
        return unique_entities
    
    def _extract_with_spacy(self, text: str, nlp_model, model_type: str) -> List[ExtractedEntity]:
        """Извлечение сущностей с помощью spaCy"""
        entities = []
        
        try:
            # Ограничиваем длину текста для обработки
            max_length = self.config.get('performance', {}).get('max_text_length', 50000)
            if len(text) > max_length:
                text = text[:max_length]
            
            doc = nlp_model(text)
            
            for ent in doc.ents:
                entity_label = self.entity_mapping[model_type].get(ent.label_, 'misc')
                
                # Простая оценка уверенности на основе длины и контекста
                confidence = self._calculate_spacy_confidence(ent, doc)
                
                entities.append(ExtractedEntity(
                    text=ent.text.strip(),
                    label=entity_label,
                    confidence=confidence,
                    start_pos=ent.start_char,
                    end_pos=ent.end_char,
                    metadata={
                        'model': model_type,
                        'original_label': ent.label_,
                        'lemma': ent.lemma_ if hasattr(ent, 'lemma_') else None
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Ошибка при извлечении сущностей с spaCy: {e}")
        
        return entities
    
    def _extract_with_natasha(self, text: str) -> List[ExtractedEntity]:
        """Извлечение сущностей с помощью Natasha"""
        entities = []
        
        try:
            from natasha import Doc
            
            # Ограничиваем длину текста
            max_length = self.config.get('performance', {}).get('max_text_length', 50000)
            if len(text) > max_length:
                text = text[:max_length]
            
            doc = Doc(text)
            doc.segment(self.natasha_segmenter)
            doc.tag_ner(self.natasha_ner)
            
            for span in doc.spans:
                entity_label = self.entity_mapping['natasha'].get(span.type, 'misc')
                
                # Natasha не предоставляет confidence, используем эвристику
                confidence = self._calculate_natasha_confidence(span, text)
                
                entities.append(ExtractedEntity(
                    text=span.text.strip(),
                    label=entity_label,
                    confidence=confidence,
                    start_pos=span.start,
                    end_pos=span.stop,
                    metadata={
                        'model': 'natasha',
                        'original_label': span.type,
                        'normal': span.normal if hasattr(span, 'normal') else None
                    }
                ))
                
        except Exception as e:
            self.logger.error(f"Ошибка при извлечении сущностей с Natasha: {e}")
        
        return entities
    
    def _calculate_spacy_confidence(self, ent, doc) -> float:
        """Расчет уверенности для spaCy сущностей"""
        # Базовая уверенность зависит от типа сущности
        base_confidence = {
            'PERSON': 0.8,
            'ORG': 0.7,
            'GPE': 0.6,
            'LOC': 0.6
        }.get(ent.label_, 0.5)
        
        # Корректировка на основе длины
        if len(ent.text) > 2:
            base_confidence += 0.1
        
        # Корректировка на основе позиции в предложении
        if ent.start > 0:
            prev_token = doc[ent.start - 1]
            if prev_token.pos_ in ['PROPN', 'NOUN']:
                base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def _calculate_natasha_confidence(self, span, text: str) -> float:
        """Расчет уверенности для Natasha сущностей"""
        # Базовая уверенность зависит от типа сущности
        base_confidence = {
            'PER': 0.8,
            'ORG': 0.7,
            'LOC': 0.6
        }.get(span.type, 0.5)
        
        # Корректировка на основе длины
        if len(span.text) > 2:
            base_confidence += 0.1
        
        # Корректировка на основе заглавных букв
        if span.text.istitle():
            base_confidence += 0.1
        
        return min(base_confidence, 1.0)
    
    def _remove_duplicates(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """Удаление дублирующихся сущностей"""
        if not entities:
            return []
        
        # Сортируем по позиции
        entities.sort(key=lambda x: (x.start_pos, x.end_pos))
        
        unique_entities = []
        for entity in entities:
            # Проверяем пересечение с уже добавленными сущностями
            is_duplicate = False
            for existing in unique_entities:
                if self._entities_overlap(entity, existing):
                    # Оставляем сущность с большей уверенностью
                    if entity.confidence > existing.confidence:
                        unique_entities.remove(existing)
                        break
                    else:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_entities.append(entity)
        
        return unique_entities
    
    def _entities_overlap(self, entity1: ExtractedEntity, entity2: ExtractedEntity) -> bool:
        """Проверка пересечения двух сущностей"""
        return not (entity1.end_pos <= entity2.start_pos or entity2.end_pos <= entity1.start_pos)
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.spacy_ru = None
        self.spacy_en = None
        self.natasha_morph = None
        self.natasha_segmenter = None
        self.natasha_emb = None
        self.natasha_ner = None
        self.logger.info("NER модуль очищен")
