import sys
import os
import time
import requests
import socket
import threading

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel,
    QSlider, QButtonGroup, QRadioButton, QHBoxLayout, QStackedWidget, QTextEdit,
    QSizePolicy, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer

# --------------------------- Robot Communication Functions ---------------------------

# Robot connection details
robot_ip = "169.254.110.39"  # IP address of the Opentrons robot
base_url = f"http://{robot_ip}:31950"  # Base URL for API endpoints - should be same for all OT-2s, 31950 is API socket
headers = {'opentrons-version': '2'}  # Required header for API requests
timeout = 30  # Timeout for API requests in seconds

def ping_robot(ip, timeout=3):
    """Check if robot is reachable at network level"""
    try:
        # Try to connect to the API port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, 31950))
        sock.close()
        return result == 0
    except Exception:
        return False

def initialize_robot_services(robot_ip):
    """Make the same initialisation calls as the OT-2 app"""
    initialisation_calls = [
        # System status and time sync
        ("GET", "/system/time"),
        ("GET", "/health"),
        
        # Robot settings and calibration data
        ("GET", "/robot/settings"),
        ("GET", "/calibration/status"),
        
        # Deck and pipette information
        ("GET", "/robot/positions/change_pipette"),
        ("GET", "/motors/engaged"),
        
        # Session initialisation
        ("GET", "/sessions"),
        ("GET", "/protocols"),
        ("GET", "/runs"),
    ]
    
    success_count = 0
    # Run each initialisation call
    for method, endpoint in initialisation_calls:
        try:
            # Allow for changes in initialisation calls
            if method == "GET":
                response = requests.get(f"{base_url}{endpoint}", 
                                      headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(f"{base_url}{endpoint}", 
                                       headers=headers, timeout=10)
            else:
                print(f"Invalid method {method} during intialisation.")
            
            # After http connection works, turn on lights


            # In HTTP, any status code above 399 is a client or server error
            if response.status_code < 400:
                success_count += 1
                print(f"✓ {endpoint}: OK")
            else:
                print(f"⚠ {endpoint}: {response.status_code}")
                
        except Exception as e:
            print(f"✗ {endpoint}: {str(e)}")
    
    return success_count >= len(initialisation_calls) // 2  # At least half successful

def startup_robot_connection():
    """Complete startup sequence"""
    print("Starting robot connection sequence...")
    # Each 3 functions returned a comparison (bool) to see if the signal is good enough

    # Step 1: Basic network connectivity
    if not ping_robot(robot_ip):
        return False, "Robot not reachable on network"
    
    # Step 2: Initialize services
    if initialize_robot_services(robot_ip):
        time.sleep(3)  # Allow services to stabilize
        
        # Step 3: Final connection test
        if check_connection():
            
            return True, "Robot initialized successfully"
    
    return False, "Robot services failed to initialize"

def check_connection_with_startup():
    """Enhanced connection check with startup procedures"""
    max_attempts = 8
    base_delay = 2
    
    for attempt in range(max_attempts):
        print(f"Connection attempt {attempt + 1}/{max_attempts}")
        
        # Try basic connection first
        if check_connection():
            return True, f"Connected on attempt {attempt + 1}"
        
        # If failed, try wake-up procedures
        success, message = startup_robot_connection()
        if success:
            return True, message
        
        # Exponential backoff
        delay = min(base_delay * (2 ** (attempt // 2)), 15)  # Cap at 15 seconds
        print(f"Waiting {delay} seconds before retry...")
        time.sleep(delay)
    
    return False, "Failed to connect after all attempts"

def check_connection():
    """Check if the robot is reachable via HTTP."""
    try:
        # Send GET request to /health endpoint to verify robot connection
        response = requests.get(f"{base_url}/health", headers=headers, timeout=5)
        # Raise exception for bad status codes (4xx, 5xx)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

def lights_on():
    headers = {
        "Content-Type": "application/json",
        "opentrons-version": "2"
    }
    try:
        response = requests.post(f"{base_url}/robot/lights", headers=headers,json={"on":True},timeout=5)
        response.raise_for_status()
        print("Lights now on")
    except Exception as e:
        print(f"Lights on failed: {e}")

def upload_protocol(filepath):
    """Send a protocol file to the robot."""
    # First verify the protocol file exists
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Protocol not found at {filepath}")
    
    # Open the file in binary mode and POST it to the protocols endpoint
    with open(filepath, 'rb') as f:
        files = {'files': f}  # Prepare file for multipart upload
        # Send POST request with protocol file
        response = requests.post(f"{base_url}/protocols", files=files, headers=headers, timeout=timeout)
    
    # Check for errors in the response
    response.raise_for_status()
    # Return the protocol ID from the response JSON
    return response.json()['data']['id']

def create_run(protocol_id):
    """Create a new run instance for a given protocol."""
    # Prepare the request payload
    data = {
        "data": {
            "protocolId": protocol_id,  # The ID of the uploaded protocol
            "labwareOffsets": [],  # Empty list for default labware positions
            "runTimeParameters": []  # No runtime parameters needed
        }
    }
    # POST the run configuration to create a new run
    response = requests.post(f"{base_url}/runs", json=data, headers=headers, timeout=timeout)
    response.raise_for_status()
    # Return the run ID from the response
    return response.json()['data']['id']

def start_run_automatically(run_id):
    """Start the robot run automatically."""
    # Prepare action payload to start the run
    data = {"data": {"actionType": "play"}}  # "play" action starts execution
    # POST the action to the run's actions endpoint
    response = requests.post(f"{base_url}/runs/{run_id}/actions", json=data, headers=headers, timeout=timeout)
    response.raise_for_status()

def pause_run(run_id):
    """Pause the robot run."""
    # Prepare action payload to pause the run
    data = {"data": {"actionType": "pause"}}  # "pause" action pauses execution
    # POST the pause action to the run's actions endpoint
    response = requests.post(f"{base_url}/runs/{run_id}/actions", json=data, headers=headers, timeout=timeout)
    response.raise_for_status()

def resume_run(run_id):
    """Resume the robot run."""
    # Prepare action payload to resume the run
    data = {"data": {"actionType": "play"}}  # "play" also resumes execution
    # POST the resume action to the run's actions endpoint
    response = requests.post(f"{base_url}/runs/{run_id}/actions", json=data, headers=headers, timeout=timeout)
    response.raise_for_status()

def monitor_run_enhanced(run_id, update_callback, pause_flag, stop_flag):
    """Enhanced monitoring with progress details and stop checking"""
    while not stop_flag.get('stop_requested', False):
        try:
            response = requests.get(f"{base_url}/runs/{run_id}", headers=headers, timeout=5)
            response.raise_for_status()
            
            data = response.json()['data']
            status = data['status']
            
            # Get more detailed info
            current_command = data.get('currentCommand', {})
            if current_command:
                cmd_type = current_command.get('commandType', 'Unknown')
                update_callback(f"Status: {status} - {cmd_type}")
            else:
                update_callback(f"Status: {status}")
            
            # Check for errors
            if 'errors' in data and data['errors']:
                error_msg = data['errors'][0].get('detail', 'Unknown error')
                update_callback(f"Error detected: {error_msg}")
            
            if status in ['succeeded', 'failed', 'stopped']:
                break
                
        except Exception as e:
            if not stop_flag.get('stop_requested', False):
                update_callback(f"Monitoring error: {e}")
            time.sleep(2)
            continue
            
        # Check stop request while paused
        while pause_flag['paused'] and not stop_flag.get('stop_requested', False):
            update_callback("Run paused...")
            time.sleep(1)
            
        # Short sleep but check stop frequently
        for _ in range(30):  # 3 seconds total, but check every 0.1s
            if stop_flag.get('stop_requested', False):
                return
            time.sleep(0.1)

def stop_run(run_id):
    """Stop run with shorter timeout"""
    try:
        stop_data = {"data": {"actionType": "stop"}}
        stop_response = requests.post(f"{base_url}/runs/{run_id}/actions", 
                                    json=stop_data, headers=headers, 
                                    timeout=5)  # Shorter timeout
        stop_response.raise_for_status()
        return True
    except requests.exceptions.Timeout:
        print("Stop request timed out")
        return False
    except Exception as e:
        print(f"Stop request failed: {e}")
        return False

# --------------------------- Worker Threads ---------------------------

class ConnectionWorker(QThread): # QThread is a class made to run in thread with others - worker classes inherit this class
    """Worker thread for connection checking"""
    finished_signal = Signal(bool, str)
    progress_signal = Signal(str)
    
    def run(self):
        # Call try connection with startup
        try:
            self.progress_signal.emit("Checking network connectivity...")
            success, message = check_connection_with_startup()
            self.finished_signal.emit(success, message)
        except Exception as e:
            self.finished_signal.emit(False, f"Connection error: {str(e)}")
        # Turn on lights
        lights_on()

class RobotWorker(QThread):
    """
    Background thread to handle robot operations without freezing GUI.
    
    Uses PySide6's Signal system to communicate with the main thread:
    - update_signal: Sends status updates
    - finished_signal: Signals completion (success/failure)
    """
    update_signal = Signal(str)  # Signal for status updates
    finished_signal = Signal(bool, str)  # Signal for completion (success, message)

    def __init__(self, vol, racks):
        super().__init__()
        self.vol = vol  # Volume to dispense
        self.racks = racks  # Number of racks to use
        self._pause_flag = {'paused': False}  # Shared pause state (dict for pass-by-reference)
        self._stop_flag = {'stop_requested': False}  # Flag for stopping the thread
        self.run_id = None  # Will store the current run ID

    def run(self):
        """Main thread execution method - handles the entire protocol workflow."""
        try:
            # Step 1: Check robot connection
            self.update_signal.emit("Checking robot connection...")
            if not check_connection():
                self.finished_signal.emit(False, "Could not connect to robot.")
                return

            # Step 2: Determine which protocol to use based on settings
            self.update_signal.emit(f"Setting up for {self.racks} rack(s) at {self.vol} ml...")
            

            # !!!! IF CHANGING PROTOCOL PATH THIS IS WHERE !!!!!
            if self.vol == 4.5:
                if self.racks == 1:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol4.5ml1Racks.py"
                elif self.racks == 2:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol4.5ml2Racks.py"
                elif self.racks == 3:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol4.5ml3Racks.py"
                elif self.racks == 4:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol4.5ml4Racks.py"
                else:
                    self.finished_signal.emit(False, f"No protocol for {self.racks} racks")
                    return
            elif self.vol == 9.0:
                if self.racks == 1:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol9.0ml1Racks.py"
                elif self.racks == 2:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol9.0ml2Racks.py"
                elif self.racks == 3:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol9.0ml3Racks.py"
                elif self.racks == 4:
                    path = r"C:\Users\melbec\Desktop\OT-2 App\dispenseProtocol9.0ml4Racks.py"
                else:
                    self.finished_signal.emit(False, f"No protocol for {self.racks} racks")
                    return
            else:
                self.finished_signal.emit(False, f"No protocol available for {self.vol} ml")
                return

            # Check if stop was requested
            if self._stop_flag['stop_requested']:
                self.finished_signal.emit(False, "Run was stopped by user.")
                return

            # Step 3: Upload the protocol file to the robot
            self.update_signal.emit("Uploading protocol...")
            protocol_id = upload_protocol(path)

            if self._stop_flag['stop_requested']:
                self.finished_signal.emit(False, "Run was stopped by user.")
                return

            # Step 4: Create a run instance for the protocol
            self.update_signal.emit("Creating run...")
            self.run_id = create_run(protocol_id)

            if self._stop_flag['stop_requested']:
                self.finished_signal.emit(False, "Run was stopped by user.")
                return

            # Step 5: Start the run automatically
            self.update_signal.emit("Starting run...")
            start_run_automatically(self.run_id)

            if self._stop_flag['stop_requested']:
                self.finished_signal.emit(False, "Run was stopped by user.")
                return

            # Step 6: Monitor the run until completion
            self.update_signal.emit("Monitoring run...")
            monitor_run_enhanced(self.run_id, self.update_signal.emit, self._pause_flag, self._stop_flag)

            # If we get here and weren't stopped, run completed successfully
            if not self._stop_flag['stop_requested']:
                self.finished_signal.emit(True, "Run completed successfully.")
            else:
                self.finished_signal.emit(False, "Run was stopped by user.")

        except Exception as e:
            # Handle any errors that occur during execution
            self.finished_signal.emit(False, f"Error: {str(e)}")

    def pause(self):
        """Pause the run by calling API and setting flag."""
        if self.run_id is not None:
            try:
                pause_run(self.run_id)  # Call API to pause
                self._pause_flag['paused'] = True  # Set pause flag
                self.update_signal.emit("Pause command sent.")
            except Exception as e:
                self.update_signal.emit(f"Error pausing: {e}")

    def resume(self):
        """Resume the run by calling API and clearing flag."""
        if self.run_id is not None:
            try:
                resume_run(self.run_id)  # Call API to resume
                self._pause_flag['paused'] = False  # Clear pause flag
                self.update_signal.emit("Resume command sent.")
            except Exception as e:
                self.update_signal.emit(f"Error resuming: {e}")

    def stop(self):
        """Stop the thread gracefully"""
        self._stop_flag['stop_requested'] = True
        
        if self.run_id is not None:
            # Do API call in a separate thread to avoid blocking
            def send_stop():
                try:
                    stop_run(self.run_id)
                    self.update_signal.emit("Stop command sent to robot")
                except Exception as e:
                    self.update_signal.emit(f"Error sending stop: {e}")
            
            stop_thread = threading.Thread(target=send_stop, daemon=True)
            stop_thread.start()

# --------------------------- GUI Main Window ---------------------------

class MainWindow(QMainWindow):
    """
    Main application window with multiple pages guiding configuration and run.
    """
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MRD Dispense O'Matic")
        self.setFixedSize(820, 620)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #fafafa;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            QLabel#titleLabel {
                font-size: 48px;
                font-weight: 700;
                color: #2c3e50;
            }
            QLabel#pageTitle {
                font-size: 36px;
                font-weight: 600;
                color: #34495e;
            }
            QPushButton {
                padding: 12px 24px;
                font-size: 18px;
                border-radius: 8px;
                background-color: #2980b9;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:pressed {
                background-color: #1c5980;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            QTextEdit {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 14px;
                color: #2c3e50;
            }
            QSlider::handle:horizontal {
                background: #2980b9;
                border-radius: 8px;
                width: 18px;
                margin: -4px 0;
            }
            QSlider::groove:horizontal {
                height: 12px;
                background: #d0d7de;
                border-radius: 6px;
            }
            QRadioButton {
                font-size: 16px;
                padding: 4px 12px;
            }
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)

        self.selected_volume = 4.5
        self.selected_racks = 1

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.create_first_page()
        self.create_second_page()
        self.create_third_page()
        self.create_fourth_page()
        self.create_fifth_page()
        self.create_sixth_page()

        self.stacked_widget.setCurrentIndex(0)
        self.worker_thread = None
        self.connection_worker = None
        self.paused = False

        # Start connection check automatically after a short delay
        QTimer.singleShot(1000, self.check_robot_connection)

    def create_first_page(self):
        """Start screen with connection status"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(60, 80, 60, 80)

        title = QLabel("MRD Dispense O'Matic")
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)

        # Connection status
        self.connection_status = QLabel("Checking robot connection...")
        self.connection_status.setAlignment(Qt.AlignCenter)
        self.connection_status.setStyleSheet("font-size: 16px; color: #f39c12;")

        # Progress bar for connection attempts
        self.connection_progress = QProgressBar()
        self.connection_progress.setVisible(False)
        self.connection_progress.setRange(0, 0)  # Indeterminate progress

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(self.connection_status)
        layout.addWidget(self.connection_progress)
        layout.addStretch()

        self.start_btn = QPushButton("Start Configuration")
        self.start_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.start_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.start_btn.setEnabled(False)  # Disabled until connected
        layout.addWidget(self.start_btn, alignment=Qt.AlignCenter)
        
        # Add manual connection button
        self.connect_btn = QPushButton("Retry Connection")
        self.connect_btn.clicked.connect(self.check_robot_connection)
        layout.addWidget(self.connect_btn, alignment=Qt.AlignCenter)
        
        layout.addStretch()

        # Make append to stacked_widget so it can cycle through pages
        self.stacked_widget.addWidget(page)

    def create_second_page(self):
        """Volume and rack number selection page"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(20)

        title = QLabel("Configuration Settings")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Slider label and slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 3)
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setFixedHeight(50)
        self.slider.setFixedWidth(600)
        self.slider.setStyleSheet("QSlider::handle { background-color: #3498db; border-radius: 10px; height: 40px; width: 40px; }")
        self.slider.valueChanged.connect(self.set_rack_count)
        layout.addWidget(self.slider, alignment=Qt.AlignCenter)

        # Labels Under Slider - Aligned Centrally Below Slider Positions
        rack_labels_layout = QHBoxLayout()
        rack_labels = ["1 Rack", "2 Racks", "3 Racks", "4 Racks"]
        for rack in rack_labels:
            label = QLabel(rack)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedWidth(150)
            label.setStyleSheet("font-size: 18px;")
            rack_labels_layout.addWidget(label)
        layout.addLayout(rack_labels_layout)

        layout.addStretch()

        # Volume selection radio buttons
        volume_label = QLabel("Select Dispense Volume")
        volume_label.setAlignment(Qt.AlignCenter)
        volume_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(volume_label)

        self.volume_group = QButtonGroup()
        volume_buttons_layout = QHBoxLayout()
        volume_buttons_layout.setAlignment(Qt.AlignCenter)
        volume_buttons_layout.addStretch(1)
        for idx, vol in enumerate([4.5, 9.0]):
            btn = QRadioButton(f"{vol} ml")
            btn.setStyleSheet("font-size: 20px;")
            btn.toggled.connect(lambda checked, v=vol: self.set_volume(v) if checked else None)
            if vol == self.selected_volume:
                btn.setChecked(True)
            self.volume_group.addButton(btn, idx)
            volume_buttons_layout.addWidget(btn)
            volume_buttons_layout.addStretch(1)
        layout.addLayout(volume_buttons_layout)

        layout.addStretch()

        # Navigation buttons
        nav = QHBoxLayout()
        back = QPushButton("Back")
        next_btn = QPushButton("Next")
        back.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        nav.addWidget(back)
        nav.addStretch()
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self.stacked_widget.addWidget(page)

    def create_third_page(self):
        """Rack placement check page"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        msg = QLabel("Ensure racks are correctly placed in the robot deck.")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 18px; color: #34495e;")
        layout.addWidget(msg)

        nav = QHBoxLayout()
        back = QPushButton("Back")
        next_btn = QPushButton("Next")
        back.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        next_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        nav.addWidget(back)
        nav.addStretch()
        nav.addWidget(next_btn)
        layout.addLayout(nav)

        self.stacked_widget.addWidget(page)

    def create_fourth_page(self):
        """Confirmation page before run"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        self.confirm_label = QLabel(f"Please confirm your selection:\n\n"
                               f"Volume: {self.selected_volume} ml\n"
                               f"Number of Racks: {self.selected_racks}")
        self.confirm_label.setAlignment(Qt.AlignCenter)
        self.confirm_label.setStyleSheet("font-size: 20px; color: #2c3e50;")
        layout.addWidget(self.confirm_label)

        nav = QHBoxLayout()
        back = QPushButton("Back")
        run_btn = QPushButton("Run Protocol")
        back.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        run_btn.clicked.connect(lambda: self.run_protocol(self.selected_volume, self.selected_racks))
        nav.addWidget(back)
        nav.addStretch()
        nav.addWidget(run_btn)
        layout.addLayout(nav)

        self.stacked_widget.addWidget(page)

    def create_fifth_page(self):
        """Run monitor page with log, pause/resume and stop buttons"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.status_label = QLabel("Running Protocol...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 22px; font-weight: 600; color: #2980b9;")
        layout.addWidget(self.status_label)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("background-color: #ecf0f1;")
        self.log_display.setMinimumHeight(280)
        layout.addWidget(self.log_display)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Pause/Resume button
        self.pause_resume_btn = QPushButton("Pause")
        self.pause_resume_btn.setFixedWidth(120)
        self.pause_resume_btn.clicked.connect(self.toggle_pause_resume)
        button_layout.addWidget(self.pause_resume_btn)

        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedWidth(120)
        self.stop_btn.clicked.connect(self.stop_protocol)
        button_layout.addWidget(self.stop_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.stacked_widget.addWidget(page)

    def create_sixth_page(self):
        """Final page after run completion"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 60, 40, 60)
        layout.setSpacing(30)

        done_label = QLabel("🎉 All done! 🎉")
        done_label.setAlignment(Qt.AlignCenter)
        done_label.setStyleSheet("font-size: 32px; font-weight: 700; color: #27ae60;")
        layout.addWidget(done_label)

        finish_btn = QPushButton("Return Home")
        finish_btn.setFixedSize(180, 50)
        finish_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        layout.addWidget(finish_btn, alignment=Qt.AlignCenter)

        self.stacked_widget.addWidget(page)

    def check_robot_connection(self):
        """Check robot connection in background thread"""
        self.connect_btn.setEnabled(False)
        self.connection_status.setText("Connecting to robot...")
        self.connection_progress.setVisible(True)
        
        # Use a separate thread for connection checking
        self.connection_worker = ConnectionWorker()
        self.connection_worker.finished_signal.connect(self.on_connection_checked)
        self.connection_worker.progress_signal.connect(self.on_connection_progress)
        self.connection_worker.start()

    def on_connection_progress(self, message):
        """Handle connection progress updates"""
        self.connection_status.setText(message)

    def on_connection_checked(self, success, message):
        """Handle connection check result"""
        self.connection_progress.setVisible(False)
        
        if success:
            self.connection_status.setText("✓ Robot connected and ready")
            self.connection_status.setStyleSheet("font-size: 16px; color: #27ae60;")
            self.start_btn.setEnabled(True)
            self.connect_btn.setText("Recheck Connection")
        else:
            self.connection_status.setText(f"✗ Connection failed: {message}")
            self.connection_status.setStyleSheet("font-size: 16px; color: #e74c3c;")
            self.start_btn.setEnabled(False)
            self.connect_btn.setText("Retry Connection")
        
        self.connect_btn.setEnabled(True)

    def set_volume(self, value):
        """Set the selected volume"""
        self.selected_volume = value
        # Update page 4 text
        self.confirm_label.setText(
            f"Please confirm your selection:\n\n"
            f"Volume: {self.selected_volume} ml\n"
            f"Number of Racks: {self.selected_racks}"
            )

    def set_rack_count(self, value):
        """Set the number of racks (slider 0-(max_racks-1) mapped to 1-max_racks)"""
        self.selected_racks = value + 1
        # Update page 4 text
        self.confirm_label.setText(
            f"Please confirm your selection:\n\n"
            f"Volume: {self.selected_volume} ml\n"
            f"Number of Racks: {self.selected_racks}"
            )

    def run_protocol(self, vol, racks):
        """Start the robot protocol thread"""
        self.log_display.clear()
        self.status_label.setText("Starting protocol...")
        self.pause_resume_btn.setEnabled(True)
        self.pause_resume_btn.setText("Pause")
        self.paused = False

        self.worker_thread = RobotWorker(vol, racks)
        self.worker_thread.update_signal.connect(self.append_log)
        self.worker_thread.finished_signal.connect(self.on_protocol_finished)
        self.worker_thread.start()

        self.stacked_widget.setCurrentIndex(4)

    def append_log(self, message):
        """Append a new message to the log display"""
        self.log_display.append(message)
        self.status_label.setText(message)

    def on_protocol_finished(self, success, message):
        """Handle end of protocol run"""
        self.append_log(message)
        self.pause_resume_btn.setEnabled(False)
        if success:
            self.status_label.setText("Protocol completed successfully.")
            self.stacked_widget.setCurrentIndex(5)
        else:
            self.status_label.setText("Protocol failed.")
            QMessageBox.critical(self, "Run Error", message)
            self.stacked_widget.setCurrentIndex(0)  # Back to beginning to reset connection.

    def toggle_pause_resume(self):
        """Toggle pause and resume of the robot run"""
        if not self.worker_thread:
            return
        if not self.paused:
            self.worker_thread.pause()
            self.pause_resume_btn.setText("Resume")
            self.paused = True
        else:
            self.worker_thread.resume()
            self.pause_resume_btn.setText("Pause")
            self.paused = False

    def stop_protocol(self):
        """Stop the running protocol without blocking GUI"""
        # Disable buttons immediately
        self.pause_resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        
        if self.worker_thread:
            # Set stop flag and let thread finish naturally
            self.worker_thread.stop()
            
            # Connect to finished signal to handle cleanup
            self.worker_thread.finished.connect(self.on_stop_completed)
            
            # Update status immediately
            self.append_log("Stopping protocol...")
            self.status_label.setText("Stopping...")

    def on_stop_completed(self):
        """Called when worker thread actually finishes"""
        self.worker_thread = None
        # don't want it to skip to end because error message will sort that.
        # self.stacked_widget.setCurrentIndex(5)
        QMessageBox.information(self, "Stopped", 
                            "Protocol run has been stopped.\n"
                            "Please wait for robot to settle if it's still moving.")
        self.pause_resume_btn.setText("Pause")
        self.paused = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

