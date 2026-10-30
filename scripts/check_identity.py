import urllib.request
import json

res = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/identity").read().decode())
print("Status:", res.get("status"), "Year:", res.get("year"))
drivers = res.get("drivers", {})
print("Total drivers:", len(drivers))
for i, (k, v) in enumerate(list(drivers.items())[:10]):
    print(f"{i+1}. key='{k}' | code='{v.get('code')}' | name='{v.get('name')}' | team='{v.get('team')}' | teamColor='{v.get('teamColor')}'")
