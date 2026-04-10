from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from wtforms import StringField, FloatField, TextAreaField, SubmitField, PasswordField, IntegerField
from wtforms.validators import DataRequired, Email, NumberRange, Length
from flask_wtf import FlaskForm
from functools import wraps
import hashlib
import os
import barcode
from barcode.writer import ImageWriter

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
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

    def to_dict(self):
        return {
            'id': self.id, 'title': self.title, 'author': self.author,
            'isbn': self.isbn, 'price': self.price, 'quantity': self.quantity,
            'description': self.description
        }

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    tax = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)

class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100)) 

# ==================== FORMS WITH VALIDATION ====================
class AddBookForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=150)])
    author = StringField('Author', validators=[DataRequired(), Length(max=100)])
    isbn = StringField('ISBN', validators=[DataRequired(), Length(max=20)])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0.01)])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    submit = SubmitField('Add Book')

class EditBookForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=150)])
    author = StringField('Author', validators=[DataRequired(), Length(max=100)])
    isbn = StringField('ISBN', validators=[DataRequired(), Length(max=20)])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0.01)])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    submit = SubmitField('Update Book')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# ==================== AUTHENTICATION HELPER ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You must be logged in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== ROUTES ====================
@app.route('/')
def home():
    books = Book.query.all()
    return render_template('index.html', books=books)

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    return render_template('book_detail.html', book=book)

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
            return redirect(url_for('inventory'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/inventory')
@login_required
def inventory():
    books = Book.query.all()
    return render_template('inventory.html', books=books)

@app.route('/add_book', methods=['GET', 'POST'])
@login_required
def add_book():
    form = AddBookForm()
    if form.validate_on_submit():
        new_book = Book(
            title=form.title.data,
            author=form.author.data,
            isbn=form.isbn.data,
            quantity=form.quantity.data,
            price=form.price.data,
            description=form.description.data
        )
        db.session.add(new_book)
        db.session.commit()
        flash(f'Book "{new_book.title}" added successfully!', 'success')
        return redirect(url_for('inventory'))
    return render_template('add_book.html', form=form)

@app.route('/edit_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    form = EditBookForm(obj=book) # Using obj=book pre-fills the form
    
    if form.validate_on_submit():
        book.title = form.title.data
        book.author = form.author.data
        book.isbn = form.isbn.data # Fix: Actually updating ISBN
        book.quantity = form.quantity.data # Fix: Actually updating Quantity
        book.price = form.price.data
        book.description = form.description.data
        db.session.commit()
        flash(f'Book "{book.title}" updated successfully!', 'success')
        return redirect(url_for('inventory'))
    
    return render_template('edit_book.html', form=form, book=book)

@app.route('/delete_book/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    title = book.title
    db.session.delete(book)
    db.session.commit()
    flash(f'Book "{title}" has been deleted.', 'success')
    return redirect(url_for('inventory'))

@app.route('/generate_barcode/<int:book_id>')
def generate_barcode(book_id):
    book = Book.query.get_or_404(book_id)
    isbn = book.isbn
    # Ensure directory exists
    if not os.path.exists('static/barcodes'):
        os.makedirs('static/barcodes')
    code = barcode.get('isbn13', isbn, writer=ImageWriter())
    code.save(f"static/barcodes/{isbn}")
    flash("Barcode generated successfully!", "success")
    return redirect(url_for('inventory'))

@app.route('/checkout')
@login_required
def checkout():
    # Placeholder for the checkout logic
    return render_template('checkout.html')

@app.route('/low_stock')
@login_required
def low_stock():
    # Placeholder for low stock logic
    return render_template('low_stock.html')

@app.route('/sales_history')
@login_required
def sales_history():
    # Placeholder for sales history
    return render_template('sales_history.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')
# ==================== DATABASE INITIALIZATION ====================
def init_db():
    with app.app_context():
  # 
        db.create_all()
        admin = User.query.filter_by(username='admin').first()
        if not admin:
             print(" Deploy LOG: NO admin found. Creating user 'admin'...")
             admin_user = User(username='admin', role='admin')
             admin_user.set_password('admin123')
             db.session.add(admin_user)
             db.session.commit()
             print(" DEPLOY LOG: Admin created successfully!")
        else:
             print(" DEPLOY LOG: Admin user already exists.") 

init_db()

if __name__ == '__main__':
       app.run(debug=True, host='127.0.0.1', port=5000)