try:
    from PySide6 import QtWidgets, QtGui, QtCharts, QtCore
except ImportError as e:  # pragma: no cover - only runs without PySide6
    raise ImportError(
        "PySide6 or underlying Qt libraries are missing. "
        "Install PySide6 via 'pip install pyside6' and ensure Qt/\n"
        "libEGL packages are installed (e.g. on Ubuntu: 'sudo apt-get install libegl1')."
    ) from e

import pandas as pd, qasync, asyncio


class ProgressChart(QtWidgets.QWidget):
    """Mini‑sparkline for a single KPI."""
    
    def __init__(self, title: str):
        super().__init__()
        self.series = QtCharts.QLineSeries()
        chart = QtCharts.QChart(); chart.addSeries(self.series)
        chart.legend().hide(); chart.setTitle(title)
        axis_x = QtCharts.QValueAxis(); axis_y = QtCharts.QValueAxis()
        chart.setAxisX(axis_x, self.series); chart.setAxisY(axis_y, self.series)
        vbox = QtWidgets.QVBoxLayout(self); vbox.addWidget(QtCharts.QChartView(chart))
        self.setToolTip(f"{title} sparkline: recent trend")
        
    def update_points(self, data: list[float]):
        self.series.clear()
        for i, val in enumerate(data): self.series.append(i, val)


class PlanStepWidget(QtWidgets.QWidget):
    def __init__(self, step_num: int, description: str, play_callback=None):
        super().__init__()
        self.step_num = step_num
        self.checkbox = QtWidgets.QCheckBox(f"Step {step_num}: {description}")
        self.play_btn = QtWidgets.QPushButton("🔊 Play Reference")
        if play_callback:
            self.play_btn.clicked.connect(play_callback)
        hbox = QtWidgets.QHBoxLayout(self)
        hbox.addWidget(self.checkbox)
        hbox.addWidget(self.play_btn)


class OnboardingDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Welcome to VoiceCoach!")
        label = QtWidgets.QLabel(
            """
            Welcome!

            This app helps you improve your articulation and track your progress.


            <ul>
            Follow the plan steps and use the Play Reference button to hear correct pronunciation.
            Check your progress in the dashboard above.
            Start a session to begin practicing!
            </ul>
            """
        )
        label.setWordWrap(True)
        btn = QtWidgets.QPushButton("Get Started")
        btn.clicked.connect(self.accept)
        vbox = QtWidgets.QVBoxLayout(self)
        vbox.addWidget(label)
        vbox.addWidget(btn)


class CoachWindow(QtWidgets.QWidget):
    # Signal definitions
    session_start = QtCore.Signal()
    session_end = QtCore.Signal()
    step_toggled = QtCore.Signal(int, bool)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceCoach")
        self.setMinimumWidth(600)

        # Main layout
        vbox = QtWidgets.QVBoxLayout(self)
        
        # Dashboard section
        dashboard_group = QtWidgets.QGroupBox("Progress Dashboard")
        dashboard_layout = QtWidgets.QVBoxLayout(dashboard_group)
        
        # Summary row
        summary_layout = QtWidgets.QHBoxLayout()
        self.cefr_label = QtWidgets.QLabel("Level: B2")
        self.last_score_label = QtWidgets.QLabel("Last Score: 85.0%")
        self.streak_label = QtWidgets.QLabel("Streak: 7")
        for label in [self.cefr_label, self.last_score_label, self.streak_label]:
            label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
            summary_layout.addWidget(label)
        dashboard_layout.addLayout(summary_layout)
        
        # KPIs row
        kpis_layout = QtWidgets.QHBoxLayout()
        self.wer = QtWidgets.QLabel("WER: 12.5%")
        self.acc = QtWidgets.QLabel("Acc: 87.5%")
        for label in [self.wer, self.acc]:
            label.setStyleSheet("font-size: 14px; padding: 2px 8px; color: #007ACC;")
            kpis_layout.addWidget(label)
        dashboard_layout.addLayout(kpis_layout)
        
        # Charts row
        charts_layout = QtWidgets.QHBoxLayout()
        self.acc_chart = ProgressChart("Accuracy")
        self.wer_chart = ProgressChart("WER")
        for chart in [self.acc_chart, self.wer_chart]:
            chart.setMaximumHeight(100)
            charts_layout.addWidget(chart)
        dashboard_layout.addLayout(charts_layout)
        
        # Trends row
        trends_layout = QtWidgets.QHBoxLayout()
        self.ma_label = QtWidgets.QLabel("7d MA: 85.2%")
        self.mom_label = QtWidgets.QLabel("MoM: +3.1%")
        for label in [self.ma_label, self.mom_label]:
            label.setStyleSheet("font-size: 12px; color: #666;")
            trends_layout.addWidget(label)
        dashboard_layout.addLayout(trends_layout)
        
        vbox.addWidget(dashboard_group)
        
        # Plan section
        plan_group = QtWidgets.QGroupBox("Training Plan")
        self.plan_steps_box = QtWidgets.QVBoxLayout(plan_group)
        
        # Plan header
        plan_header = QtWidgets.QHBoxLayout()
        plan_header.addWidget(QtWidgets.QLabel("Current Plan Progress:"))
        self.plan_progress = QtWidgets.QProgressBar()
        self.plan_progress.setMaximum(1)
        plan_header.addWidget(self.plan_progress)
        self.plan_steps_box.addLayout(plan_header)
        
        # Plan placeholder
        self.plan_steps_box.addWidget(QtWidgets.QLabel("No plan loaded yet."))
        vbox.addWidget(plan_group)
        
        # Control buttons section
        controls_group = QtWidgets.QGroupBox("Session Controls")
        controls_layout = QtWidgets.QHBoxLayout(controls_group)
        
        self.start_btn = QtWidgets.QPushButton("▶ Start Session")
        self.end_btn = QtWidgets.QPushButton("⏹ End Session")
        self.status_label = QtWidgets.QLabel("Ready to start")
        
        self.start_btn.clicked.connect(self.on_start_session)
        self.end_btn.clicked.connect(self.on_end_session)
        
        for widget in [self.start_btn, self.end_btn, self.status_label]:
            controls_layout.addWidget(widget)
        
        vbox.addWidget(controls_group)
        
        # Show onboarding dialog
        QtCore.QTimer.singleShot(500, self.show_onboarding)
    
    def show_onboarding(self):
        dialog = OnboardingDialog()
        dialog.exec()
    
    def set_listening_state(self, is_listening):
        """Toggle buttons and status text based on listening state."""
        if is_listening:
            self.start_btn.setEnabled(False)
            self.end_btn.setEnabled(True)
            self.status_label.setText("🎤 Session active - Listening...")
            self.status_label.setStyleSheet("color: #007ACC; font-weight: bold;")
        else:
            self.start_btn.setEnabled(True)
            self.end_btn.setEnabled(False)
            self.status_label.setText("Ready to start")
            self.status_label.setStyleSheet("color: #333;")
    
    def update_kpi(self, metric: str, value: float):
        if metric == "wer":
            color = "#DC3545" if value > 0.20 else "#FFC107" if value > 0.10 else "#28A745"
            self.wer.setText(f"WER: {value:.1%}")
            self.wer.setStyleSheet(f"font-size: 14px; padding: 2px 8px; color: {color};")
        elif metric == "acc":
            color = "#DC3545" if value < 0.70 else "#FFC107" if value < 0.85 else "#28A745"
            self.acc.setText(f"Acc: {value:.1%}")
            self.acc.setStyleSheet(f"font-size: 14px; padding: 2px 8px; color: {color};")
    
    def history_update(self, analytics: dict):
        self.acc_chart.update_points(analytics.get("acc", []))
        self.wer_chart.update_points(analytics.get("wer", []))
        ma = analytics.get("ma")
        mom = analytics.get("mom")
        if ma is not None:
            self.ma_label.setText(f"7d MA: {ma:.1%}")
        if mom is not None:
            self.mom_label.setText(f"MoM: {mom:+.1f}%")
    
    def update_summary(self, cefr: str, last_score: float, streak: int):
        self.cefr_label.setText(f"Level: {cefr}")
        self.last_score_label.setText(f"Last Score: {last_score:.1%}")
        self.streak_label.setText(f"Streak: {streak}")
    
    def update_plan_steps(self, steps: list, play_callback_factory=None):
        # Remove old step widgets
        for i in reversed(range(2, self.plan_steps_box.count())):
            widget = self.plan_steps_box.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # Add new step widgets
        completed = 0
        for step in steps:
            step_num = step.get("step_num", 0)
            desc = step.get("description", "")
            play_cb = play_callback_factory(step) if play_callback_factory else None
            widget = PlanStepWidget(step_num, desc, play_cb)
            self.plan_steps_box.addWidget(widget)
            if step.get("completed", False):
                widget.checkbox.setChecked(True)
                completed += 1
            widget.checkbox.setToolTip("Mark as complete when you finish this drill.")
            
            # Connect checkbox toggled signal to emit step_toggled with step_num and checked state
            widget.checkbox.toggled.connect(
                lambda checked, snum=step_num: self.step_toggled.emit(snum, checked)
            )
        
        # Update progress bar
        total = len(steps)
        self.plan_progress.setMaximum(total if total else 1)
        self.plan_progress.setValue(completed)
    
    def on_start_session(self):
        self.session_start.emit()
        self.set_listening_state(True)
        QtWidgets.QMessageBox.information(self, "Session Started", "Your practice session has started! Follow the plan and check off steps as you go.")
    
    def on_end_session(self):
        reply = QtWidgets.QMessageBox.question(self, "End Session?", "Are you sure you want to end this session?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.session_end.emit()
            self.set_listening_state(False)
            QtWidgets.QMessageBox.information(self, "Session Ended", "Session ended. Great work! Review your progress above.")
    
    def closeEvent(self, event):
        # Stop WhisperWorker if running
        if hasattr(self, 'whisper_worker') and self.whisper_worker:
            try:
                self.whisper_worker.stop()
            except Exception:
                pass
        # Stop PiperWorker if running
        if hasattr(self, 'piper_worker') and self.piper_worker:
            try:
                self.piper_worker.stop()
            except Exception:
                pass
        event.accept()
