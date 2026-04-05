import sqlite3

DB_NAME = "books.db"

SAMPLE_BOOKS = [
    (
        "The Great Gatsby",
        "F. Scott Fitzgerald",
        "9780743273565",
        12,
        "A classic novel of the Jazz Age.",
        12.99,
    ),
    (
        "To Kill a Mockingbird",
        "Harper Lee",
        "9780061120084",
        9,
        "A gripping tale of racial injustice and childhood innocence.",
        14.99,
    ),
    (
        "1984",
        "George Orwell",
        "9780451524935",
        7,
        "A dystopian novel about totalitarianism.",
        13.99,
    ),
    (
        "Pride and Prejudice",
        "Jane Austen",
        "9780141439518",
        11,
        "A romantic novel of manners and marriage.",
        11.99,
    ),
    (
        "Moby-Dick",
        "Herman Melville",
        "9781503280786",
        5,
        "An obsessive seafaring pursuit of a legendary white whale.",
        15.99,
    ),
]

DEFAULT_USERS = [
    ("admin", "admin123", "admin"),
    ("user", "user123", "user"),
]

def create_tables():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 📚 Books Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT UNIQUE,
            quantity INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            price REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 👤 Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    existing_count = cursor.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    if existing_count == 0:
        cursor.executemany(
            """
            INSERT INTO books (title, author, isbn, quantity, description, price)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            SAMPLE_BOOKS,
        )

    existing_users = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    if existing_users == 0:
        cursor.executemany(
            """
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
            """,
            DEFAULT_USERS,
        )

    conn.commit()
    conn.close()

    print("Books and Users tables created successfully!")


if __name__ == "__main__":
    create_tables()