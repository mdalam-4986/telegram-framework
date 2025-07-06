import sys, os, yaml, uuid, shutil, threading, importlib.util
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
import telebot

MODULES_PATH = Path("root-menu")
MODULES_PATH.mkdir(exist_ok=True)
CONFIG_PY = Path("config.py")


class ArrowItem(QGraphicsLineItem):
    def __init__(self, start_box, end_box):
        super().__init__()
        self.start_box, self.end_box = start_box, end_box
        self.setPen(QPen(Qt.GlobalColor.red, 2))
        self.setZValue(-1)
        self.update_position()

    def update_position(self):
        p1c = self.start_box.sceneBoundingRect().center()
        p2c = self.end_box.sceneBoundingRect().center()
        self.setLine(QLineF(p1c, p2c))


class LinkHandle(QGraphicsEllipseItem):
    def __init__(self, parent_box):
        super().__init__(-5, -5, 10, 10, parent_box)
        self.setBrush(Qt.GlobalColor.blue)
        self.setZValue(1)
        self.setToolTip("Drag to create a link from this box to another")

    def mousePressEvent(self, event):
        self.scene().views()[0].window().start_link(self.parentItem())
        event.accept()


class RoundedBoxItem(QGraphicsRectItem):
    def __init__(self, path, label, desc, media, x, y, main):
        super().__init__(0, 0, 200, 150)
        self.path = path
        self.folder_name, self.button_name, self.description, self.media = path.name, label, desc, media
        self.main_win = main
        self.setFlags(
        QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
        QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
        QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
)

        self.setBrush(QBrush(QColor("#cde")))
        self.buttons_per_row = 1  # default
        self.text = QGraphicsTextItem(self.format_text(), self)
        self.text.setDefaultTextColor(Qt.GlobalColor.black)
        self.text.setPos(10, 10)
        self.link_handle = LinkHandle(self)
        self.adjust_size()
        self.setPos(x, y)
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos = value
            grid_size = 10  # same as GridScene
            x = round(new_pos.x() / grid_size) * grid_size
            y = round(new_pos.y() / grid_size) * grid_size
            return QPointF(x, y)
        return super().itemChange(change, value)

    def format_text(self):
        parts = [
            f"Folder: {self.folder_name}",
            f"Button: {self.button_name}",
            f"Desc: {self.description}"
        ]
        if self.media: parts.append("(Has Media)")
        return "\n".join(parts)

    def adjust_size(self):
        self.text.setPlainText(self.format_text())
        doc = QTextDocument()
        doc.setPlainText(self.format_text())
        width = 200
        self.text.setTextWidth(width - 20)
        height = doc.size().height() + 30
        self.setRect(0, 0, width, height)
        self.link_handle.setPos(self.rect().bottomRight() - QPointF(10, 10))

    def update_text(self):
        self.text.setPlainText(self.format_text())
        self.adjust_size()
        self.setToolTip(
            f"Box: {self.button_name}\n"
            f"Folder: {self.folder_name}\n"
            f"Description: {self.description}\n"
            f"Media: {self.media or 'None'}"
        )
class GridScene(QGraphicsScene):
    def __init__(self, grid_size=10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grid_size = grid_size

    def drawBackground(self, painter, rect):
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)

        lines = []
        for x in range(left, int(rect.right()) + self.grid_size, self.grid_size):
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
        for y in range(top, int(rect.bottom()) + self.grid_size, self.grid_size):
            lines.append(QLineF(rect.left(), y, rect.right(), y))

        painter.setPen(QPen(QColor(230, 230, 230), 0))
        painter.drawLines(lines)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram Bot Framework")
        self.resize(1400, 800)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.bot_token = self.load_bot_token()
        self.main_text = "🚀 Welcome! Use the formatting syntax:\n*bold* _italic_ ~strike~ `mono` >quote ||spoiler||"
        self.scene, self.boxes, self.links = QGraphicsScene(), [], []
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Enable cleaner multi-select and panning
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.viewport().installEventFilter(self)
        self._last_mouse_pos = None

        self.undo_stack, self.redo_stack = [], []
        self.copied_boxes_data = []

        self.right_panel = QWidget()
        r_layout = QFormLayout()
        self.folder_input, self.button_input = QLineEdit(), QLineEdit()
        self.desc_input, self.media_input = QTextEdit(), QLineEdit()
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_media)

        media_layout = QHBoxLayout()
        media_layout.addWidget(self.media_input)
        media_layout.addWidget(browse_btn)
        media_container = QWidget()
        media_container.setLayout(media_layout)

        r_layout.addRow(QLabel("Folder Name (internal ID)"), self.folder_input)
        r_layout.addRow(QLabel("Button Label (Telegram)"), self.button_input)
        r_layout.addRow(QLabel("Description (supports formatting)"), self.desc_input)
        r_layout.addRow(QLabel("Media Path (optional)"), media_container)

        self.buttons_per_row_input = QSpinBox()
        self.buttons_per_row_input.setMinimum(1)
        self.buttons_per_row_input.setMaximum(10)
        self.buttons_per_row_input.setValue(1)
        r_layout.addRow(QLabel("Buttons per Row"), self.buttons_per_row_input)


        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self.apply_box)
        r_layout.addWidget(apply_btn)

        help_btn = QPushButton("ℹ️ Help")
        help_btn.clicked.connect(self.show_help)
        r_layout.addWidget(help_btn)

        self.right_panel.setLayout(r_layout)

        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(self.right_panel)
        self.setCentralWidget(splitter)

        tb = QToolBar()
        for text, handler in [
            ("▶️ Start Bot", self.start_bot),
            ("+ Add Box", self.add_box),
            ("💾 Save", self.save_all),
            ("🔑 API Key", self.set_bot_token),
            ("📝 Edit Main Menu", self.edit_main_menu),
            ("↩️ Undo", self.undo),
            ("↪️ Redo", self.redo)
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            tb.addWidget(btn)
        self.addToolBar(tb)

        self.current_box, self.link_origin, self.temp_arrow = None, None, None
        self.scene.selectionChanged.connect(self.on_selection)
        self.scene.mouseReleaseEvent = self.scene_mouse_release
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_arrows)
        self.timer.start(30)

        self.load_existing()
    def eventFilter(self, obj, event):
        if obj is self.view.viewport():
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.MiddleButton:
                self._last_mouse_pos = event.pos()
                self.view.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return True
            elif event.type() == QEvent.Type.MouseMove and self._last_mouse_pos:
                delta = event.pos() - self._last_mouse_pos
                self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().value() - delta.x())
                self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().value() - delta.y())
                self._last_mouse_pos = event.pos()
                event.accept()
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.MiddleButton:
                self._last_mouse_pos = None
                self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_boxes = [item for item in self.scene.selectedItems() if isinstance(item, RoundedBoxItem)]
            if selected_boxes:
                confirm = QMessageBox.question(self, "Confirm Deletion", f"Delete {len(selected_boxes)} selected box(es)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if confirm == QMessageBox.StandardButton.Yes:
                    self.save_undo()
                    for box in selected_boxes:
                        self.delete_box(box)
        elif event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selected()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.paste_copied()
        super().keyPressEvent(event)

    def delete_box(self, box):
        to_remove = []
        for link in self.links:
            if link.start_box == box or link.end_box == box:
                self.scene.removeItem(link)
                to_remove.append(link)
        for link in to_remove:
            self.links.remove(link)
        self.scene.removeItem(box)
        if box in self.boxes:
            self.boxes.remove(box)

    def undo(self):
        if not self.undo_stack: return
        state = self.undo_stack.pop()
        self.redo_stack.append(self.capture_state())
        self.restore_state(state)

    def redo(self):
        if not self.redo_stack: return
        state = self.redo_stack.pop()
        self.undo_stack.append(self.capture_state())
        self.restore_state(state)

    def save_undo(self):
        self.undo_stack.append(self.capture_state())
        self.redo_stack.clear()
    def capture_state(self):
        boxes_data, links_data = [], []
        for b in self.boxes:
            boxes_data.append((
                b.folder_name, b.button_name, b.description, b.media,
                b.scenePos().x(), b.scenePos().y()
            ))
        for l in self.links:
            links_data.append((
                self.boxes.index(l.start_box),
                self.boxes.index(l.end_box)
            ))
        return (boxes_data, links_data)

    def restore_state(self, state):
        boxes_data, links_data = state
        for item in self.boxes + self.links:
            self.scene.removeItem(item)
        self.boxes.clear()
        self.links.clear()
        for folder, label, desc, media, x, y in boxes_data:
            b = RoundedBoxItem(MODULES_PATH / folder, label, desc, media, x, y, self)
            self.scene.addItem(b)
            self.boxes.append(b)
        for start_idx, end_idx in links_data:
            a = ArrowItem(self.boxes[start_idx], self.boxes[end_idx])
            self.scene.addItem(a)
            self.links.append(a)

    def copy_selected(self):
        self.copied_boxes_data = [
            (b.folder_name, b.button_name, b.description, b.media,
             b.scenePos().x(), b.scenePos().y())
            for b in self.scene.selectedItems() if isinstance(b, RoundedBoxItem)
        ]

    def paste_copied(self):
        if not self.copied_boxes_data:
            return
        self.save_undo()
        for data in self.copied_boxes_data:
            folder = f"Box_{uuid.uuid4().hex[:6]}"
            label, desc, media, x, y = data[1], data[2], data[3], data[4]+20, data[5]+20
            b = RoundedBoxItem(MODULES_PATH / folder, label, desc, media, x, y, self)
            self.scene.addItem(b)
            self.boxes.append(b)

    def on_selection(self):
        selected_boxes = [box for box in self.boxes if box.isSelected()]

        if len(selected_boxes) == 1:
            box = selected_boxes[0]
            self.current_box = box
            box.setBrush(QBrush(QColor("#9f9")))

            # Enable UI fields
            self.folder_input.setEnabled(True)
            self.button_input.setEnabled(True)
            self.desc_input.setEnabled(True)
            self.media_input.setEnabled(True)
            self.buttons_per_row_input.setEnabled(True)

            # Populate fields
            self.folder_input.setText(box.folder_name)
            self.button_input.setText(box.button_name)
            self.desc_input.setText(box.description)
            self.media_input.setText(box.media)

            # Read buttons_per_row from parent folder
            info_path = box.path.parent / "info.yaml"
            if info_path.exists():
                info = yaml.safe_load(open(info_path)) or {}
                self.buttons_per_row_input.setValue(info.get("buttons_per_row", 1))
            else:
                self.buttons_per_row_input.setValue(1)

        else:
            self.current_box = None
            # Gray out UI fields when multi-selected or none
            self.folder_input.clear()
            self.button_input.clear()
            self.desc_input.clear()
            self.media_input.clear()
            self.buttons_per_row_input.setValue(1)

            self.folder_input.setEnabled(False)
            self.button_input.setEnabled(False)
            self.desc_input.setEnabled(False)
            self.media_input.setEnabled(False)
            self.buttons_per_row_input.setEnabled(False)

        # Reset brushes
        for box in self.boxes:
            if not box.isSelected():
                box.setBrush(QBrush(QColor("#cde")))


    def browse_media(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Media", "", "Images/Videos (*.png *.jpg *.mp4)")
        if path:
            self.media_input.setText(path)

    def show_help(self):
        QMessageBox.information(self, "Help",
            "📖 How to use Telegram Bot Framework:\n\n"
            "🖋 Adding Boxes:\n"
            "- Click '+ Add Box' to create a new menu node.\n"
            "- Drag the blue dot to another box to create a link.\n"
            "- Use Shift/Ctrl to multi-select and Delete to remove.\n"
            "- Use Ctrl+C / Ctrl+V to copy/paste.\n\n"
            "✏️ Editing Boxes:\n"
            "- Select a box by clicking it.\n"
            "- Edit its folder name (internal), button label, description, and media.\n"
            "- Folder name uniquely identifies this box and is used internally. Change carefully.\n"
            "- Description supports Markdown formatting.\n\n"
            "💾 Saving & Loading:\n"
            "- Always save using '💾 Save' before exiting.\n"
            "- On restart, the framework loads saved data.\n\n"
            "🚀 Starting the Bot:\n"
            "- Set your Telegram bot API key using '🔑 API Key'.\n"
            "- Click '▶️ Start Bot' to begin polling.\n"
        )

    def start_link(self, origin_box):
        self.link_origin = origin_box
        self.temp_arrow = QGraphicsLineItem()
        self.temp_arrow.setPen(QPen(Qt.GlobalColor.darkGray, 1, Qt.PenStyle.DashLine))
        self.scene.addItem(self.temp_arrow)
        self.view.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def scene_mouse_release(self, event):
        if self.link_origin and self.temp_arrow:
            target = None
            for item in self.scene.items(event.scenePos()):
                if isinstance(item, RoundedBoxItem) and item != self.link_origin:
                    target = item
            if target:
                arrow = ArrowItem(self.link_origin, target)
                self.links.append(arrow)
                self.scene.addItem(arrow)
            self.scene.removeItem(self.temp_arrow)
            self.temp_arrow, self.link_origin = None, None
            self.view.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        QGraphicsScene.mouseReleaseEvent(self.scene, event)

    def update_arrows(self):
        for link in self.links:
            link.update_position()
        if self.temp_arrow and self.link_origin:
            pos = self.view.mapToScene(self.view.mapFromGlobal(QCursor.pos()))
            self.temp_arrow.setLine(QLineF(self.link_origin.sceneBoundingRect().center(), pos))

    def add_box(self):
        folder = f"Box_{uuid.uuid4().hex[:6]}"

        # Current center of viewport → scene
        center_in_scene = self.view.mapToScene(self.view.viewport().rect().center())
        x, y = center_in_scene.x(), center_in_scene.y()

        b = RoundedBoxItem(MODULES_PATH / folder, folder, "Description", "", x, y, self)
        self.scene.addItem(b)
        self.boxes.append(b)

        # Optional: center view on new box
        self.view.centerOn(b)


    def apply_box(self):
        if self.current_box:
            # Update current box properties
            self.current_box.folder_name = self.folder_input.text()
            self.current_box.button_name = self.button_input.text()
            self.current_box.description = self.desc_input.toPlainText()
            self.current_box.media = self.media_input.text()
            self.current_box.update_text()

            # Save buttons_per_row in parent folder's info.yaml
            parent_path = self.current_box.path.parent
            parent_info_path = parent_path / "info.yaml"

            # If parent info.yaml exists, merge with old data
            if parent_info_path.exists():
                parent_info = yaml.safe_load(open(parent_info_path)) or {}
            else:
                parent_info = {}

            parent_info["buttons_per_row"] = self.buttons_per_row_input.value()

            yaml.safe_dump(parent_info, open(parent_info_path, "w"))

            # Save current box’s own info.yaml
            box_info_path = self.current_box.path / "info.yaml"
            children_paths = [
                l.end_box.path.relative_to(MODULES_PATH).as_posix()
                for l in self.links if l.start_box == self.current_box
            ]
            pos = self.current_box.scenePos()
            yaml.safe_dump({
                "label": self.current_box.button_name,
                "description": self.current_box.description,
                "media": self.current_box.media,
                "children": children_paths,
                "x": float(pos.x()),
                "y": float(pos.y())
            }, open(box_info_path, "w"))



    def save_all(self):
        if MODULES_PATH.exists():
            shutil.rmtree(MODULES_PATH)
        MODULES_PATH.mkdir()

        def save_box(box, path):
            b_path = path / box.folder_name
            b_path.mkdir()
            children_paths = [l.end_box.path.relative_to(MODULES_PATH).as_posix()
                              for l in self.links if l.start_box == box]
            pos = box.scenePos()
            yaml.safe_dump({
                "label": box.button_name,
                "description": box.description,
                "media": box.media,
                "children": children_paths,
                "x": float(pos.x()),
                "y": float(pos.y())
            }, open(b_path / "info.yaml", "w"))
            for link in [l for l in self.links if l.start_box == box]:
                save_box(link.end_box, b_path)

        for root in [b for b in self.boxes if not any(l.end_box == b for l in self.links)]:
            save_box(root, MODULES_PATH)

    def start_bot(self):
        if not self.bot_token:
            QMessageBox.warning(self, "Error", "API Key not set")
            return
        if hasattr(self, 'bot_thread') and self.bot_thread.is_alive():
            return
        self.bot_thread = threading.Thread(target=self.bot_loop, daemon=True)
        self.bot_thread.start()

    def bot_loop(self):
        bot = telebot.TeleBot(self.bot_token, parse_mode="Markdown")
        callback_map = {}

        def build_keyboard(path=""):
            m = telebot.types.InlineKeyboardMarkup()
            folder = MODULES_PATH / path

            # Read this folder's info.yaml to get buttons_per_row if specified
            info_path = folder / "info.yaml"
            if info_path.exists():
                folder_info = yaml.safe_load(open(info_path))
                per_row = max(1, folder_info.get("buttons_per_row", 1))  # default 1
            else:
                per_row = 1

            # Collect all child buttons
            buttons = []
            for child in sorted(folder.iterdir()):
                if child.is_dir():
                    info = yaml.safe_load(open(child / "info.yaml"))
                    lbl, cb = info.get("label", child.name), str(uuid.uuid4())[:8]
                    btn = telebot.types.InlineKeyboardButton(lbl, callback_data=cb)
                    callback_map[cb] = str(child.relative_to(MODULES_PATH))
                    buttons.append(btn)

            # Cap per_row to number of buttons if fewer
            if len(buttons) < per_row:
                per_row = len(buttons) if buttons else 1

            # Arrange buttons into rows
            for i in range(0, len(buttons), per_row):
                m.row(*buttons[i:i+per_row])

            # Add Back button if not at root
            if path:
                m.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="BACK"))

            return m

        @bot.message_handler(commands=["start"])
        def start(m):
            bot.send_message(m.chat.id, self.main_text, reply_markup=build_keyboard())

        @bot.callback_query_handler(func=lambda c: True)
        def cb(call):
            path = callback_map.get(call.data, "")
            folder, desc, media = None, "", None
            if call.data == "BACK":
                path = ""
                desc = self.main_text
            else:
                folder = MODULES_PATH / path if path else None
                if folder and (folder / "info.yaml").exists():
                    info = yaml.safe_load(open(folder / "info.yaml"))
                    desc, media = info.get("description", ""), info.get("media", "")
                if not desc.strip():
                    desc = self.main_text
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except:
                pass
            if media and Path(media).exists():
                with open(media, "rb") as f:
                    bot.send_photo(call.message.chat.id, f, caption=desc, reply_markup=build_keyboard(path))
            else:
                bot.send_message(call.message.chat.id, desc, reply_markup=build_keyboard(path))
        bot.infinity_polling()

    def edit_main_menu(self):
        text, ok = QInputDialog.getText(self, "Main Menu Text", "Enter main menu text:", text=self.main_text)
        if ok:
            self.main_text = text

    def set_bot_token(self):
        token, ok = QInputDialog.getText(self, "API Key", "Enter Bot API key:", QLineEdit.EchoMode.Password)
        if ok:
            self.bot_token = token
            CONFIG_PY.write_text(f'BOT_TOKEN="{token}"\n')

    def load_bot_token(self):
        if CONFIG_PY.exists():
            spec = importlib.util.spec_from_file_location("config", CONFIG_PY)
            cfg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfg)
            return getattr(cfg, "BOT_TOKEN", None)

    def load_existing(self):
        box_map, children_map = {}, {}
        for info_path in MODULES_PATH.rglob("info.yaml"):
            folder = info_path.parent
            info = yaml.safe_load(open(info_path))
            x, y = info.get("x", 50), info.get("y", 50)
            box = RoundedBoxItem(folder, info.get("label", ""), info.get("description", ""), info.get("media", ""), x, y, self)
            box.buttons_per_row = info.get("buttons_per_row", 1)
            self.scene.addItem(box)
            self.boxes.append(box)
            rel_path = folder.relative_to(MODULES_PATH).as_posix()
            box_map[rel_path] = box
            children_map[rel_path] = info.get("children", [])
        for parent_rel, children_rels in children_map.items():
            parent_box = box_map[parent_rel]
            for child_rel in children_rels:
                if child_rel in box_map:
                    child_box = box_map[child_rel]
                    arrow = ArrowItem(parent_box, child_box)
                    self.links.append(arrow)
                    self.scene.addItem(arrow)
        if self.boxes:
            bounding_rect = self.scene.itemsBoundingRect()
            self.scene.setSceneRect(bounding_rect.adjusted(-500, -500, 500, 500))
            self.view.centerOn(bounding_rect.center())



if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())
