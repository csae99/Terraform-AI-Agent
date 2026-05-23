import os
import sys

# Add parent directory to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.project.tracker import ProjectTracker

def test_slug_generation():
    print("🚀 Running custom verification test for sequential unique slug generation...")
    base_slug = "test-unique-slug"
    
    # 1. Clean up any existing projects/folders from previous runs
    ProjectTracker.delete(base_slug)
    ProjectTracker.delete(f"{base_slug}-1")
    ProjectTracker.delete(f"{base_slug}-2")
    
    # 2. Save first project
    print("  Saving first project...")
    ProjectTracker.save(base_slug, prompt="test 1")
    
    # 3. Simulate new run with new_project = True
    slug = base_slug
    new_project = True
    if new_project:
        base = slug
        counter = 1
        while ProjectTracker.load(slug) is not None or os.path.exists(os.path.join("output", slug)):
            slug = f"{base}-{counter}"
            counter += 1
            
    print(f"  Generated slug for run 2: {slug} (Expected: {base_slug}-1)")
    assert slug == f"{base_slug}-1", f"Expected {base_slug}-1, got {slug}"
    
    # 4. Save second project
    ProjectTracker.save(slug, prompt="test 2")
    
    # 5. Simulate new run 3 with new_project = True
    slug = base_slug
    if new_project:
        base = slug
        counter = 1
        while ProjectTracker.load(slug) is not None or os.path.exists(os.path.join("output", slug)):
            slug = f"{base}-{counter}"
            counter += 1
            
    print(f"  Generated slug for run 3: {slug} (Expected: {base_slug}-2)")
    assert slug == f"{base_slug}-2", f"Expected {base_slug}-2, got {slug}"
    
    # 6. Clean up
    ProjectTracker.delete(base_slug)
    ProjectTracker.delete(f"{base_slug}-1")
    ProjectTracker.delete(f"{base_slug}-2")
    print("✅ All tests passed successfully!")

if __name__ == "__main__":
    test_slug_generation()
