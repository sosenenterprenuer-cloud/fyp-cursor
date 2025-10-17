"""Test configuration and fixtures."""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app


@pytest.fixture
def client():
    """Create test client with proper configuration."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for tests
    with app.test_client() as client:
        yield client


@pytest.fixture
def logged_in_client(client):
    """Create client with logged in user."""
    with client.session_transaction() as sess:
        # Mock a logged in session
        sess['student_id'] = 1
        sess['student_name'] = 'Test Student'
        sess['role'] = 'student'
        sess['csrf_token'] = 'test-token'
    
    return client


@pytest.fixture
def app_context():
    """Create application context for testing."""
    with app.app_context():
        yield app
