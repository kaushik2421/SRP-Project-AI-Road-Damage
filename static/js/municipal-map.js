document.addEventListener('DOMContentLoaded',async()=>{
  const element=document.querySelector('#adminMap');
  if(!element)return;
  if(typeof L==='undefined'){element.innerHTML='<div class="empty-state">Map tiles are unavailable right now.</div>';return;}
  const map=L.map(element).setView([20.5937,78.9629],5);
  const markers=L.layerGroup().addTo(map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'Â© OpenStreetMap contributors',maxZoom:19}).addTo(map);
  const search=document.querySelector('#mapSearch');
  const filters=['mapSeverity','mapPriority','mapStatus','mapDamage'].map(id=>document.getElementById(id));
  const count=document.querySelector('#mapResultCount');
  try{
    const data=await api('/municipal/dashboard');
    Object.keys(data.damage||{}).forEach(damage=>{
      const option=document.createElement('option');option.value=damage;option.textContent=damage;
      document.querySelector('#mapDamage').append(option);
    });
  }catch(error){toast(error.message,'danger');}

  let searchTimer;
  const refresh=async()=>{
    const params=new URLSearchParams({per_page:'100'});
    if(search.value.trim())params.set('search',search.value.trim());
    const [severity,priority,status,damage]=filters.map(filter=>filter.value);
    if(severity)params.set('severity',severity);
    if(priority)params.set('priority',priority);
    if(status)params.set('status',status);
    if(damage)params.set('damage_type',damage);
    try{
      const data=await api(`/complaints?${params}`);
      markers.clearLayers();
      const points=[];
      data.items.forEach(item=>{
        const point=[item.latitude,item.longitude];points.push(point);
        const color=item.priority_level==='CRITICAL'?'#bd3b43':item.priority_level==='HIGH'?'#dc8a17':'#176fc2';
        const marker=L.circleMarker(point,{radius:8,color,fillColor:color,fillOpacity:.82,weight:2}).addTo(markers);
        const link=`/admin/complaints/${item.id}`;
        const popup=`<strong>${mapEscape(item.code)} Â· ${mapEscape(item.damage_type)}</strong><br>Severity ${Number(item.severity_score).toFixed(0)} Â· Priority ${Number(item.priority_score).toFixed(0)}<br>${mapEscape(item.road_name)}<br>${mapEscape(item.status.replaceAll('_',' '))}<br><a href="${link}">View complaint</a>`;
        marker.bindPopup(popup);
      });
      count.textContent=`Showing ${data.items.length} of ${data.total} complaints`;
      if(points.length)map.fitBounds(points,{padding:[28,28],maxZoom:14});
      else map.setView([20.5937,78.9629],5);
      setTimeout(()=>map.invalidateSize(),80);
    }catch(error){count.textContent=error.message;toast(error.message,'danger');}
  };
  filters.forEach(filter=>filter.addEventListener('change',refresh));
  search.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(refresh,220);});
  await refresh();
});

function mapEscape(value){return String(value??'').replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));}
