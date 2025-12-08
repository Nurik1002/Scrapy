import os
import glob
import re

# Calculate path relative to this script file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../data/raw"))

def main():
    print(f"Cleaning up {DATA_DIR}...")
    
    # Get all files
    files = [f for f in os.listdir(DATA_DIR) if os.path.isfile(os.path.join(DATA_DIR, f))]
    
    # Define patterns to group by
    # We use regex to identify the "type" of file
    patterns = {
        "auction_products": re.compile(r"auction_products_.*\.json"),
        "shop_products": re.compile(r"shop_products_.*\.json"),
        "auctions_page": re.compile(r"auctions_page_.*\.json"),
        "shop_deals_page": re.compile(r"shop_deals_page_.*\.json"),
        
        # Intercepted files
        "intercepted_GetCompletedDeals": re.compile(r"intercepted_.*_GetCompletedDeals\.json"),
        "intercepted_GetNotCompletedDeals": re.compile(r"intercepted_.*_GetNotCompletedDeals\.json"),
        "intercepted_GetNews": re.compile(r"intercepted_.*_GetNews\.json"),
        "intercepted_GetPopup": re.compile(r"intercepted_.*_GetPopup\.json"),
        "intercepted_GetRegions": re.compile(r"intercepted_.*_GetRegions\.json"),
        "intercepted_GetCurrentIp": re.compile(r"intercepted_.*_GetCurrentIp\.json"),
        "intercepted_shops": re.compile(r"intercepted_shops_.*\.json"),
        
        # Categories - we want to identify them but NOT delete them
        "categories": re.compile(r".*Categories\.json|categories\.json"),
    }
    
    # Group files
    groups = {key: [] for key in patterns}
    others = []
    
    for f in files:
        matched = False
        for key, regex in patterns.items():
            if regex.match(f):
                groups[key].append(f)
                matched = True
                break
        if not matched:
            others.append(f)
            
    # Process groups
    for key, file_list in groups.items():
        if key == "categories":
            print(f"Skipping cleanup for '{key}' ({len(file_list)} files) - Keeping ALL.")
            continue
            
        if not file_list:
            continue
            
        # Sort files to keep the latest ones (assuming timestamp or sequence in name)
        # We'll just sort alphabetically which usually works for timestamps/IDs
        file_list.sort()
        
        # Keep last 2
        to_keep = file_list[-2:]
        to_delete = file_list[:-2]
        
        print(f"Group '{key}': Found {len(file_list)} files. Deleting {len(to_delete)}...")
        
        for f in to_delete:
            path = os.path.join(DATA_DIR, f)
            try:
                os.remove(path)
                # print(f"Deleted {f}")
            except Exception as e:
                print(f"Error deleting {f}: {e}")
                
    print("Cleanup complete.")

if __name__ == "__main__":
    main()
