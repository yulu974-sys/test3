# -*- coding: utf-8 -*-
import os
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

USER_FILE = "users.json"


# =========================
# JSON 基本操作
# =========================
def init_json_file(file_path: str) -> None:
    if not os.path.exists(file_path):
        default_data = {
            "users": [
                {
                    "username": "admin",
                    "email": "admin@example.com",
                    "password": "admin123",
                    "phone": "0912345678",
                    "birthdate": "1990-01-01"
                }
            ]
        }
        save_users(file_path, default_data)


def read_users(file_path: str) -> dict:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "users" not in data:
            data["users"] = []

        return data

    except FileNotFoundError:
        init_json_file(file_path)
        return read_users(file_path)

    except json.JSONDecodeError:
        return {"users": []}


def save_users(file_path: str, data: dict) -> bool:
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


# =========================
# 驗證函式
# =========================
def validate_email(email: str) -> bool:
    return "@" in email and "." in email


def validate_password(password: str) -> bool:
    return 6 <= len(password) <= 16


def validate_phone(phone: str) -> bool:
    if phone == "":
        return True
    return len(phone) == 10 and phone.isdigit() and phone.startswith("09")


def validate_register(form_data: dict, users: list) -> dict:
    username = form_data.get("username", "").strip()
    email = form_data.get("email", "").strip()
    password = form_data.get("password", "").strip()
    phone = form_data.get("phone", "").strip()
    birthdate = form_data.get("birthdate", "").strip()

    if username == "" or email == "" or password == "" or birthdate == "":
        return {"success": False, "error": "帳號、Email、密碼、出生日期為必填"}

    if not validate_email(email):
        return {"success": False, "error": "Email 格式錯誤"}

    if not validate_password(password):
        return {"success": False, "error": "密碼長度需為 6 到 16 字元"}

    if not validate_phone(phone):
        return {"success": False, "error": "電話需為 10 碼數字且以 09 開頭"}

    for user in users:
        if user["username"] == username:
            return {"success": False, "error": "帳號已存在"}
        if user["email"] == email:
            return {"success": False, "error": "Email 已存在"}

    return {
        "success": True,
        "data": {
            "username": username,
            "email": email,
            "password": password,
            "phone": phone,
            "birthdate": birthdate
        }
    }


def verify_login(email: str, password: str, users: list) -> dict:
    for user in users:
        if user["email"] == email and user["password"] == password:
            return {"success": True, "data": user}

    return {"success": False, "error": "Email 或密碼錯誤"}


def find_user(username: str, users: list):
    for user in users:
        if user["username"] == username:
            return user
    return None


# =========================
# 裝飾器：登入與權限檢查
# =========================
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("error_route", message="請先登入"))
        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("error_route", message="請先登入"))

        if not session.get("is_admin"):
            return redirect(url_for("error_route", message="無權限訪問"))

        return func(*args, **kwargs)
    return wrapper


# =========================
# 自訂過濾器
# =========================
@app.template_filter("mask_phone")
def mask_phone(phone: str) -> str:
    if not phone:
        return "未填寫"
    if len(phone) < 6:
        return phone
    return phone[:4] + "****" + phone[-2:]


@app.template_filter("format_tw_date")
def format_tw_date(date_str: str) -> str:
    try:
        parts = date_str.split("-")
        year = int(parts[0]) - 1911
        month = parts[1]
        day = parts[2]
        return f"民國{year}年{month}月{day}日"
    except Exception:
        return date_str


# =========================
# 路由
# =========================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register_route():
    if request.method == "POST":
        data = read_users(USER_FILE)
        result = validate_register(request.form, data["users"])

        if not result["success"]:
            return redirect(url_for("error_route", message=result["error"]))

        data["users"].append(result["data"])
        save_users(USER_FILE, data)
        return redirect(url_for("login_route"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login_route():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        data = read_users(USER_FILE)
        result = verify_login(email, password, data["users"])

        if not result["success"]:
            return redirect(url_for("error_route", message=result["error"]))

        user_data = result["data"]
        session["username"] = user_data["username"]
        session["is_admin"] = user_data["username"] == "admin"

        return redirect(url_for("announcement"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/announcement")
@login_required
def announcement():
    return render_template("announcement.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    data = read_users(USER_FILE)
    current_user = find_user(session["username"], data["users"])

    if current_user is None:
        session.clear()
        return redirect(url_for("error_route", message="使用者不存在"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        birthdate = request.form.get("birthdate", "").strip()
        password = request.form.get("password", "").strip()

        if email == "" or birthdate == "":
            return redirect(url_for("error_route", message="Email 與出生日期不可空白"))

        if not validate_email(email):
            return redirect(url_for("error_route", message="Email 格式錯誤"))

        if not validate_phone(phone):
            return redirect(url_for("error_route", message="電話需為 10 碼數字且以 09 開頭"))

        if password != "" and not validate_password(password):
            return redirect(url_for("error_route", message="密碼長度需為 6 到 16 字元"))

        for user in data["users"]:
            if user["username"] != session["username"] and user["email"] == email:
                return redirect(url_for("error_route", message="Email 已被其他會員使用"))

        current_user["email"] = email
        current_user["phone"] = phone
        current_user["birthdate"] = birthdate

        if password != "":
            current_user["password"] = password

        save_users(USER_FILE, data)
        return redirect(url_for("profile"))

    return render_template("profile.html", user=current_user)


@app.route("/users")
@admin_required
def users_list_route():
    data = read_users(USER_FILE)
    return render_template("users.html", users=data["users"])


@app.route("/users/<username>/edit", methods=["GET", "POST"])
@admin_required
def edit_user_route(username):
    data = read_users(USER_FILE)
    user = find_user(username, data["users"])

    if user is None:
        return redirect(url_for("error_route", message="找不到會員"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        birthdate = request.form.get("birthdate", "").strip()
        password = request.form.get("password", "").strip()

        if birthdate == "":
            return redirect(url_for("error_route", message="出生日期不可空白"))

        if not validate_phone(phone):
            return redirect(url_for("error_route", message="電話需為 10 碼數字且以 09 開頭"))

        if password != "" and not validate_password(password):
            return redirect(url_for("error_route", message="密碼長度需為 6 到 16 字元"))

        user["phone"] = phone
        user["birthdate"] = birthdate

        if password != "":
            user["password"] = password

        save_users(USER_FILE, data)
        return redirect(url_for("users_list_route"))

    return render_template("edit_user.html", user=user)


@app.route("/users/<username>/delete", methods=["POST"])
@admin_required
def delete_user_route(username):
    if username == "admin":
        return redirect(url_for("error_route", message="不可刪除 admin 帳號"))

    if username == session.get("username"):
        return redirect(url_for("error_route", message="不可刪除自己"))

    data = read_users(USER_FILE)

    new_users = []
    deleted = False

    for user in data["users"]:
        if user["username"] == username:
            deleted = True
        else:
            new_users.append(user)

    if not deleted:
        return redirect(url_for("error_route", message="找不到會員"))

    data["users"] = new_users
    save_users(USER_FILE, data)

    return redirect(url_for("users_list_route"))


@app.route("/error")
def error_route():
    message = request.args.get("message", "發生未知錯誤")
    return render_template("error.html", message=message)


if __name__ == "__main__":
    init_json_file(USER_FILE)
    app.run(debug=True)
