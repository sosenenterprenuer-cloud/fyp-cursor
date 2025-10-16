"""Test dashboard views and functionality."""

import pytest


def test_student_dashboard_renders_200(logged_in_client):
    """Test that student dashboard renders successfully."""
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    assert 'Student Dashboard' in html
    assert 'Recent Score' in html
    assert 'Next Step' in html
    assert 'Concept Path to Mastery' in html


def test_dashboard_shows_reattempt_button(logged_in_client):
    """Test that dashboard shows Reattempt button."""
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    # Should contain reattempt button
    assert 'Reattempt Quiz' in html
    assert '/reattempt' in html


def test_dashboard_no_time_display(logged_in_client):
    """Test that dashboard does not show time strings in student view."""
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    # Should not contain time-related strings in the main view (but allow in CSS/JS)
    # Check that time-related content is not displayed in the main content area
    assert 'response_time_s' not in html  # Should not show raw time data
    assert 'Avg Time' not in html  # Should not show time averages
    assert 'Time(s)' not in html  # Should not show time column headers


def test_dashboard_highlights_mastery_pipeline(logged_in_client):
    """Test that dashboard highlights the mastery pipeline steps."""
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    # Should contain mastery pipeline labels
    assert 'Attempt' in html
    assert 'Score Full Marks' in html
    assert 'Excelled Mastery' in html
    assert 'Recommendation' in html


def test_next_step_shows_first_not_mastered_concept(logged_in_client):
    """Test that next step shows first not-mastered concept."""
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    # Should contain next step concept or mastered message
    assert 'Next Recommendation' in html
    # Should show one of the two concept names or a mastery status message
    assert (
        'Data Modeling &amp; DBMS Fundamentals' in html
        or 'Normalization &amp; Dependencies' in html
        or 'Recommendation Unlocked' in html
        or 'Focus on' in html
    )


def test_next_step_links_to_modules(logged_in_client):
    """Test that next step links to modules page."""
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    # Should contain link to modules
    assert '/modules' in html
    assert ('Review Module' in html or 'Review Modules' in html)


def test_dashboard_access_restricted_to_own_student_id(logged_in_client):
    """Test that dashboard access is restricted to own student ID."""
    # Try to access another student's dashboard
    response = logged_in_client.get('/student/999')
    assert response.status_code == 302  # Should redirect
    assert '/student/1' in response.location  # Should redirect to own dashboard


def test_reattempt_creates_new_attempt(logged_in_client):
    """Test that reattempt creates new attempt and redirects to quiz."""
    response = logged_in_client.get('/reattempt')
    assert response.status_code == 302
    assert '/quiz' in response.location


def test_modules_page_renders(logged_in_client):
    """Test that modules page renders successfully."""
    response = logged_in_client.get('/modules')
    assert response.status_code == 200
    
    html = response.get_data(as_text=True)
    assert 'Learning Modules' in html
    assert 'Start Learning' in html
