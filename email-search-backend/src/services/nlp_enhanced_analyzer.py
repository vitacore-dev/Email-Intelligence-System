"""
Enhanced NLP Analyzer for Email Search Backend
Integrates the existing NLP modules with the webpage analyzer for better intelligence
"""

import logging
import time
from typing import Dict, List, Any, Optional

try:
    from .nlp import nlp_manager, NLPResult
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False
    nlp_manager = None
    NLPResult = None

try:
    from .webpage_analyzer import WebpageAnalyzer
except ImportError:
    WebpageAnalyzer = None

logger = logging.getLogger(__name__)

class EnhancedNLPAnalyzer:
    """
    Enhanced NLP analyzer that combines webpage analysis with NLP processing
    for better email owner identification and information extraction
    """
    
    def __init__(self):
        self.nlp_manager = nlp_manager if NLP_AVAILABLE else None
        self.webpage_analyzer = WebpageAnalyzer() if WebpageAnalyzer else None
        self.is_nlp_initialized = False
        
        # Initialize NLP if available
        if self.nlp_manager:
            try:
                self.is_nlp_initialized = self.nlp_manager.initialize()
                if self.is_nlp_initialized:
                    logger.info("Enhanced NLP analyzer initialized successfully")
                else:
                    logger.warning("NLP manager initialization failed")
            except Exception as e:
                logger.error(f"Failed to initialize NLP manager: {e}")
                self.is_nlp_initialized = False
        else:
            logger.warning("NLP modules not available")
    
    def analyze_email_search_results(self, email: str, search_results: List[Dict], 
                                   webpage_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Enhanced analysis combining webpage extraction with NLP processing
        
        Args:
            email: Email address being searched
            search_results: List of search results from search engines
            webpage_analysis: Optional pre-computed webpage analysis
            
        Returns:
            Enhanced analysis results with NLP insights
        """
        start_time = time.time()
        
        enhanced_results = {
            'email': email,
            'nlp_analysis': {
                'enabled': self.is_nlp_initialized,
                'owner_candidates': [],
                'confidence_scores': {},
                'linguistic_features': {},
                'semantic_analysis': {}
            },
            'enhanced_insights': {
                'most_confident_owner': None,
                'professional_context': {},
                'academic_indicators': {},
                'contact_reliability': 'unknown'
            },
            'metadata': {
                'processing_time': 0.0,
                'methods_used': [],
                'analysis_timestamp': time.time()
            }
        }
        
        try:
            # Step 1: Use existing webpage analysis if available, otherwise create it
            if not webpage_analysis and self.webpage_analyzer:
                logger.info(f"Creating webpage analysis for {email}")
                webpage_analysis = self.webpage_analyzer.analyze_search_results(search_results)
                enhanced_results['metadata']['methods_used'].append('webpage_analysis')
            
            # Step 2: Apply NLP analysis to extracted text content
            if self.is_nlp_initialized and webpage_analysis:
                nlp_results = self._apply_nlp_to_webpage_data(email, webpage_analysis)
                enhanced_results['nlp_analysis'].update(nlp_results)
                enhanced_results['metadata']['methods_used'].append('nlp_analysis')
            
            # Step 3: Enhance search result snippets with NLP
            if self.is_nlp_initialized:
                snippet_analysis = self._analyze_search_snippets(email, search_results)
                self._merge_snippet_analysis(enhanced_results, snippet_analysis)
                enhanced_results['metadata']['methods_used'].append('snippet_nlp')
            
            # Step 4: Generate enhanced insights
            self._generate_enhanced_insights(enhanced_results, webpage_analysis)
            
            # Step 5: Calculate final confidence scores
            self._calculate_confidence_scores(enhanced_results)
            
        except Exception as e:
            logger.error(f"Error in enhanced NLP analysis: {e}")
            enhanced_results['metadata']['error'] = str(e)
        
        enhanced_results['metadata']['processing_time'] = time.time() - start_time
        return enhanced_results
    
    def _apply_nlp_to_webpage_data(self, email: str, webpage_analysis: Dict) -> Dict[str, Any]:
        """
        Apply NLP analysis to webpage extraction results
        """
        nlp_results = {
            'entities_found': [],
            'professional_roles': [],
            'email_contexts': [],
            'language_detected': 'unknown',
            'semantic_patterns': []
        }
        
        try:
            # Collect all text content from webpage analysis
            text_content = self._extract_text_from_webpage_analysis(webpage_analysis)
            
            if text_content and len(text_content.strip()) > 10:
                # Run full NLP analysis
                nlp_result = self.nlp_manager.analyze_text(text_content, email=email)
                
                if nlp_result:
                    nlp_results['entities_found'] = [
                        {
                            'text': entity.text,
                            'label': entity.label,
                            'confidence': entity.confidence,
                            'start_pos': entity.start_pos,
                            'end_pos': entity.end_pos
                        }
                        for entity in nlp_result.entities
                    ]
                    
                    nlp_results['professional_roles'] = [
                        {
                            'title': role.title,
                            'category': role.category,
                            'confidence': role.confidence,
                            'context': role.context
                        }
                        for role in nlp_result.professional_roles
                    ]
                    
                    nlp_results['email_contexts'] = [
                        {
                            'context_text': getattr(ctx, 'context_text', ''),
                            'owner_candidate': getattr(ctx, 'owner_candidate', ''),
                            'confidence': getattr(ctx, 'confidence', 0.0)
                        }
                        for ctx in nlp_result.email_contexts
                    ]
                    
                    nlp_results['language_detected'] = nlp_result.language
                    
                    # Extract semantic patterns
                    nlp_results['semantic_patterns'] = self._extract_semantic_patterns(nlp_result)
                    
                    logger.info(f"NLP analysis completed: {len(nlp_result.entities)} entities, "
                              f"{len(nlp_result.professional_roles)} roles detected")
            
        except Exception as e:
            logger.error(f"Error in NLP analysis: {e}")
            nlp_results['error'] = str(e)
        
        return nlp_results
    
    def _analyze_search_snippets(self, email: str, search_results: List[Dict]) -> Dict[str, Any]:
        """
        Apply NLP analysis to search result snippets
        """
        snippet_analysis = {
            'snippet_entities': [],
            'snippet_roles': [],
            'snippet_contexts': [],
            'relevance_scores': []
        }
        
        try:
            # Combine all snippets for analysis
            all_snippets = []
            for result in search_results:
                snippet = result.get('snippet', '').strip()
                if snippet:
                    all_snippets.append(snippet)
            
            combined_text = ' '.join(all_snippets)
            
            if combined_text and len(combined_text.strip()) > 20:
                # Analyze combined snippets
                nlp_result = self.nlp_manager.analyze_text(combined_text, email=email)
                
                if nlp_result:
                    snippet_analysis['snippet_entities'] = [
                        {'text': e.text, 'label': e.label, 'confidence': e.confidence}
                        for e in nlp_result.entities
                    ]
                    
                    snippet_analysis['snippet_roles'] = [
                        {'title': r.title, 'category': r.category, 'confidence': r.confidence}
                        for r in nlp_result.professional_roles
                    ]
                    
                    snippet_analysis['snippet_contexts'] = [
                        {'owner_candidate': getattr(ctx, 'owner_candidate', ''), 'confidence': getattr(ctx, 'confidence', 0.0)}
                        for ctx in nlp_result.email_contexts
                    ]
        
        except Exception as e:
            logger.error(f"Error analyzing snippets: {e}")
            snippet_analysis['error'] = str(e)
        
        return snippet_analysis
    
    def _extract_text_from_webpage_analysis(self, webpage_analysis: Dict) -> str:
        """
        Extract meaningful text content from webpage analysis results
        """
        text_parts = []
        
        try:
            # Extract names
            names = webpage_analysis.get('owner_identification', {}).get('names_found', [])
            text_parts.extend(names)
            
            # Extract professional details
            prof_details = webpage_analysis.get('professional_details', {})
            text_parts.extend(prof_details.get('positions', []))
            text_parts.extend(prof_details.get('organizations', []))
            text_parts.extend(prof_details.get('locations', []))
            text_parts.extend(prof_details.get('specializations', []))
            
            # Extract academic info
            academic_info = webpage_analysis.get('academic_info', {})
            text_parts.extend(academic_info.get('degrees', []))
            text_parts.extend(academic_info.get('research_areas', [])
            )
            # Join all parts
            return ' '.join([str(part) for part in text_parts if part])
            
        except Exception as e:
            logger.error(f"Error extracting text from webpage analysis: {e}")
            return ''
    
    def _extract_semantic_patterns(self, nlp_result: Any) -> List[str]:
        """
        Extract semantic patterns from NLP results
        """
        patterns = []
        
        try:
            # Analyze entity co-occurrences
            person_entities = [e for e in nlp_result.entities if e.label == 'PERSON']
            org_entities = [e for e in nlp_result.entities if e.label in ['ORG', 'ORGANIZATION']]
            
            if person_entities and org_entities:
                patterns.append('person_organization_association')
            
            # Analyze professional role patterns
            academic_roles = [r for r in nlp_result.professional_roles if r.category == 'academic']
            if academic_roles:
                patterns.append('academic_professional')
            
            medical_roles = [r for r in nlp_result.professional_roles if r.category == 'medical']
            if medical_roles:
                patterns.append('medical_professional')
            
            # Check for research indicators
            research_indicators = ['research', 'publication', 'journal', 'conference', 'study']
            if any(indicator in nlp_result.metadata.get('text_content', '').lower() 
                   for indicator in research_indicators):
                patterns.append('research_activity')
        
        except Exception as e:
            logger.error(f"Error extracting semantic patterns: {e}")
        
        return patterns
    
    def _merge_snippet_analysis(self, enhanced_results: Dict, snippet_analysis: Dict):
        """
        Merge snippet analysis results into enhanced results
        """
        try:
            nlp_analysis = enhanced_results['nlp_analysis']
            
            # Merge entities (avoid duplicates)
            existing_entities = {e['text'].lower() for e in nlp_analysis.get('entities_found', [])}
            for entity in snippet_analysis.get('snippet_entities', []):
                if entity['text'].lower() not in existing_entities:
                    nlp_analysis['entities_found'].append(entity)
            
            # Merge roles
            existing_roles = {r['title'].lower() for r in nlp_analysis.get('professional_roles', [])}
            for role in snippet_analysis.get('snippet_roles', []):
                if role['title'].lower() not in existing_roles:
                    nlp_analysis['professional_roles'].append(role)
            
            # Merge contexts
            nlp_analysis['email_contexts'].extend(snippet_analysis.get('snippet_contexts', []))
            
        except Exception as e:
            logger.error(f"Error merging snippet analysis: {e}")
    
    def _generate_enhanced_insights(self, enhanced_results: Dict, webpage_analysis: Optional[Dict]):
        """
        Generate enhanced insights by combining NLP and webpage analysis
        """
        try:
            insights = enhanced_results['enhanced_insights']
            nlp_data = enhanced_results['nlp_analysis']
            
            # Determine most confident owner
            owner_candidates = []
            
            # From NLP analysis
            for ctx in nlp_data.get('email_contexts', []):
                if ctx.get('owner_candidate'):
                    owner_candidates.append({
                        'name': ctx['owner_candidate'],
                        'confidence': ctx['confidence'],
                        'source': 'nlp_context'
                    })
            
            # From webpage analysis
            if webpage_analysis:
                most_likely = webpage_analysis.get('owner_identification', {}).get('most_likely_name')
                if most_likely:
                    owner_candidates.append({
                        'name': most_likely,
                        'confidence': webpage_analysis.get('owner_identification', {}).get('confidence_score', 0.0),
                        'source': 'webpage_analysis'
                    })
            
            # Select best candidate
            if owner_candidates:
                best_candidate = max(owner_candidates, key=lambda x: x['confidence'])
                insights['most_confident_owner'] = best_candidate
            
            # Analyze professional context
            professional_roles = nlp_data.get('professional_roles', [])
            if professional_roles:
                insights['professional_context'] = {
                    'primary_category': max(professional_roles, key=lambda x: x['confidence'])['category'],
                    'roles_found': [r['title'] for r in professional_roles],
                    'confidence_level': 'high' if any(r['confidence'] > 0.8 for r in professional_roles) else 'medium'
                }
            
            # Analyze academic indicators
            academic_roles = [r for r in professional_roles if r['category'] == 'academic']
            if academic_roles:
                insights['academic_indicators'] = {
                    'is_academic': True,
                    'academic_roles': [r['title'] for r in academic_roles],
                    'academic_confidence': max(r['confidence'] for r in academic_roles)
                }
            
            # Determine contact reliability
            semantic_patterns = nlp_data.get('semantic_patterns', [])
            if 'person_organization_association' in semantic_patterns:
                insights['contact_reliability'] = 'high'
            elif owner_candidates:
                insights['contact_reliability'] = 'medium'
            else:
                insights['contact_reliability'] = 'low'
                
        except Exception as e:
            logger.error(f"Error generating enhanced insights: {e}")
    
    def _calculate_confidence_scores(self, enhanced_results: Dict):
        """
        Calculate overall confidence scores for different aspects
        """
        try:
            confidence_scores = enhanced_results['nlp_analysis']['confidence_scores']
            nlp_data = enhanced_results['nlp_analysis']
            
            # Owner identification confidence
            email_contexts = nlp_data.get('email_contexts', [])
            if email_contexts:
                confidence_scores['owner_identification'] = max(ctx['confidence'] for ctx in email_contexts)
            else:
                confidence_scores['owner_identification'] = 0.0
            
            # Professional role confidence
            professional_roles = nlp_data.get('professional_roles', [])
            if professional_roles:
                confidence_scores['professional_role'] = max(r['confidence'] for r in professional_roles)
            else:
                confidence_scores['professional_role'] = 0.0
            
            # Entity extraction confidence
            entities = nlp_data.get('entities_found', [])
            if entities:
                confidence_scores['entity_extraction'] = sum(e['confidence'] for e in entities) / len(entities)
            else:
                confidence_scores['entity_extraction'] = 0.0
            
            # Overall confidence
            scores = list(confidence_scores.values())
            if scores:
                confidence_scores['overall'] = sum(scores) / len(scores)
            else:
                confidence_scores['overall'] = 0.0
                
        except Exception as e:
            logger.error(f"Error calculating confidence scores: {e}")
    
    def get_nlp_status(self) -> Dict[str, Any]:
        """
        Get status of NLP components
        """
        status = {
            'nlp_available': NLP_AVAILABLE,
            'nlp_initialized': self.is_nlp_initialized,
            'webpage_analyzer_available': self.webpage_analyzer is not None
        }
        
        if self.nlp_manager:
            status['nlp_manager_status'] = self.nlp_manager.get_status()
        
        return status
    
    def cleanup(self):
        """
        Cleanup resources
        """
        if self.nlp_manager:
            self.nlp_manager.cleanup()

