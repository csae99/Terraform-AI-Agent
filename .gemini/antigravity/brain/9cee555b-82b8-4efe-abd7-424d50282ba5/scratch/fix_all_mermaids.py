import sqlite3
conn = sqlite3.connect('terraform_agent.db')
cursor = conn.cursor()

def fix(slug, name):
    new_mermaid = f"""graph TD
    AWS["AWS Cloud"]
    S3["S3 Bucket: {name}"]
    
    AWS -->|Create| S3
    S3 -.->|Versioning| AWS"""
    cursor.execute('UPDATE projects SET mermaid_diagram = ? WHERE slug = ?', (new_mermaid, slug))

fix('shubham-nvidia-70b', 'shubham-nvidia-70b')
fix('shubham-nvidia-s3-only', 'shubham-nvidia-s3-only')

conn.commit()
print(f"Updated {cursor.rowcount} rows (last change).")
conn.close()
