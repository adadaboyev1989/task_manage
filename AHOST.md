# Topshiriqlar nazorati tizimini aHost'ga joylashtirish

Bu qo'llanma loyihani **ahost.uz**'dagi umumiy (shared) hostingga, cPanel'ning **Setup Python App** vositasi (Passenger) orqali qadam-baqadam joylash uchun.

- **Hosting turi:** Shared hosting + cPanel
- **Ishga tushirish usuli:** Apache + Passenger (WSGI, `a2wsgi` orqali ASGI'dan o'ralgan)
- **Talab qilinadigan Python versiyasi:** 3.11 yoki undan yuqori
- **Taxminiy vaqt:** 30–45 daqiqa

## Boshlashdan oldin kerak bo'ladigan narsalar

- ahost.uz'da faol shared hosting tarifi va unga ulangan domen (yoki subdomen)
- cPanel login ma'lumotlari (ahost.uz shaxsiy kabinetidan olinadi)
- Loyiha kodi GitHub'da: [`adadaboyev1989/task_manage`](https://github.com/adadaboyev1989/task_manage) — productionga chiqarishdan oldin kerakli o'zgarishlar asosiy (`main`) branchga birlashtirilgan bo'lishi kerak
- @BotFather orqali yaratilgan Telegram bot tokeni va uning username'i
- cPanel'da **Terminal** yoki SSH kirish huquqi (VAPID kalit generatsiya qilish va boshlang'ich ma'lumotlarni yuklash uchun kerak bo'ladi)

## Muhim eslatma: bu oddiy PHP saytdan farq qiladi

Bu ilova Python/FastAPI'da yozilgan. Telegram bot **webhook** rejimida ishlaydi — ya'ni alohida fon jarayoni/oqim kerak emas, Telegram yangi xabar kelganda to'g'ridan-to'g'ri saytingizga (`/api/telegram/webhook`) so'rov yuboradi, xuddi oddiy veb-so'rov kabi. Shu sababli Passenger jarayonni "uxlatib qo'yishi" boshqa funksiyalar uchun bo'lgani kabi faqat javob tezligiga ta'sir qiladi, bot butunlay ishdan chiqmaydi.

Server ichida so'rov shunday oqadi:

```
Telegram  →  Apache + Passenger  →  FastAPI ilova  →  SQLite baza + fayllar
Brauzer                              (/api/... va       (data/app.db,
                                      /api/telegram/      uploads/)
                                      webhook)
```

## Joylash qadamlari

### 1. cPanel'da Python ilovasini yarating

cPanel → **Software** bo'limidan **Setup Python App**'ni oching va **Create Application**'ni bosing:

- **Python version:** ro'yxatdagi eng yuqori 3.11+ versiyani tanlang
- **Application root:** masalan `topshiriqlar` (home papkangiz ostida yangi papka bo'ladi)
- **Application URL:** asosiy domeningiz yoki subdomen, URI'ni bo'sh (root, `/`) qoldiring
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `application`

"Create" bosilgach, cPanel ushbu papka ichida virtualenv yaratadi va sahifa yuqorisida "Enter to the virtual environment" buyrug'ini ko'rsatadi — keyingi qadamlarda shu buyruqni ishlatasiz.

### 2. Kodni serverga joylashtiring

Eng qulay yo'l — cPanel'ning **Git™ Version Control** vositasi:

```
cPanel → Git™ Version Control → Create

Clone URL:        https://github.com/adadaboyev1989/task_manage.git
Repository Path:  /home/USERNAME/topshiriqlar   # 1-qadamdagi Application root bilan bir xil
Branch:           main
```

Repository Path 1-qadamda ko'rsatgan Application root bilan aynan bir xil bo'lishi shart. Git mavjud bo'lmasa, kodni ZIP qilib **File Manager → Upload** orqali yuklab, o'sha papkaga "Extract" qilish ham mumkin.

### 3. `passenger_wsgi.py` faylini tekshiring

Passenger aynan shu fayl ichidagi `application` nomli obyektni ishga tushiradi. Loyihada bu fayl allaqachon repo ildizida mavjud:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.main import app as asgi_app
from app import telegram_bot
from a2wsgi import ASGIMiddleware

telegram_bot.start()  # oddiy thread, event loop kerak emas — shu yerda xavfsiz ishga tushadi

application = ASGIMiddleware(asgi_app)
```

FastAPI — ASGI ilova, lekin ahost.uz'dagi cPanel serverlarining ko'pchiligida ishlaydigan Passenger versiyasi ASGI'ni to'g'ridan-to'g'ri qo'llab-quvvatlamaydi (faqat WSGI). Shuning uchun `a2wsgi` kutubxonasi (`requirements.txt`'da bor) ASGI ilovani WSGI'ga o'raydi.

Bitta muhim nuance: FastAPI'ning odatiy `lifespan` mexanizmi (startup/shutdown hodisalari) WSGI orqali ishlaganda chaqirilmaydi — shuning uchun Telegram webhookni ro'yxatdan o'tkazish (`telegram_bot.start()`) shu faylning o'zida, modul yuklanganda to'g'ridan-to'g'ri chaqiriladi. Bu chaqiruv tezkor (fon oqimida, bloklamaydi) va Telegram'ning `setWebhook` so'rovini yuboradi.

`telegram_bot.start()` endi faqat bir martalik ro'yxatdan o'tkazish bo'lgani uchun, agar Passenger yuklama ostida bir nechta worker-jarayon (process) ochsa va har biri shu faylni alohida yuklasa — muammo bo'lmaydi: `setWebhook`ni bir necha marta qayta chaqirish xavfsiz (idempotent), avvalgi "long polling" rejimidagi **409 Conflict** xatosi endi mumkin emas.

### 4. Kutubxonalarni o'rnating

**Setup Python App** sahifasida ilovangizni tanlab, `requirements.txt` yo'lini ko'rsating va **Run Pip Install** tugmasini bosing. Yoki Terminal orqali:

```bash
source /home/USERNAME/virtualenv/topshiriqlar/3.11/bin/activate
cd ~/topshiriqlar
pip install -r requirements.txt
```

### 5. Muhit o'zgaruvchilarini sozlang

**Setup Python App** sahifasidagi **Environment variables** jadvaliga qo'shing (yoki ilova papkasida `.env` fayl yarating — u web orqali ochilmaydi, xavfsiz):

| O'zgaruvchi | Qiymat |
|---|---|
| `ENVIRONMENT` | `production` |
| `APP_URL` | `https://sizning-domeningiz.uz` |
| `JWT_SECRET` | uzun, tasodifiy satr (pastdagi buyruq bilan generatsiya qiling) |
| `BOT_TOKEN` | @BotFather bergan token |
| `BOT_USERNAME` | bot username'i (`@`siz) |
| `VAPID_PUBLIC_KEY` | 6-qadamda generatsiya qilinadi |
| `VAPID_PRIVATE_KEY` | 6-qadamda generatsiya qilinadi |
| `VAPID_SUBJECT` | `mailto:admin@sizning-domeningiz.uz` |

`DB_PATH` va `UPLOAD_DIR`'ni qo'shishning hojati yo'q — ular ilova papkasi ichidagi `data/` va `uploads/`'ga avtomatik yo'naladi.

`JWT_SECRET` generatsiya qilish:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 6. VAPID kalitlari, boshlang'ich ma'lumotlar, super admin

Virtualenv faollashtirilgan holda, ilova papkasida ketma-ket ishga tushiring:

```bash
python scripts/generate_vapid.py     # chiqqan ikki kalitni 5-qadamdagi jadvalga qo'shing
python scripts/seed.py               # namunaviy maktab/bog'cha tashkilotlari
python scripts/create_superadmin.py  # admin panel uchun login-parol chiqaradi — saqlab qo'ying
```

Har bir xodim va direktorning Telegram ID'sini keyinroq `/admin` panel orqali kiritasiz — ular botga `/start` yozganda ID'sini ko'rsatadi.

### 7. Ilovani qayta ishga tushiring

Muhit o'zgaruvchilarini yoki kodni har o'zgartirganingizdan so'ng, **Setup Python App** sahifasida ilovangiz qatoridagi **Restart** tugmasini bosing (yoki ilova papkasida bo'sh `tmp/restart.txt` fayl yarating).

### 8. HTTPS'ni yoqing

cPanel → **SSL/TLS Status**'da domeningiz uchun **AutoSSL**'ni ishga tushiring (odatda ahost.uz'da Let's Encrypt bepul ulanadi). Sertifikat faollashgach, `APP_URL` o'zgaruvchisi `https://` bilan boshlanishiga ishonch hosil qiling — Telegram deep-link va push-bildirishnomalar shunga tayanadi.

### 9. Telegram webhook ro'yxatdan o'tganini tekshiring

7-qadamda **Restart** qilinganda ilova avtomatik ravishda Telegram'ga "menga shu URL orqali xabar yuborib tur" deb bildiradi (webhook ro'yxatdan o'tadi) — qo'lda qiladigan boshqa ish yo'q. Tekshirish uchun (`<BOT_TOKEN>` o'rniga haqiqiy tokeningizni qo'ying):

```bash
curl -s "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

Javobda `"url"` maydoni `https://sizning-domeningiz.uz/api/telegram/webhook` ga teng va `"last_error_message"` bo'sh bo'lishi kerak.

> 💡 Ixtiyoriy: Passenger yuklama bo'lmaganda jarayonni "uxlatib qo'yishi" mumkin, bu birinchi so'rovga sal sekinroq javob berishiga olib kelishi mumkin (lekin Telegram botga ta'sir qilmaydi — webhook so'rovi kelganda jarayon avtomatik uyg'onadi). Buni oldini olish uchun **Cron Jobs**'da har 5 daqiqada ping yuborishni xohlasangiz:
>
> ```
> Cron Jobs → Common Settings: Every 5 minutes
> curl -s -o /dev/null https://sizning-domeningiz.uz/manifest.json
> ```

## Tekshirib ko'ring

- [ ] `https://sizning-domeningiz.uz/login` ochiladi va "Telegram orqali kirish" tugmasi botni ochadi
- [ ] `/admin/login`'ga 6-qadamdagi login-parol bilan kirish ishlaydi
- [ ] Telefonda saytni "Bosh ekranga qo'shish" orqali PWA sifatida o'rnatish mumkin
- [ ] Admin panelda xodimga Telegram ID biriktirilgach, u shu ID orqali tizimga kira oladi

## Muammolarni bartaraf etish

| Belgi | Ehtimoliy sabab va yechim |
|---|---|
| **500 — Internal Server Error** | cPanel → **Errors** bo'limi yoki ilova papkasidagi `stderr.log`'ni oching. Ko'pincha noto'g'ri `passenger_wsgi.py` yoki muhit o'zgaruvchisi yetishmasligi sabab bo'ladi. |
| **ModuleNotFoundError** | Kutubxonalar noto'g'ri virtualenv'ga o'rnatilgan. 4-qadamdagi `activate` buyrug'ini aynan Setup Python App sahifasidan nusxalab ishlating. |
| **502 / Bad Gateway** | Ilova ishga tushmayapti — `passenger_wsgi.py` ildiz papkada ekanini va `application` nomi to'g'ri yozilganini tekshiring, so'ng qayta **Restart** qiling. |
| **Telegram orqali kirish ishlamayapti** | `BOT_TOKEN`/`BOT_USERNAME` to'g'riligini va `APP_URL` aniq `https://` bilan boshlanishini tekshiring (webhook faqat HTTPS bilan ishlaydi). So'ng 9-qadamdagi `getWebhookInfo` buyrug'i bilan tasdiqlang. |
| **Fayl yuklab bo'lmayapti** | `uploads/` va `data/` papkalari ilova foydalanuvchisiga tegishli va yozish huquqiga ega ekanini File Manager'da tekshiring. |
| **Yangi fayl yukladim, lekin saytda hech narsa o'zgarmadi** | 1) Ilovani **Restart** qilishni unutmagansizmi (7-qadam)? Kod o'zgarganda bu shart. 2) Sayt PWA bo'lgani uchun brauzerda "service worker" ishlaydi — telefon/kompyuterda saytni to'liq yopib, keshni tozalab (yoki "Hard refresh": Ctrl+Shift+R) qayta oching. `git pull` orqali eng so'nggi kodni olganingizga ishonch hosil qiling (`git log -1` bilan tekshiring). |
| **Bot sekin yoki umuman javob bermayapti** | 9-qadamdagi `getWebhookInfo` buyrug'ini ishga tushiring — `"last_error_message"` maydoni sababni ko'rsatadi (odatda `APP_URL` https emasligi yoki sertifikat muammosi). Agar bo'sh bo'lsa-yu baribir sekin bo'lsa, ixtiyoriy cron ping (9-qadam) qo'shing. |

## Keyinchalik yangilash

Kodga o'zgartirish kiritilganda:

```bash
cd ~/topshiriqlar
git pull                              # yoki Git Version Control → Manage → Update from Remote
source ~/virtualenv/topshiriqlar/3.11/bin/activate
pip install -r requirements.txt       # faqat requirements.txt o'zgargan bo'lsa
touch tmp/restart.txt                 # yoki Setup Python App'da Restart
```

---

Loyiha: [`adadaboyev1989/task_manage`](https://github.com/adadaboyev1989/task_manage) · Namangan shahar maktabgacha va maktab ta'limi bo'limi
