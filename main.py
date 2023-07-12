#BOILERPLATE
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
login_manager = LoginManager()
login_manager.init_app(app)
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL",  "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

##CONFIGURE TABLES
# Create User Class, provide user_loader callback

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    # This will be a list of BlogPost objects that is attached to each User.
    #posts is not a BlogPost object.
    posts = relationship('BlogPost', back_populates='author')
    #NOTE how each separate child class will need its own relationship attribute
    comments = relationship('Comment', back_populates='comment_author')


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    #NOTE: rather than having author as the restrictions,
    #author is now a User object, that refers to the posts
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # {{post.author.name}}=name of the author! {{post.author}} gives User_id
    author = relationship('User', back_populates="posts") 
    #NOTE how the back_populating refers back to one another
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship('Comment', back_populates='comment_blog')

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(250), nullable=False)
    #NOTE: Here, comments are children of both User and BlogPost objects. For each relationship, it needs BOTH: id with parent id ForeignKey and relationship attributes
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship('User', back_populates="comments")
    blog_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    comment_blog = relationship('BlogPost', back_populates="comments")

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id) #docs miss the query and returns attribute error

# create adminrequired decorator for restricted URLs
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            if current_user.id == 1:
                result = f(*args, **kwargs)
                return result
        except AttributeError: #Anonymous users throw AttributeError
            return abort(403)
        else:
            return abort(403)
    return wrapper

@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods = ['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method == 'POST':
        #check database for if email is already there
        if User.query.filter_by(email=request.form.get('email')).first() != None: #changed
            flash('You have already registered, try logging in instead!')
            return redirect(url_for('login'))
        else:
            hashed_salted_password = generate_password_hash(
                    request.form.get('password'), 
                    # method='pbkdf2:sha256', #this is default
                    salt_length=8)
            new_user = User(
                email = request.form.get('email'),
                password = hashed_salted_password,
                name = request.form.get('name'),
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@app.route('/login', methods = ['GET', 'POST'])
def login():
    form = LoginForm()
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password') #the password they entered
        user = User.query.filter_by(email=email).first() #the User class, containing the hashed password from reg
        if user and check_password_hash(user.password, password): #compares passwords
            login_user(user) # ONCE LOGGED IN, the current_user proxy is available in every template, e.g. {{current_user.name}}
            return redirect(url_for('get_all_posts'))
        elif user == None:
            flash("We couldn't find your email in our database. Please try again.")
        elif check_password_hash(user.password, password) == False:
            flash("Your password is incorrect. Please try again.")
        return redirect(url_for('login'))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods = ['GET', 'POST'])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    if request.method == 'POST':
        new_comment = Comment(
            text=form.comment.data,
            author_id=current_user.id,
            blog_id=post_id,
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


# @app.route("/contact")
# def contact():
#     return render_template("contact.html")


@app.route("/new-post", methods=['GET','POST'])
@login_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods = ['POST', 'GET'])
@admin_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_required
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
