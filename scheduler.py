import psycopg2
import psycopg2.extras
from random import choice
import os  # Import the 'os' library

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

# --- CONFIGURATION ---
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
PERIODS_PER_DAY = 5
LUNCH_BREAK_PERIOD = 3

def schedule_classes():
    conn = get_db_connection() # This now uses the new function
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        print("--- Starting Intelligent Timetable Generation ---")

        # 1. Clear Old Timetable
        print("Step 1: Clearing old timetable data...")
        cur.execute("TRUNCATE TABLE timetable RESTART IDENTITY CASCADE;")
        
        # 2. Fetch All Necessary Data
        print("Step 2: Fetching all required data...")
        cur.execute("SELECT * FROM subjects;")
        subjects_map = {row['subject_id']: row for row in cur.fetchall()}

        cur.execute("SELECT * FROM teachers;")
        teachers_map = {row['teacher_id']: row for row in cur.fetchall()}

        cur.execute("SELECT * FROM batches;")
        batches_map = {row['batch_id']: row for row in cur.fetchall()}

        cur.execute("SELECT * FROM teacher_subjects;")
        teacher_subject_links = cur.fetchall()

        cur.execute("SELECT * FROM batch_subjects;")
        workload = cur.fetchall()

        # 3. Create a list of all individual classes to be scheduled
        all_classes_to_schedule = []
        for item in workload:
            for _ in range(item['classes_per_week']):
                all_classes_to_schedule.append({
                    'batch_id': item['batch_id'],
                    'subject_id': item['subject_id']
                })
        
        # 4. The Intelligent Scheduling Algorithm
        print("Step 3: Running the intelligent scheduling algorithm...")
        
        teacher_commitments = {teacher['teacher_id']: [] for teacher in teachers_map.values()}
        batch_commitments = {batch['batch_id']: [] for batch in batches_map.values()}

        for class_to_schedule in all_classes_to_schedule:
            batch_id = class_to_schedule['batch_id']
            subject_id = class_to_schedule['subject_id']
            subject_name = subjects_map[subject_id]['subject_name']

            # Find qualified teachers for this subject
            qualified_teachers = [
                link['teacher_id'] for link in teacher_subject_links if link['subject_id'] == subject_id
            ]
            if not qualified_teachers:
                print(f"  - WARNING: No teachers for {subject_name}. Skipping.")
                continue

            # Find all possible valid slots for this class
            valid_slots = []
            for day in DAYS:
                for period in range(1, PERIODS_PER_DAY + 1):
                    if period == LUNCH_BREAK_PERIOD:
                        continue
                    
                    # Is the batch free at this time?
                    if (day, period) in batch_commitments[batch_id]:
                        continue

                    # Is there a qualified and free teacher at this time?
                    available_teachers = []
                    for teacher_id in qualified_teachers:
                        if (day, period) not in teacher_commitments[teacher_id]:
                            available_teachers.append(teacher_id)
                    
                    if available_teachers:
                        valid_slots.append({'day': day, 'period': period, 'teacher_id': choice(available_teachers)})
            
            # Now, pick one of the valid slots and place the class
            if valid_slots:
                chosen_slot = choice(valid_slots)
                day = chosen_slot['day']
                period = chosen_slot['period']
                teacher_id = chosen_slot['teacher_id']

                # Insert into DB
                cur.execute("""
                    INSERT INTO timetable (batch_id, subject_id, teacher_id, day_of_week, period)
                    VALUES (%s, %s, %s, %s, %s)
                """, (batch_id, subject_id, teacher_id, day, period))

                # Record the commitment
                batch_commitments[batch_id].append((day, period))
                teacher_commitments[teacher_id].append((day, period))
                print(f"  + Success: Placed {subject_name} for Batch {batch_id} on {day}, Period {period}")
            else:
                print(f"  - FAILED: No valid slot found for {subject_name} for Batch {batch_id}.")

        # 5. Commit all successful changes
        print("\nStep 4: Committing all changes to the database...")
        conn.commit()
        print("\n✅ Scheduling completed successfully!")

    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        cur.close()
        conn.close()
        print("Database connection closed.")

if __name__ == "__main__":
    schedule_classes()