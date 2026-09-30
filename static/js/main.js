window.api = async (path, options={}) => { const response = await fetch(`/api${path}`, {headers:{...(options.body instanceof FormData ? {}:{'Content-Type':'application/json'}),...(options.headers||{})},...options}); const data=await response.json().catch(()=>({})); if(!response.ok) throw new Error(data.error||`Request failed (HTTP ${response.status}).`); return data; };
window.toast=(message,kind='success')=>{const host=document.querySelector('#toastHost');if(!host)return;const node=document.createElement('div');node.className=`toast align-items-center text-bg-${kind} border-0`;node.innerHTML=`<div class="d-flex"><div class="toast-body"></div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;node.querySelector('.toast-body').textContent=message;host.append(node);new bootstrap.Toast(node).show();};

const addStylesheet = (href) => {
	const link=document.createElement('link');
	link.rel='stylesheet';
	link.href=href;
	document.head.append(link);
};

const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));

document.addEventListener('DOMContentLoaded',()=>{
	addStylesheet('/static/css/premium.css');
	addStylesheet('https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css');
	enhanceNavigation();
	setupSearch();
	setupNotifications();
});

function enhanceNavigation(){
	const sidebar=document.querySelector('.sidebar');
	const topbar=document.querySelector('.topbar');
	if(!sidebar||!topbar)return;
	const icons=['grid-1x2','plus-circle','files','map','people','bar-chart','clipboard-data','shield-check'];
	const current=window.location.pathname;
	sidebar.querySelectorAll('a').forEach((link,index)=>{
		const href=new URL(link.href,window.location.origin).pathname;
		const active=current===href||(href.endsWith('/complaints')&&current.includes('/complaints/'));
		if(active){link.classList.add('active');link.setAttribute('aria-current','page');}
		const icon=document.createElement('i');
		icon.className=`bi bi-${icons[index%icons.length]}`;
		icon.setAttribute('aria-hidden','true');
		link.prepend(icon);
	});
	if(sidebar.querySelector('a[href*="/municipal/"]')){
		[
			{href:'/municipal/priority',label:'Priority queue',icon:'speedometer2'},
			{href:'/municipal/severity',label:'Severity analysis',icon:'activity'},
			{href:'/municipal/analytics',label:'Analytics',icon:'bar-chart-line'}
		].forEach(item=>{
			const link=document.createElement('a');
			link.href=item.href;
			link.innerHTML=`<i class="bi bi-${item.icon}" aria-hidden="true"></i>${item.label}`;
			if(current===item.href){link.classList.add('active');link.setAttribute('aria-current','page');}
			sidebar.append(link);
		});
	}
	const actions=topbar.querySelector('.ms-auto');
	const brand=topbar.querySelector('.brand');
	if(actions&&brand){
		const search=document.createElement('div');
		search.className='topbar-search';
		search.innerHTML='<i class="bi bi-search" aria-hidden="true"></i><input id="globalSearch" type="search" autocomplete="off" aria-label="Search complaints" placeholder="Search complaints, roads, damage…"><div class="search-results" id="searchResults" role="listbox" hidden></div>';
		topbar.insertBefore(search,actions);
		const name=actions.querySelector('.small');
		if(name){
			const role=document.createElement('span');
			role.className='user-role';
			role.textContent=sidebar.querySelector('a[href*="municipal"]')?'Municipal authority':sidebar.querySelector('a[href*="citizen"]')?'Citizen':'Field team';
			name.after(role);
		}
	}
	const notificationButton=topbar.querySelector('#notificationButton');
	if(notificationButton){
		notificationButton.parentElement.classList.add('notification-wrap');
		const panel=document.createElement('div');
		panel.className='notification-panel';
		panel.id='notificationPanel';
		panel.hidden=true;
		panel.innerHTML='<div class="notification-heading"><span>Notifications</span><span id="notificationSummary"></span></div><div id="notificationItems"></div>';
		notificationButton.parentElement.append(panel);
	}
}

function setupSearch(){
	const input=document.querySelector('#globalSearch');
	const results=document.querySelector('#searchResults');
	if(!input||!results)return;
	let timer;
	const isMunicipal=Boolean(document.querySelector('.sidebar a[href*="municipal"]'));
	const isWorker=Boolean(document.querySelector('.sidebar a[href*="worker"]'));
	input.addEventListener('input',()=>{
		clearTimeout(timer);
		const term=input.value.trim();
		if(term.length<2){results.hidden=true;results.replaceChildren();return;}
		timer=setTimeout(async()=>{
			try{
				const data=await api(`/complaints?search=${encodeURIComponent(term)}&per_page=6`);
				results.replaceChildren();
				if(!data.items.length)results.innerHTML='<div class="search-hint">No matching complaints found.</div>';
				data.items.forEach(item=>{
					const link=document.createElement('a');
					link.className='search-result';
					link.href=isMunicipal?`/admin/complaints/${item.id}`:isWorker?'/worker/dashboard':`/citizen/complaints/${item.id}`;
					link.innerHTML=`<strong>${escapeHTML(item.code)} · ${escapeHTML(item.damage_type)}</strong><small>${escapeHTML(item.road_name)} · ${escapeHTML(item.status.replaceAll('_',' '))}</small>`;
					results.append(link);
				});
				results.hidden=false;
			}catch(error){results.innerHTML=`<div class="search-hint">${escapeHTML(error.message)}</div>`;results.hidden=false;}
		},220);
	});
	document.addEventListener('click',event=>{if(!event.target.closest('.topbar-search'))results.hidden=true;});
}

function setupNotifications(){
	const button=document.querySelector('#notificationButton');
	const panel=document.querySelector('#notificationPanel');
	const count=document.querySelector('#notificationCount');
	if(!button||!panel)return;
	const refresh=async(show=false)=>{
		try{
			const data=await api('/notifications');
			count.textContent=data.unread;
			const list=document.querySelector('#notificationItems');
			document.querySelector('#notificationSummary').textContent=data.unread?`${data.unread} unread`:'';
			list.replaceChildren();
			if(!data.items.length)list.innerHTML='<div class="search-hint">You are all caught up.</div>';
			data.items.forEach(item=>{
				const link=document.createElement('a');
				link.className=`notification-item${item.is_read?'':' unread'}`;
				link.href=item.link||'#';
				link.innerHTML=`<strong>${escapeHTML(item.title)}</strong><small>${escapeHTML(item.message)} · ${new Date(item.created_at).toLocaleString()}</small>`;
				link.addEventListener('click',()=>{if(!item.is_read)api(`/notifications/${item.id}/read`,{method:'POST'});});
				list.append(link);
			});
			if(show)panel.hidden=false;
		}catch(_){ }
	};
	button.setAttribute('aria-expanded','false');
	button.addEventListener('click',async()=>{
		const opening=panel.hidden;
		await refresh(opening);
		panel.hidden=!opening;
		button.setAttribute('aria-expanded',String(opening));
	});
	document.addEventListener('click',event=>{if(!event.target.closest('.notification-wrap')){panel.hidden=true;button.setAttribute('aria-expanded','false');}});
	refresh();
	setInterval(()=>refresh(),30000);
}
