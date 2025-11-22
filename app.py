import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import base64
import uuid
import pycountry  # to list all countries dynamically
import io  # for Excel export

# -------------------------------------------------
#   PAGE & THEME SETUP
# -------------------------------------------------
st.set_page_config(page_title="Product Forecast Form", layout="centered")

# --- Add Google Font (Montserrat) ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600&display=swap');

    html, body, [class*="css"]  {
        font-family: 'Montserrat', sans-serif;
        color: black;
        background-color: white;
    }

    /* Make Streamlit main background white */
    .stApp {
        background-color: white;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------------------------------
#   GOOGLE SHEETS SETUP
# -------------------------------------------------
SHEET_NAME = "ProductForecast"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1  # first worksheet

# -------------------------------------------------
#   HEADER WITH LOGO
# -------------------------------------------------
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

# -------------------------------------------------
#   SESSION STATE INIT
# -------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

if "page" not in st.session_state:
    st.session_state.page = "form"   # "form" or "review"

if "review_df" not in st.session_state:
    st.session_state.review_df = None

# -------------------------------------------------
#   DATA LOAD
# -------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_csv("product list.csv")

df = load_data()

# Precompute clean product group list (no NaN)
PRODUCT_GROUPS = [g for g in df["Product Group"].unique() if str(g) != "nan"]

# Global months list
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

# -------------------------------------------------
#   FORM PAGE
# -------------------------------------------------
def render_form_page():
    # --- Country selection (dynamic global list) ---
    countries = sorted([country.name for country in pycountry.countries]) + ["Other"]

    country_choice = st.selectbox("Select Country", countries)
    country = country_choice
    if country_choice == "Other":
        country_other = st.text_input("Please type your country name")
        if country_other.strip():
            country = country_other.strip()

    # --- User Info ---
    st.markdown("### User Information")
    email = st.text_input("Enter Your Email Address")
    company = st.text_input("Company Name")

    st.markdown("---")
    st.subheader("Product Forecast")

    # --- Add forecast row button ---
    if st.button("Add Product Forecast Row"):
        st.session_state.product_entries.append({
            "group": None,
            "name": None,
            "description": None,
            "code": None,
            **{month: 0 for month in MONTHS},
            "total": 0
        })

    # --- Display product rows ---
    for i, entry in enumerate(st.session_state.product_entries):
        st.markdown(f"#### Product {i+1}")
        col1, col2 = st.columns(2)

        # ----- PRODUCT GROUP -----
        with col1:
            group = st.selectbox(
                f"Product Group {i+1}",
                PRODUCT_GROUPS,
                key=f"group_{i}"
            )

        # Filter based on selected group
        filtered_df = df[df["Product Group"] == group]

        # Create lists for dropdowns
        product_names = filtered_df["Product Name"].unique().tolist()
        product_details = filtered_df["Description"].unique().tolist()

        # ----- PRODUCT NAME -----
        with col2:
            name_choice = st.selectbox(
                f"Product Name {i+1}",
                product_names,
                key=f"name_{i}"
            )

        # ----- PRODUCT DETAIL (LONG DROPDOWN UNDER NAME) -----
        detail_choice = st.selectbox(
            f"Product Detail {i+1}",
            product_details,
            key=f"detail_{i}",
            help="Choose detailed product description"
        )

        # ----- LOGIC FOR FINAL ROW SELECTION -----
        # Priority: if detail selected → take row by detail; else by name
        row_by_detail = filtered_df[filtered_df["Description"] == detail_choice]
        if not row_by_detail.empty:
            final_row = row_by_detail.iloc[0]
        else:
            final_row = filtered_df[filtered_df["Product Name"] == name_choice].iloc[0]

        final_name = final_row["Product Name"]
        final_detail = final_row["Description"]
        final_code = final_row["PRODUCT CODE"]   # hidden from user

        # We do NOT show the product code on form (per your request)
        # We show only description under the dropdowns
        st.caption(f"Details: {final_detail}")

        # ----- MONTHLY INPUTS -----
        monthly_quantities = {}
        total = 0
        cols_month = st.columns(3)

        for idx, month in enumerate(MONTHS):
            with cols_month[idx % 3]:
                qty = st.number_input(
                    f"{month} {i+1}",
                    min_value=0,
                    key=f"{month}_{i}"
                )
                monthly_quantities[month] = qty
                total += qty

        st.write(f"Total: {total}")

        # ----- SAVE TO SESSION STATE -----
        st.session_state.product_entries[i] = {
            "group": group,
            "name": final_name,
            "description": final_detail,
            "code": final_code,   # hidden but saved
            **monthly_quantities,
            "total": total
        }

    st.markdown("---")

    # --- REVIEW FORECAST BUTTON ---
    if st.button("Review Forecast"):
        # Basic validations before going to review page
        if not email.strip():
            st.error("Please enter your email before reviewing.")
            return
        if not company.strip():
            st.error("Please enter a company name before reviewing.")
            return
        if not st.session_state.product_entries:
            st.error("Please add at least one product forecast row.")
            return

        # Build dataframe and store in session_state
        submission_df = pd.DataFrame(st.session_state.product_entries)

        # Store meta info separately in session_state
        st.session_state.review_df = submission_df
        st.session_state.review_email = email
        st.session_state.review_company = company
        st.session_state.review_country = country

        # Switch to review page
        st.session_state.page = "review"
        st.rerun()


# -------------------------------------------------
#   REVIEW PAGE
# -------------------------------------------------
def render_review_page():
    st.markdown("## Review Your Forecast")

    # Ensure we have a review dataframe
    if st.session_state.review_df is None or st.session_state.review_df.empty:
        st.warning("No data available to review. Please go back and fill the form.")
        if st.button("Back to Edit"):
            st.session_state.page = "form"
            st.experimental_rerun()
        return

    review_df = st.session_state.review_df.copy()

    # Build a user-facing table
    display_cols = (
        ["group", "name", "description"]
        + MONTHS
        + ["total"]
    )

    # Safety: only keep columns that exist
    display_cols = [c for c in display_cols if c in review_df.columns]

    display_df = review_df[display_cols].rename(columns={
        "group": "Product Group",
        "name": "Product Name",
        "description": "Product Description",
        "total": "Total"
    })

    # Styled table (grey header, simple grid)
    styled = (
        display_df.style
        .set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#f0f0f0"),
                        ("color", "black"),
                        ("font-weight", "600"),
                        ("border", "1px solid #d0d0d0"),
                        ("padding", "6px")
                    ]
                },
                {
                    "selector": "td",
                    "props": [
                        ("border", "1px solid #e0e0e0"),
                        ("padding", "6px")
                    ]
                }
            ]
        )
    )

    st.write("**Country:**", st.session_state.review_country)
    st.write("**Company:**", st.session_state.review_company)
    st.write("**Email:**", st.session_state.review_email)

    st.write("")  # spacing
    st.write(styled)

    st.write("")  # spacing

    # --------- DOWNLOAD AS EXCEL ----------
    buffer = io.BytesIO()
    excel_df = display_df.copy()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        excel_df.to_excel(writer, index=False, sheet_name="Forecast")
    buffer.seek(0)

    st.download_button(
        label="Download Forecast as Excel",
        data=buffer,
        file_name="forecast_review.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.write("")  # spacing

    # --------- ACTION BUTTONS ----------
    col_back, col_submit = st.columns(2)

    with col_back:
        if st.button("Back to Edit"):
            st.session_state.page = "form"
            st.experimental_rerun()

    with col_submit:
        if st.button("Submit Forecast"):
            # Final submission to CSV and Google Sheet
            submission_df = st.session_state.review_df.copy()
            submission_df["User ID"] = st.session_state.user_id
            submission_df["Email"] = st.session_state.review_email
            submission_df["Country"] = st.session_state.review_country
            submission_df["Company"] = st.session_state.review_company

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
                    entry.get("User ID", ""),
                    entry.get("Email", ""),
                    entry.get("Country", ""),
                    entry.get("Company", ""),
                    entry.get("group", ""),
                    entry.get("name", ""),
                    entry.get("code", ""),
                    entry.get("description", ""),
                    int(entry.get("January", 0)),
                    int(entry.get("February", 0)),
                    int(entry.get("March", 0)),
                    int(entry.get("April", 0)),
                    int(entry.get("May", 0)),
                    int(entry.get("June", 0)),
                    int(entry.get("July", 0)),
                    int(entry.get("August", 0)),
                    int(entry.get("September", 0)),
                    int(entry.get("October", 0)),
                    int(entry.get("November", 0)),
                    int(entry.get("December", 0)),
                    int(entry.get("total", 0)),
                ])

            # Reset state after submit
            st.session_state.product_entries = []
            st.session_state.review_df = None
            st.session_state.page = "form"

            st.success("Forecast submitted successfully. Thank you.")
            st.balloons()
            st.experimental_rerun()


# -------------------------------------------------
#   MAIN RENDER
# -------------------------------------------------
if st.session_state.page == "form":
    render_form_page()
else:
    render_review_page()