import os
import shutil
import base64
import time
import logging
from telebot import types
from loader import bot, USER_STATE, db_manager, lang_manager, logger
from config import States, DOWNLOADS_DIR, MAX_FILE_SIZE
from encryption import aes_cipher, rsa_cipher, ecc_cipher
from utils import file_manager, crypto_utils

try:
    import pyzipper
except ImportError:
    pyzipper = None

# --- Helpers ---
# --- Helpers ---
def secure_delete(path):
    if os.path.isfile(path):
        try:
            length = os.path.getsize(path)
            with open(path, "wb") as f:
                f.write(os.urandom(length))
        except: pass
        os.remove(path)

def cleanup(path):
    if os.path.exists(path):
        if os.path.isfile(path): secure_delete(path)
        else: shutil.rmtree(path, ignore_errors=True)
    
    dir_path = os.path.dirname(path)
    if os.path.exists(dir_path) and "downloads" in dir_path:
        shutil.rmtree(dir_path, ignore_errors=True)

# --- Handlers ---

@bot.callback_query_handler(func=lambda call: call.data in ["AES", "RSA", "ECC"])
def algo_callback(call):
    user_id = call.from_user.id
    choice = call.data
    
    state_data = USER_STATE.get(user_id, {})
    pending = state_data.get("pending_file")
    
    if pending:
        file_id, file_name, file_size = pending
        USER_STATE[user_id].update({"state": States.WAIT_FILE_ENCRYPT, "algo": choice})
        
        # Manually trigger download flow
        # We simulate a message object or just call the download part
        # Better: just update state and call a helper
        lang = db_manager.get_user_language(user_id)
        bot.edit_message_text(lang_manager.get_text(lang, 'algo_selected', algo=choice), call.message.chat.id, call.message.message_id)
        
        # Process download
        bot.send_message(call.message.chat.id, "📥 Downloading...")
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        
        download_dir = os.path.join(DOWNLOADS_DIR, str(user_id))
        os.makedirs(download_dir, exist_ok=True)
        file_path = os.path.join(download_dir, file_name)
        with open(file_path, 'wb') as f: f.write(downloaded)
        
        USER_STATE[user_id].update({
            "file_path": file_path,
            "original_name": file_name,
            "state": States.WAIT_RECIPIENT_TYPE
        })
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'btn_recipient_me'), callback_data="RECIPIENT_ME"))
        
        recent = USER_STATE[user_id].get("recent_recipient")
        if recent:
            markup.add(types.InlineKeyboardButton(f"👤 {recent['name']} uchun", callback_data=f"RECIPIENT_RECENT_{recent['id']}"))
            
        markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'btn_recipient_other'), callback_data="RECIPIENT_OTHER"))
        bot.send_message(call.message.chat.id, lang_manager.get_text(lang, 'select_recipient_type'), reply_markup=markup, parse_mode="Markdown")
        return
    
    USER_STATE[user_id] = {"state": States.WAIT_FILE_ENCRYPT, "algo": choice}
    lang = db_manager.get_user_language(user_id)
    bot.edit_message_text(
        chat_id=call.message.chat.id, 
        message_id=call.message.message_id, 
        text=lang_manager.get_text(lang, 'algo_selected', algo=choice),
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['document', 'photo'])
def handle_files(message):
    user_id = message.from_user.id
    state_data = USER_STATE.get(user_id, {"state": States.IDLE})
    state = state_data.get("state")
    
    if db_manager.is_blocked(user_id): return
    if state == States.ADMIN_BROADCAST: return # Handled in admin.py

    try:
        # 1. Info Extraction
        if message.content_type == 'document':
            file_id = message.document.file_id
            file_name = message.document.file_name
            file_size = message.document.file_size
        elif message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            file_name = f"photo_{file_id[:10]}.jpg"
            file_size = message.photo[-1].file_size
        else: return

        # 2. Check Size
        if file_size and file_size > MAX_FILE_SIZE:
            lang = db_manager.get_user_language(user_id)
            size_mb = file_size / (1024 * 1024)
            bot.send_message(message.chat.id, lang_manager.get_text(lang, 'file_too_large', size=f"{size_mb:.1f}"))
            return

        # 3. Smart Flow Detection (If IDLE)
        if state == States.IDLE:
            if file_name.endswith('.zip'):
                state = States.WAIT_FILE_DECRYPT
                USER_STATE[user_id] = {"state": state}
            else:
                lang = db_manager.get_user_language(user_id)
                USER_STATE[user_id] = {"state": States.WAIT_ALGO, "pending_file": (file_id, file_name, file_size)}
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_aes'), callback_data="AES"))
                markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_rsa'), callback_data="RSA"))
                markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'algo_ecc'), callback_data="ECC"))
                bot.send_message(message.chat.id, lang_manager.get_text(lang, 'choose_algorithm'), reply_markup=markup, parse_mode="Markdown")
                return

        # 4. Encryption Flow Logic
        if state == States.WAIT_FILE_ENCRYPT:
            bot.send_message(message.chat.id, "📥 Downloading...")
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            download_dir = os.path.join(DOWNLOADS_DIR, str(user_id))
            os.makedirs(download_dir, exist_ok=True)
            file_path = os.path.join(download_dir, file_name)
            
            with open(file_path, 'wb') as f: f.write(downloaded_file)
            
            USER_STATE[user_id].update({
                "file_path": file_path,
                "original_name": file_name,
                "state": States.WAIT_RECIPIENT_TYPE
            })
            
            lang = db_manager.get_user_language(user_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'btn_recipient_me'), callback_data="RECIPIENT_ME"))
            markup.add(types.InlineKeyboardButton(lang_manager.get_text(lang, 'btn_recipient_other'), callback_data="RECIPIENT_OTHER"))
            
            bot.send_message(message.chat.id, lang_manager.get_text(lang, 'select_recipient_type'), reply_markup=markup, parse_mode="Markdown")

        # 5. Decryption Flow Logic
        elif state == States.WAIT_FILE_DECRYPT:
            if not file_name.endswith('.zip'):
                bot.send_message(message.chat.id, "⚠️ Only .zip files!")
                return
            
            bot.send_message(message.chat.id, "📥 Downloading ZIP...")
            file_info = bot.get_file(file_id)
            downloaded = bot.download_file(file_info.file_path)
            
            download_dir = os.path.join(DOWNLOADS_DIR, str(user_id) + "_dec")
            os.makedirs(download_dir, exist_ok=True)
            zip_path = os.path.join(download_dir, file_name)
            with open(zip_path, 'wb') as f: f.write(downloaded)
            
            extract_dir = os.path.join(download_dir, "extracted")
            if os.path.exists(extract_dir): shutil.rmtree(extract_dir)

            if not pyzipper:
                bot.send_message(message.chat.id, "❌ Server Error: pyzipper missing.")
                return

            lang = db_manager.get_user_language(user_id)
            USER_STATE[user_id] = {
                "state": States.WAIT_PASSWORD_DECRYPT, 
                "zip_path": zip_path, 
                "extract_dir": extract_dir,
                "attempts": 0
            }
            bot.send_message(message.chat.id, lang_manager.get_text(lang, 'file_protected'), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"File handle error: {e}")
        bot.send_message(message.chat.id, "❌ Error occurred.")

@bot.callback_query_handler(func=lambda call: call.data in ["RECIPIENT_ME", "RECIPIENT_OTHER"] or call.data.startswith("RECIPIENT_RECENT_"))
def recipient_type_callback(call):
    user_id = call.from_user.id
    choice = call.data
    lang = db_manager.get_user_language(user_id)
    
    if choice == "RECIPIENT_ME":
        USER_STATE[user_id]["recipient_id"] = user_id
        USER_STATE[user_id]["state"] = States.WAIT_PASSWORD_ENCRYPT
        bot.edit_message_text(lang_manager.get_text(lang, 'enter_password'), call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    elif choice.startswith("RECIPIENT_RECENT_"):
        target_id = int(choice.split("_")[2])
        USER_STATE[user_id]["recipient_id"] = target_id
        USER_STATE[user_id]["state"] = States.WAIT_PASSWORD_ENCRYPT
        bot.edit_message_text(lang_manager.get_text(lang, 'enter_password'), call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        bot.send_message(call.message.chat.id, f"✅ Target: `{target_id}`")
    else:
        USER_STATE[user_id]["state"] = States.WAIT_RECIPIENT_ID
        bot.edit_message_text(lang_manager.get_text(lang, 'enter_recipient_id'), call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id, {}).get("state") == States.WAIT_RECIPIENT_ID)
def handle_recipient_id(message):
    user_id = message.from_user.id
    lang = db_manager.get_user_language(user_id)
    
    target_id = None
    name = "User"
    if message.forward_from:
        target_id = message.forward_from.id
        name = message.forward_from.first_name
    elif message.text and message.text.isdigit():
        target_id = int(message.text)
        name = f"ID: {target_id}"

    if target_id:
        USER_STATE[user_id]["recipient_id"] = target_id
        USER_STATE[user_id]["state"] = States.WAIT_PASSWORD_ENCRYPT
        bot.send_message(message.chat.id, lang_manager.get_text(lang, 'recipient_selected', name=name, id=target_id), parse_mode="Markdown")
        bot.send_message(message.chat.id, lang_manager.get_text(lang, 'enter_password'), parse_mode="Markdown")
    elif message.forward_sender_name:
        bot.send_message(message.chat.id, f"⚠️ **Xavfsizlik cheklovi:**\n\nFoydalanuvchi ({message.forward_sender_name}) o'z ID-sini yashirib qo'ygan. \n\nIltimos, undan o'z ID-sini so'rab oling va menga raqam ko'rinishida yuboring.", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID. Iltimos, raqam kiriting yoki do'stingizning xabarini yo'llang.")

@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id, {}).get("state") == States.WAIT_PASSWORD_ENCRYPT)
def handle_enc_password(message):
    user_id = message.from_user.id
    password = message.text.strip()
    state_data = USER_STATE.get(user_id)
    lang = db_manager.get_user_language(user_id)

    # Password Policy
    if len(password) < 8 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        bot.send_message(message.chat.id, lang_manager.get_text(lang, 'password_weak'), parse_mode="Markdown")
        return

    progress_msg = bot.send_message(message.chat.id, "⏳ 0% [░░░░░░░░░░]")
    
    try:
        # Animation
        for i in range(1, 4):
            time.sleep(0.2)
            bars = "█" * (i*3) + "░" * (10 - i*3)
            try: bot.edit_message_text(f"⏳ {i*30}% [{bars}]", message.chat.id, progress_msg.message_id)
            except: pass
        
        bot.edit_message_text(lang_manager.get_text(lang, 'encrypting'), message.chat.id, progress_msg.message_id)

        algo = state_data["algo"]
        file_path = state_data["file_path"]
        orig_name = state_data["original_name"]

        if algo == "AES": process_aes(message, state_data, password)
        elif algo == "RSA": process_rsa(message, state_data, password)
        elif algo == "ECC": process_ecc(message, state_data, password)
        
        db_manager.increment_stats(user_id, "encrypt")
        db_manager.add_file_history(user_id, orig_name, algo, "encrypt")
        USER_STATE[user_id]["last_password"] = password

        try: bot.delete_message(message.chat.id, progress_msg.message_id)
        except: pass
        
        bot.send_message(message.chat.id, "💡 Use /qrcode to get a QR code for your password.")

    except Exception as e:
        logger.error(f"Enc Error: {e}")
        bot.send_message(message.chat.id, f"❌ Error: {e}")
    finally:
        cleanup(state_data["file_path"])
        USER_STATE[user_id]["state"] = States.IDLE

@bot.message_handler(func=lambda m: USER_STATE.get(m.from_user.id, {}).get("state") == States.WAIT_PASSWORD_DECRYPT)
def handle_dec_password(message):
    user_id = message.from_user.id
    password = message.text.strip()
    state_data = USER_STATE.get(user_id)
    zip_path = state_data["zip_path"]
    extract_dir = state_data["extract_dir"]
    attempts = state_data.get("attempts", 0)
    lang = db_manager.get_user_language(user_id)

    bot.send_message(message.chat.id, lang_manager.get_text(lang, 'decrypting'))
    
    try:
        process_decryption_final(message, zip_path, extract_dir, password)
        cleanup(zip_path)
        USER_STATE[user_id] = {"state": States.IDLE}
    except ValueError:
        attempts += 1
        USER_STATE[user_id]["attempts"] = attempts
        if attempts < 3:
            bot.send_message(message.chat.id, lang_manager.get_text(lang, 'password_incorrect', attempts=attempts))
        else:
            bot.send_message(message.chat.id, lang_manager.get_text(lang, 'too_many_attempts'))
            cleanup(zip_path)
            USER_STATE[user_id] = {"state": States.IDLE}
    except Exception as e:
        logger.error(f"Dec Error: {e}")
        bot.send_message(message.chat.id, f"Error: {e}")
        cleanup(zip_path)
        USER_STATE[user_id] = {"state": States.IDLE}

# --- Logic Functions ---

def process_aes(message, state_data, password):
    from config import BOT_SECRET
    file_path, orig_name, recipient_id = state_data["file_path"], state_data["original_name"], state_data["recipient_id"]
    
    data = file_manager.read_file(file_path)
    aes_key = aes_cipher.generate_aes_key()
    nonce, ciphertext, tag = aes_cipher.encrypt_aes(data, aes_key)
    
    salt, pnonce, enc_aes_key, ptag = crypto_utils.encrypt_data_with_password(aes_key, password)
    
    enc_path = file_path + ".enc"
    file_manager.write_file(enc_path, ciphertext)
    
    zip_path = file_path + "_secure.zip"
    meta = {
        "nonce": nonce, "tag": tag, "algo": b"AES", 
        "filename": orig_name.encode(), "salt": salt, 
        "pnonce": pnonce, "ptag": ptag,
        "recipient": str(recipient_id).encode(),
        "signature": BOT_SECRET.encode()
    }
    file_manager.create_secure_zip(zip_path, enc_path, enc_aes_key, meta, password=password)
    
    with open(zip_path, 'rb') as f: 
        bot.send_document(message.chat.id, f, visible_file_name=orig_name+".zip", caption=f"🔐 Locked to: `{recipient_id}`", parse_mode="Markdown")

def process_rsa(message, state_data, password):
    from config import BOT_SECRET
    file_path, orig_name, recipient_id = state_data["file_path"], state_data["original_name"], state_data["recipient_id"]
    
    data = file_manager.read_file(file_path)
    priv, pub = rsa_cipher.generate_rsa_key_pair()
    aes_key = aes_cipher.generate_aes_key()
    nonce, ciphertext, tag = aes_cipher.encrypt_aes(data, aes_key)
    enc_aes_key = rsa_cipher.encrypt_rsa(aes_key, pub)
    
    priv_pem = rsa_cipher.private_key_to_pem(priv)
    salt, pnonce, enc_priv_pem, ptag = crypto_utils.encrypt_data_with_password(priv_pem, password)
    
    enc_path = file_path + ".enc"
    file_manager.write_file(enc_path, ciphertext)
    zip_path = file_path + "_rsa_secure.zip"
    
    meta = {
        "nonce": nonce, "tag": tag, "algo": b"RSA",
        "filename": orig_name.encode(), "enc_priv": enc_priv_pem,
        "salt": salt, "pnonce": pnonce, "ptag": ptag,
        "recipient": str(recipient_id).encode(),
        "signature": BOT_SECRET.encode()
    }
    file_manager.create_secure_zip(zip_path, enc_path, enc_aes_key, meta, password=password)

    with open(zip_path, 'rb') as f:
         bot.send_document(message.chat.id, f, visible_file_name=orig_name+".zip", caption=f"🛡️ RSA Locked: `{recipient_id}`", parse_mode="Markdown")

def process_ecc(message, state_data, password):
    from config import BOT_SECRET
    file_path, orig_name, recipient_id = state_data["file_path"], state_data["original_name"], state_data["recipient_id"]
    
    data = file_manager.read_file(file_path)
    priv, pub = ecc_cipher.generate_ecc_key_pair()
    aes_key = aes_cipher.generate_aes_key()
    f_nonce, f_ciphertext, f_tag = aes_cipher.encrypt_aes(data, aes_key)
    ephem_pub, k_nonce, enc_aes_tag = ecc_cipher.encrypt_ecc_hybrid(aes_key, pub)
    
    from cryptography.hazmat.primitives import serialization
    priv_pem = priv.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption())
    salt, pnonce, enc_priv_pem, ptag = crypto_utils.encrypt_data_with_password(priv_pem, password)
    
    enc_path = file_path + ".enc"
    file_manager.write_file(enc_path, f_ciphertext)
    zip_path = file_path + "_ecc_secure.zip"
    
    meta = {
        "key_nonce": k_nonce, "ephem_pub": ephem_pub,
        "file_nonce": f_nonce, "file_tag": f_tag,
        "algo": b"ECC", "filename": orig_name.encode(),
        "enc_priv": enc_priv_pem, "salt": salt,
        "pnonce": pnonce, "ptag": ptag,
        "recipient": str(recipient_id).encode(),
        "signature": BOT_SECRET.encode()
    }
    file_manager.create_secure_zip(zip_path, enc_path, enc_aes_tag, meta, password=password)

    with open(zip_path, 'rb') as f:
         bot.send_document(message.chat.id, f, visible_file_name=orig_name+".zip", caption=f"🧬 ECC Locked: `{recipient_id}`", parse_mode="Markdown")

def process_decryption_final(message, zip_path, extract_dir, password):
    from config import BOT_SECRET
    extracted = file_manager.extract_secure_zip(zip_path, extract_dir, password)
    
    # Signature Check
    sig_path = os.path.join(extract_dir, "signature.txt")
    if os.path.exists(sig_path):
        with open(sig_path, 'r') as f:
            sig = base64.b64decode(f.read().strip()).decode()
            if sig != BOT_SECRET: raise ValueError("Invalid Bot Signature! This file was not encrypted by this bot version.")
    
    # Recipient Check
    rec_path = os.path.join(extract_dir, "recipient.txt")
    if os.path.exists(rec_path):
        with open(rec_path, 'r') as f:
            locked_id = int(base64.b64decode(f.read().strip()).decode())
    # Signature Check
    sig_path = os.path.join(extract_dir, "signature.txt")
    if os.path.exists(sig_path):
        with open(sig_path, 'r') as f:
            sig_b64 = f.read().strip()
            # Handle if it's already decoded or still b64
            try: sig = base64.b64decode(sig_b64).decode()
            except: sig = sig_b64
            
            if sig != BOT_SECRET: raise ValueError("Invalid Bot Signature! This file was not encrypted by this bot version.")
    
    # Recipient Check
    rec_path = os.path.join(extract_dir, "recipient.txt")
    if os.path.exists(rec_path):
        with open(rec_path, 'r') as f:
            rec_b64 = f.read().strip()
            try: locked_id = int(base64.b64decode(rec_b64).decode())
            except: locked_id = int(rec_b64)
            
            if locked_id != message.from_user.id:
                raise ValueError(f"⛔️ Access Denied! This file is locked to user ID: {locked_id}. You cannot open it.")

    algo_file = os.path.join(extract_dir, "algo.txt")
    if os.path.exists(algo_file):
        with open(algo_file, 'r') as f:
            algo_b64 = f.read().strip()
            try: algo = base64.b64decode(algo_b64).decode()
            except: algo = algo_b64
    else: algo = "AES"

    enc_file = None
    for name in os.listdir(extract_dir):
        if name.endswith(".enc"): enc_file = os.path.join(extract_dir, name); break
    if not enc_file: raise ValueError("No encrypted data found (data.enc missing).")
    
    filename_file = os.path.join(extract_dir, "filename.txt")
    orig_name = "decrypted.file"
    if os.path.exists(filename_file):
        try:
            with open(filename_file, 'r') as f:
                fn_b64 = f.read().strip()
                try: orig_name = base64.b64decode(fn_b64).decode()
                except: orig_name = fn_b64
        except: pass

    decrypted_data = None
    
    def read_b64_file(path):
        with open(path, 'r') as f:
            content = f.read().strip()
            try: return base64.b64decode(content)
            except: return content.encode() # fallback

    if "AES" in algo:
        salt = read_b64_file(os.path.join(extract_dir, "salt.txt"))
        pnonce = read_b64_file(os.path.join(extract_dir, "pnonce.txt"))
        ptag = read_b64_file(os.path.join(extract_dir, "ptag.txt"))
        enc_key = read_b64_file(os.path.join(extract_dir, "key.txt"))
        
        aes_key = crypto_utils.decrypt_data_with_password(salt, pnonce, enc_key, ptag, password)
        
        nonce = read_b64_file(os.path.join(extract_dir, "nonce.txt"))
        tag = read_b64_file(os.path.join(extract_dir, "tag.txt"))
        enc_data = file_manager.read_file(enc_file)
        decrypted_data = aes_cipher.decrypt_aes(nonce, enc_data, tag, aes_key)
        
    elif "RSA" in algo:
        salt = read_b64_file(os.path.join(extract_dir, "salt.txt"))
        pnonce = read_b64_file(os.path.join(extract_dir, "pnonce.txt"))
        ptag = read_b64_file(os.path.join(extract_dir, "ptag.txt"))
        enc_p = read_b64_file(os.path.join(extract_dir, "enc_priv.txt"))
        
        priv_pem_bytes = crypto_utils.decrypt_data_with_password(salt, pnonce, enc_p, ptag, password)

        from cryptography.hazmat.backends import default_backend; from cryptography.hazmat.primitives import serialization
        priv = serialization.load_pem_private_key(priv_pem_bytes, password=None, backend=default_backend())

        enc_aes = read_b64_file(os.path.join(extract_dir,"key.txt"))
        nonce = read_b64_file(os.path.join(extract_dir,"nonce.txt"))
        tag = read_b64_file(os.path.join(extract_dir,"tag.txt"))
        
        aes_key = rsa_cipher.decrypt_rsa(enc_aes, priv)
        enc_data = file_manager.read_file(enc_file)
        decrypted_data = aes_cipher.decrypt_aes(nonce, enc_data, tag, aes_key)
        
    elif "ECC" in algo:
        salt = read_b64_file(os.path.join(extract_dir, "salt.txt"))
        pnonce = read_b64_file(os.path.join(extract_dir, "pnonce.txt"))
        ptag = read_b64_file(os.path.join(extract_dir, "ptag.txt"))
        enc_p = read_b64_file(os.path.join(extract_dir, "enc_priv.txt"))
        
        priv_pem_bytes = crypto_utils.decrypt_data_with_password(salt, pnonce, enc_p, ptag, password)
        
        from cryptography.hazmat.backends import default_backend; from cryptography.hazmat.primitives import serialization
        priv = serialization.load_pem_private_key(priv_pem_bytes, password=None, backend=default_backend())
        
        enc_aes_tag = read_b64_file(os.path.join(extract_dir,"key.txt"))
        key_nonce = read_b64_file(os.path.join(extract_dir,"key_nonce.txt"))
        file_nonce = read_b64_file(os.path.join(extract_dir,"file_nonce.txt"))
        file_tag = read_b64_file(os.path.join(extract_dir,"file_tag.txt"))
        
        # Public key might be stored as PEM string or B64 of PEM
        ep_path = os.path.join(extract_dir,"ephem_pub.txt")
        with open(ep_path, 'r') as f:
            ep_content = f.read().strip()
            try: ephem_pub_bytes = base64.b64decode(ep_content)
            except: ephem_pub_bytes = ep_content.encode()
        
        aes_key = ecc_cipher.decrypt_ecc_hybrid(enc_aes_tag, key_nonce, ephem_pub_bytes, priv)
        enc_data = file_manager.read_file(enc_file)
        decrypted_data = aes_cipher.decrypt_aes(file_nonce, enc_data, file_tag, aes_key)
    
    out_path = os.path.join(extract_dir, orig_name)
    with open(out_path, 'wb') as f: f.write(decrypted_data)
    with open(out_path, 'rb') as f: bot.send_document(message.chat.id, f, caption="🔓 Deshifrlangan fayl!")
