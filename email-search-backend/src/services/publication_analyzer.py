#!/usr/bin/env python3
"""
Сервис для глубокого анализа публикаций автора
Фаза 4.2: Методика анализа публикаций
"""

import re
import requests
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class PublicationAnalyzer:
    """Сервис для глубокого анализа публикаций автора"""
    
    def __init__(self):
        """Инициализация анализатора публикаций"""
        self.scopus_api_key = self._get_api_key('SCOPUS_API_KEY')
        self.pubmed_api_key = self._get_api_key('PUBMED_API_KEY')
        self.crossref_api_key = self._get_api_key('CROSSREF_API_KEY')
        
        # Настройки анализа
        self.max_publications_to_analyze = 50
        self.analysis_timeout = 30  # секунд на одну публикацию
        
        # Инициализируем кэш для метаданных
        self.metadata_cache = {}
        
        logger.info("PublicationAnalyzer инициализирован")
        logger.info(f"Scopus API: {'✓' if self.scopus_api_key else '✗'}")
        logger.info(f"PubMed API: {'✓' if self.pubmed_api_key else '✗'}")
        logger.info(f"CrossRef API: {'✓' if self.crossref_api_key else '✗'}")
    
    def _get_api_key(self, key_name: str) -> Optional[str]:
        """Получение API ключа из переменных окружения"""
        import os
        return os.getenv(key_name)
    
    def analyze_author_publications(self, author_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Главный метод для анализа всех публикаций автора
        
        Args:
            author_info: Словарь с информацией об авторе
                {
                    'full_name': 'Фамилия Имя Отчество',
                    'orcid_id': '0000-0000-0000-0000',
                    'email': 'author@email.com',
                    'publications': [...] # Базовый список публикаций
                }
        
        Returns:
            Расширенный анализ публикаций
        """
        logger.info(f"Начинаем глубокий анализ публикаций для автора: {author_info.get('full_name', 'Unknown')}")
        
        analysis_results = {
            'author_info': author_info,
            'publications_analysis': {
                'total_publications': 0,
                'analyzed_publications': 0,
                'analysis_timestamp': time.time(),
                'detailed_publications': [],
                'publication_summary': {},
                'research_profile': {},
                'collaboration_network': {},
                'temporal_analysis': {}
            },
            'analysis_metadata': {
                'processing_time': 0,
                'data_sources': [],
                'analysis_completeness': 0.0,
                'error_count': 0
            }
        }
        
        start_time = time.time()
        
        try:
            # 1. Сбор публикаций из всех доступных источников
            all_publications = self._collect_publications_from_sources(author_info)
            analysis_results['publications_analysis']['total_publications'] = len(all_publications)
            
            # 2. Анализ каждой публикации
            detailed_publications = []
            for i, publication in enumerate(all_publications[:self.max_publications_to_analyze]):
                try:
                    logger.info(f"Анализируем публикацию {i+1}/{min(len(all_publications), self.max_publications_to_analyze)}")
                    detailed_pub = self._analyze_single_publication(publication, author_info)
                    if detailed_pub:
                        detailed_publications.append(detailed_pub)
                except Exception as e:
                    logger.error(f"Ошибка анализа публикации {i+1}: {str(e)}")
                    analysis_results['analysis_metadata']['error_count'] += 1
                    continue
            
            analysis_results['publications_analysis']['detailed_publications'] = detailed_publications
            analysis_results['publications_analysis']['analyzed_publications'] = len(detailed_publications)
            
            # 3. Генерация сводного анализа
            analysis_results['publications_analysis']['publication_summary'] = self._generate_publication_summary(detailed_publications)
            analysis_results['publications_analysis']['research_profile'] = self._generate_research_profile(detailed_publications)
            analysis_results['publications_analysis']['collaboration_network'] = self._analyze_collaboration_network(detailed_publications)
            analysis_results['publications_analysis']['temporal_analysis'] = self._analyze_temporal_patterns(detailed_publications)
            
            # 4. Расчет метрик завершенности
            processing_time = time.time() - start_time
            analysis_results['analysis_metadata']['processing_time'] = processing_time
            analysis_results['analysis_metadata']['analysis_completeness'] = self._calculate_completeness(detailed_publications, all_publications)
            
            logger.info(f"Анализ публикаций завершен. Обработано {len(detailed_publications)} из {len(all_publications)} публикаций")
            
        except Exception as e:
            logger.error(f"Критическая ошибка в анализе публикаций: {str(e)}")
            analysis_results['analysis_metadata']['error_count'] += 1
            analysis_results['analysis_metadata']['critical_error'] = str(e)
        
        return analysis_results
    
    def _collect_publications_from_sources(self, author_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Сбор публикаций из всех доступных источников"""
        all_publications = []
        sources_used = []
        
        # Базовые публикации из предыдущих этапов
        if 'publications' in author_info:
            all_publications.extend(author_info['publications'])
            sources_used.append('basic_search')
        
        # ORCID публикации
        if author_info.get('orcid_id') and author_info['orcid_id'] != 'Не найден':
            try:
                orcid_publications = self._fetch_orcid_publications(author_info['orcid_id'])
                all_publications.extend(orcid_publications)
                sources_used.append('orcid')
                logger.info(f"Получено {len(orcid_publications)} публикаций из ORCID")
            except Exception as e:
                logger.error(f"Ошибка получения ORCID публикаций: {str(e)}")
        
        # Scopus публикации
        if self.scopus_api_key and author_info.get('full_name'):
            try:
                scopus_publications = self._fetch_scopus_publications(author_info)
                all_publications.extend(scopus_publications)
                sources_used.append('scopus')
                logger.info(f"Получено {len(scopus_publications)} публикаций из Scopus")
            except Exception as e:
                logger.error(f"Ошибка получения Scopus публикаций: {str(e)}")
        
        # PubMed публикации
        if author_info.get('full_name'):
            try:
                pubmed_publications = self._fetch_pubmed_publications(author_info)
                all_publications.extend(pubmed_publications)
                sources_used.append('pubmed')
                logger.info(f"Получено {len(pubmed_publications)} публикаций из PubMed")
            except Exception as e:
                logger.error(f"Ошибка получения PubMed публикаций: {str(e)}")
        
        # Дедупликация по DOI и названию
        unique_publications = self._deduplicate_publications(all_publications)
        
        logger.info(f"Собрано {len(all_publications)} публикаций из источников: {sources_used}")
        logger.info(f"После дедупликации: {len(unique_publications)} уникальных публикаций")
        
        return unique_publications
    
    def _analyze_single_publication(self, publication: Dict[str, Any], author_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Глубокий анализ одной публикации
        
        Алгоритм обработки:
        1. Извлечение метаданных
        2. Определение роли автора
        3. Анализ содержания
        4. Тематическая классификация
        """
        try:
            detailed_publication = {
                'original_data': publication,
                'metadata': {},
                'author_role': {},
                'content_analysis': {},
                'thematic_classification': {},
                'analysis_timestamp': time.time()
            }
            
            # 1. Извлечение метаданных
            detailed_publication['metadata'] = self._extract_publication_metadata(publication)
            
            # 2. Определение роли автора
            detailed_publication['author_role'] = self._determine_author_role(publication, author_info)
            
            # 3. Анализ содержания
            detailed_publication['content_analysis'] = self._analyze_publication_content(publication)
            
            # 4. Тематическая классификация
            detailed_publication['thematic_classification'] = self._classify_publication_theme(publication)
            
            return detailed_publication
            
        except Exception as e:
            logger.error(f"Ошибка детального анализа публикации: {str(e)}")
            return None
    
    def _extract_publication_metadata(self, publication: Dict[str, Any]) -> Dict[str, Any]:
        """
        1. Извлечение метаданных:
        • Заголовок
        • Журнал
        • Дата публикации
        • DOI/PMID
        • Список авторов
        """
        metadata = {
            'title': '',
            'journal': '',
            'publication_date': '',
            'doi': '',
            'pmid': '',
            'authors': [],
            'citations_count': 0,
            'publication_type': '',
            'language': '',
            'keywords': [],
            'abstract': ''
        }
        
        # Извлечение заголовка
        metadata['title'] = publication.get('title', '').strip()
        
        # Извлечение журнала
        metadata['journal'] = publication.get('journal', publication.get('venue', '')).strip()
        
        # Извлечение даты публикации
        pub_date = publication.get('year', publication.get('date', publication.get('publication_date', '')))
        metadata['publication_date'] = self._normalize_date(pub_date)
        
        # Извлечение DOI
        doi = publication.get('doi', publication.get('DOI', ''))
        if doi:
            metadata['doi'] = self._normalize_doi(doi)
        
        # Извлечение PMID
        metadata['pmid'] = publication.get('pmid', publication.get('PMID', ''))
        
        # Извлечение авторов
        authors = publication.get('authors', publication.get('author', []))
        if isinstance(authors, str):
            # Если авторы в виде строки, парсим их
            metadata['authors'] = self._parse_authors_string(authors)
        elif isinstance(authors, list):
            metadata['authors'] = [self._normalize_author_name(author) for author in authors]
        
        # Дополнительные метаданные через API
        if metadata['doi']:
            try:
                additional_metadata = self._fetch_additional_metadata_by_doi(metadata['doi'])
                metadata.update(additional_metadata)
            except Exception as e:
                logger.debug(f"Не удалось получить дополнительные метаданные для DOI {metadata['doi']}: {str(e)}")
        
        return metadata
    
    def _determine_author_role(self, publication: Dict[str, Any], author_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        2. Определение роли автора:
        • Первый автор
        • Соавтор
        • Корреспондирующий автор
        """
        author_role = {
            'is_first_author': False,
            'is_corresponding_author': False,
            'is_last_author': False,
            'author_position': 0,
            'total_authors': 0,
            'author_contribution': '',
            'confidence_score': 0.0
        }
        
        # Получаем список авторов
        authors = publication.get('authors', [])
        if isinstance(authors, str):
            authors = self._parse_authors_string(authors)
        
        author_role['total_authors'] = len(authors)
        
        # Нормализуем имя автора для поиска
        target_name = author_info.get('full_name', '')
        target_email = author_info.get('email', '')
        
        # Поиск автора в списке
        author_position = self._find_author_position(authors, target_name, target_email)
        
        if author_position >= 0:
            author_role['author_position'] = author_position + 1  # 1-based indexing
            author_role['is_first_author'] = (author_position == 0)
            author_role['is_last_author'] = (author_position == len(authors) - 1)
            author_role['confidence_score'] = 0.9  # Высокая уверенность при точном совпадении
            
            # Определение корреспондирующего автора
            corresponding_info = publication.get('corresponding_author', '')
            if target_email in corresponding_info or any(target_email in str(author) for author in authors):
                author_role['is_corresponding_author'] = True
        
        # Определение вклада автора
        if author_role['is_first_author']:
            author_role['author_contribution'] = 'Основной исследователь'
        elif author_role['is_last_author'] and author_role['total_authors'] > 2:
            author_role['author_contribution'] = 'Руководитель исследования'
        elif author_role['is_corresponding_author']:
            author_role['author_contribution'] = 'Корреспондирующий автор'
        else:
            author_role['author_contribution'] = 'Соавтор'
        
        return author_role
    
    def _analyze_publication_content(self, publication: Dict[str, Any]) -> Dict[str, Any]:
        """
        3. Анализ содержания:
        • Чтение аннотации
        • Определение методологии
        • Выявление основных результатов
        • Формулирование краткого резюме
        """
        content_analysis = {
            'abstract_analysis': {},
            'methodology': '',
            'main_results': [],
            'brief_summary': '',
            'research_type': '',
            'study_design': '',
            'sample_size': '',
            'statistical_methods': [],
            'limitations': []
        }
        
        # Анализ аннотации
        abstract = publication.get('abstract', publication.get('summary', ''))
        if abstract:
            content_analysis['abstract_analysis'] = self._analyze_abstract(abstract)
            content_analysis['brief_summary'] = self._generate_brief_summary(abstract)
            content_analysis['methodology'] = self._extract_methodology(abstract)
            content_analysis['main_results'] = self._extract_main_results(abstract)
            content_analysis['research_type'] = self._determine_research_type(abstract)
            content_analysis['study_design'] = self._extract_study_design(abstract)
        
        return content_analysis
    
    def _classify_publication_theme(self, publication: Dict[str, Any]) -> Dict[str, Any]:
        """
        4. Тематическая классификация:
        • Область исследования
        • Ключевые слова
        • Связь с другими работами автора
        """
        classification = {
            'research_field': '',
            'sub_fields': [],
            'keywords': [],
            'medical_specialties': [],
            'research_methods': [],
            'target_population': '',
            'clinical_relevance': '',
            'innovation_level': ''
        }
        
        # Извлечение ключевых слов
        keywords = publication.get('keywords', [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(',')]
        classification['keywords'] = keywords
        
        # Определение области исследования
        title = publication.get('title', '')
        abstract = publication.get('abstract', '')
        journal = publication.get('journal', '')
        
        classification['research_field'] = self._classify_research_field(title, abstract, journal)
        classification['sub_fields'] = self._identify_sub_fields(title, abstract, keywords)
        classification['medical_specialties'] = self._identify_medical_specialties(title, abstract, journal)
        
        return classification
    
    # Вспомогательные методы для анализа
    
    def _normalize_date(self, date_str: str) -> str:
        """Нормализация даты публикации"""
        if not date_str:
            return ''
        
        # Попытка парсинга различных форматов дат
        date_patterns = [
            r'(\d{4})',  # Только год
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, str(date_str))
            if match:
                if len(match.groups()) == 1:  # Только год
                    return match.group(1)
                else:
                    return date_str
        
        return str(date_str)
    
    def _normalize_doi(self, doi: str) -> str:
        """Нормализация DOI"""
        if not doi:
            return ''
        
        # Удаляем префиксы и нормализуем
        doi = doi.replace('https://doi.org/', '').replace('http://dx.doi.org/', '').replace('doi:', '')
        return doi.strip()
    
    def _parse_authors_string(self, authors_str: str) -> List[str]:
        """Парсинг строки с авторами"""
        if not authors_str:
            return []
        
        # Разделители авторов
        separators = [';', ',', ' and ', ' & ']
        authors = [authors_str]
        
        for sep in separators:
            new_authors = []
            for author in authors:
                new_authors.extend([a.strip() for a in author.split(sep)])
            authors = new_authors
        
        return [author for author in authors if author]
    
    def _normalize_author_name(self, author: Any) -> str:
        """Нормализация имени автора"""
        if isinstance(author, dict):
            first_name = author.get('given', author.get('first_name', ''))
            last_name = author.get('family', author.get('last_name', ''))
            return f"{last_name} {first_name}".strip()
        else:
            return str(author).strip()
    
    def _find_author_position(self, authors: List[str], target_name: str, target_email: str) -> int:
        """Поиск позиции автора в списке"""
        if not authors or not target_name:
            return -1
        
        # Нормализуем целевое имя
        target_parts = target_name.lower().split()
        
        for i, author in enumerate(authors):
            author_str = str(author).lower()
            
            # Проверяем совпадение по email
            if target_email and target_email.lower() in author_str:
                return i
            
            # Проверяем совпадение по имени
            if any(part in author_str for part in target_parts if len(part) > 2):
                return i
        
        return -1
    
    def _analyze_abstract(self, abstract: str) -> Dict[str, Any]:
        """Анализ аннотации"""
        return {
            'word_count': len(abstract.split()),
            'contains_methods': 'method' in abstract.lower() or 'procedure' in abstract.lower(),
            'contains_results': 'result' in abstract.lower() or 'finding' in abstract.lower(),
            'contains_conclusion': 'conclusion' in abstract.lower() or 'suggest' in abstract.lower(),
            'readability_score': len(abstract.split()) / len(abstract.split('.')) if '.' in abstract else 0
        }
    
    def _generate_brief_summary(self, abstract: str) -> str:
        """Генерация краткого резюме"""
        if not abstract:
            return ''
        
        # Простое извлечение первого предложения как резюме
        sentences = abstract.split('.')
        if sentences:
            return sentences[0].strip() + '.'
        
        return abstract[:200] + '...' if len(abstract) > 200 else abstract
    
    def _extract_methodology(self, abstract: str) -> str:
        """Извлечение методологии из аннотации"""
        methodology_keywords = [
            'randomized', 'controlled', 'retrospective', 'prospective',
            'cross-sectional', 'cohort', 'case-control', 'systematic review',
            'meta-analysis', 'experimental', 'observational'
        ]
        
        abstract_lower = abstract.lower()
        found_methods = [keyword for keyword in methodology_keywords if keyword in abstract_lower]
        
        return ', '.join(found_methods) if found_methods else 'Не определена'
    
    def _extract_main_results(self, abstract: str) -> List[str]:
        """Извлечение основных результатов"""
        # Простое извлечение предложений с результатами
        sentences = abstract.split('.')
        result_sentences = []
        
        for sentence in sentences:
            if any(keyword in sentence.lower() for keyword in ['result', 'finding', 'showed', 'demonstrated']):
                result_sentences.append(sentence.strip())
        
        return result_sentences[:3]  # Максимум 3 основных результата
    
    def _determine_research_type(self, abstract: str) -> str:
        """Определение типа исследования"""
        research_types = {
            'Клиническое исследование': ['clinical trial', 'patient', 'treatment'],
            'Лабораторное исследование': ['in vitro', 'laboratory', 'experimental'],
            'Обзор литературы': ['review', 'literature', 'systematic'],
            'Эпидемиологическое': ['population', 'epidemiological', 'prevalence'],
            'Методологическое': ['method', 'technique', 'protocol']
        }
        
        abstract_lower = abstract.lower()
        
        for research_type, keywords in research_types.items():
            if any(keyword in abstract_lower for keyword in keywords):
                return research_type
        
        return 'Не определен'
    
    def _extract_study_design(self, abstract: str) -> str:
        """Извлечение дизайна исследования"""
        design_patterns = {
            'Рандомизированное контролируемое': ['randomized controlled', 'rct'],
            'Ретроспективное': ['retrospective'],
            'Проспективное': ['prospective'],
            'Поперечное': ['cross-sectional'],
            'Когортное': ['cohort'],
            'Случай-контроль': ['case-control']
        }
        
        abstract_lower = abstract.lower()
        
        for design, patterns in design_patterns.items():
            if any(pattern in abstract_lower for pattern in patterns):
                return design
        
        return 'Не определен'
    
    def _classify_research_field(self, title: str, abstract: str, journal: str) -> str:
        """Классификация области исследования"""
        fields = {
            'Медицина': ['medical', 'clinical', 'patient', 'disease', 'treatment'],
            'Стоматология': ['dental', 'oral', 'tooth', 'стоматолог'],
            'Биология': ['biological', 'cell', 'molecular', 'gene'],
            'Фармакология': ['drug', 'pharmaceutical', 'therapy'],
            'Общественное здравоохранение': ['public health', 'epidemiology', 'prevention']
        }
        
        text = f"{title} {abstract} {journal}".lower()
        
        for field, keywords in fields.items():
            if any(keyword in text for keyword in keywords):
                return field
        
        return 'Междисциплинарное'
    
    def _identify_sub_fields(self, title: str, abstract: str, keywords: List[str]) -> List[str]:
        """Идентификация подобластей исследования"""
        text = f"{title} {abstract} {' '.join(keywords)}".lower()
        
        sub_fields = []
        field_keywords = {
            'Кардиология': ['cardiac', 'heart', 'cardiovascular'],
            'Онкология': ['cancer', 'tumor', 'oncology'],
            'Неврология': ['neurological', 'brain', 'neural'],
            'Педиатрия': ['pediatric', 'children', 'child'],
            'Хирургия': ['surgical', 'surgery', 'operative']
        }
        
        for field, keywords in field_keywords.items():
            if any(keyword in text for keyword in keywords):
                sub_fields.append(field)
        
        return sub_fields
    
    def _identify_medical_specialties(self, title: str, abstract: str, journal: str) -> List[str]:
        """Идентификация медицинских специальностей"""
        text = f"{title} {abstract} {journal}".lower()
        
        specialties = []
        specialty_keywords = {
            'Терапия': ['therapy', 'therapeutic', 'treatment'],
            'Диагностика': ['diagnostic', 'diagnosis', 'screening'],
            'Профилактика': ['prevention', 'preventive', 'prophylactic'],
            'Реабилитация': ['rehabilitation', 'recovery']
        }
        
        for specialty, keywords in specialty_keywords.items():
            if any(keyword in text for keyword in keywords):
                specialties.append(specialty)
        
        return specialties
    
    # Методы для работы с внешними API
    
    def _fetch_orcid_publications(self, orcid_id: str) -> List[Dict[str, Any]]:
        """Получение публикаций из ORCID"""
        publications = []
        
        try:
            url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
            headers = {'Accept': 'application/json'}
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Обработка ответа ORCID
            for work in data.get('group', []):
                for work_summary in work.get('work-summary', []):
                    pub = {
                        'title': work_summary.get('title', {}).get('title', {}).get('value', ''),
                        'journal': work_summary.get('journal-title', {}).get('value', ''),
                        'year': work_summary.get('publication-date', {}).get('year', {}).get('value', ''),
                        'source': 'orcid'
                    }
                    if pub['title']:
                        publications.append(pub)
            
        except Exception as e:
            logger.error(f"Ошибка получения ORCID публикаций: {str(e)}")
        
        return publications
    
    def _fetch_scopus_publications(self, author_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Получение публикаций из Scopus"""
        publications = []
        
        if not self.scopus_api_key:
            return publications
        
        try:
            # Формируем запрос для поиска автора
            author_name = author_info.get('full_name', '')
            if not author_name:
                return publications
            
            url = "https://api.elsevier.com/content/search/scopus"
            headers = {'X-ELS-APIKey': self.scopus_api_key}
            params = {
                'query': f'AUTHOR-NAME("{author_name}")',
                'count': 25,
                'start': 0
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            for entry in data.get('search-results', {}).get('entry', []):
                pub = {
                    'title': entry.get('dc:title', ''),
                    'journal': entry.get('prism:publicationName', ''),
                    'year': entry.get('prism:coverDate', '').split('-')[0] if entry.get('prism:coverDate') else '',
                    'doi': entry.get('prism:doi', ''),
                    'abstract': entry.get('dc:description', ''),
                    'authors': entry.get('dc:creator', ''),
                    'citations_count': entry.get('citedby-count', 0),
                    'source': 'scopus'
                }
                if pub['title']:
                    publications.append(pub)
            
        except Exception as e:
            logger.error(f"Ошибка получения Scopus публикаций: {str(e)}")
        
        return publications
    
    def _fetch_pubmed_publications(self, author_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Получение публикаций из PubMed"""
        publications = []
        
        try:
            author_name = author_info.get('full_name', '')
            if not author_name:
                return publications
            
            # Поиск в PubMed через eSearch
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': f'"{author_name}"[Author]',
                'retmax': 20,
                'retmode': 'json'
            }
            
            search_response = requests.get(search_url, params=search_params, timeout=10)
            search_response.raise_for_status()
            
            search_data = search_response.json()
            pmids = search_data.get('esearchresult', {}).get('idlist', [])
            
            if pmids:
                # Получение деталей через eFetch
                fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                fetch_params = {
                    'db': 'pubmed',
                    'id': ','.join(pmids[:10]),  # Ограничиваем до 10
                    'retmode': 'xml'
                }
                
                fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
                fetch_response.raise_for_status()
                
                # Простой парсинг XML (можно улучшить)
                xml_content = fetch_response.text
                
                # Извлекаем основную информацию из XML
                import xml.etree.ElementTree as ET
                root = ET.fromstring(xml_content)
                
                for article in root.findall('.//PubmedArticle'):
                    title_elem = article.find('.//ArticleTitle')
                    journal_elem = article.find('.//Journal/Title')
                    year_elem = article.find('.//PubDate/Year')
                    abstract_elem = article.find('.//Abstract/AbstractText')
                    
                    pub = {
                        'title': title_elem.text if title_elem is not None else '',
                        'journal': journal_elem.text if journal_elem is not None else '',
                        'year': year_elem.text if year_elem is not None else '',
                        'abstract': abstract_elem.text if abstract_elem is not None else '',
                        'source': 'pubmed'
                    }
                    
                    if pub['title']:
                        publications.append(pub)
            
        except Exception as e:
            logger.error(f"Ошибка получения PubMed публикаций: {str(e)}")
        
        return publications
    
    def _fetch_additional_metadata_by_doi(self, doi: str) -> Dict[str, Any]:
        """Получение дополнительных метаданных по DOI через CrossRef"""
        metadata = {}
        
        try:
            url = f"https://api.crossref.org/works/{doi}"
            headers = {'Accept': 'application/json'}
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            work = data.get('message', {})
            
            metadata.update({
                'citations_count': work.get('is-referenced-by-count', 0),
                'publication_type': work.get('type', ''),
                'language': work.get('language', ''),
                'publisher': work.get('publisher', ''),
                'subject_areas': work.get('subject', [])
            })
            
        except Exception as e:
            logger.debug(f"Ошибка получения метаданных CrossRef для DOI {doi}: {str(e)}")
        
        return metadata
    
    def _deduplicate_publications(self, publications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Дедупликация публикаций по DOI и названию"""
        seen_dois = set()
        seen_titles = set()
        unique_publications = []
        
        for pub in publications:
            doi = pub.get('doi', '').strip()
            title = pub.get('title', '').strip().lower()
            
            # Проверяем дедупликацию по DOI
            if doi and doi not in seen_dois:
                seen_dois.add(doi)
                unique_publications.append(pub)
            # Проверяем дедупликацию по названию
            elif title and title not in seen_titles and not doi:
                seen_titles.add(title)
                unique_publications.append(pub)
        
        return unique_publications
    
    def _generate_publication_summary(self, publications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерация сводки по публикациям"""
        summary = {
            'total_analyzed': len(publications),
            'by_year': {},
            'by_journal': {},
            'by_research_field': {},
            'author_roles': {
                'first_author': 0,
                'corresponding_author': 0,
                'co_author': 0
            },
            'publication_types': {},
            'average_citations': 0,
            'h_index_estimate': 0
        }
        
        citations = []
        
        for pub in publications:
            # Анализ по годам
            year = pub.get('metadata', {}).get('publication_date', '')[:4]
            if year and year.isdigit():
                summary['by_year'][year] = summary['by_year'].get(year, 0) + 1
            
            # Анализ по журналам
            journal = pub.get('metadata', {}).get('journal', '')
            if journal:
                summary['by_journal'][journal] = summary['by_journal'].get(journal, 0) + 1
            
            # Анализ по областям исследования
            field = pub.get('thematic_classification', {}).get('research_field', '')
            if field:
                summary['by_research_field'][field] = summary['by_research_field'].get(field, 0) + 1
            
            # Анализ ролей автора
            author_role = pub.get('author_role', {})
            if author_role.get('is_first_author'):
                summary['author_roles']['first_author'] += 1
            if author_role.get('is_corresponding_author'):
                summary['author_roles']['corresponding_author'] += 1
            if not author_role.get('is_first_author'):
                summary['author_roles']['co_author'] += 1
            
            # Сбор цитирований
            citations_count = pub.get('metadata', {}).get('citations_count', 0)
            if isinstance(citations_count, (int, float)) and citations_count > 0:
                citations.append(citations_count)
        
        # Расчет средних цитирований и h-индекса
        if citations:
            summary['average_citations'] = sum(citations) / len(citations)
            summary['h_index_estimate'] = self._calculate_h_index(citations)
        
        return summary
    
    def _generate_research_profile(self, publications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерация исследовательского профиля"""
        profile = {
            'primary_research_areas': [],
            'research_evolution': {},
            'collaboration_intensity': '',
            'publication_productivity': {},
            'research_impact': {},
            'specialization_score': 0.0
        }
        
        # Анализ основных областей исследования
        field_counts = {}
        for pub in publications:
            field = pub.get('thematic_classification', {}).get('research_field', '')
            if field and field != 'Не определен':
                field_counts[field] = field_counts.get(field, 0) + 1
        
        profile['primary_research_areas'] = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Оценка специализации
        if field_counts:
            total_pubs = sum(field_counts.values())
            max_field_count = max(field_counts.values())
            profile['specialization_score'] = max_field_count / total_pubs if total_pubs > 0 else 0
        
        return profile
    
    def _analyze_collaboration_network(self, publications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Анализ сети сотрудничества"""
        network = {
            'co_authors': {},
            'institutions': {},
            'collaboration_score': 0.0,
            'international_collaboration': False
        }
        
        total_authors = 0
        
        for pub in publications:
            authors = pub.get('metadata', {}).get('authors', [])
            if len(authors) > 1:
                total_authors += len(authors)
                
                # Подсчет соавторов
                for author in authors:
                    if isinstance(author, str) and author:
                        network['co_authors'][author] = network['co_authors'].get(author, 0) + 1
        
        # Расчет коэффициента сотрудничества
        if publications:
            network['collaboration_score'] = total_authors / len(publications) if len(publications) > 0 else 0
        
        return network
    
    def _analyze_temporal_patterns(self, publications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Анализ временных паттернов публикаций"""
        temporal = {
            'publication_timeline': {},
            'productivity_trend': '',
            'recent_activity': {},
            'career_stage': ''
        }
        
        years = []
        for pub in publications:
            year = pub.get('metadata', {}).get('publication_date', '')[:4]
            if year and year.isdigit():
                years.append(int(year))
                temporal['publication_timeline'][year] = temporal['publication_timeline'].get(year, 0) + 1
        
        if years:
            current_year = datetime.now().year
            recent_years = [y for y in years if y >= current_year - 3]
            
            temporal['recent_activity'] = {
                'publications_last_3_years': len(recent_years),
                'most_productive_year': max(temporal['publication_timeline'].items(), key=lambda x: x[1])[0],
                'career_span': max(years) - min(years) + 1 if len(years) > 1 else 1
            }
            
            # Определение стадии карьеры
            career_span = temporal['recent_activity']['career_span']
            if career_span < 5:
                temporal['career_stage'] = 'Начинающий исследователь'
            elif career_span < 15:
                temporal['career_stage'] = 'Опытный исследователь'
            else:
                temporal['career_stage'] = 'Старший исследователь'
        
        return temporal
    
    def _calculate_h_index(self, citations: List[int]) -> int:
        """Расчет h-индекса"""
        if not citations:
            return 0
        
        # Сортируем цитирования по убыванию
        sorted_citations = sorted(citations, reverse=True)
        
        h_index = 0
        for i, citation_count in enumerate(sorted_citations, 1):
            if citation_count >= i:
                h_index = i
            else:
                break
        
        return h_index
    
    def _calculate_completeness(self, analyzed_publications: List[Dict], all_publications: List[Dict]) -> float:
        """Расчет полноты анализа"""
        if not all_publications:
            return 0.0
        
        return len(analyzed_publications) / len(all_publications)
