# Local RAG Assistant


https://derobtw.github.io/ai_microsoft/


A local Retrieval-Augmented Generation assistant built with Microsoft Foundry Local, Flask, SQLite, and a custom HTML/CSS/JavaScript interface.

The app lets a user upload PDF, DOCX, or TXT files, indexes them into a local SQLite database, retrieves relevant chunks, and answers questions using only the retrieved document context.

## What This Version Fixes

- Creates `data/sessions/` automatically.
- Creates each session folder automatically.
- Creates the upload folder automatically.
- Creates the parent folder of `rag.db` before SQLite connects.
- Drops and recreates the `chunks` table on every upload/index operation.
- Prints the database path and indexing progress in the backend terminal.
- Adds a `/status` endpoint so the UI can show whether the database exists and how many chunks were indexed.

## Project Structure

```text
local-rag-assistant-fixed/
├── app.py
├── document_loader.py
├── rag_core.py
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── styles.css
│   └── script.js
├── documents/
│   └── sample_note.txt
└── data/
    └── sessions/
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Usage

1. Upload one or more `.pdf`, `.docx`, or `.txt` files.
2. Click **Upload and index**.
3. Wait until the UI says chunks were indexed.
4. Ask a question.

## Where the Database Is Created

The app creates a separate database per browser session:

```text
data/sessions/<session-id>/rag.db
```

It does not use the old project-level `rag.db`.

## Important

This app is designed as a local web app. It cannot run as a plain Netlify or GitHub Pages static site because it needs:

- Python Flask backend
- Foundry Local runtime
- local model loading
- SQLite database creation
- PDF/DOCX parsing

## OCR Note

Text-based PDFs work normally. Scanned image PDFs need Tesseract OCR installed on the computer. The app includes optional OCR support through `pytesseract`, but the external Tesseract program must also be installed for OCR to work.
