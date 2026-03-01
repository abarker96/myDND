from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from pymongo import MongoClient
from bson import ObjectId
import bcrypt, os

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

_client = None
def get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGODB_URI", "mongodb://localhost:27017"))
    return _client["5e-database"]

def get_user_class():
    from app import User
    return User

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home_page"))
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        user_doc = db["users"].find_one({"username": username})
        if not user_doc or not bcrypt.checkpw(password.encode(), user_doc["password_hash"]):
            flash("Invalid username or password.", "error")
            return render_template("auth/login.html")
        User = get_user_class()
        user = User(user_doc)
        login_user(user, remember=request.form.get("remember") == "on")
        flash(f"Welcome back, {username}!", "success")
        next_page = request.args.get("next")
        return redirect(next_page or url_for("home_page"))
    return render_template("auth/login.html")

@auth_bp.route("/register", methods=["GET","POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home_page"))
    if request.method == "POST":
        db = get_db()
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        confirm  = request.form.get("confirm","")
        if not username or len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(username) > 30:
            flash("Username too long (max 30 characters).", "error")
        elif not password or len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif db["users"].find_one({"username": username}):
            flash("Username already taken.", "error")
        else:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            result = db["users"].insert_one({
                "username": username,
                "password_hash": pw_hash,
                "is_admin": False,
            })
            User = get_user_class()
            user = User({"_id": result.inserted_id, "username": username, "is_admin": False})
            login_user(user)
            flash(f"Account created! Welcome, {username}!", "success")
            return redirect(url_for("home_page"))
    return render_template("auth/register.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
