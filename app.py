import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import functools
from datetime import datetime

app = Flask(__name__)
app.secret_key = "expense-tracker-secret-key-change-in-production"

# Database Configuration (ensure password matches your local PostgreSQL 18 setup)
DB_CONFIG = {
    "dbname": "expense_tracker",
    "user": "postgres",
    "password": "7499",
    "host": "localhost",
    "port": "5432"
}

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Running in the cloud on Render
        return psycopg2.connect(database_url)
    else:
        # Running locally on your laptop
        return psycopg2.connect(**DB_CONFIG)
    
# Authentication Decorator
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

# Shared Navigation & Budget Summary Helper
def get_shared_layout_data(cursor, user_id):
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    cursor.execute("""
        SELECT 
            COALESCE(SUM(b.budget_amount), 0) AS total_budget,
            COALESCE(SUM(e.amount), 0) AS total_spent
        FROM Budget b
        LEFT JOIN Expense e ON b.category_id = e.category_id 
            AND e.user_id = %s
            AND EXTRACT(MONTH FROM e.date) = %s 
            AND EXTRACT(YEAR FROM e.date) = %s
        WHERE b.user_id = %s AND b.budget_month = %s AND b.budget_year = %s;
    """, (user_id, current_month, current_year, user_id, current_month, current_year))
    
    summary = cursor.fetchone()
    total_budget = float(summary[0]) if summary else 0.0
    total_spent = float(summary[1]) if summary else 0.0
    
    return {
        "nav_budget": total_budget,
        "nav_spent": total_spent,
        "nav_remaining": total_budget - total_spent
    }

# --- AUTHENTICATION ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template('register.html')

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO Users (username, email, password_hash) VALUES (%s, %s, %s);",
                (username, email, hashed_password)
            )
            conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Username or email already registered.", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, password_hash FROM Users WHERE username = %s;", 
            (username,)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user[1], password):
            session.clear()
            session['user_id'] = user[0]
            session['username'] = username
            flash("Welcome back!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# --- CORE EXPENSE & DASHBOARD ROUTES ---

@app.route('/')
@login_required
def index():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch User Expenses
    cursor.execute("""
        SELECT e.expense_id, e.amount, e.description, e.date, c.category_name, e.category_id
        FROM Expense e
        LEFT JOIN Category c ON e.category_id = c.category_id
        WHERE e.user_id = %s
        ORDER BY e.date DESC, e.expense_id DESC;
    """, (user_id,))
    expenses = cursor.fetchall()

    # Fetch Categories for dropdown selection
    cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name;")
    categories = cursor.fetchall()

    # Spending by Category for Chart.js
    cursor.execute("""
        SELECT c.category_name, COALESCE(SUM(e.amount), 0)
        FROM Category c
        INNER JOIN Expense e ON c.category_id = e.category_id
        WHERE e.user_id = %s
        GROUP BY c.category_name;
    """, (user_id,))
    chart_data = cursor.fetchall()
    chart_labels = [row[0] for row in chart_data]
    chart_values = [float(row[1]) for row in chart_data]

    layout_data = get_shared_layout_data(cursor, user_id)

    cursor.close()
    conn.close()

    return render_template(
        'index.html',
        expenses=expenses,
        categories=categories,
        chart_labels=chart_labels,
        chart_values=chart_values,
        layout_data=layout_data,
        username=session.get('username')
    )

@app.route('/add_expense', methods=['POST'])
@login_required
def add_expense():
    user_id = session['user_id']
    amount = request.form.get('amount')
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id')
    expense_date = request.form.get('date') or datetime.now().strftime('%Y-%m-%d')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO Expense (amount, description, date, category_id, user_id)
        VALUES (%s, %s, %s, %s, %s);
    """, (amount, description, expense_date, category_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Expense added successfully!", "success")
    return redirect(url_for('index'))

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Expense WHERE expense_id = %s AND user_id = %s;", (expense_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Expense deleted.", "info")
    return redirect(url_for('index'))

# --- BUDGET MANAGEMENT ROUTES (MATCHING budgets.html) ---

@app.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Handle Form Submission for Adding a Budget
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        budget_amount = request.form.get('budget_amount')
        budget_month = request.form.get('budget_month')
        budget_year = request.form.get('budget_year')

        cursor.execute("""
            INSERT INTO Budget (category_id, budget_amount, budget_month, budget_year, user_id)
            VALUES (%s, %s, %s, %s, %s);
        """, (category_id, budget_amount, budget_month, budget_year, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Budget target saved successfully!", "success")
        return redirect(url_for('budgets'))

    # Fetch Active Budgets
    # b[0]=budget_id, b[1]=category_name, b[2]=budget_amount, b[3]=budget_month, b[4]=budget_year, b[5]=spent
    cursor.execute("""
        SELECT 
            b.budget_id,
            c.category_name,
            b.budget_amount,
            b.budget_month,
            b.budget_year,
            COALESCE(SUM(e.amount), 0) AS spent,
            b.category_id
        FROM Budget b
        JOIN Category c ON b.category_id = c.category_id
        LEFT JOIN Expense e ON b.category_id = e.category_id 
            AND e.user_id = %s
            AND EXTRACT(MONTH FROM e.date) = b.budget_month 
            AND EXTRACT(YEAR FROM e.date) = b.budget_year
        WHERE b.user_id = %s
        GROUP BY b.budget_id, c.category_name, b.budget_amount, b.budget_month, b.budget_year, b.category_id
        ORDER BY b.budget_year DESC, b.budget_month DESC;
    """, (user_id, user_id))
    budget_records = cursor.fetchall()

    # Fetch Categories for dropdown
    cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name;")
    categories = cursor.fetchall()

    layout_data = get_shared_layout_data(cursor, user_id)

    cursor.close()
    conn.close()

    return render_template(
        'budgets.html',
        budgets=budget_records,
        categories=categories,
        edit_budget=None,
        layout_data=layout_data,
        username=session.get('username')
    )

@app.route('/budgets/edit/<int:budget_id>')
@login_required
def edit_budget(budget_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch the specific budget for the edit form
    # Returns: (budget_amount, budget_month, budget_year, category_id, budget_id)
    cursor.execute("""
        SELECT budget_amount, budget_month, budget_year, category_id, budget_id
        FROM Budget
        WHERE budget_id = %s AND user_id = %s;
    """, (budget_id, user_id))
    target_budget = cursor.fetchone()

    # Fetch active budgets for the table
    cursor.execute("""
        SELECT 
            b.budget_id,
            c.category_name,
            b.budget_amount,
            b.budget_month,
            b.budget_year,
            COALESCE(SUM(e.amount), 0) AS spent,
            b.category_id
        FROM Budget b
        JOIN Category c ON b.category_id = c.category_id
        LEFT JOIN Expense e ON b.category_id = e.category_id 
            AND e.user_id = %s
            AND EXTRACT(MONTH FROM e.date) = b.budget_month 
            AND EXTRACT(YEAR FROM e.date) = b.budget_year
        WHERE b.user_id = %s
        GROUP BY b.budget_id, c.category_name, b.budget_amount, b.budget_month, b.budget_year, b.category_id
        ORDER BY b.budget_year DESC, b.budget_month DESC;
    """, (user_id, user_id))
    budget_records = cursor.fetchall()

    cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name;")
    categories = cursor.fetchall()

    layout_data = get_shared_layout_data(cursor, user_id)

    cursor.close()
    conn.close()

    return render_template(
        'budgets.html',
        budgets=budget_records,
        categories=categories,
        edit_budget=target_budget,
        layout_data=layout_data,
        username=session.get('username')
    )

@app.route('/budgets/update/<int:budget_id>', methods=['POST'])
@login_required
def update_budget(budget_id):
    user_id = session['user_id']
    category_id = request.form.get('category_id')
    budget_amount = request.form.get('budget_amount')
    budget_month = request.form.get('budget_month')
    budget_year = request.form.get('budget_year')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE Budget 
        SET category_id = %s, budget_amount = %s, budget_month = %s, budget_year = %s
        WHERE budget_id = %s AND user_id = %s;
    """, (category_id, budget_amount, budget_month, budget_year, budget_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Budget updated successfully!", "success")
    return redirect(url_for('budgets'))

@app.route('/budgets/delete/<int:budget_id>')
@login_required
def delete_budget(budget_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Budget WHERE budget_id = %s AND user_id = %s;", (budget_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Budget deleted.", "info")
    return redirect(url_for('budgets'))

if __name__ == '__main__':
    app.run(debug=True)