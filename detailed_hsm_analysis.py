#!/usr/bin/env python3
"""
Детальный анализ страницы https://hsm.susu.ru/hsm/ru/article/view/2614
с проверкой всех этапов обработки
"""

import requests
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Добавляем путь к модулям проекта
sys.path.append('src')

from services.webpage_analyzer import WebpageAnalyzer

def detailed_analysis_test():
    """Детальный тест анализа с логированием всех этапов"""
    print("=== ДЕТАЛЬНЫЙ АНАЛИЗ СТРАНИЦЫ ===")
    
    url = "https://hsm.susu.ru/hsm/ru/article/view/2614"
    test_email = "test@example.com"  # Тестовый email для контекста
    
    try:
        analyzer = WebpageAnalyzer()
        print(f"Анализируем: {url}")
        print(f"Контекст email: {test_email}")
        print()
        
        # Сохраняем email в контексте
        analyzer._current_target_email = test_email
        
        # 1. Проверяем, должна ли страница анализироваться
        should_analyze = analyzer._should_analyze_url(url)
        print(f"1. Должна ли анализироваться страница: {should_analyze}")
        
        if not should_analyze:
            print("   ❌ Страница пропущена на этапе предварительной проверки")
            return
        
        # 2. Анализируем страницу
        print("2. Выполняем анализ страницы...")
        page_data = analyzer._analyze_single_page(url)
        
        if not page_data:
            print("   ❌ Анализ не вернул данных")
            return
        
        print(f"   ✅ Анализ успешен, найдено разделов: {len(page_data)}")
        print(f"   Разделы: {list(page_data.keys())}")
        
        # 3. Детальный анализ найденных имен
        if 'names' in page_data:
            raw_names = page_data['names']
            print(f"\n3. Анализ имен:")
            print(f"   Всего найдено сырых имен: {len(raw_names)}")
            
            for i, name in enumerate(raw_names, 1):
                print(f"   {i}. '{name}'")
            
            # Проверяем фильтрацию имен
            print("\n   Применяем фильтрацию качества...")
            filtered_names = analyzer._filter_names_by_quality(raw_names)
            print(f"   После фильтрации осталось: {len(filtered_names)}")
            
            for i, name in enumerate(filtered_names, 1):
                quality_score = analyzer._calculate_name_quality_score(name)
                print(f"   {i}. '{name}' (качество: {quality_score:.3f})")
            
            # Проверяем соответствие с email
            if filtered_names:
                print(f"\n   Проверяем соответствие с email '{test_email}':")
                for name in filtered_names:
                    email_score = analyzer._calculate_email_match_score(name, test_email)
                    print(f"   - '{name}': {email_score:.3f}")
        
        # 4. Проверяем метаданные
        if 'metadata' in page_data:
            metadata = page_data['metadata']
            print(f"\n4. Метаданные:")
            print(f"   Заголовок: {metadata.get('title', 'Не найден')[:100]}...")
            print(f"   Описание: {metadata.get('description', 'Не найдено')[:100]}...")
            print(f"   Домен: {metadata.get('domain')}")
        
        # 5. Анализируем другие разделы
        for section in ['positions', 'organizations', 'locations', 'contact_info', 'academic_info']:
            if section in page_data and page_data[section]:
                print(f"\n5.{section.title()}:")
                data = page_data[section]
                if isinstance(data, list):
                    print(f"   Найдено элементов: {len(data)}")
                    for item in data[:3]:  # Показываем первые 3
                        print(f"   - {item}")
                    if len(data) > 3:
                        print(f"   ... и еще {len(data) - 3}")
                elif isinstance(data, dict):
                    print(f"   Найдено категорий: {len(data)}")
                    for key, values in data.items():
                        if values:
                            print(f"   - {key}: {len(values) if isinstance(values, list) else values}")
        
        # 6. Проверяем интеграцию в полную систему анализа
        print(f"\n6. Тестируем интеграцию в полную систему...")
        
        # Создаем фиктивные результаты поиска
        mock_search_results = [
            {
                'url': url,
                'title': 'ЗДОРОВЬЕ И ДВИГАТЕЛЬНАЯ АКТИВНОСТЬ НАСЕЛЕНИЯ ГОРОДА ВЛАДИВОСТОКА',
                'snippet': 'Научная статья о здоровье и физической активности'
            }
        ]
        
        # Анализируем как будто это результат поиска
        full_analysis = analyzer.analyze_search_results(
            search_results=mock_search_results,
            limit=1,
            email=test_email
        )
        
        print(f"   Успешные извлечения: {full_analysis['analysis_metadata']['successful_extractions']}")
        print(f"   Неудачные извлечения: {full_analysis['analysis_metadata']['failed_extractions']}")
        
        if full_analysis['owner_identification']['most_likely_name']:
            print(f"   ✅ Определено наиболее вероятное имя: '{full_analysis['owner_identification']['most_likely_name']}'")
            print(f"   Уверенность: {full_analysis['owner_identification']['confidence_score']:.3f}")
        else:
            print(f"   ❌ Наиболее вероятное имя не определено")
            print(f"   Всего найденных имен: {len(full_analysis['owner_identification']['names_found'])}")
        
        print(f"\n7. Детали анализа URL:")
        analyzed_urls = full_analysis['analysis_metadata']['analyzed_urls']
        for url_info in analyzed_urls:
            print(f"   URL: {url_info['url']}")
            print(f"   Статус: {url_info['status']}")
            if 'extracted_data_types' in url_info:
                print(f"   Извлеченные типы данных: {url_info['extracted_data_types']}")
            if 'relevance_score' in url_info:
                print(f"   Релевантность: {url_info['relevance_score']}")
            if 'reason' in url_info:
                print(f"   Причина неудачи: {url_info['reason']}")
        
    except Exception as e:
        print(f"❌ Ошибка при детальном анализе: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            analyzer.close()
        except:
            pass

def test_name_filtering():
    """Тест системы фильтрации имен на примерах"""
    print("\n" + "="*60)
    print("=== ТЕСТ СИСТЕМЫ ФИЛЬТРАЦИИ ИМЕН ===")
    
    analyzer = WebpageAnalyzer()
    
    # Тестовые имена, которые были найдены
    test_names = [
        'Ваше Имя',
        'Краснобаева Тихоокеанский', 
        'Кибирев Тихоокеанский',
        'Каерова Тихоокеанский',
        'Дьяконова Владивостокский',
        'Россия Студент',
        'Россия Мастер', 
        'Россия Кандидат'
    ]
    
    print(f"Тестируем {len(test_names)} найденных имен:")
    
    for name in test_names:
        is_human = analyzer._is_human_name(name)
        quality_score = analyzer._calculate_name_quality_score(name)
        print(f"  '{name}':")
        print(f"    Человеческое имя: {is_human}")
        print(f"    Скор качества: {quality_score:.3f}")
        print()
    
    # Тестируем фильтрацию
    filtered = analyzer._filter_names_by_quality(test_names)
    print(f"После фильтрации осталось {len(filtered)} из {len(test_names)} имен:")
    for name in filtered:
        print(f"  ✅ '{name}'")
    
    excluded = [name for name in test_names if name not in filtered]
    if excluded:
        print(f"\nИсключены {len(excluded)} имен:")
        for name in excluded:
            print(f"  ❌ '{name}'")

if __name__ == "__main__":
    print("ДЕТАЛЬНАЯ ДИАГНОСТИКА АНАЛИЗА СТРАНИЦЫ hsm.susu.ru")
    print("=" * 80)
    
    detailed_analysis_test()
    test_name_filtering()
    
    print("\n" + "=" * 80)
    print("ЗАКЛЮЧЕНИЕ:")
    print("Проверьте результаты выше, чтобы понять, на каком этапе")
    print("происходит потеря данных или фильтрация результатов.")
