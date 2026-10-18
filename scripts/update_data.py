#!/usr/bin/env python3
"""Refresh personal TickerMint watchlist from server-side API calls.

No fabricated prices: failures leave existing prices, explicitly dated/stale.
Only market-price aggregates (NOT condition-specific Near Mint quotations) are exposed.
"""
import json, math, os, re, sys, time, requests
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlencode, quote

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'site' / 'data.json'
ROSTER_PATH = ROOT / 'scripts' / 'roster.json'
MAP_PATH = ROOT / 'scripts' / 'resolved_ids.json'
API = 'https://api.tickermint.cards'
NOW = datetime.now(timezone.utc)
UA = 'PokemonCardRadar/1.0 (personal noncommercial tracker; attribution to TickerMint)'
MAX_REQUESTS = int(os.getenv('MAX_API_REQUESTS','550'))
request_count = 0
_last_fetch_at = 0.0

def fetch(path):
    global request_count, _last_fetch_at
    # Respect public-IP and stricter search endpoint rate limits.
    gap = float(os.getenv('API_MIN_INTERVAL_SECONDS', '0.8'))
    wait = gap - (time.monotonic() - _last_fetch_at)
    if wait > 0: time.sleep(wait)
    _last_fetch_at = time.monotonic()
    if request_count >= MAX_REQUESTS: raise RuntimeError('request budget exhausted')
    request_count += 1
    url = API + path
    headers = {'User-Agent': UA, 'Accept':'application/json'}
    if os.getenv('TICKERMINT_KEY'): headers['X-API-Key'] = os.getenv('TICKERMINT_KEY')
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=24)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == 2: raise
            time.sleep(min(10, 1.7 ** attempt * 2))
    return None

def numbers(s):
    s = str(s or '').upper().strip()
    m=re.search(r'(?<![A-Z0-9])(?:SV|GG|TG)?\d{1,4}\s*/\s*(?:SV|GG|TG)?\d{1,4}',s)
    return re.sub(r'\s+','',m.group()) if m else ''

def canonical_number(s):
    n=numbers(s)
    if not n:return ''
    parts=[]
    for p in n.split('/'):
        m=re.fullmatch(r'([A-Z]*)([0-9]+)',p)
        parts.append(m.group(1)+str(int(m.group(2))) if m else p)
    return '/'.join(parts)

def normalize_set(s):
    s=str(s or '').lower().replace('pokémon','pokemon')
    s=re.sub(r'\b(?:sv|swsh|sm|sun & moon|sword & shield|scarlet & violet)\s*:\s*','',s)
    return re.sub(r'[^a-z0-9]+','',s)

def list_items(payload):
    if isinstance(payload,list): return payload
    if isinstance(payload,dict):
        for field in ('results','data','products','cards','items','matches'):
            if isinstance(payload.get(field),list):return payload[field]
    return []

def first(obj,*names):
    for name in names:
        if isinstance(obj,dict) and obj.get(name) is not None: return obj[name]
    return None

def nfloat(v):
    if isinstance(v,bool): return None
    try:
        result=float(str(v).replace('$','').replace(',',''))
        if 0<result<1e7 and math.isfinite(result):return round(result,2)
    except (ValueError,TypeError): pass
    return None

def resolve(seed, old):
    # A cached product ID is safe only after it was verified by name, set and collector number.
    if old and old.get('productId') and old.get('verifiedMatch'):return old
    query = (seed['name']+' '+seed['number']).strip()
    hits=list_items(fetch('/products/search?'+urlencode({'q':query,'game':'pokemon'})))
    desired=canonical_number(seed['number'])
    expected=normalize_set(seed['set'])
    scored=[]
    for hit in hits:
        if not isinstance(hit,dict):continue
        text=' '.join(str(hit.get(k) or '') for k in ('name','number','card_number','collector_number','set_name','set'))
        got=canonical_number(first(hit,'number','card_number','collector_number') or text)
        name=str(hit.get('name') or '').lower()
        rawset=first(hit,'set_name','set','group_name')
        if isinstance(rawset,dict):rawset=rawset.get('name','')
        sets=normalize_set(rawset)
        if not desired or not got or desired!=got:continue
        if expected and not sets or (expected and not (expected in sets or sets in expected)):continue
        if seed['name'].lower().split()[0].replace("'",'') not in name.replace("'",''):continue
        pid=first(hit,'product_id','productId','id')
        if pid is None:continue
        scored.append((len(name),hit,pid))
    if not scored:return None
    _,hit,pid=sorted(scored,key=lambda x:x[0])[0]
    return {'productId':int(pid),'verifiedMatch':True,'tickermintUrl':first(hit,'tickermint_url','url') or f'https://tickermint.cards/card/{pid}',
            'image':first(hit,'image_url','image','imageUrl') or '', 'marketAtScan': nfloat(hit.get('market')),
            'tcgplayerUrl':first(hit,'tcgplayer_url','tcgplayerUrl') or ''}

def parse_history(payload):
    """Documented payload shape: {'Holofoil':[{'snapshot_date':'2026-10-08','market':42.50}, ...]}."""
    if isinstance(payload,dict):
        raw=first(payload,'data','history','prices') or payload
    else:raw=payload
    if isinstance(raw,list):
        grouped={}
        for d in raw:
            if isinstance(d,dict): grouped.setdefault(str(first(d,'printing','variant','subTypeName') or 'Holofoil'),[]).append(d)
    elif isinstance(raw,dict):
        grouped={k:v for k,v in raw.items() if isinstance(v,list)}
    else:grouped={}
    candidates=[]
    for printing, rows in grouped.items():
        if re.search('reverse|non.holo|normal',printing,re.I):continue
        clean={}
        for point in rows:
            if not isinstance(point,dict):continue
            d=str(first(point,'snapshot_date','date','as_of','timestamp') or '')[:10]
            try:date.fromisoformat(d)
            except ValueError:continue
            price=nfloat(first(point,'market','market_price','marketPrice','market_price_usd','price'))
            if price: clean[d]=price
        if clean:
            ordered=sorted(clean.items())
            candidates.append((2 if 'holofoil' in printing.lower() else 1,len(ordered),printing,ordered))
    if not candidates:return [],''
    _,_,printing,series=max(candidates,key=lambda x:(x[0],x[1]))
    # Keep only latest 120 daily points to control hosted JSON size.
    return [[day,value] for day,value in series[-120:]], printing

def nearest_price(series, days):
    if not series:return None
    lastday=date.fromisoformat(series[-1][0]); target=lastday.toordinal()-days
    eligible=[(abs(date.fromisoformat(d).toordinal()-target),v) for d,v in series[:-1] if abs(date.fromisoformat(d).toordinal()-target)<=max(3,int(days*.25))]
    return min(eligible)[1] if eligible else None

def metrics(series):
    if not series:return {'price':None,'change7':None,'change30':None,'change90':None,'drawdown90':None,'days':0}
    p=series[-1][1]
    def ch(days):
        prior=nearest_price(series,days)
        return round((p/prior-1)*100,1) if prior else None
    lastdate=date.fromisoformat(series[-1][0]); cutoff=lastdate.toordinal()-90
    recent=[v for d,v in series if date.fromisoformat(d).toordinal()>=cutoff]
    high=max(recent) if recent else p
    return {'price':p,'change7':ch(7),'change30':ch(30),'change90':ch(90),
            'drawdown90':round((p/high-1)*100,1) if high else None,'days':len(series), 'high90':round(high,2)}

def recommendation(m,hype,age):
    p=m.get('price');c7=m.get('change7');c30=m.get('change30');drop=m.get('drawdown90')
    if p is None:return 'pending',None,'Waiting for a verified market-price history.'
    if p>100:return 'over',None,'Market price is above your $100 limit.'
    if p<1:return 'watch',None,'Very low-priced card; limited investment signal.'
    if c7 is None or c30 is None or drop is None:
        return 'watch',None,'Not enough history to confirm a price correction and trend.'
    # 0–100 opportunity score blends opportunity and pop-culture appeal.
    decline=min(100, max(0,-drop)*3.5)
    trend= 100 if -2<=c7<=3 else 65 if -4<=c7< -2 else 42 if c7 < -4 else 52
    strength=max(0,min(100,65+min(18,age*2.5)))
    score=round(.37*decline+.26*hype+.27*trend+.10*strength)
    if drop<=-18 and c30<=-7 and -3<=c7<=4 and hype>=75 and m['days']>=28:
        return 'buy',score,'Significant 90-day pullback with relatively stable 7-day pricing; verify condition and liquidity.'
    if (drop<=-12 or c30<=-10) and (c7 < -3 or c30 < -16 and c7 < 0):
        return 'wait',score,'Price correction is still showing negative short-term momentum.'
    if drop<=-10 and hype>=75:
        return 'watch',score,'Strong collector appeal and a pullback, but the entry signal is not fully confirmed.'
    return 'watch',score,'No strong correction-plus-stabilization signal at current pricing.'


def nested_candidates(obj, depth=0):
    """Yield records from mover/lows feeds, tolerating arrays grouped by gainers/losers."""
    if depth>5:return
    if isinstance(obj,list):
        for val in obj:yield from nested_candidates(val,depth+1)
    elif isinstance(obj,dict):
        if first(obj,'product_id','productId') is not None:
            yield obj
        else:
            for k,v in obj.items():
                if isinstance(v,(list,dict)):
                    yield from nested_candidates(v,depth+1)

def infer_rarity(r):
    txt=str(r or '').lower().replace('_',' ')
    if 'special illustration' in txt or txt.strip()=='sir':return 'SIR'
    if 'illustration rare' in txt or txt.strip()=='ir':return 'IR'
    if 'alternate art' in txt or 'alt art' in txt:return 'Alt Art'
    if 'galarian gallery' in txt or 'trainer gallery' in txt:return 'Galarian Gallery'
    return None

def derive_year(obj,known_set_years):
    raw=first(obj,'release_date','set_release_date','released_at','releaseDate','setReleaseDate')
    if not raw and isinstance(obj.get('set'),dict):
        raw=first(obj['set'],'release_date','releaseDate','year')
    if raw:
        match=re.search(r'20(?:1[7-9]|2[0-9])',str(raw))
        if match and int(match.group())<=NOW.year:return int(match.group())
    group=first(obj,'set_name','set','group_name')
    if isinstance(group,dict):group=first(group,'name','set_name')
    return known_set_years.get(normalize_set(group))

def discover(seeds):
    """Find additional IR/SIR/Alt-Art candidates currently on market mover and low boards.

    This is a rolling discovery sample, NOT an exhaustive universe scan. New entries
    must have clear rarity, collector number, set, and known release year.
    """
    known={(normalize_set(r['set']),canonical_number(r['number'])) for r in seeds}
    years={normalize_set(r['set']):r['year'] for r in seeds}
    favorites={'pikachu':98,'charizard':98,'umbreon':99,'gengar':98,'eevee':96,'mewtwo':93,'mew':94,'greninja':95,'rayquaza':94,'dragonite':92,'giratina':93,'lugia':93,'espeon':93,'sylveon':94,'bulbasaur':90,'squirtle':92,'meowth':87,'lucario':91,'darkrai':89,'gardevoir':88,'suicune':86,'tyranitar':87,'magikarp':91,'arceus':92,'snorlax':89,'garchomp':86,'flareon':89,'vaporeon':89,'jolteon':89}
    candidate_ids=[]
    for path in ['/desk/movers?game=pokemon&days=30&min_market=5',
                 '/desk/movers?game=pokemon&days=90&min_market=5',
                 '/desk/lows?game=pokemon']:
        try:
            for c in nested_candidates(fetch(path)):
                pid=first(c,'product_id','productId')
                if pid is not None and str(pid).isdigit() and pid not in candidate_ids:
                    candidate_ids.append(int(pid))
        except Exception as e:
            print('Discovery board unavailable:',str(e),file=sys.stderr)
    added=[]
    for pid in candidate_ids[:80]:
        if len(added)>=20 or request_count>=MAX_REQUESTS-50:break
        try:
            product=fetch(f'/products/{pid}')
            if isinstance(product,dict) and isinstance(product.get('product'),dict):product=product['product']
            if not isinstance(product,dict):continue
            rarity=infer_rarity(first(product,'rarity','rarity_name','rarityName'))
            if not rarity:continue
            n=first(product,'number','card_number','collector_number','collectorNumber')
            setname=first(product,'set_name','group_name','set')
            if isinstance(setname,dict):setname=first(setname,'name','set_name')
            name=first(product,'name','product_name')
            if not n or not setname or not name:continue
            n=numbers(n) or numbers(name)
            if not n or (normalize_set(setname),canonical_number(n)) in known:continue
            year=derive_year(product,years)
            if not year or year<2017:continue
            shortname=re.sub(r'\s*[-–]\s*(?:[A-Z]*\d+/[A-Z]*\d+).*$', '',str(name)).strip()
            h=max([score for word,score in favorites.items() if re.search(r'\b'+re.escape(word)+r'\b',shortname,re.I)] or [65])
            added.append({'name':shortname,'set':str(setname),'number':n,'year':year,'rarity':rarity,'hype':h,'discovered':True})
            known.add((normalize_set(setname),canonical_number(n)))
        except Exception as e:
            print('Discovery candidate rejected:',pid,str(e),file=sys.stderr)
    return added

def search_url(seed):
    q=(seed['name']+' '+seed['number']+' '+seed['set']).strip()
    return 'https://www.tcgplayer.com/search/pokemon/product?'+urlencode({'productLineName':'pokemon','q':q,'view':'grid'})

def main():
    seeds=json.loads(ROSTER_PATH.read_text())
    olddata=json.loads(DATA_PATH.read_text()) if DATA_PATH.exists() else {}
    existing={x['key']:x for x in olddata.get('cards',[])}
    known=json.loads(MAP_PATH.read_text()) if MAP_PATH.exists() else {}
    # Retain previously verified discovered catalog members across daily updates.
    seeds.extend([{'name':c['name'],'set':c['set'],'number':c['number'],'year':c['year'],
                   'rarity':c['rarity'],'hype':c['hype'],'discovered':True} for c in existing.values()
                  if c.get('discovered') and c.get('verifiedMatch') and not any(
                    c['set'].lower()==s['set'].lower() and canonical_number(c['number'])==canonical_number(s['number']) for s in seeds)])
    if os.getenv('SKIP_DISCOVERY')!='1':seeds.extend(discover(seeds))
    rows=[];success=0;errors=[]
    for idx,seed in enumerate(seeds,1):
        key=f"{seed['set']}|{seed['number']}".lower()
        prior=existing.get(key) or known.get(key,{})
        row={'key':key,**seed,'hypeType':'Editorial fan-demand proxy (not search/social measurement)',
             'tcgplayerUrl':prior.get('tcgplayerUrl') or search_url(seed),
             'tickermintUrl':prior.get('tickermintUrl',''), 'image':prior.get('image',''),
             'productId':prior.get('productId'), 'verifiedMatch':prior.get('verifiedMatch',False),
             'history':prior.get('history',[]), 'asOf':prior.get('asOf'), 'printing':prior.get('printing',''),
             'lastChecked':prior.get('lastChecked')}
        try:
            resolved=resolve(seed,prior)
            if resolved is None:
                raise ValueError('No exact set+card-number match in provider search')
            row.update({k:v for k,v in resolved.items() if v or k in ('productId','verifiedMatch')})
            # TickerMint IDs do not establish a verified TCGplayer product URL.
            # Fall back to a precise TCGplayer search, never an assumed product ID.
            direct = resolved.get('tcgplayerUrl', '')
            row['tcgplayerUrl'] = direct if 'tcgplayer.com/' in direct else search_url(seed)
            history,printing=parse_history(fetch(f"/products/{row['productId']}/prices"))
            if not history: raise ValueError('No parseable Holofoil/market daily price history')
            row['history']=history
            row['printing']=printing
            row['asOf']=history[-1][0]
            row['lastChecked']=NOW.isoformat()
            success+=1
        except Exception as e:
            errors.append(f"{seed['name']} {seed['number']} ({seed['set']}): {e}")
        m=metrics(row['history'])
        signal,score,reason=recommendation(m,seed['hype'],NOW.year-seed['year'])
        row.update(m)
        row.update({'signal':signal,'score':score,'reason':reason,'stale':bool(row.get('asOf') and (date.today()-date.fromisoformat(row['asOf'])).days>3)})
        rows.append(row)
        print(f'[{idx:02d}/{len(seeds)}] {seed["name"]:25} {row["signal"]:8} {row["price"]!s:>8}',flush=True)
        if os.getenv('FAST_TEST')!='1':time.sleep(.9)
    # On a total API outage, do not overwrite a previously healthy data cache.
    if success==0 and any(x.get('asOf') for x in existing.values()):
        print('No fresh data; preserving previous valid snapshot',file=sys.stderr)
    data={'schemaVersion':1,'generatedAt':NOW.isoformat(),'provider':'TickerMint · TCGplayer-derived market price',
          'providerUrl':'https://tickermint.cards/developers','priceBasis':'Per-printing aggregate raw market price; not guaranteed Near Mint',
          'marketHistoryBegins':'2024-02-08', 'maxPrice':100,'successCount':success,
          'trackedCount':len(rows),'errors':errors[:15],'cards':rows}
    DATA_PATH.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
    for row in rows:
        if row.get('verifiedMatch') and row.get('productId'):
            known[row['key']]={k:row.get(k) for k in ('productId','verifiedMatch','image','tickermintUrl','tcgplayerUrl')}
    MAP_PATH.write_text(json.dumps(known,ensure_ascii=False,indent=2)+'\n')
    print(f'Saved {DATA_PATH}; {success} refreshed, {len(errors)} errors, {request_count} API requests')
    # Failing workflows should not publish an all-empty dataset silently.
    if success==0:sys.exit(2)

if __name__=='__main__': main()
