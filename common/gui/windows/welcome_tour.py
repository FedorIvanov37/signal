"""Manually launched GUI tour. Demonstrations are temporary; explicit settings are saved."""
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QEvent
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont
from PyQt6.QtWidgets import (QApplication, QDialog, QWidget, QLabel, QPushButton,
                            QTextBrowser, QVBoxLayout, QHBoxLayout, QSlider, QDialogButtonBox, QMenu)
from common.core.enums.ReleaseDefinition import ReleaseDefinition
from common.core.tools.ErrorReporting import gui_action
from common.gui.decorators.window_settings import themed_logo
from common.gui.enums.GuiFilesPath import GuiFilesPath


def configure_dialog(dialog, title):
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    dialog.setFixedWidth(540)
    # Freeze the current theme so automatic demonstrations cannot recolour the cards.
    from common.gui.data_models.Appearance import THEME_PRESETS
    import re
    base = QApplication.instance().property('signalWindowColor') or '#F0F0F0'
    light = QColor(base).lightness() > 150
    preset = THEME_PRESETS.get(base, {})
    dialog.tour_colors = {
        'base': base,
        'text': preset.get('text', '#243447' if light else '#E2E8F0'),
        'surface': preset.get('surface', '#E1E5E9' if light else QColor(base).lighter(135).name()),
        'muted': '#476579' if light else '#A7C0CE',
        'border': '#8394A0' if light else '#718C9B',
    }
    tokens = {'#182731': base, '#E1E8ED': dialog.tour_colors['text'],
              '#283F4D': dialog.tour_colors['surface'], '#94B5C6': dialog.tour_colors['muted'],
              '#6E8795': dialog.tour_colors['border'], '#7A8992': '#7A8992',
              '#42545F': dialog.tour_colors['border'], '#345363': '#879BA8' if light else '#718C9B',
              '#BDD3DF': '#243447' if light else '#E2E8F0'}
    style = '''
        QDialog { background: #182731; color: #E1E8ED; }
        QLabel, QCheckBox { color: #E1E8ED; background: transparent; font-size: 13pt; }
        QLabel#TourTitle { font-size: 20pt; font-weight: bold; }
        QLabel#TourProgress { color: #94B5C6; font-size: 11pt; }
        QPushButton { background: #283F4D; color: #E1E8ED;
            border: 1px solid #6E8795; border-radius: 4px; padding: 8px 14px; font-size: 12pt; }
        QPushButton:default { background: #245675; color: #FFFFFF; border-color: #87B1CC; }
        QPushButton:disabled { color: #7A8992; border-color: #42545F; }
        QSlider::groove:horizontal { height: 8px; background: #345363; border-radius: 4px; }
        QSlider::handle:horizontal { width: 20px; margin: -6px 0;
            background: #94B5C6; border: 2px solid #BDD3DF; border-radius: 5px; }
    '''
    dialog.setStyleSheet(re.sub(r'#[0-9A-Fa-f]{6}', lambda match: tokens.get(match[0], match[0]), style))


def tour_logo(parent, size):
    logo = QLabel(parent)
    pixmap = themed_logo(GuiFilesPath.MAIN_LOGO, dark_color='#91AFBD')
    if not pixmap.isNull():
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor('#FFFFFF' if QColor(parent.tour_colors['base']).lightness() <= 150 else parent.tour_colors['muted']))
        painter.end()
        logo.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation))
    logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo.setFixedHeight(size + 8)
    return logo


class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        configure_dialog(self, 'Signal | Welcome')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)
        self.logo = tour_logo(self, 144)
        layout.addWidget(self.logo)
        title = QLabel(f'Welcome to Signal {ReleaseDefinition.VERSION}')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName('TourTitle')
        title.setWordWrap(True)
        layout.addWidget(title)
        text = QLabel('This tour covers interface changes in this version: log formatting, '
                      'theme settings, field sorting, panel sizes, API controls and drag-and-drop.')
        text.setWordWrap(True)
        layout.addWidget(text)
        buttons = QHBoxLayout()
        self.skip = QPushButton('Not now')
        self.start = QPushButton('Start tour')
        self.start.setDefault(True)
        self.skip.clicked.connect(self.reject)
        self.start.clicked.connect(self.accept)
        buttons.addWidget(self.skip)
        buttons.addWidget(self.start)
        layout.addLayout(buttons)


class TourShade(QWidget):
    """Grey veil with a cutout mapped through the common ancestor window."""
    def __init__(self, window):
        super().__init__(window)
        self.target = None
        self.dimmed = True
        self.callout = ''
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Hide real session messages throughout the tour without changing the log.
        log = self.parentWidget().LogArea
        origin = log.mapTo(self.parentWidget(), QPoint())
        console = QRectF(origin.x(), origin.y(), log.width(), log.height())
        color = QApplication.instance().property('signalConsoleColor') or '#012E4F'
        painter.fillRect(console, QColor(color))
        path = QPainterPath()
        path.addRect(QRectF(self.rect()))
        if self.target is not None:
            origin = self.target.mapTo(self.parentWidget(), QPoint())
            hole = QRectF(origin.x()-5, origin.y()-5,
                          self.target.width()+10, self.target.height()+10)
            cutout = QPainterPath()
            cutout.addRoundedRect(hole, 6, 6)
            path = path.subtracted(cutout)
            painter.setPen(QColor('#8CBCD0'))
            painter.drawRoundedRect(hole, 6, 6)
        if self.dimmed:
            painter.fillPath(path, QColor(100, 105, 110, 185))
        if self.target is not None and self.callout:
            self.draw_callout(painter, hole)

    def draw_callout(self, painter, hole):
        from math import atan2, cos, sin, pi
        target = hole.center()
        width, height = 230, 42
        x = target.x() + 65 if target.x() < self.width()/2 else target.x() - width - 65
        y = target.y() + 70 if target.y() < self.height()/2 else target.y() - 100
        label = QRectF(max(12, min(x, self.width()-width-12)),
                       max(12, min(y, self.height()-height-12)), width, height)
        start = label.center()
        angle = atan2(target.y()-start.y(), target.x()-start.x())
        tip = QPointF(target.x()-cos(angle)*18, target.y()-sin(angle)*18)
        painter.setPen(QPen(QColor('#AAD9EA'), 3))
        painter.drawLine(start, tip)
        for offset in (-pi/6, pi/6):
            painter.drawLine(tip, QPointF(tip.x()-16*cos(angle+offset),
                                          tip.y()-16*sin(angle+offset)))
        painter.setBrush(QColor('#182731'))
        painter.drawRoundedRect(label, 7, 7)
        painter.setPen(QColor('#ECF5F8'))
        painter.setFont(QFont('Arial', 13, QFont.Weight.Bold))
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, self.callout)


class ConsoleSizeControl(QSlider):
    """Resize the real console without allowing other main-window actions."""
    def __init__(self, reset, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.reset = reset
        self.setRange(20, 75)
        self.setAccessibleName('Console height; double-click to restore')
        self.setToolTip('Drag to resize the console; double-click to restore')
        self.setMinimumHeight(28)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.reset()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


class WelcomeTour(QDialog):
    RESIZE_STEP = 6
    API_STEP = 7
    COLORS = ('#102D28', '#3B202B', '#012E4F')
    STEPS = (
        ('Console log formatting', 'Log entries use different colours for severity levels. '
         'The console below contains demonstration entries; no transactions are sent.'),
        ('Theme colours', 'The demonstration applies three dark themes, then changes the console, '
         'Data Fields and base colours separately. These automatic changes are not saved.'),
        ('Theme configuration', 'Settings → Theme provides a colour palette and a preview. '
         'Selecting a colour here applies it to the corresponding element and saves the setting.'),
        ('Configuration dialog', 'The button in the bottom-right corner opens connection, field, '
         'specification, API and theme settings. The demonstration theme has been restored to your saved colours.'),
        ('Sort Data Fields', 'The ↑ button beside Field sorts fields by number at every nesting level. '
         'This step highlights the control without sorting the current transaction.'),
        ('Automatic field sorting', 'Settings → Fields → Automatically sort fields enables sorting during editing. '
         'Changing this checkbox applies and saves the setting.'),
        ('Console panel size', 'Drag the divider above the console to resize the panels. '
         'Double-click the divider to restore the default proportions. In this tour, use the control below '
         'to resize the console; double-click it to restore the proportions from the start of the tour.'),
        ('API controls', 'The API controls are located in Tools → API: Start, Stop and Restart. '
         'The API can run alongside the GUI. The displayed menu does not execute these commands.'),
        ('Drag-and-drop files and text', 'Drop transaction files or transaction text into the transaction editor to load data. '
         'The configuration dialog accepts configuration text. Review imported values before sending a transaction.'),
        ('Release info', 'Changes included in this release are listed below. '
         'Select Finish tour to close the tour and continue the working session.'),
    )

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.step = 0
        self._cleaned = False
        self.original = {k: QApplication.instance().property(f'signal{k}Color')
                         for k in ('Window', 'Tree', 'Console')}
        self.splitter = getattr(window, 'main_splitter', None)
        self.original_sizes = self.splitter.sizes() if self.splitter is not None else None
        configure_dialog(self, 'Signal | Quick tour')
        self.content_layout = QHBoxLayout(self)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout()
        self.content_layout.addLayout(layout, 1)
        self.settings_preview = None
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(900)
        self.preview_timer.timeout.connect(self.animate_settings_preview)
        self.preview_count = 0
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.progress = QLabel()
        self.progress.setObjectName('TourProgress')
        self.title = QLabel()
        self.title.setObjectName('TourTitle')
        self.title.setWordWrap(True)
        self.description = QLabel()
        self.description.setWordWrap(True)
        for widget in (self.progress, self.title, self.description):
            layout.addWidget(widget)
        self.demo_phase = QLabel()
        self.demo_phase.setWordWrap(True)
        layout.addWidget(self.demo_phase)
        self.resize_control = ConsoleSizeControl(self.restore_console_size, self)
        self.resize_control.valueChanged.connect(self.resize_console)
        layout.addWidget(self.resize_control)
        self.final_logo = tour_logo(self, 96)
        layout.addWidget(self.final_logo)
        self.release_notes = QTextBrowser(self)
        self.release_notes.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.release_notes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.release_notes.setMinimumHeight(230)
        self.release_notes.setMaximumHeight(300)
        self.release_notes.setStyleSheet(
            f"QTextBrowser {{ background: {self.tour_colors['surface']}; color: {self.tour_colors['text']}; "
            f"border: 1px solid {self.tour_colors['border']}; font-size: 12pt; padding: 8px; }}")
        self.release_notes.setStyleSheet(self.release_notes.styleSheet() +
            f"QScrollBar:vertical {{ background: {self.tour_colors['surface']}; width: 16px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{ background: {self.tour_colors['muted']}; min-height: 28px; border-radius: 4px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }")
        self.release_notes.setHtml('''
            <h3>Signal v0.21 — Release info</h3>
            <b>New features</b><ul>
            <li>Color customization with live preview</li>
            <li>Resizable field and log panels</li>
            <li>Drag-and-drop support for transactions and configuration data</li>
            <li>Undo and redo in the complex field constructor</li>
            <li>Specification recovery from backups</li>
            <li>Version-specific guided tour of interface changes</li>
            <li>Application-wide debug logging</li>
            <li>Error dialog with a stack trace for unexpected errors</li></ul>
            <b>Updates</b><ul>
            <li>Improved interface, keyboard navigation and error reporting</li>
            <li>Consistent configuration updates across GUI and API</li>
            <li>Core code cleanup and reliability improvements</li></ul>
            <b>Fixed</b><ul>
            <li>TCP message handling and response matching</li>
            <li>Configuration and specification saving issues</li>
            <li>Various editing, display and connection shutdown issues</li></ul>
        ''')
        layout.addWidget(self.release_notes)
        buttons = QHBoxLayout()
        self.leave = QPushButton('End tour')
        self.back = QPushButton('Back')
        self.next = QPushButton('Next')
        self.next.setDefault(True)
        self.leave.clicked.connect(self.reject)
        self.back.clicked.connect(lambda: self.show_step(self.step - 1))
        self.next.clicked.connect(self.advance)
        for button in (self.leave, self.back, self.next):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.shade = TourShade(window)
        self.tools_preview = None
        self.api_preview = None
        self.demo = QTextBrowser(self.shade)
        self.demo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.demo.setStyleSheet('QTextBrowser { background: #011627; border: 1px solid #7193A5; '
                                'color: #C6D5DF; font: 14pt "Consolas"; padding: 12px; }')
        self.demo.setHtml('<p style="color:#94B5C6; font-family:Consolas; font-size:14pt">Signal tour / Console preview</p>' + ''.join(
            f'<pre style="color:{color}; margin:0; font-family:Consolas; font-size:14pt">12:00:0{i} | {("[" + level + "]"):<9} | {text}</pre>'
            for i, (color, level, text) in enumerate((
                ('#91BDB0', 'INFO', 'Connected to the demo host'),
                ('#86ADC7', 'INFO', '0200 request prepared'),
                ('#A4C493', 'INFO', '0210 response received: approved'),
                ('#C7AB80', 'WARNING', 'Example field needs your attention'),
                ('#C58E98', 'ERROR', 'Example connection timeout'),
                ('#92A6B3', 'DEBUG', 'Request matched in 0.125 seconds'),
            ))))
        self.timer = QTimer(self)
        self.timer.setInterval(1300)
        self.timer.timeout.connect(self.cycle_theme)
        self.theme_index = 0
        self.geometry_timer = QTimer(self)
        self.geometry_timer.setSingleShot(True)
        self.geometry_timer.timeout.connect(self.position_elements)
        self.geometry_sources = {window}
        for target in (window.LogArea, window.ButtonSettings):
            while target is not None and target is not window:
                self.geometry_sources.add(target)
                target = target.parentWidget()
        for source in self.geometry_sources:
            source.installEventFilter(self)
        for source in (self.release_notes, self.release_notes.viewport(), self.release_notes.verticalScrollBar()):
            source.installEventFilter(self)
        self.show_step(0)
        self.geometry_timer.start(0)

    def position_elements(self):
        if self._cleaned:
            return
        self.shade.setGeometry(self.window.rect())
        log = self.window.LogArea
        origin = log.mapTo(self.window, QPoint())
        self.demo.setGeometry(origin.x(), origin.y(), log.width(), log.height())
        self.shade.raise_()
        self.layout().invalidate()
        self.layout().activate()
        self.adjustSize()
        point = self.window.mapToGlobal(QPoint(max(12, (self.window.width()-self.width())//2), 38))
        screen = self.window.screen().availableGeometry()
        point.setX(max(screen.left(), min(point.x(), screen.right()-self.width())))
        point.setY(max(screen.top() + 12, min(point.y(), screen.bottom()-220)))
        self.move(point)
        self.position_tools_preview()
        self.shade.update()

    def eventFilter(self, obj, event):
        if (not self._cleaned and self.step == len(self.STEPS)-1
                and event.type() == QEvent.Type.Wheel
                and obj in (self.release_notes, self.release_notes.viewport(),
                            self.release_notes.verticalScrollBar())):
            bar = self.release_notes.verticalScrollBar()
            delta = event.pixelDelta().y()
            if not delta:
                delta = round(event.angleDelta().y() / 120 *
                              self.release_notes.fontMetrics().lineSpacing() * QApplication.wheelScrollLines())
            bar.setValue(bar.value() - delta)
            event.accept()
            return True
        if (not self._cleaned and obj in self.geometry_sources and event.type() in
                (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.Show, QEvent.Type.LayoutRequest)):
            if not self.geometry_timer.isActive():
                self.geometry_timer.start(0)
        return super().eventFilter(obj, event)

    def show_step(self, index):
        self.timer.stop()
        self.preview_timer.stop()
        self.step = max(0, min(index, len(self.STEPS)-1))
        if self.step != 1:
            self.window.apply_theme_colors(self.original)
        self.title.setText(self.STEPS[self.step][0])
        self.description.setText(self.STEPS[self.step][1])
        self.progress.setText(f'Signal {ReleaseDefinition.VERSION}  /  {self.step + 1} of {len(self.STEPS)}')
        self.back.setEnabled(self.step > 0)
        self.leave.setVisible(self.step != len(self.STEPS)-1)
        self.next.setText('Finish tour' if self.step == len(self.STEPS)-1 else 'Next')
        self.shade.target = self.window.LogArea if self.step in (0, self.RESIZE_STEP) else (
            self.window.ButtonSettings if self.step == 3 else (
                getattr(self.window, 'ButtonTools', None) if self.step == self.API_STEP else (
                    getattr(getattr(self.window, 'json_view', None), 'sort_fields_button', None)
                    if self.step == 4 else None)))
        self.shade.callout = {3: 'Settings', 4: 'Sort Data Fields', self.API_STEP: 'Tools → API'}.get(self.step, '')
        self.demo_phase.setVisible(self.step == 1)
        self.shade.dimmed = self.step != 1
        self.demo.setVisible(self.step in (0, self.RESIZE_STEP))
        self.resize_control.setVisible(self.step == self.RESIZE_STEP)
        self.resize_control.setEnabled(self.splitter is not None)
        self.final_logo.setVisible(self.step == len(self.STEPS)-1)
        self.release_notes.setVisible(self.step == len(self.STEPS)-1)
        self.restore_console_size()
        self.show_settings_preview()
        self.show_tools_preview()
        self.shade.show()
        if self.step == 1:
            self.theme_index = 0
            self.cycle_theme()
            self.timer.start()
        self.position_elements()
        if self.step == len(self.STEPS)-1:
            self.release_notes.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self.next.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_tools_preview(self):
        visible = self.step == self.API_STEP
        button = getattr(self.window, 'ButtonTools', None)
        if visible and self.tools_preview is None and button is not None:
            # Render the real menu structure without executing application commands
            # or giving a popup a mouse grab over the tour's navigation buttons.
            self.tools_preview = QMenu(self.shade)
            self.tools_preview.setWindowFlags(Qt.WindowType.Widget)
            self.tools_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.api_preview = QMenu(self.shade)
            self.api_preview.setWindowFlags(Qt.WindowType.Widget)
            self.api_preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            for original in button.menu().actions():
                if original.isSeparator():
                    self.tools_preview.addSeparator()
                    continue
                if original.menu() is not None and original.text() == 'API':
                    action = self.tools_preview.addMenu(self.api_preview)
                    action.setText(original.text())
                    self.tools_api_action = action
                    font = action.font()
                    font.setBold(True)
                    action.setFont(font)
                    for command in original.menu().actions():
                        copy = self.api_preview.addAction(command.text())
                        copy.setEnabled(command.isEnabled())
                else:
                    self.tools_preview.addAction(original.text())
        if self.tools_preview is not None:
            self.tools_preview.setVisible(visible)
            self.api_preview.setVisible(visible)

    def position_tools_preview(self):
        if self.tools_preview is None or self.step != self.API_STEP:
            return
        button = self.window.ButtonTools
        point = button.mapTo(self.window, QPoint())
        size = self.tools_preview.sizeHint()
        x = max(8, min(point.x(), self.shade.width()-size.width()-8))
        y = max(8, point.y()-size.height()-8)
        self.tools_preview.setGeometry(x, y, size.width(), size.height())
        api_size = self.api_preview.sizeHint()
        api_x = x+size.width()+4
        if api_x+api_size.width() > self.shade.width()-8:
            api_x = max(8, x-api_size.width()-4)
        self.api_preview.setGeometry(api_x, y, api_size.width(), api_size.height())
        self.tools_preview.raise_()
        self.api_preview.raise_()

    def show_settings_preview(self):
        visible = self.step in (2, 5) and hasattr(self.window, 'config')
        if visible and self.settings_preview is None:
            from common.gui.windows.settings_window import SettingsWindow
            settings = SettingsWindow(self.window.config.model_copy(deep=True),
                                      commit=lambda config: None, change_color=lambda *args: None,
                                      commit_theme=lambda config: None)
            settings.setParent(self, Qt.WindowType.Widget)
            settings.setAcceptDrops(False)
            for box in settings.findChildren(QDialogButtonBox):
                box.hide()
            for button in settings.findChildren(QPushButton):
                if button.text().replace('&', '') in ('OK', 'Cancel'):
                    button.setEnabled(False)
                    button.parentWidget().hide()
            settings.MainTabs.tabBar().setEnabled(False)
            self.settings_preview = settings
            field_buttons = set()
            for key, group in settings.Appearance.selectors.items():
                for button in group.buttons():
                    field_buttons.add(button)
                    button.clicked.connect(lambda checked=False, field=key, widget=button:
                        self.choose_theme({field: widget.property('themeColor')}))
            for button in settings.Appearance.color_buttons:
                if button not in field_buttons:
                    button.clicked.connect(lambda checked=False, widget=button:
                        self.choose_theme({key: widget.property('themeColor') for key in self.original}))
            settings.AutoSortFields.clicked.connect(self.choose_auto_sort)
            self.content_layout.addWidget(settings)
        if self.settings_preview is not None:
            self.settings_preview.setVisible(visible)
        self.setMinimumWidth(1000 if visible else 540)
        self.setMaximumWidth(1100 if visible else 540)
        if not visible:
            return
        settings = self.settings_preview
        settings.AutoSortFields.setStyleSheet('')
        if self.step == 2:
            settings.MainTabs.setCurrentWidget(settings.Appearance)
            settings.Appearance.set_colors(self.window.config.theme.model_copy(deep=True).colors())
            self.preview_count = 0
            self.preview_timer.start()
        else:
            # Find the Fields tab independently of generated form container names.
            for index in range(settings.MainTabs.count()):
                if settings.MainTabs.tabText(index) == 'Fields':
                    settings.MainTabs.setCurrentIndex(index)
            settings.AutoSortFields.setChecked(self.window.config.fields.auto_sort)
            settings.AutoSortFields.setStyleSheet(
                'QCheckBox { border: 2px solid #8CBCD0; border-radius: 4px; padding: 6px; }')

    def commit_choice(self, candidate):
        manager = getattr(self.window.config, 'manager', None)
        if manager is not None:
            previous = self.window.property('signalTourCommit')
            self.window.setProperty('signalTourCommit', True)
            try:
                manager.replace(candidate)
            finally:
                self.window.setProperty('signalTourCommit', previous)
        else:
            from common.core.tools.ConfigStore import save_config
            from common.core.enums.TermFilesPath import TermFilesPath
            save_config(candidate, getattr(self.window.config, '_source_file', None) or TermFilesPath.CONFIG)
            self.window.config = candidate

    @gui_action
    def choose_theme(self, colors):
        self.preview_timer.stop()
        candidate = self.window.config.model_copy(deep=True)
        fields = {'Tree': 'treeColor', 'Window': 'windowColor', 'Console': 'consoleColor'}
        for key, color in colors.items():
            setattr(candidate.theme, fields[key], color)
        try:
            self.commit_choice(candidate)
        except Exception:
            self.settings_preview.Appearance.set_colors(self.original)
            raise
        # Future demonstrations and exit restore the user's latest saved selection.
        self.original = dict(candidate.theme.colors())
        self.window.apply_theme_colors(self.original)
        self.settings_preview.Appearance.set_colors(self.original)

    @gui_action
    def choose_auto_sort(self, enabled):
        candidate = self.window.config.model_copy(deep=True)
        candidate.fields.auto_sort = enabled
        try:
            self.commit_choice(candidate)
        except Exception:
            self.settings_preview.AutoSortFields.setChecked(self.window.config.fields.auto_sort)
            raise
        from common.gui.tools.json_views.TreeView import TreeView
        for tree in self.window.findChildren(TreeView):
            if hasattr(tree, '_auto_sort_timer'):
                tree.set_auto_sort(enabled)

    def animate_settings_preview(self):
        if self._cleaned or self.step != 2 or self.settings_preview is None:
            self.preview_timer.stop()
            return
        key, color = (('Tree', '#102D28'), ('Console', '#3B202B'))[self.preview_count]
        self.settings_preview.Appearance.choose(key, color)
        self.preview_count += 1
        if self.preview_count == 2:
            self.preview_timer.stop()

    def cycle_theme(self):
        if self._cleaned or self.step != 1:
            return
        # The last whole theme is blue: use a distinct console colour first.
        separate = ({'Console': '#3B202B'}, {'Tree': '#102D28'}, {'Window': '#292D32'})
        if self.theme_index >= len(self.COLORS) + len(separate):
            self.timer.stop()
            return
        if self.theme_index < len(self.COLORS):
            color = self.COLORS[self.theme_index]
            colors = {k: color for k in self.original}
            self.demo_phase.setText(f'Whole theme · {self.theme_index + 1} of {len(self.COLORS)}')
        else:
            colors = separate[self.theme_index - len(self.COLORS)]
            self.demo_phase.setText({'Console': 'Console colour only', 'Tree': 'Data Fields colour only',
                                     'Window': 'Base colour only'}[next(iter(colors))])
        self.window.apply_theme_colors(colors)
        self.theme_index += 1
        if self.theme_index == len(self.COLORS) + len(separate):
            self.timer.stop()

    def resize_console(self, value):
        if self.splitter is None or self.step != self.RESIZE_STEP or self._cleaned:
            return
        available = sum(self.splitter.sizes())
        lower = round(available * value / 100)
        # Unlike dragging the real handle, setSizes does not emit splitterMoved.
        self.splitter.setSizes([available - lower, lower])
        self.position_elements()

    def restore_console_size(self):
        if self.splitter is None or not self.original_sizes or not sum(self.original_sizes):
            return
        self.splitter.setSizes(self.original_sizes)
        self.resize_control.blockSignals(True)
        self.resize_control.setValue(round(100 * self.original_sizes[1] / sum(self.original_sizes)))
        self.resize_control.blockSignals(False)
        self.geometry_timer.start(0)

    def advance(self):
        if self.step == len(self.STEPS)-1:
            self.accept()
        else:
            self.show_step(self.step+1)

    def cleanup(self):
        if self._cleaned:
            return
        self.restore_console_size()
        self._cleaned = True
        self.preview_timer.stop()
        if self.settings_preview is not None:
            self.settings_preview.hide()
        self.timer.stop()
        self.geometry_timer.stop()
        for source in self.geometry_sources:
            source.removeEventFilter(self)
        try:
            self.window.apply_theme_colors(self.original)
        finally:
            self.shade.hide()
            self.shade.deleteLater()

    def done(self, result):
        self.cleanup()
        super().done(result)


def offer_welcome_tour(window):
    welcome = WelcomeDialog(window)
    try:
        accepted = welcome.exec() == QDialog.DialogCode.Accepted
    finally:
        welcome.deleteLater()
    if accepted:
        run_welcome_tour(window)


def run_welcome_tour(window):
    tour = WelcomeTour(window)
    try:
        tour.exec()
    finally:
        tour.cleanup()
        tour.deleteLater()
