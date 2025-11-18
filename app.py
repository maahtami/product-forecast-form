import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import base64
import uuid
import pycountry  # to list all countries dynamically

# --- Add Google Font (Montserrat) ---
st.markdown(
    """
    <style>
    @import url('https://fonts.google.com/specimen/Montserrat?preview.text=Whereas%20recognition%20of%20the%20inherent%20dignity');
    body {
        font-family: 'Montserrat', sans-serif;
        color: black;  /* Ensures black text color throughout */
    }
    </style>
    """,
    unsafe_allow_html=True
)
# --- Google Sheets setup ---
SHEET_NAME = "ProductForecast"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1  # first worksheet

# --- Streamlit page setup ---
st.set_page_config(page_title="Product Forecast Form", layout="centered")

# --- Load and encode logo as base64 ---
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

logo_base64 = get_base64_image("logo.png")

# --- Custom header with logo and white background ---
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

# --- Generate unique user ID (hidden) ---
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]

# --- Load product data ---
@st.cache_data
def load_data():
    return pd.read_csv("product list.csv")

df = load_data()

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

# --- Initialize session state ---
if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

# --- Add forecast row button ---
if st.button("Add Product Forecast Row"):
    st.session_state.product_entries.append({
        "group": None,
        "name": None,
        "code": None,
        "description": None,
        **{month: 0 for month in [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]},
        "total": 0
    })

# --- Display product rows ---
for i, entry in enumerate(st.session_state.product_entries):
    st.markdown(f"#### Product {i+1}")
    col1, col2 = st.columns(2)

    # --- Product Group selection ---
    # Directly specify the allowed product groups
    product_groups = ["Dialyzer", "Bloodline", "Powder", "Needle", "Machinery"]

    with col1:
        group = st.selectbox(
            f"Product Group {i+1}",
            product_groups,  # List of specific product groups
            key=f"group_{i}"
        )

    with col2:
        filtered_df = df[df["Product Group"] == group]
        name = st.selectbox(
            f"Product Name {i+1}",
            filtered_df["Product Name"].unique(),
            key=f"name_{i}"
        )

    # Retrieve product details
    details_row = filtered_df.loc[filtered_df["Product Name"] == name].iloc[0]
    product_code = details_row["PRODUCT CODE"]
    description = details_row["Description"]

    st.caption(f"**Code:** {product_code}  •  **Details:** {description}")

    # Monthly inputs
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    monthly_quantities = {}
    total = 0
    cols = st.columns(3)
    for idx, month in enumerate(months):
        with cols[idx % 3]:
            qty = st.number_input(f"{month} {i+1}", min_value=0, key=f"{month}_{i}")
            monthly_quantities[month] = qty
            total += qty

    st.write(f"**Total:** {total}")

    st.session_state.product_entries[i] = {
        "group": group,
        "name": name,
        "code": product_code,
        "description": description,
        **monthly_quantities,
        "total": total
    }

st.markdown("---")

# --- Submit Forecast ---
if st.button("Submit Forecast"):
    if not email.strip():
        st.error("Please enter your email before submitting.")
    elif not company:
        st.error("Please enter a company name before submitting.")
    elif not st.session_state.product_entries:
        st.error("Please add at least one product forecast row.")
    else:
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
                country,
                company,
                entry["group"],
                entry["name"],
                entry["code"],
                entry["description"],
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

        st.session_state.product_entries = []
        st.success("✅ Forecast submitted successfully! Thank you.")
        st.balloons()