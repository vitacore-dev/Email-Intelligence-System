"""
Модуль анализа профессиональных ролей и должностей
Определяет академические, медицинские, управленческие и технические роли
"""

import re
from typing import List, Dict, Any, Set
import logging

from .base import BaseNLPModule, ProfessionalRole, TextPreprocessor

logger = logging.getLogger(__name__)

class RoleAnalysisModule(BaseNLPModule):
    """Модуль анализа профессиональных ролей"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.role_patterns = {}
        self.semantic_keywords = {}
        self._init_patterns()
    
    def _init_patterns(self):
        """Инициализация паттернов для распознавания ролей"""
        
        # Академические роли
        self.role_patterns['academic'] = {
            'ru': [
                r'профессор[а-я]*',
                r'доцент[а-я]*',
                r'декан[а-я]*',
                r'ректор[а-я]*',
                r'проректор[а-я]*',
                r'заведующий\s+кафедр[а-я]*',
                r'зав\.?\s*кафедр[а-я]*',
                r'научный\s+руководитель',
                r'научный\s+сотрудник',
                r'старший\s+научный\s+сотрудник',
                r'ведущий\s+научный\s+сотрудник',
                r'главный\s+научный\s+сотрудник',
                r'младший\s+научный\s+сотрудник',
                r'аспирант[а-я]*',
                r'докторант[а-я]*',
                r'соискатель[а-я]*',
                r'магистрант[а-я]*',
                r'студент[а-я]*',
                r'преподаватель[а-я]*',
                r'лектор[а-я]*',
                r'ассистент[а-я]*'
            ],
            'en': [
                r'professor',
                r'associate\s+professor',
                r'assistant\s+professor',
                r'full\s+professor',
                r'dean',
                r'vice\s+dean',
                r'rector',
                r'chancellor',
                r'department\s+head',
                r'chair(?:man|woman|person)?',
                r'research(?:er)?',
                r'senior\s+research(?:er)?',
                r'principal\s+research(?:er)?',
                r'research\s+fellow',
                r'postdoc(?:toral)?',
                r'phd\s+student',
                r'graduate\s+student',
                r'doctoral\s+candidate',
                r'lecturer',
                r'instructor',
                r'teaching\s+assistant'
            ]
        }
        
        # Медицинские роли
        self.role_patterns['medical'] = {
            'ru': [
                r'врач[а-я]*',
                r'доктор[а-я]*',
                r'хирург[а-я]*',
                r'терапевт[а-я]*',
                r'педиатр[а-я]*',
                r'кардиолог[а-я]*',
                r'невролог[а-я]*',
                r'онколог[а-я]*',
                r'гинеколог[а-я]*',
                r'уролог[а-я]*',
                r'офтальмолог[а-я]*',
                r'стоматолог[а-я]*',
                r'анестезиолог[а-я]*',
                r'реаниматолог[а-я]*',
                r'главный\s+врач',
                r'заведующий\s+отделением',
                r'медицинская?\s+сестра',
                r'медбрат[а-я]*',
                r'фельдшер[а-я]*',
                r'медсестра',
                r'ординатор[а-я]*',
                r'интерн[а-я]*'
            ],
            'en': [
                r'doctor',
                r'physician',
                r'surgeon',
                r'cardiologist',
                r'neurologist',
                r'oncologist',
                r'pediatrician',
                r'gynecologist',
                r'urologist',
                r'ophthalmologist',
                r'dentist',
                r'anesthesiologist',
                r'radiologist',
                r'pathologist',
                r'psychiatrist',
                r'dermatologist',
                r'chief\s+medical\s+officer',
                r'medical\s+director',
                r'head\s+of\s+department',
                r'resident',
                r'intern',
                r'fellow',
                r'nurse',
                r'registered\s+nurse',
                r'rn',
                r'paramedic'
            ]
        }
        
        # Управленческие роли
        self.role_patterns['management'] = {
            'ru': [
                r'директор[а-я]*',
                r'генеральный\s+директор',
                r'исполнительный\s+директор',
                r'заместитель\s+директора',
                r'руководитель[а-я]*',
                r'начальник[а-я]*',
                r'управляющий',
                r'менеджер[а-я]*',
                r'старший\s+менеджер',
                r'ведущий\s+менеджер',
                r'главный\s+менеджер',
                r'координатор[а-я]*',
                r'администратор[а-я]*',
                r'президент[а-я]*',
                r'вице-президент[а-я]*',
                r'председатель[а-я]*',
                r'секретарь[а-я]*'
            ],
            'en': [
                r'director',
                r'managing\s+director',
                r'executive\s+director',
                r'ceo',
                r'chief\s+executive\s+officer',
                r'cto',
                r'chief\s+technology\s+officer',
                r'cfo',
                r'chief\s+financial\s+officer',
                r'manager',
                r'senior\s+manager',
                r'project\s+manager',
                r'program\s+manager',
                r'coordinator',
                r'administrator',
                r'president',
                r'vice\s+president',
                r'chairman',
                r'chairwoman',
                r'secretary',
                r'supervisor',
                r'team\s+lead(?:er)?'
            ]
        }
        
        # Технические роли
        self.role_patterns['technical'] = {
            'ru': [
                r'инженер[а-я]*',
                r'программист[а-я]*',
                r'разработчик[а-я]*',
                r'архитектор[а-я]*',
                r'системный\s+администратор',
                r'сисадмин[а-я]*',
                r'аналитик[а-я]*',
                r'консультант[а-я]*',
                r'специалист[а-я]*',
                r'эксперт[а-я]*',
                r'техник[а-я]*',
                r'лаборант[а-я]*',
                r'оператор[а-я]*'
            ],
            'en': [
                r'engineer',
                r'software\s+engineer',
                r'systems?\s+engineer',
                r'developer',
                r'programmer',
                r'architect',
                r'software\s+architect',
                r'system\s+administrator',
                r'analyst',
                r'business\s+analyst',
                r'data\s+analyst',
                r'consultant',
                r'specialist',
                r'expert',
                r'technician',
                r'operator',
                r'designer'
            ]
        }
        
        # Семантические ключевые слова для контекста
        self.semantic_keywords = {
            'academic': {
                'ru': ['университет', 'институт', 'академия', 'факультет', 'кафедра', 'лаборатория', 'исследование'],
                'en': ['university', 'institute', 'academy', 'faculty', 'department', 'laboratory', 'research']
            },
            'medical': {
                'ru': ['больница', 'клиника', 'поликлиника', 'медцентр', 'госпиталь', 'отделение'],
                'en': ['hospital', 'clinic', 'medical center', 'healthcare', 'department']
            },
            'management': {
                'ru': ['компания', 'организация', 'предприятие', 'фирма', 'корпорация'],
                'en': ['company', 'organization', 'enterprise', 'corporation', 'firm']
            },
            'technical': {
                'ru': ['разработка', 'технология', 'программирование', 'проект', 'система'],
                'en': ['development', 'technology', 'programming', 'project', 'system']
            }
        }
    
    def initialize(self) -> bool:
        """Инициализация модуля"""
        try:
            # Компилируем регулярные выражения для производительности
            self.compiled_patterns = {}
            for category, languages in self.role_patterns.items():
                self.compiled_patterns[category] = {}
                for lang, patterns in languages.items():
                    self.compiled_patterns[category][lang] = [
                        re.compile(pattern, re.IGNORECASE | re.UNICODE)
                        for pattern in patterns
                    ]
            
            self.is_initialized = True
            self.logger.info("Модуль анализа ролей успешно инициализирован")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации модуля анализа ролей: {e}")
            return False
    
    def process(self, text: str, language: str = None, **kwargs) -> List[ProfessionalRole]:
        """Извлечение профессиональных ролей из текста"""
        if not self.is_ready():
            self.logger.warning("Модуль анализа ролей не инициализирован")
            return []
        
        if not text or not text.strip():
            return []
        
        # Очистка текста
        clean_text = TextPreprocessor.clean_text(text)
        
        # Определение языка если не указан
        if not language:
            from .base import NLPUtils
            language = NLPUtils.detect_language(clean_text)
        
        roles = []
        
        # Извлекаем роли по категориям
        for category in self.role_patterns.keys():
            if self._is_category_enabled(category):
                category_roles = self._extract_roles_by_category(
                    clean_text, category, language
                )
                roles.extend(category_roles)
        
        # Фильтрация по уверенности
        confidence_threshold = self.get_config_value('role_confidence_threshold', 0.6)
        filtered_roles = [
            role for role in roles 
            if role.confidence >= confidence_threshold
        ]
        
        # Удаление дубликатов
        unique_roles = self._remove_duplicate_roles(filtered_roles)
        
        self.logger.debug(f"Извлечено {len(unique_roles)} профессиональных ролей")
        return unique_roles
    
    def _is_category_enabled(self, category: str) -> bool:
        """Проверка, включена ли категория ролей"""
        category_key = f'include_{category}_roles'
        return self.get_config_value(category_key, True)
    
    def _extract_roles_by_category(self, text: str, category: str, language: str) -> List[ProfessionalRole]:
        """Извлечение ролей конкретной категории"""
        roles = []
        
        if language not in self.compiled_patterns.get(category, {}):
            return roles
        
        patterns = self.compiled_patterns[category][language]
        
        for pattern in patterns:
            matches = pattern.finditer(text)
            
            for match in matches:
                role_text = match.group().strip()
                start_pos = match.start()
                end_pos = match.end()
                
                # Извлекаем контекст вокруг роли
                context = self._extract_context(text, start_pos, end_pos)
                
                # Рассчитываем уверенность
                confidence = self._calculate_role_confidence(
                    role_text, context, category, language
                )
                
                roles.append(ProfessionalRole(
                    title=role_text,
                    category=category,
                    confidence=confidence,
                    context=context,
                    metadata={
                        'start_pos': start_pos,
                        'end_pos': end_pos,
                        'language': language,
                        'pattern': pattern.pattern
                    }
                ))
        
        return roles
    
    def _extract_context(self, text: str, start_pos: int, end_pos: int, window: int = 200) -> str:
        """Извлечение контекста вокруг найденной роли"""
        context_start = max(0, start_pos - window)
        context_end = min(len(text), end_pos + window)
        return text[context_start:context_end].strip()
    
    def _calculate_role_confidence(self, role_text: str, context: str, category: str, language: str) -> float:
        """Расчет уверенности в определении роли"""
        base_confidence = 0.7
        
        # Корректировка на основе длины роли
        if len(role_text.split()) > 1:
            base_confidence += 0.1
        
        # Корректировка на основе семантических ключевых слов в контексте
        if self._has_semantic_context(context, category, language):
            base_confidence += 0.2
        
        # Корректировка на основе позиции в тексте (начало предложения)
        if self._is_sentence_start(context, role_text):
            base_confidence += 0.1
        
        # Корректировка на основе заглавных букв
        if role_text.istitle() or role_text.isupper():
            base_confidence += 0.05
        
        return min(base_confidence, 1.0)
    
    def _has_semantic_context(self, context: str, category: str, language: str) -> bool:
        """Проверка наличия семантических ключевых слов в контексте"""
        if category not in self.semantic_keywords:
            return False
        
        if language not in self.semantic_keywords[category]:
            return False
        
        context_lower = context.lower()
        keywords = self.semantic_keywords[category][language]
        
        return any(keyword in context_lower for keyword in keywords)
    
    def _is_sentence_start(self, context: str, role_text: str) -> bool:
        """Проверка, начинается ли роль с начала предложения"""
        # Ищем позицию роли в контексте
        role_pos = context.lower().find(role_text.lower())
        if role_pos == -1:
            return False
        
        # Проверяем, что перед ролью есть знак конца предложения или начало текста
        before_role = context[:role_pos].strip()
        if not before_role:
            return True
        
        # Проверяем последний символ перед ролью
        return before_role[-1] in '.!?'
    
    def _remove_duplicate_roles(self, roles: List[ProfessionalRole]) -> List[ProfessionalRole]:
        """Удаление дублирующихся ролей"""
        if not roles:
            return []
        
        # Группируем роли по тексту и категории
        role_groups = {}
        for role in roles:
            key = (role.title.lower(), role.category)
            if key not in role_groups:
                role_groups[key] = []
            role_groups[key].append(role)
        
        # Выбираем лучшую роль из каждой группы
        unique_roles = []
        for group in role_groups.values():
            # Сортируем по уверенности
            group.sort(key=lambda x: x.confidence, reverse=True)
            unique_roles.append(group[0])
        
        return unique_roles
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.compiled_patterns = {}
        self.logger.info("Модуль анализа ролей очищен")
