# Northstar Commerce Desk

A new Streamlit sales-management app backed by MySQL. It provides an authenticated
workspace, live sales CRUD, validated CSV import/export, interactive reporting,
and product, customer, payment, and regional insights.

## Run locally

1. Install MySQL Server and start the MySQL service.
2. In a MySQL client, run [`schema.sql`](schema.sql). This creates the
   `northstar_retail` database and its sales table.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and enter
   the MySQL host, username, and password. Keep the local secrets file private;
   it is excluded by `.gitignore`.
4. From this folder, create and activate a virtual environment, then install
   dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   streamlit run app.py
   ```

5. Open the local Streamlit URL shown in the terminal and sign in.

## Admin sign-in

- Admin ID: `munna123`
- Password: the value supplied for this application.

The app verifies the default password using a salted PBKDF2 hash. For a deployed
app, replace the demo credential with `APP_ADMIN_USERNAME`, `APP_ADMIN_SALT`,
and `APP_ADMIN_PASSWORD_HASH` environment variables, or configure the optional
`[admin]` values in Streamlit secrets.

## Data and validation

- Sales are stored in MySQL. Revenue is calculated by MySQL from units sold
  multiplied by unit price, so it cannot drift from the underlying values.
- Create, edit, and delete operations use parameterized SQL.
- CSV import supports the included template and the supplied sample's
  `Month`, `Item_Name`, `Brand`, `Category`, `Units_Sold`, `Price_Rs`,
  `Payment_Mode`, `Customer_Type`, and `Region` columns.
- When a CSV only supplies `Month`, the selected year is used and the date is
  stored as the first day of that month. If a `Total_Revenue` column is
  supplied, its value is checked against units times price.
- Every import is validated before it is written. One invalid row stops the
  whole batch; a database error rolls the transaction back.
- MySQL host and user can be configured in Streamlit secrets or with
  `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, and
  `MYSQL_DATABASE` environment variables.

This project uses the assignment brief's live MySQL, CRUD, data-validation,
Streamlit UI, and business-insight requirements, with a new brand and
implementation rather than copying the sample app.
