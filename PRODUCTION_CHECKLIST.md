# دليل التجهيز للتشغيل الفعلي (قبل تسليم النظام للدكتور)

هذا الدليل يشرح إزاي تجهز النظام بشكل آمن قبل ما يشتغل عليه فعليًا ببيانات مرضى حقيقية.

---

## 1) أول تشغيل — التجهيز الأساسي

```bash
cd clinic-management-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# انسخ ملف الإعدادات وعدّله
cp .env.example .env
```

افتح ملف `.env` وتأكد إن `FLASK_ENV=production` (مش development). ده أهم سطر في الملف كله —
لو سايبها development أو حذفتها، أي خطأ في الموقع هيظهر لأي حد زايره (زي الصور اللي شفتها قبل كده بالظبط) وده ممكن يكشف تفاصيل حساسة عن السيرفر.

```bash
python seed.py
```

هتظهرلك كلمات مرور عشوائية قوية لحساب الدكتور والموظفين — **اكتبها فورًا في مكان آمن**
(مش على الشاشة، مش في رسالة واتساب عادية). مش هتظهر تاني بعد كده.

---

## 2) غيّر كلمات المرور بعد أول دخول

كل حد (الدكتور والموظفين) لازم يدخل بالباسورد اللي طلع من `seed.py`، وبعدين يروح على:

**"كلمة المرور" (أعلى الصفحة) → يحط باسورد جديد من عنده يعرفه بس هو.**

---

## 3) شغّله بشكل صحيح للإنتاج (مش `python run.py`)

`python run.py` مناسب للتجربة بس على جهازك. للتشغيل الفعلي المستمر، استخدم `gunicorn`
(موجود بالفعل في `requirements.txt`):

```bash
gunicorn -w 4 -b 127.0.0.1:8000 run:app
```

ده بيشغل السيرفر بشكل أقوى وأكثر استقرارًا، وبيربطه بس على الجهاز نفسه (`127.0.0.1`)
مش على الإنترنت مباشرة — وده مقصود، لأن اللي هيكشفه للإنترنت هو نظام تاني قدامه (nginx) في الخطوة الجاية.

### خليه يشتغل تلقائي حتى لو السيرفر اترستارت (systemd)

اعمل ملف `/etc/systemd/system/clinic.service`:

```ini
[Unit]
Description=Al Faidy Clinic System
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/clinic-management-system
Environment="FLASK_ENV=production"
ExecStart=/path/to/clinic-management-system/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable clinic
sudo systemctl start clinic
```

---

## 4) حط nginx قدامه مع شهادة SSL (HTTPS)

بيانات المرضى (أسماء، أرقام موبايل، تشخيصات) لازم متتبعتش على الإنترنت من غير تشفير.
لو الموقع هيتفتح من برا الشبكة المحلية للعيادة، **HTTPS إجباري مش اختياري**.

مثال إعداد nginx بسيط (`/etc/nginx/sites-available/clinic`):

```nginx
server {
    listen 80;
    server_name your-domain-or-ip;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 20M;
}
```

وبعدين شهادة مجانية عن طريق Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain
```

**لو النظام هيشتغل جوه شبكة العيادة الداخلية بس (مفيش وصول من الإنترنت أصلًا)**،
الخطوة دي مش ضرورية بنفس الإلحاح، لكن لسه الأفضل تستخدم HTTPS حتى لو محلي.

---

## 5) باك أب دوري لقاعدة البيانات

كل بيانات المرضى والمواعيد والروشتات محفوظة في ملف واحد: `clinic.db`.
لو اتمسح أو اتلف الملف ده من غير باك أب، البيانات كلها بتضيع.

مثال: باك أب يومي تلقائي بالـ cron، بيحتفظ بآخر 30 يوم:

```bash
crontab -e
```

ضيف السطر ده:
```
0 3 * * * cp /path/to/clinic-management-system/clinic.db /path/to/backups/clinic-$(date +\%Y\%m\%d).db && find /path/to/backups -name "clinic-*.db" -mtime +30 -delete
```

**الأهم: خزّن نسخة من الباك أب في مكان تاني غير نفس الجهاز** (Google Drive، USB خارجي،
سيرفر تاني) — لو الجهاز نفسه اتسرق أو اتعطل، الباك أب المحلي مش هيفيد.

---

## 6) قايمة تأكيد نهائية قبل التسليم

- [ ] `FLASK_ENV=production` في ملف `.env`
- [ ] شغّلت `python seed.py` وسجّلت الباسوردات في مكان آمن
- [ ] كل مستخدم غيّر الباسورد بتاعه من الافتراضي
- [ ] السيرفر شغال بـ `gunicorn` مش `python run.py`
- [ ] فيه HTTPS (لو النظام متاح من برا الشبكة المحلية)
- [ ] الباك أب اليومي شغال ومتأكد إنه بينسخ فعلاً (جرب استرجاع نسخة تجريبيًا)
- [ ] رقم الواتساب في `.env` (لو هتستخدم ميزة "المواعيد ممتلئة")
- [ ] جرب الحجز والدخول وكل الصفحات مرة أخيرة بعد كل التعديلات دي

---

## ملاحظة عن البيانات الطبية

النظام ده بيخزن بيانات مرضى حساسة (تشخيصات، روشتات، صور أشعة). حسب البلد/الجهة اللي
هتستخدمه، ممكن يكون فيه قوانين خصوصية بيانات صحية لازم تتراعى (زي حماية بيانات المريض،
موافقته على تخزين بياناته، من له صلاحية يشوف إيه). ده جانب قانوني مش تقني، يفضل تتأكد
منه مع الدكتور قبل التشغيل الفعلي.
