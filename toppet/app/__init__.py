# app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import environ
from flask_login import LoginManager


db = SQLAlchemy()
DB_NAME = "database.db"

# --- Calculate the actual project root directory ---
# os.path.dirname(__file__) gives the directory of the current file (app/__init__.py)
# os.path.abspath(...) makes it an absolute path
# os.path.join(..., os.pardir) goes up one level to the 'toppet' directory
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Now, define UPLOAD_FOLDER relative to that project root
UPLOAD_FOLDER_RELATIVE_TO_PROJECT_ROOT = os.path.join('static', 'uploads')
UPLOAD_FOLDER_FULL_PATH = os.path.join(PROJECT_ROOT_DIR, UPLOAD_FOLDER_RELATIVE_TO_PROJECT_ROOT)

FLASK_STATIC_FOLDER = os.path.join(PROJECT_ROOT_DIR, 'static')

# --- ADD THESE DEBUG PRINTS (VERY IMPORTANT!) ---
print(f"DEBUG: PROJECT_ROOT_DIR is: {PROJECT_ROOT_DIR}")
print(f"DEBUG: UPLOAD_FOLDER_FULL_PATH (where files are saved) is: {UPLOAD_FOLDER_FULL_PATH}")
print(f"DEBUG: FLASK_STATIC_FOLDER (where Flask serves static) is: {FLASK_STATIC_FOLDER}")
# --- END DEBUG PRINTS ---

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def create_app():
    # --- THIS IS THE CRITICAL CHANGE: Pass static_folder ---
    app = Flask(__name__, static_folder=FLASK_STATIC_FOLDER) 
    # --- END CRITICAL CHANGE ---

    app.config['SECRET_KEY'] = 'hjshjhdjah kjshkjdhjs'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    
    # Use the full, correctly calculated path for UPLOAD_FOLDER in app.config
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_FULL_PATH 
    
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

    db.init_app(app)

    from .views import views
    from .auth import auth
    from .group_bp import group_bp
    
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(group_bp, url_prefix='/')

    from .models import User, Note, Group, PetImage, GroupMember
    
    create_database(app) # This will now use the correct full path from app.config

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    return app


def create_database(app):
    database_path = os.path.join(app.root_path, DB_NAME) # This path is usually fine for database.db
    
    # Get the UPLOAD_FOLDER from app.config (which now holds the full project-level path)
    upload_path = app.config['UPLOAD_FOLDER'] 
    
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
        print(f"Created upload directory: {upload_path}") # This should now print the correct path

    if not os.path.exists(database_path):
        with app.app_context():
            db.create_all()
            print('Created Database!')
    else:
        print('Database already exists!')