import sqlite3
import psycopg2
import json
import os
from datetime import datetime

# Source: Local SQLite
SQLITE_DB = 'terraform_agent.db'
# Destination: Docker Postgres (using localhost mapping)
POSTGRES_URL = "postgresql://terra_user:terra_password@localhost:5432/terraform_agent"

def migrate():
    if not os.path.exists(SQLITE_DB):
        print(f"Source {SQLITE_DB} not found.")
        return

    print(f"Starting migration from {SQLITE_DB} to Postgres...")
    
    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(SQLITE_DB)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Connect to Postgres
        pg_conn = psycopg2.connect(POSTGRES_URL)
        pg_cursor = pg_conn.cursor()
        
        # Fetch all projects from SQLite
        sqlite_cursor.execute("SELECT * FROM projects")
        rows = sqlite_cursor.fetchall()
        
        # Get column names
        columns = [description[0] for description in sqlite_cursor.description]
        
        for row in rows:
            data = dict(zip(columns, row))
            print(f"  Migrating project: {data['slug']}...")
            
            # Upsert into Postgres
            pg_cursor.execute("""
                INSERT INTO projects (slug, prompt, status, budget, estimated_cost, security_issues, provider, mermaid_diagram, drift_status, flags, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    prompt = EXCLUDED.prompt,
                    status = EXCLUDED.status,
                    budget = EXCLUDED.budget,
                    estimated_cost = EXCLUDED.estimated_cost,
                    security_issues = EXCLUDED.security_issues,
                    provider = EXCLUDED.provider,
                    mermaid_diagram = EXCLUDED.mermaid_diagram,
                    drift_status = EXCLUDED.drift_status,
                    flags = EXCLUDED.flags,
                    updated_at = EXCLUDED.updated_at
            """, (
                data['slug'], data['prompt'], data['status'], data['budget'],
                data['estimated_cost'], data['security_issues'], data['provider'],
                data['mermaid_diagram'], data['drift_status'], data['flags'],
                data['created_at'], data['updated_at']
            ))
            
        pg_conn.commit()
        print(f"Migration successful! {len(rows)} projects moved.")
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate()
