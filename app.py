from flask import Flask,jsonify
from flask import request
from datetime import datetime
import qrcode
import os
import psycopg2
import os
import hashlib
from flask import Flask, jsonify, render_template, request
import math
import json
import sqlite3
import joblib
import pandas as pd
from werkzeug.utils import secure_filename

def init_document_table():
    import sqlite3

    conn = sqlite3.connect("land.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS document (
        document_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        document_type TEXT,
        file_hash TEXT,
        uploaded_by TEXT,
        uploaded_date TEXT,
        verification_status TEXT
    );
    """)

    conn.commit()
    conn.close()

model = joblib.load("land_price_model.pkl")
model_columns = joblib.load("model_columns.pkl")
app = Flask(__name__)
UPLOAD_FOLDER = "static/documents"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

SECRET_KEY = "land_registry_secure"

def generate_secure_hash(parcel_id):
    dataset = str(parcel_id) + SECRET_KEY
    return hashlib.sha256(dataset.encode()).hexdigest()[:10]


def generate_qr(parcel_id):

    folder = "static/qr_codes"

    if not os.path.exists(folder):
        os.makedirs(folder)

    filename = f"{folder}/land_{parcel_id}.png"

    # create secure link
    hash_value = generate_secure_hash(parcel_id)

    url = f"http://127.0.0.1:5000/verify_property/{parcel_id}/{hash_value}"

    qr = qrcode.make(url)
    qr.save(filename)

    return filename

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

#user registration#
@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.json

    user_id = data["user_id"]
    full_name = data["full_name"]
    mobile_number = data["mobile_number"]
    email = data["email"]
    role = data["role"]
    kyc_status = data["kyc_status"]
    password_hash = data["password_hash"]

    # generate wallet automatically
    wallet = Account.create()
    wallet_address = wallet.address

    cursor.execute("""
        INSERT INTO users
        (user_id, full_name, wallet_address, mobile_number, email, role, kyc_status, password_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, full_name, wallet_address, mobile_number, email, role, kyc_status, password_hash))

    conn.commit()

    return {
        "message": "User registered successfully",
        "wallet_address": wallet_address
    }

#--kyc verification--#
@app.route('/verify_kyc/<user_id>', methods=['PUT'])
def verify_kyc(user_id):

    cursor.execute("""
    UPDATE users
    SET kyc_status = 'verified'
    WHERE user_id = ?
    """, (user_id))

    conn.commit()

    return {"message": "KYC verified successfully"}

# get all properties
@app.route("/properties")
def get_properties():

    cursor.execute("SELECT * FROM property")
    rows = cursor.fetchall()

    data = []

    for row in rows:
        data.append(str(row))

    return {"properties": data}


# get one property
@app.route("/property/<parcel_id>")
def get_property(parcel_id):

    cursor.execute(
        
        "SELECT * FROM property WHERE parcel_id = ?",
        (parcel_id,)
    )

    row = cursor.fetchone()

    if row:
        return {"property": str(row)}
    else:
        return {"message": "Property not found"}
    
# Register a new property
@app.route("/add_property", methods=["POST"])
def add_property():

    data = request.json

    parcel_id = data["parcel_id"]
    owner_id = data["owner_id"]
    survey_number = data["survey_number"]
    khata_number = data["khata_number"]
    village = data["village"]
    taluk = data["taluk"]
    district = data["district"]
    state = data["state"]
    land_type = data["land_type"]
    area_sqft = data["area_sqft"]
    registration_date = data["registration_date"]
    current_market_value = data["current_market_value"]
    geo_latitude = data.get("geo_latitude")
    geo_longitude = data.get("geo_longitude")
    tax_status = data["tax_status"]
    mortgage_status = data["mortgage_status"]

    cursor.execute("""
        INSERT INTO property
        (parcel_id, owner_id, survey_number, khata_number, village, taluk, district,
         state, land_type, area_sqft, registration_date, current_market_value,
         geo_latitude, geo_longitude, tax_status, mortgage_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        parcel_id, owner_id, survey_number, khata_number, village, taluk, district,
        state, land_type, area_sqft, registration_date, current_market_value,
        geo_latitude, geo_longitude, tax_status, mortgage_status
    ))

    conn.commit()
    #---generate QR code for this property---#
    generate_qr(parcel_id)
    
    return {"message": "Property added successfully"}


#--verify_property--#
@app.route('/verify_property/<parcel_id>', methods=['GET'])
def verify_property(parcel_id):

    # Check dispute
    cursor.execute("""
        SELECT * FROM dispute
        WHERE parcel_id = ? AND status != 'Resolved'
    """, (parcel_id,))
    
    dispute = cursor.fetchone()

    if dispute:
        return {
            "status": "blocked",
            "reason": "Active dispute on property"
        }

    # Check fraud
    cursor.execute("""
        SELECT risk_score FROM fraud_detection
        WHERE parcel_id = ?
    """, (parcel_id,))
    
    fraud = cursor.fetchone()

    if fraud and fraud[0] == "High":
        return {
            "status": "blocked",
            "reason": "High fraud risk detected"
        }

    # Check tax
    cursor.execute("""
        SELECT tax_status FROM tax
        WHERE parcel_id = ?
    """, (parcel_id,))
    
    tax = cursor.fetchone()

    if tax and tax[0] == "Pending":
        return {
            "status": "blocked",
            "reason": "Property tax pending"
        }

    # Check mortgage
    cursor.execute("""
        SELECT status FROM mortgage
        WHERE parcel_id = ? AND mortgage_status='Active'
    """, (parcel_id,))
    
    mortgage = cursor.fetchone()

    if mortgage and mortgage[0] == "Active":
        return {
            "status": "blocked",
            "reason": "Property under mortgage"
        }

    return {
        "status": "approved",
        "message": "Property eligible for transfer"
    }
    

#--transaction--#
import hashlib
import datetime
import random

@app.route('/transfer_property', methods=['POST'])
def transfer_property():

    data = request.json

    parcel_id = data['parcel_id']
    seller_id = data['seller_id']
    buyer_id = data['buyer_id']
    sale_amount = data['sale_amount']
    transaction_hash=data['transaction_hash']

    # --------------------------------
    # BLOCK TRANSFER IF DISPUTE EXISTS
    # --------------------------------
    cursor.execute("""
        SELECT COUNT(*) FROM dispute
        WHERE parcel_id = ? AND status != 'Resolved'
    """, (parcel_id,))

    dispute_count = cursor.fetchone()[0]

    if dispute_count > 0:
        return jsonify({
            "message": "Transfer blocked due to active dispute"
        })
    #-----Block tranfer if mortgage exist----#
    cursor.execute("""
    SELECT mortgage_status
    FROM mortgage
    WHERE parcel_id = ? AND mortgage_status = 'Active'
""", (parcel_id,))

    mortgage = cursor.fetchone()

    if mortgage:
      return jsonify({
        "message": "Transfer blocked due to active mortgage"
    }), 400
    # --------------------------------
    # CHECK TAX
    # --------------------------------
    cursor.execute("""
        SELECT * FROM property_tax
        WHERE parcel_id = ? AND payment_status != 'Paid'
    """, (parcel_id,))

    tax = cursor.fetchone()

    if tax:
        return jsonify({
            "error": "Transfer blocked due to unpaid tax"
        })
    # 4 Check blockchain confirmation
    cursor.execute("""
    SELECT confirmation_status
    FROM blockchain
    WHERE transaction_hash = ?
    """, (transaction_hash,))

    blockchain = cursor.fetchone()

    if not blockchain:
        return jsonify({
            "message": "Blockchain transaction not found"
        })

    if blockchain[0] != 'Confirmed':
        return jsonify({
            "message": "Transfer blocked: Blockchain transaction not confirmed"
        })


    return jsonify({
        "message": "All checks passed. Transfer can proceed"
    })
    
    # --------------------------------
# Check the seller is the current owner
# --------------------------------

    cursor.execute("""
        SELECT owner_id FROM property
        WHERE parcel_id = ?
    """, (parcel_id,))

    owner = cursor.fetchone()

    if not owner:
       return jsonify({"error": "Property not found"})

    if owner[0] != seller_id:
       return jsonify({"error": "Seller is not the current owner"}) 

    # -----------------------------------
    # 2. GET PREVIOUS TRANSACTION HASH
    # -----------------------------------

    cursor.execute("""
        SELECT TOP 1 transaction_hash
        FROM transfer
        WHERE parcel_id = ?
        ORDER BY timestamp DESC
    """, (parcel_id,))

    result = cursor.fetchone()

    if result:
        previous_hash = result[0]
    else:
        previous_hash = "GENESIS"

    # -----------------------------------
    # 3. GENERATE BLOCKCHAIN HASH
    # -----------------------------------

    transaction_string = parcel_id + seller_id + buyer_id + previous_hash + str(datetime.datetime.now())

    transaction_hash = hashlib.sha256(transaction_string.encode()).hexdigest()

    # -----------------------------------
    # 4. GENERATE TRANSACTION ID
    # -----------------------------------

    transaction_id = "T" + str(random.randint(1000, 9999))

    block_number = random.randint(120000, 130000)

    timestamp = datetime.datetime.now()

    # -----------------------------------
    # 5. UPDATE PROPERTY OWNER
    # -----------------------------------

    cursor.execute("""
        UPDATE property
        SET owner_id = ?
        WHERE parcel_id = ?
    """, (buyer_id, parcel_id))

    # -----------------------------------
    # 6. INSERT TRANSACTION RECORD
    # -----------------------------------

    cursor.execute("""
        INSERT INTO transfer
        (transaction_id, parcel_id, from_owner, to_owner, transaction_type,
        transaction_hash, block_number, timestamp, sale_amount)

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (transaction_id, parcel_id, seller_id, buyer_id, "Transfer",
     transaction_hash, block_number, timestamp, sale_amount))

    conn.commit()

    return {
        "message": "Property transferred successfully",
        "transaction_id": transaction_id,
        "transaction_hash": transaction_hash
    }

#--Owner History---#
@app.route('/owner_history/<parcel_id>', methods=['GET'])
def owner_history(parcel_id):

    cursor.execute("""
    SELECT 
        transaction_id,
        parcel_id,
        from_owner,
        to_owner,
        transaction_type,
        sale_amount,
        timestamp
    FROM [transfer]
    WHERE parcel_id = ?
    ORDER BY timestamp ASC
    """, (parcel_id,))

    rows = cursor.fetchall()

    history = []

    for row in rows:
        history.append({
            "transaction_id": row[0],
            "parcel_id": row[1],
            "previous_owner": row[2],
            "new_owner": row[3],
            "transaction_type": row[4],
            "sale_amount": row[5],
            "timestamp": str(row[6])
        })
        
 #--Fraud Detection--#
@app.route('/fraud_check/<parcel_id>', methods=['GET'])
def fraud_check(parcel_id):

    cursor.execute("""
    SELECT duplicate_survey, multiple_claim, abnormal_transfer
    FROM fraud_detection
    WHERE parcel_id = ?
    """, (parcel_id,))

    result = cursor.fetchone()

    if result:

        duplicate_flag = int(result[0])
        multiple_flag = int(result[1])
        abnormal_flag = int(result[2])

        flag_sum = duplicate_flag + multiple_flag + abnormal_flag

        if flag_sum == 0:
            risk_level = "Low"
        elif flag_sum == 1:
            risk_level = "Medium"
        else:
            risk_level = "High"

        return {
            "parcel_id": parcel_id,
            "duplicate_survey": duplicate_flag,
            "multiple_claim": multiple_flag,
            "abnormal_transfer": abnormal_flag,
            "risk_level": risk_level
        }

    else:
        return {"message": "No fraud record found"}
    
    #--File Dispue--#
import random

dispute_id = "D" + str(random.randint(100,999))

#--Dispute---#
import random
import datetime

@app.route('/file_dispute', methods=['POST'])
def file_dispute():

    data = request.json

    parcel_id = data['parcel_id']
    dispute_type = data['dispute_type']
    reported_by = data['reported_by']
    description = data['description']

    # generate dispute id--#
    dispute_id = "D" + str(random.randint(100,999))

    status = "Open"
    created_date = datetime.datetime.now()

    cursor.execute("""
        INSERT INTO dispute
        (dispute_id, parcel_id, dispute_type, reported_by, description, status,
         created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (dispute_id, parcel_id, dispute_type, reported_by, description, status,
    created_date))

    conn.commit()

    return {
        "message": "Dispute filed successfully",
        "dispute_id": dispute_id
        }
#--GET DISPUTE HISTORY--#
@app.route('/get_disputes/<parcel_id>',
           methods=['GET'])
def get_disputes(parcel_id):

    cursor.execute("""
    SELECT dispute_id, dispute_type, reported_by, description, status, created_date
    FROM dispute
    WHERE parcel_id = ?
    """, (parcel_id,))

    rows = cursor.fetchall()

    disputes = []

    for row in rows:
        disputes.append({
            "dispute_id": row[0],
            "dispute_type": row[1],
            "reported_by": row[2],
            "description": row[3],
            "status": row[4],
            "created_date": str(row[5])
        })

    return {"disputes": disputes}

#--resolve dispute--#
@app.route('/resolve_dispute/<dispute_id>', methods=['POST'])
def resolve_dispute(dispute_id):

    cursor.execute("""
    UPDATE dispute
    SET status = 'Resolved',
        resolved_date = GETDATE()
    WHERE dispute_id = ?
    """, (dispute_id,))

    conn.commit()

    return {"message": "Dispute resolved successfully"}

#--Generate Tax Automatically--#
from datetime import datetime
import random

@app.route('/generate_tax/<parcel_id>', methods=['POST'])
def generate_tax(parcel_id):

    cursor = conn.cursor()

    # 1️⃣ Get market value of the property
    cursor.execute(
        "SELECT current_market_value FROM property WHERE parcel_id = ?",
        (parcel_id,)
    )

    property_data = cursor.fetchone()

    if not property_data:
        return jsonify({"error": "Property not found"})

    market_value = float(property_data[0])

    # 2️⃣ Calculate tax (1%)
    tax_amount = market_value * 0.01

    # 3️⃣ Get current year
    year = datetime.now().year

    # 4️⃣ Check if tax already exists for this property and year
    cursor.execute("""
        SELECT tax_id
        FROM tax
        WHERE parcel_id = ? AND tax_year = ?
    """, (parcel_id, year))

    existing_tax = cursor.fetchone()

    if existing_tax:
        return jsonify({
            "message": "Tax already generated for this property for this year"
        })

    # 5️⃣ Generate tax id
    tax_id = "TX" + str(random.randint(1000, 9999))

    # 6️⃣ Insert new tax record
    cursor.execute("""
        INSERT INTO tax
        (tax_id, parcel_id, tax_year, tax_amount, tax_paid, payment_date, payment_status)
        VALUES (?, ?, ?, ?, 0, NULL, 'Pending')
    """, (tax_id, parcel_id, year, tax_amount))

    conn.commit()

    # 7️⃣ Return response
    return jsonify({
        "message": "Tax generated successfully",
        "parcel_id": parcel_id,
        "tax_amount": tax_amount
    })

#--Get tax details---#
@app.route('/tax/<parcel_id>', methods=['GET'])
def get_tax(parcel_id):

    cursor = conn.cursor()

    cursor.execute("""
        SELECT tax_id, tax_year, tax_amount, tax_paid, payment_date, payment_status
        FROM tax
        WHERE parcel_id = ?
    """, (parcel_id,))

    tax = cursor.fetchall()

    results = []

    for row in tax:
        results.append({
            "tax_id": row[0],
            "tax_year": row[1],
            "tax_amount": row[2],
            "tax_paid": row[3],
            "payment_date": str(row[4]),
            "payment_status": row[5]
        })

    return jsonify(results)

#---Check pending tax---#
@app.route('/pending_tax/<parcel_id>', methods=['GET'])
def get_pending_tax(parcel_id):

    cursor = conn.cursor()

    cursor.execute("""
        SELECT tax_id, tax_year, tax_amount, tax_paid, payment_date, payment_status
        FROM tax
        WHERE parcel_id = ?
    """, (parcel_id,))

    tax = cursor.fetchall()

    results = []

    for row in tax:
        results.append({
            "tax_id": row[0],
            "tax_year": row[1],
            "tax_amount": row[2],
            "tax_paid": row[3],
            "payment_date": str(row[4]),
            "payment_status": row[5]
        })

    return jsonify(results)

#----Pay tax---#
@app.route('/pay_tax', methods=['POST'])
def pay_tax():

    data = request.json

    tax_id = data['tax_id']
    tax_paid = data['tax_paid']

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tax
        SET tax_paid = ?, payment_date = ?, payment_status = 'Paid'
        WHERE tax_id = ?
    """, (tax_paid, datetime.now(), tax_id))

    conn.commit()

    return jsonify({
        "message": "Tax payment successful"
    })

#----Get pending tax---#
@app.route('/get_tax/<parcel_id>', methods=['GET'])
def pending_tax(parcel_id):

    cursor = conn.cursor()

    cursor.execute("""
        SELECT tax_id, tax_year, tax_amount, tax_paid, payment_status
        FROM tax
        WHERE parcel_id = ?
        AND payment_status != 'Paid'
    """, (parcel_id,))

    tax = cursor.fetchall()

    results = []

    for row in tax:
        results.append({
            "tax_id": row[0],
            "tax_year": row[1],
            "tax_amount": row[2],
            "tax_paid": row[3],
            "payment_status": row[4]
        })

    return jsonify(results)
#---Mortgage---#

# ---------------------------------
# 1 Add Mortgage
# ---------------------------------

@app.route('/add_mortgage', methods=['POST'])
def add_mortgage():

    data = request.json

    parcel_id = data['parcel_id']
    owner_id = data['owner_id']
    bank_name = data['bank_name']
    loan_amount = data['loan_amount']
    interest_rate = data['interest_rate']
    start_date = data['start_date']
    end_date = data['end_date']

    cursor = conn.cursor()

    # Check if property already has active mortgage
    cursor.execute("""
    SELECT mortgage_id
    FROM mortgage
    WHERE parcel_id = ? AND mortgage_status = 'Active'
    """, (parcel_id,))

    existing = cursor.fetchone()

    if existing:
        return jsonify({
            "message": "Property already has active mortgage"
        }),400

    # Generate mortgage id
    cursor.execute("SELECT COUNT(*) FROM mortgage")
    count = cursor.fetchone()[0] + 1
    mortgage_id = f"M{count:03}"

    cursor.execute("""
    INSERT INTO mortgage
    (mortgage_id, parcel_id, owner_id, bank_name, loan_amount,
    interest_rate, start_date, end_date, mortgage_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, (mortgage_id, parcel_id, owner_id, bank_name,
          loan_amount, interest_rate, start_date, end_date))

    conn.commit()

    return jsonify({
        "message":"Mortgage added successfully",
        "mortgage_id":mortgage_id
    })


# ---------------------------------
# 2 Get Mortgage Details
# ---------------------------------

@app.route('/get_mortgage/<parcel_id>', methods=['GET'])
def get_mortgage(parcel_id):

    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM mortgage
    WHERE parcel_id = ?
    """, (parcel_id,))

    rows = cursor.fetchall()

    result = []

    for row in rows:
        result.append({
            "mortgage_id":row[0],
            "parcel_id":row[1],
            "owner_id":row[2],
            "bank_name":row[3],
            "loan_amount":row[4],
            "interest_rate":row[5],
            "start_date":str(row[6]),
            "end_date":str(row[7]),
            "mortgage_status":row[8]
        })

    return jsonify(result)


# ---------------------------------
# 3 Check Mortgage Status
# ---------------------------------

@app.route('/check_mortgage/<parcel_id>', methods=['GET'])
def check_mortgage(parcel_id):

    cursor = conn.cursor()

    cursor.execute("""
    SELECT mortgage_status
    FROM mortgage
    WHERE parcel_id = ?
    """, (parcel_id,))

    status = cursor.fetchone()

    if status:
        return jsonify({
            "mortgage_status":status[0]
        })

    return jsonify({
        "message":"No mortgage found"
    })


# ---------------------------------
# 4 Close Mortgage
# ---------------------------------

@app.route('/close_mortgage', methods=['PUT'])
def close_mortgage():

    data = request.json
    mortgage_id = data['mortgage_id']

    cursor = conn.cursor()

    cursor.execute("""
    UPDATE mortgage
    SET mortgage_status = 'Closed'
    WHERE mortgage_id = ?
    """, (mortgage_id,))

    conn.commit()

    return jsonify({
        "message":"Mortgage closed successfully"
    })


# ---------------------------------
# 5 Check Property Mortgage
# ---------------------------------

@app.route('/check_property_mortgage/<parcel_id>', methods=['GET'])
def check_property_mortgage(parcel_id):

    cursor = conn.cursor()

    cursor.execute("""
    SELECT mortgage_id
    FROM mortgage
    WHERE parcel_id = ? AND mortgage_status = 'Active'
    """, (parcel_id,))

    mortgage = cursor.fetchone()

    if mortgage:
        return jsonify({
            "mortgage_exists":True,
            "message":"Property has active mortgage"
        })

    return jsonify({
        "mortgage_exists":False,
        "message":"No active mortgage"
    })

#----Login Activity---#
@app.route('/login_activity', methods=['POST'])
def login_activity():

    data = request.json

    user_id = data['user_id']
    action_type = "Login"
    parcel_id = None
    description = "User logged into system"
    ip_address = data['ip_address']

    cursor = conn.cursor()

    # Get last login IP
    cursor.execute("""
    SELECT TOP 1 ip_address
    FROM login_activity
    WHERE user_id = ?
    ORDER BY timestamp DESC
    """, (user_id,))

    last_login = cursor.fetchone()

    suspicious = False

    if last_login:
        last_ip = last_login[0]

        if last_ip != ip_address:
            suspicious = True
            description = "Suspicious login detected (Different IP)"

    # Insert login activity
    cursor.execute("""
    INSERT INTO login_activity
    (user_id, action_type, parcel_id, description, timestamp, ip_address)
    VALUES (?, ?, ?, ?, GETDATE(), ?)
    """, (user_id, action_type, parcel_id, description, ip_address))

    conn.commit()

    return jsonify({
        "message": "Login activity recorded",
        "suspicious_login": suspicious
    })

#------Record Login Activity---#
@app.route('/log_activity', methods=['POST'])
def log_activity():

    data = request.json

    user_id = data['user_id']
    action_type = data['action_type']
    parcel_id = data.get('parcel_id')
    description = data['description']
    ip_address = data['ip_address']

    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO login_activity
    (user_id, action_type, parcel_id, description, timestamp, ip_address)
    VALUES (?, ?, ?, ?, GETDATE(), ?)
    """, (user_id, action_type, parcel_id, description, ip_address))

    conn.commit()

    return jsonify({
        "message": "Activity logged successfully"
    })

#---Get All Login Activity----#
@app.route('/get_login_activity', methods=['GET'])
def get_login_activity():

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM login_activity")

    rows = cursor.fetchall()

    result = []

    for row in rows:
        result.append({
            "login_id": row[0],
            "user_id": row[1],
            "action_type": row[2],
            "parcel_id": row[3],
            "description": row[4],
            "timestamp": str(row[5]),
            "ip_address": row[6]
        })

    return jsonify(result)

#---Get Activity By User--#
@app.route('/user_activity/<user_id>', methods=['GET'])
def user_activity(user_id):

    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM login_activity
    WHERE user_id = ?
    """, (user_id,))

    rows = cursor.fetchall()

    result = []

    for row in rows:
        result.append({
            "login_id": row[0],
            "user_id": row[1],
            "action_type": row[2],
            "parcel_id": row[3],
            "description": row[4],
            "timestamp": str(row[5]),
            "ip_address": row[6]
        })

    return jsonify(result)

#---Login Activity Filter By Dates---#
@app.route('/filter_login_activity', methods=['POST'])
def filter_login_activity():

    data = request.json

    start_date = data['start_date']
    end_date = data['end_date']

    cursor = conn.cursor()

    cursor.execute("""
        SELECT * 
        FROM login_activity
        WHERE CAST(timestamp AS DATE) BETWEEN ? AND ?
    """, (start_date, end_date))

    rows = cursor.fetchall()

    result = []

    for row in rows:
        result.append({
            "login_id": row[0],
            "user_id": row[1],
            "action_type": row[2],
            "parcel_id": row[3],
            "description": row[4],
            "timestamp": str(row[5]),
            "ip_address": row[6]
        })

    return jsonify(result)

#--Add Blockchain Transaction---#
import hashlib
import time

@app.route('/add_blockchain_transaction', methods=['POST'])
def add_blockchain_transaction():

    data = request.json
    gas_fee = data['gas_fee']

    cursor = conn.cursor()

    # Get last block
    cursor.execute("""
    SELECT TOP 1 block_number, transaction_hash
    FROM blockchain
    ORDER BY block_number DESC
    """)

    last_block = cursor.fetchone()

    if last_block:
        block_number = last_block[0] + 1
        previous_hash = last_block[1]
    else:
        block_number = 1
        previous_hash = "0"

    # Generate block id
    block_id = "B" + str(block_number).zfill(3)

    # Generate transaction hash
    raw_data = block_id + previous_hash + str(time.time())
    transaction_hash = hashlib.sha256(raw_data.encode()).hexdigest()

    confirmation_status = "Pending"

    cursor.execute("""
    INSERT INTO blockchain
    (block_id, block_number, gas_fee, confirmation_status, timestamp, transaction_hash, previous_hash)
    VALUES (?, ?, ?, ?, GETDATE(), ?, ?)
    """, (block_id, block_number, gas_fee, confirmation_status, transaction_hash, previous_hash))

    conn.commit()

    return jsonify({
        "message": "Blockchain block created",
        "block_id": block_id,
        "block_number": block_number,
        "transaction_hash": transaction_hash,
        "previous_hash": previous_hash
    })

#--Get All Blockchain Records---#
@app.route('/get_blockchain', methods=['GET'])
def get_blockchain():

    cursor = conn.cursor()

    cursor.execute("SELECT * FROM blockchain")

    rows = cursor.fetchall()

    result = []

    for row in rows:
        result.append({
            "block_id": row[0],
            "block_number": row[1],
            "gas_fee": row[2],
            "confirmation_status": row[3],
            "timestamp": str(row[4]),
            "transaction_hash": row[5]
        })

    return jsonify(result)

#----Check Transaction Status---#
@app.route('/check_blockchain/<transaction_hash>', methods=['GET'])
def check_blockchain(transaction_hash):

    cursor = conn.cursor()

    cursor.execute("""
    SELECT confirmation_status
    FROM blockchain
    WHERE transaction_hash = ?
    """, (transaction_hash,))

    result = cursor.fetchone()

    if result:
        return jsonify({
            "confirmation_status": result[0]
        })

    return jsonify({
        "message": "Transaction not found"
    })

#--Update Blockchain Confirmation--#
@app.route('/confirm_blockchain', methods=['PUT'])
def confirm_blockchain():

    data = request.json
    transaction_hash = data['transaction_hash']

    cursor = conn.cursor()

    cursor.execute("""
    UPDATE blockchain
    SET confirmation_status = 'Confirmed'
    WHERE transaction_hash = ?
    """, (transaction_hash,))

    conn.commit()

    return jsonify({
        "message": "Blockchain transaction confirmed"
    })

#--Blockchain Integrity Checks---#
@app.route('/verify_blockchain', methods=['GET'])
def verify_blockchain():

    cursor = conn.cursor()

    cursor.execute("""
    SELECT block_number, transaction_hash, previous_hash
    FROM blockchain
    ORDER BY block_number
    """)

    blocks = cursor.fetchall()

    for i in range(1, len(blocks)):

        previous_block = blocks[i-1]
        current_block = blocks[i]

        previous_hash = previous_block[1]
        stored_previous_hash = current_block[2]

        if previous_hash != stored_previous_hash:
            return jsonify({
                "blockchain_valid": False,
                "message": "Blockchain tampering detected",
                "block_number": current_block[0]
            })

    return jsonify({
        "blockchain_valid": True,
        "message": "Blockchain integrity verified"
    })

#--gis map---#
import math
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)

    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R*c


@app.route("/")
def home():
    return render_template("map.html")


@app.route('/api/land')
def get_land():

    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM gis_land_data")
        rows = cursor.fetchall()

        data = []

        for row in rows:

            polygon = []

            if len(row)>7 and row[7]:
                try:
                    polygon = json.loads(row[7])
                except:
                    polygon = []

            if not polygon:
                lat = row[5]
                lon = row[6]
                size = max(float(row[4]) / 10000000, 0.0003)

                polygon = [
                    [lat + size, lon + size],
                    [lat + size, lon - size],
                    [lat - size, lon - size],
                    [lat - size, lon + size]
                ]

            data.append({
                "parcel_id": row[0],
                "survey": row[1],
                "owner": row[2],
                "type": row[3],
                "area": row[4],
                "lat": row[5],
                "lon": row[6],
                "polygon": polygon,
                "status": row[8] if len(row)>8 and row[8] else "pending"
            })

        conn.close()
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/nearby_land")
def nearby_land():

    lat = float(request.args.get("lat"))
    lon = float(request.args.get("lon"))
    radius = float(request.args.get("radius",1))

    cursor = conn.cursor()

    cursor.execute("SELECT land_id,latitude,longitude FROM gis_land_data")

    rows = cursor.fetchall()

    result=[]

    for row in rows:

        dist = haversine(lat,lon,row.latitude,row.longitude)

        if dist<=radius:

            result.append({
                "parcel_id":str(row.land_id),
                "lat":row.latitude,
                "lon":row.longitude,
                "distance":round(dist,2)
            })

    return jsonify(result)

@app.route('/get_land_locations')
def get_land_locations():

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT parcel_id, owner, latitude, longitude
        FROM property
        WHERE latitude IS NOT NULL
    """)

    lands = cursor.fetchall()

    return jsonify(lands)

#---QR code---#

@app.route('/verify_property/<parcel_id>/<hash_value>')
def verify_property_qr(parcel_id, hash_value):

    expected_hash = generate_secure_hash(parcel_id)

    if hash_value != expected_hash:
        return render_template("property_dashboard.html",
                               error="Invalid QR Code",
                               property=None,
                               documents=[])

    cursor.execute("SELECT * FROM property WHERE parcel_id = ?", (parcel_id,))
    row = cursor.fetchone()

    if not row:
        return render_template("property_dashboard.html",
                               error="Property not found",
                               property=None,
                               documents=[])

    # ✅ PROPERTY DATA
    property_data = {
        "parcel_id": row[0],
        "owner_id": row[1],
        "survey_number": row[2],
        "khata_number": row[3],
        "village": row[4],
        "taluk": row[5],
        "district": row[6],
        "state": row[7],
        "land_type": row[8],
        "area_sqft": row[9],
        "registration_date": str(row[10]),
        "current_market_value": row[11],
        "geo_latitude": row[12],
        "geo_longitude": row[13],
        "tax_status": row[14],
        "mortgage_status": row[15],
    }

    # ✅ DOCUMENTS
    cursor.execute("""
        SELECT document_id, document_type, verification_status
        FROM document
        WHERE parcel_id = ?
    """, (parcel_id,))

    documents = cursor.fetchall()

    doc_list = []
    for d in documents:
        doc_list.append({
            "document_id": d[0],
            "document_type": d[1],
            "status": d[2],
            "url": f"/view_document/{d[0]}"
        })

    # ✅ FINAL RETURN (IMPORTANT POSITION)
    return render_template("property_dashboard.html",
                           property=property_data,
                           documents=doc_list,
                           error=None)

 
## ── 3. NEW: Regenerate QR for existing property ──
 
@app.route('/regenerate_qr/<parcel_id>', methods=['POST'])
def regenerate_qr(parcel_id):
 
    cursor.execute("SELECT parcel_id FROM property WHERE parcel_id = ?", (parcel_id,))
    row = cursor.fetchone()
 
    if not row:
        return jsonify({"error": "Property not found"}), 404
 
    filename = generate_qr(parcel_id)
 
    return jsonify({
        "message":   "QR regenerated successfully",
        "parcel_id": parcel_id,
        "qr_path":   filename
    })

@app.route('/add_land', methods=['POST'])
def add_land():
    data = request.json

    conn = sqlite3.connect("land.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO gis_land_data (land_id, owner_name, latitude, longitude)
    VALUES (?, ?, ?, ?)
    """, (data['land_id'], data['owner_name'], data['latitude'], data['longitude']))

    conn.commit()
    conn.close()

    return jsonify({"message": "Land added successfully"})

@app.route('/add-test-data')
def add_test_data():
    import os
    import psycopg2

    DATABASE_URL = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO gis_land_data VALUES
        ('L001', 'S001', 'Rama', 'Residential', 1200, 12.9716, 77.5946, ''),
        ('L002', 'S002', 'Shyam', 'Commercial', 2000, 12.9720, 77.5950, ''),
        ('L003', 'S003', 'Geeta', 'Agriculture', 3000, 12.9730, 77.5960, '')
    """)

    conn.commit()
    conn.close()

    return "Data inserted successfully!"

@app.route('/init-db')
def init_db():
    import os
    import psycopg2

    DATABASE_URL = os.environ.get("DATABASE_URL")

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gis_land_data (
        land_id TEXT,
        survey_number TEXT,
        owner_name TEXT,
        land_use_type TEXT,
        area_sq_ft REAL,
        latitude REAL,
        longitude REAL,
        boundary_polygon TEXT
    );
    """)

    conn.commit()
    conn.close()

    return "Table created successfully"

@app.route('/generate-data')
def generate_data():
    import os
    import psycopg2
    import random

    DATABASE_URL = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    # 🔥 Realistic names
    first_names = ["Ravi","Sita","Arjun","Meena","Kiran","Anita","Rahul","Priya","Vikram","Neha"]
    last_names = ["Kumar","Sharma","Reddy","Patel","Singh","Nair","Gupta","Das"]

    land_types = ["Residential", "Commercial", "Agricultural"]

    base_lat = 12.9716
    base_lon = 77.5946

    # ⚠️ Optional: clear old data
    cursor.execute("DELETE FROM gis_land_data")

    for i in range(1, 101):   # 🔥 100 records

        owner = random.choice(first_names) + " " + random.choice(last_names)

        lat = base_lat + random.uniform(-0.02, 0.02)
        lon = base_lon + random.uniform(-0.02, 0.02)

        land_type = random.choice(land_types)

        area = random.randint(800, 5000)

        cursor.execute("""
            INSERT INTO gis_land_data 
            (land_id, survey_number, owner_name, land_use_type, area_sq_ft, latitude, longitude, boundary_polygon)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            f"L{i:03}",
            f"S{i:03}",
            owner,
            land_type,
            area,
            lat,
            lon,
            '[]'
        ))

    conn.commit()
    conn.close()

    return "✅ 100 realistic land records generated!"

import os
import psycopg2
import qrcode

@app.route('/generate-qr')
def generate_qr():
    try:
        DATABASE_URL = os.environ.get("DATABASE_URL")

        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = conn.cursor()

        cursor.execute("SELECT land_id FROM gis_land_data")
        rows = cursor.fetchall()

        folder = "static/qr_codes"

        # create folder safely
        if not os.path.exists(folder):
            os.makedirs(folder)

        for row in rows:
            land_id = row[0]

            qr_data = f"https://land-registry-project.onrender.com/verify/{land_id}"

            img = qrcode.make(qr_data)
            img.save(os.path.join(folder, f"{land_id}.png"))

        conn.close()

        return "QR codes generated successfully!"

    except Exception as e:
        return f"Error: {str(e)}"

import qrcode
from io import BytesIO
from flask import send_file

@app.route('/qr/<parcel_id>')
def generate_qr_dynamically(parcel_id):
    url = f"https://land-registry-project.onrender.com/verify/{parcel_id}"

    img = qrcode.make(url)

    buffer = BytesIO()
    img.save(buffer)
    buffer.seek(0)

    return send_file(buffer, mimetype='image/png')

@app.route('/verify/<parcel_id>')
def verify(parcel_id):

    import psycopg2, os

    DATABASE_URL = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM gis_land_data WHERE land_id = %s", (parcel_id,))
    row = cursor.fetchone()

    conn.close()

    if not row:
        return f"<h2>❌ Property {parcel_id} Not Found</h2>"

    return f"""
    <h2>✅ Property Verified</h2>
    <p><b>Parcel ID:</b> {row[0]}</p>
    <p><b>Owner:</b> {row[2]}</p>
    <p><b>Type:</b> {row[3]}</p>
    <p><b>Area:</b> {row[4]} sq ft</p>
    """

# ---------------- ML PRICE PREDICTION ----------------
@app.route('/predict_price', methods=['POST'])
def predict_price():
    try:
        data = request.json

        input_data = {
            'area_sqft': data['area_sqft'],
            'road_distance_km': data['road_distance_km'],
            'city_distance_km': data['city_distance_km'],
            'nearby_school': 1 if data['nearby_school'] == 'Yes' else 0,
            'nearby_hospital': 1 if data['nearby_hospital'] == 'Yes' else 0,
            'year': data['year']
        }

        df = pd.DataFrame([input_data])

        # match training columns
        df = pd.get_dummies(df)

        for col in model_columns:
            if col not in df:
                df[col] = 0

        df = df[model_columns]

        prediction = model.predict(df)

        return jsonify({
            "predicted_price": float(prediction[0])
        })

    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/upload_document", methods=["POST"])
def upload_document():

    parcel_id = request.form.get("parcel_id")
    document_type = request.form.get("document_type")
    uploaded_by = request.form.get("uploaded_by")

    if "file" not in request.files:
        return {"error": "No file provided"}, 400

    file = request.files["file"]

    if file.filename == "":
        return {"error": "Empty filename"}, 400

    if not allowed_file(file.filename):
        return {"error": "Invalid file type"}, 400

    document_id = "DOC" + str(int(datetime.now().timestamp()))

    ext = file.filename.split(".")[-1]
    filename = f"{document_id}.{ext}"

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    file.save(file_path)

    file_hash = generate_file_hash(file_path)

    cursor.execute("""
        INSERT INTO document
        (document_id, parcel_id, document_type, file_path, file_hash, uploaded_by, uploaded_date, verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        document_id,
        parcel_id,
        document_type,
        file_path,
        file_hash,
        uploaded_by,
        datetime.now(),
        "Pending"
    ))

    conn.commit()

    return {
        "message": "Document uploaded successfully",
        "document_id": document_id
    }

@app.route('/documents/<land_id>')
def get_documents(land_id):

    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM document WHERE parcel_id = %s",
            (land_id,)
        )

        data = cursor.fetchall()

        cursor.close()
        conn.close()

        return str(data)

    except Exception as e:
        return "Error: " + str(e)

@app.route("/view_document/<document_id>")
def view_document(document_id):

    cursor.execute("""
        SELECT file_path
        FROM document
        WHERE document_id = ?
    """, (document_id,))

    row = cursor.fetchone()

    if not row:
        return {"error": "Document not found"}, 404

    file_path = row[0]

    if not os.path.exists(file_path):
        return {"error": "File missing"}, 404

    folder = os.path.dirname(file_path)
    filename = os.path.basename(file_path)

    return send_from_directory(folder, filename)

@app.route("/verify_document/<document_id>", methods=["PUT"])
def verify_document(document_id):

    data = request.json
    user_id = data.get("user_id")

    # check role
    cursor.execute("""
        SELECT role FROM users WHERE user_id = ?
    """, (user_id,))
    
    user = cursor.fetchone()

    if not user or user[0] != "admin":
        return {"error": "Unauthorized"}, 403

    cursor.execute("""
        UPDATE document
        SET verification_status = 'Verified'
        WHERE document_id = ?
    """, (document_id,))

    conn.commit()

    return {"message": "Document verified by admin"}

@app.route("/validate_document/<document_id>", methods=["GET"])
def validate_document(document_id):

    cursor.execute("""
        SELECT file_hash
        FROM document
        WHERE document_id = ?
    """, (document_id,))

    row = cursor.fetchone()

    if not row:
        return {"error": "Document not found"}

    db_hash = row[0]

    for file in os.listdir(UPLOAD_FOLDER):
        full_path = os.path.join(UPLOAD_FOLDER, file)

        if generate_file_hash(full_path) == db_hash:
            return {
                "status": "valid",
                "message": "Document is authentic"
            }

    return {
        "status": "tampered",
        "message": "Document integrity compromised"
    }

init_document_table()

@app.route("/generate_documents")
def generate_documents():

    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
        cursor = conn.cursor()

        # keep using land_id (correct for your table)
        cursor.execute("SELECT land_id FROM gis_land_data")
        lands = cursor.fetchall()

        if not lands:
            return "No lands found ❌"

        count = 1

        for land in lands:
            land_id = land[0]

            doc_id = f"DOC{count:03}"
            status=random.choice([
                "verified",
                "pebding",
                "Rejected"
            ])
            doc_type=random.choice([
                "Sale Deed",
                "Tax Receipt",
                "Mortgage Deed",
                "Transfer Deed",
                "Lease Agreement"
            ])

            cursor.execute("""
                INSERT INTO document 
                (document_id, parcel_id, document_type, file_hash, uploaded_by, uploaded_date, verification_status)
                VALUES (%s,%s,%s,%s,%s,NOW(),%s)
                ON CONFLICT (document_id) DO NOTHING
            """, (
                
                doc_id,
                land_id,   # ✅ map land_id → parcel_id
                doc_type,
                f"hash{count}",
                "U001",
                status
            ))

            count += 1

        conn.commit()
        conn.close()

        return f"Inserted {count-1} documents ✅"

    except Exception as e:
        return f"Error: {str(e)}"

@app.route("/create_document_table")
def create_document_table():

    conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS document (
        document_id TEXT PRIMARY KEY,
        parcel_id TEXT,
        document_type TEXT,
        file_hash TEXT,
        uploaded_by TEXT,
        uploaded_date TIMESTAMP,
        verification_status TEXT
    );
    """)

    conn.commit()
    conn.close()

    return "Table created"

@app.route("/check_lands")
def check_lands():
    conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
    cursor = conn.cursor()

    cursor.execute("SELECT land_id FROM gis_land_data LIMIT 10")
    rows = cursor.fetchall()

    conn.close()

    return str(rows)

@app.route('/check_documents')
def check_documents():

    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode='require')
        cursor = conn.cursor()

        # ✅ CORRECT QUERY
        cursor.execute("""
            SELECT d.document_id, d.parcel_id, d.document_type, d.verification_status
            FROM document d
        """)

        data = cursor.fetchall()

        cursor.close()
        conn.close()

        return str(data)

    except Exception as e:
        import traceback
        return f"<prep>{traceback.format_exec()}</prep>"
    
    
if __name__ == "__main__":
 app.run(host="0.0.0.0",port=500, debug=True)
                            
