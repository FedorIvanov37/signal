from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QIcon
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                            QGridLayout, QButtonGroup, QLabel, QTreeWidget, QTreeWidgetItem,
                            QPushButton, QTextEdit, QHeaderView, QApplication)


from common.gui.data_models.Appearance import THEME_PRESETS


class AppearanceTab(QWidget):
    """Immediate theme controls with a small example of the working window."""

    def __init__(self, change_color, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        form = QGridLayout()
        self.selectors = {}
        self.color_buttons = []
        self.change_color = change_color
        self.colors = {}
        colors = {'Light': '#F0F0F0', 'Dark green': '#102D28', 'Dark red': '#3B202B', 'Graphite': '#292D32', 'Slate blue': '#243447', 'Signal blue': '#012E4F', 'Midnight': '#011627', 'Black': '#000000'}
        for row, (label, key) in enumerate((('Data Fields', 'Tree'), ('Base', 'Window'), ('Console', 'Console'),
                                          ('Set all', None))):
            if key is None:
                form.setRowMinimumHeight(row, 8)
                row += 1
            form.addWidget(QLabel(label), row, 0)
            group = QButtonGroup(self)
            group.setExclusive(True)
            current = QApplication.instance().property(f'signal{key}Color')
            if key is not None:
                self.colors[key] = current or '#243447'
            for column, (name, color) in enumerate(colors.items(), 1):
                button = QPushButton()
                self.color_buttons.append(button)
                button.setFixedSize(28, 28)
                button.setCheckable(key is not None)
                button.setChecked(key is not None and color == current)
                button.setToolTip(name)
                button.setAccessibleName(f'{label}: {name}')
                button.setProperty('themeColor', color)
                button.setStyleSheet(
                    f'QPushButton {{ background: {color}; border: 1px solid #8090A0; border-radius: 3px; padding: 0; }}'
                    'QPushButton:checked { border: 3px solid #0078D7; }'
                    'QPushButton:hover { border: 2px solid #70B7FF; }')
                button.setEnabled(change_color is not None)
                if key is None:
                    button.clicked.connect(lambda checked=False, value=color: self.set_colors(
                        {field: value for field in self.selectors}))
                else:
                    button.clicked.connect(lambda checked=False, field=key, value=color: self.choose(field, value))
                group.addButton(button)
                form.addWidget(button, row, column)
            if key is not None:
                self.selectors[key] = group
        layout.addLayout(form)
        layout.addSpacing(8)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Field', 'Value', 'Description'])
        self.tree.setAlternatingRowColors(True)
        self.tree.setMinimumHeight(120)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        root = QTreeWidgetItem(self.tree, ['Transaction', '', '0200'])
        for values in (['3', '000000', 'Processing code'], ['4', '000000001000', 'Amount'],
                       ['11', '123456', 'Trace number'], ['49', '978', 'Currency']):
            QTreeWidgetItem(root, values)
        root.setExpanded(True)
        self.tree.setCurrentItem(root.child(1))
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        self.preview = QWidget()
        self.preview.setObjectName('ThemePreview')
        preview_layout = QVBoxLayout(self.preview)
        self.preview_logo = QLabel()
        self.preview_logo.setProperty('signalPreviewLogo', True)
        self.preview_logo.installEventFilter(self)
        self.preview_logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview_logo.setFixedSize(36, 36)
        preview_layout.addWidget(self.preview_logo)
        preview_layout.addWidget(self.tree, 3)
        layout.addWidget(self.preview, 1)
        toolbar = QHBoxLayout()
        for label in ('+', '\u2212', 'Undo'):
            button = QPushButton(label)
            if label in ('+', '\u2212'):
                from common.gui.tools.widgets.FieldActionIcon import set_field_action_icon
                set_field_action_icon(button, 'add' if label == '+' else 'remove',
                                      'Add field' if label == '+' else 'Remove selected field')
            button.setFixedHeight(30)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            toolbar.addWidget(button)
        toolbar.addStretch()
        preview_layout.addLayout(toolbar)
        self.console = QTextEdit()
        self.console.setObjectName('LogArea')
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(75)
        self.console.setPlainText('12:00:00 | [INFO] | Connected\n12:00:01 | [INFO] | Message sent')
        preview_layout.addWidget(self.console, 2)
        self.update_preview()
        self.initial_colors = dict(self.colors)

    def eventFilter(self, watched, event):
        from PyQt6.QtCore import QEvent
        if (watched is self.preview_logo and event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton):
            from common.gui.decorators.window_settings import toggle_logo_animation
            toggle_logo_animation()
            return True
        return super().eventFilter(watched, event)

    def set_colors(self, colors):
        self.colors.update(colors)
        for key, group in self.selectors.items():
            group.setExclusive(False)
            for button in group.buttons():
                button.setChecked(button.property('themeColor') == self.colors[key])
            group.setExclusive(True)
        self.update_preview()

    def choose(self, key, color):
        self.set_colors({key: color})

    def update_preview(self):
        tree, base, console = (self.colors[key] for key in ('Tree', 'Window', 'Console'))
        from common.gui.enums.GuiFilesPath import GuiFilesPath
        from common.gui.decorators.window_settings import LOGO_THEME_COLORS
        from PyQt6.QtGui import QPixmap
        logo = QPixmap(GuiFilesPath.MAIN_LOGO)
        if not logo.isNull():
            override = QApplication.instance().property('signalLogoColor')
            if override or base not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
                painter = QPainter(logo)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(logo.rect(), QColor(override or LOGO_THEME_COLORS[base]))
                painter.end()
            self.preview_logo.setPixmap(logo.scaled(36, 32, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
        text = '#000000' if tree in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else '#E2E8F0'
        alternate = ('#E0E9F6' if tree == '#F0F0F0' else QColor(tree).lighter(110).name()) if tree in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else ('#1B1B1B' if tree == '#000000' else QColor(tree).lighter(115).name())
        background = '#FFFFFF' if tree == '#F0F0F0' else tree
        header = '#242424' if tree == '#000000' else background
        selection = 'selection-background-color: #4A4A4A; selection-color: #FFFFFF;' if tree == '#000000' else ''
        if tree == '#011627':
            selection = 'selection-background-color: #0078D7; selection-color: #FFFFFF;'
        console_selection = ('selection-background-color: #0078D7; selection-color: #FFFFFF;'
                             if console == '#011627' else '')
        tree_preset = THEME_PRESETS.get(tree, {})
        base_preset = THEME_PRESETS.get(base, {})
        console_preset = THEME_PRESETS.get(console, {})
        text = tree_preset.get('text', text)
        alternate = tree_preset.get('surface', alternate)
        header = tree_preset.get('surface', header)
        if tree_preset:
            selection = f"selection-background-color: {tree_preset['selection']}; selection-color: #FFFFFF;"
        if console_preset:
            console_selection = f"selection-background-color: {console_preset['selection']}; selection-color: #FFFFFF;"
        button_background = '#242424' if base == '#000000' else QColor(base).lighter(125).name()
        button_background = base_preset.get('surface', button_background)
        base_text = base_preset.get('text', '#000000' if base in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else '#E2E8F0')
        console_text = console_preset.get('text', '#243447' if console in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5') else '#D6DEEB')
        self.tree.setStyleSheet(f'QTreeWidget {{ background: {background}; alternate-background-color: {alternate}; color: {text}; border: none; {selection} }}'
                                f'QHeaderView {{ background: {header}; color: {text}; border: none; padding: 0; }}'
                                f'QHeaderView::section {{ background: {header}; color: {text}; border: none; }}')
        # Preview icons follow the pending base, not the application's palette.
        icon_color = base_text
        for button in self.preview.findChildren(QPushButton):
            if button.icon().isNull():
                continue
            ratio = button.devicePixelRatioF()
            pixmap = button.icon().pixmap(button.iconSize() * ratio)
            pixmap.setDevicePixelRatio(ratio)
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), QColor(icon_color))
            painter.end()
            button.setIcon(QIcon(pixmap))
        button_border = '1px solid #929BA5' if base in ('#F0F0F0', '#FFFBEB', '#EFF1F5') else 'none'
        self.preview.setStyleSheet(f'QWidget#ThemePreview {{ background: {base}; }}'
                                  f'QPushButton {{ border: {button_border}; border-radius: 3px; background: {button_background}; color: {base_text}; }}')
        self.console.setStyleSheet(f'QTextEdit {{ background: {console}; color: {console_text}; {console_selection} }}')

    def apply(self):
        if getattr(self, 'change_colors', None) is not None:
            changes = {key: color for key, color in self.colors.items() if color != self.initial_colors[key]}
            if changes:
                self.change_colors(changes)
                self.initial_colors.update(changes)
            return
        if self.change_color is not None:
            for key, color in self.colors.items():
                if color != self.initial_colors[key]:
                    self.change_color(key, color)
                    self.initial_colors[key] = color

