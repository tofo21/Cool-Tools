import re, requests
from bs4 import BeautifulSoup
url='https://www.fantasypros.com/nfl/adp/ppr-overall.php?year=2020'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36'},timeout=60)
text=r.text
print('len',len(text))
for needle in ['Christian McCaffrey','player_name','player_id','adpData','rankings','ESPN','Sleeper','data:','players']:
    print('\nNEEDLE',needle)
    for m in list(re.finditer(re.escape(needle), text, re.I))[:3]:
        a=max(0,m.start()-500); b=min(len(text),m.start()+1500)
        print(text[a:b].replace('\n',' ')[:2000])
        print('---')
print('\nSCRIPTS')
soup=BeautifulSoup(text,'lxml')
for i,s in enumerate(soup.find_all('script')):
    body=s.string or s.get_text()
    if body and any(k.lower() in body.lower() for k in ['mccaffrey','adp','player']):
        print('SCRIPT',i,'len',len(body), 'src',s.get('src'))
        print(body[:4000].replace('\n',' '))
        print('---')
