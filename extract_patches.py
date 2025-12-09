import re
import json

def extract_patches():
    with open('debug_search.html', 'r', encoding='utf-8') as f:
        html = f.read()

    patches = []
    # Find all <noframes data-apiary="patch">...</noframes>
    # Using regex, might need DOTALL if it spans lines, though usually it's one line in Yandex
    matches = re.findall(r'<noframes data-apiary="patch">(.+?)</noframes>', html, re.DOTALL)
    
    print(f"Found {len(matches)} patches")
    
    for i, content in enumerate(matches):
        try:
            data = json.loads(content)
            patches.append(data)
        except json.JSONDecodeError as e:
            print(f"Error parsing patch {i}: {e}")

    with open('debug_patches.json', 'w', encoding='utf-8') as f:
        json.dump(patches, f, indent=2, ensure_ascii=False)
    
    print("Saved patches to debug_patches.json")

if __name__ == "__main__":
    extract_patches()
