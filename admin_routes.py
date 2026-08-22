"""
Admin Dashboard Routes
Temporary authentication with environment variable
"""
import os
from datetime import datetime
from functools import wraps
import requests
import json

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from models import db, Seller, SystemMetric, AuthorFeedback, AdminAuditLog

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Temporary admin password (change in .env or settings)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "temporary-admin-password")

# ProTalent Hub API placeholder
PROTALENT_HUB_API_URL = os.environ.get(
    "PROTALENT_HUB_API_URL",
    "https://api.protalenthub.com/v1/sellers"
)


def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_token' not in session:
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')

        if password == ADMIN_PASSWORD:
            session['admin_token'] = 'authenticated'
            session.permanent = True
            return redirect(url_for('admin.dashboard'))
        else:
            return render_template('admin/login.html', error='Invalid password'), 401

    return render_template('admin/login.html')


@admin_bp.route('/logout', methods=['POST'])
def logout():
    """Admin logout"""
    session.pop('admin_token', None)
    return redirect(url_for('admin.login'))


# ============================================================================
# DASHBOARD ROUTES
# ============================================================================

@admin_bp.route('/dashboard')
@require_admin
def dashboard():
    """Admin dashboard homepage"""
    total_sellers = Seller.query.count()
    verified_sellers = Seller.query.filter_by(verified_at != None).count()

    feedback_this_week = AuthorFeedback.query.filter(
        AuthorFeedback.created_at >= datetime.utcnow().replace(day=datetime.utcnow().day - 7)
    ).count()

    recent_sellers = Seller.query.order_by(Seller.created_at.desc()).limit(5).all()
    recent_feedback = AuthorFeedback.query.order_by(AuthorFeedback.created_at.desc()).limit(5).all()

    stats = {
        'total_sellers': total_sellers,
        'verified_sellers': verified_sellers,
        'feedback_this_week': feedback_this_week,
        'system_uptime': '99.8%'  # Placeholder
    }

    return render_template('admin/dashboard.html',
                         stats=stats,
                         recent_sellers=recent_sellers,
                         recent_feedback=recent_feedback)


# ============================================================================
# SELLER MANAGEMENT ROUTES
# ============================================================================

@admin_bp.route('/sellers')
@require_admin
def sellers_page():
    """Seller management page"""
    sellers = Seller.query.all()
    return render_template('admin/sellers.html', sellers=sellers)


@admin_bp.route('/api/sellers', methods=['GET'])
@require_admin
def get_sellers():
    """Get all sellers (JSON API)"""
    sellers = Seller.query.all()
    return jsonify([seller.to_dict() for seller in sellers])


@admin_bp.route('/api/sellers', methods=['POST'])
@require_admin
def create_seller():
    """Create a new seller"""
    data = request.get_json()

    # Validate
    if not data.get('name') or not data.get('profile_link'):
        return jsonify({'error': 'name and profile_link required'}), 400

    # Check if seller already exists
    if Seller.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Seller already exists'}), 409

    # Create seller
    seller = Seller(
        name=data['name'],
        profile_link=data['profile_link'],
        source=data.get('source', 'manual'),
        verified_at=datetime.utcnow() if data.get('source') == 'protalent_hub' else None
    )

    db.session.add(seller)
    db.session.commit()

    # Audit log
    log_admin_action('add_seller', f'seller_{seller.id}', None, seller.to_dict())

    return jsonify(seller.to_dict()), 201


@admin_bp.route('/api/sellers/<int:seller_id>', methods=['PUT'])
@require_admin
def update_seller(seller_id):
    """Update a seller"""
    seller = Seller.query.get_or_404(seller_id)
    data = request.get_json()

    old_data = seller.to_dict()

    if 'name' in data:
        seller.name = data['name']
    if 'profile_link' in data:
        seller.profile_link = data['profile_link']
    if 'is_active' in data:
        seller.is_active = data['is_active']

    seller.updated_at = datetime.utcnow()
    db.session.commit()

    # Audit log
    log_admin_action('edit_seller', f'seller_{seller_id}', old_data, seller.to_dict())

    return jsonify(seller.to_dict())


@admin_bp.route('/api/sellers/<int:seller_id>', methods=['DELETE'])
@require_admin
def delete_seller(seller_id):
    """Delete a seller"""
    seller = Seller.query.get_or_404(seller_id)

    old_data = seller.to_dict()
    db.session.delete(seller)
    db.session.commit()

    # Audit log
    log_admin_action('delete_seller', f'seller_{seller_id}', old_data, None)

    return jsonify({'success': True}), 204


@admin_bp.route('/api/sellers/<int:seller_id>/verify', methods=['POST'])
@require_admin
def verify_seller(seller_id):
    """Verify seller against ProTalent Hub"""
    seller = Seller.query.get_or_404(seller_id)

    # Call ProTalent Hub API to verify
    verified = verify_seller_with_protalent(seller.name)

    if verified:
        seller.verified_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'verified': True, 'message': 'Seller verified'})
    else:
        return jsonify({'verified': False, 'message': 'Seller not found on ProTalent Hub'}), 404


# ============================================================================
# PROTALENT HUB SYNC ROUTES
# ============================================================================

@admin_bp.route('/api/sellers/sync-protalent', methods=['POST'])
@require_admin
def sync_protalent_sellers():
    """Fetch sellers from ProTalent Hub and sync database"""
    try:
        # Fetch sellers from ProTalent Hub (placeholder for now)
        protalent_sellers = fetch_protalent_sellers()

        if not protalent_sellers:
            return jsonify({
                'error': 'Failed to fetch ProTalent Hub sellers',
                'synced': 0,
                'added': 0
            }), 500

        synced = 0
        added = 0
        errors = []

        for seller_data in protalent_sellers:
            name = seller_data.get('name')
            profile_url = seller_data.get('profile_url')

            if not name or not profile_url:
                errors.append(f'Invalid seller data: {seller_data}')
                continue

            # Check if seller exists
            existing = Seller.query.filter_by(name=name).first()

            if existing:
                # Update if needed
                if existing.profile_link != profile_url:
                    old_data = existing.to_dict()
                    existing.profile_link = profile_url
                    existing.updated_at = datetime.utcnow()
                    existing.verified_at = datetime.utcnow()
                    db.session.commit()
                    log_admin_action('sync_seller', f'seller_{existing.id}', old_data, existing.to_dict())
                    synced += 1
            else:
                # Add new seller
                new_seller = Seller(
                    name=name,
                    profile_link=profile_url,
                    source='protalent_hub',
                    verified_at=datetime.utcnow()
                )
                db.session.add(new_seller)
                db.session.commit()
                log_admin_action('add_seller_protalent', f'seller_{new_seller.id}', None, new_seller.to_dict())
                added += 1

        return jsonify({
            'synced': synced,
            'added': added,
            'total': synced + added,
            'errors': errors
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SYSTEM METRICS ROUTES
# ============================================================================

@admin_bp.route('/api/metrics', methods=['GET'])
@require_admin
def get_metrics():
    """Get system metrics"""
    metrics = {}

    metric_names = [
        'spine_width_avg_time_ms',
        'dpi_calc_avg_time_ms',
        'metadata_validator_avg_time_ms',
        'spine_width_accuracy',
        'dpi_calc_accuracy',
        'metadata_validator_accuracy'
    ]

    for metric_name in metric_names:
        latest = SystemMetric.query.filter_by(metric_name=metric_name).order_by(
            SystemMetric.recorded_at.desc()
        ).first()

        if latest:
            metrics[metric_name] = latest.value
        else:
            metrics[metric_name] = 0  # Default if no data

    return jsonify(metrics)


@admin_bp.route('/api/metrics', methods=['POST'])
def record_metric():
    """Record a system metric (called by calculator endpoints)"""
    data = request.get_json()

    metric = SystemMetric(
        metric_name=data.get('metric_name'),
        value=data.get('value')
    )

    db.session.add(metric)
    db.session.commit()

    return jsonify({'success': True}), 201


@admin_bp.route('/health')
@require_admin
def health_page():
    """System health dashboard"""
    metrics = get_metrics().get_json()
    return render_template('admin/health.html', metrics=metrics)


# ============================================================================
# AUTHOR FEEDBACK ROUTES
# ============================================================================

@admin_bp.route('/api/feedback', methods=['GET'])
@require_admin
def get_feedback():
    """Get all author feedback"""
    feedback = AuthorFeedback.query.order_by(AuthorFeedback.created_at.desc()).all()
    return jsonify([f.to_dict() for f in feedback])


@admin_bp.route('/api/feedback/<int:feedback_id>', methods=['PUT'])
@require_admin
def update_feedback(feedback_id):
    """Update feedback status"""
    feedback = AuthorFeedback.query.get_or_404(feedback_id)
    data = request.get_json()

    if 'status' in data:
        feedback.status = data['status']
        db.session.commit()

    return jsonify(feedback.to_dict())


@admin_bp.route('/api/feedback/<int:feedback_id>', methods=['DELETE'])
@require_admin
def delete_feedback(feedback_id):
    """Delete feedback"""
    feedback = AuthorFeedback.query.get_or_404(feedback_id)
    db.session.delete(feedback)
    db.session.commit()
    return jsonify({'success': True}), 204


@admin_bp.route('/feedback')
@require_admin
def feedback_page():
    """Feedback management page"""
    feedback = AuthorFeedback.query.order_by(AuthorFeedback.created_at.desc()).all()
    return render_template('admin/feedback.html', feedback=feedback)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def fetch_protalent_sellers():
    """
    Fetch sellers from ProTalent Hub API

    Placeholder implementation - will be replaced with real API call
    """
    try:
        # TODO: Replace with real ProTalent Hub API credentials
        headers = {
            'Authorization': f'Bearer {os.environ.get("PROTALENT_HUB_API_KEY", "")}',
            'Content-Type': 'application/json'
        }

        response = requests.get(PROTALENT_HUB_API_URL, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f'ProTalent Hub API error: {response.status_code}')
            return None

    except Exception as e:
        print(f'ProTalent Hub API error: {str(e)}')
        return None


def verify_seller_with_protalent(seller_name):
    """
    Verify seller name exists on ProTalent Hub

    Placeholder implementation - will be replaced with real API call
    """
    sellers = fetch_protalent_sellers()

    if not sellers:
        return False

    # Search for seller by name
    for seller in sellers:
        if seller.get('name').lower() == seller_name.lower():
            return True

    return False


def log_admin_action(action, resource, old_value, new_value, admin_user='system'):
    """Log admin action for audit trail"""
    log = AdminAuditLog(
        action=action,
        resource=resource,
        old_value=json.dumps(old_value) if old_value else None,
        new_value=json.dumps(new_value) if new_value else None,
        admin_user=admin_user
    )
    db.session.add(log)
    db.session.commit()
