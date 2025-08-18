"""Pytest configuration and fixtures for performance optimization."""
import sys
from unittest.mock import Mock, patch
import pytest


@pytest.fixture(autouse=True)
def mock_heavy_imports():
    """Mock heavy imports to speed up tests."""
    # Mock TensorFlow to prevent loading
    if 'tensorflow' not in sys.modules:
        sys.modules['tensorflow'] = Mock()
        sys.modules['tensorflow_hub'] = Mock()
    
    # Mock spaCy model loading
    with patch('spacy.load') as mock_spacy_load:
        mock_nlp = Mock()
        mock_nlp.return_value = Mock()
        mock_spacy_load.return_value = mock_nlp
        yield


@pytest.fixture
def mock_spacy_nlp():
    """Provide a mocked spaCy NLP model."""
    mock_nlp = Mock()
    mock_doc = Mock()
    mock_doc.vector = [0.1, 0.2, 0.3]
    mock_nlp.return_value = mock_doc
    return mock_nlp


@pytest.fixture
def temp_rss_file():
    """Create a temporary RSS file for testing."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("https://example.com/feed1.xml\n")
        f.write("https://example.com/feed2.xml\n")
        yield f.name
    import os
    try:
        os.unlink(f.name)
    except FileNotFoundError:
        pass


@pytest.fixture
def mock_config():
    """Provide a mock configuration."""
    return {
        'PARAMS': {
            'debug': 'False',
            'limit': '100',
            'cluster_limit': '2'
        },
        'DAEMON': {
            'wait_time': '1',
            'debug': 'False'
        }
    }
