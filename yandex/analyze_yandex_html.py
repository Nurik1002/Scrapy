import json
import re

def analyze():
    print("Reading file...")
    with open('yandex/yandex_test.html', 'r', encoding='utf-8') as f:
        content = f.read()

    print(f"File size: {len(content)} bytes")

    # 1. Find ld+json
    print("\n--- Searching for application/ld+json ---")
    # precise regex for script tag
    matches = re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', content, re.DOTALL)
    found_any = False
    for i, match in enumerate(matches):
        found_any = True
        json_str = match.group(1).strip()
        print(f"\n[LD+JSON #{i}] Length: {len(json_str)}")
        try:
            data = json.loads(json_str)
            print(json.dumps(data, indent=2)[:500])
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            print(f"Snippet: {json_str[:200]}")

    if not found_any:
        print("No ld+json script tags found.")
        
    # 2. Find Xiaomi context
    print("\n--- Searching for Xiaomi context ---")
    indices = [m.start() for m in re.finditer(r'Xiaomi', content)]
    print(f"Found 'Xiaomi' {len(indices)} times.")
    
    for idx in indices[:5]: # First 5
        start = max(0, idx - 200)
        end = min(len(content), idx + 200)
        snippet = content[start:end].replace('\n', ' ')
        print(f"\nMatch at {idx}:")
        print(f"...{snippet}...")

    # 3. Check for specific apiary or state variables
    print("\n--- Searching for State/Hydration ---")
    state_markers = ["__INITIAL_STATE__", "window.apiary", "window.__STATE__", "apiary-"]
    for marker in state_markers:
        idx = content.find(marker)
        if idx != -1:
            print(f"Found '{marker}' at {idx}")
            print(f"Context: {content[idx:idx+200]}")
        else:
            print(f"'{marker}' not found.")

if __name__ == "__main__":
    analyze()
