import os
import json
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import StringIO

from flask import Flask, request, jsonify, render_template, make_response, session, redirect, url_for, flash
import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Secret key for session management. Prefer to set via environment in production.
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')


def parse_date(d):
    if not d:
        return None
    if isinstance(d, str):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except Exception:
            return None
    if isinstance(d, datetime):
        return d.date()
    return None


def get_db_conn():
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "inventory_db")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "P@ssw0rd")

    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
    )
    return conn


# --- Authentication routes -------------------------------------------------
from werkzeug.security import generate_password_hash, check_password_hash


def get_user_by_username_or_email(identifier):
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=DictCursor)
        cur.execute("SELECT user_id, username, email, password_hash FROM users WHERE username = %s OR email = %s LIMIT 1", (identifier, identifier))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    # POST
    data = request.form or request.get_json() or {}
    identifier = (data.get('username') or data.get('identifier') or '').strip()
    password = (data.get('password') or '').strip()
    if not identifier or not password:
        flash('Username/email and password required')
        return render_template('login.html'), 400

    user = get_user_by_username_or_email(identifier)
    if not user:
        flash('Invalid credentials')
        return render_template('login.html'), 401

    if not check_password_hash(user['password_hash'], password):
        flash('Invalid credentials')
        return render_template('login.html'), 401

    # Success: set session and update last_login
    session['user_id'] = user['user_id']
    session['username'] = user['username']
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s", (user['user_id'],))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

    return redirect(url_for('search'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('search'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Simple registration endpoint. You may restrict access in production."""
    if request.method == 'GET':
        return render_template('register.html')

    data = request.form or request.get_json() or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not email or not password:
        flash('username, email and password are required')
        return render_template('register.html'), 400

    password_hash = generate_password_hash(password)
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING user_id",
            (username, email, password_hash),
        )
        uid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        # Basic duplicate handling
        msg = str(e)
        if 'unique' in msg.lower() or 'duplicate' in msg.lower():
            flash('Username or email already exists')
            return render_template('register.html'), 400
        return jsonify({'error': 'failed to create user', 'details': msg}), 500

    # Auto-login after register
    session['user_id'] = uid
    session['username'] = username
    return redirect(url_for('index'))


# Protect pages: require login for all endpoints except a small allowlist.
@app.before_request
def require_login_for_pages():
    # If user is logged in, allow
    if session.get('user_id'):
        return None

    # Allow list of endpoint names that do not require auth
    allow_endpoints = {
        'index', 'login', 'register', 'static'
    }

    # request.endpoint can be None for some requests; allow those to continue
    endpoint = request.endpoint
    if endpoint is None:
        return None

    # Allow endpoints in the allowlist
    if endpoint in allow_endpoints:
        return None

    # If this is an API request (starts with /api/) return 401 JSON
    if request.path.startswith('/api/'):
        return jsonify({'error': 'authentication_required'}), 401

    # Otherwise redirect to login (index)
    return redirect(url_for('index'))


@app.route('/add')
def add_item_page():
    return render_template('add.html')



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/bulk-import")
def bulk_import():
    """Render the bulk import page which allows CSV uploads."""
    return render_template("bulk_import.html")


@app.route("/advanced-search")
def advanced_search():
    params = {
        'record_date_start': request.args.get('record_date_start'),
        'record_date_end': request.args.get('record_date_end'),
        'purchase_date_start': request.args.get('purchase_date_start'),
        'purchase_date_end': request.args.get('purchase_date_end'),
        'maintenance_date_start': request.args.get('maintenance_date_start'),
        'maintenance_date_end': request.args.get('maintenance_date_end'),
        'price_min': request.args.get('price_min'),
        'price_max': request.args.get('price_max'),
        'label': request.args.get('label', '').strip(),
        'type': request.args.get('type', '').strip(),
        'brand': request.args.get('brand', '').strip(),
        'model_no': request.args.get('model_no', '').strip(),
        'serial_no': request.args.get('serial_no', '').strip(),
        'location': request.args.get('location', '').strip(),
        'location_2': request.args.get('location_2', '').strip(),
        'location_3': request.args.get('location_3', '').strip(),
        'invoice_no': request.args.get('invoice_no', '').strip(),
        'specification1': request.args.get('specification1', '').strip(),
        'specification2': request.args.get('specification2', '').strip(),
        'specification3': request.args.get('specification3', '').strip(),
        'project_code': request.args.get('project_code', '').strip(),
        'department': request.args.get('department', '').strip(),
        'status': request.args.get('status', '').strip(),
    }

    search_performed = any(v for v in params.values() if v)
    items = []

    if search_performed:
        try:
            conn = get_db_conn()
            cur = conn.cursor(cursor_factory=DictCursor)

            conditions = []
            query_params = []

            if params['record_date_start']:
                conditions.append("record_date >= %s")
                query_params.append(params['record_date_start'])
            if params['record_date_end']:
                conditions.append("record_date <= %s")
                query_params.append(params['record_date_end'])

            if params['purchase_date_start']:
                conditions.append("purchase_date >= %s")
                query_params.append(params['purchase_date_start'])
            if params['purchase_date_end']:
                conditions.append("purchase_date <= %s")
                query_params.append(params['purchase_date_end'])

            if params['maintenance_date_start']:
                conditions.append("maintenance_end_date >= %s")
                query_params.append(params['maintenance_date_start'])
            if params['maintenance_date_end']:
                conditions.append("maintenance_end_date <= %s")
                query_params.append(params['maintenance_date_end'])

            if params['price_min']:
                conditions.append("price >= %s")
                query_params.append(Decimal(params['price_min']))
            if params['price_max']:
                conditions.append("price <= %s")
                query_params.append(Decimal(params['price_max']))

            text_fields = ['label', 'type', 'brand', 'model_no', 'serial_no', 'location', 'location_2', 'location_3', 'invoice_no', 'specification1', 'specification2', 'specification3', 'project_code', 'department', 'status']
            for field in text_fields:
                if params[field]:
                    conditions.append(f"{field} ILIKE %s")
                    query_params.append(f"{params[field]}%")

            query = "SELECT * FROM soc_inventory"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY label, type, brand"

            cur.execute(query, query_params)
            items = [dict(row) for row in cur.fetchall()]

            cur.close()
            conn.close()

        except Exception as e:
            print("Error in advanced search:", e)
            return render_template("advanced_search.html", error=str(e), items=[], search_performed=search_performed)

    return render_template("advanced_search.html", items=items, search_performed=search_performed)


@app.route("/api/items/import-csv", methods=["POST"])
def import_csv():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']
        if not file or not file.filename.lower().endswith('.csv'):
            return jsonify({"error": "Invalid file. Please provide a CSV file"}), 400

        raw = file.stream.read()
        try:
            text = raw.decode('utf-8-sig')
        except Exception:
            text = raw.decode('utf-8', errors='replace')

        stream = StringIO(text, newline=None)
        reader = csv.DictReader(stream)

        if not reader.fieldnames:
            return jsonify({"error": "CSV file has no header row"}), 400

        normalized_fieldnames = [h.strip().lower() for h in reader.fieldnames if h]
        headers_set = set(normalized_fieldnames)

        # Verify that required headers exist
        expected_headers = {
            'record_date', 'label', 'type', 'brand', 'model_no', 'serial_no',
            'location', 'location_2', 'location_3', 'invoice_no', 'purchase_date', 'price',
            'maintenance_end_date', 'specification1', 'specification2', 'specification3', 
            'project_code', 'department', 'status'
        }
        missing_headers = expected_headers - headers_set
        if missing_headers:
            return jsonify({
                "error": f"CSV missing required headers: {', '.join(sorted(missing_headers))}"
            }), 400

        conn = get_db_conn()
        cur = conn.cursor()
        imported = 0

        for raw_row in reader:
            try:
                row = {(k.strip().lower() if k else ''): (v.strip() if isinstance(v, str) else v) for k, v in raw_row.items()}

                record_date = parse_date(row.get('record_date'))
                label = row.get('label')
                item_type = row.get('type')
                brand = row.get('brand')
                model_no = row.get('model_no')
                serial_no = row.get('serial_no')
                location = row.get('location')
                location_2 = row.get('location_2')
                location_3 = row.get('location_3')
                specification1 = row.get('specification1')
                specification2 = row.get('specification2')
                specification3 = row.get('specification3')
                invoice_no = row.get('invoice_no')
                purchase_date = parse_date(row.get('purchase_date'))
                price = row.get('price')
                maintenance_end_date = parse_date(row.get('maintenance_end_date'))
                status = row.get('status')

                price_val = None
                if price not in (None, ""):
                    try:
                        price_val = Decimal(str(price))
                    except (InvalidOperation, ValueError):
                        continue

                # Upsert by serial_no if provided, otherwise insert
                if serial_no:
                    upsert_q = sql.SQL("""
                        INSERT INTO soc_inventory (
                            record_date, label, type, brand, model_no, serial_no,
                            location, location_2, location_3, invoice_no, purchase_date, price,
                            maintenance_end_date, specification1, specification2, specification3,
                            project_code, department, status
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (serial_no) DO UPDATE SET
                          record_date = EXCLUDED.record_date,
                          label = EXCLUDED.label,
                          type = EXCLUDED.type,
                          brand = EXCLUDED.brand,
                          model_no = EXCLUDED.model_no,
                          location = EXCLUDED.location,
                          location_2 = EXCLUDED.location_2,
                          location_3 = EXCLUDED.location_3,
                          invoice_no = EXCLUDED.invoice_no,
                          purchase_date = EXCLUDED.purchase_date,
                          price = EXCLUDED.price,
                          maintenance_end_date = EXCLUDED.maintenance_end_date,
                          specification1 = EXCLUDED.specification1,
                          specification2 = EXCLUDED.specification2,
                          specification3 = EXCLUDED.specification3,
                          project_code = EXCLUDED.project_code,
                          department = EXCLUDED.department,
                          status = EXCLUDED.status
                    """)

                    cur.execute(upsert_q, (
                        record_date, label, item_type, brand, model_no, serial_no,
                        location, location_2, location_3, invoice_no, purchase_date, price_val,
                        maintenance_end_date, specification1, specification2, specification3,
                        row.get('project_code'), row.get('department'), status
                    ))
                else:
                    # Insert including the new location_3 and specification fields
                    insert_q = sql.SQL("""
                        INSERT INTO soc_inventory (
                            record_date, label, type, brand, model_no, location,
                            location_2, location_3, invoice_no, purchase_date, price,
                            maintenance_end_date, specification1, specification2, specification3,
                            project_code, department, status
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """)
                    cur.execute(insert_q, (
                        record_date, label, item_type, brand, model_no, location,
                        location_2, location_3, invoice_no, purchase_date, price_val,
                        maintenance_end_date, specification1, specification2, specification3,
                        row.get('project_code'), row.get('department'), status
                    ))

                imported += 1
            except Exception as e:
                print(f"Error importing row: {e}")
                continue

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "CSV import completed successfully", "imported": imported}), 200
    except Exception as e:
        print("Error importing CSV:", e)
        return jsonify({"error": "Failed to import CSV", "details": str(e)}), 500


@app.route("/api/items/export-csv")
def export_csv():
    search_query = request.args.get('q', '').strip()
    try:
        conn = get_db_conn()
        cur = conn.cursor(cursor_factory=DictCursor)

        # Special case: "*" exports all items
        if search_query == "*":
            cur.execute("SELECT * FROM soc_inventory ORDER BY record_date DESC, label, type")
        elif search_query:
            search_sql = sql.SQL("""
                SELECT *
                FROM soc_inventory
                WHERE label ILIKE %s OR type ILIKE %s OR brand ILIKE %s
                  OR model_no ILIKE %s OR serial_no ILIKE %s OR location ILIKE %s
                  OR location_2 ILIKE %s OR invoice_no ILIKE %s OR status ILIKE %s
                  OR project_code ILIKE %s OR department ILIKE %s
                ORDER BY record_date DESC, label, type
            """)
            sp = f"{search_query}%"
            # SQL has 11 placeholders (label,type,brand,model_no,serial_no,location,location_2,invoice_no,status,project_code,department)
            cur.execute(search_sql, [sp] * 11)
        else:
            cur.execute("SELECT * FROM soc_inventory ORDER BY label, type, brand")

        items = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()

        output = StringIO()
        if items:
            headers = list(items[0].keys())
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            writer.writerows(items)

        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        response.headers["Content-type"] = "text/csv"
        return response
    except Exception as e:
        print("Error exporting CSV:", e)
        return jsonify({"error": "Failed to export CSV", "details": str(e)}), 500


@app.route("/search")
def search():
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    items = []
    total_count = 0
    search_performed = bool(search_query)
    
    if search_query:
        try:
            conn = get_db_conn()
            cur = conn.cursor(cursor_factory=DictCursor)
            
            # Special case: "*" displays all items
            if search_query == "*":
                # Get total count
                cur.execute("SELECT COUNT(*) FROM soc_inventory")
                total_count = cur.fetchone()[0]
                
                # Get paginated results
                search_sql = sql.SQL("""
                    SELECT * FROM soc_inventory
                    ORDER BY record_date DESC, label, type
                    LIMIT %s OFFSET %s
                """)
                cur.execute(search_sql, (per_page, offset))
            else:
                # Get total count for search
                count_sql = sql.SQL("""
                    SELECT COUNT(*) FROM soc_inventory
                    WHERE label ILIKE %s OR type ILIKE %s OR brand ILIKE %s
                      OR model_no ILIKE %s OR serial_no ILIKE %s OR location ILIKE %s
                      OR location_2 ILIKE %s OR invoice_no ILIKE %s OR status ILIKE %s
                      OR project_code ILIKE %s OR department ILIKE %s
                """)
                sp = f"{search_query}%"
                cur.execute(count_sql, [sp] * 11)
                total_count = cur.fetchone()[0]
                
                # Get paginated results
                search_sql = sql.SQL("""
                    SELECT * FROM soc_inventory
                    WHERE label ILIKE %s OR type ILIKE %s OR brand ILIKE %s
                      OR model_no ILIKE %s OR serial_no ILIKE %s OR location ILIKE %s
                      OR location_2 ILIKE %s OR invoice_no ILIKE %s OR status ILIKE %s
                      OR project_code ILIKE %s OR department ILIKE %s
                    ORDER BY record_date DESC, label, type
                    LIMIT %s OFFSET %s
                """)
                cur.execute(search_sql, [sp] * 11 + [per_page, offset])
            
            items = [dict(row) for row in cur.fetchall()]
            cur.close()
            conn.close()
        except Exception as e:
            print("Error searching inventory:", e)
            return render_template("search.html", error=str(e), items=[], search_performed=search_performed, 
                                 page=page, total_count=0, per_page=per_page)
    
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0
    return render_template("search.html", items=items, search_performed=search_performed, 
                         page=page, total_count=total_count, total_pages=total_pages, per_page=per_page)


@app.route("/api/items/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Expected JSON body"}), 400

        record_date = parse_date(data.get("record_date"))
        label = data.get("label")
        item_type = data.get("type")
        brand = data.get("brand")
        model_no = data.get("model_no")
        serial_no = data.get("serial_no")
        location = data.get("location")
        location_2 = data.get("location_2")
        location_3 = data.get("location_3")
        invoice_no = data.get("invoice_no")
        purchase_date = parse_date(data.get("purchase_date"))
        maintenance_end_date = parse_date(data.get("maintenance_end_date"))
        price = data.get("price")
        if price in (None, ""):
            price_val = None
        else:
            try:
                price_val = Decimal(str(price))
            except (InvalidOperation, ValueError):
                return jsonify({"error": "'price' must be a number"}), 400
        specification1 = data.get("specification1")
        specification2 = data.get("specification2")
        specification3 = data.get("specification3")
        project_code = data.get("project_code")
        department = data.get("department")
        status = data.get("status")

        conn = get_db_conn()
        cur = conn.cursor()
        update_q = sql.SQL("""
            UPDATE soc_inventory SET
                record_date = %s,
                label = %s,
                type = %s,
                brand = %s,
                model_no = %s,
                serial_no = %s,
                location = %s,
                location_2 = %s,
                location_3 = %s,
                invoice_no = %s,
                purchase_date = %s,
                price = %s,
                maintenance_end_date = %s,
                specification1 = %s,
                specification2 = %s,
                specification3 = %s,
                project_code = %s,
                department = %s,
                status = %s
            WHERE serial_no = %s
            RETURNING serial_no
        """)
        cur.execute(update_q, (
            record_date, label, item_type, brand, model_no, serial_no,
            location, location_2, location_3, invoice_no, purchase_date, price_val,
            maintenance_end_date, specification1, specification2, specification3,
            project_code, department, status, serial_no
        ))
        updated = cur.fetchone()
        if not updated:
            conn.rollback()
            return jsonify({"error": "Item not found"}), 404
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Item saved successfully", "serial_no": serial_no}), 200
    except Exception as e:
        print("Error updating soc_inventory row:", e)
        return jsonify({"error": "internal_server_error", "details": str(e)}), 500


@app.route("/api/items/<serial_no>", methods=["DELETE"])
def delete_item(serial_no):
    """Delete an item by serial number"""
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        
        # Check if item exists first
        cur.execute("SELECT serial_no FROM soc_inventory WHERE serial_no = %s", (serial_no,))
        item = cur.fetchone()
        
        if not item:
            cur.close()
            conn.close()
            return jsonify({"error": "Item not found"}), 404
        
        # Delete the item
        delete_q = sql.SQL("DELETE FROM soc_inventory WHERE serial_no = %s")
        cur.execute(delete_q, (serial_no,))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"message": "Item deleted successfully", "serial_no": serial_no}), 200
    except Exception as e:
        print("Error deleting soc_inventory row:", e)
        return jsonify({"error": "internal_server_error", "details": str(e)}), 500



@app.route("/api/items", methods=["POST"])
def create_item():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Expected JSON body"}), 400

        record_date = parse_date(data.get("record_date"))
        label = data.get("label")
        item_type = data.get("type")
        brand = data.get("brand")
        model_no = data.get("model_no")
        serial_no = data.get("serial_no")
        location = data.get("location")
        location_2 = data.get("location_2")
        location_3 = data.get("location_3")
        invoice_no = data.get("invoice_no")
        purchase_date = parse_date(data.get("purchase_date"))
        price = data.get("price")
        if price in (None, ""):
            price_val = None
        else:
            try:
                price_val = Decimal(str(price))
            except (InvalidOperation, ValueError):
                return jsonify({"error": "'price' must be a number"}), 400
        maintenance_end_date = parse_date(data.get("maintenance_end_date"))
        specification1 = data.get("specification1")
        specification2 = data.get("specification2")
        specification3 = data.get("specification3")
        status = data.get("status")

        conn = get_db_conn()
        cur = conn.cursor()

        if serial_no:
            q = sql.SQL("""
                INSERT INTO soc_inventory (
                    record_date, label, type, brand, model_no, serial_no,
                    location, location_2, location_3, invoice_no, purchase_date, price,
                    maintenance_end_date, specification1, specification2, specification3,
                    project_code, department, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (serial_no) DO UPDATE SET
                    record_date = EXCLUDED.record_date,
                    label = EXCLUDED.label,
                    type = EXCLUDED.type,
                    brand = EXCLUDED.brand,
                    model_no = EXCLUDED.model_no,
                    location = EXCLUDED.location,
                    location_2 = EXCLUDED.location_2,
                    location_3 = EXCLUDED.location_3,
                    invoice_no = EXCLUDED.invoice_no,
                    purchase_date = EXCLUDED.purchase_date,
                    price = EXCLUDED.price,
                    maintenance_end_date = EXCLUDED.maintenance_end_date,
                    specification1 = EXCLUDED.specification1,
                    specification2 = EXCLUDED.specification2,
                    specification3 = EXCLUDED.specification3,
                    project_code = EXCLUDED.project_code,
                    department = EXCLUDED.department,
                    status = EXCLUDED.status
            """)
            cur.execute(q, (
                record_date, label, item_type, brand, model_no, serial_no,
                location, location_2, location_3, invoice_no, purchase_date, price_val,
                maintenance_end_date, specification1, specification2, specification3,
                project_code, department, status
            ))
        else:
            q = sql.SQL("""
                INSERT INTO soc_inventory (
                    record_date, label, type, brand, model_no, location,
                    location_2, location_3, invoice_no, purchase_date, price,
                    maintenance_end_date, specification1, specification2, specification3,
                    project_code, department, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """)
            cur.execute(q, (
                record_date, label, item_type, brand, model_no, location,
                location_2, location_3, invoice_no, purchase_date, price_val,
                maintenance_end_date, specification1, specification2, specification3,
                data.get('project_code'), data.get('department'), status
            ))

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Item saved successfully", "serial_no": serial_no}), 200
    except Exception as e:
        print("Error inserting soc_inventory row:", e)
        return jsonify({"error": "internal_server_error", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
