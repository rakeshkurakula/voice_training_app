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
            <b>Welcome!</b><br>
            This app helps you improve your articulation and track your progress.<br><br>
            <ul>
            <li>Follow the plan steps and use the <b>Play Reference</b> button to hear correct pronunciation.</li>
            <li>Check your progress in the dashboard above.</li>
            <li>Start a session to begin practicing!</li>
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceCoach")
        self.setMinimumWidth(600)
        # --- Onboarding ---
        self.first_run = True
        # --- Worker references ---
        self.whisper_worker = None
        self.piper_worker = None
        # --- Status Bar ---
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 12px; padding: 2px;")
        # --- Summary Panel ---
        self.cefr_label = QtWidgets.QLabel("Level: –")
        self.last_score_label = QtWidgets.QLabel("Last Score: –")
        self.streak_label = QtWidgets.QLabel("Streak: –")
        for lbl in [self.cefr_label, self.last_score_label, self.streak_label]:
            lbl.setStyleSheet("font-size: 16px; padding: 2px 8px;")
        summary_box = QtWidgets.QHBoxLayout()
        summary_box.addWidget(self.cefr_label)
        summary_box.addWidget(self.last_score_label)
        summary_box.addWidget(self.streak_label)
        # --- Metrics & Progress ---
        self.wpm = QtWidgets.QLabel("WPM: –")
        self.acc = QtWidgets.QLabel("Acc: –")
        self.ma_label = QtWidgets.QLabel("7d MA: –")
        self.mom_label = QtWidgets.QLabel("MoM: –")
        for lbl in [self.wpm, self.acc, self.ma_label, self.mom_label]:
            lbl.setStyleSheet("font-size: 14px; padding: 2px 8px;")
        self.acc.setToolTip("Phoneme accuracy for the last utterance")
        self.wpm.setToolTip("Words per minute for the last utterance")
        self.ma_label.setToolTip("7-day moving average of phoneme accuracy")
        self.mom_label.setToolTip("Month-over-month improvement in accuracy")
        self.acc_chart = ProgressChart("Phoneme Accuracy")
        self.wer_chart = ProgressChart("WER")
        # --- Plan Steps Panel ---
        self.plan_steps_box = QtWidgets.QVBoxLayout()
        self.plan_steps_label = QtWidgets.QLabel("This Week's Plan:")
        self.plan_steps_label.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.plan_steps_box.addWidget(self.plan_steps_label)
        # --- Plan Progress Bar ---
        self.plan_progress = QtWidgets.QProgressBar()
        self.plan_progress.setFormat("Plan Completion: %p%")
        self.plan_progress.setValue(0)
        self.plan_progress.setStyleSheet("height: 18px; font-size: 13px;")
        self.plan_steps_box.addWidget(self.plan_progress)
        # --- Session Controls ---
        self.start_btn = QtWidgets.QPushButton("▶ Start Session")
        self.end_btn = QtWidgets.QPushButton("■ End Session")
        self.end_btn.setStyleSheet("background: #e57373; color: white;")
        self.start_btn.setStyleSheet("background: #81c784; color: white;")
        self.start_btn.clicked.connect(self.on_start_session)
        self.end_btn.clicked.connect(self.on_end_session)
        controls_box = QtWidgets.QHBoxLayout()
        controls_box.addWidget(self.start_btn)
        controls_box.addWidget(self.end_btn)
        # --- Layout ---
        grid = QtWidgets.QGridLayout(self)
        grid.addWidget(self.status_label, 0, 0, 1, 2)
        grid.addLayout(summary_box, 1, 0, 1, 2)
        grid.addWidget(self.wpm, 2, 0); grid.addWidget(self.acc, 2, 1)
        grid.addWidget(self.ma_label, 3, 0); grid.addWidget(self.mom_label, 3, 1)
        grid.addWidget(self.acc_chart, 4, 0, 1, 2)
        grid.addWidget(self.wer_chart, 5, 0, 1, 2)
        grid.addLayout(self.plan_steps_box, 6, 0, 1, 2)
        grid.addLayout(controls_box, 7, 0, 1, 2)
        grid.setRowStretch(8, 1)
        # --- Onboarding Dialog ---
        if self.first_run:
            dlg = OnboardingDialog()
            dlg.exec()
            self.first_run = False

    def log_message(self, message: str):
        """Display a status message in the status bar."""
        self.status_label.setText(message)
        # Auto-clear status messages after 5 seconds
        QtCore.QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))

    def live_metrics(self, pace, acc):
        self.wpm.setText(f"WPM: {pace:.1f}")
        # Color code accuracy: green >0.8, orange >0.6, red else
        if acc >= 0.8:
            color = "#388e3c"
        elif acc >= 0.6:
            color = "#fbc02d"
        else:
            color = "#e53935"
        self.acc.setText(f"Acc: {acc:.1%}")
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
        # Update progress bar
        total = len(steps)
        self.plan_progress.setMaximum(total if total else 1)
        self.plan_progress.setValue(completed)

    def on_start_session(self):
        QtWidgets.QMessageBox.information(self, "Session Started", "Your practice session has started! Follow the plan and check off steps as you go.")

    def on_end_session(self):
        reply = QtWidgets.QMessageBox.question(self, "End Session?", "Are you sure you want to end this session?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
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
