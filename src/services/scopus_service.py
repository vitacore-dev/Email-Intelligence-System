import requests
import json
import logging
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class ScopusService:
    """Сервис для работы с Scopus API"""
    
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('SCOPUS_API_KEY')
        self.base_url = 'https://api.elsevier.com/content'
        
        if not self.api_key:
            logger.warning("SCOPUS_API_KEY не найден в переменных окружения")
    
    def search_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Поиск публикаций по email адресу автора"""
        if not self.api_key:
            return []
        
        try:
            # Поиск автора по email
            author_info = self.search_author_by_email(email)
            if not author_info:
                return []
            
            author_id = author_info.get('author_id')
            if not author_id:
                return []
            
            # Получение публикаций автора
            publications = self.get_author_publications(author_id)
            return publications
            
        except Exception as e:
            logger.error(f"Ошибка при поиске в Scopus по email {email}: {str(e)}")
            return []
    
    def search_author_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Поиск автора по email адресу"""
        if not self.api_key:
            return None
        
        try:
            url = f"{self.base_url}/search/author"
            headers = {
                'X-ELS-APIKey': self.api_key,
                'Accept': 'application/json'
            }
            params = {
                'query': f'email({email})',
                'count': 1
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            entries = data.get('search-results', {}).get('entry', [])
            
            if entries:
                author = entries[0]
                return {
                    'author_id': author.get('dc:identifier', '').replace('AUTHOR_ID:', ''),
                    'given_name': author.get('preferred-name', {}).get('given-name', ''),
                    'surname': author.get('preferred-name', {}).get('surname', ''),
                    'affiliation': author.get('affiliation-current', {}).get('affiliation-name', ''),
                    'document_count': author.get('document-count', 0),
                    'cited_by_count': author.get('cited-by-count', 0),
                    'h_index': author.get('h-index', 0),
                    'scopus_profile_url': author.get('link', [{}])[-1].get('@href', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при поиске автора в Scopus: {str(e)}")
            return None
    
    def get_author_publications(self, author_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Получение публикаций автора по его ID"""
        if not self.api_key:
            return []
        
        try:
            url = f"{self.base_url}/search/scopus"
            headers = {
                'X-ELS-APIKey': self.api_key,
                'Accept': 'application/json'
            }
            params = {
                'query': f'AU-ID({author_id})',
                'count': limit,
                'sort': 'pubyear',
                'view': 'COMPLETE'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            entries = data.get('search-results', {}).get('entry', [])
            
            publications = []
            for entry in entries:
                pub = {
                    'scopus_id': entry.get('dc:identifier', '').replace('SCOPUS_ID:', ''),
                    'title': entry.get('dc:title', ''),
                    'publication_name': entry.get('prism:publicationName', ''),
                    'cover_date': entry.get('prism:coverDate', ''),
                    'doi': entry.get('prism:doi', ''),
                    'cited_by_count': entry.get('citedby-count', 0),
                    'authors': self._extract_authors(entry.get('author', [])),
                    'abstract': entry.get('dc:description', ''),
                    'keywords': entry.get('authkeywords', ''),
                    'type': entry.get('subtypeDescription', ''),
                    'open_access': entry.get('openaccess', False),
                    'scopus_url': entry.get('link', [{}])[-1].get('@href', '')
                }
                publications.append(pub)
            
            return publications
            
        except Exception as e:
            logger.error(f"Ошибка при получении публикаций автора {author_id}: {str(e)}")
            return []
    
    def search_publications_by_query(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Поиск публикаций по произвольному запросу"""
        if not self.api_key:
            return []
        
        try:
            url = f"{self.base_url}/search/scopus"
            headers = {
                'X-ELS-APIKey': self.api_key,
                'Accept': 'application/json'
            }
            params = {
                'query': query,
                'count': limit,
                'sort': 'relevancy',
                'view': 'STANDARD'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            entries = data.get('search-results', {}).get('entry', [])
            
            publications = []
            for entry in entries:
                pub = {
                    'scopus_id': entry.get('dc:identifier', '').replace('SCOPUS_ID:', ''),
                    'title': entry.get('dc:title', ''),
                    'publication_name': entry.get('prism:publicationName', ''),
                    'cover_date': entry.get('prism:coverDate', ''),
                    'doi': entry.get('prism:doi', ''),
                    'cited_by_count': entry.get('citedby-count', 0),
                    'authors': self._extract_authors(entry.get('author', [])),
                    'abstract': entry.get('dc:description', ''),
                    'type': entry.get('subtypeDescription', ''),
                    'scopus_url': entry.get('link', [{}])[-1].get('@href', '')
                }
                publications.append(pub)
            
            return publications
            
        except Exception as e:
            logger.error(f"Ошибка при поиске публикаций в Scopus: {str(e)}")
            return []
    
    def get_publication_details(self, scopus_id: str) -> Optional[Dict[str, Any]]:
        """Получение детальной информации о публикации"""
        if not self.api_key:
            return None
        
        try:
            url = f"{self.base_url}/abstract/scopus_id/{scopus_id}"
            headers = {
                'X-ELS-APIKey': self.api_key,
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            abstract_retrieval = data.get('abstracts-retrieval-response', {})
            
            if abstract_retrieval:
                coredata = abstract_retrieval.get('coredata', {})
                item = abstract_retrieval.get('item', {})
                
                return {
                    'scopus_id': coredata.get('dc:identifier', '').replace('SCOPUS_ID:', ''),
                    'title': coredata.get('dc:title', ''),
                    'publication_name': coredata.get('prism:publicationName', ''),
                    'cover_date': coredata.get('prism:coverDate', ''),
                    'doi': coredata.get('prism:doi', ''),
                    'cited_by_count': coredata.get('citedby-count', 0),
                    'abstract': coredata.get('dc:description', ''),
                    'authors': self._extract_detailed_authors(abstract_retrieval.get('authors', {})),
                    'affiliations': self._extract_affiliations(abstract_retrieval.get('affiliation', [])),
                    'subject_areas': self._extract_subject_areas(abstract_retrieval.get('subject-areas', {})),
                    'keywords': self._extract_keywords(abstract_retrieval.get('authkeywords', {})),
                    'references': abstract_retrieval.get('item', {}).get('bibrecord', {}).get('tail', {}).get('bibliography', {}).get('@refcount', 0),
                    'open_access': coredata.get('openaccess', False),
                    'document_type': coredata.get('subtypeDescription', ''),
                    'source_type': coredata.get('srctype', ''),
                    'scopus_url': coredata.get('link', [{}])[-1].get('@href', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении деталей публикации {scopus_id}: {str(e)}")
            return None
    
    def get_author_metrics(self, author_id: str) -> Optional[Dict[str, Any]]:
        """Получение метрик автора"""
        if not self.api_key:
            return None
        
        try:
            url = f"{self.base_url}/author/author_id/{author_id}"
            headers = {
                'X-ELS-APIKey': self.api_key,
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            author_profile = data.get('author-retrieval-response', [{}])[0]
            
            if author_profile:
                coredata = author_profile.get('coredata', {})
                
                return {
                    'author_id': author_id,
                    'given_name': coredata.get('given-name', ''),
                    'surname': coredata.get('surname', ''),
                    'document_count': coredata.get('document-count', 0),
                    'cited_by_count': coredata.get('cited-by-count', 0),
                    'citation_count': coredata.get('citation-count', 0),
                    'h_index': coredata.get('h-index', 0),
                    'status': coredata.get('status', ''),
                    'scopus_profile_url': coredata.get('link', [{}])[-1].get('@href', ''),
                    'current_affiliation': self._extract_current_affiliation(author_profile.get('affiliation-current', {}))
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении метрик автора {author_id}: {str(e)}")
            return None
    
    def _extract_authors(self, authors_data: List[Dict]) -> List[Dict[str, str]]:
        """Извлечение информации об авторах"""
        authors = []
        for author in authors_data:
            authors.append({
                'given_name': author.get('given-name', ''),
                'surname': author.get('surname', ''),
                'authid': author.get('@auid', ''),
                'seq': author.get('@seq', '')
            })
        return authors
    
    def _extract_detailed_authors(self, authors_data: Dict) -> List[Dict[str, Any]]:
        """Извлечение детальной информации об авторах"""
        authors = []
        author_list = authors_data.get('author', [])
        if not isinstance(author_list, list):
            author_list = [author_list]
        
        for author in author_list:
            authors.append({
                'given_name': author.get('ce:given-name', ''),
                'surname': author.get('ce:surname', ''),
                'initials': author.get('ce:initials', ''),
                'authid': author.get('@auid', ''),
                'seq': author.get('@seq', ''),
                'email': author.get('ce:e-address', ''),
                'orcid': author.get('@orcid', '')
            })
        return authors
    
    def _extract_affiliations(self, affiliations_data: List[Dict]) -> List[Dict[str, str]]:
        """Извлечение информации об аффилиациях"""
        affiliations = []
        for affiliation in affiliations_data:
            affiliations.append({
                'id': affiliation.get('@id', ''),
                'name': affiliation.get('affilname', ''),
                'city': affiliation.get('affiliation-city', ''),
                'country': affiliation.get('affiliation-country', '')
            })
        return affiliations
    
    def _extract_subject_areas(self, subject_areas_data: Dict) -> List[str]:
        """Извлечение предметных областей"""
        subject_areas = []
        area_list = subject_areas_data.get('subject-area', [])
        if not isinstance(area_list, list):
            area_list = [area_list]
        
        for area in area_list:
            if isinstance(area, dict):
                subject_areas.append(area.get('$', ''))
        return subject_areas
    
    def _extract_keywords(self, keywords_data: Dict) -> List[str]:
        """Извлечение ключевых слов"""
        keywords = []
        keyword_list = keywords_data.get('author-keyword', [])
        if not isinstance(keyword_list, list):
            keyword_list = [keyword_list]
        
        for keyword in keyword_list:
            if isinstance(keyword, dict):
                keywords.append(keyword.get('$', ''))
        return keywords
    
    def _extract_current_affiliation(self, affiliation_data: Dict) -> Dict[str, str]:
        """Извлечение текущей аффилиации"""
        return {
            'name': affiliation_data.get('affiliation-name', ''),
            'city': affiliation_data.get('affiliation-city', ''),
            'country': affiliation_data.get('affiliation-country', '')
        }
