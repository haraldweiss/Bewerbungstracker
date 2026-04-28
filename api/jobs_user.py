"""User-facing Job-Discovery Endpoints (JWT-geschützt)."""
from flask import Blueprint, request, jsonify

from database import db
from models import JobSource
from api.auth import token_required
from services.ssrf_guard import is_url_safe_for_rss


jobs_user_bp = Blueprint('jobs_user', __name__, url_prefix='/api/jobs')


_VALID_TYPES = {"rss", "adzuna", "bundesagentur", "arbeitnow"}


def _validate_config(source_type: str, config: dict) -> str | None:
    """Returns Fehlermeldung oder None bei OK."""
    if source_type == "rss":
        url = (config or {}).get("url")
        if not url or not isinstance(url, str):
            return "RSS-Config benötigt 'url' (string)"
        if not is_url_safe_for_rss(url):
            return f"URL nicht erlaubt (private/lokale IP): {url}"
    elif source_type == "adzuna":
        for k in ("app_id", "app_key", "country"):
            if not (config or {}).get(k):
                return f"Adzuna-Config benötigt '{k}'"
    elif source_type == "bundesagentur":
        if not (config or {}).get("was") and not (config or {}).get("wo"):
            return "Bundesagentur-Config benötigt mindestens 'was' oder 'wo'"
    elif source_type == "arbeitnow":
        pass
    return None


def _serialize_source(s: JobSource, current_user_id: str) -> dict:
    return {
        "id": s.id, "name": s.name, "type": s.type, "config": s.config,
        "enabled": s.enabled, "crawl_interval_min": s.crawl_interval_min,
        "last_crawled_at": s.last_crawled_at.isoformat() if s.last_crawled_at else None,
        "last_error": s.last_error, "consecutive_failures": s.consecutive_failures,
        "is_global": s.user_id is None,
        "is_own": s.user_id == current_user_id,
    }


@jobs_user_bp.get('/sources')
@token_required
def list_sources(user):
    sources = JobSource.query.filter(
        (JobSource.user_id.is_(None)) | (JobSource.user_id == user.id)
    ).order_by(JobSource.name).all()
    return jsonify({"sources": [_serialize_source(s, user.id) for s in sources]}), 200


@jobs_user_bp.post('/sources')
@token_required
def create_source(user):
    data = request.get_json() or {}
    if data.get("type") not in _VALID_TYPES:
        return jsonify({"error": f"type muss eines von {_VALID_TYPES} sein"}), 400
    if not data.get("name"):
        return jsonify({"error": "name fehlt"}), 400

    err = _validate_config(data["type"], data.get("config") or {})
    if err:
        return jsonify({"error": err}), 400

    src = JobSource(
        user_id=user.id,
        name=data["name"],
        type=data["type"],
        enabled=data.get("enabled", True),
        crawl_interval_min=data.get("crawl_interval_min", 60),
    )
    src.config = data.get("config") or {}
    db.session.add(src)
    db.session.commit()
    return jsonify({"source": _serialize_source(src, user.id)}), 201


@jobs_user_bp.patch('/sources/<int:source_id>')
@token_required
def update_source(user, source_id: int):
    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    if "name" in data:
        src.name = data["name"]
    if "enabled" in data:
        src.enabled = bool(data["enabled"])
    if "crawl_interval_min" in data:
        src.crawl_interval_min = int(data["crawl_interval_min"])
    if "config" in data:
        err = _validate_config(src.type, data["config"])
        if err:
            return jsonify({"error": err}), 400
        src.config = data["config"]
    db.session.commit()
    return jsonify({"source": _serialize_source(src, user.id)}), 200


@jobs_user_bp.delete('/sources/<int:source_id>')
@token_required
def delete_source(user, source_id: int):
    src = JobSource.query.get_or_404(source_id)
    if src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(src)
    db.session.commit()
    return ('', 204)


@jobs_user_bp.post('/sources/<int:source_id>/test-crawl')
@token_required
def test_crawl_source(user, source_id: int):
    """Manueller Test-Crawl für eine Quelle."""
    from services.job_sources import get_adapter
    src = JobSource.query.get_or_404(source_id)
    if src.user_id is not None and src.user_id != user.id:
        return jsonify({"error": "Forbidden"}), 403

    try:
        adapter = get_adapter(src.type, src.config)
        jobs = adapter.fetch()
        return jsonify({"ok": True, "found_jobs": len(jobs),
                        "sample_titles": [j.title for j in jobs[:5]]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 200
