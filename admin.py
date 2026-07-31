"""Admin dashboard and authentication system.

Uses simple password-based login with session storage. Stripe is queried
for subscriber/revenue data. All data is read-only from the admin side
(writes go through Stripe's API, not stored locally).
"""
import os
import time
from functools import wraps
from flask import session, redirect, url_for

# Admin password from environment (fallback to default for dev)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123").strip()

# Track admin login attempts to prevent brute force
_login_attempts = {}


def is_admin_authenticated(session_obj):
    """Check if current session is authenticated as admin."""
    if not session_obj.get("admin_authenticated"):
        return False
    # Optional: re-auth required every 24 hours
    last_auth = session_obj.get("admin_auth_time", 0)
    if time.time() - last_auth > 86400:  # 24 hours
        return False
    return True


def mark_admin_authenticated(session_obj):
    """Mark session as authenticated admin."""
    session_obj["admin_authenticated"] = True
    session_obj["admin_auth_time"] = int(time.time())
    session_obj.permanent = True


def verify_admin_password(password):
    """Verify password and return (success, message)."""
    # Rate limiting: max 5 attempts per IP per minute
    # (simplified: using password as key instead of IP for dev)
    ip_key = "admin_login"
    now = time.time()

    attempts = _login_attempts.get(ip_key, [])
    attempts = [t for t in attempts if now - t < 60]  # Prune old attempts

    if len(attempts) >= 5:
        return False, "Too many attempts. Try again in 1 minute."

    if password != ADMIN_PASSWORD:
        attempts.append(now)
        _login_attempts[ip_key] = attempts
        return False, "Incorrect password."

    # Success: clear attempts
    _login_attempts[ip_key] = []
    return True, "Login successful."


def admin_required(f):
    """Decorator to require admin authentication on a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin_authenticated(session):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function


def get_stripe_client():
    """Get authenticated Stripe client."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    return stripe


def fetch_stripe_subscribers():
    """Fetch active & trialing subscriptions from Stripe.

    Returns list of dicts:
    {
        'customer_id': 'cus_xxx',
        'email': 'user@example.com',
        'status': 'active' or 'trialing',
        'created': timestamp,
        'current_period_start': timestamp,
        'current_period_end': timestamp,
        'amount_paid': cents (int),
        'last_payment': timestamp or None,
    }
    """
    stripe = get_stripe_client()
    if not stripe.api_key:
        return []

    try:
        subs = []
        # Fetch all active subscriptions (limit 100, paginate if needed)
        subscriptions = stripe.Subscription.list(status="all", limit=100)

        for sub in subscriptions.data:
            customer = stripe.Customer.retrieve(sub.customer)

            # Get the latest invoice for payment status
            invoices = stripe.Invoice.list(customer=sub.customer, limit=1)
            last_payment = None
            if invoices.data:
                last_payment = invoices.data[0].status_transitions.paid_at

            subs.append({
                'customer_id': sub.customer,
                'email': customer.email or 'unknown',
                'status': sub.status,
                'created': sub.created,
                'current_period_start': sub.current_period_start,
                'current_period_end': sub.current_period_end,
                'amount_paid': sub.items.data[0].price.unit_amount if sub.items.data else 0,
                'last_payment': last_payment,
                'subscription_id': sub.id,
            })
        return subs
    except Exception as e:
        return []


def calculate_mrr(subscribers):
    """Calculate Monthly Recurring Revenue from subscriber list."""
    total = 0
    for sub in subscribers:
        if sub['status'] in ['active', 'trialing']:
            total += sub['amount_paid']
    # Convert cents to dollars
    return total / 100.0


def cancel_subscription(subscription_id):
    """Cancel a Stripe subscription. Returns (success, message)."""
    stripe = get_stripe_client()
    if not stripe.api_key:
        return False, "Stripe not configured."

    try:
        stripe.Subscription.delete(subscription_id)
        return True, f"Subscription {subscription_id} cancelled."
    except Exception as e:
        return False, f"Error: {str(e)}"


def refund_subscription(subscription_id, reason=""):
    """Issue a refund for a subscription's latest invoice."""
    stripe = get_stripe_client()
    if not stripe.api_key:
        return False, "Stripe not configured."

    try:
        # Get the subscription's invoices
        subs = stripe.Subscription.retrieve(subscription_id)
        invoices = stripe.Invoice.list(subscription=subscription_id, limit=1)

        if not invoices.data:
            return False, "No invoices found for this subscription."

        invoice = invoices.data[0]
        if not invoice.charge:
            return False, "Invoice has no charge to refund."

        # Create refund
        refund = stripe.Refund.create(
            charge=invoice.charge,
            reason='requested_by_customer' if reason == 'refund' else 'other',
        )
        return True, f"Refund created: {refund.id}"
    except Exception as e:
        return False, f"Error: {str(e)}"
