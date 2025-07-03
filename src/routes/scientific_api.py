from flask import Blueprint, request, jsonify
from typing import Dict, Any
import logging
from src.services.scopus_service import ScopusService
from src.services.orcid_service import ORCIDService
from src.services.elibrary_service import ElibraryService
from src.middleware.auth_middleware import token_required

logger = logging.getLogger(__name__)

scientific_api_bp = Blueprint('scientific_api', __name__)

# Инициализация сервисов
scopus_service = ScopusService()
orcid_service = ORCIDService()
elibrary_service = ElibraryService(demo_mode=True)  # Включаем демо-режим для тестирования

@scientific_api_bp.route('/scopus/search-by-email', methods=['POST'])
@token_required
def scopus_search_by_email():
    """Поиск публикаций в Scopus по email автора"""
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({
                'error': 'Email не указан',
                'status': 'error'
            }), 400
        
        email = data['email']
        logger.info(f"Поиск в Scopus по email: {email}")
        
        # Поиск автора по email
        author_info = scopus_service.search_author_by_email(email)
        if not author_info:
            return jsonify({
                'message': 'Автор не найден в Scopus',
                'author_info': None,
                'publications': [],
                'status': 'not_found'
            })
        
        # Получение публикаций автора
        publications = scopus_service.get_author_publications(author_info['author_id'])
        
        return jsonify({
            'message': 'Данные успешно получены из Scopus',
            'author_info': author_info,
            'publications': publications,
            'total_publications': len(publications),
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при поиске в Scopus: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/scopus/search-publications', methods=['POST'])
@token_required
def scopus_search_publications():
    """Поиск публикаций в Scopus по запросу"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({
                'error': 'Поисковый запрос не указан',
                'status': 'error'
            }), 400
        
        query = data['query']
        limit = data.get('limit', 20)
        
        logger.info(f"Поиск публикаций в Scopus по запросу: {query}")
        
        publications = scopus_service.search_publications_by_query(query, limit)
        
        return jsonify({
            'message': 'Поиск выполнен успешно',
            'publications': publications,
            'total_results': len(publications),
            'query': query,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при поиске публикаций в Scopus: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/scopus/publication/<scopus_id>', methods=['GET'])
@token_required
def get_scopus_publication_details(scopus_id: str):
    """Получение детальной информации о публикации из Scopus"""
    try:
        logger.info(f"Получение деталей публикации Scopus ID: {scopus_id}")
        
        publication_details = scopus_service.get_publication_details(scopus_id)
        
        if not publication_details:
            return jsonify({
                'message': 'Публикация не найдена',
                'status': 'not_found'
            }), 404
        
        return jsonify({
            'message': 'Детали публикации получены',
            'publication': publication_details,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении деталей публикации: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/scopus/author-metrics/<author_id>', methods=['GET'])
@token_required
def get_scopus_author_metrics(author_id: str):
    """Получение метрик автора из Scopus"""
    try:
        logger.info(f"Получение метрик автора Scopus ID: {author_id}")
        
        metrics = scopus_service.get_author_metrics(author_id)
        
        if not metrics:
            return jsonify({
                'message': 'Автор не найден',
                'status': 'not_found'
            }), 404
        
        return jsonify({
            'message': 'Метрики автора получены',
            'metrics': metrics,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении метрик автора: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/orcid/search-by-email', methods=['POST'])
@token_required
def orcid_search_by_email():
    """Поиск исследователей в ORCID по email"""
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({
                'error': 'Email не указан',
                'status': 'error'
            }), 400
        
        email = data['email']
        logger.info(f"Поиск в ORCID по email: {email}")
        
        researchers = orcid_service.search_by_email(email)
        
        return jsonify({
            'message': 'Поиск выполнен успешно',
            'researchers': researchers,
            'total_results': len(researchers),
            'email': email,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при поиске в ORCID: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/orcid/search-by-name', methods=['POST'])
@token_required
def orcid_search_by_name():
    """Поиск исследователей в ORCID по имени"""
    try:
        data = request.get_json()
        if not data or 'given_name' not in data or 'family_name' not in data:
            return jsonify({
                'error': 'Имя и фамилия должны быть указаны',
                'status': 'error'
            }), 400
        
        given_name = data['given_name']
        family_name = data['family_name']
        
        logger.info(f"Поиск в ORCID по имени: {given_name} {family_name}")
        
        orcid_ids = orcid_service.search_by_name(given_name, family_name)
        
        # Получаем профили для найденных ORCID ID
        researchers = []
        for orcid_id in orcid_ids[:5]:  # Ограничиваем количество
            profile = orcid_service.get_researcher_profile(orcid_id)
            if profile:
                researchers.append(profile)
        
        return jsonify({
            'message': 'Поиск выполнен успешно',
            'researchers': researchers,
            'total_results': len(researchers),
            'query': f"{given_name} {family_name}",
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при поиске в ORCID по имени: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/orcid/profile/<orcid_id>', methods=['GET'])
@token_required
def get_orcid_profile(orcid_id: str):
    """Получение профиля исследователя из ORCID"""
    try:
        logger.info(f"Получение профиля ORCID: {orcid_id}")
        
        profile = orcid_service.get_researcher_profile(orcid_id)
        
        if not profile:
            return jsonify({
                'message': 'Профиль не найден',
                'status': 'not_found'
            }), 404
        
        return jsonify({
            'message': 'Профиль получен успешно',
            'profile': profile,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении профиля ORCID: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/orcid/works/<orcid_id>', methods=['GET'])
@token_required
def get_orcid_works(orcid_id: str):
    """Получение списка работ исследователя из ORCID"""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        logger.info(f"Получение работ ORCID: {orcid_id}")
        
        works = orcid_service.get_researcher_works(orcid_id, limit)
        
        return jsonify({
            'message': 'Список работ получен',
            'works': works,
            'total_works': len(works),
            'orcid_id': orcid_id,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении работ ORCID: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/combined-search', methods=['POST'])
@token_required
def combined_scientific_search():
    """Комбинированный поиск по Scopus и ORCID"""
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({
                'error': 'Email не указан',
                'status': 'error'
            }), 400
        
        email = data['email']
        logger.info(f"Комбинированный поиск по email: {email}")
        
        result = {
            'email': email,
            'scopus_data': {},
            'orcid_data': {},
            'combined_analysis': {},
            'status': 'success'
        }
        
        # Поиск в Scopus
        try:
            scopus_author = scopus_service.search_author_by_email(email)
            if scopus_author:
                scopus_publications = scopus_service.get_author_publications(scopus_author['author_id'])
                result['scopus_data'] = {
                    'author_info': scopus_author,
                    'publications': scopus_publications,
                    'total_publications': len(scopus_publications)
                }
            else:
                result['scopus_data'] = {'message': 'Не найден в Scopus'}
        except Exception as e:
            logger.error(f"Ошибка поиска в Scopus: {str(e)}")
            result['scopus_data'] = {'error': str(e)}
        
        # Поиск в ORCID
        try:
            orcid_researchers = orcid_service.search_by_email(email)
            if orcid_researchers:
                # Получаем детальную информацию о первом найденном исследователе
                main_researcher = orcid_researchers[0]
                orcid_works = orcid_service.get_researcher_works(main_researcher['orcid_id'])
                
                result['orcid_data'] = {
                    'researchers': orcid_researchers,
                    'main_researcher': main_researcher,
                    'works': orcid_works,
                    'total_researchers': len(orcid_researchers),
                    'total_works': len(orcid_works)
                }
            else:
                result['orcid_data'] = {'message': 'Не найден в ORCID'}
        except Exception as e:
            logger.error(f"Ошибка поиска в ORCID: {str(e)}")
            result['orcid_data'] = {'error': str(e)}
        
        # Анализ и сравнение данных
        result['combined_analysis'] = _analyze_combined_data(result['scopus_data'], result['orcid_data'])
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Ошибка комбинированного поиска: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

def _analyze_combined_data(scopus_data: Dict[str, Any], orcid_data: Dict[str, Any]) -> Dict[str, Any]:
    """Анализ и сравнение данных из Scopus и ORCID"""
    analysis = {
        'data_sources': [],
        'publication_count_comparison': {},
        'research_profile': {},
        'recommendations': []
    }
    
    # Определяем доступные источники данных
    if 'author_info' in scopus_data:
        analysis['data_sources'].append('scopus')
    if 'researchers' in orcid_data and orcid_data['researchers']:
        analysis['data_sources'].append('orcid')
    
    # Сравнение количества публикаций
    if 'total_publications' in scopus_data:
        analysis['publication_count_comparison']['scopus'] = scopus_data['total_publications']
    if 'total_works' in orcid_data:
        analysis['publication_count_comparison']['orcid'] = orcid_data['total_works']
    
    # Формирование исследовательского профиля
    if 'author_info' in scopus_data:
        author_info = scopus_data['author_info']
        analysis['research_profile']['name'] = f"{author_info.get('given_name', '')} {author_info.get('surname', '')}"
        analysis['research_profile']['affiliation'] = author_info.get('affiliation', '')
        analysis['research_profile']['h_index'] = author_info.get('h_index', 0)
        analysis['research_profile']['cited_by_count'] = author_info.get('cited_by_count', 0)
    
    if 'main_researcher' in orcid_data:
        researcher = orcid_data['main_researcher']
        personal_info = researcher.get('personal_info', {})
        analysis['research_profile']['orcid_name'] = f"{personal_info.get('given_names', '')} {personal_info.get('family_name', '')}"
        analysis['research_profile']['keywords'] = researcher.get('keywords', [])
        analysis['research_profile']['employments'] = researcher.get('employments', [])
    
    # Рекомендации на основе найденных данных
    if len(analysis['data_sources']) == 2:
        analysis['recommendations'].append("Исследователь найден в обеих базах данных - высокая достоверность")
    elif 'scopus' in analysis['data_sources']:
        analysis['recommendations'].append("Найден только в Scopus - рекомендуется проверить ORCID ID")
    elif 'orcid' in analysis['data_sources']:
        analysis['recommendations'].append("Найден только в ORCID - рекомендуется проверить публикации в Scopus")
    else:
        analysis['recommendations'].append("Не найден в научных базах данных - возможно, не является исследователем")
    
    return analysis

@scientific_api_bp.route('/elibrary/search-by-email', methods=['POST'])
@token_required
def elibrary_search_by_email():
    """Поиск публикаций в elibrary.ru по email"""
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({
                'error': 'Email не указан',
                'status': 'error'
            }), 400
        
        email = data['email']
        search_options = data.get('search_options', {})
        
        logger.info(f"Поиск в elibrary.ru по email: {email}")
        
        # Выполняем поиск по email
        search_results = elibrary_service.search_by_email(email, search_options)
        
        if 'error' in search_results:
            return jsonify({
                'error': search_results['error'],
                'status': 'error'
            }), 400
        
        # Форматируем результаты для визуализации
        formatted_results = elibrary_service.format_results_for_visualization(search_results)
        
        return jsonify({
            'message': 'Поиск в elibrary.ru выполнен успешно',
            'search_results': search_results,
            'formatted_results': formatted_results,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при поиске в elibrary.ru: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/elibrary/publication-details', methods=['POST'])
@token_required
def get_elibrary_publication_details():
    """Получение детальной информации о публикации из elibrary.ru"""
    try:
        data = request.get_json()
        if not data or 'publication_url' not in data:
            return jsonify({
                'error': 'URL публикации не указан',
                'status': 'error'
            }), 400
        
        publication_url = data['publication_url']
        
        logger.info(f"Получение деталей публикации elibrary: {publication_url}")
        
        details = elibrary_service.get_publication_details(publication_url)
        
        if not details:
            return jsonify({
                'message': 'Не удалось получить детали публикации',
                'status': 'not_found'
            }), 404
        
        return jsonify({
            'message': 'Детали публикации получены',
            'details': details,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении деталей публикации: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500

@scientific_api_bp.route('/api-status', methods=['GET'])
@token_required
def get_api_status():
    """Проверка статуса API ключей"""
    try:
        status = {
            'scopus': {
                'available': bool(scopus_service.api_key),
                'base_url': scopus_service.base_url
            },
            'orcid': {
                'available': bool(orcid_service.client_id),
                'base_url': orcid_service.base_url
            },
            'elibrary': {
                'available': True,
                'base_url': elibrary_service.base_url
            }
        }
        
        return jsonify({
            'message': 'Статус API получен',
            'api_status': status,
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса API: {str(e)}")
        return jsonify({
            'error': f'Ошибка сервера: {str(e)}',
            'status': 'error'
        }), 500
