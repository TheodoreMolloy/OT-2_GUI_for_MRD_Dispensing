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
