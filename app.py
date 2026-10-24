from google import genai
from dotenv import load_dotenv
import os
import uuid
from flask import Flask, render_template, request, redirect, session, flash
from database import create_database, get_connection
from werkzeug.security import check_password_hash, generate_password_hash
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "development-only-change-this-secret")

# Create Gemini Client. Set GEMINI_MODEL to override the supported default.
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

create_database()


def verify_password(stored_password, submitted_password):
    """Verify hashed passwords and support upgrading legacy plaintext rows."""
    if stored_password.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(stored_password, submitted_password)
    return stored_password == submitted_password


# =====================================
# LOGIN PAGE
# =====================================

@app.route("/")
def login():
    success_message = session.pop("login_success_message", None)
    return render_template("login.html", success_message=success_message)


# =====================================
# REGISTER PAGE
# =====================================

@app.route("/register")
def register():
    return render_template("register.html")


# =====================================
# FORGOT PASSWORD PAGE
# =====================================

@app.route("/forgot")
def forgot():
    return render_template("forget_password.html")


# =====================================
# REGISTER USER
# =====================================

@app.route("/register_user", methods=["POST"])
def register_user():

    fullname = request.form["fullname"]
    email = request.form["email"]
    password = request.form["password"]

    pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$"

    if not re.match(pattern, password):

        flash("Password must contain Uppercase, Lowercase, Number and Special Character.", "error")

        return redirect("/register")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    )

    existing_user = cursor.fetchone()

    if existing_user:

        conn.close()

        flash("Email already registered. Please Login.", "error")

        return redirect("/")

    cursor.execute(
        """
        INSERT INTO users(fullname,email,password)
        VALUES(?,?,?)
        """,
        (fullname, email, generate_password_hash(password))
    )

    conn.commit()
    conn.close()

    flash("Registration Successful. Please Login.", "success")

    return redirect("/")


# =====================================
# LOGIN USER
# =====================================

@app.route("/login_user", methods=["POST"])
def login_user():

    email = request.form["email"]
    password = request.form["password"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))

    user = cursor.fetchone()

    if user and verify_password(user["password"], password):
        # Upgrade existing plaintext passwords on the next successful login.
        if not user["password"].startswith(("scrypt:", "pbkdf2:")):
            cursor.execute(
                "UPDATE users SET password=? WHERE id=?",
                (generate_password_hash(password), user["id"]),
            )
            conn.commit()
    else:
        user = None

    conn.close()

    if user:

        session["user_id"] = user["id"]
        session["username"] = user["fullname"]
        session["login_success_message"] = "Login Successful."

        return redirect("/")

    flash("Invalid Email or Password.", "error")

    return redirect("/")


# =====================================
# FORGOT PASSWORD
# =====================================

@app.route("/forgot_password", methods=["POST"])
def forgot_password():

    email = request.form["email"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    )

    user = cursor.fetchone()

    conn.close()

    if user is None:

        flash("No account found with this email.", "error")

        return redirect("/forgot")

    return redirect(f"/reset/{email}")
# =====================================
# RESET PASSWORD PAGE
# =====================================

@app.route("/reset/<email>")
def reset_password_page(email):

    return render_template(
        "reset_password.html",
        email=email
    )


# =====================================
# UPDATE PASSWORD
# =====================================

@app.route("/update_password", methods=["POST"])
def update_password():

    email = request.form["email"]
    password = request.form["password"]
    confirm_password = request.form["confirm_password"]

    # Check password match
    if password != confirm_password:

        flash("Passwords do not match.", "error")

        return redirect(f"/reset/{email}")

    # Password validation
    pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$"

    if not re.match(pattern, password):

        flash("Password must contain Uppercase, Lowercase, Number and Special Character.", "error")

        return redirect(f"/reset/{email}")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET password=?
        WHERE email=?
        """,
        (generate_password_hash(password), email)
    )

    conn.commit()

    conn.close()

    flash("Password Updated Successfully. Please Login.", "success")

    return redirect("/")

# =====================================
# ASK AI
# =====================================

@app.route("/ask", methods=["POST"])
def ask():

    if "user_id" not in session:
        return {"answer": "Please login first."}

    if client is None:
        return {"answer": "Gemini API key is not configured. Set GEMINI_API_KEY in your .env file."}

    question = request.form.get("question", "").strip()
    if not question:
        return {"answer": "Please enter a question."}, 400
    if len(question) > 10000:
        return {"answer": "Please keep your question under 10,000 characters."}, 400

    session_id = request.form.get("session_id", "").strip() or uuid.uuid4().hex

    # Keep model context private to the signed-in user's selected conversation.
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT question, answer FROM chats
        WHERE user_id=? AND session_id=?
        ORDER BY id DESC
        LIMIT 20
        """,
        (session["user_id"], session_id),
    )
    previous_turns = list(reversed(cursor.fetchall()))
    conn.close()

    contents = []
    for turn in previous_turns:
        contents.append({"role": "user", "parts": [{"text": turn["question"]}]})
        contents.append({"role": "model", "parts": [{"text": turn["answer"]}]})
    contents.append({"role": "user", "parts": [{"text": question}]})

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
        )

        answer = response.text or "I couldn't generate a response. Please try again."

    except Exception:
        app.logger.exception("Gemini request failed")
        return {
            "answer": "Sorry, something went wrong. Please try again."
        }, 502

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO chats(user_id, session_id, question, answer)
        VALUES (?, ?, ?, ?)
        """,
        (
            session["user_id"],
            session_id,
            question,
            answer
        )
    )

    conn.commit()
    conn.close()

    return {"answer": answer, "session_id": session_id}
# =====================================
# CHAT HISTORY
# =====================================

@app.route("/history")
def history():

    # User login ayyi unnada check
    if "user_id" not in session:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    # Current logged-in user chats only
    cursor.execute("""
        SELECT id, question, answer
        FROM chats
        WHERE user_id=?
        ORDER BY id DESC
    """, (session["user_id"],))

    chats = cursor.fetchall()

    conn.close()

    history_data = []

    for chat in chats:

        history_data.append({
            "id": chat["id"],
            "question": chat["question"],
            "answer": chat["answer"]
        })

    return history_data
# =====================================
# GET CHAT SESSIONS (SIDEBAR)
# =====================================

@app.route("/api/chats")
def get_chats():

    if "user_id" not in session:
        return {"chats": []}

    conn = get_connection()
    cursor = conn.cursor()

# Group chats by session, showing the newest question + last message time.
    # Chats with NULL/empty session_id (legacy ones) are grouped under a
    # generated key (legacy_<id>) so they still appear in the sidebar and
    # can be opened/deleted like any other conversation.
    cursor.execute("""
        WITH grouped AS (
            SELECT user_id,
                   CASE
                       WHEN session_id IS NOT NULL AND session_id != '' THEN session_id
                       ELSE 'legacy_' || id
                   END AS session_key,
                   MAX(created_at) AS last_time
            FROM chats
            WHERE user_id=?
            GROUP BY user_id, session_key
        )
        SELECT grouped.session_key,
               grouped.last_time,
               (SELECT latest.question
                FROM chats AS latest
                WHERE latest.user_id = grouped.user_id
                  AND COALESCE(NULLIF(latest.session_id, ''), 'legacy_' || latest.id) = grouped.session_key
                ORDER BY latest.id DESC
                LIMIT 1) AS last_question
        FROM grouped
        ORDER BY grouped.last_time DESC
    """, (session["user_id"],))

    rows = cursor.fetchall()
    conn.close()

    return {
        "chats": [
            {
                "session_id": row["session_key"],
                "title": row["last_question"] or "New Chat",
                "time": row["last_time"]
            }
            for row in rows
        ]
    }


# =====================================
# GET SINGLE CONVERSATION
# =====================================

@app.route("/api/chats/<session_id>")
def get_conversation(session_id):

    if "user_id" not in session:
        return {"messages": []}

    conn = get_connection()
    cursor = conn.cursor()

    # Support legacy chats (stored with NULL session_id) via "legacy_<id>"
    if session_id.startswith("legacy_"):
        chat_id = session_id.split("_", 1)[1]
        cursor.execute("""
            SELECT question, answer, created_at
            FROM chats
            WHERE user_id=? AND id=?
            ORDER BY id ASC
        """, (session["user_id"], chat_id))
    else:
        cursor.execute("""
            SELECT question, answer, created_at
            FROM chats
            WHERE user_id=? AND session_id=?
            ORDER BY id ASC
        """, (session["user_id"], session_id))

    rows = cursor.fetchall()
    conn.close()

    return {
        "messages": [
            {
                "question": row["question"],
                "answer": row["answer"],
                "time": row["created_at"]
            }
            for row in rows
        ]
    }


# =====================================
# DELETE A CHAT SESSION
# =====================================

@app.route("/api/chats/<session_id>", methods=["DELETE"])
def delete_chat(session_id):

    if "user_id" not in session:
        return {"success": False}, 401

    conn = get_connection()
    cursor = conn.cursor()

    # Support legacy chats (stored with NULL session_id) via "legacy_<id>"
    if session_id.startswith("legacy_"):
        chat_id = session_id.split("_", 1)[1]
        cursor.execute("""
            DELETE FROM chats
            WHERE user_id=? AND id=?
        """, (session["user_id"], chat_id))
    else:
        cursor.execute("""
            DELETE FROM chats
            WHERE user_id=? AND session_id=?
        """, (session["user_id"], session_id))

    conn.commit()
    conn.close()

    return {"success": True}


# =====================================
# CLEAR ALL CHATS
# =====================================

@app.route("/api/chats", methods=["DELETE"])
def clear_chats():

    if "user_id" not in session:
        return {"success": False}, 401

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM chats WHERE user_id=?",
        (session["user_id"],)
    )

    conn.commit()
    conn.close()

    return {"success": True}

# ===========================
# CHAT PAGE
# ===========================

@app.route("/chat")
def chat():
    if "user_id" not in session:

        flash("Please Login First.", "error")

        return redirect("/")

    return render_template(
        "index.html",
        username=session["username"]
    )


# =====================================
# LOGOUT
# =====================================

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged out Successfully.", "success")

    return redirect("/")


# =====================================
# RUN APPLICATION
# =====================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
