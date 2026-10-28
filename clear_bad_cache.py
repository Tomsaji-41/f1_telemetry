import sqlite3, json

conn = sqlite3.connect('cache.sqlite')
cur = conn.cursor()

# Delete all error/empty/source_error chart cache entries
cur.execute("SELECT key, value FROM cache WHERE key LIKE 'chart:%'")
rows = cur.fetchall()
deleted = []
for key, val in rows:
    try:
        d = json.loads(val)
        if d.get("status") in ("empty", "source_error", "not_ingested", "not_published_yet"):
            cur.execute("DELETE FROM cache WHERE key=?", (key,))
            deleted.append((key, d.get("status"), d.get("coverage_note","")[:80]))
    except Exception:
        pass

conn.commit()
conn.close()
print(f"Deleted {len(deleted)} poisoned entries:")
for k, s, n in deleted:
    print(f"  [{s}] {k} | {n}")

