import csv, io, json, math, urllib.request, zipfile, xml.etree.ElementTree as ET
from pathlib import Path

CENTER_LAT, CENTER_LON, RADIUS_M = 50.5309, 15.3734, 5000
RES_URL='https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv'
ATOM_URL='https://atom.cuzk.gov.cz/RUIAN-CSV-ADR-OB/RUIAN-CSV-ADR-OB.xml'
OUT=Path('data/firms.json')
MUNICIPALITIES={'577308','577351','577397','577389','577421','577432','577424','577441','573051','577343','577381','577416','577440'}

def haversine(a,b):
    p=math.pi/180; dlat=(b[0]-a[0])*p; dlon=(b[1]-a[1])*p
    h=math.sin(dlat/2)**2+math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(h))

def load_res():
    req=urllib.request.Request(RES_URL,headers={'Accept-Encoding':'gzip'})
    with urllib.request.urlopen(req) as r: raw=r.read()
    import gzip
    try: raw=gzip.decompress(raw)
    except OSError: pass
    return [r for r in csv.DictReader(io.StringIO(raw.decode('utf-8'))) if r.get('ICZUJ') in MUNICIPALITIES and not r.get('DDATZAN')]

def ruian_links():
    root=ET.fromstring(urllib.request.urlopen(ATOM_URL).read()); ns={'a':'http://www.w3.org/2005/Atom'}; links={}
    for e in root.findall('a:entry',ns):
        blob=' '.join((x.text or '') for x in e); link=e.find('a:link',ns); href=link.attrib.get('href','') if link is not None else ''
        if href.lower().endswith('.zip'):
            for code in MUNICIPALITIES:
                if code in blob or code in href: links[code]=href
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
                    for row in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline='')):
                        k=row.get('KOD_ADM') or row.get('KODADM') or row.get('KOD_ADRESNIHO_MISTA')
                        if k not in kods: continue
                        y,x=row.get('SOURADNICE_Y'),row.get('SOURADNICE_X')
                        if not y or not x: continue
                        try: lon,lat=tr.transform(float(x),float(y)); result[k]=(lat,lon,row)
                        except ValueError: pass
    return result

def clean(row,geo):
    lat,lon,_=geo; d=haversine((CENTER_LAT,CENTER_LON),(lat,lon))
    if d>RADIUS_M: return None
    nace=row.get('NACE2025') or row.get('NACE') or ''
    address=row.get('TEXTADR','') or ' '.join(x for x in [row.get('ULICE_TEXT',''),row.get('CDOM',''),row.get('OBEC_TEXT','')] if x)
    return {'name':row.get('FIRMA',''),'ico':row.get('ICO',''),'lat':lat,'lon':lon,'distance_m':round(d),'sector':nace,'nace':nace,'size':row.get('KATPO',''),'legal':row.get('FORMA',''),'address':address,'kodadm':row.get('KODADM',''),'workers_local':None,'workers_note':'Kategorie pracovníků je údaj za ekonomický subjekt; místní zaměstnanost zatím není ověřena.','source':'ČSÚ RES + ČÚZK RÚIAN'}

if __name__=='__main__':
    rows=load_res(); geo=load_ruian({r.get('KODADM') for r in rows if r.get('KODADM')}); out=[]
    for r in rows:
        if r.get('KODADM') in geo:
            item=clean(r,geo)
            if item: out.append(item)
    out.sort(key=lambda x:(x['distance_m'],x['name'].lower())); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(f'Created {len(out)} businesses')
