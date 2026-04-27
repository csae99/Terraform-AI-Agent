import sqlite3
conn = sqlite3.connect('terraform_agent.db')
cursor = conn.cursor()
cursor.execute('SELECT mermaid_diagram FROM projects WHERE slug = ?', ('shubham-nvidia-70b',))
row = cursor.fetchone()
if row:
    print("--- MERMAID START ---")
    print(row[0])
    print("--- MERMAID END ---")
else:
    print("Project not found.")
conn.close()
