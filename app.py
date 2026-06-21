import os
import json
import io
from flask import Flask, request, jsonify, render_template, session, send_file
from werkzeug.utils import secure_filename
from utils.parser import extract_text
from utils.analyzer import analyze_resume
from utils.chatbot import chat_with_resume
from utils import database
from utils import pdf_export

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "resumeiq-dev-secret-key-2026-fixed")
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt'}
os.makedirs('uploads', exist_ok=True)

# Initialize SQLite tables on startup (safe to call every time, no-op if they exist)
database.init_db()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_and_extract(file_storage):
    filename = secure_filename(file_storage.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_storage.save(filepath)
    try:
        return extract_text(filepath)
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ── PAGES ──

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/landing')
def landing():
    return render_template('landing.html')


@app.route('/chat')
def chat_page():
    return render_template('chat.html')


# ── ANALYZE FLOW (report first) ──

@app.route('/analyze', methods=['POST'])
def analyze():
    resume_text = ''

    if 'resume' in request.files and request.files['resume'].filename != '':
        file = request.files['resume']
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Upload PDF, DOCX, DOC, or TXT'}), 400
        try:
            resume_text = _save_and_extract(file)
        except Exception as e:
            return jsonify({'error': f'Could not read file: {str(e)}'}), 400

    elif request.form.get('resume_text', '').strip():
        resume_text = request.form.get('resume_text', '').strip()
    else:
        return jsonify({'error': 'No file uploaded or text pasted'}), 400

    job_description = request.form.get('job_description', '').strip()

    if not resume_text or len(resume_text.strip()) < 50:
        return jsonify({'error': 'Could not extract enough text. Make sure the file is not a scanned image.'}), 400

    try:
        result = analyze_resume(resume_text, job_description)
    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

    # Store lightweight context for the follow-up chat.
    # The FULL report is too large for a session cookie (4KB browser limit),
    # so we only keep the resume text + a pointer (history_id) to the
    # full report already persisted in SQLite by analyze_resume().
    session['resume_text'] = resume_text[:6000]
    session['job_description'] = job_description[:3000]
    session['history_id'] = result.get('history_id')
    session['chat_history'] = []

    return jsonify(result)


# ── CHAT FLOW (report fetched from SQLite via history_id, not the cookie) ──

@app.route('/chat/start', methods=['POST'])
def chat_start():
    """Used when user clicks 'Chat about this' after seeing the report."""
    if not session.get('resume_text'):
        return jsonify({'error': 'No resume in session. Please analyze a resume first.'}), 400

    has_report = False
    history_id = session.get('history_id')
    if history_id:
        record = database.get_analysis_by_id(history_id)
        has_report = record is not None

    return jsonify({
        'success': True,
        'preview': session['resume_text'][:200],
        'has_report': has_report
    })


@app.route('/chat/upload', methods=['POST'])
def chat_upload():
    """Used when user goes directly to /chat without analyzing first."""
    resume_text = ''

    if 'resume' in request.files and request.files['resume'].filename != '':
        file = request.files['resume']
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        try:
            resume_text = _save_and_extract(file)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    elif request.form.get('resume_text', '').strip():
        resume_text = request.form.get('resume_text', '').strip()

    if not resume_text or len(resume_text.strip()) < 50:
        return jsonify({'error': 'Resume text too short or empty.'}), 400

    session['resume_text'] = resume_text[:6000]
    session['job_description'] = ''
    session['history_id'] = None
    session['chat_history'] = []

    return jsonify({'success': True, 'preview': resume_text[:200]})


@app.route('/chat/message', methods=['POST'])
def chat_message():
    data = request.get_json()
    user_message = (data or {}).get('message', '').strip()

    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    resume_text = session.get('resume_text', '')
    if not resume_text:
        return jsonify({'error': 'No resume loaded. Please upload your resume first.'}), 400

    history = session.get('chat_history', [])

    report = None
    history_id = session.get('history_id')
    if history_id:
        record = database.get_analysis_by_id(history_id)
        if record:
            report = record.get('report')

    try:
        response, updated_history = chat_with_resume(
            user_message=user_message,
            resume_text=resume_text,
            history=history,
            report=report
        )
    except Exception as e:
        return jsonify({'error': f'Chat failed: {str(e)}'}), 500

    session['chat_history'] = updated_history[-20:]
    return jsonify({'response': response})


@app.route('/chat/reset', methods=['POST'])
def chat_reset():
    session.clear()
    return jsonify({'success': True})


# ── PDF EXPORT ──

@app.route('/api/export-pdf', methods=['GET'])
def export_pdf():
    """
    Generates and downloads a PDF of the most recent analysis report,
    fetched from SQLite via the history_id stored in the session.
    """
    history_id = session.get('history_id')
    if not history_id:
        return jsonify({'error': 'No analysis found in session. Please analyze a resume first.'}), 400

    record = database.get_analysis_by_id(history_id)
    if not record:
        return jsonify({'error': 'Analysis record not found.'}), 404

    try:
        pdf_bytes = pdf_export.generate_report_pdf(record['report'])
    except Exception as e:
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

    filename = f"resumeiq-report-{history_id}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


@app.route('/api/export-pdf/<int:record_id>', methods=['GET'])
def export_pdf_by_id(record_id):
    """Generates and downloads a PDF for any specific historical record by id."""
    record = database.get_analysis_by_id(record_id)
    if not record:
        return jsonify({'error': 'Record not found.'}), 404

    try:
        pdf_bytes = pdf_export.generate_report_pdf(record['report'])
    except Exception as e:
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

    filename = f"resumeiq-report-{record_id}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


# ── HISTORY (SQLite-backed, survives restarts) ──

@app.route('/api/history', methods=['GET'])
def api_history():
    """Returns recent analysis history (summary fields only, not full reports)."""
    try:
        history = database.get_history(limit=20)
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history/<int:record_id>', methods=['GET'])
def api_history_detail(record_id):
    """Returns one full historical analysis, including the complete report JSON."""
    try:
        record = database.get_analysis_by_id(record_id)
        if not record:
            return jsonify({'error': 'Record not found'}), 404
        return jsonify(record)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, threaded=True)
