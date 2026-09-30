const insightEscape=value=>String(value??'').replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
const insightMetric=(label,value,icon)=>`<article class="metric-card"><span>${label}</span><i class="metric-icon bi bi-${icon}" aria-hidden="true"></i><b>${value}</b></article>`;

 document.addEventListener('DOMContentLoaded',async()=>{
  try{
    const data=await api('/municipal/dashboard');
    renderPriorityMetrics(data);
    renderSeverityMetrics(data);
    renderAnalytics(data);
    if(document.querySelector('#priorityRows'))bindComplaintQueue('priorityRows','priorityFilter','priority_score','priority');
    if(document.querySelector('#severityRows'))bindComplaintQueue('severityRows','severityFilter','severity_score','severity');
  }catch(error){toast(error.message,'danger');}
});

function renderPriorityMetrics(data){
  const target=document.querySelector('#priorityMetrics');
  if(!target)return;
  const open=(data.statuses?.SUBMITTED||0)+(data.statuses?.UNDER_REVIEW||0)+(data.statuses?.ASSIGNED||0)+(data.statuses?.IN_PROGRESS||0);
  target.innerHTML=[insightMetric('Critical priority',data.priority?.CRITICAL||0,'exclamation-octagon'),insightMetric('High priority',data.priority?.HIGH||0,'exclamation-triangle'),insightMetric('Open complaints',open,'hourglass-split'),insightMetric('Total scored',data.total,'speedometer2')].join('');
}

function renderSeverityMetrics(data){
  const target=document.querySelector('#severityMetrics');
  if(!target)return;
  target.innerHTML=[insightMetric('Critical severity',data.severity?.CRITICAL||0,'exclamation-octagon'),insightMetric('High severity',data.severity?.HIGH||0,'exclamation-triangle'),insightMetric('Moderate severity',data.severity?.MODERATE||0,'activity'),insightMetric('Low severity',data.severity?.LOW||0,'check2-circle')].join('');
}

function renderAnalytics(data){
  const target=document.querySelector('#analyticsMetrics');
  if(target)target.innerHTML=[insightMetric('Complaints recorded',data.total,'files'),insightMetric('Currently in progress',data.statuses?.IN_PROGRESS||0,'tools'),insightMetric('High or critical priority',(data.priority?.HIGH||0)+(data.priority?.CRITICAL||0),'exclamation-triangle'),insightMetric('Closed',data.statuses?.CLOSED||0,'check2-circle')].join('');
  if(typeof Chart==='undefined')return;
  const colors=['#176fc2','#16805d','#dc8a17','#bd3b43','#6e83a0','#36a6a0'];
  const draw=(selector,values)=>{
    const canvas=document.querySelector(selector);
    if(!canvas)return;
    if(!Object.keys(values||{}).length){canvas.remove();canvas.parentElement.insertAdjacentHTML('beforeend','<p class="chart-empty">No complaint data available yet.</p>');return;}
    new Chart(canvas,{type:'doughnut',data:{labels:Object.keys(values),datasets:[{data:Object.values(values),backgroundColor:colors,borderWidth:0}]},options:{maintainAspectRatio:false,cutout:'66%',plugins:{legend:{position:'bottom',labels:{usePointStyle:true,boxWidth:7,padding:14,font:{family:'Manrope',size:10}}}}}});
  };
  draw('#severityLevelChart',data.severity);
  draw('#severityDamageChart',data.damage);
  draw('#analyticsDamage',data.damage);
  draw('#analyticsStatus',data.statuses);
  draw('#analyticsSeverity',data.severity);
  draw('#analyticsPriority',data.priority);
}

function bindComplaintQueue(containerId,filterId,sort,filterKey){
  const container=document.getElementById(containerId);
  const filter=document.getElementById(filterId);
  const load=async()=>{
    const params=new URLSearchParams({sort,per_page:'50'});
    if(filter.value)params.set(filterKey,filter.value);
    container.innerHTML='<div class="loading">Updating ranked reports…</div>';
    try{
      const data=await api(`/complaints?${params}`);
      container.innerHTML=data.items.length?data.items.map(item=>{
        const days=Math.max(0,Math.floor((Date.now()-new Date(item.created_at).getTime())/86400000));
        const level=filterKey==='priority'?item.priority_level:item.severity_level;
        return `<a class="priority-detail-row" href="/admin/complaints/${item.id}"><span class="priority-mark ${insightEscape(level.toLowerCase())}"></span><span class="priority-main"><strong>${insightEscape(item.code)} · ${insightEscape(item.damage_type)}</strong><small>${insightEscape(item.road_name)} · ${insightEscape(item.status.replaceAll('_',' '))}</small><span class="priority-factors">Severity ${Number(item.severity_score).toFixed(0)} · ${insightEscape(item.road_category)} road · ${Number(item.duplicate_count)} related · ${days} day${days===1?'':'s'} open</span></span><span class="priority-detail-score"><b>${Number(filterKey==='priority'?item.priority_score:item.severity_score).toFixed(0)}</b><small>${insightEscape(level)}</small></span></a>`;
      }).join(''):'<div class="empty-state"><strong>No matching complaints</strong>Try another level or clear the filter.</div>';
    }catch(error){container.innerHTML=`<div class="empty-state">${insightEscape(error.message)}</div>`;}
  };
  filter.addEventListener('change',load);
  load();
}
