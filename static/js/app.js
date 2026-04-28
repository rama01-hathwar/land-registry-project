function safeFetch(url, callback){
    fetch(window.location.origin + url)
    .then(res=>{
        if(!res.ok) throw new Error("API error");
        return res.json();
    })
    .then(data=>{
        if(data.error){
            console.error(data.error);
            return;
        }
        callback(data);
    })
    .catch(err=>{
        console.error("Fetch error:", err);
    });
}

// ---------------- NAV ----------------
function show(id, el){

    document.querySelectorAll(".module").forEach(m=>{
        m.style.display = "none";
    });

    document.getElementById(id).style.display = "block";

    document.querySelectorAll(".menu").forEach(m=>{
        m.classList.remove("active");
    });

    el.classList.add("active");

    if(id==="gis") loadMap();
    if(id==="fraud") loadFraud();
    if(id==="history") loadHistory();
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

    safeFetch("/api/land", data=>{
        data.forEach(l=>{
            L.marker([l.lat,l.lon])
            .addTo(map)
            .bindPopup(l.parcel_id);
        });
    });
}

// ---------------- MODULES ----------------
function loadFraud(){
    safeFetch("/fraud_check/L001", d=>{
        document.getElementById("fraud").innerHTML =
        `${d.parcel_id} - ${d.risk_level}`;
    });
}

function loadHistory(){
    safeFetch("/owner_history/L001", data=>{
        let html="";
        data.forEach(h=>{
            html += `<div>${h.from} → ${h.to}</div>`;
        });
        document.getElementById("history").innerHTML = html;
    });
}

function loadTax(){
    safeFetch("/tax/L001", d=>{
        document.getElementById("tax").innerHTML =
        `Amount: ${d.amount}`;
    });
}

function loadMortgage(){
    safeFetch("/mortgage/L001", d=>{
        document.getElementById("mortgage").innerHTML =
        `${d.bank || ""} ${d.amount || ""}`;
    });
}

function loadDispute(){
    safeFetch("/dispute/L001", d=>{
        document.getElementById("dispute").innerHTML =
        `${d.issue || d.status}`;
    });
}

function loadLogs(){
    safeFetch("/get_login_activity", data=>{
        let html="";
        data.forEach(l=>{
            html += `<div>${l.user_id}</div>`;
        });
        document.getElementById("logs").innerHTML = html;
    });
}

function loadBlockchain(){
    safeFetch("/get_blockchain", data=>{
        let html="";
        data.forEach(b=>{
            html += `<div>Block ${b.block_number}</div>`;
        });
        document.getElementById("blockchain").innerHTML = html;
    });
}
