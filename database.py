import os
import sqlite3
from pathlib import Path


DATABASE = Path(
    os.getenv("CHATBOT_DATABASE", Path(__file__).resolve().with_name("chatbot.db"))
)

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_database():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        fullname TEXT NOT NULL,

        email TEXT UNIQUE NOT NULL,

        password TEXT NOT NULL

    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chats(

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        user_id INTEGER,

        session_id TEXT,

        question TEXT,

        answer TEXT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(user_id) REFERENCES users(id)

    )
    """)

    # Migrate older databases that predate per-conversation chat history.
    columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(chats)").fetchall()
    }
    if "session_id" not in columns:
        cursor.execute("ALTER TABLE chats ADD COLUMN session_id TEXT")

    conn.commit()

    conn.close()
