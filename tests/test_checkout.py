from setup_db import initialize
from repository import StoreRepository
from cart import ShoppingCart
from checkout import CheckoutService
from payments import FakePaymentGateway

def make_repo(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    return StoreRepository(str(db))

class FailingGateway:
    # Simulates the payment service crashing or timing out.
    def charge(self, amount, payment_token):
        raise ConnectionError('gateway unavailable')

# Verify Correcting Defect 9. Stock decremented before payment, never restored
def test_declined_payment_does_not_reduce_stock(tmp_path):
    repo = make_repo(tmp_path)
    cart = ShoppingCart('student', repo)
    cart.add_item('USB-01', 2)
    result = CheckoutService(repo, FakePaymentGateway(should_approve=False)).checkout(cart, 'TEST_TOKEN', 'req-1')
    assert result.status == 'declined'
    assert repo.get_product('USB-01').stock == 50

# Verify Correcting Defect 9. Stock decremented before payment, never restored
def test_payment_error_does_not_reduce_stock(tmp_path):
    repo = make_repo(tmp_path)
    cart = ShoppingCart('student', repo)
    cart.add_item('USB-01', 2)
    result = CheckoutService(repo, FailingGateway()).checkout(cart, 'TEST_TOKEN', 'req-1')
    assert result.status == 'payment_error'
    assert repo.get_product('USB-01').stock == 50

# Verify Correcting Defect 9. Stock decremented before payment, never restored
def test_approved_payment_reduces_stock(tmp_path):
    repo = make_repo(tmp_path)
    cart = ShoppingCart('student', repo)
    cart.add_item('USB-01', 2)
    result = CheckoutService(repo, FakePaymentGateway()).checkout(cart, 'TEST_TOKEN', 'req-1')
    assert result.status == 'paid'
    assert repo.get_product('USB-01').stock == 48


# Verify Correcting Defect 10. Stock can go negative
def test_second_checkout_fails_when_stock_already_sold(tmp_path):
    repo = make_repo(tmp_path)
    gateway = FakePaymentGateway()
    service = CheckoutService(repo, gateway)
    cart_a = ShoppingCart('alice', repo)
    cart_b = ShoppingCart('bob', repo)
    cart_a.add_item('LAP-01', 5)
    cart_b.add_item('LAP-01', 5)
    assert service.checkout(cart_a, 'TEST_TOKEN', 'req-a').status == 'paid'
    result_b = service.checkout(cart_b, 'TEST_TOKEN', 'req-b')
    assert result_b.status == 'out_of_stock'
    assert repo.get_product('LAP-01').stock == 0
    assert len(gateway.calls) == 1          # bob was never charged

# Verify Correcting Defect 10. Stock can go negative
def test_out_of_stock_checkout_rolls_back_all_lines(tmp_path):
    repo = make_repo(tmp_path)
    service = CheckoutService(repo, FakePaymentGateway())
    cart_a = ShoppingCart('alice', repo)
    cart_a.add_item('USB-01', 2)            # in stock
    cart_a.add_item('LAP-01', 5)            # will be sold out by bob
    cart_b = ShoppingCart('bob', repo)
    cart_b.add_item('LAP-01', 5)
    service.checkout(cart_b, 'TEST_TOKEN', 'req-b')
    result_a = service.checkout(cart_a, 'TEST_TOKEN', 'req-a')
    assert result_a.status == 'out_of_stock'
    assert repo.get_product('USB-01').stock == 50   # USB not taken either


# Verify Correcting Defect 11. Cart cleared on declined or failed payment
def test_declined_payment_keeps_cart(tmp_path):
    repo = make_repo(tmp_path)
    cart = ShoppingCart('student', repo)
    cart.add_item('USB-01', 2)
    cart.save()
    result = CheckoutService(repo, FakePaymentGateway(should_approve=False)).checkout(cart, 'TEST_TOKEN', 'req-1')
    assert result.status == 'declined'
    assert len(cart.lines) == 1
    assert cart.lines[0].quantity == 2
    assert repo.get_saved_cart('student') == [('USB-01', 2)]

# Verify Correcting Defect 11. Cart cleared on declined or failed payment
def test_paid_checkout_clears_cart(tmp_path):
    repo = make_repo(tmp_path)
    cart = ShoppingCart('student', repo)
    cart.add_item('USB-01', 2)
    cart.save()
    result = CheckoutService(repo, FakePaymentGateway()).checkout(cart, 'TEST_TOKEN', 'req-1')
    assert result.status == 'paid'
    assert cart.lines == []
    assert repo.get_saved_cart('student') == []


# Verify Correcting Defect 12. Duplicate request_id creates duplicate orders and charges
def test_duplicate_request_id_does_not_charge_twice(tmp_path):
    repo = make_repo(tmp_path)
    gateway = FakePaymentGateway()
    service = CheckoutService(repo, gateway)
    cart = ShoppingCart('student', repo)
    cart.add_item('USB-01', 1)
    first = service.checkout(cart, 'TEST_TOKEN', 'req-dup')
    cart.add_item('USB-01', 1)
    second = service.checkout(cart, 'TEST_TOKEN', 'req-dup')
    assert first.status == 'paid'
    assert second.order_id == first.order_id
    assert len(gateway.calls) == 1
    assert len(repo.list_orders('student')) == 1

# Verify Correcting Defect 12. Duplicate request_id creates duplicate orders and charges
def test_checkout_without_request_id_is_rejected(tmp_path):
    repo = make_repo(tmp_path)
    gateway = FakePaymentGateway()
    cart = ShoppingCart('student', repo)
    cart.add_item('USB-01', 1)
    result = CheckoutService(repo, gateway).checkout(cart, 'TEST_TOKEN', None)
    assert result.status == 'missing_request_id'
    assert gateway.calls == []
    assert repo.get_product('USB-01').stock == 50