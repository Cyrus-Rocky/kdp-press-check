"""KDP Press Check Pro: subscription gating via Stripe.

Stripe is the only source of truth for who has an active subscription. This
app stores no payment data and no password of its own: a signed Flask
session cookie (already keyed to SECRET_KEY) marks a browser as "Pro" after
we verify their email against Stripe's API, and that's it.

To switch Pro on, set three things (Stripe Dashboard > Developers > API
keys, and Product catalog for the price):
  STRIPE_SECRET_KEY   - your Stripe secret key (sk_live_... or sk_test_...)
  STRIPE_PRICE_ID     - the recurring Price ID for the Pro plan
  PRO_PRICE_DISPLAY   - optional, defaults to "$19/mo"

Until STRIPE_SECRET_KEY and STRIPE_PRICE_ID are both set, every Pro route
shows a "launching soon" state instead of a broken checkout.
"""
import os
import time

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "").strip()
PRO_PRICE_DISPLAY = os.environ.get("PRO_PRICE_DISPLAY", "$19/mo")

# How long a verified Pro session is trusted before we re-check Stripe. Short
# enough that a cancellation takes effect same-day, long enough that normal
# browsing doesn't hit the Stripe API on every request.
REVERIFY_SECONDS = 6 * 60 * 60


def enabled() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID)


def _stripe():
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def create_checkout_url(success_url: str, cancel_url: str) -> str:
    stripe = _stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        allow_promotion_codes=True,
    )
    return session.url


def create_billing_portal_url(customer_id: str, return_url: str) -> str:
    stripe = _stripe()
    portal = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
    return portal.url


def email_from_checkout_session(session_id: str):
    """Returns (email, customer_id) if the Checkout session completed, else (None, None)."""
    stripe = _stripe()
    session = stripe.checkout.Session.retrieve(session_id)
    if session.status != "complete":
        return None, None
    email = None
    if session.customer_details:
        email = session.customer_details.email
    return email, session.customer


def active_subscription(email: str):
    """Looks up Stripe directly by email. Returns the Stripe customer id if
    they have an active (or trialing) subscription, else None."""
    stripe = _stripe()
    customers = stripe.Customer.list(email=email, limit=1)
    if not customers.data:
        return None
    customer = customers.data[0]
    subs = stripe.Subscription.list(customer=customer.id, status="active", limit=1)
    if subs.data:
        return customer.id
    subs = stripe.Subscription.list(customer=customer.id, status="trialing", limit=1)
    return customer.id if subs.data else None


def mark_session_pro(session, email: str, customer_id: str):
    session["pro_email"] = email
    session["pro_customer_id"] = customer_id
    session["pro_verified_at"] = int(time.time())
    session.permanent = True


def clear_session_pro(session):
    for k in ("pro_email", "pro_customer_id", "pro_verified_at"):
        session.pop(k, None)


def is_pro(session) -> bool:
    """True if this browser session currently belongs to an active
    subscriber, re-checking Stripe if the cached verification is stale."""
    if not enabled():
        return False
    email = session.get("pro_email")
    if not email:
        return False
    verified_at = session.get("pro_verified_at", 0)
    if time.time() - verified_at < REVERIFY_SECONDS:
        return True
    # Cache expired: re-verify against Stripe before trusting it further.
    customer_id = active_subscription(email)
    if customer_id:
        mark_session_pro(session, email, customer_id)
        return True
    clear_session_pro(session)
    return False
