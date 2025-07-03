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
                logger.info("DEBUG: ВЫЗЫВАЕМ _enhance_with_webpage_data")
                self._enhance_with_webpage_data(processed_data, webpage_analysis)
                logger.info("DEBUG: _enhance_with_webpage_data completed successfully")
            except Exception as e:
                logger.error(f"DEBUG: Error in _enhance_with_webpage_data: {e}")
                import traceback
                logger.error(f"DEBUG: Traceback: {traceback.format_exc()}")
            
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
        
        # Извлекаем научные идентификаторы из базовых результатов поиска
        logger.info("Извлекаем научные идентификаторы из результатов поиска")
        basic_scientific_ids = self._extract_scientific_identifiers(results['search_results'])
        
        # Обновляем scientific_identifiers базовыми данными только если они не были найдены в веб-анализе
        if (basic_scientific_ids.get('orcid_id') != "Не найден" and 
            processed_data['scientific_identifiers']['orcid_id'] == "Не найден"):
            processed_data['scientific_identifiers']['orcid_id'] = basic_scientific_ids['orcid_id']
            logger.info(f"Найден ORCID в базовых результатах: {basic_scientific_ids['orcid_id']}")
        
        if (basic_scientific_ids.get('spin_code') != "Не найден" and 
            processed_data['scientific_identifiers']['spin_code'] == "Не найден"):
            processed_data['scientific_identifiers']['spin_code'] = basic_scientific_ids['spin_code']
            logger.info(f"Найден SPIN-код в базовых результатах: {basic_scientific_ids['spin_code']}")
        
        # Добавляем альтернативные email из базовых результатов
        if basic_scientific_ids.get('alternative_emails'):
            processed_data['scientific_identifiers']['alternative_emails'] = basic_scientific_ids['alternative_emails']
        
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
        
        processed = {
            'basic_info': self._extract_basic_info(email, search_results),
            'professional_info': self._extract_professional_info(search_results),
            'scientific_identifiers': self._extract_scientific_identifiers(search_results),
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
    
    def _extract_scientific_identifiers(self, results: List[Dict]) -> Dict[str, Any]:
        """Извлечение научных идентификаторов"""
        logger.info("Извлекаем научные идентификаторы из результатов поиска")
        logger.info(f"Обрабатываем {len(results)} результатов поиска")
        
        # Улучшенные паттерны для поиска ORCID
        orcid_patterns = [
            r'https?://orcid\.org/(?:0000-)?([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9X]{4})',  # Полный URL ORCID
            r'orcid\.org/(?:0000-)?([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9X]{4})',  # Без протокола
            r'ORCID:?\s*(?:0000-)?([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9X]{4})',  # С префиксом ORCID
            r'(0000-[0-9]{4}-[0-9]{4}-[0-9X]{4})',  # Стандартный формат
            r'([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9X]{4})'  # Простой формат
        ]
        
        spin_pattern = r'(?:SPIN|spin)[-:\s]*([0-9]{4}-[0-9]{4})'
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        
        orcid_ids = set()
        spin_codes = set()
        alternative_emails = set()
        
        for result in results:
            text = f"{result.get('title', '')} {result.get('snippet', '')} {result.get('link', '')}"
            
            # Поиск ORCID с улучшенными паттернами
            for pattern in orcid_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Нормализуем ORCID к стандартному формату
                    if not match.startswith('0000-'):
                        orcid_id = f'0000-{match}'
                    else:
                        orcid_id = match
                    
                    # Проверяем корректность формата ORCID
                    if re.match(r'^0000-[0-9]{4}-[0-9]{4}-[0-9X]{4}$', orcid_id):
                        orcid_ids.add(orcid_id)
                        logger.info(f"Найден ORCID в базовых результатах поиска: {orcid_id}")
            
            # Поиск SPIN-кода
            spin_matches = re.findall(spin_pattern, text, re.IGNORECASE)
            for match in spin_matches:
                spin_codes.add(match)
                logger.info(f"Найден SPIN-код в базовых результатах поиска: {match}")
            
            # Поиск дополнительных email адресов
            email_matches = re.findall(email_pattern, text)
            for email in email_matches:
                alternative_emails.add(email.lower())
        
        # Конвертируем множества в списки и сортируем
        orcid_list = sorted(list(orcid_ids))
        spin_list = sorted(list(spin_codes))
        email_list = sorted(list(alternative_emails))[:5]  # Ограничиваем количество
        
        return {
            'orcid_id': orcid_list[0] if orcid_list else "Не найден",
            'spin_code': spin_list[0] if spin_list else "Не найден",
            'email_for_correspondence': "Не определен",
            'alternative_emails': email_list
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
        import re
        
        logger.info(f"INFO: -------- НАЧАЛО _enhance_with_webpage_data --------")
        logger.info(f"INFO: webpage_analysis keys: {list(webpage_analysis.keys()) if webpage_analysis else 'None'}")
        
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
        logger.info(f"INFO: Обработка контактной информации. Найден блок contact_information: {bool(webpage_contacts)}")
        logger.info(f"INFO: Ключи в contact_information: {list(webpage_contacts.keys()) if webpage_contacts else 'None'}")
        
        if webpage_contacts.get('emails'):
            # Добавляем найденные email адреса как альтернативные контакты
            processed['scientific_identifiers']['alternative_emails'] = webpage_contacts['emails'][:3]
        
        # Извлекаем ORCID из найденных websites с улучшенным алгоритмом выбора
        logger.info(f"INFO: Проверяем наличие websites в contact_information: {bool(webpage_contacts.get('websites'))}")
        if webpage_contacts.get('websites'):
            websites_list = webpage_contacts['websites']
            logger.info(f"INFO: Проверяем websites в webpage_contacts: {len(websites_list)} ссылок найдено")
            
            # Логируем первые 10 сайтов для анализа
            logger.info(f"INFO: Первые 10 websites для анализа:")
            for i, site in enumerate(websites_list[:10]):
                logger.info(f"INFO:   {i+1}. {site}")
            
            # Проверяем, есть ли ORCID в принципе в данных
            orcid_count = sum(1 for site in websites_list if 'orcid' in str(site).lower())
            logger.info(f"INFO: Количество ссылок содержащих 'orcid': {orcid_count}")
            
            try:
                # Собираем все валидные ORCID с дополнительной информацией
                logger.info(f"INFO: Вызываем _extract_all_orcids_from_websites...")
                found_orcids = self._extract_all_orcids_from_websites(webpage_contacts['websites'])
                logger.info(f"INFO: _extract_all_orcids_from_websites вернула: {len(found_orcids) if found_orcids else 0} ORCID")
                
                if found_orcids:
                    # Выбираем наиболее релевантный ORCID
                    logger.info(f"INFO: Вызываем _select_best_orcid...")
                    best_orcid = self._select_best_orcid(found_orcids)
                    logger.info(f"INFO: Выбран лучший ORCID из {len(found_orcids)} найденных: {best_orcid['orcid']} (рейтинг: {best_orcid['relevance_score']:.2f})")
                    processed['scientific_identifiers']['orcid_id'] = best_orcid['orcid']
                    
                    # Добавляем дополнительную информацию для отладки
                    logger.info(f"INFO: Все найденные ORCID: {[o['orcid'] for o in found_orcids]}")
                else:
                    logger.info(f"INFO: Валидные ORCID не найдены в веб-анализе")
            except Exception as e:
                logger.error(f"ERROR: Ошибка при обработке ORCID из веб-анализа: {str(e)}")
                import traceback
                logger.error(f"ERROR: Traceback: {traceback.format_exc()}")
        
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
    
    def _extract_all_orcids_from_websites(self, websites: List[str]) -> List[Dict[str, Any]]:
        """Извлекает все валидные ORCID из списка websites с дополнительной информацией для ранжирования"""
        import re
        
        orcid_pattern = re.compile(r'https?://orcid\.org/(?:0000-)?([0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9X]{4})', re.IGNORECASE)
        found_orcids = []
        
        for index, website in enumerate(websites):
            if isinstance(website, str):
                # Убираем возможные запятые в конце URL
                clean_url = website.rstrip(',')
                logger.info(f"INFO: Проверяем website #{index+1}: {clean_url}")
                
                match = orcid_pattern.search(clean_url)
                if match:
                    orcid_id = f"0000-{match.group(1)}" if not match.group(1).startswith('0000-') else match.group(1)
                    
                    # Проверяем корректность формата ORCID
                    if re.match(r'^0000-[0-9]{4}-[0-9]{4}-[0-9X]{4}$', orcid_id):
                        logger.info(f"INFO: Найден валидный ORCID: {orcid_id} на позиции {index+1}")
                        
                        orcid_info = {
                            'orcid': orcid_id,
                            'url': clean_url,
                            'position_in_list': index,  # Позиция в исходном списке
                            'relevance_score': 0.0,     # Будет рассчитан в _calculate_orcid_relevance
                            'is_complete_url': clean_url.startswith('http'),
                            'domain_context': self._extract_domain_context(clean_url)
                        }
                        
                        # Рассчитываем релевантность
                        orcid_info['relevance_score'] = self._calculate_orcid_relevance(orcid_info, index, websites)
                        
                        found_orcids.append(orcid_info)
                    else:
                        logger.info(f"INFO: Найден ORCID с некорректным форматом: {orcid_id}")
                else:
                    logger.info(f"INFO: ORCID не найден в URL: {clean_url}")
        
        logger.info(f"INFO: Всего найдено {len(found_orcids)} валидных ORCID")
        return found_orcids
    
    def _calculate_orcid_relevance(self, orcid_info: Dict[str, Any], position: int, all_websites: List[str]) -> float:
        """Рассчитывает релевантность ORCID на основе различных факторов"""
        
        relevance_score = 0.0
        
        # 1. Бонус за позицию в списке (чем раньше, тем лучше)
        position_bonus = max(0, (len(all_websites) - position) / len(all_websites)) * 0.3
        relevance_score += position_bonus
        
        # 2. Бонус за полный URL (vs неполный)
        if orcid_info['is_complete_url']:
            relevance_score += 0.2
        
        # 3. Бонус за контекст домена
        domain_context = orcid_info['domain_context']
        if domain_context:
            # Приоритет академическим и исследовательским доменам
            academic_domains = ['edu', 'ac.', 'university', 'institute', 'research', 'ncbi', 'pubmed', 'scholar']
            if any(domain in domain_context.lower() for domain in academic_domains):
                relevance_score += 0.3
            
            # Бонус за известные научные платформы
            scientific_platforms = ['orcid.org', 'researchgate', 'academia.edu', 'ieee', 'springer', 'elsevier']
            if any(platform in domain_context.lower() for platform in scientific_platforms):
                relevance_score += 0.2
        
        # 4. Проверка на специальные паттерны в URL
        url = orcid_info['url'].lower()
        
        # Бонус за прямые ссылки на ORCID профиль
        if 'orcid.org' in url and 'record' not in url:
            relevance_score += 0.1
        
        # Штраф за подозрительные URL (например, с множественными параметрами)
        if url.count('?') > 1 or url.count('&') > 3:
            relevance_score -= 0.1
        
        # 5. Проверка на дубликаты и вариации
        # (Это можно расширить для детекции дубликатов ORCID)
        
        logger.info(f"INFO: ORCID {orcid_info['orcid']} - релевантность: {relevance_score:.3f} (позиция: {position_bonus:.3f}, URL: {0.2 if orcid_info['is_complete_url'] else 0:.3f}, домен: {domain_context})")
        
        return max(0.0, min(1.0, relevance_score))  # Ограничиваем диапазон [0, 1]
    
    def _extract_domain_context(self, url: str) -> str:
        """Извлекает контекст домена из URL для анализа релевантности"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            # Fallback для простого извлечения домена
            if '://' in url:
                domain_part = url.split('://')[1]
                return domain_part.split('/')[0]
            return url
    
    def _select_best_orcid(self, found_orcids: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Выбирает наиболее релевантный ORCID из найденных"""
        
        if not found_orcids:
            return None
        
        # Сортируем по релевантности (убывание)
        sorted_orcids = sorted(found_orcids, key=lambda x: x['relevance_score'], reverse=True)
        
        best_orcid = sorted_orcids[0]
        
        logger.info(f"INFO: Анализ всех найденных ORCID:")
        for i, orcid in enumerate(sorted_orcids):
            logger.info(f"INFO:   {i+1}. {orcid['orcid']} - релевантность: {orcid['relevance_score']:.3f} (позиция в списке: {orcid['position_in_list']+1})")
        
        # Дополнительные проверки для финального выбора
        if len(sorted_orcids) > 1:
            # Если разница в релевантности минимальна, выбираем по дополнительным критериям
            score_diff = sorted_orcids[0]['relevance_score'] - sorted_orcids[1]['relevance_score']
            
            if score_diff < 0.1:  # Если разница меньше 10%
                logger.info(f"INFO: Минимальная разница в релевантности ({score_diff:.3f}), применяем дополнительные критерии")
                
                # Приоритет URL с 'orcid.org' в домене
                orcid_domain_candidates = [o for o in sorted_orcids[:3] if 'orcid.org' in o['url'].lower()]
                if orcid_domain_candidates:
                    best_orcid = orcid_domain_candidates[0]
                    logger.info(f"INFO: Выбран ORCID с официального домена: {best_orcid['orcid']}")
        
        return best_orcid

