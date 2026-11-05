import psycopg2

# AWS RDS Configuration
HOST = "expense-tracker-db.cmj8w0eo2s5g.us-east-1.rds.amazonaws.com"
PORT = 5432
DATABASE = "postgres"
USER = "postgres"
PASSWORD = "gayu7499"  # Replace with the password you created for RDS

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    category_id INT REFERENCES categories(id) ON DELETE SET NULL,
    amount NUMERIC(10, 2) NOT NULL,
    description TEXT,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS budgets (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    category_id INT REFERENCES categories(id) ON DELETE CASCADE,
    amount NUMERIC(10, 2) NOT NULL,
    month VARCHAR(7) NOT NULL
);
"""

try:
    print("Connecting to AWS RDS PostgreSQL...")
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=DATABASE,
        user=USER,
        password=PASSWORD,
        sslmode="require"
    )
    cur = conn.cursor()
    cur.execute(CREATE_TABLES_SQL)
    conn.commit()
    print("SUCCESS: Connected to AWS RDS and all tables created successfully!")
    cur.close()
    conn.close()
except Exception as e:
    print("Connection error:", e)