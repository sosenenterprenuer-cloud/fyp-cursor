 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app/tests/test_dashboard_views.py b/app/tests/test_dashboard_views.py
index fdfa9feae6b0e45153befaf4cb736de7483b9a70..cb3e0723dfd990ff2b6701a250497a9532e6f9f7 100644
--- a/app/tests/test_dashboard_views.py
+++ b/app/tests/test_dashboard_views.py
@@ -1,102 +1,61 @@
-"""Test dashboard views and functionality."""
-
-import pytest
-
-
-def test_student_dashboard_renders_200(logged_in_client):
-    """Test that student dashboard renders successfully."""
-    response = logged_in_client.get('/student/1')
-    assert response.status_code == 200
-    
-    html = response.get_data(as_text=True)
-    assert 'Student Dashboard' in html
-    assert 'Recent Score' in html
-    assert 'Next Step' in html
-    assert 'Concept Mastery' in html
-
-
-def test_dashboard_shows_reattempt_button(logged_in_client):
-    """Test that dashboard shows Reattempt button."""
-    response = logged_in_client.get('/student/1')
-    assert response.status_code == 200
-    
-    html = response.get_data(as_text=True)
-    # Should contain reattempt button
-    assert 'Reattempt Quiz' in html
-    assert '/reattempt' in html
-
-
-def test_dashboard_no_time_display(logged_in_client):
-    """Test that dashboard does not show time strings in student view."""
-    response = logged_in_client.get('/student/1')
-    assert response.status_code == 200
-    
-    html = response.get_data(as_text=True)
-    # Should not contain time-related strings in the main view (but allow in CSS/JS)
-    # Check that time-related content is not displayed in the main content area
-    assert 'response_time_s' not in html  # Should not show raw time data
-    assert 'Avg Time' not in html  # Should not show time averages
-    assert 'Time(s)' not in html  # Should not show time column headers
-
-
-def test_dashboard_shows_per_concept_accuracy_and_mastered(logged_in_client):
-    """Test that dashboard shows per-concept accuracy and mastered status."""
-    response = logged_in_client.get('/student/1')
-    assert response.status_code == 200
-    
-    html = response.get_data(as_text=True)
-    # Should contain concept-related elements
-    assert 'Accuracy' in html
-    assert 'Mastered' in html or 'Learning' in html
-
-
-def test_next_step_shows_first_not_mastered_concept(logged_in_client):
-    """Test that next step shows first not-mastered concept."""
-    response = logged_in_client.get('/student/1')
-    assert response.status_code == 200
-    
-    html = response.get_data(as_text=True)
-    # Should contain next step concept or mastered message
-    assert 'Next Step' in html
-    # Should either show a concept name or mastered message
-    assert ('Functional Dependency' in html or 
-            'Atomic Values' in html or 
-            'Partial Dependency' in html or 
-            'Transitive Dependency' in html or
-            'mastered' in html.lower())
-
-
-def test_next_step_links_to_modules(logged_in_client):
-    """Test that next step links to modules page."""
-    response = logged_in_client.get('/student/1')
-    assert response.status_code == 200
-    
-    html = response.get_data(as_text=True)
-    # Should contain link to modules
-    assert '/modules' in html
-    assert 'Study Module' in html
-
-
-def test_dashboard_access_restricted_to_own_student_id(logged_in_client):
-    """Test that dashboard access is restricted to own student ID."""
-    # Try to access another student's dashboard
-    response = logged_in_client.get('/student/999')
-    assert response.status_code == 302  # Should redirect
-    assert '/student/1' in response.location  # Should redirect to own dashboard
-
-
-def test_reattempt_creates_new_attempt(logged_in_client):
-    """Test that reattempt creates new attempt and redirects to quiz."""
-    response = logged_in_client.get('/reattempt')
-    assert response.status_code == 302
-    assert '/quiz' in response.location
-
-
-def test_modules_page_renders(logged_in_client):
-    """Test that modules page renders successfully."""
-    response = logged_in_client.get('/modules')
-    assert response.status_code == 200
-    
-    html = response.get_data(as_text=True)
-    assert 'Learning Modules' in html
-    assert 'Study Module' in html
+"""Student dashboard view tests updated for simplified mastery flow."""
+
+
+def test_student_dashboard_renders(logged_in_client):
+    response = logged_in_client.get('/student/1')
+    assert response.status_code == 200
+
+    html = response.get_data(as_text=True)
+    assert 'Student Dashboard' in html
+    assert 'Progression Status' in html
+    assert 'Concept Path to Mastery' in html
+
+
+def test_dashboard_shows_action_buttons(logged_in_client):
+    response = logged_in_client.get('/student/1')
+    assert response.status_code == 200
+
+    html = response.get_data(as_text=True)
+    # Should contain links to retake and module pages
+    assert 'Retake Quiz' in html or 'Start Quiz' in html
+    assert '/module/fundamentals' in html
+    assert '/module/norm' in html
+
+
+def test_dashboard_displays_lock_message_until_perfect(logged_in_client):
+    response = logged_in_client.get('/student/1')
+    assert response.status_code == 200
+
+    html = response.get_data(as_text=True)
+    assert 'Get 100% in both topics (this recent quiz) to proceed.' in html
+
+
+def test_dashboard_shows_concept_breakdown(logged_in_client):
+    response = logged_in_client.get('/student/1')
+    assert response.status_code == 200
+
+    html = response.get_data(as_text=True)
+    assert 'Data Modeling &amp; DBMS Fundamentals' in html
+    assert 'Normalization &amp; Dependencies' in html
+    assert '% →' in html  # summary formatting marker
+
+
+def test_dashboard_access_restricted_to_self(logged_in_client):
+    response = logged_in_client.get('/student/999')
+    assert response.status_code == 302
+    assert '/student/1' in response.location
+
+
+def test_reattempt_redirects_to_quiz(logged_in_client):
+    response = logged_in_client.get('/reattempt')
+    assert response.status_code == 302
+    assert '/quiz' in response.location
+
+
+def test_modules_page_renders(logged_in_client):
+    response = logged_in_client.get('/modules')
+    assert response.status_code == 200
+
+    html = response.get_data(as_text=True)
+    assert 'Learning Modules' in html
+    assert 'Start Learning' in html
 
EOF
)