import os


def extract_text(filepath: str) -> str:
    ext = filepath.rsplit('.', 1)[1].lower()

    if ext == 'pdf':
        return _extract_pdf(filepath)
    elif ext in ('docx', 'doc'):
        return _extract_docx(filepath)
    elif ext == 'txt':
        return _extract_txt(filepath)
    else:
        raise ValueError(f'Unsupported file type: {ext}')


def _extract_pdf(filepath: str) -> str:
    try:
        import pdfplumber
        text = ''
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
        return text.strip()
    except ImportError:
        raise ImportError('pdfplumber not installed. Run: pip install pdfplumber')


def _extract_docx(filepath: str) -> str:
    try:
        from docx import Document
        doc = Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n'.join(paragraphs)
    except ImportError:
        raise ImportError('python-docx not installed. Run: pip install python-docx')


def _extract_txt(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read().strip()
