import yaml, uuid, importlib.util
from pathlib import Path
import telebot

MODULES_PATH = Path("root-menu")
CONFIG_PY = Path("config.py")

# Load API key
if not CONFIG_PY.exists():
    raise RuntimeError("config.py with BOT_TOKEN not found. Run main.py first and set your API Key.")
spec = importlib.util.spec_from_file_location("config", CONFIG_PY)
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)
BOT_TOKEN = getattr(cfg, "BOT_TOKEN", None)
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in config.py")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
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

# Load main text
main_text = "🚀 Welcome!"
main_menu_file = MODULES_PATH / "main_menu.txt"
if main_menu_file.exists():
    main_text = main_menu_file.read_text().strip()

@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id, main_text, reply_markup=build_keyboard())

@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    path = callback_map.get(call.data, "")
    folder = None
    desc, media = "", None

    if call.data == "BACK":
        path = ""
        desc = main_text
    else:
        folder = MODULES_PATH / path if path else None
        if folder and (folder / "info.yaml").exists():
            info = yaml.safe_load(open(folder / "info.yaml"))
            desc, media = info.get("description", ""), info.get("media", "")
        if not desc.strip():
            desc = main_text

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    if media and Path(media).exists():
        with open(media, "rb") as f:
            bot.send_photo(call.message.chat.id, f, caption=desc, reply_markup=build_keyboard(path))
    else:
        bot.send_message(call.message.chat.id, desc, reply_markup=build_keyboard(path))

print("[Bot] Starting polling (deployment mode)…")
bot.infinity_polling()
