"""
Training pipeline — extracts chat history, chunks, embeds, stores.
"""
import os
import struct
import logging
import requests
from datetime import datetime
from typing import List, Dict

from db import bridge_query, sql_query, sql_execute, get_sql_conn, INSTANCE

logger = logging.getLogger("dashboard.training")
LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://192.168.1.32:1234")
LM_STUDIO_API_KEY = os.environ.get("LM_STUDIO_API_KEY", "")


# Shared mutable status for SSE streaming
training_status = {
    "running": False,
    "stage": "",
    "progress": 0,
    "total": 0,
    "messages_processed": 0,
    "chunks_created": 0,
    "embeddings_generated": 0,
    "error": None,
}


def run_training_pipeline():
    """Full training pipeline: extract → chunk → embed → store."""
    global training_status
    training_status.update({
        "running": True, "stage": "initializing", "progress": 0, "total": 0,
        "messages_processed": 0, "chunks_created": 0, "embeddings_generated": 0, "error": None,
    })

    run_id = None
    try:
        # Ensure tables exist
        _ensure_tables()

        # Record training run
        conn = get_sql_conn()
        cur = conn.cursor()
        cur.execute(f"INSERT INTO {INSTANCE}_training_runs (status) VALUES ('running')")
        conn.commit()
        cur.execute("SELECT @@IDENTITY AS id")
        run_id = int(cur.fetchone()["id"])
        conn.close()

        # Stage 1: Extract messages
        training_status["stage"] = "extracting"
        logger.info("Stage 1: Extracting messages from bridge DB")
        messages = bridge_query("""
            SELECT m.id, m.chat_jid, m.sender, m.content, m.timestamp,
                   m.is_from_me, c.name as chat_name
            FROM messages m JOIN chats c ON m.chat_jid = c.jid
            WHERE m.content IS NOT NULL AND m.content != ''
            ORDER BY m.chat_jid, m.timestamp ASC
        """)
        training_status["messages_processed"] = len(messages)
        logger.info(f"Extracted {len(messages)} messages")

        # Stage 2: Chunk into Q&A pairs
        training_status["stage"] = "chunking"
        logger.info("Stage 2: Chunking into Q&A pairs")
        chunks = _chunk_messages(messages)
        training_status["chunks_created"] = len(chunks)
        logger.info(f"Created {len(chunks)} chunks")

        # Stage 3: Generate embeddings
        training_status["stage"] = "embedding"
        training_status["total"] = len(chunks)
        logger.info("Stage 3: Generating embeddings")
        embedded_chunks = _embed_chunks(chunks)
        training_status["embeddings_generated"] = len(embedded_chunks)

        # Stage 4: Store in SQL Server
        training_status["stage"] = "storing"
        logger.info("Stage 4: Storing in SQL Server")
        _store_chunks(embedded_chunks)

        # Mark complete
        training_status["stage"] = "complete"
        training_status["running"] = False
        if run_id:
            sql_execute(f"""
                UPDATE {INSTANCE}_training_runs
                SET status='completed', completed_at=GETDATE(),
                    messages_processed=%s, chunks_created=%s, embeddings_generated=%s
                WHERE id=%s
            """, (len(messages), len(chunks), len(embedded_chunks), run_id))
        logger.info("Training pipeline complete")

    except Exception as e:
        logger.error(f"Training pipeline error: {e}")
        training_status["error"] = str(e)
        training_status["stage"] = "failed"
        training_status["running"] = False
        if run_id:
            sql_execute(f"""
                UPDATE {INSTANCE}_training_runs
                SET status='failed', completed_at=GETDATE(), error_message=%s
                WHERE id=%s
            """, (str(e), run_id))


def _ensure_tables():
    """Create training tables if they don't exist."""
    conn = get_sql_conn()
    cur = conn.cursor()
    cur.execute(f"""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{INSTANCE}_training_chunks' AND xtype='U')
        CREATE TABLE {INSTANCE}_training_chunks (
            id INT IDENTITY(1,1) PRIMARY KEY,
            chat_jid NVARCHAR(255), chat_name NVARCHAR(255),
            chunk_type NVARCHAR(50), question_text NVARCHAR(MAX),
            answer_text NVARCHAR(MAX), full_context NVARCHAR(MAX),
            metadata_json NVARCHAR(MAX), embedding VARBINARY(MAX),
            embedding_model NVARCHAR(255), created_at DATETIME2 DEFAULT GETDATE(),
            source_msg_ids NVARCHAR(MAX))
    """)
    cur.execute(f"""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{INSTANCE}_training_runs' AND xtype='U')
        CREATE TABLE {INSTANCE}_training_runs (
            id INT IDENTITY(1,1) PRIMARY KEY,
            started_at DATETIME2 DEFAULT GETDATE(), completed_at DATETIME2,
            status NVARCHAR(20), messages_processed INT DEFAULT 0,
            chunks_created INT DEFAULT 0, embeddings_generated INT DEFAULT 0,
            error_message NVARCHAR(MAX), embedding_model NVARCHAR(255))
    """)
    conn.commit()
    conn.close()


def _chunk_messages(messages: List[Dict]) -> List[Dict]:
    """Group messages into Q&A conversation chunks."""
    chunks = []
    # Group by chat
    chats = {}
    for msg in messages:
        jid = msg["chat_jid"]
        if jid not in chats:
            chats[jid] = []
        chats[jid].append(msg)

    for jid, chat_msgs in chats.items():
        chat_name = chat_msgs[0].get("chat_name", jid) if chat_msgs else jid

        # Extract Q&A pairs: customer message(s) followed by business reply
        i = 0
        while i < len(chat_msgs):
            # Collect customer messages
            customer_msgs = []
            while i < len(chat_msgs) and not chat_msgs[i]["is_from_me"]:
                customer_msgs.append(chat_msgs[i])
                i += 1

            # Collect business replies
            business_msgs = []
            while i < len(chat_msgs) and chat_msgs[i]["is_from_me"]:
                business_msgs.append(chat_msgs[i])
                i += 1

            if customer_msgs and business_msgs:
                question = "\n".join(m["content"] for m in customer_msgs)
                answer = "\n".join(m["content"] for m in business_msgs)
                # Build context window (up to 5 msgs before)
                start_idx = max(0, chat_msgs.index(customer_msgs[0]) - 5)
                end_idx = chat_msgs.index(business_msgs[-1]) + 1
                context_window = chat_msgs[start_idx:end_idx]
                full_context = "\n".join(
                    f"{'Business' if m['is_from_me'] else 'Customer'}: {m['content']}"
                    for m in context_window
                )
                all_ids = [m["id"] for m in customer_msgs + business_msgs]
                chunks.append({
                    "chat_jid": jid, "chat_name": chat_name,
                    "chunk_type": "qa_pair",
                    "question_text": question, "answer_text": answer,
                    "full_context": full_context,
                    "metadata_json": f'{{"date": "{customer_msgs[0]["timestamp"]}", "chat": "{chat_name}"}}',
                    "source_msg_ids": str(all_ids),
                })
            elif customer_msgs and not business_msgs:
                # Unanswered — skip or move on
                pass

        # Also create conversation segment chunks (sliding window of 10)
        for start in range(0, len(chat_msgs), 8):
            window = chat_msgs[start:start + 10]
            if len(window) < 3:
                continue
            full_text = "\n".join(
                f"{'Business' if m['is_from_me'] else 'Customer'}: {m['content']}"
                for m in window
            )
            chunks.append({
                "chat_jid": jid, "chat_name": chat_name,
                "chunk_type": "conversation",
                "question_text": full_text[:500],
                "answer_text": "",
                "full_context": full_text,
                "metadata_json": f'{{"date": "{window[0]["timestamp"]}", "chat": "{chat_name}"}}',
                "source_msg_ids": str([m["id"] for m in window]),
            })

    return chunks


def _embed_chunks(chunks: List[Dict]) -> List[Dict]:
    """Generate embeddings for chunks via LM Studio."""
    embedded = []
    batch_size = 20

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["question_text"][:1000] for c in batch]

        try:
            headers = {}
            if LM_STUDIO_API_KEY:
                headers["Authorization"] = f"Bearer {LM_STUDIO_API_KEY}"
            resp = requests.post(
                f"{LM_STUDIO_URL}/v1/embeddings",
                json={"input": texts, "model": "text-embedding-nomic-embed-text-v1.5"},
                headers=headers,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                for j, emb_data in enumerate(data.get("data", [])):
                    embedding = emb_data.get("embedding", [])
                    batch[j]["embedding"] = _serialize_embedding(embedding)
                    batch[j]["embedding_model"] = data.get("model", "unknown")
                    embedded.append(batch[j])
            else:
                # If embedding fails, store without embedding
                logger.warning(f"Embedding API returned {resp.status_code}, storing without embeddings")
                for c in batch:
                    c["embedding"] = None
                    c["embedding_model"] = "none"
                    embedded.append(c)
        except Exception as e:
            logger.warning(f"Embedding request failed: {e}, storing without embeddings")
            for c in batch:
                c["embedding"] = None
                c["embedding_model"] = "none"
                embedded.append(c)

        training_status["progress"] = min(i + batch_size, len(chunks))

    return embedded


def _serialize_embedding(embedding: List[float]) -> bytes:
    """Serialize float array to bytes for SQL Server VARBINARY."""
    if not embedding:
        return None
    return struct.pack(f"{len(embedding)}f", *embedding)


def deserialize_embedding(data: bytes) -> List[float]:
    """Deserialize bytes back to float array."""
    if not data:
        return []
    count = len(data) // 4
    return list(struct.unpack(f"{count}f", data))


def _store_chunks(chunks: List[Dict]):
    """Store chunks in SQL Server, replacing old data."""
    conn = get_sql_conn()
    cur = conn.cursor()
    # Clear old chunks
    cur.execute(f"DELETE FROM {INSTANCE}_training_chunks")
    conn.commit()

    for c in chunks:
        cur.execute(f"""
            INSERT INTO {INSTANCE}_training_chunks
            (chat_jid, chat_name, chunk_type, question_text, answer_text,
             full_context, metadata_json, embedding, embedding_model, source_msg_ids)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            c["chat_jid"], c["chat_name"], c["chunk_type"],
            c["question_text"], c["answer_text"], c["full_context"],
            c["metadata_json"], c.get("embedding"), c.get("embedding_model", "none"),
            c.get("source_msg_ids", "[]"),
        ))
    conn.commit()
    conn.close()
    logger.info(f"Stored {len(chunks)} chunks in SQL Server")


def retrieve_similar(query_text: str, top_k: int = 3) -> List[Dict]:
    """Find similar training chunks for RAG context."""
    import numpy as np

    # Try to embed the query
    query_embedding = None
    try:
        headers = {}
        if LM_STUDIO_API_KEY:
            headers["Authorization"] = f"Bearer {LM_STUDIO_API_KEY}"
        resp = requests.post(
            f"{LM_STUDIO_URL}/v1/embeddings",
            json={"input": [query_text[:1000]], "model": "text-embedding-nomic-embed-text-v1.5"},
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            embs = data.get("data", [])
            if embs:
                query_embedding = np.array(embs[0]["embedding"], dtype=np.float32)
    except Exception:
        pass

    # If embedding available, do cosine similarity search
    if query_embedding is not None:
        try:
            chunks = sql_query(f"""
                SELECT id, question_text, answer_text, full_context, chat_name, embedding
                FROM {INSTANCE}_training_chunks
                WHERE chunk_type = 'qa_pair' AND embedding IS NOT NULL
            """)
            scored = []
            for c in chunks:
                emb_bytes = c.get("embedding")
                if not emb_bytes:
                    continue
                stored = np.array(deserialize_embedding(emb_bytes), dtype=np.float32)
                if len(stored) != len(query_embedding):
                    continue
                cos_sim = float(np.dot(query_embedding, stored) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(stored) + 1e-8
                ))
                scored.append((cos_sim, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [s[1] for s in scored[:top_k]]
        except Exception:
            pass

    # Fallback: keyword match
    try:
        words = query_text.split()[:5]
        conditions = " OR ".join(f"question_text LIKE '%{w}%'" for w in words if len(w) > 3)
        if conditions:
            return sql_query(f"""
                SELECT TOP {top_k} id, question_text, answer_text, full_context, chat_name
                FROM {INSTANCE}_training_chunks
                WHERE chunk_type = 'qa_pair' AND ({conditions})
                ORDER BY id DESC
            """)
    except Exception:
        pass
    return []
