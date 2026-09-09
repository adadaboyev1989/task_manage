# Topshiriqlar nazorati tizimi

Namangan shahar maktabgacha va maktab ta'limi bo'limi uchun topshiriqlar nazorati PWA tizimi.
Bo'lim xodimlari maktab va bog'cha direktorlariga topshiriq beradi, ijrosini kuzatadi va nazoratdan yechadi;
direktorlar o'z tashkilotining topshiriqlarini ko'radi va ma'lumot uchun yuborilganlarni tasdiqlaydi.

## Asosiy imkoniyatlar

- **Telegram bot orqali avtorizatsiya** — parolsiz, faqat Telegram orqali kirish
- Ikki turdagi topshiriq: **ijrosi ta'minlanadigan** (muddat bilan, bo'lim tomonidan nazoratdan yechiladi) va
  **ma'lumot uchun** (direktor "Tushunarli" tugmasini bosishi bilan yopiladi)
- Fayllarni biriktirish, jumladan **Telegramdan forward qilish** orqali
- **PWA**: telefonga ilova sifatida o'rnatish, push-bildirishnomalar
- Har bir yangi topshiriq haqida Telegram va push orqali ogohlantirish
- Direktorlar uchun shaxsiy dashboard, bo'lim xodimlari uchun barcha tashkilotlar bo'yicha umumiy statistika
- Alohida **`/admin`** panel — foydalanuvchilar, tashkilotlar va statistikani boshqarish, **login-parol** bilan
  kirish (Telegram'dan mustaqil)

## Texnologiyalar

Python + FastAPI + SQLite (stdlib `sqlite3`), vanilla HTML/CSS/JS frontend (build qadamisiz — brauzer uchun
alohida til kerak emas), Telegram Bot API (long polling, `requests` bilan alohida oqimda/thread'da), Web Push
(VAPID, `pywebpush`).

## O'rnatish

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 1. Telegram bot yaratish

1. Telegramda [@BotFather](https://t.me/BotFather) bilan suhbat oching.
2. `/newbot` buyrug'ini yuboring, botga nom va username bering (masalan `namangan_toshiriq_bot`).
3. BotFather bergan tokenni va bot username'ini `.env` fayliga yozing:
   ```
   BOT_TOKEN=123456:ABC-...
   BOT_USERNAME=namangan_toshiriq_bot
   ```

Bot sozlanmagan holatda (`BOT_TOKEN` bo'sh) tizim **dasturchi rejimida** ishlaydi: `/login` sahifasida
foydalanuvchini ro'yxatdan tanlab kirish imkoni paydo bo'ladi — bu faqat lokal test uchun, production'da
`BOT_TOKEN` kiritilgach avtomatik o'chadi.

### 2. Push-bildirishnomalar uchun kalitlar

```bash
python scripts/generate_vapid.py
```

Chiqqan `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` qatorlarini `.env` fayliga qo'shing.

Ikonkalar (`public/icons/`) tayyor holda repo ichida saqlangan — qayta generatsiya qilish shart emas.

### 3. Boshlang'ich ma'lumotlar (namunaviy tashkilotlar)

```bash
python scripts/seed.py
```

Bu bitta bo'lim xodimi va ikkita namunaviy tashkilot (maktab/bog'cha, direktorlari bilan) yaratadi — ularning
Telegram ID'si hali bo'sh, `/admin` panel orqali biriktirishingiz kerak (pastdagi "Foydalanuvchi oqimi"ga
qarang). Real muhitda ushbu seed skriptidan keyin namunaviy hisoblarni o'chirib, o'z xodimlaringizni admin
panel orqali kiriting.

### 4. Birinchi administrator (super admin)

Admin panelga kirish uchun avval kamida bitta administrator kerak — buni **login va parol** bilan yaratasiz
(Telegram shart emas, shu bilan tizimni birinchi marta ishga tushirish muammosi hal qilinadi):

```bash
python scripts/create_superadmin.py
# yoki o'z login/parolingiz bilan:
python scripts/create_superadmin.py mening_loginim MeningParolim123
```

Buyruq login va (agar berilmasa, tasodifiy) parolni konsolga bir marta chiqaradi — uni saqlab qo'ying. Keyinroq
shu administrator boshqa admin/bo'lim/direktor hisoblarini `/admin` panel orqali yaratadi.

### 5. Ishga tushirish

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 3000
```

`http://localhost:3000` manzilida ochiladi. `/admin/login` — administrator uchun login-parol bilan kirish
sahifasi. Production'da `--workers` qo'shmang — Telegram bot fonda alohida thread'da ishlaydi va bir nechta
worker jarayoni bir xil botni bir necha marta poll qilib, xabarlarni takrorlab yuborishi mumkin; yuklamani
oshirish kerak bo'lsa, uni bitta jarayon orqasida reverse-proxy (nginx) bilan boshqaring.

## Foydalanuvchi oqimi

Hech kimga kod berilmaydi — admin har bir foydalanuvchining Telegram ID'sini to'g'ridan-to'g'ri kiritadi, tizim
esa botga /start bergan odamni shu ID orqali taniydi:

1. Yangi foydalanuvchi (masalan, maktab direktori) botga (`BOT_USERNAME`) `/start` yozadi. Bot hali tizimda
   yo'qligini aytadi va **uning Telegram ID'sini** ko'rsatadi.
2. Foydalanuvchi shu ID'ni administratorga yetkazadi (telefon qo'ng'irog'i, xabar va h.k.).
3. Admin `/admin` panelda "Yangi foydalanuvchi" orqali ism, rol, tashkilot va **shu Telegram ID**ni kiritib
   hisob yaratadi — hisob darhol faollashadi, qo'shimcha tasdiqlash shart emas.
4. Foydalanuvchi botga qayta `/start` yozadi (yoki saytdagi `/login` sahifasida "Telegram orqali kirish"
   tugmasini bosadi) — tizim uni Telegram ID orqali tanib, avtomatik kiritadi.
5. Telefonda bir marta shu tarzda kirilgach, sessiya brauzerda uzoq muddat (taxminan 400 kun, foydalanish
   davomida avtomatik yangilanib boradi) saqlanadi — foydalanuvchi ilovani qayta ochganda avtorizatsiya
   so'ralmaydi, to'g'ridan-to'g'ri dashboardga kiradi.
6. Bo'lim xodimi topshiriq yaratadi (turi, muddati, qaysi tashkilotlarga), kerak bo'lsa fayl biriktiradi yoki
   Telegramdan forward qiladi.
7. Tegishli direktorlarga Telegram xabari + push-bildirishnoma yuboriladi.
8. Direktor: ma'lumot uchun topshiriqni "Tushunarli" tugmasi bilan yopadi; ijrosi ta'minlanadigan topshiriqni
   bo'lim xodimi tekshirib, nazoratdan yechadi.

Foydalanuvchi telefonini almashtirsa yoki Telegram ID'si o'zgarsa, admin panelda shu hisobning "Telegram ID"
tugmasi orqali yangi ID kiritiladi.

### Administrator uchun login-parol

Administrator roli uchun Telegram shart emas — `/admin/login` sahifasida login va parol bilan ham kirish
mumkin. Har bir administrator hisobiga admin panelda "Login-parol" tugmasi orqali alohida login/parol
o'rnatish yoki almashtirish mumkin (Telegram ID bilan bir vaqtda ham ishlatsa bo'ladi — ikkalasi ham
qo'llab-quvvatlanadi). Noto'g'ri parol bilan 5 marta urinishdan so'ng shu login 15 daqiqaga bloklanadi.

## Muhit o'zgaruvchilari

`.env.example` faylida barcha o'zgaruvchilar va izohlari keltirilgan (`APP_URL`, `JWT_SECRET`, `BOT_TOKEN`,
`VAPID_*` va h.k.). Production uchun `APP_URL` ni haqiqiy HTTPS domenga o'zgartiring — push-bildirishnoma va
Telegramdagi "Saytda ochish" tugmasi shu manzilga ishora qiladi.

## Papkalar

```
app/
  main.py          — FastAPI ilova, static/SPA marshrutlash, /admin qo'riqlash
  db.py            — SQLite sxema (thread-local ulanish)
  security.py      — parol hash (scrypt), JWT sessiya
  deps.py          — auth/rol dependency'lari
  telegram_bot.py  — bot (fon thread'da long polling, login/forward oqimlari, bildirishnomalar)
  push.py          — Web Push (pywebpush)
  datetime_utils.py
  routers/         — auth, tasks, orgs, users, stats, push API
public/
  index.html, login.html, js/app.js  — asosiy ilova (direktor/bo'lim) — Python'dan mustaqil, o'zgarishsiz
  admin/           — /admin paneli
  manifest.json, sw.js, icons/       — PWA
scripts/
  seed.py, generate_vapid.py, create_superadmin.py
```

Frontend (`public/`) oddiy HTML/CSS/JS bo'lgani uchun backend tili almashganda o'zgarishsiz qoladi — brauzer
Python kodini bajarmaydi, u faqat REST API'ga so'rov yuboradi.
