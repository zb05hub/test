const $=id=>document.getElementById(id);
const base=(document.querySelector('meta[name="game-api"]')?.content || '').replace(/\/$/,'');
let token=sessionStorage.getItem('kings-token'), me, topology, state, gid, selected=-1, pending=null, registration=false, busy=false, stamp=0, generation=0;
function fit(){
  document.documentElement.style.setProperty('--scale',Math.min(innerWidth/1280,innerHeight/720));
}
addEventListener('resize',fit);fit();
$('rules').onclick=()=>$('rulesDialog').showModal();
let historyPage=0;
const side=i=>i===1?'国王':'大臣';
async function api(path,body){
  const headers={};
  if(token) headers.Authorization='Bearer '+token;
  if(body!==undefined) headers['Content-Type']='application/json';
  const r=await fetch(base+'/api/'+path,{headers,method:body===undefined?'GET':'POST',body:JSON.stringify(body)})
    .catch(()=>{throw new Error('无法连接对局服务器，请稍后再试。');});
  if(!r.headers.get('content-type')?.includes('application/json')) throw new Error('对局服务器暂不可用。');
  const d=await r.json();
  if(!r.ok) throw new Error(d.error);
  return d;
}
const note=e=>{$('notice').textContent=e.message||e;};
function accountView(){
  $('who').textContent=me?.nickname||'';
  $('auth').textContent=me?'退出登录':'登录 / 注册';
  $('admin').hidden=!me?.admin;
}
function authDialog(){
  registration=false; authView(); $('accountDialog').showModal();
}
function authView(){
  $('formTitle').textContent=$('submitAuth').textContent=registration?'注册':'登录';
  $('switchAuth').textContent=registration?'返回登录':'创建账号';
  $('accountForm').elements.password.autocomplete=registration?'new-password':'current-password';
  $('formError').textContent='';
}
$('switchAuth').onclick=()=>{registration=!registration;authView();};
document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('accountDialog').addEventListener('close',()=>{pending=null; $('accountForm').reset();});
$('accountForm').onsubmit=async e=>{
  e.preventDefault(); $('submitAuth').disabled=true;
  try{
    me=await api(registration?'register':'login',Object.fromEntries(new FormData(e.target)));
    token=me.token;sessionStorage.setItem('kings-token',token);accountView();
    const mode=pending;pending=null;
    $('accountDialog').close();
    if(mode!==null) await start(mode);
  }catch(e){$('formError').textContent=e.message;}
  finally{$('submitAuth').disabled=false;}
};
$('auth').onclick=async()=>{
  if(!me){pending=null;authDialog();return;}
  try{await api('logout',{});}catch(e){note(e);return;}
  me=token=null;sessionStorage.removeItem('kings-token');accountView();home();
};
$('admin').onclick=async()=>{
  try{
    $('users').replaceChildren(...(await api('users')).map(([n,a])=>Object.assign(document.createElement('li'),{textContent:n+(a?' · 管理员':'')})));
    $('adminDialog').showModal();
  }catch(e){note(e);}
};
function home(){
  generation++;busy=false;gid=null;state=null;$('match').hidden=true;$('landing').hidden=false;note('');
}
$('home').onclick=$('back').onclick=home;
document.querySelectorAll('[data-ai]').forEach(b=>b.onclick=()=>{
  const ai=Number(b.dataset.ai);
  if(me) start(ai);
  else{pending=ai;authDialog();}
});
async function start(ai){
  if(busy)return;
  busy=true; const gen=++generation;note('正在开局…');
  try{
    topology??=await api('board');
    const data=await api('new',{ai});
    if(gen!==generation)return;
    gid=data.id;selected=-1;historyPage=0;state=data;stamp=performance.now();
    $('landing').hidden=true;$('match').hidden=false;note('');
  }catch(e){if(gen===generation)note(e);}
  finally{if(gen===generation){busy=false;if(state)render();}}
}
function svg(tag,attrs={},parent=$('board')){
  const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);
  parent.append(el);return el;
}
const xy=([x,y])=>[42+x*54,32+y*51];
const coord=i=>{const [x,y]=topology.points[i];return String.fromCharCode(65+x)+(y+1);};
function render(){
  const s=state;
  const focus=document.activeElement?.getAttribute('data-point');
  $('mode').textContent=s.ai?'人机对局 · 你执'+side(3-s.ai):'双人对局 · 同屏轮流';
  $('round').textContent='第 '+(Math.floor(Math.max(0,s.history.length-Number(!!s.winner&&s.reason!=='超时'))/2)+1)+' 回合';
  $('turn').textContent=s.winner?side(s.winner)+'获胜':side(s.side)+'行棋';
  $('hint').textContent=s.winner?s.reason:busy?'正在处理着法…':s.side===2&&s.reserve?'选择一个空交点添加大臣。':'先选棋子，再选高亮的落点。';
  $('captured').textContent=s.captured;$('reserve').textContent=s.reserve;
  for(const p of [1,2]) $('player'+p).classList.toggle('active',!s.winner&&s.side===p);
  renderHistory();
  drawBoard($('board'),s.board,s.legal);
  if(focus!==null&&focus!==undefined) $('board').querySelector('[data-point="'+focus+'"][tabindex="0"]')?.focus();
  tick();
}
const PAGE=7;
function renderHistory(){
  const total=state.history.length;
  const max=Math.max(0,Math.ceil(total/PAGE)-1);
  historyPage=Math.min(max,historyPage);
  const end=total-historyPage*PAGE;
  $('history').start=end;
  const items=state.history.slice(Math.max(0,end-PAGE),end).reverse().map(([p,a,b,c])=>
    Object.assign(document.createElement('li'),{textContent:side(p)+' '+(a<0?'添子至 '+coord(b):coord(a)+' → '+coord(b))+(c>=0?' · 吃子 '+coord(c):'')}));
  $('history').replaceChildren(...items);
  $('historyPage').textContent=total?(historyPage+1)+' / '+(max+1):'尚未落子';
  $('historyPrev').disabled=historyPage===0;
  $('historyNext').disabled=historyPage===max;
}
$('historyPrev').onclick=()=>{historyPage--; renderHistory();};
$('historyNext').onclick=()=>{historyPage++; renderHistory();};
function drawBoard(board,pieces,legal=[]){
  const interactive=board===$('board');
  const add=(tag,attrs,parent=board)=>svg(tag,attrs,parent);
  board.replaceChildren();
  add('rect',{x:10,y:6,width:280,height:461,rx:15,fill:'#c69558',stroke:'#8c6439'});
  for(const [a,b] of topology.edges){
    const [x1,y1]=xy(topology.points[a]),[x2,y2]=xy(topology.points[b]);
    add('line',{x1,y1,x2,y2,stroke:'#55391f','stroke-width':1.9});
  }
  for(const [i,p] of topology.points.entries()){
    const [cx,cy]=xy(p),v=pieces[i];
    const target=legal.some(([a,b])=>a===selected&&b===i);
    const source=legal.some(([a])=>a===i);
    const enabled=!busy&&(target||source);
    const g=add('g',{'data-point':i,class:enabled?'point':'',...(interactive?{role:'button','aria-disabled':!enabled,tabindex:enabled?0:-1,'aria-label':coord(i)+(v?' '+side(v):' 空点')}:{})});
    add('circle',{cx,cy,r:19,fill:'transparent',class:'focus',stroke:interactive&&i===selected?'#fff3bc':'transparent','stroke-width':3},g);
    add('circle',{cx,cy,r:v?13:target?6:2.6,fill:v===1?'#202a25':v===2?'#fff6df':target?'#e9ffbb':'#55391f',stroke:v?'#53432e':'none'},g);
    if(v){
      const t=add('text',{x:cx,y:cy+4,'text-anchor':'middle','font-size':11,fill:v===1?'#fff6df':'#443a2d','pointer-events':'none'},g);
      t.textContent=v===1?'王':'臣';
    }
    if(!interactive) continue;
    g.onclick=()=>point(i);
    g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();point(i);}};
  }
}
async function point(i){
  if(busy||state.winner)return;
  const m=state.legal.find(([a,b])=>a===selected&&b===i);
  if(!m){if(state.legal.some(([a])=>a===i)){selected=i;render();}return;}
  const gen=generation;
  busy=true;render();
  try{
    const data=await api('game/'+gid,{move:m});
    if(gen!==generation)return;
    state=data;stamp=performance.now();selected=-1;historyPage=0;note('');
  }catch(e){if(gen===generation)note(e);}
  finally{if(gen===generation){busy=false;render();}}
}
let polling=false;
function tick(){
  if(!state)return;
  const elapsed=(performance.now()-stamp)/1000;
  const format=n=>{const t=Math.max(0,Math.ceil(n));return String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0');};
  state.clocks.forEach((n,i)=>$(i?'ministerClock':'kingClock').textContent=format(n-(!state.winner&&state.side===i+1?elapsed:0)));
  if(!busy&&!polling&&!state.winner&&elapsed>=state.clocks[state.side-1]){
    polling=true;const gen=generation;
    api('game/'+gid).then(data=>{if(gen===generation&&!busy){state=data;stamp=performance.now();render();}}).catch(note).finally(()=>{polling=false;});
  }
}
setInterval(tick,500);
api('board').then(d=>{topology=d;drawBoard($('previewBoard'),d.initial);}).catch(note);
if(token){try{me=await api('me');}catch{token=null;sessionStorage.removeItem('kings-token');}}
accountView();
