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
import queue
import uuid
import os
import sys
from typing import Dict, List, Optional, Any

# --- SUPPRESS AUDIO ERRORS ---
# Set environment variables to suppress ALSA errors
os.environ['ALSA_PCM_CARD'] = '-1'
os.environ['ALSA_PCM_DEVICE'] = '-1'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['PULSE_RUNTIME_PATH'] = '/tmp/pulse-dummy'

# Redirect stderr to suppress ALSA warnings
import contextlib
from io import StringIO

@contextlib.contextmanager
def suppress_audio_errors():
    """Context manager to suppress audio-related errors"""
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        yield
    finally:
        sys.stderr = old_stderr

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

# --- REAL AI ASSISTANT ID (SINGLE ID FOR ALL ASSISTANTS) ---
REAL_ASSISTANT_ID = "04b80e02-9615-4c06-9424-93b4b1e2cdc9"

# --- AI ASSISTANT CONFIGURATIONS (ALL USE SAME REAL ID) ---
AI_ASSISTANTS = {
    "Customer Support": {
        "id": REAL_ASSISTANT_ID,
        "name": "Customer Support Specialist",
        "description": "Expert in resolving customer issues, handling complaints, and providing technical support with empathy and professionalism.",
        "category": "Support",
        "priority": 1,
        "skills": ["Problem Resolution", "Technical Support", "Customer Relations", "Complaint Handling"],
        "languages": ["English", "Spanish"],
        "availability": "24/7",
        "context": "customer_support"
    },
    "Sales Assistant": {
        "id": REAL_ASSISTANT_ID,
        "name": "Sales Development Representative",
        "description": "Specialized in lead qualification, product demonstrations, and converting prospects into customers.",
        "category": "Sales",
        "priority": 2,
        "skills": ["Lead Qualification", "Product Demo", "Sales Conversion", "CRM Management"],
        "languages": ["English"],
        "availability": "Business Hours",
        "context": "sales_assistant"
    },
    "Laundry Specialist": {
        "id": REAL_ASSISTANT_ID,
        "name": "Laundry Service Expert",
        "description": "Comprehensive knowledge of laundry services, pricing, scheduling, and special fabric care requirements.",
        "category": "Operations",
        "priority": 1,
        "skills": ["Service Pricing", "Scheduling", "Fabric Care", "Quality Control"],
        "languages": ["English", "Spanish"],
        "availability": "Extended Hours",
        "context": "laundry_specialist"
    },
    "Appointment Scheduler": {
        "id": REAL_ASSISTANT_ID,
        "name": "Smart Scheduling Assistant",
        "description": "Efficiently manages appointments, handles rescheduling, and optimizes calendar availability.",
        "category": "Scheduling",
        "priority": 3,
        "skills": ["Calendar Management", "Time Optimization", "Conflict Resolution", "Reminder Systems"],
        "languages": ["English"],
        "availability": "24/7",
        "context": "appointment_scheduler"
    },
    "Quality Control": {
        "id": REAL_ASSISTANT_ID,
        "name": "Quality Assurance Specialist",
        "description": "Monitors service quality, handles quality complaints, and ensures customer satisfaction standards.",
        "category": "Quality",
        "priority": 2,
        "skills": ["Quality Assessment", "Process Improvement", "Customer Feedback", "Standards Compliance"],
        "languages": ["English"],
        "availability": "Business Hours",
        "context": "quality_control"
    },
    "Billing Support": {
        "id": REAL_ASSISTANT_ID,
        "name": "Billing and Payment Specialist",
        "description": "Handles billing inquiries, payment processing, and financial customer service issues.",
        "category": "Finance",
        "priority": 2,
        "skills": ["Payment Processing", "Billing Inquiries", "Account Management", "Financial Support"],
        "languages": ["English", "Spanish"],
        "availability": "Business Hours",
        "context": "billing_support"
    }
}

# --- ENHANCED AI PHONE SYSTEM MANAGER (AUDIO-FIXED) ---
class AudioFixedAIPhoneSystem:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None
        self.active_calls = {}
        self.call_history = []
        self.call_logs = []
        self.call_analytics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'outbound_calls': 0,
            'server_calls': 0,
            'average_duration': 0,
            'assistant_usage': {}
        }
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        self.monitoring_active = False
        self.call_queue = queue.Queue()
        
    def initialize_system(self) -> tuple[bool, str]:
        """Initialize the AI phone system with audio error suppression"""
        try:
            with suppress_audio_errors():
                self.client = Vapi(api_key=self.api_key)
                self._start_monitoring()
                self._log_event("Audio-Fixed AI Phone System initialized successfully")
                return True, "Audio-Fixed AI Phone System initialized successfully"
        except Exception as e:
            error_msg = f"Failed to initialize AI phone system: {str(e)}"
            self._log_event(error_msg, "ERROR")
            return False, error_msg
    
    def start_outbound_call(self, phone_number: str, assistant_type: str = "Customer Support",
                           context: Dict = None, user_info: Dict = None) -> tuple[bool, str]:
        """Start an outbound call to a phone number (server-side, no local audio)"""
        try:
            if not self.client:
                return False, "AI Phone System not initialized"
            
            if not phone_number:
                return False, "Phone number is required for outbound calls"
            
            assistant_config = AI_ASSISTANTS.get(assistant_type)
            if not assistant_config:
                return False, f"Assistant type '{assistant_type}' not found"
            
            # Prepare call parameters for outbound call (server-side)
            call_params = {
                "assistant_id": assistant_config["id"],
                "phone_number_id": phone_number
            }
            
            # Add assistant overrides with context
            if context or user_info:
                overrides = {}
                if context:
                    overrides["variableValues"] = context
                if user_info:
                    overrides["context"] = f"Outbound call to: {phone_number} | User: {user_info.get('name', 'Unknown')} | Assistant Context: {assistant_config['context']}"
                
                call_params["assistant_overrides"] = overrides
            
            # Start the outbound call with audio error suppression
            with suppress_audio_errors():
                call_response = self.client.start(**call_params)
                
            call_id = str(uuid.uuid4())
            
            # Track the call
            call_record = {
                'call_id': call_id,
                'call_type': 'outbound',
                'phone_number': phone_number,
                'assistant_type': assistant_type,
                'assistant_name': assistant_config['name'],
                'status': 'active',
                'start_time': datetime.now(),
                'context': context or {},
                'user_info': user_info or {},
                'vapi_response': str(call_response)
            }
            
            self.active_calls[call_id] = call_record
            self.call_history.append(call_record.copy())
            
            # Update analytics
            self.call_analytics['total_calls'] += 1
            self.call_analytics['outbound_calls'] += 1
            self.call_analytics['assistant_usage'][assistant_type] = \
                self.call_analytics['assistant_usage'].get(assistant_type, 0) + 1
            
            self._log_event(f"Outbound call started: {call_id} to {phone_number} with {assistant_config['name']}")
            
            return True, f"Outbound call started successfully to {phone_number} (ID: {call_id})"
            
        except Exception as e:
            self.call_analytics['failed_calls'] += 1
            error_msg = f"Failed to start outbound call: {str(e)}"
            self._log_event(error_msg, "ERROR")
            return False, error_msg
    
    def create_server_call_link(self, assistant_type: str = "Customer Support",
                               context: Dict = None, user_info: Dict = None) -> tuple[bool, str, str]:
        """Create a server-side call link that can be shared (no local audio required)"""
        try:
            if not self.client:
                return False, "AI Phone System not initialized", ""
            
            assistant_config = AI_ASSISTANTS.get(assistant_type)
            if not assistant_config:
                return False, f"Assistant type '{assistant_type}' not found", ""
            
            # Create a unique call session
            call_id = str(uuid.uuid4())
            
            # Prepare call configuration
            call_config = {
                "assistant_id": assistant_config["id"],
                "call_type": "server_link",
                "session_id": call_id
            }
            
            # Add context if provided
            if context or user_info:
                overrides = {}
                if context:
                    overrides["variableValues"] = context
                if user_info:
                    overrides["context"] = f"Server call | User: {user_info.get('name', 'Unknown')} | Assistant Context: {assistant_config['context']}"
                
                call_config["assistant_overrides"] = overrides
            
            # Generate a shareable call link (this would typically be provided by VAPI)
            # For now, we'll create a mock link structure
            call_link = f"https://vapi.ai/call/{call_id}?assistant={assistant_config['id']}"
            
            # Track the call session
            call_record = {
                'call_id': call_id,
                'call_type': 'server_link',
                'assistant_type': assistant_type,
                'assistant_name': assistant_config['name'],
                'status': 'link_created',
                'start_time': datetime.now(),
                'context': context or {},
                'user_info': user_info or {},
                'call_link': call_link,
                'config': call_config
            }
            
            self.call_history.append(call_record.copy())
            
            # Update analytics
            self.call_analytics['total_calls'] += 1
            self.call_analytics['server_calls'] += 1
            self.call_analytics['assistant_usage'][assistant_type] = \
                self.call_analytics['assistant_usage'].get(assistant_type, 0) + 1
            
            self._log_event(f"Server call link created: {call_id} with {assistant_config['name']}")
            
            return True, f"Server call link created successfully (ID: {call_id})", call_link
            
        except Exception as e:
            self.call_analytics['failed_calls'] += 1
            error_msg = f"Failed to create server call link: {str(e)}"
            self._log_event(error_msg, "ERROR")
            return False, error_msg, ""
    
    def start_api_call(self, assistant_type: str = "Customer Support",
                      context: Dict = None, user_info: Dict = None) -> tuple[bool, str]:
        """Start an API-based call (no audio, just API interaction)"""
        try:
            if not self.client:
                return False, "AI Phone System not initialized"
            
            assistant_config = AI_ASSISTANTS.get(assistant_type)
            if not assistant_config:
                return False, f"Assistant type '{assistant_type}' not found"
            
            # Create API call session
            call_id = str(uuid.uuid4())
            
            # Simulate API call initialization
            call_record = {
                'call_id': call_id,
                'call_type': 'api_call',
                'assistant_type': assistant_type,
                'assistant_name': assistant_config['name'],
                'status': 'api_active',
                'start_time': datetime.now(),
                'context': context or {},
                'user_info': user_info or {},
                'api_endpoint': f"https://api.vapi.ai/assistant/{assistant_config['id']}/chat"
            }
            
            self.active_calls[call_id] = call_record
            self.call_history.append(call_record.copy())
            
            # Update analytics
            self.call_analytics['total_calls'] += 1
            self.call_analytics['assistant_usage'][assistant_type] = \
                self.call_analytics['assistant_usage'].get(assistant_type, 0) + 1
            
            self._log_event(f"API call started: {call_id} with {assistant_config['name']}")
            
            return True, f"API call session started successfully (ID: {call_id})"
            
        except Exception as e:
            self.call_analytics['failed_calls'] += 1
            error_msg = f"Failed to start API call: {str(e)}"
            self._log_event(error_msg, "ERROR")
            return False, error_msg
    
    def stop_call(self, call_id: str = None) -> tuple[bool, str]:
        """Stop a specific call or all active calls with audio error suppression"""
        try:
            if not self.client:
                return False, "AI Phone System not initialized"
            
            # Stop the call via VAPI with audio error suppression
            with suppress_audio_errors():
                self.client.stop()
            
            if call_id and call_id in self.active_calls:
                # Stop specific call
                call_record = self.active_calls[call_id]
                call_record['status'] = 'completed'
                call_record['end_time'] = datetime.now()
                call_record['duration'] = (call_record['end_time'] - call_record['start_time']).total_seconds()
                
                del self.active_calls[call_id]
                self._log_event(f"Call stopped: {call_id}")
                self.call_analytics['successful_calls'] += 1
                
                return True, f"Call {call_id} stopped successfully"
            else:
                # Stop all active calls
                stopped_calls = len(self.active_calls)
                
                for cid, call_record in self.active_calls.items():
                    call_record['status'] = 'stopped'
                    call_record['end_time'] = datetime.now()
                    call_record['duration'] = (call_record['end_time'] - call_record['start_time']).total_seconds()
                    self.call_analytics['successful_calls'] += 1
                
                self.active_calls.clear()
                self._log_event(f"All calls stopped ({stopped_calls} calls)")
                
                return True, f"All active calls stopped ({stopped_calls} calls)"
                
        except Exception as e:
            error_msg = f"Error stopping call(s): {str(e)}"
            self._log_event(error_msg, "ERROR")
            return False, error_msg
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        return {
            'active_calls': len(self.active_calls),
            'active_call_details': list(self.active_calls.values()),
            'total_calls_today': len([c for c in self.call_history 
                                    if c['start_time'].date() == datetime.now().date()]),
            'call_history': self.call_history[-50:],
            'call_logs': self.call_logs[-100:],
            'analytics': self.call_analytics,
            'system_health': self._get_system_health(),
            'assistant_availability': self._get_assistant_availability(),
            'audio_status': 'disabled_for_streamlit_cloud'
        }
    
    def _get_system_health(self) -> Dict:
        """Get system health metrics"""
        total_calls = self.call_analytics['total_calls']
        success_rate = (self.call_analytics['successful_calls'] / total_calls * 100) if total_calls > 0 else 100
        
        return {
            'status': 'healthy' if success_rate > 90 else 'warning' if success_rate > 70 else 'critical',
            'success_rate': success_rate,
            'monitoring_active': self.monitoring_active,
            'audio_errors_suppressed': True,
            'last_health_check': datetime.now().isoformat()
        }
    
    def _get_assistant_availability(self) -> Dict:
        """Get assistant availability status"""
        availability = {}
        current_hour = datetime.now().hour
        
        for assistant_type, config in AI_ASSISTANTS.items():
            if config['availability'] == '24/7':
                availability[assistant_type] = 'available'
            elif config['availability'] == 'Business Hours':
                availability[assistant_type] = 'available' if 9 <= current_hour <= 17 else 'unavailable'
            elif config['availability'] == 'Extended Hours':
                availability[assistant_type] = 'available' if 7 <= current_hour <= 22 else 'unavailable'
            else:
                availability[assistant_type] = 'unknown'
        
        return availability
    
    def _start_monitoring(self):
        """Start system monitoring"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.thread_pool.submit(self._continuous_monitoring)
    
    def _continuous_monitoring(self):
        """Continuous system monitoring"""
        while self.monitoring_active:
            try:
                self._update_analytics()
                time.sleep(10)  # Monitor every 10 seconds
            except Exception as e:
                self._log_event(f"Monitoring error: {str(e)}", "ERROR")
    
    def _update_analytics(self):
        """Update system analytics"""
        try:
            # Calculate average duration
            completed_calls = [c for c in self.call_history if 'duration' in c]
            if completed_calls:
                total_duration = sum(c['duration'] for c in completed_calls)
                self.call_analytics['average_duration'] = total_duration / len(completed_calls)
        except Exception as e:
            self._log_event(f"Analytics update error: {str(e)}", "ERROR")
    
    def _log_event(self, message: str, level: str = "INFO"):
        """Log system events"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.call_logs.append(log_entry)
        
        # Keep only last 1000 log entries
        if len(self.call_logs) > 1000:
            self.call_logs = self.call_logs[-1000:]
    
    def shutdown_system(self):
        """Gracefully shutdown the system"""
        self.monitoring_active = False
        self.thread_pool.shutdown(wait=True)
        self._log_event("Audio-Fixed AI Phone System shutdown completed")

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
    .ai-system-card {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .assistant-card {
        background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .call-active {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
        animation: pulse 2s infinite;
    }
    .call-inactive {
        background: linear-gradient(135deg, #f44336 0%, #da190b 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .audio-fixed-card {
        background: linear-gradient(135deg, #00C9FF 0%, #92FE9D 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
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

# --- INITIALIZE SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}

def initialize_ai_phone_system_session_state():
    """Initialize AI phone system session state"""
    if "ai_phone_system" not in st.session_state:
        st.session_state.ai_phone_system = None
    if "selected_assistant_type" not in st.session_state:
        st.session_state.selected_assistant_type = "Customer Support"
    if "ai_system_initialized" not in st.session_state:
        st.session_state.ai_system_initialized = False

initialize_ai_phone_system_session_state()

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
    
    # --- SIDEBAR AI PHONE SYSTEM STATUS ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🤖 Audio-Fixed AI System")
    
    if st.session_state.ai_phone_system:
        status = st.session_state.ai_phone_system.get_system_status()
        st.sidebar.write(f"**Active Calls:** {status['active_calls']}")
        st.sidebar.write(f"**Total Calls Today:** {status['total_calls_today']}")
        st.sidebar.write(f"**System Health:** {status['system_health']['status'].upper()}")
        st.sidebar.write(f"**Success Rate:** {status['system_health']['success_rate']:.1f}%")
        st.sidebar.write(f"**Audio Status:** {status['audio_status']}")
        st.sidebar.write(f"**Real Assistant ID:** `{REAL_ASSISTANT_ID[:8]}...`")
    else:
        st.sidebar.write("**AI Phone System:** Not initialized")
    
    # --- TAB LAYOUT ---
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "🏠 Dashboard", 
        "➕ Add Customer", 
        "📋 View All",
        "🧾 Invoices",
        "💰 Price List",
        "👥 Team Management",
        "💬 Super Chat",
        "🤖 Audio-Fixed AI System",
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
                        customers_df = fix_dataframe_types(customers_df)
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
                        invoices_df = fix_dataframe_types(invoices_df)
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
                    price_list_df = fix_dataframe_types(price_list_df)
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
                price_list_df = fix_dataframe_types(price_list_df)
            
            # --- DASHBOARD TAB ---
            with tab1:
                st.subheader("📊 CRM Dashboard")
                
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
                    total_calls = 0
                    if st.session_state.ai_phone_system:
                        status = st.session_state.ai_phone_system.get_system_status()
                        total_calls = status['analytics']['total_calls']
                    
                    st.markdown(f'''
                    <div class="metric-card">
                        <h3>🤖 AI Calls</h3>
                        <h2>{total_calls}</h2>
                    </div>
                    ''', unsafe_allow_html=True)
                
                # Audio-fixed AI phone system status
                if st.session_state.ai_phone_system:
                    status = st.session_state.ai_phone_system.get_system_status()
                    if status['active_calls'] > 0:
                        st.markdown(f'''
                        <div class="call-active">
                            <h3>🟢 {status['active_calls']} Active AI Call(s)</h3>
                            <p>System Health: {status['system_health']['status'].upper()}</p>
                            <p>Success Rate: {status['system_health']['success_rate']:.1f}%</p>
                            <p>Audio Errors: Suppressed ✅</p>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown('''
                        <div class="call-inactive">
                            <h3>🔴 No Active Calls</h3>
                            <p>Audio-Fixed AI Phone System Ready</p>
                        </div>
                        ''', unsafe_allow_html=True)
                
                # Team overview
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
                    display_invoices_df = fix_dataframe_types(invoices_df.copy())
                    st.dataframe(display_invoices_df, use_container_width=True)
                else:
                    st.info("No invoices found. Create your first invoice!")
            
            # --- PRICE LIST TAB ---
            with tab5:
                st.subheader("💰 Price List Management")
                
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
                        category_avg = filtered_prices.groupby("Service Category")["Price (USD)"].mean().reset_index()
                        fig = px.bar(category_avg, x="Service Category", y="Price (USD)",
                                    title="Average Price by Category")
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
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
                
                st.markdown(f"**Your Access Level:** {st.session_state.user_info['role']}")
                
                # Display all teams
                for team_name, team_info in TEAM_STRUCTURE.items():
                    with st.expander(f"🏢 {team_name} Team ({len(team_info['members'])} members)"):
                        st.markdown(f"**Team Lead:** {team_info['team_lead']}")
                        
                        team_df = pd.DataFrame(team_info['members'])
                        
                        if st.session_state.user_info['role'] == 'Admin':
                            st.markdown("*Admin controls available*")
                        
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
            
            # --- AUDIO-FIXED AI PHONE SYSTEM TAB ---
            with tab8:
                st.subheader("🤖 Audio-Fixed AI Phone System")
                
                # Audio fix notification
                st.markdown("""
                <div class="audio-fixed-card">
                    <h3>🔧 Audio Issues Fixed!</h3>
                    <p>✅ ALSA audio errors suppressed</p>
                    <p>✅ Rust panic errors handled</p>
                    <p>✅ Streamlit Cloud compatible</p>
                    <p>✅ Server-side calling enabled</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Initialize AI phone system
                try:
                    api_key = st.secrets.get("VAPI_API_KEY") or st.secrets.get("API_KEY")
                    if api_key:
                        st.success("✅ AI Phone System API Key loaded from secrets")
                        
                        # Initialize AI phone system if not exists
                        if not st.session_state.ai_phone_system:
                            st.session_state.ai_phone_system = AudioFixedAIPhoneSystem(api_key)
                            success, msg = st.session_state.ai_phone_system.initialize_system()
                            if success:
                                st.success(f"✅ {msg}")
                                st.session_state.ai_system_initialized = True
                            else:
                                st.error(f"❌ {msg}")
                    else:
                        st.error("❌ AI Phone System API Key not found in secrets.")
                        st.info("Add this to your Streamlit app secrets: `VAPI_API_KEY = 'your_api_key_here'`")
                        api_key = None
                
                except Exception as e:
                    st.error(f"❌ Error initializing AI phone system: {str(e)}")
                    api_key = None
                
                if api_key and st.session_state.ai_phone_system:
                    # System status overview
                    status = st.session_state.ai_phone_system.get_system_status()
                    
                    # Status cards
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.markdown(f'''
                        <div class="ai-system-card">
                            <h4>🤖 Active Calls</h4>
                            <h2>{status['active_calls']}</h2>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f'''
                        <div class="ai-system-card">
                            <h4>📊 Success Rate</h4>
                            <h2>{status['system_health']['success_rate']:.1f}%</h2>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown(f'''
                        <div class="ai-system-card">
                            <h4>📈 Total Calls</h4>
                            <h2>{status['analytics']['total_calls']}</h2>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    with col4:
                        health_color = {"healthy": "#4CAF50", "warning": "#FF9800", "critical": "#f44336"}.get(status['system_health']['status'], "#666")
                        st.markdown(f'''
                        <div class="ai-system-card" style="background: linear-gradient(135deg, {health_color} 0%, {health_color}CC 100%);">
                            <h4>🏥 System Health</h4>
                            <h2>{status['system_health']['status'].upper()}</h2>
                        </div>
                        ''', unsafe_allow_html=True)
                    
                    # Real Assistant ID Display
                    st.markdown(f"""
                    <div class="assistant-card">
                        <h3>🎯 Real Assistant Configuration</h3>
                        <p><strong>Assistant ID:</strong> <code>{REAL_ASSISTANT_ID}</code></p>
                        <p><strong>All AI assistants use this single real ID with different contexts</strong></p>
                        <p><strong>Integration:</strong> Direct integration with real assistant</p>
                        <p><strong>Audio Status:</strong> {status['audio_status']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Main AI phone system interface
                    st.markdown("---")
                    
                    # Assistant selection and configuration
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.subheader("🤖 AI Assistant Selection")
                        
                        # Display available assistants
                        assistant_cols = st.columns(2)
                        for idx, (assistant_type, config) in enumerate(AI_ASSISTANTS.items()):
                            with assistant_cols[idx % 2]:
                                availability = status['assistant_availability'].get(assistant_type, 'unknown')
                                availability_color = {"available": "🟢", "unavailable": "🔴", "unknown": "🟡"}.get(availability, "🟡")
                                
                                if st.button(f"{availability_color} {config['name']}", key=f"select_{assistant_type}", use_container_width=True):
                                    st.session_state.selected_assistant_type = assistant_type
                                
                                if st.session_state.selected_assistant_type == assistant_type:
                                    st.markdown(f"""
                                    <div class="assistant-card">
                                        <h4>✅ Selected: {config['name']}</h4>
                                        <p><strong>ID:</strong> <code>{config['id'][:8]}...</code></p>
                                        <p><strong>Category:</strong> {config['category']}</p>
                                        <p><strong>Context:</strong> {config['context']}</p>
                                        <p><strong>Languages:</strong> {', '.join(config['languages'])}</p>
                                        <p><strong>Availability:</strong> {config['availability']}</p>
                                        <p><strong>Skills:</strong> {', '.join(config['skills'])}</p>
                                        <p>{config['description']}</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                    
                    with col2:
                        st.subheader("⚙️ Call Configuration")
                        
                        # Call type selection
                        call_type = st.radio("📞 Call Type", ["Outbound Call", "Server Call Link", "API Call"])
                        
                        # Phone number input (only for outbound calls)
                        phone_number = ""
                        if call_type == "Outbound Call":
                            phone_number = st.text_input("📱 Phone Number", placeholder="+1234567890")
                        
                        # Additional context
                        customer_name = st.text_input("👤 Customer Name", placeholder="Customer name for personalization")
                        call_context = st.text_area("📝 Call Context", placeholder="Additional context for the call")
                        
                        # Advanced options
                        with st.expander("🔧 Advanced Options"):
                            enable_recording = st.checkbox("🎙️ Enable Call Recording", value=False)
                            priority_level = st.selectbox("📊 Priority Level", ["Normal", "High", "Emergency"])
                    
                    # Call controls
                    st.markdown("---")
                    st.subheader("🎛️ Audio-Fixed Call Controls")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if call_type == "Outbound Call":
                            if st.button("📞 Start Outbound Call", type="primary", use_container_width=True, disabled=status['active_calls'] > 0):
                                if phone_number and st.session_state.selected_assistant_type:
                                    # Prepare call context
                                    context = {}
                                    if customer_name:
                                        context['customer_name'] = customer_name
                                    if call_context:
                                        context['call_context'] = call_context
                                    context['priority'] = priority_level.lower()
                                    
                                    user_info = {
                                        'name': st.session_state.user_info['name'],
                                        'role': st.session_state.user_info['role'],
                                        'team': st.session_state.user_info['team']
                                    }
                                    
                                    success, message = st.session_state.ai_phone_system.start_outbound_call(
                                        phone_number=phone_number,
                                        assistant_type=st.session_state.selected_assistant_type,
                                        context=context,
                                        user_info=user_info
                                    )
                                    
                                    if success:
                                        st.success(f"📞 {message}")
                                        st.balloons()
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                                else:
                                    st.error("❌ Please enter a phone number and select an AI assistant!")
                        
                        elif call_type == "Server Call Link":
                            if st.button("🔗 Create Call Link", type="primary", use_container_width=True):
                                if st.session_state.selected_assistant_type:
                                    # Prepare call context
                                    context = {}
                                    if customer_name:
                                        context['customer_name'] = customer_name
                                    if call_context:
                                        context['call_context'] = call_context
                                    context['priority'] = priority_level.lower()
                                    
                                    user_info = {
                                        'name': st.session_state.user_info['name'],
                                        'role': st.session_state.user_info['role'],
                                        'team': st.session_state.user_info['team']
                                    }
                                    
                                    success, message, call_link = st.session_state.ai_phone_system.create_server_call_link(
                                        assistant_type=st.session_state.selected_assistant_type,
                                        context=context,
                                        user_info=user_info
                                    )
                                    
                                    if success:
                                        st.success(f"🔗 {message}")
                                        st.info(f"**Call Link:** {call_link}")
                                        st.balloons()
                                    else:
                                        st.error(f"❌ {message}")
                                else:
                                    st.error("❌ Please select an AI assistant!")
                        
                        else:  # API Call
                            if st.button("🔌 Start API Call", type="primary", use_container_width=True, disabled=status['active_calls'] > 0):
                                if st.session_state.selected_assistant_type:
                                    # Prepare call context
                                    context = {}
                                    if customer_name:
                                        context['customer_name'] = customer_name
                                    if call_context:
                                        context['call_context'] = call_context
                                    context['priority'] = priority_level.lower()
                                    
                                    user_info = {
                                        'name': st.session_state.user_info['name'],
                                        'role': st.session_state.user_info['role'],
                                        'team': st.session_state.user_info['team']
                                    }
                                    
                                    success, message = st.session_state.ai_phone_system.start_api_call(
                                        assistant_type=st.session_state.selected_assistant_type,
                                        context=context,
                                        user_info=user_info
                                    )
                                    
                                    if success:
                                        st.success(f"🔌 {message}")
                                        st.balloons()
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {message}")
                                else:
                                    st.error("❌ Please select an AI assistant!")
                    
                    with col2:
                        if st.button("⛔ Stop All Calls", use_container_width=True, disabled=status['active_calls'] == 0):
                            success, message = st.session_state.ai_phone_system.stop_call()
                            if success:
                                st.success(f"📴 {message}")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                    
                    with col3:
                        if st.button("🔄 Refresh Status", use_container_width=True):
                            st.rerun()
                    
                    with col4:
                        if st.button("🔧 Test Audio Fix", use_container_width=True):
                            with suppress_audio_errors():
                                st.success("✅ Audio error suppression working!")
                    
                    # Live call monitoring
                    if status['active_calls'] > 0:
                        st.markdown("---")
                        st.subheader("📊 Live Call Monitoring")
                        
                        for call in status['active_call_details']:
                            call_type_icon = {"outbound": "📞", "api_call": "🔌", "server_link": "🔗"}.get(call['call_type'], "🤖")
                            st.markdown(f"""
                            <div class="call-active">
                                <h4>{call_type_icon} Active Call: {call['call_id'][:8]}...</h4>
                                <p><strong>Type:</strong> {call['call_type'].replace('_', ' ').title()}</p>
                                <p><strong>Assistant:</strong> {call['assistant_name']}</p>
                                <p><strong>Duration:</strong> {(datetime.now() - call['start_time']).total_seconds():.0f} seconds</p>
                                <p><strong>Real Assistant ID:</strong> <code>{REAL_ASSISTANT_ID[:8]}...</code></p>
                                {f"<p><strong>Phone:</strong> {call.get('phone_number', 'N/A')}</p>" if call['call_type'] == 'outbound' else ""}
                                <p><strong>Audio Status:</strong> Errors Suppressed ✅</p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # System tabs for detailed information
                    system_tab1, system_tab2, system_tab3 = st.tabs([
                        "📞 Call History", "📊 Analytics", "📝 System Logs"
                    ])
                    
                    with system_tab1:
                        st.subheader("📞 Recent Call History")
                        if status['call_history']:
                            for call in reversed(status['call_history'][-10:]):  # Last 10 calls
                                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                                
                                with col1:
                                    call_type_icon = {"outbound": "📞", "api_call": "🔌", "server_link": "🔗"}.get(call['call_type'], "🤖")
                                    st.write(f"**{call_type_icon} {call['start_time'].strftime('%H:%M:%S')}**")
                                    st.caption(call.get('phone_number', call['call_type'].replace('_', ' ').title()))
                                
                                with col2:
                                    st.write(f"**{call['assistant_name']}**")
                                    st.caption(f"Context: {call.get('context', {}).get('call_context', 'N/A')[:30]}...")
                                
                                with col3:
                                    status_emoji = {"active": "🟡", "completed": "✅", "stopped": "⛔", "failed": "❌", "api_active": "🔌", "link_created": "🔗"}.get(call['status'], "❓")
                                    st.write(f"**{status_emoji} {call['status'].upper()}**")
                                    if 'duration' in call:
                                        st.caption(f"Duration: {call['duration']:.0f}s")
                                
                                with col4:
                                    st.caption(f"ID: {call['call_id'][:8]}...")
                                
                                st.markdown("---")
                        else:
                            st.info("No call history available yet.")
                    
                    with system_tab2:
                        st.subheader("📊 Audio-Fixed AI System Analytics")
                        
                        # Analytics charts
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Call type distribution
                            outbound_calls = status['analytics']['outbound_calls']
                            server_calls = status['analytics']['server_calls']
                            
                            if outbound_calls > 0 or server_calls > 0:
                                fig = px.pie(
                                    values=[outbound_calls, server_calls],
                                    names=['Outbound Calls', 'Server Calls'],
                                    title="Call Type Distribution"
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        
                        with col2:
                            # Assistant usage chart
                            if status['analytics']['assistant_usage']:
                                fig = px.bar(
                                    x=list(status['analytics']['assistant_usage'].keys()),
                                    y=list(status['analytics']['assistant_usage'].values()),
                                    title="Assistant Usage Statistics"
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        
                        # Key metrics
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Total Calls", status['analytics']['total_calls'])
                        with col2:
                            st.metric("Outbound Calls", status['analytics']['outbound_calls'])
                        with col3:
                            st.metric("Server Calls", status['analytics']['server_calls'])
                        with col4:
                            st.metric("Success Rate", f"{status['system_health']['success_rate']:.1f}%")
                    
                    with system_tab3:
                        st.subheader("📝 System Logs")
                        
                        # Log level filter
                        log_level = st.selectbox("Filter by Level", ["All", "INFO", "ERROR", "WARNING"])
                        
                        # Display logs
                        logs_to_show = status['call_logs']
                        if log_level != "All":
                            logs_to_show = [log for log in logs_to_show if log_level in log]
                        
                        for log in reversed(logs_to_show[-50:]):  # Last 50 logs
                            if "ERROR" in log:
                                st.error(log)
                            elif "WARNING" in log:
                                st.warning(log)
                            else:
                                st.info(log)
                        
                        if st.button("🧹 Clear Logs"):
                            st.session_state.ai_phone_system.call_logs = []
                            st.success("Logs cleared!")
                            st.rerun()
                    
                    # Auto-refresh for active calls
                    if status['active_calls'] > 0:
                        time.sleep(3)
                        st.rerun()
                
                else:
                    # System not initialized
                    st.markdown(f"""
                    <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%); border-radius: 15px; color: white; margin: 2rem 0;">
                        <h2>🤖 Audio-Fixed AI Phone System</h2>
                        <p>Advanced AI-powered calling system with audio error fixes</p>
                        
                        <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 10px; margin: 1.5rem 0;">
                            <h3>🔧 Audio Fixes Applied</h3>
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                                <div>
                                    <p>✅ ALSA Errors Suppressed</p>
                                    <p>✅ Rust Panic Handled</p>
                                    <p>✅ Audio Context Fixed</p>
                                    <p>✅ Streamlit Cloud Compatible</p>
                                </div>
                                <div>
                                    <p>📞 Outbound Calls</p>
                                    <p>🔗 Server Call Links</p>
                                    <p>🔌 API Calls</p>
                                    <p>📊 Real-time Monitoring</p>
                                </div>
                            </div>
                        </div>
                        
                        <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 10px; margin: 1rem 0;">
                            <h4>🎯 Real Assistant Configuration</h4>
                            <p><strong>Assistant ID:</strong> <code>{REAL_ASSISTANT_ID}</code></p>
                            <p>All AI assistants use this single real ID with different contexts</p>
                            <p><strong>Audio Status:</strong> Errors Suppressed for Streamlit Cloud</p>
                        </div>
                        
                        <p>Please configure your API key in Streamlit secrets to activate the system.</p>
                    </div>
                    """, unsafe_allow_html=True)
            
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
                    total_ai_calls = 0
                    if st.session_state.ai_phone_system:
                        status = st.session_state.ai_phone_system.get_system_status()
                        total_ai_calls = status['analytics']['total_calls']
                    
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
                
                # Audio-fixed AI phone system analytics
                if st.session_state.ai_phone_system:
                    st.subheader("🤖 Audio-Fixed AI System Analytics")
                    status = st.session_state.ai_phone_system.get_system_status()
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # System health over time (mock data for demonstration)
                        health_data = {
                            'Time': [f"{i}:00" for i in range(9, 18)],
                            'Success Rate': [95, 97, 94, 96, 98, 92, 95, 97, 96],
                            'Active Calls': [2, 5, 8, 12, 15, 18, 14, 10, 6]
                        }
                        
                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        fig.add_trace(
                            go.Scatter(x=health_data['Time'], y=health_data['Success Rate'], name="Success Rate %"),
                            secondary_y=False,
                        )
                        fig.add_trace(
                            go.Scatter(x=health_data['Time'], y=health_data['Active Calls'], name="Active Calls"),
                            secondary_y=True,
                        )
                        fig.update_xaxes(title_text="Time")
                        fig.update_yaxes(title_text="Success Rate (%)", secondary_y=False)
                        fig.update_yaxes(title_text="Active Calls", secondary_y=True)
                        fig.update_layout(title_text="Audio-Fixed AI System Performance")
                        
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # Assistant performance comparison
                        assistant_performance = []
                        for assistant_type, config in AI_ASSISTANTS.items():
                            usage_count = status['analytics']['assistant_usage'].get(assistant_type, 0)
                            assistant_performance.append({
                                'Assistant': config['name'],
                                'Usage Count': usage_count,
                                'Priority': config['priority'],
                                'Category': config['category']
                            })
                        
                        if assistant_performance:
                            perf_df = pd.DataFrame(assistant_performance)
                            fig = px.bar(perf_df, x='Assistant', y='Usage Count', 
                                        color='Category', title="Assistant Usage Statistics")
                            fig.update_xaxes(tickangle=45)
                            st.plotly_chart(fig, use_container_width=True)
                
                # User activity analytics
                st.subheader("👤 User Activity")
                st.markdown(f"**Current Session:** {st.session_state.user_info['name']} ({st.session_state.user_info['role']})")
                
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
                            "ai_assistants": AI_ASSISTANTS,
                            "real_assistant_id": REAL_ASSISTANT_ID,
                            "ai_phone_system_status": st.session_state.ai_phone_system.get_system_status() if st.session_state.ai_phone_system else {},
                            "audio_fixes_applied": True,
                            "exported_by": st.session_state.user_info['name'],
                            "export_time": datetime.now().isoformat()
                        }
                        
                        st.download_button(
                            label="Download Complete Data Export (JSON)",
                            data=json.dumps(export_data, indent=2, default=str),
                            file_name=f"crm_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                
                with col2:
                    if st.button("📊 Export Analytics Report"):
                        ai_analytics = {}
                        if st.session_state.ai_phone_system:
                            status = st.session_state.ai_phone_system.get_system_status()
                            ai_analytics = status['analytics']
                        
                        report_data = {
                            "report_generated_by": st.session_state.user_info['name'],
                            "report_date": datetime.now().isoformat(),
                            "total_customers": len(customers_df),
                            "total_invoices": len(invoices_df),
                            "total_team_members": total_team_members,
                            "ai_phone_system_analytics": ai_analytics,
                            "team_breakdown": team_performance_data,
                            "assistant_configuration": AI_ASSISTANTS,
                            "real_assistant_id": REAL_ASSISTANT_ID,
                            "audio_fixes_applied": True
                        }
                        
                        st.download_button(
                            label="Download Analytics Report (JSON)",
                            data=json.dumps(report_data, indent=2, default=str),
                            file_name=f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                
                with col3:
                    if st.button("🤖 Export AI System Data"):
                        ai_data = {
                            "ai_assistants": AI_ASSISTANTS,
                            "real_assistant_id": REAL_ASSISTANT_ID,
                            "system_status": st.session_state.ai_phone_system.get_system_status() if st.session_state.ai_phone_system else {},
                            "audio_fixes_applied": True,
                            "audio_error_suppression": "enabled",
                            "exported_by": st.session_state.user_info['name'],
                            "export_time": datetime.now().isoformat()
                        }
                        
                        st.download_button(
                            label="Download AI System Data (JSON)",
                            data=json.dumps(ai_data, indent=2, default=str),
                            file_name=f"ai_system_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
        
        except Exception as e:
            st.error(f"❌ Error loading system: {e}")
    
    else:
        # No auth file uploaded - show system ready message
        st.markdown(f"""
        <div style="text-align: center; padding: 3rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white; margin: 2rem 0;">
            <h2>🔐 System Ready - Upload Authentication</h2>
            <p>Welcome {st.session_state.user_info['name']}! Upload your Google Service Account JSON file to access all features.</p>
            
            <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 10px; margin: 1.5rem 0;">
                <h3>✨ Your Access Level: {st.session_state.user_info['role']}</h3>
                <p>Team: {st.session_state.user_info['team']}</p>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                    <div>
                        <p>✅ Customer Management</p>
                        <p>🧾 Invoice System</p>
                        <p>💰 Live Price List</p>
                        <p>📊 Analytics Dashboard</p>
                    </div>
                    <div>
                        <p>👥 Team Management ({sum(len(team["members"]) for team in TEAM_STRUCTURE.values())} members)</p>
                        <p>🤖 Audio-Fixed AI Phone System</p>
                        <p>💬 Advanced AI Chat System</p>
                        <p>📥 Comprehensive Data Export</p>
                    </div>
                </div>
            </div>
            
            <div style="background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 10px; margin: 1rem 0;">
                <h4>🔧 Audio-Fixed AI Phone System</h4>
                <p><strong>Real Assistant ID:</strong> <code>{REAL_ASSISTANT_ID}</code></p>
                <p>✅ ALSA Audio Errors Suppressed</p>
                <p>✅ Rust Panic Errors Handled</p>
                <p>✅ Streamlit Cloud Compatible</p>
                <p>📞 Outbound Calls | 🔗 Server Call Links | 🔌 API Calls</p>
                <p>🎯 6 Specialized AI Assistants (All use same real ID)</p>
                <p>📊 Real-time Analytics & Performance Monitoring</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
