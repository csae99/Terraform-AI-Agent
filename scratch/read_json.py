import json
import codecs

try:
    with codecs.open("scratch/infracost_test1.json", "r", "utf-8-sig") as f:
        data = json.load(f)
    print("Project count:", len(data.get("projects", [])))
    if data.get("projects"):
        print("Total cost:", data["projects"][0].get("breakdown", {}).get("totalMonthlyCost"))
        print("Resources length:", len(data["projects"][0].get("breakdown", {}).get("resources", [])))
except Exception as e:
    print("Error:", e)
    with open("scratch/infracost_test.json", "rb") as f:
        print(f.read()[:100])
