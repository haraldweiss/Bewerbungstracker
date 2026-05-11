# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
"""REST-Endpoints für den Cover-Letter-Generator.

Endpoints (alle unter /api/cover-letters):
  POST  /create                 — Draft anlegen (job_title, company, description)
  POST  /<id>/generate          — Analyse + Text-Generierung (braucht cv_text)
  GET   /<id>                   — Details + Content + Analysis
  GET   /                       — Liste aller eigenen Cover Letters
  PATCH /<id>                   — Content/Status/Config aktualisieren
  POST  /<id>/export            — PDF oder DOCX-Download
  DELETE /<id>                  — Hard-Delete
"""
from __future__ import annotations
import io
import json
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file
from api.auth import token_required
from database import db
from models import CoverLetter
from services.cover_letter_service import CoverLetterService
from services.export_service import ExportService

logger = logging.getLogger(__name__)

cover_letters_bp = Blueprint('cover_letters', __name__, url_prefix='/api/cover-letters')

# Allowed values für Config-Felder (Validation)
ALLOWED_TONE = {'professional', 'casual', 'technical'}
ALLOWED_LENGTH = {'short', 'medium', 'long'}
ALLOWED_FOCUS = {'technical', 'leadership', 'projects', 'balanced'}
ALLOWED_STATUS = {'draft', 'generated', 'finalized', 'sent'}


def _serialize(cl: CoverLetter, *, include_content: bool = True) -> dict:
    """Serialisiert CoverLetter zu JSON-kompatiblem dict."""
    result = {
        'id': cl.id,
        'application_id': cl.application_id,
        'job_title': cl.job_title,
        'company_name': cl.company_name,
        'cv_used': cl.cv_used,
        'tone': cl.tone,
        'length': cl.length,
        'focus': cl.focus,
        'status': cl.status,
        'exported_at': cl.exported_at.isoformat() if cl.exported_at else None,
        'created_at': cl.created_at.isoformat() if cl.created_at else None,
        'updated_at': cl.updated_at.isoformat() if cl.updated_at else None,
    }
    if include_content:
        result['content'] = cl.content
        result['analysis'] = json.loads(cl.analysis_json) if cl.analysis_json else None
        result['job_description'] = cl.job_description
    return result


@cover_letters_bp.post('/create')
@token_required
def create_cover_letter(user):
    """Legt einen Draft-Cover-Letter an. Content wird später via /generate erzeugt."""
    data = request.get_json() or {}

    for field in ('job_title', 'company_name', 'job_description'):
        if not data.get(field, '').strip():
            return jsonify({'error': f'{field} ist erforderlich'}), 400

    tone = data.get('tone', 'professional')
    length = data.get('length', 'medium')
    focus = data.get('focus', 'balanced')
    if tone not in ALLOWED_TONE:
        return jsonify({'error': f'tone muss in {sorted(ALLOWED_TONE)} sein'}), 400
    if length not in ALLOWED_LENGTH:
        return jsonify({'error': f'length muss in {sorted(ALLOWED_LENGTH)} sein'}), 400
    if focus not in ALLOWED_FOCUS:
        return jsonify({'error': f'focus muss in {sorted(ALLOWED_FOCUS)} sein'}), 400

    cl = CoverLetter(
        user_id=user.id,
        application_id=data.get('application_id'),
        job_title=data['job_title'].strip(),
        company_name=data['company_name'].strip(),
        job_description=data['job_description'].strip(),
        cv_used=data.get('cv_used'),
        tone=tone, length=length, focus=focus,
        status='draft',
    )
    db.session.add(cl)
    db.session.commit()
    return jsonify(_serialize(cl, include_content=False)), 201


@cover_letters_bp.post('/<cover_letter_id>/generate')
@token_required
def generate_cover_letter(user, cover_letter_id):
    """Führt Analyse + Generierung aus. Erwartet {"cv_text": "..."} im Body."""
    cl = CoverLetter.query.filter_by(id=cover_letter_id, user_id=user.id).first()
    if not cl:
        return jsonify({'error': 'Cover Letter nicht gefunden'}), 404

    data = request.get_json() or {}
    cv_text = (data.get('cv_text') or '').strip()
    if not cv_text:
        return jsonify({'error': 'cv_text ist erforderlich'}), 400

    if len(cl.job_description) < 50:
        return jsonify({
            'error': 'Stellenbeschreibung zu kurz — bitte mit mehr Details ergänzen'
        }), 400

    applicant_name = data.get('applicant_name')

    try:
        svc = CoverLetterService()
        analysis = svc.analyze(cv_text, cl.job_description, user_id=user.id)
        content = svc.generate(
            company_name=cl.company_name, job_title=cl.job_title,
            analysis=analysis, tone=cl.tone, length=cl.length, focus=cl.focus,
            user_id=user.id, applicant_name=applicant_name,
        )
    except RuntimeError as e:
        logger.warning('cover-letter generate failed for user=%s: %s', user.id, e)
        return jsonify({'error': str(e)}), 503
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception('cover-letter generate error for user=%s', user.id)
        return jsonify({'error': f'Generierung fehlgeschlagen: {type(e).__name__}'}), 500

    cl.analysis_json = json.dumps(analysis, ensure_ascii=False)
    cl.content = content
    cl.status = 'generated'
    cl.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify(_serialize(cl)), 200


@cover_letters_bp.get('/<cover_letter_id>')
@token_required
def get_cover_letter(user, cover_letter_id):
    cl = CoverLetter.query.filter_by(id=cover_letter_id, user_id=user.id).first()
    if not cl:
        return jsonify({'error': 'Cover Letter nicht gefunden'}), 404
    return jsonify(_serialize(cl)), 200


@cover_letters_bp.get('/')
@cover_letters_bp.get('')
@token_required
def list_cover_letters(user):
    """Liste der eigenen Cover Letters (sortiert nach updated_at desc)."""
    cls = CoverLetter.query.filter_by(user_id=user.id).order_by(
        CoverLetter.updated_at.desc()
    ).all()
    return jsonify({
        'cover_letters': [_serialize(cl, include_content=False) for cl in cls]
    }), 200


@cover_letters_bp.patch('/<cover_letter_id>')
@token_required
def update_cover_letter(user, cover_letter_id):
    """Aktualisiert content, status oder config-Felder."""
    cl = CoverLetter.query.filter_by(id=cover_letter_id, user_id=user.id).first()
    if not cl:
        return jsonify({'error': 'Cover Letter nicht gefunden'}), 404

    data = request.get_json() or {}

    if 'content' in data:
        cl.content = data['content']
    if 'status' in data:
        if data['status'] not in ALLOWED_STATUS:
            return jsonify({'error': f'status muss in {sorted(ALLOWED_STATUS)} sein'}), 400
        cl.status = data['status']
    if 'tone' in data:
        if data['tone'] not in ALLOWED_TONE:
            return jsonify({'error': f'tone muss in {sorted(ALLOWED_TONE)} sein'}), 400
        cl.tone = data['tone']
    if 'length' in data:
        if data['length'] not in ALLOWED_LENGTH:
            return jsonify({'error': f'length muss in {sorted(ALLOWED_LENGTH)} sein'}), 400
        cl.length = data['length']
    if 'focus' in data:
        if data['focus'] not in ALLOWED_FOCUS:
            return jsonify({'error': f'focus muss in {sorted(ALLOWED_FOCUS)} sein'}), 400
        cl.focus = data['focus']
    if 'application_id' in data:
        cl.application_id = data['application_id']

    cl.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(_serialize(cl)), 200


@cover_letters_bp.post('/<cover_letter_id>/export')
@token_required
def export_cover_letter(user, cover_letter_id):
    """Exportiert als PDF oder DOCX. Body: {"format": "pdf"|"docx"}."""
    cl = CoverLetter.query.filter_by(id=cover_letter_id, user_id=user.id).first()
    if not cl:
        return jsonify({'error': 'Cover Letter nicht gefunden'}), 404
    if not cl.content:
        return jsonify({'error': 'Kein Inhalt zum Exportieren — bitte zuerst generieren'}), 400

    data = request.get_json() or {}
    fmt = (data.get('format') or 'pdf').lower()
    if fmt not in ('pdf', 'docx'):
        return jsonify({'error': 'format muss "pdf" oder "docx" sein'}), 400

    applicant_name = data.get('applicant_name') or user.email.split('@')[0]
    applicant_address = data.get('applicant_address')

    try:
        exporter = ExportService()
        if fmt == 'pdf':
            blob = exporter.to_pdf(
                cl.content, applicant_name=applicant_name,
                company_name=cl.company_name, job_title=cl.job_title,
                applicant_address=applicant_address,
            )
            mimetype = 'application/pdf'
        else:
            blob = exporter.to_docx(
                cl.content, applicant_name=applicant_name,
                company_name=cl.company_name, job_title=cl.job_title,
                applicant_address=applicant_address,
            )
            mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    except ImportError as e:
        return jsonify({'error': f'Export-Library fehlt: {e}'}), 503
    except Exception as e:
        logger.exception('export %s failed for cl=%s', fmt, cl.id)
        return jsonify({'error': f'Export fehlgeschlagen: {type(e).__name__}'}), 500

    cl.exported_at = datetime.utcnow()
    db.session.commit()

    safe_company = ''.join(c if c.isalnum() else '_' for c in cl.company_name)[:40]
    safe_title = ''.join(c if c.isalnum() else '_' for c in cl.job_title)[:40]
    filename = f'Anschreiben_{safe_company}_{safe_title}.{fmt}'

    return send_file(io.BytesIO(blob), mimetype=mimetype,
                     as_attachment=True, download_name=filename)


@cover_letters_bp.delete('/<cover_letter_id>')
@token_required
def delete_cover_letter(user, cover_letter_id):
    cl = CoverLetter.query.filter_by(id=cover_letter_id, user_id=user.id).first()
    if not cl:
        return jsonify({'error': 'Cover Letter nicht gefunden'}), 404
    db.session.delete(cl)
    db.session.commit()
    return jsonify({'status': 'deleted', 'id': cover_letter_id}), 200
