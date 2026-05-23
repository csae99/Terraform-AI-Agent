import json
import codecs

try:
    with codecs.open("scratch/infracost_test1.json", "r", "utf-8") as f:
        data = json.load(f)
    print("Root keys:", list(data.keys()))
    print("Root totalMonthlyCost:", data.get("totalMonthlyCost"))
    if data.get("projects"):
        print("Project totalMonthlyCost:", data["projects"][0].get("breakdown", {}).get("totalMonthlyCost"))
except Exception as e:
    print("Error:", e)
