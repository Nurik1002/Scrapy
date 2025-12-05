import os
import psycopg2
from tabulate import tabulate

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://uzum_user:uzum_password@localhost:5433/uzum_db")

def run_query(query):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(query)
    headers = [desc[0] for desc in cur.description]
    results = cur.fetchall()
    conn.close()
    return headers, results

def main():
    print("Generating Analytics Report...\n")
    
    with open("scripts/analytics.sql", "r") as f:
        sql_content = f.read()
        
    queries = sql_content.split(';')
    
    for q in queries:
        q = q.strip()
        if not q:
            continue
            
        print(f"Executing Query: {q.splitlines()[0]}") # Print comment
        try:
            headers, results = run_query(q)
            print(tabulate(results, headers=headers, tablefmt="grid"))
            print("\n")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
