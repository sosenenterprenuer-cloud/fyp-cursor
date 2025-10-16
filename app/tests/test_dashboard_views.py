"""Student dashboard view tests updated for simplified mastery flow."""


def test_student_dashboard_renders(logged_in_client):
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'Student Dashboard' in html
    assert 'Progression Status' in html
    assert 'Concept Path to Mastery' in html


def test_dashboard_shows_action_buttons(logged_in_client):
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    # Should contain links to retake and module pages
    assert 'Reattempt Quiz' in html or 'Start Quiz' in html
    assert '/module/fundamentals' in html
    assert '/module/norm' in html


def test_dashboard_displays_lock_message_until_perfect(logged_in_client):
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'Get 100% in both topics (this recent quiz) to proceed.' in html


def test_dashboard_shows_concept_breakdown(logged_in_client):
    response = logged_in_client.get('/student/1')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'Data Modeling &amp; DBMS Fundamentals' in html
    assert 'Normalization &amp; Dependencies' in html
    assert '% →' in html  # summary formatting marker


def test_dashboard_access_restricted_to_self(logged_in_client):
    response = logged_in_client.get('/student/999')
    assert response.status_code == 302
    assert '/student/1' in response.location


def test_reattempt_redirects_to_quiz(logged_in_client):
    response = logged_in_client.get('/reattempt')
    assert response.status_code == 302
    assert '/quiz' in response.location


def test_modules_page_renders(logged_in_client):
    response = logged_in_client.get('/modules')
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'Learning Modules' in html
    assert 'Start Learning' in html
