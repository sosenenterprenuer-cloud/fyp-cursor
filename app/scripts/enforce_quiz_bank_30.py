import argparse
import os
import shutil
import sqlite3
from datetime import datetime

ALLOWED_TOPICS = {
    "Data Modeling & DBMS Fundamentals",
    "Normalization & Dependencies",
}


def resolve_db_path() -> str:
    default_db = os.path.join(os.path.dirname(__file__), "..", "pla.db")
    db_path = os.getenv("PLA_DB", default_db)
    return os.path.abspath(db_path)


def ensure_backup(db_path: str) -> str:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    backups_dir = os.path.join(root_dir, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_path = os.path.join(backups_dir, f"pla_{timestamp}.db")
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_path)
        print(f"[BACKUP] {db_path} -> {backup_path}")
    else:
        print(f"[BACKUP] No database found at {db_path}; skipping copy")
    return backup_path


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def short_question(text: str, length: int = 60) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def fetch_quiz_rows(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT quiz_id, question, two_category FROM quiz ORDER BY quiz_id"
    ).fetchall()
    return rows


def choose_keep(rows):
    fundamentals = [
        r for r in rows if r["two_category"] == "Data Modeling & DBMS Fundamentals"
    ]
    normalization = [
        r for r in rows if r["two_category"] == "Normalization & Dependencies"
    ]
    fundamentals = sorted(fundamentals, key=lambda r: r["quiz_id"])
    normalization = sorted(normalization, key=lambda r: r["quiz_id"])

    eligible_rows = sorted(fundamentals + normalization, key=lambda r: r["quiz_id"])

    keep_rows = fundamentals[:15] + normalization[:15]
    keep_ids = {row["quiz_id"] for row in keep_rows}

    if len(keep_rows) < 30:
        for row in eligible_rows:
            if row["quiz_id"] in keep_ids:
                continue
            keep_rows.append(row)
            keep_ids.add(row["quiz_id"])
            if len(keep_rows) == 30:
                break

    keep_rows = sorted(keep_rows, key=lambda r: r["quiz_id"])
    keep_ids = {row["quiz_id"] for row in keep_rows}

    return keep_rows, keep_ids, len(eligible_rows)


def report(rows, keep_rows, keep_ids):
    total = len(rows)
    per_topic = {topic: 0 for topic in ALLOWED_TOPICS}
    other_count = 0
    for row in rows:
        topic = row["two_category"] or ""
        if topic in per_topic:
            per_topic[topic] += 1
        else:
            other_count += 1

    print("\n[REPORT] Quiz bank status")
    print(f"Total rows: {total}")
    for topic in sorted(per_topic):
        print(f"  {topic}: {per_topic[topic]}")
    print(f"  Other/blank: {other_count}")

    print("\n[KEEP] 30 questions to retain:")
    for row in keep_rows:
        topic = row["two_category"] or "(blank)"
        print(f"  #{row['quiz_id']:>3} | {topic} | {short_question(row['question'])}")

    delete_rows = [r for r in rows if r["quiz_id"] not in keep_ids]
    print("\n[DELETE] Questions to remove:")
    if not delete_rows:
        print("  (none)")
    else:
        for row in delete_rows:
            topic = row["two_category"] or "(blank)"
            print(f"  #{row['quiz_id']:>3} | {topic} | {short_question(row['question'])}")
    return delete_rows


def apply_changes(conn, keep_ids):
    placeholders = ",".join("?" for _ in keep_ids)
    if not placeholders:
        raise RuntimeError("KEEP set is empty; refusing to modify database")
    keep_tuple = tuple(sorted(keep_ids))

    print("\n[APPLY] Deleting responses referencing removed questions...")
    conn.execute(
        f"DELETE FROM response WHERE quiz_id NOT IN ({placeholders})",
        keep_tuple,
    )
    print("[APPLY] Deleting quiz rows not in KEEP set...")
    conn.execute(
        f"DELETE FROM quiz WHERE quiz_id NOT IN ({placeholders})",
        keep_tuple,
    )
    conn.commit()

    remaining = conn.execute("SELECT COUNT(*) FROM quiz").fetchone()[0]
    print(f"[APPLY] Remaining quiz rows: {remaining}")
    return remaining


def main():
    parser = argparse.ArgumentParser(
        description="Ensure quiz bank holds exactly 30 questions across two topics."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show report without modifying the database.",
    )
    args = parser.parse_args()

    db_path = resolve_db_path()
    ensure_backup(db_path)

    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found at {db_path}. Nothing to enforce.")
        return

    conn = connect(db_path)
    try:
        rows = fetch_quiz_rows(conn)
        keep_rows, keep_ids, eligible_count = choose_keep(rows)

        if eligible_count < 30:
            print(
                "[ERROR] Unable to identify 30 questions within the allowed topics. "
                "Found only {} eligible rows.".format(eligible_count)
            )
            report(rows, keep_rows, keep_ids)
            return

        delete_rows = report(rows, keep_rows, keep_ids)

        if args.dry_run:
            print("\n[DRY-RUN] No changes have been made.")
            return

        if len(keep_ids) != 30:
            raise RuntimeError(
                f"KEEP set has {len(keep_ids)} entries; expected 30. Aborting to avoid data loss."
            )

        apply_changes(conn, keep_ids)
        print("[DONE] Quiz bank pruned to 30 questions.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
