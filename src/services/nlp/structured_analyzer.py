"""
Модуль структурированного анализа веб-страниц с учётом HTML семантики
Решает проблемы распознавания сущностей, выявленные при анализе страницы Марапова
"""

import re
import logging
from typing import Dict, List, Any, Tuple, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from .base import BaseNLPModule, ExtractedEntity, NLPUtils

logger = logging.getLogger(__name__)

class StructuredWebPageAnalyzer(BaseNLPModule):
    """Анализатор структурированных веб-страниц с приоритизацией источников"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._init_patterns()
        self._init_transliteration_map()
        
    def _init_patterns(self):
        """Инициализация паттернов для распознавания"""
        
        # Русские ФИО паттерны (улучшенные)
        self.russian_name_patterns = [
            r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)', # Полное ФИО
            r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ]\.[А-ЯЁ]\.)',                # Фамилия И.О.
            r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ]\.\s*[А-ЯЁ]\.)',             # Фамилия И. О.
            r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)',                   # Фамилия Имя
        ]
        
        # Академические титулы и степени
        self.academic_titles = [
            r'к\.м\.н\.',      # кандидат медицинских наук
            r'д\.м\.н\.',      # доктор медицинских наук
            r'к\.т\.н\.',      # кандидат технических наук
            r'д\.т\.н\.',      # доктор технических наук
            r'к\.э\.н\.',      # кандидат экономических наук
            r'д\.э\.н\.',      # доктор экономических наук
            r'к\.ф\.н\.',      # кандидат философских наук
            r'д\.ф\.н\.',      # доктор философских наук
            r'проф\.',         # профессор
            r'доц\.',          # доцент
        ]
        
        # Должности в академических учреждениях
        self.academic_positions = [
            'профессор', 'доцент', 'заведующий', 'заведующая',
            'декан', 'ректор', 'проректор', 'заместитель',
            'директор', 'руководитель', 'начальник',
            'научный сотрудник', 'старший научный сотрудник',
            'ведущий научный сотрудник', 'главный научный сотрудник'
        ]
        
        # URL паттерны для персон
        self.url_person_patterns = [
            r'/([a-z]+)_([a-z]+)_([a-z]+)/',     # underscore separated
            r'/(\w+)-(\w+)-(\w+)/',              # hyphen separated
            r'/([a-z]+)\.([a-z]+)\.([a-z]+)/',   # dot separated
            r'/people/([a-z_-]+)/',              # people directory
            r'/staff/([a-z_-]+)/',               # staff directory
            r'/faculty/([a-z_-]+)/',             # faculty directory
        ]
        
    def _init_transliteration_map(self):
        """Инициализация карты транслитерации"""
        self.translit_map = {
            # Распространённые русские имена
            'aleksandr': 'Александр', 'alexey': 'Алексей', 'andrey': 'Андрей',
            'anton': 'Антон', 'artem': 'Артём', 'boris': 'Борис',
            'damir': 'Дамир', 'dmitry': 'Дмитрий', 'evgeny': 'Евгений',
            'igor': 'Игорь', 'ivan': 'Иван', 'mikhail': 'Михаил',
            'nikolay': 'Николай', 'oleg': 'Олег', 'pavel': 'Павел',
            'petr': 'Пётр', 'roman': 'Роман', 'sergey': 'Сергей',
            'vladimir': 'Владимир', 'yury': 'Юрий',
            
            # Распространённые русские фамилии
            'ivanov': 'Иванов', 'petrov': 'Петров', 'sidorov': 'Сидоров',
            'smirnov': 'Смирнов', 'volkov': 'Волков', 'popov': 'Попов',
            'marapov': 'Марапов', 'damirov': 'Дамиров',
            
            # Отчества
            'alexandrovich': 'Александрович', 'alexeyevich': 'Алексеевич',
            'andreyevich': 'Андреевич', 'antonovich': 'Антонович',
            'borisovich': 'Борисович', 'dmitrievich': 'Дмитриевич',
            'evgenyevich': 'Евгеньевич', 'igorevich': 'Игоревич',
            'ivanovich': 'Иванович', 'mikhailovich': 'Михайлович',
            'nikolayevich': 'Николаевич', 'olegovich': 'Олегович',
            'pavlovich': 'Павлович', 'petrovich': 'Петрович',
            'romanovich': 'Романович', 'sergeyevich': 'Сергеевич',
            'vladimirovich': 'Владимирович', 'yurievich': 'Юрьевич',
            'ildarovich': 'Ильдарович',
        }
        
    def initialize(self) -> bool:
        """Инициализация модуля"""
        try:
            self.is_initialized = True
            self.logger.info("Модуль структурированного анализа инициализирован")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка инициализации структурированного анализа: {e}")
            return False
    
    def process(self, html_content: str = None, text_content: str = None, 
                url: str = None, **kwargs) -> Dict[str, Any]:
        """
        Основной метод обработки с приоритизацией источников
        
        Args:
            html_content: HTML содержимое страницы
            text_content: Текстовое содержимое
            url: URL страницы
            
        Returns:
            Результат структурированного анализа
        """
        if not self.is_ready():
            return {}
            
        result = {
            'person_identified': False,
            'confidence_score': 0.0,
            'extraction_sources': [],
            'academic_context': {},
            'priority_entities': []
        }
        
        try:
            # 1. Анализ URL (высокий приоритет)
            if url:
                url_result = self._analyze_url(url)
                if url_result:
                    result['extraction_sources'].append(url_result)
            
            # 2. Анализ HTML структуры (очень высокий приоритет)
            if html_content:
                html_result = self._analyze_html_structure(html_content)
                if html_result:
                    result['extraction_sources'].extend(html_result)
            
            # 3. Анализ текстового содержимого (базовый приоритет)
            if text_content:
                text_result = self._analyze_text_content(text_content)
                if text_result:
                    result['extraction_sources'].extend(text_result)
            
            # 4. Объединение и ранжирование результатов
            result['priority_entities'] = self._merge_and_rank_entities(
                result['extraction_sources']
            )
            
            # 5. Определение лучшего кандидата
            if result['priority_entities']:
                best_entity = result['priority_entities'][0]
                result['person_identified'] = True
                result['confidence_score'] = best_entity['confidence']
            
            # 6. Анализ академического контекста
            if text_content:
                result['academic_context'] = self._extract_academic_context(text_content)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка в структурированном анализе: {e}")
            return result
    
    def _analyze_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Анализ URL для извлечения информации о персоне"""
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()
            
            for pattern in self.url_person_patterns:
                match = re.search(pattern, path)
                if match:
                    groups = match.groups()
                    
                    # Транслитерация в кириллицу
                    if len(groups) >= 3:
                        # Полное ФИО из URL
                        surname = self._transliterate(groups[0])
                        name = self._transliterate(groups[1]) 
                        patronymic = self._transliterate(groups[2])
                        
                        full_name = f"{surname} {name} {patronymic}"
                        
                        return {
                            'source': 'url',
                            'confidence': 0.9,
                            'person_name': full_name,
                            'extraction_method': 'url_pattern_matching',
                            'raw_data': groups
                        }
                    elif len(groups) == 1:
                        # Одна группа - попытка разделить
                        name_part = groups[0].replace('_', ' ').replace('-', ' ')
                        translated = self._transliterate_phrase(name_part)
                        
                        if translated:
                            return {
                                'source': 'url',
                                'confidence': 0.7,
                                'person_name': translated,
                                'extraction_method': 'url_single_group',
                                'raw_data': groups
                            }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа URL: {e}")
            return None
    
    def _analyze_html_structure(self, html_content: str) -> List[Dict[str, Any]]:
        """Анализ HTML структуры с приоритизацией тегов"""
        results = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Приоритеты тегов
            priority_tags = [
                ('title', 1.0),
                ('h1', 0.95),
                ('h2', 0.85),
                ('h3', 0.75),
                ('.name', 0.9),      # CSS класс для имён
                ('.person', 0.9),    # CSS класс для персон
                ('#name', 0.9),      # ID для имени
            ]
            
            for tag_selector, priority in priority_tags:
                elements = []
                
                if tag_selector.startswith('.'):
                    # CSS класс
                    elements = soup.find_all(attrs={'class': tag_selector[1:]})
                elif tag_selector.startswith('#'):
                    # ID
                    element = soup.find(attrs={'id': tag_selector[1:]})
                    if element:
                        elements = [element]
                else:
                    # Обычный тег
                    elements = soup.find_all(tag_selector)
                
                for element in elements:
                    text = element.get_text(strip=True)
                    person_names = self._extract_person_names_from_text(text)
                    
                    for person_name, confidence in person_names:
                        # Увеличиваем уверенность на основе приоритета тега
                        adjusted_confidence = min(confidence + (priority - 0.5), 1.0)
                        
                        results.append({
                            'source': f'html_{tag_selector}',
                            'confidence': adjusted_confidence,
                            'person_name': person_name,
                            'extraction_method': 'html_tag_analysis',
                            'tag_priority': priority,
                            'raw_text': text
                        })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа HTML структуры: {e}")
            return results
    
    def _analyze_text_content(self, text: str) -> List[Dict[str, Any]]:
        """Анализ текстового содержимого"""
        results = []
        
        try:
            person_names = self._extract_person_names_from_text(text)
            
            for person_name, confidence in person_names:
                # Проверяем контекст вокруг имени
                context_bonus = self._calculate_context_bonus(text, person_name)
                adjusted_confidence = min(confidence + context_bonus, 1.0)
                
                results.append({
                    'source': 'text_content',
                    'confidence': adjusted_confidence,
                    'person_name': person_name,
                    'extraction_method': 'text_pattern_matching',
                    'context_bonus': context_bonus
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа текстового содержимого: {e}")
            return results
    
    def _extract_person_names_from_text(self, text: str) -> List[Tuple[str, float]]:
        """Извлечение имён персон из текста с оценкой уверенности"""
        names = []
        
        for pattern in self.russian_name_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                full_match = match.group(0)
                groups = match.groups()
                
                # Определяем тип паттерна и уверенность
                if len(groups) == 3:
                    # Полное ФИО - высокая уверенность
                    confidence = 0.9
                elif len(groups) == 2 and '.' in groups[1]:
                    # Фамилия И.О. - средняя уверенность
                    confidence = 0.8
                else:
                    # Фамилия Имя - средняя уверенность
                    confidence = 0.7
                
                # Проверяем на академические титулы рядом
                title_bonus = self._check_academic_titles_nearby(text, match.span())
                confidence += title_bonus
                
                names.append((full_match, min(confidence, 1.0)))
        
        # Удаляем дубликаты и сортируем по уверенности
        unique_names = {}
        for name, conf in names:
            if name not in unique_names or unique_names[name] < conf:
                unique_names[name] = conf
        
        return sorted(unique_names.items(), key=lambda x: x[1], reverse=True)
    
    def _check_academic_titles_nearby(self, text: str, name_span: Tuple[int, int]) -> float:
        """Проверка наличия академических титулов рядом с именем"""
        start, end = name_span
        
        # Контекст вокруг имени (100 символов до и после)
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 100)
        context = text[context_start:context_end]
        
        bonus = 0.0
        
        # Проверяем академические титулы
        for title_pattern in self.academic_titles:
            if re.search(title_pattern, context, re.IGNORECASE):
                bonus += 0.1
        
        # Проверяем должности
        for position in self.academic_positions:
            if position.lower() in context.lower():
                bonus += 0.1
        
        return min(bonus, 0.3)  # Максимальный бонус 0.3
    
    def _calculate_context_bonus(self, text: str, person_name: str) -> float:
        """Расчёт бонуса на основе контекста"""
        bonus = 0.0
        
        # Ищем позицию имени в тексте
        name_pos = text.lower().find(person_name.lower())
        if name_pos == -1:
            return bonus
        
        # Контекст вокруг имени
        context_start = max(0, name_pos - 200)
        context_end = min(len(text), name_pos + len(person_name) + 200)
        context = text[context_start:context_end].lower()
        
        # Академические ключевые слова
        academic_keywords = [
            'профессор', 'доцент', 'кафедра', 'университет', 'институт',
            'академия', 'факультет', 'декан', 'ректор', 'заведующий',
            'доктор наук', 'кандидат наук', 'научный сотрудник'
        ]
        
        for keyword in academic_keywords:
            if keyword in context:
                bonus += 0.05
        
        return min(bonus, 0.2)  # Максимальный бонус 0.2
    
    def _transliterate(self, translit_word: str) -> str:
        """Транслитерация слова в кириллицу"""
        return self.translit_map.get(translit_word.lower(), translit_word.title())
    
    def _transliterate_phrase(self, phrase: str) -> str:
        """Транслитерация фразы в кириллицу"""
        words = phrase.split()
        translated_words = []
        
        for word in words:
            translated = self._transliterate(word)
            translated_words.append(translated)
        
        return ' '.join(translated_words)
    
    def _merge_and_rank_entities(self, extraction_sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Объединение и ранжирование извлечённых сущностей"""
        # Группируем по именам
        name_groups = {}
        
        for source in extraction_sources:
            person_name = source.get('person_name', '').strip()
            if not person_name:
                continue
            
            # Нормализуем имя для группировки
            normalized_name = self._normalize_name(person_name)
            
            if normalized_name not in name_groups:
                name_groups[normalized_name] = []
            
            name_groups[normalized_name].append(source)
        
        # Ранжируем группы
        ranked_entities = []
        
        for normalized_name, sources in name_groups.items():
            # Выбираем лучший источник для группы
            best_source = max(sources, key=lambda x: x.get('confidence', 0))
            
            # Рассчитываем итоговую уверенность
            total_confidence = sum(s.get('confidence', 0) for s in sources) / len(sources)
            source_count_bonus = min(len(sources) * 0.05, 0.2)  # Бонус за количество источников
            
            final_confidence = min(total_confidence + source_count_bonus, 1.0)
            
            ranked_entities.append({
                'person_name': best_source['person_name'],
                'normalized_name': normalized_name,
                'confidence': final_confidence,
                'source_count': len(sources),
                'sources': sources,
                'best_source': best_source
            })
        
        # Сортируем по уверенности
        ranked_entities.sort(key=lambda x: x['confidence'], reverse=True)
        
        return ranked_entities
    
    def _normalize_name(self, name: str) -> str:
        """Нормализация имени для группировки похожих вариантов"""
        # Убираем лишние пробелы и приводим к единому регистру
        normalized = ' '.join(name.split()).title()
        
        # Заменяем точки в инициалах
        normalized = re.sub(r'([А-ЯЁ])\.([А-ЯЁ])\.', r'\1.\2.', normalized)
        
        return normalized
    
    def _extract_academic_context(self, text: str) -> Dict[str, Any]:
        """Извлечение академического контекста"""
        context = {
            'academic_institutions': [],
            'positions': [],
            'degrees': [],
            'departments': []
        }
        
        try:
            # Поиск учебных заведений
            institution_patterns = [
                r'(университет[а-я]*)',
                r'(институт[а-я]*)',
                r'(академи[а-я]*)',
                r'(колледж[а-я]*)',
                r'(факультет[а-я]*)'
            ]
            
            for pattern in institution_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                context['academic_institutions'].extend(matches)
            
            # Поиск должностей
            for position in self.academic_positions:
                if position.lower() in text.lower():
                    context['positions'].append(position)
            
            # Поиск степеней
            for title_pattern in self.academic_titles:
                matches = re.findall(title_pattern, text, re.IGNORECASE)
                context['degrees'].extend(matches)
            
            # Поиск кафедр
            department_pattern = r'кафедр[а-я]*\s+([а-яё\s]+?)(?:[,.]|$)'
            matches = re.findall(department_pattern, text, re.IGNORECASE)
            context['departments'].extend([m.strip() for m in matches])
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения академического контекста: {e}")
        
        return context
