import csv, io, json, math, re, unicodedata, urllib.request, zipfile
from pathlib import Path

CENTER_LAT, CENTER_LON, RADIUS_M = 50.5309, 15.3734, 5000
RES_URL='https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv'
RUIAN_INDEX_URL='https://services.cuzk.cz/atom-index/RUIAN-CSV-ADR-OB/5513/'
OUT=Path('data/firms.json')
# Broader set of nearby municipalities; the final 5 km radius is applied by coordinates.
MUNICIPALITIES={
    '577308','577341','577014','577294','577545','577553','577235','577243',
    '577197','576999','577120','577154','577421','577472','577481','577499',
    '577529','577561','577316','577332','577359','577367','577391','577413','577430','577448'
}

def haversine(a,b):
    p=math.pi/180; dlat=(b[0]-a[0])*p; dlon=(b[1]-a[1])*p
    h=math.sin(dlat/2)**2+math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(h))

def normalize_header(value):
    value=unicodedata.normalize('NFKD', value or '')
    value=''.join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z0-9]+','_',value.upper()).strip('_')

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
    # The official index links directly to vdp.cuzk.gov.cz ZIP files.
    for m in re.finditer(r'href=["\']([^"\']+\.zip)["\']', html, re.I):
        href=m.group(1)
        for code in MUNICIPALITIES:
            if re.search(rf'_{re.escape(code)}_', href):
                if href.startswith('http'):
                    links[code]=href
                else:
                    from urllib.parse import urljoin
                    links[code]=urljoin(RUIAN_INDEX_URL, href)
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
                    raw=f.read()
                    # RÚIAN municipal CSV is Windows-1250 and uses semicolons.
                    text=raw.decode('cp1250',errors='strict').lstrip('\ufeff')
                    sample=text[:4096]
                    try:
                        dialect=csv.Sniffer().sniff(sample,delimiters=';,|\t')
                    except csv.Error:
                        dialect=csv.excel
                    reader=csv.DictReader(io.StringIO(text),dialect=dialect)
                    for original in reader:
                        # Official headers are human-readable Czech names such as
                        # "Kód ADM" and "Souřadnice Y". Normalize them to stable keys.
                        row={normalize_header(k): (v or '') for k,v in original.items()}
                        k=(row.get('KOD_ADM') or row.get('KODADM') or row.get('KOD_ADRESNIHO_MISTA') or '').strip()
                        if k not in kods: continue
                        y=(row.get('SOURADNICE_Y') or '').strip(); x=(row.get('SOURADNICE_X') or '').strip()
                        if not y or not x: continue
                        try:
                            lon,lat=tr.transform(float(x.replace(',','.')),float(y.replace(',','.'))); result[k]=(lat,lon,row)
                        except (ValueError,TypeError): pass
    print(f'RUIAN: matched {len(result)} RES addresses')
    return result

def clean(row,geo):
    lat,lon,ruian=geo; d=haversine((CENTER_LAT,CENTER_LON),(lat,lon))
    if d>RADIUS_M: return None
    nace=row.get('NACE2025') or row.get('NACE') or ''
    address=row.get('TEXTADR','') or ' '.join(x for x in [ruian.get('NAZEV_ULICE',''),ruian.get('CISLO_DOMOVNI',''),ruian.get('NAZEV_OBCE','')] if x)
    return {'name':row.get('FIRMA',''),'ico':row.get('ICO',''),'lat':lat,'lon':lon,'distance_m':round(d),'sector':nace,'nace':nace,'size':row.get('KATPO',''),'legal':row.get('FORMA',''),'address':address,'kodadm':row.get('KODADM',''),'workers_local':None,'workers_note':'Kategorie pracovníků je údaj za ekonomický subjekt; místní zaměstnanost zatím není ověřena.','source':'ČSÚ RES + ČÚZK RÚIAN'}

if __name__=='__main__':
    rows=load_res(); kods={str(r.get('KODADM')).strip() for r in rows if r.get('KODADM')}; print(f'RES: {len(kods)} unique KODADM values'); geo=load_ruian(kods); out=[]
    for r in rows:
        if str(r.get('KODADM')).strip() in geo:
            item=clean(r,geo)
            if item: out.append(item)
    out.sort(key=lambda x:(x['distance_m'],x['name'].lower())); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(f'Created {len(out)} businesses')
