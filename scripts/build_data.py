import csv, io, json, math, re, unicodedata, urllib.request, zipfile, time
from pathlib import Path

CENTER_LAT, CENTER_LON, RADIUS_M = 50.5309, 15.3734, 5000
RES_URL='https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv'
RES_LOCAL=Path('res_data.csv')
RUIAN_INDEX_URL='https://services.cuzk.cz/atom-index/RUIAN-CSV-ADR-OB/5513/'
OUT=Path('data/firms.json')
MUNICIPALITIES={'577308','577341','577014','577294','577545','577553','577235','577243','577197','576999','577120','577154','577421','577472','577481','577499','577529','577561','577316','577332','577359','577367','577391','577413','577430','577448'}

def haversine(a,b):
    p=math.pi/180; dlat=(b[0]-a[0])*p; dlon=(b[1]-a[1])*p
    h=math.sin(dlat/2)**2+math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(h))

def normalize_header(value):
    value=unicodedata.normalize('NFKD', value or '')
    value=''.join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z0-9]+','_',value.upper()).strip('_')

def load_res():
    if RES_LOCAL.exists() and RES_LOCAL.stat().st_size > 10_000_000:
        raw=RES_LOCAL.read_bytes()
    else:
        req=urllib.request.Request(RES_URL,headers={'Accept-Encoding':'gzip','User-Agent':'podnikatelska-mapa-lomnice/1.0'})
        last=None
        for attempt in range(1,4):
            try:
                with urllib.request.urlopen(req,timeout=300) as r: raw=r.read()
                break
            except Exception as e:
                last=e; print(f'RES download attempt {attempt}/3 failed: {e}'); time.sleep(5*attempt)
        else: raise last
    import gzip
    try: raw=gzip.decompress(raw)
    except OSError: pass
    rows=[]
    for r in csv.DictReader(io.StringIO(raw.decode('utf-8'))):
        if r.get('ICZUJ') in MUNICIPALITIES and not r.get('DDATZAN'): rows.append(r)
    print(f'RES: {len(rows)} active entities in selected municipalities')
    return rows

def ruian_links():
    req=urllib.request.Request(RUIAN_INDEX_URL,headers={'User-Agent':'podnikatelska-mapa-lomnice/1.0'})
    html=urllib.request.urlopen(req,timeout=120).read().decode('utf-8','replace'); links={}
    for m in re.finditer(r'href=["\']([^"\']+\.zip)["\']',html,re.I):
        href=m.group(1)
        for code in MUNICIPALITIES:
            if re.search(rf'_{re.escape(code)}_',href):
                from urllib.parse import urljoin
                links[code]=href if href.startswith('http') else urljoin(RUIAN_INDEX_URL,href)
    print(f'RUIAN: found {len(links)}/{len(MUNICIPALITIES)} municipality address files'); return links

def load_ruian(kods):
    from pyproj import Transformer
    tr=Transformer.from_crs('EPSG:5514','EPSG:4326',always_xy=True); result={}
    for code,url in ruian_links().items():
        data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'podnikatelska-mapa-lomnice/1.0'}),timeout=180).read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if not name.lower().endswith('.csv'): continue
                with z.open(name) as f:
                    text=f.read().decode('cp1250',errors='strict').lstrip('\ufeff')
                    try: dialect=csv.Sniffer().sniff(text[:4096],delimiters=';,|\t')
                    except csv.Error: dialect=csv.excel
                    for original in csv.DictReader(io.StringIO(text),dialect=dialect):
                        row={normalize_header(k):(v or '') for k,v in original.items()}
                        k=(row.get('KOD_ADM') or row.get('KODADM') or row.get('KOD_ADRESNIHO_MISTA') or '').strip()
                        if k not in kods: continue
                        y=(row.get('SOURADNICE_Y') or '').strip(); x=(row.get('SOURADNICE_X') or '').strip()
                        if not y or not x: continue
                        try:
                            # RUIAN uses Czech S-JTSK columns X (northing) and Y (easting).
                            # pyproj with always_xy=True expects EPSG:5514 input as (easting, northing), i.e. (Y, X).
                            lon,lat=tr.transform(float(y.replace(',','.')),float(x.replace(',','.'))); result[k]=(lat,lon,row)
                        except (ValueError,TypeError): pass
    print(f'RUIAN: matched {len(result)} RES addresses'); return result

def clean(row,geo):
    lat,lon,ruian=geo; d=haversine((CENTER_LAT,CENTER_LON),(lat,lon))
    if d>RADIUS_M: return None
    nace=row.get('NACE2025') or row.get('NACE') or ''
    address=row.get('TEXTADR','') or ' '.join(x for x in [ruian.get('NAZEV_ULICE',''),ruian.get('CISLO_DOMOVNI',''),ruian.get('NAZEV_OBCE','')] if x)
    return {'name':row.get('FIRMA',''),'ico':row.get('ICO',''),'lat':lat,'lon':lon,'distance_m':round(d),'sector':nace,'nace':nace,'size':row.get('KATPO',''),'legal':row.get('FORMA',''),'address':address,'kodadm':row.get('KODADM',''),'workers_local':None,'workers_note':'Kategorie pracovníků je údaj za ekonomický subjekt; místní zaměstnanost zatím není ověřena.','source':'ČSÚ RES + ČÚZK RÚIAN'}

if __name__=='__main__':
    rows=load_res(); kods={str(r.get('KODADM')).strip() for r in rows if r.get('KODADM')}; print(f'RES: {len(kods)} unique KODADM values'); geo=load_ruian(kods); out=[]
    for r in rows:
        kodadm=str(r.get('KODADM')).strip()
        if kodadm in geo:
            item=clean(r,geo[kodadm])
            if item: out.append(item)
    out.sort(key=lambda x:(x['distance_m'],x['name'].lower())); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(f'Created {len(out)} businesses')
    if not out: raise RuntimeError('No businesses generated; refusing to publish empty dataset')
