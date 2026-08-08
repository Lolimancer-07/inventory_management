# Stockroom — Inventory System

A shared inventory ledger for **Material / Buying price / Wholesale price / Retail price**,
with two roles:

- **Admin** — can view, add, edit, and delete materials
- **User (Viewer)** — can only view the ledger, no editing

It works over your office WiFi: one PC is the **host** (runs the server and holds the data),
and every other PC connects to it through a browser window that looks like a plain desktop app.

---

## 1. One-time setup (do this on the HOST PC only)

The host PC should be one that stays on during work hours (e.g. the front desk / admin PC).

1. Install Python from https://python.org (during install, tick **"Add Python to PATH"**).
2. Copy this whole `inventory_app` folder onto the host PC.
3. Double-click **`Start Server.bat`**.
   - First run will take a minute to set itself up.
   - A black window will stay open and print something like:
     ```
     On THIS PC, open:      http://127.0.0.1:5000
     On OTHER PCs on WiFi, open: http://192.168.1.42:5000
     ```
   - **Write down that second address (the `192.168.x.x` one) — every other PC needs it.**
   - Leave this window open. Closing it stops the server for everyone.

4. On the host PC itself, open a browser to `http://127.0.0.1:5000` and log in (see credentials below).

## 2. Connect the OTHER PCs (viewers / admins elsewhere)

On each other PC, on the **same WiFi network**:

**Easiest way:** open a browser and go to `http://<host-ip>:5000` (the address from step 3 above).
Bookmark it.

**App-like window (optional):** if the PC has Google Chrome installed, edit
`Open Inventory (other PCs).bat` — replace the IP address on the `SERVER_IP=` line with the host's
address — then copy that file to the other PC's desktop. Double-clicking it opens the ledger in a
clean window with no address bar, like a normal desktop app.

## 3. Logging in

Default accounts (change these — see below):

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | admin    | admin123  |
| User  | user     | user123   |

You can create more accounts (e.g. one login per staff member) by running this once on the host,
in a command prompt inside the `inventory_app` folder:

```
venv\Scripts\activate
python
>>> from app import get_db, init_db
>>> from werkzeug.security import generate_password_hash
>>> import sqlite3
>>> db = sqlite3.connect("inventory.db")
>>> db.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
...            ("newusername", generate_password_hash("newpassword"), "user"))  # or "admin"
>>> db.commit()
>>> exit()
```

**Change the default passwords the same way** — delete the old row for `admin`/`user` first, or just
add new accounts and stop using the defaults.

## 4. Day-to-day use

- Run `Start Server.bat` on the host PC each morning (or set it to run automatically — ask if you
  want a startup shortcut set up).
- Everyone else just opens their saved bookmark/shortcut.
- Admin edits happen instantly for everyone — refresh the page (F5) on viewer PCs to see updates.

## 5. Notes & limits

- This is meant for a single small office on one network — not for access from outside your WiFi
  (e.g. from home) without extra setup (a VPN or hosting it online).
- All data lives in one file, `inventory.db`, in this folder on the host PC. **Back this file up
  regularly** (copy it somewhere safe, e.g. a USB drive or cloud folder, weekly).
- If the host PC restarts, just re-launch `Start Server.bat`.

---

Need it hosted online instead (accessible from anywhere, not just office WiFi), or want it
auto-starting with Windows? Just ask — both are straightforward additions.
