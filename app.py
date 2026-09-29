from openai import OpenAI
from google import genai
from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, session, flash
from database import create_database, get_connection
import re
app = Flask(__name__)

# Load environment variables
load_dotenv()

# Create Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

app.secret_key = "meta_ai_secret_key"


create_database()


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
        (fullname, email, password)
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

    cursor.execute(
        """
        SELECT * FROM users
        WHERE email=? AND password=?
        """,
        (email, password)
    )

    user = cursor.fetchone()

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
        (password, email)
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

    question = request.form["question"]
    session_id = request.form.get("session_id", "")

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=question
        )

        answer = response.text

    except Exception as e:
        print("Gemini Error:", e)
        return {
            "answer": "Sorry, something went wrong. Please try again."
        }

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

# Group chats by session, showing latest question + last message time.
    # Chats with NULL/empty session_id (legacy ones) are grouped under a
    # generated key (legacy_<id>) so they still appear in the sidebar and
    # can be opened/deleted like any other conversation.
    cursor.execute("""
        SELECT CASE
                 WHEN session_id IS NOT NULL AND session_id != '' THEN session_id
                 ELSE 'legacy_' || id
               END AS session_key,
               MAX(created_at) AS last_time,
               question AS last_question
        FROM chats
        WHERE user_id=?
        GROUP BY session_key
        ORDER BY last_time DESC
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
