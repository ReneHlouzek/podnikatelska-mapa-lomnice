const CENTER=[50.5309,15.3734], RADIUS=5000;
const map=L.map('map').setView(CENTER,13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map);
L.circle(CENTER,{radius:RADIUS,weight:2,dashArray:'6 6',fillOpacity:.035}).addTo(map);
const layer=L.layerGroup().addTo(map); let firms=[];
const $=id=>document.getElementById(id);
const dist=(a,b)=>{const R=6371000,p=Math.PI/180,dLat=(b[0]-a[0])*p,dLon=(b[1]-a[1])*p,x=Math.sin(dLat/2)**2+Math.cos(a[0]*p)*Math.cos(b[0]*p)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(x));};
function options(id,values){const s=$(id), old=s.value; [...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b,'cs')).forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;s.appendChild(o)});s.value=old}
function marker(f){const m=L.circleMarker([f.lat,f.lon],{radius:f.size==='50–99' || f.size==='100–249' || f.size==='250+'?9:7,weight:1,fillOpacity:.78});m.bindPopup(`<div class="popup"><h3>${esc(f.name)}</h3>${f.ico?`<p><b>IČO:</b> ${esc(f.ico)}</p>`:''}<p><b>Adresa:</b> ${esc(f.address||'neuvedena')}</p><p><b>Obor:</b> ${esc(f.sector||'neuveden')}</p>${f.nace?`<p><b>CZ-NACE:</b> ${esc(f.nace)}</p>`:''}<p><b>Velikost:</b> ${esc(f.size||'neuvedena')}</p><p><b>Právní forma:</b> ${esc(f.legal||'neuvedena')}</p>${f.workers_note?`<p class="muted">${esc(f.workers_note)}</p>`:''}</div>`);return m}
function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]))}
function render(){layer.clearLayers();const q=$('search').value.trim().toLowerCase(),sec=$('sector').value,sz=$('size').value,leg=$('legal').value,dr=$('distance').value;let shown=0;firms.forEach(f=>{const d=dist(CENTER,[f.lat,f.lon]),km=d/1000;let ok=d<=RADIUS&&(!q||`${f.name} ${f.ico} ${f.address}`.toLowerCase().includes(q))&&(!sec||f.sector===sec)&&(!sz||f.size===sz)&&(!leg||f.legal===leg);if(dr){const [a,b]=dr.split('-').map(Number);ok=ok&&km>=a&&km<=b}if(ok){marker(f).addTo(layer);shown++}});$('visible').textContent=shown;$('count').textContent=`${shown} subjektů`}
['search','sector','size','legal','distance'].forEach(id=>$(id).addEventListener('input',render));
fetch('data/firms.json').then(r=>r.json()).then(data=>{firms=data.filter(f=>Number.isFinite(f.lat)&&Number.isFinite(f.lon));options('sector',firms.map(f=>f.sector));options('size',firms.map(f=>f.size));options('legal',firms.map(f=>f.legal));render()}).catch(()=>{$('count').textContent='Chyba načtení dat'});
