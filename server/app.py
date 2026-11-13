# WhatsApp-first order service. Production needs HTTPS proxy, persistent disk and rate limits.
import os,sys,json,sqlite3,secrets,hmac,datetime,urllib.parse,re,logging,urllib.request,uuid
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from report import make_pdf,CHAPTERS,SIGNS
ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.getenv('ORACLE_DB',str(ROOT/'runtime/orders.sqlite3')));DB.parent.mkdir(parents=True,exist_ok=True)
ADMIN_TOKEN=os.getenv('ORACLE_ADMIN_TOKEN',''); HOST=os.getenv('ORACLE_HOST','0.0.0.0');PORT=int(os.getenv('PORT',os.getenv('ORACLE_PORT','8080')))
ORIGIN=os.getenv('ORACLE_SITE_ORIGIN','').rstrip('/');ADMIN_WA=os.getenv('ORACLE_ADMIN_WHATSAPP','').strip()
WA_TOKEN=os.getenv('WA_ACCESS_TOKEN','');WA_PHONE_ID=os.getenv('WA_PHONE_NUMBER_ID','');WA_API_VERSION=os.getenv('WA_API_VERSION','v22.0')
logging.basicConfig(level=logging.INFO)
def connect():
 c=sqlite3.connect(DB,timeout=15);c.execute('PRAGMA journal_mode=WAL');c.execute("""CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY,created_at TEXT NOT NULL,name TEXT NOT NULL,phone TEXT NOT NULL,answers TEXT NOT NULL,partner_sign TEXT,language TEXT NOT NULL,consent INTEGER NOT NULL,status TEXT NOT NULL,payment_reference TEXT,paid_at TEXT,sent_at TEXT,send_error TEXT)""");return c
with connect():pass
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def wa_send(order,pdf):
 if not WA_TOKEN or not WA_PHONE_ID:raise RuntimeError('Официальный WhatsApp API не настроен')
 # Only send within a customer-service window or after approved template initiation.
 # Client's opt-in alone does not establish a 24-hour customer-service window.
 if os.getenv('WA_24H_WINDOW_CONFIRMED','')!='true':raise RuntimeError('Не подтверждено открытое 24-часовое окно WhatsApp. Используйте утверждённый шаблон или ручную отправку.')
 base=f'https://graph.facebook.com/{WA_API_VERSION}/{WA_PHONE_ID}'
 boundary='----oracle'+uuid.uuid4().hex
 payload=(f'--{boundary}\r\nContent-Disposition: form-data; name="messaging_product"\r\n\r\nwhatsapp\r\n'+f'--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\napplication/pdf\r\n'+f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="30_tain_{order[0]}.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+pdf+f'\r\n--{boundary}--\r\n'.encode()
 def post(url,body,ctype):
  req=urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+WA_TOKEN,'Content-Type':ctype},method='POST')
  with urllib.request.urlopen(req,timeout=35) as resp:return json.loads(resp.read())
 media=post(base+'/media',payload,'multipart/form-data; boundary='+boundary)
 if not media.get('id'):raise RuntimeError('Не удалось загрузить PDF в WhatsApp')
 phone=re.sub(r'\D','',order[2]);message={'messaging_product':'whatsapp','to':phone,'type':'document','document':{'id':media['id'],'filename':'30_tain_'+order[0]+'.pdf','caption':'Спасибо, '+order[1]+'! Ваш оплаченный заказ '+order[0]+'. Ваше персональное предсказание ✨'}}
 result=post(base+'/messages',json.dumps(message).encode(),'application/json')
 if not result.get('messages'):raise RuntimeError('WhatsApp не подтвердил приём сообщения')
 return result['messages'][0].get('id')
class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args):logging.info(fmt,*args)
 def send_headers(self,status=200,ctype='application/json; charset=utf-8',length=None):
  self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer')
  if ORIGIN:self.send_header('Access-Control-Allow-Origin',ORIGIN);self.send_header('Vary','Origin')
  self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type');self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
  if length is not None:self.send_header('Content-Length',str(length))
  self.end_headers()
 def reply(self,obj,status=200):
  body=json.dumps(obj,ensure_ascii=False).encode();self.send_headers(status,length=len(body));self.wfile.write(body)
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n<2 or n>26000:raise ValueError('Неверный размер запроса')
  try:return json.loads(self.rfile.read(n))
  except Exception:raise ValueError('Некорректный JSON')
 def admin(self):return len(ADMIN_TOKEN)>=24 and hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+ADMIN_TOKEN)
 def do_OPTIONS(self):self.send_headers(204)
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
       if path == "/":
        page = (ROOT / "website" / "index.html")
        content = page.read_bytes()
        self.send_response(200)            
        self.send_header("Content-Type", "text/html;charset=utf-8")
        self.send_header("Content-Lenght",str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        return            
  if path=='/api/health':return self.reply({'ok':True,'mode':'manual-payment-verification','amount_kgs':399,'whatsapp_api_configured':bool(WA_TOKEN and WA_PHONE_ID)})
  if path=='/admin':
   content=(ROOT/'server/admin.html').read_bytes();self.send_headers(200,'text/html; charset=utf-8',len(content));return self.wfile.write(content)
  if path=='/api/admin/orders':
   if not self.admin():return self.reply({'error':'Доступ запрещён'},401)
   with connect() as db:rows=db.execute('SELECT id,created_at,name,phone,status,payment_reference,paid_at,sent_at,send_error FROM orders ORDER BY created_at DESC LIMIT 300').fetchall()
   return self.reply({'orders':[dict(zip(['id','created_at','name','phone','status','payment_reference','paid_at','sent_at','send_error'],r)) for r in rows]})
  if path.startswith('/api/admin/pdf/'):
   if not self.admin():return self.reply({'error':'Доступ запрещён'},401)
   oid=path.rsplit('/',1)[-1]
   with connect() as db:row=db.execute('SELECT answers,partner_sign,status FROM orders WHERE id=?',(oid,)).fetchone()
   if not row:return self.reply({'error':'Не найден'},404)
   if row[2] not in ('paid','sent'):return self.reply({'error':'Платёж не подтверждён'},403)
   pdf=make_pdf(json.loads(row[0]),row[1],oid);self.send_headers(200,'application/pdf',len(pdf));return self.wfile.write(pdf)
  return self.reply({'error':'Не найдено'},404)
 def do_POST(self):
  path=urllib.parse.urlparse(self.path).path
  try:
   if path=='/api/orders':
    x=self.body();name=x.get('name');phone=x.get('phone');answers=x.get('answers');partner=x.get('partner_sign') or None;language=x.get('language','ru')
    if not isinstance(name,str) or not 1<=len(name.strip())<=90:raise ValueError('Укажите имя')
    if not isinstance(phone,str) or not re.fullmatch(r'\+?[1-9][0-9 ()-]{7,19}',phone):raise ValueError('Укажите международный номер WhatsApp')
    digits=re.sub(r'\D','',phone)
    if not 9<=len(digits)<=15:raise ValueError('Некорректный международный номер')
    if x.get('consent') is not True:raise ValueError('Нужно согласие на обработку данных и сообщения по заказу')
    if language not in ('ru','ky'):raise ValueError('Неизвестный язык')
    if not isinstance(answers,list) or len(answers)!=30 or any(not isinstance(v,str) or v not in CHAPTERS[i]['choices'] for i,v in enumerate(answers)):raise ValueError('Нужны 30 корректных ответов')
    if partner and partner not in SIGNS:raise ValueError('Неизвестный знак партнёра')
    oid='TSD-'+secrets.token_hex(7).upper()
    with connect() as db:db.execute('INSERT INTO orders (id,created_at,name,phone,answers,partner_sign,language,consent,status) VALUES (?,?,?,?,?,?,?,?,?)',(oid,now(),name.strip(),digits,json.dumps(answers,ensure_ascii=False),partner,language,1,'pending'))
    return self.reply({'order_id':oid,'status':'pending','amount_kgs':399,'admin_whatsapp':ADMIN_WA},201)
   if path.startswith('/api/admin/'):
    if not self.admin():return self.reply({'error':'Доступ запрещён'},401)
    oid=path.rsplit('/',1)[-1]
    with connect() as db:row=db.execute('SELECT id,name,phone,answers,partner_sign,status FROM orders WHERE id=?',(oid,)).fetchone()
    if not row:return self.reply({'error':'Заказ не найден'},404)
    if path.startswith('/api/admin/confirm/'):
     x=self.body();reference=x.get('payment_reference','')
     if not isinstance(reference,str) or not 5<=len(reference)<=120:raise ValueError('Укажите идентификатор банковской операции (5–120 символов)')
     if row[5]!='pending':return self.reply({'error':'Заказ уже обработан'},409)
     with connect() as db:db.execute('UPDATE orders SET status=?,payment_reference=?,paid_at=? WHERE id=?',('paid',reference,now(),oid))
     return self.reply({'order_id':oid,'status':'paid','pdf_ready':True})
    if path.startswith('/api/admin/send-whatsapp/'):
     if row[5] not in ('paid','sent'):return self.reply({'error':'Платёж не подтверждён'},403)
     pdf=make_pdf(json.loads(row[3]),row[4],oid)
     try:message_id=wa_send(row,pdf)
     except Exception as e:
      with connect() as db:db.execute('UPDATE orders SET send_error=? WHERE id=?',(str(e)[:400],oid))
      return self.reply({'error':str(e)},503)
     with connect() as db:db.execute('UPDATE orders SET status=?,sent_at=?,send_error=NULL WHERE id=?',('sent',now(),oid))
     return self.reply({'status':'sent','whatsapp_message_id':message_id,'note':'API принял сообщение; фактическую доставку проверяйте через webhook Meta'})
   return self.reply({'error':'Не найдено'},404)
  except ValueError as e:return self.reply({'error':str(e)},400)
  except Exception:logging.exception('Request error');return self.reply({'error':'Ошибка сервера'},500)
if __name__=='__main__':
 if len(ADMIN_TOKEN)<24:logging.warning('ORACLE_ADMIN_TOKEN not configured: admin disabled')
 print('Server running on port',PORT,flush=True);ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
