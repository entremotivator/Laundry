import streamlit as st
import pandas as pd
import numpy as np
import requests
import weasyprint
from vapi_python import Vapi
import gspread
from google.oauth2.service_account import Credentials
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
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
import uuid
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="🧼 Auto Laundry CRM Pro Enhanced", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ENHANCED DATA MODELS ---
class LeadStatus(Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    QUALIFIED = "Qualified"
    PROPOSAL = "Proposal Sent"
    NEGOTIATION = "Negotiation"
    CLOSED_WON = "Closed Won"
    CLOSED_LOST = "Closed Lost"

class CallStatus(Enum):
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"

@dataclass
class Lead:
    id: str
    name: str
    email: str
    phone: str
    status: LeadStatus
    score: int
    source: str
    assigned_to: str
    created_date: datetime
    last_contact: Optional[datetime] = None
    notes: str = ""
    estimated_value: float = 0.0

@dataclass
class CallRecord:
    id: str
    lead_id: str
    agent_id: str
    status: CallStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: int = 0
    notes: str = ""
    recording_url: str = ""
    sentiment_score: float = 0.0

# --- ENHANCED VAPI CALL MANAGER ---
class EnhancedVAPICallManager:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.vapi_client = None
        self.active_calls: Dict[str, Any] = {}
        self.call_queue: List[Dict] = []
        self.call_history: List[CallRecord] = []
        self.agent_sessions: Dict[str, Dict] = {}
        self.call_analytics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'average_duration': 0,
            'sentiment_scores': []
        }
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.lock = threading.Lock()
        
    def initialize_client(self) -> tuple[bool, str]:
        """Initialize VAPI client with enhanced error handling"""
        try:
            self.vapi_client = Vapi(api_key=self.api_key)
            return True, "Enhanced VAPI client initialized successfully"
        except Exception as e:
            logging.error(f"VAPI initialization failed: {e}")
            return False, f"Failed to initialize VAPI client: {str(e)}"
    
    def create_agent_session(self, agent_id: str, config: Dict) -> str:
        """Create a new agent session with configuration"""
        session_id = str(uuid.uuid4())
        with self.lock:
            self.agent_sessions[session_id] = {
                'agent_id': agent_id,
                'config': config,
                'created_at': datetime.now(),
                'status': 'active',
                'call_count': 0
            }
        return session_id
    
    def start_enhanced_call(self, session_id: str, phone_number: str, 
                          lead_data: Dict, overrides: Dict = None) -> tuple[bool, str]:
        """Start an enhanced call with lead context and session management"""
        try:
            if not self.vapi_client:
                success, msg = self.initialize_client()
                if not success:
                    return False, msg
            
            session = self.agent_sessions.get(session_id)
            if not session:
                return False, "Invalid session ID"
            
            # Prepare enhanced call parameters
            call_params = {
                "assistant_id": session['config']['assistant_id'],
                "customer": {"number": phone_number},
                "assistant_overrides": {
                    "variableValues": {
                        "customer_name": lead_data.get('name', 'Customer'),
                        "customer_history": lead_data.get('history', ''),
                        "lead_score": str(lead_data.get('score', 0)),
                        "previous_interactions": lead_data.get('interactions', ''),
                        "session_id": session_id
                    }
                }
            }
            
            if overrides:
                call_params["assistant_overrides"].update(overrides)
            
            # Start the call
            call_response = self.vapi_client.start(**call_params)
            call_id = getattr(call_response, 'id', str(uuid.uuid4()))
            
            # Create call record
            call_record = CallRecord(
                id=call_id,
                lead_id=lead_data.get('id', ''),
                agent_id=session['agent_id'],
                status=CallStatus.IN_PROGRESS,
                start_time=datetime.now()
            )
            
            with self.lock:
                self.active_calls[call_id] = {
                    'record': call_record,
                    'session_id': session_id,
                    'phone_number': phone_number,
                    'lead_data': lead_data
                }
                session['call_count'] += 1
                self.call_analytics['total_calls'] += 1
            
            # Start monitoring in background
            self.executor.submit(self._monitor_enhanced_call, call_id)
            
            return True, f"Enhanced call started successfully. Call ID: {call_id}"
            
        except Exception as e:
            logging.error(f"Enhanced call start failed: {e}")
            return False, f"Failed to start enhanced call: {str(e)}"
    
    def _monitor_enhanced_call(self, call_id: str):
        """Enhanced call monitoring with analytics"""
        try:
            while call_id in self.active_calls:
                call_info = self.active_calls[call_id]
                
                # Simulate call progress monitoring
                # In real implementation, you'd use VAPI's call status API
                time.sleep(5)
                
                # Update call analytics
                with self.lock:
                    if call_id in self.active_calls:
                        duration = (datetime.now() - call_info['record'].start_time).seconds
                        call_info['record'].duration = duration
                
        except Exception as e:
            logging.error(f"Call monitoring error: {e}")
        finally:
            self._finalize_call(call_id)
    
    def _finalize_call(self, call_id: str):
        """Finalize call and update analytics"""
        if call_id in self.active_calls:
            with self.lock:
                call_info = self.active_calls[call_id]
                call_record = call_info['record']
                call_record.end_time = datetime.now()
                call_record.status = CallStatus.COMPLETED
                
                # Add to history
                self.call_history.append(call_record)
                
                # Update analytics
                self.call_analytics['successful_calls'] += 1
                durations = [c.duration for c in self.call_history if c.duration > 0]
                if durations:
                    self.call_analytics['average_duration'] = sum(durations) / len(durations)
                
                # Remove from active calls
                del self.active_calls[call_id]
    
    def get_enhanced_status(self) -> Dict:
        """Get comprehensive call manager status"""
        with self.lock:
            return {
                'active_calls': len(self.active_calls),
                'total_sessions': len(self.agent_sessions),
                'call_history_count': len(self.call_history),
                'analytics': self.call_analytics.copy(),
                'recent_calls': [asdict(c) for c in self.call_history[-10:]],
                'active_sessions': {k: v for k, v in self.agent_sessions.items() if v['status'] == 'active'}
            }

# --- ENHANCED CRM FEATURES ---
class CRMPipeline:
    def __init__(self):
        self.stages = [status.value for status in LeadStatus]
        self.conversion_rates = {
            "New": 0.8,
            "Contacted": 0.6,
            "Qualified": 0.4,
            "Proposal Sent": 0.3,
            "Negotiation": 0.7,
            "Closed Won": 1.0,
            "Closed Lost": 0.0
        }
    
    def calculate_lead_score(self, lead_data: Dict) -> int:
        """Calculate lead score based on various factors"""
        score = 50  # Base score
        
        # Email domain scoring
        if lead_data.get('email', '').endswith(('.com', '.org')):
            score += 10
        
        # Phone number presence
        if lead_data.get('phone'):
            score += 15
        
        # Interaction history
        interactions = lead_data.get('interactions', 0)
        score += min(interactions * 5, 25)
        
        # Time since last contact
        last_contact = lead_data.get('last_contact')
        if last_contact:
            days_since = (datetime.now() - last_contact).days
            if days_since < 7:
                score += 10
            elif days_since > 30:
                score -= 10
        
        return max(0, min(100, score))
    
    def get_pipeline_metrics(self, leads: List[Dict]) -> Dict:
        """Calculate pipeline metrics"""
        stage_counts = {}
        stage_values = {}
        
        for lead in leads:
            status = lead.get('status', 'New')
            value = lead.get('estimated_value', 0)
            
            stage_counts[status] = stage_counts.get(status, 0) + 1
            stage_values[status] = stage_values.get(status, 0) + value
        
        return {
            'stage_counts': stage_counts,
            'stage_values': stage_values,
            'total_pipeline_value': sum(stage_values.values()),
            'weighted_pipeline': sum(
                stage_values.get(stage, 0) * self.conversion_rates.get(stage, 0)
                for stage in self.stages
            )
        }

# --- ENHANCED GRID CONFIGURATIONS ---
def create_enhanced_customer_grid(df: pd.DataFrame) -> AgGrid:
    """Create enhanced customer grid with advanced features"""
    
    # Custom cell renderers
    status_renderer = JsCode("""
    function(params) {
        const status = params.value;
        const colors = {
            'New': '#28a745',
            'Contacted': '#17a2b8',
            'Qualified': '#ffc107',
            'Proposal Sent': '#fd7e14',
            'Negotiation': '#6f42c1',
            'Closed Won': '#28a745',
            'Closed Lost': '#dc3545'
        };
        const color = colors[status] || '#6c757d';
        return `<span style="background-color: ${color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">${status}</span>`;
    }
    """)
    
    score_renderer = JsCode("""
    function(params) {
        const score = params.value;
        let color = '#dc3545';
        if (score >= 80) color = '#28a745';
        else if (score >= 60) color = '#ffc107';
        else if (score >= 40) color = '#fd7e14';
        
        return `<div style="display: flex; align-items: center;">
            <div style="width: 50px; height: 8px; background-color: #e9ecef; border-radius: 4px; margin-right: 8px;">
                <div style="width: ${score}%; height: 100%; background-color: ${color}; border-radius: 4px;"></div>
            </div>
            <span>${score}</span>
        </div>`;
    }
    """)
    
    # Build grid options
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # Configure columns
    gb.configure_column("Status", cellRenderer=status_renderer, width=120)
    gb.configure_column("Lead Score", cellRenderer=score_renderer, width=150)
    gb.configure_column("Phone", width=130)
    gb.configure_column("Email", width=200)
    gb.configure_column("Estimated Value", type=["numericColumn", "numberColumnFilter"], width=140)
    
    # Configure grid features
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=20)
    gb.configure_side_bar(filters_panel=True, columns_panel=True)
    gb.configure_selection('multiple', use_checkbox=True, groupSelectsChildren=True)
    gb.configure_default_column(
        editable=True, 
        groupable=True, 
        value=True, 
        enableRowGroup=True, 
        aggFunc='sum', 
        enableRangeSelection=True
    )
    
    # Add context menu
    gb.configure_grid_options(
        enableRangeSelection=True,
        enableCharts=True,
        allowContextMenuWithControlKey=True,
        getContextMenuItems=JsCode("""
        function(params) {
            return [
                'copy',
                'copyWithHeaders',
                'paste',
                'separator',
                'export',
                'separator',
                {
                    name: 'Call Customer',
                    action: function() {
                        alert('Initiating call to ' + params.node.data.Name);
                    }
                },
                {
                    name: 'Send Email',
                    action: function() {
                        alert('Opening email to ' + params.node.data.Email);
                    }
                }
            ];
        }
        """)
    )
    
    return gb.build()

# --- ENHANCED SESSION STATE MANAGEMENT ---
class SessionStateManager:
    @staticmethod
    def initialize_enhanced_state():
        """Initialize enhanced session state variables"""
        defaults = {
            'enhanced_vapi_manager': None,
            'crm_pipeline': CRMPipeline(),
            'active_lead_filters': {},
            'dashboard_refresh_interval': 30,
            'call_queue': [],
            'agent_performance': {},
            'custom_fields': {},
            'automation_rules': [],
            'notification_settings': {
                'email_alerts': True,
                'call_reminders': True,
                'pipeline_updates': True
            },
            'user_preferences': {
                'default_view': 'grid',
                'items_per_page': 20,
                'auto_refresh': True
            }
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def get_user_context() -> Dict:
        """Get comprehensive user context"""
        return {
            'user_info': st.session_state.get('user_info', {}),
            'permissions': SessionStateManager.get_user_permissions(),
            'preferences': st.session_state.get('user_preferences', {}),
            'active_session_time': datetime.now().isoformat()
        }
    
    @staticmethod
    def get_user_permissions() -> Dict:
        """Get user permissions based on role"""
        role = st.session_state.get('user_info', {}).get('role', 'Demo User')
        
        permissions = {
            'Admin': {
                'can_edit_all': True,
                'can_delete': True,
                'can_manage_users': True,
                'can_access_analytics': True,
                'can_make_calls': True,
                'can_export_data': True
            },
            'Manager': {
                'can_edit_all': True,
                'can_delete': False,
                'can_manage_users': False,
                'can_access_analytics': True,
                'can_make_calls': True,
                'can_export_data': True
            },
            'Agent': {
                'can_edit_all': False,
                'can_delete': False,
                'can_manage_users': False,
                'can_access_analytics': False,
                'can_make_calls': True,
                'can_export_data': False
            }
        }
        
        return permissions.get(role, permissions['Agent'])

# --- DEMO DATA ENHANCEMENT ---
ENHANCED_DEMO_ACCOUNTS = {
    "admin": {"password": "admin123", "role": "Admin", "team": "Management", "name": "John Admin"},
    "manager1": {"password": "manager123", "role": "Manager", "team": "Operations", "name": "Sarah Manager"},
    "agent1": {"password": "agent123", "role": "Agent", "team": "Customer Service", "name": "Mike Agent"},
    "supervisor1": {"password": "super123", "role": "Supervisor", "team": "Quality Control", "name": "Emma Supervisor"},
    "demo": {"password": "demo123", "role": "Demo User", "team": "Demo", "name": "Demo User"}
}

# Enhanced sample data
SAMPLE_LEADS = [
    {
        'id': str(uuid.uuid4()),
        'name': 'Acme Corporation',
        'email': 'contact@acme.com',
        'phone': '+1-555-0101',
        'status': 'Qualified',
        'score': 85,
        'source': 'Website',
        'assigned_to': 'Mike Agent',
        'estimated_value': 5000.0,
        'created_date': datetime.now() - timedelta(days=5),
        'last_contact': datetime.now() - timedelta(days=2),
        'notes': 'Large corporate client, interested in weekly service'
    },
    {
        'id': str(uuid.uuid4()),
        'name': 'Tech Startup Inc',
        'email': 'hello@techstartup.com',
        'phone': '+1-555-0102',
        'status': 'Proposal Sent',
        'score': 72,
        'source': 'Referral',
        'assigned_to': 'Sarah Manager',
        'estimated_value': 3000.0,
        'created_date': datetime.now() - timedelta(days=10),
        'last_contact': datetime.now() - timedelta(days=1),
        'notes': 'Fast-growing startup, needs flexible scheduling'
    },
    {
        'id': str(uuid.uuid4()),
        'name': 'Local Restaurant',
        'email': 'manager@restaurant.com',
        'phone': '+1-555-0103',
        'status': 'New',
        'score': 45,
        'source': 'Cold Call',
        'assigned_to': 'Mike Agent',
        'estimated_value': 1200.0,
        'created_date': datetime.now() - timedelta(days=1),
        'notes': 'Small business, price-sensitive'
    }
]

# --- ENHANCED CSS ---
ENHANCED_CSS = """
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        font-size: 2.8rem;
        font-weight: bold;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
    }
    
    .enhanced-metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 20px;
        color: white;
        margin: 0.5rem 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
        text-align: center;
        transition: transform 0.3s ease;
    }
    
    .enhanced-metric-card:hover {
        transform: translateY(-5px);
    }
    
    .pipeline-stage {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
        transition: all 0.3s ease;
    }
    
    .pipeline-stage:hover {
        box-shadow: 0 8px 30px rgba(0,0,0,0.15);
        transform: translateX(5px);
    }
    
    .call-status-enhanced {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(76, 175, 80, 0.3);
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 4px 20px rgba(76, 175, 80, 0.3); }
        50% { box-shadow: 0 4px 30px rgba(76, 175, 80, 0.5); }
        100% { box-shadow: 0 4px 20px rgba(76, 175, 80, 0.3); }
    }
    
    .agent-performance-card {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        border-left: 5px solid #fcb69f;
    }
    
    .enhanced-sidebar {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 1rem 0;
    }
</style>
"""

# --- MAIN APPLICATION ---
def main():
    st.markdown(ENHANCED_CSS, unsafe_allow_html=True)
    
    # Initialize enhanced session state
    SessionStateManager.initialize_enhanced_state()
    
    # Login system (simplified for demo)
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_application()

def show_login_page():
    """Enhanced login page"""
    st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro Enhanced</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 15px; color: white; text-align: center;">
            <h2>🔐 Enhanced CRM Login</h2>
            <p>Access the most advanced laundry CRM system</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("enhanced_login"):
            username = st.text_input("👤 Username")
            password = st.text_input("🔒 Password", type="password")
            remember_me = st.checkbox("Remember me")
            login_button = st.form_submit_button("🚀 Login", type="primary")
            
            if login_button:
                if username in ENHANCED_DEMO_ACCOUNTS and ENHANCED_DEMO_ACCOUNTS[username]["password"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user_info = ENHANCED_DEMO_ACCOUNTS[username]
                    st.session_state.username = username
                    st.success(f"✅ Welcome {ENHANCED_DEMO_ACCOUNTS[username]['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials!")

def show_main_application():
    """Enhanced main application"""
    
    # Header with user info
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro Enhanced</div>', unsafe_allow_html=True)
    
    with col2:
        user_context = SessionStateManager.get_user_context()
        st.markdown(f"""
        <div class="enhanced-sidebar">
            <strong>👤 {user_context['user_info']['name']}</strong><br>
            <small>{user_context['user_info']['role']} | {user_context['user_info']['team']}</small>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        if st.button("🚪 Logout", type="secondary"):
            st.session_state.logged_in = False
            st.rerun()
    
    # Initialize VAPI manager
    if not st.session_state.enhanced_vapi_manager:
        try:
            api_key = st.secrets.get("VAPI_API_KEY", "demo_key")
            st.session_state.enhanced_vapi_manager = EnhancedVAPICallManager(api_key)
        except:
            st.session_state.enhanced_vapi_manager = EnhancedVAPICallManager("demo_key")
    
    # Enhanced tab layout
    tabs = st.tabs([
        "🏠 Enhanced Dashboard",
        "👥 Smart Contacts",
        "📊 Sales Pipeline", 
        "📞 AI Call Center",
        "📈 Advanced Analytics",
        "⚙️ Automation Hub"
    ])
    
    with tabs[0]:
        show_enhanced_dashboard()
    
    with tabs[1]:
        show_smart_contacts()
    
    with tabs[2]:
        show_sales_pipeline()
    
    with tabs[3]:
        show_ai_call_center()
    
    with tabs[4]:
        show_advanced_analytics()
    
    with tabs[5]:
        show_automation_hub()

def show_enhanced_dashboard():
    """Enhanced dashboard with real-time metrics"""
    st.subheader("📊 Enhanced CRM Dashboard")
    
    # Real-time metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f'''
        <div class="enhanced-metric-card">
            <h3>👥 Total Leads</h3>
            <h2>{len(SAMPLE_LEADS)}</h2>
            <p>+12% this month</p>
        </div>
        ''', unsafe_allow_html=True)
    
    with col2:
        pipeline_value = sum(lead['estimated_value'] for lead in SAMPLE_LEADS)
        st.markdown(f'''
        <div class="enhanced-metric-card">
            <h3>💰 Pipeline Value</h3>
            <h2>${pipeline_value:,.0f}</h2>
            <p>+8% this week</p>
        </div>
        ''', unsafe_allow_html=True)
    
    with col3:
        vapi_status = st.session_state.enhanced_vapi_manager.get_enhanced_status()
        st.markdown(f'''
        <div class="enhanced-metric-card">
            <h3>📞 Active Calls</h3>
            <h2>{vapi_status['active_calls']}</h2>
            <p>{vapi_status['call_history_count']} total</p>
        </div>
        ''', unsafe_allow_html=True)
    
    with col4:
        avg_score = sum(lead['score'] for lead in SAMPLE_LEADS) / len(SAMPLE_LEADS)
        st.markdown(f'''
        <div class="enhanced-metric-card">
            <h3>⭐ Avg Lead Score</h3>
            <h2>{avg_score:.0f}</h2>
            <p>Quality metric</p>
        </div>
        ''', unsafe_allow_html=True)
    
    # Pipeline overview
    st.subheader("🔄 Sales Pipeline Overview")
    
    pipeline = st.session_state.crm_pipeline
    metrics = pipeline.get_pipeline_metrics(SAMPLE_LEADS)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pipeline stages chart
        stages = list(metrics['stage_counts'].keys())
        counts = list(metrics['stage_counts'].values())
        
        fig = px.funnel(
            x=counts,
            y=stages,
            title="Sales Pipeline Funnel"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Pipeline value chart
        fig = px.pie(
            values=list(metrics['stage_values'].values()),
            names=list(metrics['stage_values'].keys()),
            title="Pipeline Value Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)

def show_smart_contacts():
    """Enhanced contact management with smart grid"""
    st.subheader("👥 Smart Contact Management")
    
    # Convert sample leads to DataFrame
    leads_df = pd.DataFrame(SAMPLE_LEADS)
    leads_df['Lead Score'] = leads_df['score']
    leads_df['Status'] = leads_df['status']
    leads_df['Name'] = leads_df['name']
    leads_df['Email'] = leads_df['email']
    leads_df['Phone'] = leads_df['phone']
    leads_df['Estimated Value'] = leads_df['estimated_value']
    
    # Smart filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=leads_df['Status'].unique(),
            default=leads_df['Status'].unique()
        )
    
    with col2:
        score_range = st.slider(
            "Lead Score Range",
            min_value=0,
            max_value=100,
            value=(0, 100)
        )
    
    with col3:
        value_range = st.slider(
            "Value Range",
            min_value=0,
            max_value=int(leads_df['Estimated Value'].max()),
            value=(0, int(leads_df['Estimated Value'].max()))
        )
    
    with col4:
        if st.button("🔄 Refresh Data"):
            st.rerun()
    
    # Apply filters
    filtered_df = leads_df[
        (leads_df['Status'].isin(status_filter)) &
        (leads_df['Lead Score'] >= score_range[0]) &
        (leads_df['Lead Score'] <= score_range[1]) &
        (leads_df['Estimated Value'] >= value_range[0]) &
        (leads_df['Estimated Value'] <= value_range[1])
    ]
    
    # Enhanced grid
    grid_options = create_enhanced_customer_grid(filtered_df)
    
    grid_response = AgGrid(
        filtered_df,
        gridOptions=grid_options,
        height=500,
        width='100%',
        theme='alpine',
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=True,
        allow_unsafe_jscode=True
    )
    
    # Bulk actions
    if grid_response['selected_rows']:
        st.subheader("🎯 Bulk Actions")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📞 Bulk Call"):
                st.success(f"Initiating calls for {len(grid_response['selected_rows'])} contacts")
        
        with col2:
            if st.button("📧 Send Email"):
                st.success(f"Sending emails to {len(grid_response['selected_rows'])} contacts")
        
        with col3:
            new_status = st.selectbox("Change Status", [status.value for status in LeadStatus])
            if st.button("🔄 Update Status"):
                st.success(f"Updated status for {len(grid_response['selected_rows'])} contacts")
        
        with col4:
            if st.button("📊 Generate Report"):
                st.success(f"Generating report for {len(grid_response['selected_rows'])} contacts")

def show_sales_pipeline():
    """Enhanced sales pipeline management"""
    st.subheader("📊 Sales Pipeline Management")
    
    pipeline = st.session_state.crm_pipeline
    
    # Pipeline stages
    stages = [status.value for status in LeadStatus]
    
    # Create pipeline board
    cols = st.columns(len(stages))
    
    for i, stage in enumerate(stages):
        with cols[i]:
            stage_leads = [lead for lead in SAMPLE_LEADS if lead['status'] == stage]
            stage_value = sum(lead['estimated_value'] for lead in stage_leads)
            
            st.markdown(f"""
            <div class="pipeline-stage">
                <h4>{stage}</h4>
                <p><strong>{len(stage_leads)}</strong> leads</p>
                <p><strong>${stage_value:,.0f}</strong> value</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Show leads in this stage
            for lead in stage_leads[:3]:  # Show top 3
                with st.expander(f"{lead['name']} (${lead['estimated_value']:,.0f})"):
                    st.write(f"**Score:** {lead['score']}")
                    st.write(f"**Assigned to:** {lead['assigned_to']}")
                    st.write(f"**Notes:** {lead['notes']}")
                    
                    if st.button(f"📞 Call {lead['name']}", key=f"call_{lead['id']}"):
                        st.success(f"Initiating call to {lead['name']}")
    
    # Pipeline analytics
    st.subheader("📈 Pipeline Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Conversion rates
        conversion_data = []
        for stage in stages[:-2]:  # Exclude Closed Won/Lost
            rate = pipeline.conversion_rates.get(stage, 0)
            conversion_data.append({'Stage': stage, 'Conversion Rate': rate * 100})
        
        conv_df = pd.DataFrame(conversion_data)
        fig = px.bar(conv_df, x='Stage', y='Conversion Rate', title='Stage Conversion Rates')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Lead score distribution
        scores = [lead['score'] for lead in SAMPLE_LEADS]
        fig = px.histogram(x=scores, nbins=10, title='Lead Score Distribution')
        st.plotly_chart(fig, use_container_width=True)

def show_ai_call_center():
    """Enhanced AI call center with advanced features"""
    st.subheader("📞 Enhanced AI Call Center")
    
    vapi_manager = st.session_state.enhanced_vapi_manager
    
    # Call center status
    status = vapi_manager.get_enhanced_status()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f'''
        <div class="call-status-enhanced">
            <h3>📊 Call Center Status</h3>
            <p><strong>Active Calls:</strong> {status['active_calls']}</p>
            <p><strong>Total Sessions:</strong> {status['total_sessions']}</p>
            <p><strong>Success Rate:</strong> {(status['analytics']['successful_calls'] / max(status['analytics']['total_calls'], 1) * 100):.1f}%</p>
        </div>
        ''', unsafe_allow_html=True)
    
    with col2:
        st.markdown(f'''
        <div class="agent-performance-card">
            <h3>⚡ Performance Metrics</h3>
            <p><strong>Total Calls:</strong> {status['analytics']['total_calls']}</p>
            <p><strong>Avg Duration:</strong> {status['analytics']['average_duration']:.0f}s</p>
            <p><strong>Success Rate:</strong> {(status['analytics']['successful_calls'] / max(status['analytics']['total_calls'], 1) * 100):.1f}%</p>
        </div>
        ''', unsafe_allow_html=True)
    
    with col3:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
        
        if st.button("📊 View Analytics", use_container_width=True):
            st.info("Analytics dashboard opened")
        
        if st.button("⚙️ Configure Agents", use_container_width=True):
            st.info("Agent configuration panel opened")
    
    # Agent configuration
    st.subheader("🤖 AI Agent Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Create New Agent Session**")
        
        agent_name = st.text_input("Agent Name", placeholder="Customer Support Agent")
        agent_id = st.text_input("Assistant ID", placeholder="Enter VAPI assistant ID")
        agent_type = st.selectbox("Agent Type", [
            "Customer Support",
            "Sales Assistant", 
            "Lead Qualifier",
            "Appointment Scheduler"
        ])
        
        if st.button("🚀 Create Session"):
            if agent_name and agent_id:
                config = {
                    'assistant_id': agent_id,
                    'name': agent_name,
                    'type': agent_type
                }
                session_id = vapi_manager.create_agent_session(agent_id, config)
                st.success(f"✅ Session created: {session_id}")
            else:
                st.error("Please fill in all fields")
    
    with col2:
        st.markdown("**Active Sessions**")
        
        active_sessions = status['active_sessions']
        if active_sessions:
            for session_id, session_info in active_sessions.items():
                with st.expander(f"Session: {session_info['config']['name']}"):
                    st.write(f"**Type:** {session_info['config']['type']}")
                    st.write(f"**Calls Made:** {session_info['call_count']}")
                    st.write(f"**Created:** {session_info['created_at'].strftime('%Y-%m-%d %H:%M')}")
                    
                    if st.button(f"🗑️ End Session", key=f"end_{session_id}"):
                        st.success("Session ended")
        else:
            st.info("No active sessions")
    
    # Call interface
    st.subheader("📱 Make Enhanced Call")
    
    if active_sessions:
        col1, col2 = st.columns(2)
        
        with col1:
            session_options = [(sid, info['config']['name']) for sid, info in active_sessions.items()]
            selected_session = st.selectbox(
                "Select Agent Session",
                options=[s[0] for s in session_options],
                format_func=lambda x: next(s[1] for s in session_options if s[0] == x)
            )
            
            phone_number = st.text_input("Phone Number", placeholder="+1234567890")
            
            # Lead selection
            lead_options = [(lead['id'], lead['name']) for lead in SAMPLE_LEADS]
            selected_lead_id = st.selectbox(
                "Select Lead",
                options=[l[0] for l in lead_options],
                format_func=lambda x: next(l[1] for l in lead_options if l[0] == x)
            )
        
        with col2:
            # Call customization
            custom_greeting = st.text_area("Custom Greeting", placeholder="Hi {customer_name}, this is...")
            call_objective = st.selectbox("Call Objective", [
                "Lead Qualification",
                "Appointment Booking", 
                "Follow-up",
                "Customer Support"
            ])
            priority = st.selectbox("Priority", ["Low", "Medium", "High", "Urgent"])
        
        # Start call button
        if st.button("📞 Start Enhanced Call", type="primary", use_container_width=True):
            if phone_number and selected_session and selected_lead_id:
                selected_lead = next(lead for lead in SAMPLE_LEADS if lead['id'] == selected_lead_id)
                
                overrides = {
                    "greeting": custom_greeting,
                    "objective": call_objective,
                    "priority": priority
                }
                
                success, message = vapi_manager.start_enhanced_call(
                    selected_session,
                    phone_number,
                    selected_lead,
                    overrides
                )
                
                if success:
                    st.success(f"📞 {message}")
                    st.balloons()
                else:
                    st.error(f"❌ {message}")
            else:
                st.error("Please fill in all required fields")
    else:
        st.warning("⚠️ Please create an agent session first")
    
    # Recent calls
    st.subheader("📋 Recent Calls")
    
    if status['recent_calls']:
        for call in status['recent_calls'][-5:]:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.write(f"**{call['start_time'][:19]}**")
            
            with col2:
                st.write(f"Status: {call['status']}")
            
            with col3:
                st.write(f"Duration: {call['duration']}s")
            
            with col4:
                if st.button(f"📊 Details", key=f"details_{call['id']}"):
                    st.info(f"Call details for {call['id']}")
    else:
        st.info("No recent calls")

def show_advanced_analytics():
    """Advanced analytics dashboard"""
    st.subheader("📈 Advanced Analytics Dashboard")
    
    # Time-based analytics
    col1, col2 = st.columns(2)
    
    with col1:
        # Lead generation over time
        dates = pd.date_range(start='2024-01-01', end='2024-01-31', freq='D')
        lead_counts = np.random.poisson(3, len(dates))
        
        fig = px.line(
            x=dates,
            y=lead_counts,
            title='Lead Generation Trend',
            labels={'x': 'Date', 'y': 'New Leads'}
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Revenue forecast
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        actual = [15000, 18000, 22000, 19000, 25000, 28000]
        forecast = [30000, 32000, 35000, 38000, 40000, 42000]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=months, y=actual, name='Actual', mode='lines+markers'))
        fig.add_trace(go.Scatter(x=months, y=forecast, name='Forecast', mode='lines+markers'))
        fig.update_layout(title='Revenue Forecast')
        st.plotly_chart(fig, use_container_width=True)
    
    # Performance metrics
    st.subheader("🎯 Performance Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    metrics = {
        'Conversion Rate': '24.5%',
        'Avg Deal Size': '$3,200',
        'Sales Cycle': '18 days',
        'Customer LTV': '$12,500'
    }
    
    for i, (metric, value) in enumerate(metrics.items()):
        with [col1, col2, col3, col4][i]:
            st.metric(metric, value, delta=f"+{np.random.randint(1, 15)}%")
    
    # Detailed analytics
    tab1, tab2, tab3 = st.tabs(["Lead Analytics", "Call Analytics", "Revenue Analytics"])
    
    with tab1:
        # Lead source analysis
        sources = ['Website', 'Referral', 'Cold Call', 'Social Media', 'Email']
        counts = [25, 18, 12, 8, 5]
        
        fig = px.pie(values=counts, names=sources, title='Lead Sources')
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Call performance
        vapi_status = st.session_state.enhanced_vapi_manager.get_enhanced_status()
        
        st.metric("Total Calls", vapi_status['analytics']['total_calls'])
        st.metric("Success Rate", f"{(vapi_status['analytics']['successful_calls'] / max(vapi_status['analytics']['total_calls'], 1) * 100):.1f}%")
        st.metric("Average Duration", f"{vapi_status['analytics']['average_duration']:.0f} seconds")
    
    with tab3:
        # Revenue breakdown
        categories = ['New Business', 'Existing Customers', 'Upsells', 'Renewals']
        values = [45000, 32000, 18000, 25000]
        
        fig = px.bar(x=categories, y=values, title='Revenue by Category')
        st.plotly_chart(fig, use_container_width=True)

def show_automation_hub():
    """Automation and workflow management"""
    st.subheader("⚙️ Automation Hub")
    
    # Automation rules
    st.markdown("### 🤖 Active Automation Rules")
    
    automation_rules = [
        {
            'name': 'New Lead Auto-Assignment',
            'trigger': 'New lead created',
            'action': 'Assign to available agent',
            'status': 'Active'
        },
        {
            'name': 'Follow-up Reminder',
            'trigger': 'No contact for 7 days',
            'action': 'Send reminder email',
            'status': 'Active'
        },
        {
            'name': 'High-Value Lead Alert',
            'trigger': 'Lead value > $5000',
            'action': 'Notify manager',
            'status': 'Active'
        }
    ]
    
    for rule in automation_rules:
        with st.expander(f"🔧 {rule['name']} - {rule['status']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Trigger:** {rule['trigger']}")
                st.write(f"**Action:** {rule['action']}")
            
            with col2:
                if st.button(f"✏️ Edit", key=f"edit_{rule['name']}"):
                    st.info("Rule editor opened")
                
                if st.button(f"⏸️ Pause", key=f"pause_{rule['name']}"):
                    st.success("Rule paused")
    
    # Workflow builder
    st.markdown("### 🔄 Workflow Builder")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Create New Workflow**")
        
        workflow_name = st.text_input("Workflow Name")
        trigger_type = st.selectbox("Trigger Type", [
            "Lead Created",
            "Status Changed", 
            "Time-based",
            "Score Threshold"
        ])
        
        action_type = st.selectbox("Action Type", [
            "Send Email",
            "Make Call",
            "Update Field",
            "Create Task"
        ])
        
        if st.button("💾 Save Workflow"):
            st.success(f"Workflow '{workflow_name}' created successfully!")
    
    with col2:
        st.markdown("**Workflow Templates**")
        
        templates = [
            "Lead Nurturing Sequence",
            "Customer Onboarding",
            "Win-Back Campaign",
            "Referral Program"
        ]
        
        for template in templates:
            if st.button(f"📋 Use {template}", key=f"template_{template}"):
                st.success(f"Applied template: {template}")
    
    # Integration status
    st.markdown("### 🔗 Integration Status")
    
    integrations = [
        {'name': 'Google Sheets', 'status': '✅ Connected', 'last_sync': '2 minutes ago'},
        {'name': 'VAPI AI', 'status': '✅ Connected', 'last_sync': '1 minute ago'},
        {'name': 'Email Service', 'status': '⚠️ Warning', 'last_sync': '1 hour ago'},
        {'name': 'Calendar', 'status': '❌ Disconnected', 'last_sync': 'Never'}
    ]
    
    for integration in integrations:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.write(f"**{integration['name']}**")
        
        with col2:
            st.write(integration['status'])
        
        with col3:
            st.write(f"Last sync: {integration['last_sync']}")
        
        with col4:
            if st.button("🔧 Configure", key=f"config_{integration['name']}"):
                st.info(f"Configuring {integration['name']}")

if __name__ == "__main__":
    main()
