/* PokéRadar: personal-use research dashboard. No fabricated prices or measured social-hype claims. */
'use strict';
const $ = (id) => document.getElementById(id);
const state = { cards:[], meta:{}, tab:'all', query:'', rarity:'all', year:'all', sort:'score', limit:16, saved:new Set(), loading:false };
try { state.saved = new Set(JSON.parse(localStorage.getItem('pokeradar_saved') || '[]')); } catch (_) {}
const usd = (v) => typeof v === 'number' && Number.isFinite(v) ? new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(v) : '—';
const signed = (v) => typeof v === 'number' && Number.isFinite(v) ? `${v>0?'+':''}${v.toFixed(1)}%` : '—';
const escapeHtml = (v) => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const validUrl = (v) => {try {const u=new URL(v);return ['https:','http:'].includes(u.protocol)?u.href:'';} catch(_){return ''}};
const signalText = {buy:'BUY NOW',wait:'WAIT TO BUY',watch:'WATCH',pending:'PENDING',over:'OVER $100'};
const cardVisible = (c) => c.price !== null && Number.isFinite(c.price) && c.price <=100 && c.price>0 && !c.stale && c.verifiedMatch;
function sigClass(c){ return c.signal==='buy'?'buy':c.signal==='wait'?'wait':c.signal==='watch'?'watch':'pending'; }
function cardPriceLabel(c){return cardVisible(c)?usd(c.price):c.price>100?'Above $100':c.price!==null?usd(c.price):'Awaiting sync';}
function safeText(v){return escapeHtml(v||'');}
function setStatus(){
 const m=state.meta||{},dt=m.generatedAt?new Date(m.generatedAt):null,age=dt&&!isNaN(dt)?(Date.now()-dt.getTime())/86400000:null;
 const live=state.cards.filter(cardVisible).length;
 $('statusDot').className='live-dot'+(live>0 && age!==null && age<2?' ok':age!==null && age>3?' warn':'');
 $('dataStatus').textContent=live ? `Updated ${dt?.toLocaleDateString('en-US',{month:'short',day:'numeric'})||'recently'} · ${live} eligible` : (m.successCount===0?'Price sync pending':'No verified under-$100 prices');
 $('boardCount').textContent=`${state.cards.length} cards on scouting roster`;
 const bought=state.cards.filter(c=>cardVisible(c)&&c.signal==='buy');
 const waiting=state.cards.filter(c=>cardVisible(c)&&c.signal==='wait');
 const dipped=state.cards.filter(c=>cardVisible(c)&&typeof c.change30==='number').sort((a,b)=>a.change30-b.change30);
 $('eligibleStat').textContent=String(live);
 $('buyStat').textContent=String(bought.length);
 $('waitStat').textContent=String(waiting.length);
 $('dipStat').textContent=dipped.length?signed(dipped[0].change30):'—';
 $('dipName').textContent=dipped.length?`${dipped[0].name} · ${dipped[0].set}`:'No confirmed 30-day drop yet';
 const counts={all:m.successCount===0?state.cards.length:live,buy:bought.length,wait:waiting.length,watch:state.cards.filter(c=>cardVisible(c)&&c.signal==='watch').length,saved:state.saved.size};
 Object.entries(counts).forEach(([k,n])=>{const el=$(k+'Count');if(el)el.textContent=n});
}
function getCards(){
 let arr=state.cards.filter(c=>state.tab==='saved'?state.saved.has(c.key):state.tab==='all'?(state.meta.successCount===0 || cardVisible(c)):cardVisible(c)&&c.signal===state.tab);
 if(state.query){const s=state.query.toLowerCase();arr=arr.filter(c=>[c.name,c.set,c.number,c.rarity,String(c.year)].some(v=>String(v||'').toLowerCase().includes(s)));}
 if(state.rarity!=='all')arr=arr.filter(c=>c.rarity===state.rarity);
 if(state.year==='2017')arr=arr.filter(c=>c.year<=2020);
 if(state.year==='2021')arr=arr.filter(c=>c.year>=2021);
 if(state.year==='2023')arr=arr.filter(c=>c.year>=2023);
 const value=(c,k)=>typeof c[k]==='number'?c[k]:-9999;
 arr.sort((a,b)=>{
   switch(state.sort){
     case 'dip':return value(a,'change30')-value(b,'change30');
     case 'hype':return value(b,'hype')-value(a,'hype');
     case 'priceLow':return value(a,'price')-value(b,'price');
     case 'priceHigh':return value(b,'price')-value(a,'price');
     case 'newest':return b.year-a.year;
     default:return value(b,'score')-value(a,'score') || value(b,'hype')-value(a,'hype');
   }
 });
 return arr;
}
function cardMarkup(c){
 const hasPrice=cardVisible(c),c7=c.change7;
 const trendClass=typeof c.change30==='number'?(c.change30<0?'red':c.change30>0?'green':'neutral'):'neutral';
 const image=validUrl(c.image);
 const art=image ? `<img class="card-art" src="${escapeHtml(image)}" loading="lazy" alt="${safeText(c.name)} card artwork" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'art-fallback',textContent:'CARD ART'}))">` : `<div class="art-fallback"><b>${safeText(c.name)}</b></div>`;
 const pill=hasPrice?signalText[c.signal]||'WATCH':c.price>100?'OVER $100':'AWAITING DATA';
 const tcg=validUrl(c.tcgplayerUrl)||`https://www.tcgplayer.com/search/pokemon/product?productLineName=pokemon&q=${encodeURIComponent(`${c.name} ${c.number} ${c.set}`)}`;
 const mint=validUrl(c.tickermintUrl);
 return `<article class="card" data-key="${safeText(c.key)}" tabindex="0" aria-label="View ${safeText(c.name)} details">
   <div class="card-top"><a class="card-art-link" href="${escapeHtml(tcg)}" target="_blank" rel="noopener noreferrer" aria-label="See ${safeText(c.name)} on TCGplayer">${art}</a><span class="signal-pill ${sigClass(c)}">${pill}</span><button class="star-button ${state.saved.has(c.key)?'saved':''}" data-save="${safeText(c.key)}" aria-label="${state.saved.has(c.key)?'Remove':'Save'} ${safeText(c.name)}">${state.saved.has(c.key)?'★':'☆'}</button></div>
   <div class="card-main"><div class="card-rarity">${safeText(c.rarity)} · ${c.year}</div><h3 class="card-title" title="${safeText(c.name)}"><a href="${escapeHtml(tcg)}" target="_blank" rel="noopener noreferrer" aria-label="See ${safeText(c.name)} on TCGplayer">${safeText(c.name)} ↗</a></h3><div class="card-set">${safeText(c.set)} · ${safeText(c.number)}</div>
   <div class="card-prices"><div><span class="price-caption">${mint ? `<a href="${escapeHtml(mint)}" target="_blank" rel="nofollow noopener noreferrer" aria-label="TickerMint source for ${safeText(c.name)}">Market price ↗</a>` : 'Market price'}</span><strong class="market-value">${cardPriceLabel(c)}</strong></div><div><span class="trend-caption">30-day move</span><div class="change ${trendClass}">${signed(c.change30)}</div></div></div>
   <div class="bottom-card"><div><div class="hype-caption">Fan appeal <b>${c.hype}/100</b></div><div class="hype-track"><span style="width:${Math.max(0,Math.min(100,Number(c.hype)||0))}%"></span></div></div><div class="score-pill ${c.score===null?'na':''}">${c.score===null?'NO SIGNAL':`${c.score} / 100`}</div></div>
   </div></article>`;
}
function draw(){
 setStatus();
 const list=getCards();const items=list.slice(0,state.limit);
 $('cardgrid').innerHTML=items.map(cardMarkup).join('');
 $('emptyState').hidden=items.length>0;
 $('moreRow').hidden=list.length<=state.limit;
 const availability=state.meta.successCount===0?' First data sync has not completed; sample prices are intentionally not shown.':'';
 $('resultText').textContent=`Showing ${items.length} of ${list.length} matching cards.${availability}`;
 if(!list.length && state.tab==='all' && state.meta.successCount===0){
   $('emptyState').querySelector('h3').textContent='Waiting for the first daily data sync';
   $('emptyState').querySelector('p').textContent='The watchlist is loaded, but we have not verified today\'s market prices yet. Deploy the GitHub workflow to populate live recommendations, or open Saved to scout the roster.';
 }else{
   $('emptyState').querySelector('h3').textContent='No cards match these filters';
   $('emptyState').querySelector('p').textContent='Try another rarity, year, or signal category. Cards over $100 and stale prices are excluded from recommendations.';
 }
 document.querySelectorAll('.tab').forEach(b=>{const on=b.dataset.tab===state.tab;b.classList.toggle('active',on);b.setAttribute('aria-selected',on?'true':'false')});
}
function trendSvg(c){
 const points=(c.history||[]).filter(p=>Array.isArray(p)&&Number.isFinite(Number(p[1]))).slice(-90);
 if(points.length<3)return '<div class="chart-empty">Historical chart becomes available after a successful data sync.</div>';
 const prices=points.map(d=>Number(d[1])),min=Math.min(...prices),max=Math.max(...prices),range=(max-min)||1;
 const p=prices.map((y,i)=>[32+i*612/(prices.length-1),134-(y-min)/range*102]);
 const d=p.map(([x,y],i)=>(i?'L':'M')+x.toFixed(1)+' '+y.toFixed(1)).join(' ');
 const fill=d+` L${p.at(-1)[0].toFixed(1)} 142 L32 142 Z`;
 return `<svg role="img" aria-label="${safeText(c.name)} last ${points.length} observed daily prices" viewBox="0 0 675 170" preserveAspectRatio="none">
 <defs><linearGradient id="linegrad" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7fe4cf" stop-opacity=".26"/><stop offset="1" stop-color="#7fe4cf" stop-opacity="0"/></linearGradient></defs>
 <path d="M32 32 H644 M32 83 H644 M32 134 H644" stroke="#2b4a59" stroke-width="1" fill="none" stroke-dasharray="3 5"/>
 <path d="${fill}" fill="url(#linegrad)"/><path d="${d}" stroke="#95eadd" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
 <circle cx="${p.at(-1)[0]}" cy="${p.at(-1)[1]}" r="4" fill="#adfff0"/>
 <text x="3" y="34" font-size="11" fill="#a7c2d5">${escapeHtml(usd(max))}</text><text x="3" y="138" font-size="11" fill="#a7c2d5">${escapeHtml(usd(min))}</text>
 <text x="32" y="161" font-size="11" fill="#a7c2d5">${safeText(points[0][0])}</text><text x="644" y="161" text-anchor="end" font-size="11" fill="#a7c2d5">${safeText(points.at(-1)[0])}</text></svg>`;
}
function openModal(html){$('modalContent').innerHTML=html;$('modalScrim').hidden=false;document.body.style.overflow='hidden';$('modalClose').focus()}
function closeModal(){$('modalScrim').hidden=true;document.body.style.overflow=''}
function cardDetails(c){
 const tcg=validUrl(c.tcgplayerUrl)||`https://www.tcgplayer.com/search/pokemon/product?productLineName=pokemon&q=${encodeURIComponent(`${c.name} ${c.number} ${c.set}`)}`;
 const mint=validUrl(c.tickermintUrl),image=validUrl(c.image);
 const status=c.price>100?'Outside the under-$100 budget':c.stale?'Price is stale — recommendation suppressed':(signalText[c.signal]||'Awaiting data');
 const trendRow=`<div class="modal-grid"><div><small>7D change</small><strong>${signed(c.change7)}</strong></div><div><small>30D change</small><strong>${signed(c.change30)}</strong></div><div><small>90D peak drawdown</small><strong>${signed(c.drawdown90)}</strong></div></div>`;
 openModal(`<div class="modal-eyebrow">${safeText(c.rarity)} · ${safeText(c.set)} · ${safeText(c.number)}</div><div class="modal-top">${image?`<img class="modal-art" src="${escapeHtml(image)}" alt="${safeText(c.name)} artwork">`:''}<div><h2 id="modalTitle">${safeText(c.name)}</h2><p>${safeText(c.set)} (${c.year}) · ${status}</p><strong style="font:700 28px var(--display)">${cardPriceLabel(c)}</strong><div style="color:#95d6db;font-size:11px;margin-top:5px">Market aggregate · ${safeText(c.asOf||'no verified date')} · not a Near Mint quote</div></div></div>
 ${trendRow}<div class="chart-section"><div class="chart-title">Daily market-price history · most recent 90 observations</div><div class="chart-box">${trendSvg(c)}</div></div>
 <div class="modal-note"><b>Why this signal:</b> ${safeText(c.reason)} ${c.signal==='buy'?'This is a screening signal, not a guarantee of future gains.':''}</div>
 <p><b>Fan appeal:</b> ${c.hype}/100, an editorial popularity estimate, not measured searches or transactions. <b>Opportunity:</b> ${c.score===null?'Insufficient evidence':c.score+'/100'}.</p>
 <div class="modal-actions"><a href="${escapeHtml(tcg)}" target="_blank" rel="noopener noreferrer">Check on TCGplayer ↗</a>${mint?`<a class="secondary" href="${escapeHtml(mint)}" target="_blank" rel="noopener noreferrer">Price source: TickerMint ↗</a>`:''}</div>
 <div class="mini-disclaimer">TCGplayer links open a card search unless a verified direct product page is available. Review the exact printing, seller condition (Near Mint), shipping and fees before buying. Historical market data does not establish condition-specific executable prices.</div>`);
}
function methodDetails(){
 openModal(`<div class="modal-eyebrow">POKÉRADAR / HOW SIGNALS WORK</div><h2 id="modalTitle">The buy, wait and watch logic</h2><p>The dashboard favors disciplined entries after significant corrections. It does not predict price direction or guarantee returns.</p>
 <ol class="modal-list"><li><b>Scope:</b> English Pokémon singles, 2017–present, IR, SIR, alternate art, Galarian Gallery and a curated selection of earlier chase cards. Candidates are a scouting list, not every printed card. Current raw-market values under $100 are eligible.</li>
 <li><b>BUY NOW:</b> price at least 18% below its rolling 90-day peak; at least 7% down in 30 days; the last 7 days between -3% and +4%; fan score at least 75; at least 28 observed days.</li>
 <li><b>WAIT:</b> a decline of at least 12% from the 90-day peak or 10% over 30 days, alongside unfavorable recent price momentum.</li>
 <li><b>WATCH:</b> all other verified sub-$100 cards without a clear signal, or cards with insufficient observation history.</li>
 <li><b>Score (0–100):</b> 37% drawdown magnitude, 26% editorial fan appeal, 27% trend quality, 10% card age. This is a simple heuristic and is not backtested.</li>
 <li><b>Limitations:</b> no transaction volume, auction liquidity, social search index, graded prices, fees, reprint schedule, or verified Near Mint prices are included. These inputs can materially change whether a card is a good buy.</li></ol>
 <div class="modal-note">Price source: <a href="https://tickermint.cards/developers" target="_blank" rel="noopener noreferrer"><u>TickerMint</u></a> (TCGplayer-derived aggregates); its history starts February 2024, so older cards don't have observations all the way back to release. The GitHub Actions publisher runs daily, but the Refresh button only reloads the newest published snapshot.</div>`);
}
function exportCsv(){
 const data=getCards();if(!data.length){alert('No matching cards to export.');return}
 const fields=['name','set','number','year','rarity','tcgplayerUrl','tickermintUrl']; // Export identifiers and links only: source data license does not grant price-dataset export rights.
 const quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
 const csv=[fields.join(','),...data.map(c=>fields.map(f=>quote(c[f])).join(','))].join('\r\n');
 const blob=new Blob([csv],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='pokeradar-shortlist-links.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
}
async function loadData(){
 if(state.loading)return;state.loading=true;
 $('refreshBtn').classList.add('spinning');
 $('dataStatus').textContent='Loading snapshot…';
 try{
  const r=await fetch(`data.json?cacheBust=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);
  const x=await r.json();if(!Array.isArray(x.cards))throw new Error('Invalid data format');
  state.cards=x.cards;state.meta=x;
 }catch(e){console.error(e);$('dataStatus').textContent='Data unavailable';$('resultText').textContent='Could not load data.json. Open this site through a web server, not as a file, and retry.';}
 finally{state.loading=false;$('refreshBtn').classList.remove('spinning');draw();}
}
$('tabbar').addEventListener('click',e=>{const b=e.target.closest('[data-tab]');if(!b)return;state.tab=b.dataset.tab;state.limit=16;draw()});
$('searchInput').addEventListener('input',e=>{state.query=e.target.value.trim();state.limit=16;draw()});
$('raritySelect').addEventListener('change',e=>{state.rarity=e.target.value;state.limit=16;draw()});
$('yearSelect').addEventListener('change',e=>{state.year=e.target.value;state.limit=16;draw()});
$('sortSelect').addEventListener('change',e=>{state.sort=e.target.value;draw()});
$('moreBtn').addEventListener('click',()=>{state.limit+=16;draw()});
$('resetFilters').addEventListener('click',()=>{state.tab='all';state.query='';state.rarity='all';state.year='all';state.sort='score';state.limit=16;$('searchInput').value='';$('raritySelect').value='all';$('yearSelect').value='all';$('sortSelect').value='score';draw()});
$('cardgrid').addEventListener('click',e=>{
 if(e.target.closest('a'))return;
 const btn=e.target.closest('[data-save]');if(btn){const key=btn.dataset.save;if(state.saved.has(key))state.saved.delete(key);else state.saved.add(key);try{localStorage.setItem('pokeradar_saved',JSON.stringify([...state.saved]))}catch(_){ }draw();return}
 const el=e.target.closest('[data-key]');if(el){const c=state.cards.find(c=>c.key===el.dataset.key);if(c)cardDetails(c)}
});
$('cardgrid').addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ') && !e.target.closest('button')){const el=e.target.closest('[data-key]');if(el){e.preventDefault();const c=state.cards.find(c=>c.key===el.dataset.key);if(c)cardDetails(c)}}});
$('refreshBtn').addEventListener('click',loadData);$('helpBtn').addEventListener('click',methodDetails);$('methodBtn').addEventListener('click',methodDetails);$('exportBtn').addEventListener('click',exportCsv);
$('modalClose').addEventListener('click',closeModal);$('modalScrim').addEventListener('click',e=>{if(e.target===$('modalScrim'))closeModal()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});
loadData();
