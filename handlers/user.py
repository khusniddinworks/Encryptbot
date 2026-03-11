import os
from telebot import types
from loader import bot, USER_STATE, db_manager, lang_manager
from config import States, ASSETS_DIR
from utils import qr_manager


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    
    # Check if blocked
    if db_manager.is_blocked(user.id):
        lang = db_manager.get_user_language(user.id)
        bot.send_message(message.chat.id, lang_manager.get_text(lang, 'blocked_user'))
        return
    
    db_manager.add_user(user.id, user.username, user.first_name, user.last_name)
    
    USER_STATE[message.from_user.id] = {"state": States.IDLE}
    lang = db_manager.get_user_language(user.id)
    
    # Clean up old keyboards
    try:
        tmp = bot.send_message(message.chat.id, "...", reply_markup=types.ReplyKeyboardRemove())
        bot.delete_message(message.chat.id, tmp.message_id)
    except: pass

    banner_path = os.path.join(ASSETS_DIR, "banner.png")
    
    # Professional Inline Keyboard
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_enc = types.InlineKeyboardButton("🔒 " + lang_manager.get_text(lang, 'btn_encrypt'), callback_data="MENU_ENCRYPT")
    btn_dec = types.InlineKeyboardButton("🔓 " + lang_manager.get_text(lang, 'btn_decrypt'), callback_data="MENU_DECRYPT")
    
    btn_help = types.InlineKeyboardButton("📚Help", callback_data="MENU_HELP")
    btn_lang = types.InlineKeyboardButton("🌐 Language", callback_data="MENU_LANG")
    
    markup.add(btn_enc, btn_dec)
    markup.add(btn_help, btn_lang)

    # Persistent Reply Keyboard (Menus area)
    reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    re_btn_enc = types.KeyboardButton("🔒 " + lang_manager.get_text(lang, 'btn_encrypt'))
    re_btn_dec = types.KeyboardButton("🔓 " + lang_manager.get_text(lang, 'btn_decrypt'))
    re_btn_hist = types.KeyboardButton("📜 History")
    re_btn_help = types.KeyboardButton("📚 Help")
    
    reply_markup.add(re_btn_enc, re_btn_dec)
    reply_markup.add(re_btn_hist, re_btn_help)
    
    caption = lang_manager.get_text(lang, 'welcome')
    
    # 1. Activate Persistent Menu (Reply Keyboard)
    bot.send_message(message.chat.id, "👇", reply_markup=reply_markup)
    
    # 2. Send Beautiful Banner with Actions (Inline Keyboard)
    if os.path.exists(banner_path):
        with open(banner_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")
    
    bot.send_message(message.chat.id, f"🆔 Your ID: `{user.id}`\nUse this ID to receive secure files.", parse_mode="Markdown")

@bot.message_handler(commands=['id', 'myid'])
def get_my_id(message):
    lang = db_manager.get_user_language(message.from_user.id)
    bot.reply_to(message, f"🆔 Your ID: `{message.from_user.id}`\nShare this ID with the sender.", parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def send_help(message):
    if db_manager.is_blocked(message.from_user.id): return
    lang = db_manager.get_user_language(message.from_user.id)
    bot.send_message(message.chat.id, lang_manager.get_text(lang, 'help_text'), parse_mode="Markdown")

@bot.message_handler(commands=['language'])
def language_menu(message):
    if db_manager.is_blocked(message.from_user.id): return
    send_language_selection(message.chat.id, message.from_user.id)

@bot.message_handler(commands=['history'])
def show_history(message):
    if db_manager.is_blocked(message.from_user.id): return
    
    lang = db_manager.get_user_language(message.from_user.id)
    history = db_manager.get_user_file_history(message.from_user.id, limit=10)
    
    if not history:
        bot.send_message(message.chat.id, lang_manager.get_text(lang, 'history_empty'))
        return
    
    text = lang_manager.get_text(lang, 'history_title')
    for idx, (filename, algo, action, timestamp) in enumerate(history, 1):
        action_text = "🔒" if action == "encrypt" else "🔓"
        text += lang_manager.get_text(lang, 'history_item', index=idx, filename=filename, action=action_text, algo=algo, date=timestamp)
        text += "\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['qrcode'])
def qrcode_menu(message):
    if db_manager.is_blocked(message.from_user.id): return
    
    state_data = USER_STATE.get(message.from_user.id, {})
    last_password = state_data.get("last_password")
    
    if not last_password:
        bot.send_message(message.chat.id, "❌ Avval fayl shifrlang.")
        return
    
    lang = db_manager.get_user_language(message.from_user.id)
    qr_image = qr_manager.generate_password_qr(last_password)
    
    bot.send_photo(message.chat.id, qr_image, caption=lang_manager.get_text(lang, 'qrcode_text'), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("MENU_"))
def menu_callback(call):
    user_id = call.from_user.id
    action = call.data.split("_")[1]
    
    if db_manager.is_blocked(user_id): return

    lang = db_manager.get_user_language(user_id)
    
    if action == "ENCRYPT":
        USER_STATE[user_id] = {"state": States.WAIT_ALGO}
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_aes'), callback_data="AES"))
        markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_rsa'), callback_data="RSA"))
        markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_ecc'), callback_data="ECC"))
        
        bot.send_message(call.message.chat.id, lang_manager.get_text(lang, 'choose_algorithm'), reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        
    elif action == "DECRYPT":
        USER_STATE[user_id] = {"state": States.WAIT_FILE_DECRYPT}
        bot.send_message(call.message.chat.id, lang_manager.get_text(lang, 'send_file_decrypt'))
        bot.answer_callback_query(call.id)
        
    elif action == "HELP":
        bot.send_message(call.message.chat.id, lang_manager.get_text(lang, 'help_text'), parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        
    elif action == "LANG":
        send_language_selection(call.message.chat.id, user_id)
        bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def language_callback(call):
    if db_manager.is_blocked(call.from_user.id): return
    
    lang_code = call.data.split("_")[1]
    db_manager.set_user_language(call.from_user.id, lang_code)
    
    lang_names = {'uz': '🇺🇿 O\'zbek', 'en': '🇬🇧 English', 'ru': '🇷🇺 Русский'}
    bot.answer_callback_query(call.id, "✅ OK")
    bot.edit_message_text(
        lang_manager.get_text(lang_code, 'language_changed', language=lang_names.get(lang_code, lang_code)),
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

def send_language_selection(chat_id, user_id):
    lang = db_manager.get_user_language(user_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang_uz"))
    markup.add(types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"))
    markup.add(types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"))
    
    bot.send_message(chat_id, lang_manager.get_text(lang, 'language_select'), reply_markup=markup, parse_mode="Markdown")

# --- Reply Keyboard Handlers ---

@bot.message_handler(func=lambda m: m.text and ("🔒" in m.text or "Encrypt" in m.text or "Shifrlash" in m.text or "Зашифровать" in m.text))
def reply_enc(message):
    lang = db_manager.get_user_language(message.from_user.id)
    USER_STATE[message.from_user.id] = {"state": States.WAIT_ALGO}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_aes'), callback_data="AES"))
    markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_rsa'), callback_data="RSA"))
    markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_ecc'), callback_data="ECC"))
    
    bot.send_message(message.chat.id, lang_manager.get_text(lang, 'choose_algorithm'), reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and ("🔓" in m.text or "Decrypt" in m.text or "Deshifrlash" in m.text or "Расшифровать" in m.text))
def reply_dec(message):
    lang = db_manager.get_user_language(message.from_user.id)
    USER_STATE[message.from_user.id] = {"state": States.WAIT_FILE_DECRYPT}
    bot.send_message(message.chat.id, lang_manager.get_text(lang, 'send_file_decrypt'))

@bot.message_handler(func=lambda m: m.text and ("📜" in m.text or "History" in m.text))
def reply_hist(message):
    show_history(message)

@bot.message_handler(func=lambda m: m.text and ("📚" in m.text or "Help" in m.text))
def reply_help(message):
    send_help(message)

@bot.message_handler(func=lambda m: (m.forward_from or m.forward_sender_name) and USER_STATE.get(m.from_user.id, {}).get("state") == States.IDLE)
def handle_forward_idle(message):
    if db_manager.is_blocked(message.from_user.id): return
    
    if message.forward_from:
        target_id = message.forward_from.id
        name = message.forward_from.first_name
        # Store as recent for easy use
        USER_STATE[message.from_user.id]["recent_recipient"] = {"id": target_id, "name": name}
        bot.reply_to(message, f"🎯 **Foydalanuvchi aniqlandi:** `{target_id}` ({name})\n\nEndi shifrlamoqchi bo'lgan faylingizni yuborsangiz, ushbu foydalanuvchini tanlashingiz mumkin.", parse_mode="Markdown")
    else:
        bot.reply_to(message, "⚠️ Ushbu foydalanuvchi o'z ID-sini yashirgan. Shifrlash uchun uning ID-sini raqam ko'rinishida yozing.")
