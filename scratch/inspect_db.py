import sqlite3

def main():
    conn = sqlite3.connect("terraform_agent.db")
    cursor = conn.cursor()
    
    print("=== Users ===")
    try:
        cursor.execute("SELECT id, username, email FROM users")
        for row in cursor.fetchall():
            print(f"ID: {row[0]}, Username: {row[1]}, Email: {row[2]}")
    except Exception as e:
        print("Error reading users:", e)
        
    print("\n=== Projects ===")
    try:
        cursor.execute("SELECT slug, status, owner_id FROM projects")
        for row in cursor.fetchall():
            print(f"Slug: {row[0]}, Status: {row[1]}, Owner ID: {row[2]}")
    except Exception as e:
        print("Error reading projects:", e)
        
    conn.close()

if __name__ == "__main__":
    main()
