from flask import Flask, render_template, request, redirect, url_for, session , flash
import joblib
import re
import string
from datetime import datetime
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
import os


app = Flask(__name__)
app.secret_key = "secret123"

@app.context_processor
def inject_user():
    return dict(username=session.get("username"))



# ---------------- DATABASE ----------------
conn = sqlite3.connect('history.db', check_same_thread=False)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE history ADD COLUMN is_starred INTEGER DEFAULT 0")
    conn.commit()
except:
    pass

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT UNIQUE,
    password TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    email TEXT,
    result TEXT,
    date TEXT,
    is_starred INTEGER DEFAULT 0
)
''')

conn.commit()

# ---------------- LOAD MODEL ----------------
model = joblib.load("spam_model.pkl")
tfidf = joblib.load("tfidf_vectorizer.pkl")

# ---------------- CLEAN TEXT ----------------
def clean_text(text):
    text = str(text).lower()
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'\d+', '', text)
    text = text.translate(str.maketrans('', '', string.punctuation))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ---------------- HOME ----------------
@app.route("/")
def home():
    if 'user_id' not in session:
        return redirect("/login")
    return render_template("Homepage.html", username=session.get("username"))

# ---------------- SEND OTP EMAIL ----------------
def send_otp_email(receiver_email, otp):
    sender_email = "emailspamdetection555@gmail.com"      # 👉 change this
    app_password = "phzj cwtn oqqe pgqo"        # 👉 paste app password here

    subject = "OTP Verification"
    body = f"Your OTP is: {otp}"

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        print("OTP sent to email ✅")
    except Exception as e:
        print("Error:", e)


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        try:
            cursor.execute(
    "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
    (username, email, password)
)
            conn.commit()
            return redirect("/login")
        except:
            return "Email already exists"

    return render_template("signup.html")


# ---------------- LOGIN ----------------
# @app.route("/login", methods=["GET","POST"])
# def login():
#     if request.method == "POST":
#         email = request.form['email']
#         password = request.form['password']

#         cursor.execute(
#             "SELECT * FROM users WHERE email=? AND password=?",
#             (email, password)
#         )
#         user = cursor.fetchone()

#         if user:
#             session['user_id'] = user[0]
#             session['username'] = user[1]   # ✅ now username column
#             session['email'] = user[2]
#             return redirect("/")   # ✅ go to homepage
#         else:
#             return "Invalid Login"

#     return render_template("login.html")
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        cursor.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['email'] = user[2]
            return redirect("/")
        else:
            flash("Invalid email or password", "danger")   # 🔥 HERE
            return redirect("/login")

    return render_template("login.html")


# ---------------- FORGOT PASSWORD ----------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = request.form['email']

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        if user:
            otp = str(random.randint(1000, 9999))

            session["reset_email"] = email
            session["otp"] = otp

            send_otp_email(email, otp)   # ✅ send OTP

            return redirect("/otp")
        else:
            return "Email not found"

    return render_template("forgot.html")


# ---------------- OTP PAGE ----------------
@app.route("/otp")
def otp():
    return render_template("otp.html")


# ---------------- VERIFY OTP ----------------
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    user_otp = request.form['otp']

    if user_otp == session.get("otp"):
        return redirect("/reset")
    else:
        return "Invalid OTP"


@app.route("/reset")
def reset_page():
    return render_template("resetpassword.html")


# ---------------- RESET PASSWORD PAGE ----------------
@app.route("/reset-password", methods=["POST"])
def reset_password():
    new_password = request.form['password']
    email = session.get("reset_email")

    cursor.execute("UPDATE users SET password=? WHERE email=?", (new_password, email))
    conn.commit()

    session.clear()
    return redirect("/login?reset=success")

@app.route("/logout")
def logout():
    session.clear()          # remove all session data
    return redirect("/login")

# ---------------- PROFILE ----------------
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if 'user_id' not in session:
        return redirect("/login")

    if request.method == "POST":
        username = request.form.get("username")

        # VALIDATION
        if username and len(username) < 3:
            return redirect("/profile?error=username")

        # UPDATE USERNAME
        if username:
            cursor.execute(
                "UPDATE users SET username=? WHERE id=?",
                (username, session['user_id'])
            )
            session['username'] = username
            conn.commit()

        return redirect("/profile?success=1")

    return render_template(
        "profile.html",
        username=session.get("username"),
        email=session.get("email")
    )

@app.route("/change-password", methods=["GET","POST"])
def change_password():
    if 'user_id' not in session:
        return redirect("/login")

    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")

        if len(new_password) < 4:
            return redirect("/change-password?error=weak")

        cursor.execute(
            "SELECT password FROM users WHERE id=?",
            (session['user_id'],)
        )
        current = cursor.fetchone()[0]

        if old_password != current:
            return redirect("/change-password?error=wrong")

        cursor.execute(
            "UPDATE users SET password=? WHERE id=?",
            (new_password, session['user_id'])
        )
        conn.commit()

        # ✅ IMPORTANT FIX
        session.clear()
        return redirect("/login?reset=success")

    return render_template("change_password.html")

# ---------------- PREDICT ----------------
@app.route("/Predict", methods=["GET", "POST"])
def predict():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == "POST":
        email_text = request.form.get("email")

        cleaned = clean_text(email_text)
        vec = tfidf.transform([cleaned])

        prob = model.predict_proba(vec)[0][1]
        prediction = "SPAM" if prob >= 0.7 else "NOT SPAM"

        date = datetime.now().strftime("%d-%m-%Y %H:%M")

        cursor.execute(
            "INSERT INTO history (user_id, email, result, date) VALUES (?, ?, ?, ?)",
            (session['user_id'], email_text, prediction, date)
        )
        conn.commit()

        return render_template(
            "result.html",
            prediction=prediction,
            probability=f"{prob:.2%}",
            email=email_text
        )

    return render_template("Predict.html")

# ---------------- HISTORY ----------------
# @app.route("/history")
# def view_history():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))

#     cursor.execute(
#         "SELECT * FROM history WHERE user_id=? ORDER BY id DESC",
#         (session['user_id'],)
#     )
#     data = cursor.fetchall()

#     history = []
#     total = len(data)

#     for i, row in enumerate(data):
#         history.append({
#             "id": total - i,        # ✅ correct numbering (1,2,3...)
#             "real_id": row[0],      # DB id for delete
#             "email": row[2],
#             "result": row[3],
#             "date": row[4]
#         })

#     return render_template("history.html", history=history, from_search=False)

@app.route("/history")
def view_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute(
        "SELECT * FROM history WHERE user_id=? ORDER BY id DESC",
        (session['user_id'],)
    )
    data = cursor.fetchall()

    history = []
    total = len(data)

    for i, row in enumerate(data):
        history.append({
            "id": row[0] ,
            "real_id": row[0],
            "email": row[2],
            "result": row[3],
            "date": row[4],
            "starred": row[5]   # ⭐ NEW
        })

    return render_template("history.html", history=history, page_title="Prediction History")

@app.route("/toggle_star/<int:id>")
def toggle_star(id):
    if 'user_id' not in session:
        return redirect("/login")

    cursor.execute("SELECT is_starred FROM history WHERE id=?", (id,))
    current = cursor.fetchone()[0]

    new_value = 0 if current == 1 else 1

    cursor.execute("UPDATE history SET is_starred=? WHERE id=?", (new_value, id))
    conn.commit()

    return redirect(request.referrer)

@app.route("/starred")
def starred():
    if 'user_id' not in session:
        return redirect("/login")

    cursor.execute(
        "SELECT * FROM history WHERE user_id=? AND is_starred=1 ORDER BY id DESC",
        (session['user_id'],)
    )
    data = cursor.fetchall()

    history = []
    total = len(data)

    for i, row in enumerate(data):
        history.append({
            "id": row[0],
            "real_id": row[0],
            "email": row[2],
            "result": row[3],
            "date": row[4],
            "starred": row[5]
        })

    return render_template("history.html", history=history, page_title="Starred Emails")

# ---------------- DELETE SINGLE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("DELETE FROM history WHERE id=?", (id,))
    conn.commit()

    return redirect(url_for('view_history'))

# ---------------- DELETE ALL ----------------
@app.route("/clear_history")
def clear_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("DELETE FROM history WHERE user_id=?", (session['user_id'],))
    conn.commit()

    return redirect(url_for('view_history'))

# ---------------- SEARCH ----------------
# @app.route("/search", methods=["POST"])
# def search():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))

#     keyword = request.form.get("keyword")

#     cursor.execute(
#         "SELECT * FROM history WHERE user_id=? AND email LIKE ? ORDER BY id DESC",
#         (session['user_id'], f"%{keyword}%")
#     )
#     data = cursor.fetchall()

#     history = []
#     total = len(data)

#     for i, row in enumerate(data):
#         history.append({
#             "id": total - i,
#             "real_id": row[0],
#             "email": row[2],
#             "result": row[3],
#             "date": row[4],
#             "starred": row[5] 
#         })

#     return render_template("history.html", history=history, from_search=True)

@app.route("/search", methods=["POST"])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    keyword = request.form.get("keyword")

    cursor.execute(
        """SELECT * FROM history 
           WHERE user_id=? 
           AND (email LIKE ? OR result LIKE ? OR date LIKE ?) 
           ORDER BY id DESC""",
        (session['user_id'], f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
    )

    data = cursor.fetchall()

    history = []
    total = len(data)

    for i, row in enumerate(data):
        history.append({
            "id": total - i,
            "real_id": row[0],
            "email": row[2],
            "result": row[3],
            "date": row[4],
            "starred": row[5]   # ⭐ IMPORTANT (must include this)
        })

    return render_template("history.html", history=history, from_search=True)

@app.route("/delete_selected", methods=["POST"])
def delete_selected():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    ids = request.form.getlist("selected_ids")

    for id in ids:
        cursor.execute("DELETE FROM history WHERE id=?", (id,))

    conn.commit()
    return redirect(url_for('view_history'))

# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
