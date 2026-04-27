let allMarkers = [];

/* NAVIGATION */
function show(id, el){

    document.querySelectorAll(".module").forEach(m => m.classList.add("hidden"));
    document.getElementById(id).classList.remove("hidden");

    document.querySelectorAll(".menu").forEach(m => m.classList.remove("bg-blue-500"));
    if(el) el.classList.add("bg-blue-500");

    if(id === "gis"){
        setTimeout(()=>{
            if(window.map){
                window.map.invalidateSize();
            } else {
                loadMap();
            }
        },300);
    }

    if(id === "dashboard"){
        loadChart();
    }
}

/* MAP */
function loadMap(){

    window.map = L.map('map').setView([12.97,77.59], 12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
    .addTo(window.map);

    fetch("/api/land")
    .then(res=>res.json())
    .then(data=>{

        data.forEach(land=>{

            let color="blue", type="normal";

            if(land.type==="Commercial"){color="red"; type="dispute";}
            else if(land.type==="Residential"){color="green"; type="sale";}

            let icon=L.icon({
                iconUrl:`https://maps.google.com/mapfiles/ms/icons/${color}-dot.png`,
                iconSize:[30,30]
            });

            let marker=L.marker([land.lat, land.lon],{icon}).addTo(window.map);

            marker.type=type;

            marker.bindPopup(`${land.parcel_id}<br>${land.owner}`);

            allMarkers.push(marker);
        });

    });
}

/* FILTER */
function filterMap(type){
    allMarkers.forEach(m=>window.map.removeLayer(m));
    allMarkers.forEach(m=>{
        if(type==="all"||m.type===type) m.addTo(window.map);
    });
}

/* CHART */
function loadChart(){
    new Chart(document.getElementById("chart"),{
        type:'bar',
        data:{
            labels:["2019","2020","2021","2022","2023"],
            datasets:[{
                label:"Prices",
                data:[40,50,60,70,90]
            }]
        }
    });
}
