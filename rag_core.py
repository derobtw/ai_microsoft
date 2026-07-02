import json
import math
import re
import sqlite3
from pathlib import Path


TOP_K = 5
MIN_COMBINED_SCORE = 0.42
MIN_KEYWORD_OVERLAP = 0.20
MAX_ANSWER_CHARS = 1200

STOPWORDS = {
    "what",
    "who",
    "is",
    "the",
    "a",
    "an",
    "of",
    "in",
    "on",
    "to",
    "for",
    "and",
    "or",
    "does",
    "do",
    "did",
    "with",
    "by",
    "from",
    "this",
    "that",
    "it",
    "are",
    "was",
    "were",
    "be",
    "as",
    "at",
    "how",
    "why",
    "when",
    "where",
    "which",
    "can",
    "could",
    "should",
    "would",
    "tell",
    "me",
    "about",
    "please",
}


def normalize_token(token):
    token = token.lower()

    if len(token) > 3 and token.endswith("s"):
        token = token[:-1]

    return token


def tokenize_keywords(text):
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())

    return [
        normalize_token(token)
        for token in tokens
        if token not in STOPWORDS and len(token) > 1
    ]


def keyword_overlap(question, searchable_text):
    question_keywords = set(tokenize_keywords(question))

    if not question_keywords:
        return 0.0

    searchable_keywords = set(tokenize_keywords(searchable_text))
    matched_keywords = question_keywords.intersection(searchable_keywords)

    return len(matched_keywords) / len(question_keywords)


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def create_database(database_path):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[database] Creating database at: {database_path}")

    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    cursor.execute("DROP TABLE IF EXISTS chunks")

    cursor.execute(
        """
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            content_type TEXT NOT NULL,
            location TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding TEXT NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()

    print("[database] Database table created.")


def insert_chunks(database_path, rows):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    cursor.executemany(
        """
        INSERT INTO chunks (
            source,
            content_type,
            location,
            chunk_index,
            chunk_text,
            embedding
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    connection.commit()
    connection.close()


def load_chunks(database_path):
    connection = sqlite3.connect(database_path)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, source, content_type, location, chunk_index, chunk_text, embedding
        FROM chunks
        """
    )

    rows = cursor.fetchall()
    connection.close()

    chunks = []

    for row in rows:
        chunk_id, source, content_type, location, chunk_index, chunk_text, embedding_json = row

        chunks.append(
            {
                "id": chunk_id,
                "source": source,
                "content_type": content_type,
                "location": location,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "embedding": json.loads(embedding_json),
            }
        )

    return chunks


def find_relevant_chunks(question, query_embedding, chunks, top_k=TOP_K):
    scored_chunks = []

    for chunk in chunks:
        searchable_text = (
            f"{chunk['source']} "
            f"{chunk['content_type']} "
            f"{chunk['location']} "
            f"{chunk['chunk_text']}"
        )

        similarity = cosine_similarity(query_embedding, chunk["embedding"])
        overlap = keyword_overlap(question, searchable_text)
        combined_score = (0.70 * similarity) + (0.30 * overlap)

        scored_chunks.append((chunk, combined_score, similarity, overlap))

    scored_chunks.sort(key=lambda item: item[1], reverse=True)

    return scored_chunks[:top_k]


def filter_relevant_results(results):
    relevant_results = []

    for chunk, combined_score, similarity, overlap in results:
        if combined_score >= MIN_COMBINED_SCORE and (
            overlap >= MIN_KEYWORD_OVERLAP or similarity >= 0.55
        ):
            relevant_results.append((chunk, combined_score, similarity, overlap))

    return relevant_results


def build_context(results):
    context_parts = []

    for index, (chunk, combined_score, similarity, overlap) in enumerate(results, start=1):
        context_parts.append(f"Excerpt {index}:\n{chunk['chunk_text']}")

    return "\n\n".join(context_parts)


def build_messages(question, context):
    return [
        {
            "role": "system",
            "content": (
                "You are a local document Q&A assistant. "
                "Use ONLY the provided context to answer the user's question. "
                "Do NOT use your own knowledge. "
                "Do NOT answer from memory. "
                "If the answer is not explicitly written in the context, say exactly: "
                "'The documents do not contain enough information to answer this question.' "
                "Give the direct answer only. "
                "Do not mention excerpts, chunks, scores, or internal retrieval details. "
                "Do not explain your reasoning. "
                "Do not repeat the same sentence. "
                "Stop after the answer is complete.\n\n"
                f"Context:\n{context}"
            ),
        },
        {
            "role": "user",
            "content": question,
        },
    ]


def is_percentage_question(question):
    question = question.lower()

    return (
        "percentage" in question
        or "percentages" in question
        or "percent" in question
        or "yüzde" in question
        or "%" in question
    )


def extract_percentage_answer(results):
    extracted = []
    seen = set()

    for chunk, combined_score, similarity, overlap in results:
        text = chunk["chunk_text"]
        pattern = r"([A-Za-z][A-Za-z0-9 .:/_-]{1,60}?)(?:\s*\|\s*|\s+)(\d+(?:\.\d+)?)%"
        matches = re.findall(pattern, text)

        for label, percentage in matches:
            label = " ".join(label.split()).strip(":-| ")

            if len(label) > 50:
                label = label[-50:].strip()

            item = f"{label}: {percentage}%"

            if item not in seen:
                extracted.append(item)
                seen.add(item)

    if not extracted:
        return None

    return "\n".join(f"- {item}" for item in extracted)


def generate_answer(chat_client, messages):
    answer = ""

    for chunk in chat_client.complete_streaming_chat(messages):
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)

        if content:
            answer += content

        if len(answer) >= MAX_ANSWER_CHARS:
            answer += "\n\n[Answer stopped because it became too long.]"
            break

    return answer.strip()
