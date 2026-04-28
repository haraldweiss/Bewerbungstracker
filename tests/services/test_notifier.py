"""Tests für Job-Notification-Service."""
from unittest.mock import patch
from services.job_matching.notifier import send_match_notification


@patch("services.job_matching.notifier._send_push")
def test_send_match_notification_calls_push(mock_push):
    send_match_notification(user_id="u1",
                            title="React Senior Job",
                            company="ACME",
                            score=92,
                            url="https://example.com/job/1")
    assert mock_push.called
    args = mock_push.call_args
    assert "React" in args[1]["body"]
    assert "92" in args[1]["body"]
