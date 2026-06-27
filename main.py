"""Desktop task list widget using PySide6."""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QMimeData, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QIcon, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)


DATA_DIR = Path(__file__).resolve().parent / "data"
TASKS_FILE = DATA_DIR / "tasks.json"


@dataclass
class Task:
    id: str
    text: str
    completed: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            text=data.get("text", ""),
            completed=data.get("completed", False),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


class TaskStore:
    def __init__(self, path: Path = TASKS_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: list[Task] = []
        self.load()

    def load(self):
        if not self.path.exists():
            self.tasks = []
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self.tasks = [Task.from_dict(item) for item in data if isinstance(item, dict)]
        except (json.JSONDecodeError, OSError):
            self.tasks = []

    def save(self):
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump([task.to_dict() for task in self.tasks], f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def add(self, text: str) -> Task:
        task = Task(id=str(uuid.uuid4()), text=text.strip())
        self.tasks.insert(0, task)
        self.save()
        return task

    def remove(self, task_id: str) -> bool:
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                self.save()
                return True
        return False

    def update_text(self, task_id: str, text: str) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.text = text.strip()
                self.save()
                return True
        return False

    def toggle(self, task_id: str) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.completed = not task.completed
                self.save()
                return True
        return False

    def move(self, from_index: int, to_index: int) -> bool:
        if not (0 <= from_index < len(self.tasks) and 0 <= to_index < len(self.tasks)):
            return False
        if from_index == to_index:
            return True
        task = self.tasks.pop(from_index)
        # Adjust target index after removal if target was after source
        if to_index > from_index:
            to_index -= 1
        self.tasks.insert(to_index, task)
        self.save()
        return True


class DragHandle(QLabel):
    def __init__(self, parent: "TaskItemWidget"):
        super().__init__("≡", parent)
        self.task_item = parent
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("拖动排序")
        self.setStyleSheet(
            """
            QLabel {
                color: rgba(255, 255, 255, 120);
                font-size: 14px;
                padding: 0 2px;
            }
            QLabel:hover {
                color: rgba(255, 255, 255, 200);
            }
            """
        )
        self.setFixedWidth(16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-taskwidget-taskid", self.task_item.task.id.encode("utf-8"))
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()


class TaskItemWidget(QWidget):
    def __init__(self, task: Task, store: TaskStore, parent: "TaskWidget"):
        super().__init__(parent)
        self.task = task
        self.store = store
        self.main_widget = parent
        self._build_ui()

    def _build_ui(self):
        self.setAcceptDrops(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.drag_handle = DragHandle(self)
        layout.addWidget(self.drag_handle)

        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.task.completed)
        self.checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.checkbox.setStyleSheet(
            """
            QCheckBox {
                color: #eeeeee;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 80);
                background-color: rgba(255, 255, 255, 20);
            }
            QCheckBox::indicator:checked {
                background-color: #66bb6a;
                border-color: #66bb6a;
            }
            """
        )
        self.checkbox.stateChanged.connect(self._on_toggled)
        layout.addWidget(self.checkbox)

        self.label = QLabel(self.task.text)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.label.setStyleSheet(
            """
            QLabel {
                color: #eeeeee;
                font-size: 13px;
                padding: 2px 0;
            }
            QLabel[completed="true"] {
                color: #888888;
                text-decoration: line-through;
            }
            """
        )
        self.label.setProperty("completed", self.task.completed)
        self.label.style().unpolish(self.label)
        self.label.style().polish(self.label)
        layout.addWidget(self.label, 1)

        self.edit = QLineEdit(self.task.text)
        self.edit.setStyleSheet(
            """
            QLineEdit {
                color: #eeeeee;
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(79, 195, 247, 120);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 13px;
            }
            """
        )
        self.edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.edit.hide()
        self.edit.returnPressed.connect(self._finish_edit)
        self.edit.editingFinished.connect(self._finish_edit)
        layout.addWidget(self.edit, 1)

        self.edit_btn = QPushButton("✎")
        self.edit_btn.setToolTip("编辑")
        self.edit_btn.setFixedSize(22, 22)
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self._start_edit)

        self.delete_btn = QPushButton("×")
        self.delete_btn.setToolTip("删除")
        self.delete_btn.setFixedSize(22, 22)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._on_delete)

        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

    def _on_toggled(self, state: int):
        completed = state == Qt.CheckState.Checked.value
        self.task.completed = completed
        self.store.toggle(self.task.id)
        self.label.setProperty("completed", completed)
        self.label.style().unpolish(self.label)
        self.label.style().polish(self.label)
        if self.main_widget:
            self.main_widget._update_summary()

    def _start_edit(self):
        self.label.hide()
        self.edit_btn.hide()
        self.edit.show()
        self.edit.setText(self.task.text)
        self.edit.setFocus()
        self.edit.selectAll()

    def _finish_edit(self):
        if self.edit.isHidden():
            return
        new_text = self.edit.text().strip()
        if new_text:
            self.task.text = new_text
            self.store.update_text(self.task.id, new_text)
            self.label.setText(new_text)
        self.edit.hide()
        self.label.show()
        self.edit_btn.show()
        if self.main_widget:
            self.main_widget._update_summary()

    def _on_delete(self):
        self.store.remove(self.task.id)
        if self.main_widget:
            self.main_widget._reload_tasks()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-taskwidget-taskid"):
            event.acceptProposedAction()
            self._set_drop_highlight(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-taskwidget-taskid"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_highlight(False)

    def dropEvent(self, event):
        self._set_drop_highlight(False)
        mime = event.mimeData()
        if not mime.hasFormat("application/x-taskwidget-taskid"):
            event.ignore()
            return

        source_id = bytes(mime.data("application/x-taskwidget-taskid")).decode("utf-8")
        if source_id == self.task.id:
            event.ignore()
            return

        source_widget = None
        for i in range(self.main_widget.tasks_layout.count() - 1):  # exclude stretch
            widget = self.main_widget.tasks_layout.itemAt(i).widget()
            if isinstance(widget, TaskItemWidget) and widget.task.id == source_id:
                source_widget = widget
                break

        if source_widget is None or self.main_widget is None:
            event.ignore()
            return

        source_index = self.main_widget.tasks_layout.indexOf(source_widget)
        target_index = self.main_widget.tasks_layout.indexOf(self)
        if source_index < 0 or target_index < 0:
            event.ignore()
            return

        # Account for trailing stretch in layout index -> store index mapping
        if source_index >= self.main_widget.tasks_layout.count() - 1:
            source_index = len(self.store.tasks) - 1
        if target_index >= self.main_widget.tasks_layout.count() - 1:
            target_index = len(self.store.tasks) - 1

        self.store.move(source_index, target_index)
        self.main_widget._reload_tasks()
        event.acceptProposedAction()

    def _set_drop_highlight(self, active: bool):
        if active:
            self.setStyleSheet(
                """
                TaskItemWidget {
                    background-color: rgba(79, 195, 247, 40);
                    border-radius: 6px;
                }
                """
            )
        else:
            self.setStyleSheet("")


class TaskWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.drag_pos: QPoint | None = None
        self.store = TaskStore()
        self.compact_mode = False
        self.locked = False

        self._setup_tray()
        self._build_ui()
        self._center_on_screen()

    def _build_ui(self):
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet(
            """
            #container {
                background-color: rgba(30, 30, 30, 220);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 40);
            }
            QLabel {
                color: #eeeeee;
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            }
            QLabel#title {
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
            QLabel#hint {
                color: #888888;
                font-size: 12px;
            }
            QLabel#summary {
                color: #aaaaaa;
                font-size: 11px;
            }
            QLineEdit {
                color: #eeeeee;
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 13px;
                font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            }
            QLineEdit:focus {
                border-color: rgba(79, 195, 247, 180);
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 30);
                color: #ffffff;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 60);
            }
            QPushButton#add {
                background-color: rgba(79, 195, 247, 180);
            }
            QPushButton#add:hover {
                background-color: rgba(79, 195, 247, 220);
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            """
        )

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Title bar
        title_layout = QHBoxLayout()
        title_layout.setSpacing(6)

        self.title_label = QLabel("任务清单")
        self.title_label.setObjectName("title")
        title_layout.addWidget(self.title_label)

        title_layout.addStretch()

        self.lock_btn = QPushButton("🔓")
        self.lock_btn.setToolTip("锁定：防止误操作")
        self.lock_btn.setCheckable(True)
        self.lock_btn.setFixedSize(22, 22)
        self.lock_btn.clicked.connect(self._toggle_lock)

        self.compact_btn = QPushButton("◱")
        self.compact_btn.setToolTip("切换精简模式")
        self.compact_btn.setCheckable(True)
        self.compact_btn.setFixedSize(22, 22)
        self.compact_btn.clicked.connect(self._toggle_compact_mode)

        minimize_btn = QPushButton("−")
        minimize_btn.setToolTip("最小化")
        minimize_btn.setFixedSize(22, 22)
        minimize_btn.clicked.connect(self.showMinimized)

        title_layout.addWidget(self.lock_btn)
        title_layout.addWidget(self.compact_btn)
        title_layout.addWidget(minimize_btn)
        layout.addLayout(title_layout)

        # Body stack
        self.body_stack = QStackedWidget()
        self.body_stack.setContentsMargins(0, 0, 0, 0)

        # Normal page
        normal_page = QWidget()
        normal_layout = QVBoxLayout(normal_page)
        normal_layout.setContentsMargins(0, 0, 0, 0)
        normal_layout.setSpacing(10)

        # Scroll area for tasks
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(
            """
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 20);
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 80);
                border-radius: 3px;
                min-height: 20px;
            }
            """
        )

        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(0, 0, 4, 0)
        self.tasks_layout.setSpacing(8)
        self.tasks_layout.addStretch()
        self.scroll.setWidget(self.tasks_container)
        normal_layout.addWidget(self.scroll, 1)

        # Empty hint
        self.empty_hint = QLabel("暂无任务，点击下方添加")
        self.empty_hint.setObjectName("hint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        normal_layout.addWidget(self.empty_hint)

        # Add task row
        add_layout = QHBoxLayout()
        add_layout.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入新任务...")
        self.input.returnPressed.connect(self._add_task)
        add_layout.addWidget(self.input, 1)

        self.add_btn = QPushButton("+")
        self.add_btn.setObjectName("add")
        self.add_btn.setFixedSize(28, 28)
        self.add_btn.setToolTip("添加任务")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._add_task)
        add_layout.addWidget(self.add_btn)
        normal_layout.addLayout(add_layout)

        # Summary
        self.summary_label = QLabel()
        self.summary_label.setObjectName("summary")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        normal_layout.addWidget(self.summary_label)

        self.body_stack.addWidget(normal_page)

        # Compact page
        compact_page = QWidget()
        compact_layout = QVBoxLayout(compact_page)
        compact_layout.setContentsMargins(0, 0, 0, 0)
        compact_layout.setSpacing(6)

        self.compact_count = QLabel("0")
        self.compact_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compact_count.setStyleSheet("font-size: 32px; font-weight: bold; color: #4fc3f7;")
        compact_layout.addWidget(self.compact_count)

        self.compact_text = QLabel("待办任务")
        self.compact_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compact_text.setStyleSheet("font-size: 11px; color: #aaaaaa;")
        compact_layout.addWidget(self.compact_text)

        self.body_stack.addWidget(compact_page)

        layout.addWidget(self.body_stack)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.addWidget(self.container)
        self.setLayout(self.main_layout)

        self.setFixedSize(260, 360)
        self._reload_tasks()

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self._create_tray_icon(0))

        tray_menu = QMenu()
        show_action = QAction("显示", self)
        show_action.triggered.connect(self.show)
        hide_action = QAction("隐藏", self)
        hide_action.triggered.connect(self.hide)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.setToolTip("任务清单")
        self.tray_icon.show()

    def _create_tray_icon(self, count: int) -> QIcon:
        pixmap = QPixmap(128, 128)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 30, 30, 220))
        painter.drawRoundedRect(8, 8, 112, 112, 20, 20)

        # Circle ring
        painter.setPen(QColor(79, 195, 247))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = painter.pen()
        pen.setWidth(8)
        painter.setPen(pen)
        painter.drawEllipse(28, 28, 72, 72)

        # Count text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Microsoft YaHei UI", 28, QFont.Weight.Bold)
        painter.setFont(font)
        text = str(count)
        rect = painter.boundingRect(0, 0, 128, 128, Qt.AlignmentFlag.AlignCenter, text)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.end()
        return QIcon(pixmap)

    def _toggle_lock(self):
        locked = self.lock_btn.isChecked()
        self._set_locked(locked)

    def _set_locked(self, locked: bool):
        self.locked = locked
        self.lock_btn.setChecked(locked)
        if locked:
            self.lock_btn.setText("🔒")
            self.lock_btn.setToolTip("已锁定：点击下方项目和按钮不可操作")
        else:
            self.lock_btn.setText("🔓")
            self.lock_btn.setToolTip("锁定：防止误操作")

        self.tasks_container.setEnabled(not locked)
        self.input.setEnabled(not locked)
        self.add_btn.setEnabled(not locked)

    def _toggle_compact_mode(self):
        self.compact_mode = not self.compact_mode
        self.compact_btn.setChecked(self.compact_mode)

        if self.compact_mode:
            self.body_stack.setCurrentIndex(1)
            self.title_label.hide()
            self.main_layout.setContentsMargins(2, 2, 2, 2)
            self.container.layout().setContentsMargins(4, 4, 4, 4)
            self.setFixedSize(100, 100)
        else:
            self.body_stack.setCurrentIndex(0)
            self.title_label.show()
            self.main_layout.setContentsMargins(8, 8, 8, 8)
            self.container.layout().setContentsMargins(16, 16, 16, 16)
            self.setFixedSize(260, 360)

        self._update_summary()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        margin = 24
        x = geo.right() - self.width() - margin
        y = geo.top() + margin
        self.move(x, y)

    def _add_task(self):
        text = self.input.text().strip()
        if not text:
            return
        self.store.add(text)
        self.input.clear()
        self._reload_tasks()

    def _reload_tasks(self):
        # Remove existing task widgets (keep stretch at end)
        while self.tasks_layout.count() > 1:
            item = self.tasks_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for task in self.store.tasks:
            item = TaskItemWidget(task, self.store, self)
            self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, item)

        self.empty_hint.setVisible(len(self.store.tasks) == 0)
        self._update_summary()
        self._set_locked(self.locked)

    def _update_summary(self):
        total = len(self.store.tasks)
        completed = sum(1 for t in self.store.tasks if t.completed)
        pending = total - completed

        self.summary_label.setText(f"共 {total} 项 · 已完成 {completed} · 待办 {pending}")
        self.compact_count.setText(str(pending))
        self.tray_icon.setIcon(self._create_tray_icon(pending))
        self.tray_icon.setToolTip(f"任务清单\n待办: {pending} 项\n已完成: {completed} 项")

    # Mouse dragging support
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drag_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(exit_action)
        menu.exec(event.globalPos())


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)

    widget = TaskWidget()
    widget.show()

    test_mode = "--test" in sys.argv
    if test_mode:
        QTimer.singleShot(3000, app.quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
