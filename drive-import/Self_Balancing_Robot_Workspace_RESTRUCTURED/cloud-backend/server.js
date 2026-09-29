const http = require('http');
const fs = require('fs');
const path = require('path');
const PORT = Number(process.env.PORT || 8080);
const TOKEN = process.env.CONTROL_TOKEN || 'change-me';
const root = path.resolve(__dirname, '..', 'web-dashboard');
let state = { angle: 0, output: 0, distance: -1, command: 'S', mode: 'unknown', uptime: 0, updatedAt: new Date().toISOString() };
const clients = new Set();
function authorized(req,url){ return req.headers.authorization === `Bearer ${TOKEN}` || req.headers['x-control-token'] === TOKEN || url.searchParams.get('token') === TOKEN; }
function json(res, code, value){const body=JSON.stringify(value);res.writeHead(code, {'Content-Type':'application/json','Cache-Control':'no-store','Access-Control-Allow-Origin':'*'});res.end(body);}
function body(req){return new Promise((resolve,reject)=>{let s='';req.on('data',c=>{s+=c});req.on('end',()=>{try{resolve(JSON.parse(s||'{}'))}catch(e){reject(e)}});});}
function broadcast(){const msg=`data: ${JSON.stringify(state)}\n\n`;for(const res of clients)res.write(msg);}
const server=http.createServer(async (req,res)=>{
  const url=new URL(req.url,`http://${req.headers.host}`);
  if(req.method==='OPTIONS'){res.writeHead(204,{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'Content-Type,Authorization'});return res.end();}
  if(url.pathname==='/api/state'&&req.method==='GET')return json(res,200,state);
  if(url.pathname==='/api/stream'&&req.method==='GET'){if(!authorized(req,url))return json(res,401,{error:'unauthorized'});res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache','Connection':'keep-alive','Access-Control-Allow-Origin':'*'});res.write(`data: ${JSON.stringify(state)}\n\n`);clients.add(res);req.on('close',()=>clients.delete(res));return;}
  if(!authorized(req,url)&&url.pathname.startsWith('/api/'))return json(res,401,{error:'unauthorized'});
  if(url.pathname==='/api/command'&&req.method==='POST'){try{const x=await body(req);const c=String(x.command||'S').toUpperCase();if(!'FBLRS'.includes(c))return json(res,400,{error:'invalid command'});state.command=c;state.updatedAt=new Date().toISOString();broadcast();return json(res,200,{ok:true,command:c});}catch(e){return json(res,400,{error:'invalid json'});}}
  if(url.pathname==='/api/device/command'&&req.method==='GET')return json(res,200,{command:state.command,updatedAt:state.updatedAt});
  if(url.pathname==='/api/telemetry'&&req.method==='POST'){try{const x=await body(req);state={...state,...x,updatedAt:new Date().toISOString()};broadcast();return json(res,200,{ok:true});}catch(e){return json(res,400,{error:'invalid json'});}}
  const file=url.pathname==='/'?'index.html':url.pathname.replace(/^\//,'');const full=path.resolve(root,file);if(!full.startsWith(root))return json(res,403,{error:'forbidden'});fs.readFile(full,(err,data)=>{if(err)return json(res,404,{error:'not found'});const ext=path.extname(full);const types={'.html':'text/html','.js':'application/javascript','.css':'text/css'};res.writeHead(200,{'Content-Type':types[ext]||'application/octet-stream'});res.end(data);});
});
server.listen(PORT,()=>console.log(`BalanceBot cloud backend listening on :${PORT}`));
