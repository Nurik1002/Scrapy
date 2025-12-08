import re

def extract():
    try:
        with open('yandex/yandex_search_clothes.html', 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"Read {len(content)} bytes")
        
        # Try multiple patterns
        patterns = [
            r'href="(/product--[^"]+)"',
            r'href="(/offer/[^"]+)"',
            r'href="(https://market.yandex.uz/product--[^"]+)"',
            r'"url":"(/product--[^"]+)"'
        ]
        
        found = set()
        for p in patterns:
            matches = re.findall(p, content)
            for m in matches:
                found.add(m)
                
        print(f"Found {len(found)} unique links")
        for link in list(found)[:10]:
            print(link)
            
    except Exception as e:
        print(e)

if __name__ == "__main__":
    extract()
