"""Analytics system to track feature usage, uploads, and errors.

Stores data in-memory (lost on server restart). For production,
consider migrating to a real database (SQLite, PostgreSQL).
"""
import time
from collections import defaultdict

# In-memory analytics store
_analytics = {
    'checks': defaultdict(int),  # feature_name -> count
    'uploads': defaultdict(int),  # format -> count (pdf, docx, etc)
    'errors': [],  # list of error events
    'pro_checks': defaultdict(int),  # pro feature -> count
    'start_time': time.time(),
}


def track_check(feature_name):
    """Track a free feature check."""
    _analytics['checks'][feature_name] += 1


def track_pro_check(feature_name):
    """Track a pro feature check."""
    _analytics['pro_checks'][feature_name] += 1


def track_upload(file_format):
    """Track a file upload by format (pdf, docx, txt, rtf, odt)."""
    ext = file_format.lower().strip('.')
    _analytics['uploads'][ext] += 1


def log_error(error_message, feature=None):
    """Log an error event."""
    _analytics['errors'].append({
        'timestamp': int(time.time()),
        'message': error_message,
        'feature': feature,
    })
    # Keep only last 1000 errors (prune old ones)
    if len(_analytics['errors']) > 1000:
        _analytics['errors'] = _analytics['errors'][-1000:]


def get_stats():
    """Get current analytics snapshot."""
    uptime_seconds = time.time() - _analytics['start_time']

    return {
        'uptime_seconds': int(uptime_seconds),
        'total_checks': sum(_analytics['checks'].values()),
        'checks_by_feature': dict(_analytics['checks']),
        'total_pro_checks': sum(_analytics['pro_checks'].values()),
        'pro_checks_by_feature': dict(_analytics['pro_checks']),
        'total_uploads': sum(_analytics['uploads'].values()),
        'uploads_by_format': dict(_analytics['uploads']),
        'error_count': len(_analytics['errors']),
        'recent_errors': _analytics['errors'][-20:],  # Last 20 errors
    }


def get_top_features(n=5):
    """Get top N most-used features."""
    checks = sorted(
        _analytics['checks'].items(),
        key=lambda x: x[1],
        reverse=True
    )
    return dict(checks[:n])


def get_error_summary():
    """Get summary of error patterns."""
    summary = defaultdict(int)
    for error in _analytics['errors']:
        feature = error.get('feature', 'unknown')
        summary[feature] += 1
    return dict(summary)


def reset_stats():
    """Reset all analytics (admin only)."""
    global _analytics
    _analytics = {
        'checks': defaultdict(int),
        'uploads': defaultdict(int),
        'errors': [],
        'pro_checks': defaultdict(int),
        'start_time': time.time(),
    }
