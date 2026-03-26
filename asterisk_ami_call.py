#!/usr/bin/env python3
"""
Asterisk AMI (Asterisk Manager Interface) Call Originator
Initiates calls via Asterisk and detects DTMF 9 to trigger door unlock
"""

import socket
import time
import sys
import logging
import hashlib
import re
from threading import Thread, Event

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

class AsteriskAMI:
    """Manages connection to Asterisk Manager Interface"""
    
    def __init__(self, host, port, username, secret):
        """
        Initialize AMI connection parameters
        
        Args:
            host: Asterisk server IP/hostname
            port: AMI port (default 5038)
            username: Manager username
            secret: Manager secret
        """
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.socket = None
        self.connected = False
        self.action_id_counter = 0
        self.dtmf_detected = Event()
        self.dtmf_digit = None
        self.call_active = False
        self.channel_name = None
        
    def connect(self):
        """Establish connection to AMI"""
        try:
            logger.info(f"Connecting to Asterisk AMI at {self.host}:{self.port}")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            
            # Read Asterisk welcome message
            welcome = self.socket.recv(1024).decode('utf-8')
            logger.info("Connected to Asterisk")
            
            # Authenticate
            self._authenticate()
            
            # Start event listener thread
            listener_thread = Thread(target=self._listen_events, daemon=True)
            listener_thread.start()
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to AMI: {e}")
            return False
    
    def disconnect(self):
        """Close AMI connection"""
        if self.socket:
            try:
                self.socket.close()
                logger.info("Disconnected from AMI")
            except:
                pass
        self.connected = False
    
    def _get_action_id(self):
        """Generate unique action ID for AMI requests"""
        self.action_id_counter += 1
        return str(self.action_id_counter)
    
    def _authenticate(self):
        """Authenticate with Asterisk Manager"""
        logger.info(f"Authenticating as {self.username}")
        
        action_id = self._get_action_id()
        auth_cmd = (
            f"Action: Login\r\n"
            f"ActionID: {action_id}\r\n"
            f"Username: {self.username}\r\n"
            f"Secret: {self.secret}\r\n"
            f"\r\n"
        )
        
        self.socket.send(auth_cmd.encode('utf-8'))
        
        # Read authentication response
        time.sleep(0.5)
        response = self._read_response()
        
        if 'Success' in response or 'success' in response:
            logger.info("Authentication successful")
            return True
        else:
            logger.error(f"Authentication failed: {response}")
            raise Exception("AMI authentication failed")
    
    def _read_response(self, timeout=2):
        """Read response from socket"""
        response = ""
        self.socket.settimeout(timeout)
        try:
            while True:
                data = self.socket.recv(1024).decode('utf-8')
                if not data:
                    break
                response += data
                if '\r\n\r\n' in response:
                    break
        except socket.timeout:
            pass
        except Exception as e:
            logger.error(f"Error reading response: {e}")
        
        return response
    
    def _listen_events(self):
        """Listen for AMI events (runs in background thread)"""
        logger.info("Event listener started")
        
        buffer = ""
        self.socket.settimeout(None)  # Blocking mode
        
        try:
            while self.connected:
                try:
                    data = self.socket.recv(4096).decode('utf-8', errors='ignore')
                    if not data:
                        break
                    
                    buffer += data
                    
                    # Process complete events (separated by \r\n\r\n)
                    while '\r\n\r\n' in buffer:
                        event, buffer = buffer.split('\r\n\r\n', 1)
                        self._process_event(event)
                        
                except Exception as e:
                    if self.connected:
                        logger.error(f"Event listener error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Event listener crashed: {e}")
        finally:
            logger.info("Event listener stopped")
    
    def _process_event(self, event_text):
        """Process incoming AMI event"""
        lines = event_text.strip().split('\r\n')
        event_data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                event_data[key.strip()] = value.strip()
        
        event_type = event_data.get('Event', '')
        
        # Log all events for debugging
        if event_type:
            logger.debug(f"Event: {event_type}")
        
        # Track call state
        if event_type == 'VarSet':
            channel = event_data.get('Channel', '')
            if 'DTMF' in event_data.get('Variable', ''):
                logger.info(f"DTMF Hint: {event_data}")
        
        # *** CRITICAL: Listen for DTMF events ***
        if event_type == 'DTMFEnd':
            digit = event_data.get('Digit', '')
            channel = event_data.get('Channel', '')
            logger.info(f"[DTMF DETECTED] Digit: {digit} on channel {channel}")
            
            if digit == '9':
                logger.warning("DTMF 9 DETECTED - TRIGGERING DOOR UNLOCK!")
                self.dtmf_digit = digit
                self.dtmf_detected.set()
        
        # Track NewChannel to identify the outbound call channel
        elif event_type == 'NewChannel':
            channel = event_data.get('Channel', '')
            if '27878096471' in channel or 'PJSIP' in channel:
                logger.info(f"New channel created: {channel}")
                self.channel_name = channel
        
        # Track call answered
        elif event_type == 'VarSet' and 'ANSWERING' in event_data.get('Variable', ''):
            logger.info("Call answered!")
            self.call_active = True
        
        # Track hangup
        elif event_type == 'Hangup':
            channel = event_data.get('Channel', '')
            cause = event_data.get('Cause', '')
            logger.info(f"Call hung up: {channel} (Cause: {cause})")
            self.call_active = False
    
    def originate_call(self, phone_number, trunk='27878096471', timeout=30):
        """
        Originate a call through Asterisk trunk
        
        Args:
            phone_number: Phone number to call (e.g., '+27656231093')
            trunk: SIP trunk endpoint (e.g., '27878096471')
            timeout: How long to wait for DTMF 9 (seconds)
        
        Returns:
            dict with call result
        """
        if not self.connected:
            logger.error("Not connected to AMI")
            return {'success': False, 'error': 'Not connected'}
        
        try:
            # Format phone number for AMI
            if phone_number.startswith('+'):
                phone_number = phone_number[1:]  # Remove + prefix
            
            action_id = self._get_action_id()
            
            logger.info(f"Originating call to {phone_number} via trunk {trunk}")
            
            # Try direct SIP URI approach (bypass registration, authenticate per-call)
            # Format: PJSIP/number@server:port (will use outbound_auth from endpoint)
            originate_cmd = (
                f"Action: Originate\r\n"
                f"ActionID: {action_id}\r\n"
                f"Channel: PJSIP/{phone_number}@jhb1.vphone.co.za\r\n"
                f"Context: from-internal\r\n"
                f"Exten: {phone_number}\r\n"
                f"Priority: 1\r\n"
                f"CallerID: AccessControl<{trunk}>\r\n"
                f"Variable: SIPFROMUSER={trunk}\r\n"
                f"Timeout: 300000\r\n"  # 5 minutes timeout at Asterisk level
                f"\r\n"
            )
            
            self.socket.send(originate_cmd.encode('utf-8'))
            self.call_active = True
            self.dtmf_detected.clear()
            self.dtmf_digit = None
            
            logger.info(f"Call initiated. Waiting up to {timeout}s for response or DTMF 9...")
            
            # Wait for DTMF 9 or timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.dtmf_detected.wait(timeout=1):
                    logger.info(f"DTMF 9 received! Call duration: {time.time() - start_time:.1f}s")
                    return {
                        'success': True,
                        'dtmf': self.dtmf_digit,
                        'duration': time.time() - start_time,
                        'message': 'Call answered and DTMF 9 detected'
                    }
                
                remaining = timeout - (time.time() - start_time)
                if remaining > 0:
                    logger.debug(f"Waiting for DTMF 9... {remaining:.1f}s remaining")
            
            logger.warning(f"Timeout waiting for DTMF 9 (waited {timeout}s)")
            return {
                'success': False,
                'error': f'Timeout after {timeout}s',
                'call_initiated': True,
                'dtmf_received': False
            }
            
        except Exception as e:
            logger.error(f"Failed to originate call: {e}")
            return {'success': False, 'error': str(e)}
    
    def hangup_call(self, channel=None):
        """Hang up the current call"""
        if not self.connected:
            return False
        
        try:
            action_id = self._get_action_id()
            
            # If no channel specified, hang up all PJSIP channels
            if not channel:
                channel = 'PJSIP/*'
            
            logger.info(f"Hanging up call on channel: {channel}")
            
            hangup_cmd = (
                f"Action: Hangup\r\n"
                f"ActionID: {action_id}\r\n"
                f"Channel: {channel}\r\n"
                f"\r\n"
            )
            
            self.socket.send(hangup_cmd.encode('utf-8'))
            self.call_active = False
            return True
            
        except Exception as e:
            logger.error(f"Failed to hangup call: {e}")
            return False


def make_call(phone_number, vps_host='37.27.196.132', ami_username='4a3516b0de1e6ea7248ff8f37113c175', 
              ami_secret='78281333b287e3a14a3dc662da6296f7', trunk='27878096471', timeout=30):
    """
    Main function to initiate a call and wait for DTMF 9
    
    Args:
        phone_number: Phone number to call
        vps_host: Asterisk VPS IP/hostname
        ami_username: AMI manager username
        ami_secret: AMI manager secret
        trunk: SIP trunk endpoint
        timeout: Timeout in seconds
    
    Returns:
        dict with call results
    """
    ami = AsteriskAMI(vps_host, 5038, ami_username, ami_secret)
    
    try:
        if not ami.connect():
            return {'success': False, 'error': 'Failed to connect to Asterisk AMI'}
        
        time.sleep(0.5)  # Let listener thread start
        
        result = ami.originate_call(phone_number, trunk=trunk, timeout=timeout)
        
        # Hang up if still connected
        if result.get('success') or result.get('call_initiated'):
            time.sleep(1)
            ami.hangup_call()
        
        return result
        
    finally:
        ami.disconnect()


if __name__ == '__main__':
    import os
    
    # Get credentials from environment or use hardcoded defaults
    vps_host = os.getenv('ASTERISK_HOST', '37.27.196.132')
    ami_user = os.getenv('ASTERISK_AMI_USER', '4a3516b0de1e6ea7248ff8f37113c175')
    ami_secret = os.getenv('ASTERISK_AMI_SECRET', '78281333b287e3a14a3dc662da6296f7')
    trunk = os.getenv('ASTERISK_TRUNK', 'vphone-trunk')
    
    if not ami_secret:
        logger.error("ASTERISK_AMI_SECRET not set in environment or defaults")
        sys.exit(1)
    
    # Test call to South African number
    phone = '+27656231093'
    
    logger.info("=" * 60)
    logger.info(f"Making call to {phone}")
    logger.info(f"VPS: {vps_host}, Trunk: {trunk}")
    logger.info("=" * 60)
    
    result = make_call(
        phone_number=phone,
        vps_host=vps_host,
        ami_username=ami_user,
        ami_secret=ami_secret,
        trunk=trunk,
        timeout=60  # Wait up to 60 seconds for DTMF 9
    )
    
    logger.info("=" * 60)
    logger.info(f"Result: {result}")
    logger.info("=" * 60)
    
    sys.exit(0 if result.get('success') else 1)
