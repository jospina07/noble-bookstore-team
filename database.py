import sqlite3

DB_NAME = "books.db"


def init_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # BOOKS TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS books (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        isbn TEXT UNIQUE,
        quantity INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    

    # USERS TABLE WITH ROLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT DEFAULT 'user'
    )
    """)

    conn.commit()
    conn.close()


def create_users():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    users = [

        ("EBarreno01", "team123", "admin"),
        ("JOspina02", "team123", "admin"),
        ("ROwens03", "team123", "admin"),
        ("KPeekSM", "team123", "admin"),
        ("FAlmarasiFadi01", "team123", "user")

    ]   # ← THIS WAS MISSING

    for user in users:

        try:

            cursor.execute("""
                INSERT INTO users
                (username, password, role)
                VALUES (?, ?, ?)
            """, user)

        except sqlite3.IntegrityError:

            pass

    conn.commit()
    conn.close()
 