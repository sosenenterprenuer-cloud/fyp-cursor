"""Test Excel import functionality."""

import pytest
import os
import tempfile
import pandas as pd
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import import_excel


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Initialize with basic schema
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    
    # Create tables
    conn.executescript("""
        CREATE TABLE student (
            student_id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT UNIQUE,
            program TEXT,
            password_hash TEXT NOT NULL
        );
        
        CREATE TABLE quiz (
            quiz_id INTEGER PRIMARY KEY,
            question TEXT NOT NULL,
            options_text TEXT,
            correct_answer TEXT NOT NULL,
            nf_level TEXT NOT NULL,
            concept_tag TEXT NOT NULL,
            explanation TEXT
        );
        
        CREATE TABLE attempt (
            attempt_id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            nf_scope TEXT,
            started_at TEXT,
            finished_at TEXT,
            items_total INTEGER,
            items_correct INTEGER,
            score_pct REAL,
            FOREIGN KEY(student_id) REFERENCES student(student_id)
        );
        
        CREATE TABLE response (
            response_id INTEGER PRIMARY KEY,
            attempt_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            answer TEXT,
            score INTEGER,
            response_time_s REAL,
            FOREIGN KEY(attempt_id) REFERENCES attempt(attempt_id),
            FOREIGN KEY(student_id) REFERENCES student(student_id),
            FOREIGN KEY(quiz_id) REFERENCES quiz(quiz_id)
        );
        
        CREATE TABLE student_mastery (
            student_id INTEGER NOT NULL,
            concept_tag TEXT NOT NULL,
            mastered INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(student_id, concept_tag),
            FOREIGN KEY(student_id) REFERENCES student(student_id)
        );
        
        CREATE TABLE module (
            module_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            nf_level TEXT NOT NULL,
            concept_tag TEXT NOT NULL,
            resource_url TEXT
        );
        
        CREATE TABLE recommendation (
            recommendation_id INTEGER PRIMARY KEY,
            student_id INTEGER NOT NULL,
            concept_tag TEXT NOT NULL,
            suggested_action TEXT NOT NULL,
            module_id INTEGER,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(student_id) REFERENCES student(student_id),
            FOREIGN KEY(module_id) REFERENCES module(module_id)
        );
    """)
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    os.unlink(db_path)


@pytest.fixture
def sample_questions_file():
    """Create sample questions Excel file."""
    data = []
    
    # FD questions (12 total)
    for i in range(12):
        data.append({
            'question': f'FD Question {i+1}',
            'option_a': f'Option A{i+1}',
            'option_b': f'Option B{i+1}',
            'option_c': f'Option C{i+1}',
            'option_d': f'Option D{i+1}',
            'correct_answer': f'Option A{i+1}',
            'nf_level': 'FD',
            'concept_tag': 'Functional Dependency',
            'explanation': f'Explanation for FD question {i+1}'
        })
    
    # 1NF questions (12 total)
    for i in range(12):
        data.append({
            'question': f'1NF Question {i+1}',
            'option_a': f'Option A{i+1}',
            'option_b': f'Option B{i+1}',
            'option_c': f'Option C{i+1}',
            'option_d': f'Option D{i+1}',
            'correct_answer': f'Option A{i+1}',
            'nf_level': '1NF',
            'concept_tag': 'Atomic Values',
            'explanation': f'Explanation for 1NF question {i+1}'
        })
    
    # 2NF questions (3 total)
    for i in range(3):
        data.append({
            'question': f'2NF Question {i+1}',
            'option_a': f'Option A{i+1}',
            'option_b': f'Option B{i+1}',
            'option_c': f'Option C{i+1}',
            'option_d': f'Option D{i+1}',
            'correct_answer': f'Option A{i+1}',
            'nf_level': '2NF',
            'concept_tag': 'Partial Dependency',
            'explanation': f'Explanation for 2NF question {i+1}'
        })
    
    # 3NF questions (3 total)
    for i in range(3):
        data.append({
            'question': f'3NF Question {i+1}',
            'option_a': f'Option A{i+1}',
            'option_b': f'Option B{i+1}',
            'option_c': f'Option C{i+1}',
            'option_d': f'Option D{i+1}',
            'correct_answer': f'Option A{i+1}',
            'nf_level': '3NF',
            'concept_tag': 'Transitive Dependency',
            'explanation': f'Explanation for 3NF question {i+1}'
        })
    
    # Create Excel file
    df = pd.DataFrame(data)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
        with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='questions', index=False)
        file_path = f.name
    
    yield file_path
    
    # Cleanup
    os.unlink(file_path)


@pytest.fixture
def sample_history_file():
    """Create sample history Excel file."""
    # Create attempts data
    attempts_data = []
    for i in range(17):  # 17 students
        attempts_data.append({
            'external_student_email': f'student{i+1}@example.com',
            'started_at': f'2024-01-{15+i:02d}T10:00:00',
            'finished_at': f'2024-01-{15+i:02d}T10:30:00'
        })
    
    # Create responses data
    responses_data = []
    for i in range(17):  # 17 students
        for j in range(10):  # 10 questions per student
            responses_data.append({
                'external_student_email': f'student{i+1}@example.com',
                'started_at': f'2024-01-{15+i:02d}T10:00:00',
                'quiz_question': f'FD Question {j+1}' if j < 3 else f'1NF Question {j-2}' if j < 6 else f'2NF Question {j-5}' if j < 8 else f'3NF Question {j-7}',
                'answer': f'Option A{j+1}',
                'response_time_s': 15.0 + j
            })
    
    # Create Excel file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
        with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
            pd.DataFrame(attempts_data).to_excel(writer, sheet_name='attempts', index=False)
            pd.DataFrame(responses_data).to_excel(writer, sheet_name='responses', index=False)
        file_path = f.name
    
    yield file_path
    
    # Cleanup
    os.unlink(file_path)


def test_import_questions(temp_db, sample_questions_file):
    """Test importing questions from Excel file."""
    import_excel.import_questions(temp_db, sample_questions_file)
    
    # Check that questions were imported
    import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.execute("SELECT COUNT(*) FROM quiz")
    count = cur.fetchone()[0]
    assert count == 30  # 12+12+3+3 = 30 questions
    
    # Check NF level distribution
    cur = conn.execute("SELECT nf_level, COUNT(*) FROM quiz GROUP BY nf_level")
    nf_counts = dict(cur.fetchall())
    assert nf_counts['FD'] == 12
    assert nf_counts['1NF'] == 12
    assert nf_counts['2NF'] == 3
    assert nf_counts['3NF'] == 3
    
    conn.close()


def test_import_history(temp_db, sample_questions_file, sample_history_file):
    """Test importing student history from Excel file."""
    # First import questions (needed for responses)
    import_excel.import_questions(temp_db, sample_questions_file)
    
    # Then import history
    import_excel.import_history(temp_db, sample_history_file)
    
    # Check that students were created
    import sqlite3
    conn = sqlite3.connect(temp_db)
    cur = conn.execute("SELECT COUNT(*) FROM student")
    student_count = cur.fetchone()[0]
    assert student_count == 17
    
    # Check that attempts were created
    cur = conn.execute("SELECT COUNT(*) FROM attempt")
    attempt_count = cur.fetchone()[0]
    assert attempt_count == 17
    
    # Check that responses were created
    cur = conn.execute("SELECT COUNT(*) FROM response")
    response_count = cur.fetchone()[0]
    assert response_count == 170  # 17 students * 10 questions
    
    conn.close()


def test_import_with_missing_columns_raises_error(temp_db):
    """Test that import raises error with missing columns."""
    # Create invalid Excel file
    data = [{'question': 'Test', 'option_a': 'A'}]  # Missing required columns
    df = pd.DataFrame(data)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
        with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='questions', index=False)
        file_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Missing columns"):
            import_excel.import_questions(temp_db, file_path)
    finally:
        os.unlink(file_path)


def test_import_handles_missing_quiz_questions_gracefully(temp_db, sample_questions_file):
    """Test that import handles missing quiz questions gracefully."""
    # Import questions first
    import_excel.import_questions(temp_db, sample_questions_file)
    
    # Create history with questions that don't exist in quiz table
    responses_data = [{
        'external_student_email': 'student1@example.com',
        'started_at': '2024-01-15T10:00:00',
        'quiz_question': 'Non-existent Question',
        'answer': 'Option A1',
        'response_time_s': 15.0
    }]
    
    attempts_data = [{
        'external_student_email': 'student1@example.com',
        'started_at': '2024-01-15T10:00:00',
        'finished_at': '2024-01-15T10:30:00'
    }]
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as f:
        with pd.ExcelWriter(f.name, engine='openpyxl') as writer:
            pd.DataFrame(attempts_data).to_excel(writer, sheet_name='attempts', index=False)
            pd.DataFrame(responses_data).to_excel(writer, sheet_name='responses', index=False)
        file_path = f.name
    
    try:
        # Should not crash, should skip invalid questions
        import_excel.import_history(temp_db, file_path)
        
        # Check that student was created but no responses
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cur = conn.execute("SELECT COUNT(*) FROM student")
        assert cur.fetchone()[0] == 1
        
        cur = conn.execute("SELECT COUNT(*) FROM response")
        assert cur.fetchone()[0] == 0
        
        conn.close()
    finally:
        os.unlink(file_path)
