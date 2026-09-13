let globalSettings, globalDefaults;
const GLOBAL_FIELDS={genres:'Genres',averageRating:'IMDb rating',numVotes:'Vote count',startYear:'Release year',runtimeMinutes:'Runtime',isAdult:'Adult content'};
const globalNumber=(name,label,value,min,max,step='0.1')=>`<label>${label}<input name="${name}" type="number" min="${min}" max="${max}" step="${step}" value="${value}" required></label>`;
function renderGlobalSettings(){
 const s=globalSettings,form=$('global-form');
 $('global-weights').innerHTML=Object.entries(GLOBAL_FIELDS).map(([key,label])=>globalNumber('gw-'+key,label+' weight',s.weights[key],0,10).replace('</label>',`<small class="weight-share" data-weight-share="${key}"></small></label>`)).join('');
 $('global-genres').innerHTML=meta.genres.map((genre,i)=>globalNumber('gg-'+i,esc(genre),s.genrePoints[genre]||0,-10,10)).join('');
 $('global-fields').innerHTML=Object.entries(s.fields).map(([key,f])=>`<fieldset data-global-field="${key}"><legend>${GLOBAL_FIELDS[key]}</legend><div class="scoring-grid"><label>Preference<select name="${key}-mode"><option value="higher">Favor higher values</option><option value="lower">Favor lower values</option><option value="target">Favor a target value</option></select></label><label>Score scale<select name="${key}-scale"><option value="percentile">Percentile across the library</option><option value="fixed">Fixed anchors / target distance</option></select></label><div data-global-part="anchors">${globalNumber(key+'-low','Low anchor',f.low,0,enrichmentSpec(key)?.maximum||(key==='averageRating'?10:key==='startYear'?9999:1000000000))}${globalNumber(key+'-high','High anchor',f.high,0,enrichmentSpec(key)?.maximum||(key==='averageRating'?10:key==='startYear'?9999:1000000000))}<small>Higher preference: low scores 0, high scores 100. Lower preference reverses these scores.</small></div><div data-global-part="target">${globalNumber(key+'-target','Target value',f.target,0,enrichmentSpec(key)?.maximum||(key==='averageRating'?10:key==='startYear'?9999:1000000000))}</div><div data-global-part="tolerance">${globalNumber(key+'-tolerance','Distance from target for score 0',f.tolerance,0.01,10000000000,'any')}<small>Target scores 100. Scores fall evenly to 0 at this distance in either direction.</small></div></div></fieldset>`).join('');
 form.elements.genreMode.value=s.genreMode;
 form.elements.missingScore.value=s.missingScore;
 form.elements.adult0.value=s.adultScores['0'];form.elements.adult1.value=s.adultScores['1'];
 for(const [key,f] of Object.entries(s.fields)){form.elements[key+'-mode'].value=f.mode;form.elements[key+'-scale'].value=f.scale;}
 updateGlobalControls();
 updateWeightShares();
}
function updateWeightShares(){
 const inputs=[...$('global-weights').querySelectorAll('input')];
 const values=inputs.map(input=>Number.isFinite(input.valueAsNumber)&&input.valueAsNumber>=0?input.valueAsNumber:0);
 const total=values.reduce((sum,value)=>sum+value,0);
 inputs.forEach((input,index)=>{input.parentElement.querySelector('[data-weight-share]').textContent=`${total?(100*values[index]/total).toFixed(1):'0.0'}% of total weight`;});
}
function updateGlobalControls(){
 const form=$('global-form');
 for(const panel of form.querySelectorAll('[data-global-field]')){
  const key=panel.dataset.globalField,mode=form.elements[key+'-mode'].value,scale=form.elements[key+'-scale'].value;
  for(const [part,visible] of Object.entries({anchors:scale==='fixed'&&mode!=='target',target:mode==='target',tolerance:scale==='fixed'&&mode==='target'})){
   const section=panel.querySelector(`[data-global-part="${part}"]`);section.hidden=!visible;section.querySelectorAll('input').forEach(input=>input.disabled=!visible);
  }
 }
}
async function initGlobalSettings(){
 const response=await fetch('/api/global-scoring');const result=await response.json();if(!response.ok)throw new Error(result.error);
 globalSettings=result.settings;globalDefaults=result.defaults;for(const f of meta.enrichmentFields||[])if(f.kind==='number')GLOBAL_FIELDS[f.key]=f.label;renderGlobalSettings();
 $('global-form').addEventListener('change',updateGlobalControls);
 $('global-weights').addEventListener('input',updateWeightShares);
 $('global-reset').onclick=()=>{globalSettings=structuredClone(globalDefaults);renderGlobalSettings();$('global-status').textContent='Default controls restored. Save to apply.';};
 $('global-rank').onclick=()=>{state.sort='globalScore';state.direction='desc';if(!state.columns.includes('globalScore'))state.columns.splice(1,0,'globalScore');renderColumns();syncSort();refresh();};
 $('global-form').addEventListener('submit',async event=>{
  event.preventDefault();const form=event.currentTarget;if(!form.reportValidity())return;
  const next=structuredClone(globalSettings);
  for(const key of Object.keys(GLOBAL_FIELDS))next.weights[key]=Number(form.elements['gw-'+key].value);
  next.genrePoints=Object.fromEntries(meta.genres.map((genre,i)=>[genre,Number(form.elements['gg-'+i].value)]));
  next.genreMode=form.elements.genreMode.value;next.missingScore=Number(form.elements.missingScore.value);
  next.adultScores={'0':Number(form.elements.adult0.value),'1':Number(form.elements.adult1.value)};
  for(const [key,f] of Object.entries(next.fields))for(const part of Object.keys(f))f[part]=['mode','scale'].includes(part)?form.elements[key+'-'+part].value:Number(form.elements[key+'-'+part].value);
  const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);$('global-status').textContent='Saving and recalculating the full library…';
  try{
   const response=await fetch('/api/global-scoring',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(next)});
   const result=await response.json();if(!response.ok)throw new Error(result.error);
   globalSettings=result.settings;clearTimeout(debounce);await load();$('global-status').textContent=$('error').hidden?'Saved on this computer. Global scores updated.':'Settings saved; reload to finish loading scores.';
  }catch(error){$('global-status').textContent='Could not apply settings: '+error.message;}
  finally{buttons.forEach(b=>b.disabled=false);}
 });
}
