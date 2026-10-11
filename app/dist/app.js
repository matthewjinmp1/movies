const $ = id => document.getElementById(id);
const DEFAULT_COLUMNS=['starred','blocked','primaryTitle','myRating','predictedRating','googleSearch','globalRank','globalScore','filterScore','startYear','averageRating','numVotes','runtimeMinutes','genres'];
const state={view:'all',columns:[...DEFAULT_COLUMNS],sort:'numVotes',direction:'desc',page:1,size:50,q:'',filters:[],visibleFilters:['genres','averageRating','startYear']};
let meta, data, controller, debounce, columnWidths={};
const format = new Intl.NumberFormat();
const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const savedViewsNote = document.getElementById('view-note');
if (savedViewsNote && !document.querySelector('[data-view="seen"]')) savedViewsNote.insertAdjacentHTML('beforebegin','<button data-view="seen" aria-pressed="false">✓ Seen <span id="seen-count">0</span></button>');
savedViewsNote.insertAdjacentHTML('beforebegin','<button data-view="blocked" aria-pressed="false">Blocked <span id="blocked-count">0</span></button>');
const basePersist = persist;
persist = () => { if (!state.columns.includes('seen')) state.columns.splice(Math.min(1,state.columns.length),0,'seen'); basePersist(); };
try { const savedPreferences = JSON.parse(localStorage.getItem('frame-preferences')); if (savedPreferences?.view === 'seen') state.view = 'seen'; } catch {}
function persist(){try{localStorage.setItem('frame-preferences',JSON.stringify({columns:state.columns,sort:state.sort,direction:state.direction,size:state.size,visibleFilters:state.visibleFilters,scoreColumnAdded:true,googleColumnAdded:true,globalRankColumnAdded:true,globalColumnAdded:true,starColumnAdded:true,blockColumnAdded:true,ratingColumnAdded:true,predictedColumnAdded:true,view:state.view,columnWidths}));}catch{}}
// Expanding a long cell replaces its preview with the full text, so nothing is shown twice.
function expandableText(preview,full){return preview===full?esc(full):`<details class="mdb-text"><summary><span class="mdb-preview">${esc(preview)}</span><span class="mdb-full">${esc(full)}</span></summary></details>`;}
function cell(row,key){if(enrichmentSpec(key)){const v=row[key];if(v===null||v===undefined||Array.isArray(v)&&!v.length)return '<span class="null">—</span>';if(key==='mdbAvailable')return v?'Downloaded':'Not downloaded';if(Array.isArray(v))return expandableText(v.slice(0,2).join(', ')+(v.length>2?' …':''),v.join(', '));if(['poster','trailer'].includes(key)){try{const url=new URL(v);if(url.protocol!=='https:'&&url.protocol!=='http:')return '—';return `<a href="${esc(url.href)}" target="_blank" rel="noreferrer">${key==='poster'?`<img class="movie-poster" src="${esc(url.href)}" loading="lazy" alt="${esc(row.primaryTitle)} poster">`:'Watch trailer'}</a>`;}catch{return '—';}}if(['description','tagline','awards'].includes(key))return expandableText(String(v).slice(0,70)+(String(v).length>70?'…':''),String(v));if(enrichmentSpec(key).kind==='number')return format.format(v);return esc(v);}if(key==='blocked')return `<button data-blocked="${esc(row.tconst)}" aria-pressed="${row.blocked}" aria-label="${row.blocked?'Unblock':'Block'} ${esc(row.primaryTitle)}" title="${row.blocked?'Unblock movie':'Block movie'}">${row.blocked?'Unblock':'Block'}</button>`;if(key==='starred')return `<button class="save-star" data-star="${esc(row.tconst)}" aria-pressed="${row.starred}" aria-label="${row.starred?'Unstar':'Star'} ${esc(row.primaryTitle)}" title="${row.starred?'Remove from':'Add to'} starred movies">${row.starred?'★':'☆'}</button>`;if(key==='googleSearch'){const query=[row.primaryTitle,row.startYear,'movie'].filter(v=>v!==null&&v!=='').join(' ');return `<a class="google-search" href="https://www.google.com/search?q=${encodeURIComponent(query)}" target="_self" data-google-search aria-label="Search Google for ${esc(row.primaryTitle)}${row.startYear?' ('+row.startYear+')':''}">Search Google</a>`;}const v=row[key];if(v===null)return '<span class="null">—</span>';if(key==='globalScore')return `<button class="global-score-button" data-global-breakdown="${esc(row.tconst)}" aria-label="Show global score breakdown for ${esc(row.primaryTitle)}">${Number(v).toFixed(1)}<small>/100 ⓘ</small></button>`;if(key==='filterScore')return `<details class="score-detail"><summary aria-label="Filter score ${Number(v).toFixed(1)} out of 100; show breakdown">${Number(v).toFixed(1)}<span>/100</span></summary><div>${row.scoreBreakdown.map(c=>`<p><span>${esc(c.label)} <small>×${c.weight}</small></span><strong>${Number(c.score).toFixed(1)}</strong></p>`).join('')}<small>Weighted average of active fields</small></div></details>`;if(key==='primaryTitle')return `<a href="https://www.imdb.com/title/${encodeURIComponent(row.tconst)}/" target="_blank" rel="noreferrer">${esc(v)}</a>`;if(key==='averageRating')return `<span class="rating"><span class="star" aria-hidden="true">★</span>${Number(v).toFixed(1)}</span>`;if(key==='globalRank')return '#'+format.format(v);if(key==='numVotes')return format.format(v);if(key==='genres')return v.split(',').map(g=>`<span class="genre-tag">${esc(g)}</span>`).join('');if(key==='isAdult')return v?'Yes':'No';return esc(v);}
const baseCell = cell;
cell = (row,key) => key==='seen' ? `<button class="save-seen" data-seen="${esc(row.tconst)}" aria-pressed="${row.seen}" aria-label="${row.seen?'Mark':'Unmark'} ${esc(row.primaryTitle)} as seen" title="${row.seen?'Mark as unseen':'Mark as seen'}">${row.seen?'✓':'○'}</button>` : baseCell(row,key);
function renderTable(){if(!data)return;$('score-rules').innerHTML=data.scoreRules.length?data.scoreRules.map(r=>`<li><strong>${esc(r.label)} (weight ${r.weight}):</strong> ${esc(r.rule)}</li>`).join(''):'<li>Choose a filter value or enter a search to calculate scores.</li>';const columns=state.columns.map(k=>meta.columns.find(c=>c.key===k));$('movies-table').querySelector('thead').innerHTML='<tr>'+columns.map(c=>c.kind==='action'?`<th class="action-heading" data-column="${c.key}" title="Drag to move column">${esc(c.label)}<span class="column-resizer" data-resize-column="${c.key}" title="Drag to resize · double-click to fit"></span></th>`:`<th class="${c.kind==='number'?'numeric':''}" data-column="${c.key}" title="Click to sort · drag to move column" aria-sort="${state.sort===c.key?(state.direction==='asc'?'ascending':'descending'):'none'}"><button data-sort="${c.key}">${esc(c.label)}${state.sort===c.key?(state.direction==='asc'?' ↑':' ↓'):''}</button><span class="column-resizer" data-resize-column="${c.key}" title="Drag to resize · double-click to fit"></span></th>`).join('')+'</tr>';$('movies-table').querySelector('tbody').innerHTML=data.rows.map(r=>'<tr>'+columns.map(c=>`<td class="${c.kind==='number'?'numeric ':''}${c.key==='primaryTitle'?'title-cell':''}" title="${c.kind==='action'?(c.key==='starred'?'Save movie':'Search in this tab'):r[c.key]===null?'Not available':esc(r[c.key])}">${cell(r,c.key)}</td>`).join('')+'</tr>').join('');$('empty').hidden=data.total!==0;$('movies-table').hidden=data.total===0;$('results-title').textContent=state.view==='starred'?'Starred movies':state.q.trim()||state.filters.length?'Matching movies':'All movies';$('starred-count').textContent=format.format(data.starredCount);for(const b of document.querySelectorAll('[data-view]'))b.setAttribute('aria-pressed',String(b.dataset.view===state.view));$('view-note').textContent=state.view==='starred'?'Your saved movies. This tab has its own saved filters.':'Star movies to save them for later.';$('empty').querySelector('strong').textContent=state.view==='starred'&&!data.starredCount?'No starred movies yet':'No movies found';$('empty').querySelector('p').textContent=state.view==='starred'&&!data.starredCount?'Go to All movies and click a star to save a movie.':'Try a different title or remove a filter.';$('result-count').textContent=format.format(data.total);$('result-summary').textContent=data.total?`${format.format((data.page-1)*data.size+1)}–${format.format(Math.min(data.page*data.size,data.total))} of ${format.format(data.total)} movies`:'0 matching movies';$('page').value=data.page;$('page').max=data.pages;$('pages').textContent=`of ${format.format(data.pages)}`;for(const id of ['first','previous'])$(id).disabled=data.page<=1;for(const id of ['next','last'])$(id).disabled=data.page>=data.pages;$('status').textContent=$('result-summary').textContent;}
async function load(){controller?.abort();controller=new AbortController();const current=controller;$('error').hidden=true;$('movies-table').setAttribute('aria-busy','true');document.querySelector('.results').classList.add('loading');const params=new URLSearchParams({...state,scoring:JSON.stringify(state.scoring),filters:JSON.stringify(state.filters.filter(f=>['missing','present'].includes(f.op)||String(f.value).trim()!==''))});try{const response=await fetch('/api/movies?'+params,{signal:current.signal});const result=await response.json();if(!response.ok)throw new Error(result.error);if(current!==controller)return;data=result;state.page=data.page;renderTable();}catch(e){if(e.name!=='AbortError'){$('error').textContent=e.message+' Change your filters or reload to try again.';$('error').hidden=false;}}finally{if(current===controller){document.querySelector('.results').classList.remove('loading');$('movies-table').setAttribute('aria-busy','false');}}}
function refresh(){state.page=1;clearTimeout(debounce);debounce=setTimeout(load,250);}
function syncSort(){$('sort').value=state.sort;$('direction').textContent=state.direction==='desc'?'↓':'↑';$('direction').setAttribute('aria-label',`Sort ${state.direction==='desc'?'ascending':'descending'}`);persist();}
function renderColumns(){
 const ordered=[...state.columns.map(key=>meta.columns.find(c=>c.key===key)),...meta.columns.filter(c=>!state.columns.includes(c.key))];
 $('column-options').innerHTML='<p class="muted">Shown in table order. Enter a position and press Enter or leave the box to move a column. Other columns shift automatically.</p>'+ordered.map(c=>{
  const index=state.columns.indexOf(c.key),visible=index!==-1;
  return `<div class="column-option"><label><input type="checkbox" value="${c.key}" ${visible?'checked':''} ${state.columns.length===1&&visible?'disabled':''}>${esc(c.label)}</label>${visible?`<div class="column-moves"><input class="column-position" type="number" min="1" max="${state.columns.length}" step="1" value="${index+1}" data-column-position="${c.key}" aria-label="${esc(c.label)} column position" title="Position (1–${state.columns.length})"><button type="button" data-move-column="${c.key}" data-step="-1" aria-label="Move ${esc(c.label)} left" title="Move left" ${index===0?'disabled':''}>←</button><button type="button" data-move-column="${c.key}" data-step="1" aria-label="Move ${esc(c.label)} right" title="Move right" ${index===state.columns.length-1?'disabled':''}>→</button></div>`:''}</div>`;
 }).join('');
}
const baseRenderColumns = renderColumns;
renderColumns = () => {
 if (meta && !meta.columns.some(c=>c.key==='seen')) {
  const starIndex=meta.columns.findIndex(c=>c.key==='starred');
  meta.columns.splice(starIndex<0?0:starIndex+1,0,{key:'seen',label:'Seen',kind:'action'});
 }
 if (!state.columns.includes('seen')) state.columns.splice(Math.min(1,state.columns.length),0,'seen');
 baseRenderColumns();
};
const FILTERS = [
  {key:'notSeen',label:'Not seen'},
  {key:'genres',label:'Genres'},
  {key:'averageRating',label:'IMDb rating'},
  {key:'numVotes',label:'Vote count'},
  {key:'startYear',label:'Release year'},
  {key:'runtimeMinutes',label:'Runtime'},
  {key:'isAdult',label:'Adult content'},
];
const enrichmentSpec = key => meta?.enrichmentFields?.find(f=>f.key===key);
const defaults = key => enrichmentSpec(key)?.kind==='category'?{values:[],mode:'any_of'}:enrichmentSpec(key)?.kind==='number'?{min:'',max:'',status:'any'}:key==='mdbAvailable'?{value:''}: key==='notSeen'?{}: key==='genres'?{values:[],mode:'any_of'}:key==='averageRating'?{min:'',status:'any'}:key==='numVotes'?{min:''}:key==='isAdult'?{value:''}:{min:'',max:''};
const filterValues = Object.fromEntries(FILTERS.map(f=>[f.key,defaults(f.key)]));
let filterSaving = Promise.resolve();
const filterProfiles={};
let filterProfilesLoaded=false;
function saveFilters(){
  const view=state.view;
  const payload=JSON.stringify({version:1,q:state.q,visibleFilters:state.visibleFilters,values:filterValues,scoring:state.scoring});
  filterProfiles[view]=JSON.parse(payload);
  $('filter-save-status').textContent='Saving filters…';
  filterSaving=filterSaving.catch(()=>{}).then(async()=>{
    const response=await fetch('/api/filters?view='+encodeURIComponent(view),{method:'PUT',headers:{'Content-Type':'application/json'},body:payload,keepalive:true});
    if(!response.ok)throw new Error('Save failed');
  });
  const current=filterSaving;
  current.then(()=>{if(current===filterSaving)$('filter-save-status').textContent='Filters saved on this computer';}).catch(()=>{if(current===filterSaving)$('filter-save-status').textContent='Could not save filters. Change a filter to retry.';});
}
function useFilterProfile(view){
  const saved=filterProfiles[view];
  state.q=saved?.q||'';state.visibleFilters=saved?.visibleFilters?[...saved.visibleFilters]:(view==='all'?['genres','averageRating','startYear']:[]);
  state.scoring=structuredClone(saved?.scoring||meta.scoringDefaults);
  for(const f of FILTERS)filterValues[f.key]={...defaults(f.key),...structuredClone(saved?.values[f.key]||{})};
  state.filters=compileFilters();$('search').value=state.q;
  $('filter-save-status').textContent='Filters saved separately for each movie tab';
}
async function restoreFilters(){
  await Promise.all(['all','starred','seen','blocked'].map(async view=>{
    const response=await fetch('/api/filters?view='+view);
    if(!response.ok)throw new Error('Could not restore saved filters.');
    filterProfiles[view]=await response.json();
  }));
  filterProfilesLoaded=true;useFilterProfile(state.view);
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
    if(enrichmentSpec(key)?.kind==='category'){
      controls=`<label class="filter-control">Match<select data-value="mode"><option value="any_of" ${v.mode==='any_of'?'selected':''}>Any selected</option><option value="all_of" ${v.mode==='all_of'?'selected':''}>All selected</option></select></label><div class="genre-options mdb-options">${(meta.enrichmentOptions[key]||[]).map(value=>`<label><input type="checkbox" data-genre="${esc(value)}" ${v.values.includes(value)?'checked':''}>${esc(value)}</label>`).join('')}</div><p class="genre-summary">${v.values.length?esc(v.values.join(', ')):'Any value'}</p>`;
    }else if(enrichmentSpec(key)?.kind==='number'){
      controls=`<label class="filter-control">Data availability<select data-value="status"><option value="any" ${v.status==='any'?'selected':''}>Any</option><option value="present" ${v.status==='present'?'selected':''}>Has data</option><option value="missing" ${v.status==='missing'?'selected':''}>Missing data</option></select></label>`;
      if(v.status!=='missing')controls+='<div class="filter-range">'+numberControl(key,'min','Minimum','Any',0,'','any')+numberControl(key,'max','Maximum','Any',0,'','any')+'</div>';
    }else if(key==='mdbAvailable'){
      controls=`<label class="filter-control">MDBList data<select data-value="value"><option value="" ${v.value===''?'selected':''}>All movies</option><option value="1" ${v.value==='1'?'selected':''}>Downloaded only</option><option value="0" ${v.value==='0'?'selected':''}>Not downloaded</option></select></label>`;
    }else if(key==='notSeen'){
      controls='<p class="control-hint">Movies marked as seen are hidden. Remove this filter to include them again.</p>';
    }else if(key==='genres'){
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
    if(enrichmentSpec(key)?.kind==='category'){if(v.values.length)filters.push({field:key,op:v.mode,value:v.values});}
    else if(enrichmentSpec(key)?.kind==='number'){if(v.status==='missing')filters.push({field:key,op:'missing'});else{if(v.status==='present')filters.push({field:key,op:'present'});if(v.min!=='')filters.push({field:key,op:'gte',value:v.min});if(v.max!=='')filters.push({field:key,op:'lte',value:v.max});}}
    else if(key==='mdbAvailable'){if(v.value!=='')filters.push({field:key,op:'eq',value:v.value});}
    else if(key==='notSeen')filters.push({field:key,op:'eq',value:true});
    else if(key==='genres'){if(v.values.length)filters.push({field:key,op:v.mode,value:v.values});}
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
  state.visibleFilters=[];state.filters=[];state.q='';$('search').value='';renderFilters();saveFilters();refresh();
}
function setFilterVisibility(key,visible){
  if(visible&&!state.visibleFilters.includes(key))state.visibleFilters.push(key);
  if(!visible){state.visibleFilters=state.visibleFilters.filter(k=>k!==key);filterValues[key]=defaults(key);}
  renderFilters();persist();applyFilters();
}
function renderScoringSettings(){
  const settings=state.scoring;
  $('weight-settings').innerHTML=[...FILTERS.filter(f=>!['notSeen','mdbAvailable'].includes(f.key)),{key:'search',label:'Title search'}].map(f=>`<label>${f.label}<input aria-label="${f.label} weight" name="weight-${f.key}" type="number" min="0" max="10" step="0.1" required value="${settings.weights[f.key]}"></label>`).join('');
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
async function init(){try{const response=await fetch('/api/meta');if(!response.ok)throw new Error('Could not load the library.');meta=await response.json();meta.columns.unshift({key:'seen',label:'Seen',kind:'action'});for(const f of meta.enrichmentFields||[]){if(['number','category','boolean'].includes(f.kind)){FILTERS.push({key:f.key,label:f.label});filterValues[f.key]=defaults(f.key);}}meta.columns.unshift({key:'blocked',label:'Block',kind:'action'});state.scoring=structuredClone(meta.scoringDefaults);meta.columns.unshift({key:'starred',label:'Star',kind:'action'});meta.columns.splice(2,0,{key:'googleSearch',label:'Google search',kind:'action'});try{const saved=JSON.parse(localStorage.getItem('frame-preferences'));if(saved){if(['all','starred','seen','blocked'].includes(saved.view))state.view=saved.view;if(!saved.starColumnAdded)state.columns.unshift('starred');if(Array.isArray(saved.visibleFilters))state.visibleFilters=[...new Set(saved.visibleFilters)].filter(k=>FILTERS.some(f=>f.key===k));if(Array.isArray(saved.columns)){const cols=[...new Set(saved.columns)].filter(k=>meta.columns.some(c=>c.key===k));if(cols.length)state.columns=cols;}if(!saved.blockColumnAdded&&!state.columns.includes('blocked'))state.columns.splice(1,0,'blocked');if(!saved.starColumnAdded&&!state.columns.includes('starred'))state.columns.unshift('starred');if(!saved.globalColumnAdded&&!state.columns.includes('globalScore'))state.columns.splice(1,0,'globalScore');if(!saved.globalRankColumnAdded&&!state.columns.includes('globalRank'))state.columns.splice(Math.max(0,state.columns.indexOf('globalScore')),0,'globalRank');if(!saved.scoreColumnAdded&&!state.columns.includes('filterScore'))state.columns.splice(1,0,'filterScore');if(!saved.googleColumnAdded&&!state.columns.includes('googleSearch'))state.columns.splice(1,0,'googleSearch');if(!saved.ratingColumnAdded&&!state.columns.includes('myRating'))state.columns.splice(state.columns.indexOf('primaryTitle')+1,0,'myRating');if(!saved.predictedColumnAdded&&!state.columns.includes('predictedRating'))state.columns.splice(state.columns.indexOf('myRating')+1,0,'predictedRating');if(meta.columns.some(c=>c.key===saved.sort&&c.kind!=='action'))state.sort=saved.sort;if(['asc','desc'].includes(saved.direction))state.direction=saved.direction;if([25,50,100,250].includes(saved.size))state.size=saved.size;}}catch{}await restoreFilters();await initFilterPresets();$('library-count').textContent=format.format(meta.total);$('snapshot').textContent=`Snapshot · ${meta.snapshot}`;$('sort').innerHTML=meta.columns.filter(c=>c.kind!=='action').map(c=>`<option value="${c.key}">Sort: ${esc(c.label)}</option>`).join('');$('page-size').value=state.size;const returnView=history.state?.movieReturn;if(returnView&&Number.isInteger(returnView.page)&&returnView.page>0)state.page=returnView.page;syncSort();renderColumns();renderFilters();renderScoringSettings();await initGlobalSettings();await load();if(returnView){window.scrollTo(returnView.windowX||0,returnView.windowY||0);document.querySelector('.table-scroll').scrollLeft=returnView.scrollLeft||0;history.replaceState(null,'');}}catch(e){$('error').hidden=false;$('error').textContent=e.message;}}
$('search').addEventListener('input',e=>{state.q=e.target.value;saveFilters();refresh();});
$('sort').addEventListener('change',e=>{state.sort=e.target.value;if(['filterScore','globalScore','globalRank','myRating','predictedRating'].includes(state.sort)){state.direction=state.sort==='globalRank'?'asc':'desc';if(!state.columns.includes(state.sort)){state.columns.splice(1,0,state.sort);renderColumns();}}syncSort();refresh();});
$('direction').onclick=()=>{state.direction=state.direction==='asc'?'desc':'asc';syncSort();refresh();};
$('movies-table').addEventListener('click',e=>{if(e.target.closest('[data-google-search]')){const scroller=document.querySelector('.table-scroll');history.replaceState({movieReturn:{page:state.page,windowX:window.scrollX,windowY:window.scrollY,scrollLeft:scroller.scrollLeft}},'');return;}const b=e.target.closest('[data-sort]');if(!b)return;state.direction=state.sort===b.dataset.sort?(state.direction==='asc'?'desc':'asc'):(['filterScore','globalScore','myRating','predictedRating'].includes(b.dataset.sort)?'desc':'asc');state.sort=b.dataset.sort;syncSort();refresh();});
$('columns-button').onclick=()=>{const open=$('columns-menu').hidden;$('columns-menu').hidden=!open;$('columns-button').setAttribute('aria-expanded',String(open));};
document.addEventListener('click',e=>{if(!e.composedPath().includes($('columns-button').closest('.columns-wrap'))){$('columns-menu').hidden=true;$('columns-button').setAttribute('aria-expanded','false');}});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('columns-menu').hidden){$('columns-menu').hidden=true;$('columns-button').setAttribute('aria-expanded','false');$('columns-button').focus();}});
$('column-options').addEventListener('change',e=>{if(e.target.type!=='checkbox')return;if(e.target.checked)state.columns.push(e.target.value);else state.columns=state.columns.filter(k=>k!==e.target.value);persist();renderColumns();renderTable();});
function applyColumnPosition(input){
 const key=input.dataset.columnPosition,index=state.columns.indexOf(key),position=Number(input.value);
 if(index<0)return;
 if(!input.value.trim()||!Number.isInteger(position)||position<1||position>state.columns.length){input.value=index+1;$('status').textContent=`Enter a whole-number position from 1 to ${state.columns.length}.`;return;}
 if(position===index+1)return;
 state.columns.splice(index,1);state.columns.splice(position-1,0,key);
 persist();renderColumns();renderTable();
 $('status').textContent=`${meta.columns.find(c=>c.key===key).label} moved to column ${position} of ${state.columns.length}.`;
}
$('column-options').addEventListener('change',e=>{if(e.target.matches('[data-column-position]'))applyColumnPosition(e.target);});
$('column-options').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('[data-column-position]')){e.preventDefault();const key=e.target.dataset.columnPosition;applyColumnPosition(e.target);$('column-options').querySelector(`[data-column-position="${key}"]`)?.focus();}});
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
$('reset-columns').onclick=()=>{state.columns=[...DEFAULT_COLUMNS];columnWidths={};persist();renderColumns();renderTable();};
let columnDrag=null,suppressTableClick=false;
const columnGhost=document.createElement('div');columnGhost.className='column-drag-ghost';columnGhost.hidden=true;document.body.append(columnGhost);
const columnHeaders=()=>[...$('movies-table').querySelectorAll('thead th[data-column]')];
function clearColumnDropMarks(){for(const th of columnHeaders())th.classList.remove('column-dragged','drop-before','drop-after');}
function columnDropIndex(x){
 const headers=columnHeaders(),index=headers.findIndex(th=>{const r=th.getBoundingClientRect();return x<r.left+r.width/2;});
 return index<0?headers.length:index;
}
function markColumnDrop(){
 clearColumnDropMarks();
 const headers=columnHeaders(),from=state.columns.indexOf(columnDrag.key),to=columnDrag.index=columnDropIndex(columnDrag.x);
 headers[from]?.classList.add('column-dragged');
 if(to===from||to===from+1)return;
 if(to<headers.length)headers[to].classList.add('drop-before');else headers[headers.length-1]?.classList.add('drop-after');
}
function autoScrollColumns(time){
 if(!columnDrag?.active||columnDrag.cancelled)return;
 const scroller=document.querySelector('.table-scroll'),r=scroller.getBoundingClientRect(),edge=48,x=columnDrag.x,elapsed=Math.min(100,time-(columnDrag.lastFrame??time));
 columnDrag.lastFrame=time;
 const depth=x<r.left+edge?-Math.min(edge,r.left+edge-x):x>r.right-edge?Math.min(edge,x-(r.right-edge)):0;
 if(depth&&elapsed){scroller.scrollLeft+=Math.sign(depth)*Math.ceil(Math.abs(depth)/edge*elapsed);markColumnDrop();}
 columnDrag.frame=requestAnimationFrame(autoScrollColumns);
}
function stopColumnDragFeedback(){cancelAnimationFrame(columnDrag.frame);columnGhost.hidden=true;document.body.classList.remove('column-dragging');clearColumnDropMarks();}
$('movies-table').addEventListener('pointerdown',e=>{
 suppressTableClick=false;
 const th=e.target.closest('thead th[data-column]');
 if(!th||e.target.closest('.column-resizer')||e.button!==0||!e.isPrimary||e.pointerType==='touch')return;
 columnDrag={key:th.dataset.column,startX:e.clientX,x:e.clientX,index:0,frame:0,active:false,cancelled:false};
});
document.addEventListener('pointermove',e=>{
 if(!columnDrag||columnDrag.cancelled)return;
 columnDrag.x=e.clientX;
 if(!columnDrag.active){
  if(Math.abs(e.clientX-columnDrag.startX)<6)return;
  columnDrag.active=true;document.body.classList.add('column-dragging');
  columnGhost.textContent=meta.columns.find(c=>c.key===columnDrag.key)?.label||'';columnGhost.hidden=false;
  columnDrag.frame=requestAnimationFrame(autoScrollColumns);
 }
 columnGhost.style.transform=`translate(${e.clientX+14}px,${e.clientY+14}px)`;
 markColumnDrop();
});
function endColumnDrag(e){
 if(!columnDrag)return;
 const drag=columnDrag;stopColumnDragFeedback();columnDrag=null;
 if(!drag.active)return;
 suppressTableClick=true;setTimeout(()=>{suppressTableClick=false;});
 if(drag.cancelled||e.type==='pointercancel')return;
 const from=state.columns.indexOf(drag.key);let to=drag.index;
 if(from<0||to===from||to===from+1)return;
 if(to>from)to--;
 state.columns.splice(from,1);state.columns.splice(to,0,drag.key);
 persist();renderColumns();renderTable();
 $('status').textContent=`${meta.columns.find(c=>c.key===drag.key).label} moved to column ${to+1} of ${state.columns.length}.`;
}
document.addEventListener('pointerup',endColumnDrag);
document.addEventListener('pointercancel',endColumnDrag);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&columnDrag?.active&&!columnDrag.cancelled){columnDrag.cancelled=true;stopColumnDragFeedback();}});
$('movies-table').addEventListener('click',e=>{if(suppressTableClick){e.stopImmediatePropagation();e.preventDefault();suppressTableClick=false;}},true);
const columnWidthSheet=new CSSStyleSheet();document.adoptedStyleSheets=[...document.adoptedStyleSheets,columnWidthSheet];
const clampColumnWidth=width=>Math.round(Math.min(1200,Math.max(40,width)));
try{const saved=JSON.parse(localStorage.getItem('frame-preferences'))?.columnWidths;if(saved&&typeof saved==='object')for(const [key,width] of Object.entries(saved))if(Number.isFinite(width))columnWidths[key]=clampColumnWidth(width);}catch{}
function applyColumnWidths(){
 columnWidthSheet.replaceSync(state.columns.map((key,i)=>columnWidths[key]?`#movies-table tr>:nth-child(${i+1}){width:${columnWidths[key]}px;min-width:${columnWidths[key]}px;max-width:${columnWidths[key]}px;overflow:hidden;text-overflow:ellipsis}`:'').join('\n'));
}
const renderTableBeforeWidths=renderTable;
renderTable=()=>{renderTableBeforeWidths();applyColumnWidths();markColumnEdge(null);};
const columnEdgeSheet=new CSSStyleSheet();document.adoptedStyleSheets=[...document.adoptedStyleSheets,columnEdgeSheet];
let columnResize=null,edgeColumn=null;
// Every column edge can be dragged, not only the header handle, so columns can be resized anywhere in a long table.
function columnEdgeAt(e){
 const handle=e.target.closest('.column-resizer');if(handle)return handle.dataset.resizeColumn;
 const cell=e.pointerType!=='touch'&&e.target.closest('#movies-table tbody td');if(!cell)return null;
 const r=cell.getBoundingClientRect();
 return e.clientX>r.right-7?state.columns[cell.cellIndex]:e.clientX<r.left+5&&state.columns[cell.cellIndex-1]||null;
}
// Hovering an edge only changes the cursor; a faint guide line appears while resizing.
function markColumnEdge(key,resizing=false){
 const mark=key&&`${key}:${resizing}`;if(mark===edgeColumn)return;
 edgeColumn=mark;const index=state.columns.indexOf(key);
 columnEdgeSheet.replaceSync(index<0?'':'#movies-table tbody{cursor:col-resize}'+(resizing?`#movies-table tr>:nth-child(${index+1}){box-shadow:inset -1px 0 0 #59606b}`:''));
}
$('movies-table').addEventListener('pointermove',e=>{if(!columnResize&&!columnDrag?.active)markColumnEdge(columnEdgeAt(e));});
$('movies-table').addEventListener('pointerleave',()=>{if(!columnResize)markColumnEdge(null);});
$('movies-table').addEventListener('pointerdown',e=>{
 const key=columnEdgeAt(e);
 if(!key||e.button!==0||!e.isPrimary)return;
 e.preventDefault();
 markColumnEdge(key,true);document.body.classList.add('column-resizing');
 columnResize={key,startX:e.clientX,startWidth:$('movies-table').querySelector(`thead th[data-column="${key}"]`).getBoundingClientRect().width,previous:columnWidths[key],moved:false};
});
document.addEventListener('pointermove',e=>{
 if(!columnResize||!columnResize.moved&&e.clientX===columnResize.startX)return;
 columnResize.moved=true;columnWidths[columnResize.key]=clampColumnWidth(columnResize.startWidth+e.clientX-columnResize.startX);applyColumnWidths();
});
function restoreColumnWidth(resize){if(resize.previous)columnWidths[resize.key]=resize.previous;else delete columnWidths[resize.key];applyColumnWidths();}
function stopColumnResize(){columnResize=null;document.body.classList.remove('column-resizing');markColumnEdge(null);}
function endColumnResize(e){
 if(!columnResize)return;
 const resize=columnResize;stopColumnResize();
 if(!resize.moved)return;
 suppressTableClick=true;setTimeout(()=>{suppressTableClick=false;});
 if(e.type==='pointercancel')restoreColumnWidth(resize);else persist();
}
document.addEventListener('pointerup',endColumnResize);
document.addEventListener('pointercancel',endColumnResize);
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&columnResize){restoreColumnWidth(columnResize);stopColumnResize();}});
$('movies-table').addEventListener('dblclick',e=>{
 const key=columnEdgeAt(e);if(!key)return;
 delete columnWidths[key];applyColumnWidths();persist();
});
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
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{if(!filterProfilesLoaded||state.view===button.dataset.view)return;clearTimeout(debounce);controller?.abort();state.view=button.dataset.view;useFilterProfile(state.view);persist();renderFilters();renderScoringSettings();refresh();});
$('movies-table').addEventListener('click',async e=>{
 const button=e.target.closest('[data-star]');if(!button||button.disabled)return;
 const selected=button.getAttribute('aria-pressed')!=='true';button.disabled=true;
 try{
  const response=await fetch('/api/starred',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tconst:button.dataset.star,starred:selected})});
  const result=await response.json();if(!response.ok)throw new Error(result.error);
  clearTimeout(debounce);await load();
 }catch(error){$('error').textContent='Could not save movie: '+error.message;$('error').hidden=false;button.disabled=false;}
});
const baseRenderTable = renderTable;
renderTable = () => {
 baseRenderTable();
 if (!data) return;
 $('results-title').textContent=state.view==='starred'?'Starred movies':state.view==='seen'?'Seen movies':state.q.trim()||state.filters.length?'Matching movies':'All movies';
 $('blocked-count').textContent=format.format(data.blockedCount);
 if(state.view==='blocked')$('results-title').textContent='Blocked movies';
 $('seen-count').textContent=format.format(data.seenCount);
 for (const button of document.querySelectorAll('[data-seen]')) button.closest('td').title=button.title;
 $('view-note').textContent=state.view==='starred'?'Your saved movies. This tab has its own saved filters.':state.view==='seen'?'Movies you have marked as seen. This tab has its own saved filters.':'Star or mark movies as seen for later.';
 $('empty').querySelector('strong').textContent=state.view==='starred'&&!data.starredCount?'No starred movies yet':state.view==='seen'&&!data.seenCount?'No seen movies yet':'No movies found';
 $('empty').querySelector('p').textContent=state.view==='starred'&&!data.starredCount?'Go to All movies and click a star to save a movie.':state.view==='seen'&&!data.seenCount?'Go to All movies and mark a movie as seen.':'Try a different title or remove a filter.';
 if(state.view==='blocked'){ $('view-note').textContent='Blocked movies are hidden from other library views. Unblock to show them again. This tab has its own saved filters.'; $('empty').querySelector('strong').textContent=data.blockedCount?'No movies found':'No blocked movies'; }
 for(const button of document.querySelectorAll('[data-blocked]'))button.closest('td').title=button.title;
};
$('movies-table').addEventListener('click',async e=>{
 const button=e.target.closest('[data-seen]');if(!button||button.disabled)return;
 const selected=button.getAttribute('aria-pressed')!=='true';button.disabled=true;
 try{
  const response=await fetch('/api/seen',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tconst:button.dataset.seen,seen:selected})});
  const result=await response.json();if(!response.ok)throw new Error(result.error);
  clearTimeout(debounce);await load();
 }catch(error){$('error').textContent='Could not save seen status: '+error.message;$('error').hidden=false;button.disabled=false;}
});
$('movies-table').addEventListener('click',async e=>{
 const button=e.target.closest('[data-blocked]');if(!button||button.disabled)return;
 button.disabled=true;
 try{
  const response=await fetch('/api/blocked',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tconst:button.dataset.blocked,blocked:button.getAttribute('aria-pressed')!=='true'})});
  const result=await response.json();if(!response.ok)throw new Error(result.error);
  clearTimeout(debounce);await load();
 }catch(error){$('error').textContent='Could not save blocked status: '+error.message;$('error').hidden=false;button.disabled=false;}
});
const cellBeforeRating=cell;
cell=(row,key)=>key==='myRating'?`<input class="my-rating" type="number" min="0" max="10" step="1" inputmode="numeric" placeholder="—" data-rating="${esc(row.tconst)}" value="${row.myRating??''}" aria-label="Your rating for ${esc(row.primaryTitle)}, 0 to 10">`:cellBeforeRating(row,key);
const renderTableBeforeRatings=renderTable;
renderTable=()=>{renderTableBeforeRatings();for(const input of document.querySelectorAll('[data-rating]'))input.closest('td').title='Your rating, 0–10. Leave blank to clear.';};
$('movies-table').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('[data-rating]'))e.target.blur();});
$('movies-table').addEventListener('change',async e=>{
 const input=e.target.closest('[data-rating]');if(!input)return;
 const rating=input.value.trim()===''?null:Number(input.value),movie=data?.rows.find(r=>r.tconst===input.dataset.rating);
 if(input.validity.badInput||rating!==null&&!(Number.isInteger(rating)&&rating>=0&&rating<=10)){input.value=movie?.myRating??'';$('status').textContent='Enter a whole number from 0 to 10.';input.classList.remove('saved');input.classList.add('invalid');return;}
 input.classList.remove('invalid','saved');
 try{
  const response=await fetch('/api/ratings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tconst:input.dataset.rating,rating})});
  const result=await response.json();if(!response.ok)throw new Error(result.error);
  if(movie)movie.myRating=rating;
  input.value=movie?.myRating??'';input.classList.add('saved');setTimeout(()=>input.classList.remove('saved'),1500);$('status').textContent=rating===null?'Rating cleared.':`Rating saved: ${input.value}.`;
 }catch(error){$('error').textContent='Could not save rating: '+error.message;$('error').hidden=false;}
});
const renderFiltersBeforeNote=renderFilters;
renderFilters=()=>{renderFiltersBeforeNote();$('filters-view-note').textContent=`Editing filters for ${{all:'All movies',starred:'Starred',seen:'Seen',blocked:'Blocked'}[state.view]}. Each movie list keeps its own filters.`;};
const cellBeforePrediction=cell;
cell=(row,key)=>key==='predictedRating'&&row[key]!==null?Number(row[key]).toFixed(1):cellBeforePrediction(row,key);
function renderPrediction(p){
 const signed=v=>(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(2);
 if(p.ratings<p.minRatings){$('prediction-rules').innerHTML=`<p>Rate at least ${p.minRatings} movies in My rating to get predictions. You have rated ${p.ratings}.</p>`;return;}
 const effects=p.genreEffects.map(([genre,value])=>`${esc(genre)} ${signed(value)}`).join(', ');
 $('prediction-rules').innerHTML=`<p>Predicts your 0–10 rating for movies with at least ${format.format(p.minVotes)} IMDb votes, learned from your ${p.ratings} ratings. Movies you have rated also show a prediction for comparison.</p><ul>
<li><strong>Crowd quality:</strong> each IMDb point above or below ${p.imdbMean} (the average for movies you rated) adds or subtracts ${p.qualitySlope}. This is fixed, because your ratings only cover well-reviewed movies.</li>
<li><strong>Your genre taste</strong> (points added when a movie has the genre): ${effects||'no clear effects yet'}.</li>
${p.metacriticEffect===null?'':`<li><strong>Metacritic:</strong> ${signed(p.metacriticEffect)} for every ${p.metacriticSd} Metacritic points above the average of your rated movies; movies without a score count as average.</li>`}
<li><strong>Accuracy:</strong> predicting each rated movie with that movie left out, the model is off by ${p.heldOutError.toFixed(2)} points on average, versus ${p.averageGuessError.toFixed(2)} for always guessing your average rating (${p.averageRating.toFixed(1)}). Correlation with your ratings: ${p.heldOutCorrelation===null?'—':p.heldOutCorrelation.toFixed(2)}.</li></ul>
<p class="muted">With few ratings the predictions are rough. Rating more movies, especially across different genres, makes them more accurate. After you change a rating, predictions refresh the next time the list loads.</p>`;
}
const renderTableBeforePrediction=renderTable;
renderTable=()=>{renderTableBeforePrediction();if(data?.prediction)renderPrediction(data.prediction);};
$('column-options').insertAdjacentHTML('beforebegin','<div class="column-search"><input type="search" id="column-search" placeholder="Search columns…" aria-label="Search columns" autocomplete="off"><p id="column-no-match" class="muted" hidden>No columns match.</p></div>');
function filterColumnOptions(){
 const query=$('column-search').value.trim().toLowerCase();let shown=0;
 for(const option of $('column-options').querySelectorAll('.column-option')){const match=!query||option.querySelector('label').textContent.toLowerCase().includes(query);option.hidden=!match;shown+=match;}
 $('column-no-match').hidden=shown>0;
}
const renderColumnsBeforeSearch=renderColumns;
renderColumns=()=>{renderColumnsBeforeSearch();filterColumnOptions();};
$('column-search').addEventListener('input',filterColumnOptions);
$('columns-button').addEventListener('click',()=>{if(!$('columns-menu').hidden)$('column-search').focus();});
function renderInsights(result){
 if(result.ratings<5){$('rating-insights').innerHTML=`<p>Rate at least 5 movies in My rating to see correlations. You have rated ${result.ratings}.</p>`;return;}
 const chance=Math.tanh(1.96*Math.sqrt(1.06/(result.ratings-3))),signed=v=>(v>0?'+':v<0?'−':'')+Math.abs(v).toFixed(2);
 const evidence=s=>s.q<0.1?'Likely real':s.p<0.05?'Possible, could be chance':'Unclear';
 $('rating-insights').innerHTML=`<p>Spearman correlation between your ${result.ratings} ratings and each stat, strongest first. Positive means you tend to rate movies higher when the stat is higher (or when a movie has that genre or label); negative means lower. With ${result.ratings} ratings, correlations within about ±${chance.toFixed(2)} can easily be chance, and testing ${result.tested} stats at once makes a few chance hits likely, so Evidence uses a false-discovery-rate check. Pearson uses the logarithm of vote counts and money. Keywords are left out because hundreds would be tested.</p>
<div class="insights-scroll"><table class="insights-table"><thead><tr><th>Stat</th><th>Correlation</th><th class="numeric">Pearson</th><th class="numeric">Movies</th><th class="numeric">p</th><th>Evidence</th></tr></thead><tbody>${result.stats.map(s=>`<tr><td>${esc(s.label)} <small>${esc(s.group)}</small></td><td><span class="corr-value">${signed(s.spearman)}</span><span class="corr-track"><span class="corr-fill${s.spearman<0?' negative':''}" data-correlation="${s.spearman}"></span></span></td><td class="numeric">${signed(s.pearson)}</td><td class="numeric">${s.movies}</td><td class="numeric">${s.p<0.001?'<0.001':s.p.toFixed(3)}</td><td>${evidence(s)}</td></tr>`).join('')}</tbody></table></div>`;
 for(const fill of $('rating-insights').querySelectorAll('[data-correlation]')){const v=Number(fill.dataset.correlation);fill.style.width=`${Math.abs(v)*50}%`;fill.style[v<0?'right':'left']='50%';}
}
// Correlations are recalculated whenever the Insights tab is shown, however it was opened.
new MutationObserver(async()=>{
 if($('insights-panel').hidden)return;
 $('rating-insights').innerHTML='<p class="muted">Calculating…</p>';
 try{const response=await fetch('/api/rating-insights');const result=await response.json();if(!response.ok)throw new Error(result.error);renderInsights(result);}
 catch(error){$('rating-insights').innerHTML=`<p>Could not calculate correlations: ${esc(error.message)}</p>`;}
}).observe($('insights-panel'),{attributes:true,attributeFilter:['hidden']});
// Ranking from the Global score tab shows the result on the Movies tab.
$('global-rank').addEventListener('click',()=>{location.hash='library';});
// Only one expandable cell (plot, list, or score breakdown) stays open at a time.
$('movies-table').addEventListener('toggle',e=>{
 if(e.target.tagName!=='DETAILS'||!e.target.open)return;
 for(const other of $('movies-table').querySelectorAll('details[open]'))if(other!==e.target)other.open=false;
},true);
init();

const globalScoreDialog=document.createElement('dialog');
globalScoreDialog.className='global-score-dialog';
globalScoreDialog.setAttribute('aria-labelledby','global-breakdown-title');
document.body.append(globalScoreDialog);
$('movies-table').addEventListener('click',event=>{
 const button=event.target.closest('[data-global-breakdown]');if(!button)return;
 const movie=data.rows.find(row=>row.tconst===button.dataset.globalBreakdown);if(!movie)return;
 const active=movie.globalBreakdown.filter(c=>c.weight>0),unused=movie.globalBreakdown.length-active.length;
 globalScoreDialog.innerHTML=`<form method="dialog"><button aria-label="Close score breakdown">Close</button></form><h2 id="global-breakdown-title">${esc(movie.primaryTitle)} — ${Number(movie.globalScore).toFixed(1)}/100</h2><p>Each field contributes its score × its share of the total weight. These points add up to the global score.</p><div class="breakdown-scroll"><table><thead><tr><th>Field / calculation</th><th>Movie value</th><th>Field score /100</th><th>Weight</th><th>Share</th><th>Points added</th></tr></thead><tbody>${active.map(c=>`<tr><td><strong>${esc(c.label)}</strong><p>${esc(c.rule)}</p></td><td>${c.value===null?'Missing':esc(c.value)}</td><td>${c.score.toFixed(2)}</td><td>${c.weight}</td><td>${c.share.toFixed(2)}%</td><td>${c.contribution.toFixed(2)}</td></tr>`).join('')}</tbody></table></div><p><strong>Total: ${Number(movie.globalScore).toFixed(1)} / 100</strong> · ${unused} zero-weight fields excluded.</p><p class="muted">Calculated from saved global settings. Displayed components are rounded; the total uses full precision.</p>`;
 globalScoreDialog.showModal();
});
globalScoreDialog.addEventListener('click',event=>{if(event.target===globalScoreDialog){const r=globalScoreDialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)globalScoreDialog.close();}});

async function initFilterPresets(){
 const container=document.createElement('section');container.className='filter-presets';
 container.innerHTML=`<h3>Saved filters</h3><div class="scoring-actions"><label>Preset<select id="filter-preset-select"></select></label><button type="button" id="filter-preset-load">Load settings</button><label>Preset name<input id="filter-preset-name" maxlength="100" placeholder="e.g. Thriller night"></label><button type="button" id="filter-preset-save">Save as new</button><button type="button" id="filter-preset-update">Update selected</button><button type="button" id="filter-preset-delete">Delete selected</button></div><p class="muted">Save your filters, then Clear all to browse without them. Loading a preset applies it to the current tab. Saved presets stay unchanged until you update them.</p><p id="filter-preset-status" role="status"></p>`;
 $('filter-list').before(container);
 let presets=[];
 async function request(payload){const response=await fetch('/api/filter-presets',payload?{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}:undefined);const result=await response.json();if(!response.ok)throw Error(result.error||'Could not load presets.');return result;}
 function render(selected=''){ $('filter-preset-select').innerHTML='<option value="">Choose a preset</option>'+presets.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');$('filter-preset-select').value=selected;}
 $('filter-preset-select').onchange=()=>{const p=presets.find(p=>p.id===$('filter-preset-select').value);if(p)$('filter-preset-name').value=p.name;};
 $('filter-preset-load').onclick=()=>{const p=presets.find(p=>p.id===$('filter-preset-select').value);if(!p){$('filter-preset-status').textContent='Choose a preset first.';return;}filterProfiles[state.view]=structuredClone(p.settings);useFilterProfile(state.view);renderFilters();renderScoringSettings();saveFilters();refresh();$('filter-preset-status').textContent=`Loaded ${p.name} into this tab.`;};
 for(const action of ['save','update','delete'])$('filter-preset-'+action).onclick=async()=>{
  const id=$('filter-preset-select').value;if(action!=='save'&&!id){$('filter-preset-status').textContent='Choose a preset first.';return;}
  const name=$('filter-preset-name').value.trim();const buttons=[...container.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  try{presets=await request({action,id,name,settings:action==='delete'?undefined:{version:1,q:state.q,visibleFilters:state.visibleFilters,values:filterValues,scoring:state.scoring}});render(action==='delete'?'':action==='save'?presets.find(p=>p.name===name)?.id:id);$('filter-preset-status').textContent=action==='delete'?'Preset deleted. Current filters are unchanged.':'Preset saved on this computer.';}
  catch(e){$('filter-preset-status').textContent=e.message;}finally{buttons.forEach(b=>b.disabled=false);}
 };
 try{presets=await request();render();}catch(e){$('filter-preset-status').textContent=e.message;}
}
