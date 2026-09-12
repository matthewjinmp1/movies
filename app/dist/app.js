const $ = id => document.getElementById(id);
const DEFAULT_COLUMNS=['starred','primaryTitle','googleSearch','globalScore','filterScore','startYear','averageRating','numVotes','runtimeMinutes','genres'];
const state={view:'all',columns:[...DEFAULT_COLUMNS],sort:'numVotes',direction:'desc',page:1,size:50,q:'',filters:[],visibleFilters:['genres','averageRating','startYear']};
let meta, data, controller, debounce;
const format = new Intl.NumberFormat();
const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function persist(){try{localStorage.setItem('frame-preferences',JSON.stringify({columns:state.columns,sort:state.sort,direction:state.direction,size:state.size,visibleFilters:state.visibleFilters,scoreColumnAdded:true,googleColumnAdded:true,globalColumnAdded:true,starColumnAdded:true,view:state.view}));}catch{}}
function cell(row,key){if(key==='starred')return `<button class="save-star" data-star="${esc(row.tconst)}" aria-pressed="${row.starred}" aria-label="${row.starred?'Unstar':'Star'} ${esc(row.primaryTitle)}" title="${row.starred?'Remove from':'Add to'} starred movies">${row.starred?'★':'☆'}</button>`;if(key==='googleSearch'){const query=[row.primaryTitle,row.startYear,'movie'].filter(v=>v!==null&&v!=='').join(' ');return `<a class="google-search" href="https://www.google.com/search?q=${encodeURIComponent(query)}" target="_self" data-google-search aria-label="Search Google for ${esc(row.primaryTitle)}${row.startYear?' ('+row.startYear+')':''}">Search Google</a>`;}const v=row[key];if(v===null)return '<span class="null">—</span>';if(key==='globalScore')return `<details class="score-detail"><summary aria-label="Global score ${Number(v).toFixed(1)} out of 100; show breakdown">${Number(v).toFixed(1)}<span>/100</span></summary><div>${row.globalBreakdown.map(c=>`<p><span>${esc(c.label)} <small>×${c.weight}${c.label==='Genres'?' · average points '+(c.raw===null?'missing':Number(c.raw).toFixed(2)):''}</small></span><strong>${Number(c.score).toFixed(1)}</strong></p>`).join('')}<small>Weighted average across the full library. Weight 0 has no effect.</small></div></details>`;if(key==='filterScore')return `<details class="score-detail"><summary aria-label="Filter score ${Number(v).toFixed(1)} out of 100; show breakdown">${Number(v).toFixed(1)}<span>/100</span></summary><div>${row.scoreBreakdown.map(c=>`<p><span>${esc(c.label)} <small>×${c.weight}</small></span><strong>${Number(c.score).toFixed(1)}</strong></p>`).join('')}<small>Weighted average of active fields</small></div></details>`;if(key==='primaryTitle')return `<a href="https://www.imdb.com/title/${encodeURIComponent(row.tconst)}/" target="_blank" rel="noreferrer">${esc(v)}</a>`;if(key==='averageRating')return `<span class="rating"><span class="star" aria-hidden="true">★</span>${Number(v).toFixed(1)}</span>`;if(key==='numVotes')return format.format(v);if(key==='genres')return v.split(',').map(g=>`<span class="genre-tag">${esc(g)}</span>`).join('');if(key==='isAdult')return v?'Yes':'No';return esc(v);}
function renderTable(){if(!data)return;$('score-rules').innerHTML=data.scoreRules.length?data.scoreRules.map(r=>`<li><strong>${esc(r.label)} (weight ${r.weight}):</strong> ${esc(r.rule)}</li>`).join(''):'<li>Choose a filter value or enter a search to calculate scores.</li>';const columns=state.columns.map(k=>meta.columns.find(c=>c.key===k));$('movies-table').querySelector('thead').innerHTML='<tr>'+columns.map(c=>c.kind==='action'?`<th class="action-heading">${esc(c.label)}</th>`:`<th class="${c.kind==='number'?'numeric':''}" aria-sort="${state.sort===c.key?(state.direction==='asc'?'ascending':'descending'):'none'}"><button data-sort="${c.key}">${esc(c.label)}${state.sort===c.key?(state.direction==='asc'?' ↑':' ↓'):''}</button></th>`).join('')+'</tr>';$('movies-table').querySelector('tbody').innerHTML=data.rows.map(r=>'<tr>'+columns.map(c=>`<td class="${c.kind==='number'?'numeric ':''}${c.key==='primaryTitle'?'title-cell':''}" title="${c.kind==='action'?(c.key==='starred'?'Save movie':'Search in this tab'):r[c.key]===null?'Not available':esc(r[c.key])}">${cell(r,c.key)}</td>`).join('')+'</tr>').join('');$('empty').hidden=data.total!==0;$('movies-table').hidden=data.total===0;$('results-title').textContent=state.view==='starred'?'Starred movies':state.q.trim()||state.filters.length?'Matching movies':'All movies';$('starred-count').textContent=format.format(data.starredCount);for(const b of document.querySelectorAll('[data-view]'))b.setAttribute('aria-pressed',String(b.dataset.view===state.view));$('view-note').textContent=state.view==='starred'?'Your saved movies. Current filters also apply here.':'Star movies to save them for later.';$('empty').querySelector('strong').textContent=state.view==='starred'&&!data.starredCount?'No starred movies yet':'No movies found';$('empty').querySelector('p').textContent=state.view==='starred'&&!data.starredCount?'Go to All movies and click a star to save a movie.':'Try a different title or remove a filter.';$('result-count').textContent=format.format(data.total);$('result-summary').textContent=data.total?`${format.format((data.page-1)*data.size+1)}–${format.format(Math.min(data.page*data.size,data.total))} of ${format.format(data.total)} movies`:'0 matching movies';$('page').value=data.page;$('page').max=data.pages;$('pages').textContent=`of ${format.format(data.pages)}`;for(const id of ['first','previous'])$(id).disabled=data.page<=1;for(const id of ['next','last'])$(id).disabled=data.page>=data.pages;$('status').textContent=$('result-summary').textContent;}
async function load(){controller?.abort();controller=new AbortController();const current=controller;$('error').hidden=true;$('movies-table').setAttribute('aria-busy','true');document.querySelector('.results').classList.add('loading');const params=new URLSearchParams({...state,scoring:JSON.stringify(state.scoring),filters:JSON.stringify(state.filters.filter(f=>['missing','present'].includes(f.op)||String(f.value).trim()!==''))});try{const response=await fetch('/api/movies?'+params,{signal:current.signal});const result=await response.json();if(!response.ok)throw new Error(result.error);if(current!==controller)return;data=result;state.page=data.page;renderTable();}catch(e){if(e.name!=='AbortError'){$('error').textContent=e.message+' Change your filters or reload to try again.';$('error').hidden=false;}}finally{if(current===controller){document.querySelector('.results').classList.remove('loading');$('movies-table').setAttribute('aria-busy','false');}}}
function refresh(){state.page=1;clearTimeout(debounce);debounce=setTimeout(load,250);}
function syncSort(){$('sort').value=state.sort;$('direction').textContent=state.direction==='desc'?'↓':'↑';$('direction').setAttribute('aria-label',`Sort ${state.direction==='desc'?'ascending':'descending'}`);persist();}
function renderColumns(){
 const ordered=[...state.columns.map(key=>meta.columns.find(c=>c.key===key)),...meta.columns.filter(c=>!state.columns.includes(c.key))];
 $('column-options').innerHTML='<p class="muted">Shown in table order. Use arrows to move a column left or right.</p>'+ordered.map(c=>{
  const index=state.columns.indexOf(c.key),visible=index!==-1;
  return `<div class="column-option"><label><input type="checkbox" value="${c.key}" ${visible?'checked':''} ${state.columns.length===1&&visible?'disabled':''}>${esc(c.label)}</label>${visible?`<div class="column-moves"><button type="button" data-move-column="${c.key}" data-step="-1" aria-label="Move ${esc(c.label)} left" title="Move left" ${index===0?'disabled':''}>←</button><button type="button" data-move-column="${c.key}" data-step="1" aria-label="Move ${esc(c.label)} right" title="Move right" ${index===state.columns.length-1?'disabled':''}>→</button></div>`:''}</div>`;
 }).join('');
}
const FILTERS = [
  {key:'genres',label:'Genres'},
  {key:'averageRating',label:'IMDb rating'},
  {key:'numVotes',label:'Vote count'},
  {key:'startYear',label:'Release year'},
  {key:'runtimeMinutes',label:'Runtime'},
  {key:'isAdult',label:'Adult content'},
];
const defaults = key => key==='genres'?{values:[],mode:'any_of'}:key==='averageRating'?{min:'',status:'any'}:key==='numVotes'?{min:''}:key==='isAdult'?{value:''}:{min:'',max:''};
const filterValues = Object.fromEntries(FILTERS.map(f=>[f.key,defaults(f.key)]));
let filterSaving = Promise.resolve();
function saveFilters(){
  const payload=JSON.stringify({version:1,q:state.q,visibleFilters:state.visibleFilters,values:filterValues,scoring:state.scoring});
  $('filter-save-status').textContent='Saving filters…';
  filterSaving=filterSaving.catch(()=>{}).then(async()=>{
    const response=await fetch('/api/filters',{method:'PUT',headers:{'Content-Type':'application/json'},body:payload,keepalive:true});
    if(!response.ok)throw new Error('Save failed');
  });
  const current=filterSaving;
  current.then(()=>{if(current===filterSaving)$('filter-save-status').textContent='Filters saved on this computer';}).catch(()=>{if(current===filterSaving)$('filter-save-status').textContent='Could not save filters. Change a filter to retry.';});
}
async function restoreFilters(){
  const response=await fetch('/api/filters');
  if(!response.ok)throw new Error('Could not restore saved filters.');
  const saved=await response.json();
  if(saved){
    state.q=saved.q;state.visibleFilters=saved.visibleFilters;state.scoring=saved.scoring||structuredClone(meta.scoringDefaults);
    for(const f of FILTERS)filterValues[f.key]={...defaults(f.key),...saved.values[f.key]};
    state.filters=compileFilters();$('search').value=state.q;
    $('filter-save-status').textContent='Filters restored from this computer';
  }else saveFilters();
}
function renderFilterPicker(){
  $('filter-options').innerHTML=FILTERS.map(f=>`<label><input type="checkbox" value="${f.key}" ${state.visibleFilters.includes(f.key)?'checked':''}>${f.label}</label>`).join('');
  $('filter-picker-count').textContent=state.visibleFilters.length;
}
function numberControl(key,part,label,placeholder,min=0,max='',step=1){
  return `<label class="filter-control">${label}<input type="number" data-value="${part}" aria-label="${label}" min="${min}" ${max!==''?`max="${max}"`:''} step="${step}" placeholder="${placeholder}" value="${esc(filterValues[key][part])}"></label>`;
}
function renderFilters(){
  renderFilterPicker();
  $('filter-list').innerHTML=state.visibleFilters.map(key=>{
    const f=FILTERS.find(f=>f.key===key),v=filterValues[key];let controls='';
    if(key==='genres'){
      controls=`<label class="filter-control">Match movies with<select data-value="mode" aria-label="Genre matching"><option value="any_of" ${v.mode==='any_of'?'selected':''}>Any selected genre</option><option value="all_of" ${v.mode==='all_of'?'selected':''}>All selected genres</option></select></label><div class="genre-options" role="group" aria-label="Select genres">${meta.genres.map(g=>`<label><input type="checkbox" data-genre="${esc(g)}" ${v.values.includes(g)?'checked':''}>${esc(g)}</label>`).join('')}</div><p class="genre-summary">${v.values.length?esc(v.values.join(', ')):'All genres'}</p>`;
    }else if(key==='averageRating'){
      controls=`<label class="filter-control">Rating availability<select data-value="status" aria-label="Rating availability"><option value="any" ${v.status==='any'?'selected':''}>All movies</option><option value="rated" ${v.status==='rated'?'selected':''}>Rated movies only</option><option value="unrated" ${v.status==='unrated'?'selected':''}>Unrated movies only</option></select></label>`;
      if(v.status!=='unrated')controls+=numberControl(key,'min','Minimum IMDb rating','Any rating',1,10,0.1);
    }else if(key==='numVotes')controls=numberControl(key,'min','Minimum votes','Any vote count')+'<p class="control-hint">Require more votes for a larger audience sample.</p>';
    else if(key==='startYear')controls='<div class="filter-range">'+numberControl(key,'min','From year','Any',1800,9999)+numberControl(key,'max','To year','Any',1800,9999)+'</div>';
    else if(key==='runtimeMinutes')controls='<div class="filter-range">'+numberControl(key,'min','Min minutes','Any')+numberControl(key,'max','Max minutes','Any')+'</div>';
    else controls=`<label class="filter-control">Include<select data-value="value" aria-label="Adult content"><option value="" ${v.value===''?'selected':''}>All movies</option><option value="0" ${v.value==='0'?'selected':''}>Exclude adult content</option><option value="1" ${v.value==='1'?'selected':''}>Adult content only</option></select></label>`;
    return `<section class="custom-filter" data-filter="${key}" aria-label="${f.label} filter"><div class="section-top"><h3>${f.label}</h3><button class="remove-filter" data-hide="${key}" aria-label="Hide ${f.label} filter">×</button></div>${controls}<p class="filter-validation" role="status" hidden></p></section>`;
  }).join('');
}
function compileFilters(){
  const filters=[];
  for(const key of state.visibleFilters){
    const v=filterValues[key];
    if(key==='genres'){if(v.values.length)filters.push({field:key,op:v.mode,value:v.values});}
    else if(key==='isAdult'){if(v.value!=='')filters.push({field:key,op:'eq',value:v.value});}
    else if(key==='averageRating'&&v.status==='unrated')filters.push({field:key,op:'missing'});
    else{
      if(key==='averageRating'&&v.status==='rated')filters.push({field:key,op:'present'});
      if(v.min!=='')filters.push({field:key,op:'gte',value:v.min});
      if(v.max!==undefined&&v.max!=='')filters.push({field:key,op:'lte',value:v.max});
    }
  }
  return filters;
}
function applyFilters(){
  let valid=true;
  for(const panel of $('filter-list').querySelectorAll('[data-filter]')){
    const value=filterValues[panel.dataset.filter];let message='';
    for(const input of panel.querySelectorAll('input[type="number"]')){
      if(!input.validity.valid){message=`Check ${input.getAttribute('aria-label').toLowerCase()}.`;break;}
    }
    if(!message&&value.min!==''&&value.max!==undefined&&value.max!==''&&Number(value.min)>Number(value.max))message='The minimum must not exceed the maximum.';
    const note=panel.querySelector('.filter-validation');note.textContent=message;note.hidden=!message;
    if(message)valid=false;
  }
  clearTimeout(debounce);
  if(!valid){controller?.abort();return;}
  state.filters=compileFilters();saveFilters();refresh();
}
function clearFilters(){
  for(const f of FILTERS)filterValues[f.key]=defaults(f.key);
  state.filters=[];state.q='';$('search').value='';renderFilters();saveFilters();refresh();
}
function setFilterVisibility(key,visible){
  if(visible&&!state.visibleFilters.includes(key))state.visibleFilters.push(key);
  if(!visible){state.visibleFilters=state.visibleFilters.filter(k=>k!==key);filterValues[key]=defaults(key);}
  renderFilters();persist();applyFilters();
}
function renderScoringSettings(){
  const settings=state.scoring;
  $('weight-settings').innerHTML=[...FILTERS,{key:'search',label:'Title search'}].map(f=>`<label>${f.label}<input aria-label="${f.label} weight" name="weight-${f.key}" type="number" min="0" max="10" step="0.1" required value="${settings.weights[f.key]}"></label>`).join('');
  for(const key of ['genrePenalty','ratingPower','votesCap','votesScale','yearMode','runtimeMode','rangeEdgeScore'])$('scoring-form').elements[key].value=settings[key];
}
$('scoring-form').addEventListener('submit',e=>{
  e.preventDefault();const form=e.currentTarget;if(!form.reportValidity())return;
  const settings=structuredClone(state.scoring);
  for(const field of Object.keys(settings.weights))settings.weights[field]=Number(form.elements['weight-'+field].value);
  for(const key of ['genrePenalty','ratingPower','votesCap','rangeEdgeScore'])settings[key]=Number(form.elements[key].value);
  for(const key of ['votesScale','yearMode','runtimeMode'])settings[key]=form.elements[key].value;
  state.scoring=settings;saveFilters();refresh();$('scoring-applied').textContent='Scoring settings applied.';
});
$('reset-scoring').onclick=()=>{state.scoring=structuredClone(meta.scoringDefaults);renderScoringSettings();saveFilters();refresh();$('scoring-applied').textContent='Default scoring restored.';};
async function init(){try{const response=await fetch('/api/meta');if(!response.ok)throw new Error('Could not load the library.');meta=await response.json();state.scoring=structuredClone(meta.scoringDefaults);meta.columns.unshift({key:'starred',label:'Star',kind:'action'});meta.columns.splice(2,0,{key:'googleSearch',label:'Google search',kind:'action'});try{const saved=JSON.parse(localStorage.getItem('frame-preferences'));if(saved){if(['all','starred'].includes(saved.view))state.view=saved.view;if(!saved.starColumnAdded)state.columns.unshift('starred');if(Array.isArray(saved.visibleFilters))state.visibleFilters=[...new Set(saved.visibleFilters)].filter(k=>FILTERS.some(f=>f.key===k));if(Array.isArray(saved.columns)){const cols=[...new Set(saved.columns)].filter(k=>meta.columns.some(c=>c.key===k));if(cols.length)state.columns=cols;}if(!saved.starColumnAdded&&!state.columns.includes('starred'))state.columns.unshift('starred');if(!saved.globalColumnAdded&&!state.columns.includes('globalScore'))state.columns.splice(1,0,'globalScore');if(!saved.scoreColumnAdded&&!state.columns.includes('filterScore'))state.columns.splice(1,0,'filterScore');if(!saved.googleColumnAdded&&!state.columns.includes('googleSearch'))state.columns.splice(1,0,'googleSearch');if(meta.columns.some(c=>c.key===saved.sort&&c.kind!=='action'))state.sort=saved.sort;if(['asc','desc'].includes(saved.direction))state.direction=saved.direction;if([25,50,100,250].includes(saved.size))state.size=saved.size;}}catch{}await restoreFilters();$('library-count').textContent=format.format(meta.total);$('snapshot').textContent=`Snapshot · ${meta.snapshot}`;$('sort').innerHTML=meta.columns.filter(c=>c.kind!=='action').map(c=>`<option value="${c.key}">Sort: ${esc(c.label)}</option>`).join('');$('page-size').value=state.size;const returnView=history.state?.movieReturn;if(returnView&&Number.isInteger(returnView.page)&&returnView.page>0)state.page=returnView.page;syncSort();renderColumns();renderFilters();renderScoringSettings();await initGlobalSettings();await load();if(returnView){window.scrollTo(returnView.windowX||0,returnView.windowY||0);document.querySelector('.table-scroll').scrollLeft=returnView.scrollLeft||0;history.replaceState(null,'');}}catch(e){$('error').hidden=false;$('error').textContent=e.message;}}
$('search').addEventListener('input',e=>{state.q=e.target.value;saveFilters();refresh();});
$('sort').addEventListener('change',e=>{state.sort=e.target.value;if(['filterScore','globalScore'].includes(state.sort)){state.direction='desc';if(!state.columns.includes(state.sort)){state.columns.splice(1,0,state.sort);renderColumns();}}syncSort();refresh();});
$('direction').onclick=()=>{state.direction=state.direction==='asc'?'desc':'asc';syncSort();refresh();};
$('movies-table').addEventListener('click',e=>{if(e.target.closest('[data-google-search]')){const scroller=document.querySelector('.table-scroll');history.replaceState({movieReturn:{page:state.page,windowX:window.scrollX,windowY:window.scrollY,scrollLeft:scroller.scrollLeft}},'');return;}const b=e.target.closest('[data-sort]');if(!b)return;state.direction=state.sort===b.dataset.sort?(state.direction==='asc'?'desc':'asc'):(['filterScore','globalScore'].includes(b.dataset.sort)?'desc':'asc');state.sort=b.dataset.sort;syncSort();refresh();});
$('columns-button').onclick=()=>{const open=$('columns-menu').hidden;$('columns-menu').hidden=!open;$('columns-button').setAttribute('aria-expanded',String(open));};
document.addEventListener('click',e=>{if(!e.target.closest('.columns-wrap')){$('columns-menu').hidden=true;$('columns-button').setAttribute('aria-expanded','false');}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('columns-menu').hidden){$('columns-menu').hidden=true;$('columns-button').setAttribute('aria-expanded','false');$('columns-button').focus();}});
$('column-options').addEventListener('change',e=>{if(e.target.checked)state.columns.push(e.target.value);else state.columns=state.columns.filter(k=>k!==e.target.value);persist();renderColumns();renderTable();});
$('column-options').addEventListener('click',e=>{
 const button=e.target.closest('[data-move-column]');if(!button||button.disabled)return;
 const key=button.dataset.moveColumn,index=state.columns.indexOf(key),step=Number(button.dataset.step),next=index+step;
 if(index<0||next<0||next>=state.columns.length)return;
 [state.columns[index],state.columns[next]]=[state.columns[next],state.columns[index]];
 persist();renderColumns();renderTable();
 const buttons=[...$('column-options').querySelectorAll('[data-move-column]')].filter(b=>b.dataset.moveColumn===key);
 (buttons.find(b=>Number(b.dataset.step)===step&&!b.disabled)||buttons.find(b=>!b.disabled))?.focus();
 $('status').textContent=`${meta.columns.find(c=>c.key===key).label} moved to column ${next+1} of ${state.columns.length}.`;
});
$('reset-columns').onclick=()=>{state.columns=[...DEFAULT_COLUMNS];persist();renderColumns();renderTable();};
$('filters-button').onclick=()=>{const open=$('filters-menu').hidden;$('filters-menu').hidden=!open;$('filters-button').setAttribute('aria-expanded',String(open));};
document.addEventListener('click',e=>{if(!e.target.closest('.filter-picker-wrap')){$('filters-menu').hidden=true;$('filters-button').setAttribute('aria-expanded','false');}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('filters-menu').hidden){$('filters-menu').hidden=true;$('filters-button').setAttribute('aria-expanded','false');$('filters-button').focus();}});
$('filter-options').addEventListener('change',e=>{if(e.target.type==='checkbox')setFilterVisibility(e.target.value,e.target.checked);});
$('filter-list').addEventListener('click',e=>{const button=e.target.closest('[data-hide]');if(button)setFilterVisibility(button.dataset.hide,false);});
$('filter-list').addEventListener('change',e=>{
  const panel=e.target.closest('[data-filter]');if(!panel)return;
  const key=panel.dataset.filter,v=filterValues[key];
  if(e.target.dataset.genre){const genre=e.target.dataset.genre;v.values=e.target.checked?[...v.values,genre]:v.values.filter(g=>g!==genre);panel.querySelector('.genre-summary').textContent=v.values.length?v.values.join(', '):'All genres';}
  else if(e.target.dataset.value){v[e.target.dataset.value]=e.target.value;if(e.target.dataset.value==='status')renderFilters();}
  applyFilters();
});
$('filter-list').addEventListener('input',e=>{if(e.target.type==='number'){const key=e.target.closest('[data-filter]').dataset.filter;filterValues[key][e.target.dataset.value]=e.target.value;applyFilters();}});
$('clear-filters').onclick=clearFilters;$('empty-reset').onclick=clearFilters;
$('page-size').onchange=e=>{state.size=Number(e.target.value);persist();refresh();};
async function go(page){if(!data)return;clearTimeout(debounce);state.page=Math.max(1,Math.min(data.pages,page||1));await load();document.querySelector('.toolbar').scrollIntoView({block:'start'});}
$('first').onclick=()=>go(1);$('previous').onclick=()=>go(state.page-1);$('next').onclick=()=>go(state.page+1);$('last').onclick=()=>go(data.pages);$('page').onchange=e=>go(Number(e.target.value));
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{state.view=button.dataset.view;persist();refresh();});
$('movies-table').addEventListener('click',async e=>{
 const button=e.target.closest('[data-star]');if(!button||button.disabled)return;
 const selected=button.getAttribute('aria-pressed')!=='true';button.disabled=true;
 try{
  const response=await fetch('/api/starred',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tconst:button.dataset.star,starred:selected})});
  const result=await response.json();if(!response.ok)throw new Error(result.error);
  clearTimeout(debounce);await load();
 }catch(error){$('error').textContent='Could not save movie: '+error.message;$('error').hidden=false;button.disabled=false;}
});
init();
