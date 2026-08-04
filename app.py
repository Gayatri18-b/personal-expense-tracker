import psycopg2
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

DB_CONFIG = {
    "dbname": "Expense_Tracker",
    "user": "postgres",
    "password": "postgres",  
    "host": "localhost",
    "port": "5433" 
}

def get_shared_layout_data(cursor):
    """Helper function to fetch layout details to keep code DRY (Don't Repeat Yourself)."""
    # 1. Fetch total sum of all expenses
    cursor.execute("SELECT SUM(amount) FROM Expense;")
    total_result = cursor.fetchone()[0]
    total_spent = total_result if total_result is not None else 0.00

    # 2. Fetch categories for dropdown
    cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name ASC;")
    all_categories = cursor.fetchall()
    
    # 3. Fetch updated expenses history table with precise budget alerts (Strict Single Rows!)
    cursor.execute('''
        SELECT 
            e.amount, 
            e.description, 
            TO_CHAR(e.date, 'DD-Mon-YYYY'), 
            c.category_name, 
            e.expense_id, 
            e.category_id,
            COALESCE((
                SELECT b.budget_amount
                FROM Budget b
                WHERE b.category_id = e.category_id 
                  AND b.budget_month = EXTRACT(MONTH FROM e.date)
                  AND b.budget_year = EXTRACT(YEAR FROM e.date)
                LIMIT 1
            ), 0) AS budget_limit,
            COALESCE((
                SELECT SUM(sub_e.amount)
                FROM Expense sub_e
                WHERE sub_e.category_id = e.category_id 
                  AND EXTRACT(MONTH FROM sub_e.date) = EXTRACT(MONTH FROM e.date)
                  AND EXTRACT(YEAR FROM sub_e.date) = EXTRACT(YEAR FROM e.date)
            ), 0) AS total_spent_that_month
        FROM Expense e
        LEFT JOIN Category c ON e.category_id = c.category_id
        WHERE e.amount IS NOT NULL
        ORDER BY e.date DESC, e.expense_id DESC;
    ''')
    history = cursor.fetchall()
    
    cursor.execute('''
        SELECT COALESCE(c.category_name, 'Uncategorized'), SUM(e.amount)
        FROM Expense e
        LEFT JOIN Category c ON e.category_id=c.category_id
        GROUP BY c.category_name
    ''')
    chart_data = cursor.fetchall()
    
    return total_spent, all_categories, history, chart_data
     
    
@app.route('/', methods=['GET', 'POST'])
def home():
    # 🌟 Level 1: All these start exactly 4 spaces in
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if request.method == 'POST':
        # 🌟 Level 2: These start exactly 8 spaces in
        expense_amount = request.form.get('amount')
        expense_desc = request.form.get('description')
        selected_category=request.form.get('category')
        
        try:
            cursor.execute('''
                INSERT INTO Expense (user_id, category_id, amount, description, payment_method)
                VALUES (NULL, %s, %s, %s, 'Cash');
            ''', (selected_category,expense_amount, expense_desc))
            conn.commit()
            print(f"\n✅ SUCCESS! Saved to PostgreSQL: {expense_amount} for {expense_desc}\n")
        except Exception as e:
            conn.rollback()
            print(f"\n❌ Database Insert Failed: {e}\n")
        finally:
            cursor.close()
            conn.close()
        return redirect('/')
    
    # B. READ FLOW (Normal Page Load)
    total_spent, all_categories, history, chart_data = get_shared_layout_data(cursor)
    cursor.close()
    conn.close()
    
    # Separate the names and the amounts into clean lists for JavaScript to read
    chart_labels = [row[0] for row in chart_data]
    chart_values = [float(row[1]) for row in chart_data]

    return render_template('index.html', expenses=history, categories=all_categories, 
                           total=total_spent, edit_expense=None,
                           chart_labels=chart_labels, chart_values=chart_values)
    
@app.route('/edit/<int:expense_id>')
def edit_expense(expense_id):
    """Triggered when user clicks 'Edit'. Reloads layout with record loaded into input forms."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # Fetch the target expense item we want to modify
        cursor.execute('''
            SELECT amount, 
            description, 
            TO_CHAR(e.date, 'DD-Mon-YYYY'),
            NULL AS category_name, 
            e.expense_id, 
            e.category_id,
            COALESCE((
                SELECT budget_amount 
                FROM Budget 
                WHERE category_id = e.category_id 
                  AND budget_month = EXTRACT(MONTH FROM e.date)
                  AND budget_year = EXTRACT(YEAR FROM e.date)
                LIMIT 1
                ), 0) AS budget_limit,
                COALESCE((
                    SELECT SUM(amount) 
                    FROM Expense 
                    WHERE category_id = e.category_id 
                      AND EXTRACT(MONTH FROM date) = EXTRACT(MONTH FROM e.date)
                      AND EXTRACT(YEAR FROM date) = EXTRACT(YEAR FROM e.date)
                ), 0) AS total_spent_that_month
            FROM Expense WHERE expense_id = %s;
        ''', (expense_id,))
        target_item = cursor.fetchone()
        
        # Load all ambient dashboard records around it
        total_spent, all_categories, history,chart_data = get_shared_layout_data(cursor)
    except Exception as e:
        print(f"❌ Error loading edit state: {e}")
        return redirect('/')
    finally:
        cursor.close()
        conn.close()

    chart_labels = [row[0] for row in chart_data]
    chart_values = [float(row[1]) for row in chart_data]

    return render_template('index.html', expenses=history, categories=all_categories, 
                           total=total_spent, edit_expense=target_item,
                           chart_labels=chart_labels, chart_values=chart_values)
    
@app.route('/update/<int:expense_id>', methods=['POST'])
def update_expense(expense_id):
    """Triggered when the form is submitted while operating in Edit Mode."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    updated_amount = request.form.get('amount')
    updated_desc = request.form.get('description')
    updated_cat = request.form.get('category')
    
    try:
        # Run standard SQL UPDATE query targeted to this ID
        cursor.execute('''
            UPDATE Expense 
            SET amount = %s, description = %s, category_id = %s
            WHERE expense_id = %s;
        ''', (updated_amount, updated_desc, updated_cat, expense_id))
        conn.commit()
        print(f"\n✏️ SUCCESS! Updated item ID: {expense_id} in PostgreSQL\n")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Database Update Failed: {e}\n")
    finally:
        cursor.close()
        conn.close()
        
    return redirect('/')

    
@app.route('/delete/<int:expense_id>')
def delete_expense(expense_id):
    conn=psycopg2.connect(**DB_CONFIG)
    cursor=conn.cursor()

    try:
        # run the targeted delete cmd for spcific row id
        cursor.execute("DELETE FROM Expense WHERE expense_id=%s;" ,(expense_id,))
        conn.commit()
        print(f"\n SUCCESS! Deleted expense ID:{expense_id} from postgreSQL\n")
    except Exception as e:
        conn.rollback()
        print(f"\n FAILED deletion:{e}\n")
    finally:
        cursor.close()
        conn.close()

    #redirect back to the main database page 
    return redirect('/')

@app.route('/categories', methods=['GET', 'POST'])
def manage_categories():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 🅰️ WRITE FLOW: If the user submits a new category name
    if request.method == 'POST':
        new_cat_name = request.form.get('category_name')
        
        try:
            cursor.execute('''
                INSERT INTO Category (category_name) 
                VALUES (%s);
            ''', (new_cat_name,))
            conn.commit()
            print(f"\n✅ SUCCESS! Added new category: {new_cat_name}\n")
        except Exception as e:
            conn.rollback()
            print(f"\n❌ Failed to add category: {e}\n")
        finally:
            cursor.close()
            conn.close()
        return redirect('/categories')

    # 🅱️ READ FLOW: Fetch all categories to show on the page
    cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name ASC;")
    all_categories = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('categories.html', categories=all_categories)

@app.route('/categories/delete/<int:category_id>')
def delete_category(category_id):
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM Category WHERE category_id = %s;", (category_id,))
        conn.commit()
        print(f"\n🗑️ SUCCESS! Deleted category ID: {category_id}\n")
    except Exception as e:
        conn.rollback()
        # This catches if an expense is still using this category (Foreign Key Constraint)
        print(f"\n❌ Cannot delete category. It might be linked to existing expenses: {e}\n")
    finally:
        cursor.close()
        conn.close()

    return redirect('/categories')


@app.route('/budgets', methods=['GET','POST'])
def manage_budgets():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    if request.method =='POST':
        cat_id = request.form.get('category_id')
        amount =request.form.get('budget_amount')
        month =request.form.get('budget_month')
        year =request.form.get('budget_year')
            
        try:
            cursor.execute('''
                INSERT INTO Budget(category_id, budget_amount, budget_month, budget_year)
                values(%s, %s, %s, %s);
            ''', (cat_id, amount, month, year))    
            conn.commit()
            print(f"\n✅ SUCCESS! Added budget limit of ₹{amount} for category ID: {cat_id}")
        except Exception as e:
            conn.rollback()
            print(f"\n❌ Failed to add budget: {e}\n")
        finally:
            cursor.close()
            conn.close()
        return redirect('/budgets')
    
    cursor.execute('''
        SELECT b.budget_id, 
            c.category_name, 
            b.budget_amount,
            b.budget_month,
            b.budget_year,
            COALESCE(SUM(e.amount),0) AS total_spent
        FROM Budget b
        LEFT JOIN Category c ON b.category_id=c.category_id
        LEFT JOIN Expense e ON b.category_id = e.category_id
            AND EXTRACT (MONTH FROM e.date) =b.budget_month
            AND EXTRACT (YEAR FROM e.date) =b.budget_year
        GROUP BY b.budget_id, c.category_name, b.budget_amount, b.budget_month, b.budget_year
        ORDER BY b.budget_year DESC, b.budget_month DESC ;
    ''')
    all_budgets = cursor.fetchall()
    
    cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name ASC;")
    all_categories=cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('budgets.html', budgets=all_budgets, categories=all_categories,edit_budget=None)
@app.route('/budgets/edit/<int:budget_id>')
def edit_budget(budget_id):
    """Triggered when user clicks 'Edit' on a budget row. Loads data back into the ambient view."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # Fetch the targeting budget item
        cursor.execute('''
            SELECT budget_amount, budget_month, budget_year, category_id, budget_id 
            FROM Budget WHERE budget_id = %s;
        ''', (budget_id,))
        target_budget = cursor.fetchone()
        
        # Load the surrounding dashboard elements so the page renders completely
        cursor.execute('''
            SELECT b.budget_id, 
                c.category_name, 
                b.budget_amount,
                b.budget_month,
                b.budget_year,
                COALESCE(SUM(e.amount),0) AS total_spent,
                b.category_id
            FROM Budget b
            LEFT JOIN Category c ON b.category_id=c.category_id
            LEFT JOIN Expense e ON b.category_id = e.category_id
                AND EXTRACT (MONTH FROM e.date) = b.budget_month
                AND EXTRACT (YEAR FROM e.date) = b.budget_year
            GROUP BY b.budget_id, c.category_name, b.budget_amount, b.budget_month, b.budget_year, b.category_id
            ORDER BY b.budget_year DESC, b.budget_month DESC ;
        ''')
        all_budgets = cursor.fetchall()
        
        cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name ASC;")
        all_categories = cursor.fetchall()
        
    except Exception as e:
        print(f"❌ Error loading budget edit state: {e}")
        return redirect('/budgets')
    finally:
        cursor.close()
        conn.close()
        
    return render_template('budgets.html', budgets=all_budgets, categories=all_categories, edit_budget=target_budget)
@app.route('/budgets/update/<int:budget_id>', methods=['POST'])
def update_budget(budget_id):
    """Processes the submitted form to update an existing budget target."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    updated_cat = request.form.get('category_id')
    updated_amount = request.form.get('budget_amount')
    updated_month = request.form.get('budget_month')
    updated_year = request.form.get('budget_year')
    
    try:
        cursor.execute('''
            UPDATE Budget 
            SET category_id = %s, budget_amount = %s, budget_month = %s, budget_year = %s
            WHERE budget_id = %s;
        ''', (updated_cat, updated_amount, updated_month, updated_year, budget_id))
        conn.commit()
        print(f"\n✏️ SUCCESS! Updated Budget ID: {budget_id}\n")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Database Budget Update Failed: {e}\n")
    finally:
        cursor.close()
        conn.close()
        
    return redirect('/budgets')

    
def get_shared_layout_data(cursor):
    """Helper function to fetch layout details to keep code DRY (Don't Repeat Yourself)."""
    # 1. Fetch total sum of all expenses
    cursor.execute("SELECT SUM(amount) FROM Expense;")
    total_result = cursor.fetchone()[0]
    total_spent = total_result if total_result is not None else 0.00

    # 2. Fetch categories for dropdown
    cursor.execute("SELECT category_id, category_name FROM Category ORDER BY category_name ASC;")
    all_categories = cursor.fetchall()
    
    # 3. Fetch updated expenses history table with precise budget alerts (Strict Single Rows!)
    cursor.execute('''
        SELECT 
            e.amount, 
            e.description, 
            TO_CHAR(e.date, 'DD-Mon-YYYY'), 
            c.category_name, 
            e.expense_id, 
            e.category_id,
            COALESCE((
                SELECT b.budget_amount
                FROM Budget b
                WHERE b.category_id = e.category_id 
                  AND b.budget_month = EXTRACT(MONTH FROM e.date)
                  AND b.budget_year = EXTRACT(YEAR FROM e.date)
                LIMIT 1
            ), 0) AS budget_limit,
            COALESCE((
                SELECT SUM(sub_e.amount)
                FROM Expense sub_e
                WHERE sub_e.category_id = e.category_id 
                  AND EXTRACT(MONTH FROM sub_e.date) = EXTRACT(MONTH FROM e.date)
                  AND EXTRACT(YEAR FROM sub_e.date) = EXTRACT(YEAR FROM e.date)
            ), 0) AS total_spent_that_month
        FROM Expense e
        LEFT JOIN Category c ON e.category_id = c.category_id
        WHERE e.amount IS NOT NULL
        ORDER BY e.date DESC, e.expense_id DESC;
    ''')
    history = cursor.fetchall()
    
    cursor.execute('''
        SELECT COALESCE(c.category_name, 'Uncategorized'), SUM(e.amount)
        FROM Expense e
        LEFT JOIN Category c ON e.category_id=c.category_id
        GROUP BY c.category_name
    ''')
    chart_data = cursor.fetchall()
    
    return total_spent, all_categories, history, chart_data

@app.route('/budgets/delete/<int:budget_id>')
def delete_budget(budget_id):
    """Removes a budget entry by its specific ID."""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM Budget WHERE budget_id = %s;", (budget_id,))
        conn.commit()
        print(f"\n🗑️ SUCCESS! Deleted budget ID: {budget_id}\n")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Failed to delete budget: {e}\n")
    finally:
        cursor.close()
        conn.close()

    return redirect('/budgets')    
if __name__ == '__main__':
    app.run(debug=True)