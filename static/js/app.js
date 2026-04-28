let allMarkers=[];

/* ROLE CONTROL */
window.onload=function(){
let role=localStorage.getItem("role")||"admin";
document.getElementById("roleDisplay").innerText=role.toUpperCase();

// hide based on role
document.querySelectorAll(".menu").forEach(m=>{
if(m.classList.contains("role-"+role) || !m.className.includes("role-")){
m.style.display="block";
}else{
m.style.display="none";
}
});
}

/* NAV */
function show(id,el){
document.querySelectorAll(".module").forEach(m=>m.classList.add("hidden"));
document.getElementById(id).classList.remove("hidden");

document.querySelectorAll(".menu").forEach(m=>m.classList.remove("active"));
el.classList.add("active");

if(id==="gis"){
setTimeout(()=>{
if(window.map){window.map.invalidateSize();}
else{loadMap();}
},300);
}
}

/* MAP */
function loadMap(){
window.map=L.map('map').setView([12.97,77.59],12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

fetch("/api/land")
.then(r=>r.json())
.then(data=>{
data.forEach(l=>{
let color="blue",type="normal";
if(l.type==="Commercial"){color="red";type="dispute";}
else{color="green";type="sale";}

let icon=L.icon({
iconUrl:`https://maps.google.com/mapfiles/ms/icons/${color}-dot.png`,
iconSize:[30,30]
});

let m=L.marker([l.lat,l.lon],{icon}).addTo(map);
m.type=type;
allMarkers.push(m);
});
});
}

/* FILTER */
function filterMap(type){
allMarkers.forEach(m=>map.removeLayer(m));
allMarkers.forEach(m=>{
if(type==="all"||m.type===type)m.addTo(map);
});
}
