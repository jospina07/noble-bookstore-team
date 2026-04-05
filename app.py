from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookstore.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --------------------------
# Database Models
# --------------------------

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)


class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer,
        db.ForeignKey('book.id'),
        nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )
    password = db.Column(
        db.String(100),
        nullable=False
    )
    role = db.Column(
        db.String(20),
        nullable=False
    )

# --------------------------
# Create Default Users
# --------------------------

def create_default_users():

    users = [

        User(
            username="EBarreno01",
            password="EBarreno01",
            role="admin"
        ),

        User(
            username="JOspina02",
            password="JOspina02",
            role="admin"
        ),

        User(
            username="KPeekSM",
            password="KPeekSM",
            role="admin"
        ),

        User(
            username="ROwens03",
            password="ROwens03",
            role="admin"
        ),

        User(
            username="FAlmasri01",
            password="FAlmasri01",
            role="user"
        )
    ]

    for user in users:

        existing = User.query.filter_by(
            username=user.username
        ).first()

        if not existing:
            db.session.add(user)

    db.session.commit()

# --------------------------
# Login Route
# --------------------------

@app.route('/', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(
            username=username,
            password=password
        ).first()

        if user:

            session['username'] = user.username
            session['role'] = user.role

            return redirect(url_for('dashboard'))

        else:
            flash("Invalid login credentials", "danger")

    return render_template('login.html')


# --------------------------
# Dashboard
# --------------------------

@app.route('/dashboard')
def dashboard():

    if 'username' not in session:
        return redirect(url_for('login'))

    return render_template(
        'dashboard.html',
        username=session['username'],
        role=session['role']
    )


# --------------------------
# Book Management
# --------------------------

@app.route('/books')
def books():

    all_books = Book.query.all()

    return render_template(
        'books.html',
        books=all_books
    )


@app.route('/add_book', methods=['GET', 'POST'])
def add_book():

    if request.method == 'POST':

        try:

            title = request.form['title']
            author = request.form['author']
            isbn = request.form['isbn']
            quantity = int(request.form['quantity'])

            new_book = Book(
                title=title,
                author=author,
                isbn=isbn,
                quantity=quantity
            )

            db.session.add(new_book)
            db.session.commit()

            flash(
                f"Book '{title}' added successfully!",
                "success"
            )

            return redirect(url_for('books'))

        except Exception as e:

            flash(
                f"Error adding book: {e}",
                "danger"
            )

            return redirect(url_for('add_book'))

    return render_template('add_book.html')


@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):

    book = Book.query.get_or_404(book_id)

    if request.method == 'POST':

        try:

            book.title = request.form['title']
            book.author = request.form['author']
            book.isbn = request.form['isbn']
            book.quantity = int(request.form['quantity'])

            db.session.commit()

            flash(
                f"Book '{book.title}' updated successfully!",
                "success"
            )

            return redirect(url_for('books'))

        except Exception as e:

            flash(
                f"Error updating book: {e}",
                "danger"
            )

            return redirect(
                url_for('edit_book', book_id=book.id)
            )

    return render_template(
        'edit_book.html',
        book=book
    )


@app.route('/delete_book/<int:book_id>')
def delete_book(book_id):

    book = Book.query.get_or_404(book_id)

    try:

        db.session.delete(book)
        db.session.commit()

        flash(
            f"Book '{book.title}' deleted successfully!",
            "success"
        )

    except Exception as e:

        flash(
            f"Error deleting book: {e}",
            "danger"
        )

    return redirect(url_for('books'))


# --------------------------
# Checkout
# --------------------------

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():

    if request.method == 'POST':

        try:

            subtotal = float(
                request.form['subtotal']
            )

            tax = subtotal * 0.07
            total = subtotal + tax

            sale = Sale(
                subtotal=subtotal,
                tax=tax,
                total=total
            )

            db.session.add(sale)
            db.session.commit()

            flash(
                "Sale completed!",
                "success"
            )

            return redirect(url_for('dashboard'))

        except Exception as e:

            flash(
                f"Error processing sale: {e}",
                "danger"
            )

            return redirect(url_for('checkout'))

    books = Book.query.all()

    return render_template(
        'checkout.html',
        books=books
    )


# --------------------------
# Sales History
# --------------------------

@app.route('/sales_history')
def sales_history():

    sales = Sale.query.order_by(
        Sale.date.desc()
    ).all()

    return render_template(
        'sales_history.html',
        sales=sales
    )
# --------------------------
# Low Stock
# --------------------------

@app.route('/low_stock')
def low_stock():

    threshold = 5

    low_stock_books = Book.query.filter(
        Book.quantity <= threshold
    ).all()

    return render_template(
        'low_stock.html',
        books=low_stock_books,
        threshold=threshold
    )

# --------------------------
# Purchase Orders
# --------------------------

@app.route('/purchase_orders')
def purchase_orders():

    orders = PurchaseOrder.query.all()
    books = Book.query.all()

    return render_template(
        'purchase_orders.html',
        orders=orders,
        books=books
    )


@app.route('/add_purchase_order', methods=['POST'])
def add_purchase_order():

    try:

        book_id = int(request.form['book_id'])
        quantity = int(request.form['quantity'])

        order = PurchaseOrder(
            book_id=book_id,
            quantity=quantity
        )

        db.session.add(order)
        db.session.commit()

        flash(
            "Purchase order created.",
            "success"
        )

    except Exception as e:

        flash(
            f"Error creating order: {e}",
            "danger"
        )

    return redirect(
        url_for('purchase_orders')
    )


# --------------------------
# Suppliers
# --------------------------

@app.route('/suppliers')
def suppliers():

    all_suppliers = Supplier.query.all()

    return render_template(
        'suppliers.html',
        suppliers=all_suppliers
    )


@app.route('/add_supplier', methods=['POST'])
def add_supplier():

    try:

        name = request.form['name']
        contact = request.form.get('contact', '')

        supplier = Supplier(
            name=name,
            contact=contact
        )

        db.session.add(supplier)
        db.session.commit()

        flash(
            "Supplier added.",
            "success"
        )

    except Exception as e:

        flash(
            f"Error adding supplier: {e}",
            "danger"
        )

    return redirect(
        url_for('suppliers')
    )
# --------------------------
# Main
# --------------------------

import os

if __name__ == "__main__":

    with app.app_context():
        db.create_all()
        create_default_users()

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )