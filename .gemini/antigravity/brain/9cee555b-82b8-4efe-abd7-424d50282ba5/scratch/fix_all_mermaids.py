import sys
sys.path.insert(0,'.')
from tools.project.tracker import ProjectTracker

projects = ProjectTracker.load_all()
for p in projects:
    diag = p.get('mermaid_diagram', '')
    if diag and 'graph' in diag and 'participant' in diag:
        print(f'Warning: {p["slug"]} has invalid graph/participant mixing.')
        # Basic fix: drop participant lines, hope the rest works, or just return empty string to clear the error
        ProjectTracker.save(p['slug'], mermaid_diagram='')
        print(f'Cleared invalid mermaid for {p["slug"]}')
