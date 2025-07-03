"""
Конфигурация NLP модулей для анализа веб-страниц
Позволяет включать/отключать отдельные компоненты
"""

class NLPConfig:
    """Конфигурация NLP компонентов"""
    
    def __init__(self):
        # Основные настройки
        self.enabled = True  # Главный переключатель NLP
        
        # Модульные компоненты (можно включать/отключать независимо)
        self.modules = {
            'named_entity_recognition': {
                'enabled': True,
                'use_spacy_ru': True,
                'use_spacy_en': True,
                'use_natasha': True,  # Специально для русского языка
                'confidence_threshold': 0.7
            },
            
            'syntactic_analysis': {
                'enabled': True,
                'extract_dependencies': True,
                'analyze_relations': True,
                'max_sentence_length': 500
            },
            
            'professional_role_analysis': {
                'enabled': True,
                'use_semantic_classification': True,
                'role_confidence_threshold': 0.6,
                'include_academic_roles': True,
                'include_medical_roles': True,
                'include_management_roles': True
            },
            
            'email_owner_identification': {
                'enabled': True,
                'proximity_analysis': True,
                'semantic_markers': True,
                'context_window': 300,  # символов вокруг email
                'min_confidence': 0.5
            },
            
            'content_relevance_analysis': {
                'enabled': True,
                'sentiment_analysis': False,  # Пока отключено
                'topic_classification': True,
                'relevance_threshold': 0.3
            },
            
            'multilingual_support': {
                'enabled': True,
                'auto_detect_language': True,
                'supported_languages': ['ru', 'en'],
                'fallback_language': 'en'
            }
        }
        
        # Настройки производительности
        self.performance = {
            'max_text_length': 50000,  # Максимальная длина текста для NLP
            'batch_processing': False,
            'use_gpu': False,
            'timeout_seconds': 30
        }
        
        # Настройки моделей
        self.models = {
            'spacy_ru_model': 'ru_core_news_sm',
            'spacy_en_model': 'en_core_web_sm',
            'use_large_models': False,  # True для _lg моделей (лучше качество, больше ресурсов)
        }
    
    def is_module_enabled(self, module_name: str) -> bool:
        """Проверяет, включен ли конкретный модуль"""
        if not self.enabled:
            return False
        return self.modules.get(module_name, {}).get('enabled', False)
    
    def get_module_config(self, module_name: str) -> dict:
        """Возвращает конфигурацию конкретного модуля"""
        return self.modules.get(module_name, {})
    
    def enable_module(self, module_name: str):
        """Включает конкретный модуль"""
        if module_name in self.modules:
            self.modules[module_name]['enabled'] = True
    
    def disable_module(self, module_name: str):
        """Отключает конкретный модуль"""
        if module_name in self.modules:
            self.modules[module_name]['enabled'] = False
    
    def get_enabled_modules(self) -> list:
        """Возвращает список включенных модулей"""
        return [name for name, config in self.modules.items() if config.get('enabled', False)]

# Глобальный экземпляр конфигурации
nlp_config = NLPConfig()
