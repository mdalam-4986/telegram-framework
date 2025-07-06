# telegram-framework
Simple, codeless bot creation tool for Telegram with testing and a script for deployment included. Ensure you run this in a fresh directory.

# 📦 Telegram Bot Framework with Visual Menu Builder

An advanced yet intuitive **Telegram Bot Menu Builder with Visual Editor**.  
Design your bot’s nested inline keyboards visually with draggable boxes, links, formatting, media support, and more.

---

## 🚀 Features
✅ Drag & drop visual editor  
✅ Link menu boxes by dragging  
✅ Edit folder name (internal ID), button text, description, media per box  
✅ Supports Markdown formatting:  
   - `*bold*`, `_italic_`, `~strike~`, `` `mono` ``, `>quote`, `||spoiler||`  
✅ Optional media (image/video) per menu node  
✅ Fully interactive right-panel editor with tooltips  
✅ Dynamic box sizes to fit content  
✅ Save & load project automatically (`root-menu/`)  
✅ Persist Telegram Bot API key securely (`config.py`)  
✅ Help dialog with detailed guidance  
✅ All elements annotated with hoverable tooltips  

---

## 🛠 Requirements
- Python ≥ 3.9

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 📖 Quick Start Guide

### 🖥️ 1. Launch the Visual Editor
```bash
python3 main.py
```

### 🔑 2. Set Up the Bot API Key
- In the toolbar, click `🔑 API Key`.
- Enter the token from @BotFather.
- It is Saved securely in `config.py`.

---

## 🐣 Creating a Basic Bot (Flat Menu)

### ➕ 3. Add a Menu Box
- Click `+ Add Box`.
- Select the box.
- Fill out:
  - **Folder Name**: Unique internal ID (default is random but editable)
  - **Button Label**: What users see
  - **Description**: Markdown text: `*bold*`, `_italic_`, `~strike~`, etc.
  - **Media Path**: Optional

Click `Apply Changes`.

---

### 💾 4. Save
- Click `💾 Save` to write `root-menu/`.

---

### ▶️ 5. Run the Bot
- In the editor, click `▶️ Start Bot` to test live.
- Start chatting in Telegram and type `/start`.

---

## 🌲 Creating a Nested Bot (Multi-Level Menus)

### ➕➕ 6. Add More Boxes
- Create more boxes for submenus.
- Fill in each as above.

### 🔗 7. Link Boxes
- Drag the **blue dot** from one box and drop onto another to link them.

---

### 💾 8. Save & Test
- Save your project (`💾 Save`).
- Run (`▶️ Start Bot`) and navigate through menus.

---

## 🚀 Deployment
When ready to deploy production bot:
- Run the future deployment script:
```bash
python3 deploy_bot.py
```
(This keeps the bot running without the GUI. The deployment script will be created later.)

You can keep editing with `main.py` to update `root-menu/` and restart the deployment bot.

---

## 📂 Project Structure
- `main.py` – Visual editor & testing.
- `deploy_bot.py` – Production bot runner for when you want to turn it into a production-level bot.
- `config.py` – Stores API key.
- `root-menu/` – Your menu definitions.
- `requirements.txt` – Python dependencies.
Ensure that when deploying onto a server, the root-menu folder with its contents and deploy_bot.py are in the same directory; with deploy_bot.py being the file to always be ran by the server.
---

## 📦 requirements.txt
```
PyYAML
telebot
PyQt6
```

---

Enjoy building your bots visually! 🚀  
For questions, open an issue or check the help dialog (`ℹ️ Help`) in the app.
