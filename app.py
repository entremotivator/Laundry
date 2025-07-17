import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder
import json

# --- PAGE CONFIG ---
st.set_page_config(page_title="🧼 Auto Laundry CRM", layout="wide")
st.title("🧼 Auto Laundry CRM")

# --- SIDEBAR AUTH JSON UPLOAD ---
st.sidebar.header("🔐 Upload Google Auth JSON")
auth_file = st.sidebar.file_uploader("Upload service_account.json", type="json")

# --- HOME TAB LAYOUT ---
tab1, tab2, tab3 = st.tabs(["🏠 Overview", "➕ Add Customer", "📋 View All"])

if auth_file:
    try:
        auth_json = json.load(auth_file)
        creds = Credentials.from_service_account_info(auth_json, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)

        SHEET_URL = st.sidebar.text_input("📄 Google Sheet URL", "")
        if SHEET_URL:
            sheet = client.open_by_url(SHEET_URL)
            worksheet = sheet.sheet1
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)

            # --- OVERVIEW TAB ---
            with tab1:
                st.subheader("📊 CRM Dashboard Features")

                st.markdown("""
                **What You Can Do:**
                - 🔍 Search for customers by name or phone number  
                - 📇 View contact details in card format  
                - 📝 Add new customer records  
                - 📋 Browse full customer table with sorting and filtering  
                - 💾 Data is saved in real-time to Google Sheets  
                """)

                # --- SEARCH ---
                search = st.text_input("🔍 Search by Name or Phone Number", "")
                if search:
                    df = df[
                        df["Name"].str.contains(search, case=False) |
                        df["Phone Number"].str.contains(search, case=False)
                    ]

                # --- METRICS ---
                st.subheader("📈 CRM Summary")
                col1, col2 = st.columns(2)
                col1.metric("Total Customers", len(df))
                col2.metric("With Notes", len(df[df["Notes"].str.strip() != ""]))

                st.subheader("📇 Customer Cards")
                for idx, row in df.iterrows():
                    with st.expander(f"{row['Name']} ({row['Phone Number']})"):
                        st.markdown(f"**📧 Email:** {row['Email']}")
                        st.markdown(f"**📍 Address:** {row['Address']}")
                        st.markdown(f"**🕑 Preferred Time:** {row['Preferred_Time']}")
                        st.markdown(f"**📦 Items:** {row['Items']}")
                        st.markdown(f"**📞 Contact Preference:** {row['Preference']}")
                        st.markdown(f"**📝 Notes:** {row['Notes']}")
                        st.markdown(f"**📋 Call Summary:** {row['Call_summary']}")

            # --- ADD NEW TAB ---
            with tab2:
                st.subheader("➕ Add New Customer")
                with st.form("add_contact"):
                    col1, col2 = st.columns(2)
                    with col1:
                        name = st.text_input("Name")
                        email = st.text_input("Email")
                        phone = st.text_input("Phone Number")
                        preference = st.selectbox("Contact Preference", ["Call", "Text", "Email"])
                        preferred_time = st.text_input("Preferred Time")
                    with col2:
                        address = st.text_input("Address")
                        items = st.text_input("Items")
                        notes = st.text_area("Notes")
                        call_summary = st.text_area("Call Summary")

                    submitted = st.form_submit_button("Submit")
                    if submitted:
                        worksheet.append_row([
                            name, email, phone, preference, preferred_time,
                            address, items, notes, call_summary
                        ])
                        st.success("✅ Customer added!")
                        st.experimental_rerun()

            # --- TABLE VIEW TAB ---
            with tab3:
                st.subheader("📋 All Customers Table")
                gb = GridOptionsBuilder.from_dataframe(df)
                gb.configure_pagination()
                gb.configure_default_column(editable=False, groupable=True)
                grid_options = gb.build()
                AgGrid(df, gridOptions=grid_options, height=450, theme='streamlit')

        else:
            st.warning("Paste the Google Sheet URL in the sidebar to continue.")
    except Exception as e:
        st.error(f"❌ Error loading JSON or connecting to Google Sheets: {e}")
else:
    st.info("Please upload your Google Service Account JSON file from the sidebar.")
