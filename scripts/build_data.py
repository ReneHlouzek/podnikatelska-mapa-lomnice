import csv, io, json, math, os, re, urllib.request, zipfile, xml.etree.ElementTree as ET
from pathlib import Path

CENTER_LAT, CENTER_LON, RADIUS_M = 50.5309, 15.3734, 5000
RES_URL = 'https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv'
ATOM_URL = 'https://atom.cuzk.gov.cz/RUIAN-CSV-ADR-OB/RUIAN-CSV-ADR-OB.xml'
OUT = Path('data/firms.json')

# The first pass intentionally keeps a generous municipality set around Lomnice.
# Exact inclusion is decided from address-point coordinates afterwards.
MUNICIPALITIES = {
    '577308','577351','577397','577389','577421','577432','577424','577441',
    '573051','577343','577351','577381','577416','577440'
}

def haversine(lat1, lon1, lat2, lon2):
    p=math.pi/180; a=math.sin((lat2-lat1)*p/2)**2+math.cos(lat1*p)*math.cos(lat2*p)*math.sin((lon2-lon1)*p/2)**2
    return 6371000*2*math.asin(math.sqrt(a))

def load_res():
    req=urllib.request.Request(RES_URL,headers={'Accept-Encoding':'gzip'})
    with urllib.request.urlopen(req) as r:
        raw=r.read()
    import gzip
    try: raw=gzip.decompress(raw)
    except OSError: pass
    wanted=[]
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8'))):
        if row.get('ICZUJ') in MUNICIPALITIES and row.get('DDATZAN','') in ('','0','0000-00-00'):
            wanted.append(row)
    return wanted

def ruian_feed_url():
    root=ET.fromstring(urllib.request.urlopen(ATOM_URL).read())
    ns={'a':'http://www.w3.org/2005/Atom'}
    # Prefer the latest ZIP whose title/link identifies a municipality dataset.
    for e in root.findall('a:entry',ns):
        link=e.find('a:link',ns)
        if link is not None and link.attrib.get('href','').lower().endswith('.zip'):
            return link.attrib['href']
    raise RuntimeError('RÚIAN ATOM feed did not contain a ZIP download')

def load_ruian(kods):
    url=ruian_feed_url()
    req=urllib.request.Request(url,headers={'User-Agent':'podnikatelska-mapa-lomnice/1.0'})
    data=urllib.request.urlopen(req).read()
    z=zipfile.ZipFile(io.BytesIO(data))
    result={}
    for name in z.namelist():
        if not name.lower().endswith('.csv'): continue
        with z.open(name) as f:
            text=io.TextIOWrapper(f,encoding='utf-8-sig',newline='')
            for row in csv.DictReader(text):
                k=row.get('KOD_ADM') or row.get('KODADM') or row.get('KOD_ADRESNIHO_MISTA')
                if k in kods:
                    # RÚIAN exports coordinates as ETRS89 lon/lat in current CSV product when available.
                    lat=row.get('SOURADNICE_Y') or row.get('LAT')
                    lon=row.get('SOURADNICE_X') or row.get('LON')
                    if lat and lon:
                        try: result[k]=(float(lat),float(lon),row)
                        except ValueError: pass
    return result

def clean(row, geo):
    lat,lon,adr=geo
    # Some RÚIAN variants expose S-JTSK only; those records are skipped until an ETRS89 export is available.
    d=haversine(CENTER_LAT,CENTER_LON,lat,lon)
    if d>RADIUS_M: return None
    nace=row.get('NACE2025') or row.get('NACE') or ''
    return {
      'name':row.get('FIRMA',''), 'ico':row.get('ICO',''), 'lat':lat, 'lon':lon,
      'distance_m':round(d), 'sector':nace, 'nace':nace,
      'size':row.get('KATPO',''), 'legal':row.get('FORMA',''),
      'address':row.get('TEXTADR','') or ' '.join(x for x in [row.get('ULICE_TEXT',''),row.get('CDOM',''),row.get('OBEC_TEXT','')] if x),
      'kodadm':row.get('KODADM',''), 'workers_local':None,
      'workers_note':'Kategorie pracovníků je údaj za ekonomický subjekt; místní zaměstnanost zatím není ověřena.',
      'source':'ČSÚ RES + ČÚZK RÚIAN'
    }

if __name__=='__main__':
    rows=load_res(); kods={r.get('KODADM') for r in rows if r.get('KODADM')}
    geo=load_ruian(kods)
    out=[]
    for r in rows:
        k=r.get('KODADM')
        if k in geo:
            item=clean(r,geo[k])
            if item: out.append(item)
    out.sort(key=lambda x:(x['distance_m'],x['name'].lower()))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Created {len(out)} businesses')
