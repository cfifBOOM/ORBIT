"""ORBIT: учебный магазин. Запуск: python app.py."""
import io
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from functools import wraps
from flask import Flask, jsonify, render_template, request, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / '.env')
app = Flask(__name__)
app.config.update(SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=16384, SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE') == '1')
DATA = Path(os.getenv('ORBIT_DATA_DIR', str(ROOT / 'instance')))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'orbit.db'
PRODUCTS = [
    dict(id=1, name='Orbit One', category='Город', color='Лайм', price=8900, stock=24, image='lime'),
    dict(id=2, name='Cloud Runner', category='Бег', color='Лёд', price=11900, stock=16, image='ice'),
    dict(id=3, name='Terra Low', category='Город', color='Песок', price=7900, stock=32, image='sand'),
    dict(id=4, name='Pulse Pro', category='Тренировки', color='Коралл', price=12900, stock=8, image='coral'),
    dict(id=5, name='Night Shift', category='Город', color='Графит', price=9900, stock=12, image='dark'),
    dict(id=6, name='Air Circuit', category='Бег', color='Лайм', price=10900, stock=19, image='lime')]

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,name TEXT,password TEXT);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,user_id INTEGER,body TEXT,created TEXT);
    CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY,email TEXT,body TEXT,created TEXT,status TEXT);''')

def user():
    with db() as c:
        r = c.execute('SELECT id,email,name FROM users WHERE id=?', (session.get('uid'),)).fetchone()
        return dict(r) if r else None

def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not user(): return jsonify(error='Сначала войдите в аккаунт.'), 401
        return f(*a, **kw)
    return wrapped

@app.before_request
def csrf():
    if request.method == 'POST':
        expected = session.get('csrf', '')
        if not expected or not secrets.compare_digest(expected, request.headers.get('X-CSRF-Token', '')):
            return jsonify(error='Обновите страницу и повторите действие.'), 403

@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if request.path.startswith('/api/'): response.headers['Cache-Control'] = 'no-store'
    return response

@app.get('/api/session')
def current():
    session.setdefault('csrf', secrets.token_hex(32))
    return jsonify(user=user(), csrf=session['csrf'])

@app.post('/api/register')
def register():
    d = request.get_json(silent=True) or {}
    name, email = (str(d.get(k, '')).strip() for k in ('name','email'))
    password = str(d.get('password',''))
    email = email.lower()
    if not 2 <= len(name) <= 60 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email)>254 or not 8 <= len(password) <= 128:
        return jsonify(error='Имя: 2–60 символов, корректная почта и пароль от 8 до 128 символов.'), 400
    try:
        with db() as c:
            cur = c.execute('INSERT INTO users(email,name,password) VALUES(?,?,?)', (email,name,generate_password_hash(password)))
            session['uid'] = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error='Такая почта уже зарегистрирована.'), 409
    return jsonify(user=user()), 201

@app.post('/api/login')
def login():
    d = request.get_json(silent=True) or {}
    with db() as c: r = c.execute('SELECT * FROM users WHERE email=?', (str(d.get('email','')).lower().strip(),)).fetchone()
    if not r or not check_password_hash(r['password'], str(d.get('password',''))):
        return jsonify(error='Неверная почта или пароль.'), 401
    session['uid'] = r['id']
    return jsonify(user=user())

@app.post('/api/logout')
def logout():
    session.pop('uid', None)
    return jsonify(ok=True)

def filtered():
    q = request.args.get('q','').lower()[:100]
    category = request.args.get('category','')
    rows = [p for p in PRODUCTS if q in (p['name']+' '+p['category']+' '+p['color']).lower() and (not category or p['category']==category)]
    key = request.args.get('sort','name')
    if key not in ('name','category','color','price','stock'): key='name'
    return sorted(rows, key=lambda p:p[key], reverse=request.args.get('direction')=='desc')

@app.get('/api/products')
def products(): return jsonify(filtered())

@app.get('/api/export/<kind>')
def export(kind):
    rows = [[p[k] for k in ('name','category','color','price','stock')] for p in filtered()]
    headings = ['Модель','Назначение','Цвет','Цена, ₽','В наличии']
    buf = io.BytesIO()
    if kind == 'xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        w=Workbook(); s=w.active; s.title='Каталог ORBIT'; s.append(headings)
        for row in rows: s.append(row)
        for cell in s[1]: cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='202522')
        for col in 'ABCDE': s.column_dimensions[col].width=22
        s.auto_filter.ref=s.dimensions; s.freeze_panes='A2'
        w.save(buf)
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif kind == 'pdf':
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib import colors
        pdfmetrics.registerFont(TTFont('Noto', str(ROOT/'static/fonts/NotoSans.ttf')))
        table=Table([headings]+rows, colWidths=[125,105,85,85,85], repeatRows=1)
        table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Noto'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#c6f35c')),('GRID',(0,0),(-1,-1),.5,colors.lightgrey),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        SimpleDocTemplate(buf).build([Paragraph('ORBIT — каталог кроссовок',ParagraphStyle('title',fontName='Noto',fontSize=20)),Spacer(1,24),table])
        mime='application/pdf'
    else: return jsonify(error='Неизвестный формат.'),404
    buf.seek(0)
    return send_file(buf,mimetype=mime,as_attachment=True,download_name='orbit-catalog.'+kind)

@app.get('/api/qr')
def qr():
    import qrcode
    buf=io.BytesIO(); qrcode.make(os.getenv('PUBLIC_URL','http://127.0.0.1:5000')+'/catalog').save(buf,format='PNG'); buf.seek(0)
    return send_file(buf,mimetype='image/png')

@app.route('/api/messages', methods=['GET','POST'])
def messages():
    if request.method=='POST':
        u=user()
        if not u: return jsonify(error='Войдите, чтобы участвовать в чате.'),401
        body=str((request.get_json(silent=True) or {}).get('body','')).strip()
        if not 1<=len(body)<=500: return jsonify(error='Сообщение должно содержать 1–500 символов.'),400
        with db() as c: c.execute('INSERT INTO messages(user_id,body,created) VALUES(?,?,?)',(u['id'],body,datetime.now(timezone.utc).isoformat()))
    with db() as c:
        rows=c.execute('SELECT messages.id,users.name,body,created FROM messages JOIN users ON users.id=user_id ORDER BY messages.id DESC LIMIT 100').fetchall()
    return jsonify([dict(r) for r in reversed(rows)])

@app.post('/api/feedback')
def feedback():
    d=request.get_json(silent=True) or {}; email=str(d.get('email','')).strip(); body=str(d.get('body','')).strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not 10<=len(body)<=3000:
        return jsonify(error='Укажите корректную почту и сообщение от 10 до 3000 символов.'),400
    if not all(os.getenv(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','MAIL_FROM','MAIL_TO')):
        return jsonify(error='Отправка почты не подключена. Заполните SMTP в файле .env.'),503
    msg=EmailMessage(); msg['Subject']='ORBIT: обратная связь'; msg['From']=os.environ['MAIL_FROM']; msg['To']=os.environ['MAIL_TO']; msg['Reply-To']=email; msg.set_content(body)
    try:
        port=int(os.getenv('SMTP_PORT','587'))
        smtp=smtplib.SMTP_SSL if port==465 else smtplib.SMTP
        with smtp(os.environ['SMTP_HOST'],port,timeout=15) as s:
            if port!=465: s.starttls(context=ssl.create_default_context())
            s.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']); s.send_message(msg)
    except (OSError,smtplib.SMTPException,ValueError):
        return jsonify(error='Письмо не отправлено. Проверьте настройки почты и повторите попытку.'),502
    with db() as c: c.execute('INSERT INTO feedback(email,body,created,status) VALUES(?,?,?,?)',(email,body,datetime.now(timezone.utc).isoformat(),'sent'))
    return jsonify(message='Письмо отправлено. Спасибо за обращение!')

@app.post('/api/payment')
@login_required
def payment():
    public_id=os.getenv('CLOUDPAYMENTS_PUBLIC_ID')
    if not public_id: return jsonify(error='Оплата не подключена. Добавьте тестовый Public ID CloudPayments в .env.'),503
    # Учебная оплата услуги: цена определяется сервером, реквизиты принимает только виджет провайдера.
    return jsonify(publicId=public_id,description='ORBIT — подбор кроссовок',amount=500,currency='RUB',accountId=str(user()['id']),invoiceId=secrets.token_hex(12))

PAGES={'/':('home','Кроссовки в твоём ритме'),'/catalog':('catalog','Каталог'),'/club':('club','Клуб ORBIT'),'/checkout':('checkout','Подбор и оплата'),'/account':('account','Личный кабинет'),'/contact':('contact','Связаться с нами')}
def page():
    name,title=PAGES[request.path]
    return render_template('index.html',page=name,title=title,products=PRODUCTS,canonical=os.getenv('PUBLIC_URL','http://127.0.0.1:5000').rstrip('/')+request.path)
for path in PAGES: app.add_url_rule(path,endpoint='page_'+PAGES[path][0],view_func=page)

@app.errorhandler(404)
def missing(e): return render_template('404.html'),404

if __name__=='__main__': app.run(host='127.0.0.1',port=5000,debug=False)
