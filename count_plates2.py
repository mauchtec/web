import sqlite3, json
conn=sqlite3.connect('db.sqlite3')
c=conn.cursor()
plates=set()
rows=c.execute("SELECT raw_scan_data, request_data FROM GateCore_accesslog").fetchall()
for raw, req in rows:
    for payload in (raw, req):
        if not payload:
            continue
        if isinstance(payload, str):
            try:
                data=json.loads(payload)
            except json.JSONDecodeError:
                continue
        else:
            data=payload
        if not isinstance(data, dict):
            continue
        for key in ('plate_number','vehicle_register_number'):
            val=data.get(key)
            if val:
                plates.add(val)
        components=data.get('components')
        if isinstance(components, list):
            for comp in components:
                if isinstance(comp, dict):
                    for field in comp.get('fields') or []:
                        if isinstance(field, dict):
                            label=field.get('label','').replace(' ','').lower()
                            if label in ('plate','platenumber','registrationnumber','vehicleregisternumber'):
                                value=field.get('value')
                                if value:
                                    plates.add(value)
plates_list=sorted(plates)
print(len(plates_list))
print(plates_list)
conn.close()
