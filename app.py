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

# ------------------------------------------------------------------
# BASIC PAGE CONFIG
# ------------------------------------------------------------------
st.set_page_config(page_title="Product Forecast Form", layout="centered")

# ------------------------------------------------------------------
# GLOBAL STYLE (Montserrat + button color)
# ------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
    }

    /* NephroCan red buttons */
    .stButton>button {
        background-color: #A6192E !important;
        color: white !important;
        border-radius: 6px !important;
        border: none !important;
        font-weight: 500 !important;
        padding: 0.4rem 1.2rem !important;
    }
    .stButton>button:hover {
        opacity: 0.9 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------
# GOOGLE SHEETS SETUP
# ------------------------------------------------------------------
SHEET_NAME = "ProductForecast"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1  # first worksheet

# ------------------------------------------------------------------
# LOAD LOGO
# ------------------------------------------------------------------
def get_base64_image(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


logo_base64 = get_base64_image("logo.png")

def render_header(title: str = "Product Forecast Form"):
    st.markdown(
        f"""
        <div style="text-align: center; padding: 15px; background-color: white; border-radius: 12px; margin-bottom: 25px;">
            <img src="data:image/png;base64,{logo_base64}" width="160" style="margin-bottom:10px;">
            <h1 style="color: black;">{title}</h1>
            <p style="color: black; margin-top:-10px;">Nephrocan Forecast Portal</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------
# LOAD PRODUCT DATA
# ------------------------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_csv("product list.csv")


df = load_data()

# ------------------------------------------------------------------
# INITIALISE SESSION STATE
# ------------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

if "page" not in st.session_state:
    st.session_state.page = "form"  # "form" or "review"


# ------------------------------------------------------------------
# FORM PAGE
# ------------------------------------------------------------------
def render_form_page():
    render_header("Product Forecast Form")

    # ----- COUNTRY -----
    countries = sorted([c.name for c in pycountry.countries]) + ["Other"]
    country_choice = st.selectbox("Select Country", countries, key="country_choice")
    country = country_choice
    if country_choice == "Other":
        country_other = st.text_input("Please type your country name", key="country_other")
        if country_other.strip():
            country = country_other.strip()
    st.session_state.country = country

    # ----- USER INFO -----
    st.markdown("### User Information")
    email = st.text_input("Enter Your Email Address", key="email")
    company = st.text_input("Company Name", key="company")

    st.markdown("---")
    st.subheader("Product Forecast")

    # ----- ADD ROW BUTTON -----
    if st.button("Add Product Forecast Row", key="add_row"):
        st.session_state.product_entries.append(
            {
                "group": None,
                "name": None,
                "detail": None,
                "code": None,
                **{
                    month: 0
                    for month in [
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                    ]
                },
                "total": 0,
            }
        )

    # ----- DISPLAY PRODUCT ROWS -----
    for i, entry in enumerate(st.session_state.product_entries):
        st.markdown(f"#### Product {i+1}")

        col1, col2 = st.columns(2)

        # PRODUCT GROUP OPTIONS (no NaN)
        product_groups = [g for g in df["Product Group"].unique() if str(g) != "nan"]

        with col1:
            group = st.selectbox(
                f"Product Group {i+1}",
                product_groups,
                key=f"group_{i}",
            )

        filtered_df = df[df["Product Group"] == group]

        names = filtered_df["Product Name"].tolist()
        details = filtered_df["Description"].tolist()

        # Default state for this row
        if f"name_{i}" not in st.session_state:
            st.session_state[f"name_{i}"] = names[0]
        if f"detail_{i}" not in st.session_state:
            st.session_state[f"detail_{i}"] = details[0]
        if f"code_{i}" not in st.session_state:
            st.session_state[f"code_{i}"] = filtered_df.iloc[0]["PRODUCT CODE"]

        # --- callbacks to sync name & detail ---
        def on_name_change(row_index=i, df_filtered=filtered_df):
            selected_name = st.session_state[f"name_{row_index}"]
            row = df_filtered[df_filtered["Product Name"] == selected_name]
            if not row.empty:
                st.session_state[f"detail_{row_index}"] = row["Description"].values[0]
                st.session_state[f"code_{row_index}"] = row["PRODUCT CODE"].values[0]
                st.rerun()

        def on_detail_change(row_index=i, df_filtered=filtered_df):
            selected_detail = st.session_state[f"detail_{row_index}"]
            row = df_filtered[df_filtered["Description"] == selected_detail]
            if not row.empty:
                st.session_state[f"name_{row_index}"] = row["Product Name"].values[0]
                st.session_state[f"code_{row_index}"] = row["PRODUCT CODE"].values[0]
                st.rerun()

        with col2:
            st.selectbox(
                f"Product Name {i+1}",
                names,
                key=f"name_{i}",
                on_change=on_name_change,
            )

        # Large dropdown for details
        st.selectbox(
            f"Product Detail {i+1}",
            details,
            key=f"detail_{i}",
            on_change=on_detail_change,
            help="Choose detailed product description",
        )

        # Final values after any sync
        selected_name = st.session_state[f"name_{i}"]
        selected_detail = st.session_state[f"detail_{i}"]
        product_code = st.session_state[f"code_{i}"]  # hidden from user

        # ----- MONTHLY INPUTS -----
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        monthly_quantities = {}
        total = 0
        cols = st.columns(3)

        for idx, month in enumerate(months):
            with cols[idx % 3]:
                qty = st.number_input(
                    f"{month} {i+1}",
                    min_value=0,
                    key=f"{month}_{i}",
                )
                monthly_quantities[month] = qty
                total += qty

        st.write(f"**Total:** {total}")

        # Save this row into session state
        st.session_state.product_entries[i] = {
            "group": group,
            "name": selected_name,
            "detail": selected_detail,
            "code": product_code,
            **monthly_quantities,
            "total": total,
        }

    st.markdown("---")

    # ----- REVIEW BUTTON -----
    if st.button("Review Forecast", key="review_button"):
        if not email.strip():
            st.error("Please enter your email before reviewing.")
        elif not company.strip():
            st.error("Please enter a company name before reviewing.")
        elif not st.session_state.product_entries:
            st.error("Please add at least one product forecast row.")
        else:
            st.session_state.page = "review"
            st.rerun()


# ------------------------------------------------------------------
# REVIEW PAGE
# ------------------------------------------------------------------
def render_review_page():
    render_header("Review Your Forecast")

    country = st.session_state.get("country", "")
    company = st.session_state.get("company", "")
    email = st.session_state.get("email", "")

    st.markdown(f"**Country:** {country}")
    st.markdown(f"**Company:** {company}")
    st.markdown(f"**Email:** {email}")

    st.write("")
    entries = st.session_state.product_entries

    if not entries:
        st.warning("There are no forecast entries to review.")
        if st.button("Back to edit forecast"):
            st.session_state.page = "form"
            st.rerun()
        return

    review_df = pd.DataFrame(entries)

    display_cols = [
        "group",
        "name",
        "detail",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
        "total",
    ]

    pretty_df = review_df[display_cols].rename(
        columns={
            "group": "Product Group",
            "name": "Product Name",
            "detail": "Product Description",
            "total": "Total",
        }
    )

    st.write("")
    st.dataframe(pretty_df, use_container_width=True)

    # ----- DOWNLOAD AS EXCEL -----
    st.write("")
    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            pretty_df.to_excel(writer, index=False, sheet_name="Forecast")
        buffer.seek(0)

        st.download_button(
            label="Download Forecast as Excel",
            data=buffer,
            file_name="product_forecast.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except ModuleNotFoundError:
        st.error(
            "Excel export is not available because the 'xlsxwriter' package is not installed "
            "on the server. Please install it with 'pip install xlsxwriter'."
        )

    st.write("")
    col1, col2 = st.columns(2)

    # ----- BACK BUTTON -----
    with col1:
        if st.button("Back to edit forecast"):
            st.session_state.page = "form"
            st.rerun()

    # ----- SUBMIT BUTTON -----
    with col2:
        if st.button("Submit Forecast"):
            submission_df = review_df.copy()
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
                sheet.append_row(
                    [
                        "Timestamp",
                        "User ID",
                        "Email",
                        "Country",
                        "Company Name",
                        "Product Group",
                        "Product Name",
                        "Product Code",
                        "Description",
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                        "Total",
                    ]
                )

            # Upload rows to Google Sheets
            for _, entry in submission_df.iterrows():
                sheet.append_row(
                    [
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
                        int(entry["total"]),
                    ]
                )

            # Reset state
            st.session_state.product_entries = []
            st.success("Forecast submitted successfully. Thank you.")


# ------------------------------------------------------------------
# MAIN ROUTER
# ------------------------------------------------------------------
if st.session_state.page == "form":
    render_form_page()
else:
    render_review_page()