import requests
import json
import logging
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import re

logger = logging.getLogger(__name__)

class ORCIDService:
    """Сервис для работы с ORCID API"""
    
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv('ORCID_CLIENT_ID')
        self.client_secret = os.getenv('ORCID_CLIENT_SECRET')
        self.base_url = 'https://pub.orcid.org/v3.0'
        self.search_url = 'https://pub.orcid.org/v3.0/search'
        
        if not self.client_id:
            logger.warning("ORCID_CLIENT_ID не найден в переменных окружения")
    
    def search_by_email(self, email: str) -> List[Dict[str, Any]]:
        """Поиск исследователей по email адресу"""
        try:
            # Поиск ORCID ID по email
            orcid_ids = self.search_orcid_by_email(email)
            
            researchers = []
            for orcid_id in orcid_ids[:5]:  # Ограничиваем количество результатов
                researcher_info = self.get_researcher_profile(orcid_id)
                if researcher_info:
                    researchers.append(researcher_info)
            
            return researchers
            
        except Exception as e:
            logger.error(f"Ошибка при поиске в ORCID по email {email}: {str(e)}")
            return []
    
    def search_orcid_by_email(self, email: str) -> List[str]:
        """Поиск ORCID ID по email адресу"""
        try:
            headers = {
                'Accept': 'application/json'
            }
            params = {
                'q': f'email:{email}',
                'rows': 10
            }
            
            response = requests.get(self.search_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('result', [])
            
            orcid_ids = []
            for result in results:
                orcid_path = result.get('orcid-identifier', {}).get('path')
                if orcid_path:
                    orcid_ids.append(orcid_path)
            
            return orcid_ids
            
        except Exception as e:
            logger.error(f"Ошибка при поиске ORCID ID по email: {str(e)}")
            return []
    
    def search_by_name(self, given_name: str, family_name: str) -> List[str]:
        """Поиск ORCID ID по имени и фамилии"""
        try:
            headers = {
                'Accept': 'application/json'
            }
            params = {
                'q': f'given-names:{given_name} AND family-name:{family_name}',
                'rows': 10
            }
            
            response = requests.get(self.search_url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('result', [])
            
            orcid_ids = []
            for result in results:
                orcid_path = result.get('orcid-identifier', {}).get('path')
                if orcid_path:
                    orcid_ids.append(orcid_path)
            
            return orcid_ids
            
        except Exception as e:
            logger.error(f"Ошибка при поиске ORCID ID по имени: {str(e)}")
            return []
    
    def get_researcher_profile(self, orcid_id: str) -> Optional[Dict[str, Any]]:
        """Получение полного профиля исследователя"""
        if not self._validate_orcid_id(orcid_id):
            logger.error(f"Неверный формат ORCID ID: {orcid_id}")
            return None
        
        try:
            url = f"{self.base_url}/{orcid_id}/record"
            headers = {
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Извлекаем основную информацию
            person = data.get('person', {})
            activities_summary = data.get('activities-summary', {})
            
            profile = {
                'orcid_id': orcid_id,
                'orcid_url': f"https://orcid.org/{orcid_id}",
                'personal_info': self._extract_personal_info(person),
                'biography': self._extract_biography(person),
                'keywords': self._extract_keywords(person),
                'external_identifiers': self._extract_external_identifiers(person),
                'addresses': self._extract_addresses(person),
                'educations': self._extract_educations(activities_summary),
                'employments': self._extract_employments(activities_summary),
                'works': self._extract_works_summary(activities_summary),
                'fundings': self._extract_fundings_summary(activities_summary),
                'peer_reviews': self._extract_peer_reviews_summary(activities_summary)
            }
            
            return profile
            
        except Exception as e:
            logger.error(f"Ошибка при получении профиля ORCID {orcid_id}: {str(e)}")
            return None
    
    def get_researcher_works(self, orcid_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Получение списка работ исследователя"""
        if not self._validate_orcid_id(orcid_id):
            return []
        
        try:
            url = f"{self.base_url}/{orcid_id}/works"
            headers = {
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            works_group = data.get('group', [])
            
            works = []
            for group in works_group[:limit]:
                work_summary = group.get('work-summary', [])
                if work_summary:
                    work_detail = self._get_work_details(orcid_id, work_summary[0].get('put-code'))
                    if work_detail:
                        works.append(work_detail)
            
            return works
            
        except Exception as e:
            logger.error(f"Ошибка при получении работ ORCID {orcid_id}: {str(e)}")
            return []
    
    def _get_work_details(self, orcid_id: str, put_code: str) -> Optional[Dict[str, Any]]:
        """Получение детальной информации о работе"""
        try:
            url = f"{self.base_url}/{orcid_id}/work/{put_code}"
            headers = {
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            title = data.get('title', {})
            journal_title = data.get('journal-title', {})
            publication_date = data.get('publication-date', {})
            external_ids = data.get('external-ids', {}).get('external-id', [])
            
            # Извлекаем DOI
            doi = None
            for ext_id in external_ids:
                if ext_id.get('external-id-type') == 'doi':
                    doi = ext_id.get('external-id-value')
                    break
            
            return {
                'put_code': put_code,
                'title': title.get('title', {}).get('value', ''),
                'subtitle': title.get('subtitle', {}).get('value', '') if title.get('subtitle') else '',
                'journal_title': journal_title.get('value', '') if journal_title else '',
                'type': data.get('type', ''),
                'publication_date': self._format_publication_date(publication_date),
                'doi': doi,
                'url': data.get('url', {}).get('value', '') if data.get('url') else '',
                'language_code': data.get('language-code', ''),
                'short_description': data.get('short-description', ''),
                'citation': self._extract_citation(data.get('citation', {})),
                'contributors': self._extract_contributors(data.get('contributors', {})),
                'external_identifiers': self._extract_work_external_ids(external_ids)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении деталей работы {put_code}: {str(e)}")
            return None
    
    def _extract_personal_info(self, person: Dict) -> Dict[str, Any]:
        """Извлечение личной информации"""
        name = person.get('name', {})
        
        return {
            'given_names': name.get('given-names', {}).get('value', '') if name.get('given-names') else '',
            'family_name': name.get('family-name', {}).get('value', '') if name.get('family-name') else '',
            'credit_name': name.get('credit-name', {}).get('value', '') if name.get('credit-name') else '',
            'other_names': [other.get('content') for other in person.get('other-names', {}).get('other-name', [])],
            'researcher_urls': [url.get('url', {}).get('value') for url in person.get('researcher-urls', {}).get('researcher-url', [])]
        }
    
    def _extract_biography(self, person: Dict) -> str:
        """Извлечение биографии"""
        biography = person.get('biography', {})
        return biography.get('content', '') if biography else ''
    
    def _extract_keywords(self, person: Dict) -> List[str]:
        """Извлечение ключевых слов"""
        keywords = person.get('keywords', {}).get('keyword', [])
        return [kw.get('content', '') for kw in keywords]
    
    def _extract_external_identifiers(self, person: Dict) -> List[Dict[str, str]]:
        """Извлечение внешних идентификаторов"""
        external_ids = person.get('external-identifiers', {}).get('external-identifier', [])
        
        identifiers = []
        for ext_id in external_ids:
            identifiers.append({
                'type': ext_id.get('external-id-type', ''),
                'value': ext_id.get('external-id-value', ''),
                'url': ext_id.get('external-id-url', {}).get('value', '') if ext_id.get('external-id-url') else ''
            })
        
        return identifiers
    
    def _extract_addresses(self, person: Dict) -> List[Dict[str, str]]:
        """Извлечение адресов"""
        addresses = person.get('addresses', {}).get('address', [])
        
        result = []
        for address in addresses:
            result.append({
                'country': address.get('country', {}).get('value', '') if address.get('country') else '',
                'region': address.get('region', {}).get('value', '') if address.get('region') else '',
                'city': address.get('city', {}).get('value', '') if address.get('city') else ''
            })
        
        return result
    
    def _extract_educations(self, activities: Dict) -> List[Dict[str, Any]]:
        """Извлечение информации об образовании"""
        educations = activities.get('educations', {}).get('education-summary', [])
        
        result = []
        for education in educations:
            organization = education.get('organization', {})
            start_date = education.get('start-date', {})
            end_date = education.get('end-date', {})
            
            result.append({
                'department': education.get('department-name', ''),
                'role_title': education.get('role-title', ''),
                'organization_name': organization.get('name', ''),
                'organization_city': organization.get('address', {}).get('city', ''),
                'organization_country': organization.get('address', {}).get('country', ''),
                'start_date': self._format_date(start_date),
                'end_date': self._format_date(end_date),
                'url': education.get('url', {}).get('value', '') if education.get('url') else ''
            })
        
        return result
    
    def _extract_employments(self, activities: Dict) -> List[Dict[str, Any]]:
        """Извлечение информации о трудоустройстве"""
        employments = activities.get('employments', {}).get('employment-summary', [])
        
        result = []
        for employment in employments:
            organization = employment.get('organization', {})
            start_date = employment.get('start-date', {})
            end_date = employment.get('end-date', {})
            
            result.append({
                'department': employment.get('department-name', ''),
                'role_title': employment.get('role-title', ''),
                'organization_name': organization.get('name', ''),
                'organization_city': organization.get('address', {}).get('city', ''),
                'organization_country': organization.get('address', {}).get('country', ''),
                'start_date': self._format_date(start_date),
                'end_date': self._format_date(end_date),
                'url': employment.get('url', {}).get('value', '') if employment.get('url') else ''
            })
        
        return result
    
    def _extract_works_summary(self, activities: Dict) -> Dict[str, Any]:
        """Извлечение сводки по работам"""
        works = activities.get('works', {})
        groups = works.get('group', [])
        
        return {
            'total_works': len(groups),
            'last_modified': works.get('last-modified-date', {}).get('value', '') if works.get('last-modified-date') else ''
        }
    
    def _extract_fundings_summary(self, activities: Dict) -> Dict[str, Any]:
        """Извлечение сводки по финансированию"""
        fundings = activities.get('fundings', {})
        groups = fundings.get('group', [])
        
        return {
            'total_fundings': len(groups),
            'last_modified': fundings.get('last-modified-date', {}).get('value', '') if fundings.get('last-modified-date') else ''
        }
    
    def _extract_peer_reviews_summary(self, activities: Dict) -> Dict[str, Any]:
        """Извлечение сводки по рецензированию"""
        peer_reviews = activities.get('peer-reviews', {})
        groups = peer_reviews.get('group', [])
        
        return {
            'total_peer_reviews': len(groups),
            'last_modified': peer_reviews.get('last-modified-date', {}).get('value', '') if peer_reviews.get('last-modified-date') else ''
        }
    
    def _extract_citation(self, citation: Dict) -> Dict[str, str]:
        """Извлечение информации о цитировании"""
        return {
            'type': citation.get('citation-type', ''),
            'value': citation.get('citation-value', '')
        }
    
    def _extract_contributors(self, contributors: Dict) -> List[Dict[str, str]]:
        """Извлечение информации о соавторах"""
        contributor_list = contributors.get('contributor', [])
        
        result = []
        for contributor in contributor_list:
            credit_name = contributor.get('credit-name', {})
            result.append({
                'name': credit_name.get('value', '') if credit_name else '',
                'role': contributor.get('contributor-attributes', {}).get('contributor-role', ''),
                'sequence': contributor.get('contributor-attributes', {}).get('contributor-sequence', '')
            })
        
        return result
    
    def _extract_work_external_ids(self, external_ids: List[Dict]) -> List[Dict[str, str]]:
        """Извлечение внешних идентификаторов работы"""
        identifiers = []
        for ext_id in external_ids:
            identifiers.append({
                'type': ext_id.get('external-id-type', ''),
                'value': ext_id.get('external-id-value', ''),
                'relationship': ext_id.get('external-id-relationship', ''),
                'url': ext_id.get('external-id-url', {}).get('value', '') if ext_id.get('external-id-url') else ''
            })
        
        return identifiers
    
    def _format_date(self, date_info: Dict) -> str:
        """Форматирование даты"""
        if not date_info:
            return ''
        
        year = date_info.get('year', {}).get('value', '') if date_info.get('year') else ''
        month = date_info.get('month', {}).get('value', '') if date_info.get('month') else ''
        day = date_info.get('day', {}).get('value', '') if date_info.get('day') else ''
        
        parts = [part for part in [year, month, day] if part]
        return '-'.join(parts)
    
    def _format_publication_date(self, date_info: Dict) -> str:
        """Форматирование даты публикации"""
        return self._format_date(date_info)
    
    def _validate_orcid_id(self, orcid_id: str) -> bool:
        """Валидация формата ORCID ID"""
        # ORCID ID имеет формат: 0000-0000-0000-0000
        pattern = r'^\d{4}-\d{4}-\d{4}-\d{4}$'
        return bool(re.match(pattern, orcid_id))
