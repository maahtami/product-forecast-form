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
# GOOGLE FONT + UI FIX
# ---------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');
html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif !important;
}
body { background: transparent !important; }
button, .stButton > button {
    background-color: #A6192E !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# GOOGLE SHEET SETUP
# ---------------------------------------------------
SHEET_NAME = "ProductForecast"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# ---------------------------------------------------
# LOAD LOGO
# ---------------------------------------------------
def load_logo(path="logo.png"):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

logo_base64 = load_logo()

# ---------------------------------------------------
# PRODUCT LIST
# ---------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_csv("product list.csv")

df = load_data().dropna(subset=["Product Group"])

# ---------------------------------------------------
# STATE
# ---------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "form"

if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

if "locked" not in st.session_state:
    st.session_state.locked = False

if "email" not in st.session_state:
    st.session_state.email = ""

if "company" not in st.session_state:
    st.session_state.company = ""

if "country" not in st.session_state:
    st.session_state.country = ""

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
def render_header():
    st.markdown(
        f"""
        <div style="text-align:center; padding:10px; margin-bottom:20px;">
            <img src="data:image/png;base64,{logo_base64}" width="200">
            <p style="font-size:22px; font-weight:500; margin-top:5px;">
                Nephrocan Forecast Portal
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------------------------------------------
# MONTH LIST
# ---------------------------------------------------
month_list = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

# ---------------------------------------------------
# FORM PAGE
# ---------------------------------------------------
def render_form_page():
    render_header()

    # COUNTRY
    countries = sorted([c.name for c in pycountry.countries]) + ["Other"]
    st.session_state.country = st.selectbox(
        "Select Country",
        countries,
        index=countries.index(st.session_state.country)
        if st.session_state.country in countries else 0
    )

    if st.session_state.country == "Other":
        st.session_state.country = st.text_input(
            "Please type your country name",
            st.session_state.country
        )

    # USER INFO
    st.session_state.email = st.text_input("Enter Your Email Address", st.session_state.email)
    st.session_state.company = st.text_input("Company Name", st.session_state.company)

    st.markdown("---")
    st.subheader("Product Forecast")

    # ADD ROW
    if st.button("Add Product Forecast Row"):
        st.session_state.product_entries.append({
            "group": None,
            "name": None,
            "detail": None,
            "code": None,
            **{m: 0 for m in month_list},
            "total": 0,
            "locked": False
        })

    # PRODUCT ROWS
    for i, entry in enumerate(st.session_state.product_entries):
        st.markdown(f"#### Product {i+1}")
        col1, col2 = st.columns(2)

        # If user returned from review → lock all existing rows
        locked = entry.get("locked", False)

        # GROUP DROPDOWN
        groups = sorted(df["Product Group"].unique())
        group = col1.selectbox(
            f"Product Group {i+1}",
            groups,
            index=groups.index(entry["group"]) if entry["group"] in groups else 0,
            key=f"group_{i}",
            disabled=locked
        )

        filtered = df[df["Product Group"] == group]

        # NAME DROPDOWN
        names = filtered["Product Name"].unique().tolist()
        name = col2.selectbox(
            f"Product Name {i+1}",
            names,
            index=names.index(entry["name"]) if entry["name"] in names else 0,
            key=f"name_{i}",
            disabled=locked
        )

        # DETAIL DROPDOWN
        details = filtered["Description"].unique().tolist()
        detail = st.selectbox(
            f"Product Detail {i+1}",
            details,
            index=details.index(entry["detail"]) if entry["detail"] in details else 0,
            key=f"detail_{i}",
            disabled=locked
        )

        # SYNC
        if not locked:  # only sync if editable
            row_by_name = filtered[filtered["Product Name"] == name]
            row_by_detail = filtered[filtered["Description"] == detail]

            if not row_by_name.empty:
                detail = row_by_name["Description"].values[0]
            if not row_by_detail.empty:
                name = row_by_detail["Product Name"].values[0]

        code = filtered[filtered["Product Name"] == name]["PRODUCT CODE"].values[0]

        # MONTH INPUTS (always editable)
        cols = st.columns(3)
        total = 0
        month_values = {}

        for idx, m in enumerate(month_list):
            with cols[idx % 3]:
                qty = st.number_input(
                    f"{m} ({i+1})",
                    min_value=0,
                    value=entry.get(m, 0),
                    key=f"{m}_{i}"
                )
                month_values[m] = qty
                total += qty

        st.write(f"**Total: {total}**")

        st.session_state.product_entries[i] = {
            "group": group,
            "name": name,
            "detail": detail,
            "code": code,
            **month_values,
            "total": total,
            "locked": locked
        }

    st.markdown("---")

    # REVIEW BUTTON
    if st.button("Review Forecast"):
        # lock all existing rows
        for item in st.session_state.product_entries:
            item["locked"] = True

        st.session_state.page = "review"

# ---------------------------------------------------
# REVIEW PAGE
# ---------------------------------------------------
def render_review_page():
    st.markdown("## Review Your Forecast")
    st.write(f"**Country:** {st.session_state.country}")
    st.write(f"**Company:** {st.session_state.company}")
    st.write(f"**Email:** {st.session_state.email}")

    df_review = pd.DataFrame(st.session_state.product_entries)
    st.dataframe(df_review)

    # EXPORT EXCEL
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_review.to_excel(writer, index=False)

    st.download_button(
        "Download as Excel",
        buffer.getvalue(),
        "forecast_review.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← Go Back & Edit"):
            st.session_state.page = "form"

    with col2:
        if st.button("Submit Forecast"):
            submit_to_google()
            st.success("Your forecast was submitted successfully!")
            st.balloons()

# ---------------------------------------------------
# SUBMIT TO GOOGLE SHEETS
# ---------------------------------------------------
def submit_to_google():
    df_submit = pd.DataFrame(st.session_state.product_entries)
    df_submit["User ID"] = str(uuid.uuid4())[:8]
    df_submit["Email"] = st.session_state.email
    df_submit["Country"] = st.session_state.country
    df_submit["Company"] = st.session_state.company

    if len(sheet.get_all_values()) == 0:
        sheet.append_row(["Timestamp","User ID","Email","Country","Company",
                          "Product Group","Product Name","Product Code","Description",
                          *month_list,"Total"])

    for _, row in df_submit.iterrows():
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            row["User ID"],
            row["Email"],
            row["Country"],
            row["Company"],
            row["group"],
            row["name"],
            row["code"],
            row["detail"],
            *[int(row[m]) for m in month_list],
            int(row["total"])
        ])

# ---------------------------------------------------
# ROUTING
# ---------------------------------------------------
if st.session_state.page == "form":
    render_form_page()
else:
    render_review_page()