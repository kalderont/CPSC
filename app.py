import pyodbc
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sdr382t09fsdupiuHDZJKHFskndusvoiut8wciyrasiojfkcpowgu4v6t7'

db_config = {
    'server': 'CPSC.database.windows.net', 
    'database': 'CPSC', 
    'username': 'CPSC',  
    'password': 'Password1',  
    'driver': '{ODBC Driver 18 for SQL Server}'  
}

def get_db_connection():
    conn_str = f'DRIVER={db_config["driver"]};SERVER={db_config["server"]},1433;DATABASE={db_config["database"]};UID={db_config["username"]};PWD={db_config["password"]};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;'
    connection = pyodbc.connect(conn_str)
    return connection

@app.route("/")
def home():
        return "Success!"

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM Employee WHERE Email = ? AND Pass = ?", (email, password))
        user = cursor.fetchone()

        # if user:
        #     session['user_id'] = user[-1] 
        #     session['is_manager'] = user[-3]  
        #     return redirect(url_for('dashboard'))
        if user:
            session['user_id'] = user[0] 
            session['is_manager'] = user[-2]  
            return redirect(url_for('dashboard'))

        flash('Invalid credentials. Please try again.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_manager', None)
    return redirect(url_for('login'))

@app.route('/forgotpassword', methods=['GET', 'POST'])
def forgotpassword():
    if request.method == 'POST':
        email = request.form['email']
        new_password = request.form['new_password']

        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the user exists
        cursor.execute("SELECT * FROM Employee WHERE Email = ?", (email,))
        user = cursor.fetchone()

        if user:
            # Update the user's password
            cursor.execute("UPDATE Employee SET Pass = ? WHERE Email = ?", (new_password, email))
            conn.commit()
            flash('Password reset successfully!', 'success')
            return redirect(url_for('login'))  # Redirect to login page
        else:
            flash('User does not exist. Please check the email and try again.', 'danger')
            return redirect(url_for('forgotpassword'))

    return render_template('forgot-password.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        user_type = request.form['user_type']
        manager = 1 if user_type == 'manager' else 0
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO employee (First_Name, Last_Name, Email, Pass, Manager)
                VALUES (?, ?, ?, ?, ?)
            """, (first_name, last_name, email, password, manager))
            conn.commit()
            flash("Account successfully created!", "success")
            return redirect(url_for('login')) 
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')  

@app.route('/dashboard')
def dashboard():
    # Check if user is a manager or not
    if 'is_manager' in session and session['is_manager'] == 1:
        return render_template('dashboard.html')  # Render manager-specific page
    elif 'is_manager' in session and session['is_manager'] == 0:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Recall WHERE Priority = 'High';")
        high_recalls = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('investigator_dashboard.html', high_recalls=high_recalls)  # Render regular user page
    else:
        return redirect(url_for('login'))  # Redirect to login if no session

@app.route('/importdata')
def import_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Recall")
    recall_data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('importData.html', recall_data=recall_data)

@app.route('/importlistings')
def import_listings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Marketplace_Listing")
    listings = cursor.fetchall()
    cursor.execute("SELECT Recall_ID, Name_of_product FROM Recall")
    recalls = cursor.fetchall()
    cursor.execute("SELECT Listing_ID, Recall_ID FROM Incidents")
    existing_incidents = {(row.Listing_ID, row.Recall_ID) for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return render_template(
        'importlistings.html',
        listings=listings,
        recalls=recalls,
        existing_incidents=existing_incidents
    )


@app.route('/add_listing', methods=['POST'])
def add_listing():
    data = request.json
    product_name = data['product_name']
    listing_price = data['listing_price']
    date_of_listing = data['date_of_listing']
    marketplace_name = data['marketplace_name']
    url = data['url']
    seller_name = data['seller_name']
    
    seller_email = data['seller_email']

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if seller exists
    cursor.execute("SELECT seller_ID FROM Seller WHERE Seller_Email = ?", (seller_email,))
    seller = cursor.fetchone()

    if seller:
        seller_id = seller[0]
    else:
        cursor.execute(
            "INSERT INTO Seller (Seller_Name, Seller_Email) OUTPUT INSERTED.seller_ID VALUES (?, ?)",
            (seller_name, seller_email)
        )
        seller_id = cursor.fetchone()[0]

    # Insert into Marketplace_Listing
    cursor.execute(
        "INSERT INTO Marketplace_Listing (Product_Name, Seller_ID, Listing_Price, Date_Of_Listing, Marketplace_Name, URL) VALUES (?, ?, ?, ?, ?, ?)",
        (product_name, seller_id, listing_price, date_of_listing, marketplace_name, url)
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Listing added successfully"}), 201

@app.route('/get_listings', methods=['GET'])
def get_listings():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT Listing_ID, Product_Name, Marketplace_Name FROM Marketplace_Listing")
    listings = cursor.fetchall()

    listing_data = [
        {"listing_ID": row[0], "product_name": row[1], "marketplace_name": row[-2]}
        for row in listings
    ]

    conn.close()
    return jsonify(listing_data)


@app.route('/delete_listing', methods=['POST'])
def delete_listing():
    data = request.json
    listing_id = data['listing_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete the listing
    cursor.execute("DELETE FROM Marketplace_Listing WHERE Listing_ID = ?", (listing_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Listing deleted successfully"}), 200

@app.route('/get_sellers', methods=['GET'])
def get_sellers():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT Seller_ID, Seller_Name, Seller_Email FROM Seller")
    sellers = cursor.fetchall()

    seller_data = [
        {"seller_ID": row[0], "seller_name": row[1], "seller_email": row[2]}
        for row in sellers
    ]

    conn.close()
    return jsonify(seller_data)

@app.route('/delete_unassociated_sellers', methods=['POST'])
def delete_unassociated_sellers():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM Seller WHERE Seller_ID NOT IN (SELECT DISTINCT seller_ID FROM Marketplace_Listing)
    """)
    deleted_rows = cursor.rowcount

    conn.commit()
    conn.close()

    return jsonify({"message": f"Deleted {deleted_rows} unassociated sellers"}), 200

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file uploaded"})

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No file selected"})

    try:
        df = pd.read_csv(file)
        # Check if the CSV has the required columns
        required_columns = {"Recall_Number", "Date", "Name_of_product", "Description", "Units", "Priority"}
        if not required_columns.issubset(df.columns):
            return jsonify({"success": False, "message": "CSV is missing required columns"})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Remove duplicate entries before inserting
        df = df.drop_duplicates(subset=["Recall_Number"])
        
        # Inserting data into SQL Server, ensuring no duplicates
        for _, row in df.iterrows():
            cursor.execute(
                "MERGE INTO Recall AS target USING (SELECT ? AS Recall_Number, ? AS Date, ? AS Name_of_product, ? AS Description, ? AS Units, ? AS Priority) AS source "
                "ON target.Recall_Number = source.Recall_Number "
                "WHEN NOT MATCHED THEN INSERT (Recall_Number, Date, Name_of_product, Description, Units, Priority) VALUES (source.Recall_Number, source.Date, source.Name_of_produt, source.Description, source.Units, source.Priority);",
                row['Recall_Number'], row['Date'], row['Name_of_product'], row['Description'], row['Units'], row['Priority']
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True})
    
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/update_priorities", methods=["POST"])
def update_priorities():
    data = request.json  # Receive list of priority changes from frontend

    if not data or not isinstance(data, list):
        return jsonify({"status": "error", "message": "Invalid data format"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        unique_entries = {}
        
        for item in data:
            recall_number = item.get("recall_number")
            new_priority = item.get("priority")
            
            if recall_number and new_priority:
                unique_entries[recall_number] = new_priority
        
        for recall_number, new_priority in unique_entries.items():
            cursor.execute("UPDATE Recall SET Priority = ? WHERE Recall_Number = ?", (new_priority, recall_number))

        conn.commit()
        return jsonify({"status": "success", "message": "All priorities updated successfully!"})
    
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    
    finally:
        conn.close()

@app.route('/highpriority')
def priority():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Recall WHERE Priority = 'High';")
    high_recalls = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('highPriority.html', high_recalls=high_recalls)

@app.route('/investigatorhighpriority')
def investigator_priority():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Recall WHERE Priority = 'High';")
    high_recalls = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('investigatorhighpriority.html', high_recalls=high_recalls)

@app.route('/createincident', methods=['POST'])
def create_incident():
    listing_id = request.form['listing_id']
    recall_id = request.form['recall_id']
    description = request.form['description']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM Incident 
        WHERE Listing_ID = ? AND Recall_ID = ?
    """, (listing_id, recall_id))
    existing = cursor.fetchone()
    if existing:
        flash("This incident already exists.", "danger")
    else:
        cursor.execute("""
            INSERT INTO Incident (Listing_ID, Recall_ID, Description)
            VALUES (?, ?, ?)
        """, (listing_id, recall_id, description))
        conn.commit()
        flash("Incident added successfully!", "success")

    cursor.close()
    conn.close()
    return redirect('/importlistings')  

@app.route('/incidents')
def incidents():
    if 'user_id' not in session:
        flash('You must be logged in to view incidents.')
        return redirect('/login')

    employee_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            i.Incident_ID,
            i.Incident_Description,
            r.Recall_ID, r.Name_of_product AS Recall_Product, r.Manufacturers, r.Recall_Status,
            ml.Listing_ID, ml.Product_Name AS Listing_Product, ml.Marketplace_Name, ml.URL,
            a.Is_True_Positive
        FROM Incidents i
        LEFT JOIN Recall r ON i.Recall_ID = r.Recall_ID
        LEFT JOIN Marketplace_Listing ml ON i.Listing_ID = ml.Listing_ID
        LEFT JOIN Annotation a ON a.Incident_ID = i.Incident_ID AND a.Employee_ID = ?
    """
    cursor.execute(query, (employee_id,))
    rows = cursor.fetchall()

    incidents = []
    for row in rows:
        incidents.append({
            'incident_id': row.Incident_ID,
            'description': row.Incident_Description,
            'recall_id': row.Recall_ID,
            'recall_product': row.Recall_Product,
            'manufacturer': row.Manufacturers,
            'recall_status': row.Recall_Status,
            'listing_id': row.Listing_ID,
            'listing_product': row.Listing_Product,
            'marketplace': row.Marketplace_Name,
            'url': row.URL,
            'annotation': row.Is_True_Positive
        })

    conn.close()
    return render_template('incidents.html', incidents=incidents)


@app.route('/annotate', methods=['POST'])
def annotate():
    if 'user_id' not in session:
        flash('You must be logged in to annotate.')
        return redirect('/login')

    incident_id = request.form.get('incident_id')
    label = request.form.get('label')  # 0 or 1 as string
    annotation_text = request.form.get('annotation_text', '')
    employee_id = session['user_id']

    if incident_id is None or label is None:
        flash('Missing incident ID or label.')
        return redirect('/incidents')

    is_true_positive = int(label)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if annotation already exists
    cursor.execute("""
        SELECT Annotation_ID FROM Annotation 
        WHERE Incident_ID = ? AND Employee_ID = ?
    """, (incident_id, employee_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE Annotation
            SET is_true_positive = ?, Annotation_Text = ?, Date_Of_Annotation = ?
            WHERE Annotation_ID = ?
        """, (is_true_positive, annotation_text, datetime.now(), existing.Annotation_ID))
    else:
        cursor.execute("""
            INSERT INTO Annotation (Incident_ID, is_true_positive, Annotation_Text, Date_Of_Annotation, Employee_ID)
            VALUES (?, ?, ?, ?, ?)
        """, (incident_id, is_true_positive, annotation_text, datetime.now(), employee_id))

    conn.commit()
    conn.close()

    flash(f"Annotation for incident #{incident_id} submitted.")
    return redirect('/incidents')



@app.route('/delete_annotation', methods=['POST'])
def delete_annotation():
    if 'user_id' not in session:
        flash('You must be logged in to delete annotations.')
        return redirect('/login')

    incident_id = request.form.get('incident_id')
    employee_id = session['user_id']

    if not incident_id:
        flash('No incident ID provided.')
        return redirect('/incidents')

    conn = get_db_connection()
    cursor = conn.cursor()

    delete_query = """
        DELETE FROM Annotation
        WHERE Incident_ID = ? AND Employee_ID = ?
    """
    cursor.execute(delete_query, (incident_id, employee_id))
    conn.commit()
    conn.close()

    flash(f"Annotation for Incident #{incident_id} deleted.")
    return redirect('/incidents')


@app.route('/contactseller')
def contact_seller():
    return render_template('contact_seller.html')

if __name__ == "__main__":
    app.run(debug=True)
