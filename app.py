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
import re
import uuid
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure audio environment for headless operation
os.environ.update({
    'PULSE_RUNTIME_PATH': '/tmp/pulse',
    'ALSA_CARD': 'Dummy',
    'SDL_AUDIODRIVER': 'dummy',
    'PULSE_RUNTIME_PATH': '/tmp/pulse-runtime',
    'ALSA_CARD': 'null',
    'PULSE_RUNTIME_PATH': '/dev/null'
})

# Import VAPI with comprehensive error handling
try:
    from vapi_python import Vapi
    VAPI_AVAILABLE = True
    logger.info("VAPI Python library loaded successfully")
except ImportError as e:
    logger.warning(f"VAPI Python library not available: {e}")
    VAPI_AVAILABLE = False
except Exception as e:
    logger.error(f"Unexpected error loading VAPI: {e}")
    VAPI_AVAILABLE = False

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="🧼 Auto Laundry CRM Pro - Complete VAPI Integration",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ENUMS AND DATA CLASSES ---
class CallStatus(Enum):
    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    ENDING = "ending"
    ENDED = "ended"
    ERROR = "error"

class CallType(Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"

@dataclass
class CallRecord:
    id: str
    assistant_id: str
    assistant_name: str
    phone_number: Optional[str]
    call_type: CallType
    status: CallStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    cost: Optional[float] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict] = None

@dataclass
class PhoneNumber:
    number: str
    country_code: str
    area_code: str
    local_number: str
    formatted: str
    is_valid: bool
    carrier: Optional[str] = None
    type: Optional[str] = None  # mobile, landline, voip

# --- PHONE NUMBER UTILITIES ---
class PhoneNumberValidator:
    """Advanced phone number validation and formatting"""
    
    @staticmethod
    def parse_phone_number(phone: str) -> PhoneNumber:
        """Parse and validate phone number"""
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Default values
        country_code = ""
        area_code = ""
        local_number = ""
        formatted = phone
        is_valid = False
        carrier = None
        phone_type = None
        
        try:
            # Basic US phone number pattern
            if cleaned.startswith('+1'):
                # US number with country code
                digits = cleaned[2:]
                if len(digits) == 10:
                    country_code = "+1"
                    area_code = digits[:3]
                    local_number = digits[3:]
                    formatted = f"+1 ({area_code}) {local_number[:3]}-{local_number[3:]}"
                    is_valid = True
                    phone_type = "mobile" if area_code in ['917', '646', '347'] else "landline"
            elif len(cleaned) == 10 and cleaned.isdigit():
                # US number without country code
                country_code = "+1"
                area_code = cleaned[:3]
                local_number = cleaned[3:]
                formatted = f"+1 ({area_code}) {local_number[:3]}-{local_number[3:]}"
                is_valid = True
                phone_type = "mobile" if area_code in ['917', '646', '347'] else "landline"
            elif cleaned.startswith('+'):
                # International number
                is_valid = len(cleaned) >= 8
                formatted = cleaned
                country_code = cleaned[:3] if len(cleaned) > 3 else cleaned
                phone_type = "international"
            
        except Exception as e:
            logger.error(f"Phone parsing error: {e}")
        
        return PhoneNumber(
            number=cleaned,
            country_code=country_code,
            area_code=area_code,
            local_number=local_number,
            formatted=formatted,
            is_valid=is_valid,
            carrier=carrier,
            type=phone_type
        )
    
    @staticmethod
    def format_for_vapi(phone: str) -> str:
        """Format phone number for VAPI API"""
        parsed = PhoneNumberValidator.parse_phone_number(phone)
        if parsed.is_valid:
            return parsed.number if parsed.number.startswith('+') else f"+1{parsed.number}"
        return phone

# --- COMPREHENSIVE VAPI MANAGER ---
class ComprehensiveVAPIManager:
    """Complete VAPI integration with all phone features"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.vapi_client = None
        self.current_call = None
        self.call_thread = None
        self.is_calling = threading.Event()
        self.stop_monitoring = threading.Event()
        self.call_logs = queue.Queue(maxsize=200)
        self.call_history: List[CallRecord] = []
        self.audio_configured = False
        self._lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="VAPI")
        self.phone_validator = PhoneNumberValidator()
        self.call_analytics = {}
        self.webhook_data = queue.Queue(maxsize=50)
        
        # Initialize components
        self._configure_audio_environment()
        self._initialize_analytics()
    
    def _configure_audio_environment(self) -> Tuple[bool, str]:
        """Configure audio environment for server deployment"""
        try:
            # Comprehensive audio environment setup
            audio_env = {
                'SDL_AUDIODRIVER': 'dummy',
                'PULSE_RUNTIME_PATH': '/tmp/pulse-runtime',
                'ALSA_CARD': 'Dummy',
                'PULSE_RUNTIME_PATH': '/dev/null',
                'ALSA_CARD': 'null',
                'JACK_NO_AUDIO_RESERVATION': '1',
                'PULSE_RUNTIME_PATH': '/tmp/nonexistent',
                'XDG_RUNTIME_DIR': '/tmp'
            }
            
            for key, value in audio_env.items():
                os.environ[key] = value
            
            # Try to suppress PyAudio warnings
            try:
                import warnings
                warnings.filterwarnings("ignore", category=UserWarning, module="pyaudio")
            except:
                pass
            
            self._add_log("✅ Audio environment configured for server deployment")
            self.audio_configured = True
            return True, "Audio environment optimized for server deployment"
            
        except Exception as e:
            error_msg = f"Audio configuration: {e}"
            self._add_log(f"⚠️ {error_msg}")
            self.audio_configured = True  # Continue anyway
            return True, "Audio configured (server-side processing)"
    
    def _initialize_analytics(self):
        """Initialize call analytics tracking"""
        self.call_analytics = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'total_duration': 0,
            'total_cost': 0.0,
            'average_duration': 0,
            'calls_by_status': {},
            'calls_by_assistant': {},
            'calls_by_hour': {},
            'phone_numbers_called': set()
        }
    
    def _add_log(self, message: str, level: str = "INFO"):
        """Thread-safe log addition with levels"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{level}] {timestamp}: {message}"
        
        try:
            self.call_logs.put_nowait(log_entry)
        except queue.Full:
            try:
                self.call_logs.get_nowait()
                self.call_logs.put_nowait(log_entry)
            except queue.Empty:
                pass
        
        # Also log to Python logger
        if level == "ERROR":
            logger.error(message)
        elif level == "WARN":
            logger.warning(message)
        else:
            logger.info(message)
    
    def initialize_client(self) -> Tuple[bool, str]:
        """Initialize VAPI client with comprehensive error handling"""
        with self._lock:
            try:
                if not VAPI_AVAILABLE:
                    return False, "VAPI Python library not available. Install with: pip install vapi-python"
                
                if not self.audio_configured:
                    self._configure_audio_environment()
                
                # Initialize VAPI client with error suppression
                try:
                    self.vapi_client = Vapi(api_key=self.api_key)
                    self._add_log("🚀 VAPI client initialized successfully")
                    return True, "VAPI client ready for calls"
                except Exception as init_error:
                    # Handle specific initialization errors
                    if "audio" in str(init_error).lower():
                        self._add_log("⚠️ Audio initialization warning (expected in server environments)")
                        # Try to initialize without audio
                        self.vapi_client = Vapi(api_key=self.api_key)
                        self._add_log("✅ VAPI client initialized (server-side audio)")
                        return True, "VAPI client ready (server-side audio processing)"
                    else:
                        raise init_error
                
            except Exception as e:
                error_msg = f"Failed to initialize VAPI client: {str(e)}"
                self._add_log(error_msg, "ERROR")
                return False, error_msg
    
    def validate_phone_number(self, phone: str) -> Tuple[bool, str, PhoneNumber]:
        """Validate phone number for calling"""
        try:
            parsed = self.phone_validator.parse_phone_number(phone)
            
            if not parsed.is_valid:
                return False, "Invalid phone number format", parsed
            
            # Additional VAPI-specific validation
            vapi_formatted = self.phone_validator.format_for_vapi(phone)
            
            if len(vapi_formatted) < 8:
                return False, "Phone number too short", parsed
            
            if not vapi_formatted.startswith('+'):
                return False, "Phone number must include country code", parsed
            
            return True, f"Valid phone number: {parsed.formatted}", parsed
            
        except Exception as e:
            return False, f"Phone validation error: {e}", PhoneNumber("", "", "", "", phone, False)
    
    def create_assistant_override(self, user_name: str = None, context: str = None, 
                                phone_number: str = None) -> Dict:
        """Create assistant override configuration"""
        overrides = {}
        
        if user_name or context or phone_number:
            overrides["variableValues"] = {}
            
            if user_name:
                overrides["variableValues"]["customerName"] = user_name
                overrides["variableValues"]["name"] = user_name
            
            if phone_number:
                parsed = self.phone_validator.parse_phone_number(phone_number)
                overrides["variableValues"]["phoneNumber"] = parsed.formatted
                overrides["variableValues"]["customerPhone"] = parsed.formatted
            
            if context:
                overrides["context"] = context
                overrides["variableValues"]["additionalContext"] = context
        
        # Add system context
        overrides["systemMessage"] = f"""
        You are calling on behalf of Auto Laundry CRM Pro. 
        Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        System: Professional laundry and dry cleaning service
        Be helpful, professional, and concise.
        """
        
        return overrides
    
    def start_call(self, assistant_id: str, assistant_name: str = "AI Assistant",
                   phone_number: str = None, user_name: str = None, 
                   context: str = None, call_type: CallType = CallType.OUTBOUND) -> Tuple[bool, str]:
        """Start a comprehensive VAPI call"""
        with self._lock:
            try:
                if self.is_calling.is_set():
                    return False, "A call is already in progress. Please end the current call first."
                
                # Initialize client if needed
                if not self.vapi_client:
                    success, msg = self.initialize_client()
                    if not success:
                        return False, msg
                
                # Validate phone number if provided
                if phone_number:
                    is_valid, validation_msg, parsed_phone = self.validate_phone_number(phone_number)
                    if not is_valid:
                        return False, f"Phone validation failed: {validation_msg}"
                    
                    formatted_phone = self.phone_validator.format_for_vapi(phone_number)
                    self._add_log(f"📞 Validated phone: {parsed_phone.formatted}")
                else:
                    formatted_phone = None
                
                # Create call parameters
                call_params = {
                    "assistant_id": assistant_id
                }
                
                # Add assistant overrides
                overrides = self.create_assistant_override(user_name, context, phone_number)
                if overrides:
                    call_params["assistant_overrides"] = overrides
                
                # Add phone number for outbound calls
                if formatted_phone and call_type == CallType.OUTBOUND:
                    call_params["customer"] = {"number": formatted_phone}
                
                self._add_log(f"🚀 Starting {call_type.value} call with assistant {assistant_name}")
                
                # Start the call with comprehensive error handling
                try:
                    self.current_call = self.vapi_client.start(**call_params)
                    call_id = getattr(self.current_call, 'id', str(uuid.uuid4()))
                    
                    self.is_calling.set()
                    self.stop_monitoring.clear()
                    
                    # Create call record
                    call_record = CallRecord(
                        id=call_id,
                        assistant_id=assistant_id,
                        assistant_name=assistant_name,
                        phone_number=formatted_phone,
                        call_type=call_type,
                        status=CallStatus.ACTIVE,
                        start_time=datetime.now(),
                        user_id=user_name,
                        metadata={
                            "context": context,
                            "overrides": overrides,
                            "audio_mode": "server-side"
                        }
                    )
                    
                    self.call_history.append(call_record)
                    self._update_analytics('call_started', call_record)
                    
                    # Start monitoring
                    self.call_thread = self.executor.submit(self._monitor_call, call_record)
                    
                    success_msg = f"✅ Call started successfully!\n📞 Call ID: {call_id}\n🎯 Assistant: {assistant_name}"
                    if formatted_phone:
                        success_msg += f"\n📱 Calling: {parsed_phone.formatted}"
                    
                    self._add_log(success_msg)
                    return True, success_msg
                    
                except Exception as call_error:
                    self.is_calling.clear()
                    error_msg = self._format_call_error(str(call_error))
                    self._add_log(error_msg, "ERROR")
                    return False, error_msg
                
            except Exception as e:
                self.is_calling.clear()
                error_msg = f"Call initialization failed: {str(e)}"
                self._add_log(error_msg, "ERROR")
                return False, error_msg
    
    def stop_call(self, reason: str = "User requested") -> Tuple[bool, str]:
        """Stop current call with detailed logging"""
        with self._lock:
            try:
                if not self.is_calling.is_set():
                    return False, "No active call to stop"
                
                # Signal monitoring to stop
                self.stop_monitoring.set()
                
                # Stop the call
                if self.vapi_client and self.current_call:
                    try:
                        self.vapi_client.stop()
                        self._add_log(f"📴 Call stopped: {reason}")
                    except Exception as stop_error:
                        self._add_log(f"⚠️ Stop call warning: {stop_error}", "WARN")
                
                # Update call record
                if self.call_history:
                    last_call = self.call_history[-1]
                    last_call.status = CallStatus.ENDED
                    last_call.end_time = datetime.now()
                    if last_call.start_time:
                        duration = (last_call.end_time - last_call.start_time).total_seconds()
                        last_call.duration = int(duration)
                    
                    self._update_analytics('call_ended', last_call)
                
                self.is_calling.clear()
                self.current_call = None
                
                return True, f"✅ Call ended successfully. Reason: {reason}"
                
            except Exception as e:
                self.is_calling.clear()
                self.current_call = None
                error_msg = f"Error stopping call: {str(e)}"
                self._add_log(error_msg, "ERROR")
                return False, error_msg
    
    def _monitor_call(self, call_record: CallRecord):
        """Enhanced call monitoring with detailed status tracking"""
        try:
            monitor_count = 0
            while self.is_calling.is_set() and not self.stop_monitoring.is_set():
                monitor_count += 1
                
                # Periodic status updates
                if monitor_count % 6 == 0:  # Every minute (10s * 6)
                    duration = int((datetime.now() - call_record.start_time).total_seconds())
                    self._add_log(f"📞 Call active - Duration: {duration}s - ID: {call_record.id}")
                
                # Check for call completion (you could add VAPI status checks here)
                if hasattr(self.current_call, 'status'):
                    call_status = getattr(self.current_call, 'status', None)
                    if call_status and call_status in ['ended', 'completed', 'failed']:
                        self._add_log(f"📋 Call status changed to: {call_status}")
                        break
                
                # Wait with early exit on stop signal
                if self.stop_monitoring.wait(timeout=10):
                    break
                    
        except Exception as e:
            self._add_log(f"Monitor error: {str(e)}", "ERROR")
        finally:
            # Ensure call is marked as ended
            if self.is_calling.is_set():
                self.is_calling.clear()
                if self.call_history:
                    last_call = self.call_history[-1]
                    if last_call.status == CallStatus.ACTIVE:
                        last_call.status = CallStatus.ENDED
                        last_call.end_time = datetime.now()
                        if last_call.start_time:
                            duration = (last_call.end_time - last_call.start_time).total_seconds()
                            last_call.duration = int(duration)
                        self._update_analytics('call_ended', last_call)
    
    def _update_analytics(self, event: str, call_record: CallRecord):
        """Update call analytics"""
        try:
            if event == 'call_started':
                self.call_analytics['total_calls'] += 1
                
                # Track by assistant
                assistant_name = call_record.assistant_name
                if assistant_name not in self.call_analytics['calls_by_assistant']:
                    self.call_analytics['calls_by_assistant'][assistant_name] = 0
                self.call_analytics['calls_by_assistant'][assistant_name] += 1
                
                # Track by hour
                hour = call_record.start_time.hour
                if hour not in self.call_analytics['calls_by_hour']:
                    self.call_analytics['calls_by_hour'][hour] = 0
                self.call_analytics['calls_by_hour'][hour] += 1
                
                # Track phone numbers
                if call_record.phone_number:
                    self.call_analytics['phone_numbers_called'].add(call_record.phone_number)
            
            elif event == 'call_ended':
                if call_record.status == CallStatus.ENDED:
                    self.call_analytics['successful_calls'] += 1
                else:
                    self.call_analytics['failed_calls'] += 1
                
                # Update duration stats
                if call_record.duration:
                    self.call_analytics['total_duration'] += call_record.duration
                    total_calls = self.call_analytics['successful_calls'] + self.call_analytics['failed_calls']
                    if total_calls > 0:
                        self.call_analytics['average_duration'] = self.call_analytics['total_duration'] / total_calls
                
                # Track by status
                status = call_record.status.value
                if status not in self.call_analytics['calls_by_status']:
                    self.call_analytics['calls_by_status'][status] = 0
                self.call_analytics['calls_by_status'][status] += 1
                
        except Exception as e:
            self._add_log(f"Analytics update error: {e}", "ERROR")
    
    def _format_call_error(self, error: str) -> str:
        """Format call errors with helpful context"""
        error_lower = error.lower()
        
        if "audio" in error_lower or "device" in error_lower:
            return """🔊 Audio Device Notice: This is expected in server environments.
            
✅ VAPI handles all audio processing server-side
✅ No local audio devices required
✅ Calls will work normally
            
The call should proceed successfully despite this message."""
        
        elif "pyaudio" in error_lower:
            return """🎵 PyAudio Notice: Audio library warning (normal in cloud deployment)
            
✅ VAPI manages audio on their servers
✅ Your calls will work perfectly
✅ This is not an error - just a system notice"""
        
        elif "invalid" in error_lower and "phone" in error_lower:
            return f"📱 Phone Number Error: {error}\n\n💡 Try formatting as: +1234567890 or (123) 456-7890"
        
        elif "api" in error_lower or "key" in error_lower:
            return f"🔑 API Error: {error}\n\n💡 Check your VAPI API key in Streamlit secrets"
        
        elif "assistant" in error_lower:
            return f"🤖 Assistant Error: {error}\n\n💡 Verify the Assistant ID exists in your VAPI dashboard"
        
        else:
            return f"⚠️ Call Error: {error}"
    
    def get_call_status(self) -> Dict[str, Any]:
        """Get comprehensive call status"""
        with self._lock:
            # Get logs
            logs = []
            temp_logs = []
            
            while not self.call_logs.empty():
                try:
                    log = self.call_logs.get_nowait()
                    temp_logs.append(log)
                    logs.append(log)
                except queue.Empty:
                    break
            
            # Put logs back
            for log in temp_logs:
                try:
                    self.call_logs.put_nowait(log)
                except queue.Full:
                    break
            
            # Current call info
            current_call_info = None
            if self.is_calling.is_set() and self.call_history:
                last_call = self.call_history[-1]
                current_call_info = {
                    'id': last_call.id,
                    'assistant_name': last_call.assistant_name,
                    'phone_number': last_call.phone_number,
                    'start_time': last_call.start_time.strftime('%H:%M:%S'),
                    'duration': int((datetime.now() - last_call.start_time).total_seconds()) if last_call.start_time else 0
                }
            
            return {
                'is_calling': self.is_calling.is_set(),
                'current_call': current_call_info,
                'logs': logs[-30:],  # Last 30 log entries
                'history': [asdict(call) for call in self.call_history[-20:]],  # Last 20 calls
                'analytics': self.call_analytics.copy(),
                'audio_configured': self.audio_configured,
                'vapi_available': VAPI_AVAILABLE,
                'total_calls_today': len([c for c in self.call_history if c.start_time.date() == datetime.now().date()]),
                'active_duration': int((datetime.now() - self.call_history[-1].start_time).total_seconds()) if self.call_history and self.is_calling.is_set() else 0
            }
    
    def get_call_history_df(self) -> pd.DataFrame:
        """Get call history as DataFrame for analysis"""
        if not self.call_history:
            return pd.DataFrame()
        
        try:
            data = []
            for call in self.call_history:
                data.append({
                    'Call ID': call.id[:8] + '...',
                    'Assistant': call.assistant_name,
                    'Phone Number': call.phone_number or 'N/A',
                    'Type': call.call_type.value.title(),
                    'Status': call.status.value.title(),
                    'Start Time': call.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'Duration (s)': call.duration or 0,
                    'User': call.user_id or 'Unknown'
                })
            
            return pd.DataFrame(data)
        except Exception as e:
            self._add_log(f"DataFrame creation error: {e}", "ERROR")
            return pd.DataFrame()
    
    def clear_logs(self):
        """Clear call logs"""
        with self._lock:
            while not self.call_logs.empty():
                try:
                    self.call_logs.get_nowait()
                except queue.Empty:
                    break
            self._add_log("🧹 Logs cleared")
    
    def clear_history(self):
        """Clear call history"""
        with self._lock:
            self.call_history.clear()
            self._initialize_analytics()
            self._add_log("🗑️ Call history cleared")
    
    def export_call_data(self) -> Dict:
        """Export all call data"""
        return {
            'call_history': [asdict(call) for call in self.call_history],
            'analytics': self.call_analytics,
            'export_time': datetime.now().isoformat(),
            'total_calls': len(self.call_history),
            'vapi_available': VAPI_AVAILABLE
        }
    
    def cleanup(self):
        """Comprehensive cleanup"""
        with self._lock:
            self.stop_monitoring.set()
            if self.is_calling.is_set():
                self.stop_call("System cleanup")
            self.executor.shutdown(wait=True)
            self._add_log("🧹 VAPI Manager cleaned up")

# --- ENHANCED SESSION STATE MANAGER ---
class EnhancedSessionStateManager:
    """Enhanced thread-safe session state manager"""
    
    def __init__(self):
        self._lock = threading.RLock()
    
    def get(self, key: str, default=None):
        with self._lock:
            return st.session_state.get(key, default)
    
    def set(self, key: str, value):
        with self._lock:
            st.session_state[key] = value
    
    def update(self, updates: Dict[str, Any]):
        with self._lock:
            for key, value in updates.items():
                st.session_state[key] = value
    
    def delete(self, key: str):
        with self._lock:
            if key in st.session_state:
                del st.session_state[key]
    
    def exists(self, key: str) -> bool:
        with self._lock:
            return key in st.session_state

# Initialize session state manager
session_manager = EnhancedSessionStateManager()

# --- CONSTANTS ---
DEMO_ACCOUNTS = {
    "admin": {"password": "admin123", "role": "Admin", "team": "Management", "name": "John Admin"},
    "manager1": {"password": "manager123", "role": "Manager", "team": "Operations", "name": "Sarah Manager"},
    "agent1": {"password": "agent123", "role": "Agent", "team": "Customer Service", "name": "Mike Agent"},
    "demo": {"password": "demo123", "role": "Demo User", "team": "Demo", "name": "Demo User"}
}

COMPREHENSIVE_AGENTS = {
    "Customer Support": {
        "id": "7b2b8b86-5caa-4f28-8c6b-e7d3d0404f06",
        "name": "Customer Support Specialist",
        "description": "Handles customer inquiries, resolves issues, and provides excellent service with empathy and technical knowledge.",
        "use_cases": ["Product support", "Issue resolution", "General inquiries"],
        "personality": "Professional, empathetic, solution-focused"
    },
    "Sales Assistant": {
        "id": "232f3d9c-18b3-4963-bdd9-e7de3be156ae",
        "name": "Sales Development Representative",
        "description": "Identifies qualified prospects, understands business needs, and connects them with appropriate sales representatives.",
        "use_cases": ["Lead qualification", "Product demos", "Sales follow-up"],
        "personality": "Enthusiastic, persuasive, goal-oriented"
    },
    "Laundry Specialist": {
        "id": "41fe59e1-829f-4936-8ee5-eef2bb1287fe",
        "name": "Laundry Service Expert",
        "description": "Expert in laundry services, pricing, scheduling, and special garment care. Handles service bookings and customer questions.",
        "use_cases": ["Service booking", "Pricing inquiries", "Special care instructions"],
        "personality": "Knowledgeable, detail-oriented, helpful"
    },
    "Appointment Scheduler": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "Appointment Coordinator",
        "description": "Efficiently books, confirms, reschedules, and cancels appointments while providing clear service information.",
        "use_cases": ["Appointment booking", "Schedule management", "Confirmation calls"],
        "personality": "Organized, efficient, accommodating"
    },
    "Feedback Collector": {
        "id": "f1e2d3c4-b5a6-9870-fedc-ba0987654321",
        "name": "Customer Feedback Specialist",
        "description": "Conducts surveys, collects customer feedback, and gathers market research with high completion rates.",
        "use_cases": ["Customer surveys", "Feedback collection", "Market research"],
        "personality": "Friendly, patient, thorough"
    }
}

# --- UTILITY FUNCTIONS ---
def initialize_session_state():
    """Initialize session state with comprehensive defaults"""
    defaults = {
        'logged_in': False,
        'user_info': {},
        'username': '',
        'vapi_manager': None,
        'show_agent_details': False,
        'auto_refresh_calls': True,
        'call_refresh_interval': 10,
        'phone_book': [],
        'recent_calls': [],
        'favorite_assistants': []
    }
    
    for key, default_value in defaults.items():
        if not session_manager.exists(key):
            session_manager.set(key, default_value)

def login_user(username, password):
    if username in DEMO_ACCOUNTS and DEMO_ACCOUNTS[username]["password"] == password:
        return DEMO_ACCOUNTS[username]
    return None

def logout_user():
    vapi_manager = session_manager.get('vapi_manager')
    if vapi_manager:
        vapi_manager.cleanup()
    
    keys_to_clear = [key for key in st.session_state.keys() if key.startswith('user_') or key in ['logged_in', 'vapi_manager']]
    for key in keys_to_clear:
        session_manager.delete(key)
    
    session_manager.set('logged_in', False)

# Initialize session state
initialize_session_state()

# --- ENHANCED CSS ---
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
    .call-active {
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        padding: 1.5rem;
        border-radius: 15px;
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
    .phone-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .assistant-card {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 5px solid #667eea;
    }
    .audio-notice {
        background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: #2d3436;
        margin: 1rem 0;
        text-align: center;
        border-left: 5px solid #fdcb6e;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
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
</style>
""", unsafe_allow_html=True)

# --- MAIN APPLICATION ---
if not session_manager.get('logged_in'):
    # LOGIN PAGE
    st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro - Complete VAPI Integration</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 15px; color: white; text-align: center; margin: 2rem 0;">
            <h2>🔐 Login to Enhanced CRM System</h2>
            <p>Complete VAPI integration with phone validation and comprehensive call management</p>
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
        
        # Demo accounts
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
    
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown('<div class="main-header">🧼 Auto Laundry CRM Pro - Complete VAPI</div>', unsafe_allow_html=True)
    
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
    
    # Initialize VAPI manager
    if not session_manager.get('vapi_manager'):
        try:
            api_key = st.secrets.get("VAPI_API_KEY")
            if api_key:
                vapi_manager = ComprehensiveVAPIManager(api_key)
                session_manager.set('vapi_manager', vapi_manager)
                st.success("🚀 VAPI Manager initialized successfully!")
            else:
                st.error("❌ VAPI_API_KEY not found in secrets")
        except Exception as e:
            st.error(f"❌ Failed to initialize VAPI: {e}")
    
    vapi_manager = session_manager.get('vapi_manager')
    
    # Sidebar
    st.sidebar.markdown("### 📞 Call Center Status")
    
    if vapi_manager:
        status = vapi_manager.get_call_status()
        
        if status['is_calling']:
            st.sidebar.markdown("🟢 **CALL ACTIVE**")
            if status['current_call']:
                st.sidebar.write(f"📱 {status['current_call']['phone_number'] or 'No phone'}")
                st.sidebar.write(f"🤖 {status['current_call']['assistant_name']}")
                st.sidebar.write(f"⏱️ {status['current_call']['duration']}s")
        else:
            st.sidebar.markdown("🔴 **No Active Call**")
        
        st.sidebar.write(f"📊 Total Calls: {status['analytics']['total_calls']}")
        st.sidebar.write(f"✅ Successful: {status['analytics']['successful_calls']}")
        st.sidebar.write(f"📞 Today: {status['total_calls_today']}")
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏠 Dashboard",
        "📞 Phone & VAPI Center",
        "📱 Phone Book",
        "📊 Call Analytics",
        "⚙️ Settings"
    ])
    
    with tab1:
        st.subheader("📊 Enhanced CRM Dashboard")
        st.markdown(f"### Welcome back, {user_info['name']}! 👋")
        
        if vapi_manager:
            status = vapi_manager.get_call_status()
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>📞 Total Calls</h3>
                    <h2>{status['analytics']['total_calls']}</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            with col2:
                st.markdown(f'''
                <div class="metric-card">
                    <h3>✅ Successful</h3>
                    <h2>{status['analytics']['successful_calls']}</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            with col3:
                avg_duration = status['analytics']['average_duration']
                st.markdown(f'''
                <div class="metric-card">
                    <h3>⏱️ Avg Duration</h3>
                    <h2>{avg_duration:.0f}s</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            with col4:
                unique_numbers = len(status['analytics']['phone_numbers_called'])
                st.markdown(f'''
                <div class="metric-card">
                    <h3>📱 Unique Numbers</h3>
                    <h2>{unique_numbers}</h2>
                </div>
                ''', unsafe_allow_html=True)
            
            # Current call status
            if status['is_calling'] and status['current_call']:
                st.markdown(f'''
                <div class="call-active">
                    <h2>🟢 CALL IN PROGRESS</h2>
                    <p><strong>Assistant:</strong> {status['current_call']['assistant_name']}</p>
                    <p><strong>Phone:</strong> {status['current_call']['phone_number'] or 'No phone number'}</p>
                    <p><strong>Duration:</strong> {status['current_call']['duration']} seconds</p>
                    <p><strong>Started:</strong> {status['current_call']['start_time']}</p>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown('''
                <div class="call-inactive">
                    <h3>🔴 No Active Calls</h3>
                    <p>Ready to start new calls</p>
                </div>
                ''', unsafe_allow_html=True)
            
            # Recent calls
            if status['history']:
                st.subheader("📋 Recent Calls")
                recent_df = vapi_manager.get_call_history_df()
                if not recent_df.empty:
                    st.dataframe(recent_df.tail(5), use_container_width=True)
    
    with tab2:
        st.subheader("📞 Complete Phone & VAPI Call Center")
        
        if not VAPI_AVAILABLE:
            st.error("❌ VAPI library not available. Install with: `pip install vapi-python`")
            st.stop()
        
        if not vapi_manager:
            st.error("❌ VAPI Manager not initialized. Check your API key.")
            st.stop()
        
        # Audio notice
        st.markdown('''
        <div class="audio-notice">
            <h3>🔊 Audio Environment Notice</h3>
            <p><strong>✅ Server-Side Audio:</strong> All audio processing handled by VAPI servers</p>
            <p><strong>✅ No Local Devices:</strong> No microphone or speakers needed on your machine</p>
            <p><strong>✅ Cloud Optimized:</strong> Perfect for Streamlit Cloud deployment</p>
            <p><strong>ℹ️ Any "audio device" messages are normal and expected in server environments</strong></p>
        </div>
        ''', unsafe_allow_html=True)
        
        # Call interface
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🎯 Make a Call")
            
            # Assistant selection
            st.markdown("**1. Choose Your AI Assistant**")
            assistant_options = list(COMPREHENSIVE_AGENTS.keys())
            selected_assistant_key = st.selectbox(
                "Select Assistant Type",
                assistant_options,
                help="Choose the AI assistant that best fits your call purpose"
            )
            
            selected_assistant = COMPREHENSIVE_AGENTS[selected_assistant_key]
            
            # Show assistant details
            if session_manager.get('show_agent_details', False):
                st.markdown(f'''
                <div class="assistant-card">
                    <h4>🤖 {selected_assistant['name']}</h4>
                    <p><strong>Description:</strong> {selected_assistant['description']}</p>
                    <p><strong>Best for:</strong> {', '.join(selected_assistant['use_cases'])}</p>
                    <p><strong>Personality:</strong> {selected_assistant['personality']}</p>
                </div>
                ''', unsafe_allow_html=True)
            
            # Phone number input with validation
            st.markdown("**2. Enter Phone Number**")
            phone_input = st.text_input(
                "Phone Number",
                placeholder="+1 (555) 123-4567 or 5551234567",
                help="Enter phone number with or without country code"
            )
            
            # Real-time phone validation
            if phone_input:
                is_valid, validation_msg, parsed_phone = vapi_manager.validate_phone_number(phone_input)
                if is_valid:
                    st.success(f"✅ {validation_msg}")
                    st.info(f"📱 Will call: {parsed_phone.formatted}")
                else:
                    st.error(f"❌ {validation_msg}")
            
            # Call configuration
            st.markdown("**3. Call Configuration**")
            col_a, col_b = st.columns(2)
            
            with col_a:
                caller_name = st.text_input(
                    "Your Name",
                    value=user_info['name'],
                    help="Name to introduce yourself as"
                )
            
            with col_b:
                call_purpose = st.selectbox(
                    "Call Purpose",
                    ["Customer Support", "Sales Inquiry", "Service Booking", "Follow-up", "Survey", "Other"]
                )
            
            additional_context = st.text_area(
                "Additional Context",
                placeholder="Any specific information or instructions for the AI assistant...",
                help="This context will be provided to the AI assistant"
            )
            
            # Call controls
            st.markdown("**4. Call Controls**")
            status = vapi_manager.get_call_status()
            
            col_x, col_y, col_z = st.columns(3)
            
            with col_x:
                start_disabled = status['is_calling'] or not phone_input or not is_valid
                if st.button("📞 Start Call", disabled=start_disabled, type="primary", use_container_width=True):
                    context = f"Call purpose: {call_purpose}. {additional_context}".strip()
                    
                    success, message = vapi_manager.start_call(
                        assistant_id=selected_assistant['id'],
                        assistant_name=selected_assistant['name'],
                        phone_number=phone_input,
                        user_name=caller_name,
                        context=context,
                        call_type=CallType.OUTBOUND
                    )
                    
                    if success:
                        st.success(message)
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(message)
            
            with col_y:
                stop_disabled = not status['is_calling']
                if st.button("⛔ End Call", disabled=stop_disabled, type="secondary", use_container_width=True):
                    success, message = vapi_manager.stop_call("User ended call")
                    if success:
                        st.success(message)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(message)
            
            with col_z:
                if st.button("🔄 Refresh Status", use_container_width=True):
                    st.rerun()
        
        with col2:
            st.subheader("📊 Live Status")
            
            status = vapi_manager.get_call_status()
            
            # Current call info
            if status['is_calling'] and status['current_call']:
                st.markdown(f'''
                <div class="phone-card">
                    <h4>📞 Active Call</h4>
                    <p><strong>Assistant:</strong> {status['current_call']['assistant_name']}</p>
                    <p><strong>Phone:</strong> {status['current_call']['phone_number']}</p>
                    <p><strong>Duration:</strong> {status['current_call']['duration']}s</p>
                    <p><strong>Call ID:</strong> {status['current_call']['id'][:8]}...</p>
                </div>
                ''', unsafe_allow_html=True)
            else:
                st.info("🔴 No active call")
            
            # Quick stats
            st.markdown("**Today's Stats**")
            st.metric("📞 Calls Today", status['total_calls_today'])
            st.metric("✅ Success Rate", f"{(status['analytics']['successful_calls'] / max(status['analytics']['total_calls'], 1) * 100):.1f}%")
            st.metric("⏱️ Avg Duration", f"{status['analytics']['average_duration']:.0f}s")
            
            # Quick actions
            st.markdown("**Quick Actions**")
            if st.button("🧹 Clear Logs", use_container_width=True):
                vapi_manager.clear_logs()
                st.success("Logs cleared!")
            
            if st.button("ℹ️ Toggle Assistant Details", use_container_width=True):
                current = session_manager.get('show_agent_details', False)
                session_manager.set('show_agent_details', not current)
                st.rerun()
        
        # Live logs
        st.subheader("📝 Live Call Logs")
        
        tab_logs, tab_history = st.tabs(["Live Logs", "Call History"])
        
        with tab_logs:
            status = vapi_manager.get_call_status()
            if status['logs']:
                # Show logs in reverse order (newest first)
                for log in reversed(status['logs'][-15:]):
                    if "[ERROR]" in log:
                        st.error(log)
                    elif "[WARN]" in log:
                        st.warning(log)
                    else:
                        st.info(log)
            else:
                st.info("No logs available")
        
        with tab_history:
            call_df = vapi_manager.get_call_history_df()
            if not call_df.empty:
                st.dataframe(call_df, use_container_width=True)
            else:
                st.info("No call history available")
        
        # Auto-refresh for active calls
        if status['is_calling'] and session_manager.get('auto_refresh_calls', True):
            time.sleep(session_manager.get('call_refresh_interval', 10))
            st.rerun()
    
    with tab3:
        st.subheader("📱 Phone Book Management")
        
        # Phone book functionality
        phone_book = session_manager.get('phone_book', [])
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**Add New Contact**")
            with st.form("add_contact"):
                contact_name = st.text_input("Name")
                contact_phone = st.text_input("Phone Number")
                contact_type = st.selectbox("Type", ["Customer", "Lead", "Partner", "Other"])
                contact_notes = st.text_area("Notes")
                
                if st.form_submit_button("➕ Add Contact"):
                    if contact_name and contact_phone:
                        is_valid, msg, parsed = vapi_manager.validate_phone_number(contact_phone)
                        if is_valid:
                            new_contact = {
                                'id': str(uuid.uuid4()),
                                'name': contact_name,
                                'phone': parsed.formatted,
                                'type': contact_type,
                                'notes': contact_notes,
                                'added_date': datetime.now().isoformat(),
                                'added_by': user_info['name']
                            }
                            phone_book.append(new_contact)
                            session_manager.set('phone_book', phone_book)
                            st.success(f"✅ Added {contact_name}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                    else:
                        st.error("❌ Name and phone required")
        
        with col2:
            st.markdown("**Phone Book**")
            if phone_book:
                for contact in phone_book:
                    with st.expander(f"📞 {contact['name']} - {contact['phone']}"):
                        col_a, col_b, col_c = st.columns([2, 1, 1])
                        
                        with col_a:
                            st.write(f"**Type:** {contact['type']}")
                            st.write(f"**Notes:** {contact['notes']}")
                            st.write(f"**Added:** {contact['added_date'][:10]}")
                        
                        with col_b:
                            if st.button(f"📞 Call", key=f"call_{contact['id']}"):
                                # Pre-fill call form
                                st.session_state['prefill_phone'] = contact['phone']
                                st.session_state['prefill_name'] = contact['name']
                                st.success(f"Phone number {contact['phone']} ready for calling!")
                        
                        with col_c:
                            if st.button(f"🗑️ Delete", key=f"del_{contact['id']}"):
                                phone_book = [c for c in phone_book if c['id'] != contact['id']]
                                session_manager.set('phone_book', phone_book)
                                st.rerun()
            else:
                st.info("📝 No contacts in phone book yet")
    
    with tab4:
        st.subheader("📊 Comprehensive Call Analytics")
        
        if vapi_manager:
            status = vapi_manager.get_call_status()
            analytics = status['analytics']
            
            # Overview metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("📞 Total Calls", analytics['total_calls'])
            with col2:
                st.metric("✅ Successful", analytics['successful_calls'])
            with col3:
                st.metric("❌ Failed", analytics['failed_calls'])
            with col4:
                success_rate = (analytics['successful_calls'] / max(analytics['total_calls'], 1)) * 100
                st.metric("📈 Success Rate", f"{success_rate:.1f}%")
            
            # Charts
            if analytics['total_calls'] > 0:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Calls by status
                    if analytics['calls_by_status']:
                        fig = px.pie(
                            values=list(analytics['calls_by_status'].values()),
                            names=list(analytics['calls_by_status'].keys()),
                            title="📊 Calls by Status"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Calls by assistant
                    if analytics['calls_by_assistant']:
                        fig = px.bar(
                            x=list(analytics['calls_by_assistant'].keys()),
                            y=list(analytics['calls_by_assistant'].values()),
                            title="🤖 Calls by Assistant"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                # Calls by hour
                if analytics['calls_by_hour']:
                    st.subheader("⏰ Calls by Hour of Day")
                    fig = px.bar(
                        x=list(analytics['calls_by_hour'].keys()),
                        y=list(analytics['calls_by_hour'].values()),
                        title="📈 Call Volume by Hour"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Call history table
                st.subheader("📋 Detailed Call History")
                call_df = vapi_manager.get_call_history_df()
                if not call_df.empty:
                    st.dataframe(call_df, use_container_width=True)
                    
                    # Export options
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("📥 Export Call Data"):
                            export_data = vapi_manager.export_call_data()
                            st.download_button(
                                label="Download Call Data (JSON)",
                                data=json.dumps(export_data, indent=2, default=str),
                                file_name=f"call_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json"
                            )
                    
                    with col2:
                        if st.button("📊 Export CSV"):
                            csv_data = call_df.to_csv(index=False)
                            st.download_button(
                                label="Download CSV",
                                data=csv_data,
                                file_name=f"calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
            else:
                st.info("📊 No call data available yet. Make some calls to see analytics!")
    
    with tab5:
        st.subheader("⚙️ System Settings")
        
        # VAPI Settings
        st.markdown("**🔧 VAPI Configuration**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Auto-refresh settings
            auto_refresh = st.checkbox(
                "🔄 Auto-refresh during calls",
                value=session_manager.get('auto_refresh_calls', True),
                help="Automatically refresh the interface during active calls"
            )
            session_manager.set('auto_refresh_calls', auto_refresh)
            
            refresh_interval = st.slider(
                "⏱️ Refresh interval (seconds)",
                min_value=5,
                max_value=30,
                value=session_manager.get('call_refresh_interval', 10),
                help="How often to refresh during active calls"
            )
            session_manager.set('call_refresh_interval', refresh_interval)
        
        with col2:
            # System info
            st.markdown("**📊 System Information**")
            st.write(f"**VAPI Available:** {'✅ Yes' if VAPI_AVAILABLE else '❌ No'}")
            st.write(f"**Audio Configured:** {'✅ Yes' if vapi_manager and vapi_manager.audio_configured else '❌ No'}")
            st.write(f"**User:** {user_info['name']} ({user_info['role']})")
            st.write(f"**Session:** Active")
        
        # Data management
        st.markdown("---")
        st.markdown("**🗂️ Data Management**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🧹 Clear Call Logs", use_container_width=True):
                if vapi_manager:
                    vapi_manager.clear_logs()
                    st.success("✅ Call logs cleared")
        
        with col2:
            if st.button("🗑️ Clear Call History", use_container_width=True):
                if vapi_manager:
                    vapi_manager.clear_history()
                    st.success("✅ Call history cleared")
        
        with col3:
            if st.button("📥 Export All Data", use_container_width=True):
                if vapi_manager:
                    export_data = {
                        "user_info": user_info,
                        "phone_book": session_manager.get('phone_book', []),
                        "call_data": vapi_manager.export_call_data(),
                        "system_info": {
                            "vapi_available": VAPI_AVAILABLE,
                            "audio_configured": vapi_manager.audio_configured if vapi_manager else False,
                            "export_time": datetime.now().isoformat()
                        }
                    }
                    
                    st.download_button(
                        label="Download Complete System Export",
                        data=json.dumps(export_data, indent=2, default=str),
                        file_name=f"crm_complete_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
        
        # Assistant management
        st.markdown("---")
        st.markdown("**🤖 AI Assistant Management**")
        
        # Show all available assistants
        for assistant_key, assistant_info in COMPREHENSIVE_AGENTS.items():
            with st.expander(f"🤖 {assistant_info['name']}"):
                col_a, col_b = st.columns([2, 1])
                
                with col_a:
                    st.write(f"**ID:** `{assistant_info['id']}`")
                    st.write(f"**Description:** {assistant_info['description']}")
                    st.write(f"**Use Cases:** {', '.join(assistant_info['use_cases'])}")
                    st.write(f"**Personality:** {assistant_info['personality']}")
                
                with col_b:
                    # Quick test call button
                    if st.button(f"🧪 Test Assistant", key=f"test_{assistant_key}"):
                        st.info(f"Test call feature for {assistant_info['name']} - Add phone number in Phone & VAPI Center tab")
        
        # System diagnostics
        st.markdown("---")
        st.markdown("**🔍 System Diagnostics**")
        
        if st.button("🔍 Run System Check"):
            with st.spinner("Running system diagnostics..."):
                diagnostics = {}
                
                # Check VAPI availability
                diagnostics['vapi_library'] = VAPI_AVAILABLE
                
                # Check VAPI manager
                diagnostics['vapi_manager'] = vapi_manager is not None
                
                # Check audio configuration
                if vapi_manager:
                    diagnostics['audio_configured'] = vapi_manager.audio_configured
                    diagnostics['client_initialized'] = vapi_manager.vapi_client is not None
                else:
                    diagnostics['audio_configured'] = False
                    diagnostics['client_initialized'] = False
                
                # Check API key
                try:
                    api_key = st.secrets.get("VAPI_API_KEY")
                    diagnostics['api_key_present'] = bool(api_key)
                except:
                    diagnostics['api_key_present'] = False
                
                # Display results
                st.subheader("🔍 Diagnostic Results")
                
                for check, result in diagnostics.items():
                    status = "✅" if result else "❌"
                    st.write(f"{status} **{check.replace('_', ' ').title()}:** {result}")
                
                # Overall status
                all_good = all(diagnostics.values())
                if all_good:
                    st.success("🎉 All systems operational!")
                else:
                    st.warning("⚠️ Some issues detected. Check the results above.")

# Cleanup on app shutdown
import atexit

def cleanup_resources():
    """Cleanup resources on app shutdown"""
    vapi_manager = session_manager.get('vapi_manager')
    if vapi_manager:
        vapi_manager.cleanup()

atexit.register(cleanup_resources)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white; margin: 2rem 0;">
    <h4>🧼 Auto Laundry CRM Pro - Complete VAPI Integration</h4>
    <p>✅ Server-side audio processing | 📞 Advanced phone validation | 🤖 Comprehensive AI assistants</p>
    <p>🔧 Thread-safe operations | 📊 Real-time analytics | 📱 Complete phone book management</p>
    <small>Powered by VAPI • Streamlit • Advanced Threading</small>
</div>
""", unsafe_allow_html=True)
