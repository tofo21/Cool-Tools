import io
import pandas as pd
import requests

urls = [
    'https://www.fantasypros.com/nfl/adp/ppr-overall.php?year=2020',
    'https://www.fantasypros.com/nfl/adp/ppr-overall.php?year=2020&export=xls',
    'https://www.fantasypros.com/nfl/adp/ppr-overall.php?export=xls&year=2020',
]
h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142 Safari/537.36'}
for url in urls:
    print('\nURL', url)
    r = requests.get(url, headers=h, timeout=60)
    print('status', r.status_code, 'type', r.headers.get('content-type'), 'len', len(r.content), 'disp', r.headers.get('content-disposition'))
    print('first', repr(r.content[:120]))
    try:
        tables = pd.read_html(io.StringIO(r.text))
        print('html tables', len(tables))
        for i,t in enumerate(tables[:5]):
            print(i, list(map(str,t.columns)), t.shape)
    except Exception as e:
        print('read_html_error', type(e).__name__, str(e)[:300])
    try:
        xls = pd.read_excel(io.BytesIO(r.content))
        print('excel', xls.shape, list(xls.columns))
    except Exception as e:
        print('read_excel_error', type(e).__name__, str(e)[:300])
