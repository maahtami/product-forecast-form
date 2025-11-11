import streamlit as st
import pandas as pd
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from PIL import Image

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

st.markdown(
    """
    <div style="text-align: center;">
        <img src="logo.png" width="180">
        <h1>📊 Product Forecast Form</h1>
    </div>
    """,
    unsafe_allow_html=True
)

st.title("📊 Product Forecast Form")



# --- Load product data ---
@st.cache_data
def load_data():
    return pd.read_csv("product list.csv")

df = load_data()

# --- Country selection ---
countries = [
    "Kyrgyzstan", "Morocco", "Romania", "Bangladesh", "Ukraine", "Maldives",
    "Germany", "Greece", "Lebanon", "Tanzania", "Botswana", "Syria",
    "South Africa", "Netherland", "Kenya", "Sudan", "Bulgaria", "Other"
]

country_choice = st.selectbox("🌍 Select Country", countries)
country = country_choice
if country_choice == "Other":
    country_other = st.text_input("✍️ Please type your country name")
    if country_other.strip():
        country = country_other.strip()

# --- Company name ---
company = st.text_input("🏢 Company Name")

st.markdown("---")
st.subheader("🧾 Product Forecast")

# --- Initialize session state ---
if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

# --- Add forecast row button ---
if st.button("➕ Add Product Forecast Row"):
    st.session_state.product_entries.append({
        "group": None,
        "name": None,
        "code": None,
        "description": None,
        "q1": 0, "q2": 0, "q3": 0, "q4": 0,
        "total": 0
    })

# --- Display product rows ---
for i, entry in enumerate(st.session_state.product_entries):
    st.markdown(f"#### Product {i+1}")
    col1, col2 = st.columns(2)
    with col1:
        group = st.selectbox(
            f"Product Group {i+1}",
            df["Product Group"].unique(),
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

    # Show details to the user
    st.caption(f"**Code:** {product_code}  •  **Details:** {description}")

    # Quantity inputs
    q1 = st.number_input(f"Q1 Quantity {i+1}", min_value=0, key=f"q1_{i}")
    q2 = st.number_input(f"Q2 Quantity {i+1}", min_value=0, key=f"q2_{i}")
    q3 = st.number_input(f"Q3 Quantity {i+1}", min_value=0, key=f"q3_{i}")
    q4 = st.number_input(f"Q4 Quantity {i+1}", min_value=0, key=f"q4_{i}")
    total = q1 + q2 + q3 + q4
    st.write(f"**Total:** {total}")

    st.session_state.product_entries[i] = {
        "group": group,
        "name": name,
        "code": product_code,
        "description": description,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "q4": q4,
        "total": total
    }

st.markdown("---")

# --- Submit Forecast ---
if st.button("✅ Submit Forecast"):
    if not company:
        st.error("Please enter a company name before submitting.")
    elif not st.session_state.product_entries:
        st.error("Please add at least one product forecast row.")
    else:
        # Convert entries to DataFrame
        submission_df = pd.DataFrame(st.session_state.product_entries)
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
                "Timestamp", "Country", "Company Name",
                "Product Group", "Product Name", "Product Code", "Description",
                "Q1", "Q2", "Q3", "Q4", "Total"
            ])

        # Save to Google Sheet
        for _, entry in submission_df.iterrows():
            sheet.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Timestamp
                country,
                company,
                entry["group"],
                entry["name"],
                entry["code"],
                entry["description"],
                int(entry["q1"]),
                int(entry["q2"]),
                int(entry["q3"]),
                int(entry["q4"]),
                int(entry["total"])
            ])

        # Clear state
        st.session_state.product_entries = []
        st.success("✅ Forecast submitted successfully! Thank you.")