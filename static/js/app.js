function show(id){
    document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
    document.getElementById(id).classList.add('active');

    if(id==="dashboard") loadDashboard();
    if(id==="transfer") loadTransfer();
    if(id==="history") loadHistory();
    if(id==="documents") loadDocuments();
    if(id==="tax") loadTax();
    if(id==="mortgage") loadMortgage();
    if(id==="fraud") loadFraud();
    if(id==="dispute") loadDispute();
    if(id==="gis") loadGIS();
    if(id==="qr") loadQR();
    if(id==="ml") loadML();
    if(id==="logs") loadLogs();
    if(id==="blockchain") loadBlockchain();
}

/* ================= DASHBOARD ================= */
function loadDashboard(){
    fetch('/dashboard_data')
    .then(r=>r.json())
    .then(d=>{
        dashboard.innerHTML = `
        <h2>Dashboard</h2>
        <div class="card">Parcels: ${d.parcels}</div>
        <div class="card">Revenue: ₹${d.revenue}</div>
        <div class="card">Frauds: ${d.frauds}</div>`;
    });
}

/* ================= TRANSFER ================= */
function loadTransfer(){
    transfer.innerHTML = `
    <h2>Ownership Transfer</h2>
    <input id="p" placeholder="Parcel ID">
    <input id="s" placeholder="Seller">
    <input id="b" placeholder="Buyer">
    <button onclick="transferOwnership()">Transfer</button>`;
}

function transferOwnership(){
    fetch('/transfer',{method:'POST'});
}

/* ================= HISTORY ================= */
function loadHistory(){
    fetch('/history').then(r=>r.json()).then(d=>{
        history.innerHTML = "<h2>Ownership History</h2>"+
        d.map(x=>`<div class="card">${x}</div>`).join('');
    });
}

/* ================= DOCUMENT ================= */
function loadDocuments(){
    documents.innerHTML = `
    <h2>Upload Document</h2>
    <input type="file">
    <button>Upload</button>`;
}

/* ================= TAX ================= */
function loadTax(){
    fetch('/tax').then(r=>r.json()).then(d=>{
        tax.innerHTML = "<h2>Tax</h2>"+
        d.map(x=>`<div class="card">${x.amount}</div>`).join('');
    });
}

/* ================= MORTGAGE ================= */
function loadMortgage(){
    fetch('/mortgage').then(r=>r.json()).then(d=>{
        mortgage.innerHTML = "<h2>Mortgage</h2>"+
        d.map(x=>`<div class="card">${x.bank}</div>`).join('');
    });
}

/* ================= FRAUD ================= */
function loadFraud(){
    fetch('/fraud').then(r=>r.json()).then(d=>{
        fraud.innerHTML = "<h2>Fraud</h2>"+
        d.map(x=>`<div class="card">${x.status}</div>`).join('');
    });
}

/* ================= DISPUTE ================= */
function loadDispute(){
    dispute.innerHTML="<h2>Disputes</h2>";
}

/* ================= GIS ================= */
function loadGIS(){
    gis.innerHTML="<h2>GIS Map</h2><div id='map'></div>";
}

/* ================= QR ================= */
function loadQR(){
    qr.innerHTML="<h2>QR Verification</h2>";
}

/* ================= ML ================= */
function loadML(){
    ml.innerHTML="<h2>Price Prediction</h2>";
}

/* ================= LOGS ================= */
function loadLogs(){
    logs.innerHTML="<h2>Activity Logs</h2>";
}

/* ================= BLOCKCHAIN ================= */
function loadBlockchain(){
    blockchain.innerHTML="<h2>Blockchain Explorer</h2>";
}

window.onload = loadDashboard;
