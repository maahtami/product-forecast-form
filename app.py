import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import base64
import uuid
import pycountry
from io import BytesIO

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(page_title="Product Forecast Form", layout="centered")

# ---------------------------------------------------
# GLOBAL CONSTANTS
# ---------------------------------------------------
NEPHRO_RED = "#A6192E"

MONTH_LIST = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

# ---------------------------------------------------
# FONT + BASIC STYLING (NO FORCED BACKGROUND)
# ---------------------------------------------------
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');

/* Apply Montserrat */
html, body, [class*="css"] {{
    font-family: 'Montserrat', sans-serif;
}}

/* Do NOT override background / text, respect dark or light mode */
body {{
    background: transparent !important;
    color: inherit !important;
}}

/* Buttons: Nephrocan Red */
button, .stButton > button {{
    background-color: {NEPHRO_RED} !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 0.5rem 1.0rem !important;
    border: none !important;
}}

/* Center header content */
.nephro-header {{
    text-align: center;
    padding: 10px;
    margin-bottom: 20px;
}}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------
# GOOGLE SHEETS SETUP
# ---------------------------------------------------
SHEET_NAME = "ProductForecast"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ---------------------------------------------------
# LOAD LOGO
# ---------------------------------------------------
def load_logo(path: str = "logo.png") -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


logo_base64 = load_logo()

# ---------------------------------------------------
# LOAD PRODUCT LIST
# ---------------------------------------------------
@st.cache_data
def load_product_data():
    return pd.read_csv("product list.csv")


df = load_product_data()
df = df.dropna(subset=["Product Group"])  # ensure no NaN groups
PRODUCT_GROUPS = sorted(df["Product Group"].unique().tolist())

# ---------------------------------------------------
# SESSION STATE INITIALIZATION
# ---------------------------------------------------
ss = st.session_state

if "page" not in ss:
    ss.page = "form"  # "form" or "review"

if "product_entries" not in ss:
    ss.product_entries = []  # list of dict rows

if "email" not in ss:
    ss.email = ""

if "company" not in ss:
    ss.company = ""

if "country" not in ss:
    ss.country = ""

if "user_id" not in ss:
    ss.user_id = str(uuid.uuid4())[:8]

# Number of rows that are "locked" after first review
# (0 means nothing locked yet)
if "lock_rows" not in ss:
    ss.lock_rows = 0

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
def render_header():
    st.markdown(
        f"""
        <div class="nephro-header">
            <img src="data:image/png;base64,{logo_base64}" width="200" style="margin-bottom:5px;">
            <p style="font-size:22px; font-weight:500; margin-top:5px;">
                Nephrocan Forecast Portal
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------
# CALLBACKS FOR SYNCING NAME <-> DETAIL
# ---------------------------------------------------
def on_change_group(row_index: int):
    """When group changes, pick first product in that group."""
    group = ss.get(f"group_{row_index}")
    filtered = df[df["Product Group"] == group]
    if filtered.empty:
        return
    first = filtered.iloc[0]
    ss[f"name_{row_index}"] = first["Product Name"]
    ss[f"detail_{row_index}"] = first["Description"]
    ss[f"code_{row_index}"] = first["PRODUCT CODE"]


def on_change_name(row_index: int):
    """When name changes, update detail + code."""
    group = ss.get(f"group_{row_index}")
    name = ss.get(f"name_{row_index}")
    filtered = df[(df["Product Group"] == group) & (df["Product Name"] == name)]
    if filtered.empty:
        return
    row = filtered.iloc[0]
    ss[f"detail_{row_index}"] = row["Description"]
    ss[f"code_{row_index}"] = row["PRODUCT CODE"]


def on_change_detail(row_index: int):
    """When detail changes, update name + code."""
    group = ss.get(f"group_{row_index}")
    detail = ss.get(f"detail_{row_index}")
    filtered = df[(df["Product Group"] == group) & (df["Description"] == detail)]
    if filtered.empty:
        return
    row = filtered.iloc[0]
    ss[f"name_{row_index}"] = row["Product Name"]
    ss[f"code_{row_index}"] = row["PRODUCT CODE"]


# ---------------------------------------------------
# FORM PAGE
# ---------------------------------------------------
def render_form_page():
    render_header()
    st.write("")
    st.write("")

    # ----------------------
    # COUNTRY
    # ----------------------
    countries = sorted([c.name for c in pycountry.countries]) + ["Other"]
    default_country_index = (
        countries.index(ss.country) if ss.country in countries else 0
    )
    country_choice = st.selectbox(
        "Select Country",
        countries,
        index=default_country_index,
    )

    if country_choice == "Other":
        ss.country = st.text_input(
            "Please type your country name",
            value=ss.country if ss.country not in countries else "",
        )
    else:
        ss.country = country_choice

    # ----------------------
    # USER INFO
    # ----------------------
    st.markdown("### User Information")
    ss.email = st.text_input("Enter Your Email Address", value=ss.email)
    ss.company = st.text_input("Company Name", value=ss.company)

    st.markdown("---")
    st.subheader("Product Forecast")

    # ----------------------
    # ADD ROW
    # ----------------------
    if st.button("Add Product Forecast Row"):
        # New empty row – fully editable
        ss.product_entries.append(
            {
                "group": PRODUCT_GROUPS[0],
                "name": None,
                "detail": None,
                "code": None,
                **{m: 0 for m in MONTH_LIST},
                "total": 0,
            }
        )

    # ----------------------
    # RENDER ROWS
    # ----------------------
    for i, entry in enumerate(ss.product_entries):
        st.markdown(f"#### Product {i+1}")

        is_locked = i < ss.lock_rows  # existing row after review

        # ----- META (GROUP / NAME / DETAIL) -----
        if is_locked:
            # Locked – no widgets, only text display
            st.write(f"**Product Group {i+1}:** {entry['group']}")
            st.write(f"**Product Name {i+1}:** {entry['name']}")
            st.write(f"**Product Detail {i+1}:** {entry['detail']}")
            group = entry["group"]
            name = entry["name"]
            detail = entry["detail"]
            code = entry["code"]
        else:
            # Editable row
            col1, col2 = st.columns(2)

            # --- Initialize session_state keys ONCE (before widgets) ---
            # Group
            if f"group_{i}" not in ss:
                ss[f"group_{i}"] = entry.get("group") or PRODUCT_GROUPS[0]
            group_value = ss[f"group_{i}"]

            # Names + details for this group
            filtered = df[df["Product Group"] == group_value]
            if filtered.empty:
                # Should not happen, but guard
                names_for_group = []
                details_for_group = []
            else:
                names_for_group = filtered["Product Name"].unique().tolist()
                details_for_group = filtered["Description"].unique().tolist()

            # Name
            if f"name_{i}" not in ss:
                if entry.get("name") and entry["name"] in names_for_group:
                    ss[f"name_{i}"] = entry["name"]
                elif names_for_group:
                    ss[f"name_{i}"] = names_for_group[0]

            # Detail
            if f"detail_{i}" not in ss:
                if entry.get("detail") and entry["detail"] in details_for_group:
                    ss[f"detail_{i}"] = entry["detail"]
                elif details_for_group:
                    ss[f"detail_{i}"] = details_for_group[0]

            # Code
            if f"code_{i}" not in ss:
                # try to find matching row for name+group
                row_match = df[
                    (df["Product Group"] == ss[f"group_{i}"])
                    & (df["Product Name"] == ss[f"name_{i}"])
                ]
                if not row_match.empty:
                    ss[f"code_{i}"] = row_match.iloc[0]["PRODUCT CODE"]
                else:
                    ss[f"code_{i}"] = entry.get("code")

            # --- Widgets ---
            group = col1.selectbox(
                f"Product Group {i+1}",
                PRODUCT_GROUPS,
                index=PRODUCT_GROUPS.index(ss[f"group_{i}"]),
                key=f"group_{i}",
                on_change=on_change_group,
                args=(i,),
            )

            # Recompute filtered after potential group change
            filtered = df[df["Product Group"] == group]
            names_for_group = filtered["Product Name"].unique().tolist()
            details_for_group = filtered["Description"].unique().tolist()

            # Ensure selected name/detail are valid for this group
            if ss[f"name_{i}"] not in names_for_group and names_for_group:
                ss[f"name_{i}"] = names_for_group[0]
            if ss[f"detail_{i}"] not in details_for_group and details_for_group:
                ss[f"detail_{i}"] = details_for_group[0]

            name = col2.selectbox(
                f"Product Name {i+1}",
                names_for_group,
                index=names_for_group.index(ss[f"name_{i}"]),
                key=f"name_{i}",
                on_change=on_change_name,
                args=(i,),
            )

            detail = st.selectbox(
                f"Product Detail {i+1}",
                details_for_group,
                index=details_for_group.index(ss[f"detail_{i}"]),
                key=f"detail_{i}",
                on_change=on_change_detail,
                args=(i,),
            )

            code = ss.get(f"code_{i}")

        # ----- MONTH INPUTS (ALWAYS EDITABLE) -----
        cols = st.columns(3)
        total = 0
        month_values = {}

        for idx, m in enumerate(MONTH_LIST):
            key = f"{m}_{i}"
            if key not in ss:
                ss[key] = entry.get(m, 0) or 0
            with cols[idx % 3]:
                qty = st.number_input(
                    f"{m} ({i+1})",
                    min_value=0,
                    value=ss[key],
                    key=key,
                )
                month_values[m] = qty
                total += qty

        st.write(f"**Total: {total}**")

        # ----- UPDATE product_entries WITH CURRENT STATE -----
        ss.product_entries[i] = {
            "group": group,
            "name": name,
            "detail": detail,
            "code": code,
            **month_values,
            "total": total,
        }

    st.markdown("---")

    # ----------------------
    # REVIEW BUTTON
    # ----------------------
    if st.button("Review Forecast"):
        if not ss.email.strip():
            st.error("Please enter your email before reviewing.")
        elif not ss.company.strip():
            st.error("Please enter a company name before reviewing.")
        elif not ss.product_entries:
            st.error("Please add at least one product forecast row.")
        else:
            # First time going to review: lock current rows
            if ss.lock_rows == 0:
                ss.lock_rows = len(ss.product_entries)
            ss.page = "review"


# ---------------------------------------------------
# REVIEW PAGE
# ---------------------------------------------------
def render_review_page():
    st.markdown("## Review Your Forecast")
    st.write(f"**Country:** {ss.country}")
    st.write(f"**Company:** {ss.company}")
    st.write(f"**Email:** {ss.email}")

    df_review = pd.DataFrame(ss.product_entries)

    # Reorder columns for readability
    col_order = ["group", "name", "detail"] + MONTH_LIST + ["total"]
    df_review = df_review[col_order]

    st.dataframe(df_review, use_container_width=True)

    # --- EXPORT TO EXCEL ---
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_review.to_excel(writer, index=False)

    st.download_button(
        "Download as Excel",
        data=buffer.getvalue(),
        file_name="forecast_review.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← Go Back & Edit"):
            # Going back: keep lock_rows as-is
            ss.page = "form"

    with col2:
        if st.button("Submit Forecast"):
            submit_to_google()
            st.success("Your forecast was submitted successfully!")
            st.balloons()


# ---------------------------------------------------
# SUBMIT TO GOOGLE SHEETS
# ---------------------------------------------------
def submit_to_google():
    df_submit = pd.DataFrame(ss.product_entries)
    df_submit["User ID"] = ss.user_id
    df_submit["Email"] = ss.email
    df_submit["Country"] = ss.country
    df_submit["Company"] = ss.company

    # Ensure header row exists
    if len(sheet.get_all_values()) == 0:
        sheet.append_row(
            [
                "Timestamp",
                "User ID",
                "Email",
                "Country",
                "Company",
                "Product Group",
                "Product Name",
                "Product Code",
                "Description",
                *MONTH_LIST,
                "Total",
            ]
        )

    for _, row in df_submit.iterrows():
        sheet.append_row(
            [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                row["User ID"],
                row["Email"],
                row["Country"],
                row["Company"],
                row["group"],
                row["name"],
                row["code"],
                row["detail"],
                *[int(row[m]) for m in MONTH_LIST],
                int(row["total"]),
            ]
        )


# ---------------------------------------------------
# ROUTER
# ---------------------------------------------------
if ss.page == "form":
    render_form_page()
else:
    render_review_page()