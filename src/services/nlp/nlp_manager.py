"""
Главный менеджер NLP системы
Координирует работу всех NLP модулей и предоставляет единый API
"""

import time
from typing import Dict, List, Any, Optional
import logging

from .config import nlp_config
from .base import NLPResult, ExtractedEntity, EmailContext, ProfessionalRole, NLPUtils
from .ner_module import NERModule
from .role_analysis_module import RoleAnalysisModule
from .email_owner_module import EmailOwnerModule

logger = logging.getLogger(__name__)

class NLPManager:
    """Главный менеджер NLP системы"""
    
    def __init__(self, config=None):
        self.config = config or nlp_config
        self.modules = {}
        self.is_initialized = False
        self.logger = logging.getLogger(__name__)
    
    def initialize(self) -> bool:
        """Инициализация всех NLP модулей"""
        if not self.config.enabled:
            self.logger.info("NLP система отключена в конфигурации")
            return True
        
        try:
            success = True
            
            # Инициализация модуля NER
            if self.config.is_module_enabled('named_entity_recognition'):
                ner_config = self.config.get_module_config('named_entity_recognition')
                ner_config.update(self.config.models)
                ner_config.update(self.config.performance)
                
                self.modules['ner'] = NERModule(ner_config)
                if not self.modules['ner'].initialize():
                    self.logger.warning("NER модуль не инициализирован")
                    success = False
            
            # Инициализация модуля анализа ролей
            if self.config.is_module_enabled('professional_role_analysis'):
                role_config = self.config.get_module_config('professional_role_analysis')
                role_config.update(self.config.performance)
                
                self.modules['roles'] = RoleAnalysisModule(role_config)
                if not self.modules['roles'].initialize():
                    self.logger.warning("Модуль анализа ролей не инициализирован")
                    success = False
            
            # Инициализация модуля идентификации владельцев email
            if self.config.is_module_enabled('email_owner_identification'):
                owner_config = self.config.get_module_config('email_owner_identification')
                
                self.modules['email_owner'] = EmailOwnerModule(owner_config)
                if not self.modules['email_owner'].initialize():
                    self.logger.warning("Модуль идентификации владельцев email не инициализирован")
                    success = False
            
            self.is_initialized = success
            
            if success:
                enabled_modules = list(self.modules.keys())
                self.logger.info(f"NLP система инициализирована. Активные модули: {enabled_modules}")
            else:
                self.logger.warning("NLP система инициализирована частично")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации NLP системы: {e}")
            return False
    
    def analyze_text(self, text: str, email: str = None, **kwargs) -> NLPResult:
        """
        Полный анализ текста с использованием всех доступных модулей
        
        Args:
            text: Текст для анализа
            email: Email адрес для специального анализа (опционально)
            **kwargs: Дополнительные параметры
            
        Returns:
            Результат NLP анализа
        """
        start_time = time.time()
        
        if not self.is_initialized or not self.config.enabled:
            self.logger.debug("NLP система не активна")
            return NLPResult(
                entities=[],
                email_contexts=[],
                professional_roles=[],
                language='unknown',
                processing_time=0.0
            )
        
        if not text or not text.strip():
            return NLPResult(
                entities=[],
                email_contexts=[],
                professional_roles=[],
                language='unknown',
                processing_time=0.0
            )
        
        try:
            # Определение языка
            language = kwargs.get('language') or NLPUtils.detect_language(text)
            
            # Результаты анализа
            entities = []
            email_contexts = []
            professional_roles = []
            metadata = {'modules_used': []}
            
            # Извлечение именованных сущностей
            if 'ner' in self.modules:
                try:
                    entities = self.modules['ner'].process(text, language=language)
                    metadata['modules_used'].append('ner')
                    self.logger.debug(f"NER извлек {len(entities)} сущностей")
                except Exception as e:
                    self.logger.error(f"Ошибка в NER модуле: {e}")
            
            # Анализ профессиональных ролей
            if 'roles' in self.modules:
                try:
                    professional_roles = self.modules['roles'].process(text, language=language)
                    metadata['modules_used'].append('roles')
                    self.logger.debug(f"Анализ ролей извлек {len(professional_roles)} ролей")
                except Exception as e:
                    self.logger.error(f"Ошибка в модуле анализа ролей: {e}")
            
            # Анализ владельцев email (если email указан)
            if email and 'email_owner' in self.modules:
                try:
                    owner_info = self.modules['email_owner'].process(
                        text, email, entities=entities, language=language
                    )
                    
                    if owner_info and owner_info.get('email_context'):
                        email_contexts.append(owner_info['email_context'])
                        metadata['email_owner_analysis'] = owner_info
                        metadata['modules_used'].append('email_owner')
                    
                except Exception as e:
                    self.logger.error(f"Ошибка в модуле владельцев email: {e}")
            
            processing_time = time.time() - start_time
            
            result = NLPResult(
                entities=entities,
                email_contexts=email_contexts,
                professional_roles=professional_roles,
                language=language,
                processing_time=processing_time,
                metadata=metadata
            )
            
            self.logger.debug(f"NLP анализ завершен за {processing_time:.3f} сек")
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка в NLP анализе: {e}")
            processing_time = time.time() - start_time
            return NLPResult(
                entities=[],
                email_contexts=[],
                professional_roles=[],
                language='unknown',
                processing_time=processing_time,
                metadata={'error': str(e)}
            )
    
    def extract_entities(self, text: str, language: str = None) -> List[ExtractedEntity]:
        """Извлечение только именованных сущностей"""
        if not self.is_initialized or 'ner' not in self.modules:
            return []
        
        try:
            return self.modules['ner'].process(text, language=language)
        except Exception as e:
            self.logger.error(f"Ошибка извлечения сущностей: {e}")
            return []
    
    def extract_professional_roles(self, text: str, language: str = None) -> List[ProfessionalRole]:
        """Извлечение только профессиональных ролей"""
        if not self.is_initialized or 'roles' not in self.modules:
            return []
        
        try:
            return self.modules['roles'].process(text, language=language)
        except Exception as e:
            self.logger.error(f"Ошибка извлечения ролей: {e}")
            return []
    
    def identify_email_owner(self, text: str, email: str, entities: List[ExtractedEntity] = None,
                           language: str = None) -> Dict[str, Any]:
        """Идентификация владельца email адреса"""
        if not self.is_initialized or 'email_owner' not in self.modules:
            return {}
        
        try:
            return self.modules['email_owner'].process(
                text, email, entities=entities, language=language
            )
        except Exception as e:
            self.logger.error(f"Ошибка идентификации владельца email: {e}")
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса NLP системы"""
        return {
            'enabled': self.config.enabled,
            'initialized': self.is_initialized,
            'modules': {
                name: module.is_ready() if hasattr(module, 'is_ready') else True
                for name, module in self.modules.items()
            },
            'enabled_config_modules': self.config.get_enabled_modules(),
            'configuration': {
                'max_text_length': self.config.performance.get('max_text_length'),
                'timeout_seconds': self.config.performance.get('timeout_seconds'),
                'use_gpu': self.config.performance.get('use_gpu')
            }
        }
    
    def enable_module(self, module_name: str) -> bool:
        """Включение конкретного модуля"""
        try:
            self.config.enable_module(module_name)
            
            # Пере-инициализация если нужно
            if module_name not in self.modules:
                return self.initialize()
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка включения модуля {module_name}: {e}")
            return False
    
    def disable_module(self, module_name: str) -> bool:
        """Отключение конкретного модуля"""
        try:
            self.config.disable_module(module_name)
            
            # Удаляем модуль из активных
            module_mapping = {
                'named_entity_recognition': 'ner',
                'professional_role_analysis': 'roles',
                'email_owner_identification': 'email_owner'
            }
            
            internal_name = module_mapping.get(module_name)
            if internal_name and internal_name in self.modules:
                self.modules[internal_name].cleanup()
                del self.modules[internal_name]
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка отключения модуля {module_name}: {e}")
            return False
    
    def cleanup(self):
        """Очистка всех ресурсов"""
        for name, module in self.modules.items():
            try:
                if hasattr(module, 'cleanup'):
                    module.cleanup()
            except Exception as e:
                self.logger.error(f"Ошибка очистки модуля {name}: {e}")
        
        self.modules.clear()
        self.is_initialized = False
        self.logger.info("NLP система очищена")

# Глобальный экземпляр менеджера
nlp_manager = NLPManager()
