from flask import Flask, render_template, request, redirect, url_for, session
import joblib
import re
import string
from datetime import datetime
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText

# ✅ FIXED (no wrong folder name)
app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ----------------
conn = sqlite3.connect('history.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    date TEXT
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
    return render_template("Homepage.html", email=session['email'])

# ---------------- SEND OTP EMAIL ----------------
def send_otp_email(receiver_email, otp):
    sender_email = "emailspamdetection555@gmail.com"   # ⚠️ replace if needed
    app_password = "phzj cwtn oqqe pgqo"               # ⚠️ replace app password

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
        print("OTP sent ✅")
    except Exception as e:
        print("Email Error:", e)

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        try:
            cursor.execute("INSERT INTO users (email,password) VALUES (?,?)", (email, password))
            conn.commit()
            return redirect("/login")
        except:
            return "Email already exists"

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['email'] = user[1]
            return redirect("/")
        else:
            return "Invalid Login"

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

            send_otp_email(email, otp)

            return redirect("/otp")
        else:
            return "Email not found"

    return render_template("forgot.html")

# ---------------- OTP ----------------
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

# ---------------- RESET PAGE ----------------
@app.route("/reset")
def reset():
    return render_template("resetpassword.html")

# ---------------- UPDATE PASSWORD ----------------
@app.route("/reset-password", methods=["POST"])
def reset_password():
    new_password = request.form['password']
    email = session.get("reset_email")

    cursor.execute("UPDATE users SET password=? WHERE email=?", (new_password, email))
    conn.commit()

    return redirect("/login")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

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
@app.route("/history")
def view_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM history WHERE user_id=? ORDER BY id DESC", (session['user_id'],))
    data = cursor.fetchall()

    history = []
    total = len(data)

    for i, row in enumerate(data):
        history.append({
            "id": total - i,
            "real_id": row[0],
            "email": row[2],
            "result": row[3],
            "date": row[4]
        })

    return render_template("history.html", history=history, from_search=False)

# ---------------- DELETE SINGLE ----------------
@app.route("/delete/<int:id>")
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("DELETE FROM history WHERE id=?", (id,))
    conn.commit()

    return redirect(url_for('view_history'))

# ---------------- CLEAR ALL ----------------
@app.route("/clear_history")
def clear_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("DELETE FROM history WHERE user_id=?", (session['user_id'],))
    conn.commit()

    return redirect(url_for('view_history'))

# ---------------- SEARCH ----------------
@app.route("/search", methods=["POST"])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    search_id = request.form.get("search_id")

    cursor.execute("SELECT * FROM history WHERE user_id=? ORDER BY id DESC", (session['user_id'],))
    data = cursor.fetchall()

    history = []
    total = len(data)

    for i, row in enumerate(data):
        display_id = total - i

        if str(display_id) == search_id:
            history.append({
                "id": display_id,
                "real_id": row[0],
                "email": row[2],
                "result": row[3],
                "date": row[4]
            })

    return render_template("history.html", history=history, from_search=True)

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
