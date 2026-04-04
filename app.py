from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from wtforms import StringField, FloatField, TextAreaField, SubmitField, PasswordField, ValidationError
from wtforms.validators import DataRequired, Email, NumberRange, Length
from flask_wtf import FlaskForm
from functools import wraps
import hashlib
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bookstore.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== DATABASE MODELS ====================
class User(db.Model):
    """User model for authentication."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        """Hash and set password."""
        self.password = hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password):
        """Check if password matches."""
        return self.password == hashlib.sha256(password.encode()).hexdigest()


class Book(db.Model):
    """Book model for inventory."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)

    def to_dict(self):
        """Convert book to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'price': self.price,
            'description': self.description
        }


# ==================== FORMS WITH VALIDATION ====================
class AddBookForm(FlaskForm):
    """Form to add a new book."""
    title = StringField('Book Title', validators=[
        DataRequired(message='Title is required'),
        Length(min=2, max=200, message='Title must be between 2 and 200 characters')
    ])
    author = StringField('Author', validators=[
        DataRequired(message='Author is required'),
        Length(min=2, max=120, message='Author name must be between 2 and 120 characters')
    ])
    price = FloatField('Price', validators=[
        DataRequired(message='Price is required'),
        NumberRange(min=0.01, message='Price must be greater than 0')
    ])
    description = TextAreaField('Description', validators=[
        Length(max=1000, message='Description cannot exceed 1000 characters')
    ])
    submit = SubmitField('Add Book')


class EditBookForm(FlaskForm):
    """Form to edit an existing book."""
    title = StringField('Book Title', validators=[
        DataRequired(message='Title is required'),
        Length(min=2, max=200, message='Title must be between 2 and 200 characters')
    ])
    author = StringField('Author', validators=[
        DataRequired(message='Author is required'),
        Length(min=2, max=120, message='Author name must be between 2 and 120 characters')
    ])
    price = FloatField('Price', validators=[
        DataRequired(message='Price is required'),
        NumberRange(min=0.01, message='Price must be greater than 0')
    ])
    description = TextAreaField('Description', validators=[
        Length(max=1000, message='Description cannot exceed 1000 characters')
    ])
    submit = SubmitField('Update Book')


class LoginForm(FlaskForm):
    """Form for user login."""
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    submit = SubmitField('Login')


# ==================== AUTHENTICATION HELPER ====================
def login_required(f):
    """Decorator to require login for routes."""
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
    """Display the homepage with all books."""
    books = Book.query.all()
    return render_template('index.html', books=books)


@app.route('/book/<int:book_id>')
def book_detail(book_id):
    """Display details for a specific book."""
    book = Book.query.get_or_404(book_id)
    return render_template('book_detail.html', book=book)


@app.route('/api/books')
def api_books():
    """API endpoint to get all books as JSON."""
    books = Book.query.all()
    return jsonify([book.to_dict() for book in books])


@app.route('/api/books/<int:book_id>')
def api_book_detail(book_id):
    """API endpoint to get a specific book as JSON."""
    book = Book.query.get(book_id)
    if not book:
        return jsonify({'error': 'Book not found'}), 404
    return jsonify(book.to_dict())


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('inventory'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    """Handle user logout."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))


@app.route('/inventory')
@login_required
def inventory():
    """Display inventory management screen (admin view)."""
    books = Book.query.all()
    return render_template('inventory.html', books=books)


@app.route('/add-book', methods=['GET', 'POST'])
@login_required
def add_book():
    """Handle adding a new book."""
    form = AddBookForm()
    if form.validate_on_submit():
        new_book = Book(
            title=form.title.data,
            author=form.author.data,
            price=form.price.data,
            description=form.description.data
        )
        db.session.add(new_book)
        db.session.commit()
        flash(f'Book "{new_book.title}" added successfully!', 'success')
        return redirect(url_for('inventory'))
    return render_template('add_book.html', form=form)


@app.route('/edit-book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    """Handle editing a book."""
    book = Book.query.get_or_404(book_id)
    form = EditBookForm()
    
    if form.validate_on_submit():
        book.title = form.title.data
        book.author = form.author.data
        book.price = form.price.data
        book.description = form.description.data
        db.session.commit()
        flash(f'Book "{book.title}" updated successfully!', 'success')
        return redirect(url_for('inventory'))
    
    elif request.method == 'GET':
        form.title.data = book.title
        form.author.data = book.author
        form.price.data = book.price
        form.description.data = book.description
    
    return render_template('edit_book.html', form=form, book=book)


@app.route('/delete-book/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    """Handle deleting a book."""
    book = Book.query.get_or_404(book_id)
    title = book.title
    db.session.delete(book)
    db.session.commit()
    flash(f'Book "{title}" has been deleted.', 'success')
    return redirect(url_for('inventory'))


@app.route('/about')
def about():
    """Display the about page."""
    return render_template('about.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Handle contact form."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        # In a real app, you would save this or send an email
        return render_template('contact.html', success=True, name=name)
    return render_template('contact.html')


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return render_template('500.html'), 500


# ==================== DATABASE INITIALIZATION ====================
def init_db():
    """Initialize the database with sample data."""
    with app.app_context():
        db.create_all()
        
        # Check if books already exist
        if Book.query.first() is None:
            sample_books = [
                Book(
                    title='The Great Gatsby',
                    author='F. Scott Fitzgerald',
                    price=12.99,
                    description='A classic novel of the Jazz Age.'
                ),
                Book(
                    title='To Kill a Mockingbird',
                    author='Harper Lee',
                    price=14.99,
                    description='A gripping tale of racial injustice and childhood innocence.'
                ),
                Book(
                    title='1984',
                    author='George Orwell',
                    price=13.99,
                    description='A dystopian novel about totalitarianism.'
                ),
                Book(
                    title='Pride and Prejudice',
                    author='Jane Austen',
                    price=11.99,
                    description='A romantic novel of manners and marriage.'
                ),
                Book(
                    title='The Catcher in the Rye',
                    author='J.D. Salinger',
                    price=13.99,
                    description='A story of teenage rebellion and alienation.'
                ),
            ]
            db.session.add_all(sample_books)
            db.session.commit()
        
        # Check if admin user exists
        if User.query.filter_by(username='admin').first() is None:
            admin_user = User(username='admin')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='127.0.0.1', port=5000)
