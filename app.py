from flask import Flask, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import os, webbrowser
from db import get_db_connection
import re
from datetime import date, datetime, timedelta
from flask import request, jsonify

app = Flask(__name__)
app.secret_key = "supersecretkey"

# USER LOGIN 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if role == 'doctor':
            cursor.execute("SELECT * FROM Doctor WHERE DocName=%s", (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session['doctor_id'] = user['DoctorID']
                session['doctor_name'] = user['DocName']
                return redirect('/doctor_dashboard')
            else:
                flash("Invalid doctor credentials!", "danger")

        elif role == 'patient':
            cursor.execute("SELECT * FROM Patient WHERE PatientName=%s", (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session['patient_id'] = user['PatientID']
                session['patient_name'] = user['PatientName']
                return redirect(url_for('patient_portal'))

            else:
                flash("Invalid patient credentials!", "danger")

        elif role == 'admin':
            if username == 'admin' and password == 'admin123':
                session['user_role'] = 'admin'
                return redirect('/')
            else:
                flash("Invalid admin credentials!", "danger")

        cursor.close()
        conn.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))


# DASHBOARD STATS 
def get_dashboard_stats():
    stats = {"total_patients": 0, "total_appointments": 0, "unpaid_bills": 0, "today_appointments": 0}
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS cnt FROM Patient")
        stats['total_patients'] = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) AS cnt FROM Appointment")
        stats['total_appointments'] = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) AS cnt FROM Billing WHERE PaymentStatus='Unpaid'")
        stats['unpaid_bills'] = cursor.fetchone()['cnt']
        today = date.today()
        cursor.execute("SELECT COUNT(*) AS cnt FROM Appointment WHERE AppointmentDate=%s", (today,))
        stats['today_appointments'] = cursor.fetchone()['cnt']
        cursor.close()
        conn.close()
    return stats


@app.route('/')
def home():
    if 'user_role' not in session:
        return redirect('/login')
    stats = get_dashboard_stats()
    return render_template('index.html', section='welcome', **stats, user_role=session['user_role'])


# PATIENT MANAGEMENT 
@app.route('/patients', methods=['GET', 'POST'])
def patients():
    if 'user_role' not in session or session['user_role'] != 'admin':
        flash("Only admin can manage patients.", "warning")
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        address = request.form['address']
        contact = request.form['contact']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        try:
            age=int(age)
            if age<1 or age>99:
                flash("Age must be between 1 and 99.", "danger")
                cursor.close()
                conn.close()
                return redirect('/patients')
        except ValueError:
            flash("Age must be a valid number.", "danger")
            cursor.close()
            conn.close()
            return redirect('/patients')

        if not contact.isdigit() or len(contact)!=10:
            flash("Phone number must be exactly 10 digits.", "danger")
            cursor.close()
            conn.close()
            return redirect('/patients')

        if password!=confirm_password:
            flash("Passwords do not match!", "danger")
            cursor.close()
            conn.close()
            return redirect('/patients')

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO Patient (PatientName, Age, Address, PatientContact, password) VALUES (%s,%s,%s,%s,%s)",
            (name, age, address, contact, hashed_password)
        )
        conn.commit()
        flash("Patient " + name + " added successfully!", "success")
        cursor.close()
        conn.close()
        return redirect('/patients')

    cursor.execute("SELECT * FROM Patient")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', section='patients', data=data)


# DOCTOR MANAGEMENT 
@app.route('/doctors', methods=['GET', 'POST'])
def doctors():
    if 'user_role' not in session or session['user_role'] != 'admin':
        flash("Only admin can manage doctors.", "warning")
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        dept = request.form["dept"]
        spec = request.form["spec"]
        contact = request.form["contact"]
        exp = request.form["exp"]
        password = request.form["pass"]

        if not re.fullmatch(r'\d{10}', contact):
            flash("Contact number must be exactly 10 digits.", "danger")
            cursor.close()
            conn.close()
            return redirect('/doctors')

        try:
            exp = int(exp)
            if exp < 0 or exp > 60:
                flash("Experience must be between 0 and 60 years.", "danger")
                cursor.close()
                conn.close()
                return redirect('/doctors')
        except ValueError:
            flash("Experience must be a valid number.", "danger")
            cursor.close()
            conn.close()
            return redirect('/doctors')
        
        if not password:
            flash("Password is required!", "danger")
            cursor.close()
            conn.close()
            return redirect('/doctors')

        hashed_password = generate_password_hash(password)
        cursor.execute("SELECT DeptID FROM Department WHERE DeptName=%s", (dept,))
        dept_row = cursor.fetchone()
        if dept_row:
            dept_id = dept_row["DeptID"]
        else:
            cursor.execute("INSERT INTO Department (DeptName) VALUES (%s)", (dept,))
            conn.commit()
            dept_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO Doctor (DocName, DeptID, Specialization, DeptContact, Experience, password)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, dept_id, spec, contact, exp, hashed_password))
        conn.commit()
        flash("Doctor added successfully!", "success")
        cursor.close()
        conn.close()
        return redirect("/doctors")

    cursor.execute("""
        SELECT d.DoctorID, d.DocName, dep.DeptName AS DepartmentName, d.Specialization, d.DeptContact, d.Experience
        FROM Doctor d LEFT JOIN Department dep ON d.DeptID = dep.DeptID
    """)
    doctors_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("index.html", section="doctors", doctors=doctors_list)


# APPOINTMENTS 
@app.route('/appointments', methods=['GET', 'POST'])
def appointments():
    if 'user_role' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST' and session['user_role'] == 'admin':
        patient_id = request.form['patient']
        doctor_id = request.form['doctor']
        appointment_date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        status = request.form.get('status', 'Scheduled')

        cursor.execute("""
            INSERT INTO Appointment (PatientID, DoctorID, AppointmentDate, StartTime, EndTime, Status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (patient_id, doctor_id, appointment_date, start_time, end_time, status))
        conn.commit()
        appointment_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO Billing (AppointmentID, PatientID, Amount, PaymentStatus)
            VALUES (%s, %s, %s, %s)
        """, (appointment_id, patient_id, 500.00, 'Unpaid'))
        conn.commit()
        flash("Appointment booked successfully! Bill generated.", "success")
        cursor.close()
        conn.close()
        return redirect('/appointments')

    cursor.execute("""
        SELECT a.AppointmentID, p.PatientName, d.DocName, a.AppointmentDate, a.StartTime, a.EndTime, a.Status
        FROM Appointment a JOIN Patient p ON a.PatientID = p.PatientID JOIN Doctor d ON a.DoctorID = d.DoctorID
        ORDER BY a.AppointmentDate, a.StartTime
    """)
    appointments_list = cursor.fetchall()
    cursor.execute("SELECT PatientID, PatientName FROM Patient")
    patients_list = cursor.fetchall()
    cursor.execute("SELECT DoctorID, DocName FROM Doctor")
    doctors_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', section='appointments', appointments=appointments_list, patients=patients_list, doctors=doctors_list)


#  BILLING 
@app.route('/billing', methods=['GET', 'POST'])
def billing():
    if 'user_role' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST' and session['user_role'] == 'admin':
        bill_id = request.form['bill_id']
        cursor.execute("UPDATE Billing SET PaymentStatus = 'Paid', BillDate = CURDATE() WHERE BillID = %s", (bill_id,))
        conn.commit()
        flash("Payment marked as Paid successfully!", "success")
        cursor.close()
        conn.close()
        return redirect('/billing')

    cursor.execute("""
        SELECT b.BillID, p.PatientName, a.AppointmentDate, b.Amount, b.PaymentStatus, b.BillDate
        FROM Billing b LEFT JOIN Patient p ON b.PatientID = p.PatientID
        LEFT JOIN Appointment a ON b.AppointmentID = a.AppointmentID ORDER BY b.BillID ASC
    """)
    bills_list = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', section='billing', bills=bills_list)

@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.get_json()
    user_msg = data.get('message', '').lower()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    reply = "I'm here to help you. Type 'hi' to greet or 'book appointment with Dr Name at TIME on DATE'."

    # Greeting
    if re.search(r'\b(hi|hello)\b', user_msg):
        reply = "Hello! I am your assistant. Type 'book appointment with Dr Name at TIME on DATE' to book an appointment."

    # Booking an appointment
    elif re.search(r'book.*appointment', user_msg):
        # Regex to capture doctor (Dr optional dot), time, and date
        match = re.search(
            r'book appointment with (dr\.?\s*[a-zA-Z]+\s*[a-zA-Z]*) at (\d{1,2}(?::\d{2})?\s*[ap]m) on (\d{1,2}\s+[a-zA-Z]+)',
            user_msg
        )
        if match:
            doctor_name = match.group(1).title().replace('.', '')  # Normalize doctor name
            time_str = match.group(2).lower()
            date_str = match.group(3).title()

            # Convert time
            try:
                if ':' in time_str:
                    start_time = datetime.strptime(time_str, "%I:%M %p").time()
                else:
                    start_time = datetime.strptime(time_str, "%I %p").time()
            except ValueError:
                reply = "Invalid time format. Example: '10 am' or '3:30 pm'."
                cursor.close()
                conn.close()
                return jsonify({"reply": reply})

            # End time = start + 1 hour
            end_time = (datetime.combine(datetime.today(), start_time) + timedelta(hours=1)).time()

            # Convert date
            try:
                appt_date = datetime.strptime(date_str, "%d %B").date()
                appt_date = appt_date.replace(year=datetime.now().year)
            except ValueError:
                reply = "Invalid date format. Example: '17 November'."
                cursor.close()
                conn.close()
                return jsonify({"reply": reply})

            # Lookup doctor ID
            cursor.execute("SELECT DoctorID FROM Doctor WHERE REPLACE(DocName, '.', '')=%s", (doctor_name,))
            doctor = cursor.fetchone()

            if not doctor:
                reply = f"Doctor {doctor_name} not found."
            else:
                doctor_id = doctor['DoctorID']
                # Use session patient_id if logged in, else demo 1
                patient_id = session.get('patient_id', 1)

                # Optional: Check for conflict
                cursor.execute("""
                    SELECT * FROM Appointment
                    WHERE DoctorID=%s AND AppointmentDate=%s
                    AND ((StartTime <= %s AND EndTime > %s) OR (StartTime < %s AND EndTime >= %s))
                """, (doctor_id, appt_date, start_time, start_time, end_time, end_time))
                conflict = cursor.fetchone()

                if conflict:
                    reply = f"Time conflict! Doctor {doctor_name} already has an appointment at {time_str} on {date_str}."
                else:
                    # Insert appointment
                    cursor.execute("""
                        INSERT INTO Appointment (PatientID, DoctorID, AppointmentDate, StartTime, EndTime, Status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (patient_id, doctor_id, appt_date, start_time, end_time, 'Scheduled'))
                    conn.commit()

                    # Insert billing
                    cursor.execute("""
                        INSERT INTO Billing (PatientID, AppointmentDate, Amount, PaymentStatus, BillDate)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (patient_id, appt_date, 500.0, 'Unpaid', datetime.now().date()))
                    conn.commit()

                    reply = f"Appointment booked successfully with {doctor_name} at {time_str} on {date_str}. Have a nice day!"

        else:
            reply = "Please specify doctor, time, and date like: 'book appointment with Dr Ruchi Gupta at 10 am on 17 November'."

    # Goodbye
    elif re.search(r'\b(bye|goodbye)\b', user_msg):
        reply = "Goodbye! Have a nice day."

    cursor.close()
    conn.close()
    return jsonify({"reply": reply})

# PATIENT PORTAL 
@app.route('/patient_portal', methods=['GET', 'POST'])
def patient_portal():
    if 'patient_id' not in session:
        return redirect('/login')

    patient_id = session['patient_id']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        address = request.form['address']
        contact = request.form['contact']
        cursor.execute("""
            UPDATE Patient SET PatientName=%s, Age=%s, Address=%s, PatientContact=%s WHERE PatientID=%s
        """, (name, age, address, contact, patient_id))
        conn.commit()
        flash("Profile updated successfully!", "success")
        return redirect('/patient_portal')

    cursor.execute("SELECT * FROM Patient WHERE PatientID=%s", (patient_id,))
    patient = cursor.fetchone()

    cursor.execute("""
        SELECT a.AppointmentID, d.DocName, a.AppointmentDate, a.StartTime, a.EndTime, a.Status
        FROM Appointment a JOIN Doctor d ON a.DoctorID = d.DoctorID
        WHERE a.PatientID = %s
        ORDER BY a.AppointmentDate DESC
    """, (patient_id,))
    appointments_list = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('patient_portal.html', appointments=appointments_list, patient=patient)

# DOCTOR LOGIN HELPER 
def get_doctor_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Doctor WHERE DocName=%s", (username,))
    doctor = cursor.fetchone()
    cursor.close()
    conn.close()
    return doctor


# DOCTOR LOGIN 
@app.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        doctor = get_doctor_by_username(username)
        if doctor and check_password_hash(doctor['password'], password):
            session['doctor_id'] = doctor['DoctorID']
            session['doctor_name'] = doctor['DocName']
            return redirect('/doctor_dashboard')
        else:
            flash('Invalid username or password', 'danger')

    return render_template('doctor_login.html')

# DOCTOR DASHBOARD 
@app.route('/doctor_dashboard')
def doctor_dashboard():
    if 'doctor_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Doctor WHERE DoctorID=%s", (session['doctor_id'],))
    doctor = cursor.fetchone()

    cursor.execute("""SELECT a.AppointmentID, p.PatientName, a.AppointmentDate, a.StartTime, a.EndTime, a.Status
                      FROM Appointment a JOIN Patient p ON a.PatientID = p.PatientID
                      WHERE a.DoctorID=%s ORDER BY a.AppointmentDate DESC""", (session['doctor_id'],))
    appointments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('doctor_portal.html', doctor_name=doctor['DocName'], appointments=appointments)

@app.route('/doctor/update_status/<int:appointment_id>/<status>')
def doctor_update_status(appointment_id, status):
    if 'doctor_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Appointment SET Status=%s WHERE AppointmentID=%s AND DoctorID=%s",
        (status, appointment_id, session['doctor_id'])
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash("Appointment status updated!", "success")
    return redirect(url_for('doctor_dashboard'))

@app.route('/complete_appointment', methods=['POST'])
def complete_appointment():
    appointment_id = request.form['appointment_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE Appointment SET Status=%s WHERE AppointmentID=%s", ("Completed", appointment_id))
    cursor.execute("DELETE FROM Appointment WHERE AppointmentID=%s AND Status='Completed'", (appointment_id,))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Appointment completed and removed from active list.", "success")
    return redirect("/appointments")

@app.route('/doctor/logout')
def doctor_logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect('/login')

if __name__ == '__main__':
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)
