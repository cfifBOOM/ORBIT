"""Собрать отдельный статический лендинг для GitHub Pages: python build_pages.py."""
from pathlib import Path
import shutil
from app import app

root=Path(__file__).parent
out=root/'docs'
out.mkdir(exist_ok=True)
with app.test_client() as client:
    html=client.get('/').data.decode('utf-8')
html=html.replace('href="/"','href="#"').replace('src="/static/','src="static/').replace('href="/static/','href="static/')
import re
html=re.sub(r'href="/catalog[^\"]*"','href="#collection"',html)
for path in ('/club','/checkout','/account','/contact'):
    html=html.replace('href="'+path+'"','href="#about"')
html=html.replace('<span class="account-name">Войти</span>','<span>О проекте</span>')
html=re.sub(r'<link rel="canonical"[^>]*>','',html)
html=html.replace('</main>','''<section id="about" class="container section"><p class="eyebrow">О ПРОЕКТЕ</p><h2>ORBIT — учебный магазин</h2><p class="muted">Это статический лендинг для GitHub Pages. Полная версия проекта на Flask включает каталог с экспортом, аккаунты, общий чат, обратную связь и платёжную интеграцию. Для её запуска скачайте исходники и следуйте README.md.</p></section></main>''')
(out/'index.html').write_text(html,encoding='utf-8')
(out/'.nojekyll').touch()
shutil.copytree(root/'static',out/'static',dirs_exist_ok=True)
css=(out/'static/style.css').read_text(encoding='utf-8').replace("url('/static/fonts/NotoSans.ttf')","url('fonts/NotoSans.ttf')")
(out/'static/style.css').write_text(css,encoding='utf-8')
(out/'static/app.js').write_text('''const $=s=>document.querySelector(s);
$('.menu-toggle').onclick=()=>{let open=$('.main-nav').classList.toggle('open');$('.menu-toggle').setAttribute('aria-expanded',String(open));};
document.querySelectorAll('.iso-item').forEach(b=>b.onclick=()=>{b.classList.toggle('active');b.setAttribute('aria-pressed',String(b.classList.contains('active')));});
let n=0;function slide(delta){n+=delta;$('#slider-cube').style.transform=`translateZ(-165px) rotateX(${-90*n}deg)`;$('#slide-counter').textContent=`0${((n%4)+4)%4+1} / 04`;document.querySelectorAll('.slide-face').forEach((e,i)=>e.setAttribute('aria-hidden',String(i!==((n%4)+4)%4)));}
$('#slide-prev').onclick=()=>slide(-1);$('#slide-next').onclick=()=>slide(1);slide(0);
''',encoding='utf-8')
print('Готово: docs/index.html')
