import os
import psycopg2
import psycopg2.extras
import scheduler
from flask import (Flask, render_template, request, jsonify, session,
                   redirect, url_for)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_super_secret_key_for_sih_project')

# ===================================================================
#      DATABASE CONNECTION
# ===================================================================
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        db_url = "postgresql://postgres:55555@localhost/sih"
    return psycopg2.connect(db_url)

# ===================================================================
#      PUBLIC ROUTES (No Changes)
# ===================================================================
@app.route('/')
def home():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT batch_id, batch_name, department FROM batches ORDER BY department, batch_name;")
    batches_by_dept = {}
    for batch in cur.fetchall():
        dept = batch['department']
        if dept not in batches_by_dept:
            batches_by_dept[dept] = []
        batches_by_dept[dept].append(batch)
    cur.close()
    conn.close()
    return render_template('index.html', batches_by_dept=batches_by_dept)

@app.route('/get_timetable', methods=['POST'])
def get_timetable():
    # ... (This function remains the same)
    batch_id = request.form.get('batch_id')
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""
        SELECT t.day_of_week, t.period, s.subject_name, s.subject_id, te.name AS teacher_name, t.teacher_id
        FROM timetable t
        JOIN subjects s ON t.subject_id = s.subject_id
        JOIN teachers te ON t.teacher_id = te.teacher_id
        WHERE t.batch_id = %s ORDER BY t.day_of_week, t.period;
    """, (batch_id,))
    data = cur.fetchall()
    cur.close()
    conn.close()
    
    period_to_time_map = {
        1: "09:30-10:20", 2: "10:20-11:10", 3: "11:10-12:00 (LUNCH)",
        4: "12:00-12:50", 5: "12:50-01:40"
    }
    schedule = [dict(row) for row in data]
    for item in schedule:
        item['time'] = period_to_time_map.get(item['period'])
    return jsonify(schedule)


# ===================================================================
#      ADMINISTRATION ROUTES
# ===================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (This function remains the same)
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
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if 'loggedin' in session:
        return render_template('admin.html', username=session['username'])
    return redirect(url_for('login'))

# --- SCHEDULER TRIGGERS ---

@app.route('/run-scheduler', methods=['POST'])
def run_scheduler_route():
    """Triggers the scheduler for ALL batches."""
    if 'loggedin' in session:
        try:
            scheduler.schedule_all_classes() # Calls the main scheduler function
            return jsonify({"success": True, "message": "New global timetable generated successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": f"An error occurred: {e}"}), 500
    return jsonify({"error": "Unauthorized"}), 403

# --- NEW: Route to schedule only a single batch ---
@app.route('/admin/run-scheduler-batch', methods=['POST'])
def run_scheduler_for_batch():
    """Triggers the scheduler for only ONE specific batch."""
    if 'loggedin' in session:
        batch_id = request.form.get('batch_id')
        if not batch_id:
            return jsonify({"success": False, "message": "Batch ID is required."}), 400
        try:
            # Calls the new, targeted scheduler function
            scheduler.schedule_single_batch(int(batch_id))
            return jsonify({"success": True, "message": f"Successfully optimized timetable for Batch ID {batch_id}."})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403

# --- All other admin API routes for CRUD remain the same ---
# ... (add_teacher, update_teacher, delete_teacher, etc.)
# ...
@app.route('/admin/data/all', methods=['GET'])
def get_all_admin_data():
    if 'loggedin' in session:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        cur.execute("SELECT * FROM teachers ORDER BY teacher_id;")
        teachers = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT * FROM subjects ORDER BY subject_id;")
        subjects = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT * FROM batches ORDER BY batch_id;")
        batches = [dict(row) for row in cur.fetchall()]

        cur.execute("SELECT * FROM teacher_subjects;")
        teacher_subjects = [dict(row) for row in cur.fetchall()]
        
        cur.execute("SELECT * FROM batch_subjects;")
        batch_subjects = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        return jsonify(
            teachers=teachers, subjects=subjects, batches=batches,
            teacher_subjects=teacher_subjects, batch_subjects=batch_subjects
        )
    return jsonify({"error": "Unauthorized"}), 403

# --- TEACHER CRUD ---
@app.route('/admin/teacher/add', methods=['POST'])
def add_teacher():
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO teachers (name, subject_specialization, email, max_classes_per_week) VALUES (%s, %s, %s, %s) RETURNING teacher_id",
                (data['name'], data['specialization'], data['email'], data['max_classes'])
            )
            teacher_id = cur.fetchone()[0]
            if data.get('subjects'):
                subject_links = [(teacher_id, int(sub_id)) for sub_id in data['subjects']]
                cur.executemany("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (%s, %s);", subject_links)
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Teacher added successfully!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403

@app.route('/admin/teacher/update/<int:teacher_id>', methods=['POST'])
def update_teacher(teacher_id):
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE teachers SET name=%s, subject_specialization=%s, email=%s, max_classes_per_week=%s WHERE teacher_id=%s",
                (data['name'], data['specialization'], data['email'], data['max_classes'], teacher_id)
            )
            cur.execute("DELETE FROM teacher_subjects WHERE teacher_id = %s;", (teacher_id,))
            if data.get('subjects'):
                subject_links = [(teacher_id, int(sub_id)) for sub_id in data['subjects']]
                cur.executemany("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (%s, %s);", subject_links)
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Teacher updated successfully!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403


@app.route('/admin/teacher/delete/<int:teacher_id>', methods=['POST'])
def delete_teacher(teacher_id):
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM teachers WHERE teacher_id = %s;", (teacher_id,))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Teacher deleted successfully."})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": "Cannot delete: Teacher might be linked to existing timetable slots."}), 400
    return jsonify({"error": "Unauthorized"}), 403


# --- SUBJECT CRUD ---
@app.route('/admin/subject/add', methods=['POST'])
def add_subject():
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO subjects (subject_name, short_code, classes_per_week, max_per_day) VALUES (%s, %s, %s, %s)",
                (data['name'], data['short_code'], data['classes_week'], data['max_day'])
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Subject added successfully!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403


@app.route('/admin/subject/update/<int:subject_id>', methods=['POST'])
def update_subject(subject_id):
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE subjects SET subject_name=%s, short_code=%s, classes_per_week=%s, max_per_day=%s WHERE subject_id=%s",
                (data['name'], data['short_code'], data['classes_week'], data['max_day'], subject_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Subject updated successfully!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403


@app.route('/admin/subject/delete/<int:subject_id>', methods=['POST'])
def delete_subject(subject_id):
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM subjects WHERE subject_id = %s;", (subject_id,))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Subject deleted successfully."})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": "Cannot delete: Subject might be linked to batches or timetables."}), 400
    return jsonify({"error": "Unauthorized"}), 403


# --- BATCH CRUD ---
@app.route('/admin/batch/add', methods=['POST'])
def add_batch():
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO batches (batch_name, department, level) VALUES (%s, %s, %s) RETURNING batch_id",
                (data['name'], data['department'], data['level'])
            )
            batch_id = cur.fetchone()[0]
            if data.get('subjects'):
                for sub in data['subjects']:
                    cur.execute("INSERT INTO batch_subjects (batch_id, subject_id, classes_per_week) VALUES (%s, %s, %s);", (batch_id, sub['id'], sub['classes']))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Batch added successfully!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403


@app.route('/admin/batch/update/<int:batch_id>', methods=['POST'])
def update_batch(batch_id):
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE batches SET batch_name=%s, department=%s, level=%s WHERE batch_id=%s",
                (data['name'], data['department'], data['level'], batch_id)
            )
            cur.execute("DELETE FROM batch_subjects WHERE batch_id = %s;", (batch_id,))
            if data.get('subjects'):
                 for sub in data['subjects']:
                    cur.execute("INSERT INTO batch_subjects (batch_id, subject_id, classes_per_week) VALUES (%s, %s, %s);", (batch_id, sub['id'], sub['classes']))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Batch updated successfully!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403


@app.route('/admin/batch/delete/<int:batch_id>', methods=['POST'])
def delete_batch(batch_id):
    # ... (code remains the same)
    if 'loggedin' in session:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM batches WHERE batch_id = %s;", (batch_id,))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Batch deleted successfully."})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": "Cannot delete: Batch might be linked to existing timetables."}), 400
    return jsonify({"error": "Unauthorized"}), 403


# --- TIMETABLE SLOT UPDATE ---
@app.route('/admin/update-slot', methods=['POST'])
def update_slot():
    if 'loggedin' in session:
        try:
            data = request.get_json()
            conn = get_db_connection()
            cur = conn.cursor()
            # Check if a slot exists to update it
            cur.execute("SELECT timetable_id FROM timetable WHERE batch_id = %s AND day_of_week = %s AND period = %s", 
                        (data['batch_id'], data['day'], data['period']))
            slot_exists = cur.fetchone()

            if slot_exists:
                cur.execute("""
                    UPDATE timetable SET teacher_id = %s, subject_id = %s 
                    WHERE batch_id = %s AND day_of_week = %s AND period = %s
                """, (data['teacher_id'], data['subject_id'], data['batch_id'], data['day'], data['period']))
            else:
                # If the slot was empty (---), we need to insert a new record
                cur.execute("""
                    INSERT INTO timetable (batch_id, subject_id, teacher_id, day_of_week, period)
                    VALUES (%s, %s, %s, %s, %s)
                """, (data['batch_id'], data['subject_id'], data['teacher_id'], data['day'], data['period']))

            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Slot updated successfully!"})
        except Exception as e:
            conn.rollback()
            return jsonify({"success": False, "message": str(e)}), 500
    return jsonify({"error": "Unauthorized"}), 403


if __name__ == '__main__':
    app.run(debug=True)

