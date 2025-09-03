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
