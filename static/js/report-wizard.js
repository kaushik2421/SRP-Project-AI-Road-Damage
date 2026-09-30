const escapeReportText=value=>String(value??'').replace(/[&<>"']/g,character=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));

document.addEventListener('DOMContentLoaded',()=>{
  const form=document.querySelector('#reportForm');
  if(!form)return;
  const steps=[...form.querySelectorAll('[data-wizard-step]')];
  const indicators=[...document.querySelectorAll('#wizardSteps li')];
  const fileInput=document.querySelector('#imageInput');
  const dropZone=document.querySelector('#dropZone');
  const preview=document.querySelector('#imagePreview');
  const removeButton=document.querySelector('#removeImage');
  const imageMeta=document.querySelector('#imageMeta');
  let activeStep=0;
  let map;
  let marker;

  const setStep=index=>{
    activeStep=index;
    steps.forEach((step,stepIndex)=>step.hidden=stepIndex!==index);
    indicators.forEach((indicator,stepIndex)=>{
      indicator.classList.toggle('active',stepIndex===index);
      indicator.classList.toggle('complete',stepIndex<index);
      if(stepIndex===index)indicator.setAttribute('aria-current','step');else indicator.removeAttribute('aria-current');
    });
    if(index===2)refreshReview();
    if(index===1&&map)setTimeout(()=>map.invalidateSize(),80);
  };

  const validateStep=()=>{
    if(activeStep===0&&!fileInput.files.length){toast('Add a road photo before continuing.','warning');return false;}
    if(activeStep===1){
      const fields=[...steps[1].querySelectorAll('[required]')];
      for(const field of fields){if(!field.checkValidity()){field.reportValidity();return false;}}
      if(!document.querySelector('#latitude').value){toast('Set the location using GPS or the map.','warning');return false;}
    }
    return true;
  };

  form.querySelectorAll('[data-next]').forEach(button=>button.addEventListener('click',()=>{if(validateStep())setStep(Math.min(activeStep+1,2));}));
  form.querySelectorAll('[data-back]').forEach(button=>button.addEventListener('click',()=>setStep(Math.max(activeStep-1,0))));

  const setImage=file=>{
    if(!file)return;
    const validTypes=['image/jpeg','image/png','image/webp'];
    if(!validTypes.includes(file.type)){toast('Choose a JPG, PNG, or WebP image.','warning');fileInput.value='';return;}
    if(file.size>10*1024*1024){toast('The image must be 10 MB or smaller.','warning');fileInput.value='';return;}
    const prior=preview.dataset.objectUrl;
    if(prior)URL.revokeObjectURL(prior);
    const objectUrl=URL.createObjectURL(file);
    preview.dataset.objectUrl=objectUrl;
    preview.src=objectUrl;
    preview.hidden=false;
    dropZone.classList.add('has-image');
    document.querySelector('#uploadTitle').textContent=file.name;
    imageMeta.textContent=`${(file.size/1024/1024).toFixed(2)} MB Â· Ready to upload`;
    removeButton.hidden=false;
  };

  fileInput.addEventListener('change',()=>setImage(fileInput.files[0]));
  removeButton.addEventListener('click',()=>{
    if(preview.dataset.objectUrl)URL.revokeObjectURL(preview.dataset.objectUrl);
    fileInput.value='';preview.removeAttribute('src');preview.hidden=true;dropZone.classList.remove('has-image');
    document.querySelector('#uploadTitle').textContent='Drop a photo here or browse';
    imageMeta.textContent='A photo is required to submit your report.';removeButton.hidden=true;
  });
  ['dragenter','dragover'].forEach(name=>dropZone.addEventListener(name,event=>{event.preventDefault();dropZone.classList.add('dragging');}));
  ['dragleave','drop'].forEach(name=>dropZone.addEventListener(name,event=>{event.preventDefault();dropZone.classList.remove('dragging');}));
  dropZone.addEventListener('drop',event=>{
    const file=event.dataTransfer.files[0];
    if(file){const transfer=new DataTransfer();transfer.items.add(file);fileInput.files=transfer.files;setImage(file);}
  });
  dropZone.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();fileInput.click();}});

  const setPoint=(latitude,longitude)=>{
    document.querySelector('#latitude').value=latitude;
    document.querySelector('#longitude').value=longitude;
    document.querySelector('#locationText').textContent=`Location selected Â· ${Number(latitude).toFixed(6)}, ${Number(longitude).toFixed(6)}`;
    if(marker)marker.setLatLng([latitude,longitude]);else marker=L.marker([latitude,longitude]).addTo(map);
    map.setView([latitude,longitude],16);
  };
  const mapElement=document.querySelector('#reportMap');
  if(typeof L!=='undefined'&&mapElement){
    map=L.map(mapElement).setView([20.5937,78.9629],5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'Â© OpenStreetMap contributors',maxZoom:19}).addTo(map);
    map.on('click',event=>setPoint(event.latlng.lat,event.latlng.lng));
  }else if(mapElement){mapElement.innerHTML='<div class="empty-state">Map tiles are unavailable. GPS can still set the report location.</div>';}
  document.querySelector('#locateButton').addEventListener('click',()=>{
    if(!navigator.geolocation){toast('Geolocation is not supported. Select a point on the map.','warning');return;}
    navigator.geolocation.getCurrentPosition(position=>setPoint(position.coords.latitude,position.coords.longitude),()=>toast('Location unavailable. Select a point on the map.','warning'),{enableHighAccuracy:true,timeout:10000});
  });

  function refreshReview(){
    const file=fileInput.files[0];
    document.querySelector('#reviewImage').src=preview.src;
    document.querySelector('#reviewDetails').innerHTML=[
      ['Photo',escapeReportText(file?.name||'')],
      ['Road',escapeReportText(document.querySelector('#roadName').value)],
      ['Category',escapeReportText(document.querySelector('#roadCategory').value)],
      ['Location',escapeReportText(document.querySelector('#locationText').textContent.replace('Location selected Â· ','').trim())],
      ['Description',escapeReportText(document.querySelector('#description').value)]
    ].map(([label,value])=>`<div><dt>${label}</dt><dd>${value}</dd></div>`).join('');
  }

  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(!validateStep())return;
    setStepIndicator(3);
    form.hidden=true;
    document.querySelector('#processing').hidden=false;
    try{
      const result=await api('/complaints',{method:'POST',body:new FormData(form)});
      const stages=document.querySelector('#analysisStages');
      stages.innerHTML='<li class="complete">Photo and location received</li><li class="complete">Detection response received</li><li class="complete">Severity and priority calculated</li><li class="complete">Duplicate check completed</li>';
      document.querySelector('#processing').hidden=true;
      indicators[3].classList.add('complete');
      setStepIndicator(4);
      renderResult(result);
      document.querySelector('#reportResult').hidden=false;
      toast('Road report submitted.','success');
    }catch(error){
      document.querySelector('#processing').hidden=true;
      form.hidden=false;
      setStep(2);
      toast(error.message,'danger');
    }
  });

  function setStepIndicator(index){
    indicators.forEach((item,itemIndex)=>{
      item.classList.toggle('active',itemIndex===index);
      item.classList.toggle('complete',itemIndex<index);
      if(itemIndex===index)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
    });
  }

  function imageUrl(path){return `/api/uploads/${path.split('/').map(encodeURIComponent).join('/')}`;}
  function renderResult(result){
    const severity=Math.max(0,Math.min(100,Number(result.severity_score)||0));
    const detections=result.detections||[];
    const detectionList=detections.length?detections.map(detection=>`<li><strong>${escapeReportText(detection.class_name)}</strong><span>${Math.round(Number(detection.confidence)*100)}% confidence</span></li>`).join(''):'<li class="no-detection">No road-damage detections were returned.</li>';
    const aiMessage=result.ai_warning?`<div class="ai-warning"><strong>AI model not configured</strong><span>${escapeReportText(result.ai_warning)}</span></div>`:`<div class="ai-ready"><i class="bi bi-check-circle" aria-hidden="true"></i> Model analysis returned ${detections.length} detection${detections.length===1?'':'s'}.</div>`;
    const duplicate=result.duplicate?`<p class="duplicate-note">Possible duplicate of <strong>${escapeReportText(result.duplicate.code)}</strong>, ${Number(result.duplicate.distance_meters).toFixed(0)} m away.</p>`:'<p class="duplicate-note">No matching nearby report was identified.</p>';
    document.querySelector('#reportResult').innerHTML=`
      <div class="result-heading"><span class="section-kicker">STEP 05 Â· REPORT RECEIVED</span><h2>Report ${escapeReportText(result.code)} is on record</h2><p>Its status and repair progress will be available in your report history.</p></div>
      ${aiMessage}
      <div class="result-grid">
        <section class="result-visual"><div class="result-images"><figure><img src="${imageUrl(result.original_image)}" alt="Uploaded road evidence"><figcaption>Submitted photo</figcaption></figure>${result.detected_image?`<figure><img src="${imageUrl(result.detected_image)}" alt="AI detection image"><figcaption>AI detection view</figcaption></figure>`:''}</div><div class="detection-summary"><h3>Detection results</h3><ul>${detectionList}</ul></div></section>
        <section class="result-scores"><div class="score-feature"><span class="section-kicker">AI SEVERITY</span><div class="score-gauge" style="--score:${severity}%"><b>${severity.toFixed(0)}<small>/100</small></b></div><strong>${escapeReportText(result.severity_level)}</strong><p>Estimated damage seriousness, based on available model detections and road category.</p></div><div class="priority-feature"><span class="section-kicker">REPAIR PRIORITY</span><strong>${Number(result.priority_score).toFixed(0)} <small>/ 100</small></strong><span class="priority-label">${escapeReportText(result.priority_level)} PRIORITY</span><p>Response urgency also reflects road importance and related reports.</p></div>${duplicate}</section>
      </div>
      <a class="btn btn-primary" href="/citizen/complaints/${result.id}">Track this report</a>
    `;
  }
});
