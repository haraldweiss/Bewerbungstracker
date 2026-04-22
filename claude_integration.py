"""
Claude API Integration Blueprint
Provides endpoints for email analysis, application matching, and usage tracking.
"""

from flask import Blueprint, request, jsonify
from api.auth import token_required
from models import Email, Application, ApiCall
from routing_service import RoutingService
from database import db
import json

claude_bp = Blueprint('claude', __name__, url_prefix='/api/claude')


@claude_bp.route('/analyze-email', methods=['POST'])
@token_required
def analyze_email(user):
    """
    Analyze email using Claude AI.

    Request:
        {
            "email_id": "email-uuid"
        }

    Returns:
        {
            "email_id": "email-uuid",
            "analysis": {
                "company": "Company Name",
                "position": "Job Title",
                "deadline": "2026-05-22",
                "sentiment": "positive|neutral|negative",
                "confidence": 0.85
            },
            "model_used": "claude-haiku-3-5",
            "cost": 0.0005
        }
    """
    data = request.get_json()

    if not data or not data.get('email_id'):
        return {'error': 'email_id required'}, 400

    email = Email.query.filter_by(id=data['email_id'], user_id=user.id).first()

    if not email:
        return {'error': 'Email not found'}, 404

    # Get model recommendation from routing service
    model_selection = RoutingService.select_model(
        task_description=f"Analyze email: {email.subject}",
        task_type='email_analysis'
    )

    # TODO: Call Claude API with model_selection['model']
    # For now, return mock analysis
    analysis = {
        'company': 'Example Corp',
        'position': 'Senior Engineer',
        'deadline': '2026-05-22',
        'sentiment': 'positive',
        'confidence': 0.85
    }

    # Log API call
    RoutingService.log_api_call(
        user_id=user.id,
        endpoint='/api/claude/analyze-email',
        model=model_selection['model'],
        tokens_in=150,  # Placeholder
        tokens_out=model_selection['estimated_tokens_out'],
        cost=model_selection['estimated_cost']
    )

    return {
        'email_id': email.id,
        'analysis': analysis,
        'model_used': model_selection['model'],
        'cost': model_selection['estimated_cost']
    }, 200


@claude_bp.route('/match-application', methods=['POST'])
@token_required
def match_application(user):
    """
    Smart match email to application using Claude AI.

    Request:
        {
            "email_id": "email-uuid"
        }

    Returns:
        {
            "email_id": "email-uuid",
            "matched_application_id": "app-uuid" or null,
            "confidence": 0.92,
            "model_used": "claude-haiku-3-5",
            "cost": 0.0005
        }
    """
    data = request.get_json()

    if not data or not data.get('email_id'):
        return {'error': 'email_id required'}, 400

    email = Email.query.filter_by(id=data['email_id'], user_id=user.id).first()

    if not email:
        return {'error': 'Email not found'}, 404

    # Get model selection from routing service
    model_selection = RoutingService.select_model(
        task_description=f"Match email to application",
        task_type='matching'
    )

    # TODO: Call Claude API to find best matching application
    # For now, return mock match
    matched_app_id = None
    confidence = 0.0

    # Log API call
    RoutingService.log_api_call(
        user_id=user.id,
        endpoint='/api/claude/match-application',
        model=model_selection['model'],
        tokens_in=200,
        tokens_out=model_selection['estimated_tokens_out'],
        cost=model_selection['estimated_cost']
    )

    return {
        'email_id': email.id,
        'matched_application_id': matched_app_id,
        'confidence': confidence,
        'model_used': model_selection['model'],
        'cost': model_selection['estimated_cost']
    }, 200


@claude_bp.route('/usage/monthly', methods=['GET'])
@token_required
def get_monthly_usage(user):
    """
    Get monthly usage stats and cost breakdown.

    Returns:
        {
            "total_cost_usd": 0.0145,
            "api_calls": 25,
            "cost_by_model": {
                "claude-haiku-3-5": 0.0145
            }
        }
    """
    monthly_cost = RoutingService.get_monthly_cost(user.id)
    cost_by_model = RoutingService.get_cost_by_model(user.id)

    api_calls = ApiCall.query.filter_by(user_id=user.id).count()

    return {
        'total_cost_usd': round(monthly_cost, 4),
        'api_calls': api_calls,
        'cost_by_model': {k: round(v, 4) for k, v in cost_by_model.items()}
    }, 200
