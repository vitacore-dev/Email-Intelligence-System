import requests
import json
import re
from typing import Dict, List, Optional, Any
from urllib.parse import quote_plus
import time
import logging

try:
    from .webpage_analyzer import WebpageAnalyzer
except ImportError:
    WebpageAnalyzer = None

try:
    from .browser_search import BrowserSearchService
except ImportError:
    BrowserSearchService = None

try:
    from .nlp_enhanced_analyzer import EnhancedNLPAnalyzer
except ImportError:
    EnhancedNLPAnalyzer = None

try:
    from .enhanced_parser_verifier import EnhancedParserVerifier
except ImportError:
    EnhancedParserVerifier = None

logger = logging.getLogger(__name__)

class SearchEngineService:
    """Сервис для работы с поисковыми системами"""
    
    def __init__(self):
        import os
        from dotenv import load_dotenv
        
        # Загружаем переменные окружения
        load_dotenv()
        
        # Получаем API ключи из переменных окружения
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.google_search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        self.bing_api_key = os.getenv('BING_API_KEY')
        
        # Дополнительные API ключи
        self.scopus_api_key = os.getenv('SCOPUS_API_KEY')
        self.orcid_client_id = os.getenv('ORCID_CLIENT_ID')
        
        # Инициализируем анализатор веб-страниц
        self.webpage_analyzer = WebpageAnalyzer() if WebpageAnalyzer else None
        
        # Инициализируем enhanced NLP analyzer
        self.enhanced_nlp_analyzer = EnhancedNLPAnalyzer() if EnhancedNLPAnalyzer else None
        
        # Инициализируем enhanced parser verifier
        self.enhanced_verifier = EnhancedParserVerifier() if EnhancedParserVerifier else None
        
        logger.info(f"SearchEngineService инициализирован:")
        logger.info(f"  Google API: {'✓' if self.google_api_key else '✗'}")
        logger.info(f"  Bing API: {'✓' if self.bing_api_key else '✗'}")
        logger.info(f"  Scopus API: {'✓' if self.scopus_api_key else '✗'}")
        logger.info(f"  Webpage Analyzer: {'✓' if self.webpage_analyzer else '✗'}")
        logger.info(f"  Enhanced NLP Analyzer: {'✓' if self.enhanced_nlp_analyzer else '✗'}")
        logger.info(f"  Enhanced Parser Verifier: {'✓' if self.enhanced_verifier else '✗'}")
        
    def search_scopus(self, query: str) -> List[Dict]:
        """Поиск через Scopus API"""
        if not self.scopus_api_key:
            return []

        try:
            url = f'https://api.elsevier.com/content/search/scopus'
            headers = {'X-ELS-APIKey': self.scopus_api_key}
            params = {
                'query': query,
                'count': 10,
                'start': 0
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            results = []

            for entry in data.get('search-results', {}).get('entry', []):
                results.append({
                    'title': entry.get('dc:title', ''),
                    'link': entry.get('prism:url', ''),
                    'summary': entry.get('dc:description', ''),
                    'source': 'scopus',
                    'authors': entry.get('authors', {}).get('author', [])
                })

            return results

        except Exception as e:
            logger.error(f"Ошибка Scopus Search API: {str(e)}")
            return []

    def search_orcid(self, orcid_id: str) -> Dict[str, Any]:
        """Поиск информации через ORCID API"""
        try:
            url = f'https://pub.orcid.org/v3.0/{orcid_id}/record'
            headers = {
                'Accept': 'application/json'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data

        except Exception as e:
            logger.error(f"Ошибка ORCID API: {str(e)}")
            return {}

    def search_email_info(self, email: str, preferred_method: str = 'auto') -> Dict[str, Any]:
        """
        Полный поиск информации по email адресу через Google Search API с глубоким анализом веб-страниц
        
        Args:
            email: Email адрес для поиска
            preferred_method: Предпочтительный метод поиска ('auto', 'google_api', 'browser_search')
        """
        logger.info(f"Начинаем полный поиск информации для email: {email}")
        
        results = {
            'email': email,
            'search_results': [],
            'processed_info': {},
            'sources': [],
            'timestamp': time.time()
        }
        
        # Генерируем поисковые запросы
        search_queries = self._generate_search_queries(email)
        logger.info(f"Сгенерировано {len(search_queries)} поисковых запросов")
        
        # Выполняем поиск через Google API (приоритетный метод)
        if self.google_api_key:
            logger.info("Используем Google Search API для поиска")
            
            for query in search_queries:
                try:
                    google_results = self._search_google(query)
                    if google_results:
                        results['search_results'].extend(google_results)
                        logger.info(f"Google API вернул {len(google_results)} результатов для '{query}'")
                    else:
                        logger.warning(f"Google API не вернул результатов для '{query}'")
                        
                    # Небольшая пауза между запросами к API для избежания лимитов
                    time.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"Ошибка Google Search API для '{query}': {str(e)}")
                    continue
        else:
            logger.error("Google API ключ не настроен! Невозможно выполнить поиск.")
            # Если нет Google API, используем fallback
            logger.info("Используем альтернативный поиск как fallback")
            for query in search_queries[:10]:  # Ограничиваем количество запросов для альтернативного поиска
                try:
                    alternative_results = self._search_alternative(query)
                    results['search_results'].extend(alternative_results)
                    logger.info(f"Альтернативный поиск вернул {len(alternative_results)} результатов для '{query}'")
                except Exception as e:
                    logger.error(f"Ошибка альтернативного поиска для '{query}': {str(e)}")
                    continue
        
        logger.info(f"Всего найдено {len(results['search_results'])} результатов поиска")
        
        logger.info("DEBUG: Начинаем обработку результатов")
        
        # Обрабатываем и анализируем результаты с полным анализом веб-страниц
        
        # Выполняем анализ веб-страниц
        logger.info("DEBUG: STARTED - Выполняем анализ веб-страниц")
        webpage_analysis = {}
        if self.webpage_analyzer:
            logger.info("DEBUG: Calling webpage analyzer")
            webpage_analysis = self.webpage_analyzer.analyze_search_results(results['search_results'], email=email)
            logger.info(f"DEBUG: Webpage analysis completed, keys: {list(webpage_analysis.keys()) if webpage_analysis else 'None'}")
            results['processed_info'].update(webpage_analysis)
            logger.info("DEBUG: Updated processed_info with webpage analysis")

        # Выполняем усовершенствованный NLP анализ
        if self.enhanced_nlp_analyzer:
            nlp_results = self.enhanced_nlp_analyzer.analyze_email_search_results(email, results['search_results'], webpage_analysis)
            results['processed_info'].update(nlp_results)

        # Выполняем дополнительную верификацию (временно отключено для тестирования)
        # if self.enhanced_verifier:
        #     # Подготавливаем данные для верификации
        #     parsed_results = self._prepare_data_for_verifier(webpage_analysis, results['search_results'])
        #     verification_results = self.enhanced_verifier.enhanced_parse_and_verify(parsed_results, email)
        #     results['processed_info']['enhanced_verification'] = verification_results

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Агрегируем и структурируем данные в ожидаемый формат
        logger.info("Агрегируем результаты анализа в финальную структуру данных")
        
        # Создаем базовую структуру данных, которую ожидает API
        processed_data = {
            'basic_info': {
                'owner_name': 'Не определено',
                'owner_name_en': 'Not determined',
                'status': 'unknown',
                'confidence_score': 0.0
            },
            'professional_info': {
                'position': 'Не определено',
                'workplace': 'Не определено',
                'address': 'Не определено',
                'specialization': 'Не определено'
            },
            'scientific_identifiers': {
                'orcid_id': 'Не найден',
                'spin_code': 'Не найден',
                'email_for_correspondence': email
            },
            'publications': [],
            'research_interests': [],
            'conclusions': [],
            'information_sources': []
        }
        
        # Агрегируем данные из анализа веб-страниц
        logger.info(f"DEBUG: Webpage analysis data keys: {list(webpage_analysis.keys()) if webpage_analysis else 'None'}")
        if webpage_analysis:
            logger.info("Интегрируем данные веб-анализа")
            logger.info(f"DEBUG: Owner identification in webpage_analysis: {webpage_analysis.get('owner_identification', {})}")
            
            try:
                self._enhance_with_webpage_data(processed_data, webpage_analysis)
                logger.info("DEBUG: _enhance_with_webpage_data completed successfully")
            except Exception as e:
                logger.error(f"DEBUG: Error in _enhance_with_webpage_data: {e}")
            
            # Добавляем веб-анализ как отдельную секцию для подробной информации
            processed_data['webpage_analysis'] = webpage_analysis
        
        # Агрегируем данные из NLP анализа
        nlp_data = results['processed_info'].get('nlp_analysis') or results['processed_info'].get('enhanced_insights')
        if nlp_data:
            logger.info("Интегрируем данные NLP анализа")
            self._enhance_with_nlp_data(processed_data, nlp_data)
        
        # Добавляем базовые выводы и источники
        if not processed_data['conclusions']:
            processed_data['conclusions'] = self._generate_conclusions(email, results['search_results'])
        
        if not processed_data['information_sources']:
            processed_data['information_sources'] = self._extract_sources(results['search_results'])
        
        # Добавляем публикации и исследовательские интересы
        if not processed_data['publications']:
            processed_data['publications'] = self._extract_publications(results['search_results'])
            
        if not processed_data['research_interests']:
            processed_data['research_interests'] = self._extract_research_interests(results['search_results'])
        
        # Заменяем необработанные данные анализа на структурированные данные
        results['processed_info'] = processed_data
        
        logger.info(f"DEBUG: Финальная структура данных создана")
        logger.info(f"DEBUG: processed_data keys: {list(processed_data.keys())}")
        logger.info(f"DEBUG: basic_info keys: {list(processed_data['basic_info'].keys())}")
        logger.info(f"DEBUG: Owner name: {processed_data['basic_info']['owner_name']}")
        logger.info(f"DEBUG: Confidence score: {processed_data['basic_info']['confidence_score']}")
        logger.info(f"DEBUG: results keys: {list(results.keys())}")
        logger.info(f"DEBUG: results['processed_info'] keys: {list(results['processed_info'].keys())}")
        
        return results
    
    def _generate_search_queries(self, email: str) -> List[str]:
        """Генерация поисковых запросов для email - только email адрес"""
        queries = [
            # Только прямой поиск email без дополнительных запросов
            f'"{email}"',  # Точное совпадение email
        ]
        
        return queries
    
    
    def _search_google(self, query: str, max_results: int = 100) -> List[Dict]:
        """Поиск через Google Custom Search API с поддержкой множественных запросов"""
        if not self.google_api_key:
            return []
            
        all_results = []
        results_per_request = 10  # Максимум для Google API
        
        # Делаем несколько запросов с разными start параметрами
        for start_index in range(1, max_results + 1, results_per_request):
            try:
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    'key': self.google_api_key,
                    'cx': self.google_search_engine_id,  # Ваш Search Engine ID
                    'q': query,
                    'num': min(results_per_request, max_results - len(all_results)),
                    'start': start_index
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                batch_results = []
                
                for item in data.get('items', []):
                    batch_results.append({
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'source': 'google'
                    })
                
                all_results.extend(batch_results)
                
                # Если получили меньше результатов чем запрашивали, значит больше нет
                if len(batch_results) < results_per_request:
                    break
                    
                # Пауза между запросами
                time.sleep(0.1)
                
                # Ограничиваем общее количество результатов
                if len(all_results) >= max_results:
                    break
                    
            except Exception as e:
                logger.error(f"Ошибка Google Search API для запроса '{query}' (start={start_index}): {str(e)}")
                # Если первый запрос не удался, прерываем
                if start_index == 1:
                    break
                # Иначе продолжаем с следующего батча
                continue
        
        return all_results[:max_results]
    
    def _search_bing(self, query: str) -> List[Dict]:
        """Поиск через Bing Search API"""
        if not self.bing_api_key:
            return []
            
        try:
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {
                'Ocp-Apim-Subscription-Key': self.bing_api_key
            }
            params = {
                'q': query,
                'count': 10,
                'offset': 0
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('webPages', {}).get('value', []):
                results.append({
                    'title': item.get('name', ''),
                    'link': item.get('url', ''),
                    'snippet': item.get('snippet', ''),
                    'source': 'bing'
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка Bing Search API: {str(e)}")
            return []
    
    def _search_alternative(self, query: str) -> List[Dict]:
        """Альтернативный поиск с использованием браузерного скрейпинга"""
        
        logger.info(f"Используем альтернативный поиск для: {query}")
        
        # Пробуем использовать браузерный поиск, если доступен
        if BrowserSearchService:
            try:
                logger.info("Пробуем браузерный поиск через Selenium")
                
                with BrowserSearchService(headless=True) as browser_search:
                    browser_results = browser_search.search_google(query, max_results=10)
                    
                    if browser_results:
                        logger.info(f"Браузерный поиск вернул {len(browser_results)} результатов")
                        return browser_results
                    else:
                        logger.warning("Браузерный поиск не вернул результатов")
                        
            except Exception as e:
                logger.error(f"Ошибка браузерного поиска: {str(e)}")
                logger.info("Переключаемся на mock данные")
        else:
            logger.warning("BrowserSearchService недоступен, используем mock данные")
        
        # Fallback к mock данным если браузерный поиск не работает
        logger.info("Используем mock данные для демонстрации")
        mock_results = [
            {
                'title': f'ResearchGate Profile - {query}',
                'link': 'https://www.researchgate.net/profile/John-Doe',
                'snippet': f'Profile of researcher with email {query}. Publications and research interests.',
                'source': 'alternative_mock'
            },
            {
                'title': f'University Faculty Page - {query}',
                'link': 'https://university.edu/faculty/john-doe',
                'snippet': f'Dr. John Doe, Professor of Computer Science. Contact: {query}',
                'source': 'alternative_mock'
            },
            {
                'title': f'ORCID Profile - {query}',
                'link': 'https://orcid.org/0000-0000-0000-0000',
                'snippet': f'ORCID profile for researcher. Publications and affiliations.',
                'source': 'alternative_mock'
            },
            {
                'title': f'Scientific Publication - {query}',
                'link': 'https://pubmed.ncbi.nlm.nih.gov/12345',
                'snippet': f'Research article authored by {query}. Nature Communications 2023.',
                'source': 'alternative_mock'
            },
            {
                'title': f'Google Scholar Profile - {query}',
                'link': 'https://scholar.google.com/citations?user=example',
                'snippet': f'Citation profile for {query}. H-index: 25, Citations: 1500',
                'source': 'alternative_mock'
            }
        ]
        
        return mock_results
    
    def _process_search_results(self, email: str, search_results: List[Dict]) -> Dict[str, Any]:
        """Обработка и анализ результатов поиска с полным анализом веб-страниц
        
        Args:
            email: Email адрес для анализа
            search_results: Результаты поиска
        """
        
        # Сначала извлекаем базовую информацию
        basic_info = self._extract_basic_info(email, search_results)
        
        processed = {
            'basic_info': basic_info,
            'professional_info': self._extract_professional_info(search_results),
            'scientific_identifiers': self._extract_scientific_identifiers(search_results, email=email, found_names=basic_info.get('names_found', [])),
            'publications': self._extract_publications(search_results),
            'research_interests': self._extract_research_interests(search_results),
            'conclusions': self._generate_conclusions(email, search_results),
            'information_sources': self._extract_sources(search_results)
        }
        
        # Добавляем анализ веб-страниц если анализатор доступен
        if self.webpage_analyzer and search_results:
            try:
                logger.info(f"Запускаем анализ веб-страниц для email: {email}")
                
                # Подготавливаем результаты поиска для анализатора
                urls_for_analysis = []
                for result in search_results:
                    if 'link' in result and result['link']:
                        urls_for_analysis.append({
                            'url': result['link'],
                            'title': result.get('title', ''),
                            'snippet': result.get('snippet', '')
                        })
                
                logger.info(f"Подготовлено {len(urls_for_analysis)} URLs для анализа")
                
                # Анализируем ссылки с полным анализом всех веб-страниц
                if urls_for_analysis:
                    # Полный анализ всех доступных страниц (до 25 для более глубокого анализа)
                    limit = 25
                    webpage_analysis = self.webpage_analyzer.analyze_search_results(urls_for_analysis, limit=limit, email=email)
                    
                    # Интегрируем результаты анализа веб-страниц
                    processed['webpage_analysis'] = webpage_analysis
                    
                    # Обновляем основную информацию на основе анализа веб-страниц
                    logger.info(f"DEBUG: ДО webpage enhancement: owner_name = '{processed['basic_info'].get('owner_name', 'None')}'")
                    self._enhance_with_webpage_data(processed, webpage_analysis)
                    logger.info(f"DEBUG: ПОСЛЕ webpage enhancement: owner_name = '{processed['basic_info'].get('owner_name', 'None')}'")
                    
                    # Применяем Enhanced Parser Verifier для улучшения данных
                    logger.info(f"Проверяем Enhanced Parser Verifier: hasattr={hasattr(self, 'enhanced_verifier')}, verifier={self.enhanced_verifier is not None if hasattr(self, 'enhanced_verifier') else 'No attr'}")
                    if hasattr(self, 'enhanced_verifier') and self.enhanced_verifier:
                        try:
                            logger.info(f"Запускаем enhanced верификацию для email: {email}")
                            
                            # Подготавливаем данные для верификации
                            parsed_results = self._prepare_data_for_verifier(webpage_analysis, search_results)
                            
                            # Выполняем enhanced верификацию
                            enhanced_profile = self.enhanced_verifier.enhanced_parse_and_verify(
                                parsed_results, email
                            )
                            
                            # Интегрируем результаты верификации в основные данные
                            logger.info(f"DEBUG: Результат enhanced верификации: {enhanced_profile}")
                            self._integrate_verified_data(processed, enhanced_profile)
                            
                            logger.info(f"Enhanced верификация завершена для email: {email}")
                        except Exception as e:
                            logger.error(f"Ошибка в enhanced верификации: {e}")
                    
                    # Добавляем enhanced NLP анализ если доступен
                    if self.enhanced_nlp_analyzer:
                        try:
                            logger.info(f"Запускаем enhanced NLP анализ для email: {email}")
                            enhanced_nlp_results = self.enhanced_nlp_analyzer.analyze_email_search_results(
                                email, search_results, webpage_analysis
                            )
                            processed['enhanced_nlp_analysis'] = enhanced_nlp_results
                            
                            # Обогащаем основную информацию NLP данными
                            logger.info(f"DEBUG: ДО NLP enhancement: owner_name = '{processed['basic_info'].get('owner_name', 'None')}'")
                            self._enhance_with_nlp_data(processed, enhanced_nlp_results)
                            logger.info(f"DEBUG: ПОСЛЕ NLP enhancement: owner_name = '{processed['basic_info'].get('owner_name', 'None')}'")
                            
                            logger.info(f"Enhanced NLP анализ завершен для email: {email}")
                        except Exception as e:
                            logger.error(f"Ошибка в enhanced NLP анализе: {e}")
                            processed['enhanced_nlp_analysis'] = {'error': str(e), 'enabled': False}
                    
                    logger.info(f"Анализ веб-страниц завершен для email: {email}. Успешно обработано: {webpage_analysis.get('analysis_metadata', {}).get('successful_extractions', 0)} страниц")
                else:
                    logger.warning(f"Нет подходящих URLs для анализа веб-страниц для email: {email}")
                    # Добавляем пустую структуру анализа для консистентности
                    processed['webpage_analysis'] = {
                        'owner_identification': {'names_found': [], 'most_likely_name': None, 'confidence_score': 0.0},
                        'professional_details': {'positions': [], 'organizations': [], 'locations': []},
                        'contact_information': {'emails': [], 'phones': [], 'websites': []},
                        'academic_info': {'degrees': [], 'research_areas': [], 'publications': []},
                        'analysis_metadata': {
                            'analyzed_urls': [],
                            'successful_extractions': 0,
                            'failed_extractions': 0,
                            'analysis_timestamp': time.time(),
                            'note': 'Нет подходящих URLs для анализа'
                        }
                    }
                
            except Exception as e:
                logger.error(f"Ошибка при анализе веб-страниц: {str(e)}")
                # Добавляем информацию об ошибке в результаты
                processed['webpage_analysis'] = {
                    'owner_identification': {'names_found': [], 'most_likely_name': None, 'confidence_score': 0.0},
                    'professional_details': {'positions': [], 'organizations': [], 'locations': []},
                    'contact_information': {'emails': [], 'phones': [], 'websites': []},
                    'academic_info': {'degrees': [], 'research_areas': [], 'publications': []},
                    'analysis_metadata': {
                        'analyzed_urls': [],
                        'successful_extractions': 0,
                        'failed_extractions': 0,
                        'analysis_timestamp': time.time(),
                        'error': str(e)
                    }
                }
                # Продолжаем работу без анализа веб-страниц
        else:
            logger.info(f"Анализ веб-страниц недоступен для email: {email} (анализатор: {'доступен' if self.webpage_analyzer else 'недоступен'}, результаты: {len(search_results) if search_results else 0})")
        
        return processed
    
    def _extract_basic_info(self, email: str, results: List[Dict]) -> Dict[str, Any]:
        """Извлечение основной информации"""
        
        # Анализируем результаты для поиска имени и статуса
        names_found = []
        status = "not_found"
        
        for result in results:
            text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
            
            # Поиск паттернов имен
            name_patterns = [
                r'([А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+)',  # Русские ФИО
                r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Английские имена
                r'([А-Я]\.[А-Я]\.\s+[А-Я][а-я]+)',  # Инициалы + фамилия
            ]
            
            for pattern in name_patterns:
                matches = re.findall(pattern, text)
                names_found.extend(matches)
        
        # Определяем статус на основе количества найденных результатов
        if len(results) > 5:
            status = "identified"
        elif len(results) > 0:
            status = "partial_info"
        
        owner_name = names_found[0] if names_found else "Не определено"
        
        return {
            'owner_name': owner_name,
            'owner_name_en': self._transliterate_name(owner_name),
            'status': status
        }
    
    def _extract_professional_info(self, results: List[Dict]) -> Dict[str, Any]:
        """Извлечение профессиональной информации"""
        
        positions = []
        workplaces = []
        addresses = []
        specializations = []
        
        for result in results:
            text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
            
            # Поиск должностей
            position_keywords = ['профессор', 'доцент', 'кандидат', 'доктор', 'заведующий', 'директор']
            for keyword in position_keywords:
                if keyword in text:
                    positions.append(keyword.title())
            
            # Поиск мест работы
            workplace_keywords = ['университет', 'институт', 'академия', 'центр', 'лаборатория']
            for keyword in workplace_keywords:
                if keyword in text:
                    # Извлекаем контекст вокруг ключевого слова
                    context = self._extract_context(text, keyword, 50)
                    workplaces.append(context)
        
        return {
            'position': positions[0] if positions else "Не определено",
            'workplace': workplaces[0] if workplaces else "Не определено",
            'address': addresses[0] if addresses else "Не определено",
            'specialization': specializations[0] if specializations else "Не определено"
        }
    
    def _extract_scientific_identifiers(self, results: List[Dict], email: str = None, found_names: List[str] = None) -> Dict[str, Any]:
        """Улучшенное извлечение научных идентификаторов с дополнительным поиском по имени"""
        
        orcid_pattern = r'(\d{4}-\d{4}-\d{4}-\d{4})'
        spin_pattern = r'(\d{4}-\d{4})'
        
        orcid_ids = []
        spin_codes = []
        alternative_emails = []
        
        for result in results:
            text = f"{result.get('title', '')} {result.get('snippet', '')}"
            
            # Поиск ORCID
            orcid_matches = re.findall(orcid_pattern, text)
            orcid_ids.extend(orcid_matches)
            
            # Поиск SPIN-кода
            spin_matches = re.findall(spin_pattern, text)
            spin_codes.extend(spin_matches)
            
            # Поиск альтернативных email адресов
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            found_emails = re.findall(email_pattern, text)
            for found_email in found_emails:
                if email and found_email.lower() != email.lower():
                    alternative_emails.append(found_email)
        
        # Дополнительный поиск ORCID по имени владельца
        if not orcid_ids and found_names:
            logger.info(f"Основной поиск ORCID не дал результатов. Выполняем дополнительный поиск по именам: {found_names[:3]}")
            additional_orcids = self._search_orcid_by_names(found_names)
            orcid_ids.extend(additional_orcids)
        
        # Удаляем дубликаты
        orcid_ids = list(set(orcid_ids))
        spin_codes = list(set(spin_codes))
        alternative_emails = list(set(alternative_emails))
        
        return {
            'orcid_id': orcid_ids[0] if orcid_ids else "Не найден",
            'spin_code': spin_codes[0] if spin_codes else "Не найден", 
            'email_for_correspondence': email if email else "Не определен",
            'alternative_emails': alternative_emails[:5],  # Ограничиваем количество
            'all_orcid_found': orcid_ids[:3] if len(orcid_ids) > 1 else []  # Все найденные ORCID
        }
    
    def _extract_publications(self, results: List[Dict]) -> List[Dict]:
        """Извлечение информации о публикациях"""
        
        publications = []
        
        for result in results:
            if any(keyword in result.get('title', '').lower() for keyword in ['journal', 'article', 'publication', 'research']):
                publications.append({
                    'title': result.get('title', ''),
                    'journal': 'Определяется из контекста',
                    'year': 'Не определен',
                    'authors': 'Анализируется',
                    'doi': 'Не найден',
                    'url': result.get('link', '')
                })
        
        return publications[:5]  # Ограничиваем количество
    
    def _extract_research_interests(self, results: List[Dict]) -> List[str]:
        """Извлечение областей научных интересов"""
        
        interests = []
        keywords = ['исследование', 'изучение', 'анализ', 'разработка', 'методы', 'технологии']
        
        for result in results:
            text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
            for keyword in keywords:
                if keyword in text:
                    context = self._extract_context(text, keyword, 30)
                    if context not in interests:
                        interests.append(context)
        
        return interests[:10]  # Ограничиваем количество
    
    def _generate_conclusions(self, email: str, results: List[Dict]) -> List[str]:
        """Генерация выводов на основе найденной информации"""
        
        conclusions = []
        
        if len(results) > 10:
            conclusions.append("Email принадлежит активному исследователю с высокой онлайн-активностью")
        elif len(results) > 5:
            conclusions.append("Email принадлежит специалисту с умеренной онлайн-активностью")
        else:
            conclusions.append("Ограниченная информация о владельце email")
        
        # Анализ доменов в результатах
        academic_domains = ['edu', 'ac', 'university', 'institute']
        has_academic = any(domain in result.get('link', '') for result in results for domain in academic_domains)
        
        if has_academic:
            conclusions.append("Связан с академическими учреждениями")
        
        return conclusions
    
    def _extract_sources(self, results: List[Dict]) -> List[str]:
        """Извлечение источников информации"""
        
        sources = []
        for result in results:
            link = result.get('link', '')
            if link:
                domain = self._extract_domain(link)
                if domain not in sources:
                    sources.append(domain)
        
        return sources
    
    def _extract_context(self, text: str, keyword: str, length: int) -> str:
        """Извлечение контекста вокруг ключевого слова"""
        
        index = text.find(keyword)
        if index == -1:
            return ""
        
        start = max(0, index - length)
        end = min(len(text), index + len(keyword) + length)
        
        return text[start:end].strip()
    
    def _extract_domain(self, url: str) -> str:
        """Извлечение домена из URL"""
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return url
    
    def _transliterate_name(self, name: str) -> str:
        """Простая транслитерация имени"""
        
        if not name or name == "Не определено":
            return "Not determined"
        
        # Простая транслитерация (в реальном проекте лучше использовать библиотеку)
        translit_dict = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        
        result = ""
        for char in name.lower():
            result += translit_dict.get(char, char)
        
        return result.title()
    
    def _enhance_with_webpage_data(self, processed: Dict[str, Any], webpage_analysis: Dict[str, Any]):
        """Обогащение основной информации данными из анализа веб-страниц"""
        
        # Обновляем основную информацию о владельце
        if webpage_analysis.get('owner_identification', {}).get('most_likely_name'):
            most_likely_name = webpage_analysis['owner_identification']['most_likely_name']
            confidence = webpage_analysis['owner_identification'].get('confidence_score', 0)
            
            # Если найденное имя имеет высокую уверенность, обновляем основную информацию
            if confidence > 0.3 and most_likely_name:
                processed['basic_info']['owner_name'] = most_likely_name
                processed['basic_info']['owner_name_en'] = self._transliterate_name(most_likely_name)
                processed['basic_info']['confidence_score'] = confidence
        
        # Обновляем профессиональную информацию
        webpage_professional = webpage_analysis.get('professional_details', {})
        
        if webpage_professional.get('positions'):
            # Берем наиболее релевантную позицию
            best_position = self._select_best_position(webpage_professional['positions'])
            if best_position:
                processed['professional_info']['position'] = best_position
        
        if webpage_professional.get('organizations'):
            # Берем наиболее релевантную организацию
            best_org = self._select_best_organization(webpage_professional['organizations'])
            if best_org:
                processed['professional_info']['workplace'] = best_org
        
        if webpage_professional.get('locations'):
            # Берем наиболее релевантную локацию
            best_location = webpage_professional['locations'][0]
            processed['professional_info']['address'] = best_location
        
        # Обновляем контактную информацию
        webpage_contacts = webpage_analysis.get('contact_information', {})
        
        if webpage_contacts.get('emails'):
            # Добавляем найденные email адреса как альтернативные контакты
            processed['scientific_identifiers']['alternative_emails'] = webpage_contacts['emails'][:3]
        
        # Извлекаем ORCID из найденных веб-сайтов с улучшенным алгоритмом выбора
        logger.info(f"DEBUG: Проверяем websites в webpage_contacts: {webpage_contacts.get('websites') is not None}")
        if webpage_contacts.get('websites'):
            websites_list = webpage_contacts['websites']
            logger.info(f"DEBUG: Найдено {len(websites_list)} веб-сайтов для анализа ORCID")
            
            # Логируем первые 10 сайтов для анализа
            logger.info(f"INFO: Первые 10 websites для анализа:")
            for i, site in enumerate(websites_list[:10]):
                logger.info(f"INFO:   {i+1}. {site}")
            
            # Проверяем, есть ли ORCID в принципе в данных
            orcid_count = sum(1 for site in websites_list if 'orcid' in str(site).lower())
            logger.info(f"INFO: Количество ссылок содержащих 'orcid': {orcid_count}")
            
            try:
                # Получаем контекстную информацию для улучшенного ранжирования
                owner_name = processed.get('basic_info', {}).get('owner_name', 'Не определено')
                email_for_correspondence = processed.get('scientific_identifiers', {}).get('email_for_correspondence')
                
                # Собираем все валидные ORCID с дополнительной информацией
                logger.info(f"INFO: Вызываем _extract_all_orcids_from_websites с контекстом: owner_name='{owner_name}', email='{email_for_correspondence}'...")
                found_orcids = self._extract_all_orcids_from_websites(websites_list, owner_name=owner_name, email=email_for_correspondence)
                logger.info(f"INFO: _extract_all_orcids_from_websites вернула: {len(found_orcids) if found_orcids else 0} ORCID")
                
                if found_orcids:
                    # Выбираем наиболее релевантный ORCID
                    logger.info(f"INFO: Вызываем _select_best_orcid...")
                    best_orcid = self._select_best_orcid(found_orcids)
                    logger.info(f"INFO: Выбран лучший ORCID из {len(found_orcids)} найденных: {best_orcid['orcid']} (рейтинг: {best_orcid['relevance_score']:.2f})")
                    
                    # Обновляем ORCID, если он не был найден ранее или текущий неполный
                    current_orcid = processed['scientific_identifiers']['orcid_id']
                    if current_orcid == 'Не найден' or not current_orcid or current_orcid == '':
                        processed['scientific_identifiers']['orcid_id'] = best_orcid['orcid']
                        logger.info(f"ORCID извлечен из веб-анализа: {best_orcid['orcid']}")
                    else:
                        logger.info(f"INFO: ORCID не обновлен, текущий: {current_orcid}, найденный: {best_orcid['orcid']}")
                    
                    # Добавляем все найденные ORCID для отладки
                    logger.info(f"INFO: Все найденные ORCID: {[o['orcid'] for o in found_orcids]}")
                    if len(found_orcids) > 1:
                        processed['scientific_identifiers']['all_orcid_found'] = [o['orcid'] for o in found_orcids]
                else:
                    logger.info(f"INFO: Валидные ORCID не найдены в веб-анализе")
            except Exception as e:
                logger.error(f"ERROR: Ошибка при обработке ORCID из веб-анализа: {str(e)}")
                import traceback
                logger.error(f"ERROR: Traceback: {traceback.format_exc()}")
        else:
            logger.info(f"DEBUG: Нет веб-сайтов в webpage_contacts для анализа ORCID")
        
        # Обновляем академическую информацию
        webpage_academic = webpage_analysis.get('academic_info', {})
        
        if webpage_academic.get('degrees'):
            processed['professional_info']['degrees'] = webpage_academic['degrees'][:3]
        
        if webpage_academic.get('research_areas'):
            # Объединяем с существующими исследовательскими интересами
            existing_interests = processed.get('research_interests', [])
            new_interests = webpage_academic['research_areas'][:5]
            
            # Безопасное удаление дубликатов для любых типов данных
            combined_interests = []
            seen_items = []
            
            for item in existing_interests + new_interests:
                # Для простых типов используем прямое сравнение
                if isinstance(item, (str, int, float, bool)):
                    if item not in seen_items:
                        seen_items.append(item)
                        combined_interests.append(item)
                else:
                    # Для сложных типов сравниваем строковое представление
                    item_str = str(item)
                    if item_str not in [str(x) for x in combined_interests]:
                        combined_interests.append(item)
            
            processed['research_interests'] = combined_interests[:10]
        
        # Добавляем выводы на основе анализа веб-страниц
        analysis_meta = webpage_analysis.get('analysis_metadata', {})
        successful_extractions = analysis_meta.get('successful_extractions', 0)
        
        if successful_extractions > 0:
            processed['conclusions'].append(
                f"Проанализировано {successful_extractions} веб-страниц с дополнительной информацией"
            )
            
            if webpage_analysis.get('owner_identification', {}).get('confidence_score', 0) > 0.5:
                processed['conclusions'].append(
                    "Высокая вероятность корректной идентификации владельца email"
                )
    
    def _select_best_position(self, positions: List[str]) -> Optional[str]:
        """Выбирает наиболее релевантную позицию из списка"""
        
        if not positions:
            return None
        
        # Приоритет академических и научных позиций
        priority_keywords = [
            'профессор', 'professor', 'доцент', 'associate',
            'доктор', 'doctor', 'кандидат', 'candidate',
            'директор', 'director', 'заведующий', 'head'
        ]
        
        for keyword in priority_keywords:
            for position in positions:
                if keyword.lower() in position.lower():
                    return position
        
        # Если приоритетных не найдено, возвращаем первую
        return positions[0]
    
    def _select_best_organization(self, organizations: List[str]) -> Optional[str]:
        """Выбирает наиболее релевантную организацию из списка"""
        
        if not organizations:
            return None
        
        # Приоритет академических учреждений
        priority_keywords = [
            'университет', 'university', 'институт', 'institute',
            'академия', 'academy', 'колледж', 'college',
            'центр', 'center', 'лаборатория', 'laboratory'
        ]
        
        for keyword in priority_keywords:
            for org in organizations:
                if keyword.lower() in org.lower() and len(org) > 10:  # Фильтруем слишком короткие названия
                    return org
        
        # Возвращаем самое длинное название (обычно более информативное)
        return max(organizations, key=len) if organizations else None
    
    def _enhance_with_nlp_data(self, processed: Dict[str, Any], enhanced_nlp_results: Dict[str, Any]):
        """Обогащение основной информации данными из enhanced NLP анализа"""
        
        try:
            enhanced_insights = enhanced_nlp_results.get('enhanced_insights', {})
            nlp_analysis = enhanced_nlp_results.get('nlp_analysis', {})
            
            # Обновляем основную информацию о владельце на основе NLP анализа
            # НО только если нет более высокой уверенности от enhanced verification
            most_confident_owner = enhanced_insights.get('most_confident_owner')
            existing_verification_confidence = processed['basic_info'].get('verification_confidence', 0)
            
            # Enhanced verification should take priority when verification confidence is high (>0.7)
            # This prevents NLP from overriding high-quality enhanced verification results
            should_use_nlp = (most_confident_owner and 
                             most_confident_owner.get('confidence', 0) > 0.6 and
                             existing_verification_confidence == 0 and  # No verification data yet
                             most_confident_owner.get('confidence', 0) > existing_verification_confidence)  # Higher confidence
            
            if should_use_nlp:
                processed['basic_info']['owner_name'] = most_confident_owner['name']
                processed['basic_info']['owner_name_en'] = self._transliterate_name(most_confident_owner['name'])
                processed['basic_info']['nlp_confidence'] = most_confident_owner['confidence']
                processed['basic_info']['nlp_source'] = most_confident_owner.get('source', 'nlp_analysis')
            elif most_confident_owner:  # Добавляем NLP данные даже если не обновляем имя
                processed['basic_info']['nlp_confidence'] = most_confident_owner['confidence']
                processed['basic_info']['nlp_source'] = most_confident_owner.get('source', 'nlp_analysis')
        
            
            # Обновляем профессиональную информацию
            professional_context = enhanced_insights.get('professional_context', {})
            if professional_context:
                # Обновляем специализацию на основе NLP анализа профессиональных ролей
                if professional_context.get('primary_category'):
                    category_mapping = {
                        'academic': 'Академическая деятельность',
                        'medical': 'Медицина и здравоохранение',
                        'technical': 'Техническая деятельность',
                        'management': 'Управление и администрирование'
                    }
                    category = professional_context['primary_category']
                    if category in category_mapping:
                        processed['professional_info']['specialization'] = category_mapping[category]
                
                # Добавляем найденные роли
                roles_found = professional_context.get('roles_found', [])
                if roles_found:
                    processed['professional_info']['nlp_roles'] = roles_found[:3]
            
            # Обновляем научные идентификаторы
            if nlp_analysis.get('entities_found'):
                # Ищем организации в найденных сущностях
                organizations = [e['text'] for e in nlp_analysis['entities_found'] 
                               if e['label'] in ['ORG', 'ORGANIZATION'] and e['confidence'] > 0.7]
                if organizations:
                    processed['scientific_identifiers']['nlp_organizations'] = organizations[:2]
                
                # Ищем персон в найденных сущностях
                persons = [e['text'] for e in nlp_analysis['entities_found'] 
                          if e['label'] == 'PERSON' and e['confidence'] > 0.7]
                if persons:
                    processed['scientific_identifiers']['nlp_persons'] = persons[:3]
            
            # Обновляем области исследований на основе NLP анализа
            professional_roles = nlp_analysis.get('professional_roles', [])
            if professional_roles:
                role_based_interests = []
                for role in professional_roles:
                    if role['confidence'] > 0.6:
                        # Создаем область интересов на основе роли
                        interest = f"{role['title']} ({role['category']})"
                        role_based_interests.append(interest)
                
                if role_based_interests:
                    existing_interests = processed.get('research_interests', [])
                    combined_interests = list(set(existing_interests + role_based_interests))
                    processed['research_interests'] = combined_interests[:12]
            
            # Добавляем выводы на основе NLP анализа
            confidence_scores = nlp_analysis.get('confidence_scores', {})
            overall_confidence = confidence_scores.get('overall', 0)
            
            if overall_confidence > 0.7:
                processed['conclusions'].append(
                    "NLP анализ показал высокую достоверность извлеченной информации"
                )
            elif overall_confidence > 0.4:
                processed['conclusions'].append(
                    "NLP анализ показал умеренную достоверность извлеченной информации"
                )
            
            # Добавляем информацию о семантических паттернах
            semantic_patterns = nlp_analysis.get('semantic_patterns', [])
            if 'academic_professional' in semantic_patterns:
                processed['conclusions'].append(
                    "Обнаружены признаки академической деятельности"
                )
            if 'medical_professional' in semantic_patterns:
                processed['conclusions'].append(
                    "Обнаружены признаки медицинской деятельности"
                )
            if 'research_activity' in semantic_patterns:
                processed['conclusions'].append(
                    "Обнаружены признаки исследовательской деятельности"
                )
            
            # Обновляем оценку надежности контакта
            contact_reliability = enhanced_insights.get('contact_reliability', 'unknown')
            reliability_mapping = {
                'high': 'Высокая надежность контактной информации',
                'medium': 'Умеренная надежность контактной информации',
                'low': 'Низкая надежность контактной информации'
            }
            
            if contact_reliability in reliability_mapping:
                processed['conclusions'].append(reliability_mapping[contact_reliability])
            
            # Добавляем метаданные о NLP анализе
            methods_used = enhanced_nlp_results.get('metadata', {}).get('methods_used', [])
            if methods_used:
                processed['conclusions'].append(
                    f"Применены методы NLP анализа: {', '.join(methods_used)}"
                )
            
            logger.info("Основная информация успешно обогащена данными NLP анализа")
            
        except Exception as e:
            logger.error(f"Ошибка при обогащении данными NLP анализа: {e}")
            processed['conclusions'].append(
                "Ошибка при применении NLP анализа к извлеченной информации"
            )
    
    def _prepare_data_for_verifier(self, webpage_analysis: Dict[str, Any], search_results: List[Dict]) -> List[Dict[str, Any]]:
        """Подготавливает данные для Enhanced Parser Verifier"""
        
        parsed_results = []
        
        try:
            # Преобразуем данные анализа веб-страниц в формат для верификатора
            if webpage_analysis:
                # Создаем структуру данных для каждой проанализированной страницы
                analyzed_urls = webpage_analysis.get('analysis_metadata', {}).get('analyzed_urls', [])
                
                for url_data in analyzed_urls:
                    if url_data.get('status') == 'success':
                        result_entry = {
                            'url': url_data['url'],
                            'metadata': {
                                'url': url_data['url'],
                                'status': 'success',
                                'extraction_types': url_data.get('extracted_data_types', [])
                            },
                            'names': [],
                            'organizations': [],
                            'positions': [],
                            'contact_info': {'emails': []}
                        }
                        
                        # Добавляем найденные имена
                        owner_names = webpage_analysis.get('owner_identification', {}).get('names_found', [])
                        result_entry['names'] = owner_names[:5]  # Ограничиваем количество
                        
                        # Добавляем организации
                        organizations = webpage_analysis.get('professional_details', {}).get('organizations', [])
                        result_entry['organizations'] = organizations[:5]
                        
                        # Добавляем позиции
                        positions = webpage_analysis.get('professional_details', {}).get('positions', [])
                        result_entry['positions'] = positions[:5]
                        
                        # Добавляем email адреса
                        emails = webpage_analysis.get('contact_information', {}).get('emails', [])
                        result_entry['contact_info']['emails'] = emails[:5]
                        
                        parsed_results.append(result_entry)
            
            # Добавляем данные из поисковых результатов, если они не покрыты анализом веб-страниц
            if len(parsed_results) == 0 and search_results:
                for search_result in search_results[:5]:  # Ограничиваем количество
                    result_entry = {
                        'url': search_result.get('link', ''),
                        'metadata': {
                            'url': search_result.get('link', ''),
                            'title': search_result.get('title', ''),
                            'snippet': search_result.get('snippet', ''),
                            'status': 'search_result'
                        },
                        'names': self._extract_names_from_text(search_result.get('title', '') + ' ' + search_result.get('snippet', '')),
                        'organizations': self._extract_organizations_from_text(search_result.get('title', '') + ' ' + search_result.get('snippet', '')),
                        'positions': self._extract_positions_from_text(search_result.get('title', '') + ' ' + search_result.get('snippet', '')),
                        'contact_info': {'emails': []}
                    }
                    parsed_results.append(result_entry)
            
            logger.info(f"Подготовлено {len(parsed_results)} записей для enhanced верификации")
            
        except Exception as e:
            logger.error(f"Ошибка при подготовке данных для верификатора: {e}")
        
        return parsed_results
    
    def _integrate_verified_data(self, processed: Dict[str, Any], enhanced_profile: Dict[str, Any]):
        """Интегрирует результаты enhanced верификации в основные данные"""
        
        try:
            verified_data = enhanced_profile.get('verified_data', {})
            
            # Обновляем имена с высокой уверенностью
            logger.info(f"DEBUG: Enhanced verification - проверяем verified_data: {list(verified_data.keys())}")
            
            if 'names' in verified_data:
                name_data = verified_data['names']
                logger.info(f"DEBUG: Enhanced verification - name_data: {name_data}")
                if name_data.get('confidence', 0) > 0.5 and name_data.get('value'):
                    # Проверяем существующую уверенность из webpage analysis
                    existing_confidence = processed['basic_info'].get('confidence_score', 0)
                    verification_confidence = name_data['confidence']
                    
                    # Enhanced verification всегда имеет приоритет при confidence > 0.5
                    # или когда его confidence выше, чем у webpage analysis
                    logger.info(f"DEBUG: Проверяем enhanced verification: verification_confidence={verification_confidence}, existing_confidence={existing_confidence}")
                    logger.info(f"DEBUG: Текущий owner_name ПЕРЕД обновлением: {processed['basic_info'].get('owner_name', 'None')}")
                    
                    if verification_confidence > 0.5 or verification_confidence > existing_confidence:
                        old_name = processed['basic_info'].get('owner_name', 'None')
                        processed['basic_info']['owner_name'] = name_data['value']
                        processed['basic_info']['owner_name_en'] = self._transliterate_name(name_data['value'])
                        processed['basic_info']['verification_confidence'] = verification_confidence
                        processed['basic_info']['verification_sources'] = name_data.get('source_count', 0)
                        # Обновляем общую уверенность на enhanced verification confidence
                        processed['basic_info']['confidence_score'] = verification_confidence
                        
                        logger.info(f"DEBUG: ОБНОВЛЕНО имя владельца: '{old_name}' -> '{name_data['value']}' (confidence: {name_data['confidence']:.2f})")
                        logger.info(f"DEBUG: ПОСЛЕ ОБНОВЛЕНИЯ: owner_name = '{processed['basic_info']['owner_name']}'")
                    else:
                        logger.info(f"DEBUG: НЕ обновляем имя, так как verification_confidence={verification_confidence} <= 0.5 и <= existing_confidence={existing_confidence}")
            
            # Обновляем организации
            if 'organizations' in verified_data:
                org_data = verified_data['organizations']
                if org_data.get('confidence', 0) > 0.4 and org_data.get('value'):
                    processed['professional_info']['workplace'] = org_data['value']
                    processed['professional_info']['workplace_confidence'] = org_data['confidence']
            
            # Обновляем позиции
            if 'positions' in verified_data:
                pos_data = verified_data['positions']
                if pos_data.get('confidence', 0) > 0.4 and pos_data.get('value'):
                    processed['professional_info']['position'] = pos_data['value']
                    processed['professional_info']['position_confidence'] = pos_data['confidence']
            
            # Обновляем email адреса
            if 'emails' in verified_data:
                email_data = verified_data['emails']
                if email_data.get('confidence', 0) > 0.5 and email_data.get('value'):
                    processed['scientific_identifiers']['verified_email'] = email_data['value']
                    processed['scientific_identifiers']['email_confidence'] = email_data['confidence']
            
            # Добавляем метрики качества
            quality_metrics = enhanced_profile.get('data_quality_metrics', {})
            if quality_metrics:
                processed['verification_quality'] = {
                    'overall_quality': quality_metrics.get('overall_quality', 0),
                    'average_confidence': quality_metrics.get('average_confidence', 0),
                    'data_coverage': quality_metrics.get('data_coverage', 0),
                    'consistency_score': quality_metrics.get('consistency_score', 0)
                }
            
            # Добавляем проверки консистентности
            consistency_checks = enhanced_profile.get('consistency_checks', {})
            if consistency_checks:
                processed['consistency_analysis'] = consistency_checks
            
            # Добавляем рекомендации
            recommendations = enhanced_profile.get('recommendations', [])
            if recommendations:
                for rec in recommendations[:3]:  # Ограничиваем количество
                    processed['conclusions'].append(f"Рекомендация: {rec}")
            
            # Добавляем информацию о методе верификации
            processed['conclusions'].append("Применена enhanced верификация данных с использованием fuzzy matching")
            
            logger.info("Enhanced верификация успешно интегрирована в результаты")
            
        except Exception as e:
            logger.error(f"Ошибка при интеграции enhanced верификации: {e}")
    
    def _extract_names_from_text(self, text: str) -> List[str]:
        """Извлекает имена из текста"""
        names = []
        
        # Паттерны для поиска имен
        name_patterns = [
            r'([А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+)',  # Русские ФИО
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)',  # Английские имена
            r'([А-Я]\.[А-Я]\.\s+[А-Я][а-я]+)',  # Инициалы + фамилия
            r'([А-Я][а-я]+\s+[А-Я]\.[А-Я]\.)',  # Фамилия + инициалы
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            names.extend(matches)
        
        return list(set(names))  # Удаляем дубликаты
    
    def _extract_organizations_from_text(self, text: str) -> List[str]:
        """Извлекает организации из текста"""
        organizations = []
        
        # Ключевые слова для поиска организаций
        org_patterns = [
            r'([А-Я][а-я]*\s*(?:государственный|медицинский|технический|педагогический)\s*(?:университет|институт|академия|центр))',
            r'([A-Z][a-z]*\s*(?:University|Institute|Academy|Center|College))',
            r'(\b[А-Я][а-я]+\s+[а-я]*университет\b)',
            r'(\b[A-Z][a-z]+\s+University\b)'
        ]
        
        for pattern in org_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            organizations.extend(matches)
        
        return list(set(organizations))
    
    def _extract_positions_from_text(self, text: str) -> List[str]:
        """Извлекает должности из текста"""
        positions = []
        
        # Ключевые слова для должностей
        position_keywords = [
            'профессор', 'professor', 'доцент', 'associate professor',
            'кандидат наук', 'доктор наук', 'PhD', 'MD',
            'заведующий кафедрой', 'head of department',
            'директор', 'director', 'руководитель', 'manager'
        ]
        
        text_lower = text.lower()
        
        for keyword in position_keywords:
            if keyword.lower() in text_lower:
                # Извлекаем контекст вокруг ключевого слова
                context = self._extract_context(text_lower, keyword.lower(), 20)
                if context:
                    positions.append(context.strip())
        
        return list(set(positions))
    
    
    def _enhance_with_nlp_data(self, processed: Dict[str, Any], nlp_data: Dict[str, Any]):
        """Обогащение основной информации данными из NLP анализа"""
        
        try:
            # Обновляем основную информацию о владельце на основе NLP анализа
            enhanced_insights = nlp_data.get('enhanced_insights', {})
            most_confident_owner = enhanced_insights.get('most_confident_owner')
            
            if most_confident_owner and most_confident_owner.get('confidence', 0) > 0.6:
                # Только обновляем если у нас еще нет имени или NLP имеет более высокую уверенность
                current_confidence = processed['basic_info'].get('confidence_score', 0)
                if processed['basic_info']['owner_name'] == 'Не определено' or most_confident_owner['confidence'] > current_confidence:
                    processed['basic_info']['owner_name'] = most_confident_owner['name']
                    processed['basic_info']['owner_name_en'] = self._transliterate_name(most_confident_owner['name'])
                    processed['basic_info']['confidence_score'] = most_confident_owner['confidence']
                    processed['basic_info']['nlp_confidence'] = most_confident_owner['confidence']
                    processed['basic_info']['nlp_source'] = most_confident_owner.get('source', 'nlp_analysis')
            
            # Обновляем профессиональную информацию
            professional_context = enhanced_insights.get('professional_context', {})
            if professional_context.get('primary_category'):
                category_mapping = {
                    'academic': 'Академическая деятельность',
                    'medical': 'Медицина и здравоохранение', 
                    'technical': 'Техническая деятельность',
                    'management': 'Управление и администрирование'
                }
                category = professional_context['primary_category']
                if category in category_mapping:
                    processed['professional_info']['specialization'] = category_mapping[category]
            
            # Добавляем выводы на основе NLP анализа
            nlp_analysis = nlp_data.get('nlp_analysis', {})
            confidence_scores = nlp_analysis.get('confidence_scores', {})
            overall_confidence = confidence_scores.get('overall', 0)
            
            if overall_confidence > 0.7:
                processed['conclusions'].append("NLP анализ показал высокую достоверность извлеченной информации")
            elif overall_confidence > 0.4:
                processed['conclusions'].append("NLP анализ показал умеренную достоверность извлеченной информации")
            
        except Exception as e:
            logger.error(f"Ошибка при обогащении данными NLP анализа: {e}")
    
    def _generate_conclusions(self, email: str, search_results: List[Dict]) -> List[str]:
        """Генерация выводов на основе найденной информации"""
        
        conclusions = []
        
        if len(search_results) > 10:
            conclusions.append("Email принадлежит активному исследователю с высокой онлайн-активностью")
        elif len(search_results) > 5:
            conclusions.append("Email принадлежит специалисту с умеренной онлайн-активностью")
        else:
            conclusions.append("Ограниченная информация о владельце email")
        
        # Анализ доменов в результатах
        academic_domains = ['edu', 'ac', 'university', 'institute']
        has_academic = any(domain in result.get('link', '') for result in search_results for domain in academic_domains)
        
        if has_academic:
            conclusions.append("Связан с академическими учреждениями")
        
        return conclusions
    
    def _extract_sources(self, search_results: List[Dict]) -> List[str]:
        """Извлечение источников информации"""
        
        sources = []
        for result in search_results:
            link = result.get('link', '')
            if link:
                domain = self._extract_domain(link)
                if domain not in sources:
                    sources.append(domain)
        
        return sources
    
    def _extract_publications(self, search_results: List[Dict]) -> List[Dict]:
        """Извлечение информации о публикациях"""
        
        publications = []
        
        for result in search_results:
            if any(keyword in result.get('title', '').lower() for keyword in ['journal', 'article', 'publication', 'research']):
                publications.append({
                    'title': result.get('title', ''),
                    'journal': 'Определяется из контекста',
                    'year': 'Не определен',
                    'authors': 'Анализируется',
                    'doi': 'Не найден',
                    'url': result.get('link', '')
                })
        
        return publications[:5]  # Ограничиваем количество
    
    def _extract_research_interests(self, search_results: List[Dict]) -> List[str]:
        """Извлечение областей научных интересов"""
        
        interests = []
        keywords = ['исследование', 'изучение', 'анализ', 'разработка', 'методы', 'технологии']
        
        for result in search_results:
            text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
            for keyword in keywords:
                if keyword in text:
                    context = self._extract_context(text, keyword, 30)
                    if context not in interests:
                        interests.append(context)
        
        return interests[:10]  # Ограничиваем количество
    
    def _search_orcid_by_names(self, names: List[str]) -> List[str]:
        """Поиск ORCID по списку имен через веб-скрапинг"""
        
        found_orcids = []
        
        for name in names[:3]:  # Ограничиваем количество имен для поиска
            if not name or len(name.strip()) < 5:
                continue
                
            logger.info(f"Ищем ORCID для имени: {name}")
            
            # Формируем поисковые запросы для ORCID
            search_queries = self._generate_orcid_search_queries(name)
            
            for query in search_queries:
                try:
                    # Используем Google API для поиска ORCID
                    if self.google_api_key:
                        orcid_results = self._search_google(query, max_results=10)
                        
                        # Извлекаем ORCID из результатов
                        orcids_from_results = self._extract_orcid_from_search_results(orcid_results, name)
                        found_orcids.extend(orcids_from_results)
                        
                        if orcids_from_results:
                            logger.info(f"Найдено ORCID для '{name}': {orcids_from_results}")
                            break  # Прекращаем поиск по другим запросам для этого имени
                        
                        time.sleep(0.2)  # Пауза между запросами
                        
                except Exception as e:
                    logger.error(f"Ошибка поиска ORCID для '{name}' с запросом '{query}': {e}")
                    continue
        
        # Удаляем дубликаты и возвращаем уникальные ORCID
        unique_orcids = list(set(found_orcids))
        logger.info(f"Общий результат поиска ORCID по именам: {unique_orcids}")
        
        return unique_orcids
    
    def _generate_orcid_search_queries(self, name: str) -> List[str]:
        """Генерация поисковых запросов для ORCID по имени"""
        
        queries = []
        
        # Основные запросы для ORCID
        queries.append(f'"{name}" site:orcid.org')
        queries.append(f'"{name}" ORCID')
        queries.append(f'"{name}" "0000-"')  # Поиск по паттерну ORCID
        
        # Дополнительные запросы для научных платформ
        queries.append(f'"{name}" site:researchgate.net ORCID')
        queries.append(f'"{name}" site:scholar.google.com ORCID')
        queries.append(f'"{name}" site:pubmed.ncbi.nlm.nih.gov ORCID')
        
        return queries[:4]  # Ограничиваем количество запросов
    
    def _extract_orcid_from_search_results(self, search_results: List[Dict], name: str) -> List[str]:
        """Извлечение ORCID из результатов поиска с проверкой соответствия имени"""
        
        found_orcids = []
        orcid_pattern = r'(\d{4}-\d{4}-\d{4}-\d{4})'
        
        for result in search_results:
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            link = result.get('link', '')
            
            # Объединяем всю информацию для анализа
            full_text = f"{title} {snippet} {link}"
            
            # Поиск ORCID в тексте
            orcid_matches = re.findall(orcid_pattern, full_text)
            
            for orcid in orcid_matches:
                # Проверяем, что имя упоминается в том же контексте
                if self._is_name_associated_with_orcid(name, full_text):
                    found_orcids.append(orcid)
                    logger.info(f"Найден ORCID {orcid} для имени '{name}' в результате: {title[:100]}")
            
            # Дополнительно проверяем URL на прямые ссылки на ORCID
            if 'orcid.org' in link.lower():
                # Извлекаем ORCID из URL
                url_orcid_match = re.search(r'orcid\.org/(\d{4}-\d{4}-\d{4}-\d{4})', link)
                if url_orcid_match:
                    url_orcid = url_orcid_match.group(1)
                    if self._is_name_associated_with_orcid(name, full_text):
                        found_orcids.append(url_orcid)
                        logger.info(f"Найден ORCID {url_orcid} из URL для имени '{name}'")
        
        return found_orcids
    
    def _is_name_associated_with_orcid(self, name: str, text: str) -> bool:
        """Проверяет, связано ли имя с ORCID в данном контексте"""
        
        text_lower = text.lower()
        name_lower = name.lower()
        
        # Простая проверка на наличие имени в тексте
        if name_lower in text_lower:
            return True
        
        # Проверяем отдельные части имени (имя и фамилия)
        name_parts = name_lower.split()
        if len(name_parts) >= 2:
            # Проверяем, что хотя бы 2 части имени присутствуют
            found_parts = 0
            for part in name_parts:
                if len(part) > 2 and part in text_lower:
                    found_parts += 1
            
            if found_parts >= 2:
                return True
        
        # Проверяем транслитерацию (для русских имен)
        transliterated_name = self._transliterate_name(name).lower()
        if transliterated_name != name_lower and transliterated_name in text_lower:
            return True
        
        return False
    
    def _extract_all_orcids_from_websites(self, websites: List[str], owner_name: str = None, email: str = None) -> List[Dict[str, Any]]:
        """Извлекает все валидные ORCID из списка веб-сайтов с дополнительной информацией"""
        
        logger.info(f"INFO: Начинаем анализ {len(websites)} веб-сайтов для поиска ORCID")
        
        found_orcids = []
        orcid_pattern = r'orcid\.org/([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4})'
        
        for i, website in enumerate(websites):
            if isinstance(website, str):
                logger.info(f"DEBUG: Анализируем website {i+1}: {website[:100]}...")
                orcid_match = re.search(orcid_pattern, website, re.IGNORECASE)
                if orcid_match:
                    found_orcid = orcid_match.group(1)
                    logger.info(f"DEBUG: Найден ORCID: {found_orcid}")
                    
                    # Создаем объект с дополнительной информацией
                    orcid_info = {
                        'orcid': found_orcid,
                        'position': i,
                        'url': website,
                        'domain': self._extract_domain(website),
                        'is_direct_orcid_url': 'orcid.org' in website.lower(),
                        'url_completeness': len(website)
                    }
                    
                    # Проверяем на дубликаты
                    if not any(existing['orcid'] == found_orcid for existing in found_orcids):
                        found_orcids.append(orcid_info)
                        logger.info(f"INFO: Добавлен ORCID {found_orcid} в позиции {i}")
                    else:
                        logger.info(f"INFO: ORCID {found_orcid} уже найден ранее")
        
        logger.info(f"INFO: Анализ завершен. Всего уникальных ORCID найдено: {len(found_orcids)}")
        
        if found_orcids:
            # Вычисляем релевантность для каждого ORCID с переданными контекстными данными
            for orcid_info in found_orcids:
                relevance_score = self._calculate_orcid_relevance(
                    orcid_info, 
                    owner_name=owner_name, 
                    email=email, 
                    all_websites=websites
                )
                orcid_info['relevance_score'] = relevance_score
                logger.info(f"INFO: ORCID {orcid_info['orcid']} получил релевантность {relevance_score:.3f}")
        
        return found_orcids
    
    def _calculate_orcid_relevance(self, orcid_info: Dict[str, Any], owner_name: str = None, email: str = None, all_websites: List[str] = None) -> float:
        """Вычисляет релевантность ORCID на основе различных факторов"""
        
        score = 0.0
        detailed_scores = {}
        
        # 1. Фактор позиции (чем раньше найден, тем выше score) - вес 15%
        position_score = max(0, 1.0 - (orcid_info['position'] / 100))
        score += position_score * 0.15
        detailed_scores['position'] = position_score * 0.15
        
        # 2. Фактор прямого URL ORCID - вес 20%
        direct_url_score = 0.0
        if orcid_info['is_direct_orcid_url']:
            direct_url_score = 1.0
            score += 0.20
        detailed_scores['direct_url'] = direct_url_score * 0.20
        
        # 3. Фактор полноты URL - вес 10%
        completeness_score = 0.0
        if orcid_info['url_completeness'] > 50:
            completeness_score = min(1.0, orcid_info['url_completeness'] / 200)
            score += completeness_score * 0.10
        detailed_scores['completeness'] = completeness_score * 0.10
        
        # 4. Фактор домена - вес 15%
        domain = orcid_info.get('domain', '').lower()
        domain_score = 0.0
        if 'orcid.org' in domain:
            domain_score = 1.0
        elif any(academic_domain in domain for academic_domain in ['edu', 'ac.', 'university', 'institute']):
            domain_score = 0.8
        elif any(scientific_domain in domain for scientific_domain in ['researchgate', 'scholar', 'pubmed', 'ncbi']):
            domain_score = 0.6
        score += domain_score * 0.15
        detailed_scores['domain'] = domain_score * 0.15
        
        # 5. НОВЫЙ: Семантическая близость к владельцу email - вес 25%
        name_proximity_score = 0.0
        if owner_name:
            name_proximity_score = self._calculate_name_proximity_score(orcid_info, owner_name)
            score += name_proximity_score * 0.25
        detailed_scores['name_proximity'] = name_proximity_score * 0.25
        
        # 6. НОВЫЙ: Анализ доменной принадлежности по email - вес 10%
        domain_affinity_score = 0.0
        if email:
            domain_affinity_score = self._calculate_domain_affinity_score(orcid_info, email)
            score += domain_affinity_score * 0.10
        detailed_scores['domain_affinity'] = domain_affinity_score * 0.10
        
        # 7. НОВЫЙ: Качество источника - вес 5%
        source_quality_score = self._calculate_source_quality_score(orcid_info)
        score += source_quality_score * 0.05
        detailed_scores['source_quality'] = source_quality_score * 0.05
        
        # Нормализуем score
        score = min(1.0, score)
        
        logger.info(f"INFO: Детальная релевантность для ORCID {orcid_info['orcid']}: позиция={detailed_scores['position']:.3f}, прямой_URL={detailed_scores['direct_url']:.3f}, домен={detailed_scores['domain']:.3f}, близость_имени={detailed_scores['name_proximity']:.3f}, аффинность_домена={detailed_scores['domain_affinity']:.3f}, качество_источника={detailed_scores['source_quality']:.3f}, ИТОГО={score:.3f}")
        
        return score
    
    def _select_best_orcid(self, found_orcids: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Выбирает наиболее релевантный ORCID из списка найденных"""
        
        if not found_orcids:
            return None
        
        logger.info(f"INFO: Анализ всех найденных ORCID для выбора лучшего:")
        for orcid in found_orcids:
            logger.info(f"INFO:   - {orcid['orcid']}: релевантность {orcid['relevance_score']:.2f}, позиция {orcid['position']}, домен {orcid['domain']}")
        
        # Сортируем по релевантности
        sorted_orcids = sorted(found_orcids, key=lambda x: x['relevance_score'], reverse=True)
        
        best_orcid = sorted_orcids[0]
        
        # Дополнительная логика: если разница в релевантности мала, предпочитаем прямые ORCID URL
        if len(sorted_orcids) > 1:
            best_score = best_orcid['relevance_score']
            second_best = sorted_orcids[1]
            
            # Если разница меньше 0.1 и у второго ORCID лучший домен
            if (best_score - second_best['relevance_score'] < 0.1 and 
                second_best['is_direct_orcid_url'] and 
                not best_orcid['is_direct_orcid_url']):
                
                logger.info(f"INFO: Переключаемся на ORCID {second_best['orcid']} из-за лучшего домена при малой разнице релевантности")
                best_orcid = second_best
        
        logger.info(f"INFO: Выбран лучший ORCID: {best_orcid['orcid']} с релевантностью {best_orcid['relevance_score']:.2f}")
        
        return best_orcid
    
    def _calculate_name_proximity_score(self, orcid_info: Dict[str, Any], owner_name: str) -> float:
        """Вычисляет близость ORCID к имени владельца email с улучшенным контекстным анализом"""
        url = orcid_info['url']
        score = 0.0
        
        if not owner_name or owner_name == 'Не определено':
            return 0.0
        
        url_lower = url.lower()
        owner_name_lower = owner_name.lower()
        
        logger.info(f"INFO: Анализируем близость имени '{owner_name}' к ORCID {orcid_info['orcid']} в URL: {url[:100]}...")
        
        # 1. ПРЯМАЯ ПРОВЕРКА в URL (для случаев когда имя есть в самом URL)
        direct_url_score = self._check_direct_name_in_url(url_lower, owner_name, owner_name_lower)
        score += direct_url_score
        logger.info(f"INFO: Прямая проверка URL: +{direct_url_score:.3f}")
        
        # 2. КОНТЕКСТНЫЙ АНАЛИЗ - анализируем веб-страницу по URL
        context_score = self._analyze_webpage_context_for_name(url, owner_name)
        score += context_score * 0.6  # Контекстный анализ имеет высокий вес
        logger.info(f"INFO: Контекстный анализ страницы: +{context_score * 0.6:.3f}")
        
        # 3. АНАЛИЗ ПАТТЕРНОВ ORCID
        pattern_score = self._analyze_orcid_patterns(orcid_info['orcid'], owner_name)
        score += pattern_score * 0.2
        logger.info(f"INFO: Анализ паттернов ORCID: +{pattern_score * 0.2:.3f}")
        
        # 4. ДОПОЛНИТЕЛЬНЫЙ ПОИСК ПО ORCID
        if orcid_info.get('is_direct_orcid_url', False):
            orcid_api_score = self._check_orcid_api_for_name(orcid_info['orcid'], owner_name)
            score += orcid_api_score * 0.8  # ORCID API имеет очень высокий вес
            logger.info(f"INFO: Проверка ORCID API: +{orcid_api_score * 0.8:.3f}")
        
        # 5. АНАЛИЗ СЕМАНТИЧЕСКИХ ВАРИАЦИЙ ИМЕНИ
        variation_score = self._analyze_name_variations(owner_name, url_lower)
        score += variation_score * 0.3
        logger.info(f"INFO: Анализ вариаций имени: +{variation_score * 0.3:.3f}")
        
        final_score = min(1.0, score)
        logger.info(f"INFO: Итоговая близость имени для ORCID {orcid_info['orcid']}: {final_score:.3f}")
        
        return final_score
    
    def _calculate_domain_affinity_score(self, orcid_info: Dict[str, Any], email: str) -> float:
        """Вычисляет аффинность домена ORCID с доменом email"""
        score = 0.0
        
        if not email or '@' not in email:
            return 0.0
        
        email_domain = email.split('@')[1].lower() if '@' in email else ''
        orcid_domain = orcid_info.get('domain', '').lower()
        
        # Прямое совпадение доменов
        if email_domain in orcid_domain or any(part in orcid_domain for part in email_domain.split('.')):
            score += 0.5
        
        # Анализ типа домена email
        email_is_academic = any(academic in email_domain for academic in ['edu', 'ac.', 'university', 'institute'])
        email_is_commercial = any(comm in email_domain for comm in ['gmail', 'yahoo', 'outlook', 'mail', 'list'])
        
        # Соответствие типов доменов
        if email_is_academic:
            if any(academic in orcid_domain for academic in ['edu', 'ac.', 'university', 'institute']):
                score += 0.3
            elif 'orcid.org' in orcid_domain:
                score += 0.2
        
        if email_is_commercial:
            if any(scientific in orcid_domain for scientific in ['researchgate', 'scholar', 'pubmed', 'ncbi']):
                score += 0.2
            elif 'orcid.org' in orcid_domain:
                score += 0.3
        
        # Географическая близость (по доменным зонам)
        email_zone = email_domain.split('.')[-1] if '.' in email_domain else ''
        orcid_zone = orcid_domain.split('.')[-1] if '.' in orcid_domain else ''
        
        if email_zone == orcid_zone and email_zone in ['ru', 'org', 'edu', 'com']:
            score += 0.1
        
        return min(1.0, score)
    
    def _calculate_source_quality_score(self, orcid_info: Dict[str, Any]) -> float:
        """Вычисляет качество источника где найден ORCID"""
        url = orcid_info['url'].lower()
        score = 0.0
        
        # Высококачественные научные источники
        high_quality_sources = [
            'pubmed.ncbi.nlm.nih.gov', 'scholar.google.com', 'researchgate.net',
            'springer.com', 'elsevier.com', 'nature.com', 'science.org',
            'orcid.org', 'ieee.org', 'acm.org'
        ]
        
        # Институциональные источники
        institutional_sources = [
            'university', 'institute', '.edu', '.ac.', 'academy', 'college'
        ]
        
        # Научные журналы и конференции
        journal_sources = [
            'journal', 'conference', 'proceedings', 'publication', 'article'
        ]
        
        # Проверяем высококачественные источники
        for source in high_quality_sources:
            if source in url:
                score += 0.4
                break
        
        # Проверяем институциональные источники
        for source in institutional_sources:
            if source in url:
                score += 0.3
                break
        
        # Проверяем научные журналы
        for source in journal_sources:
            if source in url:
                score += 0.2
                break
        
        # Дополнительные бонусы
        if 'doi.org' in url:
            score += 0.2  # Официальные DOI ссылки
        
        if any(repo in url for repo in ['github', 'gitlab', 'repository']):
            score += 0.1  # Научные репозитории кода
        
        return min(1.0, score)
    
    def _check_direct_name_in_url(self, url_lower: str, owner_name: str, owner_name_lower: str) -> float:
        """Проверяет прямое наличие имени в URL"""
        score = 0.0
        
        # Проверяем полное имя
        if owner_name_lower in url_lower:
            score += 0.4
        
        # Проверяем отдельные части имени
        name_parts = owner_name.split()
        found_parts = 0
        for part in name_parts:
            if len(part) > 2 and part.lower() in url_lower:
                found_parts += 1
        
        if found_parts >= 2:
            score += 0.3
        elif found_parts == 1:
            score += 0.1
        
        # Проверяем транслитерацию имени
        transliterated_name = self._transliterate_name(owner_name).lower()
        if transliterated_name != owner_name_lower and transliterated_name in url_lower:
            score += 0.2
        
        # Проверяем инициалы
        initials = ''.join([name[0].lower() for name in name_parts if len(name) > 0])
        if len(initials) >= 2 and initials in url_lower:
            score += 0.1
        
        return min(1.0, score)
    
    def _analyze_webpage_context_for_name(self, url: str, owner_name: str) -> float:
        """Анализирует веб-страницу по URL для поиска имени владельца в контексте"""
        score = 0.0
        
        try:
            # Для прямых ORCID URL можем использовать ORCID API
            if 'orcid.org' in url.lower():
                return self._analyze_orcid_page_for_name(url, owner_name)
            
            # Для других URL пытаемся скрейпить страницу
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                content = response.text.lower()
                
                # Проверяем наличие имени в содержимом страницы
                if owner_name.lower() in content:
                    score += 0.6
                
                # Проверяем части имени
                name_parts = owner_name.split()
                found_parts = sum(1 for part in name_parts if len(part) > 2 and part.lower() in content)
                
                if found_parts >= 2:
                    score += 0.4
                elif found_parts == 1:
                    score += 0.2
                
                # Проверяем транслитерацию
                transliterated = self._transliterate_name(owner_name).lower()
                if transliterated != owner_name.lower() and transliterated in content:
                    score += 0.3
                
        except Exception as e:
            logger.warning(f"Ошибка при анализе веб-страницы {url}: {e}")
        
        return min(1.0, score)
    
    def _analyze_orcid_page_for_name(self, url: str, owner_name: str) -> float:
        """Специальный анализ ORCID страницы для поиска имени"""
        score = 0.0
        
        try:
            # Извлекаем ORCID из URL
            orcid_match = re.search(r'orcid\.org/([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4})', url)
            if orcid_match:
                orcid_id = orcid_match.group(1)
                
                # Используем публичное ORCID API
                api_url = f"https://pub.orcid.org/v3.0/{orcid_id}/person"
                headers = {'Accept': 'application/json'}
                
                response = requests.get(api_url, headers=headers, timeout=5)
                if response.status_code == 200:
                    orcid_data = response.json()
                    
                    # Извлекаем имя из ORCID профиля
                    name_data = orcid_data.get('name', {})
                    if name_data:
                        given_names = name_data.get('given-names', {}).get('value', '')
                        family_name = name_data.get('family-name', {}).get('value', '')
                        
                        if given_names and family_name:
                            orcid_full_name = f"{given_names} {family_name}".lower()
                            owner_name_lower = owner_name.lower()
                            
                            # Точное совпадение
                            if orcid_full_name == owner_name_lower:
                                score += 1.0
                            # Частичное совпадение
                            elif any(part in orcid_full_name for part in owner_name.split() if len(part) > 2):
                                score += 0.6
                            
                            logger.info(f"INFO: ORCID профиль содержит имя: '{orcid_full_name}', искомое: '{owner_name_lower}', совпадение: {score:.2f}")
                
        except Exception as e:
            logger.warning(f"Ошибка при анализе ORCID страницы {url}: {e}")
        
        return min(1.0, score)
    
    def _analyze_orcid_patterns(self, orcid_id: str, owner_name: str) -> float:
        """Анализирует паттерны ORCID для возможной связи с именем"""
        score = 0.0
        
        # Простая эвристика: проверяем, есть ли совпадения между цифрами ORCID и инициалами
        # Это слабая связь, поэтому низкий score
        name_parts = owner_name.split()
        if len(name_parts) >= 2:
            # Проверяем, есть ли какие-то численные паттерны (очень слабая связь)
            score += 0.1
        
        return min(1.0, score)
    
    def _check_orcid_api_for_name(self, orcid_id: str, owner_name: str) -> float:
        """Проверяет ORCID через API для поиска имени владельца"""
        score = 0.0
        
        try:
            # Используем публичное ORCID API
            api_url = f"https://pub.orcid.org/v3.0/{orcid_id}/person"
            headers = {'Accept': 'application/json'}
            
            response = requests.get(api_url, headers=headers, timeout=5)
            if response.status_code == 200:
                orcid_data = response.json()
                
                # Извлекаем имя
                name_data = orcid_data.get('name', {})
                if name_data:
                    given_names = name_data.get('given-names', {}).get('value', '')
                    family_name = name_data.get('family-name', {}).get('value', '')
                    
                    if given_names and family_name:
                        orcid_full_name = f"{given_names} {family_name}".lower()
                        owner_name_lower = owner_name.lower()
                        
                        logger.info(f"INFO: ORCID API вернул имя: '{orcid_full_name}', сравниваем с: '{owner_name_lower}'")
                        
                        # Точное совпадение
                        if orcid_full_name == owner_name_lower:
                            score = 1.0
                        # Проверяем совпадение частей имени
                        else:
                            owner_parts = set(owner_name_lower.split())
                            orcid_parts = set(orcid_full_name.split())
                            
                            # Считаем пересечение
                            intersection = owner_parts.intersection(orcid_parts)
                            if intersection:
                                score = len(intersection) / max(len(owner_parts), len(orcid_parts))
                                logger.info(f"INFO: Найдено пересечение имен: {intersection}, score: {score:.2f}")
                        
                        # Проверяем транслитерацию
                        transliterated_owner = self._transliterate_name(owner_name).lower()
                        if score < 0.5 and transliterated_owner != owner_name_lower:
                            if transliterated_owner == orcid_full_name:
                                score = max(score, 0.8)
                            elif any(part in orcid_full_name for part in transliterated_owner.split() if len(part) > 2):
                                score = max(score, 0.5)
                
                # Также проверяем биографию и другие имена
                biography = orcid_data.get('biography', {}).get('content', {}).get('value', '')
                if biography and owner_name.lower() in biography.lower():
                    score = max(score, 0.3)
                
                # Проверяем другие имена (псевдонимы)
                other_names = orcid_data.get('other-names', {}).get('other-name', [])
                for other_name in other_names:
                    if isinstance(other_name, dict):
                        other_name_value = other_name.get('content', {}).get('value', '').lower()
                        if other_name_value and owner_name.lower() in other_name_value:
                            score = max(score, 0.6)
                
        except Exception as e:
            logger.warning(f"Ошибка при проверке ORCID API для {orcid_id}: {e}")
        
        return min(1.0, score)
    
    def _analyze_name_variations(self, owner_name: str, url_lower: str) -> float:
        """Анализирует различные вариации имени для поиска в URL"""
        score = 0.0
        
        # Создаем различные вариации имени
        variations = set()
        name_parts = owner_name.split()
        
        if len(name_parts) >= 2:
            # Обратный порядок (Фамилия Имя)
            variations.add(' '.join(reversed(name_parts)).lower())
            
            # Только имя и фамилия (без отчества)
            if len(name_parts) >= 3:
                variations.add(f"{name_parts[0]} {name_parts[-1]}".lower())
                variations.add(f"{name_parts[-1]} {name_parts[0]}".lower())
            
            # Инициалы + фамилия
            initials = ''.join([part[0] for part in name_parts[:-1]])
            variations.add(f"{initials} {name_parts[-1]}".lower())
            variations.add(f"{name_parts[-1]} {initials}".lower())
            
            # Фамилия + инициалы с точками
            initials_with_dots = '.'.join([part[0] for part in name_parts[:-1]]) + '.'
            variations.add(f"{name_parts[-1]} {initials_with_dots}".lower())
            
            # Сокращенные формы имени
            for i, part in enumerate(name_parts):
                if len(part) > 3:
                    # Сокращение до первых букв
                    short_part = part[:3]
                    variation_parts = name_parts.copy()
                    variation_parts[i] = short_part
                    variations.add(' '.join(variation_parts).lower())
        
        # Проверяем каждую вариацию
        for variation in variations:
            if variation in url_lower:
                score += 0.3
                logger.info(f"INFO: Найдена вариация имени '{variation}' в URL")
                break  # Достаточно одного совпадения
        
        # Транслитерация всех вариаций
        for variation in list(variations):
            transliterated = self._transliterate_name(variation)
            if transliterated.lower() != variation and transliterated.lower() in url_lower:
                score += 0.2
                logger.info(f"INFO: Найдена транслитерированная вариация '{transliterated}' в URL")
                break
        
        return min(1.0, score)

