import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Product Forecast Form", layout="centered")

st.title("📈 Product Forecast Form")

# --- Load product list ---
@st.cache_data
def load_data():
    df = pd.read_csv("product list.csv")
    return df

df = load_data()

# --- Country selection ---
countries = [
    "Kyrgyzstan", "Morocco", "Romania", "Bangladesh", "Ukraine", "Maldives",
    "Germany", "Greece", "Lebanon", "Tanzania", "Botswana", "Syria",
    "South Africa", "Netherland", "Kenya", "Sudan", "Bulgaria", "Other"
]
country = st.selectbox("🌍 Select Country", countries)

# --- Company name ---
company = st.text_input("🏢 Company Name")

st.markdown("---")

st.subheader("🧾 Product Forecast")

# --- Product entry section ---
if "product_entries" not in st.session_state:
    st.session_state.product_entries = []

# Add new product row
if st.button("➕ Add Forecast Row"):
    st.session_state.product_entries.append({
        "group": None, "product": None,
        "q1": 0, "q2": 0, "q3": 0, "q4": 0,
        "code": None, "description": None
    })

# --- Display product selection rows ---
for i, entry in enumerate(st.session_state.product_entries):
    st.markdown(f"### 🔹 Product #{i+1}")

    col1, col2 = st.columns(2)
    with col1:
        group = st.selectbox(
            f"Product Group {i+1}",
            df["Product Group"].unique(),
            key=f"group_{i}"
        )
    with col2:
        filtered_df = df[df["Product Group"] == group]
        product = st.selectbox(
            f"Product Name {i+1}",
            filtered_df["Product Name"].unique(),
            key=f"product_{i}"
        )

    # --- Show product details (code + description) ---
    details = filtered_df[filtered_df["Product Name"] == product].iloc[0]
    st.write(f"**Product Code:** {details['PRODUCT CODE']}")
    st.write(f"**Description:** {details['Description']}")

    # --- Quarterly forecast inputs ---
    st.markdown("#### 📦 Forecast Quantities per Quarter")
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        q1_val = st.number_input("Q1", min_value=0, key=f"q1_{i}")
    with q2:
        q2_val = st.number_input("Q2", min_value=0, key=f"q2_{i}")
    with q3:
        q3_val = st.number_input("Q3", min_value=0, key=f"q3_{i}")
    with q4:
        q4_val = st.number_input("Q4", min_value=0, key=f"q4_{i}")

    total = q1_val + q2_val + q3_val + q4_val
    st.info(f"**Total Forecast Quantity:** {total}")

    st.session_state.product_entries[i].update({
        "country": country,
        "company": company,
        "group": group,
        "product": product,
        "code": details["PRODUCT CODE"],
        "description": details["Description"],
        "q1": q1_val, "q2": q2_val, "q3": q3_val, "q4": q4_val,
        "total": total
    })

    st.markdown("---")

# --- Submit Forecast ---
if st.button("✅ Submit Forecast"):
    if not company:
        st.error("Please enter a company name before submitting.")
    elif not st.session_state.product_entries:
        st.error("Please add at least one product forecast row.")
    else:
        # Save submission to a CSV file
        submission_df = pd.DataFrame(st.session_state.product_entries)

        file_path = "forecast_submissions.csv"

        # If file exists, append; otherwise, create new
        if os.path.exists(file_path):
            existing = pd.read_csv(file_path)
            updated = pd.concat([existing, submission_df], ignore_index=True)
            updated.to_csv(file_path, index=False)
        else:
            submission_df.to_csv(file_path, index=False)

        # Clear session entries
        st.session_state.product_entries = []

        st.success("✅ Forecast submitted successfully! Thank you.")