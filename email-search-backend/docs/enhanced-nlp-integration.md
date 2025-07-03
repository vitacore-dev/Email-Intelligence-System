# Enhanced NLP Integration for Email Search Backend

## Overview

This document describes the enhanced NLP (Natural Language Processing) integration that has been added to the Email Search Backend. The enhanced NLP system provides intelligent analysis of web content, email owner identification, and semantic information extraction.

## Features

### Core NLP Capabilities

1. **Named Entity Recognition (NER)**
   - Extracts persons, organizations, and locations from text
   - Supports Russian and English languages
   - Uses spaCy and Natasha libraries for high accuracy

2. **Professional Role Analysis**
   - Identifies academic roles (professor, associate professor, researcher)
   - Detects medical roles (doctor, surgeon, specialist)
   - Recognizes management positions (director, manager, head)
   - Classifies technical roles (engineer, developer, analyst)

3. **Email Owner Identification**
   - Analyzes context around email addresses
   - Determines most likely email owner
   - Provides confidence scores for identifications

4. **Semantic Pattern Recognition**
   - Detects academic activity patterns
   - Identifies medical professional indicators
   - Recognizes research activity markers

### Enhanced Analysis Pipeline

The enhanced NLP analyzer integrates with the existing webpage analyzer to provide:

- **Deep Text Analysis**: Processes extracted text from web pages using advanced NLP techniques
- **Confidence Scoring**: Provides reliability scores for all extracted information
- **Multi-source Integration**: Combines data from webpage analysis and search snippets
- **Intelligent Filtering**: Removes duplicate and low-confidence information

## Architecture

### Components

```
Enhanced NLP System
├── EnhancedNLPAnalyzer (Main coordinator)
├── NLP Manager (Core NLP processing)
│   ├── NER Module (Named entity recognition)
│   ├── Role Analysis Module (Professional role detection)
│   └── Email Owner Module (Owner identification)
├── Webpage Analyzer (Existing component)
└── Search Engine Service (Updated with NLP integration)
```

### Integration Points

1. **Search Engine Service**: Main integration point where NLP analysis is triggered
2. **Webpage Analyzer**: Provides structured data for NLP processing
3. **API Endpoints**: Enhanced search results include NLP analysis data
4. **Monitoring**: New endpoints for NLP system status and testing

## Installation and Setup

### 1. Install Dependencies

```bash
# Install basic requirements
pip install -r requirements.txt

# Install NLP-specific packages
pip install spacy>=3.4.0 natasha>=1.6.0 navec>=0.10.0
```

### 2. Download Language Models

Run the setup script to install required spaCy models:

```bash
python setup_nlp.py
```

Or install manually:

```bash
# Required models
python -m spacy download ru_core_news_sm
python -m spacy download en_core_web_sm

# Optional larger models (better accuracy)
python -m spacy download ru_core_news_lg
python -m spacy download en_core_web_lg
```

### 3. Configuration

The NLP system is configured through `src/services/nlp/config.py`:

```python
# Enable/disable NLP system
nlp_config.enabled = True

# Configure individual modules
nlp_config.modules['named_entity_recognition']['enabled'] = True
nlp_config.modules['professional_role_analysis']['enabled'] = True
nlp_config.modules['email_owner_identification']['enabled'] = True

# Performance settings
nlp_config.performance['max_text_length'] = 50000
nlp_config.performance['timeout_seconds'] = 30
```

### 4. Verification

Check NLP system status:

```bash
# Via API
curl http://localhost:5001/api/monitoring/nlp-status

# Via Python
from src.services.nlp_enhanced_analyzer import EnhancedNLPAnalyzer
analyzer = EnhancedNLPAnalyzer()
print(analyzer.get_nlp_status())
```

## Usage

### API Integration

When performing email searches, the enhanced NLP analysis is automatically applied:

```bash
curl -X POST http://localhost:5001/api/email/search \
  -H "Content-Type: application/json" \
  -d '{"email": "researcher@university.edu"}'
```

### Response Structure

The API response now includes enhanced NLP analysis:

```json
{
  "email": "researcher@university.edu",
  "basic_info": {
    "owner_name": "Dr. John Smith",
    "nlp_confidence": 0.85,
    "nlp_source": "nlp_analysis"
  },
  "professional_info": {
    "specialization": "Академическая деятельность",
    "nlp_roles": ["профессор", "исследователь"]
  },
  "enhanced_nlp_analysis": {
    "nlp_analysis": {
      "entities_found": [
        {
          "text": "John Smith",
          "label": "PERSON",
          "confidence": 0.95
        }
      ],
      "professional_roles": [
        {
          "title": "профессор",
          "category": "academic",
          "confidence": 0.88
        }
      ],
      "semantic_patterns": ["academic_professional"]
    },
    "enhanced_insights": {
      "most_confident_owner": {
        "name": "Dr. John Smith",
        "confidence": 0.85,
        "source": "nlp_analysis"
      },
      "contact_reliability": "high"
    }
  }
}
```

### Monitoring and Testing

#### NLP Status Endpoint

```bash
GET /api/monitoring/nlp-status
```

Returns:
```json
{
  "nlp_status": {
    "nlp_available": true,
    "nlp_initialized": true,
    "nlp_manager_status": {
      "enabled": true,
      "initialized": true,
      "modules": {
        "ner": true,
        "roles": true,
        "email_owner": true
      }
    }
  }
}
```

#### NLP Testing Endpoint

```bash
POST /api/monitoring/nlp-test
Content-Type: application/json

{
  "text": "Профессор Иван Иванович работает в университете. Email: ivan@uni.ru",
  "email": "ivan@uni.ru"
}
```

## Performance Considerations

### Resource Usage

- **Memory**: NLP models require 200-500MB RAM (small models) or 1-2GB (large models)
- **CPU**: Processing time scales with text length (0.1-5 seconds for typical content)
- **Storage**: Language models require 50-150MB disk space each

### Optimization Options

1. **Model Selection**:
   - Use small models (`_sm`) for faster processing
   - Use large models (`_lg`) for better accuracy

2. **Text Length Limits**:
   ```python
   nlp_config.performance['max_text_length'] = 25000  # Reduce for faster processing
   ```

3. **Module Selection**:
   ```python
   # Disable modules not needed
   nlp_config.disable_module('professional_role_analysis')
   ```

4. **Timeout Configuration**:
   ```python
   nlp_config.performance['timeout_seconds'] = 15  # Reduce timeout
   ```

## Error Handling

The NLP system is designed to be fault-tolerant:

1. **Graceful Degradation**: If NLP is unavailable, the system continues with standard webpage analysis
2. **Module Isolation**: Individual NLP modules can fail without affecting others
3. **Timeout Protection**: Long-running analysis is automatically terminated
4. **Error Logging**: All NLP errors are logged for debugging

### Common Issues and Solutions

#### 1. Model Not Found Error
```
OSError: Can't find model 'ru_core_news_sm'
```
**Solution**: Run `python setup_nlp.py` or manually download the model

#### 2. Memory Issues
```
MemoryError: Unable to allocate array
```
**Solution**: 
- Use smaller models
- Reduce `max_text_length`
- Process fewer URLs simultaneously

#### 3. Slow Performance
**Solution**:
- Use small models instead of large ones
- Reduce text length limits
- Disable unused NLP modules

## Development

### Adding Custom NLP Modules

1. Create a new module inheriting from `BaseNLPModule`:

```python
from src.services.nlp.base import BaseNLPModule

class CustomAnalysisModule(BaseNLPModule):
    def initialize(self) -> bool:
        # Initialize your module
        return True
    
    def process(self, text: str, **kwargs):
        # Process text and return results
        return results
```

2. Register the module in `nlp_manager.py`

3. Add configuration options in `config.py`

### Testing

Run NLP-specific tests:

```bash
python src/services/nlp/test_nlp.py
```

## API Reference

### New Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/monitoring/nlp-status` | GET | Get NLP system status | Optional |
| `/api/monitoring/nlp-test` | POST | Test NLP functionality | Required |

### Enhanced Response Fields

All email search responses now include:

- `enhanced_nlp_analysis`: Complete NLP analysis results
- `basic_info.nlp_confidence`: Confidence score for owner identification
- `basic_info.nlp_source`: Source of NLP-derived information
- `professional_info.nlp_roles`: Roles identified by NLP
- `scientific_identifiers.nlp_organizations`: Organizations found by NLP
- `scientific_identifiers.nlp_persons`: Persons identified by NLP

## Security Considerations

1. **Input Validation**: All text input is validated before NLP processing
2. **Resource Limits**: Processing time and memory usage are bounded
3. **Error Sanitization**: Error messages don't expose sensitive information
4. **Access Control**: NLP testing endpoint requires authentication

## Future Enhancements

Planned improvements include:

1. **Additional Languages**: Support for more languages beyond Russian and English
2. **Custom Models**: Training domain-specific models for better accuracy
3. **Real-time Processing**: Streaming analysis for large documents
4. **Advanced Semantics**: Relationship extraction and knowledge graph construction
5. **Machine Learning**: Continuous learning from user feedback

## Support

For issues related to the enhanced NLP system:

1. Check the logs in `data/logs/app.log`
2. Verify NLP status via `/api/monitoring/nlp-status`
3. Test individual components via `/api/monitoring/nlp-test`
4. Review configuration in `src/services/nlp/config.py`

For performance issues, consider adjusting the configuration parameters or switching to smaller language models.
