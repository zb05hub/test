import argparse, getpass, hashlib, hmac, json, os, secrets, sqlite3, time
from contextlib import contextmanager, closing
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit
import game

ROOT = Path(__file__).resolve().parent
DB = os.getenv('GAME_DB', str(ROOT/'game.sqlite3'))
ORIGIN = os.getenv('GAME_WEB_ORIGIN','')
GAMES = {}
LOCK = Lock()
LIMIT = 40*60

@contextmanager
def db():
    with closing(sqlite3.connect(DB)) as c, c:
        yield c

def init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, nickname TEXT UNIQUE NOT NULL,
           salt TEXT NOT NULL, password TEXT NOT NULL, admin INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, uid INTEGER NOT NULL, expires INTEGER NOT NULL);
        """)

def digest(password,salt):
    return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()

def account(c,n,p,admin=False):
    if not 2<=len(n)<=24 or not 8<=len(p)<=128: raise ValueError('昵称须为 2–24 字，密码须为 8–128 字')
    salt=secrets.token_hex(16)
    return c.execute('INSERT INTO users(nickname,salt,password,admin) VALUES(?,?,?,?)',
                     (n,salt,digest(p,salt),int(admin))).lastrowid

class Match:
    def __init__(self,uid,ai):
        self.uid,self.ai=uid,ai
        self.s=game.initial()
        self.left=[0,LIMIT,LIMIT]
        self.start=time.monotonic()
        self.history=[]
        self.w=0
        self.reason=''
        self.legal=game.moves(self.s)
        self.lock=Lock()
    def clock(self):
        if self.w: return
        now=time.monotonic()
        side=self.s.side
        self.left[side]=max(0,self.left[side]-(now-self.start))
        self.start=now
        if not self.left[side]:
            self.w,self.reason=3-side,'超时'
    def step(self,m):
        self.clock()
        if self.w or m not in self.legal: raise ValueError('当前不能执行这步棋')
        side=self.s.side
        self.s=game.play(self.s,m)
        self.history.append([side,*m])
        self.legal=game.moves(self.s)
        self.w=game.winner(self.s,self.legal)
        if self.w:
            self.reason='吃满 11 枚' if self.s.captured>=11 else '对手无合法着法'
    def view(self):
        self.clock()
        return dict(board=self.s.board,side=self.s.side,reserve=self.s.reserve,captured=self.s.captured,
                    clocks=self.left[1:],history=self.history,winner=self.w,reason=self.reason,
                    legal=[] if self.w else self.legal,ai=self.ai)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'web'),**kw)
    def end_headers(self):
        if ORIGIN and self.headers.get('Origin')==ORIGIN:
            self.send_header('Access-Control-Allow-Origin',ORIGIN)
            self.send_header('Vary','Origin')
        super().end_headers()
    def reply(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Headers','Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS')
        self.end_headers()
    def do_GET(self):
        if self.path.startswith('/api/'): self.api()
        else: super().do_GET()
    def do_POST(self):
        if self.path.startswith('/api/'): self.api()
        else: self.reply({'error':'地址不存在'},404)
    def api(self):
        try: self.dispatch(urlsplit(self.path).path)
        except (ValueError,TypeError,AttributeError,KeyError,OverflowError) as e:
            self.reply({'error':str(e) or '请求格式错误'},400)
        except sqlite3.IntegrityError:
            self.reply({'error':'昵称已被使用'},409)
    def computer(self,m):
        move=game.choose(m.s)
        m.clock()
        if not m.w: m.step(move)
    def dispatch(self,path):
        if self.command=='GET' and path=='/api/board':
            return self.reply(dict(points=game.POINTS,edges=game.EDGES,initial=game.initial().board))
        d={}
        if self.command=='POST':
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=8192: raise ValueError('请求大小不正确')
            d=json.loads(self.rfile.read(size))
        token=self.headers.get('Authorization','').removeprefix('Bearer ')
        th=lambda t: hashlib.sha256(t.encode()).hexdigest()
        with db() as c:
            if self.command=='POST' and path in ('/api/login','/api/register'):
                n,p=d['nickname'].strip(),d['password']
                if not isinstance(p,str) or not 8<=len(p)<=128: raise ValueError('请输入 8–128 字的密码')
                if path.endswith('register'): account(c,n,p)
                row=c.execute('SELECT id,nickname,salt,password,admin FROM users WHERE nickname=?',(n,)).fetchone()
                if not row or not hmac.compare_digest(row[3],digest(p,row[2])):
                    return self.reply({'error':'昵称或密码不正确'},401)
                t=secrets.token_urlsafe(32)
                c.execute('DELETE FROM sessions WHERE expires<=?',(int(time.time()),))
                c.execute('INSERT INTO sessions VALUES(?,?,?)',(th(t),row[0],int(time.time())+86400))
                return self.reply(dict(token=t,nickname=row[1],admin=bool(row[4])))
            row=c.execute('SELECT id,nickname,admin FROM sessions JOIN users ON uid=id WHERE token=? AND expires>?',
                          (th(token),int(time.time()))).fetchone()
            if not row: return self.reply({'error':'请先登录'},401)
            uid,n,admin=row
            if self.command=='GET' and path=='/api/me': return self.reply(dict(nickname=n,admin=bool(admin)))
            if self.command=='POST' and path=='/api/logout':
                c.execute('DELETE FROM sessions WHERE token=?',(th(token),))
                return self.reply({})
            if self.command=='GET' and path=='/api/users':
                if not admin: return self.reply({'error':'需要管理员权限'},403)
                return self.reply(c.execute('SELECT nickname,admin FROM users ORDER BY id').fetchall())
        if self.command=='POST' and path=='/api/new':
            ai=d['ai']
            if type(ai) is not int or ai not in (0,1,2): raise ValueError('未知模式')
            m=Match(uid,ai)
            if ai==game.K: self.computer(m)
            gid=secrets.token_urlsafe(18)
            with LOCK:
                for key,old in list(GAMES.items()):
                    if old.uid==uid or time.monotonic()-old.start>86400: GAMES.pop(key,None)
                GAMES[gid]=m
            return self.reply(dict(id=gid,**m.view()))
        if path.startswith('/api/game/'):
            with LOCK: m=GAMES.get(path.split('/')[-1])
            if not m or m.uid!=uid: return self.reply({'error':'对局不存在'},404)
            with m.lock:
                if self.command=='POST':
                    if m.ai==m.s.side: raise ValueError('当前为电脑回合')
                    m.step(tuple(d['move']))
                    if not m.w and m.ai==m.s.side: self.computer(m)
                return self.reply(m.view())
        return self.reply({'error':'地址不存在'},404)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--admin',metavar='NICKNAME')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=int(os.getenv('PORT','8000')))
    args=parser.parse_args()
    init()
    if args.admin:
        password=getpass.getpass('管理员密码: ')
        if password!=getpass.getpass('再次输入: '): parser.error('两次密码不一致')
        try:
            with db() as c: account(c,args.admin.strip(),password,True)
        except (ValueError,sqlite3.IntegrityError) as e: parser.error(str(e))
        print('管理员已创建')
    else:
        print(f'http://{args.host}:{args.port}',flush=True)
        ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()


