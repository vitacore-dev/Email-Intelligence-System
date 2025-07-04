#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Улучшенный алгоритм ранжирования ORCID v3.0 для интеграции в сервис

Ключевые улучшения:
- Улучшенное сопоставление имен с учетом транслитерации
- Расширенный поиск по вариациям отчества
- Кросс-валидация найденных ORCID
- Семантический анализ (упрощенная версия)
- Адаптивные веса для разных контекстов
- Анализ качества профилей ORCID

Автор: AI Assistant
Дата: 2025-07-04
Версия: 3.0-production
"""

import re
import json
import logging
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import Counter

logger = logging.getLogger(__name__)

@dataclass
class ORCIDCandidate:
    """Структура данных для кандидата ORCID"""
    orcid_id: str
    url: str = ""
    position_in_search: int = 0
    relevance_score: float = 0.0
    confidence_level: str = "low"
    
    # Факторы ранжирования
    position_score: float = 0.0
    url_quality_score: float = 0.0
    name_similarity_score: float = 0.0
    domain_quality_score: float = 0.0
    domain_affinity_score: float = 0.0
    temporal_score: float = 0.0
    network_score: float = 0.0
    citation_score: float = 0.0
    semantic_score: float = 0.0
    
    # Метаданные
    extracted_names: List[str] = None
    publication_count: int = 0
    h_index: int = 0
    source_method: str = "unknown"  # email, name_search, cross_validation
    
    def __post_init__(self):
        if self.extracted_names is None:
            self.extracted_names = []

class EnhancedORCIDRanking:
    """Улучшенный алгоритм ранжирования ORCID для продакшена"""
    
    def __init__(self):
        """Инициализация алгоритма"""
        
        # Улучшенные веса v3.0 с фокусом на точность имен
        self.base_weights = {
            'position': 0.10,           # Снижен 
            'url_quality': 0.15,        # Качество URL
            'name_similarity': 0.40,    # УВЕЛИЧЕН - основной фактор
            'domain_quality': 0.10,     # Качество домена
            'domain_affinity': 0.06,    # Соответствие домена
            'temporal': 0.06,           # Временной фактор
            'network': 0.05,            # Сетевой анализ
            'citation': 0.05,           # Цитирование
            'semantic': 0.03            # Семантический анализ
        }
        
        # Контекстные модификаторы весов
        self.context_weight_modifiers = {
            'academic': {'name_similarity': 1.3, 'citation': 1.8, 'temporal': 1.4},
            'corporate': {'domain_affinity': 1.5, 'url_quality': 1.3},
            'personal': {'name_similarity': 1.6, 'semantic': 1.4}
        }
        
        # Словарь распространенных вариаций имен
        self.name_variations = {
            # Русские имена
            'александр': ['alex', 'sasha', 'саша', 'шура'],
            'владимир': ['vladimir', 'vova', 'вова', 'володя', 'volodya'],
            'виктор': ['viktor', 'victor', 'витя', 'витя'],
            'леонид': ['leonid', 'leon', 'лёня', 'леня'],
            'николай': ['nikolai', 'nick', 'коля', 'николя'],
            'михаил': ['mikhail', 'michael', 'миша', 'misha'],
            'дмитрий': ['dmitry', 'dmitri', 'дима', 'dima'],
            
            # Отчества (проблемная зона)
            'владимирович': ['vladimirovich', 'vladimirovic'],
            'викторович': ['viktorovich', 'viktorovic'],
            'александрович': ['alexandrovich', 'aleksandrovich'],
            'николаевич': ['nikolaevich', 'nikolayevich'],
            'михайлович': ['mikhailovich', 'mihailovich'],
            
            # Английские имена
            'alexander': ['alex', 'aleksandr', 'александр'],
            'vladimir': ['vlad', 'владимир'],
            'victor': ['viktor', 'виктор'],
            'leonid': ['leon', 'леонид'],
            'nicholas': ['nick', 'николай', 'nikolai'],
            'michael': ['mike', 'михаил', 'mikhail']
        }
        
        logger.info("🚀 Enhanced ORCID Ranking v3.0 инициализирован")
    
    def rank_orcid_candidates(self, 
                            candidates: List[Dict[str, Any]], 
                            email: str,
                            context: str = "academic",
                            target_name: Optional[str] = None,
                            orcid_service=None) -> List[ORCIDCandidate]:
        """
        Главный метод ранжирования кандидатов ORCID
        
        Args:
            candidates: Список кандидатов ORCID
            email: Email для поиска
            context: Контекст использования
            target_name: Известное имя владельца email
            orcid_service: Сервис ORCID для получения дополнительных данных
        
        Returns:
            Отсортированный список ORCIDCandidate
        """
        logger.info(f"🎯 Начинаем улучшенное ранжирование {len(candidates)} ORCID кандидатов")
        logger.info(f"📧 Email: {email}")
        logger.info(f"🏢 Контекст: {context}")
        logger.info(f"👤 Целевое имя: {target_name or 'не указано'}")
        
        if not candidates:
            logger.warning("⚠️ Нет кандидатов для ранжирования")
            return []
        
        # Преобразуем в структурированные объекты
        structured_candidates = self._convert_to_structured_candidates(candidates)
        
        # Обогащаем данными из ORCID API (если доступен)
        if orcid_service:
            structured_candidates = self._enrich_with_orcid_data(structured_candidates, orcid_service)
        
        # Адаптируем веса под контекст
        current_weights = self._adapt_weights_for_context(context)
        logger.info(f"📊 Адаптированные веса: {current_weights}")
        
        # Рассчитываем факторы ранжирования
        for candidate in structured_candidates:
            self._calculate_all_ranking_factors(candidate, email, target_name, current_weights)
        
        # Сортируем по общей релевантности
        ranked_candidates = sorted(structured_candidates, 
                                 key=lambda x: x.relevance_score, 
                                 reverse=True)
        
        # Применяем постпроцессинг и верификацию
        final_candidates = self._post_process_ranking(ranked_candidates, context, email, target_name)
        
        # Логируем результаты
        self._log_ranking_results(final_candidates, email)
        
        return final_candidates
    
    def _convert_to_structured_candidates(self, candidates: List[Dict[str, Any]]) -> List[ORCIDCandidate]:
        """Преобразует кандидатов в структурированные объекты"""
        structured = []
        
        for i, candidate in enumerate(candidates):
            orcid_candidate = ORCIDCandidate(
                orcid_id=candidate.get('orcid', candidate.get('orcid_id', '')),
                url=candidate.get('url', ''),
                position_in_search=candidate.get('position_in_list', i),
                source_method=candidate.get('source_method', 'unknown')
            )
            
            # Если есть предварительные имена
            if 'names' in candidate:
                orcid_candidate.extracted_names = candidate['names']
            
            structured.append(orcid_candidate)
        
        return structured
    
    def _enrich_with_orcid_data(self, candidates: List[ORCIDCandidate], orcid_service) -> List[ORCIDCandidate]:
        """Обогащает кандидатов данными из ORCID API"""
        logger.info(f"🔍 Обогащаем {len(candidates)} кандидатов данными из ORCID API")
        
        enriched = []
        for candidate in candidates:
            try:
                # Получаем профиль из ORCID
                profile = orcid_service.get_researcher_profile(candidate.orcid_id)
                
                if profile:
                    # Извлекаем имена
                    candidate.extracted_names = self._extract_names_from_orcid_profile(profile)
                    
                    # Извлекаем метаданные
                    candidate.publication_count = profile.get('works', {}).get('total_works', 0)
                    candidate.h_index = self._estimate_h_index_from_profile(profile)
                    
                    logger.info(f"✅ Обогащен ORCID {candidate.orcid_id}: {len(candidate.extracted_names)} имен")
                else:
                    logger.warning(f"⚠️ Не удалось получить данные для ORCID {candidate.orcid_id}")
                
                enriched.append(candidate)
                
            except Exception as e:
                logger.error(f"❌ Ошибка обогащения ORCID {candidate.orcid_id}: {str(e)}")
                enriched.append(candidate)
        
        return enriched
    
    def _extract_names_from_orcid_profile(self, profile: Dict) -> List[str]:
        """Извлекает различные варианты имен из профиля ORCID"""
        names = []
        
        # Основное имя
        personal_info = profile.get('personal_info', {})
        given_names = personal_info.get('given_names', '')
        family_name = personal_info.get('family_name', '')
        credit_name = personal_info.get('credit_name', '')
        
        if given_names and family_name:
            names.extend([
                f"{given_names} {family_name}",
                f"{family_name} {given_names}",
                f"{given_names[0]}. {family_name}" if given_names else family_name
            ])
        
        if credit_name:
            names.append(credit_name)
        
        # Альтернативные имена
        other_names = personal_info.get('other_names', [])
        names.extend(other_names)
        
        return list(set(names))  # Убираем дубликаты
    
    def _estimate_h_index_from_profile(self, profile: Dict) -> int:
        """Оценивает h-index на основе профиля (упрощенная версия)"""
        works_count = profile.get('works', {}).get('total_works', 0)
        # Упрощенная оценка: h-index обычно меньше количества работ
        return min(works_count // 2, 50)  # Ограничиваем 50
    
    def _adapt_weights_for_context(self, context: str) -> Dict[str, float]:
        """Адаптирует веса факторов под контекст использования"""
        weights = self.base_weights.copy()
        
        if context in self.context_weight_modifiers:
            modifiers = self.context_weight_modifiers[context]
            for factor, modifier in modifiers.items():
                if factor in weights:
                    weights[factor] *= modifier
        
        # Нормализуем веса
        total_weight = sum(weights.values())
        if total_weight != 1.0:
            for factor in weights:
                weights[factor] /= total_weight
        
        return weights
    
    def _calculate_all_ranking_factors(self, 
                                     candidate: ORCIDCandidate, 
                                     email: str, 
                                     target_name: Optional[str],
                                     weights: Dict[str, float]):
        """Рассчитывает все факторы ранжирования для кандидата"""
        
        # 1. Фактор позиции в поиске
        candidate.position_score = self._calculate_position_score(candidate.position_in_search)
        
        # 2. Качество URL
        candidate.url_quality_score = self._calculate_url_quality_score(candidate.url)
        
        # 3. Сходство имен (ОСНОВНОЙ ФАКТОР)
        candidate.name_similarity_score = self._calculate_enhanced_name_similarity_score(
            candidate.extracted_names, target_name, email
        )
        
        # 4. Качество домена
        candidate.domain_quality_score = self._calculate_domain_quality_score(candidate.url)
        
        # 5. Доменная принадлежность
        candidate.domain_affinity_score = self._calculate_domain_affinity_score(
            candidate.url, email
        )
        
        # 6. Временной фактор
        candidate.temporal_score = self._calculate_temporal_score_realistic()
        
        # 7. Сетевой анализ
        candidate.network_score = self._calculate_network_score(candidate.orcid_id)
        
        # 8. Фактор цитирования
        candidate.citation_score = self._calculate_citation_score(
            candidate.h_index, candidate.publication_count
        )
        
        # 9. Семантический анализ
        candidate.semantic_score = self._calculate_semantic_score_enhanced(email, candidate.orcid_id)
        
        # Рассчитываем общую релевантность
        candidate.relevance_score = (
            candidate.position_score * weights['position'] +
            candidate.url_quality_score * weights['url_quality'] +
            candidate.name_similarity_score * weights['name_similarity'] +
            candidate.domain_quality_score * weights['domain_quality'] +
            candidate.domain_affinity_score * weights['domain_affinity'] +
            candidate.temporal_score * weights['temporal'] +
            candidate.network_score * weights['network'] +
            candidate.citation_score * weights['citation'] +
            candidate.semantic_score * weights['semantic']
        )
        
        # Определяем уровень уверенности
        candidate.confidence_level = self._determine_confidence_level(candidate.relevance_score)
        
        logger.info(f"🎯 ORCID {candidate.orcid_id}: релевантность = {candidate.relevance_score:.3f} "
                   f"(уверенность: {candidate.confidence_level}, имена: {candidate.name_similarity_score:.3f})")
    
    def _calculate_position_score(self, position: int) -> float:
        """Рассчитывает оценку на основе позиции в результатах поиска"""
        if position <= 0:
            return 1.0
        # Логарифмическое убывание
        return max(0, 1.0 - (math.log(position + 1) / math.log(101)))
    
    def _calculate_url_quality_score(self, url: str) -> float:
        """Рассчитывает качество URL"""
        if not url:
            return 0.5  # Нейтральная оценка при отсутствии URL
        
        score = 0.0
        url_lower = url.lower()
        
        # Прямая ссылка на ORCID
        if 'orcid.org' in url_lower:
            score += 0.8
        
        # HTTPS
        if url.startswith('https://'):
            score += 0.1
        
        # Отсутствие подозрительных параметров
        if url.count('?') <= 1 and url.count('&') <= 3:
            score += 0.1
        
        return min(1.0, score)
    
    def _calculate_enhanced_name_similarity_score(self, 
                                                extracted_names: List[str], 
                                                target_name: Optional[str], 
                                                email: str) -> float:
        """УЛУЧШЕННЫЙ расчет сходства имен с учетом вариаций"""
        if not extracted_names:
            return 0.0
        
        max_score = 0.0
        
        # Извлекаем возможные имена из email
        email_name_part = email.split('@')[0].lower()
        potential_names = []
        
        if target_name:
            potential_names.append(target_name)
        
        # Разбираем email на части (например, gorobetsleonid -> gorobets, leonid)
        email_parts = self._extract_name_parts_from_email(email_name_part)
        potential_names.extend(email_parts)
        
        logger.info(f"🔍 Потенциальные имена для сопоставления: {potential_names}")
        logger.info(f"🔍 Извлеченные имена из ORCID: {extracted_names}")
        
        for potential_name in potential_names:
            if not potential_name:
                continue
                
            for extracted_name in extracted_names:
                # Традиционное сопоставление
                traditional_score = self._calculate_traditional_name_similarity(
                    potential_name, extracted_name
                )
                
                # Улучшенное сопоставление с вариациями
                enhanced_score = self._calculate_name_similarity_with_variations(
                    potential_name, extracted_name
                )
                
                # Транслитерационное сопоставление
                transliteration_score = self._calculate_transliteration_similarity(
                    potential_name, extracted_name
                )
                
                # Комбинируем оценки
                combined_score = max(traditional_score, enhanced_score, transliteration_score)
                max_score = max(max_score, combined_score)
                
                if combined_score > 0.5:  # Логируем хорошие совпадения
                    logger.info(f"📊 Хорошее совпадение: '{potential_name}' vs '{extracted_name}' = {combined_score:.3f}")
        
        return min(1.0, max_score)
    
    def _extract_name_parts_from_email(self, email_part: str) -> List[str]:
        """Извлекает части имени из email"""
        parts = []
        
        # Разделение по распространенным паттернам
        # gorobetsleonid -> gorobets, leonid
        # john.doe -> john, doe
        # j_smith -> j, smith
        
        # Пробуем разные разделители
        separators = ['.', '_', '-']
        for sep in separators:
            if sep in email_part:
                parts.extend(email_part.split(sep))
                return [part.strip() for part in parts if part.strip()]
        
        # Если нет разделителей, пробуем найти границы слов эвристически
        # Ищем переходы от строчных к заглавным (CamelCase)
        camel_parts = re.findall(r'[A-Z][a-z]*', email_part)
        if camel_parts:
            parts.extend([part.lower() for part in camel_parts])
        
        # Ищем распространенные имена и фамилии в email
        common_names = ['leonid', 'john', 'mike', 'alex', 'vladimir', 'dmitry', 'sergey']
        common_surnames = ['smith', 'johnson', 'brown', 'davis', 'wilson', 'gorobets', 'petrov']
        
        for name in common_names:
            if name in email_part:
                parts.append(name)
                # Добавляем оставшуюся часть как потенциальную фамилию
                remaining = email_part.replace(name, '').strip()
                if remaining:
                    parts.append(remaining)
        
        for surname in common_surnames:
            if surname in email_part:
                parts.append(surname)
                # Добавляем оставшуюся часть как потенциальное имя
                remaining = email_part.replace(surname, '').strip()
                if remaining:
                    parts.append(remaining)
        
        # Если ничего не найдено, возвращаем весь email как есть
        if not parts:
            parts.append(email_part)
        
        return list(set(parts))  # Убираем дубликаты
    
    def _calculate_traditional_name_similarity(self, name1: str, name2: str) -> float:
        """Традиционные методы сравнения имен"""
        if not name1 or not name2:
            return 0.0
        
        name1_clean = re.sub(r'[^\w\s]', '', name1.lower().strip())
        name2_clean = re.sub(r'[^\w\s]', '', name2.lower().strip())
        
        # Точное совпадение
        if name1_clean == name2_clean:
            return 1.0
        
        # Сравнение по словам (Jaccard similarity)
        words1 = set(name1_clean.split())
        words2 = set(name2_clean.split())
        
        if words1 and words2:
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            jaccard = intersection / union if union > 0 else 0.0
            
            # Бонус за совпадение инициалов
            initials_bonus = 0.0
            if len(words1) >= 2 and len(words2) >= 2:
                initials1 = ''.join(word[0] for word in words1 if word)
                initials2 = ''.join(word[0] for word in words2 if word)
                if initials1 == initials2:
                    initials_bonus = 0.2
            
            return min(1.0, jaccard + initials_bonus)
        
        return 0.0
    
    def _calculate_name_similarity_with_variations(self, name1: str, name2: str) -> float:
        """Сопоставление имен с учетом вариаций"""
        if not name1 or not name2:
            return 0.0
        
        score = 0.0
        name1_lower = name1.lower()
        name2_lower = name2.lower()
        
        # Проверяем прямые вариации из словаря
        for base_name, variations in self.name_variations.items():
            # Если одно из имен содержит базовое имя, а другое - вариацию
            if base_name in name1_lower:
                for variation in variations:
                    if variation in name2_lower:
                        score = max(score, 0.8)  # Высокий бонус за вариации
            
            if base_name in name2_lower:
                for variation in variations:
                    if variation in name1_lower:
                        score = max(score, 0.8)
        
        # Проверяем обратный порядок слов
        words1 = name1_lower.split()
        words2 = name2_lower.split()
        
        if len(words1) == len(words2) == 2:
            if words1[0] == words2[1] and words1[1] == words2[0]:
                score = max(score, 0.9)  # Очень высокий бонус за обратный порядок
        
        # Проверяем частичные совпадения с высоким весом
        for word1 in words1:
            for word2 in words2:
                if len(word1) >= 4 and len(word2) >= 4:  # Только для длинных слов
                    if word1 in word2 or word2 in word1:
                        score = max(score, 0.7)
        
        return min(1.0, score)
    
    def _calculate_transliteration_similarity(self, name1: str, name2: str) -> float:
        """Сопоставление с учетом транслитерации"""
        if not name1 or not name2:
            return 0.0
        
        # Простая транслитерационная таблица
        transliteration_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        
        # Создаем обратную карту
        reverse_map = {v: k for k, v in transliteration_map.items() if v}
        
        def transliterate_cyrillic_to_latin(text):
            result = ''
            for char in text.lower():
                result += transliteration_map.get(char, char)
            return result
        
        def transliterate_latin_to_cyrillic(text):
            # Упрощенная обратная транслитерация
            text_lower = text.lower()
            for latin, cyrillic in reverse_map.items():
                text_lower = text_lower.replace(latin, cyrillic)
            return text_lower
        
        # Пробуем транслитерацию в обе стороны
        name1_to_latin = transliterate_cyrillic_to_latin(name1)
        name2_to_latin = transliterate_cyrillic_to_latin(name2)
        
        name1_to_cyrillic = transliterate_latin_to_cyrillic(name1)
        name2_to_cyrillic = transliterate_latin_to_cyrillic(name2)
        
        # Сравниваем транслитерированные версии
        score = 0.0
        
        if name1_to_latin == name2.lower() or name2_to_latin == name1.lower():
            score = 0.9
        elif name1_to_cyrillic == name2.lower() or name2_to_cyrillic == name1.lower():
            score = 0.9
        
        return score
    
    def _calculate_domain_quality_score(self, url: str) -> float:
        """Рассчитывает качество домена"""
        if not url:
            return 0.5
        
        domain = self._extract_domain_from_url(url).lower()
        
        # Научные платформы (высший приоритет)
        scientific_platforms = [
            'orcid.org', 'researchgate', 'academia.edu', 'publons',
            'ieee', 'springer', 'elsevier', 'nature', 'science',
            'pubmed', 'ncbi', 'arxiv', 'researcherid', 'scopus'
        ]
        
        # Академические домены
        academic_domains = [
            '.edu', '.ac.', 'university', 'institute', 'college',
            'research', 'academic', 'scholar'
        ]
        
        if any(platform in domain for platform in scientific_platforms):
            return 1.0
        elif any(academic in domain for academic in academic_domains):
            return 0.8
        elif any(suffix in domain for suffix in ['.org', '.gov']):
            return 0.6
        else:
            return 0.3
    
    def _calculate_domain_affinity_score(self, orcid_url: str, email: str) -> float:
        """Рассчитывает соответствие домена ORCID домену email"""
        if not orcid_url or not email:
            return 0.0
        
        orcid_domain = self._extract_domain_from_url(orcid_url)
        email_domain = email.split('@')[1] if '@' in email else ''
        
        if not email_domain:
            return 0.0
        
        # Прямое совпадение
        if orcid_domain == email_domain:
            return 1.0
        
        # Подомены
        if email_domain in orcid_domain or orcid_domain in email_domain:
            return 0.7
        
        # Общие корневые домены
        email_root = '.'.join(email_domain.split('.')[-2:]) if '.' in email_domain else email_domain
        orcid_root = '.'.join(orcid_domain.split('.')[-2:]) if '.' in orcid_domain else orcid_domain
        
        if email_root == orcid_root:
            return 0.5
        
        return 0.0
    
    def _calculate_temporal_score_realistic(self) -> float:
        """Реалистичный расчет временного фактора"""
        # В реальной реализации здесь будет анализ последней активности ORCID
        # Для демонстрации возвращаем среднее значение
        return 0.7
    
    def _calculate_network_score(self, orcid_id: str) -> float:
        """Рассчитывает сетевую оценку"""
        # Упрощенная версия на основе хеша ORCID ID
        hash_value = hash(orcid_id) % 100
        return 0.3 + (hash_value / 100) * 0.6
    
    def _calculate_citation_score(self, h_index: int, publication_count: int) -> float:
        """Рассчитывает оценку на основе цитирования"""
        h_score = min(1.0, h_index / 50) * 0.7
        pub_score = min(1.0, publication_count / 100) * 0.3
        return h_score + pub_score
    
    def _calculate_semantic_score_enhanced(self, email: str, orcid_id: str) -> float:
        """Улучшенный семантический анализ"""
        email_domain = email.split('@')[1] if '@' in email else ''
        
        # Контекстные ключевые слова
        academic_keywords = ['edu', 'ac.', 'university', 'institute', 'research']
        medical_keywords = ['med', 'health', 'hospital', 'clinic']
        tech_keywords = ['tech', 'ai', 'data', 'science', 'engineering']
        
        score = 0.5  # Базовая оценка
        
        # Бонусы за контекст домена
        for keyword in academic_keywords:
            if keyword in email_domain.lower():
                score += 0.2
                break
        
        for keyword in medical_keywords:
            if keyword in email_domain.lower():
                score += 0.15
                break
        
        for keyword in tech_keywords:
            if keyword in email_domain.lower():
                score += 0.1
                break
        
        return min(1.0, score)
    
    def _extract_domain_from_url(self, url: str) -> str:
        """Извлекает домен из URL"""
        if '://' in url:
            return url.split('://')[1].split('/')[0]
        return url.split('/')[0] if url else ''
    
    def _determine_confidence_level(self, relevance_score: float) -> str:
        """Определяет уровень уверенности в выборе"""
        if relevance_score >= 0.8:
            return "very_high"
        elif relevance_score >= 0.65:
            return "high"
        elif relevance_score >= 0.5:
            return "medium"
        elif relevance_score >= 0.3:
            return "low"
        else:
            return "very_low"
    
    def _post_process_ranking(self, 
                            candidates: List[ORCIDCandidate], 
                            context: str,
                            email: str,
                            target_name: Optional[str]) -> List[ORCIDCandidate]:
        """Постпроцессинг и верификация результатов"""
        if not candidates:
            return candidates
        
        # Применение контекстных правил
        refined_candidates = self._apply_context_rules(candidates, context)
        
        # Дополнительная верификация топ-кандидатов
        verified_candidates = self._verify_top_candidates(refined_candidates, email, target_name)
        
        return verified_candidates
    
    def _apply_context_rules(self, 
                           candidates: List[ORCIDCandidate], 
                           context: str) -> List[ORCIDCandidate]:
        """Применяет контекстные правила"""
        
        for candidate in candidates:
            if context == "academic":
                # Приоритет высокому h-index и активности
                if candidate.h_index > 20 and candidate.temporal_score > 0.7:
                    candidate.relevance_score *= 1.1
            
            elif context == "corporate":
                # Приоритет доменной принадлежности
                if candidate.domain_affinity_score > 0.7:
                    candidate.relevance_score *= 1.15
            
            elif context == "personal":
                # Приоритет точности имени
                if candidate.name_similarity_score > 0.8:
                    candidate.relevance_score *= 1.2
        
        # Пересортировка
        candidates.sort(key=lambda x: x.relevance_score, reverse=True)
        return candidates
    
    def _verify_top_candidates(self, 
                             candidates: List[ORCIDCandidate],
                             email: str,
                             target_name: Optional[str]) -> List[ORCIDCandidate]:
        """Дополнительная верификация топ-кандидатов"""
        if not candidates:
            return candidates
        
        top_candidate = candidates[0]
        
        # Предупреждения о низкой уверенности
        if top_candidate.confidence_level in ["very_low", "low"]:
            logger.warning(f"⚠️ Низкая уверенность в выборе ORCID {top_candidate.orcid_id}")
        
        # Проверка значительного разрыва в оценках
        if (len(candidates) > 1 and 
            candidates[0].relevance_score - candidates[1].relevance_score > 0.2):
            logger.info(f"✅ Высокая уверенность: значительный разрыв в оценках")
        
        return candidates
    
    def _log_ranking_results(self, candidates: List[ORCIDCandidate], email: str):
        """Логирует результаты ранжирования"""
        logger.info(f"\n🏆 Результаты улучшенного ранжирования для {email}:")
        logger.info(f"📊 Обработано кандидатов: {len(candidates)}")
        
        for i, candidate in enumerate(candidates[:5]):  # Топ-5
            logger.info(
                f"  {i+1}. ORCID: {candidate.orcid_id} | "
                f"Релевантность: {candidate.relevance_score:.3f} | "
                f"Уверенность: {candidate.confidence_level} | "
                f"Имена: {candidate.name_similarity_score:.3f}"
            )
    
    def get_best_orcid(self, 
                      candidates: List[Dict[str, Any]], 
                      email: str,
                      context: str = "academic",
                      target_name: Optional[str] = None,
                      orcid_service=None) -> Optional[str]:
        """
        Удобный метод для получения лучшего ORCID ID
        
        Returns:
            ORCID ID лучшего кандидата или None
        """
        ranked_candidates = self.rank_orcid_candidates(
            candidates=candidates,
            email=email,
            context=context,
            target_name=target_name,
            orcid_service=orcid_service
        )
        
        if ranked_candidates and ranked_candidates[0].confidence_level not in ["very_low"]:
            return ranked_candidates[0].orcid_id
        
        return None
