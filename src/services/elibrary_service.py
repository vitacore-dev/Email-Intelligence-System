"""
Сервис для автоматизации поиска публикаций на elibrary.ru
"""

import requests
import time
import re
import json
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from urllib.parse import quote, unquote
import logging

logger = logging.getLogger(__name__)

class ElibraryService:
    """Сервис для поиска публикаций на elibrary.ru"""
    
    def __init__(self, demo_mode=False):
        self.base_url = "https://elibrary.ru"
        self.demo_mode = demo_mode
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })
        # Добавляем таймауты и retry логику
        adapter = requests.adapters.HTTPAdapter(max_retries=3)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        if not self.demo_mode:
            self._initialize_session()
        else:
            logger.info("Инициализирован демо-режим elibrary сервиса")
    
    def _initialize_session(self):
        """Инициализация сессии с получением главной страницы"""
        try:
            response = self.session.get(f"{self.base_url}/defaultx.asp")
            response.raise_for_status()
            logger.info("Сессия elibrary.ru успешно инициализирована")
        except requests.RequestException as e:
            logger.error(f"Ошибка инициализации сессии elibrary.ru: {e}")
    
    def search_by_email(self, email: str, search_options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Поиск публикаций по email адресу
        
        Args:
            email: Email адрес для поиска
            search_options: Дополнительные опции поиска
            
        Returns:
            Словарь с результатами поиска
        """
        if not email or "@" not in email:
            return {"error": "Некорректный email адрес", "publications": []}
        
        # Если включен демо-режим, возвращаем тестовые данные
        if self.demo_mode:
            return self._generate_demo_data(email)
        
        # Извлекаем части email для поиска
        local_part, domain = email.split("@", 1)
        
        # Варианты поиска
        search_variants = [
            email,  # Полный email
            local_part,  # Только локальная часть
            domain,  # Только домен
            email.replace("@", " "),  # Email с пробелом вместо @
        ]
        
        all_results = {
            "email": email,
            "publications": [],
            "search_summary": {
                "total_found": 0,
                "search_variants_used": len(search_variants),
                "successful_searches": 0
            }
        }
        
        for variant in search_variants:
            try:
                logger.info(f"Поиск по варианту: {variant}")
                results = self._perform_search(variant, search_options)
                
                if results and results.get("publications"):
                    all_results["publications"].extend(results["publications"])
                    all_results["search_summary"]["successful_searches"] += 1
                    
                # Задержка между запросами для соблюдения этики
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка поиска по варианту {variant}: {e}")
                continue
        
        # Удаляем дубликаты
        all_results["publications"] = self._remove_duplicates(all_results["publications"])
        all_results["search_summary"]["total_found"] = len(all_results["publications"])
        
        return all_results
    
    def _perform_search(self, query: str, search_options: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Выполнение поиска на elibrary.ru
        
        Args:
            query: Поисковый запрос
            search_options: Опции поиска
            
        Returns:
            Результаты поиска
        """
        # Параметры поиска по умолчанию
        default_params = {
            'ftext': query,
            'where_fulltext': 'on',
            'where_name': 'on',
            'where_abstract': 'on',
            'where_keywords': 'on',
            'where_affiliation': 'on',
            'type_article': 'on',
            'type_disser': 'on',
            'type_book': 'on',
            'type_conf': 'on',
            'search_morph': 'on',
            'begin_year': '2000',  # Ограничиваем поиск последними годами
            'end_year': '2024'
        }
        
        # Применяем пользовательские опции
        if search_options:
            default_params.update(search_options)
        
        try:
            # Выполняем POST запрос к поисковой системе
            response = self.session.post(
                f"{self.base_url}/query_results.asp",
                data=default_params,
                timeout=30
            )
            response.raise_for_status()
            
            # Парсим результаты
            return self._parse_search_results(response.text, query)
            
        except requests.RequestException as e:
            logger.error(f"Ошибка HTTP запроса: {e}")
            return {"error": str(e), "publications": []}
        except Exception as e:
            logger.error(f"Ошибка парсинга результатов: {e}")
            return {"error": str(e), "publications": []}
    
    def _parse_search_results(self, html_content: str, query: str) -> Dict[str, Any]:
        """
        Парсинг HTML результатов поиска
        
        Args:
            html_content: HTML содержимое страницы результатов
            query: Исходный поисковый запрос
            
        Returns:
            Структурированные результаты
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        publications = []
        
        # Ищем блоки с результатами поиска
        # На elibrary.ru результаты обычно в таблицах или div с определенными классами
        result_blocks = soup.find_all(['tr', 'div'], class_=re.compile(r'(row|result|item)', re.I))
        
        if not result_blocks:
            # Альтернативный поиск структур
            result_blocks = soup.find_all('table')
        
        for block in result_blocks:
            try:
                publication = self._extract_publication_data(block, query)
                if publication and publication.get('title'):
                    publications.append(publication)
            except Exception as e:
                logger.debug(f"Ошибка извлечения данных публикации: {e}")
                continue
        
        # Если стандартный парсинг не сработал, пробуем извлечь любые ссылки на публикации
        if not publications:
            publications = self._fallback_parse(soup, query)
        
        return {
            "query": query,
            "publications": publications,
            "total_found": len(publications)
        }
    
    def _extract_publication_data(self, block, query: str) -> Optional[Dict[str, Any]]:
        """
        Извлечение данных о публикации из HTML блока
        
        Args:
            block: HTML элемент с данными публикации
            query: Поисковый запрос для контекста
            
        Returns:
            Словарь с данными публикации или None
        """
        publication = {
            "title": "",
            "authors": [],
            "source": "",
            "year": "",
            "abstract": "",
            "url": "",
            "type": "",
            "relevance_score": 0,
            "search_context": query
        }
        
        # Извлекаем заголовок
        title_elem = block.find(['a', 'b', 'strong'], href=re.compile(r'item_id=\d+', re.I))
        if not title_elem:
            title_elem = block.find(['b', 'strong'])
        if title_elem:
            publication["title"] = title_elem.get_text(strip=True)
            if title_elem.get('href'):
                publication["url"] = self.base_url + title_elem['href'] if title_elem['href'].startswith('/') else title_elem['href']
        
        # Извлекаем авторов
        author_patterns = [
            r'Авторы?:\s*([^\.]+)',
            r'Автор:\s*([^\.]+)',
            r'([А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.[А-ЯЁ]\.)',
        ]
        
        text_content = block.get_text()
        for pattern in author_patterns:
            authors_match = re.search(pattern, text_content)
            if authors_match:
                authors_text = authors_match.group(1)
                # Разделяем авторов по запятым или точкам с запятой
                authors = [author.strip() for author in re.split('[,;]', authors_text)]
                publication["authors"] = [auth for auth in authors if auth and len(auth) > 2]
                break
        
        # Извлекаем источник/журнал
        source_patterns = [
            r'Журнал:\s*([^\.]+)',
            r'Источник:\s*([^\.]+)',
            r'В книге:\s*([^\.]+)',
        ]
        
        for pattern in source_patterns:
            source_match = re.search(pattern, text_content)
            if source_match:
                publication["source"] = source_match.group(1).strip()
                break
        
        # Извлекаем год
        year_match = re.search(r'(\d{4})', text_content)
        if year_match:
            publication["year"] = year_match.group(1)
        
        # Извлекаем аннотацию (если есть)
        abstract_elem = block.find(text=re.compile(r'(аннотация|abstract)', re.I))
        if abstract_elem:
            # Ищем текст после ключевого слова
            parent = abstract_elem.parent
            if parent:
                abstract_text = parent.get_text()
                abstract_start = abstract_text.lower().find('аннотация')
                if abstract_start > -1:
                    publication["abstract"] = abstract_text[abstract_start:abstract_start+200] + "..."
        
        # Определяем тип публикации
        if 'диссертация' in text_content.lower():
            publication["type"] = "dissertation"
        elif 'конференция' in text_content.lower():
            publication["type"] = "conference"
        elif 'книга' in text_content.lower():
            publication["type"] = "book"
        else:
            publication["type"] = "article"
        
        # Вычисляем релевантность
        publication["relevance_score"] = self._calculate_relevance(publication, query)
        
        return publication if publication["title"] else None
    
    def _fallback_parse(self, soup, query: str) -> List[Dict[str, Any]]:
        """
        Резервный парсинг для извлечения любых найденных публикаций
        
        Args:
            soup: BeautifulSoup объект
            query: Поисковый запрос
            
        Returns:
            Список найденных публикаций
        """
        publications = []
        
        # Ищем все ссылки, которые могут быть публикациями
        links = soup.find_all('a', href=re.compile(r'item_id=\d+'))
        
        for link in links:
            try:
                publication = {
                    "title": link.get_text(strip=True),
                    "url": self.base_url + link['href'] if link['href'].startswith('/') else link['href'],
                    "authors": [],
                    "source": "",
                    "year": "",
                    "abstract": "",
                    "type": "unknown",
                    "relevance_score": 1,
                    "search_context": query
                }
                
                # Пытаемся извлечь дополнительную информацию из окружающего контекста
                parent = link.parent
                if parent:
                    parent_text = parent.get_text()
                    
                    # Извлекаем год из контекста
                    year_match = re.search(r'(\d{4})', parent_text)
                    if year_match:
                        publication["year"] = year_match.group(1)
                
                if publication["title"] and len(publication["title"]) > 10:
                    publications.append(publication)
                    
            except Exception as e:
                logger.debug(f"Ошибка в fallback парсинге: {e}")
                continue
        
        return publications[:20]  # Ограничиваем количество результатов
    
    def _calculate_relevance(self, publication: Dict[str, Any], query: str) -> float:
        """
        Вычисление релевантности публикации к поисковому запросу
        
        Args:
            publication: Данные публикации
            query: Поисковый запрос
            
        Returns:
            Оценка релевантности от 0 до 10
        """
        score = 0.0
        query_lower = query.lower()
        
        # Проверяем наличие запроса в заголовке
        if query_lower in publication.get("title", "").lower():
            score += 3.0
        
        # Проверяем наличие в авторах
        for author in publication.get("authors", []):
            if query_lower in author.lower():
                score += 2.0
                break
        
        # Проверяем наличие в источнике
        if query_lower in publication.get("source", "").lower():
            score += 1.0
        
        # Проверяем наличие в аннотации
        if query_lower in publication.get("abstract", "").lower():
            score += 1.5
        
        # Бонус за недавние публикации
        try:
            year = int(publication.get("year", "0"))
            if year >= 2020:
                score += 1.0
            elif year >= 2015:
                score += 0.5
        except ValueError:
            pass
        
        return min(score, 10.0)  # Максимальная оценка 10
    
    def _remove_duplicates(self, publications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Удаление дубликатов публикаций
        
        Args:
            publications: Список публикаций
            
        Returns:
            Список уникальных публикаций
        """
        seen_titles = set()
        unique_publications = []
        
        for pub in publications:
            title = pub.get("title", "").strip().lower()
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique_publications.append(pub)
        
        # Сортируем по релевантности
        unique_publications.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return unique_publications
    
    def get_publication_details(self, publication_url: str) -> Optional[Dict[str, Any]]:
        """
        Получение детальной информации о публикации
        
        Args:
            publication_url: URL публикации
            
        Returns:
            Детальная информация о публикации
        """
        try:
            response = self.session.get(publication_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            details = {
                "full_text_available": False,
                "doi": "",
                "keywords": [],
                "citation_count": 0,
                "full_abstract": "",
                "references": []
            }
            
            # Ищем DOI
            doi_elem = soup.find(text=re.compile(r'DOI:', re.I))
            if doi_elem:
                doi_text = doi_elem.parent.get_text() if doi_elem.parent else ""
                doi_match = re.search(r'DOI:\s*([\d\.\/\w-]+)', doi_text)
                if doi_match:
                    details["doi"] = doi_match.group(1)
            
            # Ищем ключевые слова
            keywords_elem = soup.find(text=re.compile(r'ключевые слова', re.I))
            if keywords_elem:
                keywords_text = keywords_elem.parent.get_text() if keywords_elem.parent else ""
                # Извлекаем ключевые слова после "Ключевые слова:"
                keywords_match = re.search(r'ключевые слова[:\s]*([^\.]+)', keywords_text, re.I)
                if keywords_match:
                    keywords = [kw.strip() for kw in keywords_match.group(1).split(',')]
                    details["keywords"] = [kw for kw in keywords if kw]
            
            # Ищем количество цитирований
            citations_elem = soup.find(text=re.compile(r'цитирован', re.I))
            if citations_elem:
                citations_text = citations_elem.parent.get_text() if citations_elem.parent else ""
                citations_match = re.search(r'(\d+)', citations_text)
                if citations_match:
                    details["citation_count"] = int(citations_match.group(1))
            
            return details
            
        except Exception as e:
            logger.error(f"Ошибка получения деталей публикации: {e}")
            return None
    
    def format_results_for_visualization(self, search_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Форматирование результатов для визуализации в разделе публикаций
        
        Args:
            search_results: Результаты поиска
            
        Returns:
            Отформатированные данные для визуализации
        """
        publications = search_results.get("publications", [])
        
        # Статистика по годам
        years_stats = {}
        for pub in publications:
            year = pub.get("year", "Unknown")
            years_stats[year] = years_stats.get(year, 0) + 1
        
        # Статистика по типам
        types_stats = {}
        for pub in publications:
            pub_type = pub.get("type", "unknown")
            types_stats[pub_type] = types_stats.get(pub_type, 0) + 1
        
        # Топ авторов
        all_authors = []
        for pub in publications:
            all_authors.extend(pub.get("authors", []))
        
        authors_stats = {}
        for author in all_authors:
            authors_stats[author] = authors_stats.get(author, 0) + 1
        
        top_authors = sorted(authors_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Сортируем публикации по релевантности
        sorted_publications = sorted(publications, key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return {
            "email": search_results.get("email", ""),
            "summary": {
                "total_publications": len(publications),
                "years_range": f"{min(years_stats.keys(), default='N/A')} - {max(years_stats.keys(), default='N/A')}",
                "most_productive_year": max(years_stats.items(), key=lambda x: x[1])[0] if years_stats else "N/A",
                "primary_type": max(types_stats.items(), key=lambda x: x[1])[0] if types_stats else "N/A"
            },
            "statistics": {
                "by_year": years_stats,
                "by_type": types_stats,
                "top_authors": dict(top_authors)
            },
            "publications": sorted_publications[:50],  # Ограничиваем для визуализации
            "search_info": search_results.get("search_summary", {}),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def _generate_demo_data(self, email: str) -> Dict[str, Any]:
        """
        Генерация демо-данных для тестирования интеграции
        
        Args:
            email: Email адрес для которого генерируются данные
            
        Returns:
            Сгенерированные тестовые данные
        """
        logger.info(f"Генерация демо-данных для email: {email}")
        
        # Получаем локальную часть email для персонализации
        local_part = email.split("@")[0] if "@" in email else email
        
        # Базовые демо-публикации
        demo_publications = [
            {
                "title": f"Исследование методов машинного обучения в обработке данных ({local_part})",
                "authors": [f"{local_part.capitalize()} А.И.", "Иванов П.С.", "Петров В.К."],
                "source": "Журнал вычислительной математики и математической физики",
                "year": "2023",
                "abstract": "В данной работе рассматриваются современные методы машинного обучения...",
                "url": f"https://elibrary.ru/item.asp?id=123456{hash(email) % 1000}",
                "type": "article",
                "relevance_score": 8.5,
                "search_context": email
            },
            {
                "title": f"Анализ алгоритмов глубокого обучения для задач классификации",
                "authors": [f"{local_part.capitalize()} А.И.", "Сидоров К.М."],
                "source": "Известия высших учебных заведений. Приборостроение",
                "year": "2022",
                "abstract": "Статья посвящена сравнительному анализу различных архитектур нейронных сетей...",
                "url": f"https://elibrary.ru/item.asp?id=234567{hash(email) % 1000}",
                "type": "article",
                "relevance_score": 7.8,
                "search_context": email
            },
            {
                "title": f"Применение технологий искусственного интеллекта в медицине",
                "authors": ["Козлов Д.В.", f"{local_part.capitalize()} А.И.", "Морозов С.П."],
                "source": "Медицинская техника",
                "year": "2023",
                "abstract": "Обзор современных подходов к использованию ИИ в диагностике...",
                "url": f"https://elibrary.ru/item.asp?id=345678{hash(email) % 1000}",
                "type": "article",
                "relevance_score": 7.2,
                "search_context": email
            },
            {
                "title": f"Разработка системы автоматического анализа текстов на русском языке",
                "authors": [f"{local_part.capitalize()} А.И."],
                "source": "Программирование",
                "year": "2021",
                "abstract": "Представлена система обработки естественного языка...",
                "url": f"https://elibrary.ru/item.asp?id=456789{hash(email) % 1000}",
                "type": "article",
                "relevance_score": 6.9,
                "search_context": email
            },
            {
                "title": f"Методы оптимизации в задачах больших данных",
                "authors": ["Федоров М.А.", f"{local_part.capitalize()} А.И.", "Белов Н.К.", "Зайцев Р.Л."],
                "source": "Прикладная математика и механика",
                "year": "2022",
                "abstract": "Исследуются эффективные алгоритмы обработки больших объемов данных...",
                "url": f"https://elibrary.ru/item.asp?id=567890{hash(email) % 1000}",
                "type": "article",
                "relevance_score": 6.5,
                "search_context": email
            },
            {
                "title": f"Конференция по информационным технологиям и искусственному интеллекту",
                "authors": [f"{local_part.capitalize()} А.И.", "Орлов В.В."],
                "source": "Материалы международной конференции ИТиИИ-2023",
                "year": "2023",
                "abstract": "Доклад представляет новые подходы к решению задач ИИ...",
                "url": f"https://elibrary.ru/item.asp?id=678901{hash(email) % 1000}",
                "type": "conference",
                "relevance_score": 5.8,
                "search_context": email
            }
        ]
        
        # Добавляем вариативность в зависимости от email
        if "list.ru" in email:
            demo_publications.append({
                "title": "Исследование российских научных баз данных",
                "authors": [f"{local_part.capitalize()} А.И.", "Соколов П.И."],
                "source": "Научно-техническая информация",
                "year": "2023",
                "abstract": "Анализ современного состояния российских научных ресурсов...",
                "url": f"https://elibrary.ru/item.asp?id=789012{hash(email) % 1000}",
                "type": "article",
                "relevance_score": 6.2,
                "search_context": email
            })
        
        return {
            "email": email,
            "publications": demo_publications,
            "search_summary": {
                "total_found": len(demo_publications),
                "search_variants_used": 4,
                "successful_searches": 3
            }
        }
