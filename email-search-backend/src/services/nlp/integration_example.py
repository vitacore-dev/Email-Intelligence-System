"""
Пример интеграции NLP системы с существующим анализатором веб-страниц
Показывает, как использовать NLP модули для улучшения извлечения информации
"""

import logging
from typing import Dict, List, Any, Optional

from .nlp_manager import nlp_manager
from .config import nlp_config

logger = logging.getLogger(__name__)

class EnhancedWebPageAnalyzer:
    """
    Улучшенный анализатор веб-страниц с NLP поддержкой
    Интегрируется с существующим WebPageAnalyzer
    """
    
    def __init__(self):
        self.nlp_manager = nlp_manager
        self.nlp_enabled = False
        
    def initialize_nlp(self) -> bool:
        """Инициализация NLP компонентов"""
        try:
            if self.nlp_manager.initialize():
                self.nlp_enabled = True
                logger.info("NLP система успешно инициализирована")
                return True
            else:
                logger.warning("NLP система инициализирована частично")
                return False
        except Exception as e:
            logger.error(f"Ошибка инициализации NLP: {e}")
            return False
    
    def analyze_with_nlp(self, url: str, text_content: str, email: str) -> Dict[str, Any]:
        """
        Анализ веб-страницы с использованием NLP
        
        Args:
            url: URL страницы
            text_content: Текстовое содержимое страницы
            email: Email адрес для анализа
            
        Returns:
            Расширенная информация с NLP анализом
        """
        
        # Базовая информация
        result = {
            'url': url,
            'email': email,
            'text_length': len(text_content),
            'nlp_enabled': self.nlp_enabled,
            'nlp_analysis': None
        }
        
        if not self.nlp_enabled or not text_content.strip():
            return result
        
        try:
            # Полный NLP анализ
            nlp_result = self.nlp_manager.analyze_text(text_content, email=email)
            
            # Преобразуем результат в словарь для сериализации
            nlp_analysis = {
                'language': nlp_result.language,
                'processing_time': nlp_result.processing_time,
                'modules_used': nlp_result.metadata.get('modules_used', []),
                
                'entities': [
                    {
                        'text': entity.text,
                        'label': entity.label,
                        'confidence': entity.confidence,
                        'start_pos': entity.start_pos,
                        'end_pos': entity.end_pos,
                        'metadata': entity.metadata
                    }
                    for entity in nlp_result.entities
                ],
                
                'professional_roles': [
                    {
                        'title': role.title,
                        'category': role.category,
                        'confidence': role.confidence,
                        'context': role.context[:200] + '...' if len(role.context) > 200 else role.context,
                        'metadata': role.metadata
                    }
                    for role in nlp_result.professional_roles
                ],
                
                'email_contexts': [
                    {
                        'email': ctx.email,
                        'before_text': ctx.before_text,
                        'after_text': ctx.after_text,
                        'full_sentence': ctx.full_sentence,
                        'position': ctx.position
                    }
                    for ctx in nlp_result.email_contexts
                ],
                
                'email_owner_analysis': nlp_result.metadata.get('email_owner_analysis', {})
            }
            
            result['nlp_analysis'] = nlp_analysis
            
            # Извлекаем ключевую информацию для совместимости
            result['enhanced_info'] = self._extract_key_info(nlp_analysis)
            
            logger.debug(f"NLP анализ завершен для {url}")
            
        except Exception as e:
            logger.error(f"Ошибка NLP анализа для {url}: {e}")
            result['nlp_error'] = str(e)
        
        return result
    
    def _extract_key_info(self, nlp_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение ключевой информации из NLP анализа"""
        
        key_info = {
            'detected_persons': [],
            'detected_organizations': [],
            'professional_roles': [],
            'most_likely_owner': None,
            'owner_confidence': 0.0,
            'language': nlp_analysis.get('language', 'unknown')
        }
        
        # Извлекаем персон и организации
        for entity in nlp_analysis.get('entities', []):
            if entity['label'] == 'person' and entity['confidence'] > 0.7:
                key_info['detected_persons'].append({
                    'name': entity['text'],
                    'confidence': entity['confidence']
                })
            elif entity['label'] == 'organization' and entity['confidence'] > 0.7:
                key_info['detected_organizations'].append({
                    'name': entity['text'],
                    'confidence': entity['confidence']
                })
        
        # Извлекаем роли
        for role in nlp_analysis.get('professional_roles', []):
            if role['confidence'] > 0.6:
                key_info['professional_roles'].append({
                    'title': role['title'],
                    'category': role['category'],
                    'confidence': role['confidence']
                })
        
        # Определяем наиболее вероятного владельца email
        owner_analysis = nlp_analysis.get('email_owner_analysis', {})
        if owner_analysis and owner_analysis.get('best_owner'):
            best_owner = owner_analysis['best_owner']
            key_info['most_likely_owner'] = self._format_owner_info(best_owner)
            key_info['owner_confidence'] = owner_analysis.get('analysis_confidence', 0.0)
        
        return key_info
    
    def _format_owner_info(self, best_owner: Dict[str, Any]) -> Dict[str, Any]:
        """Форматирование информации о владельце"""
        
        owner_info = {
            'source': best_owner['source'],
            'confidence': best_owner['confidence'],
            'type': best_owner['data'].get('type', 'unknown')
        }
        
        # Извлекаем конкретную информацию в зависимости от источника
        data = best_owner['data']
        
        if best_owner['source'] == 'pattern' and 'extracted_data' in data:
            extracted = data['extracted_data']
            if 'name' in extracted:
                owner_info['name'] = extracted['name']
            if 'role' in extracted:
                owner_info['role'] = extracted['role']
        
        elif best_owner['source'] == 'proximity' and 'entity' in data:
            entity = data['entity']
            owner_info['name'] = entity['text']
            owner_info['distance'] = data['distance']
        
        elif best_owner['source'] == 'direct':
            owner_info['matched_text'] = data.get('matched_text', '')
        
        return owner_info
    
    def get_nlp_status(self) -> Dict[str, Any]:
        """Получение статуса NLP системы"""
        if not self.nlp_enabled:
            return {'enabled': False, 'reason': 'NLP not initialized'}
        
        return self.nlp_manager.get_status()
    
    def configure_nlp(self, **config_updates) -> bool:
        """
        Обновление конфигурации NLP
        
        Примеры использования:
        - configure_nlp(named_entity_recognition={'enabled': False})
        - configure_nlp(email_owner_identification={'context_window': 500})
        """
        try:
            for module_name, module_config in config_updates.items():
                if module_name in nlp_config.modules:
                    nlp_config.modules[module_name].update(module_config)
                    logger.info(f"Обновлена конфигурация модуля {module_name}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления конфигурации NLP: {e}")
            return False

# Пример использования
def example_usage():
    """Пример использования улучшенного анализатора"""
    
    # Создаем анализатор и инициализируем NLP
    analyzer = EnhancedWebPageAnalyzer()
    analyzer.initialize_nlp()
    
    # Пример текста веб-страницы
    sample_text = """
    Кафедра хирургии
    
    Заведующий кафедрой: профессор Иванов Иван Иванович
    
    Профессор Иванов И.И. является ведущим специалистом в области 
    сердечно-сосудистой хирургии. Для связи с профессором используйте 
    email: surgery-89@yandex.ru
    
    Кафедра располагается в Московском государственном медицинском 
    университете им. И.М. Сеченова.
    """
    
    # Анализируем страницу
    result = analyzer.analyze_with_nlp(
        url="https://example.com/surgery-department",
        text_content=sample_text,
        email="surgery-89@yandex.ru"
    )
    
    # Выводим результат
    print("=== Результат NLP анализа ===")
    print(f"Язык: {result.get('nlp_analysis', {}).get('language', 'unknown')}")
    print(f"Время обработки: {result.get('nlp_analysis', {}).get('processing_time', 0):.3f} сек")
    
    enhanced_info = result.get('enhanced_info', {})
    
    print(f"\nОбнаруженные персоны:")
    for person in enhanced_info.get('detected_persons', []):
        print(f"  - {person['name']} (уверенность: {person['confidence']:.2f})")
    
    print(f"\nПрофессиональные роли:")
    for role in enhanced_info.get('professional_roles', []):
        print(f"  - {role['title']} ({role['category']}, уверенность: {role['confidence']:.2f})")
    
    most_likely_owner = enhanced_info.get('most_likely_owner')
    if most_likely_owner:
        print(f"\nНаиболее вероятный владельец email:")
        print(f"  - Источник: {most_likely_owner['source']}")
        print(f"  - Уверенность: {enhanced_info.get('owner_confidence', 0):.2f}")
        if 'name' in most_likely_owner:
            print(f"  - Имя: {most_likely_owner['name']}")
        if 'role' in most_likely_owner:
            print(f"  - Роль: {most_likely_owner['role']}")

if __name__ == "__main__":
    example_usage()
