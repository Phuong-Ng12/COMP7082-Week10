from setup_db import initialize
from repository import StoreRepository
from models import CartLine

# Verify Correcting Defect 1. SQL injection in get_product
def test_get_product_rejects_sql_injection(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    repo = StoreRepository(str(db))
    assert repo.get_product("NOPE' OR '1'='1") is None
    assert repo.get_product('MOU-01').name == 'Wireless mouse'

# Verify Correcting Defect 2. SQL injection in get_saved_cart
def test_get_saved_cart_rejects_sql_injection(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    repo = StoreRepository(str(db))
    repo.save_cart('alice', [CartLine('LAP-01', 'Laptop', 999.99, 1)])
    repo.save_cart('bob', [CartLine('USB-01', 'USB cable', 9.99, 3)])
    assert repo.get_saved_cart('bob') == [('USB-01', 3)]
    assert repo.get_saved_cart("bob' OR '1'='1") == []

# Verify Correcting Defect 3. list_orders leaks all users's orders
def test_list_orders_returns_only_that_users_orders(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    repo = StoreRepository(str(db))
    repo.save_order('alice', 10.00, 'paid', 'req-a')
    repo.save_order('bob', 20.00, 'paid', 'req-b')
    orders = repo.list_orders('alice')
    assert len(orders) == 1
    assert orders[0][1] == 'alice'