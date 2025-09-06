from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg2
import psycopg2.extras
import scheduler
import os  # Import the 'os' library to access environment variables

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_for_sih_project'

# ===================================================================
#      DATABASE CONNECTION (FOR ONLINE DEPLOYMENT)
# ===================================================================
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    # This will use the DATABASE_URL from the Render environment when online
    db_url = os.environ.get('DATABASE_URL')
    
    # If it's not online, it will fall back to your local database for testing
    if not db_url:
        db_url = "postgresql://postgres:55555@localhost/sih"
        
    return psycopg2.connect(db_url)

# ===================================================================
#      PUBLIC ROUTES (No changes needed here)
# ===================================================================
# In your app.py file

@app.route('/')
def home():
    """Renders the main timetable viewer page and provides batches grouped by department."""
    conn = get_db_connection()
    # Use DictCursor to easily access columns by name (e.g., batch['department'])
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Fetch the department along with other batch details
    cur.execute("SELECT batch_id, batch_name, department FROM batches ORDER BY department, batch_name;")
    
    # --- This is the new logic ---
    # Group the flat list of batches into a dictionary by department
    batches_by_dept = {}
    for batch in cur.fetchall():
        dept = batch['department']
        if dept not in batches_by_dept:
            batches_by_dept[dept] = []
        batches_by_dept[dept].append(batch)
        
    cur.close()
    conn.close()
    
    # Send the correctly named and structured variable to the template
    return render_template('index.html', batches_by_dept=batches_by_dept)


@app.route('/get_timetable', methods=['POST'])
def get_timetable():
    """API endpoint to fetch the timetable for a selected batch."""
    batch_id = request.form.get('batch_id')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT t.day_of_week, t.period, s.subject_name, te.name AS teacher_name
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.subject_id
        JOIN teachers te ON t.teacher_id = te.teacher_id
        WHERE t.batch_id = %s ORDER BY t.day_of_week, t.period;
    """, (batch_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    
    period_to_time_map = {
        1: "09:30 - 10:20", 2: "10:20 - 11:10", 3: "11:10 - 12:00 (LUNCH)",
        4: "12:00 - 12:50", 5: "12:50 - 01:40"
    }
    schedule = []
    for row in data:
        item = dict(row)
        item['time'] = period_to_time_map.get(item['period'])
        schedule.append(item)
    return jsonify(schedule)


# ===================================================================
#      ADMINISTRATION ROUTES
# ===================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles admin login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM admin WHERE username = %s AND password = %s;", (username, password))
        account = cur.fetchone()
        cur.close()
        conn.close()
        if account:
            session['loggedin'] = True
            session['username'] = account['username']
            return redirect(url_for('admin'))
        else:
            return render_template('login.html', msg='Incorrect username or password!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs the admin out."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    """Renders the main admin dashboard if logged in."""
    if 'loggedin' in session:
        return render_template('admin.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/run-scheduler', methods=['POST'])
def run_scheduler_route():
    """API endpoint to trigger the scheduler script."""
    if 'loggedin' in session:
        try:
            scheduler.schedule_classes()
            return jsonify({"success": True, "message": "New timetable generated successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403

# --- API Routes for Data Management ---

@app.route('/admin/data', methods=['GET'])
def get_admin_data():
    """Fetches all data for the dynamic admin panel."""
    if 'loggedin' in session:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("SELECT * FROM teachers ORDER BY teacher_id;")
        teachers = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT * FROM subjects ORDER BY subject_id;")
        subjects = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT * FROM batches ORDER BY batch_id;")
        batches = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        return jsonify(teachers=teachers, subjects=subjects, batches=batches)
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/admin/add-teacher', methods=['POST'])
def add_teacher():
    """API endpoint to add a new teacher."""
    if 'loggedin' in session:
        try:
            name = request.form['name']
            specialization = request.form['specialization']
            email = request.form['email']
            max_classes = request.form['max_classes']
            
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO teachers (name, subject_specialization, email, max_classes_per_week) VALUES (%s, %s, %s, %s)",
                (name, specialization, email, max_classes)
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Teacher added successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/admin/add-subject', methods=['POST'])
def add_subject():
    """API endpoint to add a new subject."""
    if 'loggedin' in session:
        try:
            subject_name = request.form['subject_name']
            short_code = request.form['short_code']
            classes_per_week = request.form['classes_per_week']
            max_per_day = request.form['max_per_day']
            
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO subjects (subject_name, short_code, classes_per_week, max_per_day) VALUES (%s, %s, %s, %s)",
                (subject_name, short_code, classes_per_week, max_per_day)
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Subject added successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403


if __name__ == '__main__':
    app.run(debug=True)