"""Проверки API, экспорта и изоляции сессий: python -m unittest tests -v."""
import os
import tempfile
import unittest
import io
os.environ['ORBIT_DATA_DIR']=tempfile.mkdtemp(prefix='orbit-test-')
os.environ['SMTP_HOST']=''
os.environ['CLOUDPAYMENTS_PUBLIC_ID']=''
from app import app
from openpyxl import load_workbook

class OrbitTests(unittest.TestCase):
    def setUp(self):
        self.c=app.test_client()
        self.token=self.c.get('/api/session').json['csrf']
    def post(self,path,data):
        return self.c.post(path,json=data,headers={'X-CSRF-Token':self.token})
    def test_pages(self):
        for path in ['/','/catalog','/club','/checkout','/account','/contact']:
            self.assertEqual(self.c.get(path).status_code,200,path)
        self.assertEqual(self.c.get('/missing').status_code,404)
    def test_auth_and_chat(self):
        self.assertEqual(self.post('/api/messages',{'body':'hello'}).status_code,401)
        data={'name':'Тестер','email':'test@example.org','password':'testpass123'}
        self.assertEqual(self.post('/api/register',data).status_code,201)
        self.assertEqual(self.post('/api/register',data).status_code,409)
        self.assertEqual(self.post('/api/messages',{'body':'<script>привет</script>'}).status_code,200)
        other=app.test_client()
        self.assertEqual(other.get('/api/messages').json[-1]['body'],'<script>привет</script>')
        self.assertIsNone(other.get('/api/session').json['user'])
        self.assertEqual(self.post('/api/logout',{}).status_code,200)
        self.assertEqual(self.post('/api/login',{**data,'password':'wrong'}).status_code,401)
        self.assertEqual(self.post('/api/login',data).status_code,200)
        self.assertEqual(self.post('/api/payment',{}).status_code,503)
    def test_filters_and_exports(self):
        rows=self.c.get('/api/products?sort=price&direction=desc&category=Бег').json
        self.assertEqual(len(rows),2);self.assertGreater(rows[0]['price'],rows[1]['price'])
        for key in ['name','category','color','price','stock']:
            rows=self.c.get('/api/products?sort='+key).json
            self.assertEqual([p[key] for p in rows],sorted(p[key] for p in rows))
        x=self.c.get('/api/export/xlsx?category=Бег&sort=price&direction=desc')
        s=load_workbook(io.BytesIO(x.data)).active
        self.assertEqual(s.max_row,3);self.assertEqual(s['D2'].value,11900)
        pdf=self.c.get('/api/export/pdf')
        self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.data.startswith(b'%PDF'))
        self.assertEqual(self.c.get('/api/export/nope').status_code,404)
        self.assertTrue(self.c.get('/api/qr').data.startswith(b'\x89PNG'))
    def test_validation(self):
        self.assertEqual(self.c.post('/api/register',json={}).status_code,403)
        self.assertEqual(self.post('/api/register',{}).status_code,400)
        self.assertEqual(self.post('/api/feedback',{'email':'hello@example.org','body':'Это тестовое письмо'}).status_code,503)
        self.assertEqual(self.post('/api/feedback',{'email':'bad','body':'no'}).status_code,400)

if __name__=='__main__': unittest.main()
