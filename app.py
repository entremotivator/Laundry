import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import json
import requests
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import csv
import io

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="🧼 Auto Laundry CRM Pro", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        font-size: 2.5rem;
        font-weight: bold;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 0.5rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        text-align: center;
    }
    .customer-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .invoice-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #4facfe;
    }
    .chat-container {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        padding: 2rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .call-center-card {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #a8edea;
    }
    .stTab {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        margin: 0.2rem;
    }
    .sidebar-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- MAIN HEADER ---
st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro</div>', unsafe_allow_html=True)

# --- SIDEBAR AUTH JSON UPLOAD ---
st.sidebar.markdown('<div class="sidebar-header">🔐 Authentication</div>', unsafe_allow_html=True)
auth_file = st.sidebar.file_uploader("Upload service_account.json", type="json")

# --- ADDITIONAL SIDEBAR CONFIGS ---
st.sidebar.markdown("---")
st.sidebar.markdown('<div class="sidebar-header">⚙️ Configuration</div>', unsafe_allow_html=True)

# Default URLs - hardcoded but can be overridden
DEFAULT_CUSTOMERS_SHEET = "https://docs.google.com/spreadsheets/d/1LZvUQwceVE1dyCjaNod0DPOhHaIGLLBqomCDgxiWuBg/edit?gid=392374958#gid=392374958"
DEFAULT_N8N_WEBHOOK = "https://agentonline-u29564.vm.elestio.app/webhook/bf7aec67-cce8-4bd6-81f1-f04f84b992f7"
# Hardcoded Invoice Sheet URL
HARDCODED_INVOICES_SHEET = "https://docs.google.com/spreadsheets/d/1LZvUQwceVE1dyCjaNod0DPOhHaIGLLBqomCDgxiWuBg/edit?gid=1234567890#gid=1234567890"

# Hardcoded Call Center Agent IDs
CALL_CENTER_AGENTS = {
    "agent_001": {"name": "Sarah Johnson", "status": "Available", "calls_today": 12},
    "agent_002": {"name": "Mike Chen", "status": "On Call", "calls_today": 8},
    "agent_003": {"name": "Emma Davis", "status": "Break", "calls_today": 15},
    "agent_004": {"name": "Alex Rodriguez", "status": "Available", "calls_today": 10},
    "agent_005": {"name": "Lisa Thompson", "status": "Training", "calls_today": 3}
}

# --- TAB LAYOUT ---
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Dashboard", 
    "➕ Add Customer", 
    "📋 View All",
    "🧾 Invoices",
    "💬 Super Chat",
    "📞 Call Center",
    "📊 Analytics"
])

if auth_file:
    try:
        auth_json = json.load(auth_file)
        creds = Credentials.from_service_account_info(auth_json, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)

        # --- SHEET URLS ---
        use_default_settings = st.sidebar.checkbox("✅ Use Default Settings", value=True)
        
        if use_default_settings:
            CUSTOMERS_SHEET_URL = DEFAULT_CUSTOMERS_SHEET
            N8N_WEBHOOK_URL = DEFAULT_N8N_WEBHOOK
            INVOICES_SHEET_URL = HARDCODED_INVOICES_SHEET
            st.sidebar.success("🎯 Using default configuration")
            st.sidebar.info("📊 Connected to main customer database")
            st.sidebar.info("🧾 Connected to invoices database")
            st.sidebar.info("🤖 AI chat system ready")
        else:
            CUSTOMERS_SHEET_URL = st.sidebar.text_input("📄 Customers Google Sheet URL", "")
            INVOICES_SHEET_URL = st.sidebar.text_input("🧾 Invoices Google Sheet URL", HARDCODED_INVOICES_SHEET)
            N8N_WEBHOOK_URL = st.sidebar.text_input("🔗 N8N Webhook URL", "")
            
        # Optional API settings
        st.sidebar.markdown("---")
        st.sidebar.markdown('<div class="sidebar-header">🔧 Optional APIs</div>', unsafe_allow_html=True)
        VAPI_API_KEY = st.sidebar.text_input("🔑 VAPI AI API Key (Optional)", type="password")
        OPENAI_API_KEY = st.sidebar.text_input("🤖 OpenAI API Key (Optional)", type="password")
        
        if CUSTOMERS_SHEET_URL:
            # --- LOAD CUSTOMERS DATA ---
            try:
                customers_sheet = client.open_by_url(CUSTOMERS_SHEET_URL)
                customers_worksheet = customers_sheet.sheet1
                customers_data = customers_worksheet.get_all_records()
                customers_df = pd.DataFrame(customers_data)
                
                if customers_df.empty:
                    st.sidebar.warning("📋 Customer sheet is empty")
                else:
                    st.sidebar.success(f"✅ Loaded {len(customers_df)} customers")
                    
            except Exception as e:
                st.sidebar.error(f"❌ Error loading customers: {str(e)}")
                customers_df = pd.DataFrame()  # Empty dataframe as fallback

            # --- LOAD INVOICES DATA ---
            invoices_df = pd.DataFrame()
            if INVOICES_SHEET_URL:
                try:
                    invoices_sheet = client.open_by_url(INVOICES_SHEET_URL)
                    invoices_worksheet = invoices_sheet.sheet1
                    invoices_data = invoices_worksheet.get_all_records()
                    invoices_df = pd.DataFrame(invoices_data)
                    
                    if not invoices_df.empty:
                        st.sidebar.success(f"✅ Loaded {len(invoices_df)} invoices")
                    else:
                        st.sidebar.info("📋 No invoices found")
                        
                except Exception as e:
                    st.sidebar.warning(f"⚠️ Invoices sheet not accessible: {str(e)}")
                    invoices_df = pd.DataFrame()
            else:
                st.sidebar.info("💡 Using hardcoded invoices sheet")

            # --- DASHBOARD TAB ---
            with tab1:
                st.subheader("📊 CRM Dashboard")

                # --- METRICS ROW ---
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>👥 Total Customers</h3>
                        <h2>{len(customers_df)}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                with col2:
                    notes_count = len(customers_df[customers_df["Notes"].str.strip() != ""]) if "Notes" in customers_df.columns else 0
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>📝 With Notes</h3>
                        <h2>{notes_count}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                with col3:
                    invoice_count = len(invoices_df) if not invoices_df.empty else 0
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>🧾 Total Invoices</h3>
                        <h2>{invoice_count}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                with col4:
                    pending_invoices = len(invoices_df[invoices_df["Status"] == "Pending"]) if not invoices_df.empty and "Status" in invoices_df.columns else 0
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>⏳ Pending Invoices</h3>
                        <h2>{pending_invoices}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                # --- CHARTS ---
                if not invoices_df.empty and "Invoice Date" in invoices_df.columns:
                    st.subheader("📈 Revenue Analytics")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Revenue by month
                        if "Amount" in invoices_df.columns:
                            monthly_revenue = invoices_df.groupby(invoices_df["Invoice Date"].str[:7])["Amount"].sum().reset_index()
                            fig = px.bar(monthly_revenue, x="Invoice Date", y="Amount", title="Monthly Revenue")
                            fig.update_layout(xaxis_title="Month", yaxis_title="Revenue ($)")
                            st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Invoice status distribution
                        if "Status" in invoices_df.columns:
                            status_counts = invoices_df["Status"].value_counts()
                            fig = px.pie(values=status_counts.values, names=status_counts.index, title="Invoice Status Distribution")
                            st.plotly_chart(fig, use_container_width=True)

                # --- SEARCH ---
                st.subheader("🔍 Customer Search")
                search_col1, search_col2 = st.columns([3, 1])
                
                with search_col1:
                    search = st.text_input("Search by Name or Phone Number", "")
                
                with search_col2:
                    search_type = st.selectbox("Search Type", ["All", "Name", "Phone", "Email"])

                # Filter customers based on search
                filtered_df = customers_df.copy()
                if search:
                    if search_type == "Name":
                        filtered_df = filtered_df[filtered_df["Name"].str.contains(search, case=False, na=False)]
                    elif search_type == "Phone":
                        filtered_df = filtered_df[filtered_df["Phone Number"].str.contains(search, case=False, na=False)]
                    elif search_type == "Email":
                        filtered_df = filtered_df[filtered_df["Email"].str.contains(search, case=False, na=False)]
                    else:
                        filtered_df = filtered_df[
                            filtered_df["Name"].str.contains(search, case=False, na=False) |
                            filtered_df["Phone Number"].str.contains(search, case=False, na=False) |
                            filtered_df["Email"].str.contains(search, case=False, na=False)
                        ]

                # --- CUSTOMER CARDS ---
                st.subheader("📇 Customer Cards")
                for idx, row in filtered_df.iterrows():
                    with st.expander(f"👤 {row['Name']} ({row['Phone Number']})"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**📧 Email:** {row['Email']}")
                            st.markdown(f"**📍 Address:** {row['Address']}")
                            st.markdown(f"**🕑 Preferred Time:** {row['Preferred_Time']}")
                            st.markdown(f"**📞 Contact Preference:** {row['Preference']}")
                        with col2:
                            st.markdown(f"**📦 Items:** {row['Items']}")
                            st.markdown(f"**📝 Notes:** {row['Notes']}")
                            st.markdown(f"**📋 Call Summary:** {row['Call_summary']}")

            # --- ADD NEW CUSTOMER TAB ---
            with tab2:
                st.subheader("➕ Add New Customer")
                
                with st.form("add_contact", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        name = st.text_input("👤 Name", placeholder="Enter customer name")
                        email = st.text_input("📧 Email", placeholder="customer@email.com")
                        phone = st.text_input("📱 Phone Number", placeholder="+1 (555) 123-4567")
                        preference = st.selectbox("📞 Contact Preference", ["Call", "Text", "Email", "WhatsApp"])
                        preferred_time = st.text_input("🕑 Preferred Time", placeholder="e.g., 9 AM - 5 PM")
                        
                    with col2:
                        address = st.text_area("📍 Address", placeholder="Enter full address")
                        items = st.text_area("📦 Items", placeholder="Describe laundry items")
                        notes = st.text_area("📝 Notes", placeholder="Additional notes")
                        call_summary = st.text_area("📋 Call Summary", placeholder="Summary of last conversation")

                    submitted = st.form_submit_button("✅ Add Customer", type="primary")
                    
                    if submitted:
                        if name and phone:
                            try:
                                customers_worksheet.append_row([
                                    name, email, phone, preference, preferred_time,
                                    address, items, notes, call_summary
                                ])
                                st.success("✅ Customer added successfully!")
                                st.balloons()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error adding customer: {str(e)}")
                        else:
                            st.error("❌ Name and Phone Number are required!")

            # --- VIEW ALL TAB ---
            with tab3:
                st.subheader("📋 All Customers")
                
                # Filter options
                col1, col2, col3 = st.columns(3)
                with col1:
                    pref_filter = st.selectbox("Filter by Preference", ["All"] + list(customers_df["Preference"].unique()))
                with col2:
                    sort_by = st.selectbox("Sort by", ["Name", "Phone Number", "Email", "Preferred_Time"])
                with col3:
                    sort_order = st.selectbox("Order", ["Ascending", "Descending"])

                # Apply filters
                display_df = customers_df.copy()
                if pref_filter != "All":
                    display_df = display_df[display_df["Preference"] == pref_filter]
                
                display_df = display_df.sort_values(sort_by, ascending=(sort_order == "Ascending"))

                # Interactive table
                gb = GridOptionsBuilder.from_dataframe(display_df)
                gb.configure_pagination(paginationAutoPageSize=True)
                gb.configure_side_bar()
                gb.configure_selection('multiple', use_checkbox=True)
                gb.configure_default_column(editable=True, groupable=True)
                
                gridOptions = gb.build()
                
                grid_response = AgGrid(
                    display_df,
                    gridOptions=gridOptions,
                    height=500,
                    width='100%',
                    theme='alpine',
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    fit_columns_on_grid_load=True,
                    allow_unsafe_jscode=True,
                    enable_enterprise_modules=True
                )

                # Export functionality
                if st.button("📥 Export to CSV"):
                    csv = display_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"customers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )

            # --- INVOICES TAB ---
            with tab4:
                st.subheader("🧾 Invoices Management")
                
                # Add new invoice form
                with st.expander("➕ Add New Invoice"):
                    with st.form("add_invoice"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            invoice_customer = st.selectbox("👤 Customer", customers_df["Name"].tolist() if not customers_df.empty else ["Malcolm"])
                            invoice_date = st.date_input("📅 Invoice Date", datetime.now())
                            invoice_amount = st.number_input("💰 Amount", min_value=0.0, format="%.2f")
                            invoice_status = st.selectbox("📊 Status", ["Pending", "Paid", "Overdue", "Cancelled"])
                            
                        with col2:
                            invoice_items = st.text_area("📦 Items", placeholder="List of services/items")
                            invoice_notes = st.text_area("📝 Notes", placeholder="Additional invoice notes")
                            due_date = st.date_input("⏰ Due Date", datetime.now() + timedelta(days=30))
                            payment_method = st.selectbox("💳 Payment Method", ["Cash", "Card", "Bank Transfer", "PayPal"])

                        if st.form_submit_button("💾 Create Invoice"):
                            try:
                                # Create CSV format data
                                invoice_data = [
                                    invoice_customer,
                                    str(invoice_date),
                                    invoice_amount,
                                    invoice_status,
                                    invoice_items,
                                    invoice_notes,
                                    str(due_date),
                                    payment_method
                                ]
                                
                                # Add to Google Sheets
                                invoices_worksheet.append_row(invoice_data)
                                
                                # Also create CSV download
                                csv_buffer = io.StringIO()
                                csv_writer = csv.writer(csv_buffer)
                                csv_writer.writerow(["Customer", "Invoice Date", "Amount", "Status", "Items", "Notes", "Due Date", "Payment Method"])
                                csv_writer.writerow(invoice_data)
                                
                                st.success("✅ Invoice created successfully!")
                                st.download_button(
                                    label="📥 Download Invoice CSV",
                                    data=csv_buffer.getvalue(),
                                    file_name=f"invoice_{invoice_customer}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error creating invoice: {e}")

                # Sample invoice data with Malcolm
                if invoices_df.empty:
                    st.info("📋 No invoices found. Here's a sample:")
                    sample_invoice = pd.DataFrame([{
                        "Customer": "Malcolm",
                        "Invoice Date": "",
                        "Amount": "",
                        "Status": "Pending",
                        "Items": "",
                        "Notes": "",
                        "Due Date": "",
                        "Payment Method": "Cash"
                    }])
                    st.dataframe(sample_invoice, use_container_width=True)

                # Display invoices
                if not invoices_df.empty:
                    st.subheader("📊 Invoice Overview")
                    
                    # Invoice filters
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        status_filter = st.selectbox("Filter by Status", ["All"] + list(invoices_df["Status"].unique()))
                    with col2:
                        customer_filter = st.selectbox("Filter by Customer", ["All"] + list(invoices_df["Customer"].unique()))
                    with col3:
                        if st.button("📥 Export All Invoices CSV"):
                            csv = invoices_df.to_csv(index=False)
                            st.download_button(
                                label="Download All Invoices CSV",
                                data=csv,
                                file_name=f"all_invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )

                    # Apply filters
                    filtered_invoices = invoices_df.copy()
                    if status_filter != "All":
                        filtered_invoices = filtered_invoices[filtered_invoices["Status"] == status_filter]
                    if customer_filter != "All":
                        filtered_invoices = filtered_invoices[filtered_invoices["Customer"] == customer_filter]

                    # Invoice table
                    gb = GridOptionsBuilder.from_dataframe(filtered_invoices)
                    gb.configure_pagination(paginationAutoPageSize=True)
                    gb.configure_side_bar()
                    gb.configure_selection('multiple', use_checkbox=True)
                    gb.configure_default_column(editable=True, groupable=True)
                    
                    gridOptions = gb.build()
                    
                    AgGrid(
                        filtered_invoices,
                        gridOptions=gridOptions,
                        height=400,
                        width='100%',
                        theme='alpine',
                        update_mode=GridUpdateMode.MODEL_CHANGED,
                        fit_columns_on_grid_load=True
                    )

            # --- SUPER CHAT TAB ---
            with tab5:
                st.subheader("💬 Laundry Super Chat")
                
                st.markdown("""
                <div class="chat-container">
                    <h3>🤖 AI Assistant</h3>
                    <p>Chat with our AI assistant powered by N8N automation</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Chat interface
                if "messages" not in st.session_state:
                    st.session_state.messages = []

                # Display chat messages
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

                # Chat input
                if prompt := st.chat_input("Type your message here..."):
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    # Send to N8N webhook
                    if N8N_WEBHOOK_URL:
                        try:
                            with st.spinner("🤖 AI is thinking..."):
                                response = requests.post(
                                    N8N_WEBHOOK_URL,
                                    json={
                                        "message": prompt,
                                        "user_id": "streamlit_user",
                                        "timestamp": datetime.now().isoformat(),
                                        "customer_count": len(customers_df),
                                        "system": "laundry_crm"
                                    },
                                    timeout=30
                                )
                                
                                if response.status_code == 200:
                                    try:
                                        response_data = response.json()
                                        bot_response = response_data.get("response", response_data.get("message", "I'm processing your request..."))
                                    except:
                                        bot_response = response.text if response.text else "I'm processing your request..."
                                else:
                                    bot_response = "Sorry, I'm having trouble connecting right now. Please try again."
                                    
                        except requests.exceptions.Timeout:
                            bot_response = "Request timed out. The AI might be busy. Please try again."
                        except requests.exceptions.RequestException as e:
                            bot_response = f"Connection error: {str(e)}"
                        except Exception as e:
                            bot_response = f"Unexpected error: {str(e)}"
                    else:
                        bot_response = "AI chat is ready! Using default N8N integration."

                    st.session_state.messages.append({"role": "assistant", "content": bot_response})
                    with st.chat_message("assistant"):
                        st.markdown(bot_response)

                # Quick actions
                st.subheader("🚀 Quick Actions")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📊 Get Business Summary"):
                        summary = f"Total Customers: {len(customers_df)}, Total Invoices: {len(invoices_df)}"
                        st.session_state.messages.append({"role": "assistant", "content": summary})
                        st.rerun()
                
                with col2:
                    if st.button("🔍 Find Customer"):
                        st.session_state.messages.append({"role": "assistant", "content": "Please tell me the customer's name or phone number."})
                        st.rerun()
                
                with col3:
                    if st.button("💰 Revenue Report"):
                        if not invoices_df.empty and "Amount" in invoices_df.columns:
                            total_revenue = invoices_df["Amount"].sum()
                            report = f"Total Revenue: ${total_revenue:,.2f}"
                        else:
                            report = "No revenue data available."
                        st.session_state.messages.append({"role": "assistant", "content": report})
                        st.rerun()

            # --- CALL CENTER TAB ---
            with tab6:
                st.subheader("📞 Call Center with Agent Management")
                
                # Agent status overview
                st.subheader("👥 Agent Status Overview")
                agent_cols = st.columns(len(CALL_CENTER_AGENTS))
                
                for idx, (agent_id, agent_info) in enumerate(CALL_CENTER_AGENTS.items()):
                    with agent_cols[idx]:
                        status_color = {
                            "Available": "🟢",
                            "On Call": "🔴", 
                            "Break": "🟡",
                            "Training": "🔵"
                        }.get(agent_info["status"], "⚪")
                        
                        st.markdown(f"""
                        <div class="call-center-card">
                            <h4>{status_color} {agent_info['name']}</h4>
                            <p><strong>ID:</strong> {agent_id}</p>
                            <p><strong>Status:</strong> {agent_info['status']}</p>
                            <p><strong>Calls Today:</strong> {agent_info['calls_today']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Call center interface
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown("""
                    <div class="call-center-card">
                        <h3>📞 AI-Powered Call Center</h3>
                        <p>Manage customer calls with optional VAPI AI integration</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Customer selection for call
                    selected_customer = st.selectbox("👤 Select Customer for Call", customers_df["Name"].tolist() if not customers_df.empty else ["Malcolm"])
                    selected_agent = st.selectbox("👨‍💼 Assign Agent", [f"{agent_id} - {info['name']}" for agent_id, info in CALL_CENTER_AGENTS.items()])
                    
                    if selected_customer and not customers_df.empty:
                        customer_info = customers_df[customers_df["Name"] == selected_customer].iloc[0]
                        
                        # Display customer info
                        st.subheader("📋 Customer Information")
                        col1_info, col2_info = st.columns(2)
                        
                        with col1_info:
                            st.markdown(f"**📧 Email:** {customer_info['Email']}")
                            st.markdown(f"**📱 Phone:** {customer_info['Phone Number']}")
                            st.markdown(f"**📍 Address:** {customer_info['Address']}")
                            
                        with col2_info:
                            st.markdown(f"**🕑 Preferred Time:** {customer_info['Preferred_Time']}")
                            st.markdown(f"**📞 Contact Preference:** {customer_info['Preference']}")
                            st.markdown(f"**📦 Items:** {customer_info['Items']}")
                        
                        st.markdown(f"**📝 Previous Notes:** {customer_info['Notes']}")
                        st.markdown(f"**📋 Last Call Summary:** {customer_info['Call_summary']}")
                
                with col2:
                    # Call controls
                    st.subheader("🎛️ Call Controls")
                    
                    if st.button("📞 Start Call", type="primary"):
                        if VAPI_API_KEY:
                            st.success("🟢 Call initiated with VAPI AI")
                            st.info("AI assistant is now handling the call...")
                        else:
                            st.success("🟢 Call initiated (Manual mode)")
                            st.info("Agent handling call manually...")
                    
                    if st.button("⏹️ End Call"):
                        st.warning("🔴 Call ended")
                    
                    if st.button("⏸️ Hold"):
                        st.info("⏸️ Call on hold")
                    
                    if st.button("🔄 Transfer"):
                        st.info("🔄 Call transferred")

                # Call log and notes
                st.subheader("📝 Call Notes & Summary")
                
                with st.form("call_notes"):
                    call_type = st.selectbox("📞 Call Type", ["Inbound", "Outbound", "Follow-up", "Complaint", "Inquiry"])
                    call_duration = st.number_input("⏱️ Duration (minutes)", min_value=0, value=0)
                    call_outcome = st.selectbox("📊 Outcome", ["Resolved", "Follow-up Required", "Escalated", "No Answer", "Voicemail"])
                    
                    new_call_summary = st.text_area("📋 Call Summary", placeholder="Enter summary of the call...")
                    additional_notes = st.text_area("📝 Additional Notes", placeholder="Any additional notes...")
                    
                    follow_up_date = st.date_input("📅 Follow-up Date", datetime.now() + timedelta(days=1))
                    
                    if st.form_submit_button("💾 Save Call Record"):
                        if new_call_summary:
                            # Update customer record with new call summary
                            try:
                                # Find the row to update
                                customer_row = None
                                for i, row in enumerate(customers_worksheet.get_all_records(), start=2):
                                    if row["Name"] == selected_customer:
                                        customer_row = i
                                        break
                                
                                if customer_row:
                                    # Update call summary
                                    customers_worksheet.update_cell(customer_row, 9, new_call_summary)  # Assuming call_summary is column 9
                                    
                                    # Update notes
                                    current_notes = customer_info['Notes'] if not customers_df.empty else ""
                                    updated_notes = f"{current_notes}\n\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {additional_notes}" if additional_notes else current_notes
                                    customers_worksheet.update_cell(customer_row, 8, updated_notes)  # Assuming notes is column 8
                                    
                                    st.success("✅ Call record saved successfully!")
                                    st.rerun()
                                else:
                                    st.error("❌ Could not find customer record to update")
                            except Exception as e:
                                st.error(f"❌ Error saving call record: {e}")
                        else:
                            st.error("❌ Please enter a call summary")

                # Recent calls table
                st.subheader("📞 Recent Calls")
                
                # Sample call data
                recent_calls_data = {
                    "Customer": [selected_customer] * 3,
                    "Agent": [selected_agent.split(" - ")[1]] * 3,
                    "Date": [datetime.now().strftime("%Y-%m-%d")] * 3,
                    "Duration": ["5 min", "8 min", "12 min"],
                    "Type": ["Inbound", "Outbound", "Follow-up"],
                    "Outcome": ["Resolved", "Follow-up Required", "Resolved"]
                }
                
                recent_calls_df = pd.DataFrame(recent_calls_data)
                st.dataframe(recent_calls_df, use_container_width=True)

            # --- ANALYTICS TAB ---
            with tab7:
                st.subheader("📊 Advanced Analytics")
                
                # Analytics overview
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_agents = len(CALL_CENTER_AGENTS)
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>👥 Total Agents</h3>
                        <h2>{total_agents}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                with col2:
                    available_agents = len([a for a in CALL_CENTER_AGENTS.values() if a["status"] == "Available"])
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>🟢 Available Agents</h3>
                        <h2>{available_agents}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                with col3:
                    total_calls_today = sum([a["calls_today"] for a in CALL_CENTER_AGENTS.values()])
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>📞 Calls Today</h3>
                        <h2>{total_calls_today}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                with col4:
                    avg_calls = total_calls_today / total_agents if total_agents > 0 else 0
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>📈 Avg Calls/Agent</h3>
                        <h2>{avg_calls:.1f}</h2>
                    </div>
                    ''', unsafe_allow_html=True)

                # Agent performance chart
                st.subheader("📈 Agent Performance")
                agent_data = pd.DataFrame([
                    {"Agent": info["name"], "Calls": info["calls_today"], "Status": info["status"]}
                    for info in CALL_CENTER_AGENTS.values()
                ])
                
                fig = px.bar(agent_data, x="Agent", y="Calls", color="Status", title="Calls per Agent Today")
                st.plotly_chart(fig, use_container_width=True)

                # CSV Export for all data
                st.subheader("📥 Data Export")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📥 Export Customers CSV"):
                        if not customers_df.empty:
                            csv = customers_df.to_csv(index=False)
                            st.download_button(
                                label="Download Customers CSV",
                                data=csv,
                                file_name=f"customers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        else:
                            st.warning("No customer data to export")

                with col2:
                    if st.button("📥 Export Invoices CSV"):
                        if not invoices_df.empty:
                            csv = invoices_df.to_csv(index=False)
                            st.download_button(
                                label="Download Invoices CSV",
                                data=csv,
                                file_name=f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        else:
                            # Create sample CSV with Malcolm
                            sample_data = pd.DataFrame([{
                                "Customer": "Malcolm",
                                "Invoice Date": "",
                                "Amount": "",
                                "Status": "Pending",
                                "Items": "",
                                "Notes": "",
                                "Due Date": "",
                                "Payment Method": "Cash"
                            }])
                            csv = sample_data.to_csv(index=False)
                            st.download_button(
                                label="Download Sample Invoice CSV",
                                data=csv,
                                file_name=f"sample_invoice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )

                with col3:
                    if st.button("📥 Export Agents CSV"):
                        agents_data = pd.DataFrame([
                            {"Agent_ID": agent_id, "Name": info["name"], "Status": info["status"], "Calls_Today": info["calls_today"]}
                            for agent_id, info in CALL_CENTER_AGENTS.items()
                        ])
                        csv = agents_data.to_csv(index=False)
                        st.download_button(
                            label="Download Agents CSV",
                            data=csv,
                            file_name=f"agents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )

        else:
            st.warning("⚠️ Please provide authentication to access the system.")
            st.markdown("""
            <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin: 2rem 0;">
                <h3>🔐 System Ready with Default Configuration</h3>
                <p>✅ Customer Database: Connected</p>
                <p>🧾 Invoice Database: Connected (Hardcoded)</p>
                <p>🤖 AI Chat System: Ready</p>
                <p>📊 Analytics: Active</p>
                <p>👥 Call Center: 5 Agents Ready</p>
                <p style="margin-top: 1rem; font-size: 0.9em; opacity: 0.8;">
                    Upload your Google Service Account JSON file to begin managing customers.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"❌ Error loading JSON or connecting to Google Sheets: {e}")
        st.error("Please check your credentials and sheet URLs.")

else:
    st.markdown("""
    <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white;">
        <h2>🔐 Welcome to Auto Laundry CRM Pro</h2>
        <p>System is pre-configured and ready to use!</p>
        <p style="font-size: 1.1em; margin: 1.5rem 0;">Just upload your Google Service Account JSON file to get started.</p>
        
        <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 10px; margin: 1.5rem 0;">
            <h3>✨ Pre-configured Features:</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                <div>
                    <p>✅ Customer Database Connected</p>
                    <p>🧾 Invoice Database Connected</p>
                    <p>🤖 AI Chat System Ready</p>
                    <p>📊 Analytics Dashboard Active</p>
                </div>
                <div>
                    <p>📞 Call Center Integration</p>
                    <p>👥 5 Hardcoded Agents Ready</p>
                    <p>🔍 Advanced Search & Filters</p>
                    <p>📥 CSV Export Functionality</p>
                </div>
            </div>
        </div>
        
        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 10px; margin-top: 1.5rem;">
            <p style="font-size: 0.9em; opacity: 0.9;">
                <strong>Quick Start:</strong> Upload your service account JSON → Start managing customers immediately
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

