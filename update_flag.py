import sqlite3

conn = sqlite3.connect('jobs.db')
c = conn.cursor()

c.execute("UPDATE flagged_jobs SET status='reviewed' WHERE id=1")
conn.commit()

print("Updated successfully")

conn.close()