"""Settings dialog for Card Assistant."""

from aqt import mw
from aqt.qt import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QThread,
    QVBoxLayout,
    pyqtSignal,
)

from .api_client import fetch_models, test_connection


class _BgWorker(QThread):
    """Run a callable in the background and deliver the result."""
    done = pyqtSignal(object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        result = self._fn()
        if not self._cancelled:
            self.done.emit(result)

MODULE = __name__.split(".")[0]


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("Card Assistant \u2014 Settings")
        self.setMinimumWidth(500)
        self._bg: _BgWorker | None = None
        self._build_ui()
        self._load()

    def done(self, result):
        """Cancel any background thread before closing the dialog."""
        if self._bg is not None:
            self._bg.cancel()
            try:
                self._bg.done.disconnect()
            except (TypeError, RuntimeError):
                pass
            # Thread will finish on its own; prevent parent-destroy crash
            self._bg.setParent(None)
            self._bg = None
        super().done(result)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Provider selector
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["OpenRouter", "Ollama"])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)

        # API Key (OpenRouter only)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-or-...")
        self._api_key_label = QLabel("API Key:")
        form.addRow(self._api_key_label, self.api_key_edit)

        # Ollama URL (Ollama only)
        self.ollama_url_edit = QLineEdit()
        self.ollama_url_edit.setPlaceholderText("http://localhost:11434")
        self._ollama_url_label = QLabel("Ollama URL:")
        form.addRow(self._ollama_url_label, self.ollama_url_edit)

        # Model row
        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(300)
        model_row.addWidget(self.model_combo)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_models)
        model_row.addWidget(self.refresh_btn)
        form.addRow("Model:", model_row)

        # Test Connection row
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_btn)
        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)
        test_row.addWidget(self.test_status, stretch=1)
        form.addRow("", test_row)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(120)
        self.prompt_edit.setStyleSheet("font-family: monospace;")
        form.addRow("System Prompt:", self.prompt_edit)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(64, 16384)
        self.max_tokens_spin.setSingleStep(128)
        form.addRow("Max Tokens:", self.max_tokens_spin)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setDecimals(2)
        form.addRow("Temperature:", self.temp_spin)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        form.addRow("Font Size:", self.font_size_spin)

        self.panel_width_spin = QSpinBox()
        self.panel_width_spin.setRange(200, 1000)
        self.panel_width_spin.setSingleStep(50)
        form.addRow("Panel Width:", self.panel_width_spin)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _on_provider_changed(self):
        is_ollama = self.provider_combo.currentText() == "Ollama"

        # Save current combo text to the outgoing provider before switching
        current_model = self.model_combo.currentText().strip()
        if hasattr(self, "_active_provider"):
            if self._active_provider == "openrouter":
                self._openrouter_model = current_model
            else:
                self._ollama_model = current_model

        # Update active provider and load its saved model
        self._active_provider = "ollama" if is_ollama else "openrouter"
        incoming = self._ollama_model if is_ollama else self._openrouter_model
        self.model_combo.clear()
        if incoming:
            self.model_combo.addItem(incoming)
        self.model_combo.setCurrentText(incoming)

        self.api_key_edit.setVisible(not is_ollama)
        self._api_key_label.setVisible(not is_ollama)
        self.ollama_url_edit.setVisible(is_ollama)
        self._ollama_url_label.setVisible(is_ollama)
        self.test_status.setText("")

    def _load(self):
        conf = mw.addonManager.getConfig(MODULE) or {}

        # Load per-provider models (fall back to legacy "model" key)
        legacy = conf.get("model", "")
        self._openrouter_model = conf.get("openrouter_model", legacy or "deepseek/deepseek-v3.2")
        self._ollama_model = conf.get("ollama_model", "")

        provider = conf.get("provider", "openrouter")
        self._active_provider = provider

        # Populate combo with the active provider's model
        active_model = self._ollama_model if provider == "ollama" else self._openrouter_model
        self.model_combo.clear()
        if active_model:
            self.model_combo.addItem(active_model)
        self.model_combo.setCurrentText(active_model)

        self.provider_combo.setCurrentText(
            "Ollama" if provider == "ollama" else "OpenRouter"
        )

        self.api_key_edit.setText(conf.get("api_key", ""))
        self.ollama_url_edit.setText(
            conf.get("ollama_url", "http://localhost:11434")
        )

        self.prompt_edit.setPlainText(conf.get("system_prompt", ""))
        self.max_tokens_spin.setValue(conf.get("max_tokens", 1024))
        self.temp_spin.setValue(conf.get("temperature", 0.7))
        self.font_size_spin.setValue(conf.get("font_size", 12))
        self.panel_width_spin.setValue(conf.get("panel_width", 400))

        # Set initial visibility
        self._on_provider_changed()

    def _current_provider(self):
        return "ollama" if self.provider_combo.currentText() == "Ollama" else "openrouter"

    def _refresh_models(self):
        provider = self._current_provider()
        api_key = self.api_key_edit.text().strip()
        ollama_url = self.ollama_url_edit.text().strip() or "http://localhost:11434"

        if provider == "openrouter" and not api_key:
            return

        self.refresh_btn.setText("Loading...")
        self.refresh_btn.setEnabled(False)

        current = self.model_combo.currentText()

        def _fetch():
            return fetch_models(api_key, provider=provider, ollama_url=ollama_url)

        def _on_done(models):
            self.model_combo.clear()
            if models:
                self.model_combo.addItems(models)
            if current:
                self.model_combo.setCurrentText(current)
            self.refresh_btn.setText("Refresh")
            self.refresh_btn.setEnabled(True)
            self._bg = None

        self._bg = _BgWorker(_fetch, self)
        self._bg.done.connect(_on_done)
        self._bg.start()

    def _test_connection(self):
        provider = self._current_provider()
        api_key = self.api_key_edit.text().strip()
        ollama_url = self.ollama_url_edit.text().strip() or "http://localhost:11434"

        self.test_btn.setEnabled(False)
        self.test_status.setText("Testing...")
        self.test_status.setStyleSheet("color: #888;")

        model = self.model_combo.currentText().strip()

        def _test():
            return test_connection(api_key, provider=provider, ollama_url=ollama_url,
                                   model=model)

        def _on_done(result):
            ok, message = result
            if ok:
                self.test_status.setStyleSheet("color: #2e7d32;")
            else:
                self.test_status.setStyleSheet("color: #c62828;")
            self.test_status.setText(message)
            self.test_btn.setEnabled(True)
            self._bg = None

        self._bg = _BgWorker(_test, self)
        self._bg.done.connect(_on_done)
        self._bg.start()

    def _save(self):
        conf = mw.addonManager.getConfig(MODULE) or {}
        conf["provider"] = self._current_provider()
        conf["api_key"] = self.api_key_edit.text().strip()
        conf["ollama_url"] = self.ollama_url_edit.text().strip() or "http://localhost:11434"
        # Save per-provider models
        active_model = self.model_combo.currentText().strip()
        if self._active_provider == "openrouter":
            conf["openrouter_model"] = active_model
            conf["ollama_model"] = self._ollama_model
        else:
            conf["ollama_model"] = active_model
            conf["openrouter_model"] = self._openrouter_model
        conf.pop("model", None)
        conf["system_prompt"] = self.prompt_edit.toPlainText()
        conf["max_tokens"] = self.max_tokens_spin.value()
        conf["temperature"] = self.temp_spin.value()
        conf["font_size"] = self.font_size_spin.value()
        conf["panel_width"] = self.panel_width_spin.value()
        mw.addonManager.writeConfig(MODULE, conf)
        self.accept()
