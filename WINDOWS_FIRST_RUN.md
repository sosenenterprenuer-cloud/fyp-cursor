# Windows first-run guide

Follow these steps in **Command Prompt** to set up the project database on Windows.

1. Navigate to your project folder and create a virtual environment (optional but recommended):
   ```cmd
   cd path\to\fyp-cursor
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r app\requirements.txt
   ```

2. Point the application at a writable SQLite database file (the `%CD%` token expands to the current folder):
   ```cmd
   set PLA_DB=%CD%\pla.db
   ```

3. Stabilize the database and ensure required tables/columns exist (use `py` if it is available on your machine, otherwise replace it with `python`):
   ```cmd
   py -m scripts.stabilize_db_and_app
   ```

4. Import the curated 30-question bank (run once, or whenever you need to top up the quiz table; again, `python` works if `py` is unavailable):
   ```cmd
   py -m scripts.import_questions data\quiz_30.csv
   ```

   > Tip: if the CSV path is different on your system, wrap it in quotes (e.g. `"C:\\path\\quiz_30.csv"`).

5. Start the Flask development server:
   ```cmd
   cd app
   python app.py
   ```

These commands are safe to re-run. The stabilizer is idempotent, and the importer will only add questions until the quiz table reaches 30 rows.
