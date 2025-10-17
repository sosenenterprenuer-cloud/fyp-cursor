"""
Excel import utilities for the PLA app.
Imports questions from questions.xlsx and student history from history.xlsx.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

if __package__:
    from .db_utils import DEFAULT_DB_RELATIVE, ensure_db_path
else:
    sys.path.insert(0, os.path.dirname(__file__))
    from db_utils import DEFAULT_DB_RELATIVE, ensure_db_path


def import_questions(db_path: str, questions_file: str) -> None:
    """Import questions from Excel file into the quiz table."""
    print(f"Importing questions from {questions_file}...")
    
    # Read questions from Excel
    df = pd.read_excel(questions_file, sheet_name="questions")
    
    # Validate required columns
    required_cols = ['question', 'option_a', 'option_b', 'option_c', 'option_d', 
                     'correct_answer', 'nf_level', 'concept_tag', 'explanation']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing columns: {missing_cols}")
    
    # Validate NF level distribution
    nf_counts = df['nf_level'].value_counts().to_dict()
    expected_counts = {'FD': 12, '1NF': 12, '2NF': 3, '3NF': 3}  # Total 30
    
    print(f"Found questions by NF level: {nf_counts}")
    for level, expected in expected_counts.items():
        actual = nf_counts.get(level, 0)
        if actual < expected:
            print(f"Warning: {level} has {actual} questions, need at least {expected}")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    
    try:
        # Clear existing questions
        conn.execute("DELETE FROM quiz")
        
        imported_count = 0
        for _, row in df.iterrows():
            # Build options_text as JSON array
            options = [
                str(row['option_a']),
                str(row['option_b']),
                str(row['option_c']),
                str(row['option_d'])
            ]
            options_text = json.dumps(options)
            
            # Insert question
            conn.execute("""
                INSERT INTO quiz (question, options_text, correct_answer, nf_level, concept_tag, explanation)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(row['question']),
                options_text,
                str(row['correct_answer']),
                str(row['nf_level']),
                str(row['concept_tag']),
                str(row['explanation']) if pd.notna(row['explanation']) else None
            ))
            imported_count += 1
        
        conn.commit()
        print(f"Successfully imported {imported_count} questions")
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def import_history(db_path: str, history_file: str) -> None:
    """Import student history from Excel file."""
    print(f"Importing history from {history_file}...")
    
    # Read attempts and responses
    attempts_df = pd.read_excel(history_file, sheet_name="attempts")
    responses_df = pd.read_excel(history_file, sheet_name="responses")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    
    try:
        # Get quiz questions for matching
        quiz_cur = conn.execute("SELECT quiz_id, question FROM quiz")
        quiz_map = {row[1]: row[0] for row in quiz_cur.fetchall()}
        
        # Process each student
        students_processed = 0
        attempts_created = 0
        responses_created = 0
        
        for email in attempts_df['external_student_email'].unique():
            # Create or find student
            student_cur = conn.execute(
                "SELECT student_id FROM student WHERE email = ?", (email,)
            )
            student_row = student_cur.fetchone()
            
            if not student_row:
                # Create new student
                conn.execute("""
                    INSERT INTO student (name, email, program, password_hash)
                    VALUES (?, ?, ?, ?)
                """, (email.split('@')[0], email, "Imported", "imported"))
                student_cur = conn.execute(
                    "SELECT student_id FROM student WHERE email = ?", (email,)
                )
                student_row = student_cur.fetchone()
            
            student_id = student_row[0]
            
            # Process attempts for this student
            student_attempts = attempts_df[attempts_df['external_student_email'] == email]
            
            for _, attempt_row in student_attempts.iterrows():
                started_at = attempt_row['started_at']
                finished_at = attempt_row.get('finished_at')
                
                # Create attempt
                conn.execute("""
                    INSERT INTO attempt (student_id, nf_scope, started_at, finished_at, items_total, items_correct, score_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, "FD+1NF+2NF+3NF", started_at, finished_at, 0, 0, 0.0))
                
                attempt_cur = conn.execute(
                    "SELECT attempt_id FROM attempt WHERE student_id = ? AND started_at = ?",
                    (student_id, started_at)
                )
                attempt_row_db = attempt_cur.fetchone()
                if not attempt_row_db:
                    continue
                
                attempt_id = attempt_row_db[0]
                attempts_created += 1
                
                # Process responses for this attempt
                attempt_responses = responses_df[
                    (responses_df['external_student_email'] == email) & 
                    (responses_df['started_at'] == started_at)
                ]
                
                correct_count = 0
                total_count = 0
                
                for _, response_row in attempt_responses.iterrows():
                    question_text = response_row['quiz_question']
                    answer = response_row['answer']
                    response_time = response_row.get('response_time_s', 0.0)
                    
                    # Find matching quiz_id
                    quiz_id = quiz_map.get(question_text)
                    if not quiz_id:
                        print(f"Warning: Question not found in quiz bank: {question_text[:50]}...")
                        continue
                    
                    # Get correct answer to calculate score
                    quiz_cur = conn.execute(
                        "SELECT correct_answer FROM quiz WHERE quiz_id = ?", (quiz_id,)
                    )
                    quiz_row = quiz_cur.fetchone()
                    if not quiz_row:
                        continue
                    
                    correct_answer = quiz_row[0]
                    score = 1 if answer == correct_answer else 0
                    correct_count += score
                    total_count += 1
                    
                    # Insert response
                    conn.execute("""
                        INSERT INTO response (attempt_id, student_id, quiz_id, answer, score, response_time_s)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (attempt_id, student_id, quiz_id, answer, score, response_time))
                    responses_created += 1
                
                # Update attempt with totals
                score_pct = (correct_count / total_count * 100.0) if total_count > 0 else 0.0
                conn.execute("""
                    UPDATE attempt SET items_total = ?, items_correct = ?, score_pct = ?
                    WHERE attempt_id = ?
                """, (total_count, correct_count, score_pct, attempt_id))
            
            students_processed += 1
        
        conn.commit()
        print(f"Successfully processed {students_processed} students")
        print(f"Created {attempts_created} attempts and {responses_created} responses")
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Import Excel data into PLA database")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_RELATIVE),
        help="Database file path",
    )
    parser.add_argument("--questions", help="Questions Excel file path")
    parser.add_argument("--history", help="History Excel file path")

    args = parser.parse_args()

    try:
        if args.questions:
            import_questions(str(ensure_db_path(args.db)), args.questions)

        if args.history:
            import_history(str(ensure_db_path(args.db)), args.history)
            
        print("Import completed successfully!")
        
    except Exception as e:
        print(f"Import failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
