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
import hashlib
import subprocess
import sys
import os
import time
import tempfile

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="🧼 Auto Laundry CRM Pro", 
    layout="wide",
    initial_sidebar_state="expanded"
)

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
DEFAULT_N8N_WEBHOOK = "https://agentonline-u29564.vm.elestio.app/webhook/bf7aec67-cce8-4bd6-81f1-f04f84b992f7"
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
        "id": "your-support-agent-id",
        "name": "Customer Support Agent",
        "description": "Resolves product issues, answers questions, and ensures satisfying customer experiences with technical knowledge and empathy."
    },
    "Sales Assistant": {
        "id": "your-sales-agent-id",
        "name": "Sales Assistant",
        "description": "Identifies qualified prospects, understands business challenges, and connects them with appropriate sales representatives."
    },
    "Appointment Scheduler": {
        "id": "your-scheduler-agent-id",
        "name": "Appointment Scheduler",
        "description": "Efficiently books, confirms, reschedules, or cancels appointments while providing clear service information."
    },
    "Laundry Specialist": {
        "id": "your-laundry-agent-id",
        "name": "Laundry Specialist",
        "description": "Expert in laundry services, pricing, and scheduling. Handles customer inquiries about cleaning services and special requests."
    }
}

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

# --- CALL CENTER FUNCTIONS ---
def create_vapi_caller_script():
    script_content = '''
import sys
import json
import time
from vapi_python import Vapi
import signal
import os

def signal_handler(signum, frame):
    print("Call interrupted by user")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def main():
    try:
        if len(sys.argv) != 2:
            print("Usage: python vapi_caller.py <config_json>")
            sys.exit(1)
       
        config = json.loads(sys.argv[1])
        api_key = config["api_key"]
        assistant_id = config["assistant_id"]
        overrides = config.get("overrides", {})
       
        print(f"Initializing VAPI with assistant: {assistant_id}")
       
        vapi = Vapi(api_key=api_key)
       
        print("Starting call...")
        call_response = vapi.start(
            assistant_id=assistant_id,
            assistant_overrides=overrides
        )
       
        call_id = getattr(call_response, 'id', 'unknown')
        print(f"Call started successfully. Call ID: {call_id}")
       
        print("Call is active. Press Ctrl+C to stop.")
       
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping call...")
            try:
                vapi.stop()
                print("Call stopped successfully")
            except Exception as e:
                print(f"Error stopping call: {e}")
       
    except Exception as e:
        print(f"Error in VAPI caller: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
   
    script_path = os.path.join(tempfile.gettempdir(), "vapi_caller.py")
    with open(script_path, "w") as f:
        f.write(script_content)
   
    return script_path

def start_call_isolated(assistant_id, user_name=None, customer_info=None):
    try:
        # Get API key from secrets
        try:
            api_key = st.secrets["VAPI_API_KEY"]
        except KeyError:
            return False, "VAPI_API_KEY not found in secrets. Please add it to your .streamlit/secrets.toml file."
        
        # Kill any existing process
        if st.session_state.current_process:
            try:
                st.session_state.current_process.terminate()
                st.session_state.current_process.wait(timeout=5)
            except:
                try:
                    st.session_state.current_process.kill()
                except:
                    pass
            st.session_state.current_process = None
       
        # Create the caller script
        script_path = create_vapi_caller_script()
       
        # Prepare configuration
        config = {
            "api_key": api_key,
            "assistant_id": assistant_id,
            "overrides": {}
        }
       
        # Add user context
        variable_values = {}
        if user_name:
            variable_values["name"] = user_name
        if customer_info:
            variable_values.update(customer_info)
        
        if variable_values:
            config["overrides"]["variableValues"] = variable_values
       
        config_json = json.dumps(config)
       
        # Start the isolated process
        process = subprocess.Popen(
            [sys.executable, script_path, config_json],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
       
        st.session_state.current_process = process
        st.session_state.call_active = True
        st.session_state.call_logs = []
       
        # Add to call history
        st.session_state.call_history.append({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'assistant_id': assistant_id,
            'user_name': user_name,
            'customer_info': customer_info,
            'status': 'started',
            'process_id': process.pid,
            'initiated_by': st.session_state.user_info['name']
        })
       
        return True, f"Call started (PID: {process.pid})"
       
    except Exception as e:
        st.session_state.call_active = False
        return False, f"Failed to start call: {str(e)}"

def stop_call_isolated():
    try:
        if st.session_state.current_process:
            st.session_state.current_process.terminate()
           
            try:
                st.session_state.current_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                st.session_state.current_process.kill()
                st.session_state.current_process.wait()
           
            st.session_state.current_process = None
       
        st.session_state.call_active = False
       
        # Update call history
        if st.session_state.call_history:
            st.session_state.call_history[-1]['status'] = 'stopped'
            st.session_state.call_history[-1]['ended_by'] = st.session_state.user_info['name']
       
        return True, "Call stopped successfully"
       
    except Exception as e:
        st.session_state.call_active = False
        st.session_state.current_process = None
        return False, f"Error stopping call: {str(e)}"

def check_call_status():
    if st.session_state.current_process:
        poll_result = st.session_state.current_process.poll()
        if poll_result is not None:
            st.session_state.call_active = False
            st.session_state.current_process = None
           
            if st.session_state.call_history:
                st.session_state.call_history[-1]['status'] = 'ended'
           
            return False, f"Call process ended with code: {poll_result}"
   
    return st.session_state.call_active, "Call is active"

# --- INITIALIZE SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}

# Call center session state
if "call_active" not in st.session_state:
    st.session_state.call_active = False
if "call_history" not in st.session_state:
    st.session_state.call_history = []
if "current_process" not in st.session_state:
    st.session_state.current_process = None
if "call_logs" not in st.session_state:
    st.session_state.call_logs = []

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
    call_active, status_msg = check_call_status()
    st.sidebar.write(f"**Call Active:** {'✅ Yes' if call_active else '❌ No'}")
    st.sidebar.write(f"**Total Calls:** {len(st.session_state.call_history)}")
    
    if st.session_state.current_process:
        st.sidebar.write(f"**Process ID:** {st.session_state.current_process.pid}")
    
    # Emergency controls
    st.sidebar.subheader("🚨 Emergency Controls")
    if st.sidebar.button("🔄 Reset Call System"):
        if st.session_state.current_process:
            try:
                st.session_state.current_process.kill()
            except:
                pass
        st.session_state.call_active = False
        st.session_state.current_process = None
        st.session_state.call_logs = []
        st.sidebar.success("Call system reset")
    
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
                    total_calls = len(st.session_state.call_history)
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>📞 Total Calls</h3>
                        <h2>{total_calls}</h2>
                    </div>
                    ''', unsafe_allow_html=True)
                
                # Call status indicator
                if st.session_state.call_active:
                    st.markdown(f'''
                    <div class="call-status-active">
                        <h3>🟢 Call Currently Active</h3>
                        <p>Process ID: {st.session_state.current_process.pid if st.session_state.current_process else 'Unknown'}</p>
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
                    st.dataframe(invoices_df, use_container_width=True)
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
            
            # --- ADVANCED CALL CENTER TAB ---
            with tab8:
                st.subheader("📞 Advanced Call Center with AI Agents")
                
                # Call status indicator
                call_active, status_msg = check_call_status()
                if call_active:
                    st.markdown(f'''
                    <div class="call-status-active">
                        <h3>🟢 Call Currently Active</h3>
                        <p>{status_msg}</p>
                        <p>Process ID: {st.session_state.current_process.pid if st.session_state.current_process else 'Unknown'}</p>
                        <p>Initiated by: {st.session_state.user_info['name']}</p>
                    </div>
                    ''', unsafe_allow_html=True)
                else:
                    st.markdown(f'''
                    <div class="call-status-inactive">
                        <h3>🔴 No Active Calls</h3>
                        <p>{status_msg}</p>
                        <p>Ready to initiate new calls</p>
                    </div>
                    ''', unsafe_allow_html=True)
                
                # Main call interface
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader("🤖 AI Agent Selection")
                    
                    # Display AI agent cards
                    for agent_key, agent_info in STATIC_AGENTS.items():
                        with st.expander(f"🤖 {agent_info['name']}", expanded=False):
                            st.markdown(f"""
                            <div class="agent-card">
                                <h4>{agent_info['name']}</h4>
                                <p><strong>Description:</strong> {agent_info['description']}</p>
                                <p><strong>Agent ID:</strong> {agent_info['id']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Customer selection and user input
                            col_customer, col_user = st.columns(2)
                            
                            with col_customer:
                                selected_customer = st.selectbox(
                                    "👤 Select Customer (optional):", 
                                    ["None"] + (customers_df["Name"].tolist() if not customers_df.empty else []),
                                    key=f"customer_{agent_key}"
                                )
                            
                            with col_user:
                                user_name = st.text_input(
                                    f"Your Name:", 
                                    value=st.session_state.user_info['name'],
                                    key=f"name_{agent_key}"
                                )
                            
                            # Prepare customer info
                            customer_info = None
                            if selected_customer != "None" and not customers_df.empty:
                                customer_row = customers_df[customers_df["Name"] == selected_customer].iloc[0]
                                customer_info = {
                                    "customer_name": customer_row.get("Name", ""),
                                    "customer_phone": customer_row.get("Phone Number", ""),
                                    "customer_email": customer_row.get("Email", ""),
                                    "customer_preference": customer_row.get("Preference", ""),
                                    "customer_notes": customer_row.get("Notes", "")
                                }
                            
                            # Call control buttons
                            col_start, col_stop = st.columns(2)
                            
                            with col_start:
                                if st.button(
                                    f"📞 Call with {agent_key}", 
                                    key=f"call_{agent_key}", 
                                    disabled=st.session_state.call_active,
                                    type="primary"
                                ):
                                    success, message = start_call_isolated(
                                        agent_info["id"], 
                                        user_name, 
                                        customer_info
                                    )
                                    if success:
                                        st.success(f"✅ {message}")
                                        st.balloons()
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                            
                            with col_stop:
                                if st.button(
                                    f"⛔ Stop Call", 
                                    key=f"stop_{agent_key}", 
                                    disabled=not st.session_state.call_active
                                ):
                                    success, message = stop_call_isolated()
                                    if success:
                                        st.success(f"📴 {message}")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                
                with col2:
                    st.subheader("📊 Call Center Stats")
                    
                    # Agent status overview
                    st.markdown("### 👥 Human Agent Status")
                    for agent_id, agent_info in CALL_CENTER_AGENTS.items():
                        status_color = {
                            "Available": "🟢",
                            "On Call": "🔴", 
                            "Break": "🟡",
                            "Training": "🔵"
                        }.get(agent_info["status"], "⚪")
                        
                        st.markdown(f"""
                        <div style="background: rgba(102, 126, 234, 0.1); padding: 0.5rem; border-radius: 5px; margin: 0.5rem 0;">
                            <strong>{status_color} {agent_info['name']}</strong><br>
                            <small>Status: {agent_info['status']} | Calls: {agent_info['calls_today']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Call metrics
                    st.markdown("### 📈 Call Metrics")
                    total_ai_calls = len(st.session_state.call_history)
                    total_human_calls = sum([a["calls_today"] for a in CALL_CENTER_AGENTS.values()])
                    available_agents = len([a for a in CALL_CENTER_AGENTS.values() if a["status"] == "Available"])
                    
                    st.metric("🤖 AI Calls Today", total_ai_calls)
                    st.metric("👥 Human Calls Today", total_human_calls)
                    st.metric("✅ Available Agents", available_agents)
                    st.metric("🎧 Your Role", st.session_state.user_info['role'])
                
                # Call history section
                st.subheader("📞 Recent Call History")
                if st.session_state.call_history:
                    # Display recent calls in a table format
                    history_df = pd.DataFrame(st.session_state.call_history[-10:])  # Last 10 calls
                    st.dataframe(history_df, use_container_width=True)
                    
                    # Call history analytics
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Calls by agent type
                        agent_counts = {}
                        for call in st.session_state.call_history:
                            agent_id = call['assistant_id']
                            agent_name = next((info['name'] for info in STATIC_AGENTS.values() if info['id'] == agent_id), agent_id)
                            agent_counts[agent_name] = agent_counts.get(agent_name, 0) + 1
                        
                        if agent_counts:
                            fig = px.pie(
                                values=list(agent_counts.values()), 
                                names=list(agent_counts.keys()),
                                title="Calls by AI Agent Type"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Calls over time
                        if len(st.session_state.call_history) > 1:
                            history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
                            calls_by_hour = history_df.groupby(history_df['timestamp'].dt.hour).size().reset_index()
                            calls_by_hour.columns = ['Hour', 'Calls']
                            
                            fig = px.bar(calls_by_hour, x='Hour', y='Calls', title="Calls by Hour")
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No call history yet. Start your first AI-powered call!")
                
                # Live process output
                if st.session_state.call_active:
                    st.subheader("📝 Live Call Process Output")
                    
                    # Try to read process output
                    if st.session_state.current_process:
                        try:
                            # Read available output
                            output = st.session_state.current_process.stdout.readline()
                            if output:
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                st.session_state.call_logs.append(f"[{timestamp}] {output.strip()}")
                                
                                # Keep only last 10 logs
                                if len(st.session_state.call_logs) > 10:
                                    st.session_state.call_logs = st.session_state.call_logs[-10:]
                        except:
                            pass
                    
                    # Display logs
                    if st.session_state.call_logs:
                        for log in st.session_state.call_logs:
                            st.text(log)
                    
                    # Auto-refresh for live updates
                    time.sleep(2)
                    st.rerun()
                
                # Instructions
                st.markdown("---")
                st.markdown("""
                💡 **Instructions:** 
                - Select an AI agent above based on your call purpose
                - Optionally select a customer from your CRM database
                - Enter your name (defaults to your logged-in name)
                - Click 'Call' to start an AI-powered conversation
                - Use 'Stop Call' or emergency controls to end the call
                - All calls are logged with full context including customer information
                """)
            
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
                    total_ai_calls = len(st.session_state.call_history)
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
                
                if st.session_state.call_history:
                    # Advanced call analytics
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Calls by user
                        user_calls = {}
                        for call in st.session_state.call_history:
                            user = call.get('initiated_by', 'Unknown')
                            user_calls[user] = user_calls.get(user, 0) + 1
                        
                        fig = px.bar(
                            x=list(user_calls.keys()), 
                            y=list(user_calls.values()),
                            title="Calls by User",
                            labels={'x': 'User', 'y': 'Number of Calls'}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Call status distribution
                        status_counts = {}
                        for call in st.session_state.call_history:
                            status = call.get('status', 'unknown')
                            status_counts[status] = status_counts.get(status, 0) + 1
                        
                        fig = px.pie(
                            values=list(status_counts.values()),
                            names=list(status_counts.keys()),
                            title="Call Status Distribution"
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
                            "call_history": st.session_state.call_history,
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
                            "total_ai_calls": len(st.session_state.call_history),
                            "team_breakdown": team_performance_data,
                            "call_analytics": {
                                "active_call": st.session_state.call_active,
                                "total_calls": len(st.session_state.call_history)
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
                            "call_history": st.session_state.call_history,
                            "ai_agents": STATIC_AGENTS,
                            "human_agents": CALL_CENTER_AGENTS,
                            "current_call_active": st.session_state.call_active,
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
                <h4>🚀 New: Advanced Call Center Features</h4>
                <p>✨ AI-powered customer calls with VAPI integration</p>
                <p>🎯 Customer context integration for personalized calls</p>
                <p>📊 Real-time call monitoring and analytics</p>
                <p>🔄 Seamless integration with CRM customer database</p>
            </div>
        </div>
        """.format(
            user_name=st.session_state.user_info['name'],
            user_role=st.session_state.user_info['role'],
            user_team=st.session_state.user_info['team'],
            total_members=sum(len(team["members"]) for team in TEAM_STRUCTURE.values())
        ), unsafe_allow_html=True)

