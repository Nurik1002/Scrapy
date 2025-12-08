import json

def parse_categories():
    with open('categories.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # The structure is usually simple, but let's check
    # data might be a list or a dict {'state': 0, 'payloadVersion': 2, 'data': ...} 
    # Actually checking the previous curl output suggests the structure.
    
    # Standard WB menu structure: List of objects.
    
    hierarchy = []
    
    # If it's the raw list directly
    if isinstance(data, list):
        items = data
    else:
        items = data.get('data', []) # Just in case

    print(f"Total top-level items: {len(items)}")
    
    for item in items:
        cat = {
            "id": item.get("id"),
            "name": item.get("name"),
            "url": item.get("url"),
            "shard": item.get("shard"),
            "query": item.get("query"),
            "childs": len(item.get("childs", []))
        }
        hierarchy.append(cat)
        print(f"{cat['id']}: {cat['name']} ({cat['childs']} subcategories)")

    with open('category_hierarchy_summary.json', 'w', encoding='utf-8') as f:
        json.dump(hierarchy, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    parse_categories()
