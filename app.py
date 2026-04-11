import os
import hashlib
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, TextAreaField, SubmitField, PasswordField, IntegerField
from wtforms.validators import DataRequired, Email, NumberRange, Length
import barcode
from barcode.writer import ImageWriter

app = Flask(__name__)

# Security & Database Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookstore.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')

    def set_password(self, password):
        self.password = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        return self.password == hashlib.sha256(password.encode()).hexdigest()

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)

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

class AddBookForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    author = StringField('Author', validators=[DataRequired()])
    isbn = StringField('ISBN', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Add Book')

# ==================== AUTH WRAPPER ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login required to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== CORE ROUTES ====================
@app.route('/')
def home():
    books = Book.query.all()
    return render_template('index.html', books=books)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))

@app.route('/books', endpoint='books') # Explicitly naming this for the teammate's dashboard
@app.route('/inventory')
@login_required
def inventory():
    books = Book.query.all()
    return render_template('inventory.html', books=books)

# ==================== BOOK ACTIONS ====================
@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    form = AddBookForm()
    if form.validate_on_submit():
        new_book = Book(title=form.title.data, author=form.author.data, isbn=form.isbn.data, 
                        quantity=form.quantity.data, price=form.price.data, description=form.description.data)
        db.session.add(new_book)
        db.session.commit()
        flash(f'Book "{new_book.title}" added!', 'success')
        return redirect(url_for('inventory'))
    return render_template('add_book.html', form=form)

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    # Fixes the 'book_detail' BuildError on the storefront
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
    barcode_dir = os.path.join(app.root_path, 'static', 'barcodes')
    if not os.path.exists(barcode_dir):
        os.makedirs(barcode_dir)
    # Using code128 as settled for stability
    code = barcode.get('code128', isbn, writer=ImageWriter())
    code.save(os.path.join(barcode_dir, isbn))
    return render_template('barcode.html', book=book, barcode_url=f"barcodes/{isbn}.png")

# ==================== ADMIN FEATURES ====================
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session['username'], role=session['role'])

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if request.method == 'POST':
        book_id = request.form.get('book_id')
        quantity = int(request.form.get('quantity', 1))
        book = Book.query.get(book_id)
        if book and book.quantity >= quantity:
            subtotal = book.price * quantity
            tax = subtotal * 0.07
            total = subtotal + tax
            book.quantity -= quantity
            new_sale = Sale(book_id=book.id, quantity=quantity, subtotal=subtotal, tax=tax, total=total)
            db.session.add(new_sale)
            db.session.commit()
            flash('Sale completed!', 'success')
            return redirect(url_for('sales_history'))
        flash('Not enough stock!', 'danger')
    books = Book.query.all()
    return render_template('checkout.html', books=books)

@app.route('/sales_history')
@login_required
def sales_history():
    sales = Sale.query.order_by(Sale.date.desc()).all()
    return render_template('sales_history.html', sales=sales)

@app.route('/low_stock')
@login_required
def low_stock():
    books = Book.query.filter(Book.quantity <= 5).all()
    return render_template('low_stock.html', books=books)

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

@app.route('/receipt/<int:sale_id>')
@login_required
def receipt(sale_id):
    # This is a bridge for the sales system links
    sale = Sale.query.get_or_404(sale_id)
    return render_template('receipt.html', sale=sale)
# ==================== INITIALIZATION ====================
def init_db():
    with app.app_context():
        db.create_all()
        # Merge Ryan's admin creator with teammate's default list
        if not User.query.filter_by(username='admin').first():
            users_to_create = [
                ('admin', 'admin123', 'admin'),
                ('ROwens03', 'ROwens03', 'admin'),
                ('J0spina02', 'J0spina02', 'admin'),
                ('EBarreno01', 'EBarreno01', 'admin'),
                ('KPeekSM', 'KPeekSM', 'admin'),
                ('CPowersQA', 'CPowersQA', 'admin'),
                ('FAlmasri01', 'FAlmasri01', 'user')
            ]
            for u, p, r in users_to_create:
                if not User.query.filter_by(username=u).first():
                    new_user = User(username=u, role=r)
                    new_user.set_password(p)
                    db.session.add(new_user)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    # Support Render's port binding or local dev
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)