import psycopg2

POSTGRES_URL = "postgresql://terra_user:terra_password@localhost:5432/terraform_agent"

def cleanup():
    print(f"Cleaning up Postgres database at {POSTGRES_URL}...")
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        
        # Truncate the projects table
        cursor.execute("TRUNCATE TABLE projects RESTART IDENTITY CASCADE")
        conn.commit()
        
        print("Database cleaned successfully! (Projects table truncated)")
    except Exception as e:
        print(f"Cleanup failed: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    cleanup()
