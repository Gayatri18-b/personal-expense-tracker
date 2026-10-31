# Personal Expense Tracker

A full-stack personal finance web application built with **Python (Flask)** and **PostgreSQL**. The platform enables individual users to log daily expenditures, categorize transactions, set dynamic monthly budget limits, track budget utilization with visual progress bars, and analyze spending habits through interactive charts.

---

## Key Features

- **User Authentication & Session Management**: Secure user registration and login built using session cookies and salted SHA-256 password hashing via `werkzeug.security`.
- **User Data Isolation**: Relational database architecture ensures all transactions, categories, and monthly targets remain completely isolated to the logged-in user.
- **Dynamic Dashboard**: Displays real-time aggregated metrics including Total Budget, Total Spent, and Remaining Balance for the active cycle.
- **Interactive Data Visualization**: Integrated **Chart.js** doughnut charts providing category-wise spending breakdowns calculated server-side.
- **Budget Tracking & Visual Progress**: Allows users to set category limits per month/year, automatically computing percentage utilization and flagging over-budget states.
- **Full CRUD Capabilities**: Add and delete expense records; create, update, and remove monthly budget limits.

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python, Flask, Psycopg2, Werkzeug |
| **Database** | PostgreSQL 18 |
| **Frontend** | HTML5, CSS3 (Modern Flexbox & CSS Grid), JavaScript |
| **Visualization** | Chart.js |
| **Version Control** | Git, GitHub |

---

## Database Architecture

The schema uses a normalized relational model configured in PostgreSQL with foreign-key constraints and cascading actions:

```text
       +------------------+
       |      Users       |
       +------------------+
       | user_id (PK)     |<----------+
       | username (UQ)    |           |
       | email (UQ)       |           |
       | password_hash    |           |
       | created_at       |           |
       +------------------+           |
                |                     |
                | 1:N                 | 1:N
                v                     |
       +------------------+           |
       |     Expense      |           |
       +------------------+           |
       | expense_id (PK)  |           |
       | amount           |           |
       | description      |           |
       | date             |           |
       | category_id (FK) |           |
       | user_id (FK)-----+           |
       +------------------+           |
                |                     |
                | N:1                 |
                v                     |
       +------------------+           |
       |     Category     |           |
       +------------------+           |
       | category_id (PK) |           |
       | category_name(UQ)|           |
       +------------------+           |
                ^                     |
                | 1:N                 |
                |                     |
       +------------------+           |
       |      Budget      |           |
       +------------------+           |
       | budget_id (PK)   |           |
       | category_id (FK) |           |
       | budget_amount    |           |
       | budget_month     |           |
       | budget_year      |           |
       | user_id (FK)-----+-----------+
       +------------------+
```

---

## Project Structure

```text
Expense_Tracker/
├── static/
│   └── style.css            # Custom CSS styling and responsive layouts
├── templates/
│   ├── index.html           # Main dashboard, KPI cards, expense table, and chart
│   ├── budgets.html         # Monthly budget management and progress bars
│   ├── login.html           # Authentication login portal
│   └── register.html        # New user registration portal
├── app.py                   # Flask routing, auth decorators, and PostgreSQL interactions
├── requirements.txt         # Pinned Python package dependencies
├── .gitignore               # Ignored environments, cache files, and credentials
└── README.md                # Project documentation
```