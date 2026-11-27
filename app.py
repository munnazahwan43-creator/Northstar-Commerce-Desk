from __future__ import annotations

import hashlib
import hmac
import io
import os
import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Northstar | Commerce Desk",
    page_icon="N",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "NORTHSTAR"
PAGE_NAMES = ["Overview", "Sales register", "Insights", "Import & export"]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
REQUIRED_FIELDS = {
    "sale_date": "Sale date",
    "item_name": "Product",
    "category": "Category",
    "units_sold": "Units sold",
    "unit_price": "Unit price",
}
DEFAULT_ADMIN_SALT = "2d1f3e37d8f3808018eac222087c696a"
DEFAULT_ADMIN_HASH = "088fa140eb12ae98b7261645f6276dbb51249359fe35b34f28943b70b570f1bc"


class AppError(RuntimeError):
    """A user-actionable application or database error."""


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
    :root { --ink:#17243a; --muted:#6d7a8c; --line:#e6ebf2; --teal:#087f8c; --paper:#f5f7fa; }
    html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    [data-testid="stSidebar"] { background:#101c2d; border-right:1px solid #263449; }
    [data-testid="stSidebar"] * { color:#e7edf5; }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color:#9eafc3; }
    .block-container { max-width:1420px; padding-top:2rem; padding-bottom:3rem; }
    .brand { display:flex; gap:12px; align-items:center; padding:8px 4px 24px; }
    .brand-mark { width:42px; height:42px; border-radius:14px; display:grid; place-items:center;
        color:#fff; font-weight:800; background:linear-gradient(145deg,#16a6a0,#087f8c); }
    .brand-name { font-size:1.04rem; letter-spacing:.13em; color:#fff; font-weight:800; }
    .brand-caption { color:#91a1b5; font-size:.72rem; margin-top:2px; }
    .eyebrow { color:var(--teal); font-weight:800; font-size:.7rem; letter-spacing:.16em; text-transform:uppercase; }
    .page-title { color:#17243a; font-size:2rem; letter-spacing:-.04em; font-weight:800; margin:.1rem 0 .2rem; }
    .page-subtitle { color:var(--muted); margin:0 0 1.5rem; }
    .metric { padding:18px 20px; border:1px solid var(--line); border-radius:16px; background:#fff;
        box-shadow:0 5px 18px rgba(27,45,71,.035); min-height:112px; }
    .metric-label { color:var(--muted); font-size:.76rem; font-weight:700; letter-spacing:.04em; }
    .metric-value { color:var(--ink); font-size:1.7rem; font-weight:800; margin-top:6px; }
    .metric-note { color:#8793a3; font-size:.75rem; margin-top:3px; }
    .panel-title { color:var(--ink); font-weight:800; font-size:1rem; margin:4px 0 12px; }
    div[data-testid="stForm"] { background:#fff; border:1px solid var(--line); border-radius:14px; padding:18px; }
    div[data-testid="stForm"] label {
    color: #17243a !important;
    font-weight: 700 !important;}
    .stButton button, .stFormSubmitButton button, .stDownloadButton button { border-radius:10px; font-weight:700; }
    .stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
        background:#087f8c; border-color:#087f8c; }
    [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:12px; overflow:hidden; }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stCaptionContainer"] p { color:#526174; }
    [data-testid="stWidgetLabel"] p,
    [data-testid="stTextInput"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stDateInput"] label { color:#263445 !important; }
    div[data-testid="stMetricLabel"] { color:#526174 !important; }
    div[data-testid="stMetricValue"] { color:#17243a !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret(section: str, key: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(section, {}).get(key, default)
    except (AttributeError, FileNotFoundError, KeyError):
        return default


def _secret_section(section: str) -> dict[str, Any]:
    try:
        return dict(st.secrets.get(section, {}))
    except (AttributeError, FileNotFoundError, KeyError):
        return {}


def _admin_credentials() -> tuple[str, str, str]:
    salt = os.getenv("APP_ADMIN_SALT") or _secret("admin", "password_salt") or DEFAULT_ADMIN_SALT
    expected_hash = (
        os.getenv("APP_ADMIN_PASSWORD_HASH")
        or _secret("admin", "password_hash")
        or DEFAULT_ADMIN_HASH
    )
    username = os.getenv("APP_ADMIN_USERNAME") or _secret("admin", "username") or "munna123"
    return str(username), str(salt), str(expected_hash)


def _password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 310_000
    ).hex()


def _login() -> bool:
    if st.session_state.get("authenticated"):
        return True

    left, center, right = st.columns([1, 1.2, 1])
    with center:
        st.markdown('<div class="eyebrow">Northstar Commerce Desk</div>', unsafe_allow_html=True)
        st.title("Sign in to your workspace")
        st.caption("Secure access to sales records, reporting, and data tools.")
        with st.form("login_form"):
            username = st.text_input("Admin ID", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if submitted:
            expected_user, salt, expected_hash = _admin_credentials()
            try:
                candidate_hash = _password_hash(password, salt)
            except ValueError:
                st.error("Admin password configuration has an invalid salt.")
                return False
            if hmac.compare_digest(username, expected_user) and hmac.compare_digest(
                candidate_hash, expected_hash
            ):
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("The admin ID or password is incorrect.")
    return False


def _mysql_config() -> dict[str, Any]:
    config = _secret_section("mysql")
    for key, env_name in {
        "host": "MYSQL_HOST",
        "port": "MYSQL_PORT",
        "user": "MYSQL_USER",
        "password": "MYSQL_PASSWORD",
        "database": "MYSQL_DATABASE",
    }.items():
        if os.getenv(env_name) is not None:
            config[key] = os.getenv(env_name)
    if not config.get("database"):
        config["database"] = "northstar_retail"
    if not config.get("host") or not config.get("user"):
        raise AppError(
            "MySQL is not configured. Add host, user, password, and database to "
            ".streamlit/secrets.toml, then run schema.sql in MySQL."
        )
    try:
        config["port"] = int(config.get("port", 3306))
    except (TypeError, ValueError) as exc:
        raise AppError("MySQL port must be a valid number.") from exc
    config.setdefault("connection_timeout", 5)
    config.setdefault("charset", "utf8mb4")
    config.setdefault("use_unicode", True)
    return config


@contextmanager
def _connection() -> Iterator[Any]:
    config = _mysql_config()
    try:
        import mysql.connector
    except ImportError as exc:
        raise AppError(
            "The MySQL connector is missing. Install the packages in requirements.txt."
        ) from exc

    connection = None
    try:
        connection = mysql.connector.connect(**config)
        yield connection
    except mysql.connector.Error as exc:
        if connection is not None:
            connection.rollback()
        message = getattr(exc, "msg", str(exc))
        raise AppError(f"MySQL operation failed: {message}") from exc
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


def _fetch_sales() -> pd.DataFrame:
    query = """
        SELECT sale_id, sale_date, item_name, brand, category, units_sold,
               unit_price, total_revenue, payment_mode, customer_type, region
        FROM sales
        ORDER BY sale_date DESC, sale_id DESC
    """
    with _connection() as connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
        finally:
            cursor.close()
    columns = [
        "sale_id", "sale_date", "item_name", "brand", "category", "units_sold",
        "unit_price", "total_revenue", "payment_mode", "customer_type", "region",
    ]
    frame = pd.DataFrame(rows, columns=columns)
    if not frame.empty:
        frame["sale_date"] = pd.to_datetime(frame["sale_date"])
        for column in ["unit_price", "total_revenue"]:
            frame[column] = pd.to_numeric(frame[column])
    return frame


def _clean_text(value: Any, label: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required.")
    if len(text) > max_length:
        raise ValueError(f"{label} must be {max_length} characters or fewer.")
    return text


def _make_record(
    sale_date: Any,
    item_name: Any,
    brand: Any,
    category: Any,
    units_sold: Any,
    unit_price: Any,
    payment_mode: Any,
    customer_type: Any,
    region: Any,
) -> tuple[Any, ...]:
    try:
        parsed_date = pd.to_datetime(sale_date, errors="raise").date()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Sale date must be a valid date.") from exc
    if parsed_date > date.today():
        raise ValueError("Sale date cannot be in the future.")

    try:
        units_decimal = Decimal(str(units_sold))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Units sold must be a positive whole number.") from exc
    if not units_decimal.is_finite() or units_decimal <= 0 or units_decimal % 1:
        raise ValueError("Units sold must be a positive whole number.")
    if units_decimal > 2_147_483_647:
        raise ValueError("Units sold is too large.")

    try:
        price = Decimal(str(unit_price))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Unit price must be a positive amount.") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError("Unit price must be positive and have no more than 2 decimals.")
    if price >= Decimal("10000000000"):
        raise ValueError("Unit price is too large.")
    if price != price.quantize(Decimal("0.01")):
        raise ValueError("Unit price must have no more than 2 decimals.")

    return (
        parsed_date,
        _clean_text(item_name, "Product", 100),
        _clean_text(brand, "Brand", 100) if str(brand or "").strip() else "Unbranded",
        _clean_text(category, "Category", 60),
        int(units_decimal),
        price,
        _clean_text(payment_mode, "Payment mode", 40)
        if str(payment_mode or "").strip() else "Not specified",
        _clean_text(customer_type, "Customer type", 40)
        if str(customer_type or "").strip() else "Not specified",
        _clean_text(region, "Region", 80) if str(region or "").strip() else "Not specified",
    )


def _insert_sale(record: tuple[Any, ...]) -> None:
    with _connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO sales
                    (sale_date, item_name, brand, category, units_sold, unit_price,
                     payment_mode, customer_type, region)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                record,
            )
            connection.commit()
        finally:
            cursor.close()


def _update_sale(sale_id: int, record: tuple[Any, ...]) -> None:
    with _connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                UPDATE sales SET sale_date=%s, item_name=%s, brand=%s, category=%s,
                    units_sold=%s, unit_price=%s, payment_mode=%s, customer_type=%s,
                    region=%s
                WHERE sale_id=%s
                """,
                record + (sale_id,),
            )
            connection.commit()
        finally:
            cursor.close()


def _delete_sale(sale_id: int) -> None:
    with _connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute("DELETE FROM sales WHERE sale_id=%s", (sale_id,))
            if cursor.rowcount == 0:
                raise AppError("That sales record no longer exists. Refresh and try again.")
            connection.commit()
        finally:
            cursor.close()


def _money(value: Any) -> str:
    amount = float(value or 0)
    return f"₹{amount:,.2f}"


def _style_chart(chart: Any) -> Any:
    """Apply readable, consistent styling without changing the chart palette."""
    chart.update_layout(
        font=dict(family="Arial, sans-serif", size=13, color="#263445"),
        legend=dict(font=dict(size=12, color="#263445")),
        xaxis=dict(
            tickfont=dict(size=12, color="#263445"),
            title_font=dict(size=13, color="#263445"),
            gridcolor="#e8edf3",
            zerolinecolor="#d9e1ea",
        ),
        yaxis=dict(
            tickfont=dict(size=12, color="#263445"),
            title_font=dict(size=13, color="#263445"),
            gridcolor="#e8edf3",
            zerolinecolor="#d9e1ea",
        ),
        hoverlabel=dict(
            bgcolor="#17243a",
            bordercolor="#17243a",
            font=dict(color="#ffffff", size=13),
        ),
    )
    chart.update_traces(textfont=dict(color="#263445", size=12))
    return chart


def _metric(label: str, value: str, note: str) -> None:
    st.markdown(
        f'<div class="metric"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div><div class="metric-note">{note}</div></div>',
        unsafe_allow_html=True,
    )


def _page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def _apply_filters(frame: pd.DataFrame) -> pd.DataFrame:
    filtered = frame.copy()
    with st.sidebar.expander("Report filters", expanded=False):
        for column, label in [
            ("category", "Category"),
            ("brand", "Brand"),
            ("region", "Region"),
        ]:
            options = sorted(filtered[column].dropna().astype(str).unique())
            selected = st.multiselect(label, options, key=f"filter_{column}")
            if selected:
                filtered = filtered[filtered[column].astype(str).isin(selected)]
        if not filtered.empty:
            min_date = filtered["sale_date"].min().date()
            max_date = filtered["sale_date"].max().date()
            if min_date < max_date:
                date_range = st.date_input(
                    "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
                )
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start, end = date_range
                    filtered = filtered[
                        filtered["sale_date"].dt.date.between(start, end)
                    ]
    return filtered


def _overview(frame: pd.DataFrame) -> None:
    _page_header("Your business at a glance", "Overview", "Live sales data from your MySQL database.")
    if frame.empty:
        st.info("There are no sales records yet. Add your first sale or import a CSV to get started.")
        return

    revenue = frame["total_revenue"].sum()
    units = int(frame["units_sold"].sum())
    transactions = len(frame)
    average = revenue / transactions if transactions else 0
    cols = st.columns(4)
    with cols[0]:
        _metric("TOTAL REVENUE", _money(revenue), "For the selected filters")
    with cols[1]:
        _metric("TRANSACTIONS", f"{transactions:,}", "Sales in this selection")
    with cols[2]:
        _metric("UNITS SOLD", f"{units:,}", "Combined quantity")
    with cols[3]:
        _metric("AVG. SALE VALUE", _money(average), "Revenue per transaction")

    st.write("")
    left, right = st.columns([1.5, 1])
    with left:
        st.markdown('<div class="panel-title">Revenue by month</div>', unsafe_allow_html=True)
        monthly = (
            frame.assign(month=frame["sale_date"].dt.to_period("M").dt.to_timestamp())
            .groupby("month", as_index=False)["total_revenue"]
            .sum()
        )
        chart = px.area(
            monthly, x="month", y="total_revenue", markers=True,
            color_discrete_sequence=["#087f8c"],
        )
        chart.update_layout(
            height=330, margin=dict(l=12, r=12, t=18, b=12),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title=None, yaxis_title="Revenue (₹)",
        )
        st.plotly_chart(_style_chart(chart), use_container_width=True)
    with right:
        st.markdown('<div class="panel-title">Revenue by category</div>', unsafe_allow_html=True)
        category = frame.groupby("category", as_index=False)["total_revenue"].sum()
        chart = px.pie(
            category, names="category", values="total_revenue", hole=0.62,
            color_discrete_sequence=["#087f8c", "#23a59e", "#8bc9c2", "#f0a35e", "#637a93"],
        )
        chart.update_layout(
            height=330, margin=dict(l=12, r=12, t=18, b=12),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            legend_title=None,
        )
        st.plotly_chart(_style_chart(chart), use_container_width=True)

    best = frame.groupby("item_name")["total_revenue"].sum().nlargest(5).reset_index()
    recent = frame.sort_values(["sale_date", "sale_id"], ascending=False).head(8)
    left, right = st.columns([1, 1.5])
    with left:
        st.markdown('<div class="panel-title">Top products</div>', unsafe_allow_html=True)
        chart = px.bar(
            best.sort_values("total_revenue"), x="total_revenue", y="item_name",
            orientation="h", color_discrete_sequence=["#23a59e"],
        )
        chart.update_layout(
            height=290, margin=dict(l=12, r=12, t=10, b=12),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Revenue (₹)", yaxis_title=None,
            
        )
        st.plotly_chart(_style_chart(chart), use_container_width=True)
    with right:
        st.markdown('<div class="panel-title">Latest transactions</div>', unsafe_allow_html=True)
        st.dataframe(
            recent[["sale_id", "sale_date", "item_name", "units_sold", "total_revenue", "region"]]
            .rename(columns={
                "sale_id": "Sale ID", "sale_date": "Date", "item_name": "Product",
                "units_sold": "Units", "total_revenue": "Revenue", "region": "Region",
            }),
            hide_index=True, use_container_width=True,
        )


def _record_form(prefix: str, record: dict[str, Any] | None = None) -> tuple[Any, ...] | None:
    record = record or {}

    def value(key: str, default: Any = "") -> Any:
        result = record.get(key, default)
        if pd.isna(result):
            return default
        return result

    old_date = value("sale_date", date.today())
    if isinstance(old_date, pd.Timestamp):
        old_date = old_date.date()
    if isinstance(old_date, datetime):
        old_date = old_date.date()
    if not isinstance(old_date, date):
        old_date = pd.to_datetime(old_date).date()
    old_price = value("unit_price", 0.01)

    with st.form(f"{prefix}_form"):
        first, second = st.columns(2)
        with first:
            sale_date = st.date_input("Sale date", value=old_date, key=f"{prefix}_date")
            item_name = st.text_input("Product name *", value=str(value("item_name")), key=f"{prefix}_item")
            brand = st.text_input("Brand", value=str(value("brand")), key=f"{prefix}_brand")
            category = st.text_input("Category *", value=str(value("category")), key=f"{prefix}_category")
            units = st.number_input(
                "Units sold *", min_value=1, max_value=2_147_483_647,
                value=max(1, int(value("units_sold", 1))), step=1, key=f"{prefix}_units",
            )
        with second:
            unit_price = st.number_input(
                "Unit price (₹) *", min_value=0.01, max_value=9_999_999_999.99,
                value=max(0.01, float(old_price)), step=1.0, format="%.2f", key=f"{prefix}_price",
            )
            payment_mode = st.text_input(
                "Payment mode", value=str(value("payment_mode")), key=f"{prefix}_payment"
            )
            customer_type = st.text_input(
                "Customer type", value=str(value("customer_type")), key=f"{prefix}_customer"
            )
            region = st.text_input("Region", value=str(value("region")), key=f"{prefix}_region")
        submitted = st.form_submit_button(
            "Save sale" if prefix == "create" else "Update sale",
            type="primary", use_container_width=True,
        )
    if submitted:
        return _make_record(
            sale_date, item_name, brand, category, units, unit_price,
            payment_mode, customer_type, region,
        )
    return None


def _sales_register(frame: pd.DataFrame) -> None:
    _page_header("Record keeping", "Sales register", "Create, review, update, and remove sales transactions.")
    browse, add, edit, delete = st.tabs(["Browse records", "Add sale", "Edit sale", "Delete sale"])
    with browse:
        if frame.empty:
            st.info("No sales records found.")
        else:
            search = st.text_input("Search product, category, brand, or region")
            visible = frame
            if search.strip():
                needle = re.escape(search.strip())
                matches = visible[["item_name", "category", "brand", "region"]].astype(str)
                mask = matches.apply(
                    lambda column: column.str.contains(needle, case=False, na=False)
                ).any(axis=1)
                visible = visible[mask]
            st.caption(f"{len(visible):,} record(s)")
            st.dataframe(
                visible.rename(columns={
                    "sale_id": "Sale ID", "sale_date": "Date", "item_name": "Product",
                    "brand": "Brand", "category": "Category", "units_sold": "Units",
                    "unit_price": "Unit price (₹)", "total_revenue": "Revenue (₹)",
                    "payment_mode": "Payment", "customer_type": "Customer type", "region": "Region",
                }),
                hide_index=True, use_container_width=True,
            )
    with add:
        try:
            record = _record_form("create")
            if record is not None:
                _insert_sale(record)
                st.session_state["flash_message"] = "Sale added successfully."
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except AppError as exc:
            st.error(str(exc))
    with edit:
        if frame.empty:
            st.info("Add or import a sale before editing records.")
        else:
            selected_id = st.selectbox("Choose a sale ID", frame["sale_id"].astype(int).tolist())
            selected = frame.loc[frame["sale_id"] == selected_id].iloc[0].to_dict()
            try:
                record = _record_form("edit", selected)
                if record is not None:
                    _update_sale(int(selected_id), record)
                    st.session_state["flash_message"] = "Sale updated successfully."
                    st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except AppError as exc:
                st.error(str(exc))
    with delete:
        if frame.empty:
            st.info("There are no records to delete.")
        else:
            selected_id = st.selectbox(
                "Choose a sale ID to delete", frame["sale_id"].astype(int).tolist(),
                key="delete_sale_id",
            )
            row = frame.loc[frame["sale_id"] == selected_id].iloc[0]
            st.warning(
                f"Sale #{selected_id}: {row['item_name']} · {row['units_sold']} unit(s) · "
                f"{_money(row['total_revenue'])}"
            )
            confirmed = st.checkbox("I understand this permanently deletes the selected record.")
            if st.button("Delete sale", type="primary", disabled=not confirmed):
                try:
                    _delete_sale(int(selected_id))
                    st.session_state["flash_message"] = "Sale deleted successfully."
                    st.rerun()
                except AppError as exc:
                    st.error(str(exc))


def _insights(frame: pd.DataFrame) -> None:
    _page_header("Understand what is working", "Insights", "Explore product, customer, payment, and regional performance.")
    if frame.empty:
        st.info("Add or import sales to unlock business insights.")
        return
    first, second = st.columns(2)
    with first:
        st.markdown('<div class="panel-title">Product performance</div>', unsafe_allow_html=True)
        products = (
            frame.groupby("item_name", as_index=False)
            .agg(Revenue=("total_revenue", "sum"), Units=("units_sold", "sum"), Sales=("sale_id", "count"))
            .sort_values("Revenue", ascending=False)
        )
        st.dataframe(products, hide_index=True, use_container_width=True)
    with second:
        st.markdown('<div class="panel-title">Regional revenue</div>', unsafe_allow_html=True)
        regions = frame.groupby("region", as_index=False)["total_revenue"].sum()
        chart = px.bar(
            regions.sort_values("total_revenue"), x="total_revenue", y="region",
            orientation="h", color_discrete_sequence=["#087f8c"],
        )
        chart.update_layout(
            height=340, margin=dict(l=12, r=12, t=10, b=12),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Revenue (₹)", yaxis_title=None,
        )
        st.plotly_chart(_style_chart(chart), use_container_width=True)
    first, second = st.columns(2)
    with first:
        st.markdown('<div class="panel-title">Payment mix</div>', unsafe_allow_html=True)
        payment = frame.groupby("payment_mode", as_index=False)["total_revenue"].sum()
        chart = px.pie(
            payment, names="payment_mode", values="total_revenue", hole=0.55,
            color_discrete_sequence=["#087f8c", "#23a59e", "#f0a35e", "#637a93"],
        )
        chart.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)", legend_title=None)
        st.plotly_chart(_style_chart(chart), use_container_width=True)
    with second:
        st.markdown('<div class="panel-title">Customer segments</div>', unsafe_allow_html=True)
        customers = (
            frame.groupby("customer_type", as_index=False)
            .agg(Revenue=("total_revenue", "sum"), Transactions=("sale_id", "count"))
            .sort_values("Revenue", ascending=False)
        )
        st.dataframe(customers, hide_index=True, use_container_width=True)


CSV_COLUMNS = [
    "sale_date", "item_name", "brand", "category", "units_sold", "unit_price",
    "payment_mode", "customer_type", "region",
]
CSV_ALIASES = {
    "sale_date": {"sale_date", "date", "transaction_date"},
    "item_name": {"item_name", "product", "product_name", "item"},
    "brand": {"brand"},
    "category": {"category"},
    "units_sold": {"units_sold", "units", "quantity", "qty"},
    "unit_price": {"unit_price", "price_rs", "price", "unit_cost"},
    "payment_mode": {"payment_mode", "payment", "payment_method"},
    "customer_type": {"customer_type", "customer_segment"},
    "region": {"region", "location"},
    "month": {"month"},
    "total_revenue": {"total_revenue", "revenue", "sales"},
}


def _normalise_column(name: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _parse_import(upload: Any, default_year: int) -> tuple[list[tuple[Any, ...]], list[str]]:
    try:
        source = pd.read_csv(io.BytesIO(upload.getvalue()))
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        raise AppError(f"Could not read the CSV file: {exc}") from exc
    if source.empty:
        raise AppError("The uploaded CSV contains no data rows.")

    aliases: dict[str, str] = {}
    for column in source.columns:
        normalized = _normalise_column(column)
        for canonical, names in CSV_ALIASES.items():
            if normalized in names:
                aliases[canonical] = column
                break
    missing = [field for field in REQUIRED_FIELDS if field not in aliases and field != "sale_date"]
    if "sale_date" not in aliases and "month" not in aliases:
        missing.append("sale_date (or Month)")
    if missing:
        raise AppError("Missing required CSV columns: " + ", ".join(missing))

    valid_rows: list[tuple[Any, ...]] = []
    errors: list[str] = []
    for index, row in source.iterrows():
        row_number = int(index) + 2
        try:
            if "sale_date" in aliases:
                sale_date = pd.to_datetime(row[aliases["sale_date"]], errors="raise").date()
            else:
                month_value = str(row[aliases["month"]]).strip()
                month_number = int(month_value) if month_value.isdigit() else MONTHS.index(
                    month_value.title()
                ) + 1
                sale_date = date(default_year, month_number, 1)

            def field(name: str, default: Any = "") -> Any:
                column = aliases.get(name)
                return row[column] if column is not None and pd.notna(row[column]) else default

            record = _make_record(
                sale_date, field("item_name"), field("brand"), field("category"),
                field("units_sold"), field("unit_price"), field("payment_mode"),
                field("customer_type"), field("region"),
            )
            source_revenue = field("total_revenue")
            if source_revenue != "":
                revenue = Decimal(str(source_revenue))
                calculated = Decimal(record[4]) * record[5]
                if not revenue.is_finite() or abs(revenue - calculated) > Decimal("0.02"):
                    raise ValueError(
                        f"Revenue does not match units × unit price ({calculated:.2f})."
                    )
            valid_rows.append(record)
        except (ValueError, InvalidOperation, TypeError, OverflowError) as exc:
            errors.append(f"Row {row_number}: {exc}")

    if errors:
        return [], errors
    return valid_rows, []


def _insert_many(records: list[tuple[Any, ...]]) -> None:
    with _connection() as connection:
        cursor = connection.cursor()
        try:
            cursor.executemany(
                """
                INSERT INTO sales
                    (sale_date, item_name, brand, category, units_sold, unit_price,
                     payment_mode, customer_type, region)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                records,
            )
            connection.commit()
        finally:
            cursor.close()


def _import_export(frame: pd.DataFrame) -> None:
    _page_header("Move data in and out", "Import & export", "Validate CSV uploads and download a portable copy of your records.")
    template = pd.DataFrame([{
        "Sale_Date": date.today().isoformat(), "Item_Name": "Example product", "Brand": "Northstar",
        "Category": "Accessories", "Units_Sold": 2, "Price_Rs": 499.00,
        "Payment_Mode": "Card", "Customer_Type": "Retail", "Region": "North",
    }])
    st.download_button(
        "Download CSV template", template.to_csv(index=False).encode("utf-8"),
        file_name="northstar_sales_template.csv", mime="text/csv",
    )
    st.markdown("#### Import sales")
    st.caption(
        "Accepts `Sale_Date` (or `Month`) and the sample format "
        "`Item_Name`, `Brand`, `Category`, `Units_Sold`, `Price_Rs`, "
        "`Payment_Mode`, `Customer_Type`, and `Region`."
    )
    uploaded = st.file_uploader("Choose a CSV file", type=["csv"], key="sales_csv")
    year = st.number_input("Year to use when the CSV only has a Month column", min_value=2000, max_value=2100, value=date.today().year)
    if uploaded is not None and st.button("Validate and import", type="primary"):
        try:
            records, errors = _parse_import(uploaded, int(year))
            if errors:
                st.error(f"Import stopped: {len(errors)} row(s) need attention. No rows were saved.")
                for message in errors[:20]:
                    st.write(f"- {message}")
                if len(errors) > 20:
                    st.caption(f"{len(errors) - 20} more validation error(s) not shown.")
            else:
                _insert_many(records)
                st.session_state["flash_message"] = f"Imported {len(records):,} sales record(s)."
                st.rerun()
        except AppError as exc:
            st.error(str(exc))
    st.divider()
    st.markdown("#### Export current records")
    if frame.empty:
        st.info("No records are available to export.")
    else:
        export = frame.copy()
        export["sale_date"] = export["sale_date"].dt.strftime("%Y-%m-%d")
        export = export.rename(columns={
            "sale_id": "Sale_ID", "sale_date": "Sale_Date", "item_name": "Item_Name",
            "brand": "Brand", "category": "Category", "units_sold": "Units_Sold",
            "unit_price": "Price_Rs", "total_revenue": "Total_Revenue",
            "payment_mode": "Payment_Mode", "customer_type": "Customer_Type", "region": "Region",
        })
        st.download_button(
            "Export sales to CSV", export.to_csv(index=False).encode("utf-8"),
            file_name=f"northstar_sales_{date.today().isoformat()}.csv",
            mime="text/csv", type="primary",
        )


def _show_connection_help(error: AppError) -> None:
    st.error(str(error))
    with st.expander("Quick setup"):
        st.markdown(
            "1. Start MySQL and run [`schema.sql`](schema.sql) in your MySQL client.\n"
            "2. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.\n"
            "3. Add your MySQL host, user, and password in that local file.\n"
            "4. Restart Streamlit."
        )


def main() -> None:
    if not _login():
        return

    if st.session_state.get("flash_message"):
        st.success(st.session_state.pop("flash_message"))

    with st.sidebar:
        st.markdown(
            '<div class="brand"><div class="brand-mark">N</div><div>'
            '<div class="brand-name">NORTHSTAR</div>'
            '<div class="brand-caption">COMMERCE DESK</div></div></div>',
            unsafe_allow_html=True,
        )
        page = st.radio("Workspace", PAGE_NAMES, label_visibility="collapsed")
        st.divider()
        if st.button("Sign out", use_container_width=True):
            st.session_state.pop("authenticated", None)
            st.rerun()

    try:
        sales = _fetch_sales()
    except AppError as exc:
        _show_connection_help(exc)
        return

    st.sidebar.caption(f"MySQL live · {len(sales):,} sales record(s)")
    reports = _apply_filters(sales) if page in {"Overview", "Insights"} else sales

    if page == "Overview":
        _overview(reports)
    elif page == "Sales register":
        _sales_register(sales)
    elif page == "Insights":
        _insights(reports)
    elif page == "Import & export":
        _import_export(sales)


if __name__ == "__main__":
    main()
