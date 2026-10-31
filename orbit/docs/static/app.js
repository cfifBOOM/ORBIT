const $=s=>document.querySelector(s);
$('.menu-toggle').onclick=()=>{let open=$('.main-nav').classList.toggle('open');$('.menu-toggle').setAttribute('aria-expanded',String(open));};
document.querySelectorAll('.iso-item').forEach(b=>b.onclick=()=>{b.classList.toggle('active');b.setAttribute('aria-pressed',String(b.classList.contains('active')));});
let n=0;function slide(delta){n+=delta;$('#slider-cube').style.transform=`translateZ(-165px) rotateX(${-90*n}deg)`;$('#slide-counter').textContent=`0${((n%4)+4)%4+1} / 04`;document.querySelectorAll('.slide-face').forEach((e,i)=>e.setAttribute('aria-hidden',String(i!==((n%4)+4)%4)));}
$('#slide-prev').onclick=()=>slide(-1);$('#slide-next').onclick=()=>slide(1);slide(0);
