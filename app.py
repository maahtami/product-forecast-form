import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import base64
import uuid
import pycountry  # to list all countries dynamically

# -----------------------------
# PAGE CONFIG (set first)
# -----------------------------
st.set_page_config(page_title="Product Forecast Form", layout="centered")

# -----------------------------
# GLOBAL STYLE: FONT + COLORS
# -----------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif;
        color: black !important;
        background-color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# GOOGLE SHEETS SETUP
# -----------------------------
SHEET_NAME = "ProductForecast"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1  # first worksheet

# -----------------------------
# LOGO / HEADER
# -----------------------------
def get_base64_image(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

logo_base64 = get_base64_image("logo.png")

st.markdown(
    f"""
    <div style="text-align: center; padding: 15px; background-color: white; border-radius: 12px;">
        <img src="data:image/png;base64,{logo_base64}" width="160" style="margin-bottom:10px;">
        <h1 style="color: black; font-family: 'Montserrat', sans-serif;">Product Forecast Form</h1>
        <p style="color: black; margin-top:-10px; font-family: 'Montserrat', sans-serif;">Nephrocan Forecast Portal</p>
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# SESSION STATE INITIALIZATION
# -----------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

if "review_mode" not in st.session_state:
    st.session_state.review_mode = False

# -----------------------------
# LOAD PRODUCT DATA
# -----------------------------
@st.cache_data
def load_data():
    return pd.read_csv("product list.csv")

df = load_data()

# -----------------------------
# COUNTRY SELECTION (GLOBAL LIST)
# -----------------------------
countries = sorted([country.name for country in pycountry.countries]) + ["Other"]

country_choice = st.selectbox("Select Country", countries)
country = country_choice
if country_choice == "Other":
    country_other = st.text_input("Please type your country name")
    if country_other.strip():
        country = country_other.strip()

# -----------------------------
# USER INFO
# -----------------------------
st.markdown("### User Information")
email = st.text_input("Enter Your Email Address")
company = st.text_input("Company Name")

st.markdown("---")
st.subheader("Product Forecast")

# -----------------------------
# ADD ROW BUTTON
# -----------------------------
if st.button("Add Product Forecast Row") and not st.session_state.review_mode:
    st.session_state.product_entries.append({
        "group": None,
        "name": None,
        "detail": None,
        "code": None,
        "January": 0,
        "February": 0,
        "March": 0,
        "April": 0,
        "May": 0,
        "June": 0,
        "July": 0,
        "August": 0,
        "September": 0,
        "October": 0,
        "November": 0,
        "December": 0,
        "total": 0
    })

# -----------------------------
# PRODUCT ROWS (ONLY IN EDIT MODE)
# -----------------------------
months = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

if not st.session_state.review_mode:
    for i, entry in enumerate(st.session_state.product_entries):
        st.markdown(f"#### Product {i+1}")
        col1, col2 = st.columns(2)

        # --- PRODUCT GROUP DROPDOWN ---
        product_groups = [g for g in df["Product Group"].unique() if str(g) != "nan"]

        # Previous selected group, name, detail (for persistence)
        prev_group = entry.get("group", product_groups[0] if product_groups else "")
        prev_name = entry.get("name", None)
        prev_detail = entry.get("detail", None)

        with col1:
            group = st.selectbox(
                f"Product Group {i+1}",
                product_groups,
                index=product_groups.index(prev_group) if prev_group in product_groups else 0,
                key=f"group_{i}"
            )

        # Filter df for this group
        filtered_df = df[df["Product Group"] == group]

        # Prepare name and detail lists
        product_names = filtered_df["Product Name"].unique().tolist()
        product_details = filtered_df["Description"].unique().tolist()

        # --- PRODUCT NAME DROPDOWN ---
        with col2:
            if product_names:
                name_index = product_names.index(prev_name) if prev_name in product_names else 0
            else:
                product_names = [""]
                name_index = 0

            selected_name = st.selectbox(
                f"Product Name {i+1}",
                product_names,
                index=name_index,
                key=f"name_{i}"
            )

        # --- PRODUCT DETAIL DROPDOWN (BIG) ---
        if product_details:
            if prev_detail in product_details:
                detail_index = product_details.index(prev_detail)
            else:
                detail_index = 0
        else:
            product_details = [""]
            detail_index = 0

        selected_detail = st.selectbox(
            f"Product Detail {i+1}",
            product_details,
            index=detail_index,
            key=f"detail_{i}",
            help="Choose detailed product description"
        )

        # --- SYNC LOGIC BETWEEN NAME AND DETAIL ---
        # Determine what changed relative to previous stored entry
        last_name = entry.get("name", selected_name)
        last_detail = entry.get("detail", selected_detail)

        source = None
        if selected_name != last_name:
            source = "name"
        if selected_detail != last_detail:
            source = "detail"

        # Default row used to fetch mapping
        row_by_name = filtered_df[filtered_df["Product Name"] == selected_name]
        row_by_detail = filtered_df[filtered_df["Description"] == selected_detail]

        if source == "name" and not row_by_name.empty:
            # If user changed name → update detail from that row
            selected_detail = row_by_name["Description"].values[0]
            row = row_by_name.iloc[0]
        elif source == "detail" and not row_by_detail.empty:
            # If user changed detail → update name from that row
            selected_name = row_by_detail["Product Name"].values[0]
            row = row_by_detail.iloc[0]
        else:
            # Fallback if nothing changed or data inconsistency
            if not row_by_name.empty:
                row = row_by_name.iloc[0]
                selected_detail = row["Description"]
            elif not row_by_detail.empty:
                row = row_by_detail.iloc[0]
                selected_name = row["Product Name"]
            else:
                row = None

        # Hidden product code (not shown in form)
        product_code = row["PRODUCT CODE"] if row is not None else None

        # --- MONTHLY QUANTITIES ---
        monthly_quantities = {}
        total = 0
        cols_months = st.columns(3)

        for idx, month in enumerate(months):
            with cols_months[idx % 3]:
                previous_qty = entry.get(month, 0)
                qty = st.number_input(
                    f"{month} {i+1}",
                    min_value=0,
                    value=int(previous_qty),
                    key=f"{month}_{i}"
                )
                monthly_quantities[month] = qty
                total += qty

        st.write(f"**Total:** {total}")

        # --- SAVE ROW BACK TO SESSION STATE ---
        st.session_state.product_entries[i] = {
            "group": group,
            "name": selected_name,
            "detail": selected_detail,
            "code": product_code,
            **monthly_quantities,
            "total": total
        }

st.markdown("---")

# -----------------------------
# REVIEW / SUBMIT SECTION
# -----------------------------
if not st.session_state.review_mode:
    # Show "Review Forecast" instead of direct submit
    if st.button("Review Forecast"):
        if not email.strip():
            st.error("Please enter your email before reviewing.")
        elif not company:
            st.error("Please enter a company name before reviewing.")
        elif not st.session_state.product_entries:
            st.error("Please add at least one product forecast row.")
        else:
            st.session_state.review_mode = True
else:
    # -------- REVIEW TABLE --------
    st.subheader("Review Your Forecast")

    review_df = pd.DataFrame(st.session_state.product_entries)

    # Order and show relevant columns
    ordered_cols = [
        "name", "detail",
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
        "total"
    ]
    review_df = review_df[ordered_cols].rename(columns={
        "name": "Product Name",
        "detail": "Product Detail",
        "total": "Total"
    })

    st.dataframe(review_df, use_container_width=True)

    col_back, col_submit = st.columns(2)

    # Back to editing
    with col_back:
        if st.button("Back to Edit"):
            st.session_state.review_mode = False

    # Final submit
    with col_submit:
        if st.button("Submit Final Forecast"):
            submission_df = pd.DataFrame(st.session_state.product_entries)
            submission_df["User ID"] = st.session_state.user_id
            submission_df["Email"] = email
            submission_df["Country"] = country
            submission_df["Company"] = company

            # Save locally
            file_path = "forecast_submissions.csv"
            if os.path.exists(file_path):
                existing = pd.read_csv(file_path)
                updated = pd.concat([existing, submission_df], ignore_index=True)
                updated.to_csv(file_path, index=False)
            else:
                submission_df.to_csv(file_path, index=False)

            # Ensure Google Sheet headers exist
            if len(sheet.get_all_values()) == 0:
                sheet.append_row([
                    "Timestamp", "User ID", "Email", "Country", "Company Name",
                    "Product Group", "Product Name", "Product Code", "Description",
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December",
                    "Total"
                ])

            # Upload to Google Sheets
            for _, entry in submission_df.iterrows():
                sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    entry["User ID"],
                    entry["Email"],
                    entry["Country"],
                    entry["Company"],
                    entry["group"],
                    entry["name"],
                    entry["code"],
                    entry["detail"],
                    int(entry["January"]),
                    int(entry["February"]),
                    int(entry["March"]),
                    int(entry["April"]),
                    int(entry["May"]),
                    int(entry["June"]),
                    int(entry["July"]),
                    int(entry["August"]),
                    int(entry["September"]),
                    int(entry["October"]),
                    int(entry["November"]),
                    int(entry["December"]),
                    int(entry["total"])
                ])

            # Reset after submission
            st.session_state.product_entries = []
            st.session_state.review_mode = False
            st.success("Forecast submitted successfully!")
            st.balloons()