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
