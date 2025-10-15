"""Test navigation layout and visibility."""

import pytest


def test_login_page_no_navbar(client):
    """Test that login page does not show navbar."""
    response = client.get('/login')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    # Should not contain navbar elements
    assert 'nav-right' not in html
    assert 'navbar' not in html or 'auth-page' in html


def test_register_page_no_navbar(client):
    """Test that register page does not show navbar."""
    response = client.get('/register')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    # Should not contain navbar elements
    assert 'nav-right' not in html
    assert 'navbar' not in html or 'auth-page' in html


def test_dashboard_shows_navbar_when_logged_in(client):
    """Test that dashboard shows navbar when user is logged in."""
    # Register a user
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
    # Should contain navbar elements
    assert 'navbar' in html
    assert 'nav-right' in html


def test_logout_present_in_navbar(client):
    """Test that logout link is present in navbar."""
    # Register a user
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
    # Should contain logout button in navbar
    assert 'logout-btn' in html
    assert '/logout' in html


def test_navbar_links_when_logged_in(client):
    """Test navbar links when user is logged in."""
    # Register a user
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
    # Should contain main navigation links
    assert '/student/1' in html  # Dashboard link
    assert '/modules' in html    # Modules link
    assert 'Home' in html        # Home link


def test_navbar_right_alignment_when_logged_in(client):
    """Test that navbar right section shows logout when logged in."""
    # Register a user
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
    # Should have nav-right section with logout
    assert 'nav-right' in html
    assert 'Logout' in html
    # Should not show login/register links
    assert 'Login' not in html
    assert 'Register' not in html
