import json
import re
from bs4 import BeautifulSoup

def extract_json(html):
    soup = BeautifulSoup(html, 'html.parser')
    data = {}
    
    # 1. data-zone-data on html tag
    html_tag = soup.find('html')
    if html_tag and html_tag.get('data-zone-data'):
        try:
            data['zone_data'] = json.loads(html_tag['data-zone-data'])
        except:
            print("Failed to parse data-zone-data")
            pass

    # 2. LD+JSON
    scripts = soup.find_all('script', type='application/ld+json')
    data['ld_json'] = []
    for script in scripts:
        if script.string:
            try:
                data['ld_json'].append(json.loads(script.string))
            except:
                pass

    # 3. Canonical
    canonical = soup.find('link', rel='canonical')
    if canonical:
        data['canonical'] = canonical.get('href')
    
    # 4. OG:URL
    og_url = soup.find('meta', property='og:url')
    if og_url:
        data['og_url'] = og_url.get('content')

    return data

with open('product_dump_103581125050.html') as f:
    html = f.read()
    data = extract_json(html)
    print(json.dumps(data, indent=2))
