# Security

## 1. SQL injection in get_product
- **Location:** repository.py, StoreRepository.get_product
- **Cause:** SKU is inserted into the SQL with an f-string.
- **Reproduce:** repo.get_product("x' OR '1'='1")
- **Observed:** Returns Product(sku='LAP-01', ...), a product that was never requested.
- **Impact:** Any caller controlled SKU can rewrite the query.
- **Fix:** Use a parameterized query: cconn.execute("SELECT sku, name, price, stock FROM products WHERE sku = ?", (sku,))
- **Test:** An injection strings returns None. A normal lookup get_product returns only the requested product.

## 2. SQL injection in get_saved_cart
- **Location:** repository.py, StoreRepository.get_saved_cart
- **Cause:** user_id is inserted into the SQL with an f-string.
- **Reproduce:** repo.get_saved_cart("x' OR '1'='1")
- **Observed:** Returns every user's saved cart lines
- **Impact:** One user can load another user's cart
- **Fix:** Use a parameterized query: cconn.execute("SELECT sku, name, price, stock FROM products WHERE sku = ?", (sku,))
- **Test:** Save carts for 2 users, the injection string returns []. A normal get_saved_cart of a user returns only user's line.

## 3. list_orders leaks all users's orders
- **Location:** repository.py, StoreRepository.list_orders
- **Cause:** user_id is accepted but no WHERE clause were used to use the user_id
- **Reproduce:** repo.list_orders('u')
- **Observed:** Returns orders belong to u2
- **Impact:** Broken access control and a privacy leak
- **Fix:** Add WHERE user_id = ?: conn.execute('SELECT id, user_id, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC', (user_id,))
- **Test:** Saved orders for 2 users and asserting list_users of 1 user only returns that one user's order.


# Input validation

## 4. Zero or negative quantities accepted
- **Location:** cart.py, add_item, remove_item
- **Cause:** Missing zero or negative quantity check
- **Reproduce:** cart.add_item('USB-01', -5)
- **Observed:** Returns true, subtotal() is -49.95
- **Impact:** Negative totals, can lead to refunds or free goods.
- **Fix:** Reject quantity that is not a positive int in both add_item and remove_item.
- **Test:** add_items rejects negative or zero quantity. remove_items rejects negative quantiry, removes the whole line when zero quantity.

## 5. Stock check ignores quantity already in the cart
- **Location:** cart.py, add_item
- **Cause:** product.stock < quantity comparison only uses the new quantity
- **Reproduce:** Laptop stock is 5. Call add_item('LAP-01', 3) twice
- **Observed:** Both calls succeed and the cart quantity is 6
- **Impact:** Place order on not enough stock
- **Fix:** Check the existing stock first, then compare the combined quantity against stock in_cart + quantity > product.stock
- **Test:** add_item rejects quantity > stock. add_item allows quantity = stock.


# Business logic

## 6. Discounts stack and compound
- **Location:** cart.py, apply_discount
- **Cause:** Discount is applied to self.total() which already includes previous discount
- **Reproduce:** two mice, then apply_discount('WELCOME10') twice
- **Observed:** total price got discount twice: 59.90 → 53.91 → 48.519.
- **Impact:** Unlimited discounting
- **Fix:** Always calculate discount from subtotal(), allow only one active code
- **Test:** Applying the same discount code twice gives the same total as applying it once.

## 7. Discounted total goes stale
- **Location:** cart.py, total / apply_discount
- **Cause:** discounted_total is a cached number that never updates after add_item or remove_item
- **Reproduce:** apply a discount, add a $999.99 laptop
- **Observed:** total stays at 48.519 
- **Impact:** customer is charged the wrong amount at checkout
- **Fix:** store only discount_code, have total() calculate the discount from the current subtotal() each time it's called
- **Test:** after a discount, add an item and assert the total reflects the new subtotal

## 8. SAVE15 can make the total negative
- **Location:** cart.py, apply_discount
- **Cause:** take off $15 without checking the total order is at least $15
- **Reproduce:** one USB cable ($9.99) with SAVE15
- **Observed:** total is -5.01 
- **Impact:** negative total
- **Fix:** set a minimum order of $15 for SAVE15
- **Test:** the total is never below 0


# Data consistency (checkout)

## 9. Stock decremented before payment, never restored
- **Location:** checkout.py, checkout
- **Cause:** update_stock runs for every line before payment_gateway.charge
- **Reproduce:** checkout 2 USB cables with FakePaymentGateway(should_approve=False)
- **Observed:** status is declined, but stock dropped from 50 to 48 
- **Impact:** inventory leaks on every failed payment
- **Fix:** charge first, only decrement stock when payment is approved 
- **Test:** after a declined payment and after gateway exception, stock is unchanged

## 10. Stock can go negative
- **Location:** checkout.py, repository.update_stock
- **Cause:** stock is only checked when an item is added to cart, not at checkout.
- **Reproduce:** 2 carts each add 5 laptops. then both checkout
- **Observed:** laptop stock is -5 
- **Impact:** overselling records
- **Fix:** Replaced update_stock with reserve_stock, which decrements all lines in one transaction using WHERE stock >= ? and rolls back if any line is short. Checkout now reserves stock before charging and calls release_stock if payment is declined or errors. The unguarded update_stock was removed.
- **Test:** The second checkout fails with out of stock status, stock stays at 0

## 11. Cart cleared on declined or failed payment
- **Location:** checkout.py, at the end of checkout
- **Cause:** cart.lines.clear() and cart.save() run whatever the status is.
- **Reproduce:** declined payment
- **Observed:** after a decline, cart.lines == [] and the saved cart is empty.
- **Impact:** the customer loses their cart and can't simply retry.
- **Fix:** clear and save the cart only when the status is 'paid'.
- **Test:** after a decline, the cart lines and the saved cart are unchanged.

## 12. Duplicate request_id creates duplicate orders and charges
- **Location:** checkout.py, setup_db.py
- **Cause:** request_id is stored but never checked. Even for large orders, a missing ID only triggers a print. The orders.request_id column has no UNIQUE constraint.
- **Reproduce:** call checkout(...request_id='dup') twice.
- **Observed:** two paid orders (ids 2 and 3) and two gateway charges.
- **Impact:** a retry, double click or network replay double charges the customer.
- **Fix:** require request_id. If an order with that ID already exists, return the existing result without charging again. Add UNIQUE to request_id.
- **Test:** duplicate request_id does not charge twice. Checkout without request_id is rejected

# Reliability and Design
## 13. load() duplicates quantities
- **Location:** cart.py, load
- **Cause:** saved lines are merged into the existing in-memory lines through add_item
- **Reproduce:** add 2 USB cables, save(), then load()
- **Observed:** the quantity is 4
- **Impact:** customer is overcharged, cart and database disagree
- **Fix:** load() now clears self.lines before re-adding the saved lines, so it replaces the in-memory cart instead of merging into it. Since "Stock check ignores quantity already in the cart" was fixed, merging would also have made add_item reject some saved lines for exceeding stock, leaving a partial cart, clearing first avoids that too.
- **Test:** load does not duplicate quantities (add 2 USB cables, saves, loads, assert 1 line with quantity 2), load restores saved cart into new cart (a fresh ShoppingCart for the same user gets the saved line back)