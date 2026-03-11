# 🔐 EncryptorBot - Professional Secure File Sharing System

Assalomu alaykum! Ushbu loyiha fayllarni maksimal darajada xavfsiz shifrlash va faqat belgilangan inson ocha olishini ta'minlash uchun yaratilgan professional Telegram bot hisoblanadi. 

Loyiha muallifi: **Khusniddin Khamidov**

## 🌟 Asosiy Imkoniyatlar

### 1. 🛡️ Ko'p Bosqichli Shifrlash (Multi-Layer Security)
Bot hozirgi kunda eng kuchli hisoblangan shifrlash algoritmlarini qo'llab-quvvatlaydi:
*   **AES-GCM (256-bit):** High-speed simmetrik shifrlash.
*   **RSA (4096-bit):** Asimmetrik qulflash tizimi.
*   **ECC (Elliptic Curve Cryptography):** Eng zamonaviy va ixcham xavfsizlik standarti.

### 2. 🆔 Foydalanuvchiga Qulflash (Recipient-Locked Encryption)
Bu botning eng kuchli xususiyati. Shifrlangan fayl ichiga **qabul qiluvchining Telegram ID-si** mantiqiy ravishda muhrlanadi. 
*   Faylni shifrlaganingizda uni kim ocha olishini belgilaysiz.
*   Agar fayl boshqa birovning qo'liga tushib qolsa yoki boshqa Telegram akkauntidan ochishga urinsa, bot unga ruxsat bermaydi.

### 3. 🔐 ZIP Arxiv Himoyasi (AES-encrypted ZIP)
Fayl shifrlangandan so'ng u maxsus ZIP arxivga joylanadi.
*   ZIP arxivning o'zi ham siz qo'ygan parol bilan himoyalangan bo'ladi.
*   Arxiv ichidagi barcha metadata (fayl nomi, shifrlash kalitlari) `manifest.json` ichiga berkitilgan va foydalanuvchi ko'zi uchun yopiq.

### 4. 🎯 Smart UX & Forward Detection
*   **Smart Flow:** Botga shunchaki `.zip` yuborsangiz deshifrlashni, boshqa fayl yuborsangiz shifrlashni taklif qiladi.
*   **Auto-detect:** Qabul qiluvchining ID-sini bilish shart emas. Shunchaki uning xabarini botga **Forward** qiling, bot uni taniydi va keyingi shifrlash jarayonida "O'sha odam uchun" degan qulay tugmani chiqaradi.

## 🛠️ Texnologiyalar
*   **Python 3.12+**
*   **PyTelegramBotAPI:** Bot interfeysi uchun.
*   **Cryptography:** Har xil algoritmlar (AES, RSA, ECC) uchun.
*   **Pyzipper:** AES-256 darajasidagi ZIP arxivlash uchun.
*   **SQLite:** Foydalanuvchi bazasi va tarixini saqlash uchun.

