"""
Wrapper around Phase 2 Claude Routing System.
Imports the routing library and provides app-specific integration.

This module provides:
- Model selection based on task type
- Cost estimation
- API call logging to database
- Usage statistics and analytics
"""

from typing import Optional, Dict, Any
from models import ApiCall
from database import db
from config import Config
from datetime import datetime
import json


class RoutingService:
    """Service for Claude model routing and cost tracking"""

    @staticmethod
    def select_model(task_description: str, task_type: str = 'default') -> Dict[str, Any]:
        """
        Select optimal Claude model for task.

        This is a PLACEHOLDER that always returns Haiku.
        Will be replaced with Phase 2 routing system after deployment.

        Args:
            task_description: Natural language description of the task
            task_type: Type of task ('email_analysis', 'matching', 'default', etc.)

        Returns:
            {
                'model': 'claude-haiku-3-5',
                'estimated_tokens_out': 500,
                'estimated_cost': 0.0005,
                'use_batch': False
            }
        """
        # TODO: Import actual router from Phase 2
        # For now, always return Haiku with mocked token/cost estimates
        return {
            'model': 'claude-haiku-3-5',
            'estimated_tokens_out': 500,
            'estimated_cost': 0.0005,
            'use_batch': False
        }

    @staticmethod
    def log_api_call(
        user_id: str,
        endpoint: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost: float
    ) -> ApiCall:
        """
        Log API call to database for cost tracking.

        Args:
            user_id: User making the API call
            endpoint: API endpoint called (e.g., '/api/claude/analyze-email')
            model: Claude model used (e.g., 'claude-haiku-3-5')
            tokens_in: Input tokens
            tokens_out: Output tokens
            cost: Total cost in USD

        Returns:
            ApiCall model instance
        """
        api_call = ApiCall(
            user_id=user_id,
            endpoint=endpoint,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost
        )
        db.session.add(api_call)
        db.session.commit()
        return api_call

    @staticmethod
    def get_monthly_cost(user_id: str) -> float:
        """
        Get total cost for current month.

        Args:
            user_id: User ID

        Returns:
            Total cost in USD for current month
        """
        from sqlalchemy import func

        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total = db.session.query(
            func.sum(ApiCall.cost)
        ).filter(
            ApiCall.user_id == user_id,
            ApiCall.timestamp >= month_start
        ).scalar() or 0.0

        return float(total)

    @staticmethod
    def get_cost_by_model(user_id: str) -> Dict[str, float]:
        """
        Get cost breakdown by model for user.

        Args:
            user_id: User ID

        Returns:
            Dict mapping model name to total cost in USD
        """
        from sqlalchemy import func

        results = db.session.query(
            ApiCall.model,
            func.sum(ApiCall.cost).label('total_cost')
        ).filter(
            ApiCall.user_id == user_id
        ).group_by(
            ApiCall.model
        ).all()

        return {model: float(cost) for model, cost in results}
