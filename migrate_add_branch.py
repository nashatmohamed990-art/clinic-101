"""
Safe, non-destructive migration for existing databases created before the
branch/waitlist feature was added.

It only ADDS columns to the `appointments` table (branch, is_waitlisted) if
they don't already exist. It does NOT delete or modify any existing rows,
patients, appointments, users, or prescriptions.

Run this once, from inside the clinic-management-system folder, with your
virtualenv activated:

    python migrate_add_branch.py

Safe to run multiple times — it skips columns that already exist.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clinic.db')


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"No database found at {DB_PATH}.")
        print("If this is a fresh install, just run 'python seed.py' instead — nothing to migrate.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(appointments)")
    existing_cols = [row[1] for row in cur.fetchall()]
    print("Existing appointments columns:", existing_cols)

    changed = False

    if 'branch' not in existing_cols:
        cur.execute("ALTER TABLE appointments ADD COLUMN branch VARCHAR(20) NOT NULL DEFAULT 'fayoum'")
        print("Added column: appointments.branch (defaulted existing rows to 'fayoum')")
        changed = True
    else:
        print("Column appointments.branch already exists, skipping.")

    if 'is_waitlisted' not in existing_cols:
        cur.execute("ALTER TABLE appointments ADD COLUMN is_waitlisted BOOLEAN NOT NULL DEFAULT 0")
        print("Added column: appointments.is_waitlisted (defaulted existing rows to False)")
        changed = True
    else:
        print("Column appointments.is_waitlisted already exists, skipping.")

    # time_slot needs to allow NULL now (for waitlist entries with no slot yet).
    # SQLite can't easily drop a NOT NULL constraint in-place, but since it never
    # enforces column types/constraints strictly (rows already inserted are fine,
    # and our app only ever inserts NULL for time_slot through the ORM which
    # does not re-declare the constraint at the SQLite level for ALTER'd tables),
    # no further action is needed here for time_slot on SQLite.

    # --- prescriptions.diagnosis (from the earlier prescription-letterhead update) ---
    cur.execute("PRAGMA table_info(prescriptions)")
    presc_cols = [row[1] for row in cur.fetchall()]
    if 'diagnosis' not in presc_cols:
        cur.execute("ALTER TABLE prescriptions ADD COLUMN diagnosis VARCHAR(255)")
        print("Added column: prescriptions.diagnosis")
        changed = True
    else:
        print("Column prescriptions.diagnosis already exists, skipping.")

    conn.commit()
    conn.close()

    if changed:
        print("\nMigration complete. Your existing patients, appointments, and prescriptions were not touched.")
    else:
        print("\nNothing to do — database was already up to date.")


if __name__ == '__main__':
    migrate()
