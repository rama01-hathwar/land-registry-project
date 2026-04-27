function showModule(id, el){
document.querySelectorAll(".module").forEach(m=>m.classList.add("hidden"))
document.getElementById(id).classList.remove("hidden")

document.querySelectorAll(".menu").forEach(m=>m.classList.remove("bg-blue-500"))
el.classList.add("bg-blue-500")
}

/* MAP */
var map = L.map('map').setView([12.97,77.75],12)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map)

fetch("/api/land")
.then(r=>r.json())
.then(data=>{
data.forEach(l=>{
let m=L.marker([l.lat,l.lon]).addTo(map)
m.on("click",()=>{
document.getElementById("details").innerHTML=l.parcel_id
document.getElementById("qrSection").innerHTML=`<img src="/qr/${l.parcel_id}" width="100">`

fetch("/predict_price",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({area_sqft:l.area,road_distance_km:2,city_distance_km:5,nearby_school:"Yes",nearby_hospital:"No",year:2024})})
.then(r=>r.json())
.then(d=>{
document.getElementById("priceBox").innerHTML="₹ "+d.predicted_price
})
})
})
})

/* ML */
function predict(){
let a=document.getElementById("area").value
fetch("/predict_price",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({area_sqft:a,road_distance_km:2,city_distance_km:5,nearby_school:"Yes",nearby_hospital:"No",year:2024})})
.then(r=>r.json())
.then(d=>{
document.getElementById("result").innerHTML="₹ "+d.predicted_price

new Chart(document.getElementById("mlChart"),{
type:"bar",
data:{labels:["Price"],datasets:[{data:[d.predicted_price]}]}
})
})
}

/* FRAUD */
function checkFraud(){
let id=document.getElementById("fraudId").value
fetch(`/fraud_check/${id}`)
.then(r=>r.json())
.then(d=>{
document.getElementById("fraudTable").innerHTML=
`<tr><td>${d.parcel_id}</td><td>${d.risk_level}</td></tr>`
})
}

/* QR */
function loadQR(){
let id=document.getElementById("qrId").value
document.getElementById("qrImage").innerHTML=`<img src="/qr/${id}" width="150">`
}

/* LOGS */
function loadLogs(){
fetch("/get_login_activity")
.then(r=>r.json())
.then(data=>{
let h=""
data.forEach(l=>{
h+=`<tr><td>${l.user_id}</td><td>${l.action_type}</td></tr>`
})
document.getElementById("logTable").innerHTML=h
})
}

/* BLOCKCHAIN */
function loadBlockchain(){
fetch("/get_blockchain")
.then(r=>r.json())
.then(data=>{
let h=""
data.forEach(b=>{
h+=`<tr><td>${b.block_number}</td><td>${b.confirmation_status}</td></tr>`
})
document.getElementById("blockTable").innerHTML=h
})
}

/* CHARTS */
new Chart(document.getElementById("propertyChart"),{
type:"doughnut",
data:{labels:["Res","Com","Agri"],datasets:[{data:[40,30,30]}]}
})

new Chart(document.getElementById("transactionChart"),{
type:"line",
data:{labels:["Jan","Feb","Mar"],datasets:[{data:[5,10,15]}]}
})
