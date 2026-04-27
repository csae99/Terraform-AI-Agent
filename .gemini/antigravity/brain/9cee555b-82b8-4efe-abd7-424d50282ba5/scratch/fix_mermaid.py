import sqlite3
conn = sqlite3.connect('terraform_agent.db')
cursor = conn.cursor()
new_mermaid = """graph TD
    AWS["AWS Cloud"]
    S3["S3 Bucket: shubham-nvidia-70b"]
    
    AWS -->|Create| S3
    S3 -.->|Versioning| AWS"""

cursor.execute('UPDATE projects SET mermaid_diagram = ? WHERE slug = ?', (new_mermaid, 'shubham-nvidia-70b'))
conn.commit()
print(f"Updated {cursor.rowcount} rows.")
conn.close()
