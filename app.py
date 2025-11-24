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
MONTH_LIST = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

NEPHRO_RED = "#A6192E"

# ---------------------------------------------------
# GLOBAL STYLE (Montserrat + buttons)
# ---------------------------------------------------
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600&display=swap');

/* Apply Montserrat everywhere */
html, body, [class*="css"] {{
    font-family: 'Montserrat', sans-serif;
}}

/* Do NOT force background or text color — respect dark / light mode */
body {{
    background: transparent !important;
    color: inherit !important;
}}

/* Buttons: Nephrocan Red */
button, .stButton > button {{
    background-color: {NEPHRO_RED} !important;
    color: white !important;
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
    border: none !important;
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
def load_data() -> pd.DataFrame:
    return pd.read_csv("product list.csv")


df_products = load_data()
df_products = df_products.dropna(subset=["Product Group"])

# ---------------------------------------------------
# SESSION STATE INITIALISATION
# ---------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "form"      # "form" or "review"

if "product_entries" not in st.session_state:
    st.session_state.product_entries = []   # list of dicts

if "email" not in st.session_state:
    st.session_state.email = ""

if "company" not in st.session_state:
    st.session_state.company = ""

if "country" not in st.session_state:
    st.session_state.country = ""

if "locked_rows" not in st.session_state:
    # number of rows whose group/name/detail are locked
    st.session_state.locked_rows = 0

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
        unsafe_allow_html=True,
    )

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
def ensure_entry_list_length():
    """Make sure product_entries has at least one row when needed."""
    if not st.session_state.product_entries:
        st.session_state.product_entries.append(
            {
                "group": None,
                "name": None,
                "detail": None,
                "code": None,
                **{m: 0 for m in MONTH_LIST},
                "total": 0,
            }
        )

def get_filtered_df(group: str) -> pd.DataFrame:
    return df_products[df_products["Product Group"] == group]

def find_row_index(filtered: pd.DataFrame, entry: dict) -> int:
    """
    Choose the best matching row index for a given entry (by code, then name, then detail).
    Returns an index from filtered.index.
    """
    if filtered.empty:
        raise ValueError("Filtered DataFrame is empty")

    # By product code first
    if entry.get("code") in filtered["PRODUCT CODE"].values:
        return filtered.index[filtered["PRODUCT CODE"] == entry["code"]][0]

    # Then by product name
    if entry.get("name") in filtered["Product Name"].values:
        return filtered.index[filtered["Product Name"] == entry["name"]][0]

    # Then by description
    if entry.get("detail") in filtered["Description"].values:
        return filtered.index[filtered["Description"] == entry["detail"]][0]

    # Fallback: first row
    return filtered.index[0]

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

    current_country = (
        st.session_state.country if st.session_state.country in countries else countries[0]
    )

    country_choice = st.selectbox(
        "Select Country",
        countries,
        index=countries.index(current_country),
    )

    if country_choice == "Other":
        country_text = st.text_input(
            "Please type your country name",
            st.session_state.country if st.session_state.country not in countries else "",
        )
        st.session_state.country = country_text.strip() or "Other"
    else:
        st.session_state.country = country_choice

    # ----------------------
    # USER INFO
    # ----------------------
    st.markdown("### User Information")
    st.session_state.email = st.text_input(
        "Enter Your Email Address",
        value=st.session_state.email,
        key="email_input",
    )
    st.session_state.company = st.text_input(
        "Company Name",
        value=st.session_state.company,
        key="company_input",
    )

    st.markdown("---")
    st.subheader("Product Forecast")

    # Guarantee list exists (optional)
    ensure_entry_list_length()

    # ----------------------
    # ADD ROW BUTTON
    # ----------------------
    if st.button("Add Product Forecast Row"):
        st.session_state.product_entries.append(
            {
                "group": None,
                "name": None,
                "detail": None,
                "code": None,
                **{m: 0 for m in MONTH_LIST},
                "total": 0,
            }
        )

    # ----------------------
    # PRODUCT ROWS
    # ----------------------
    for i, entry in enumerate(st.session_state.product_entries):
        st.markdown(f"#### Product {i + 1}")

        locked = i < st.session_state.locked_rows

        if locked:
            # Existing row after review: lock group, name, detail
            st.text(f"Product Group {i+1}: {entry.get('group', '')}")
            st.text(f"Product Name {i+1}: {entry.get('name', '')}")
            st.text(f"Product Detail {i+1}: {entry.get('detail', '')}")

            # Use stored values for months
            cols = st.columns(3)
            total = 0
            new_month_values = {}

            for idx, m in enumerate(MONTH_LIST):
                with cols[idx % 3]:
                    qty = st.number_input(
                        f"{m} ({i+1})",
                        min_value=0,
                        value=int(entry.get(m, 0)),
                        key=f"{m}_{i}",
                    )
                    new_month_values[m] = qty
                    total += qty

            st.write(f"**Total: {total}**")

            # Update only quantities and total
            st.session_state.product_entries[i].update(
                {**new_month_values, "total": total}
            )

        else:
            # Row is editable: group + linked name/detail
            col1, col2 = st.columns(2)

            # --- Product Group dropdown ---
            product_groups = sorted(df_products["Product Group"].unique().tolist())
            current_group = entry["group"] if entry["group"] in product_groups else product_groups[0]

            group = col1.selectbox(
                f"Product Group {i+1}",
                product_groups,
                index=product_groups.index(current_group),
                key=f"group_{i}",
            )

            filtered = get_filtered_df(group)

            if filtered.empty:
                st.warning("No products found for this group.")
                continue

            # All row indices in this group
            option_indices = list(filtered.index)

            # Choose default index based on entry
            default_row_idx = find_row_index(filtered, entry)

            # Canonical row index for this row
            canonical_key = f"row_idx_{i}"
            if canonical_key not in st.session_state:
                st.session_state[canonical_key] = default_row_idx

            prev_idx = st.session_state[canonical_key]
            if prev_idx not in option_indices:
                prev_idx = option_indices[0]
                st.session_state[canonical_key] = prev_idx

            # --- Name dropdown (options are row indices) ---
            selected_idx_name = col2.selectbox(
                f"Product Name {i+1}",
                option_indices,
                index=option_indices.index(prev_idx),
                key=f"name_idx_{i}",
                format_func=lambda idx: filtered.loc[idx, "Product Name"],
            )

            # --- Detail dropdown (also row indices, long text) ---
            selected_idx_detail = st.selectbox(
                f"Product Detail {i+1}",
                option_indices,
                index=option_indices.index(prev_idx),
                key=f"detail_idx_{i}",
                format_func=lambda idx: filtered.loc[idx, "Description"],
            )

            # Decide which control changed
            new_idx = prev_idx
            if selected_idx_name != prev_idx:
                new_idx = selected_idx_name
            elif selected_idx_detail != prev_idx:
                new_idx = selected_idx_detail

            st.session_state[canonical_key] = new_idx

            # Use final row index
            selected_row = filtered.loc[new_idx]

            group_value = group
            name_value = selected_row["Product Name"]
            detail_value = selected_row["Description"]
            code_value = selected_row["PRODUCT CODE"]

            # MONTH INPUTS
            cols = st.columns(3)
            total = 0
            new_month_values = {}

            for idx, m in enumerate(MONTH_LIST):
                with cols[idx % 3]:
                    qty = st.number_input(
                        f"{m} ({i+1})",
                        min_value=0,
                        value=int(entry.get(m, 0)),
                        key=f"{m}_{i}",
                    )
                    new_month_values[m] = qty
                    total += qty

            st.write(f"**Total: {total}**")

            # Save whole entry back
            st.session_state.product_entries[i] = {
                "group": group_value,
                "name": name_value,
                "detail": detail_value,
                "code": code_value,
                **new_month_values,
                "total": total,
            }

    st.markdown("---")

    # ----------------------
    # REVIEW BUTTON
    # ----------------------
    if st.button("Review Forecast"):
        # First basic validation
        if not st.session_state.email.strip():
            st.error("Please enter your email before reviewing.")
            return
        if not st.session_state.company.strip():
            st.error("Please enter a company name before reviewing.")
            return
        if not st.session_state.product_entries:
            st.error("Please add at least one product forecast row before reviewing.")
            return

        # From this moment, rows that exist become "locked"
        st.session_state.locked_rows = len(st.session_state.product_entries)
        st.session_state.page = "review"

# ---------------------------------------------------
# PAGE 2 — REVIEW PAGE
# ---------------------------------------------------
def render_review_page():
    render_header()

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
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("← Go Back & Edit"):
            # Go back, keep locked_rows as is
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

    # Ensure header exists
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
# PAGE ROUTING
# ---------------------------------------------------
if st.session_state.page == "form":
    render_form_page()
else:
    render_review_page()