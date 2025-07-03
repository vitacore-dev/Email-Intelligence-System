"""
NLP модуль для анализа веб-страниц и PDF документов
Предоставляет модульную систему для контекстного извлечения информации вокруг email адресов
"""

from .config import nlp_config, NLPConfig
from .base import (
    ExtractedEntity, 
    EmailContext, 
    ProfessionalRole, 
    NLPResult,
    BaseNLPModule,
    TextPreprocessor,
    NLPUtils
)
from .nlp_manager import nlp_manager, NLPManager
from .ner_module import NERModule
from .role_analysis_module import RoleAnalysisModule
from .email_owner_module import EmailOwnerModule

__version__ = "1.0.0"

__all__ = [
    # Конфигурация
    'nlp_config',
    'NLPConfig',
    
    # Базовые классы и структуры данных
    'ExtractedEntity',
    'EmailContext', 
    'ProfessionalRole',
    'NLPResult',
    'BaseNLPModule',
    'TextPreprocessor',
    'NLPUtils',
    
    # Основной менеджер
    'nlp_manager',
    'NLPManager',
    
    # Модули
    'NERModule',
    'RoleAnalysisModule', 
    'EmailOwnerModule'
]
