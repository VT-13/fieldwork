import csv
import json
import sys
with open(sys.argv[1],newline='',encoding='utf-8-sig') as handle:
    rows=list(csv.DictReader(handle))
if len(rows)>50:
    raise SystemExit('Split export into batches of at most 50 rows')
result=[]
for r in rows:
    result.append({'name':r['name'],'website':r['website'],'industry':r.get('industry') or 'Unknown',
        'distance_miles':float(r['distance_miles']) if r.get('distance_miles') else None,'source':r.get('source') or 'authorized CSV import'})
print(json.dumps(result,indent=2))
