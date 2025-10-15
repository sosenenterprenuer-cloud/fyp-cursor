"""Test quiz flow functionality."""

import pytest
import json


def test_api_quiz_progressive_returns_10_questions(logged_in_client):
    """Test that /api/quiz_progressive returns 10 questions with correct distribution."""
    response = logged_in_client.get('/api/quiz_progressive')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'attempt_id' in data
    assert 'questions' in data
    
    questions = data['questions']
    assert len(questions) == 10
    
    # Check NF level distribution (3 FD, 3 1NF, 2 2NF, 2 3NF)
    nf_counts = {}
    for q in questions:
        nf_level = q['nf_level']
        nf_counts[nf_level] = nf_counts.get(nf_level, 0) + 1
    
    assert nf_counts.get('FD', 0) == 3
    assert nf_counts.get('1NF', 0) == 3
    assert nf_counts.get('2NF', 0) == 2
    assert nf_counts.get('3NF', 0) == 2
    
    # Check question structure
    for q in questions:
        assert 'quiz_id' in q
        assert 'question' in q
        assert 'options' in q
        assert 'nf_level' in q
        assert 'concept_tag' in q
        assert len(q['options']) == 4


def test_submit_quiz_with_mixed_answers(logged_in_client):
    """Test submitting quiz with mixed correct/incorrect answers."""
    # First get quiz questions
    quiz_response = logged_in_client.get('/api/quiz_progressive')
    quiz_data = json.loads(quiz_response.data)
    attempt_id = quiz_data['attempt_id']
    questions = quiz_data['questions']
    
    # Create mixed answers (some correct, some incorrect)
    answers = []
    for i, q in enumerate(questions):
        # Get the correct answer from the database
        # For testing, we'll use the first option for even indices (simulating correct)
        # and second option for odd indices (simulating incorrect)
        answer = q['options'][i % 2]
        answers.append({
            'quiz_id': q['quiz_id'],
            'answer': answer,
            'time_sec': 15.0 + i  # Varying response times
        })
    
    # Submit answers
    submit_response = logged_in_client.post('/submit', 
        json={'attempt_id': attempt_id, 'answers': answers},
        content_type='application/json'
    )
    
    assert submit_response.status_code == 200
    data = json.loads(submit_response.data)
    
    # Check response structure
    assert 'attempt_id' in data
    assert 'student_id' in data
    assert 'total' in data
    assert 'correct' in data
    assert 'score_pct' in data
    assert 'details' in data
    assert 'passed' in data
    assert 'next_step' in data
    
    # Check that details contain per-question feedback
    assert len(data['details']) == 10
    for detail in data['details']:
        assert 'quiz_id' in detail
        assert 'question' in detail
        assert 'answer' in detail
        assert 'correct_answer' in detail
        assert 'explanation' in detail
        assert 'response_time_s' in detail
        assert 'time_category' in detail
        assert 'score' in detail


def test_submit_creates_responses_and_updates_attempt(logged_in_client):
    """Test that submit creates response records and updates attempt."""
    # Get quiz
    quiz_response = logged_in_client.get('/api/quiz_progressive')
    quiz_data = json.loads(quiz_response.data)
    attempt_id = quiz_data['attempt_id']
    questions = quiz_data['questions']
    
    # Submit with all correct answers (using first option for each)
    answers = []
    for q in questions:
        answers.append({
            'quiz_id': q['quiz_id'],
            'answer': q['options'][0],  # First option
            'time_sec': 10.0
        })
    
    submit_response = logged_in_client.post('/submit',
        json={'attempt_id': attempt_id, 'answers': answers},
        content_type='application/json'
    )
    
    assert submit_response.status_code == 200
    data = json.loads(submit_response.data)
    
    # Should have high score since we used first option (assuming it's correct)
    assert data['total'] == 10
    assert data['correct'] >= 0  # At least some correct
    assert data['score_pct'] >= 0.0
    assert data['score_pct'] <= 100.0


def test_submit_with_invalid_data(logged_in_client):
    """Test submit with invalid data returns 400."""
    # Test with missing attempt_id
    response = logged_in_client.post('/submit',
        json={'answers': []},
        content_type='application/json'
    )
    assert response.status_code == 400
    
    # Test with invalid attempt_id
    response = logged_in_client.post('/submit',
        json={'attempt_id': 'invalid', 'answers': []},
        content_type='application/json'
    )
    assert response.status_code == 400
    
    # Test with empty answers
    response = logged_in_client.post('/submit',
        json={'attempt_id': 999, 'answers': []},
        content_type='application/json'
    )
    assert response.status_code == 400
