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
# GOOGLE FONT (Montserrat)
# ---------------------------------------------------
# ---------------------------------------------------
# FORCE LIGHT THEME + MONTSERRAT
# ---------------------------------------------------
st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');

/* Apply Montserrat everywhere */
html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif;
}

/* Do NOT force background or text color — allow dark/light mode */
body {
    background: transparent !important;
    color: inherit !important;
}

/* Buttons: Nephrocan Red */
button, .stButton > button {
    background-color: #A6192E !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
}

/* Center header content */
.nephro-header {
    text-align: center;
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 25px;
}

/* Light/dark mode adaptive box */
[data-baseweb="block"] {
    background: none !important;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# GOOGLE SHEETS SETUP
# ---------------------------------------------------
SHEET_NAME = "ProductForecast"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
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
# LOAD PRODUCT LIST
# ---------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_csv("product list.csv")

df = load_data()
df = df.dropna(subset=["Product Group"])

# ---------------------------------------------------
# MULTI-PAGE STATE
# ---------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "form"

if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

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
        <div style="text-align: center; padding: 10px; margin-bottom: 20px;">
            <img src="data:image/png;base64,{logo_base64}" width="200" style="margin-bottom:5px;">
            <p style="color:inherit; font-size:22px; font-weight:500; margin-top:5px;">
                Nephrocan Forecast Portal
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------------------------------------------
# PAGE 1 — FORM PAGE
# ---------------------------------------------------
def render_form_page():

    render_header()
    st.write("")
    st.write("")

    # ----------------------
    # COUNTRY
    # ----------------------
    countries = sorted([c.name for c in pycountry.countries]) + ["Other"]
    st.session_state.country = st.selectbox(
        "Select Country",
        countries,
        index=countries.index(st.session_state.country) if st.session_state.country in countries else 0
    )

    if st.session_state.country == "Other":
        st.session_state.country = st.text_input(
            "Please type your country name",
            st.session_state.country
        )

    # ----------------------
    # USER INFO
    # ----------------------
    st.markdown("### User Information")
    st.session_state.email = st.text_input(
        "Enter Your Email Address",
        st.session_state.email
    )
    st.session_state.company = st.text_input(
        "Company Name",
        st.session_state.company
    )

    st.markdown("---")
    st.subheader("Product Forecast")

    # ----------------------
    # ADD ROW BUTTON
    # ----------------------
    if st.button("Add Product Forecast Row"):
        st.session_state.product_entries.append({
            "group": None,
            "name": None,
            "detail": None,
            "code": None,
            **{m: 0 for m in month_list},
            "total": 0,
        })

    # ----------------------
    # PRODUCT ROWS
    # ----------------------
    for i, entry in enumerate(st.session_state.product_entries):
        st.markdown(f"#### Product {i+1}")
        col1, col2 = st.columns(2)

        # This row is NEW if group is still None
        is_new_row = entry["group"] is None

        # --- Product Group List ---
        product_groups = sorted(df["Product Group"].unique())

        # PRE-SELECT group
        default_group = entry["group"] if entry["group"] in product_groups else product_groups[0]

        # Disable dropdown if row already exists
        with col1:
            group = st.selectbox(
                f"Product Group {i+1}",
                product_groups,
                index=product_groups.index(default_group),
                key=f"group_{i}",
                disabled=not is_new_row    # ← user cannot modify after review
            )

        # Filter product list
        filtered = df[df["Product Group"] == group]

        # Name & detail list
        product_names = filtered["Product Name"].unique().tolist()
        product_details = filtered["Description"].unique().tolist()

        # PRE-SELECT name & detail
        default_name = entry["name"] if entry["name"] in product_names else product_names[0]
        default_detail = entry["detail"] if entry["detail"] in product_details else product_details[0]

        # --- Product Name ---
        with col2:
            name = st.selectbox(
                f"Product Name {i+1}",
                product_names,
                index=product_names.index(default_name),
                key=f"name_{i}",
                disabled=not is_new_row
            )

        # --- Product Detail (big dropdown) ---
        detail = st.selectbox(
            f"Product Detail {i+1}",
            product_details,
            index=product_details.index(default_detail),
            key=f"detail_{i}",
            disabled=not is_new_row
        )

        # --- SYNC NAME ↔ DETAIL ---
        if is_new_row:
            # If user selects name → update description
            row_name = filtered[filtered["Product Name"] == name]
            if not row_name.empty:
                detail = row_name["Description"].values[0]

            # If user selects detail → update name
            row_detail = filtered[filtered["Description"] == detail]
            if not row_detail.empty:
                name = row_detail["Product Name"].values[0]
        else:
            # locked row → always force synced values
            row_detail = filtered[filtered["Description"] == detail]
            name = row_detail["Product Name"].values[0]

        # Product Code (hidden)
        product_code = filtered[filtered["Product Name"] == name]["PRODUCT CODE"].values[0]

        # --- MONTH INPUTS ---
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

        # SAVE ENTRY (group/name/detail locked for old rows)
        st.session_state.product_entries[i] = {
            "group": group,
            "name": name,
            "detail": detail,
            "code": product_code,
            **month_values,
            "total": total
        }

    # ----------------------
    # REVIEW BUTTON
    # ----------------------
    if st.button("Review Forecast"):
        st.session_state.page = "review"

# ---------------------------------------------------
# MONTH LIST
# ---------------------------------------------------
month_list = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

# ---------------------------------------------------
# PAGE 2 — REVIEW PAGE
# ---------------------------------------------------
def render_review_page():
    st.markdown("## Review Your Forecast")
    st.write(f"**Country:** {st.session_state.country}")
    st.write(f"**Company:** {st.session_state.company}")
    st.write(f"**Email:** {st.session_state.email}")

    df_review = pd.DataFrame(st.session_state.product_entries)
    st.dataframe(df_review)

    # --- EXPORT TO EXCEL ---
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_review.to_excel(writer, index=False)

    st.download_button(
        "Download as Excel",
        data=buffer.getvalue(),
        file_name="forecast_review.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
# GOOGLE SUBMIT
# ---------------------------------------------------
def submit_to_google():
    df_submit = pd.DataFrame(st.session_state.product_entries)
    df_submit["User ID"] = str(uuid.uuid4())[:8]
    df_submit["Email"] = st.session_state.email
    df_submit["Country"] = st.session_state.country
    df_submit["Company"] = st.session_state.company

    # sheet header if empty
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
# PAGE ROUTING
# ---------------------------------------------------
if st.session_state.page == "form":
    render_form_page()
else:
    render_review_page()