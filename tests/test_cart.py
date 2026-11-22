from setup_db import initialize
from repository import StoreRepository
from cart import ShoppingCart
import pytest

def make_cart(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    return ShoppingCart('student', StoreRepository(str(db)))

# Verify Correcting Defect 4. Zero or negative quantities accepted
def test_add_item_rejects_negative_quantity(tmp_path):
    cart = make_cart(tmp_path)
    assert cart.add_item('USB-01', -5) is False
    assert cart.lines == []
    assert cart.subtotal() == 0

# Verify Correcting Defect 4. Zero or negative quantities accepted
def test_add_item_rejects_zero_quantity(tmp_path):
    cart = make_cart(tmp_path)
    assert cart.add_item('USB-01', 0) is False
    assert cart.lines == []

# Verify Correcting Defect 4. Zero or negative quantities accepted
def test_remove_item_without_quantity_removes_whole_line(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('USB-01', 3)
    assert cart.remove_item('USB-01') is True
    assert cart.lines == []

# Verify Correcting Defect 4. Zero or negative quantities accepted
def test_remove_item_rejects_negative_quantity(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('USB-01', 3)
    assert cart.remove_item('USB-01', -2) is False
    assert cart.lines[0].quantity == 3

# Verify Correcting Defect 5. Stock check ignores quantity already in the cart
def test_add_item_rejects_quantity_exceeding_stock_across_calls(tmp_path):
    cart = make_cart(tmp_path)          # laptop stock is 5 in the seed data
    assert cart.add_item('LAP-01', 3) is True
    assert cart.add_item('LAP-01', 3) is False
    assert cart.lines[0].quantity == 3

# Verify Correcting Defect 5. Stock check ignores quantity already in the cart
def test_add_item_allows_quantity_equal_to_stock(tmp_path):
    cart = make_cart(tmp_path)
    assert cart.add_item('LAP-01', 3) is True
    assert cart.add_item('LAP-01', 2) is True
    assert cart.lines[0].quantity == 5

# Verify Correcting Defect 6. Discounts stack and compound
def test_applying_same_discount_twice_does_not_stack(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('MOU-01', 2)                  # 2 × 29.95 = 59.90
    cart.apply_discount('WELCOME10')
    cart.apply_discount('WELCOME10')
    assert cart.total() == pytest.approx(53.91)

# Verify Correcting Defect 7. Discounted total goes stale
def test_discount_updates_when_cart_changes(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('MOU-01', 2)
    cart.apply_discount('WELCOME10')
    cart.add_item('USB-01', 1)
    assert cart.total() == pytest.approx((59.90 + 9.99) * 0.9)

# Verify Correcting Defect 8. SAVE15 can make the total negative
def test_save15_rejected_below_minimum_order(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('USB-01', 1)                      # 9.99
    assert cart.apply_discount('SAVE15') is False
    assert cart.total() == pytest.approx(9.99)

# Verify Correcting Defect 8. SAVE15 can make the total negative
def test_save15_accepted_at_or_above_minimum(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('MOU-01', 1)                      # 29.95
    assert cart.apply_discount('SAVE15') is True
    assert cart.total() == pytest.approx(14.95)

# Verify Correcting Defect 8. SAVE15 can make the total negative
def test_save15_stops_applying_if_items_removed_below_minimum(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('MOU-01', 1)                      # 29.95
    cart.add_item('USB-01', 1)                      # + 9.99
    cart.apply_discount('SAVE15')
    cart.remove_item('MOU-01')                      # now 9.99
    assert cart.total() == pytest.approx(9.99)

# Verify Correcting Defect 13. load() duplicates quantities
def test_load_does_not_duplicate_quantities(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('USB-01', 2)
    cart.save()
    cart.load()
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2

# Verify Correcting Defect 13. load() duplicates quantities
def test_load_restores_saved_cart_into_new_cart(tmp_path):
    cart = make_cart(tmp_path)
    cart.add_item('USB-01', 2)
    cart.save()
    fresh = ShoppingCart('student', cart.repository)
    fresh.load()
    assert [(l.sku, l.quantity) for l in fresh.lines] == [('USB-01', 2)]