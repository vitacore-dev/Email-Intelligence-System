import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import time
from typing import Dict, List, Optional, Any
import json
import PyPDF2
import pdfplumber
import io
from fuzzywuzzy import fuzz

# Временно отключаем SSL предупреждения для тестирования
import urllib3
import ssl
import warnings

# Глобально отключаем SSL предупреждения
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Отключаем SSL верификацию глобально
ssl._create_default_https_context = ssl._create_unverified_context
try:
    from langdetect import detect
    from langdetect.lang_detect_exception import LangDetectException
except ImportError:
    # Fallback если langdetect не установлен
    def detect(text):
        # Простая эвристика: если есть кириллица - русский, иначе английский
        if re.search(r'[А-Яа-я]', text):
            return 'ru'
        return 'en'
    
    class LangDetectException(Exception):
        pass

import chardet

logger = logging.getLogger(__name__)

class WebpageAnalyzer:
    """Сервис для анализа веб-страниц и извлечения структурированной информации о владельце email"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'no-cache'
        })
        
        # Принудительно отключаем SSL верификацию для всех запросов
        self.session.verify = False
        
        # Настройка SSL адаптера для обработки устаревших серверов
        self._setup_ssl_adapter()
        self.timeout = 8  # секунды (агрессивный таймаут для быстрого восстановления)
        self.max_content_size = 2 * 1024 * 1024  # 2MB максимум для HTML
        self.max_pdf_size = 30 * 1024 * 1024    # 30MB максимум для PDF
        self.max_retries = 1  # Только одна попытка для проблемных страниц
        self.retry_delay = 0.5  # Минимальная задержка между попытками
        self.connection_timeout = 5  # Таймаут подключения
        
        # Типы файлов, которые мы не будем анализировать
        self.skip_extensions = {
            '.zip', '.rar', '.7z', '.tar', '.gz',  # Архивы
            '.exe', '.msi', '.dmg', '.pkg',        # Исполняемые файлы
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',  # Изображения
            '.mp3', '.mp4', '.avi', '.mov', '.wmv',  # Медиа файлы
            '.xlsx', '.xls', '.ppt', '.pptx'       # Офисные документы (кроме PDF)
        }
    
    def _setup_ssl_adapter(self):
        """
        Настройка SSL адаптера для работы с устаревшими серверами
        Решает проблемы типа 'DH_KEY_TOO_SMALL' и другие SSL ошибки
        """
        try:
            import ssl
            from requests.adapters import HTTPAdapter
            from urllib3.util.ssl_ import create_urllib3_context
            
            class SSLContextAdapter(HTTPAdapter):
                """
                Кастомный SSL адаптер для работы с устаревшими серверами
                """
                def __init__(self, ssl_context=None, **kwargs):
                    self.ssl_context = ssl_context
                    super().__init__(**kwargs)
                
                def init_poolmanager(self, *args, **kwargs):
                    kwargs['ssl_context'] = self.ssl_context
                    return super().init_poolmanager(*args, **kwargs)
            
            # Создаем более толерантный SSL контекст
            ctx = create_urllib3_context()
            
            # Понижаем требования безопасности для совместимости с устаревшими серверами
            try:
                # Пробуем разные варианты cipher suites для максимальной совместимости
                cipher_suites = [
                    'ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS:!aECDH',
                    'ALL:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA',
                    'DEFAULT@SECLEVEL=1',
                    'DEFAULT@SECLEVEL=0'  # Самый низкий уровень безопасности
                ]
                
                for cipher_suite in cipher_suites:
                    try:
                        ctx.set_ciphers(cipher_suite)
                        logger.debug(f"Успешно установлен cipher suite: {cipher_suite}")
                        break
                    except ssl.SSLError:
                        continue
                else:
                    logger.warning("Не удалось установить ни один cipher suite")
                    
            except Exception as cipher_error:
                logger.warning(f"Ошибка настройки cipher suites: {cipher_error}")
            
            ctx.check_hostname = False  # Отключаем проверку hostname
            ctx.verify_mode = ssl.CERT_NONE  # Отключаем проверку сертификатов
            
            # Добавляем поддержку старых протоколов для максимальной совместимости
            try:
                # Для новых версий Python
                ctx.minimum_version = ssl.TLSVersion.TLSv1  # Разрешаем TLS 1.0+
                ctx.maximum_version = ssl.TLSVersion.TLSv1_3  # До TLS 1.3
            except AttributeError:
                # Для старых версий Python - убираем запреты на старые протоколы
                try:
                    ctx.options &= ~ssl.OP_NO_TLSv1
                    ctx.options &= ~ssl.OP_NO_TLSv1_1
                    ctx.options &= ~ssl.OP_NO_TLSv1_2
                except AttributeError:
                    pass
            
            # Устанавливаем адаптер для HTTPS
            ssl_adapter = SSLContextAdapter(ssl_context=ctx)
            self.session.mount('https://', ssl_adapter)
            
            logger.info("SSL адаптер настроен для работы с устаревшими серверами")
            
        except Exception as e:
            logger.warning(f"Не удалось настроить SSL адаптер: {e}")
            logger.info("Будет использоваться стандартный SSL")
        
    def analyze_search_results(self, search_results: List[Dict], limit: int = 15, email: str = None) -> Dict[str, Any]:
        """
        Анализирует ссылки из результатов поиска с приоритизацией наиболее релевантных страниц
        
        Args:
            search_results: Список результатов поиска
            limit: Количество ссылок для анализа (по умолчанию 15)
            email: Целевой email для контекстного анализа
            
        Returns:
            Dict с структурированной информацией о владельце email
        """
        # Сохраняем целевой email для использования в анализе
        if email:
            self._current_target_email = email
        analyzed_data = {
            'owner_identification': {
                'names_found': [],
                'most_likely_name': None,
                'confidence_score': 0.0,
                'name_variations': []
            },
            'professional_details': {
                'positions': [],
                'organizations': [],
                'locations': [],
                'specializations': []
            },
            'contact_information': {
                'emails': [],
                'phones': [],
                'social_media': [],
                'websites': []
            },
            'academic_info': {
                'degrees': [],
                'publications': [],
                'research_areas': [],
                'affiliations': []
            },
            'analysis_metadata': {
                'analyzed_urls': [],
                'successful_extractions': 0,
                'failed_extractions': 0,
                'analysis_timestamp': time.time(),
                'extraction_methods': [],
                'relevance_analysis_applied': True
            }
        }
        
        # Анализируем релевантность ссылок для конкретного email
        email_param = email or 'unknown@example.com'
        analyzed_results = self._analyze_url_relevance(search_results[:limit * 2], email_param)
        
        # Берем топ N наиболее релевантных ссылок
        urls_to_analyze = []
        # Используем порядок, заданный Google API, для определения приоритета
        for i, result in enumerate(search_results[:limit]):
            # Проверяем разные варианты ключей для URL
            url = result.get('url') or result.get('link')
            if url:
                urls_to_analyze.append({
                    'url': url,
                    'relevance_score': 1.0,  # Максимальный приоритет для всех результатов Google API
                    'relevance_reasons': ['Google API порядок приоритета'],
                    'google_api_rank': i + 1  # Сохраняем позицию в Google API результатах
                })
                logger.info(f"Используем URL: {url} с Google API приоритетом #{i + 1}")
        
        # URLs уже отсортированы в порядке Google API, дополнительная сортировка не нужна
        
        logger.info(f"Начинаем анализ релевантности {len(urls_to_analyze)} веб-страниц")
        
        # Анализируем в порядке приоритета
        for i, url_data in enumerate(urls_to_analyze):
            url = url_data['url']
            try:
                logger.info(f"Анализируем страницу {i+1}/{len(urls_to_analyze)}: {url} (релевантность: {url_data['relevance_score']:.2f})")
                page_data = self._analyze_single_page(url)
                
                if page_data:
                    self._merge_page_data(analyzed_data, page_data)
                    analyzed_data['analysis_metadata']['successful_extractions'] += 1
                    analyzed_data['analysis_metadata']['analyzed_urls'].append({
                        'url': url,
                        'status': 'success',
                        'extracted_data_types': list(page_data.keys()),
                        'relevance_score': url_data['relevance_score'],
                        'relevance_reasons': url_data['relevance_reasons']
                    })
                else:
                    analyzed_data['analysis_metadata']['failed_extractions'] += 1
                    analyzed_data['analysis_metadata']['analyzed_urls'].append({
                        'url': url,
                        'status': 'failed',
                        'reason': 'No data extracted',
                        'relevance_score': url_data['relevance_score'],
                        'relevance_reasons': url_data['relevance_reasons']
                    })
                    
            except Exception as e:
                logger.error(f"Ошибка анализа страницы {url}: {str(e)}")
                analyzed_data['analysis_metadata']['failed_extractions'] += 1
                analyzed_data['analysis_metadata']['analyzed_urls'].append({
                    'url': url,
                    'status': 'error',
                    'reason': str(e),
                    'relevance_score': url_data.get('relevance_score', 0),
                    'relevance_reasons': url_data.get('relevance_reasons', [])
                })
            
            # Адаптивная пауза: меньше для высокорелевантных страниц
            pause_time = 0.15 if url_data.get('relevance_score', 0) > 0.7 else 0.25
            time.sleep(pause_time)
        
        # Постобработка: определяем наиболее вероятное имя
        self._determine_most_likely_name(analyzed_data)
        
        logger.info(f"Анализ релевантности завершен. Успешно: {analyzed_data['analysis_metadata']['successful_extractions']}, "
                   f"неудачно: {analyzed_data['analysis_metadata']['failed_extractions']}")
        
        return analyzed_data
    
    def _analyze_single_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Анализирует одну веб-страницу с улучшенной обработкой ошибок"""
        try:
            # Предварительная проверка URL
            if not self._should_analyze_url(url):
                return None
            
            response = self._make_request_with_retry(url)
            if not response:
                logger.warning(f"Не удалось получить ответ от {url} после всех попыток")
                return None
            
            # Проверяем тип контента
            content_type = response.headers.get('content-type', '').lower()
            
            # Определяем максимальный размер в зависимости от типа файла
            max_size = self.max_content_size
            if 'pdf' in content_type:
                max_size = self.max_pdf_size
            elif not any(ct in content_type for ct in ['text/html', 'text/plain', 'application/xhtml']):
                logger.warning(f"Неподдерживаемый тип контента {content_type} для {url}")
                return None
            
            # Проверяем размер контента
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > max_size:
                logger.warning(f"Страница {url} слишком большая ({content_length} байт), пропускаем")
                return None
            
            # Читаем контент с ограничением размера
            content = b''
            current_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                current_size += len(chunk)
                if current_size > max_size:
                    logger.warning(f"Достигнут лимит размера для {url} ({current_size} байт), обрезаем")
                    break
                content += chunk
            
            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code} для {url}")
                return None
            
            # Проверяем, является ли файл PDF
            if 'pdf' in content_type or content.startswith(b'%PDF'):
                logger.info(f"Обнаружен PDF файл: {url}")
                return self._analyze_pdf_content(content, url)
            
            # Определяем кодировку для HTML/текстового контента
            encoding = response.encoding or 'utf-8'
            html_content = content.decode(encoding, errors='ignore')
            
            # Парсим HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            page_data = {
                'names': self._extract_names(soup, url),
                'positions': self._extract_positions(soup),
                'organizations': self._extract_organizations(soup),
                'locations': self._extract_locations(soup),
                'contact_info': self._extract_contact_info(soup),
                'academic_info': self._extract_academic_info(soup),
                'metadata': self._extract_metadata(soup, url)
            }
            
            # Фильтруем пустые данные
            return {k: v for k, v in page_data.items() if v}
            
        except requests.exceptions.SSLError as e:
            # Специальная обработка SSL ошибок
            if 'DH_KEY_TOO_SMALL' in str(e) or 'dh key too small' in str(e).lower():
                logger.warning(f"SSL DH_KEY_TOO_SMALL для {url} - сервер использует устаревшие настройки SSL")
                # Попробуем обойти с менее строгими настройками
                try:
                    response = self.session.get(url, timeout=self.timeout, stream=True, verify=False)
                    if response.status_code == 200:
                        logger.info(f"Успешно подключились к {url} с отключенной верификацией SSL")
                        # Продолжаем обработку как обычно
                        content_type = response.headers.get('content-type', '').lower()
                        max_size = self.max_pdf_size if 'pdf' in content_type else self.max_content_size
                        
                        content = b''
                        current_size = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            current_size += len(chunk)
                            if current_size > max_size:
                                break
                            content += chunk
                        
                        if 'pdf' in content_type or content.startswith(b'%PDF'):
                            return self._analyze_pdf_content(content, url)
                        
                        encoding = response.encoding or 'utf-8'
                        html_content = content.decode(encoding, errors='ignore')
                        soup = BeautifulSoup(html_content, 'html.parser')
                        
                        page_data = {
                            'names': self._extract_names(soup, url),
                            'positions': self._extract_positions(soup),
                            'organizations': self._extract_organizations(soup),
                            'locations': self._extract_locations(soup),
                            'contact_info': self._extract_contact_info(soup),
                            'academic_info': self._extract_academic_info(soup),
                            'metadata': self._extract_metadata(soup, url)
                        }
                        
                        return {k: v for k, v in page_data.items() if v}
                        
                except Exception as fallback_e:
                    logger.error(f"Fallback анализ также не удался для {url}: {str(fallback_e)}")
            else:
                logger.error(f"SSL ошибка для {url}: {str(e)}")
            return None
        except requests.RequestException as e:
            logger.error(f"Ошибка HTTP запроса к {url}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга {url}: {str(e)}")
            return None
    
    def _make_request_with_retry(self, url: str):
        """Выполняет HTTP запрос с повторными попытками и улучшенной обработкой ошибок"""
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Попытка {attempt + 1}/{self.max_retries + 1} для {url}")
                
                response = self.session.get(url, timeout=self.timeout, stream=True, verify=False)
                response.raise_for_status()
                return response
                
            except requests.exceptions.ConnectionError as e:
                error_msg = str(e).lower()
                if attempt < self.max_retries:
                    if 'connection reset' in error_msg or 'connection aborted' in error_msg:
                        logger.warning(f"Соединение сброшено для {url}, попытка {attempt + 1}/{self.max_retries + 1}")
                        time.sleep(self.retry_delay * (attempt + 1))  # Увеличиваем задержку
                        continue
                    elif 'timed out' in error_msg or 'timeout' in error_msg:
                        logger.warning(f"Таймаут для {url}, попытка {attempt + 1}/{self.max_retries + 1}")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        logger.warning(f"Ошибка соединения для {url}: {error_msg}")
                        time.sleep(self.retry_delay)
                        continue
                else:
                    logger.error(f"Не удалось подключиться к {url} после {self.max_retries + 1} попыток: {e}")
                    return None
            
            except requests.exceptions.Timeout as e:
                if attempt < self.max_retries:
                    logger.warning(f"Таймаут для {url}, попытка {attempt + 1}/{self.max_retries + 1}")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Таймаут для {url} после {self.max_retries + 1} попыток: {e}")
                    return None
            
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response else 'unknown'
                if status_code in [429, 503, 502, 504]:  # Временные ошибки сервера
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)  # Экспоненциальная задержка
                        logger.warning(f"HTTP {status_code} для {url}, ждем {wait_time}с перед повтором")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"HTTP {status_code} для {url} после всех попыток: {e}")
                        return None
                elif status_code in [404, 403, 401]:  # Постоянные ошибки
                    logger.warning(f"HTTP {status_code} для {url}, не повторяем: {e}")
                    return None
                else:
                    logger.error(f"HTTP ошибка {status_code} для {url}: {e}")
                    return None
            
            except requests.exceptions.SSLError as e:
                ssl_error_str = str(e).lower()
                if any(ssl_indicator in ssl_error_str for ssl_indicator in [
                    'certificate verify failed', 'ssl', 'dh_key_too_small', 'dh key too small',
                    'handshake failure', 'protocol error', 'wrong version number'
                ]):
                    logger.warning(f"SSL ошибка для {url}: {e}")
                    # Попробуем с различными SSL настройками
                    if attempt < self.max_retries:
                        fallback_success = False
                        
                        # Попытка 1: Отключение SSL верификации
                        try:
                            logger.info(f"Попытка 1 - без SSL верификации для {url}")
                            response = self.session.get(url, timeout=self.timeout, stream=True, verify=False)
                            response.raise_for_status()
                            fallback_success = True
                            return response
                        except Exception as fallback_e1:
                            logger.debug(f"Попытка 1 неудачна: {fallback_e1}")
                        
                        # Попытка 2: Создание нового session с минимальными SSL требованиями
                        if not fallback_success:
                            try:
                                logger.info(f"Попытка 2 - новая сессия с минимальными SSL требованиями для {url}")
                                import ssl
                                
                                # Создаем новую сессию только для этого запроса
                                temp_session = requests.Session()
                                temp_session.headers.update(self.session.headers)
                                
                                # Настраиваем максимально permissive SSL
                                from requests.adapters import HTTPAdapter
                                from urllib3.util.ssl_ import create_urllib3_context
                                
                                class UltraPermissiveSSLAdapter(HTTPAdapter):
                                    def init_poolmanager(self, *args, **kwargs):
                                        ctx = create_urllib3_context()
                                        ctx.check_hostname = False
                                        ctx.verify_mode = ssl.CERT_NONE
                                        try:
                                            ctx.set_ciphers('ALL:!aNULL:!eNULL:@SECLEVEL=0')
                                        except ssl.SSLError:
                                            try:
                                                ctx.set_ciphers('DEFAULT@SECLEVEL=0')
                                            except ssl.SSLError:
                                                pass
                                        kwargs['ssl_context'] = ctx
                                        return super().init_poolmanager(*args, **kwargs)
                                
                                temp_session.mount('https://', UltraPermissiveSSLAdapter())
                                
                                response = temp_session.get(url, timeout=self.timeout, stream=True, verify=False)
                                response.raise_for_status()
                                fallback_success = True
                                return response
                                
                            except Exception as fallback_e2:
                                logger.debug(f"Попытка 2 неудачна: {fallback_e2}")
                        
                        # Если все fallback попытки неудачны, пробуем следующую итерацию retry
                        if not fallback_success and attempt < self.max_retries:
                            logger.warning(f"Все SSL fallback попытки неудачны для {url}, пауза перед следующей попыткой")
                            time.sleep(self.retry_delay * (attempt + 1))
                            continue
                    
                    logger.error(f"SSL ошибка для {url} не удалось обойти после всех попыток: {e}")
                    return None
                else:
                    logger.error(f"Неизвестная SSL ошибка для {url}: {e}")
                    return None
            
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"Неожиданная ошибка для {url}, попытка {attempt + 1}/{self.max_retries + 1}: {e}")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"Неожиданная ошибка для {url} после всех попыток: {e}")
                    return None
        
        return None
    
    def _extract_names(self, soup: BeautifulSoup, url: str) -> List[str]:
        """Извлекает имена людей из страницы"""
        names = []
        
        # Улучшенные паттерны для поиска имен
        name_patterns = [
            # Русские ФИО
            r'\b[А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+\b',  # Фамилия Имя Отчество
            r'\b[А-Я][а-я]+\s+[А-Я]\.\s*[А-Я]\.\b',          # Фамилия И.О.
            r'\b[А-Я]\.\s*[А-Я]\.\s*[А-Я][а-я]+\b',          # И.О. Фамилия
            r'\b[А-Я][а-я]+,?\s+[А-Я][а-я]+\b',              # Фамилия Имя
            
            # Английские имена
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b',  # Имя Фамилия [Отчество]
            r'\b[A-Z][a-z]+,\s*[A-Z]\.\s*[A-Z]\.\b',              # Фамилия, И.О.
            r'\b[A-Z]\.\s*[A-Z]\.\s*[A-Z][a-z]+\b',              # И.О. Фамилия
            r'\b[A-Z][a-z]+,?\s+[A-Z][a-z]+\b',                  # Фамилия Имя
            
            # Специальные форматы для научных публикаций
            r'\b[A-ZА-Я][a-zа-я]+\s+[A-ZА-Я]\s*[A-ZА-Я]?\s*[a-zа-я]*\b',  # Фамилия И О
            r'\b[A-ZА-Я]\s*[A-ZА-Я]?\s*[a-zа-я]*\s+[A-ZА-Я][a-zа-я]+\b'   # И О Фамилия
        ]
        
        # Ищем в заголовках, метаданных, и тексте
        search_areas = [
            soup.find('title'),
            soup.find('meta', {'name': 'author'}),
            soup.find('meta', {'property': 'article:author'}),
            *soup.find_all(['h1', 'h2', 'h3']),
            *soup.find_all(class_=re.compile(r'author|name|researcher|scientist', re.I)),
            *soup.find_all(id=re.compile(r'author|name|researcher|scientist', re.I))
        ]
        
        for area in search_areas:
            if area and area.get_text():
                text = area.get_text().strip()
                for pattern in name_patterns:
                    matches = re.findall(pattern, text)
                    names.extend(matches)
        
        # Дополнительно ищем в структурированных данных
        json_ld = soup.find_all('script', type='application/ld+json')
        for script in json_ld:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'name' in data:
                    names.append(data['name'])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'name' in item:
                            names.append(item['name'])
            except (json.JSONDecodeError, AttributeError):
                continue
        
        # Фильтруем и очищаем имена
        filtered_names = self._filter_and_clean_names(names, target_email=None)
        
        return filtered_names
    
    def _filter_and_clean_names(self, names: List[str], target_email: str = None) -> List[str]:
        """Фильтрует и очищает найденные имена от шума и артефактов"""
        if not names:
            return []
        
        filtered_names = []
        
        # Слова и фразы, которые не являются именами
        noise_patterns = [
            r'^[А-Я]\.\s*[А-Я]\.\s*Эффективность',  # Н.В. Эффективность
            r'^[A-Z]\.\s*[A-Z]\.\s*[A-Z][a-z]*$',    # Просто инициалы без фамилии
            r'^[А-Я]\.\s*[А-Я]\.$',                   # Просто русские инициалы
            r'\b(Abstract|Аннотация|Keywords|Ключевые слова|References|Литература)\b',
            r'\b(Copyright|©|All rights reserved|Все права защищены)\b',
            r'\b(Click|Нажмите|Download|Скачать|PDF|DOI|PMID)\b',
            r'^[0-9]+',  # Начинается с цифр
            r'[<>\[\]{}()"\']',  # Содержит специальные символы
            r'\b(www\.|http|@|\.com|\.ru|\.org)\b',  # Содержит веб-элементы
            
            # Названия журналов и публикаций
            r'\b(Вестник|Журнал|Бюллетень|Bulletin|Journal|Review|Magazine)\b',
            r'\b(ISSN|DOI|Volume|Выпуск|Том|Issue|Article|Статья)\b',
            r'\b(Publication|Публикация|Издание|Edition|Press|Пресс)\b',
            r'\b(Medical Journal|Медицинский журнал|Scientific|Научный)\b',
            r'\b(Proceedings|Труды|Conference|Конференция|Symposium)\b',
            r'\b(University Press|Издательство|Publishing|Print|Online)\b',
            
            # Организационные названия
            r'\b(State Medical University|Clinical Dental Clinic)\b',
            r'\b(Thermo Fisher Scientific|Original Study)\b',
            r'\b(Kazan Medical Journal|Kazan State)\b',
            r'\b(Russian University|Российский университет)\b',
            
            # Технические термины
            r'\b(Study|Исследование|Analysis|Анализ|Method|Метод)\b',
            r'\b(Clinical|Клинический|Diagnostic|Диагностический)\b',
            r'\b(Treatment|Лечение|Therapy|Терапия|Surgery|Хирургия)\b',
        ]
        
        # Минимальные требования к именам
        min_name_length = 3
        max_name_length = 100
        
        for name in names:
            if not name or not isinstance(name, str):
                continue
            
            # Очищаем от лишних пробелов и табуляции
            cleaned_name = re.sub(r'\s+', ' ', name.strip())
            
            # Проверяем длину
            if len(cleaned_name) < min_name_length or len(cleaned_name) > max_name_length:
                continue
            
            # Проверяем на шумовые паттерны
            is_noise = False
            for pattern in noise_patterns:
                if re.search(pattern, cleaned_name, re.I):
                    is_noise = True
                    break
            
            if is_noise:
                continue
            
            # Проверяем на совпадение с локальной частью email
            if target_email and '@' in target_email:
                email_local = target_email.split('@')[0].lower()
                if not any(part in email_local for part in cleaned_name.lower().split()):
                    continue
            
            # Проверяем, что имя содержит хотя бы одну букву
            if not re.search(r'[A-Za-zА-Яа-я]', cleaned_name):
                continue
            
            # Дополнительная фильтрация для русских имен
            if re.search(r'[А-Яа-я]', cleaned_name):
                # Проверяем, что это похоже на настоящее имя
                russian_name_patterns = [
                    r'^[А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+$',  # ФИО
                    r'^[А-Я][а-я]+\s+[А-Я]\.[А-Я]\.$',              # Фамилия И.О.
                    r'^[А-Я]\.[А-Я]\.\s+[А-Я][а-я]+$',              # И.О. Фамилия
                    r'^[А-Я][а-я]+\s+[А-Я][а-я]+$'                  # Фамилия Имя
                ]
                
                is_valid_russian = any(re.match(pattern, cleaned_name) for pattern in russian_name_patterns)
                if not is_valid_russian:
                    continue
            
            # Дополнительная фильтрация для английских имен
            elif re.search(r'[A-Za-z]', cleaned_name):
                english_name_patterns = [
                    r'^[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$',  # Имя Фамилия [Отчество]
                    r'^[A-Z][a-z]+,\s*[A-Z]\.[A-Z]\.$',                 # Фамилия, И.О.
                    r'^[A-Z]\.[A-Z]\.\s+[A-Z][a-z]+$',                 # И.О. Фамилия
                    r'^[A-Z][a-z]+\s+[A-Z][a-z]+$'                     # Фамилия Имя
                ]
                
                is_valid_english = any(re.match(pattern, cleaned_name) for pattern in english_name_patterns)
                if not is_valid_english:
                    continue
            
            # Если имя прошло все проверки, добавляем его
            if cleaned_name not in filtered_names:
                filtered_names.append(cleaned_name)
        
        return filtered_names
    
    def _extract_positions(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает должности и позиции"""
        positions = []
        
        position_keywords = [
            'professor', 'профессор', 'associate professor', 'доцент',
            'researcher', 'исследователь', 'scientist', 'ученый',
            'director', 'директор', 'head', 'заведующий', 'руководитель',
            'senior', 'старший', 'junior', 'младший', 'lead', 'ведущий',
            'doctor', 'доктор', 'candidate', 'кандидат', 'phd', 'к.м.н', 'д.м.н'
        ]
        
        # Ищем в классах и идентификаторах, связанных с позициями
        for keyword in position_keywords:
            elements = soup.find_all(class_=re.compile(keyword, re.I))
            elements.extend(soup.find_all(id=re.compile(keyword, re.I)))
            
            for elem in elements:
                text = elem.get_text().strip()
                if text and len(text) < 200:  # Разумное ограничение длины
                    if text not in positions:
                        positions.append(text)
        
        return list(positions)
    
    def _extract_organizations(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает названия организаций"""
        organizations = []
        
        # Ищем в метаданных
        org_meta = soup.find('meta', {'name': 'organization'})
        if org_meta and org_meta.get('content'):
            if org_meta['content'] not in organizations:
                organizations.append(org_meta['content'])
        
        # Ищем по ключевым словам
        org_keywords = [
            'university', 'университет', 'institute', 'институт',
            'college', 'колледж', 'academy', 'академия',
            'laboratory', 'лаборатория', 'center', 'центр',
            'hospital', 'больница', 'clinic', 'клиника'
        ]
        
        for keyword in org_keywords:
            elements = soup.find_all(class_=re.compile(keyword, re.I))
            elements.extend(soup.find_all(id=re.compile(keyword, re.I)))
            
            for elem in elements:
                text = elem.get_text().strip()
                if text and len(text) < 300:
                    if text not in organizations:
                        organizations.append(text)
        
        return list(organizations)
    
    def _extract_locations(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает географические локации"""
        locations = []
        
        # Паттерны для городов и стран
        location_patterns = [
            r'\b[A-ZА-Я][a-zа-я]+,\s*[A-ZА-Я][a-zа-я]+\b',  # Город, Страна
            r'\b[A-ZА-Я][a-zа-я]+\s+[A-ZА-Я][a-zа-я]+,\s*[A-ZА-Я]{2,}\b'  # Город Область, Страна
        ]
        
        text_content = soup.get_text()
        for pattern in location_patterns:
            matches = re.findall(pattern, text_content)
            for match in matches:
                if match not in locations:
                    locations.append(match)
        
        return list(locations)
    
    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Извлекает контактную информацию"""
        contact_info = {
            'emails': [],
            'phones': [],
            'websites': []
        }
        
        text_content = soup.get_text()
        
        # Email адреса
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text_content)
        # Безопасное удаление дубликатов
        unique_emails = []
        for email in emails:
            if email not in unique_emails:
                unique_emails.append(email)
        contact_info['emails'] = unique_emails
        
        # Телефоны
        phone_patterns = [
            r'\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
            r'\(\d{3}\)[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}'
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text_content)
            contact_info['phones'].extend(phones)
        
        # Безопасное удаление дубликатов
        unique_phones = []
        for phone in contact_info['phones']:
            if phone not in unique_phones:
                unique_phones.append(phone)
        contact_info['phones'] = unique_phones
        
        return contact_info
    
    def _extract_academic_info(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Извлекает академическую информацию"""
        academic_info = {
            'degrees': [],
            'research_areas': [],
            'publications': []
        }
        
        # Ищем ученые степени
        degree_patterns = [
            r'\b(PhD|Ph\.D\.?|Doctorate|Доктор|Кандидат|М\.Д\.?|М\.С\.?|Б\.С\.?)\b',
            r'\b(к\.м\.н\.?|д\.м\.н\.?|к\.т\.н\.?|д\.т\.н\.?)\b'
        ]
        
        text_content = soup.get_text()
        for pattern in degree_patterns:
            degrees = re.findall(pattern, text_content, re.I)
            academic_info['degrees'].extend(degrees)
        
        # Ищем области исследований
        research_keywords = [
            'research', 'исследование', 'study', 'изучение',
            'analysis', 'анализ', 'development', 'разработка'
        ]
        
        for keyword in research_keywords:
            elements = soup.find_all(class_=re.compile(keyword, re.I))
            for elem in elements:
                text = elem.get_text().strip()
                if text and len(text) < 500:
                    academic_info['research_areas'].append(text)
        
        return academic_info
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Извлекает метаданные страницы"""
        metadata = {
            'title': '',
            'description': '',
            'domain': urlparse(url).netloc,
            'url': url
        }
        
        title = soup.find('title')
        if title:
            metadata['title'] = title.get_text().strip()
        
        description = soup.find('meta', {'name': 'description'})
        if description and description.get('content'):
            metadata['description'] = description['content']
        
        return metadata
    
    def _merge_page_data(self, analyzed_data: Dict[str, Any], page_data: Dict[str, Any]):
        """Объединяет данные со страницы с общими результатами анализа"""
        
        if 'names' in page_data:
            analyzed_data['owner_identification']['names_found'].extend(page_data['names'])
        
        if 'positions' in page_data:
            analyzed_data['professional_details']['positions'].extend(page_data['positions'])
        
        if 'organizations' in page_data:
            analyzed_data['professional_details']['organizations'].extend(page_data['organizations'])
        
        if 'locations' in page_data:
            analyzed_data['professional_details']['locations'].extend(page_data['locations'])
        
        if 'contact_info' in page_data:
            for key, values in page_data['contact_info'].items():
                if key in analyzed_data['contact_information']:
                    analyzed_data['contact_information'][key].extend(values)
        
        if 'academic_info' in page_data:
            for key, values in page_data['academic_info'].items():
                if key in analyzed_data['academic_info']:
                    analyzed_data['academic_info'][key].extend(values)
        
        # Удаляем дубликаты (безопасно для всех типов данных)
        for section in analyzed_data.values():
            if isinstance(section, dict):
                for key, value in section.items():
                    if isinstance(value, list):
                        # Безопасное удаление дубликатов для любых типов данных
                        seen = []
                        unique_items = []
                        for item in value:
                            # Для простых типов используем прямое сравнение
                            if isinstance(item, (str, int, float, bool)):
                                if item not in seen:
                                    seen.append(item)
                                    unique_items.append(item)
                            else:
                                # Для сложных типов (dict, list) сравниваем строковое представление
                                item_str = str(item)
                                if item_str not in [str(x) for x in unique_items]:
                                    unique_items.append(item)
                        section[key] = unique_items
    
    def _should_analyze_url(self, url: str) -> bool:
        """Проверяет, стоит ли анализировать данный URL"""
        try:
            parsed_url = urlparse(url)
            
            # Проверяем расширение файла
            path_lower = parsed_url.path.lower()
            for ext in self.skip_extensions:
                if path_lower.endswith(ext):
                    logger.info(f"Пропускаем файл с расширением {ext}: {url}")
                    return False
            
            # Пропускаем слишком длинные URL (могут быть подозрительными)
            if len(url) > 500:
                logger.info(f"Пропускаем слишком длинный URL: {url[:100]}...")
                return False
            
            # Проверяем домены, которые обычно не содержат полезной информации
            skip_domains = {
                'google.com', 'youtube.com', 'facebook.com', 'twitter.com',
                'instagram.com', 'linkedin.com', 'vk.com', 'ok.ru',
                'amazon.com', 'ebay.com', 'aliexpress.com'
            }
            
            domain = parsed_url.netloc.lower()
            # Убираем www. для проверки
            if domain.startswith('www.'):
                domain = domain[4:]
            
            if domain in skip_domains:
                logger.info(f"Пропускаем домен {domain}: {url}")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Ошибка при проверке URL {url}: {str(e)}")
            return False
    
    def _determine_most_likely_name(self, analyzed_data: Dict[str, Any]):
        """Определяет наиболее вероятное имя владельца email с интеллектуальной фильтрацией и контекстным анализом"""
        names = analyzed_data['owner_identification']['names_found']
        
        if not names:
            logger.info("📊 Enhanced Analysis: Нет имен для анализа")
            return
        
        logger.info(f"📊 Enhanced Analysis: Начинаем анализ {len(names)} найденных имен")
        
        # Фильтруем имена по качеству и исключаем нечеловеческие названия
        filtered_names = self._filter_names_by_quality(names)
        
        if not filtered_names:
            logger.info("📊 Enhanced Analysis: Все имена отфильтрованы как некачественные")
            return
        
        logger.info(f"📊 Enhanced Analysis: После фильтрации осталось {len(filtered_names)} качественных имен")
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Всегда используем сохраненный целевой email в первую очередь
        target_email = None
        if hasattr(self, '_current_target_email') and self._current_target_email:
            target_email = self._current_target_email
            logger.info(f"📊 Enhanced Analysis: ПРИОРИТЕТ - Используем сохраненный целевой email: {target_email}")
        else:
            # Только если нет сохраненного email, получаем из метаданных
            target_email = self._get_target_email_from_metadata(analyzed_data)
            logger.warning(f"📊 Enhanced Analysis: Целевой email НЕ СОХРАНЕН, используем из метаданных: {target_email}")
            logger.warning(f"📊 Enhanced Analysis: hasattr(_current_target_email): {hasattr(self, '_current_target_email')}")
            if hasattr(self, '_current_target_email'):
                logger.warning(f"📊 Enhanced Analysis: _current_target_email value: '{self._current_target_email}'")
        
        # Система скоринга для каждого имени с учетом контекста
        scored_names = []
        
        for name in filtered_names:
            base_score = self._calculate_name_quality_score(name)
            
            # Улучшение 1: Добавляем контекстный анализ
            context_score = self._calculate_context_score(name, analyzed_data, target_email)
            
            # Улучшение 2: Анализируем соответствие с email
            email_match_score = self._calculate_email_match_score(name, target_email) if target_email else 0.0
            
            # Комбинируем скоры
            total_score = base_score * 0.3 + context_score * 0.4 + email_match_score * 0.3
            
            logger.info(f"📊 Enhanced Analysis: '{name}' - базовый: {base_score:.3f}, контекст: {context_score:.3f}, email: {email_match_score:.3f}, итоговая уверенность: {total_score:.3f}")
            
            scored_names.append((name, total_score))
        
        # Сортируем по убыванию скора
        scored_names.sort(key=lambda x: x[1], reverse=True)
        
        if scored_names:
            best_name = scored_names[0]
            analyzed_data['owner_identification']['most_likely_name'] = best_name[0]
            analyzed_data['owner_identification']['confidence_score'] = min(best_name[1], 1.0)
            
            # Добавляем информацию о методе определения
            analyzed_data['owner_identification']['determination_method'] = 'enhanced_context_analysis'
            analyzed_data['owner_identification']['score_breakdown'] = {
                'context_analysis': True,
                'email_matching': target_email is not None,
                'quality_filtering': True
            }
            
            # Группируем вариации имен
            base_name = best_name[0].split()[0] if best_name[0] else ""
            variations = [name for name in filtered_names if base_name.lower() in name.lower()]
            analyzed_data['owner_identification']['name_variations'] = variations
    
    def _filter_names_by_quality(self, names: List[str]) -> List[str]:
        """Фильтрует имена по качеству, исключая нечеловеческие названия и технические префиксы"""
        filtered_names = []
        
        technical_prefixes = [
            'антиплагиат', 'antiplagiat', 'система', 'сервис', 'платформа', 
            'программа', 'software', 'system', 'service'
        ]

        for name in names:
            if not name or not isinstance(name, str):
                continue
            
            # Базовая очистка
            clean_name = re.sub(r'\s+', ' ', name.strip())
            
            # Исключаем имена с техническими префиксами
            if any(clean_name.lower().startswith(prefix) for prefix in technical_prefixes):
                continue
            
            # Проверяем длину
            if len(clean_name) < 3 or len(clean_name) > 100:
                continue
            
            # Исключаем названия журналов и публикаций (расширенный список)
            journal_indicators = [
                'вестник', 'журнал', 'бюллетень', 'journal', 'bulletin', 'review',
                'proceedings', 'publication', 'издание', 'scientific', 'medical',
                'issn', 'volume', 'issue', 'article', 'study', 'analysis',
                'university press', 'editorial', 'editor', 'редакция',
                'kazan medical journal', 'kazan state', 'oral biol craniofacial',
                'sci med sport', 'family med prim', 'exp ther med', 'complement ther med',
                'research involving human', 'beijing da xue', 'xue bao yi',
                'acta medica eurasica', 'russian federation russian',
                'central black earth', 'центрального черноземья'
            ]
            
            name_lower = clean_name.lower()
            if any(indicator in name_lower for indicator in journal_indicators):
                continue
            
            # Исключаем организационные названия (расширенный список)
            org_indicators = [
                'state medical university', 'clinical dental clinic', 
                'thermo fisher scientific', 'original study',
                'center', 'centre', 'центр', 'laboratory', 'лаборатория',
                'dental outpatient clinic', 'voronezh state medical',
                'chief medical officer', 'small innovative enterprises',
                'international center', 'международный центр',
                'clinic', 'клиника', 'hospital', 'больница'
            ]
            
            if any(indicator in name_lower for indicator in org_indicators):
                continue
            
            # Исключаем технические термины и аббревиатуры
            technical_indicators = [
                'показатели покой покой', 'level professional football',
                'med sci sports', 'российская федерация российская',
                'russian federation disorder', 'россия реферат', 'актуальность',
                'реферат актуальность', 'научная работа', 'курсовая работа',
                'дипломная работа', 'магистерская диссертация', 'кандидатская диссертация',
                'докторская диссертация', 'введение актуальность', 'заключение выводы',
                'список литературы', 'библиографический список', 'annotation abstract',
                'keywords ключевые', 'research methodology', 'методология исследования',
                'теоретические основы', 'практическая значимость', 'новизна исследования'
            ]
            
            if any(indicator in name_lower for indicator in technical_indicators):
                continue
            
            # Проверяем, что это похоже на человеческое имя
            if self._is_human_name(clean_name):
                filtered_names.append(clean_name)
        
        return filtered_names
 
    def _extract_human_name_from_technical(self, technical_name: str) -> Optional[str]:
        """Извлекает человеческое имя из технического названия"""
        # Список технических префиксов для удаления
        technical_prefixes = [
            'антиплагиат', 'antiplagiat', 'система', 'сервис', 'платформа',
            'программа', 'software', 'system', 'service', 'tool', 'инструмент',
            'приложение', 'application', 'модуль', 'module', 'компонент',
            'решение', 'solution', 'технология', 'technology', 'методика',
            'procedure', 'процедура', 'алгоритм', 'algorithm', 'framework',
            'библиотека', 'library', 'пакет', 'package', 'комплекс', 'complex',
            'проект', 'project', 'разработка', 'development', 'версия', 'version'
        ]
        
        name_lower = technical_name.lower()
        
        # Ищем и удаляем технический префикс
        for prefix in technical_prefixes:
            patterns = [
                f'^{prefix}\s+',      # "антиплагиат "
                f'^{prefix}-',        # "антиплагиат-"
                f'^{prefix}:',        # "антиплагиат:"
                f'^{prefix}\.',       # "антиплагиат."
            ]
            
            for pattern in patterns:
                if re.match(pattern, name_lower):
                    # Удаляем префикс и очищаем
                    remaining = re.sub(pattern, '', technical_name, flags=re.IGNORECASE).strip()
                    if remaining:
                        return remaining
        
        return None
    
    def _contains_technical_components(self, name: str) -> bool:
        """Проверяет, содержит ли имя технические компоненты"""
        name_lower = name.lower()
        
        # Технические слова, которые не должны быть в человеческих именах
        technical_words = [
            'api', 'bot', 'система', 'system', 'сервис', 'service',
            'платформа', 'platform', 'версия', 'version', 'релиз', 'release',
            'update', 'обновление', 'patch', 'патч', 'fix', 'исправление',
            'bug', 'баг', 'error', 'ошибка', 'log', 'лог', 'debug',
            'тест', 'test', 'demo', 'демо', 'beta', 'бета', 'alpha',
            'config', 'конфигурация', 'setup', 'настройка', 'install',
            'установка', 'download', 'скачать', 'upload', 'загрузить'
        ]
        
        # Проверяем наличие технических слов
        words = name_lower.split()
        for word in words:
            if word in technical_words:
                return True
        
        # Проверяем технические паттерны
        technical_patterns = [
            r'v\d+\.\d+',           # версии типа v1.0
            r'\d+\.\d+\.\d+',       # версии типа 1.2.3
            r'build\s*\d+',         # build номера
            r'\w+\.exe',            # исполняемые файлы
            r'\w+\.dll',            # библиотеки
            r'\w+\.jar',            # Java архивы
            r'\w+@\w+',             # email-подобные структуры
        ]
        
        for pattern in technical_patterns:
            if re.search(pattern, name_lower):
                return True
        
        return False 
 
    def _calculate_email_match_score(self, name: str, target_email: str) -> float:
        """Вычисляет соответствие имени с email адресом"""
        if not target_email or not name:
            return 0.0
        
        # НОВОЕ: Очищаем имя от технических префиксов для корректного сопоставления
        clean_name = self._clean_name_for_email_matching(name)
        if not clean_name:
            return 0.0
        
        # Извлекаем локальную часть email
        email_local = target_email.split('@')[0].lower() if '@' in target_email else target_email.lower()
        name_lower = clean_name.lower()
        
        score = 0.0
        
        # Проверяем прямое совпадение полного имени
        if name_lower in email_local or email_local in name_lower:
            score += 0.4
        
        # Проверяем совпадение частей имени (только реальные части имени)
        name_parts = self._extract_real_name_parts(clean_name)
        matched_parts = 0
        
        for part in name_parts:
            if part in email_local:
                matched_parts += 1
                score += 0.3
            elif self._fuzzy_match(part, email_local) > 0.8:
                matched_parts += 1
                score += 0.2
        
        # Бонус за множественные совпадения
        if matched_parts >= 2:
            score += 0.2
        
        # Проверяем транслитерацию для русских имен
        if re.search(r'[А-Яа-я]', clean_name):
            transliterated = self._simple_transliterate(clean_name).lower()
            if transliterated != name_lower:
                if transliterated in email_local or email_local in transliterated:
                    score += 0.3
                
                # Проверяем части транслитерированного имени
                trans_parts = [part for part in transliterated.split() if len(part) > 2]
                for part in trans_parts:
                    if part in email_local:
                        score += 0.2
        
        # Проверяем инициалы (только от реальных частей имени)
        real_name_parts = [part for part in clean_name.split() if len(part) > 0 and part[0].isupper()]
        initials = ''.join([part[0].lower() for part in real_name_parts])
        if len(initials) >= 2 and initials in email_local:
            score += 0.1
        
        return min(score, 1.0)
    
    def _clean_name_for_email_matching(self, name: str) -> str:
        """Очищает имя от технических префиксов для корректного сопоставления с email"""
        if not name:
            return ''
        
        # Попытка извлечь человеческое имя из технического
        clean_name = self._extract_human_name_from_technical(name)
        if clean_name:
            return clean_name
        
        # Если извлечь не удалось, используем оригинальное имя
        return name
    
    def _extract_real_name_parts(self, name: str) -> List[str]:
        """Извлекает только реальные части имени, исключая технические термины"""
        if not name:
            return []
        
        parts = name.split()
        real_parts = []
        
        # Технические слова, которые не являются частью имени
        technical_words = [
            'антиплагиат', 'antiplagiat', 'система', 'сервис', 'платформа',
            'программа', 'software', 'system', 'service', 'api', 'bot',
            'версия', 'version', 'demo', 'test', 'beta', 'alpha'
        ]
        
        for part in parts:
            part_lower = part.lower()
            
            # Пропускаем технические слова
            if part_lower in technical_words:
                continue
            
            # Пропускаем слишком короткие части (кроме инициалов)
            if len(part) < 2 and not (len(part) == 2 and part.endswith('.')):
                continue
            
            # Пропускаем части, состоящие только из цифр
            if part.isdigit():
                continue
            
            # Оставляем только части, похожие на имена
            if part[0].isupper() and (part[1:].islower() or part.endswith('.')):
                real_parts.append(part_lower)
        
        return real_parts 
 
    def _is_human_name(self, name: str) -> bool:
        """Проверяет, является ли строка человеческим именем"""
        name_parts = name.split()
        
        # Должно быть от 2 до 4 частей
        if len(name_parts) < 2 or len(name_parts) > 4:
            return False
        
        # НОВОЕ: Дополнительная проверка на технические термины
        if self._contains_technical_components(name):
            return False
        
        # Каждая часть должна начинаться с заглавной буквы
        for part in name_parts:
            if not part[0].isupper():
                return False
            
            # Проверяем, что остальная часть состоит из букв
            if not all(c.isalpha() or c == '.' for c in part[1:]):
                return False
        
        # НОВОЕ: Проверяем, что все части - это реальные слова (не аббревиатуры)
        for part in name_parts:
            # Пропускаем инициалы (одна буква + точка)
            if len(part) == 2 and part.endswith('.'):
                continue
            # Для полных слов проверяем минимальную длину
            if len(part) < 2:
                return False
            # Проверяем, что это не техническая аббревиатура
            if part.isupper() and len(part) > 2:
                return False
        
        # Проверяем паттерны для русских имен
        if re.search(r'[А-Яа-я]', name):
            russian_patterns = [
                r'^[А-Я][а-я]+ [А-Я][а-я]+ [А-Я][а-я]+$',  # ФИО
                r'^[А-Я][а-я]+ [А-Я]\.[А-Я]\.$',           # Фамилия И.О.
                r'^[А-Я]\.[А-Я]\. [А-Я][а-я]+$',           # И.О. Фамилия
                r'^[А-Я][а-я]+ [А-Я][а-я]+$'               # Фамилия Имя
            ]
            return any(re.match(pattern, name) for pattern in russian_patterns)
        
        # Проверяем паттерны для английских имен
        elif re.search(r'[A-Za-z]', name):
            english_patterns = [
                r'^[A-Z][a-z]+ [A-Z][a-z]+( [A-Z][a-z]+)?$',  # First Last [Middle]
                r'^[A-Z][a-z]+, [A-Z]\.[A-Z]\.$',             # Last, F.M.
                r'^[A-Z]\.[A-Z]\. [A-Z][a-z]+$',              # F.M. Last
                r'^[A-Z][a-z]+ [A-Z][a-z]+$'                 # First Last
            ]
            return any(re.match(pattern, name) for pattern in english_patterns)
        
        return False

 
    def _calculate_email_match_score(self, name: str, target_email: str) -> float:
        """Вычисляет соответствие имени с email адресом"""
        if not target_email or not name:
            return 0.0
        
        # НОВОЕ: Очищаем имя от технических префиксов для корректного сопоставления
        clean_name = self._clean_name_for_email_matching(name)
        if not clean_name:
            return 0.0
        
        # Извлекаем локальную часть email
        email_local = target_email.split('@')[0].lower() if '@' in target_email else target_email.lower()
        name_lower = clean_name.lower()
        
        score = 0.0
        
        # Проверяем прямое совпадение полного имени
        if name_lower in email_local or email_local in name_lower:
            score += 0.4
        
        # Проверяем совпадение частей имени (только реальные части имени)
        name_parts = self._extract_real_name_parts(clean_name)
        matched_parts = 0
        
        for part in name_parts:
            if part in email_local:
                matched_parts += 1
                score += 0.3
            elif self._fuzzy_match(part, email_local) > 0.8:
                matched_parts += 1
                score += 0.2
        
        # Бонус за множественные совпадения
        if matched_parts >= 2:
            score += 0.2
        
        # Проверяем транслитерацию для русских имен
        if re.search(r'[А-Яа-я]', clean_name):
            transliterated = self._simple_transliterate(clean_name).lower()
            if transliterated != name_lower:
                if transliterated in email_local or email_local in transliterated:
                    score += 0.3
                
                # Проверяем части транслитерированного имени
                trans_parts = [part for part in transliterated.split() if len(part) > 2]
                for part in trans_parts:
                    if part in email_local:
                        score += 0.2
        
        # Проверяем инициалы (только от реальных частей имени)
        real_name_parts = [part for part in clean_name.split() if len(part) > 0 and part[0].isupper()]
        initials = ''.join([part[0].lower() for part in real_name_parts])
        if len(initials) >= 2 and initials in email_local:
            score += 0.1
        
        return min(score, 1.0)
    
    def _clean_name_for_email_matching(self, name: str) -> str:
        """Очищает имя от технических префиксов для корректного сопоставления с email"""
        if not name:
            return ''
        
        # Попытка извлечь человеческое имя из технического
        clean_name = self._extract_human_name_from_technical(name)
        if clean_name:
            return clean_name
        
        # Если извлечь не удалось, используем оригинальное имя
        return name
    
    def _extract_real_name_parts(self, name: str) -> List[str]:
        """Извлекает только реальные части имени, исключая технические термины"""
        if not name:
            return []
        
        parts = name.split()
        real_parts = []
        
        # Технические слова, которые не являются частью имени
        technical_words = [
            'антиплагиат', 'antiplagiat', 'система', 'сервис', 'платформа',
            'программа', 'software', 'system', 'service', 'api', 'bot',
            'версия', 'version', 'demo', 'test', 'beta', 'alpha'
        ]
        
        for part in parts:
            part_lower = part.lower()
            
            # Пропускаем технические слова
            if part_lower in technical_words:
                continue
            
            # Пропускаем слишком короткие части (кроме инициалов)
            if len(part) < 2 and not (len(part) == 2 and part.endswith('.')):
                continue
            
            # Пропускаем части, состоящие только из цифр
            if part.isdigit():
                continue
            
            # Оставляем только части, похожие на имена
            if part[0].isupper() and (part[1:].islower() or part.endswith('.')):
                real_parts.append(part_lower)
        
        return real_parts 
    
    def _is_human_name(self, name: str) -> bool:
        """Проверяет, является ли строка человеческим именем"""
        name_parts = name.split()
        
        # Должно быть от 2 до 4 частей
        if len(name_parts) < 2 or len(name_parts) > 4:
            return False
        
        # Каждая часть должна начинаться с заглавной буквы
        for part in name_parts:
            if not part[0].isupper():
                return False
            
            # Проверяем, что остальная часть состоит из букв
            if not all(c.isalpha() or c == '.' for c in part[1:]):
                return False
        
        # Проверяем паттерны для русских имен
        if re.search(r'[А-Яа-я]', name):
            russian_patterns = [
                r'^[А-Я][а-я]+ [А-Я][а-я]+ [А-Я][а-я]+$',  # ФИО
                r'^[А-Я][а-я]+ [А-Я]\.[А-Я]\.$',           # Фамилия И.О.
                r'^[А-Я]\.[А-Я]\. [А-Я][а-я]+$',           # И.О. Фамилия
                r'^[А-Я][а-я]+ [А-Я][а-я]+$'               # Фамилия Имя
            ]
            return any(re.match(pattern, name) for pattern in russian_patterns)
        
        # Проверяем паттерны для английских имен
        elif re.search(r'[A-Za-z]', name):
            english_patterns = [
                r'^[A-Z][a-z]+ [A-Z][a-z]+( [A-Z][a-z]+)?$',  # First Last [Middle]
                r'^[A-Z][a-z]+, [A-Z]\.[A-Z]\.$',             # Last, F.M.
                r'^[A-Z]\.[A-Z]\. [A-Z][a-z]+$',              # F.M. Last
                r'^[A-Z][a-z]+ [A-Z][a-z]+$'                 # First Last
            ]
            return any(re.match(pattern, name) for pattern in english_patterns)
        
        return False
    
    def _calculate_name_quality_score(self, name: str) -> float:
        """Вычисляет скор качества для имени"""
        score = 0.0
        
        # Базовый скор
        score += 0.3
        
        # Бонус за русские имена
        if re.search(r'[А-Яа-я]', name):
            score += 0.2
            
            # Дополнительный бонус за полное русское ФИО
            name_parts = name.split()
            if len(name_parts) == 3 and all(len(part) > 2 for part in name_parts):
                score += 0.3
        
        # Бонус за правильную структуру
        name_parts = name.split()
        if 2 <= len(name_parts) <= 3:
            score += 0.2
        
        # Штраф за слишком длинные или короткие имена
        if len(name) < 5 or len(name) > 50:
            score -= 0.2
        
        # Штраф за содержание цифр или специальных символов
        if re.search(r'[0-9@#$%&*]', name):
            score -= 0.5
        
        # Штраф за содержание ключевых слов журналов
        journal_words = ['вестник', 'журнал', 'scientific', 'medical', 'study']
        if any(word in name.lower() for word in journal_words):
            score -= 0.8
        
        # Специальный штраф за артефакты типа "Россия Реферат Актуальность"
        artifact_patterns = [
            'россия реферат', 'реферат актуальность', 'актуальность исследования',
            'научная работа', 'дипломная работа', 'курсовая работа', 'магистерская диссертация',
            'введение актуальность', 'заключение выводы', 'список литературы',
            'теоретические основы', 'практическая значимость', 'новизна исследования',
            'методология исследования', 'библиографический список'
        ]
        
        name_lower = name.lower()
        if any(pattern in name_lower for pattern in artifact_patterns):
            score -= 1.0  # Максимальный штраф для полного исключения
        
        # Дополнительный штраф за бессмысленные комбинации слов
        name_parts = name.split()
        if len(name_parts) >= 3:
            # Проверяем, если все части имени - это абстрактные понятия
            abstract_words = {
                'россия', 'реферат', 'актуальность', 'исследование', 'анализ',
                'методы', 'результаты', 'выводы', 'заключение', 'введение',
                'работа', 'диссертация', 'тема', 'проблема', 'вопрос',
                'russia', 'research', 'analysis', 'methods', 'results',
                'conclusion', 'introduction', 'work', 'thesis', 'problem'
            }
            
            abstract_count = sum(1 for part in name_parts if part.lower() in abstract_words)
            if abstract_count >= 2:  # Если 2 или более частей - абстрактные слова
                score -= 0.7
        
        return max(0.0, min(1.0, score))
    
    def _analyze_pdf_content(self, content: bytes, url: str) -> Optional[Dict[str, Any]]:
        """Анализирует PDF содержимое с использованием специализированных библиотек"""
        try:
            # Создаем объект io.BytesIO для работы с библиотеками PDF
            pdf_stream = io.BytesIO(content)
            
            # Сначала пробуем извлечь текст с помощью pdfplumber
            extracted_text = ""
            pdf_metadata = {}
            
            try:
                with pdfplumber.open(pdf_stream) as pdf:
                    logger.info(f"PDF содержит {len(pdf.pages)} страниц")
                    
                    # Извлекаем метаданные PDF
                    if hasattr(pdf, 'metadata') and pdf.metadata:
                        pdf_metadata = pdf.metadata
                        logger.info(f"Извлечены метаданные PDF: {list(pdf_metadata.keys())}")
                    
                    # Извлекаем текст со всех страниц (ограничиваем первыми 300 страницами)
                    max_pages = min(300, len(pdf.pages))
                    for i, page in enumerate(pdf.pages[:max_pages]):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                extracted_text += page_text + "\n"
                                logger.debug(f"Извлечен текст со страницы {i+1}: {len(page_text)} символов")
                        except Exception as e:
                            logger.warning(f"Ошибка извлечения текста со страницы {i+1}: {e}")
                            continue
                    
                    logger.info(f"Общий объем извлеченного текста: {len(extracted_text)} символов")
                    
            except Exception as e:
                logger.warning(f"Ошибка при использовании pdfplumber: {e}")
                
                # Fallback к PyPDF2
                try:
                    pdf_stream.seek(0)  # Сбрасываем позицию в потоке
                    pdf_reader = PyPDF2.PdfReader(pdf_stream)
                    
                    logger.info(f"PyPDF2: PDF содержит {len(pdf_reader.pages)} страниц")
                    
                    # Извлекаем метаданные
                    if pdf_reader.metadata:
                        pdf_metadata = dict(pdf_reader.metadata)
                        logger.info(f"PyPDF2: Извлечены метаданные: {list(pdf_metadata.keys())}")
                    
                    # Извлекаем текст
                    max_pages = min(300, len(pdf_reader.pages))
                    for i in range(max_pages):
                        try:
                            page = pdf_reader.pages[i]
                            page_text = page.extract_text()
                            if page_text:
                                extracted_text += page_text + "\n"
                                logger.debug(f"PyPDF2: Извлечен текст со страницы {i+1}: {len(page_text)} символов")
                        except Exception as e:
                            logger.warning(f"PyPDF2: Ошибка извлечения текста со страницы {i+1}: {e}")
                            continue
                    
                    logger.info(f"PyPDF2: Общий объем извлеченного текста: {len(extracted_text)} символов")
                    
                except Exception as e:
                    logger.error(f"Ошибка при использовании PyPDF2: {e}")
                    return None
            
            if not extracted_text.strip():
                logger.warning(f"Не удалось извлечь текст из PDF: {url}")
                return {
                    'metadata': {
                        'domain': urlparse(url).netloc,
                        'url': url,
                        'file_type': 'pdf',
                        'pdf_metadata': pdf_metadata,
                        'extraction_status': 'no_text_extracted'
                    }
                }
            
            # Создаем временный BeautifulSoup объект для использования существующих методов извлечения
            # Обертываем текст в HTML теги для совместимости
            html_content = f"<html><body><p>{extracted_text}</p></body></html>"
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Используем существующие методы для извлечения структурированных данных
            page_data = {
                'names': self._extract_names_from_pdf_text(extracted_text, url),
                'positions': self._extract_positions_from_text(extracted_text),
                'organizations': self._extract_organizations_from_text(extracted_text),
                'locations': self._extract_locations_from_text(extracted_text),
                'contact_info': self._extract_contact_info_from_text(extracted_text),
                'academic_info': self._extract_academic_info_from_text(extracted_text),
                'pdf_specific_data': self._extract_pdf_specific_data(extracted_text, pdf_metadata),
                'metadata': {
                    'domain': urlparse(url).netloc,
                    'url': url,
                    'file_type': 'pdf',
                    'pdf_metadata': pdf_metadata,
                    'text_length': len(extracted_text),
                    'extraction_status': 'success'
                }
            }
            
            # Фильтруем пустые данные
            return {k: v for k, v in page_data.items() if v}
            
        except Exception as e:
            logger.error(f"Ошибка анализа PDF {url}: {str(e)}")
            return {
                'metadata': {
                    'domain': urlparse(url).netloc,
                    'url': url,
                    'file_type': 'pdf',
                    'extraction_status': 'error',
                    'error_message': str(e)
                }
            }
    
    def _extract_names_from_pdf_text(self, text: str, url: str) -> List[str]:
        """Специализированное извлечение имен из PDF текста"""
        names = []
        
        # Улучшенные паттерны для PDF (часто содержат артефакты)
        pdf_name_patterns = [
            # Авторы в научных статьях
            r'Authors?:\s*([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я](?:\.[A-ZА-Я])?[a-zа-я]*)*(?:,\s*[A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я](?:\.[A-ZА-Я])?[a-zа-я]*)*)*)',
            r'Авторы?:\s*([А-Я][а-я]+(?:\s+[А-Я](?:\.[А-Я])?[а-я]*)*(?:,\s*[А-Я][а-я]+(?:\s+[А-Я](?:\.[А-Я])?[а-я]*)*)*)',
            
            # Корреспондирующий автор
            r'Corresponding author:\s*([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]*)*)',
            r'Автор для корреспонденции:\s*([А-Я][а-я]+(?:\s+[А-Я][а-я]*)*)',
            
            # Стандартные паттерны имен
            r'\b([A-ZА-Я][a-zа-я]+)\s+([A-ZА-Я][a-zа-я]+)\s+([A-ZА-Я][a-zа-я]+)\b',  # ФИО
            r'\b([A-ZА-Я][a-zа-я]+),\s*([A-ZА-Я])\.*\s*([A-ZА-Я])\.*\b',               # Фамилия, И.О.
            r'\b([A-ZА-Я])\.*\s*([A-ZА-Я])\.*\s*([A-ZА-Я][a-zа-я]+)\b',               # И.О. Фамилия
        ]
        
        for pattern in pdf_name_patterns:
            matches = re.findall(pattern, text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Если это группы из regex
                    name = ' '.join(filter(None, match)).strip()
                else:
                    name = match.strip()
                
                if name and len(name) > 2:
                    names.append(name)
        
        # Дополнительный поиск email адресов рядом с именами
        email_context_pattern = r'([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]*){1,2})\s*[\(\[]?\s*[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        email_contexts = re.findall(email_context_pattern, text)
        names.extend([name.strip() for name in email_contexts if name.strip()])
        
        return self._filter_and_clean_names(names, target_email=None)
    
    def _extract_positions_from_text(self, text: str) -> List[str]:
        """Извлечение должностей из чистого текста"""
        positions = []
        
        position_patterns = [
            r'\b(Professor|Профессор)\s+(?:of\s+)?([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)?)',
            r'\b(Associate Professor|Доцент)\s+(?:of\s+)?([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)?)',
            r'\b(Senior Researcher|Старший исследователь)',
            r'\b(Research Fellow|Научный сотрудник)',
            r'\b(Head of Department|Заведующий кафедрой)',
            r'\b(Director|Директор)\s+(?:of\s+)?([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)?)',
            r'\b(PhD|Ph\.D\.|Доктор наук|Кандидат наук)\b',
        ]
        
        for pattern in position_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    position = ' '.join(filter(None, match)).strip()
                else:
                    position = match.strip()
                
                if position and position not in positions:
                    positions.append(position)
        
        return positions
    
    def _extract_organizations_from_text(self, text: str) -> List[str]:
        """Извлечение организаций из чистого текста"""
        organizations = []
        
        org_patterns = [
            r'\b([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)*\s+(?:University|Университет))\b',
            r'\b([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)*\s+(?:Institute|Институт))\b',
            r'\b([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)*\s+(?:Academy|Академия))\b',
            r'\b([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)*\s+(?:Hospital|Больница|Clinic|Клиника))\b',
            r'\b([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)*\s+(?:Center|Centre|Центр))\b',
        ]
        
        for pattern in org_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                org = match.strip() if isinstance(match, str) else ' '.join(match).strip()
                if org and len(org) < 200 and org not in organizations:
                    organizations.append(org)
        
        return organizations
    
    def _extract_locations_from_text(self, text: str) -> List[str]:
        """Извлечение локаций из чистого текста"""
        locations = []
        
        location_patterns = [
            r'\b([A-ZА-Я][a-zа-я]+),\s*([A-ZА-Я][a-zа-я]+)\b',  # Город, Страна
            r'\b([A-ZА-Я][a-zа-я]+)\s*,\s*([A-ZА-Я]{2,3})\b',     # Город, Код страны
            # Адреса с почтовыми индексами
            r'\b\d{5,6}[,\s]+([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]+)*)\b',
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    location = ', '.join(filter(None, match)).strip()
                else:
                    location = match.strip()
                
                if location and location not in locations:
                    locations.append(location)
        
        return locations
    
    def _extract_contact_info_from_text(self, text: str) -> Dict[str, List[str]]:
        """Извлечение контактной информации из чистого текста"""
        contact_info = {
            'emails': [],
            'phones': [],
            'websites': []
        }
        
        # Email адреса (улучшенный паттерн для PDF)
        email_pattern = r'\b[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        # Фильтруем очевидно неправильные email
        valid_emails = []
        for email in emails:
            if not re.search(r'[\s\n\r\t]', email) and '@' in email and '.' in email.split('@')[1]:
                if email not in valid_emails:
                    valid_emails.append(email)
        contact_info['emails'] = valid_emails
        
        # Телефоны (улучшенные паттерны)
        phone_patterns = [
            r'\+\d{1,4}[\s\-\(\)]?\d{1,4}[\s\-\(\)]?\d{1,4}[\s\-\(\)]?\d{1,4}[\s\-\(\)]?\d{1,4}',
            r'\(\d{3}\)[\s\-]?\d{3}[\s\-]?\d{4}',
            r'\d{3}[\s\-\.]\d{3}[\s\-\.]\d{4}',
            r'\d{3}[\s\-\.]\d{2}[\s\-\.]\d{2}',
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            for phone in phones:
                # Очищаем от лишних символов
                clean_phone = re.sub(r'[^\d\+\(\)\-\s]', '', phone)
                if len(clean_phone) >= 7 and clean_phone not in contact_info['phones']:
                    contact_info['phones'].append(clean_phone)
        
        # Веб-сайты
        url_pattern = r'https?://[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]/[^\s]*|www\.[a-zA-Z0-9][a-zA-Z0-9.-]*[a-zA-Z0-9]'
        websites = re.findall(url_pattern, text)
        contact_info['websites'] = list(set(websites))
        
        return contact_info
    
    def _extract_academic_info_from_text(self, text: str) -> Dict[str, List[str]]:
        """Извлечение академической информации из чистого текста"""
        academic_info = {
            'degrees': [],
            'research_areas': [],
            'publications': []
        }
        
        # Ученые степени (улучшенные паттерны)
        degree_patterns = [
            r'\b(Ph\.?D\.?|PhD|Doctorate|Doctor of Philosophy)\b',
            r'\b(M\.?D\.?|Doctor of Medicine|Medical Doctor)\b',
            r'\b(M\.?S\.?|M\.?Sc\.?|Master of Science)\b',
            r'\b(B\.?S\.?|B\.?Sc\.?|Bachelor of Science)\b',
            r'\b(доктор|кандидат)\s+(наук|медицинских\s+наук|технических\s+наук)\b',
            r'\b(д\.|к\.)\s*(м\.|т\.|ф\.|х\.|б\.)\s*н\.\b',
        ]
        
        for pattern in degree_patterns:
            degrees = re.findall(pattern, text, re.IGNORECASE)
            for degree in degrees:
                degree_str = degree if isinstance(degree, str) else ' '.join(degree)
                if degree_str not in academic_info['degrees']:
                    academic_info['degrees'].append(degree_str)
        
        # Области исследований
        research_patterns = [
            r'Research interests?:\s*([^\n\r]{1,200})',
            r'Научные интересы:\s*([^\n\r]{1,200})',
            r'Fields? of study:\s*([^\n\r]{1,200})',
            r'Specialization:\s*([^\n\r]{1,200})',
        ]
        
        for pattern in research_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                research_area = match.strip()
                if research_area and research_area not in academic_info['research_areas']:
                    academic_info['research_areas'].append(research_area)
        
        return academic_info
    
    def _extract_pdf_specific_data(self, text: str, pdf_metadata: Dict) -> Dict[str, Any]:
        """Извлечение специфичных для PDF данных"""
        pdf_data = {
            'title_from_metadata': pdf_metadata.get('/Title', ''),
            'author_from_metadata': pdf_metadata.get('/Author', ''),
            'subject_from_metadata': pdf_metadata.get('/Subject', ''),
            'keywords_from_metadata': pdf_metadata.get('/Keywords', ''),
            'creation_date': pdf_metadata.get('/CreationDate', ''),
            'modification_date': pdf_metadata.get('/ModDate', ''),
            'producer': pdf_metadata.get('/Producer', ''),
            'creator': pdf_metadata.get('/Creator', ''),
        }
        
        # Ищем DOI в тексте
        doi_pattern = r'DOI:\s*([10\.\d+/[^\s]+)'
        doi_matches = re.findall(doi_pattern, text, re.IGNORECASE)
        if doi_matches:
            pdf_data['doi'] = doi_matches[0]
        
        # Ищем PMID
        pmid_pattern = r'PMID:\s*(\d+)'
        pmid_matches = re.findall(pmid_pattern, text, re.IGNORECASE)
        if pmid_matches:
            pdf_data['pmid'] = pmid_matches[0]
        
        # Ищем журнал
        journal_patterns = [
            r'Published in:\s*([^\n\r]{1,100})',
            r'Journal:\s*([^\n\r]{1,100})',
            r'Опубликовано в:\s*([^\n\r]{1,100})',
        ]
        
        for pattern in journal_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                pdf_data['journal'] = matches[0].strip()
                break
        
        # Фильтруем пустые значения
        return {k: v for k, v in pdf_data.items() if v}
        
    def identify_email_owner_in_pdf(self, content: bytes, target_email: str, url: str = "") -> Dict[str, Any]:
        """Продвинутая идентификация владельца email в PDF документе"""
        try:
            pdf_stream = io.BytesIO(content)
            extracted_text = ""
            pdf_metadata = {}
            
            # Извлекаем текст из PDF
            try:
                with pdfplumber.open(pdf_stream) as pdf:
                    logger.info(f"Анализируем PDF для поиска владельца email {target_email}")
                    
                    if hasattr(pdf, 'metadata') and pdf.metadata:
                        pdf_metadata = pdf.metadata
                    
                    # Извлекаем текст (ограничиваем анализ первыми 50 страницами для быстродействия)
                    max_pages = min(50, len(pdf.pages))
                    for i, page in enumerate(pdf.pages[:max_pages]):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                extracted_text += page_text + "\n"
                        except Exception as e:
                            logger.warning(f"Ошибка извлечения текста со страницы {i+1}: {e}")
                            continue
                            
            except Exception as e:
                logger.warning(f"Ошибка pdfplumber: {e}, пробуем PyPDF2")
                
                # Fallback к PyPDF2
                pdf_stream.seek(0)
                pdf_reader = PyPDF2.PdfReader(pdf_stream)
                
                if pdf_reader.metadata:
                    pdf_metadata = dict(pdf_reader.metadata)
                
                max_pages = min(50, len(pdf_reader.pages))
                for i in range(max_pages):
                    try:
                        page = pdf_reader.pages[i]
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += page_text + "\n"
                    except Exception as e:
                        logger.warning(f"PyPDF2: Ошибка извлечения текста со страницы {i+1}: {e}")
                        continue
            
            if not extracted_text.strip():
                return {
                    'success': False,
                    'error': 'Не удалось извлечь текст из PDF',
                    'target_email': target_email
                }
            
            # Ищем целевой email в тексте
            email_found = target_email.lower() in extracted_text.lower()
            
            if not email_found:
                return {
                    'success': False,
                    'error': f'Email {target_email} не найден в тексте PDF',
                    'target_email': target_email,
                    'text_length': len(extracted_text)
                }
            
            # Находим контексты вокруг email
            email_contexts = self._find_email_contexts(extracted_text, target_email)
            
            # Извлекаем потенциальных владельцев
            potential_owners = self._extract_potential_owners_from_contexts(email_contexts, target_email)
            
            # Анализируем весь текст для дополнительной информации
            all_names = self._extract_names_from_pdf_text(extracted_text, url or "pdf_analysis")
            all_emails = self._extract_emails_from_text(extracted_text)
            
            # Определяем наиболее вероятного владельца
            most_likely_owner, confidence = self._determine_most_likely_owner(
                potential_owners, all_names, target_email, extracted_text
            )
            
            result = {
                'success': True,
                'target_email': target_email,
                'most_likely_owner': most_likely_owner,
                'confidence_score': confidence,
                'potential_owners': potential_owners,
                'email_contexts': email_contexts,
                'all_names_found': all_names[:20],  # Ограничиваем для читаемости
                'all_emails_found': all_emails,
                'pdf_metadata': {
                    'title': pdf_metadata.get('/Title', ''),
                    'author': pdf_metadata.get('/Author', ''),
                    'subject': pdf_metadata.get('/Subject', ''),
                    'creation_date': pdf_metadata.get('/CreationDate', ''),
                },
                'text_analysis': {
                    'text_length': len(extracted_text),
                    'email_occurrences': extracted_text.lower().count(target_email.lower())
                }
            }
            
            # Если владелец найден с высокой уверенностью, добавляем дополнительную информацию
            if most_likely_owner and confidence > 0.5:
                result['owner_details'] = self._extract_owner_details(
                    most_likely_owner, extracted_text, target_email
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка идентификации владельца email в PDF: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'target_email': target_email
            }
    
    def _find_email_contexts(self, text: str, email: str, context_length: int = 300) -> List[str]:
        """Находит контексты вокруг email адреса"""
        contexts = []
        email_lower = email.lower()
        text_lower = text.lower()
        
        start = 0
        while True:
            pos = text_lower.find(email_lower, start)
            if pos == -1:
                break
            
            # Определяем границы контекста
            context_start = max(0, pos - context_length)
            context_end = min(len(text), pos + len(email) + context_length)
            
            context = text[context_start:context_end].strip()
            if context and context not in contexts:
                contexts.append(context)
            
            start = pos + len(email)
        
        return contexts
    
    def _extract_potential_owners_from_contexts(self, contexts: List[str], target_email: str) -> List[Dict[str, Any]]:
        """Извлекает потенциальных владельцев из контекстов вокруг email"""
        potential_owners = []
        
        # Улучшенные паттерны для поиска имен в контексте email
        name_patterns = [
            # Перед email: "Иван Петров (ivan.petrov@example.com)"
            r'([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]*){1,2})\s*[\(\[]?\s*' + re.escape(target_email.lower()),
            
            # После email: "ivan.petrov@example.com (Иван Петров)"
            re.escape(target_email.lower()) + r'\s*[\(\[]?\s*([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]*){1,2})',
            
            # В строке с email: "Контакт: Иван Петров ivan.petrov@example.com"
            r'([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]*){1,2})\s+' + re.escape(target_email.lower()),
            
            # Автор статьи
            r'(?:Author|Автор)[\s:]*([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]*){1,2})',
            
            # Корреспондирующий автор
            r'(?:Corresponding author|Автор для корреспонденции)[\s:]*([A-ZА-Я][a-zа-я]+(?:\s+[A-ZА-Я][a-zа-я]*){1,2})',
        ]
        
        for i, context in enumerate(contexts):
            context_owners = []
            
            for pattern in name_patterns:
                matches = re.findall(pattern, context, re.IGNORECASE)
                for match in matches:
                    name = match.strip() if isinstance(match, str) else ' '.join(match).strip()
                    if name and len(name) > 3 and not re.search(r'\d|[@\.]', name):
                        # Дополнительная фильтрация шумовых слов
                        noise_words = {
                            'abstract', 'background', 'openaccess', 'introduction', 'method', 'methods',
                            'results', 'conclusion', 'discussion', 'references', 'figure', 'table',
                            'department', 'university', 'institute', 'center', 'centre', 'laboratory',
                            'email', 'contact', 'corresponding', 'author', 'et al', 'страница', 'page'
                        }
                        
                        # Проверяем, что имя не является шумовым словом
                        name_lower = name.lower()
                        if any(noise_word in name_lower for noise_word in noise_words):
                            continue
                            
                        # Проверяем структуру имени (должно содержать хотя бы 2 слова с заглавными буквами)
                        name_parts = name.split()
                        if len(name_parts) >= 2 and all(part[0].isupper() for part in name_parts if len(part) > 1):
                            context_owners.append({
                                'name': name,
                                'context_index': i,
                                'extraction_method': 'context_pattern',
                                'pattern_type': 'email_context'
                            })
            
            potential_owners.extend(context_owners)
        
        # Удаляем дубликаты
        unique_owners = []
        seen_names = set()
        for owner in potential_owners:
            if owner['name'].lower() not in seen_names:
                seen_names.add(owner['name'].lower())
                unique_owners.append(owner)
        
        return unique_owners
    
    def _extract_emails_from_text(self, text: str) -> List[str]:
        """Извлекает все email адреса из текста"""
        email_pattern = r'\b[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}\b'
        emails = re.findall(email_pattern, text)
        
        # Фильтруем и очищаем
        valid_emails = []
        for email in emails:
            if '@' in email and '.' in email.split('@')[1] and len(email) > 5:
                if email not in valid_emails:
                    valid_emails.append(email)
        
        return valid_emails
    
    def _determine_most_likely_owner(self, potential_owners: List[Dict], all_names: List[str], 
                                   target_email: str, full_text: str) -> tuple:
        """Определяет наиболее вероятного владельца email с улучшенной поддержкой русских имен"""
        if not potential_owners:
            return None, 0.0
        
        # Система скоринга для каждого потенциального владельца
        scored_owners = []
        email_local = target_email.split('@')[0].lower()
        email_domain = target_email.split('@')[1].lower() if '@' in target_email else ''
        
        for owner in potential_owners:
            name = owner['name']
            score = 0.0
            
            # Базовый балл за наличие в контексте email
            score += 0.4
            
            # Проверяем, является ли имя русским (содержит кириллицу)
            is_russian_name = bool(re.search(r'[А-Яа-я]', name))
            is_full_russian_name = False
            
            if is_russian_name:
                # Дополнительный бонус за русские имена
                score += 0.15
                
                # Проверяем, является ли это полным русским именем (Фамилия Имя Отчество)
                russian_name_parts = name.split()
                if len(russian_name_parts) >= 3:
                    # Проверяем паттерн: все части начинаются с заглавной и содержат кириллицу
                    if all(part[0].isupper() and re.search(r'[А-Яа-я]', part) for part in russian_name_parts):
                        is_full_russian_name = True
                        score += 0.25  # Большой бонус за полное русское ФИО
                elif len(russian_name_parts) == 2:
                    # Бонус за русское имя из двух частей
                    if all(part[0].isupper() and re.search(r'[А-Яа-я]', part) for part in russian_name_parts):
                        score += 0.15
            
            # Штраф за организационные названия
            org_indicators = [
                'center', 'centre', 'центр', 'clinic', 'клиника', 'hospital', 'больница',
                'university', 'университет', 'institute', 'институт', 'laboratory', 'лаборатория',
                'department', 'департамент', 'отдел', 'service', 'сервис', 'company', 'компания',
                'organization', 'организация', 'foundation', 'фонд', 'society', 'общество',
                'diagnostic', 'диагностический', 'medical', 'медицинский', 'clinical', 'клинический'
            ]
            
            name_lower = name.lower()
            if any(indicator in name_lower for indicator in org_indicators):
                score -= 0.4  # Значительный штраф за организационные названия
            
            # Дополнительные баллы за соответствие email
            name_parts = [part.lower() for part in name.split() if len(part) > 1]
            
            # Проверяем прямое совпадение
            for part in name_parts:
                if part in email_local:
                    score += 0.3
                elif fuzz.partial_ratio(part, email_local) > 80:
                    score += 0.2
            
            # Для русских имен: проверяем транслитерацию
            if is_russian_name:
                transliteration_bonus = self._check_transliteration_match(name, email_local)
                score += transliteration_bonus
            
            # Бонус за соответствие русского домена
            if is_russian_name and any(domain in email_domain for domain in ['.ru', 'mail.ru', 'yandex.ru', 'rambler.ru']):
                score += 0.1
            
            # Баллы за частоту встречаемости в тексте
            name_count = full_text.lower().count(name.lower())
            if name_count > 1:
                score += min(0.2, name_count * 0.05)
            
            # Баллы за то, что имя есть в общем списке найденных имен
            if any(fuzz.ratio(name.lower(), found_name.lower()) > 85 for found_name in all_names):
                score += 0.1
            
            # Штраф за слишком общие имена (если это не полное русское ФИО)
            if len(name.split()) < 2 and not is_full_russian_name:
                score -= 0.2
            
            # Дополнительный штраф за односложные организационные названия
            if len(name.split()) == 1 and len(name) > 10 and not is_russian_name:
                score -= 0.3
            
            scored_owners.append((name, min(score, 1.0)))
        
        if scored_owners:
            # Сортируем по убыванию скора
            scored_owners.sort(key=lambda x: x[1], reverse=True)
            return scored_owners[0][0], scored_owners[0][1]
        
        return None, 0.0
    
    def _check_transliteration_match(self, russian_name: str, email_local: str) -> float:
        """Проверяет соответствие между русским именем и его транслитерацией в email"""
        if not re.search(r'[А-Яа-я]', russian_name):
            return 0.0
        
        # Таблица транслитерации (русский -> латиница)
        transliteration_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
            'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
            'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
        }
        
        # Альтернативные варианты транслитерации
        alt_transliteration = {
            'ж': 'j', 'х': 'h', 'ц': 'c', 'ч': 'c', 'ш': 's', 'щ': 's', 'ю': 'u', 'я': 'a'
        }
        
        name_parts = russian_name.lower().split()
        total_bonus = 0.0
        matches_found = 0
        
        for part in name_parts:
            if len(part) < 2:
                continue
                
            # Основная транслитерация
            transliterated = ''.join(transliteration_map.get(char, char) for char in part)
            
            # Альтернативная транслитерация
            alt_transliterated = part
            for ru_char, alt_char in alt_transliteration.items():
                alt_transliterated = alt_transliterated.replace(ru_char, alt_char)
            alt_transliterated = ''.join(transliteration_map.get(char, char) for char in alt_transliterated)
            
            # Проверяем различные варианты совпадений
            variants = [transliterated, alt_transliterated]
            
            # Добавляем варианты с удаленными гласными (часто используется в email)
            vowels = 'aeiou'
            for variant in variants[:]:
                no_vowels = ''.join(char for char in variant if char not in vowels)
                if len(no_vowels) >= 2:
                    variants.append(no_vowels)
            
            # Проверяем совпадения
            for variant in variants:
                if len(variant) >= 3:
                    if variant in email_local:
                        total_bonus += 0.3
                        matches_found += 1
                        break
                    elif fuzz.partial_ratio(variant, email_local) > 85:
                        total_bonus += 0.2
                        matches_found += 1
                        break
                    elif variant[:3] in email_local or variant[-3:] in email_local:
                        total_bonus += 0.1
                        matches_found += 1
                        break
        
        # Бонус за несколько совпадений (указывает на полное ФИО)
        if matches_found >= 2:
            total_bonus += 0.15
        elif matches_found >= 3:
            total_bonus += 0.25
        
        return min(total_bonus, 0.5)  # Максимум 0.5 балла за транслитерацию
    
    def _extract_owner_details(self, owner_name: str, text: str, email: str) -> Dict[str, Any]:
        """Извлекает дополнительные детали о владельце"""
        details = {
            'positions': [],
            'organizations': [],
            'locations': [],
            'additional_emails': [],
            'context_summary': ''
        }
        
        # Ищем контекст вокруг имени владельца
        name_contexts = self._find_email_contexts(text, owner_name, 400)
        
        if name_contexts:
            # Объединяем контексты для анализа
            combined_context = ' '.join(name_contexts)
            details['context_summary'] = combined_context[:500] + '...' if len(combined_context) > 500 else combined_context
            
            # Извлекаем должности из контекста
            details['positions'] = self._extract_positions_from_text(combined_context)
            
            # Извлекаем организации
            details['organizations'] = self._extract_organizations_from_text(combined_context)
            
            # Извлекаем локации
            details['locations'] = self._extract_locations_from_text(combined_context)
            
            # Ищем дополнительные email адреса рядом с именем
            additional_emails = self._extract_emails_from_text(combined_context)
            details['additional_emails'] = [e for e in additional_emails if e.lower() != email.lower()]
        
        return details
    
    def _analyze_url_relevance(self, search_results: List[Dict], email: str) -> List[Dict]:
        """
        Анализирует релевантность URLs для поиска информации о конкретном email
        
        Args:
            search_results: Список результатов поиска
            email: Email адрес для поиска
            
        Returns:
            Список результатов с добавленными метриками релевантности
        """
        analyzed_results = []
        
        for result in search_results:
            url = result.get('url', '')
            title = result.get('title', '').lower()
            snippet = result.get('snippet', '').lower()
            
            relevance_score = 0.0
            relevance_reasons = []
            
            # === АНАЛИЗ НА НАЛИЧИЕ EMAIL ===
            combined_text = f"{title} {snippet} {url}".lower()
            
            # Проверяем точное совпадение email
            if email.lower() in combined_text:
                relevance_score += 0.8
                relevance_reasons.append('Точное совпадение email')
            
            # Проверяем домен email
            if '@' in email:
                domain = email.split('@')[1].lower()
                if domain in combined_text:
                    relevance_score += 0.3
                    relevance_reasons.append(f'Совпадение домена: {domain}')
            
            # Проверяем username email
            if '@' in email:
                username = email.split('@')[0].lower()
                if len(username) > 3 and username in combined_text:
                    relevance_score += 0.2
                    relevance_reasons.append(f'Совпадение username: {username}')
            
            # === КОНТЕКСТУАЛЬНАЯ РЕЛЕВАНТНОСТЬ ===
            
            # Личные профили или страницы
            personal_indicators = [
                'profile', 'профиль', 'about', 'biography', 'cv', 'resume',
                'contact', 'контакт', 'person', 'персона'
            ]
            
            personal_count = sum(1 for indicator in personal_indicators if indicator in combined_text)
            if personal_count > 0:
                relevance_score += min(0.3, personal_count * 0.1)
                relevance_reasons.append(f'Личная информация ({personal_count} индикаторов)')
            
            # Профессиональная информация
            professional_indicators = [
                'author', 'автор', 'researcher', 'исследователь',
                'scientist', 'ученый', 'faculty', 'преподаватель',
                'staff', 'сотрудник', 'employee', 'работник'
            ]
            
            professional_count = sum(1 for indicator in professional_indicators if indicator in combined_text)
            if professional_count > 0:
                relevance_score += min(0.2, professional_count * 0.08)
                relevance_reasons.append(f'Профессиональная информация ({professional_count} индикаторов)')
            
            # === КАЧЕСТВО ИСТОЧНИКА ===
            
            # Официальные сайты учреждений
            institutional_domains = [
                '.edu', '.ac.', 'university', 'institute', 'academy',
                'college', 'school', 'research', 'org'
            ]
            
            institutional_count = sum(1 for domain in institutional_domains if domain in url.lower())
            if institutional_count > 0:
                relevance_score += 0.1
                relevance_reasons.append('Институциональный домен')
            
            # === ФИНАЛЬНАЯ ОБРАБОТКА ===
            
            # Ограничиваем максимальный скор
            relevance_score = min(relevance_score, 1.0)
            relevance_score = max(relevance_score, 0.0)
            
            # Создаем результат с метриками релевантности
            analyzed_result = result.copy()
            analyzed_result['relevance_score'] = relevance_score
            analyzed_result['relevance_reasons'] = relevance_reasons
            
            analyzed_results.append(analyzed_result)
        
        # Сортируем по убыванию релевантности
        analyzed_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Логируем топ-5 результатов для отладки
        logger.info(f"Топ-5 релевантных результатов для email {email}:")
        for i, result in enumerate(analyzed_results[:5], 1):
            score = result.get('relevance_score', 0)
            url = result.get('url', '')[:60] + '...' if len(result.get('url', '')) > 60 else result.get('url', '')
            reasons = ', '.join(result.get('relevance_reasons', [])[:2])  # Первые 2 причины
            logger.info(f"  {i}. Релевантность: {score:.3f} | {url} | {reasons}")
        
        return analyzed_results
    
    def _get_target_email_from_metadata(self, analyzed_data: Dict[str, Any]) -> Optional[str]:
        """Извлекает целевой email из метаданных анализа"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Приоритизируем сохраненный контекстный email
        if hasattr(self, '_current_target_email') and self._current_target_email:
            logger.info(f"📧 Используем сохраненный целевой email: {self._current_target_email}")
            return self._current_target_email
        
        # Ищем email в метаданных анализа
        for url_metadata in analyzed_data.get('analysis_metadata', {}).get('analyzed_urls', []):
            if 'email_context' in url_metadata:
                email_from_metadata = url_metadata.get('email_context')
                logger.info(f"📧 Найден email в метаданных: {email_from_metadata}")
                return email_from_metadata
        
        # НЕ ИСПОЛЬЗУЕМ email из контактной информации, так как там может быть любой email
        # Если нет сохраненного целевого email, возвращаем None
        logger.warning("⚠️ Целевой email не найден ни в контексте, ни в метаданных")
        return None
    
    def _calculate_context_score(self, name: str, analyzed_data: Dict[str, Any], target_email: Optional[str]) -> float:
        """Рассчитывает скор на основе контекста вокруг имени"""
        score = 0.0
        context_details = []
        
        # Проверяем, есть ли имя в профессиональных деталях
        professional_details = analyzed_data.get('professional_details', {})
        
        # Бонус, если имя встречается в контексте организаций
        organizations = professional_details.get('organizations', [])
        for org in organizations:
            if name.lower() in org.lower():
                score += 0.3
                context_details.append(f"в организации: {org[:50]}")
                break
        
        # Бонус, если имя встречается в контексте позиций
        positions = professional_details.get('positions', [])
        for pos in positions:
            if name.lower() in pos.lower():
                score += 0.2
                context_details.append(f"в должности: {pos[:50]}")
                break
        
        # Бонус за академическую информацию
        academic_info = analyzed_data.get('academic_info', {})
        research_areas = academic_info.get('research_areas', [])
        for area in research_areas:
            if name.lower() in area.lower():
                score += 0.1
                context_details.append(f"в исследованиях: {area[:50]}")
                break
        
        # Дополнительный бонус, если имя встречается в нескольких контекстах
        contexts_count = 0
        all_text_fields = [
            str(analyzed_data.get('professional_details', {})),
            str(analyzed_data.get('academic_info', {})),
            str(analyzed_data.get('contact_information', {}))
        ]
        
        for text in all_text_fields:
            if name.lower() in text.lower():
                contexts_count += 1
        
        if contexts_count >= 2:
            score += 0.15
            context_details.append(f"в {contexts_count} контекстах")
        elif contexts_count >= 3:
            score += 0.25
            context_details.append(f"в {contexts_count} контекстах")
        
        if context_details:
            logger.debug(f"🎯 Контекстный анализ '{name}': {'; '.join(context_details)}")
        
        return min(score, 1.0)
    
    def _calculate_email_match_score(self, name: str, email: str) -> float:
        """Рассчитывает скор соответствия имени и email адреса"""
        if not email or '@' not in email:
            return 0.0
        
        score = 0.0
        email_local = email.split('@')[0].lower()
        name_lower = name.lower()
        name_parts = [part.strip() for part in name_lower.split() if len(part) > 1]
        match_details = []
        
        # Прямое совпадение частей имени с локальной частью email
        for part in name_parts:
            if len(part) >= 3:
                if part in email_local:
                    score += 0.4
                    match_details.append(f"прямое совпадение '{part}'")
                elif fuzz.partial_ratio(part, email_local) > 85:
                    score += 0.3
                    match_details.append(f"частичное совпадение '{part}'")
                elif part[:3] in email_local or part[-3:] in email_local:
                    score += 0.1
                    match_details.append(f"частичное совпадение начала/конца '{part}'")
        
        # Специальная обработка для русских имен
        if re.search(r'[А-Яа-я]', name):
            transliteration_score = self._check_transliteration_match(name, email_local)
            if transliteration_score > 0:
                score += transliteration_score
                match_details.append(f"транслитерация (+{transliteration_score:.2f})")
        
        # Улучшенная проверка инициалов и производных форм
        if len(name_parts) >= 2:
            # Стандартные инициалы (первые буквы)
            initials = ''.join([part[0] for part in name_parts[:3]])  # Первые буквы имени
            if initials.lower() in email_local:
                score += 0.2
                match_details.append(f"инициалы '{initials}'")
            
            # Специальная обработка для случаев типа "Марапов Дамир" -> "damirov"
            # Проверяем производные формы имени (например, Дамир -> Damir -> damirov)
            for i, part in enumerate(name_parts):
                if len(part) >= 4:
                    # Проверяем возможные производные формы
                    derived_forms = [
                        part,  # исходная форма
                        part + 'ov',  # добавление 'ov' (русская фамилия -> email)
                        part + 'ova',  # женская форма
                        part + 'in',   # другой тип русских фамилий
                        part + 'ina',  # женская форма
                        part + 'ski',  # польские фамилии
                        part + 'sky',  # альтернативная транслитерация
                    ]
                    
                    for form in derived_forms:
                        if form.lower() in email_local or email_local in form.lower():
                            score += 0.35
                            match_details.append(f"производная форма '{form}' от '{part}'")
                            break
            
            # Проверка для имени "Дамир" -> "damir" -> "damirov"
            if len(name_parts) >= 2:
                # Берем имя (обычно второе слово в русских ФИО)
                first_name = name_parts[1] if len(name_parts) >= 2 else name_parts[0]
                if len(first_name) >= 3:
                    # Транслитерируем имя и проверяем различные формы
                    transliterated_name = self._transliterate_name(first_name)
                    if transliterated_name:
                        forms_to_check = [
                            transliterated_name,
                            transliterated_name + 'ov',
                            transliterated_name + 'ova'
                        ]
                        
                        for form in forms_to_check:
                            if form.lower() == email_local or form.lower() in email_local:
                                score += 0.5  # Высокий бонус за точное соответствие
                                match_details.append(f"транслитерированная форма имени '{form}' от '{first_name}'")
                                break
                            elif fuzz.ratio(form.lower(), email_local) > 80:
                                score += 0.3
                                match_details.append(f"близкая транслитерированная форма '{form}' от '{first_name}'")
                                break
        
        if match_details:
            logger.debug(f"📧 Email соответствие '{name}' <-> '{email_local}': {'; '.join(match_details)}")
        
        return min(score, 1.0)
    
    def _transliterate_name(self, russian_name: str) -> str:
        """Транслитерирует русское имя в латиницу"""
        transliteration_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
            'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
            'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            # Альтернативные варианты для простоты
            'ж': 'j', 'х': 'h', 'ц': 'c', 'ч': 'c', 'ш': 's', 'щ': 's', 'ю': 'u', 'я': 'a'
        }
        
        result = ""
        for char in russian_name.lower():
            if char in transliteration_map:
                result += transliteration_map[char]
            else:
                result += char
        
        return result
    
    def close(self):
        """Закрытие сессии"""
        if self.session:
            self.session.close()
