// 🔥 MODULE SWITCHING (MAIN FIX)
function show(id, el){

    // hide all modules
    document.querySelectorAll(".module").forEach(m=>{
        m.classList.add("hidden");
    });

    // show selected module
    let active = document.getElementById(id);
    if(active){
        active.classList.remove("hidden");
    }

    // highlight sidebar
    document.querySelectorAll(".menu").forEach(m=>{
        m.classList.remove("bg-blue-100");
    });

    if(el){
        el.classList.add("bg-blue-100");
    }
}


/* ---------------- FRAUD ---------------- */
function checkFraud(){
    let id = document.getElementById("fraudId").value;

    fetch(`/fraud_check/${id}`)
    .then(r=>r.json())
    .then(d=>{
        document.getElementById("fraudTable").innerHTML =
        `<tr>
            <td>${d.parcel_id}</td>
            <td>${d.risk_level}</td>
        </tr>`;
    });
}


/* ---------------- QR ---------------- */
function loadQR(){
    let id = document.getElementById("qrId").value;
    document.getElementById("qrImage").innerHTML =
        `<img src="/qr/${id}" width="150">`;
}


/* ---------------- LOGS ---------------- */
function loadLogs(){
    fetch("/get_login_activity")
    .then(r=>r.json())
    .then(data=>{
        let html="";
        data.forEach(l=>{
            html += `<tr>
                <td>${l.user_id}</td>
                <td>${l.action_type}</td>
            </tr>`;
        });
        document.getElementById("logTable").innerHTML = html;
    });
}


/* ---------------- BLOCKCHAIN ---------------- */
function loadBlockchain(){
    fetch("/get_blockchain")
    .then(r=>r.json())
    .then(data=>{
        let html="";
        data.forEach(b=>{
            html += `<tr>
                <td>${b.block_number}</td>
                <td>${b.confirmation_status}</td>
            </tr>`;
        });
        document.getElementById("blockTable").innerHTML = html;
    });
}


/* ---------------- MAP (SAFE INIT) ---------------- */
setTimeout(() => {

    let mapDiv = document.getElementById("map");
    if(!mapDiv) return;

    var map = L.map('map').setView([12.97,77.75],12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    fetch("/api/land")
    .then(r=>r.json())
    .then(data=>{
        data.forEach(l=>{
            let m=L.marker([l.lat,l.lon]).addTo(map);
            m.on("click",()=>{
                document.getElementById("details").innerHTML = l.parcel_id;
            });
        });
    });

}, 500);
