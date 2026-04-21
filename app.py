import os
import json
import hashlib
from datetime import datetime
from functools import wraps
from sqlalchemy import or_
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, TextAreaField, SubmitField, PasswordField, IntegerField
from wtforms.validators import DataRequired, Email, NumberRange, Length
import barcode
from barcode.writer import ImageWriter

app = Flask(__name__)

# Security & Database Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Ensure instance folder exists
os.makedirs(app.instance_path, exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'bookstore.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Create the barcodes directory if it doesn't exist
os.makedirs(os.path.join('static', 'barcodes'), exist_ok=True)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# ==================== DATABASE MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

    def set_password(self, password):
        self.password = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password == hashlib.sha256(password.encode()).hexdigest()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- FORM DEFINITION ---
class AddBookForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    author = StringField('Author', validators=[DataRequired()])
    isbn = StringField('ISBN', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Add Book')


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Allow guests if needed
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Transaction-level totals
    subtotal = db.Column(db.Float, nullable=False, default=0.0)
    tax = db.Column(db.Float, nullable=False, default=0.0)
    total = db.Column(db.Float, nullable=False, default=0.0)

    # Optional tax info for clearer receipts/history
    tax_state = db.Column(db.String(50), nullable=True)
    tax_rate = db.Column(db.Float, nullable=False, default=0.0)

    # One sale has many items
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)

    # Link to original book
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)

    # Snapshot data for history/receipt
    book_title = db.Column(db.String(200), nullable=False)
    book_isbn = db.Column(db.String(20), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    line_subtotal = db.Column(db.Float, nullable=False)   

# ==================== DATABASE MODELS ====================
class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100))

class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== FORMS ====================
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# ==================== CORE ROUTES ====================
@app.route('/')
def home():
    books = Book.query.all()
    return render_template('index.html', books=books)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f"Welcome back, {user.username}!", "success")

            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard')

            return redirect(next_page)
        else:
            flash("Invalid login credentials", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')

# --------------------------
# Dashboard
# --------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    sales = Sale.query.all()
    total_revenue = sum(sale.total for sale in sales)
    total_transactions = len(sales)
    low_stock_count = Book.query.filter(Book.quantity <= 5).count()
    total_books = Book.query.count()
    total_purchase_orders = PurchaseOrder.query.count()

    return render_template(
        'dashboard.html',
        username=current_user.username,
        role=current_user.role,
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        low_stock_count=low_stock_count,
        total_books=total_books,
        total_purchase_orders=total_purchase_orders
    )
# --------------------------
# Book Management
# --------------------------
@app.route('/inventory')
@login_required
def inventory():
    search = request.args.get('search', '').strip()

    if search:
        books = Book.query.filter(
            (Book.title.ilike(f'%{search}%')) |
            (Book.author.ilike(f'%{search}%')) |
            (Book.isbn.ilike(f'%{search}%'))
        ).all()
    else:
        books = Book.query.all()

    return render_template('inventory.html', books=books, os=os, search=search)

from sqlalchemy import or_

@app.route('/books')
def books():
    query = request.args.get('q', '').strip()

    books_query = Book.query

    if query:
        books_query = books_query.filter(
            or_(
                Book.title.ilike(f"%{query}%"),
                Book.author.ilike(f"%{query}%"),
                Book.isbn.ilike(f"%{query}%")
            )
        )

    books = books_query.all()
    return render_template('books.html', books=books, query=query)
# ==================== BOOK ACTIONS ====================

@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    form = AddBookForm()

    if form.validate_on_submit():
        try:
            # 🔍 Check for duplicate ISBN
            existing_book = Book.query.filter_by(isbn=form.isbn.data).first()

            if existing_book:
                flash(
                    f'A book with ISBN {form.isbn.data} already exists: "{existing_book.title}".',
                    'warning'
                )
                return render_template('add_book.html', form=form)

            # ✅ Create new book
            new_book = Book(
                title=form.title.data,
                author=form.author.data,
                isbn=form.isbn.data,
                price=form.price.data,
                quantity=form.quantity.data,
                description=form.description.data
            )

            db.session.add(new_book)
            db.session.commit()

            flash(f"Book '{form.title.data}' added successfully!", "success")
            return redirect(url_for('inventory'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error adding book: {e}", "danger")

    return render_template('add_book.html', form=form)

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('book_detail.html', book=book)

@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    # Fixes the 'edit_book' BuildError in the inventory
    book = Book.query.get_or_404(book_id)
    form = AddBookForm(obj=book) # Pre-fills the form with existing data
    
    if form.validate_on_submit():
        book.title = form.title.data
        book.author = form.author.data
        book.isbn = form.isbn.data
        book.price = form.price.data
        book.quantity = form.quantity.data
        book.description = form.description.data
        db.session.commit()
        flash(f'Updated "{book.title}" successfully!', 'success')
        return redirect(url_for('inventory'))
    
    return render_template('edit_book.html', form=form, book=book)

@app.route('/delete_book/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    flash(f'Deleted "{book.title}".', 'info')
    return redirect(url_for('inventory'))

@app.route('/generate_barcode/<int:book_id>')
@login_required
def generate_barcode(book_id):
    book = Book.query.get_or_404(book_id)
    isbn = book.isbn

    # Use code128 to accept any numbers/text
    barcode_dir = os.path.join(app.root_path, 'static', 'barcodes')
    if not os.path.exists(barcode_dir):
        os.makedirs(barcode_dir)

    code = barcode.get(
        'code128',
        isbn,
        writer=ImageWriter()
    )

    code.save(os.path.join(barcode_dir, isbn))

    flash("Barcode generated successfully!", "success")

    return render_template('barcode.html', book=book, barcode_url=f"barcodes/{isbn}.png")


# TASK: Barcode Lookup Logic
@app.route('/api/check_book/<isbn>')
def api_check_book(isbn):
    book = Book.query.filter_by(isbn=isbn).first()
    if book:
        return jsonify({
            'success': True,
            'id': book.id,
            'title': book.title,
            'price': book.price,
            'stock': book.quantity
        })
    return jsonify({'success': False, 'message': 'Book not found'})

# --------------------------
# Checkout
# -------------------------

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():

    if request.method == 'POST':
        cart_data = request.form.get('cart_data', '[]')

        try:
            cart = json.loads(cart_data)
        except:
            cart = []

        if not cart:
            flash('Cart is empty.', 'warning')
            return redirect(url_for('checkout'))

        tax_rate = float(request.form.get('tax_rate', 0.06))
        tax_state = request.form.get('tax_state', 'Unknown')
        cart_subtotal = 0.0
        sale_items_data = []

        for item in cart:
            book_id = int(item['id'])
            quantity = int(item['quantity'])

            book = db.session.get(Book, book_id)
            if not book:
                continue

            unit_price = float(book.price)
            line_subtotal = round(unit_price * quantity, 2)
            cart_subtotal += line_subtotal

            sale_items_data.append({
                'book_id': book.id,
                'book_title': book.title,
                'book_isbn': book.isbn,
                'quantity': quantity,
                'unit_price': unit_price,
                'line_subtotal': line_subtotal
            })

        if not sale_items_data:
            flash('No valid books found in cart.', 'warning')
            return redirect(url_for('checkout'))

        cart_subtotal = round(cart_subtotal, 2)
        cart_tax = round(cart_subtotal * tax_rate, 2)
        cart_total = round(cart_subtotal + cart_tax, 2)

        try:
            sale = Sale(
                date=datetime.utcnow(),
                user_id=current_user.id if current_user.is_authenticated else None,
                subtotal=cart_subtotal,
                tax=cart_tax,
                total=cart_total,
                tax_state=tax_state,
                tax_rate=tax_rate
            )
            db.session.add(sale)
            db.session.flush()

            for item in sale_items_data:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    book_id=item['book_id'],
                    book_title=item['book_title'],
                    book_isbn=item['book_isbn'],
                    quantity=item['quantity'],
                    unit_price=item['unit_price'],
                    line_subtotal=item['line_subtotal']
                )
                db.session.add(sale_item)

                # Reduce inventory
                book = db.session.get(Book, item['book_id'])
                if book:
                    if book.quantity < item['quantity']:
                        raise ValueError(f"Not enough stock for {book.title}")

                    book.quantity -= item['quantity']

                    # Auto-create Purchase Order when stock is low
                    if book.quantity <= 4:
                        existing_po = PurchaseOrder.query.filter_by(book_id=book.id).first()

                        if not existing_po:
                            auto_po = PurchaseOrder(
                                book_id=book.id,
                                quantity=10
                            )
                            db.session.add(auto_po)

            db.session.commit()

            flash(
                f'Sale completed successfully! '
                f'Cart subtotal: ${cart_subtotal:.2f}, '
                f'tax: ${cart_tax:.2f}, '
                f'total after tax: ${cart_total:.2f}',
                'success'
            )

            if current_user.is_authenticated:
                return redirect(url_for('sales_history'))
            else:
                return redirect(url_for('books'))

        except Exception as e:
            db.session.rollback()
            flash(f'Transaction Error: {str(e)}', 'danger')
            return redirect(url_for('checkout'))

    return render_template('checkout.html', books=Book.query.all())

@app.route("/receipt/<int:sale_id>")
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template("receipt.html", sale=sale)
# --------------------------
# Sales History
# --------------------------

@app.route('/sales_history')
@login_required
def sales_history():
    sales = Sale.query.order_by(Sale.date.desc()).all()
    return render_template('sales_history.html', sales=sales)

@app.route('/low_stock')
@login_required
def low_stock():
    threshold = 5
    books = Book.query.filter(Book.quantity <= threshold).all()
    return render_template('low_stock.html', books=books, threshold=threshold)

@app.route('/seed_suppliers')
@login_required
def seed_suppliers():
    demo_suppliers = [
        Supplier(name="Baltimore Book Distrib.", contact="orders@bmorebooks.com"),
        Supplier(name="Annapolis Paper Co.", contact="410-555-0199"),
        Supplier(name="DC Scholastic Hub", contact="dc-sales@scholastic.com")
    ]

    for s in demo_suppliers:
        existing = Supplier.query.filter_by(name=s.name).first()
        if not existing:
            db.session.add(s)

    db.session.commit()
    flash("Demo suppliers generated!", "info")
    return redirect(url_for('suppliers'))

@app.route('/suppliers')
@login_required
def suppliers():
    all_suppliers = Supplier.query.all()
    return render_template('suppliers.html', suppliers=all_suppliers)

@app.route('/purchase_orders')
@login_required
def purchase_orders():
    orders = PurchaseOrder.query.all()
    books = Book.query.all()
    return render_template('purchase_orders.html', orders=orders, books=books)

@app.route('/add_purchase_order', methods=['POST'])
@login_required
def add_purchase_order():
    try:
        book_id = int(request.form['book_id'])
        quantity = int(request.form['quantity'])

        order = PurchaseOrder(book_id=book_id, quantity=quantity)
        db.session.add(order)
        db.session.commit()

        flash('Purchase order created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating purchase order: {e}', 'danger')

    return redirect(url_for('purchase_orders'))

@app.route('/add_supplier', methods=['POST'])
@login_required
def add_supplier():
    try:
        name = request.form['name']
        contact = request.form.get('contact', '')

        existing = Supplier.query.filter_by(name=name).first()
        if existing:
            flash(f"Supplier '{name}' already exists!", "warning")
            return redirect(url_for('suppliers'))

        supplier = Supplier(name=name, contact=contact)
        db.session.add(supplier)
        db.session.commit()
        flash("Supplier added successfully!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding supplier: {e}", "danger")

    return redirect(url_for('suppliers'))

# --- SUPPLIER MANAGEMENT ---

@app.route('/delete_supplier/<int:id>', methods=['POST'])
@login_required
def delete_supplier(id):
    supplier = Supplier.query.get_or_404(id)
    try:
        db.session.delete(supplier)
        db.session.commit()
        flash('Supplier removed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: Could not remove supplier. {str(e)}', 'danger')

    return redirect(url_for('suppliers'))

# ==================== INITIALIZATION ====================
def init_db():
    with app.app_context():

        db.create_all()

        # =========================
        # 1. Create Admin Users
        # =========================
        admin_usernames = [
            'EBarreno01', 'JOspina02', 'ROwens03',
            'KPeekSM', 'CPowers04', 'FAlmarasiFadi01', 'SShad02'
        ]

        for username in admin_usernames:
            existing_user = User.query.filter_by(username=username).first()
            if not existing_user:
                new_user = User(
                    username=username,
                    role='admin'
                )
                new_user.set_password(username)
                db.session.add(new_user)
                print(f"✅ ADMIN CREATED: {username}")

        # =========================
        # 2. Seed Books (SAFE)
        # =========================
        books_to_create = [
            {
                "title": "The Great Gatsby",
                "author": "F. Scott Fitzgerald",
                "isbn": "9780743273565",
                "price": 15.00,
                "quantity": 10,
                "description": "Classic American novel set in the Jazz Age."
            },
            {
                "title": "1984",
                "author": "George Orwell",
                "isbn": "9780451524935",
                "price": 12.50,
                "quantity": 15,
                "description": "Dystopian novel about surveillance and totalitarianism."
            },
            {
                "title": "The Hobbit",
                "author": "J.R.R. Tolkien",
                "isbn": "9780547928227",
                "price": 20.00,
                "quantity": 8,
                "description": "Fantasy adventure featuring Bilbo Baggins."
            },
            {
                "title": "Attack on Titan",
                "author": "Hajime Isayama",
                "isbn": "9780316201234",
                "price": 15.99,
                "quantity": 10,
                "description": "Post-apocalyptic manga series."
            },
            {
                "title": "Atomic Habits",
                "author": "James Clear",
                "isbn": "9780735211292",
                "price": 18.00,
                "quantity": 20,
                "description": "Practical guide to building good habits."
            },
            {
                "title": "Harry Potter",
                "author": "J.K. Rowling",
                "isbn": "123456789874",
                "price": 20.99,
                "quantity": 25,
                "description": "Popular fantasy novel about a young wizard."
            }
        ]

        for b in books_to_create:
            existing_book = Book.query.filter_by(isbn=b["isbn"]).first()
            if not existing_book:
                db.session.add(Book(
                    title=b["title"],
                    author=b["author"],
                    isbn=b["isbn"],
                    price=b["price"],
                    quantity=b["quantity"],
                    description=b["description"]
                ))
                print(f"📖 Added Book: {b['title']}")

        # =========================
        # 3. Seed Suppliers
        # =========================
        suppliers = [
            {'name': 'Baltimore Book Distrib.', 'contact': 'orders@bmorebooks.com'},
            {'name': 'Annapolis Paper Co.', 'contact': '410-555-0199'},
            {'name': 'DC Scholastic Hub', 'contact': 'dc-sales@scholastic.com'}
        ]

        for s in suppliers:
            existing_supplier = Supplier.query.filter_by(name=s['name']).first()
            if not existing_supplier:
                db.session.add(Supplier(name=s['name'], contact=s['contact']))
                print(f"🏢 Added Supplier: {s['name']}")

        # =========================
        # 4. Commit Everything
        # =========================
        db.session.commit()

        print("\n✅ DATABASE INITIALIZED SAFELY (no data wiped)\n")

with app.app_context():
    db.create_all()
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)