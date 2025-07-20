import streamlit as st
import pandas as pd
import numpy as np
import requests
import weasyprint
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
import os
import queue
import logging
from typing import Dict, List, Optional, Tuple, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure audio environment for headless operation
os.environ['PULSE_RUNTIME_PATH'] = '/tmp/pulse'
os.environ['ALSA_CARD'] = 'Dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

# Import VAPI with proper error handling
try:
    from vapi_python import Vapi
    VAPI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"VAPI Python library not available: {e}")
    VAPI_AVAILABLE = False

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="🧼 Auto Laundry CRM Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- THREAD-SAFE SESSION STATE MANAGER ---
class SessionStateManager:
    """Thread-safe session state manager"""
    
    def __init__(self):
        self._lock = threading.RLock()
    
    def get(self, key: str, default=None):
        """Thread-safe get from session state"""
        with self._lock:
            return st.session_state.get(key, default)
    
    def set(self, key: str, value):
        """Thread-safe set to session state"""
        with self._lock:
            st.session_state[key] = value
    
    def update(self, updates: Dict[str, Any]):
        """Thread-safe batch update"""
        with self._lock:
            for key, value in updates.items():
                st.session_state[key] = value
    
    def delete(self, key: str):
        """Thread-safe delete from session state"""
        with self._lock:
            if key in st.session_state:
                del st.session_state[key]
    
    def exists(self, key: str) -> bool:
        """Thread-safe check if key exists"""
        with self._lock:
            return key in st.session_state

# Initialize session state manager
session_manager = SessionStateManager()

# --- IMPROVED VAPI CALL MANAGER WITH BETTER THREADING ---
class ImprovedVAPICallManager:
    """Improved VAPI call manager with better threading and state management"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.vapi_client = None
        self.current_call = None
        self.call_thread = None
        self.is_calling = threading.Event()
        self.stop_monitoring = threading.Event()
        self.call_logs = queue.Queue(maxsize=100)
        self.call_history = []
        self.audio_configured = False
        self._lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="VAPI")
        
        # Initialize audio environment
        self._configure_audio_environment()
    
    def _configure_audio_environment(self) -> Tuple[bool, str]:
        """Configure audio environment for headless operation"""
        try:
            # Set environment variables for headless audio
            audio_env = {
                'SDL_AUDIODRIVER': 'dummy',
                'PULSE_RUNTIME_PATH': '/tmp/pulse',
                'ALSA_CARD': 'Dummy',
                'PULSE_RUNTIME_PATH': '/tmp/pulse-runtime'
            }
            
            for key, value in audio_env.items():
                os.environ[key] = value
            
            self._add_log("Audio environment configured for headless operation")
            self.audio_configured = True
            return True, "Audio environment configured successfully"
            
        except Exception as e:
            error_msg = f"Audio configuration warning: {e}"
            self._add_log(error_msg)
            # Continue without local audio - VAPI handles server-side
            self.audio_configured = True
            return True, "Audio configured (server-side only)"
    
    def _add_log(self, message: str):
        """Thread-safe log addition"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"{timestamp}: {message}"
        
        try:
            self.call_logs.put_nowait(log_entry)
        except queue.Full:
            # Remove oldest log if queue is full
            try:
                self.call_logs.get_nowait()
                self.call_logs.put_nowait(log_entry)
            except queue.Empty:
                pass
    
    def initialize_client(self) -> Tuple[bool, str]:
        """Initialize VAPI client with proper error handling"""
        with self._lock:
            try:
                if not VAPI_AVAILABLE:
                    return False, "VAPI Python library not available"
                
                if not self.audio_configured:
                    self._configure_audio_environment()
                
                # Initialize VAPI client
                self.vapi_client = Vapi(api_key=self.api_key)
                self._add_log("VAPI client initialized successfully")
                return True, "VAPI client initialized successfully"
                
            except Exception as e:
                error_msg = f"Failed to initialize VAPI client: {str(e)}"
                self._add_log(f"ERROR - {error_msg}")
                return False, error_msg
    
    def start_call(self, assistant_id: str, overrides: Optional[Dict] = None, 
                   phone_number: Optional[str] = None) -> Tuple[bool, str]:
        """Start a VAPI call with improved error handling"""
        with self._lock:
            try:
                if self.is_calling.is_set():
                    return False, "A call is already in progress"
                
                if not self.vapi_client:
                    success, msg = self.initialize_client()
                    if not success:
                        return False, msg
                
                # Prepare call parameters
                call_params = {"assistant_id": assistant_id}
                
                if overrides:
                    call_params["assistant_overrides"] = overrides
                
                if phone_number:
                    call_params["customer"] = {"number": phone_number}
                
                self._add_log(f"Starting call with assistant {assistant_id}")
                
                # Start the call
                self.current_call = self.vapi_client.start(**call_params)
                self.is_calling.set()
                self.stop_monitoring.clear()
                
                # Add to call history
                call_record = {
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'assistant_id': assistant_id,
                    'status': 'started',
                    'call_id': getattr(self.current_call, 'id', 'unknown'),
                    'phone_number': phone_number,
                    'audio_mode': 'server-side'
                }
                self.call_history.append(call_record)
                
                # Start monitoring in thread pool
                self.call_thread = self.executor.submit(self._monitor_call)
                
                success_msg = f"Call started successfully. Call ID: {getattr(self.current_call, 'id', 'unknown')}"
                self._add_log(success_msg)
                return True, success_msg
                
            except Exception as e:
                self.is_calling.clear()
                error_msg = self._format_error_message(str(e))
                self._add_log(f"ERROR - {error_msg}")
                return False, error_msg
    
    def stop_call(self) -> Tuple[bool, str]:
        """Stop the current VAPI call"""
        with self._lock:
            try:
                if not self.is_calling.is_set():
                    return False, "No active call to stop"
                
                # Signal monitoring to stop
                self.stop_monitoring.set()
                
                if self.vapi_client and self.current_call:
                    self.vapi_client.stop()
                    self._add_log("Call stopped by user")
                
                self.is_calling.clear()
                self.current_call = None
                
                # Update call history
                if self.call_history:
                    self.call_history[-1]['status'] = 'stopped'
                    self.call_history[-1]['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                return True, "Call stopped successfully"
                
            except Exception as e:
                self.is_calling.clear()
                self.current_call = None
                error_msg = f"Error stopping call: {str(e)}"
                self._add_log(f"ERROR - {error_msg}")
                return False, error_msg
    
    def _monitor_call(self):
        """Monitor call status in background thread"""
        try:
            while self.is_calling.is_set() and not self.stop_monitoring.is_set():
                if self.current_call:
                    self._add_log("Call is active (server-side audio)")
                
                # Check every 10 seconds or until stop signal
                if self.stop_monitoring.wait(timeout=10):
                    break
                    
        except Exception as e:
            self._add_log(f"Monitor error - {str(e)}")
        finally:
            if self.is_calling.is_set():
                self.is_calling.clear()
                if self.call_history:
                    self.call_history[-1]['status'] = 'ended'
                    self.call_history[-1]['end_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_call_status(self) -> Dict[str, Any]:
        """Get current call status thread-safely"""
        with self._lock:
            # Convert queue to list for display
            logs = []
            temp_logs = []
            
            # Get all logs from queue
            while not self.call_logs.empty():
                try:
                    log = self.call_logs.get_nowait()
                    temp_logs.append(log)
                    logs.append(log)
                except queue.Empty:
                    break
            
            # Put logs back in queue
            for log in temp_logs:
                try:
                    self.call_logs.put_nowait(log)
                except queue.Full:
                    break
            
            return {
                'is_calling': self.is_calling.is_set(),
                'call_id': getattr(self.current_call, 'id', None) if self.current_call else None,
                'logs': logs[-20:],  # Last 20 log entries
                'history': self.call_history.copy(),
                'audio_configured': self.audio_configured,
                'vapi_available': VAPI_AVAILABLE
            }
    
    def clear_logs(self):
        """Clear call logs thread-safely"""
        with self._lock:
            while not self.call_logs.empty():
                try:
                    self.call_logs.get_nowait()
                except queue.Empty:
                    break
    
    def _format_error_message(self, error: str) -> str:
        """Format error messages with helpful context"""
        if "Invalid input device" in error or "no default output device" in error:
            return "Audio device error detected. This is normal in server environments - VAPI handles audio server-side."
        elif "PyAudio" in error:
            return f"Audio system error: {error}. This may be due to server environment limitations."
        else:
            return f"Call error: {error}"
    
    def cleanup(self):
        """Cleanup resources"""
        with self._lock:
            self.stop_monitoring.set()
            if self.is_calling.is_set():
                self.stop_call()
            self.executor.shutdown(wait=True)

# --- IMPROVED SESSION STATE INITIALIZATION ---
def initialize_session_state():
    """Initialize all session state variables with thread safety"""
    defaults = {
        'logged_in': False,
        'user_info': {},
        'username': '',
        'vapi_manager': None,
        'show_descriptions': False,
        'messages': [],
        'call_status_last_update': time.time(),
        'auto_refresh_enabled': True
    }
    
    for key, default_value in defaults.items():
        if not session_manager.exists(key):
            session_manager.set(key, default_value)

# Initialize session state
initialize_session_state()

# --- UTILITY FUNCTIONS ---
def calculate_analytics_with_numpy(data):
    """Use numpy for advanced analytics calculations"""
    if not data:
        return {}
    
    try:
        values = np.array([float(item.get('amount', 0)) for item in data])
        return {
            'mean': np.mean(values),
            'std': np.std(values),
            'median': np.median(values),
            'total': np.sum(values),
            'percentile_75': np.percentile(values, 75),
            'percentile_25': np.percentile(values, 25)
        }
    except Exception as e:
        logger.error(f"Analytics calculation error: {e}")
        return {}

def fetch_external_data_with_requests(url=None):
    """Use requests library for external API calls"""
    try:
        if not url:
            url = "https://api.exchangerate-api.com/v4/latest/USD"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def process_dataframe_with_pandas(data):
    """Use pandas for advanced data processing"""
    if not data:
        return pd.DataFrame()
    
    try:
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
    except Exception as e:
        logger.error(f"DataFrame processing error: {e}")
        return pd.DataFrame()

def fix_dataframe_types(df):
    """Fix PyArrow data type conversion issues"""
    if df.empty:
        return df
    
    try:
        string_columns = [
            'Phone Number', 'Phone', 'phone', 'phone_number',
            'Customer ID', 'customer_id', 'ID', 'id',
            'Order ID', 'order_id', 'Invoice Number', 'invoice_number',
            'Account Number', 'account_number', 'Reference', 'reference',
            'Zip Code', 'zip_code', 'Postal Code', 'postal_code'
        ]
        
        for col in df.columns:
            if any(string_col.lower() in col.lower() for string_col in string_columns):
                df[col] = df[col].fillna('').astype(str)
        
        return df
    except Exception as e:
        logger.error(f"DataFrame type fixing error: {e}")
        return df

# --- CONSTANTS ---
DEMO_ACCOUNTS = {
    "admin": {"password": "admin123", "role": "Admin", "team": "Management", "name": "John Admin"},
    "manager1": {"password": "manager123", "role": "Manager", "team": "Operations", "name": "Sarah Manager"},
    "agent1": {"password": "agent123", "role": "Agent", "team": "Customer Service", "name": "Mike Agent"},
    "supervisor1": {"password": "super123", "role": "Supervisor", "team": "Quality Control", "name": "Emma Supervisor"},
    "demo": {"password": "demo123", "role": "Demo User", "team": "Demo", "name": "Demo User"}
}

TEAM_STRUCTURE = {
    "Management": {
        "team_lead": "John Admin",
        "members": [
            {"name": "John Admin", "role": "Admin", "status": "Active", "login": "admin"},
            {"name": "Lisa Director", "role": "Director", "status": "Active", "login": "director1"},
        ]
    },
    "Operations": {
        "team_lead": "Sarah Manager",
        "members": [
            {"name": "Sarah Manager", "role": "Operations Manager", "status": "Active", "login": "manager1"},
            {"name": "Tom Operator", "role": "Senior Operator", "status": "Active", "login": "op1"},
        ]
    },
    "Customer Service": {
        "team_lead": "Mike Agent",
        "members": [
            {"name": "Mike Agent", "role": "Senior Agent", "status": "Active", "login": "agent1"},
            {"name": "Kelly Support", "role": "Support Agent", "status": "Active", "login": "support1"},
        ]
    }
}

# Hardcoded credentials
DEFAULT_CUSTOMERS_SHEET = "https://docs.google.com/spreadsheets/d/1LZvUQwceVE1dyCjaNod0DPOhHaIGLLBqomCDgxiWuBg/edit?gid=392374958#gid=392374958"
DEFAULT_N8N_WEBHOOK = "https://agentonline-u29564.vm.elestio.app/webhook/bf7aec67-cce8-4bd6-81f1-f04f84b992f7"

STATIC_AGENTS = {
    "Customer Support": {
        "id": "7b2b8b86-5caa-4f28-8c6b-e7d3d0404f06",
        "name": "Customer Support Agent",
        "description": "Resolves product issues and ensures customer satisfaction."
    },
    "Sales Assistant": {
        "id": "232f3d9c-18b3-4963-bdd9-e7de3be156ae",
        "name": "Sales Assistant",
        "description": "Identifies prospects and connects them with sales representatives."
    }
}

# --- LOGIN FUNCTIONS ---
def login_user(username, password):
    """Authenticate user"""
    if username in DEMO_ACCOUNTS and DEMO_ACCOUNTS[username]["password"] == password:
        return DEMO_ACCOUNTS[username]
    return None

def logout_user():
    """Logout user and cleanup"""
    # Cleanup VAPI manager
    vapi_manager = session_manager.get('vapi_manager')
    if vapi_manager:
        vapi_manager.cleanup()
    
    # Clear session state
    keys_to_clear = [key for key in st.session_state.keys() if key.startswith('user_') or key in ['logged_in', 'vapi_manager']]
    for key in keys_to_clear:
        session_manager.delete(key)
    
    session_manager.set('logged_in', False)

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
    .audio-warning {
        background: linear-gradient(135deg, #ff9a56 0%, #ff6b6b 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- MAIN APPLICATION ---
if not session_manager.get('logged_in'):
    # LOGIN PAGE
    st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 15px; color: white; text-align: center; margin: 2rem 0;">
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
                    session_manager.update({
                        'logged_in': True,
                        'user_info': user_info,
                        'username': username
                    })
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
    # MAIN APPLICATION
    user_info = session_manager.get('user_info')
    
    # Header with user info
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%); padding: 1rem; border-radius: 10px; margin: 1rem 0; text-align: center; color: #333;">
            <strong>👤 {user_info['name']}</strong><br>
            <small>{user_info['role']} | {user_info['team']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        if st.button("🚪 Logout", type="secondary"):
            logout_user()
            st.rerun()
    
    # Initialize VAPI manager if needed
    if not session_manager.get('vapi_manager'):
        try:
            api_key = st.secrets.get("VAPI_API_KEY")
            if api_key:
                vapi_manager = ImprovedVAPICallManager(api_key)
                session_manager.set('vapi_manager', vapi_manager)
        except Exception as e:
            logger.error(f"Failed to initialize VAPI manager: {e}")
    
    # Sidebar
    st.sidebar.markdown("### 🔐 Authentication")
    auth_file = st.sidebar.file_uploader("Upload service_account.json", type="json")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Current User:** {user_info['name']}")
    st.sidebar.markdown(f"**Role:** {user_info['role']}")
    st.sidebar.markdown(f"**Team:** {user_info['team']}")
    
    # Call status in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📞 Call Center Status")
    
    vapi_manager = session_manager.get('vapi_manager')
    if vapi_manager:
        status = vapi_manager.get_call_status()
        st.sidebar.write(f"**Call Active:** {'✅ Yes' if status['is_calling'] else '❌ No'}")
        st.sidebar.write(f"**Total Calls:** {len(status['history'])}")
        st.sidebar.write(f"**VAPI Available:** {'✅ Yes' if status['vapi_available'] else '❌ No'}")
        if status['call_id']:
            st.sidebar.write(f"**Call ID:** {status['call_id']}")
    else:
        st.sidebar.write("**VAPI Manager:** Not initialized")
    
    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏠 Dashboard",
        "📞 Call Center",
        "👥 Team Management",
        "📊 Analytics"
    ])
    
    with tab1:
        st.subheader("📊 CRM Dashboard")
        st.markdown(f"### Welcome back, {user_info['name']}! 👋")
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('''
            <div class="metric-card">
                <h3>👥 Total Users</h3>
                <h2>5</h2>
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
            st.markdown('''
            <div class="metric-card">
                <h3>🧾 Total Invoices</h3>
                <h2>0</h2>
            </div>
            ''', unsafe_allow_html=True)
        
        with col4:
            total_calls = len(vapi_manager.get_call_status()['history']) if vapi_manager else 0
            st.markdown(f'''
            <div class="metric-card">
                <h3>📞 Total Calls</h3>
                <h2>{total_calls}</h2>
            </div>
            ''', unsafe_allow_html=True)
        
        # Call status indicator
        if vapi_manager:
            status = vapi_manager.get_call_status()
            if status['is_calling']:
                st.markdown(f'''
                <div class="call-status-active">
                    <h3>🟢 Call Currently Active</h3>
                    <p>Call ID: {status['call_id'] or 'Unknown'}</p>
                    <p>Audio Mode: Server-side</p>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown('''
                <div class="call-status-inactive">
                    <h3>🔴 No Active Calls</h3>
                    <p>Ready to initiate new calls</p>
                </div>
                ''', unsafe_allow_html=True)
    
    with tab2:
        st.subheader("📞 AI Agent Caller - Improved Threading & State Management")
        
        if not VAPI_AVAILABLE:
            st.markdown('''
            <div class="audio-warning">
                <h3>⚠️ VAPI Library Not Available</h3>
                <p>The vapi_python library is not installed. Please install it to use call features.</p>
            </div>
            ''', unsafe_allow_html=True)
        
        if vapi_manager and VAPI_AVAILABLE:
            # Audio environment info
            st.markdown('''
            <div class="audio-warning">
                <h3>🔊 Audio Environment - Server Optimized</h3>
                <p><strong>Threading:</strong> Improved with ThreadPoolExecutor and proper cleanup</p>
                <p><strong>State Management:</strong> Thread-safe session state with locks</p>
                <p><strong>Audio:</strong> Server-side handling, no local devices required</p>
                <p><strong>Error Handling:</strong> Comprehensive error catching and recovery</p>
            </div>
            ''', unsafe_allow_html=True)
            
            # Status and controls
            col1, col2 = st.columns([2, 1])
            
            with col2:
                st.subheader("📊 Status")
                status = vapi_manager.get_call_status()
                st.write(f"**Call Active:** {'✅ Yes' if status['is_calling'] else '❌ No'}")
                st.write(f"**Total Calls:** {len(status['history'])}")
                st.write(f"**Audio Configured:** {'✅ Yes' if status['audio_configured'] else '❌ No'}")
                
                if status['call_id']:
                    st.write(f"**Call ID:** {status['call_id']}")
            
            with col1:
                st.subheader("🎛️ Call Controls")
                
                # Agent selection
                agent_options = list(STATIC_AGENTS.keys())
                selected_agent_key = st.selectbox("Choose Assistant", agent_options)
                selected_agent = STATIC_AGENTS[selected_agent_key]
                
                # Call configuration
                col_a, col_b = st.columns(2)
                with col_a:
                    user_name = st.text_input("Your Name:", placeholder="Enter your name")
                    phone_number = st.text_input("Phone Number:", placeholder="+1234567890")
                
                with col_b:
                    additional_context = st.text_area("Additional Context:", placeholder="Any specific information")
                
                # Call buttons
                col_x, col_y, col_z = st.columns(3)
                
                with col_x:
                    start_disabled = status['is_calling']
                    if st.button("▶️ Start Call", disabled=start_disabled, use_container_width=True):
                        overrides = {}
                        if user_name:
                            overrides["variableValues"] = {"name": user_name}
                        if additional_context:
                            overrides["context"] = additional_context
                        
                        success, message = vapi_manager.start_call(
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
                
                with col_y:
                    stop_disabled = not status['is_calling']
                    if st.button("⛔ Stop Call", disabled=stop_disabled, use_container_width=True):
                        success, message = vapi_manager.stop_call()
                        if success:
                            st.success(f"📴 {message}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                
                with col_z:
                    if st.button("🔄 Refresh", use_container_width=True):
                        st.rerun()
            
            # Call history and logs
            tab_history, tab_logs = st.tabs(["Call History", "Live Logs"])
            
            with tab_history:
                st.subheader("📞 Call History")
                if status['history']:
                    for call in reversed(status['history'][-10:]):
                        status_icon = {"started": "🟡", "stopped": "✅", "ended": "🔴"}.get(call['status'], "❓")
                        st.write(f"{status_icon} **{call['timestamp']}** - {call['assistant_id']} ({call['status']})")
                        if 'call_id' in call:
                            st.caption(f"Call ID: {call['call_id']}")
                else:
                    st.info("No calls made yet.")
            
            with tab_logs:
                st.subheader("📝 Live Call Logs")
                if status['logs']:
                    for log in status['logs']:
                        st.text(log)
                else:
                    st.info("No logs available.")
            
            # Auto-refresh for active calls (less aggressive)
            if status['is_calling']:
                current_time = time.time()
                last_update = session_manager.get('call_status_last_update', 0)
                
                if current_time - last_update > 10:  # Update every 10 seconds
                    session_manager.set('call_status_last_update', current_time)
                    time.sleep(1)
                    st.rerun()
        
        else:
            st.error("❌ VAPI manager not available. Please check your API key configuration.")
    
    with tab3:
        st.subheader("👥 Team Management")
        st.markdown(f"**Your Access Level:** {user_info['role']}")
        
        for team_name, team_info in TEAM_STRUCTURE.items():
            with st.expander(f"🏢 {team_name} Team ({len(team_info['members'])} members)"):
                st.markdown(f"**Team Lead:** {team_info['team_lead']}")
                
                team_df = pd.DataFrame(team_info['members'])
                team_df = fix_dataframe_types(team_df)
                st.dataframe(team_df, use_container_width=True)
                
                active_members = len([m for m in team_info['members'] if m['status'] == 'Active'])
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("👥 Total Members", len(team_info['members']))
                with col2:
                    st.metric("✅ Active", active_members)
                with col3:
                    st.metric("📊 Team Load", f"{active_members * 20}%")
    
    with tab4:
        st.subheader("📊 Advanced Analytics")
        
        # Analytics metrics
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
            total_ai_calls = len(vapi_manager.get_call_status()['history']) if vapi_manager else 0
            st.markdown(f'''
            <div class="metric-card">
                <h3>🤖 AI Calls</h3>
                <h2>{total_ai_calls}</h2>
            </div>
            ''', unsafe_allow_html=True)
        
        with col4:
            st.markdown('''
            <div class="metric-card">
                <h3>💰 Avg Price</h3>
                <h2>$18.50</h2>
            </div>
            ''', unsafe_allow_html=True)
        
        # Call analytics
        if vapi_manager:
            status = vapi_manager.get_call_status()
            if status['history']:
                st.subheader("📞 Call Analytics")
                
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
        
        # Export functionality
        st.subheader("📥 Data Export")
        if st.button("📥 Export System Data"):
            export_data = {
                "user_info": user_info,
                "teams": TEAM_STRUCTURE,
                "call_history": vapi_manager.get_call_status()['history'] if vapi_manager else [],
                "exported_by": user_info['name'],
                "export_time": datetime.now().isoformat()
            }
            
            st.download_button(
                label="Download System Export (JSON)",
                data=json.dumps(export_data, indent=2),
                file_name=f"crm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

# Cleanup on app shutdown
import atexit

def cleanup_resources():
    """Cleanup resources on app shutdown"""
    vapi_manager = session_manager.get('vapi_manager')
    if vapi_manager:
        vapi_manager.cleanup()

atexit.register(cleanup_resources)
