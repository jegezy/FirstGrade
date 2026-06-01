from database.db import get_db, get_slave_db, fetchone, fetchall
from datetime import datetime, timezone


# ITEM

def get_all_items(type_filter=None, condition_filter=None, sort=None):
    sql = "SELECT * FROM item WHERE status = 'active'"
    params = []
    if type_filter:
        sql += " AND type = %s"
        params.append(type_filter)
    if condition_filter:
        sql += " AND condition = %s"
        params.append(condition_filter)
    if sort == 'price_asc':
        sql += " ORDER BY price ASC"
    elif sort == 'price_desc':
        sql += " ORDER BY price DESC"
    conn = get_slave_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    data = fetchall(cur)
    conn.close()
    return data


def get_item_by_id(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM item WHERE id = %s", (item_id,))
    item = fetchone(cur)
    conn.close()
    return item


def create_item(title, price, type_, condition, description, number):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO item (title, price, type, condition, description, number) VALUES (%s, %s, %s, %s, %s, %s)",
        (title, price, type_, condition, description, number)
    )
    conn.commit()
    conn.close()


def update_item(item_id, title, price, type_, condition, description, number):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE item SET title=%s, price=%s, type=%s, condition=%s, description=%s, number=%s WHERE id=%s",
        (title, price, type_, condition, description, number, item_id)
    )
    conn.commit()
    conn.close()


def delete_item(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM item WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()


# USER

def get_user_by_id(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM "user" WHERE id = %s', (user_id,))
    row = fetchone(cur)
    conn.close()
    return row


def get_user_by_username(username):
    conn = get_slave_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM "user" WHERE username = %s', (username,))
    row = fetchone(cur)
    conn.close()
    return row


def get_user_by_login(login_input):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM "user" WHERE email = %s OR username = %s', (login_input, login_input))
    row = fetchone(cur)
    conn.close()
    return row


def create_user(username, email, hashed_password, user_uuid, created_at):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO "user" (username, email, password, is_admin, uuid, created_at) VALUES (%s, %s, %s, %s, %s, %s)',
        (username, email, hashed_password, 0, user_uuid, created_at)
    )
    conn.commit()
    conn.close()


# ORDERS

def get_orders_by_user(user_id):
    conn = get_slave_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT orders.id, item.title, item.price, orders.status, orders.created_at FROM orders JOIN item ON orders.item_id = item.id WHERE orders.user_id = %s",
        (user_id,)
    )
    data = fetchall(cur)
    conn.close()
    return data


def get_all_orders():
    conn = get_slave_db()
    cur = conn.cursor()
    cur.execute(
        'SELECT orders.id, "user".username, item.title, orders.status, orders.created_at FROM orders JOIN "user" ON orders.user_id = "user".id JOIN item ON orders.item_id = item.id'
    )
    data = fetchall(cur)
    conn.close()
    return data


def get_existing_order(user_id, item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM orders WHERE user_id = %s AND item_id = %s", (user_id, item_id))
    row = fetchone(cur)
    conn.close()
    return row


def create_order(user_id, item_id):
    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, item_id, status, created_at) VALUES (%s, %s, %s, %s)",
        (user_id, item_id, 'pending', created_at)
    )
    cur.execute("UPDATE item SET status = 'sold' WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()


def update_order_status(order_id, status):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    conn.commit()
    conn.close()


# DASHBOARD

def get_dashboard_data():
    conn = get_slave_db()
    cur = conn.cursor()
    cur.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
    orders_by_status = fetchall(cur)
    cur.execute("SELECT type, COUNT(*) as count FROM item GROUP BY type")
    items_by_type = fetchall(cur)
    cur.execute("SELECT DATE(created_at) as date, COUNT(*) as count FROM orders GROUP BY DATE(created_at) ORDER BY date")
    orders_by_date = fetchall(cur)
    conn.close()
    return orders_by_status, items_by_type, orders_by_date


# HASH LOG

def create_hash_log(text, hashed):
    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO hash_log (request, result, created_at) VALUES (%s, %s, %s)",
        (text, hashed, created_at)
    )
    conn.commit()
    conn.close()