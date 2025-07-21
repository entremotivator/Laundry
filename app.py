import streamlit as st
import pandas as pd
import numpy as np
import requests
import weasyprint
from vapi_python import Vapi
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import json
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import csv
import io
import hashlib
import threading
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="🧼 Auto Laundry CRM Pro", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- UTILITY FUNCTIONS USING ALL LIBRARIES ---
def calculate_analytics_with_numpy(data):
    """Use numpy for advanced analytics calculations"""
    if not data:
        return {}
    
    values = np.array([float(item.get('amount', 0)) for item in data])
    return {
        'mean': np.mean(values),
        'std': np.std(values),
        'median': np.median(values),
        'total': np.sum(values),
        'percentile_75': np.percentile(values, 75),
        'percentile_25': np.percentile(values, 25)
    }

def fetch_external_data_with_requests(url=None):
    """Use requests library for external API calls"""
    try:
        # Example API call (can be customized)
        if not url:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def generate_pdf_report_with_weasyprint(html_content, filename):
    """Use WeasyPrint to generate PDF reports"""
    try:
        # Create a simple HTML template
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>CRM Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1 {{ color: #2E86AB; }}
                .header {{ border-bottom: 2px solid #2E86AB; padding-bottom: 10px; }}
                .content {{ margin-top: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧼 Auto Laundry CRM Report</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <div class="content">
                {html_content}
            </div>
        </body>
        </html>
        """
        
        # Generate PDF using WeasyPrint
        pdf_path = f"/tmp/{filename}.pdf"
        weasyprint.HTML(string=html_template).write_pdf(pdf_path)
        return pdf_path
    except Exception as e:
        return f"Error generating PDF: {str(e)}"

def process_dataframe_with_pandas(data):
    """Use pandas for advanced data processing"""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # Add calculated columns using pandas
    if 'amount' in df.columns:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df['amount_category'] = pd.cut(df['amount'], 
                                     bins=[0, 50, 100, 200, float('inf')], 
                                     labels=['Low', 'Medium', 'High', 'Premium'])
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['month'] = df['date'].dt.month
        df['year'] = df['date'].dt.year
        df['day_of_week'] = df['date'].dt.day_name()
    
    return df

# --- DEMO ACCOUNTS ---
DEMO_ACCOUNTS = {
    "admin": {"password": "admin123", "role": "Admin", "team": "Management", "name": "John Admin"},
    "manager1": {"password": "manager123", "role": "Manager", "team": "Operations", "name": "Sarah Manager"},
    "agent1": {"password": "agent123", "role": "Agent", "team": "Customer Service", "name": "Mike Agent"},
    "supervisor1": {"password": "super123", "role": "Supervisor", "team": "Quality Control", "name": "Emma Supervisor"},
    "demo": {"password": "demo123", "role": "Demo User", "team": "Demo", "name": "Demo User"}
}

# --- TEAM STRUCTURE ---
TEAM_STRUCTURE = {
    "Management": {
        "team_lead": "John Admin",
        "members": [
            {"name": "John Admin", "role": "Admin", "status": "Active", "login": "admin"},
            {"name": "Lisa Director", "role": "Director", "status": "Active", "login": "director1"},
            {"name": "Robert VP", "role": "Vice President", "status": "Active", "login": "vp1"},
            {"name": "Maria CFO", "role": "CFO", "status": "Active", "login": "cfo1"},
            {"name": "David CTO", "role": "CTO", "status": "Active", "login": "cto1"}
        ]
    },
    "Operations": {
        "team_lead": "Sarah Manager",
        "members": [
            {"name": "Sarah Manager", "role": "Operations Manager", "status": "Active", "login": "manager1"},
            {"name": "Tom Operator", "role": "Senior Operator", "status": "Active", "login": "op1"},
            {"name": "Jenny Coordinator", "role": "Coordinator", "status": "Active", "login": "coord1"},
            {"name": "Paul Scheduler", "role": "Scheduler", "status": "Active", "login": "sched1"},
            {"name": "Anna Logistics", "role": "Logistics", "status": "Active", "login": "log1"}
        ]
    },
    "Customer Service": {
        "team_lead": "Mike Agent",
        "members": [
            {"name": "Mike Agent", "role": "Senior Agent", "status": "Active", "login": "agent1"},
            {"name": "Kelly Support", "role": "Support Agent", "status": "Active", "login": "support1"},
            {"name": "Chris Helper", "role": "Customer Helper", "status": "Active", "login": "helper1"},
            {"name": "Nina Assistant", "role": "Assistant", "status": "Active", "login": "assist1"},
            {"name": "Ryan Specialist", "role": "Specialist", "status": "Active", "login": "spec1"}
        ]
    }
}

# --- HARDCODED CREDENTIALS ---
DEFAULT_CUSTOMERS_SHEET = "https://docs.google.com/spreadsheets/d/1LZvUQwceVE1dyCjaNod0DPOhHaIGLLBqomCDgxiWuBg/edit?gid=392374958#gid=392374958"
DEFAULT_N8N_WEBHOOK = "https://agentonline-u29564.vm.elestio.app/webhook/f4927f0d-167b-4ab0-94d2-87d4c373f9e9"
HARDCODED_INVOICES_SHEET = "https://docs.google.com/spreadsheets/d/1LZvUQwceVE1dyCjaNod0DPOhHaIGLLBqomCDgxiWuBg/edit?gid=1234567890#gid=1234567890"
PRICE_LIST_SHEET = "https://docs.google.com/spreadsheets/d/1WeDpcSNnfCrtx4F3bBC9osigPkzy3LXybRO6jpN7BXE/edit?usp=drivesdk"

# --- CALL CENTER AGENTS ---
CALL_CENTER_AGENTS = {
    "agent_001": {"name": "Sarah Johnson", "status": "Available", "calls_today": 12, "team": "Customer Service"},
    "agent_002": {"name": "Mike Chen", "status": "On Call", "calls_today": 8, "team": "Customer Service"},
    "agent_003": {"name": "Emma Davis", "status": "Break", "calls_today": 15, "team": "Customer Service"},
    "agent_004": {"name": "Alex Rodriguez", "status": "Available", "calls_today": 10, "team": "Operations"},
    "agent_005": {"name": "Lisa Thompson", "status": "Training", "calls_today": 3, "team": "Operations"}
}

# --- AI AGENTS CONFIGURATION ---
STATIC_AGENTS = {
    "Customer Support": {
        "id": "7b2b8b86-5caa-4f28-8c6b-e7d3d0404f06",
        "name": "Customer Support Agent",
        "description": "Resolves product issues, answers questions, and ensures satisfying customer experiences with technical knowledge and empathy."
    },
    "Sales Assistant": {
        "id": "232f3d9c-18b3-4963-bdd9-e7de3be156ae",
        "name": "Sales Assistant",
        "description": "Identifies qualified prospects, understands business challenges, and connects them with appropriate sales representatives."
    },
    "Laundry Specialist": {
        "id": "41fe59e1-829f-4936-8ee5-eef2bb1287fe",
        "name": "Laundry Specialist",
        "description": "Expert in laundry services, pricing, and scheduling. Handles customer inquiries about cleaning services and special requests."
    }
}

# Define agent type descriptions for call center
AGENT_TYPES = {
    "Customer Support Specialist": "Resolves product issues, answers questions, and ensures satisfying customer experiences with technical knowledge and empathy.",
    "Lead Qualification Specialist": "Identifies qualified prospects, understands business challenges, and connects them with appropriate sales representatives.",
    "Appointment Scheduler": "Efficiently books, confirms, reschedules, or cancels appointments while providing clear service information.",
    "Info Collector": "Gathers accurate and complete information from customers while ensuring data quality and regulatory compliance.",
    "Care Coordinator": "Schedules medical appointments, answers health questions, and coordinates patient services with HIPAA compliance.",
    "Feedback Gatherer": "Conducts surveys, collects customer feedback, and gathers market research with high completion rates."
}

# --- VAPI CALL MANAGEMENT ---
class VAPICallManager:
    def __init__(self, api_key):
        self.api_key = api_key
        self.vapi_client = None
        self.current_call = None
        self.call_thread = None
        self.is_calling = False
        self.call_logs = []
        self.call_history = []
        
    def initialize_client(self):
        """Initialize VAPI client"""
        try:
            self.vapi_client = Vapi(api_key=self.api_key)
            return True, "VAPI client initialized successfully"
        except Exception as e:
            return False, f"Failed to initialize VAPI client: {str(e)}"
    
    def start_call(self, assistant_id, overrides=None, phone_number=None):
        """Start a VAPI call using native features"""
        try:
            if self.is_calling:
                return False, "A call is already in progress"
            
            if not self.vapi_client:
                success, msg = self.initialize_client()
                if not success:
                    return False, msg
            
            # Prepare call parameters
            call_params = {
                "assistant_id": assistant_id
            }
            
            if overrides:
                call_params["assistant_overrides"] = overrides
            
            if phone_number:
                call_params["customer"] = {"number": phone_number}
            
            # Start the call
            self.current_call = self.vapi_client.start(**call_params)
            self.is_calling = True
            
            # Add to call history
            call_record = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'assistant_id': assistant_id,
                'status': 'started',
                'call_id': getattr(self.current_call, 'id', 'unknown'),
                'phone_number': phone_number
            }
            self.call_history.append(call_record)
            
            # Start monitoring thread
            self.call_thread = threading.Thread(target=self._monitor_call, daemon=True)
            self.call_thread.start()
            
            return True, f"Call started successfully. Call ID: {getattr(self.current_call, 'id', 'unknown')}"
            
        except Exception as e:
            self.is_calling = False
            error_msg = f"Failed to start call: {str(e)}"
            self.call_logs.append(f"{datetime.now().strftime('%H:%M:%S')}: ERROR - {error_msg}")
            return False, error_msg
    
    def stop_call(self):
        """Stop the current VAPI call"""
        try:
            if not self.is_calling:
                return False, "No active call to stop"
            
            if self.vapi_client and self.current_call:
                self.vapi_client.stop()
                self.call_logs.append(f"{datetime.now().strftime('%H:%M:%S')}: Call stopped by user")
            
            self.is_calling = False
            self.current_call = None
            
            # Update call history
            if self.call_history:
                self.call_history[-1]['status'] = 'stopped'
                self.call_history[-1]['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            return True, "Call stopped successfully"
            
        except Exception as e:
            self.is_calling = False
            self.current_call = None
            error_msg = f"Error stopping call: {str(e)}"
            self.call_logs.append(f"{datetime.now().strftime('%H:%M:%S')}: ERROR - {error_msg}")
            return False, error_msg
    
    def _monitor_call(self):
        """Monitor call status in background thread"""
        try:
            while self.is_calling and self.current_call:
                # Add periodic status updates
                self.call_logs.append(f"{datetime.now().strftime('%H:%M:%S')}: Call is active...")
                time.sleep(10)  # Check every 10 seconds
                
                # You can add more sophisticated monitoring here
                # such as checking call status via VAPI API
                
        except Exception as e:
            self.call_logs.append(f"{datetime.now().strftime('%H:%M:%S')}: Monitor error - {str(e)}")
        finally:
            if self.is_calling:
                self.is_calling = False
                if self.call_history:
                    self.call_history[-1]['status'] = 'ended'
                    self.call_history[-1]['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_call_status(self):
        """Get current call status"""
        return {
            'is_calling': self.is_calling,
            'call_id': getattr(self.current_call, 'id', None) if self.current_call else None,
            'logs': self.call_logs[-20:],  # Last 20 log entries
            'history': self.call_history
        }
    
    def clear_logs(self):
        """Clear call logs"""
        self.call_logs = []

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
    .login-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 2rem 0;
    }
    .team-card {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .price-card {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #a8edea;
    }
    .user-info {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        text-align: center;
        color: #333;
    }
    .call-status-active {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .call-status-inactive {
        background: linear-gradient(135deg, #f44336 0%, #da190b 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .agent-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIN SYSTEM ---
def login_user(username, password):
    if username in DEMO_ACCOUNTS and DEMO_ACCOUNTS[username]["password"] == password:
        return DEMO_ACCOUNTS[username]
    return None

def logout_user():
    for key in list(st.session_state.keys()):
        if key.startswith('user_'):
            del st.session_state[key]
    st.session_state.logged_in = False

# --- DATA TYPE HANDLING ---
def fix_dataframe_types(df):
    """Fix PyArrow data type conversion issues for phone numbers and ID columns"""
    if df.empty:
        return df
    
    # List of columns that should be treated as strings to avoid PyArrow conversion errors
    string_columns = [
        'Phone Number', 'Phone', 'phone', 'phone_number',
        'Customer ID', 'customer_id', 'ID', 'id',
        'Order ID', 'order_id', 'Invoice Number', 'invoice_number',
        'Account Number', 'account_number', 'Reference', 'reference',
        'Zip Code', 'zip_code', 'Postal Code', 'postal_code'
    ]
    
    # Convert matching columns to string type
    for col in df.columns:
        if any(string_col.lower() in col.lower() for string_col in string_columns):
            # Handle null values first, then convert to string
            df[col] = df[col].fillna('').astype(str)
    
    return df

# --- INITIALIZE SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}

# Initialize VAPI call manager
def initialize_vapi_session_state():
    if "vapi_manager" not in st.session_state:
        st.session_state.vapi_manager = None
    if "show_descriptions" not in st.session_state:
        st.session_state.show_descriptions = False

# Initialize VAPI session state
initialize_vapi_session_state()

# --- LOGIN PAGE ---
if not st.session_state.logged_in:
    st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="login-container">
            <h2>🔐 Login to CRM System</h2>
            <p>Enter your credentials to access the system</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("👤 Username")
            password = st.text_input("🔒 Password", type="password")
            login_button = st.form_submit_button("🚀 Login", type="primary")
            
            if login_button:
                user_info = login_user(username, password)
                if user_info:
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_info
                    st.session_state.username = username
                    st.success(f"✅ Welcome {user_info['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials!")
        
        # Demo accounts info
        st.markdown("---")
        st.subheader("🎯 Demo Accounts")
        
        demo_col1, demo_col2 = st.columns(2)
        
        with demo_col1:
            st.markdown("""
            **👑 Admin Access:**
            - Username: `admin`
            - Password: `admin123`
            
            **👨‍💼 Manager Access:**
            - Username: `manager1`
            - Password: `manager123`
            """)
        
        with demo_col2:
            st.markdown("""
            **🎧 Agent Access:**
            - Username: `agent1`
            - Password: `agent123`
            
            **🎮 Demo Access:**
            - Username: `demo`
            - Password: `demo123`
            """)

else:
    # --- MAIN APPLICATION ---
    
    # --- HEADER WITH USER INFO ---
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="user-info">
            <strong>👤 {st.session_state.user_info['name']}</strong><br>
            <small>{st.session_state.user_info['role']} | {st.session_state.user_info['team']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        if st.button("🚪 Logout", type="secondary"):
            logout_user()
            st.rerun()
    
    # --- SIDEBAR AUTH JSON UPLOAD ---
    st.sidebar.markdown('<div class="sidebar-header">🔐 Authentication</div>', unsafe_allow_html=True)
    auth_file = st.sidebar.file_uploader("Upload service_account.json", type="json")
    
    # --- SIDEBAR USER INFO ---
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Current User:** {st.session_state.user_info['name']}")
    st.sidebar.markdown(f"**Role:** {st.session_state.user_info['role']}")
    st.sidebar.markdown(f"**Team:** {st.session_state.user_info['team']}")
    
    # --- SIDEBAR CALL STATUS ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📞 Call Center Status")
    
    if st.session_state.vapi_manager:
        status = st.session_state.vapi_manager.get_call_status()
        st.sidebar.write(f"**Call Active:** {'✅ Yes' if status['is_calling'] else '❌ No'}")
        st.sidebar.write(f"**Total Calls:** {len(status['history'])}")
        if status['call_id']:
            st.sidebar.write(f"**Call ID:** {status['call_id']}")
    else:
        st.sidebar.write("**VAPI Manager:** Not initialized")
    
    # --- TAB LAYOUT ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "🏠 Dashboard", 
        "➕ Add Customer", 
        "📋 View All",
        "🧾 Invoices",
        "💰 Price List",
        "👥 Team Management",
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
            else:
                CUSTOMERS_SHEET_URL = st.sidebar.text_input("📄 Customers Google Sheet URL", DEFAULT_CUSTOMERS_SHEET)
                INVOICES_SHEET_URL = st.sidebar.text_input("🧾 Invoices Google Sheet URL", HARDCODED_INVOICES_SHEET)
                N8N_WEBHOOK_URL = st.sidebar.text_input("🔗 N8N Webhook URL", DEFAULT_N8N_WEBHOOK)
            
            # --- LOAD DATA ---
            customers_df = pd.DataFrame()
            invoices_df = pd.DataFrame()
            price_list_df = pd.DataFrame()
            
            # Load customers
            if CUSTOMERS_SHEET_URL:
                try:
                    customers_sheet = client.open_by_url(CUSTOMERS_SHEET_URL)
                    customers_worksheet = customers_sheet.sheet1
                    customers_data = customers_worksheet.get_all_records()
                    customers_df = pd.DataFrame(customers_data)
                    if not customers_df.empty:
                        customers_df = fix_dataframe_types(customers_df)  # Fix data types
                        st.sidebar.success(f"✅ Loaded {len(customers_df)} customers")
                except Exception as e:
                    st.sidebar.error(f"❌ Error loading customers: {str(e)}")
            
            # Load invoices
            if INVOICES_SHEET_URL:
                try:
                    invoices_sheet = client.open_by_url(INVOICES_SHEET_URL)
                    invoices_worksheet = invoices_sheet.sheet1
                    invoices_data = invoices_worksheet.get_all_records()
                    invoices_df = pd.DataFrame(invoices_data)
                    if not invoices_df.empty:
                        invoices_df = fix_dataframe_types(invoices_df)  # Fix data types
                        st.sidebar.success(f"✅ Loaded {len(invoices_df)} invoices")
                except Exception as e:
                    st.sidebar.warning(f"⚠️ Invoices sheet not accessible: {str(e)}")
            
            # Load price list
            try:
                price_sheet = client.open_by_url(PRICE_LIST_SHEET)
                price_worksheet = price_sheet.sheet1
                price_data = price_worksheet.get_all_records()
                price_list_df = pd.DataFrame(price_data)
                if not price_list_df.empty:
                    price_list_df = fix_dataframe_types(price_list_df)  # Fix data types
                    st.sidebar.success(f"✅ Loaded {len(price_list_df)} price items")
            except Exception as e:
                st.sidebar.warning(f"⚠️ Price list not accessible: {str(e)}")
                # Create sample price data
                price_list_df = pd.DataFrame([
                    {"Service Category": "Washing", "Item": "Regular Wash", "Price (USD)": 15.00, "Turnaround Time": "2 hours", "Notes": "Standard washing service"},
                    {"Service Category": "Dry Cleaning", "Item": "Suit Cleaning", "Price (USD)": 25.00, "Turnaround Time": "24 hours", "Notes": "Professional dry cleaning"},
                    {"Service Category": "Pressing", "Item": "Shirt Press", "Price (USD)": 8.00, "Turnaround Time": "1 hour", "Notes": "Professional pressing"},
                    {"Service Category": "Alterations", "Item": "Hem Adjustment", "Price (USD)": 12.00, "Turnaround Time": "48 hours", "Notes": "Basic alterations"},
                    {"Service Category": "Special", "Item": "Express Service", "Price (USD)": 35.00, "Turnaround Time": "30 minutes", "Notes": "Rush service available"}
                ])
                price_list_df = fix_dataframe_types(price_list_df)  # Fix data types for sample data too
            
            # --- DASHBOARD TAB ---
            with tab1:
                st.subheader("📊 CRM Dashboard")
                
                # User-specific greeting
                st.markdown(f"### Welcome back, {st.session_state.user_info['name']}! 👋")
                
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
                    team_members = sum(len(team["members"]) for team in TEAM_STRUCTURE.values())
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>👨‍💼 Team Members</h3>
                        <h2>{team_members}</h2>
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
                    total_calls = len(st.session_state.vapi_manager.get_call_status()['history']) if st.session_state.vapi_manager else 0
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>📞 Total Calls</h3>
                        <h2>{total_calls}</h2>
                    </div>
                    ''', unsafe_allow_html=True)
                
                # Call status indicator
                if st.session_state.vapi_manager:
                    status = st.session_state.vapi_manager.get_call_status()
                    if status['is_calling']:
                        st.markdown(f'''
                        <div class="call-status-active">
                            <h3>🟢 Call Currently Active</h3>
                            <p>Call ID: {status['call_id'] or 'Unknown'}</p>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown('''
                        <div class="call-status-inactive">
                            <h3>🔴 No Active Calls</h3>
                            <p>Ready to initiate new calls</p>
                        </div>
                        ''', unsafe_allow_html=True)
                
                # Team overview for current user
                st.subheader(f"👥 Your Team: {st.session_state.user_info['team']}")
                
                user_team = TEAM_STRUCTURE.get(st.session_state.user_info['team'], {})
                if user_team:
                    st.markdown(f"**Team Lead:** {user_team['team_lead']}")
                    
                    team_cols = st.columns(len(user_team['members']))
                    for idx, member in enumerate(user_team['members']):
                        with team_cols[idx % len(team_cols)]:
                            status_emoji = "🟢" if member['status'] == 'Active' else "🔴"
                            st.markdown(f"""
                            <div class="team-card" style="font-size: 0.9em;">
                                <strong>{status_emoji} {member['name']}</strong><br>
                                <small>{member['role']}</small>
                            </div>
                            """, unsafe_allow_html=True)
            
            # --- ADD CUSTOMER TAB ---
            with tab2:
                st.subheader("➕ Add New Customer")
                st.markdown(f"*Adding as: {st.session_state.user_info['name']}*")
                
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
                        call_summary = st.text_area("📋 Call Summary", placeholder="Summary of conversation")
                    
                    submitted = st.form_submit_button("✅ Add Customer", type="primary")
                    
                    if submitted:
                        if name and phone:
                            try:
                                # Add user info to the record
                                customers_worksheet.append_row([
                                    name, email, phone, preference, preferred_time,
                                    address, items, f"{notes} [Added by: {st.session_state.user_info['name']}]", 
                                    call_summary
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
                
                if not customers_df.empty:
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
                    
                    # Ensure data types are correct before displaying
                    display_df = fix_dataframe_types(display_df)
                    
                    # Interactive table
                    gb = GridOptionsBuilder.from_dataframe(display_df)
                    gb.configure_pagination(paginationAutoPageSize=True)
                    gb.configure_side_bar()
                    gb.configure_selection('multiple', use_checkbox=True)
                    gb.configure_default_column(editable=True, groupable=True)
                    
                    gridOptions = gb.build()
                    
                    AgGrid(
                        display_df,
                        gridOptions=gridOptions,
                        height=500,
                        width='100%',
                        theme='alpine',
                        update_mode=GridUpdateMode.MODEL_CHANGED,
                        fit_columns_on_grid_load=True
                    )
                else:
                    st.info("No customers found. Add some customers first!")
            
            # --- INVOICES TAB ---
            with tab4:
                st.subheader("🧾 Invoices Management")
                
                # Add new invoice form
                with st.expander("➕ Add New Invoice"):
                    with st.form("add_invoice"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            invoice_customer = st.selectbox("👤 Customer", customers_df["Name"].tolist() if not customers_df.empty else ["Sample Customer"])
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
                                invoice_data = [
                                    invoice_customer,
                                    str(invoice_date),
                                    invoice_amount,
                                    invoice_status,
                                    invoice_items,
                                    f"{invoice_notes} [Created by: {st.session_state.user_info['name']}]",
                                    str(due_date),
                                    payment_method
                                ]
                                
                                invoices_worksheet.append_row(invoice_data)
                                st.success("✅ Invoice created successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error creating invoice: {e}")
                
                # Display invoices
                if not invoices_df.empty:
                    # Ensure data types are correct before displaying
                    display_invoices_df = fix_dataframe_types(invoices_df.copy())
                    st.dataframe(display_invoices_df, use_container_width=True)
                else:
                    st.info("No invoices found. Create your first invoice!")
            
            # --- PRICE LIST TAB ---
            with tab5:
                st.subheader("💰 Price List Management")
                
                # Price list header
                st.markdown(f"""
                <div class="price-card">
                    <h3>📊 Live Price List</h3>
                    <p>Connected to: <a href="{PRICE_LIST_SHEET}" target="_blank">Google Sheets Price Database</a></p>
                    <p>Managed by: {st.session_state.user_info['name']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if not price_list_df.empty:
                    # Price list filters
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        category_filter = st.selectbox("Filter by Category", ["All"] + list(price_list_df["Service Category"].unique()))
                    
                    with col2:
                        price_range = st.slider("Price Range (USD)", 
                                              min_value=float(price_list_df["Price (USD)"].min()), 
                                              max_value=float(price_list_df["Price (USD)"].max()),
                                              value=(float(price_list_df["Price (USD)"].min()), float(price_list_df["Price (USD)"].max())))
                    
                    with col3:
                        if st.button("🔄 Refresh Price List"):
                            st.rerun()
                    
                    # Apply filters
                    filtered_prices = price_list_df.copy()
                    if category_filter != "All":
                        filtered_prices = filtered_prices[filtered_prices["Service Category"] == category_filter]
                    
                    filtered_prices = filtered_prices[
                        (filtered_prices["Price (USD)"] >= price_range[0]) & 
                        (filtered_prices["Price (USD)"] <= price_range[1])
                    ]
                    
                    # Display price list
                    st.subheader("📋 Current Prices")
                    
                    # Price cards
                    for idx, row in filtered_prices.iterrows():
                        col1, col2, col3, col4 = st.columns([2, 2, 1, 3])
                        
                        with col1:
                            st.markdown(f"**{row['Service Category']}**")
                            st.markdown(f"*{row['Item']}*")
                        
                        with col2:
                            st.markdown(f"**💰 ${row['Price (USD)']}**")
                        
                        with col3:
                            st.markdown(f"**⏱️ {row['Turnaround Time']}**")
                        
                        with col4:
                            st.markdown(f"📝 {row['Notes']}")
                        
                        st.markdown("---")
                    
                    # Price analytics
                    st.subheader("📊 Price Analytics")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Price by category
                        category_avg = filtered_prices.groupby("Service Category")["Price (USD)"].mean().reset_index()
                        fig = px.bar(category_avg, x="Service Category", y="Price (USD)", 
                                   title="Average Price by Category")
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Price distribution
                        fig = px.histogram(filtered_prices, x="Price (USD)", 
                                         title="Price Distribution", nbins=10)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Export price list
                    if st.button("📥 Export Price List CSV"):
                        csv = filtered_prices.to_csv(index=False)
                        st.download_button(
                            label="Download Price List CSV",
                            data=csv,
                            file_name=f"price_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                
                else:
                    st.warning("⚠️ Price list not available. Please check the Google Sheets connection.")
            
            # --- TEAM MANAGEMENT TAB ---
            with tab6:
                st.subheader("👥 Team Management")
                
                # Team overview
                st.markdown(f"**Your Access Level:** {st.session_state.user_info['role']}")
                
                # Display all teams
                for team_name, team_info in TEAM_STRUCTURE.items():
                    with st.expander(f"🏢 {team_name} Team ({len(team_info['members'])} members)"):
                        st.markdown(f"**Team Lead:** {team_info['team_lead']}")
                        
                        # Team members table
                        team_df = pd.DataFrame(team_info['members'])
                        
                        # Add action buttons for admins
                        if st.session_state.user_info['role'] == 'Admin':
                            st.markdown("*Admin controls available*")
                        
                        # Ensure data types are correct before displaying
                        team_df = fix_dataframe_types(team_df)
                        st.dataframe(team_df, use_container_width=True)
                        
                        # Team stats
                        active_members = len([m for m in team_info['members'] if m['status'] == 'Active'])
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("👥 Total Members", len(team_info['members']))
                        with col2:
                            st.metric("✅ Active", active_members)
                        with col3:
                            st.metric("📊 Team Load", f"{active_members * 20}%")
                
                # Team performance chart
                st.subheader("📈 Team Performance Overview")
                
                team_data = []
                for team_name, team_info in TEAM_STRUCTURE.items():
                    active_count = len([m for m in team_info['members'] if m['status'] == 'Active'])
                    team_data.append({
                        "Team": team_name,
                        "Active Members": active_count,
                        "Total Members": len(team_info['members'])
                    })
                
                team_df = pd.DataFrame(team_data)
                fig = px.bar(team_df, x="Team", y=["Active Members", "Total Members"], 
                           title="Team Composition", barmode="group")
                st.plotly_chart(fig, use_container_width=True)
            
            # --- SUPER CHAT TAB ---
            with tab7:
                st.subheader("💬 Laundry Super Chat")
                
                st.markdown(f"""
                <div class="chat-container">
                    <h3>🤖 AI Assistant for {st.session_state.user_info['name']}</h3>
                    <p>Chat with our AI assistant powered by N8N automation</p>
                    <p><strong>User Context:</strong> {st.session_state.user_info['role']} in {st.session_state.user_info['team']}</p>
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
                    
                    # Send to N8N webhook with user context
                    if N8N_WEBHOOK_URL:
                        try:
                            with st.spinner("🤖 AI is thinking..."):
                                response = requests.post(
                                    N8N_WEBHOOK_URL,
                                    json={
                                        "message": prompt,
                                        "user_id": st.session_state.username,
                                        "user_name": st.session_state.user_info['name'],
                                        "user_role": st.session_state.user_info['role'],
                                        "user_team": st.session_state.user_info['team'],
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
                        
                        except Exception as e:
                            bot_response = f"Connection error: {str(e)}"
                    else:
                        bot_response = f"Hello {st.session_state.user_info['name']}! AI chat is ready with your user context."
                    
                    st.session_state.messages.append({"role": "assistant", "content": bot_response})
                    with st.chat_message("assistant"):
                        st.markdown(bot_response)
            
            # --- IMPROVED CALL CENTER TAB ---
            with tab8:
                st.subheader("📞 AI Agent Caller - Native VAPI Integration")
                
                # Get API key from secrets
                try:
                    api_key = st.secrets["VAPI_API_KEY"]
                    st.success("✅ VAPI API Key loaded from secrets")
                    
                    # Initialize VAPI manager if not exists
                    if not st.session_state.vapi_manager:
                        st.session_state.vapi_manager = VAPICallManager(api_key)
                        success, msg = st.session_state.vapi_manager.initialize_client()
                        if success:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")
                    
                except KeyError:
                    st.error("❌ VAPI_API_KEY not found in secrets. Please add it to your Streamlit secrets.")
                    st.info("Add this to your Streamlit app secrets: `VAPI_API_KEY = 'your_api_key_here'`")
                    api_key = None
                
                if api_key and st.session_state.vapi_manager:
                    # Configuration section
                    col1, col2 = st.columns([2, 1])
                    
                    with col2:
                        # Status information
                        st.subheader("📊 Status")
                        status = st.session_state.vapi_manager.get_call_status()
                        st.write(f"**Call Active:** {'✅ Yes' if status['is_calling'] else '❌ No'}")
                        st.write(f"**Total Calls:** {len(status['history'])}")
                        
                        if status['call_id']:
                            st.write(f"**Call ID:** {status['call_id']}")
                    
                    # Controls
                    st.subheader("🎛️ Controls")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("🔄 Refresh Status"):
                            st.rerun()
                    
                    with col2:
                        if st.button("🧹 Clear Logs"):
                            if st.session_state.vapi_manager:
                                st.session_state.vapi_manager.clear_logs()
                                st.success("Logs cleared!")
                    
                    with col3:
                        if st.button("ℹ️ Toggle Agent Types"):
                            st.session_state.show_descriptions = not st.session_state.show_descriptions
                    
                    # Show Agent Type Descriptions
                    if st.session_state.show_descriptions:
                        st.subheader("📚 Agent Type Descriptions")
                        for role, desc in AGENT_TYPES.items():
                            with st.expander(role):
                                st.write(desc)
                    
                    # Agent Setup
                    st.subheader("🧠 Define Your Assistants")
                    agent_configs = []
                    
                    # Create tabs for better organization
                    tab_setup, tab_history, tab_logs = st.tabs(["Assistant Setup", "Call History", "Live Logs"])
                    
                    with tab_setup:
                        col1, col2 = st.columns(2)
                        
                        for i in range(1, 6):
                            with col1 if i <= 2 else col2:
                                with st.expander(f"Assistant {i} Setup", expanded=(i == 1)):
                                    agent_id = st.text_input(f"Assistant ID", key=f"assistant_id_{i}")
                                    agent_name = st.text_input(f"Agent Name", key=f"agent_name_{i}")
                                    agent_type = st.selectbox(
                                        f"Agent Type", 
                                        options=[""] + list(AGENT_TYPES.keys()), 
                                        key=f"agent_type_{i}"
                                    )

                                    if agent_id and agent_type:
                                        agent_configs.append({
                                            "id": agent_id,
                                            "name": agent_name or f"Agent {i}",
                                            "type": agent_type
                                        })
                    
                    with tab_history:
                        st.subheader("📞 Call History")
                        status = st.session_state.vapi_manager.get_call_status()
                        if status['history']:
                            for i, call in enumerate(reversed(status['history'][-10:])):
                                status_icon = {"started": "🟡", "stopped": "✅", "ended": "🔴"}.get(call['status'], "❓")
                                st.write(f"{status_icon} **{call['timestamp']}** - {call['assistant_id']} ({call['status']})")
                                if 'call_id' in call:
                                    st.caption(f"Call ID: {call['call_id']}")
                                if 'phone_number' in call and call['phone_number']:
                                    st.caption(f"Phone: {call['phone_number']}")
                        else:
                            st.info("No calls made yet.")
                    
                    with tab_logs:
                        st.subheader("📝 Live Call Logs")
                        status = st.session_state.vapi_manager.get_call_status()
                        if status['logs']:
                            for log in status['logs']:
                                st.text(log)
                        else:
                            st.info("No logs available.")
                    
                    # User Info
                    st.subheader("🙋 Call Configuration")
                    col1, col2 = st.columns(2)
                    with col1:
                        user_name = st.text_input("Your Name (for personalized greeting):", placeholder="Enter your name")
                        phone_number = st.text_input("Phone Number to Call:", placeholder="+1234567890")
                    with col2:
                        additional_context = st.text_area("Additional Context:", placeholder="Any specific information for the call")
                    
                    # Select Agent to Call
                    if agent_configs:
                        st.subheader("📲 Select Assistant")
                        agent_labels = [f"{a['name']} - {a['type']}" for a in agent_configs]
                        selected_index = st.selectbox(
                            "Choose Assistant to Call", 
                            range(len(agent_configs)), 
                            format_func=lambda i: agent_labels[i]
                        )
                        selected_agent = agent_configs[selected_index]
                        
                        # Show selected agent details
                        with st.expander("Selected Assistant Details", expanded=True):
                            st.write(f"**Name:** {selected_agent['name']}")
                            st.write(f"**Type:** {selected_agent['type']}")
                            st.write(f"**ID:** {selected_agent['id']}")
                            st.write(f"**Description:** {AGENT_TYPES[selected_agent['type']]}")
                    else:
                        selected_agent = None
                        st.warning("⚠️ Please define at least one assistant above.")
                    
                    # Call Controls
                    st.subheader("📞 Call Controls")
                    
                    if selected_agent:
                        status = st.session_state.vapi_manager.get_call_status()
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            start_disabled = status['is_calling']
                            if st.button("▶️ Start Call", disabled=start_disabled, use_container_width=True):
                                overrides = {}
                                if user_name:
                                    overrides["variableValues"] = {"name": user_name}
                                if additional_context:
                                    overrides["context"] = additional_context
                                
                                success, message = st.session_state.vapi_manager.start_call(
                                    selected_agent["id"], 
                                    overrides, 
                                    phone_number if phone_number else None
                                )
                                if success:
                                    st.success(f"📞 {message}")
                                    st.balloons()
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                        
                        with col2:
                            stop_disabled = not status['is_calling']
                            if st.button("⛔ Stop Call", disabled=stop_disabled, use_container_width=True):
                                success, message = st.session_state.vapi_manager.stop_call()
                                if success:
                                    st.success(f"📴 {message}")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")
                        
                        with col3:
                            if st.button("🔄 Check Status", use_container_width=True):
                                status = st.session_state.vapi_manager.get_call_status()
                                if status['is_calling']:
                                    st.success(f"✅ Call is active (ID: {status['call_id']})")
                                else:
                                    st.info("ℹ️ No active call")
                        
                        # Call status indicator
                        if status['is_calling']:
                            st.success("🟢 **Call is currently active using native VAPI integration**")
                            if status['call_id']:
                                st.info(f"Call ID: {status['call_id']}")
                        else:
                            st.info("🔴 **No active call**")
                    
                    # Native VAPI Benefits
                    st.markdown("---")
                    st.subheader("💡 Native VAPI Integration Benefits")
                    st.markdown("""
                    - **🚀 Direct Integration**: Uses vapi_python library directly
                    - **🔄 Stable Connections**: No subprocess management issues
                    - **📊 Real-time Monitoring**: Native call status tracking
                    - **🛡️ Reliable State**: Proper session state management
                    - **⚡ Better Performance**: Eliminates process overhead
                    - **🎯 Full VAPI Features**: Access to all native VAPI capabilities
                    """)
                
                # Auto-refresh for live updates (less aggressive)
                if st.session_state.vapi_manager:
                    status = st.session_state.vapi_manager.get_call_status()
                    if status['is_calling']:
                        time.sleep(5)  # Reduced from 2 seconds to 5 seconds
                        st.rerun()
            
            # --- ANALYTICS TAB ---
            with tab9:
                st.subheader("📊 Advanced Analytics")
                
                # Analytics overview
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>👥 Total Users</h3>
                        <h2>{len(DEMO_ACCOUNTS)}</h2>
                    </div>
                    ''', unsafe_allow_html=True)
                
                with col2:
                    total_team_members = sum(len(team["members"]) for team in TEAM_STRUCTURE.values())
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>👨‍💼 Team Members</h3>
                        <h2>{total_team_members}</h2>
                    </div>
                    ''', unsafe_allow_html=True)
                
                with col3:
                    total_ai_calls = len(st.session_state.vapi_manager.get_call_status()['history']) if st.session_state.vapi_manager else 0
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>🤖 AI Calls</h3>
                        <h2>{total_ai_calls}</h2>
                    </div>
                    ''', unsafe_allow_html=True)
                
                with col4:
                    avg_price = price_list_df["Price (USD)"].mean() if not price_list_df.empty else 0
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>💰 Avg Price</h3>
                        <h2>${avg_price:.2f}</h2>
                    </div>
                    ''', unsafe_allow_html=True)
                
                # User activity analytics
                st.subheader("👤 User Activity")
                st.markdown(f"**Current Session:** {st.session_state.user_info['name']} ({st.session_state.user_info['role']})")
                
                # Call center analytics
                st.subheader("📞 Call Center Analytics")
                
                if st.session_state.vapi_manager:
                    status = st.session_state.vapi_manager.get_call_status()
                    if status['history']:
                        # Advanced call analytics
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Call status distribution
                            status_counts = {}
                            for call in status['history']:
                                call_status = call.get('status', 'unknown')
                                status_counts[call_status] = status_counts.get(call_status, 0) + 1
                            
                            fig = px.pie(
                                values=list(status_counts.values()),
                                names=list(status_counts.keys()),
                                title="Call Status Distribution"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # Calls over time
                            call_dates = [call['timestamp'][:10] for call in status['history']]
                            date_counts = {}
                            for date in call_dates:
                                date_counts[date] = date_counts.get(date, 0) + 1
                            
                            fig = px.bar(
                                x=list(date_counts.keys()), 
                                y=list(date_counts.values()),
                                title="Calls by Date",
                                labels={'x': 'Date', 'y': 'Number of Calls'}
                            )
                            st.plotly_chart(fig, use_container_width=True)
                
                # Team performance analytics
                st.subheader("📈 Team Performance")
                
                team_performance_data = []
                for team_name, team_info in TEAM_STRUCTURE.items():
                    active_members = len([m for m in team_info['members'] if m['status'] == 'Active'])
                    team_performance_data.append({
                        "Team": team_name,
                        "Active Members": active_members,
                        "Performance Score": active_members * 85  # Mock performance score
                    })
                
                team_perf_df = pd.DataFrame(team_performance_data)
                fig = px.bar(team_perf_df, x="Team", y="Performance Score", 
                           title="Team Performance Scores")
                st.plotly_chart(fig, use_container_width=True)
                
                # Export all data
                st.subheader("📥 Data Export")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📥 Export All Data"):
                        # Create comprehensive export
                        export_data = {
                            "customers": customers_df.to_dict('records') if not customers_df.empty else [],
                            "invoices": invoices_df.to_dict('records') if not invoices_df.empty else [],
                            "price_list": price_list_df.to_dict('records') if not price_list_df.empty else [],
                            "teams": TEAM_STRUCTURE,
                            "call_center_agents": CALL_CENTER_AGENTS,
                            "ai_agents": STATIC_AGENTS,
                            "call_history": st.session_state.vapi_manager.get_call_status()['history'] if st.session_state.vapi_manager else [],
                            "exported_by": st.session_state.user_info['name'],
                            "export_time": datetime.now().isoformat()
                        }
                        
                        st.download_button(
                            label="Download Complete Data Export (JSON)",
                            data=json.dumps(export_data, indent=2),
                            file_name=f"crm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                
                with col2:
                    if st.button("📊 Export Analytics Report"):
                        report_data = {
                            "report_generated_by": st.session_state.user_info['name'],
                            "report_date": datetime.now().isoformat(),
                            "total_customers": len(customers_df),
                            "total_invoices": len(invoices_df),
                            "total_team_members": total_team_members,
                            "total_ai_calls": len(st.session_state.vapi_manager.get_call_status()['history']) if st.session_state.vapi_manager else 0,
                            "team_breakdown": team_performance_data,
                            "call_analytics": {
                                "active_call": st.session_state.vapi_manager.get_call_status()['is_calling'] if st.session_state.vapi_manager else False,
                                "total_calls": len(st.session_state.vapi_manager.get_call_status()['history']) if st.session_state.vapi_manager else 0
                            }
                        }
                        
                        st.download_button(
                            label="Download Analytics Report (JSON)",
                            data=json.dumps(report_data, indent=2),
                            file_name=f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                
                with col3:
                    if st.button("📞 Export Call Data"):
                        call_data = {
                            "call_history": st.session_state.vapi_manager.get_call_status()['history'] if st.session_state.vapi_manager else [],
                            "ai_agents": STATIC_AGENTS,
                            "human_agents": CALL_CENTER_AGENTS,
                            "current_call_active": st.session_state.vapi_manager.get_call_status()['is_calling'] if st.session_state.vapi_manager else False,
                            "exported_by": st.session_state.user_info['name'],
                            "export_time": datetime.now().isoformat()
                        }
                        
                        st.download_button(
                            label="Download Call Data (JSON)",
                            data=json.dumps(call_data, indent=2),
                            file_name=f"call_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
        
        except Exception as e:
            st.error(f"❌ Error loading system: {e}")
    
    else:
        # No auth file uploaded - show system ready message
        st.markdown("""
        <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin: 2rem 0;">
            <h2>🔐 System Ready - Upload Authentication</h2>
            <p>Welcome {user_name}! Upload your Google Service Account JSON file to access all features.</p>
            
            <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 10px; margin: 1.5rem 0;">
                <h3>✨ Your Access Level: {user_role}</h3>
                <p>Team: {user_team}</p>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                    <div>
                        <p>✅ Customer Management</p>
                        <p>🧾 Invoice System</p>
                        <p>💰 Live Price List</p>
                        <p>📊 Analytics Dashboard</p>
                    </div>
                    <div>
                        <p>👥 Team Management ({total_members} members)</p>
                        <p>📞 AI-Powered Call Center</p>
                        <p>🤖 Advanced AI Chat System</p>
                        <p>📥 Comprehensive Data Export</p>
                    </div>
                </div>
            </div>
            
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 10px; margin: 1rem 0;">
                <h4>🚀 New: Native VAPI Integration</h4>
                <p>✨ Direct vapi_python library integration for stable calls</p>
                <p>🎯 Improved session state management</p>
                <p>📊 Real-time call monitoring without subprocess issues</p>
                <p>🔄 Reliable call management with full VAPI features</p>
            </div>
        </div>
        """.format(
            user_name=st.session_state.user_info['name'],
            user_role=st.session_state.user_info['role'],
            user_team=st.session_state.user_info['team'],
            total_members=sum(len(team["members"]) for team in TEAM_STRUCTURE.values())
        ), unsafe_allow_html=True)

