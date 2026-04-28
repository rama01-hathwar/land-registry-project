from flask import Flask, jsonify, request, render_template, send_file, session, redirect
import psycopg2
import os
import qrcode
from io import BytesIO
import joblib
import pandas as pd

app = Flask(__name__)
app.secret_key = "supersecretkey"

# DB
def get_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ---------------- GIS ----------------
@app.route('/api/land')
def get_land():
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM gis_land_data")
        rows = cursor.fetchall()

        data = []
        for r in rows:
            data.append({
                "parcel_id": r[0],   # land_id
                "owner": r[3],       # village (temporary)
                "type": r[4],        # taluk (temporary)
                "area": 1000,        # dummy (you don’t have area column)
                "lat": r[7],         # latitude
                "lon": 77.59         # dummy longitude (you don’t have it)
            })

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- FRAUD ----------------
@app.route('/fraud_check/<parcel_id>')
def fraud_check(parcel_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT duplicate_survey, multiple_claim, abnormal_transfer
            FROM fraud_detection
            WHERE parcel_id=%s
        """, (parcel_id,))

        result = cursor.fetchone()

        if not result:
            return jsonify({"parcel_id": parcel_id, "risk_level": "Unknown"})

        score = sum(result)
        risk = "Low" if score == 0 else "Medium" if score == 1 else "High"

        return jsonify({"parcel_id": parcel_id, "risk_level": risk})

    except Exception as e:
        return jsonify({"error": str(e)})

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

# ---------------- TAX ----------------
@app.route('/tax/<parcel_id>')
def tax(parcel_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT amount, status FROM tax WHERE parcel_id=%s", (parcel_id,))
        row = cursor.fetchone()

        return jsonify({"amount": row[0], "status": row[1]}) if row else jsonify({"amount": 0, "status": "No Data"})

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- MORTGAGE ----------------
@app.route('/mortgage/<parcel_id>')
def mortgage(parcel_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT bank_name, amount, status FROM mortgage WHERE parcel_id=%s", (parcel_id,))
        row = cursor.fetchone()

        return jsonify({
            "bank": row[0],
            "amount": row[1],
            "status": row[2]
        }) if row else jsonify({"status": "No Mortgage"})

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- DISPUTE ----------------
@app.route('/dispute/<parcel_id>')
def dispute(parcel_id):
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT dispute_type, status FROM dispute WHERE parcel_id=%s LIMIT 1
        """, (parcel_id,))

        row = cursor.fetchone()

        return jsonify({"issue": row[0], "status": row[1]}) if row else jsonify({"status": "No dispute"})

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- LOGS ----------------
@app.route('/get_login_activity')
def logs():
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, action_type FROM login_activity")
        rows = cursor.fetchall()

        return jsonify([{"user_id": r[0], "action_type": r[1]} for r in rows])

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- BLOCKCHAIN ----------------
@app.route('/get_blockchain')
def blockchain():
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT block_number, confirmation_status FROM blockchain")
        rows = cursor.fetchall()

        return jsonify([{"block_number": r[0], "confirmation_status": r[1]} for r in rows])

    except Exception as e:
        return jsonify({"error": str(e)})

#--------------login------------------#
@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.json

        session["role"] = data.get("role")
        session["user"] = data.get("username")

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
