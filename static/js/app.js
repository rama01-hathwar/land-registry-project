/* ---------------- NAVIGATION ---------------- */
function show(id, el){

    // Hide all modules
    document.querySelectorAll(".module").forEach(m => {
        m.classList.add("hidden");
    });

    // Show selected module
    let active = document.getElementById(id);
    if(active){
        active.classList.remove("hidden");
    }

    // Highlight sidebar
    document.querySelectorAll(".menu").forEach(m => {
        m.classList.remove("bg-blue-500");
    });

    if(el){
        el.classList.add("bg-blue-500");
    }
}


/* ---------------- ROLE DISPLAY ---------------- */
window.onload = function(){

    let role = localStorage.getItem("role") || "admin";

    let roleBox = document.getElementById("role") || document.getElementById("roleDisplay");

    if(roleBox){
        roleBox.innerText = role.toUpperCase();
    }

    // Optional role-based hiding
    if(role === "bank"){
        hideModule("fraud");
    }

    if(role === "landowner"){
        hideModule("blockchain");
    }

};


/* ---------------- ROLE HIDE ---------------- */
function hideModule(id){
    let el = document.getElementById(id);
    if(el){
        el.style.display = "none";
    }
}


/* ---------------- FRAUD ---------------- */
function checkFraud(){

    let id = document.getElementById("fraudId").value;

    fetch(`/fraud_check/${id}`)
    .then(res => res.json())
    .then(data => {

        document.getElementById("fraudTable").innerHTML = `
            <tr>
                <td>${data.parcel_id}</td>
                <td>${data.risk_level}</td>
            </tr>
        `;
    })
    .catch(err => console.log(err));
}


/* ---------------- ML PREDICTION ---------------- */
function predict(){

    let area = document.getElementById("area").value;

    fetch("/predict_price", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            area_sqft: area,
            road_distance_km: 2,
            city_distance_km: 5,
            nearby_school: "Yes",
            nearby_hospital: "No",
            year: 2024
        })
    })
    .then(res => res.json())
    .then(data => {

        document.getElementById("result").innerHTML =
            "₹ " + data.predicted_price;

    })
    .catch(err => console.log(err));
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
    .then(res => res.json())
    .then(data => {

        let html = "";

        data.forEach(log => {
            html += `
            <tr>
                <td>${log.user_id}</td>
                <td>${log.action_type}</td>
            </tr>`;
        });

        document.getElementById("logTable").innerHTML = html;

    })
    .catch(err => console.log(err));
}


/* ---------------- BLOCKCHAIN ---------------- */
function loadBlockchain(){

    fetch("/get_blockchain")
    .then(res => res.json())
    .then(data => {

        let html = "";

        data.forEach(b => {
            html += `
            <tr>
                <td>${b.block_number}</td>
                <td>${b.confirmation_status}</td>
            </tr>`;
        });

        document.getElementById("blockTable").innerHTML = html;

    })
    .catch(err => console.log(err));
}


/* ---------------- DARK MODE ---------------- */
function toggleDark(){

    document.body.classList.toggle("bg-gray-900");
    document.body.classList.toggle("text-white");

}


/* ---------------- MAP (SAFE LOAD) ---------------- */
setTimeout(() => {

    let mapDiv = document.getElementById("map");

    if(!mapDiv) return;

    let map = L.map('map').setView([12.97, 77.75], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
    .addTo(map);

    fetch("/api/land")
    .then(res => res.json())
    .then(data => {

        data.forEach(land => {

            let marker = L.marker([land.lat, land.lon]).addTo(map);

            marker.on("click", () => {

                if(document.getElementById("details")){
                    document.getElementById("details").innerHTML =
                        `Parcel: ${land.parcel_id}`;
                }

            });

        });

    })
    .catch(err => console.log(err));

}, 500);
