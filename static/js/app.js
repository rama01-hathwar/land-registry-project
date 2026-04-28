function show(id, el){

    document.querySelectorAll(".module").forEach(m=>{
        m.classList.add("hidden");
    });

    let active = document.getElementById(id);
    if(active){
        active.classList.remove("hidden");
    }

    document.querySelectorAll(".menu").forEach(m=>{
        m.classList.remove("active");
    });

    if(el){
        el.classList.add("active");
    }

    if(id==="gis"){
        setTimeout(()=>{
            if(window.map){
                window.map.invalidateSize();
            } else {
                loadMap();
            }
        },300);
    }
}

function logout(){
    localStorage.clear();
    window.location.href="/";
}

function loadMap(){

    window.map = L.map('map').setView([12.97,77.59],12);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

    fetch("/api/land")
    .then(res=>res.json())
    .then(data=>{
        data.forEach(l=>{
            L.marker([l.lat, l.lon])
            .addTo(map)
            .bindPopup(`<b>${l.parcel_id}</b><br>${l.owner}`);
        });
    });
}
