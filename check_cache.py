import sqlite3
conn = sqlite3.connect('cache.sqlite')
cur = conn.cursor()
cur.execute("SELECT key, substr(value, 1, 300) FROM cache WHERE key LIKE '%lap_scatter%' OR key LIKE '%stints%' OR key LIKE '%team_pace%'")
rows = cur.fetchall()
for r in rows:
    print(r[0], '|', r[1])
print(f"\nTotal matching: {len(rows)}")

