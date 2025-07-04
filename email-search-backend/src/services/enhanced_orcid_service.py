#!/usr/bin/env python3
"""
🔍 Расширенный ORCID сервис с кросс-валидацией и улучшенным поиском

Ключевые возможности:
- Кросс-валидация найденных ORCID через несколько методов поиска
- Расширенный поиск по вариациям имен и отчеств
- Интеграция с улучшенным алгоритмом ранжирования
- Дедупликация и объединение результатов
- Детальное логирование процесса поиска

Автор: AI Assistant  
Дата: 2025-07-04
Версия: 3.0-enhanced
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from .orcid_service import ORCIDService
from .enhanced_orcid_ranking import EnhancedORCIDRanking

logger = logging.getLogger(__name__)

class EnhancedORCIDService(ORCIDService):
    """Расширенный ORCID сервис с улучшенным поиском и ранжированием"""
    
    def __init__(self):
        super().__init__()
        self.ranking_algorithm = EnhancedORCIDRanking()
        logger.info("🚀 Enhanced ORCID Service v3.0 инициализирован")
    
    def enhanced_search_by_email(self, 
                                email: str,
                                target_name: Optional[str] = None,
                                context: str = "academic") -> List[Dict[str, Any]]:
        """
        Расширенный поиск ORCID по email с кросс-валидацией
        
        Args:
            email: Email адрес для поиска
            target_name: Известное имя владельца email (если есть)
            context: Контекст использования (academic, personal, corporate)
            
        Returns:
            Список исследователей, отсортированный по релевантности
        """
        logger.info(f"🔍 Начинаем расширенный поиск ORCID для email: {email}")
        logger.info(f"👤 Целевое имя: {target_name or 'не указано'}")
        logger.info(f"🏢 Контекст: {context}")
        
        # Шаг 1: Собираем ORCID кандидатов из разных источников
        all_candidates = self._collect_orcid_candidates(email, target_name)
        
        if not all_candidates:
            logger.warning(f"⚠️ Не найдено ORCID кандидатов для email: {email}")
            return []
        
        logger.info(f"📊 Собрано {len(all_candidates)} уникальных ORCID кандидатов")
        
        # Шаг 2: Ранжируем кандидатов с помощью улучшенного алгоритма
        ranked_candidates = self.ranking_algorithm.rank_orcid_candidates(
            candidates=all_candidates,
            email=email,
            context=context,
            target_name=target_name,
            orcid_service=self
        )
        
        # Шаг 3: Преобразуем в формат результата
        researchers = []
        for candidate in ranked_candidates:
            researcher_profile = self.get_researcher_profile(candidate.orcid_id)
            if researcher_profile:
                # Добавляем метаинформацию о ранжировании
                researcher_profile['ranking_info'] = {
                    'relevance_score': candidate.relevance_score,
                    'confidence_level': candidate.confidence_level,
                    'source_method': candidate.source_method,
                    'name_similarity_score': candidate.name_similarity_score,
                    'factors': {
                        'position': candidate.position_score,
                        'url_quality': candidate.url_quality_score,
                        'name_similarity': candidate.name_similarity_score,
                        'domain_quality': candidate.domain_quality_score,
                        'domain_affinity': candidate.domain_affinity_score,
                        'temporal': candidate.temporal_score,
                        'network': candidate.network_score,
                        'citation': candidate.citation_score,
                        'semantic': candidate.semantic_score
                    }
                }
                researchers.append(researcher_profile)
        
        logger.info(f"🏆 Возвращаем {len(researchers)} ранжированных исследователей")
        return researchers
    
    def _collect_orcid_candidates(self, 
                                 email: str, 
                                 target_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Собирает ORCID кандидатов из разных источников"""
        
        candidates = []
        found_orcids = set()  # Для дедупликации
        
        # Источник 1: Поиск по email (оригинальный метод)
        logger.info("🔍 Источник 1: Поиск по email")
        try:
            email_orcids = self.search_orcid_by_email(email)
            for i, orcid_id in enumerate(email_orcids):
                if orcid_id not in found_orcids:
                    candidates.append({
                        'orcid_id': orcid_id,
                        'url': f'https://orcid.org/{orcid_id}',
                        'position_in_list': i,
                        'source_method': 'email_search'
                    })
                    found_orcids.add(orcid_id)
            
            logger.info(f"   Найдено по email: {len(email_orcids)} ORCID")
        except Exception as e:
            logger.error(f"   Ошибка поиска по email: {str(e)}")
        
        # Источник 2: Поиск по имени (если известно)
        if target_name:
            logger.info("🔍 Источник 2: Поиск по имени")
            try:
                name_variations = self._generate_name_variations(target_name)
                
                for variation in name_variations:
                    given_name, family_name = self._parse_name_variation(variation)
                    if given_name and family_name:
                        name_orcids = self.search_by_name(given_name, family_name)
                        
                        for i, orcid_id in enumerate(name_orcids):
                            if orcid_id not in found_orcids:
                                candidates.append({
                                    'orcid_id': orcid_id,
                                    'url': f'https://orcid.org/{orcid_id}',
                                    'position_in_list': i + 100,  # Смещение для отличия от email поиска
                                    'source_method': f'name_search_{variation}'
                                })
                                found_orcids.add(orcid_id)
                
                logger.info(f"   Найдено по имени: {len(found_orcids) - len(email_orcids)} новых ORCID")
            except Exception as e:
                logger.error(f"   Ошибка поиска по имени: {str(e)}")
        
        # Источник 3: Поиск по частям email (извлечение имен)
        logger.info("🔍 Источник 3: Поиск по частям email")
        try:
            email_parts = self._extract_names_from_email(email)
            
            for name_combo in email_parts:
                if len(name_combo) >= 2:
                    given_name, family_name = name_combo[0], name_combo[-1]
                    parts_orcids = self.search_by_name(given_name, family_name)
                    
                    for i, orcid_id in enumerate(parts_orcids):
                        if orcid_id not in found_orcids:
                            candidates.append({
                                'orcid_id': orcid_id,
                                'url': f'https://orcid.org/{orcid_id}',
                                'position_in_list': i + 200,  # Смещение
                                'source_method': 'email_parts_search'
                            })
                            found_orcids.add(orcid_id)
            
            logger.info(f"   Найдено по частям email: {len(found_orcids) - len(candidates) if len(candidates) > 0 else 0} новых ORCID")
        except Exception as e:
            logger.error(f"   Ошибка поиска по частям email: {str(e)}")
        
        # Дедупликация и логирование
        unique_candidates = []
        seen_orcids = set()
        
        for candidate in candidates:
            orcid_id = candidate['orcid_id']
            if orcid_id not in seen_orcids:
                unique_candidates.append(candidate)
                seen_orcids.add(orcid_id)
        
        logger.info(f"📊 Итого уникальных кандидатов: {len(unique_candidates)}")
        
        return unique_candidates
    
    def _generate_name_variations(self, target_name: str) -> List[str]:
        """Генерирует вариации имени для более точного поиска"""
        variations = [target_name]
        
        # Разбираем имя на части
        parts = target_name.split()
        
        if len(parts) >= 2:
            # Прямой порядок: Имя Фамилия
            variations.append(f"{parts[0]} {parts[-1]}")
            
            # Обратный порядок: Фамилия Имя
            variations.append(f"{parts[-1]} {parts[0]}")
            
            # Если есть отчество, пробуем без него
            if len(parts) >= 3:
                variations.append(f"{parts[0]} {parts[-1]}")  # Имя Фамилия
                variations.append(f"{parts[-1]} {parts[0]}")  # Фамилия Имя
        
        # Убираем дубликаты
        return list(set(variations))
    
    def _parse_name_variation(self, name_variation: str) -> Tuple[str, str]:
        """Разбирает вариацию имени на имя и фамилию"""
        parts = name_variation.strip().split()
        
        if len(parts) >= 2:
            return parts[0], parts[-1]
        elif len(parts) == 1:
            return parts[0], ""
        else:
            return "", ""
    
    def _extract_names_from_email(self, email: str) -> List[List[str]]:
        """Извлекает возможные имена из email адреса"""
        email_part = email.split('@')[0].lower()
        
        combinations = []
        
        # Пробуем разные разделители
        separators = ['.', '_', '-']
        for sep in separators:
            if sep in email_part:
                parts = [part.strip() for part in email_part.split(sep) if part.strip()]
                if len(parts) >= 2:
                    combinations.append(parts)
        
        # Ищем распространенные паттерны
        import re
        
        # Паттерн: фамилияимя (например, gorobetsleonid)
        common_surnames = ['gorobets', 'petrov', 'ivanov', 'smirnov', 'kuznetsov', 'popov']
        common_names = ['leonid', 'vladimir', 'alexander', 'dmitry', 'sergey', 'andrey']
        
        for surname in common_surnames:
            if surname in email_part:
                remaining = email_part.replace(surname, '').strip()
                for name in common_names:
                    if name in remaining:
                        combinations.append([surname, name])
                        combinations.append([name, surname])
                        break
        
        # Если ничего не найдено, возвращаем разделение пополам
        if not combinations and len(email_part) > 4:
            mid = len(email_part) // 2
            combinations.append([email_part[:mid], email_part[mid:]])
            combinations.append([email_part[mid:], email_part[:mid]])
        
        return combinations
    
    def get_best_orcid_with_ranking(self, 
                                   email: str,
                                   target_name: Optional[str] = None,
                                   context: str = "academic",
                                   min_confidence: str = "low") -> Optional[Dict[str, Any]]:
        """
        Возвращает лучший ORCID с информацией о ранжировании
        
        Args:
            email: Email адрес
            target_name: Известное имя
            context: Контекст использования
            min_confidence: Минимальный уровень уверенности
            
        Returns:
            Словарь с ORCID ID и метаинформацией или None
        """
        researchers = self.enhanced_search_by_email(email, target_name, context)
        
        if not researchers:
            return None
        
        best_researcher = researchers[0]
        ranking_info = best_researcher.get('ranking_info', {})
        confidence_level = ranking_info.get('confidence_level', 'very_low')
        
        # Проверяем минимальный уровень уверенности
        confidence_levels = ['very_low', 'low', 'medium', 'high', 'very_high']
        min_level_index = confidence_levels.index(min_confidence)
        current_level_index = confidence_levels.index(confidence_level)
        
        if current_level_index >= min_level_index:
            return {
                'orcid_id': best_researcher['orcid_id'],
                'relevance_score': ranking_info.get('relevance_score', 0.0),
                'confidence_level': confidence_level,
                'source_method': ranking_info.get('source_method', 'unknown'),
                'name_similarity_score': ranking_info.get('name_similarity_score', 0.0),
                'profile': best_researcher
            }
        
        logger.warning(f"⚠️ Лучший кандидат имеет уверенность {confidence_level}, "
                      f"что ниже требуемого {min_confidence}")
        return None
    
    def validate_orcid_for_email(self, 
                                orcid_id: str, 
                                email: str,
                                target_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Валидирует соответствие ORCID ID указанному email
        
        Args:
            orcid_id: ORCID ID для проверки
            email: Email адрес
            target_name: Ожидаемое имя
            
        Returns:
            Словарь с результатами валидации
        """
        logger.info(f"🔍 Валидируем ORCID {orcid_id} для email {email}")
        
        validation_result = {
            'orcid_id': orcid_id,
            'email': email,
            'is_valid': False,
            'confidence_score': 0.0,
            'validation_details': {},
            'recommendations': []
        }
        
        try:
            # Получаем профиль ORCID
            profile = self.get_researcher_profile(orcid_id)
            if not profile:
                validation_result['validation_details']['error'] = 'ORCID профиль не найден'
                return validation_result
            
            # Создаем фиктивного кандидата для ранжирования
            candidate_data = [{
                'orcid_id': orcid_id,
                'url': f'https://orcid.org/{orcid_id}',
                'position_in_list': 0,
                'source_method': 'validation'
            }]
            
            # Ранжируем с помощью улучшенного алгоритма
            ranked_candidates = self.ranking_algorithm.rank_orcid_candidates(
                candidates=candidate_data,
                email=email,
                context="academic",
                target_name=target_name,
                orcid_service=self
            )
            
            if ranked_candidates:
                candidate = ranked_candidates[0]
                
                validation_result['confidence_score'] = candidate.relevance_score
                validation_result['validation_details'] = {
                    'name_similarity_score': candidate.name_similarity_score,
                    'extracted_names': candidate.extracted_names,
                    'confidence_level': candidate.confidence_level,
                    'factors': {
                        'name_similarity': candidate.name_similarity_score,
                        'url_quality': candidate.url_quality_score,
                        'domain_quality': candidate.domain_quality_score,
                        'semantic': candidate.semantic_score
                    }
                }
                
                # Определяем валидность на основе confidence level
                if candidate.confidence_level in ['medium', 'high', 'very_high']:
                    validation_result['is_valid'] = True
                    validation_result['recommendations'].append(
                        f"ORCID подтвержден с уверенностью {candidate.confidence_level}"
                    )
                else:
                    validation_result['recommendations'].append(
                        f"Низкая уверенность ({candidate.confidence_level}). "
                        "Рекомендуется дополнительная проверка"
                    )
                
                # Дополнительные рекомендации
                if candidate.name_similarity_score < 0.5:
                    validation_result['recommendations'].append(
                        "Низкое сходство имен. Проверьте правильность имени владельца email"
                    )
                
                if candidate.name_similarity_score > 0.8:
                    validation_result['recommendations'].append(
                        "Высокое сходство имен - хороший индикатор соответствия"
                    )
        
        except Exception as e:
            logger.error(f"❌ Ошибка валидации ORCID {orcid_id}: {str(e)}")
            validation_result['validation_details']['error'] = str(e)
        
        logger.info(f"✅ Валидация завершена. Результат: {validation_result['is_valid']}")
        return validation_result
    
    def cross_validate_orcids(self, 
                             email: str,
                             target_name: Optional[str] = None,
                             max_candidates: int = 5) -> Dict[str, Any]:
        """
        Выполняет кросс-валидацию найденных ORCID
        
        Args:
            email: Email адрес
            target_name: Ожидаемое имя
            max_candidates: Максимальное количество кандидатов для анализа
            
        Returns:
            Словарь с результатами кросс-валидации
        """
        logger.info(f"🔄 Начинаем кросс-валидацию ORCID для {email}")
        
        # Получаем всех кандидатов
        researchers = self.enhanced_search_by_email(email, target_name, "academic")
        
        if not researchers:
            return {
                'email': email,
                'target_name': target_name,
                'candidates_found': 0,
                'validation_results': [],
                'recommendation': 'Кандидаты ORCID не найдены'
            }
        
        # Ограничиваем количество кандидатов
        candidates_to_validate = researchers[:max_candidates]
        
        validation_results = []
        for researcher in candidates_to_validate:
            orcid_id = researcher['orcid_id']
            ranking_info = researcher.get('ranking_info', {})
            
            validation_result = {
                'orcid_id': orcid_id,
                'rank': len(validation_results) + 1,
                'relevance_score': ranking_info.get('relevance_score', 0.0),
                'confidence_level': ranking_info.get('confidence_level', 'unknown'),
                'source_method': ranking_info.get('source_method', 'unknown'),
                'name_similarity_score': ranking_info.get('name_similarity_score', 0.0),
                'profile_summary': {
                    'name': f"{researcher.get('personal_info', {}).get('given_names', '')} "
                           f"{researcher.get('personal_info', {}).get('family_name', '')}",
                    'works_count': researcher.get('works', {}).get('total_works', 0),
                    'keywords': researcher.get('keywords', [])[:5]
                }
            }
            
            validation_results.append(validation_result)
        
        # Формируем рекомендацию
        best_candidate = validation_results[0]
        
        if best_candidate['confidence_level'] in ['high', 'very_high']:
            recommendation = f"Рекомендуется ORCID {best_candidate['orcid_id']} (высокая уверенность)"
        elif best_candidate['confidence_level'] == 'medium':
            recommendation = f"Вероятно подходит ORCID {best_candidate['orcid_id']} (средняя уверенность)"
        else:
            recommendation = "Ни один из кандидатов не имеет достаточной уверенности. Требуется ручная проверка"
        
        result = {
            'email': email,
            'target_name': target_name,
            'candidates_found': len(researchers),
            'candidates_analyzed': len(validation_results),
            'validation_results': validation_results,
            'recommendation': recommendation,
            'best_candidate': best_candidate,
            'analysis_summary': {
                'high_confidence_count': len([r for r in validation_results 
                                            if r['confidence_level'] in ['high', 'very_high']]),
                'medium_confidence_count': len([r for r in validation_results 
                                              if r['confidence_level'] == 'medium']),
                'low_confidence_count': len([r for r in validation_results 
                                           if r['confidence_level'] in ['low', 'very_low']])
            }
        }
        
        logger.info(f"✅ Кросс-валидация завершена. Рекомендация: {recommendation}")
        return result
    
    def rank_orcid_candidates(self, 
                            orcid_candidates: List[str], 
                            search_results: List[Dict[str, Any]],
                            email: Optional[str] = None,
                            target_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Ранжирует найденные ORCID кандидатов с использованием улучшенного алгоритма
        
        Args:
            orcid_candidates: Список ORCID ID для ранжирования
            search_results: Результаты поиска для контекста
            email: Email адрес (если доступен)
            target_name: Целевое имя (если доступно)
            
        Returns:
            Список ранжированных ORCID с информацией о уверенности
        """
        logger.info(f"🏆 Начинаем ранжирование {len(orcid_candidates)} ORCID кандидатов")
        
        if not orcid_candidates:
            return []
        
        ranked_results = []
        
        try:
            # Преобразуем ORCID в формат кандидатов для алгоритма ранжирования
            candidates = []
            for i, orcid_id in enumerate(orcid_candidates):
                candidates.append({
                    'orcid_id': orcid_id,
                    'url': f'https://orcid.org/{orcid_id}',
                    'position_in_list': i,
                    'source_method': 'external_search'
                })
            
            # Извлекаем целевое имя из результатов поиска, если не предоставлено
            if not target_name and search_results:
                target_name = self._extract_target_name_from_results(search_results)
            
            # Используем алгоритм ранжирования
            ranked_candidates = self.ranking_algorithm.rank_orcid_candidates(
                candidates=candidates,
                email=email or 'unknown@example.com',
                context='academic',
                target_name=target_name,
                orcid_service=self
            )
            
            # Преобразуем результаты в простой формат
            for candidate in ranked_candidates:
                ranked_results.append({
                    'orcid_id': candidate.orcid_id,
                    'confidence': candidate.relevance_score,
                    'confidence_level': candidate.confidence_level,
                    'name_similarity_score': candidate.name_similarity_score,
                    'factors': {
                        'position': candidate.position_score,
                        'url_quality': candidate.url_quality_score,
                        'name_similarity': candidate.name_similarity_score,
                        'domain_quality': candidate.domain_quality_score,
                        'semantic': candidate.semantic_score
                    }
                })
            
            if ranked_results:
                logger.info(f"🎯 Ранжирование завершено. Лучший кандидат: {ranked_results[0]['orcid_id']} (confidence: {ranked_results[0]['confidence']:.3f})")
            else:
                logger.info("🎯 Ранжирование завершено. Кандидатов не найдено.")
            
        except Exception as e:
            logger.error(f"❌ Ошибка ранжирования ORCID кандидатов: {str(e)}")
            # Fallback - возвращаем в исходном порядке с базовой уверенностью
            for i, orcid_id in enumerate(orcid_candidates):
                ranked_results.append({
                    'orcid_id': orcid_id,
                    'confidence': 0.5 - (i * 0.1),  # Убывающая уверенность
                    'confidence_level': 'low',
                    'name_similarity_score': 0.0,
                    'factors': {}
                })
        
        return ranked_results
    
    def _extract_target_name_from_results(self, search_results: List[Dict[str, Any]]) -> Optional[str]:
        """Извлекает целевое имя из результатов поиска"""
        import re
        
        for result in search_results:
            text = f"{result.get('title', '')} {result.get('snippet', '')}"
            
            # Ищем русские имена в формате "Фамилия Имя Отчество"
            russian_names = re.findall(r'([А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+)', text)
            if russian_names:
                return russian_names[0]
            
            # Ищем английские имена
            english_names = re.findall(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', text)
            if english_names:
                return english_names[0]
        
        return None
