import csv, io, json, math, re, urllib.request, zipfile
from pathlib import Path

CENTER_LAT, CENTER_LON, RADIUS_M = 50.5309, 15.3734, 5000
RES_URL='https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv'
RUIAN_INDEX_URL='https://services.cuzk.cz/atom-index/RUIAN-CSV-ADR-OB/5513/'
OUT=Path('data/firms.json')
MUNICIPALITIES={'577308','577341','577343','577351','577381','577389','577397','577416','577421','577424','577432','577440','577441','577197','576999','577120','577154','577235','577243'}

def haversine(a,b):
    p=math.pi/180; dlat=(b[0]-a[0])*p; dlon=(b[1]-a[1])*p
    h=math.sin(dlat/2)**2+math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(h))

def load_res():
    req=urllib.request.Request(RES_URL,headers={'Accept-Encoding':'gzip','User-Agent':'podnikatelska-mapa-lomnice/1.0'})
    with urllib.request.urlopen(req) as r: raw=r.read()
    import gzip
    try: raw=gzip.decompress(raw)
    except OSError: pass
    rows=[]
    for r in csv.DictReader(io.StringIO(raw.decode('utf-8'))):
        if r.get('ICZUJ') in MUNICIPALITIES and not r.get('DDATZAN'):
            rows.append(r)
    print(f'RES: {len(rows)} active entities in selected municipalities')
    return rows

def ruian_links():
    req=urllib.request.Request(RUIAN_INDEX_URL,headers={'User-Agent':'podnikatelska-mapa-lomnice/1.0'})
    html=urllib.request.urlopen(req).read().decode('utf-8','replace')
    links={}
    for code in MUNICIPALITIES:
        m=re.search(r'href=["\']([^"\']*?_OB_'+re.escape(code)+r'_ADR\.csv\.zip)["\']',html,re.I)
        if m:
            href=m.group(1)
            links[code]=href if href.startswith('http') else 'https://services.cuzk.cz'+('/' if not href.startswith('/') else '')+href
    print(f'RUIAN: found {len(links)}/{len(MUNICIPALITIES)} municipality address files')
    return links

def load_ruian(kods):
    from pyproj import Transformer
    tr=Transformer.from_crs('EPSG:5514','EPSG:4326',always_xy=True); result={}
    for code,url in ruian_links().items():
        data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'podnikatelska-mapa-lomnice/1.0'})).read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if not name.lower().endswith('.csv'): continue
                with z.open(name) as f:
                    reader=csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
                    for row in reader:
                        k=row.get('KOD_ADM') or row.get('KODADM') or row.get('KOD_ADRESNIHO_MISTA')
                        if k not in kods: continue
                        y,x=row.get('SOURADNICE_Y'),row.get('SOURADNICE_X')
                        if not y or not x: continue
                        try:
                            lon,lat=tr.transform(float(x),float(y)); result[k]=(lat,lon,row)
                        except (ValueError,TypeError): pass
    print(f'RUIAN: matched {len(result)} RES addresses')
    return result

def clean(row,geo):
    lat,lon,_=geo; d=haversine((CENTER_LAT,CENTER_LON),(lat,lon))
    if d>RADIUS_M: return None
    nace=row.get('NACE2025') or row.get('NACE') or ''
    address=row.get('TEXTADR','') or ' '.join(x for x in [row.get('ULICE_TEXT',''),row.get('CDOM',''),row.get('OBEC_TEXT','')] if x)
    return {'name':row.get('FIRMA',''),'ico':row.get('ICO',''),'lat':lat,'lon':lon,'distance_m':round(d),'sector':nace,'nace':nace,'size':row.get('KATPO',''),'legal':row.get('FORMA',''),'address':address,'kodadm':row.get('KODADM',''),'workers_local':None,'workers_note':'Kategorie pracovníků je údaj za ekonomický subjekt; místní zaměstnanost zatím není ověřena.','source':'ČSÚ RES + ČÚZK RÚIAN'}

if __name__=='__main__':
    rows=load_res(); kods={r.get('KODADM') for r in rows if r.get('KODADM')}; print(f'RES: {len(kods)} unique KODADM values'); geo=load_ruian(kods); out=[]
    for r in rows:
        if r.get('KODADM') in geo:
            item=clean(r,geo)
            if item: out.append(item)
    out.sort(key=lambda x:(x['distance_m'],x['name'].lower())); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(f'Created {len(out)} businesses')
