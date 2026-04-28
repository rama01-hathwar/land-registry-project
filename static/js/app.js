function show(id, el){

    document.querySelectorAll(".module").forEach(m=>{
        m.classList.add("hidden");
    });

    document.getElementById(id).classList.remove("hidden");

    document.querySelectorAll(".menu").forEach(m=>{
        m.classList.remove("active");
    });

    el.classList.add("active");

    if(id==="dashboard") loadChart();
    if(id==="gis") loadMap();
    if(id==="fraud") loadFraud();
    if(id==="history") loadHistory();
    if(id==="documents") loadDocuments();
    if(id==="tax") loadTax();
    if(id==="mortgage") loadMortgage();
    if(id==="dispute") loadDispute();
    if(id==="logs") loadLogs();
    if(id==="blockchain") loadBlockchain();
}

// ---------------- MAP ----------------
function loadMap(){
    if(window.map) return;

    window.map = L.map('map').setView([12.97,77.59],12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    fetch(window.location.origin + "/api/land")
    .then(res=>res.json())
    .then(data=>{
        data.forEach(l=>{
            L.marker([l.lat,l.lon])
            .addTo(map)
            .bindPopup(`<b>${l.parcel_id}</b><br>${l.owner}`);
        });
    });
}

// ---------------- FRAUD ----------------
function loadFraud(){
    fetch("/fraud_check/L001")
    .then(r=>r.json())
    .then(d=>{
        document.getElementById("fraud").innerHTML =
        `<div class="card red">${d.parcel_id} - ${d.risk_level}</div>`;
    });
}

// ---------------- HISTORY ----------------
function loadHistory(){
    fetch("/owner_history/L001")
    .then(r=>r.json())
    .then(data=>{
        let html="";
        data.forEach(h=>{
            html += `<div>${h.from} → ${h.to}</div>`;
        });
        document.getElementById("history").innerHTML = html;
    });
}

// ---------------- DOCUMENTS ----------------
function loadDocuments(){
    fetch("/documents/L001")
    .then(r=>r.json())
    .then(data=>{
        let html="";
        data.forEach(d=>{
            html += `<div>${d.type} - ${d.status}</div>`;
        });
        document.getElementById("documents").innerHTML = html;
    });
}

// ---------------- TAX ----------------
function loadTax(){
    fetch("/tax/L001")
    .then(r=>r.json())
    .then(d=>{
        document.getElementById("tax").innerHTML =
        `<div>Amount: ${d.amount} | Status: ${d.status}</div>`;
    });
}

// ---------------- MORTGAGE ----------------
function loadMortgage(){
    fetch("/mortgage/L001")
    .then(r=>r.json())
    .then(d=>{
        document.getElementById("mortgage").innerHTML =
        `<div>${d.bank} - ${d.amount} - ${d.status}</div>`;
    });
}

// ---------------- DISPUTE ----------------
function loadDispute(){
    fetch("/dispute/L001")
    .then(r=>r.json())
    .then(d=>{
        document.getElementById("dispute").innerHTML =
        `<div>${d.issue} - ${d.status}</div>`;
    });
}

// ---------------- LOGS ----------------
function loadLogs(){
    fetch("/get_login_activity")
    .then(r=>r.json())
    .then(data=>{
        let html="";
        data.forEach(l=>{
            html += `<div>${l.user_id} - ${l.action_type}</div>`;
        });
        document.getElementById("logs").innerHTML = html;
    });
}

// ---------------- BLOCKCHAIN ----------------
function loadBlockchain(){
    fetch("/get_blockchain")
    .then(r=>r.json())
    .then(data=>{
        let html="";
        data.forEach(b=>{
            html += `<div>Block ${b.block_number} - ${b.confirmation_status}</div>`;
        });
        document.getElementById("blockchain").innerHTML = html;
    });
}

// ---------------- LOGOUT ----------------
function logout(){
    localStorage.clear();
    window.location.href="/";
}
