import json
import os
import shutil
import sqlite3
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from werkzeug.utils import secure_filename

from foundry_local_sdk import Configuration, FoundryLocalManager

from document_loader import SUPPORTED_EXTENSIONS, chunk_text, read_document
from rag_core import (
    build_context,
    build_messages,
    create_database,
    extract_percentage_answer,
    filter_relevant_results,
    find_relevant_chunks,
    generate_answer,
    insert_chunks,
    is_percentage_question,
    load_chunks,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
MAX_FILE_SIZE_MB = 25

app = Flask(__name__)
app.secret_key = os.environ.get("LOCAL_RAG_SECRET_KEY", "local-rag-assistant-secret-key")
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE_MB * 1024 * 1024

_embedding_client = None
_chat_client = None


def ensure_base_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def get_session_id():
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())

    return session["session_id"]


def get_session_dir():
    ensure_base_dirs()

    session_id = get_session_id()
    session_dir = SESSIONS_DIR / session_id
    upload_dir = session_dir / "uploads"

    upload_dir.mkdir(parents=True, exist_ok=True)

    return session_dir


def get_upload_dir():
    return get_session_dir() / "uploads"


def get_database_path():
    database_path = get_session_dir() / "rag.db"
    print(f"[session] Database path: {database_path}")
    return database_path


def allowed_file(filename):
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def get_clients():
    global _embedding_client
    global _chat_client

    if _embedding_client is not None and _chat_client is not None:
        return _embedding_client, _chat_client

    print("[models] Initializing Foundry Local...")

    config = Configuration(app_name="local_rag_website")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    print("[models] Loading embedding model...")
    embedding_model = manager.catalog.get_model("qwen3-embedding-0.6b")
    embedding_model.download()
    embedding_model.load()
    _embedding_client = embedding_model.get_embedding_client()

    print("[models] Loading chat model...")
    chat_model = manager.catalog.get_model("qwen2.5-0.5b")
    chat_model.download()
    chat_model.load()
    _chat_client = chat_model.get_chat_client()

    print("[models] Models are ready.")

    return _embedding_client, _chat_client


def build_database_from_uploads():
    upload_dir = get_upload_dir()
    database_path = get_database_path()

    print(f"[indexing] Upload directory: {upload_dir}")
    print(f"[indexing] Database path: {database_path}")

    embedding_client, _ = get_clients()

    create_database(database_path)

    uploaded_files = [
        file_path
        for file_path in upload_dir.iterdir()
        if file_path.is_file() and allowed_file(file_path.name)
    ]

    if not uploaded_files:
        raise ValueError("No supported files were found in the upload folder.")

    total_chunks = 0
    processed_files = []
    insert_rows = []

    for file_path in uploaded_files:
        print(f"[indexing] Reading {file_path.name}...")
        document_items = read_document(file_path)

        for item in document_items:
            chunks = chunk_text(item["text"])

            for chunk_index, chunk in enumerate(chunks):
                response = embedding_client.generate_embedding(chunk)
                embedding = response.data[0].embedding

                insert_rows.append(
                    (
                        file_path.name,
                        item["content_type"],
                        item["location"],
                        chunk_index,
                        chunk,
                        json.dumps(embedding),
                    )
                )

                total_chunks += 1

        processed_files.append(file_path.name)

    if not insert_rows:
        raise ValueError("No readable text chunks were extracted from the uploaded files.")

    insert_chunks(database_path, insert_rows)

    print(f"[indexing] Inserted {total_chunks} chunks.")

    return processed_files, total_chunks


@app.route("/")
def index():
    ensure_base_dirs()
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_files():
    if "files" not in request.files:
        return jsonify({"success": False, "message": "No files were uploaded."}), 400

    files = request.files.getlist("files")

    if not files:
        return jsonify({"success": False, "message": "Please select at least one file."}), 400

    upload_dir = get_upload_dir()
    saved_files = []

    for file in files:
        if not file.filename:
            continue

        if not allowed_file(file.filename):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Unsupported file type: {file.filename}",
                    }
                ),
                400,
            )

        filename = secure_filename(file.filename)
        file_path = upload_dir / filename
        file.save(file_path)
        saved_files.append(filename)

    if not saved_files:
        return jsonify({"success": False, "message": "No valid files were saved."}), 400

    try:
        processed_files, total_chunks = build_database_from_uploads()
    except Exception as error:
        print(f"[indexing-error] {error}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Files were uploaded, but indexing failed: {error}",
                }
            ),
            500,
        )

    return jsonify(
        {
            "success": True,
            "message": "Files uploaded and indexed successfully.",
            "files": processed_files,
            "chunks": total_chunks,
            "database_created": get_database_path().exists(),
        }
    )


@app.route("/ask", methods=["POST"])
def ask_question():
    data = request.get_json()
    question = data.get("question", "").strip() if data else ""

    if not question:
        return jsonify({"success": False, "message": "Please enter a question."}), 400

    database_path = get_database_path()

    if not database_path.exists():
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Please upload and index at least one document first.",
                }
            ),
            400,
        )

    try:
        chunks = load_chunks(database_path)
    except sqlite3.OperationalError:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "The database is not ready. Please upload your documents again.",
                }
            ),
            400,
        )

    if not chunks:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "No document chunks found. Please upload your documents again.",
                }
            ),
            400,
        )

    embedding_client, chat_client = get_clients()

    query_response = embedding_client.generate_embedding(question)
    query_embedding = query_response.data[0].embedding

    results = find_relevant_chunks(question, query_embedding, chunks)
    relevant_results = filter_relevant_results(results)

    if not relevant_results:
        return jsonify(
            {
                "success": True,
                "answer": "The documents do not contain enough information to answer this question.",
                "sources": [],
            }
        )

    if is_percentage_question(question):
        direct_answer = extract_percentage_answer(relevant_results)

        if direct_answer:
            sources = [
                {
                    "source": chunk["source"],
                    "location": chunk["location"],
                    "score": round(combined_score, 4),
                }
                for chunk, combined_score, similarity, overlap in relevant_results
            ]

            return jsonify({"success": True, "answer": direct_answer, "sources": sources})

    context = build_context(relevant_results)
    messages = build_messages(question, context)
    answer = generate_answer(chat_client, messages)

    sources = [
        {
            "source": chunk["source"],
            "location": chunk["location"],
            "score": round(combined_score, 4),
        }
        for chunk, combined_score, similarity, overlap in relevant_results
    ]

    return jsonify({"success": True, "answer": answer, "sources": sources})


@app.route("/status")
def status():
    database_path = get_database_path()
    upload_dir = get_upload_dir()

    chunk_count = 0

    if database_path.exists():
        try:
            chunk_count = len(load_chunks(database_path))
        except sqlite3.OperationalError:
            chunk_count = 0

    files = [
        file_path.name
        for file_path in upload_dir.iterdir()
        if file_path.is_file()
    ]

    return jsonify(
        {
            "success": True,
            "database_exists": database_path.exists(),
            "chunk_count": chunk_count,
            "uploaded_files": files,
        }
    )


@app.route("/reset", methods=["POST"])
def reset_session():
    session_dir = get_session_dir()

    if session_dir.exists():
        shutil.rmtree(session_dir)

    session.clear()

    ensure_base_dirs()

    return jsonify({"success": True, "message": "Session cleared."})


if __name__ == "__main__":
    ensure_base_dirs()
    app.run(host="127.0.0.1", port=5000, debug=False)
