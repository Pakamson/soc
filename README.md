# Simple Inventory System (Flask + PostgreSQL)

This project is a minimal inventory recorder: a small HTML form posts to a Flask backend which inserts rows into a PostgreSQL database.

Files added:
- `app.py` - Flask application with POST `/api/items` endpoint (inserts into `soc_inventory`)
- `templates/index.html` - front-end form matching the `soc_inventory` columns
- `schema.sql` - SQL to create the `soc_inventory` table
- `requirements.txt` - Python dependencies
- `.env.example` - sample environment variables

Quick start (Windows PowerShell):

1. Create a Python virtualenv and activate it

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```


2. Create the database and table (example using psql)

```powershell
# create database (adjust user/host as needed)
psql -h localhost -U postgres -c "CREATE DATABASE inventory_db;"
# apply schema
psql -h localhost -U postgres -d inventory_db -f schema.sql
```

3. Create a `.env` file in the project root (copy from `.env.example`) and set credentials.

4. Run the app

```powershell
python app.py
```

5. Open http://localhost:5000 in your browser and add items.

Notes:
- This is a minimal example for local development. Use a proper WSGI server and secure secrets for production.
- If you need help connecting to a remote PostgreSQL server or using Docker, tell me and I can add examples.
