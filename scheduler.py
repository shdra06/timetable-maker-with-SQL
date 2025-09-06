import psycopg2
import psycopg2.extras
from random import choice
import os

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        db_url = "postgresql://postgres:55555@localhost/sih"
    return psycopg2.connect(db_url)

# --- CONFIGURATION ---
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
PERIODS_PER_DAY = 5
LUNCH_BREAK_PERIOD = 3

def _run_scheduling_logic(cur, batch_ids):
    """A helper function containing the main scheduling algorithm."""
    
    cur.execute("SELECT * FROM subjects;")
    subjects_map = {row['subject_id']: row for row in cur.fetchall()}

    cur.execute("SELECT * FROM teachers;")
    teachers_map = {row['teacher_id']: row for row in cur.fetchall()}

    cur.execute("SELECT * FROM teacher_subjects;")
    teacher_subject_links = cur.fetchall()

    cur.execute("SELECT * FROM batch_subjects WHERE batch_id = ANY(%s);", (batch_ids,))
    workload = cur.fetchall()

    cur.execute("SELECT teacher_id, day_of_week, period FROM timetable;")
    teacher_commitments = {t['teacher_id']: [] for t in teachers_map.values()}
    for row in cur.fetchall():
        teacher_commitments[row['teacher_id']].append((row['day_of_week'], row['period']))

    cur.execute("SELECT batch_id, day_of_week, period FROM timetable;")
    batch_commitments = {b_id: [] for b_id in batch_ids}
    for row in cur.fetchall():
        if row['batch_id'] in batch_commitments:
            batch_commitments[row['batch_id']].append((row['day_of_week'], row['period']))

    all_classes_to_schedule = []
    for item in workload:
        for _ in range(item['classes_per_week']):
            all_classes_to_schedule.append({
                'batch_id': item['batch_id'],
                'subject_id': item['subject_id']
            })
    
    for class_to_schedule in all_classes_to_schedule:
        batch_id = class_to_schedule['batch_id']
        subject_id = class_to_schedule['subject_id']
        subject_name = subjects_map[subject_id]['subject_name']

        qualified_teachers = [link['teacher_id'] for link in teacher_subject_links if link['subject_id'] == subject_id]
        if not qualified_teachers:
            print(f"  - WARNING: No teachers for {subject_name}. Skipping.")
            continue

        valid_slots = []
        for day in DAYS:
            for period in range(1, PERIODS_PER_DAY + 1):
                if period == LUNCH_BREAK_PERIOD: continue
                if (day, period) in batch_commitments[batch_id]: continue

                available_teachers = [t_id for t_id in qualified_teachers if (day, period) not in teacher_commitments[t_id]]
                if available_teachers:
                    valid_slots.append({'day': day, 'period': period, 'teacher_id': choice(available_teachers)})
        
        if valid_slots:
            chosen_slot = choice(valid_slots)
            day, period, teacher_id = chosen_slot['day'], chosen_slot['period'], chosen_slot['teacher_id']

            cur.execute(
                "INSERT INTO timetable (batch_id, subject_id, teacher_id, day_of_week, period) VALUES (%s, %s, %s, %s, %s)",
                (batch_id, subject_id, teacher_id, day, period)
            )
            batch_commitments[batch_id].append((day, period))
            teacher_commitments[teacher_id].append((day, period))
        else:
            print(f"  - FAILED: No valid slot found for {subject_name} for Batch {batch_id}.")

def schedule_all_classes():
    """Clears the entire timetable and regenerates it for ALL batches."""
    print("--- Starting Global Timetable Generation ---")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("TRUNCATE TABLE timetable RESTART IDENTITY CASCADE;")
        cur.execute("SELECT batch_id FROM batches;")
        all_batch_ids = [row['batch_id'] for row in cur.fetchall()]
        if all_batch_ids:
            _run_scheduling_logic(cur, all_batch_ids)
        conn.commit()
        print("\n✅ Global scheduling completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"❌ An error occurred during global scheduling: {e}")
        raise e
    finally:
        cur.close()
        conn.close()

def schedule_single_batch(batch_id_to_schedule):
    """Clears the timetable for only ONE batch and regenerates it."""
    print(f"--- Starting Targeted Optimization for Batch ID: {batch_id_to_schedule} ---")
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    try:
        cur.execute("DELETE FROM timetable WHERE batch_id = %s;", (batch_id_to_schedule,))
        _run_scheduling_logic(cur, [batch_id_to_schedule])
        conn.commit()
        print(f"\n✅ Targeted optimization for Batch ID {batch_id_to_schedule} completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"❌ An error occurred during targeted optimization: {e}")
        raise e
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    schedule_all_classes()