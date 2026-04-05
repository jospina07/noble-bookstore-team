from datetime import datetime
from functools import wraps
import sqlite3

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_NAME = "books.db"

SAMPLE_BOOKS = [
    {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "isbn": "9780743273565",
        "quantity": 12,
        "price": 12.99,
        "description": "A classic novel of the Jazz Age.",
    },
    {
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "isbn": "9780061120084",
        "quantity": 9,
        "price": 14.99,
        "description": "A gripping tale of racial injustice and childhood innocence.",
    },
    {
        "title": "1984",
        "author": "George Orwell",
        "isbn": "9780451524935",
        "quantity": 7,
        "price": 13.99,
        "description": "A dystopian novel about totalitarianism.",
    },
    {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "isbn": "9780141439518",
        "quantity": 11,
        "price": 11.99,
        "description": "A romantic novel of manners and marriage.",
    },
    {
        "title": "Moby-Dick",
        "author": "Herman Melville",
        "isbn": "9781503280786",
        "quantity": 5,
        "price": 15.99,
        "description": "An obsessive seafaring pursuit of a legendary white whale.",
    },
]

DEFAULT_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "role": "admin",
    },
    {
        "username": "user",
        "password": "user123",
        "role": "user",
    },
]


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_catalog_schema():
    conn = get_db_connection()
    conn.execute(
        """
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
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(books)").fetchall()
    }

    if "description" not in columns:
        conn.execute("ALTER TABLE books ADD COLUMN description TEXT DEFAULT ''")

    if "price" not in columns:
        conn.execute("ALTER TABLE books ADD COLUMN price REAL DEFAULT 0")

    user_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }

    if "role" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")

    conn.commit()
    conn.close()


def seed_books_if_empty():
    conn = get_db_connection()
    book_count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    if book_count == 0:
        conn.executemany(
            """
            INSERT INTO books (title, author, isbn, quantity, description, price)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    book["title"],
                    book["author"],
                    book["isbn"],
                    book["quantity"],
                    book["description"],
                    book["price"],
                )
                for book in SAMPLE_BOOKS
            ],
        )
        conn.commit()

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    if user_count == 0:
        conn.executemany(
            """
            INSERT INTO users (username, password, role)
            VALUES (?, ?, ?)
            """,
            [
                (user["username"], user["password"], user["role"])
                for user in DEFAULT_USERS
            ],
        )
        conn.commit()

    conn.close()


def get_books():
    conn = get_db_connection()
    books = conn.execute("SELECT * FROM books ORDER BY id ASC").fetchall()
    conn.close()
    return books


def get_book_or_404(book_id):
    conn = get_db_connection()
    book = conn.execute(
        "SELECT * FROM books WHERE id = ?",
        (book_id,),
    ).fetchone()
    conn.close()

    if book is None:
        abort(404)

    return book


def login_required(role=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in to continue.")
                return redirect(url_for("login"))

            if role and session.get("role") != role:
                flash("You do not have permission to access that page.")
                return redirect(url_for("dashboard"))

            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator


def validate_book_form(form):
    form_data = {
        "title": form.get("title", "").strip(),
        "author": form.get("author", "").strip(),
        "isbn": form.get("isbn", "").strip(),
        "quantity": form.get("quantity", "").strip(),
        "price": form.get("price", "").strip(),
        "description": form.get("description", "").strip(),
    }
    errors = []

    if not form_data["title"]:
        errors.append("Title is required.")

    if not form_data["author"]:
        errors.append("Author is required.")

    if not form_data["description"]:
        errors.append("Description is required.")

    try:
        quantity = int(form_data["quantity"])
        if quantity < 0:
            errors.append("Quantity must be 0 or higher.")
    except ValueError:
        errors.append("Quantity must be a whole number.")
        quantity = 0

    try:
        price = float(form_data["price"])
        if price <= 0:
            errors.append("Price must be greater than 0.")
    except ValueError:
        errors.append("Price must be a valid number.")
        price = 0

    cleaned_data = {
        "title": form_data["title"],
        "author": form_data["author"],
        "isbn": form_data["isbn"] or None,
        "quantity": quantity,
        "price": round(price, 2),
        "description": form_data["description"],
    }

    return cleaned_data, errors, form_data


def build_form_data(book=None):
    if book is None:
        return {
            "title": "",
            "author": "",
            "isbn": "",
            "quantity": "",
            "price": "",
            "description": "",
        }

    return {
        "title": book["title"],
        "author": book["author"],
        "isbn": book["isbn"] or "",
        "quantity": str(book["quantity"]),
        "price": f"{book['price']:.2f}",
        "description": book["description"],
    }


@app.context_processor
def inject_template_context():
    return {"current_year": datetime.now().year}


@app.route("/")
def home():
    return render_template(
        "books.html",
        books=get_books(),
        page_title="Home - Noble Bookstore",
        active_page="home",
    )


@app.route("/about")
def about():
    return render_template(
        "about.html",
        total_titles=len(get_books()),
        page_title="About - Noble Bookstore",
        active_page="about",
    )


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form_data = {
        "name": "",
        "email": "",
        "message": "",
    }

    if request.method == "POST":
        form_data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "message": request.form.get("message", "").strip(),
        }
        errors = []

        if not form_data["name"]:
            errors.append("Name is required.")

        if not form_data["email"] or "@" not in form_data["email"]:
            errors.append("A valid email address is required.")

        if not form_data["message"]:
            errors.append("Message is required.")

        if errors:
            for error in errors:
                flash(error)
        else:
            flash("Thanks for reaching out. We received your message.")
            return redirect(url_for("contact"))

    return render_template(
        "contact.html",
        form_data=form_data,
        page_title="Contact - Noble Bookstore",
        active_page="contact",
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        ).fetchone()
        conn.close()

        if user is None:
            flash("Invalid username or password.")
        else:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash(f"Welcome back, {user['username']}.")
            return redirect(url_for("dashboard"))

    return render_template(
        "login.html",
        page_title="Login - Noble Bookstore",
        active_page="login",
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("home"))


@app.route("/books")
def books():
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required()
def dashboard():
    books = get_books()
    total_titles = len(books)
    total_units = sum(book["quantity"] for book in books)
    inventory_value = sum(book["quantity"] * book["price"] for book in books)

    return render_template(
        "dashboard.html",
        books=books,
        total_titles=total_titles,
        total_units=total_units,
        inventory_value=inventory_value,
        page_title="Inventory Dashboard - Noble Bookstore",
        active_page="dashboard",
    )


@app.route("/add_book", methods=["GET", "POST"])
@login_required(role="admin")
def add_book():
    form_data = build_form_data()

    if request.method == "POST":
        cleaned_data, errors, form_data = validate_book_form(request.form)

        if errors:
            for error in errors:
                flash(error)
        else:
            conn = get_db_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO books (title, author, isbn, quantity, description, price)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cleaned_data["title"],
                        cleaned_data["author"],
                        cleaned_data["isbn"],
                        cleaned_data["quantity"],
                        cleaned_data["description"],
                        cleaned_data["price"],
                    ),
                )
                conn.commit()
                flash("Book added to inventory.")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("ISBN must be unique. Please use a different ISBN.")
            finally:
                conn.close()

    return render_template(
        "add_book.html",
        form_data=form_data,
        page_title="Add Book - Noble Bookstore",
        active_page="add_book",
    )


@app.route("/edit_book/<int:book_id>", methods=["GET", "POST"])
@login_required(role="admin")
def edit_book(book_id):
    book = get_book_or_404(book_id)
    form_data = build_form_data(book)

    if request.method == "POST":
        cleaned_data, errors, form_data = validate_book_form(request.form)

        if errors:
            for error in errors:
                flash(error)
        else:
            conn = get_db_connection()
            try:
                conn.execute(
                    """
                    UPDATE books
                    SET title = ?,
                        author = ?,
                        isbn = ?,
                        quantity = ?,
                        description = ?,
                        price = ?
                    WHERE id = ?
                    """,
                    (
                        cleaned_data["title"],
                        cleaned_data["author"],
                        cleaned_data["isbn"],
                        cleaned_data["quantity"],
                        cleaned_data["description"],
                        cleaned_data["price"],
                        book_id,
                    ),
                )
                conn.commit()
                flash("Book updated successfully.")
                return redirect(url_for("dashboard"))
            except sqlite3.IntegrityError:
                flash("ISBN must be unique. Please use a different ISBN.")
            finally:
                conn.close()

    return render_template(
        "edit_book.html",
        form_data=form_data,
        book=book,
        page_title="Edit Book - Noble Bookstore",
        active_page="dashboard",
    )


@app.route("/book/<int:book_id>")
def book_detail(book_id):
    book = get_book_or_404(book_id)
    return render_template(
        "book_detail.html",
        book=book,
        page_title=f"{book['title']} - Noble Bookstore",
        active_page="home",
    )


@app.post("/cart/add/<int:book_id>")
def add_to_cart(book_id):
    book = get_book_or_404(book_id)
    flash(f"{book['title']} added to cart.")
    return redirect(url_for("book_detail", book_id=book_id))


if __name__ == "__main__":
    ensure_catalog_schema()
    seed_books_if_empty()
    app.run(debug=True)