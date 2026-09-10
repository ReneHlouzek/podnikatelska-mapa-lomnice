import csv, io, json, math, re, unicodedata, urllib.request, zipfile, time
from pathlib import Path

CENTER_LAT, CENTER_LON, RADIUS_M = 50.5309, 15.3734, 5000
RES_URL='https://opendata.csu.gov.cz/soubory/od/od_org03/res_data.csv'
RES_LOCAL=Path('res_data.csv')
RUIAN_INDEX_URL='https://services.cuzk.cz/atom-index/RUIAN-CSV-ADR-OB/5513/'
OUT=Path('data/firms.json')
MUNICIPALITIES={'577308','577341','577014','577294','577545','577553','577235','577243','577197','576999','577120','577154','577421','577472','577481','577499','577529','577561','577316','577332','577359','577367','577391','577413','577430','577448'}

SECTORS={
 '01':'Zemědělství, lesnictví a rybářství','02':'Zemědělství, lesnictví a rybářství','03':'Zemědělství, lesnictví a rybářství',
 '05':'Těžba a dobývání','06':'Těžba a dobývání','07':'Těžba a dobývání','08':'Těžba a dobývání','09':'Těžba a dobývání',
 **{f'{i:02d}':'Zpracovatelský průmysl' for i in range(10,34)},
 '35':'Energetika a zásobování energiemi',
 '36':'Voda, odpady a sanace','37':'Voda, odpady a sanace','38':'Voda, odpady a sanace','39':'Voda, odpady a sanace',
 '41':'Stavebnictví','42':'Stavebnictví','43':'Stavebnictví',
 '45':'Obchod a opravy motorových vozidel','46':'Velkoobchod a maloobchod','47':'Velkoobchod a maloobchod',
 '49':'Doprava a skladování','50':'Doprava a skladování','51':'Doprava a skladování','52':'Doprava a skladování','53':'Doprava a skladování',
 '55':'Ubytování a stravování','56':'Ubytování a stravování',
 '58':'Informace a komunikace','59':'Informace a komunikace','60':'Informace a komunikace','61':'Informace a komunikace','62':'Informace a komunikace','63':'Informace a komunikace',
 '64':'Finance a pojišťovnictví','65':'Finance a pojišťovnictví','66':'Finance a pojišťovnictví',
 '68':'Nemovitosti',
 '69':'Profesní, vědecké a technické činnosti','70':'Profesní, vědecké a technické činnosti','71':'Profesní, vědecké a technické činnosti','72':'Profesní, vědecké a technické činnosti','73':'Profesní, vědecké a technické činnosti','74':'Profesní, vědecké a technické činnosti','75':'Profesní, vědecké a technické činnosti',
 '77':'Administrativní a podpůrné činnosti','78':'Administrativní a podpůrné činnosti','79':'Administrativní a podpůrné činnosti','80':'Administrativní a podpůrné činnosti','81':'Administrativní a podpůrné činnosti','82':'Administrativní a podpůrné činnosti',
 '84':'Veřejná správa a obrana','85':'Vzdělávání','86':'Zdravotní a sociální péče','87':'Zdravotní a sociální péče','88':'Zdravotní a sociální péče',
 '90':'Kultura, zábava a rekreace','91':'Kultura, zábava a rekreace','92':'Kultura, zábava a rekreace','93':'Kultura, zábava a rekreace',
 '94':'Ostatní služby','95':'Ostatní služby','96':'Ostatní služby','97':'Domácnosti jako zaměstnavatelé','98':'Domácnosti jako výrobci','99':'Exteritoriální organizace'
}
SIZE_LABELS={'000':'Neuvedeno','110':'Bez zaměstnanců','120':'1–5 zaměstnanců','130':'6–9 zaměstnanců','210':'10–19 zaměstnanců','220':'20–24 zaměstnanců','230':'25–49 zaměstnanců','240':'50–99 zaměstnanců','310':'100–199 zaměstnanců','320':'200–249 zaměstnanců','330':'250–499 zaměstnanců','340':'500–999 zaměstnanců','410':'1 000–1 499 zaměstnanců','420':'1 500–1 999 zaměstnanců','430':'2 000–2 499 zaměstnanců','440':'2 500–2 999 zaměstnanců','450':'3 000–3 999 zaměstnanců','460':'4 000–4 999 zaměstnanců','470':'5 000–9 999 zaměstnanců','510':'10 000+ zaměstnanců'}
LEGAL_LABELS={'000':'Neuvedeno','101':'Fyzická osoba podnikající dle živnostenského zákona','102':'Živnostník zapsaný v obchodním rejstříku','103':'Samostatně hospodařící rolník','104':'Samostatně hospodařící rolník zapsaný v obchodním rejstříku','105':'Fyzická osoba podnikající dle jiných zákonů','106':'Fyzická osoba podnikající dle jiných zákonů, zapsaná v OR','107':'Zemědělský podnikatel – fyzická osoba','108':'Zemědělský podnikatel – fyzická osoba, zapsaná v OR','111':'Veřejná obchodní společnost','112':'Společnost s ručením omezeným','113':'Komanditní společnost','115':'Společný podnik','116':'Zájmové sdružení','117':'Nadace','118':'Nadační fond','121':'Akciová společnost','141':'Obecně prospěšná společnost','145':'Společenství vlastníků jednotek','151':'Komoditní burza','161':'Ústav','205':'Družstvo','301':'Státní podnik','313':'Česká národní banka','325':'Organizační složka státu','331':'Příspěvková organizace','421':'Zahraniční osoba','601':'Vysoká škola','611':'Střední škola','621':'Základní škola','631':'Předškolní zařízení','701':'Spolek / sdružení'}

def haversine(a,b):
    p=math.pi/180; dlat=(b[0]-a[0])*p; dlon=(b[1]-a[1])*p
    h=math.sin(dlat/2)**2+math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(h))

def normalize_header(value):
    value=unicodedata.normalize('NFKD', value or '')
    value=''.join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r'[^A-Z0-9]+','_',value.upper()).strip('_')

def load_res():
    if RES_LOCAL.exists() and RES_LOCAL.stat().st_size > 10_000_000: raw=RES_LOCAL.read_bytes()
    else:
        req=urllib.request.Request(RES_URL,headers={'Accept-Encoding':'gzip','User-Agent':'podnikatelska-mapa-lomnice/1.0'}); last=None
        for attempt in range(1,4):
            try:
                with urllib.request.urlopen(req,timeout=300) as r: raw=r.read()
                break
            except Exception as e: last=e; print(f'RES download attempt {attempt}/3 failed: {e}'); time.sleep(5*attempt)
        else: raise last
    import gzip
    try: raw=gzip.decompress(raw)
    except OSError: pass
    rows=[r for r in csv.DictReader(io.StringIO(raw.decode('utf-8'))) if r.get('ICZUJ') in MUNICIPALITIES and not r.get('DDATZAN')]
    print(f'RES: {len(rows)} active entities in selected municipalities'); return rows

def ruian_links():
    req=urllib.request.Request(RUIAN_INDEX_URL,headers={'User-Agent':'podnikatelska-mapa-lomnice/1.0'}); html=urllib.request.urlopen(req,timeout=120).read().decode('utf-8','replace'); links={}
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
                        row={normalize_header(k):(v or '') for k,v in original.items()}; k=(row.get('KOD_ADM') or row.get('KODADM') or row.get('KOD_ADRESNIHO_MISTA') or '').strip()
                        if k not in kods: continue
                        y=(row.get('SOURADNICE_Y') or '').strip(); x=(row.get('SOURADNICE_X') or '').strip()
                        if not y or not x: continue
                        try:
                            lon,lat=tr.transform(-float(y.replace(',','.')),-float(x.replace(',','.'))); result[k]=(lat,lon,row)
                        except (ValueError,TypeError): pass
    print(f'RUIAN: matched {len(result)} RES addresses'); return result

def clean(row,geo):
    lat,lon,ruian=geo; d=haversine((CENTER_LAT,CENTER_LON),(lat,lon))
    if d>RADIUS_M: return None
    nace=row.get('NACE2025') or row.get('NACE') or ''; nace_key=re.sub(r'\D','',nace)[:2]; sector_code=nace_key or '00'; sector=SECTORS.get(sector_code,'Ostatní / nezařazené')
    size_code=row.get('KATPO','') or '000'; legal_code=row.get('FORMA','') or '000'
    address=row.get('TEXTADR','') or ' '.join(x for x in [ruian.get('NAZEV_ULICE',''),ruian.get('CISLO_DOMOVNI',''),ruian.get('NAZEV_OBCE','')] if x)
    return {'name':row.get('FIRMA',''),'ico':row.get('ICO',''),'lat':lat,'lon':lon,'distance_m':round(d),'sector':sector,'sector_code':sector_code,'nace':nace,'size':SIZE_LABELS.get(size_code,f'Kód {size_code}'),'size_code':size_code,'legal':LEGAL_LABELS.get(legal_code,f'Kód {legal_code}'),'legal_code':legal_code,'address':address,'kodadm':row.get('KODADM',''),'workers_local':None,'workers_note':'Kategorie pracovníků je údaj za ekonomický subjekt; místní zaměstnanost zatím není ověřena.','source':'ČSÚ RES + ČÚZK RÚIAN'}

if __name__=='__main__':
    rows=load_res(); kods={str(r.get('KODADM')).strip() for r in rows if r.get('KODADM')}; print(f'RES: {len(kods)} unique KODADM values'); geo=load_ruian(kods); out=[]
    for r in rows:
        kodadm=str(r.get('KODADM')).strip()
        if kodadm in geo:
            item=clean(r,geo[kodadm])
            if item: out.append(item)
    out.sort(key=lambda x:(x['distance_m'],x['name'].lower())); OUT.parent.mkdir(exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(f'Created {len(out)} businesses')
    if not out: raise RuntimeError('No businesses generated; refusing to publish empty dataset')
