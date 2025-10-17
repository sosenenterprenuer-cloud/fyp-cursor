# Quiz data directory

This folder ships with the curated 30-question bank used by the importer and
runtime seeding helpers. The canonical file lives at:

- `data/quiz_30.csv`

If you clone the repository and do not see the CSV, double-check that your Git
client pulled subdirectories (some sparse-checkout tools omit data folders by
default). Git does **not** sync files in real time—pull the latest commits to
update your local copy:

```bash
git pull
```

After pulling, you can confirm locally with:

```bash
ls data
```

The importer accepts either relative or absolute paths, so you may also run:

```bash
python scripts/import_questions.py data/quiz_30.csv
```

and it will resolve the file for you.
