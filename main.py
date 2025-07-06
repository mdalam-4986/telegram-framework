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
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setBrush(QBrush(QColor("#cde")))
        self.text = QGraphicsTextItem(self.format_text(), self)
        self.text.setDefaultTextColor(Qt.GlobalColor.black)
        self.text.setPos(10, 10)
        self.link_handle = LinkHandle(self)
        self.adjust_size()
        self.setPos(x, y)

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram Bot Framework")
        self.resize(1400, 800)

        self.bot_token = self.load_bot_token()
        self.main_text = "🚀 Welcome! Use the formatting syntax:\n*bold* _italic_ ~strike~ `mono` >quote ||spoiler||"
        self.scene, self.boxes, self.links = QGraphicsScene(), [], []
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

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

        apply_btn = QPushButton("Apply Changes")
        apply_btn.setToolTip("Save changes made to selected box.")
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
            ("📝 Edit Main Menu", self.edit_main_menu)
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

    def browse_media(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Media", "", "Images/Videos (*.png *.jpg *.mp4)")
        if path: self.media_input.setText(path)

    def show_help(self):
        QMessageBox.information(self, "Help",
            "📖 How to use Telegram Bot Framework:\n\n"
            "🖋 Adding Boxes:\n"
            "- Click '+ Add Box' to create a new menu node.\n"
            "- Drag the blue dot to another box to create a link.\n"
            "- Move boxes around freely.\n\n"
            "✏️ Editing Boxes:\n"
            "- Select a box by clicking it.\n"
            "- Edit its folder name (internal), button label, description, and media.\n"
            "- Folder name uniquely identifies this box and is used internally. Change carefully.\n"
            "- Description can use Markdown: *bold*, _italic_, ~strike~, `mono`, >quote, ||spoiler||.\n"
            "- Media path (optional) sends an image/video with the text.\n\n"
            "💾 Saving & Loading:\n"
            "- Always save using '💾 Save' before exiting. All positions, links, and data are saved.\n"
            "- On restart, the framework loads all saved data automatically.\n\n"
            "🚀 Starting the Bot:\n"
            "- Set your Telegram bot API key using '🔑 API Key' if not set yet.\n"
            "- Click '▶️ Start Bot' to begin polling.\n"
            "- The bot uses your boxes and links to build menus and respond to clicks.\n\n"
            "📄 Other Notes:\n"
            "- Main Menu text can be customized with '📝 Edit Main Menu'.\n"
            "- Blue link handle shows a tooltip.\n"
            "- Hover over all inputs/buttons for quick tooltips.\n"
            "- Always keep folder names unique.\n"
        )


    def on_selection(self):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], RoundedBoxItem):
            b = items[0]
            self.current_box = b
            self.folder_input.setText(b.folder_name)
            self.button_input.setText(b.button_name)
            self.desc_input.setText(b.description)
            self.media_input.setText(b.media)

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
            self.view.viewport().unsetCursor()
        QGraphicsScene.mouseReleaseEvent(self.scene, event)

    def update_arrows(self):
        for link in self.links:
            link.update_position()
        if self.temp_arrow and self.link_origin:
            pos = self.view.mapToScene(self.view.mapFromGlobal(QCursor.pos()))
            self.temp_arrow.setLine(QLineF(self.link_origin.sceneBoundingRect().center(), pos))

    def add_box(self):
        folder = f"Box_{uuid.uuid4().hex[:6]}"
        b = RoundedBoxItem(MODULES_PATH / folder, folder, "Description", "", 50, 50, self)
        self.scene.addItem(b)
        self.boxes.append(b)

    def apply_box(self):
        if self.current_box:
            self.current_box.folder_name = self.folder_input.text()
            self.current_box.button_name = self.button_input.text()
            self.current_box.description = self.desc_input.toPlainText()
            self.current_box.media = self.media_input.text()
            self.current_box.update_text()

    def save_all(self):
        if MODULES_PATH.exists():
            shutil.rmtree(MODULES_PATH)
        MODULES_PATH.mkdir()

        def save_box(box, path):
            b_path = path / box.folder_name
            b_path.mkdir()
            children_paths = [l.end_box.path.relative_to(MODULES_PATH).as_posix() for l in self.links if l.start_box == box]
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
            for child in folder.iterdir():
                if child.is_dir():
                    info = yaml.safe_load(open(child / "info.yaml"))
                    lbl, cb = info.get("label", child.name), str(uuid.uuid4())[:8]
                    m.add(telebot.types.InlineKeyboardButton(lbl, callback_data=cb))
                    callback_map[cb] = str(child.relative_to(MODULES_PATH))
            if path:
                m.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="BACK"))
            return m

        @bot.message_handler(commands=["start"])
        def start(m):
            bot.send_message(m.chat.id, self.main_text, reply_markup=build_keyboard())

        @bot.callback_query_handler(func=lambda c: True)
        def cb(call):
            path = callback_map.get(call.data, "")
            folder = None
            desc, media = "", None

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
        if ok: self.main_text = text

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())
