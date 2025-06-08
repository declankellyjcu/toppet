from flask import Blueprint, render_template, request, flash, redirect, url_for
from .models import User
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from flask_login import login_user, login_required, logout_user, current_user # <--- Ensure these are imported

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        userName = request.form.get('userName')
        password = request.form.get('password')

        user = User.query.filter_by(userName=userName).first()

        if user:
            if check_password_hash(user.password, password): 
                flash('Logged in succesfully', category='success')
                login_user(user, remember=True) # <--- Logs the user into the session
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password', category='error')
        else:
            flash('User does not exist', category='error')


    data=request.form
    print(data)
    return render_template("login.html")

@auth.route('/logout')
@login_required
def logout():
    logout_user() # <--- Logs the user out of the session
    flash('You have been logged out.', category='info')
    return redirect(url_for('auth.login'))

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        userName = request.form.get('userName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        user = User.query.filter_by(email=email).first()

        if user: 
            flash('Username already exists', category="error")
        elif len(email) < 4:
            flash('Email must be greater than 4 characters', category='error')
        elif password1 != password2:
            flash('Passwords must match', category='error')
        elif len(password1) < 3:
            flash('Passwords must be atleast 3 characters', category='error')
        else:
            new_user = User(email=email, userName=userName, password=generate_password_hash(password1))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True) # Optional: Log user in directly after signup
            flash('Account succesfully created!', category='success')
            return redirect(url_for('views.home'))

    return render_template("signup.html")
