"""Test authentication guards for protected routes."""

import pytest


def test_protected_routes_redirect_when_not_logged_in(client):
    """Test that protected routes redirect to login when not authenticated."""
    protected_routes = [
        '/quiz',
        '/student/1',
        '/api/quiz_progressive',
        '/submit',
        '/modules',
        '/module/1',
    ]
    
    for route in protected_routes:
        if route == '/submit':
            # POST request for submit
            response = client.post(route, json={'attempt_id': 1, 'answers': []})
        else:
            # GET request for others
            response = client.get(route)
        
        assert response.status_code == 302
        assert '/login' in response.location


def test_login_register_pages_dont_show_navbar(client):
    """Test that login and register pages don't show navbar."""
    response = client.get('/login')
    assert response.status_code == 200
    # Should not contain navbar elements
    assert 'nav-right' not in response.get_data(as_text=True)
    
    response = client.get('/register')
    assert response.status_code == 200
    # Should not contain navbar elements
    assert 'nav-right' not in response.get_data(as_text=True)


def test_dashboard_shows_navbar_when_logged_in(client):
    """Test that dashboard shows navbar when user is logged in."""
    # First register a user
    response = client.post('/register', data={
        'csrf_token': 'test-token',
        'name': 'Test User',
        'email': 'test@example.com',
        'program': 'CS',
        'password': 'password123'
    })
    
    # Should redirect to dashboard
    assert response.status_code == 302
    
    # Follow redirect to dashboard
    response = client.get('/student/1')
    assert response.status_code == 200
    
    # Should contain navbar elements
    html = response.get_data(as_text=True)
    assert 'nav-right' in html
    assert 'Logout' in html


def test_logout_present_on_dashboard(client):
    """Test that logout link is present on dashboard."""
    # Register and login
    client.post('/register', data={
        'csrf_token': 'test-token',
        'name': 'Test User',
        'email': 'test@example.com',
        'program': 'CS',
        'password': 'password123'
    })
    
    response = client.get('/student/1')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    assert 'logout-btn' in html
    assert '/logout' in html
