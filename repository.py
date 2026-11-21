"""SQLite persistence. Contains deliberate reliability/security problems."""
import sqlite3
from models import Product


class StoreRepository:
    def __init__(self, db_path='shop.db'):
        self.db_path = db_path

    def connect(self):
        return sqlite3.connect(self.db_path, timeout=2)

    def get_product(self, sku):
        conn = self.connect()
        row = conn.execute("SELECT sku, name, price, stock FROM products WHERE sku = ?", (sku,)).fetchone()
        conn.close()
        return Product(*row) if row else None

    def get_saved_cart(self, user_id):
        conn = self.connect()
        rows = conn.execute("SELECT sku, quantity FROM saved_cart WHERE user_id = ?", (user_id,)).fetchall()
        conn.close()
        return rows

    def save_cart(self, user_id, lines):
        conn = self.connect()
        conn.execute('DELETE FROM saved_cart WHERE user_id = ?', (user_id,))
        for line in lines:
            conn.execute('INSERT INTO saved_cart VALUES (?, ?, ?)', (user_id, line.sku, line.quantity))
        conn.commit()
        conn.close()

    def reserve_stock(self, lines):
        conn = self.connect()
        try:
            with conn:   # commits on success, rolls back on exception
                for line in lines:
                    cur = conn.execute(
                        'UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?',
                        (line.quantity, line.sku, line.quantity))
                    if cur.rowcount == 0:
                        raise ValueError(f'Not enough stock for {line.sku}')
            return True
        except ValueError:
            return False
        finally:
            conn.close()

    def release_stock(self, lines):
        conn = self.connect()
        try:
            with conn:
                for line in lines:
                    conn.execute('UPDATE products SET stock = stock + ? WHERE sku = ?',
                                (line.quantity, line.sku))
        finally:
            conn.close()

    def save_order(self, user_id, amount, status, request_id):
        conn = self.connect()
        cur = conn.execute('INSERT INTO orders(user_id, amount, status, request_id) VALUES (?, ?, ?, ?)',
                           (user_id, amount, status, request_id))
        conn.commit()
        order_id = cur.lastrowid
        conn.close()
        return order_id

    def list_orders(self, user_id):
        conn = self.connect()
        rows = conn.execute('SELECT id, user_id, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,)).fetchall()
        conn.close()
        return rows
    
    def get_order_by_request_id(self, request_id):
        conn = self.connect()
        try:
            return conn.execute(
                'SELECT id, status, amount FROM orders WHERE request_id = ?',
                (request_id,)).fetchone()
        finally:
            conn.close()
