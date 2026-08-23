/* The hero on every one of these pages is a CSS background-image on a banner
   section, so an <img> scrape misses it entirely. Find those, fetch them in
   the page context, and write them out. */
import fs from 'node:fs';
const PORT=9222, OUT=process.argv[2], SLUGS=process.argv.slice(3);
const t=await (async()=>{for(let i=0;i<40;i++){try{
  const l=await(await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  const p=l.find(x=>x.type==='page'); if(p)return p;}catch{}
  await new Promise(r=>setTimeout(r,500));}})();
const ws=new WebSocket(t.webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0; const pend=new Map(), wq=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);
  if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);}
  if(m.method)for(let i=wq.length-1;i>=0;i--)if(wq[i].m===m.method){wq[i].r(m);wq.splice(i,1);}});
const send=(m,p={})=>new Promise(r=>{const n=++id;pend.set(n,r);ws.send(JSON.stringify({id:n,method:m,params:p}));});
const ev=m=>new Promise(r=>wq.push({m,r}));
const js=async x=>(await send('Runtime.evaluate',{expression:x,awaitPromise:true,returnByValue:true}))
  .result?.result?.value;
await send('Page.enable'); await send('Runtime.enable');
const EXT={'image/png':'png','image/jpeg':'jpg','image/gif':'gif','image/webp':'webp'};
for(const s of SLUGS){
  const loaded=ev('Page.loadEventFired');
  await send('Page.navigate',{url:`https://www.sovrn.art/curated/${s}`});
  await loaded; await new Promise(r=>setTimeout(r,3500));
  const bgs=await js(`(()=>{const out=[],seen=new Set();
    document.querySelectorAll('*').forEach(el=>{
      const b=getComputedStyle(el).backgroundImage;
      if(!b||b==='none')return;
      const m=b.match(/url\\("?([^")]+)"?\\)/);
      if(!m||!m[1].includes('googleusercontent'))return;
      if(seen.has(m[1]))return; seen.add(m[1]);
      const r=el.getBoundingClientRect();
      out.push({url:m[1],w:Math.round(r.width),h:Math.round(r.height),
                y:Math.round(r.top+scrollY)});});
    return out.sort((a,b)=>a.y-b.y);})()`);
  const dir=`${OUT}/${s}`; fs.mkdirSync(dir,{recursive:true});
  const man=[];
  for(let i=0;i<bgs.length;i++){
    const g=bgs[i];
    let got=null;
    try{ got=await js(`(async()=>{const r=await fetch(${JSON.stringify(g.url)});
      if(!r.ok)return{err:r.status};const b=await r.blob();
      const u=new Uint8Array(await b.arrayBuffer());let s='';const C=0x8000;
      for(let i=0;i<u.length;i+=C)s+=String.fromCharCode.apply(null,u.subarray(i,i+C));
      return{mime:b.type,b64:btoa(s)};})()`);}catch(e){got={err:String(e).slice(0,60)};}
    if(!got||got.err){console.log(`   ${s} bg${i+1}: FAIL ${got?.err}`);continue;}
    const f=`${dir}/bg${String(i+1).padStart(2,'0')}.${EXT[got.mime]||'bin'}`;
    fs.writeFileSync(f,Buffer.from(got.b64,'base64'));
    man.push({file:f,box:[g.w,g.h],y:g.y,bytes:fs.statSync(f).size});
  }
  fs.writeFileSync(`${dir}/bg.json`,JSON.stringify(man,null,1));
  console.log(`  ${s.padEnd(26)} ${man.length} background images, ${(man.reduce((a,b)=>a+b.bytes,0)/1e6).toFixed(1)} MB`);
}
ws.close(); process.exit(0);
