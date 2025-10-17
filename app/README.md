# Database Normalization Quiz App

A modern Flask web application for learning and practicing database normalization concepts. Features interactive quizzes, progress tracking, and personalized learning paths.

## Features

### Student Experience
- **Authentication**: Secure registration and login with password hashing
- **Interactive Quizzes**: 10-question quizzes with proper NF distribution (3 FD, 3 1NF, 2 2NF, 2 3NF)
- **Smart Results**: Immediate feedback with pass/fail logic and next steps
- **Progress Dashboard**: Visual progress tracking with concept mastery cards
- **Learning Modules**: Access to concept-specific learning resources
- **Mastery Tracking**: Automatic mastery detection based on performance
- **Recommendations**: Personalized suggestions for improvement

### Admin Features
- **Excel Import**: Bulk import questions and student history from Excel files
- **Database Management**: Safe migrations and schema updates

## Technology Stack

- **Backend**: Python 3.11, Flask, SQLite3 (no ORM)
- **Frontend**: HTML5, CSS3, JavaScript (ES6), Chart.js
- **Data Processing**: pandas, openpyxl for Excel import
- **Testing**: pytest
- **Security**: Werkzeug password hashing, CSRF protection

## Quick Start

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
# FLASK_SECRET=your-secret-key-here
# PLA_DB=instance/pla.db
# DEBUG=True
```

### 3. Database Setup

```bash
# Initialize database with schema and seed data
python -c "
import os
import sqlite3
from db_utils import ensure_db_path

db_path = ensure_db_path(os.getenv('PLA_DB'))
conn = sqlite3.connect(str(db_path))
conn.executescript(open('schema.sql').read())
conn.executescript(open('seed.sql').read())
conn.close()
print('Database initialized successfully')
"
```

### 4. Excel Data Import (Optional)

```bash
# Import questions from Excel
python import_excel.py --db instance/pla.db --questions questions.xlsx

# Import student history from Excel
python import_excel.py --db instance/pla.db --history history.xlsx

# Import both
python import_excel.py --db instance/pla.db --questions questions.xlsx --history history.xlsx
```

### 5. Run Application

```bash
# Start the development server
python app.py

# Open browser to http://localhost:5000
```

### 6. Run Tests

```bash
# Run all tests
pytest -q

# Run specific test file
pytest tests/test_auth_guard.py -v
```

## Excel Import Format

### Questions File (`questions.xlsx`)
Sheet name: `questions`

| Column | Description | Example |
|--------|-------------|---------|
| question | The quiz question text | "In relation Orders(OrderID, CustomerID), which FD holds?" |
| option_a | First answer option | "OrderID -> CustomerID, OrderDate" |
| option_b | Second answer option | "CustomerID -> OrderID" |
| option_c | Third answer option | "OrderDate -> OrderID" |
| option_d | Fourth answer option | "CustomerID, OrderDate -> OrderID" |
| correct_answer | The correct answer (exact text) | "OrderID -> CustomerID, OrderDate" |
| nf_level | Normal form level | "FD", "1NF", "2NF", "3NF" |
| concept_tag | Concept category | "Functional Dependency", "Atomic Values", etc. |
| explanation | Explanation text | "Primary key determines other attributes." |

**Requirements**: 30 questions total with at least 12 FD, 12 1NF, 3 2NF, 3 3NF questions.

### History File (`history.xlsx`)

#### Attempts Sheet
| Column | Description |
|--------|-------------|
| external_student_email | Student email address |
| started_at | Attempt start time (ISO format) |
| finished_at | Attempt end time (ISO format) |

#### Responses Sheet
| Column | Description |
|--------|-------------|
| external_student_email | Student email address |
| started_at | Matching attempt start time |
| quiz_question | Question text (must match quiz table) |
| answer | Student's answer |
| response_time_s | Response time in seconds |

## API Endpoints

### Public Routes
- `GET /` - Home page
- `GET/POST /register` - User registration
- `GET/POST /login` - User login
- `GET /logout` - User logout

### Protected Routes (require login)
- `GET /quiz` - Quiz interface
- `GET /api/quiz_progressive` - Get quiz questions
- `POST /submit` - Submit quiz answers
- `GET /student/<student_id>` - Student dashboard
- `GET /modules` - Learning modules
- `GET /module/<module_id>` - Individual module
- `GET /reattempt` - Create new attempt and start quiz

## Database Schema

### Core Tables
- **student**: User accounts with authentication
- **quiz**: Question bank with options and explanations
- **attempt**: Quiz attempts with scoring
- **response**: Individual question responses with timing
- **student_mastery**: Per-concept mastery tracking
- **module**: Learning modules and resources
- **recommendation**: Personalized learning suggestions

### Key Features
- Foreign key constraints enabled
- Automatic mastery calculation (≥3 attempts, ≥80% accuracy, ≤20s avg time)
- Recommendation generation for struggling concepts
- Time categorization (Fast <10s, Normal 10-20s, Slow >20s)

## Development

### Running Migrations
```bash
# Apply database migrations
python migrations.py
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test categories
pytest tests/test_auth_guard.py
pytest tests/test_quiz_flow.py
pytest tests/test_dashboard_views.py
pytest tests/test_nav_layout.py
pytest tests/test_import_excel.py
```

### Code Quality
- Type hints throughout
- Comprehensive error handling
- Security best practices (CSRF, password hashing)
- Responsive design
- Accessible UI components

## Deployment

### Production Setup
1. Set `DEBUG=False` in environment
2. Use a strong `FLASK_SECRET` key
3. Configure proper database path
4. Set up reverse proxy (nginx/Apache)
5. Use WSGI server (gunicorn/uWSGI)

### Environment Variables
- `FLASK_SECRET`: Flask secret key for sessions
- `PLA_DB`: SQLite database file path
- `DEBUG`: Enable/disable debug mode

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License.