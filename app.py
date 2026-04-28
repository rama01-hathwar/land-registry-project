from flask import Flask, jsonify, request, render_template, send_file,session, redirect
import psycopg2
import os
import json
import hashlib
import datetime
import random
import qrcode
from io import BytesIO



app = Flask(__name__)
app.secret_key = "supersecretkey"


# ---------------- DB CONNECTION ----------------
def get_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')

#----------------------------------------------------
def require_role(roles):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                return jsonify({"error": "Unauthorized"}), 403
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# ---------------- BASIC ROUTES ----------------
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ---------------- GIS ----------------
@app.route('/api/land')
@require_role(["admin","bank","registrar","landowner","verifier"])
def get_land():
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM gis_land_data")
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "parcel_id": row[0],
                "owner": row[2],
                "type": row[3],
                "area": row[4],
                "lat": row[5],
                "lon": row[6]
            })

        conn.close()
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- FRAUD ----------------
@app.route('/fraud_check/<parcel_id>')
# @require_role(["admin"])
def fraud_check(parcel_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT duplicate_survey, multiple_claim, abnormal_transfer
        FROM fraud_detection
        WHERE parcel_id = %s
    """, (parcel_id,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return jsonify({"parcel_id": parcel_id, "risk_level": "Unknown"})

    score = sum(result)

    if score == 0:
        risk = "Low"
    elif score == 1:
        risk = "Medium"
    else:
        risk = "High"

    return jsonify({
        "parcel_id": parcel_id,
        "risk_level": risk
    })

# ---------------- TRANSFER ----------------
@app.route('/transfer_property', methods=['POST'])
@require_role(["registrar","admin"])
def transfer_property():
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    parcel_id = data['parcel_id']
    seller = data['seller_id']
    buyer = data['buyer_id']

    # Check owner
    cursor.execute("SELECT owner_id FROM property WHERE parcel_id=%s", (parcel_id,))
    owner = cursor.fetchone()

    if not owner or owner[0] != seller:
        return jsonify({"error": "Invalid seller"})

    # Update owner
    cursor.execute("UPDATE property SET owner_id=%s WHERE parcel_id=%s", (buyer, parcel_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "Transfer successful"})

# ---------------- HISTORY ----------------
@app.route('/owner_history/<parcel_id>')
def owner_history(parcel_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT from_owner, to_owner, transfer_date
            FROM ownership_history
            WHERE parcel_id=%s
        """, (parcel_id,))

        rows = cursor.fetchall()

        return jsonify([
            {"from": r[0], "to": r[1], "date": str(r[2])}
            for r in rows
        ])

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- DOCUMENTS ----------------
@app.route('/documents/<parcel_id>')
def documents(parcel_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT document_id, document_type, verification_status
        FROM document
        WHERE parcel_id=%s
    """, (parcel_id,))

    docs = cursor.fetchall()
    conn.close()

    result = []
    for d in docs:
        result.append({
            "id": d[0],
            "type": d[1],
            "status": d[2]
        })

    return jsonify(result)

# ---------------- TAX ----------------
@app.route('/tax/<parcel_id>')
def tax(parcel_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT amount, status
            FROM tax
            WHERE parcel_id=%s
        """, (parcel_id,))

        row = cursor.fetchone()

        if row:
            return jsonify({"amount": row[0], "status": row[1]})
        else:
            return jsonify({"amount": 0, "status": "No Data"})

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- MORTGAGE ----------------
@app.route('/mortgage/<parcel_id>')
def mortgage(parcel_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT bank_name, amount, status
            FROM mortgage
            WHERE parcel_id=%s
        """, (parcel_id,))

        row = cursor.fetchone()

        if row:
            return jsonify({
                "bank": row[0],
                "amount": row[1],
                "status": row[2]
            })
        else:
            return jsonify({"status": "No Mortgage"})

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- DISPUTE ----------------
@app.route('/dispute/<parcel_id>')
def dispute(parcel_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT dispute_type, status
        FROM dispute
        WHERE parcel_id=%s
        LIMIT 1
    """, (parcel_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "No dispute"})

    return jsonify({
        "issue": row[0],
        "status": row[1]
    })

# ---------------- LOGS ----------------
@app.route('/get_login_activity')
def logs():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id, action_type FROM login_activity")
    rows = cursor.fetchall()

    conn.close()

    return jsonify([
        {"user_id": r[0], "action_type": r[1]} for r in rows
    ])

# ---------------- BLOCKCHAIN ----------------
@app.route('/get_blockchain')
def blockchain():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT block_number, confirmation_status FROM blockchain")
    rows = cursor.fetchall()

    conn.close()

    return jsonify([
        {"block_number": r[0], "confirmation_status": r[1]} for r in rows
    ])

# ---------------- QR ----------------
@app.route('/qr/<parcel_id>')
def qr(parcel_id):
    url = f"https://land-registry-project.onrender.com/verify/{parcel_id}"

    img = qrcode.make(url)
    buffer = BytesIO()
    img.save(buffer)
    buffer.seek(0)

    return send_file(buffer, mimetype='image/png')

# ---------------- ML ----------------
import joblib
import pandas as pd

model = joblib.load("land_price_model.pkl")
cols = joblib.load("model_columns.pkl")

@app.route('/predict_price', methods=['POST'])
def predict():
    data = request.json

    df = pd.DataFrame([data])
    df = pd.get_dummies(df)

    for c in cols:
        if c not in df:
            df[c] = 0

    df = df[cols]

    pred = model.predict(df)

    return jsonify({"predicted_price": float(pred[0])})

@app.route("/login", methods=["POST"])
def login():
    data = request.json

    session["role"] = data.get("role")
    session["user"] = data.get("username")

    return jsonify({"message": "success"})



# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
