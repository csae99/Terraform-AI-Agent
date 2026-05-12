import sys
sys.path.insert(0,'.')
from tools.project.tracker import ProjectTracker

mermaid = """graph LR
    AWS["AWS Cloud"] -->|Create| S3["S3 Bucket"]"""

ProjectTracker.save('simple-s3-bucket', mermaid_diagram=mermaid)
print('Fixed simple-s3-bucket mermaid')

# Fix others if they have similar issues
projects = ProjectTracker.load_all()
for p in projects:
    diag = p.get('mermaid_diagram', '')
    if diag and 'graph' in diag and 'participant' in diag:
        # replace participant with simple nodes
        lines = []
        for line in diag.split('\n'):
            if 'participant' in line: continue
            lines.append(line)
        ProjectTracker.save(p['slug'], mermaid_diagram='\n'.join(lines))
        print(f'Fixed {p["slug"]} mermaid')
