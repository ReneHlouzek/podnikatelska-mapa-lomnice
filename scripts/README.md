# Datová pipeline

Cílem je automaticky připravovat `data/firms.json` z otevřených dat RES ČSÚ.

RES poskytuje mimo jiné IČO, právní formu, kategorii podle počtu pracovníků, CZ-NACE/NACE2025 a adresní údaje včetně KODADM. Kompletní data jsou aktualizována dvakrát měsíčně.

Další krok pipeline:
1. stáhnout aktuální `res_data.csv`,
2. vybrat subjekty s aktivitou a adresou v okolí Lomnice,
3. napojit KODADM na adresní body RÚIAN,
4. spočítat vzdálenost od středu Lomnice,
5. ponechat pouze 0–5 km,
6. převést RES kódy na čitelné názvy,
7. vytvořit kompaktní `data/firms.json`.

Pozor: KATPO je kategorie pracovníků celého ekonomického subjektu. Samostatný údaj `workers_local` bude používán pouze pro ověřený nebo kvalifikovaný odhad pracovních míst fyzicky v Lomnici.
