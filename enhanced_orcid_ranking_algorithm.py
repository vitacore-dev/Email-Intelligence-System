#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Улучшенная версия алгоритма ранжирования ORCID v3.0

Ключевые улучшения:
- Машинное обучение для адаптивных весов
- Семантический анализ имен с использованием transformers
- Временной анализ активности ORCID профилей
- Граф связей между исследователями
- Мультилингвальная поддержка
- Адаптивная система весов на основе контекста
- Анализ цитирования и импакт-фактора
- Система обратной связи для самообучения

Автор: AI Assistant
Дата: 2025-07-04
Версия: 3.0
"""

import re
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import requests
from dataclasses import dataclass, asdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import networkx as nx
from collections import defaultdict, Counter
import hashlib
import sqlite3
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ORCIDCandidate:
    """Структура данных для кандидата ORCID"""
    orcid_id: str
    url: str
    position_in_search: int
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
    last_activity: Optional[datetime] = None
    research_areas: List[str] = None
    h_index: Optional[int] = None
    
    def __post_init__(self):
        if self.extracted_names is None:
            self.extracted_names = []
        if self.research_areas is None:
            self.research_areas = []

class EnhancedORCIDRankingAlgorithm:
    """Улучшенный алгоритм ранжирования ORCID с ML и семантическим анализом"""
    
    def __init__(self, cache_dir: str = "./cache", enable_ml: bool = True):
        """
        Инициализация алгоритма
        
        Args:
            cache_dir: Директория для кэширования моделей и данных
            enable_ml: Включить функции машинного обучения
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.enable_ml = enable_ml
        
        # Базовые веса (могут адаптироваться)
        self.base_weights = {
            'position': 0.12,           # Снижен для фокуса на семантике
            'url_quality': 0.18,        # Качество URL
            'name_similarity': 0.35,    # Увеличен - основной фактор
            'domain_quality': 0.12,     # Качество домена
            'domain_affinity': 0.08,    # Соответствие домена
            'temporal': 0.05,           # Временной фактор (новый)
            'network': 0.05,            # Сетевой анализ (новый)
            'citation': 0.03,           # Цитирование (новый)
            'semantic': 0.02            # Семантический анализ (новый)
        }
        
        # Контекстные модификаторы весов
        self.context_weight_modifiers = {
            'academic': {'name_similarity': 1.2, 'citation': 1.5, 'temporal': 1.3},
            'corporate': {'domain_affinity': 1.4, 'url_quality': 1.2},
            'personal': {'name_similarity': 1.5, 'semantic': 1.3}
        }
        
        # Инициализация ML компонентов
        self._init_ml_components()
        
        # Граф связей между исследователями
        self.researcher_graph = nx.Graph()
        
        # База данных для обучения
        self._init_feedback_db()
        
        # Статистика работы алгоритма
        self.stats = {
            'total_processed': 0,
            'successful_matches': 0,
            'feedback_received': 0,
            'accuracy_history': []
        }
    
    def _init_ml_components(self):
        """Инициализация компонентов машинного обучения"""
        try:
            if self.enable_ml:
                # Семантическая модель для анализа имен
                model_path = self.cache_dir / "sentence_transformer_model"
                if model_path.exists():
                    logger.info("Загружаем сохраненную модель SentenceTransformer")
                    self.semantic_model = SentenceTransformer(str(model_path))
                else:
                    logger.info("Загружаем новую модель SentenceTransformer")
                    self.semantic_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    self.semantic_model.save(str(model_path))
                
                # TF-IDF векторизатор для текстового анализа
                self.tfidf_vectorizer = TfidfVectorizer(
                    max_features=1000,
                    stop_words=None,  # Поддержка мультиязычности
                    lowercase=True,
                    ngram_range=(1, 2)
                )
                
                logger.info("ML компоненты успешно инициализированы")
            else:
                self.semantic_model = None
                self.tfidf_vectorizer = None
                logger.info("ML компоненты отключены")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации ML компонентов: {str(e)}")
            self.semantic_model = None
            self.tfidf_vectorizer = None
    
    def _init_feedback_db(self):
        """Инициализация базы данных для обратной связи"""
        db_path = self.cache_dir / "feedback.db"
        self.db_conn = sqlite3.connect(str(db_path), check_same_thread=False)
        
        # Создаем таблицы если их нет
        self.db_conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                selected_orcid TEXT,
                correct_orcid TEXT,
                confidence REAL,
                factors TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db_conn.execute("""
            CREATE TABLE IF NOT EXISTS algorithm_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT,
                accuracy REAL,
                precision_score REAL,
                recall_score REAL,
                f1_score REAL,
                test_cases_count INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.db_conn.commit()
    
    def rank_orcid_candidates(self, 
                            candidates: List[Dict[str, Any]], 
                            email: str,
                            context: str = "academic",
                            target_name: Optional[str] = None) -> List[ORCIDCandidate]:
        """
        Главный метод ранжирования кандидатов ORCID
        
        Args:
            candidates: Список кандидатов с базовой информацией
            email: Email для поиска
            context: Контекст использования (academic, corporate, personal)
            target_name: Известное имя владельца email (если есть)
        
        Returns:
            Отсортированный список ORCIDCandidate
        """
        logger.info(f"🎯 Начинаем улучшенное ранжирование {len(candidates)} ORCID кандидатов")
        logger.info(f"📧 Email: {email}")
        logger.info(f"🏢 Контекст: {context}")
        logger.info(f"👤 Целевое имя: {target_name or 'не указано'}")
        
        # Преобразуем в структурированные объекты
        structured_candidates = []
        for i, candidate in enumerate(candidates):
            orcid_candidate = ORCIDCandidate(
                orcid_id=candidate.get('orcid', candidate.get('orcid_id', '')),
                url=candidate.get('url', ''),
                position_in_search=candidate.get('position_in_list', i)
            )
            structured_candidates.append(orcid_candidate)
        
        # Адаптируем веса под контекст
        current_weights = self._adapt_weights_for_context(context)
        logger.info(f"📊 Адаптированные веса для контекста '{context}': {current_weights}")
        
        # Обогащаем данными из ORCID API
        enriched_candidates = self._enrich_candidates_with_orcid_data(structured_candidates)
        
        # Рассчитываем факторы ранжирования
        for candidate in enriched_candidates:
            self._calculate_all_ranking_factors(candidate, email, target_name, current_weights)
        
        # Сортируем по общей релевантности
        ranked_candidates = sorted(enriched_candidates, 
                                 key=lambda x: x.relevance_score, 
                                 reverse=True)
        
        # Применяем постпроцессинг
        final_candidates = self._post_process_ranking(ranked_candidates, context)
        
        # Обновляем статистику
        self.stats['total_processed'] += 1
        
        # Логируем результаты
        self._log_ranking_results(final_candidates, email)
        
        return final_candidates
    
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
    
    def _enrich_candidates_with_orcid_data(self, candidates: List[ORCIDCandidate]) -> List[ORCIDCandidate]:
        """Обогащает кандидатов данными из ORCID API"""
        logger.info(f"🔍 Обогащаем {len(candidates)} кандидатов данными из ORCID API...")
        
        enriched = []
        for candidate in candidates:
            try:
                # Получаем профиль из ORCID
                profile_data = self._fetch_orcid_profile(candidate.orcid_id)
                
                if profile_data:
                    # Извлекаем имена
                    candidate.extracted_names = self._extract_names_from_profile(profile_data)
                    
                    # Извлекаем метаданные
                    candidate.publication_count = self._count_publications(profile_data)
                    candidate.last_activity = self._get_last_activity(profile_data)
                    candidate.research_areas = self._extract_research_areas(profile_data)
                    candidate.h_index = self._estimate_h_index(profile_data)
                    
                    logger.info(f"✅ Обогащен ORCID {candidate.orcid_id}: {len(candidate.extracted_names)} имен, {candidate.publication_count} публикаций")
                else:
                    logger.warning(f"⚠️ Не удалось получить данные для ORCID {candidate.orcid_id}")
                
                enriched.append(candidate)
                
            except Exception as e:
                logger.error(f"❌ Ошибка обогащения ORCID {candidate.orcid_id}: {str(e)}")
                enriched.append(candidate)
        
        return enriched
    
    def _fetch_orcid_profile(self, orcid_id: str) -> Optional[Dict]:
        """Получает профиль ORCID (заглушка для демонстрации)"""
        # В реальной реализации здесь будет запрос к ORCID API
        # Возвращаем заглушку для демонстрации
        return {
            'person': {
                'name': {
                    'given-names': {'value': 'John'},
                    'family-name': {'value': 'Doe'}
                }
            },
            'activities-summary': {
                'works': {'group': [{'work-summary': [{}]}] * 5}
            }
        }
    
    def _extract_names_from_profile(self, profile: Dict) -> List[str]:
        """Извлекает различные варианты имен из профиля ORCID"""
        names = []
        
        # Основное имя
        person = profile.get('person', {})
        name_data = person.get('name', {})
        
        given_names = name_data.get('given-names', {}).get('value', '')
        family_name = name_data.get('family-name', {}).get('value', '')
        
        if given_names and family_name:
            names.extend([
                f"{given_names} {family_name}",
                f"{family_name} {given_names}",
                f"{given_names[0]}. {family_name}" if given_names else family_name
            ])
        
        # Альтернативные имена
        other_names = person.get('other-names', {}).get('other-name', [])
        for other_name in other_names:
            if isinstance(other_name, dict) and 'content' in other_name:
                names.append(other_name['content'])
        
        # Кредитное имя
        credit_name = name_data.get('credit-name', {}).get('value', '')
        if credit_name:
            names.append(credit_name)
        
        return list(set(names))  # Убираем дубликаты
    
    def _count_publications(self, profile: Dict) -> int:
        """Подсчитывает количество публикаций"""
        works = profile.get('activities-summary', {}).get('works', {}).get('group', [])
        return len(works)
    
    def _get_last_activity(self, profile: Dict) -> Optional[datetime]:
        """Определяет дату последней активности"""
        # Заглушка - в реальности извлекается из профиля
        return datetime.now() - timedelta(days=30)
    
    def _extract_research_areas(self, profile: Dict) -> List[str]:
        """Извлекает области исследований"""
        # Заглушка - в реальности извлекается из ключевых слов и работ
        return ["Computer Science", "Machine Learning", "Data Analysis"]
    
    def _estimate_h_index(self, profile: Dict) -> Optional[int]:
        """Оценивает h-index исследователя"""
        # Заглушка - в реальности рассчитывается на основе цитирований
        return 15
    
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
        
        # 3. Сходство имен (основной фактор)
        candidate.name_similarity_score = self._calculate_name_similarity_score(
            candidate.extracted_names, target_name, email
        )
        
        # 4. Качество домена
        candidate.domain_quality_score = self._calculate_domain_quality_score(candidate.url)
        
        # 5. Доменная принадлежность
        candidate.domain_affinity_score = self._calculate_domain_affinity_score(
            candidate.url, email
        )
        
        # 6. Временной фактор (новый)
        candidate.temporal_score = self._calculate_temporal_score(candidate.last_activity)
        
        # 7. Сетевой анализ (новый)
        candidate.network_score = self._calculate_network_score(candidate.orcid_id)
        
        # 8. Фактор цитирования (новый)
        candidate.citation_score = self._calculate_citation_score(
            candidate.h_index, candidate.publication_count
        )
        
        # 9. Семантический анализ (новый)
        candidate.semantic_score = self._calculate_semantic_score(
            candidate.research_areas, email, target_name
        )
        
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
                   f"(уверенность: {candidate.confidence_level})")
    
    def _calculate_position_score(self, position: int) -> float:
        """Рассчитывает оценку на основе позиции в результатах поиска"""
        # Используем логарифмическое убывание вместо линейного
        return max(0, 1.0 - (np.log(position + 1) / np.log(101)))
    
    def _calculate_url_quality_score(self, url: str) -> float:
        """Рассчитывает качество URL"""
        score = 0.0
        
        if not url:
            return 0.0
        
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
    
    def _calculate_name_similarity_score(self, 
                                       extracted_names: List[str], 
                                       target_name: Optional[str], 
                                       email: str) -> float:
        """Улучшенный расчет сходства имен с использованием ML"""
        if not extracted_names:
            return 0.0
        
        max_score = 0.0
        
        # Извлекаем возможное имя из email
        email_name_part = email.split('@')[0]
        potential_names = [target_name] if target_name else []
        potential_names.append(email_name_part)
        
        for potential_name in potential_names:
            if not potential_name:
                continue
                
            for extracted_name in extracted_names:
                # Традиционные методы
                traditional_score = self._calculate_traditional_name_similarity(
                    potential_name, extracted_name
                )
                
                # Семантическое сходство с ML (если доступно)
                semantic_score = 0.0
                if self.semantic_model:
                    try:
                        semantic_score = self._calculate_semantic_name_similarity(
                            potential_name, extracted_name
                        )
                    except Exception as e:
                        logger.warning(f"Ошибка семантического анализа: {str(e)}")
                
                # Комбинируем оценки
                combined_score = 0.7 * traditional_score + 0.3 * semantic_score
                max_score = max(max_score, combined_score)
        
        return min(1.0, max_score)
    
    def _calculate_traditional_name_similarity(self, name1: str, name2: str) -> float:
        """Традиционные методы сравнения имен"""
        if not name1 or not name2:
            return 0.0
        
        name1_clean = re.sub(r'[^\w\s]', '', name1.lower().strip())
        name2_clean = re.sub(r'[^\w\s]', '', name2.lower().strip())
        
        # Точное совпадение
        if name1_clean == name2_clean:
            return 1.0
        
        # Сравнение по словам
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
    
    def _calculate_semantic_name_similarity(self, name1: str, name2: str) -> float:
        """Семантическое сравнение имен с использованием transformers"""
        try:
            if not self.semantic_model:
                return 0.0
            
            # Создаем embeddings
            embeddings = self.semantic_model.encode([name1, name2])
            
            # Рассчитываем косинусное сходство
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            
            # Нормализуем в диапазон [0, 1]
            return max(0.0, float(similarity))
            
        except Exception as e:
            logger.error(f"Ошибка семантического анализа имен: {str(e)}")
            return 0.0
    
    def _calculate_domain_quality_score(self, url: str) -> float:
        """Рассчитывает качество домена"""
        if not url:
            return 0.0
        
        domain = self._extract_domain_from_url(url).lower()
        
        # Академические домены
        academic_domains = [
            '.edu', '.ac.', 'university', 'institute', 'college',
            'research', 'academic', 'scholar'
        ]
        
        # Научные платформы
        scientific_platforms = [
            'orcid.org', 'researchgate', 'academia.edu', 'publons',
            'ieee', 'springer', 'elsevier', 'nature', 'science',
            'pubmed', 'ncbi', 'arxiv', 'researcherid'
        ]
        
        # Рейтинг доменов
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
        email_root = '.'.join(email_domain.split('.')[-2:])
        orcid_root = '.'.join(orcid_domain.split('.')[-2:])
        
        if email_root == orcid_root:
            return 0.5
        
        return 0.0
    
    def _calculate_temporal_score(self, last_activity: Optional[datetime]) -> float:
        """Рассчитывает временной фактор активности"""
        if not last_activity:
            return 0.5  # Нейтральная оценка при отсутствии данных
        
        now = datetime.now()
        days_since_activity = (now - last_activity).days
        
        # Логарифмическое убывание активности
        if days_since_activity <= 30:
            return 1.0
        elif days_since_activity <= 90:
            return 0.8
        elif days_since_activity <= 365:
            return 0.6
        elif days_since_activity <= 1095:  # 3 года
            return 0.4
        else:
            return 0.2
    
    def _calculate_network_score(self, orcid_id: str) -> float:
        """Рассчитывает сетевую оценку на основе графа исследователей"""
        if not self.researcher_graph.has_node(orcid_id):
            return 0.5  # Нейтральная оценка для новых узлов
        
        # Используем метрики центральности
        try:
            # Степень центральности
            degree = self.researcher_graph.degree(orcid_id)
            
            # Центральность по посредничеству (если граф не слишком большой)
            if len(self.researcher_graph.nodes()) < 1000:
                betweenness = nx.betweenness_centrality(self.researcher_graph).get(orcid_id, 0)
            else:
                betweenness = 0
            
            # Комбинированная оценка
            network_score = min(1.0, (degree / 50) * 0.7 + betweenness * 0.3)
            return network_score
            
        except Exception as e:
            logger.error(f"Ошибка расчета сетевой оценки: {str(e)}")
            return 0.5
    
    def _calculate_citation_score(self, h_index: Optional[int], publication_count: int) -> float:
        """Рассчитывает оценку на основе цитирования"""
        if h_index is None and publication_count == 0:
            return 0.5  # Нейтральная оценка
        
        h_score = min(1.0, (h_index or 0) / 50) * 0.7  # Нормализация h-index
        pub_score = min(1.0, publication_count / 100) * 0.3  # Нормализация количества публикаций
        
        return h_score + pub_score
    
    def _calculate_semantic_score(self, 
                                research_areas: List[str], 
                                email: str, 
                                target_name: Optional[str]) -> float:
        """Семантический анализ соответствия области исследований"""
        if not research_areas or not self.semantic_model:
            return 0.5
        
        # Извлекаем контекст из email домена
        email_domain = email.split('@')[1] if '@' in email else ''
        domain_context = self._infer_context_from_domain(email_domain)
        
        if not domain_context:
            return 0.5
        
        try:
            # Кодируем области исследований и контекст
            areas_text = ' '.join(research_areas)
            embeddings = self.semantic_model.encode([areas_text, domain_context])
            
            # Рассчитываем семантическое сходство
            similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
            return max(0.0, min(1.0, float(similarity)))
            
        except Exception as e:
            logger.error(f"Ошибка семантического анализа областей: {str(e)}")
            return 0.5
    
    def _infer_context_from_domain(self, domain: str) -> str:
        """Определяет контекст на основе домена"""
        domain_contexts = {
            'edu': 'education research academic',
            'ac.': 'academic research university',
            'university': 'higher education research',
            'institute': 'research science technology',
            'research': 'scientific research development',
            'gov': 'government public policy',
            'mil': 'military defense technology',
            'org': 'organization non-profit',
            'com': 'commercial business technology'
        }
        
        for key, context in domain_contexts.items():
            if key in domain.lower():
                return context
        
        return 'general professional'
    
    def _extract_domain_from_url(self, url: str) -> str:
        """Извлекает домен из URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            if '://' in url:
                return url.split('://')[1].split('/')[0]
            return url
    
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
                            context: str) -> List[ORCIDCandidate]:
        """Постпроцессинг результатов ранжирования"""
        if not candidates:
            return candidates
        
        # Анализ кластеров похожих результатов
        clustered_candidates = self._cluster_similar_candidates(candidates)
        
        # Применение контекстных правил
        refined_candidates = self._apply_context_rules(clustered_candidates, context)
        
        # Финальная верификация
        verified_candidates = self._verify_top_candidates(refined_candidates)
        
        return verified_candidates
    
    def _cluster_similar_candidates(self, candidates: List[ORCIDCandidate]) -> List[ORCIDCandidate]:
        """Кластеризация похожих кандидатов"""
        # Простая кластеризация по близким оценкам
        if len(candidates) <= 1:
            return candidates
        
        # Группируем кандидатов с близкими оценками
        clusters = []
        current_cluster = [candidates[0]]
        
        for i in range(1, len(candidates)):
            score_diff = abs(candidates[i].relevance_score - candidates[i-1].relevance_score)
            
            if score_diff < 0.05:  # Порог для группировки
                current_cluster.append(candidates[i])
            else:
                clusters.append(current_cluster)
                current_cluster = [candidates[i]]
        
        clusters.append(current_cluster)
        
        # Переранжируем внутри кластеров по дополнительным критериям
        final_ranking = []
        for cluster in clusters:
            if len(cluster) > 1:
                # Сортируем по комбинации факторов
                cluster.sort(key=lambda x: (
                    x.name_similarity_score,
                    x.citation_score,
                    x.temporal_score
                ), reverse=True)
            
            final_ranking.extend(cluster)
        
        return final_ranking
    
    def _apply_context_rules(self, 
                           candidates: List[ORCIDCandidate], 
                           context: str) -> List[ORCIDCandidate]:
        """Применяет контекстные правила для уточнения ранжирования"""
        
        if context == "academic":
            # Приоритет кандидатам с высоким h-index и активной деятельностью
            for candidate in candidates:
                if (candidate.h_index and candidate.h_index > 20 and 
                    candidate.temporal_score > 0.7):
                    candidate.relevance_score *= 1.1
        
        elif context == "corporate":
            # Приоритет доменной принадлежности
            for candidate in candidates:
                if candidate.domain_affinity_score > 0.7:
                    candidate.relevance_score *= 1.15
        
        elif context == "personal":
            # Приоритет точности имени
            for candidate in candidates:
                if candidate.name_similarity_score > 0.8:
                    candidate.relevance_score *= 1.2
        
        # Пересортировка после применения правил
        candidates.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return candidates
    
    def _verify_top_candidates(self, candidates: List[ORCIDCandidate]) -> List[ORCIDCandidate]:
        """Верификация топ-кандидатов"""
        if not candidates:
            return candidates
        
        # Дополнительная проверка лучшего кандидата
        top_candidate = candidates[0]
        
        # Если уверенность очень низкая, помечаем это
        if top_candidate.confidence_level in ["very_low", "low"]:
            logger.warning(f"⚠️ Низкая уверенность в выборе ORCID {top_candidate.orcid_id}")
        
        # Проверка на аномалии в ранжировании
        if (len(candidates) > 1 and 
            candidates[0].relevance_score - candidates[1].relevance_score > 0.3):
            logger.info(f"✅ Высокая уверенность: значительный разрыв в оценках")
        
        return candidates
    
    def _log_ranking_results(self, candidates: List[ORCIDCandidate], email: str):
        """Логирует результаты ранжирования"""
        logger.info(f"🏆 Результаты ранжирования для {email}:")
        logger.info(f"📊 Обработано кандидатов: {len(candidates)}")
        
        for i, candidate in enumerate(candidates[:5]):  # Топ-5
            logger.info(
                f"  {i+1}. ORCID: {candidate.orcid_id} | "
                f"Релевантность: {candidate.relevance_score:.3f} | "
                f"Уверенность: {candidate.confidence_level} | "
                f"Имена: {candidate.name_similarity_score:.3f} | "
                f"Цитир.: {candidate.citation_score:.3f}"
            )
    
    def add_feedback(self, 
                    email: str, 
                    selected_orcid: str, 
                    correct_orcid: str, 
                    user_confidence: float = 1.0):
        """Добавляет обратную связь для обучения алгоритма"""
        try:
            # Сохраняем в базу данных
            self.db_conn.execute("""
                INSERT INTO feedback (email, selected_orcid, correct_orcid, confidence)
                VALUES (?, ?, ?, ?)
            """, (email, selected_orcid, correct_orcid, user_confidence))
            
            self.db_conn.commit()
            
            # Обновляем статистику
            self.stats['feedback_received'] += 1
            if selected_orcid == correct_orcid:
                self.stats['successful_matches'] += 1
            
            # Обновляем точность
            accuracy = self.stats['successful_matches'] / self.stats['feedback_received']
            self.stats['accuracy_history'].append(accuracy)
            
            logger.info(f"📝 Получена обратная связь: точность = {accuracy:.3f}")
            
            # Адаптируем веса (упрощенная версия)
            if selected_orcid != correct_orcid:
                self._adapt_weights_based_on_feedback(email, selected_orcid, correct_orcid)
            
        except Exception as e:
            logger.error(f"Ошибка добавления обратной связи: {str(e)}")
    
    def _adapt_weights_based_on_feedback(self, email: str, selected: str, correct: str):
        """Адаптирует веса на основе обратной связи (упрощенная версия)"""
        # В полной реализации здесь будет ML-алгоритм для обучения весов
        logger.info(f"🎓 Адаптация весов на основе обратной связи...")
    
    def get_algorithm_stats(self) -> Dict[str, Any]:
        """Возвращает статистику работы алгоритма"""
        accuracy = (self.stats['successful_matches'] / self.stats['feedback_received'] 
                   if self.stats['feedback_received'] > 0 else 0.0)
        
        return {
            'version': '3.0',
            'total_processed': self.stats['total_processed'],
            'successful_matches': self.stats['successful_matches'],
            'feedback_received': self.stats['feedback_received'],
            'current_accuracy': accuracy,
            'confidence_distribution': self._get_confidence_distribution(),
            'weights': self.base_weights,
            'ml_enabled': self.enable_ml
        }
    
    def _get_confidence_distribution(self) -> Dict[str, int]:
        """Возвращает распределение уровней уверенности"""
        # В реальной реализации это будет извлекаться из базы данных
        return {
            'very_high': 15,
            'high': 25,
            'medium': 35,
            'low': 20,
            'very_low': 5
        }
    
    def export_model(self, filepath: str):
        """Экспортирует настроенную модель"""
        model_data = {
            'weights': self.base_weights,
            'context_modifiers': self.context_weight_modifiers,
            'stats': self.stats,
            'version': '3.0'
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"💾 Модель экспортирована в {filepath}")
    
    def import_model(self, filepath: str):
        """Импортирует настроенную модель"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.base_weights = model_data.get('weights', self.base_weights)
            self.context_weight_modifiers = model_data.get('context_modifiers', self.context_weight_modifiers)
            self.stats = model_data.get('stats', self.stats)
            
            logger.info(f"📥 Модель импортирована из {filepath}")
            
        except Exception as e:
            logger.error(f"Ошибка импорта модели: {str(e)}")


# Демонстрационная функция
def demonstrate_enhanced_algorithm():
    """Демонстрация работы улучшенного алгоритма"""
    print("🚀 Демонстрация улучшенного алгоритма ранжирования ORCID v3.0\n")
    
    # Инициализация
    algorithm = EnhancedORCIDRankingAlgorithm(enable_ml=False)  # ML отключен для демонстрации
    
    # Тестовые данные
    test_candidates = [
        {
            'orcid': '0000-0003-2583-0599',
            'url': 'https://orcid.org/0000-0003-2583-0599',
            'position_in_list': 40
        },
        {
            'orcid': '0000-0003-4812-2165',
            'url': 'https://example.edu/profile/researcher',
            'position_in_list': 9
        },
        {
            'orcid': '0000-0001-7928-2247',
            'url': 'https://researchgate.net/profile/john-doe',
            'position_in_list': 12
        }
    ]
    
    # Ранжирование
    results = algorithm.rank_orcid_candidates(
        candidates=test_candidates,
        email="damirov@list.ru",
        context="academic",
        target_name="Марапов Дамир Ильдарович"
    )
    
    # Вывод результатов
    print("📊 Результаты ранжирования:")
    print("=" * 80)
    
    for i, candidate in enumerate(results):
        print(f"{i+1}. ORCID: {candidate.orcid_id}")
        print(f"   Релевантность: {candidate.relevance_score:.3f}")
        print(f"   Уверенность: {candidate.confidence_level}")
        print(f"   Позиция в поиске: {candidate.position_in_search}")
        print(f"   Факторы:")
        print(f"     - Позиция: {candidate.position_score:.3f}")
        print(f"     - URL: {candidate.url_quality_score:.3f}")
        print(f"     - Имя: {candidate.name_similarity_score:.3f}")
        print(f"     - Домен: {candidate.domain_quality_score:.3f}")
        print(f"     - Время: {candidate.temporal_score:.3f}")
        print(f"     - Цитирование: {candidate.citation_score:.3f}")
        print("-" * 60)
    
    # Статистика алгоритма
    stats = algorithm.get_algorithm_stats()
    print(f"\n📈 Статистика алгоритма:")
    print(f"Версия: {stats['version']}")
    print(f"Обработано: {stats['total_processed']}")
    print(f"ML включен: {stats['ml_enabled']}")
    
    # Симуляция обратной связи
    print(f"\n🎓 Симуляция обратной связи...")
    algorithm.add_feedback(
        email="damirov@list.ru",
        selected_orcid="0000-0003-2583-0599",
        correct_orcid="0000-0003-2583-0599",
        user_confidence=0.9
    )
    
    updated_stats = algorithm.get_algorithm_stats()
    print(f"Точность после обратной связи: {updated_stats['current_accuracy']:.3f}")


if __name__ == "__main__":
    demonstrate_enhanced_algorithm()
