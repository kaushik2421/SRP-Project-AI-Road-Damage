const escapeText=value=>String(value??'').replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const countStatuses=(values,...keys)=>keys.reduce((total,key)=>total+(values[key]||0),0);
const makeMetric=(label,value,icon,note='')=>`<article class="metric-card"><span>${label}</span><i class="metric-icon bi bi-${icon}" aria-hidden="true"></i><b>${value}</b>${note?`<small class="metric-note">${note}</small>`:''}</article>`;

 document.addEventListener('DOMContentLoaded',async()=>{
  try{
    const data=await api('/dashboard');
    const statuses=data.statuses||{};
    const citizen=document.querySelector('.citizen-dashboard');
    const municipal=document.querySelector('#operationsMap');
    const metrics=document.querySelector('#metrics');
    if(metrics&&municipal){
      const priority=data.priority||{};
      metrics.innerHTML=[
        makeMetric('Total complaints',data.total,'files'),
        makeMetric('New reports',countStatuses(statuses,'SUBMITTED','UNDER_REVIEW'),'inbox'),
        makeMetric('High priority',(priority.HIGH||0)+(priority.CRITICAL||0),'exclamation-triangle'),
        makeMetric('Critical',priority.CRITICAL||0,'exclamation-octagon'),
        makeMetric('In progress',statuses.IN_PROGRESS||0,'tools'),
        makeMetric('Completed',countStatuses(statuses,'REPAIR_COMPLETED','VERIFIED','CLOSED'),'check2-circle')
      ].join('');
    }else if(metrics&&citizen){
      metrics.innerHTML=[
        makeMetric('Total reports',data.total,'geo-alt','Submitted by you'),
        makeMetric('Repair in progress',countStatuses(statuses,'ASSIGNED','IN_PROGRESS'),'wrench-adjustable'),
        makeMetric('Resolved',countStatuses(statuses,'REPAIR_COMPLETED','VERIFIED','CLOSED'),'check2-circle')
      ].join('');
    }

    const reports=data.recent||[];
    const reportList=document.querySelector('#recent .report-list');
    if(reportList){
      reportList.innerHTML=reports.length?reports.map(report=>`<a class="report-row" href="/citizen/complaints/${report.id}"><div><b>${escapeText(report.code)}</b><small class="d-block">${escapeText(report.damage_type)} · ${escapeText(report.road_name)}</small></div><div class="spacer"><span class="report-row-meta">Priority ${Number(report.priority_score).toFixed(0)}</span><span class="status ${escapeText(report.status.toLowerCase())}">${escapeText(report.status.replaceAll('_',' '))}</span></div></a>`).join(''):'<div class="empty-state"><strong>No reports yet</strong>Your submitted road reports will appear here.</div>';
    }
    const impact=document.querySelector('#impactStats');
    if(impact)impact.innerHTML=[
      ['Reports submitted',data.total],
      ['Repairs completed',countStatuses(statuses,'REPAIR_COMPLETED','VERIFIED','CLOSED')],
      ['Currently being handled',countStatuses(statuses,'UNDER_REVIEW','ASSIGNED','IN_PROGRESS')]
    ].map(([label,value])=>`<div class="impact-stat"><b>${value}</b><span>${label}</span></div>`).join('');

    renderCharts(data);
    if(municipal){await renderPriorityQueue();await renderOperationsMap();}
  }catch(error){toast(error.message,'danger');}
});

function renderCharts(data){
  if(typeof Chart==='undefined')return;
  const colors=['#176fc2','#16805d','#dc8a17','#bd3b43','#6e83a0','#36a6a0'];
  const create=(selector,entries)=>{
    const canvas=document.querySelector(selector);
    if(!canvas)return;
    if(!Object.keys(entries||{}).length){
      canvas.remove();
      const empty=document.createElement('p');
      empty.className='chart-empty';
      empty.textContent='No complaint data available yet.';
      canvas.parentElement.append(empty);
      return;
    }
    new Chart(canvas,{type:'doughnut',data:{labels:Object.keys(entries),datasets:[{data:Object.values(entries),backgroundColor:colors,borderWidth:0,hoverOffset:4}]},options:{maintainAspectRatio:false,cutout:'68%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:7,padding:15,font:{family:'Manrope',size:10}}}}}});
  };
  create('#damageChart',data.damage);
  create('#statusChart',data.statuses);
  create('#severityChart',data.severity);
}

async function renderPriorityQueue(){
  const host=document.querySelector('#priorityQueue');
  if(!host)return;
  try{
    const data=await api('/complaints?sort=priority_score&per_page=6');
    host.innerHTML=data.items.length?data.items.map(item=>`<a class="priority-row" href="/admin/complaints/${item.id}"><i class="priority-mark ${escapeText(item.priority_level.toLowerCase())}"></i><span><strong>${escapeText(item.code)} · ${escapeText(item.damage_type)}</strong><small>${escapeText(item.road_name)} · ${escapeText(item.status.replaceAll('_',' '))}</small></span><span class="priority-score">${Number(item.priority_score).toFixed(0)}<small>${escapeText(item.priority_level)}</small></span></a>`).join(''):'<div class="empty-state"><strong>Queue is clear</strong>New complaints will appear here ranked by their recorded priority scores.</div>';
  }catch(error){host.innerHTML=`<div class="empty-state">${escapeText(error.message)}</div>`;}
}

async function renderOperationsMap(){
  const element=document.querySelector('#operationsMap');
  if(!element)return;
  if(typeof L==='undefined'){element.innerHTML='<div class="empty-state">Map tiles are unavailable right now.</div>';return;}
  const map=L.map(element,{scrollWheelZoom:false}).setView([20.5937,78.9629],5);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(map);
  try{
    const data=await api('/complaints?per_page=100');
    const points=[];
    data.items.forEach(item=>{
      const point=[item.latitude,item.longitude];
      points.push(point);
      const color=item.priority_level==='CRITICAL'?'#bd3b43':item.priority_level==='HIGH'?'#dc8a17':'#176fc2';
      const popup=`<strong>${escapeText(item.code)} · ${escapeText(item.damage_type)}</strong><br>Severity ${Number(item.severity_score).toFixed(0)} · Priority ${Number(item.priority_score).toFixed(0)}<br>${escapeText(item.road_name)}<br><a href="/admin/complaints/${item.id}">Open complaint</a>`;
      L.circleMarker(point,{radius:7,color,fillColor:color,fillOpacity:.82,weight:2}).addTo(map).bindPopup(popup);
    });
    if(points.length)map.fitBounds(points,{padding:[24,24],maxZoom:14});
    else element.insertAdjacentHTML('beforeend','<div class="map-empty">No complaints with coordinates yet</div>');
    setTimeout(()=>map.invalidateSize(),120);
  }catch(error){toast(error.message,'danger');}
}
