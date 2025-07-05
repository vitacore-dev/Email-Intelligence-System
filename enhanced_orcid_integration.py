#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔗 Интеграция улучшенного алгоритма ранжирования ORCID в существующую систему

Этот модуль показывает, как интегрировать новый алгоритм в текущую архитектуру
email-search-backend с минимальными изменениями в существующем коде.

Автор: AI Assistant
Дата: 2025-07-04
Версия: 1.0
"""

import logging
from typing import Dict, List, Optional, Any
from enhanced_orcid_ranking_algorithm import EnhancedORCIDRankingAlgorithm, ORCIDCandidate

logger = logging.getLogger(__name__)

class EnhancedORCIDIntegration:
    """Класс для интеграции улучшенного алгоритма в существующую систему"""
    
    def __init__(self, enable_ml: bool = True, cache_dir: str = "./cache"):
        """
        Инициализация интегратора
        
        Args:
            enable_ml: Включить ML функции (требует дополнительные зависимости)
            cache_dir: Директория для кэширования
        """
        self.enhanced_algorithm = EnhancedORCIDRankingAlgorithm(
            cache_dir=cache_dir,
            enable_ml=enable_ml
        )
        
        # Флаг для включения/выключения нового алгоритма
        self.use_enhanced_algorithm = True
        
        logger.info("🚀 Интеграция улучшенного алгоритма ORCID инициализирована")
    
    def enhance_existing_orcid_selection(self,
                                       found_orcids: List[Dict[str, Any]], 
                                       email: str,
                                       target_name: Optional[str] = None,
                                       context: str = "academic") -> Dict[str, Any]:
        """
        Улучшает существующую логику выбора ORCID
        
        Args:
            found_orcids: Список найденных ORCID из существующего алгоритма
            email: Email для поиска
            target_name: Известное имя владельца
            context: Контекст использования
            
        Returns:
            Лучший ORCID кандидат с дополнительной информацией
        """
        if not self.use_enhanced_algorithm or not found_orcids:
            # Fallback к старому алгоритму
            return self._fallback_to_legacy_algorithm(found_orcids)
        
        try:
            logger.info(f"🎯 Применяем улучшенный алгоритм к {len(found_orcids)} кандидатам")
            
            # Ранжируем кандидатов новым алгоритмом
            ranked_candidates = self.enhanced_algorithm.rank_orcid_candidates(
                candidates=found_orcids,
                email=email,
                context=context,
                target_name=target_name
            )
            
            if not ranked_candidates:
                return self._fallback_to_legacy_algorithm(found_orcids)
            
            # Выбираем лучшего кандидата
            best_candidate = ranked_candidates[0]
            
            # Формируем результат в формате совместимом со старой системой
            result = {
                'orcid': best_candidate.orcid_id,
                'url': best_candidate.url,
                'position_in_list': best_candidate.position_in_search,
                'relevance_score': best_candidate.relevance_score,
                'confidence_level': best_candidate.confidence_level,
                'is_direct_orcid_url': 'orcid.org' in best_candidate.url.lower(),
                
                # Дополнительная информация от нового алгоритма
                'enhanced_scores': {
                    'position': best_candidate.position_score,
                    'url_quality': best_candidate.url_quality_score,
                    'name_similarity': best_candidate.name_similarity_score,
                    'domain_quality': best_candidate.domain_quality_score,
                    'domain_affinity': best_candidate.domain_affinity_score,
                    'temporal': best_candidate.temporal_score,
                    'network': best_candidate.network_score,
                    'citation': best_candidate.citation_score,
                    'semantic': best_candidate.semantic_score
                },
                
                # Метаданные
                'extracted_names': best_candidate.extracted_names,
                'publication_count': best_candidate.publication_count,
                'h_index': best_candidate.h_index,
                'research_areas': best_candidate.research_areas,
                
                # Все ранжированные кандидаты для отладки
                'all_candidates': [
                    {
                        'orcid': c.orcid_id,
                        'relevance_score': c.relevance_score,
                        'confidence_level': c.confidence_level,
                        'position_in_search': c.position_in_search
                    }
                    for c in ranked_candidates
                ]
            }
            
            logger.info(f"✅ Выбран ORCID {best_candidate.orcid_id} с релевантностью {best_candidate.relevance_score:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка в улучшенном алгоритме: {str(e)}")
            return self._fallback_to_legacy_algorithm(found_orcids)
    
    def _fallback_to_legacy_algorithm(self, found_orcids: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback к существующему алгоритму"""
        if not found_orcids:
            return None
            
        # Сортируем по существующему полю relevance_score
        sorted_orcids = sorted(found_orcids, 
                             key=lambda x: x.get('relevance_score', 0), 
                             reverse=True)
        
        best_orcid = sorted_orcids[0]
        logger.info(f"🔄 Fallback к старому алгоритму: выбран {best_orcid.get('orcid')}")
        
        return best_orcid
    
    def get_comparative_analysis(self,
                               found_orcids: List[Dict[str, Any]], 
                               email: str,
                               target_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Сравнивает результаты старого и нового алгоритмов
        
        Returns:
            Сравнительный анализ двух алгоритмов
        """
        if not found_orcids:
            return {'error': 'Нет кандидатов для сравнения'}
        
        # Результат старого алгоритма
        legacy_result = self._fallback_to_legacy_algorithm(found_orcids)
        
        # Результат нового алгоритма
        enhanced_result = None
        try:
            self.use_enhanced_algorithm = True
            enhanced_result = self.enhance_existing_orcid_selection(
                found_orcids, email, target_name
            )
        except:
            enhanced_result = None
        
        comparison = {
            'legacy_algorithm': {
                'selected_orcid': legacy_result.get('orcid') if legacy_result else None,
                'relevance_score': legacy_result.get('relevance_score', 0) if legacy_result else 0
            },
            'enhanced_algorithm': {
                'selected_orcid': enhanced_result.get('orcid') if enhanced_result else None,
                'relevance_score': enhanced_result.get('relevance_score', 0) if enhanced_result else 0,
                'confidence_level': enhanced_result.get('confidence_level') if enhanced_result else None
            },
            'comparison': {
                'algorithms_agree': False,
                'score_difference': 0,
                'recommendation': 'use_legacy'
            }
        }
        
        # Анализ сравнения
        if enhanced_result and legacy_result:
            legacy_orcid = legacy_result.get('orcid')
            enhanced_orcid = enhanced_result.get('orcid')
            
            comparison['comparison']['algorithms_agree'] = (legacy_orcid == enhanced_orcid)
            comparison['comparison']['score_difference'] = (
                enhanced_result.get('relevance_score', 0) - 
                legacy_result.get('relevance_score', 0)
            )
            
            # Рекомендация
            if enhanced_result.get('confidence_level') in ['high', 'very_high']:
                comparison['comparison']['recommendation'] = 'use_enhanced'
            elif comparison['comparison']['algorithms_agree']:
                comparison['comparison']['recommendation'] = 'both_agree'
            else:
                comparison['comparison']['recommendation'] = 'manual_review'
        
        return comparison
    
    def add_user_feedback(self,
                         email: str,
                         selected_orcid: str,
                         correct_orcid: str,
                         confidence: float = 1.0):
        """Добавляет обратную связь пользователя для обучения алгоритма"""
        try:
            self.enhanced_algorithm.add_feedback(
                email=email,
                selected_orcid=selected_orcid,
                correct_orcid=correct_orcid,
                user_confidence=confidence
            )
            logger.info(f"📝 Обратная связь добавлена для {email}")
        except Exception as e:
            logger.error(f"Ошибка добавления обратной связи: {str(e)}")
    
    def get_algorithm_performance(self) -> Dict[str, Any]:
        """Возвращает метрики производительности алгоритма"""
        return self.enhanced_algorithm.get_algorithm_stats()
    
    def export_trained_model(self, filepath: str):
        """Экспортирует обученную модель"""
        self.enhanced_algorithm.export_model(filepath)
    
    def import_trained_model(self, filepath: str):
        """Импортирует обученную модель"""
        self.enhanced_algorithm.import_model(filepath)


def create_migration_patch_for_search_engines():
    """
    Генерирует патч для интеграции в существующий файл search_engines.py
    
    Returns:
        Код патча для добавления в существующий класс
    """
    
    patch_code = '''
# Добавить в начало файла search_engines.py:
from enhanced_orcid_integration import EnhancedORCIDIntegration

# Добавить в __init__ метод класса SearchEngineService:
self.enhanced_orcid = EnhancedORCIDIntegration(
    enable_ml=True,  # Можно отключить если нет зависимостей
    cache_dir="./data/cache"
)

# Заменить существующий метод _select_best_orcid:
def _select_best_orcid(self, found_orcids: List[Dict[str, Any]], 
                      email: str = None, 
                      target_name: str = None) -> Dict[str, Any]:
    """Выбирает наиболее релевантный ORCID из найденных (улучшенная версия)"""
    
    if not found_orcids:
        return None
    
    try:
        # Используем улучшенный алгоритм
        result = self.enhanced_orcid.enhance_existing_orcid_selection(
            found_orcids=found_orcids,
            email=email or "unknown@example.com",
            target_name=target_name,
            context="academic"  # Можно динамически определять
        )
        
        if result:
            logger.info(f"✅ Улучшенный алгоритм выбрал ORCID: {result.get('orcid')}")
            return result
        
    except Exception as e:
        logger.error(f"Ошибка улучшенного алгоритма: {str(e)}")
    
    # Fallback к существующей логике
    sorted_orcids = sorted(found_orcids, key=lambda x: x['relevance_score'], reverse=True)
    best_orcid = sorted_orcids[0]
    
    logger.info(f"🔄 Fallback: выбран ORCID {best_orcid['orcid']}")
    return best_orcid

# Добавить новый метод для сравнительного анализа:
def compare_orcid_algorithms(self, found_orcids: List[Dict[str, Any]], 
                           email: str, target_name: str = None) -> Dict[str, Any]:
    """Сравнивает результаты старого и нового алгоритмов"""
    
    return self.enhanced_orcid.get_comparative_analysis(
        found_orcids=found_orcids,
        email=email,
        target_name=target_name
    )

# Добавить метод для обратной связи:
def add_orcid_feedback(self, email: str, selected_orcid: str, 
                      correct_orcid: str, confidence: float = 1.0):
    """Добавляет обратную связь для обучения алгоритма"""
    
    self.enhanced_orcid.add_user_feedback(
        email=email,
        selected_orcid=selected_orcid,
        correct_orcid=correct_orcid,
        confidence=confidence
    )
'''
    
    return patch_code


def demonstrate_integration():
    """Демонстрация интеграции с существующей системой"""
    print("🔗 Демонстрация интеграции улучшенного алгоритма\n")
    
    # Инициализация интегратора
    integration = EnhancedORCIDIntegration(enable_ml=False)
    
    # Симуляция данных из существующей системы
    legacy_orcids = [
        {
            'orcid': '0000-0003-2583-0599',
            'url': 'https://orcid.org/0000-0003-2583-0599',
            'position_in_list': 40,
            'relevance_score': 0.61,  # Старая оценка
            'is_direct_orcid_url': True
        },
        {
            'orcid': '0000-0003-4812-2165',
            'url': 'https://example.edu/profile/researcher',
            'position_in_list': 9,
            'relevance_score': 0.63,  # Старая оценка
            'is_direct_orcid_url': False
        }
    ]
    
    email = "damirov@list.ru"
    target_name = "Марапов Дамир Ильдарович"
    
    print("📊 Тестовые данные:")
    print(f"Email: {email}")
    print(f"Целевое имя: {target_name}")
    print(f"Кандидатов: {len(legacy_orcids)}")
    print()
    
    # Сравнительный анализ
    comparison = integration.get_comparative_analysis(
        found_orcids=legacy_orcids,
        email=email,
        target_name=target_name
    )
    
    print("🔄 Сравнительный анализ алгоритмов:")
    print("=" * 60)
    
    legacy = comparison['legacy_algorithm']
    enhanced = comparison['enhanced_algorithm']
    comp = comparison['comparison']
    
    print(f"Старый алгоритм:")
    print(f"  ORCID: {legacy['selected_orcid']}")
    print(f"  Оценка: {legacy['relevance_score']:.3f}")
    print()
    
    print(f"Новый алгоритм:")
    print(f"  ORCID: {enhanced['selected_orcid']}")
    print(f"  Оценка: {enhanced['relevance_score']:.3f}")
    print(f"  Уверенность: {enhanced['confidence_level']}")
    print()
    
    print(f"Сравнение:")
    print(f"  Алгоритмы согласны: {comp['algorithms_agree']}")
    print(f"  Разница в оценках: {comp['score_difference']:.3f}")
    print(f"  Рекомендация: {comp['recommendation']}")
    print()
    
    # Детальный результат нового алгоритма
    enhanced_result = integration.enhance_existing_orcid_selection(
        found_orcids=legacy_orcids,
        email=email,
        target_name=target_name,
        context="academic"
    )
    
    if enhanced_result:
        print("🎯 Детальный анализ нового алгоритма:")
        print("=" * 60)
        print(f"Выбранный ORCID: {enhanced_result['orcid']}")
        print(f"Общая релевантность: {enhanced_result['relevance_score']:.3f}")
        print(f"Уровень уверенности: {enhanced_result['confidence_level']}")
        print()
        
        scores = enhanced_result['enhanced_scores']
        print("Детализация факторов:")
        for factor, score in scores.items():
            print(f"  {factor}: {score:.3f}")
        print()
        
        print(f"Метаданные:")
        print(f"  Извлечено имен: {len(enhanced_result['extracted_names'])}")
        print(f"  Публикации: {enhanced_result['publication_count']}")
        print(f"  H-index: {enhanced_result['h_index']}")
        print(f"  Области исследований: {enhanced_result['research_areas']}")
    
    # Симуляция обратной связи
    print("\n🎓 Симуляция обратной связи...")
    integration.add_user_feedback(
        email=email,
        selected_orcid=enhanced_result['orcid'],
        correct_orcid="0000-0003-2583-0599",  # Референсный ORCID
        confidence=0.9
    )
    
    # Статистика
    stats = integration.get_algorithm_performance()
    print(f"\n📈 Статистика алгоритма:")
    print(f"Версия: {stats['version']}")
    print(f"Точность: {stats['current_accuracy']:.3f}")
    print(f"Обработано случаев: {stats['total_processed']}")
    print(f"Получено обратной связи: {stats['feedback_received']}")
    
    # Генерация патча
    print(f"\n🔧 Генерация патча для интеграции...")
    patch = create_migration_patch_for_search_engines()
    
    with open("integration_patch.py", "w", encoding="utf-8") as f:
        f.write(f"# Патч для интеграции улучшенного алгоритма ORCID\n")
        f.write(f"# Дата: 2025-07-04\n\n")
        f.write(patch)
    
    print(f"✅ Патч сохранен в integration_patch.py")
    
    return enhanced_result


if __name__ == "__main__":
    demonstrate_integration()
