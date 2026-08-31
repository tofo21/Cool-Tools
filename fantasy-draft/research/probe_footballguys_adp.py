from __future__ import annotations

import json
import re
import requests
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'output'
OUT.mkdir(parents=True, exist_ok=True)
URLS = [
 'https://www.footballguys.com/article/2021-fpc-adp07',
 'https://www.footballguys.com/article/2022-fpc-adp04',
 'https://www.footballguys.com/article/2023-ffpc-adp12',
 'https://www.footballguys.com/article/2024-nffc-average-draft-position-adp-02',
 'https://www.footballguys.com/article/2025-nffc-adp-movement-high-stakes-01',
]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36'
for i,u in enumerate(URLS):
 r=requests.get(u,headers={'User-Agent':UA},timeout=30); t=r.text
 info={'url':u,'status':r.status_code,'len':len(t),'tables':len(re.findall(r'<table',t,re.I)),'mccaffrey':t.lower().find('mccaffrey'),'rank_adp':t.lower().find('rank -- rank by adp'),'next_data':t.find('__NEXT_DATA__'),'apollo':t.lower().find('apollo')}
 print(json.dumps(info))
 for needle in ['mccaffrey','rank -- rank by adp','articleBody','content','markdown']:
  p=t.lower().find(needle.lower())
  if p>=0:
   print('\nNEEDLE',needle,'\n',t[max(0,p-600):p+2000])
 (OUT/f'fbg_probe_{i}.html').write_text(t,encoding='utf-8')
