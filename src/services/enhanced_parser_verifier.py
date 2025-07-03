#!/usr/bin/env python3
"""
Улучшенная система парсинга найденных страниц с Fuzzy Matching и перекрестной верификацией
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import defaultdict, Counter
from difflib import SequenceMatcher
from dataclasses import dataclass, field
import numpy as np
from datetime import datetime
from enum import Enum

# Для Fuzzy Matching
try:
    from fuzzywuzzy import fuzz, process
    FUZZYWUZZY_AVAILABLE = True
except ImportError:
    FUZZYWUZZY_AVAILABLE = False
    logging.warning("fuzzywuzzy не установлен. Используется встроенный алгоритм similarity.")

logger = logging.getLogger(__name__)

class SourceAuthority(Enum):
    """Уровень авторитетности источника"""
    HIGH = "high"  # Официальные сайты, научные публикации
    MEDIUM = "medium"  # Профессиональные профили, корпоративные сайты
    LOW = "low"  # Социальные сети, блоги
    UNKNOWN = "unknown"  # Неопределенный источник

class ConflictType(Enum):
    """Типы конфликтов в данных"""
    SOURCE_CONFLICT = "source_conflict"  # Конфликт между источниками
    DATA_CONFLICT = "data_conflict"  # Конфликт в самих данных
    TEMPORAL_CONFLICT = "temporal_conflict"  # Конфликт по времени
    CONTEXT_CONFLICT = "context_conflict"  # Конфликт контекста

@dataclass
class ConfidenceComponents:
    """Компоненты уверенности для детального анализа"""
    source_confidence: float = 0.0  # Уверенность в источнике
    context_confidence: float = 0.0  # Уверенность в контексте
    validation_confidence: float = 0.0  # Уверенность в валидации
    consistency_confidence: float = 0.0  # Уверенность в консистентности
    
    @property
    def overall_confidence(self) -> float:
        """Вычисляет общую уверенность как взвешенную сумму компонентов"""
        weights = {
            'source': 0.3,
            'context': 0.25,
            'validation': 0.25,
            'consistency': 0.2
        }
        return (
            self.source_confidence * weights['source'] +
            self.context_confidence * weights['context'] +
            self.validation_confidence * weights['validation'] +
            self.consistency_confidence * weights['consistency']
        )

@dataclass
class SourceMetadata:
    """Расширенные метаданные источника"""
    authority: SourceAuthority = SourceAuthority.UNKNOWN
    certainty: float = 0.0  # Уверенность в надежности источника (0-1)
    domain_reputation: float = 0.0  # Репутация домена (0-1)
    last_updated: Optional[datetime] = None  # Последнее обновление источника
    page_rank: float = 0.0  # PageRank или аналогичная метрика

@dataclass
class DataPoint:
    """Точка данных с метрикой достоверности"""
    value: str
    confidence_components: ConfidenceComponents
    source: str
    source_type: str  # 'title', 'meta', 'content', 'json_ld', etc.
    source_metadata: SourceMetadata = field(default_factory=SourceMetadata)
    context: str = ""
    url: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 1
    
    @property
    def confidence(self) -> float:
        """Обратная совместимость - возвращает общую уверенность"""
        return self.confidence_components.overall_confidence

@dataclass
class ConflictDetail:
    """Детали конфликта в данных"""
    conflict_type: ConflictType
    conflicting_value: str
    source: str
    description: str
    severity: float  # 0-1, где 1 - критический конфликт

@dataclass
class VerificationResult:
    """Результат верификации данных"""
    verified_value: str
    confidence_components: ConfidenceComponents
    supporting_sources: List[str]
    conflicting_data: List[ConflictDetail] = field(default_factory=list)
    verification_method: str = ""
    context_explanation: str = ""  # Объяснение контекста верификации
    suggestions: List[str] = field(default_factory=list)  # Предложения по улучшению
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def confidence_score(self) -> float:
        """Обратная совместимость - возвращает общую уверенность"""
        if isinstance(self.confidence_components, ConfidenceComponents):
            return self.confidence_components.overall_confidence
        else:
            # Если confidence_components это число (старый формат)
            return float(self.confidence_components) if self.confidence_components else 0.0
    
    @property
    def has_critical_conflicts(self) -> bool:
        """Проверяет наличие критических конфликтов"""
        return any(conflict.severity > 0.7 for conflict in self.conflicting_data)
    
    def get_conflicts_by_type(self, conflict_type: ConflictType) -> List[ConflictDetail]:
        """Возвращает конфликты определенного типа"""
        return [c for c in self.conflicting_data if c.conflict_type == conflict_type]

class EnhancedParserVerifier:
    """Улучшенная система парсинга с верификацией данных"""
    
    def __init__(self):
        self.fuzzy_threshold = 85  # Порог для fuzzy matching
        self.min_confidence = 0.3  # Минимальная уверенность для принятия данных
        self.verification_rules = self._init_verification_rules()
        
    def _init_verification_rules(self) -> Dict[str, Dict]:
        """Инициализация правил верификации для разных типов данных"""
        return {
            'names': {
                'min_sources': 2,  # Минимум источников для верификации
                'fuzzy_threshold': 90,
                'weight_by_source': {
                    'title': 1.0,
                    'meta': 0.9,
                    'h1': 0.8,
                    'json_ld': 0.9,
                    'content': 0.5
                }
            },
            'emails': {
                'min_sources': 1,
                'fuzzy_threshold': 95,  # Высокий порог для email
                'weight_by_source': {
                    'meta': 1.0,
                    'content': 0.8,
                    'json_ld': 0.9
                }
            },
            'organizations': {
                'min_sources': 2,
                'fuzzy_threshold': 85,
                'weight_by_source': {
                    'title': 0.9,
                    'meta': 1.0,
                    'h1': 0.8,
                    'json_ld': 0.9,
                    'content': 0.6
                }
            },
            'positions': {
                'min_sources': 1,
                'fuzzy_threshold': 80,
                'weight_by_source': {
                    'title': 0.8,
                    'meta': 0.9,
                    'content': 0.7,
                    'json_ld': 0.9
                }
            }
        }

    def enhanced_parse_and_verify(self, 
                                 parsed_results: List[Dict[str, Any]], 
                                 target_email: str) -> Dict[str, Any]:
        """
        Основной метод для улучшенного парсинга и верификации
        
        Args:
            parsed_results: Результаты парсинга от WebpageAnalyzer
            target_email: Целевой email для анализа
            
        Returns:
            Верифицированные и обогащенные данные
        """
        logger.info(f"Запуск enhanced парсинга для {len(parsed_results)} источников")
        
        # Извлекаем и группируем данные по типам
        grouped_data = self._extract_and_group_data(parsed_results, target_email)
        
        # Верифицируем каждый тип данных
        verified_results = {}
        for data_type, data_points in grouped_data.items():
            logger.info(f"Верификация {data_type}: {len(data_points)} точек данных")
            verified_results[data_type] = self._verify_data_type(data_type, data_points)
        
        # Перекрестная верификация между типами данных
        cross_verified = self._cross_verify_data(verified_results, target_email)
        
        # Построение итогового профиля с метриками качества
        final_profile = self._build_final_profile(cross_verified, target_email)
        
        return final_profile

    def _extract_and_group_data(self, 
                               parsed_results: List[Dict[str, Any]], 
                               target_email: str) -> Dict[str, List[DataPoint]]:
        """Извлекает и группирует данные по типам с метаданными источников"""
        grouped_data = defaultdict(list)
        
        for result in parsed_results:
            if not result:
                continue
                
            url = result.get('metadata', {}).get('url', 'unknown')
            
            # Извлекаем имена
            names = result.get('names', [])
            for name in names:
                if self._is_valid_name(name):
                    confidence = self._calculate_name_confidence(name, result, target_email)
                    source_type = self._determine_source_type(name, result)
                    
                    grouped_data['names'].append(DataPoint(
                        value=self._normalize_name(name),
                        confidence_components=ConfidenceComponents(
                            source_confidence=confidence,
                            context_confidence=0.5,
                            validation_confidence=0.5,
                            consistency_confidence=0.5
                        ),
                        source=url,
                        source_type=source_type,
                        context=self._extract_context(name, result),
                        url=url
                    ))
            
            # Извлекаем email адреса
            emails = result.get('contact_info', {}).get('emails', [])
            for email in emails:
                if self._is_valid_email(email):
                    confidence = self._calculate_email_confidence(email, target_email)
                    source_type = self._determine_email_source_type(email, result)
                    
                    grouped_data['emails'].append(DataPoint(
                        value=email.lower().strip(),
                        confidence_components=ConfidenceComponents(
                            source_confidence=confidence,
                            context_confidence=0.5,
                            validation_confidence=0.9,
                            consistency_confidence=0.7
                        ),
                        source=url,
                        source_type=source_type,
                        url=url
                    ))
            
            # Извлекаем организации
            organizations = result.get('organizations', [])
            for org in organizations:
                if self._is_valid_organization(org):
                    confidence = self._calculate_org_confidence(org, result)
                    source_type = self._determine_source_type(org, result)
                    
                    grouped_data['organizations'].append(DataPoint(
                        value=self._normalize_organization(org),
                        confidence_components=ConfidenceComponents(
                            source_confidence=confidence,
                            context_confidence=0.5,
                            validation_confidence=0.5,
                            consistency_confidence=0.5
                        ),
                        source=url,
                        source_type=source_type,
                        context=self._extract_context(org, result),
                        url=url
                    ))
            
            # Извлекаем должности
            positions = result.get('positions', [])
            for position in positions:
                if self._is_valid_position(position):
                    confidence = self._calculate_position_confidence(position, result)
                    source_type = self._determine_source_type(position, result)
                    
                    grouped_data['positions'].append(DataPoint(
                        value=self._normalize_position(position),
                        confidence_components=ConfidenceComponents(
                            source_confidence=confidence,
                            context_confidence=0.5,
                            validation_confidence=0.5,
                            consistency_confidence=0.5
                        ),
                        source=url,
                        source_type=source_type,
                        context=self._extract_context(position, result),
                        url=url
                    ))
        
        return dict(grouped_data)

    def _verify_data_type(self, data_type: str, data_points: List[DataPoint]) -> VerificationResult:
        """Верифицирует данные определенного типа с использованием fuzzy matching"""
        if not data_points:
            return VerificationResult("", 0.0, [], [], "no_data")
        
        rules = self.verification_rules.get(data_type, {})
        
        # Группируем похожие значения с помощью fuzzy matching
        clustered_data = self._cluster_similar_values(data_points, rules.get('fuzzy_threshold', 85))
        
        # Находим наиболее достоверный кластер
        best_cluster = self._select_best_cluster(clustered_data, rules)
        
        if not best_cluster:
            return VerificationResult("", 0.0, [], [], "no_reliable_data")
        
        # Вычисляем итоговую уверенность
        final_confidence = self._calculate_cluster_confidence(best_cluster, rules)
        
        # Находим консенсусное значение в кластере
        consensus_value = self._find_consensus_value(best_cluster)
        
        # Собираем поддерживающие источники
        supporting_sources = [dp.source for dp in best_cluster]
        
        # Находим конфликтующие данные
        conflicting_data = self._find_conflicting_data(best_cluster, clustered_data)
        
        return VerificationResult(
            verified_value=consensus_value,
            confidence_components=ConfidenceComponents(
                source_confidence=final_confidence,
                context_confidence=final_confidence * 0.8,
                validation_confidence=final_confidence * 0.9,
                consistency_confidence=final_confidence * 0.7
            ),
            supporting_sources=list(set(supporting_sources)),
            conflicting_data=conflicting_data,
            verification_method="fuzzy_clustering"
        )

    def _cluster_similar_values(self, data_points: List[DataPoint], threshold: float) -> List[List[DataPoint]]:
        """Кластеризует похожие значения с помощью fuzzy matching"""
        if not data_points:
            return []
        
        clusters = []
        used_indices = set()
        
        for i, dp in enumerate(data_points):
            if i in used_indices:
                continue
            
            # Создаем новый кластер с текущей точкой
            cluster = [dp]
            used_indices.add(i)
            
            # Ищем похожие значения
            for j, other_dp in enumerate(data_points):
                if j in used_indices:
                    continue
                
                similarity = self._calculate_similarity(dp.value, other_dp.value)
                if similarity >= threshold:
                    cluster.append(other_dp)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        # Сортируем кластеры по размеру и средней уверенности
        clusters.sort(key=lambda c: (len(c), np.mean([dp.confidence for dp in c])), reverse=True)
        
        return clusters

    def _calculate_similarity(self, value1: str, value2: str) -> float:
        """Вычисляет сходство между двумя строками"""
        if FUZZYWUZZY_AVAILABLE:
            return fuzz.ratio(value1, value2)
        else:
            # Встроенный алгоритм как fallback
            return SequenceMatcher(None, value1, value2).ratio() * 100

    def _select_best_cluster(self, clusters: List[List[DataPoint]], rules: Dict) -> Optional[List[DataPoint]]:
        """Выбирает лучший кластер на основе правил верификации"""
        min_sources = rules.get('min_sources', 1)
        weight_by_source = rules.get('weight_by_source', {})
        
        for cluster in clusters:
            # Проверяем минимальное количество источников
            unique_sources = len(set(dp.source for dp in cluster))
            if unique_sources < min_sources:
                continue
            
            # Вычисляем взвешенную уверенность
            weighted_confidence = 0
            total_weight = 0
            
            for dp in cluster:
                weight = weight_by_source.get(dp.source_type, 0.5)
                weighted_confidence += dp.confidence * weight
                total_weight += weight
            
            if total_weight > 0:
                avg_confidence = weighted_confidence / total_weight
                if avg_confidence >= self.min_confidence:
                    return cluster
        
        return None

    def _calculate_cluster_confidence(self, cluster: List[DataPoint], rules: Dict) -> float:
        """Вычисляет итоговую уверенность для кластера"""
        if not cluster:
            return 0.0
        
        weight_by_source = rules.get('weight_by_source', {})
        
        # Базовая уверенность от точек данных
        weighted_confidence = 0
        total_weight = 0
        
        for dp in cluster:
            weight = weight_by_source.get(dp.source_type, 0.5)
            weighted_confidence += dp.confidence * weight
            total_weight += weight
        
        base_confidence = weighted_confidence / total_weight if total_weight > 0 else 0
        
        # Бонус за множественные источники
        unique_sources = len(set(dp.source for dp in cluster))
        source_bonus = min(0.2, unique_sources * 0.05)
        
        # Бонус за качественные источники
        quality_bonus = 0
        for dp in cluster:
            if dp.source_type in ['meta', 'json_ld', 'title']:
                quality_bonus += 0.02
        quality_bonus = min(0.1, quality_bonus)
        
        final_confidence = min(1.0, base_confidence + source_bonus + quality_bonus)
        
        return final_confidence

    def _find_consensus_value(self, cluster: List[DataPoint]) -> str:
        """Находит консенсусное значение в кластере"""
        if not cluster:
            return ""
        
        # Подсчитываем частоту каждого значения
        value_counts = Counter(dp.value for dp in cluster)
        
        # Если есть явный лидер, возвращаем его
        most_common = value_counts.most_common(1)[0]
        if most_common[1] > 1:
            return most_common[0]
        
        # Иначе выбираем значение с наибольшей уверенностью
        best_dp = max(cluster, key=lambda dp: dp.confidence)
        return best_dp.value

    def _cross_verify_data(self, verified_results: Dict[str, VerificationResult], target_email: str) -> Dict[str, Any]:
        """Перекрестная верификация между разными типами данных"""
        cross_verified = {}
        
        # Проверяем соответствие имени и email
        name_result = verified_results.get('names')
        email_result = verified_results.get('emails')
        
        if name_result and email_result:
            name_email_consistency = self._check_name_email_consistency(
                name_result.verified_value, 
                email_result.verified_value, 
                target_email
            )
            cross_verified['name_email_consistency'] = name_email_consistency
            
            # Корректируем уверенность на основе консистентности
            if name_email_consistency['is_consistent']:
                if name_result.confidence_score > 0:
                    name_result.confidence_score = min(1.0, name_result.confidence_score * 1.2)
                if email_result.confidence_score > 0:
                    email_result.confidence_score = min(1.0, email_result.confidence_score * 1.1)
        
        # Проверяем соответствие организации и должности
        org_result = verified_results.get('organizations')
        pos_result = verified_results.get('positions')
        
        if org_result and pos_result:
            org_position_consistency = self._check_org_position_consistency(
                org_result.verified_value,
                pos_result.verified_value
            )
            cross_verified['org_position_consistency'] = org_position_consistency
        
        # Добавляем верифицированные результаты
        for data_type, result in verified_results.items():
            cross_verified[data_type] = {
                'value': result.verified_value,
                'confidence': result.confidence_score,
                'sources': result.supporting_sources,
                'conflicts': result.conflicting_data,
                'method': result.verification_method
            }
        
        return cross_verified

    def _check_name_email_consistency(self, name: str, email: str, target_email: str) -> Dict[str, Any]:
        """Проверяет консистентность имени и email адреса"""
        if not name or not email:
            return {'is_consistent': False, 'reason': 'missing_data'}
        
        # Используем целевой email для анализа
        check_email = target_email if target_email else email
        
        # Извлекаем части имени
        name_parts = re.findall(r'[А-Яа-яA-Za-z]+', name.lower())
        if len(name_parts) < 2:
            return {'is_consistent': False, 'reason': 'insufficient_name_parts'}
        
        # Извлекаем локальную часть email
        email_local = check_email.split('@')[0].lower()
        
        # Проверяем различные паттерны соответствия
        patterns = [
            # Имя.Фамилия
            f"{name_parts[0]}.{name_parts[-1]}",
            f"{name_parts[-1]}.{name_parts[0]}",
            # ИмяФамилия
            f"{name_parts[0]}{name_parts[-1]}",
            f"{name_parts[-1]}{name_parts[0]}",
            # Инициалы + фамилия
            f"{name_parts[0][0]}{name_parts[-1]}",
            f"{name_parts[-1]}{name_parts[0][0]}",
            # Фамилия + инициалы
            f"{name_parts[-1]}{name_parts[0][0]}{name_parts[1][0] if len(name_parts) > 2 else ''}",
        ]
        
        # Проверяем соответствие
        for pattern in patterns:
            similarity = self._calculate_similarity(pattern, email_local)
            if similarity > 70:  # Порог для соответствия
                return {
                    'is_consistent': True, 
                    'pattern': pattern,
                    'similarity': similarity,
                    'method': 'pattern_matching'
                }
        
        # Проверяем fuzzy matching
        if FUZZYWUZZY_AVAILABLE:
            best_match = process.extractOne(email_local, patterns)
            if best_match and best_match[1] > 60:
                return {
                    'is_consistent': True,
                    'pattern': best_match[0],
                    'similarity': best_match[1],
                    'method': 'fuzzy_matching'
                }
        
        return {'is_consistent': False, 'reason': 'no_pattern_match'}

    def _check_org_position_consistency(self, organization: str, position: str) -> Dict[str, Any]:
        """Проверяет консистентность организации и должности"""
        if not organization or not position:
            return {'is_consistent': False, 'reason': 'missing_data'}
        
        org_lower = organization.lower()
        pos_lower = position.lower()
        
        # Определяем тип организации
        org_type = 'unknown'
        if any(word in org_lower for word in ['университет', 'university', 'институт', 'institute']):
            org_type = 'academic'
        elif any(word in org_lower for word in ['больница', 'hospital', 'клиника', 'clinic']):
            org_type = 'medical'
        elif any(word in org_lower for word in ['компания', 'company', 'корпорация', 'corporation']):
            org_type = 'corporate'
        
        # Проверяем соответствие должности типу организации
        consistency_rules = {
            'academic': ['профессор', 'professor', 'доцент', 'associate', 'lecturer', 'researcher'],
            'medical': ['врач', 'doctor', 'медсестра', 'nurse', 'хирург', 'surgeon'],
            'corporate': ['менеджер', 'manager', 'директор', 'director', 'specialist']
        }
        
        if org_type in consistency_rules:
            relevant_positions = consistency_rules[org_type]
            if any(pos_word in pos_lower for pos_word in relevant_positions):
                return {
                    'is_consistent': True,
                    'org_type': org_type,
                    'reason': 'position_matches_org_type'
                }
        
        return {'is_consistent': False, 'reason': 'position_org_mismatch'}

    def _build_final_profile(self, cross_verified: Dict[str, Any], target_email: str) -> Dict[str, Any]:
        """Строит итоговый профиль с метриками качества"""
        profile = {
            'target_email': target_email,
            'verification_timestamp': datetime.now().isoformat(),
            'data_quality_metrics': {},
            'verified_data': {},
            'consistency_checks': {},
            'recommendations': []
        }
        
        # Добавляем верифицированные данные
        for data_type in ['names', 'emails', 'organizations', 'positions']:
            if data_type in cross_verified:
                data = cross_verified[data_type]
                profile['verified_data'][data_type] = {
                    'value': data['value'],
                    'confidence': data['confidence'],
                    'source_count': len(data['sources']),
                    'has_conflicts': len(data['conflicts']) > 0
                }
        
        # Добавляем проверки консистентности
        if 'name_email_consistency' in cross_verified:
            profile['consistency_checks']['name_email'] = cross_verified['name_email_consistency']
        
        if 'org_position_consistency' in cross_verified:
            profile['consistency_checks']['org_position'] = cross_verified['org_position_consistency']
        
        # Вычисляем общие метрики качества
        profile['data_quality_metrics'] = self._calculate_quality_metrics(cross_verified)
        
        # Генерируем рекомендации
        profile['recommendations'] = self._generate_recommendations(cross_verified)
        
        return profile

    def _calculate_quality_metrics(self, cross_verified: Dict[str, Any]) -> Dict[str, float]:
        """Вычисляет метрики качества данных"""
        metrics = {}
        
        # Средняя уверенность по всем типам данных
        confidences = []
        for data_type in ['names', 'emails', 'organizations', 'positions']:
            if data_type in cross_verified and cross_verified[data_type]['confidence'] > 0:
                confidences.append(cross_verified[data_type]['confidence'])
        
        metrics['average_confidence'] = np.mean(confidences) if confidences else 0.0
        
        # Покрытие данных (сколько типов данных мы смогли верифицировать)
        total_types = 4
        verified_types = len([dt for dt in ['names', 'emails', 'organizations', 'positions'] 
                             if dt in cross_verified and cross_verified[dt]['confidence'] > 0.3])
        metrics['data_coverage'] = verified_types / total_types
        
        # Консистентность данных
        consistency_score = 0
        consistency_count = 0
        
        if 'name_email_consistency' in cross_verified:
            consistency_score += 1 if cross_verified['name_email_consistency']['is_consistent'] else 0
            consistency_count += 1
        
        if 'org_position_consistency' in cross_verified:
            consistency_score += 1 if cross_verified['org_position_consistency']['is_consistent'] else 0
            consistency_count += 1
        
        metrics['consistency_score'] = consistency_score / consistency_count if consistency_count > 0 else 0.0
        
        # Общий score качества
        metrics['overall_quality'] = (
            metrics['average_confidence'] * 0.4 +
            metrics['data_coverage'] * 0.3 +
            metrics['consistency_score'] * 0.3
        )
        
        return metrics

    def _generate_recommendations(self, cross_verified: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации по улучшению качества данных"""
        recommendations = []
        
        # Анализируем каждый тип данных
        for data_type in ['names', 'emails', 'organizations', 'positions']:
            if data_type not in cross_verified:
                recommendations.append(f"Не найдены данные типа '{data_type}' - требуется дополнительный поиск")
            elif cross_verified[data_type]['confidence'] < 0.5:
                recommendations.append(f"Низкая уверенность для '{data_type}' ({cross_verified[data_type]['confidence']:.2f}) - требуется дополнительная верификация")
            elif len(cross_verified[data_type]['conflicts']) > 0:
                recommendations.append(f"Обнаружены конфликтующие данные для '{data_type}' - требуется ручная проверка")
        
        # Проверяем консистентность
        if 'name_email_consistency' in cross_verified:
            if not cross_verified['name_email_consistency']['is_consistent']:
                recommendations.append("Имя и email не соответствуют друг другу - возможна ошибка идентификации")
        
        if 'org_position_consistency' in cross_verified:
            if not cross_verified['org_position_consistency']['is_consistent']:
                recommendations.append("Организация и должность могут не соответствовать друг другу")
        
        return recommendations

    # Вспомогательные методы для валидации и нормализации данных
    
    def _is_valid_name(self, name: str) -> bool:
        """Проверяет валидность имени"""
        if not name or len(name) < 3 or len(name) > 100:
            return False
        
        # Проверяем, что содержит буквы
        if not re.search(r'[A-Za-zА-Яа-я]', name):
            return False
        
        # Исключаем очевидно невалидные паттерны
        invalid_patterns = [
            r'^\d+',  # Начинается с цифр
            r'[<>{}\\[\\]()"\']',  # Содержит специальные символы
            r'(abstract|keywords|copyright|download|pdf)',  # Служебные слова
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, name, re.I):
                return False
        
        return True

    def _is_valid_email(self, email: str) -> bool:
        """Проверяет валидность email"""
        if not email:
            return False
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))

    def _is_valid_organization(self, org: str) -> bool:
        """Проверяет валидность названия организации"""
        if not org or len(org) < 5 or len(org) > 200:
            return False
        
        # Должна содержать буквы
        if not re.search(r'[A-Za-zА-Яа-я]', org):
            return False
        
        return True

    def _is_valid_position(self, position: str) -> bool:
        """Проверяет валидность должности"""
        if not position or len(position) < 3 or len(position) > 100:
            return False
        
        # Должна содержать буквы
        if not re.search(r'[A-Za-zА-Яа-я]', position):
            return False
        
        return True

    def _normalize_name(self, name: str) -> str:
        """Нормализует имя"""
        # Удаляем лишние пробелы
        normalized = re.sub(r'\s+', ' ', name.strip())
        
        # Приводим к правильному регистру
        words = normalized.split()
        normalized_words = []
        
        for word in words:
            if re.match(r'^[А-Яа-я]+$', word):
                # Русские слова
                normalized_words.append(word.capitalize())
            elif re.match(r'^[A-Za-z]+$', word):
                # Английские слова
                normalized_words.append(word.capitalize())
            else:
                normalized_words.append(word)
        
        return ' '.join(normalized_words)

    def _normalize_organization(self, org: str) -> str:
        """Нормализует название организации"""
        # Удаляем лишние пробелы и приводим к правильному регистру
        normalized = re.sub(r'\s+', ' ', org.strip())
        
        # Сокращения, которые должны быть заглавными
        abbreviations = ['МГУ', 'СПбГУ', 'РАН', 'РАМН', 'ФГБУ', 'ГУ', 'НИИ', 'НИИР']
        
        for abbr in abbreviations:
            normalized = re.sub(f'\\b{abbr.lower()}\\b', abbr, normalized, flags=re.I)
        
        return normalized

    def _normalize_position(self, position: str) -> str:
        """Нормализует должность"""
        normalized = re.sub(r'\s+', ' ', position.strip())
        
        # Стандартизируем общие должности
        position_mapping = {
            'prof': 'профессор',
            'prof.': 'профессор',
            'professor': 'профессор',
            'assoc prof': 'доцент',
            'associate professor': 'доцент',
            'dr': 'доктор',
            'doctor': 'доктор'
        }
        
        normalized_lower = normalized.lower()
        for abbr, full in position_mapping.items():
            if abbr in normalized_lower:
                normalized = normalized.replace(abbr, full)
        
        return normalized

    def _calculate_name_confidence(self, name: str, result: Dict, target_email: str) -> float:
        """Вычисляет уверенность для имени с интеллектуальной фильтрацией шума"""
        if not name or len(name.strip()) < 3:
            return 0.0
        
        name_clean = name.strip()
        name_lower = name_clean.lower()
        
        # КРИТИЧНАЯ ФИЛЬТРАЦИЯ: Исключаем названия журналов и организаций
        noise_indicators = [
            'вестник', 'журнал', 'бюллетень', 'bulletin', 'journal', 'review',
            'proceedings', 'publication', 'издание', 'научный', 'scientific', 'medical',
            'issn', 'volume', 'issue', 'article', 'study', 'analysis',
            'university press', 'editorial', 'editor', 'редакция',
            'центрального черноземья', 'central black earth', 'kazan medical',
            'oral biol craniofacial', 'sci med sport', 'family med prim',
            'exp ther med', 'complement ther med', 'acta medica eurasica',
            'russian federation', 'российская федерация', 'beijing da xue',
            'state medical university', 'clinical dental clinic',
            'thermo fisher scientific', 'original study', 'research involving',
            'показатели покой покой', 'level professional football'
        ]
        
        # Если содержит шумовые индикаторы - очень низкая уверенность
        if any(indicator in name_lower for indicator in noise_indicators):
            return 0.01  # Практически исключаем
        
        # Дополнительная проверка на технические термины
        if re.search(r'\b(issn|doi|volume|vol\.|no\.|pp\.|page|стр\.)\b', name_lower):
            return 0.02
        
        # Проверяем, является ли это настоящим человеческим именем
        confidence = 0.0
        
        # Русские имена - высший приоритет
        if re.search(r'[А-Яа-я]', name_clean):
            # Полное русское ФИО (Фамилия Имя Отчество)
            if re.match(r'^[А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+$', name_clean):
                confidence = 0.9
            # Сокращенное русское ФИО (Фамилия И.О.)
            elif re.match(r'^[А-Я][а-я]+\s+[А-Я]\.[А-Я]\.$', name_clean):
                confidence = 0.85
            # И.О. Фамилия
            elif re.match(r'^[А-Я]\.[А-Я]\.\s+[А-Я][а-я]+$', name_clean):
                confidence = 0.85
            # Русское имя и фамилия
            elif re.match(r'^[А-Я][а-я]+\s+[А-Я][а-я]+$', name_clean):
                confidence = 0.8
            else:
                confidence = 0.3  # Другие русские варианты
        
        # Английские имена
        elif re.search(r'[A-Za-z]', name_clean):
            # Полное английское имя (First Middle Last)
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+$', name_clean):
                confidence = 0.75
            # Английское имя и фамилия
            elif re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', name_clean):
                confidence = 0.7
            # Фамилия, И.О. (Last, F.M.)
            elif re.match(r'^[A-Z][a-z]+,\s*[A-Z]\.[A-Z]\.$', name_clean):
                confidence = 0.7
            # И.О. Фамилия (F.M. Last)
            elif re.match(r'^[A-Z]\.[A-Z]\.\s+[A-Z][a-z]+$', name_clean):
                confidence = 0.7
            else:
                confidence = 0.25  # Другие английские варианты
        else:
            return 0.05  # Не содержит букв - очень низкая уверенность
        
        # Дополнительные бонусы и штрафы
        
        # Бонус за соответствие с email (только для высококачественных имен)
        if confidence > 0.5 and target_email:
            email_local = target_email.split('@')[0].lower()
            name_parts = re.findall(r'[А-Яа-яA-Za-z]+', name_lower)
            
            if len(name_parts) >= 2:
                # Проверяем прямое совпадение частей имени с email
                for part in name_parts[:2]:
                    if len(part) > 2 and part in email_local:
                        confidence += 0.15
                        break
                
                # Проверяем транслитерацию для русских имен
                if re.search(r'[А-Яа-я]', name_clean):
                    transliteration_bonus = self._check_name_email_transliteration(name_parts, email_local)
                    confidence += transliteration_bonus
        
        # Штраф за слишком длинные "имена" (вероятно, не имена)
        if len(name_clean) > 50:
            confidence *= 0.6
        
        # Штраф за односложные "имена"
        if len(name_clean.split()) < 2:
            confidence *= 0.4
        
        # Штраф за содержание цифр
        if re.search(r'\d', name_clean):
            confidence *= 0.3
        
        # Штраф за содержание специальных символов
        if re.search(r'[<>{}\[\]()"\']', name_clean):
            confidence *= 0.2
        
        return min(1.0, max(0.0, confidence))

    def _calculate_email_confidence(self, email: str, target_email: str) -> float:
        """Вычисляет уверенность для email"""
        if email.lower() == target_email.lower():
            return 1.0
        
        # Базовая уверенность для других email
        return 0.6

    def _calculate_org_confidence(self, org: str, result: Dict) -> float:
        """Вычисляет уверенность для организации"""
        confidence = 0.5
        
        # Бонус за ключевые слова
        academic_keywords = ['университет', 'university', 'институт', 'institute', 'академия', 'academy']
        if any(keyword in org.lower() for keyword in academic_keywords):
            confidence += 0.2
        
        # Бонус за длину (более длинные названия обычно более специфичны)
        if len(org) > 20:
            confidence += 0.1
        
        return min(1.0, confidence)

    def _calculate_position_confidence(self, position: str, result: Dict) -> float:
        """Вычисляет уверенность для должности"""
        confidence = 0.5
        
        # Бонус за академические должности
        academic_positions = ['профессор', 'professor', 'доцент', 'доктор', 'doctor', 'кандидат']
        if any(pos in position.lower() for pos in academic_positions):
            confidence += 0.2
        
        return min(1.0, confidence)

    def _determine_source_type(self, value: str, result: Dict) -> str:
        """Определяет тип источника для значения"""
        # Упрощенная логика - в реальности нужно отслеживать откуда пришло значение
        metadata = result.get('metadata', {})
        
        if 'title' in str(result).lower():
            return 'title'
        elif 'meta' in str(result).lower():
            return 'meta'
        else:
            return 'content'

    def _determine_email_source_type(self, email: str, result: Dict) -> str:
        """Определяет тип источника для email"""
        return 'content'  # Упрощенно

    def _extract_context(self, value: str, result: Dict) -> str:
        """Извлекает контекст для значения"""
        # Упрощенная реализация
        return ""

    def _find_conflicting_data(self, best_cluster: List[DataPoint], all_clusters: List[List[DataPoint]]) -> List[Dict[str, Any]]:
        """Находит конфликтующие данные"""
        conflicts = []
        
        for cluster in all_clusters:
            if cluster == best_cluster:
                continue
            
            # Если кластер содержит значительно отличающиеся данные
            if cluster and len(cluster) > 1:
                cluster_value = self._find_consensus_value(cluster)
                conflicts.append({
                    'alternative_value': cluster_value,
                    'support_count': len(cluster),
                    'sources': [dp.source for dp in cluster]
                })
        
        return conflicts
    
    def _check_name_email_transliteration(self, name_parts: List[str], email_local: str) -> float:
        """Проверяет соответствие между русским именем и его транслитерацией в email"""
        if not name_parts or not email_local:
            return 0.0
        
        transliteration_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
            'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
            'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ы': 'y', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        
        alt_transliteration = {
            'ж': 'j', 'х': 'h', 'ц': 'c', 'ч': 'c', 'ш': 's', 'щ': 's', 'ю': 'u', 'я': 'a'
        }
        
        total_bonus = 0.0
        matches_found = 0
        
        for part in name_parts[:2]:  
            if len(part) < 2:
                continue
                
            transliterated = ''.join(transliteration_map.get(char.lower(), char) for char in part)
            
            alt_transliterated = part.lower()
            for ru_char, alt_char in alt_transliteration.items():
                alt_transliterated = alt_transliterated.replace(ru_char, alt_char)
            alt_transliterated = ''.join(transliteration_map.get(char, char) for char in alt_transliterated)
            
            variants = [transliterated, alt_transliterated]
            
            vowels = 'aeiou'
            for variant in variants[:]:
                no_vowels = ''.join(char for char in variant if char not in vowels)
                if len(no_vowels) >= 2:
                    variants.append(no_vowels)
            
            for variant in variants:
                if len(variant) >= 3:
                    if variant in email_local:
                        total_bonus += 0.15
                        matches_found += 1
                        break
                    elif FUZZYWUZZY_AVAILABLE and fuzz.partial_ratio(variant, email_local) > 85:
                        total_bonus += 0.1
                        matches_found += 1
                        break
                    elif variant[:3] in email_local or variant[-3:] in email_local:
                        total_bonus += 0.05
                        matches_found += 1
                        break
        
        if matches_found >= 2:
            total_bonus += 0.1
        
        return min(total_bonus, 0.25)
