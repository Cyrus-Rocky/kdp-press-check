from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Seller(db.Model):
    __tablename__ = 'sellers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    profile_link = db.Column(db.String(500), nullable=False)
    source = db.Column(db.String(50), nullable=False)  # "manual", "protalent_hub", "auto"
    verified_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'profile_link': self.profile_link,
            'source': self.source,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active
        }


class SystemMetric(db.Model):
    __tablename__ = 'system_metrics'

    id = db.Column(db.Integer, primary_key=True)
    metric_name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'metric_name': self.metric_name,
            'value': self.value,
            'recorded_at': self.recorded_at.isoformat()
        }


class AuthorFeedback(db.Model):
    __tablename__ = 'author_feedback'

    id = db.Column(db.Integer, primary_key=True)
    tool_name = db.Column(db.String(100), nullable=False)  # "spine_width", "dpi_calc", "metadata_validator"
    feedback_type = db.Column(db.String(50), nullable=False)  # "bug", "feature_request", "unclear", "accurate"
    message = db.Column(db.Text)
    author_email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="open")  # "open", "reviewed", "addressed"

    def to_dict(self):
        return {
            'id': self.id,
            'tool_name': self.tool_name,
            'feedback_type': self.feedback_type,
            'message': self.message,
            'author_email': self.author_email,
            'created_at': self.created_at.isoformat(),
            'status': self.status
        }


class AdminAuditLog(db.Model):
    __tablename__ = 'admin_audit_log'

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)  # "add_seller", "edit_seller", "delete_seller"
    resource = db.Column(db.String(255))  # "seller_123", "settings_dpi"
    old_value = db.Column(db.Text)  # JSON
    new_value = db.Column(db.Text)  # JSON
    admin_user = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'action': self.action,
            'resource': self.resource,
            'old_value': json.loads(self.old_value) if self.old_value else None,
            'new_value': json.loads(self.new_value) if self.new_value else None,
            'admin_user': self.admin_user,
            'created_at': self.created_at.isoformat()
        }
