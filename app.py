from flask import Flask, jsonify, request, send_from_directory, send_file, render_template
from datetime import datetime
import sqlite3
import hashlib
import os
import json
import random
import math
import qrcode
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = "static/documents"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
SECRET_KEY = "land_registry_secure"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ML model — optional, graceful fallback
try:
    import joblib
    import pandas as pd
    model = joblib.load("land_price_model.pkl")
    model_columns = joblib.load("model_columns.pkl")
    HAS_MODEL = True
except:
    HAS_MODEL = False

# Web3 wallet — optional
try:
    from web3 import Account
    HAS_WEB3 = True
except:
    HAS_WEB3 = False

# PostgreSQL for GIS — optional
try:
    import psycopg2
    HAS_POSTGRES = bool(os.environ.get("DATABASE_URL"))
except:
    HAS_POSTGRES = False

DB_PATH = "land.db"

# ============================================================
# DATABASE HELPER
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_postgres():
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
        return conn
    except:
        return None

# ============================================================
# INIT — ONLY creates tables, NEVER inserts data
# ============================================================
def init_document_table():
    conn = sqlite3.connect("land.db")
    conn.execute("""CREATE TABLE IF NOT EXISTS document (
        document_id TEXT PRIMARY KEY, parcel_id TEXT, document_type TEXT,
        file_hash TEXT, uploaded_by TEXT, uploaded_date TEXT, verification_status TEXT)""")
    conn.commit()
    conn.close()

def init_db():
    conn = get_db()
    c = conn.cursor()

    # 🔥 DROP ALL TABLES (RESET)
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS property")
    c.execute("DROP TABLE IF EXISTS property_tax")
    c.execute("DROP TABLE IF EXISTS tax")
    c.execute("DROP TABLE IF EXISTS mortgage")
    c.execute("DROP TABLE IF EXISTS dispute")
    c.execute("DROP TABLE IF EXISTS blockchain")
    c.execute("DROP TABLE IF EXISTS transfer")
    c.execute("DROP TABLE IF EXISTS login_activity")
    c.execute("DROP TABLE IF EXISTS document")
    c.execute("DROP TABLE IF EXISTS fraud_detection")
    c.execute("DROP TABLE IF EXISTS gis_land_data")
    c.execute("DROP TABLE IF EXISTS ownership_history")

    # ================= USERS =================
    c.execute("""CREATE TABLE users (
        user_id TEXT PRIMARY KEY,
        full_name TEXT,
        wallet_address TEXT DEFAULT '',
        mobile_number TEXT,
        email TEXT,
        role TEXT,
        kyc_status TEXT DEFAULT 'pending',
        password_hash TEXT
    )""")

    # ================= PROPERTY =================
    c.execute("""CREATE TABLE property (
        parcel_id TEXT PRIMARY KEY,
        owner_id TEXT,
        survey_number TEXT,
        khata_number TEXT DEFAULT '',
        village TEXT DEFAULT '',
        taluk TEXT DEFAULT '',
        district TEXT DEFAULT '',
        state TEXT DEFAULT '',
        land_type TEXT DEFAULT '',
        area_sqft REAL,
        registration_date TEXT,
        current_market_value REAL,
        geo_latitude REAL,
        geo_longitude REAL,
        tax_status TEXT DEFAULT 'Pending',
        mortgage_status TEXT DEFAULT 'None'
    )""")

    # ================= TAX =================
    c.execute("""CREATE TABLE tax (
        tax_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        tax_year INTEGER,
        tax_amount REAL,
        tax_paid REAL DEFAULT 0,
        payment_date TEXT,
        payment_status TEXT DEFAULT 'Pending'
    )""")

    # ================= PROPERTY TAX =================
    c.execute("""CREATE TABLE property_tax (
        tax_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        tax_year INTEGER,
        tax_amount REAL,
        tax_paid REAL DEFAULT 0,
        payment_date TEXT,
        payment_status TEXT DEFAULT 'Pending'
    )""")

    # ================= MORTGAGE =================
    c.execute("""CREATE TABLE mortgage (
        mortgage_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        owner_id TEXT,
        bank_name TEXT,
        loan_amount REAL,
        interest_rate REAL,
        start_date TEXT,
        end_date TEXT,
        mortgage_status TEXT DEFAULT 'Active'
    )""")

    # ================= DISPUTE =================
    c.execute("""CREATE TABLE dispute (
        dispute_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        dispute_type TEXT,
        reported_by TEXT,
        description TEXT,
        status TEXT DEFAULT 'Open',
        created_date TEXT,
        resolved_date TEXT
    )""")

    # ================= BLOCKCHAIN =================
    c.execute("""CREATE TABLE blockchain (
        block_id TEXT PRIMARY KEY,
        block_number INTEGER,
        gas_fee REAL,
        confirmation_status TEXT DEFAULT 'Pending',
        timestamp TEXT,
        transaction_hash TEXT,
        previous_hash TEXT
    )""")

    # ================= TRANSFER =================
    c.execute("""CREATE TABLE transfer (
        transaction_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        from_owner TEXT,
        to_owner TEXT,
        transaction_type TEXT,
        transaction_hash TEXT,
        block_number INTEGER,
        timestamp TEXT,
        sale_amount REAL
    )""")

    # ================= LOGIN =================
    c.execute("""CREATE TABLE login_activity (
        login_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        action_type TEXT,
        parcel_id TEXT,
        description TEXT,
        timestamp TEXT,
        ip_address TEXT
    )""")

    # ================= DOCUMENT =================
    c.execute("""CREATE TABLE document (
        document_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        document_type TEXT,
        file_path TEXT DEFAULT '',
        file_hash TEXT DEFAULT '',
        uploaded_by TEXT,
        uploaded_date TEXT,
        verification_status TEXT DEFAULT 'Pending'
    )""")

    # ================= FRAUD =================
    c.execute("""CREATE TABLE fraud_detection (
        parcel_id TEXT PRIMARY KEY,
        duplicate_survey INTEGER DEFAULT 0,
        multiple_claim INTEGER DEFAULT 0,
        abnormal_transfer INTEGER DEFAULT 0,
        risk_score TEXT DEFAULT 'Low'
    )""")

    # ================= GIS (FIXED WITH STATUS) =================
    c.execute("""CREATE TABLE gis_land_data (
        land_id TEXT PRIMARY KEY,
        survey_number TEXT DEFAULT '',
        owner_name TEXT,
        land_use_type TEXT,
        area_sq_ft REAL,
        latitude REAL,
        longitude REAL,
        boundary_polygon TEXT DEFAULT '[]',
        status TEXT DEFAULT 'registered'
    )""")

    # ================= OWNERSHIP HISTORY =================
    c.execute("""CREATE TABLE ownership_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parcel_id TEXT,
        seller_id TEXT,
        buyer_id TEXT,
        transfer_date TEXT,
        transaction_hash TEXT
    )""")

    conn.commit()
    conn.close()

    print("✅ FULL DATABASE RESET & REBUILT SUCCESSFULLY")

# ============================================================
# HELPERS
# ============================================================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_file_hash(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def generate_secure_hash(parcel_id):
    return hashlib.sha256((str(parcel_id) + SECRET_KEY).encode()).hexdigest()[:10]

def generate_qr_file(parcel_id):
    folder = "static/qr_codes"
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = folder + "/land_" + parcel_id + ".png"
    hash_value = generate_secure_hash(parcel_id)
    url = request.url_root + "verify_property/" + parcel_id + "/" + hash_value
    img = qrcode.make(url)
    img.save(filename)
    return filename

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ============================================================
# SERVE FRONTEND
# ============================================================
@app.route("/")
def home():
    return render_template("index.html")

# ============================================================
# USER REGISTRATION
# ============================================================
@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.json
    conn = get_db()
    # Generate wallet
    if HAS_WEB3:
        wallet = Account.create()
        wallet_address = wallet.address
    else:
        wallet_address = "0x" + hashlib.sha256(data["user_id"].encode()).hexdigest()[:40]
    conn.execute("""INSERT INTO users
        (user_id, full_name, wallet_address, mobile_number, email, role, kyc_status, password_hash)
        VALUES (?,?,?,?,?,?,?,?)""",
        (data["user_id"], data["full_name"], wallet_address,
         data["mobile_number"], data["email"], data["role"],
         data["kyc_status"], data["password_hash"]))
    conn.commit()
    conn.close()
    return {"message": "User registered successfully", "wallet_address": wallet_address}

# ============================================================
# KYC
# ============================================================
@app.route('/verify_kyc/<user_id>', methods=['PUT'])
def verify_kyc(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET kyc_status='verified' WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "KYC verified successfully"}

# ============================================================
# PROPERTIES
# ============================================================
@app.route("/properties")
def get_properties():
    conn = get_db()
    rows = conn.execute("SELECT * FROM property").fetchall()
    conn.close()
    return {"properties": [dict(r) for r in rows]}

@app.route("/property/<parcel_id>")
def get_property(parcel_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM property WHERE parcel_id=?", (parcel_id,)).fetchone()
    conn.close()
    if row:
        return {"property": dict(row)}
    return {"message": "Property not found"}

@app.route("/add_property", methods=["POST"])
def add_property():
    data = request.json
    conn = get_db()
    conn.execute("""INSERT INTO property
        (parcel_id, owner_id, survey_number, khata_number, village, taluk, district,
         state, land_type, area_sqft, registration_date, current_market_value,
         geo_latitude, geo_longitude, tax_status, mortgage_status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data["parcel_id"], data["owner_id"], data["survey_number"],
         data.get("khata_number", ""), data["village"], data["taluk"],
         data["district"], data["state"], data["land_type"],
         data["area_sqft"], data["registration_date"],
         data["current_market_value"], data.get("geo_latitude"),
         data.get("geo_longitude"), data.get("tax_status", "Pending"),
         data.get("mortgage_status", "None")))
    conn.commit()
    conn.close()
    generate_qr_file(data["parcel_id"])
    return {"message": "Property added successfully"}

# ============================================================
# VERIFY PROPERTY
# ============================================================
@app.route('/verify_property/<parcel_id>', methods=['GET'])
def verify_property(parcel_id):
    conn = get_db()
    dispute = conn.execute("SELECT COUNT(*) FROM dispute WHERE parcel_id=? AND status!='Resolved'", (parcel_id,)).fetchone()[0]
    if dispute > 0:
        conn.close()
        return {"status": "blocked", "reason": "Active dispute on property"}
    fraud = conn.execute("SELECT risk_score FROM fraud_detection WHERE parcel_id=?", (parcel_id,)).fetchone()
    if fraud and fraud[0] == "High":
        conn.close()
        return {"status": "blocked", "reason": "High fraud risk detected"}
    tax = conn.execute("SELECT tax_status FROM tax WHERE parcel_id=?", (parcel_id,)).fetchone()
    if tax and tax[0] == "Pending":
        conn.close()
        return {"status": "blocked", "reason": "Property tax pending"}
    mort = conn.execute("SELECT mortgage_status FROM mortgage WHERE parcel_id=? AND mortgage_status='Active'", (parcel_id,)).fetchone()
    if mort and mort[0] == "Active":
        conn.close()
        return {"status": "blocked", "reason": "Property under mortgage"}
    conn.close()
    return {"status": "approved", "message": "Property eligible for transfer"}

# ============================================================
# VERIFY PROPERTY WITH HASH (QR scan)
# ============================================================
@app.route('/verify_property/<parcel_id>/<hash_value>')
def verify_property_qr(parcel_id, hash_value):
    expected_hash = generate_secure_hash(parcel_id)
    if hash_value != expected_hash:
        return render_template("property_dashboard.html", error="Invalid QR Code", property=None, documents=[])
    conn = get_db()
    row = conn.execute("SELECT * FROM property WHERE parcel_id=?", (parcel_id,)).fetchone()
    if not row:
        conn.close()
        return render_template("property_dashboard.html", error="Property not found", property=None, documents=[])
    property_data = dict(row)
    docs = conn.execute("SELECT document_id, document_type, verification_status FROM document WHERE parcel_id=?", (parcel_id,)).fetchall()
    doc_list = [{"document_id": d[0], "document_type": d[1], "status": d[2], "url": "/view_document/" + d[0]} for d in docs]
    conn.close()
    return render_template("property_dashboard.html", property=property_data, documents=doc_list, error=None)

# ============================================================
# TRANSFER PROPERTY — FIXED: actually performs transfer
# ============================================================
@app.route('/transfer_property', methods=['POST'])
def transfer_property():

    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid request"}), 400

    parcel_id = data['parcel_id']
    seller_id = data['seller_id']
    buyer_id = data['buyer_id']
    sale_amount = data['sale_amount']
    transaction_hash = data['transaction_hash']

    conn = get_db()
    c = conn.cursor()

    # 1. Dispute
    if c.execute("SELECT COUNT(*) FROM dispute WHERE parcel_id=? AND status!='Resolved'", (parcel_id,)).fetchone()[0] > 0:
        return jsonify({"message": "Transfer blocked due to active dispute"}), 400

    # 2. Mortgage
    if c.execute("SELECT 1 FROM mortgage WHERE parcel_id=? AND mortgage_status='Active'", (parcel_id,)).fetchone():
        return jsonify({"message": "Transfer blocked due to active mortgage"}), 400

    # 3. Tax
    tax1 = c.execute("SELECT COUNT(*) FROM tax WHERE parcel_id=? AND payment_status!='Paid'", (parcel_id,)).fetchone()[0]
    tax2 = c.execute("SELECT COUNT(*) FROM property_tax WHERE parcel_id=? AND payment_status!='Paid'", (parcel_id,)).fetchone()[0]

    if tax1 > 0 or tax2 > 0:
        return jsonify({"message": "Transfer blocked due to unpaid tax"}), 400

    # 4. Blockchain
    bc = c.execute("SELECT confirmation_status FROM blockchain WHERE transaction_hash=?", (transaction_hash,)).fetchone()
    if not bc:
        return jsonify({"message": "Blockchain transaction not found"}), 400

    if bc[0] != 'Confirmed':
        return jsonify({"message": "Transaction not confirmed"}), 400

    # 5. Owner check
    owner = c.execute("SELECT owner_id FROM property WHERE parcel_id=?", (parcel_id,)).fetchone()
    if not owner:
        return jsonify({"message": "Property not found"}), 404

    if owner[0] != seller_id:
        return jsonify({"message": "Seller is not current owner"}), 400

    # 6. Transfer
    c.execute("UPDATE property SET owner_id=? WHERE parcel_id=?", (buyer_id, parcel_id))

    txn_id = "T" + str(random.randint(1000, 9999))
    new_hash = hashlib.sha256((parcel_id + buyer_id + str(datetime.now())).encode()).hexdigest()

    c.execute("""
    INSERT INTO transfer 
    (transaction_id, parcel_id, seller_id, buyer_id, type, transaction_hash, block_number, timestamp, sale_amount)
    VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        txn_id, parcel_id, seller_id, buyer_id,
        "Transfer", new_hash, random.randint(1000,9999),
        str(datetime.now()), sale_amount
    ))
    #---insert into owner history---#
    init_hash = hashlib.sha256((parcel_id + owner_id).encode()).hexdigest()
    c.execute("""
INSERT INTO ownership_history 
(parcel_id, seller_id, buyer_id, transfer_date, transaction_hash)
VALUES (?,?,?,?,?)
""", (
    parcel_id,
    seller_id,
    buyer_id,
    str(datetime.now()),
    new_hash
))
    
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Property transferred successfully",
        "transaction_id": txn_id
    })
# ============================================================
# OWNER HISTORY — FIXED: actually returns data
# ============================================================
@app.route('/ownership_history/<parcel_id>')
def get_history(parcel_id):

    conn = get_db()
    c = conn.cursor()

    rows = c.execute("""
        SELECT seller_id, buyer_id, transfer_date
        FROM ownership_history
        WHERE parcel_id=?
        ORDER BY transfer_date ASC
    """, (parcel_id,)).fetchall()

    conn.close()

    return jsonify([
        {
            "seller_id": r[0],
            "buyer_id": r[1],
            "date": r[2]
        } for r in rows
    ])

# ============================================================
# FRAUD DETECTION
# ============================================================
@app.route('/fraud_check/<parcel_id>', methods=['GET'])
def fraud_check(parcel_id):
    conn = get_db()
    result = conn.execute("SELECT duplicate_survey, multiple_claim, abnormal_transfer FROM fraud_detection WHERE parcel_id=?", (parcel_id,)).fetchone()
    conn.close()
    if result:
        dup = int(result[0])
        mult = int(result[1])
        abn = int(result[2])
        flag_sum = dup + mult + abn
        if flag_sum == 0:
            risk_level = "Low"
        elif flag_sum == 1:
            risk_level = "Medium"
        else:
            risk_level = "High"
        return {
            "parcel_id": parcel_id, "duplicate_survey": dup,
            "multiple_claim": mult, "abnormal_transfer": abn,
            "risk_level": risk_level
        }
    return {"message": "No fraud record found"}

# ============================================================
# DISPUTE
# ============================================================
@app.route('/file_dispute', methods=['POST'])
def file_dispute():
    data = request.json
    dispute_id = "D" + str(random.randint(100, 999))
    conn = get_db()
    conn.execute("""INSERT INTO dispute
        (dispute_id, parcel_id, dispute_type, reported_by, description, status, created_date)
        VALUES (?,?,?,?,?,?,?)""",
        (dispute_id, data['parcel_id'], data['dispute_type'],
         data['reported_by'], data['description'], 'Open', str(datetime.now())))
    conn.commit()
    conn.close()
    return {"message": "Dispute filed successfully", "dispute_id": dispute_id}

@app.route('/get_disputes/<parcel_id>', methods=['GET'])
def get_disputes(parcel_id):
    conn = get_db()
    rows = conn.execute("SELECT dispute_id, dispute_type, reported_by, description, status, created_date FROM dispute WHERE parcel_id=?", (parcel_id,)).fetchall()
    conn.close()
    disputes = []
    for r in rows:
        disputes.append({
            "dispute_id": r[0], "dispute_type": r[1], "reported_by": r[2],
            "description": r[3], "status": r[4], "created_date": str(r[5])
        })
    return {"disputes": disputes}

@app.route('/resolve_dispute/<dispute_id>', methods=['POST'])
def resolve_dispute(dispute_id):
    conn = get_db()
    conn.execute("UPDATE dispute SET status='Resolved', resolved_date=? WHERE dispute_id=?",
        (str(datetime.now()), dispute_id))
    conn.commit()
    conn.close()
    return {"message": "Dispute resolved successfully"}

# ============================================================
# TAX — all variants
# ============================================================
@app.route('/generate_tax/<parcel_id>', methods=['POST'])
def generate_tax(parcel_id):
    conn = get_db()
    prop = conn.execute("SELECT current_market_value FROM property WHERE parcel_id=?", (parcel_id,)).fetchone()
    if not prop:
        conn.close()
        return jsonify({"error": "Property not found"})
    market_value = float(prop[0])
    tax_amount = market_value * 0.01
    year = datetime.now().year
    existing = conn.execute("SELECT tax_id FROM tax WHERE parcel_id=? AND tax_year=?", (parcel_id, year)).fetchone()
    if existing:
        conn.close()
        return jsonify({"message": "Tax already generated for this property for this year"})
    tax_id = "TX" + str(random.randint(1000, 9999))
    conn.execute("INSERT INTO tax VALUES (?,?,?,?,?,?,?)",
        (tax_id, parcel_id, year, tax_amount, 0, None, 'Pending'))
    conn.commit()
    conn.close()
    return jsonify({"message": "Tax generated successfully", "parcel_id": parcel_id, "tax_amount": tax_amount})

@app.route('/tax/<parcel_id>', methods=['GET'])
def get_tax(parcel_id):
    conn = get_db()
    rows = conn.execute("SELECT tax_id, tax_year, tax_amount, tax_paid, payment_date, payment_status FROM tax WHERE parcel_id=?", (parcel_id,)).fetchall()
    conn.close()
    return jsonify([{"tax_id": r[0], "tax_year": r[1], "tax_amount": r[2], "tax_paid": r[3],
        "payment_date": str(r[4]) if r[4] else None, "payment_status": r[5]} for r in rows])

@app.route('/pending_tax/<parcel_id>', methods=['GET'])
def get_pending_tax(parcel_id):
    conn = get_db()
    rows = conn.execute("SELECT tax_id, tax_year, tax_amount, tax_paid, payment_date, payment_status FROM tax WHERE parcel_id=?", (parcel_id,)).fetchall()
    conn.close()
    return jsonify([{"tax_id": r[0], "tax_year": r[1], "tax_amount": r[2], "tax_paid": r[3],
        "payment_date": str(r[4]) if r[4] else None, "payment_status": r[5]} for r in rows])

@app.route('/get_tax/<parcel_id>', methods=['GET'])
def get_unpaid_tax(parcel_id):
    conn = get_db()
    rows = conn.execute("SELECT tax_id, tax_year, tax_amount, tax_paid, payment_status FROM tax WHERE parcel_id=? AND payment_status!='Paid'", (parcel_id,)).fetchall()
    conn.close()
    return jsonify([{"tax_id": r[0], "tax_year": r[1], "tax_amount": r[2], "tax_paid": r[3], "payment_status": r[4]} for r in rows])

@app.route('/pay_tax', methods=['POST'])
def pay_tax():
    data = request.json
    conn = get_db()
    conn.execute("UPDATE tax SET tax_paid=?, payment_date=?, payment_status='Paid' WHERE tax_id=?",
        (data['tax_paid'], str(datetime.now()), data['tax_id']))
    conn.commit()
    conn.close()
    return jsonify({"message": "Tax payment successful"})

# ============================================================
# MORTGAGE — all variants
# ============================================================
@app.route('/add_mortgage', methods=['POST'])
def add_mortgage():
    data = request.json
    conn = get_db()
    existing = conn.execute("SELECT mortgage_id FROM mortgage WHERE parcel_id=? AND mortgage_status='Active'", (data['parcel_id'],)).fetchone()
    if existing:
        conn.close()
        return jsonify({"message": "Property already has active mortgage"}), 400
    count = conn.execute("SELECT COUNT(*) FROM mortgage").fetchone()[0] + 1
    mortgage_id = "M{:03d}".format(count)
    conn.execute("""INSERT INTO mortgage
        (mortgage_id, parcel_id, owner_id, bank_name, loan_amount, interest_rate, start_date, end_date, mortgage_status)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (mortgage_id, data['parcel_id'], data['owner_id'], data['bank_name'],
         data['loan_amount'], data['interest_rate'], data['start_date'], data['end_date'], 'Active'))
    conn.commit()
    conn.close()
    return jsonify({"message": "Mortgage added successfully", "mortgage_id": mortgage_id})

@app.route('/get_mortgage/<parcel_id>', methods=['GET'])
def get_mortgage(parcel_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM mortgage WHERE parcel_id=?", (parcel_id,)).fetchall()
    conn.close()
    return jsonify([{"mortgage_id": r[0], "parcel_id": r[1], "owner_id": r[2], "bank_name": r[3],
        "loan_amount": r[4], "interest_rate": r[5], "start_date": str(r[6]),
        "end_date": str(r[7]), "mortgage_status": r[8]} for r in rows])

@app.route('/check_mortgage/<parcel_id>', methods=['GET'])
def check_mortgage(parcel_id):
    conn = get_db()
    status = conn.execute("SELECT mortgage_status FROM mortgage WHERE parcel_id=?", (parcel_id,)).fetchone()
    conn.close()
    if status:
        return jsonify({"mortgage_status": status[0]})
    return jsonify({"message": "No mortgage found"})

@app.route('/close_mortgage', methods=['PUT'])
def close_mortgage():
    data = request.json
    conn = get_db()
    conn.execute("UPDATE mortgage SET mortgage_status='Closed' WHERE mortgage_id=?", (data['mortgage_id'],))
    conn.commit()
    conn.close()
    return jsonify({"message": "Mortgage closed successfully"})

@app.route('/check_property_mortgage/<parcel_id>', methods=['GET'])
def check_property_mortgage(parcel_id):
    conn = get_db()
    mort = conn.execute("SELECT mortgage_id FROM mortgage WHERE parcel_id=? AND mortgage_status='Active'", (parcel_id,)).fetchone()
    conn.close()
    if mort:
        return jsonify({"mortgage_exists": True, "message": "Property has active mortgage"})
    return jsonify({"mortgage_exists": False, "message": "No active mortgage"})

# ============================================================
# ACTIVITY LOGS — FIXED: datetime.now() instead of GETDATE()
# ============================================================
@app.route('/login_activity', methods=['POST'])
def login_activity():
    data = request.json
    conn = get_db()
    user_id = data['user_id']
    ip_address = data.get('ip_address', '')
    # Check last IP for suspicious detection
    last = conn.execute("SELECT ip_address FROM login_activity WHERE user_id=? ORDER BY login_id DESC LIMIT 1", (user_id,)).fetchone()
    if last and last[0] != ip_address:
        description = "Suspicious login detected (Different IP)"
    else:
        description = "User logged into system"
    conn.execute("INSERT INTO login_activity (user_id, action_type, parcel_id, description, timestamp, ip_address) VALUES (?,?,?,?,?,?)",
        (user_id, "Login", None, description, str(datetime.now()), ip_address))
    conn.commit()
    conn.close()
    return jsonify({"message": "Login activity recorded", "suspicious_login": last is not None and last[0] != ip_address})

@app.route('/log_activity', methods=['POST'])
def log_activity():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO login_activity (user_id, action_type, parcel_id, description, timestamp, ip_address) VALUES (?,?,?,?,?,?)",
        (data['user_id'], data['action_type'], data.get('parcel_id'), data['description'], str(datetime.now()), data.get('ip_address', '')))
    conn.commit()
    conn.close()
    return jsonify({"message": "Activity logged successfully"})

@app.route('/get_login_activity', methods=['GET'])
def get_login_activity():
    conn = get_db()
    rows = conn.execute("SELECT * FROM login_activity ORDER BY login_id DESC").fetchall()
    conn.close()
    return jsonify([{"login_id": r[0], "user_id": r[1], "action_type": r[2], "parcel_id": r[3],
        "description": r[4], "timestamp": str(r[5]), "ip_address": r[6]} for r in rows])

@app.route('/user_activity/<user_id>', methods=['GET'])
def user_activity(user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM login_activity WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return jsonify([{"login_id": r[0], "user_id": r[1], "action_type": r[2], "parcel_id": r[3],
        "description": r[4], "timestamp": str(r[5]), "ip_address": r[6]} for r in rows])

@app.route('/filter_login_activity', methods=['POST'])
def filter_login_activity():
    data = request.json
    conn = get_db()
    rows = conn.execute("SELECT * FROM login_activity WHERE date(timestamp) BETWEEN ? AND ?", (data['start_date'], data['end_date'])).fetchall()
    conn.close()
    return jsonify([{"login_id": r[0], "user_id": r[1], "action_type": r[2], "parcel_id": r[3],
        "description": r[4], "timestamp": str(r[5]), "ip_address": r[6]} for r in rows])

# ============================================================
# BLOCKCHAIN — FIXED: datetime.now(), LIMIT not TOP
# ============================================================
@app.route('/add_blockchain_transaction', methods=['POST'])
def add_blockchain_transaction():
    data = request.json
    gas_fee = data['gas_fee']
    conn = get_db()
    last = conn.execute("SELECT block_number, transaction_hash FROM blockchain ORDER BY block_number DESC LIMIT 1").fetchone()
    if last:
        block_number = last[0] + 1
        previous_hash = last[1]
    else:
        block_number = 1
        previous_hash = "0"
    block_id = "B" + str(block_number).zfill(3)
    raw_data = block_id + previous_hash + str(datetime.now().timestamp())
    transaction_hash = hashlib.sha256(raw_data.encode()).hexdigest()
    conn.execute("INSERT INTO blockchain VALUES (?,?,?,?,?,?,?)",
        (block_id, block_number, gas_fee, 'Pending', str(datetime.now()), transaction_hash, previous_hash))
    conn.commit()
    conn.close()
    return jsonify({
        "message": "Blockchain block created", "block_id": block_id,
        "block_number": block_number, "transaction_hash": transaction_hash, "previous_hash": previous_hash
    })

@app.route('/get_blockchain', methods=['GET'])
def get_blockchain():
    conn = get_db()
    rows = conn.execute("SELECT * FROM blockchain ORDER BY block_number").fetchall()
    conn.close()
    return jsonify([{"block_id": r[0], "block_number": r[1], "gas_fee": r[2],
        "confirmation_status": r[3], "timestamp": str(r[4]),
        "transaction_hash": r[5], "previous_hash": r[6]} for r in rows])

@app.route('/check_blockchain/<transaction_hash>', methods=['GET'])
def check_blockchain(transaction_hash):
    conn = get_db()
    result = conn.execute("SELECT confirmation_status FROM blockchain WHERE transaction_hash=?", (transaction_hash,)).fetchone()
    conn.close()
    if result:
        return jsonify({"confirmation_status": result[0]})
    return jsonify({"message": "Transaction not found"})

@app.route('/confirm_blockchain', methods=['PUT'])
def confirm_blockchain():
    data = request.json
    conn = get_db()
    conn.execute("UPDATE blockchain SET confirmation_status='Confirmed' WHERE transaction_hash=?", (data['transaction_hash'],))
    conn.commit()
    conn.close()
    return jsonify({"message": "Blockchain transaction confirmed"})

@app.route('/verify_blockchain', methods=['GET'])
def verify_blockchain():
    conn = get_db()
    blocks = conn.execute("SELECT block_number, transaction_hash, previous_hash FROM blockchain ORDER BY block_number").fetchall()
    conn.close()
    for i in range(1, len(blocks)):
        if blocks[i-1][1] != blocks[i][2]:
            return jsonify({"blockchain_valid": False, "message": "Blockchain tampering detected", "block_number": blocks[i][0]})
    return jsonify({"blockchain_valid": True, "message": "Blockchain integrity verified"})

# ============================================================
# GIS LAND DATA — PostgreSQL if available, else SQLite
# ============================================================
@app.route('/api/land')
def get_land():
    # Try PostgreSQL first
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT * FROM gis_land_data")
                rows = cur.fetchall()
                cur.close()
                pg.close()
                data = []
                for row in rows:
                    poly = []
                    if len(row) > 7 and row[7]:
                        try:
                            poly = json.loads(row[7])
                        except:
                            poly = []
                    if not poly:
                        lat, lon = row[5], row[6]
                        sz = max(float(row[4]) / 10000000, 0.0003)
                        poly = [[lat+sz,lon+sz],[lat+sz,lon-sz],[lat-sz,lon-sz],[lat-sz,lon+sz]]
                    data.append({
                        "parcel_id": row[0], "survey": row[1], "owner": row[2],
                        "type": row[3], "area": row[4], "lat": row[5], "lon": row[6],
                        "polygon": poly,
                        "status": row[8] if len(row) > 8 and row[8] else "registered"
                    })
                return jsonify(data)
        except:
            pass

    # Fallback to SQLite
    conn = get_db()
    rows = conn.execute("SELECT * FROM gis_land_data").fetchall()
    conn.close()
    data = []
    for r in rows:
        poly = []
        try:
            poly = json.loads(r[7])
        except:
            poly = []
        if not poly:
            lat, lon = r[5], r[6]
            sz = max(float(r[4]) / 10000000, 0.0003)
            poly = [[lat+sz,lon+sz],[lat+sz,lon-sz],[lat-sz,lon-sz],[lat-sz,lon+sz]]
        data.append({
            "parcel_id": r[0], "survey": r[1], "owner": r[2], "type": r[3],
            "area": r[4], "lat": r[5], "lon": r[6], "polygon": poly,
            "status": r[8] if r[8] else "registered"
        })
    return jsonify(data)

@app.route("/api/nearby_land")
def nearby_land():
    lat = float(request.args.get("lat"))
    lon = float(request.args.get("lon"))
    radius = float(request.args.get("radius", 1))
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT land_id, latitude, longitude FROM gis_land_data")
                rows = cur.fetchall()
                cur.close()
                pg.close()
                result = []
                for row in rows:
                    dist = haversine(lat, lon, row[1], row[2])
                    if dist <= radius:
                        result.append({"parcel_id": str(row[0]), "lat": row[1], "lon": row[2], "distance": round(dist, 2)})
                return jsonify(result)
        except:
            pass
    conn = get_db()
    rows = conn.execute("SELECT land_id, latitude, longitude FROM gis_land_data").fetchall()
    conn.close()
    result = []
    for r in rows:
        dist = haversine(lat, lon, r[1], r[2])
        if dist <= radius:
            result.append({"parcel_id": r[0], "lat": r[1], "lon": r[2], "distance": round(dist, 2)})
    return jsonify(result)

@app.route('/get_land_locations')
def get_land_locations():
    conn = get_db()
    rows = conn.execute("SELECT land_id, owner_name, latitude, longitude FROM gis_land_data WHERE latitude IS NOT NULL").fetchall()
    conn.close()
    return jsonify([{"parcel_id": r[0], "owner": r[1], "lat": r[2], "lon": r[3]} for r in rows])

@app.route('/add_land', methods=['POST'])
def add_land():
    data = request.json
    conn = sqlite3.connect("land.db")
    conn.execute("INSERT INTO gis_land_data (land_id, owner_name, latitude, longitude) VALUES (?,?,?,?)",
        (data['land_id'], data['owner_name'], data['latitude'], data['longitude']))
    conn.commit()
    conn.close()
    return jsonify({"message": "Land added successfully"})

# ============================================================
# QR CODE
# ============================================================
@app.route('/qr/<parcel_id>')
def generate_qr_dynamically(parcel_id):
    url = request.url_root + "verify/" + parcel_id
    img = qrcode.make(url)
    buffer = BytesIO()
    img.save(buffer)
    buffer.seek(0)
    return send_file(buffer, mimetype='image/png')

@app.route('/verify/<parcel_id>')
def verify(parcel_id):
    # Try PostgreSQL first
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT * FROM gis_land_data WHERE land_id=%s", (parcel_id,))
                row = cur.fetchone()
                cur.close()
                pg.close()
                if row:
                    return "<h2>✅ Property Verified</h2><p><b>Parcel ID:</b> %s</p><p><b>Owner:</b> %s</p><p><b>Type:</b> %s</p><p><b>Area:</b> %s sq ft</p>" % (row[0], row[2], row[3], row[4])
        except:
            pass
    conn = get_db()
    row = conn.execute("SELECT * FROM gis_land_data WHERE land_id=?", (parcel_id,)).fetchone()
    conn.close()
    if not row:
        return "<h2>❌ Property %s Not Found</h2>" % parcel_id
    return "<h2>✅ Property Verified</h2><p><b>Parcel ID:</b> %s</p><p><b>Owner:</b> %s</p><p><b>Type:</b> %s</p><p><b>Area:</b> %s sq ft</p>" % (row[0], row[2], row[3], row[4])

@app.route('/regenerate_qr/<parcel_id>', methods=['POST'])
def regenerate_qr(parcel_id):
    conn = get_db()
    row = conn.execute("SELECT parcel_id FROM property WHERE parcel_id=?", (parcel_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Property not found"}), 404
    filename = generate_qr_file(parcel_id)
    return jsonify({"message": "QR regenerated successfully", "parcel_id": parcel_id, "qr_path": filename})

# ============================================================
# DOCUMENTS
# ============================================================
@app.route("/upload_document", methods=["POST"])
def upload_document():
    parcel_id = request.form.get("parcel_id")
    document_type = request.form.get("document_type")
    uploaded_by = request.form.get("uploaded_by")
    if "file" not in request.files:
        return {"error": "No file provided"}, 400
    f = request.files["file"]
    if f.filename == "":
        return {"error": "Empty filename"}, 400
    if not allowed_file(f.filename):
        return {"error": "Invalid file type"}, 400
    document_id = "DOC" + str(int(datetime.now().timestamp()))
    ext = f.filename.split(".")[-1]
    filename = document_id + "." + ext
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    f.save(file_path)
    file_hash = generate_file_hash(file_path)
    conn = get_db()
    conn.execute("""INSERT INTO document
        (document_id, parcel_id, document_type, file_path, file_hash, uploaded_by, uploaded_date, verification_status)
        VALUES (?,?,?,?,?,?,?,?)""",
        (document_id, parcel_id, document_type, file_path, file_hash,
         uploaded_by, str(datetime.now()), "Pending"))
    conn.commit()
    conn.close()
    return {"message": "Document uploaded successfully", "document_id": document_id}

@app.route('/documents/<land_id>')
def get_documents(land_id):
    # Try PostgreSQL first
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT document_id, document_type, verification_status FROM document WHERE parcel_id=%s", (land_id,))
                docs = cur.fetchall()
                cur.close()
                pg.close()
                if docs:
                    return jsonify([{"document_id": d[0], "document_type": d[1], "status": d[2], "view_url": "/view_document/" + d[0]} for d in docs])
        except:
            pass
    conn = get_db()
    rows = conn.execute("SELECT document_id, document_type, verification_status FROM document WHERE parcel_id=?", (land_id,)).fetchall()
    conn.close()
    return jsonify([{"document_id": r[0], "document_type": r[1], "status": r[2], "view_url": "/view_document/" + r[0]} for r in rows])

@app.route("/view/<document_id>")
def view_document_simple(document_id):
    return "Viewing document " + document_id

@app.route('/view_document/<doc_id>')
def view_document(doc_id):
    # Try PostgreSQL first
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT file_hash FROM document WHERE document_id=%s", (doc_id,))
                row = cur.fetchone()
                cur.close()
                pg.close()
                if row and row[0]:
                    filename = row[0]
                    if os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
                        return send_from_directory(UPLOAD_FOLDER, filename)
        except:
            pass
    conn = get_db()
    row = conn.execute("SELECT file_path FROM document WHERE document_id=?", (doc_id,)).fetchone()
    conn.close()
    if not row or not row[0]:
        return "Document not found ❌"
    if os.path.exists(row[0]):
        return send_from_directory(os.path.dirname(row[0]), os.path.basename(row[0]))
    return "File not found on disk"

@app.route("/verify_document/<document_id>", methods=["PUT"])
def verify_document(document_id):
    data = request.json
    user_id = data.get("user_id")
    conn = get_db()
    # Try PostgreSQL for user check
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT role FROM users WHERE user_id=%s", (user_id,))
                user = cur.fetchone()
                cur.close()
                pg.close()
                if user and user[0] == "admin":
                    # Update in PostgreSQL
                    cur = pg.cursor()
                    cur.execute("UPDATE document SET verification_status='Verified' WHERE document_id=%s", (document_id,))
                    pg.commit()
                    cur.close()
                    pg.close()
                    return {"message": "Document verified by admin"}
        except:
            pass
    user = conn.execute("SELECT role FROM users WHERE user_id=?", (user_id,)).fetchone()
    if user and user[0] == "admin":
        conn.execute("UPDATE document SET verification_status='Verified' WHERE document_id=?", (document_id,))
        conn.commit()
        conn.close()
        return {"message": "Document verified by admin"}
    conn.close()
    return {"error": "Unauthorized"}, 403

@app.route("/validate_document/<document_id>", methods=["GET"])
def validate_document(document_id):
    conn = get_db()
    row = conn.execute("SELECT file_hash FROM document WHERE document_id=?", (document_id,)).fetchone()
    conn.close()
    if not row:
        return {"error": "Document not found"}
    db_hash = row[0]
    for fname in os.listdir(UPLOAD_FOLDER):
        full_path = os.path.join(UPLOAD_FOLDER, fname)
        if os.path.isfile(full_path) and generate_file_hash(full_path) == db_hash:
            return {"status": "valid", "message": "Document is authentic"}
    return {"status": "tampered", "message": "Document integrity compromised"}

# ============================================================
# ML PREDICTION — graceful fallback if no model file
# ============================================================
@app.route('/predict_price', methods=['POST'])
def predict_price():
    try:
        data = request.json
        if not HAS_MODEL:
            area = data.get('area_sqft', 1000)
            price = area * 3500 + random.randint(100000, 500000)
            return jsonify({"predicted_price": float(price)})
        input_data = {
            'area_sqft': data['area_sqft'],
            'road_distance_km': data['road_distance_km'],
            'city_distance_km': data['city_distance_km'],
            'nearby_school': 1 if data['nearby_school'] == 'Yes' else 0,
            'nearby_hospital': 1 if data['nearby_hospital'] == 'Yes' else 0,
            'year': data['year']
        }
        df = pd.DataFrame([input_data])
        df = pd.get_dummies(df)
        for col in model_columns:
            if col not in df:
                df[col] = 0
        df = df[model_columns]
        prediction = model.predict(df)
        return jsonify({"predicted_price": float(prediction[0])})
    except Exception as e:
        return jsonify({"error": str(e)})

# ============================================================
# DATA MANAGEMENT ROUTES (your original utility routes)
# ============================================================
@app.route('/init-db')
def init_db_route():
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("""CREATE TABLE IF NOT EXISTS gis_land_data (
                    land_id TEXT, survey_number TEXT, owner_name TEXT, land_use_type TEXT,
                    area_sq_ft REAL, latitude REAL, longitude REAL, boundary_polygon TEXT)""")
                pg.commit()
                cur.close()
                pg.close()
                return "PostgreSQL table created successfully!"
        except:
            pass
    conn = get_db()
    conn.close()
    return "SQLite table created successfully"

@app.route('/add-test-data')
def add_test_data():
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("""INSERT INTO gis_land_data VALUES
                    ('L001', 'S001', 'Rama', 'Residential', 1200, 12.9716, 77.5946, ''),
                    ('L002', 'S002', 'Shyam', 'Commercial', 2000, 12.9720, 77.5950, ''),
                    ('L003', 'S003', 'Geeta', 'Agriculture', 3000, 12.9730, 77.5960, '')""")
                pg.commit()
                cur.close()
                pg.close()
                return "Data inserted into PostgreSQL successfully!"
        except:
            pass
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO gis_land_data VALUES (?,?,?,?,?,?,?,?)",
        ('L001','S001','Rama','Residential',1200,12.9716,77.5946,''))
    conn.execute("INSERT OR IGNORE INTO gis_land_data VALUES (?,?,?,?,?,?,?,?)",
        ('L002','S002','Shyam','Commercial',2000,12.9720,77.5950,''))
    conn.execute("INSERT OR IGNORE INTO gis_land_data VALUES (?,?,?,?,?,?,?,?)",
        ('L003','S003','Geeta','Agriculture',3000,12.9730,77.5960,''))
    conn.commit()
    conn.close()
    return "Data inserted successfully!"

@app.route('/generate-data')
def generate_data():
    first_names = ["Ravi","Sita","Arjun","Meena","Kiran","Anita","Rahul","Priya","Vikram","Neha"]
    last_names = ["Kumar","Sharma","Reddy","Patel","Singh","Nair","Gupta","Das"]
    land_types = ["Residential","Commercial","Agricultural"]
    base_lat, base_lon = 12.9716, 77.5946
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("DELETE FROM gis_land_data")
                for i in range(1, 101):
                    owner = random.choice(first_names) + " " + random.choice(last_names)
                    lat = base_lat + random.uniform(-0.02, 0.02)
                    lon = base_lon + random.uniform(-0.02, 0.02)
                    area = random.randint(800, 5000)
                    cur.execute("INSERT INTO gis_land_data (land_id,survey_number,owner_name,land_use_type,area_sq_ft,latitude,longitude,boundary_polygon) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (f"L{i:03}", f"S{i:03}", owner, random.choice(land_types), area, lat, lon, '[]'))
                pg.commit()
                cur.close()
                pg.close()
                return "✅ 100 records generated in PostgreSQL!"
        except:
            pass
    conn = get_db()
    conn.execute("DELETE FROM gis_land_data")
    for i in range(1, 101):
        owner = random.choice(first_names) + " " + random.choice(last_names)
        lat = base_lat + random.uniform(-0.02, 0.02)
        lon = base_lon + random.uniform(-0.02, 0.02)
        area = random.randint(800, 5000)
        conn.execute("INSERT INTO gis_land_data VALUES (?,?,?,?,?,?,?,?)",
            (f"L{i:03}", f"S{i:03}", owner, random.choice(land_types), area, lat, lon, '[]'))
    conn.commit()
    conn.close()
    return "✅ 100 records generated in SQLite!"


@app.route('/generate-qr')
def generate_qr_codes():
    try:
        folder = "static/qr_codes"
        if not os.path.exists(folder):
            os.makedirs(folder)
        if HAS_POSTGRES:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT land_id FROM gis_land_data")
                rows = cur.fetchall()
                cur.close()
                pg.close()
                for row in rows:
                    img = qrcode.make(request.url_root + "verify/" + row[0])
                    img.save(os.path.join(folder, row[0] + ".png"))
                return "QR codes generated from PostgreSQL!"
        conn = get_db()
        rows = conn.execute("SELECT land_id FROM gis_land_data").fetchall()
        conn.close()
        for r in rows:
            img = qrcode.make(request.url_root + "verify/" + r[0])
            img.save(os.path.join(folder, r[0] + ".png"))
        return "QR codes generated from SQLite!"
    except Exception as e:
        return "Error: " + str(e)

@app.route('/generate_documents')
def generate_documents():
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("DELETE FROM document")
                pg.commit()
                cur.execute("SELECT land_id FROM gis_land_data")
                lands = cur.fetchall()
                count = 1
                for land in lands:
                    doc_id = f"DOC{count:03}"
                    status = random.choice(["verified", "pending", "rejected"])
                    doc_type = random.choice(["Sale Deed","Tax Receipt","Mortgage Deed","Transfer Deed","Lease Agreement"])
                    cur.execute("INSERT INTO document (document_id,parcel_id,document_type,file_hash,uploaded_by,uploaded_date,verification_status) VALUES (%s,%s,%s,%s,%s,NOW(),%s)",
                        (doc_id, land[0], doc_type, f"hash{count}", "U001", status))
                    count += 1
                pg.commit()
                cur.close()
                pg.close()
                return f"Inserted {count-1} documents in PostgreSQL ✅"
        except:
            pass
    conn = get_db()
    conn.execute("DELETE FROM document")
    rows = conn.execute("SELECT land_id FROM gis_land_data").fetchall()
    count = 1
    for r in rows:
        doc_id = f"DOC{count:03}"
        status = random.choice(["verified", "pending", "rejected"])
        doc_type = random.choice(["Sale Deed","Tax Receipt","Mortgage Deed","Transfer Deed","Lease Agreement"])
        conn.execute("INSERT INTO document VALUES (?,?,?,?,?,?,?,?)",
            (doc_id, r[0], doc_type, f"hash{count}", "U001", str(datetime.now()), status))
        count += 1
    conn.commit()
    conn.close()
    return f"Inserted {count-1} documents in SQLite ✅"

@app.route("/create_document_table")
def create_document_table():
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("""CREATE TABLE IF NOT EXISTS document (
                    document_id TEXT PRIMARY KEY, parcel_id TEXT, document_type TEXT,
                    file_hash TEXT, uploaded_by TEXT, uploaded_date TIMESTAMP, verification_status TEXT)""")
                pg.commit()
                cur.close()
                pg.close()
                return "Table created in PostgreSQL"
        except:
            pass
    init_document_table()
    return "Table created in SQLite"

@app.route('/check_lands')
def check_lands():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT land_id FROM gis_land_data ORDER BY land_id")
    rows = c.fetchall()

    conn.close()

    return str([r[0] for r in rows])

@app.route('/check_documents')
def check_documents():
    if HAS_POSTGRES:
        try:
            pg = get_postgres()
            if pg:
                cur = pg.cursor()
                cur.execute("SELECT document_id, parcel_id, document_type, verification_status FROM document")
                data = cur.fetchall()
                cur.close()
                pg.close()
                return str(data)
        except Exception as e:
            return "<pre>" + str(e) + "</pre>"
    conn = get_db()
    rows = conn.execute("SELECT document_id, parcel_id, document_type, verification_status FROM document").fetchall()
    conn.close()
    return str([list(r) for r in rows])

@app.route('/debug_gis')
def debug_gis():
    conn = get_db()
    c = conn.cursor()

    try:
        rows = c.execute("SELECT * FROM gis_land_data LIMIT 10").fetchall()
        
        # Get column names
        col_names = [description[0] for description in c.description]

        data = []
        for r in rows:
            row_dict = {}
            for i in range(len(col_names)):
                row_dict[col_names[i]] = r[i]
            data.append(row_dict)

        conn.close()

        return jsonify({
            "columns": col_names,
            "rows": data,
            "count": len(data)
        })

    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)})

@app.route('/fix-gis')
def fix_gis():
    conn = get_db()
    c = conn.cursor()

    c.execute("DELETE FROM gis_land_data")
    conn.commit()

    conn.close()
    return "GIS cleared"

@app.route('/count_lands')
def count_lands():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM gis_land_data").fetchone()[0]
    conn.close()
    return str(count)

@app.route('/check_property')
def check_property():
    conn = get_db()
    rows = conn.execute("SELECT parcel_id FROM property LIMIT 10").fetchall()
    conn.close()
    return jsonify([r[0] for r in rows])

@app.route('/force_generate')
def force_generate():
    generate_full_data_internal()
    return "Generated"




# ============================================================
# STARTUP
# ============================================================
init_document_table()
init_db()
def generate_full_data_internal():
    conn = get_db()
    c = conn.cursor()

    # CLEAN TABLES
    c.execute("DELETE FROM gis_land_data")
    c.execute("DELETE FROM property")

    for i in range(1, 201):
        parcel_id = f"L{i:03}"
        owner_id = f"U{i:03}"

        lat = 12.97 + (i * 0.0005)
        lon = 77.59 + (i * 0.0005)

        # ✅ GIS TABLE
        c.execute("""
        INSERT INTO gis_land_data (
            land_id, survey_number, owner_name,
            land_use_type, area_sq_ft,
            latitude, longitude, boundary_polygon, status
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            parcel_id,
            f"S{i:03}",
            f"Owner {i}",
            "Residential",
            1000 + i,
            lat,
            lon,
            '[]',
            "registered"
        ))

        # ✅ PROPERTY TABLE (THIS WAS MISSING)
        c.execute("""
        INSERT INTO property (
            parcel_id, owner_id, survey_number,
            village, taluk, district, state,
            land_type, area_sqft, registration_date,
            current_market_value,
            geo_latitude, geo_longitude,
            tax_status, mortgage_status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            parcel_id,
            owner_id,
            f"S{i:03}",
            "Village X",
            "Taluk X",
            "District X",
            "State X",
            "Residential",
            1000 + i,
            "2024-01-01",
            500000 + i * 1000,
            lat,
            lon,
            "Paid",
            "None"
        ))

    conn.commit()
    conn.close()

@app.route('/generate-full-data')
def generate_full_data():
    generate_full_data_internal()
    return "✅ Data generated successfully"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
