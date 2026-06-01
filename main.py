import uuid, os, json, re, jwt

from flask import Flask, render_template, request, redirect, make_response, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from functools import wraps
from dotenv import load_dotenv
from database.db import get_db, fetchone
from database.crud import (
    get_all_items, get_item_by_id, create_item, update_item, delete_item,
    get_user_by_id, get_user_by_username, get_user_by_login, create_user,
    get_orders_by_user, get_all_orders, get_existing_order, create_order, update_order_status,
    get_dashboard_data, create_hash_log
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
JWT_SECRET = os.getenv("JWT_SECRET")


def create_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def get_current_user():
    token = request.cookies.get('jwt_token')
    if not token:
        return None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return get_user_by_id(data['user_id'])
    except:
        return None


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return redirect('/login')
        if user['is_admin'] != 1:
            return redirect('/index')
        return f(*args, **kwargs)
    return decorated


def validate_password(password):
    errors = []
    if len(password) < 8:
        errors.append('• минимум 8 символов')
    if not re.search(r'[A-Z]', password):
        errors.append('• хотя бы одна заглавная буква')
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password):
        errors.append('• хотя бы один специальный символ')
    if errors:
        return 'Пароль должен содержать:\n' + '\n'.join(errors)
    return None


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS item (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            price INTEGER NOT NULL,
            type TEXT,
            condition TEXT,
            description TEXT NOT NULL,
            number TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS "user" (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            is_admin INTEGER NOT NULL DEFAULT 0,
            uuid TEXT UNIQUE,
            created_at TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES "user"(id),
            FOREIGN KEY (item_id) REFERENCES item(id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS hash_log (
            id SERIAL PRIMARY KEY,
            request TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


@app.route('/')
@app.route('/index')
def index():
    type_filter = request.args.get('type')
    condition_filter = request.args.get('condition')
    sort = request.args.get('sort')
    data = get_all_items(type_filter, condition_filter, sort)
    return render_template('index.html', data=data)


@app.route('/state')
def state():
    return render_template('state.html')


@app.route('/api/about')
def api_about():
    with open('instance/about.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify(data)


@app.route('/create', methods=['POST', 'GET'])
@admin_required
def create():
    if request.method == 'POST':
        title = request.form['title'].strip()
        price = request.form['price'].strip()
        type_ = request.form['type']
        condition = request.form['condition']
        description = request.form['description'].strip()
        number = request.form['number'].strip()

        if not title or not price or not description or not number:
            return render_template('create.html', error='Все поля должны быть заполнены')

        try:
            create_item(title, price, type_, condition, description, number)
            return redirect('/index')
        except Exception as e:
            return f"Ошибка: {e}"
    else:
        return render_template('create.html')


@app.route('/edit/<int:id>', methods=['POST', 'GET'])
@admin_required
def edit(id):
    item = get_item_by_id(id)

    if request.method == 'POST':
        title = request.form['title'].strip()
        price = request.form['price'].strip()
        type_ = request.form['type']
        condition = request.form['condition']
        description = request.form['description'].strip()
        number = request.form['number'].strip()

        try:
            update_item(id, title, price, type_, condition, description, number)
            return redirect('/index')
        except Exception as e:
            return f"Ошибка: {e}"
    else:
        return render_template('edit.html', item=item)


@app.route('/delete/<int:id>')
@admin_required
def delete(id):
    try:
        delete_item(id)
        return redirect('/index')
    except Exception as e:
        return f"Ошибка: {e}"


@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password2 = request.form['password2']

        if password != password2:
            return render_template('register.html', error='Пароли не совпадают')

        error = validate_password(password)
        if error:
            return render_template('register.html', error=error)

        hashed_password = generate_password_hash(password)
        user_uuid = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        try:
            create_user(username, email, hashed_password, user_uuid, created_at)
            return redirect('/login')
        except Exception:
            return render_template('register.html', error='Логин или Email уже занят')
    else:
        return render_template('register.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        login_input = request.form['login']
        password = request.form['password']

        row = get_user_by_login(login_input)

        if row and check_password_hash(row['password'], password):
            token = create_token(row['id'])
            response = make_response(redirect('/index'))
            response.set_cookie('jwt_token', token, httponly=True, max_age=7*24*60*60)
            return response
        else:
            return render_template('login.html', error='Неверный логин или пароль')
    else:
        return render_template('login.html')


@app.route('/logout')
def logout():
    response = make_response(redirect('/index'))
    response.delete_cookie('jwt_token')
    return response


@app.route('/api/hash/<string:text>')
def hash_string(text):
    hashed = generate_password_hash(text)
    create_hash_log(text, hashed)
    return jsonify({"request": text, "result": hashed})


@app.route('/profile/<username>')
@jwt_required
def profile(username):
    token = request.cookies.get('jwt_token')
    data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])

    current = get_user_by_id(data['user_id'])
    row = get_user_by_username(username)

    if not row:
        return "Пользователь не найден", 404
    if current['username'] != username and current['is_admin'] != 1:
        return redirect('/index')

    return render_template('profile.html', user=row)


@app.route('/profile/<username>/refresh_token')
@jwt_required
def refresh_token(username):
    token = request.cookies.get('jwt_token')
    data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])

    new_token = create_token(data['user_id'])
    response = make_response(redirect(f'/profile/{username}'))
    response.set_cookie('jwt_token', new_token, httponly=True, max_age=7*24*60*60)
    return response


@app.route('/buy/<int:item_id>')
@jwt_required
def buy(item_id):
    token = request.cookies.get('jwt_token')
    data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])

    existing = get_existing_order(data['user_id'], item_id)
    if existing:
        return redirect('/index?error=already_bought')

    create_order(data['user_id'], item_id)
    return redirect('/orders')


@app.route('/orders')
@jwt_required
def orders():
    token = request.cookies.get('jwt_token')
    data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    data_orders = get_orders_by_user(data['user_id'])
    return render_template('orders.html', orders=data_orders)


@app.route('/admin/orders')
@admin_required
def admin_orders():
    data = get_all_orders()
    return render_template('admin_orders.html', orders=data)


@app.route('/order/<int:order_id>/status/<string:status>')
@admin_required
def change_order_status(order_id, status):
    update_order_status(order_id, status)
    return redirect('/admin/orders')


@app.route('/dashboard')
@admin_required
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/dashboard')
@admin_required
def api_dashboard():
    orders_by_status, items_by_type, orders_by_date = get_dashboard_data()
    status_map = {'pending': 'В обработке', 'paid': 'Оплачен', 'delivered': 'Доставлен'}
    return app.response_class(
        response=json.dumps({
            'orders_by_status': [{'status': status_map.get(r['status'], r['status']), 'count': r['count']} for r in orders_by_status],
            'items_by_type': [{'type': r['type'], 'count': r['count']} for r in items_by_type],
            'orders_by_date': [{'date': str(r['date']), 'count': r['count']} for r in orders_by_date]
        }, ensure_ascii=False),
        mimetype='application/json'
    )


@app.context_processor
def inject_user():
    user = get_current_user()
    return {'current_user': user}


if __name__ == '__main__':
    init_db()
    app.run(debug=True)