/* Record where everything actually sits on the original page: every image and
   text block with its box. Grouping those by y gives the real row/column
   structure, which is what "true to the original" has to mean. */
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
const send=(method,params={})=>new Promise(r=>{const n=++id;pend.set(n,r);
  ws.send(JSON.stringify({id:n,method,params}));});
const ev=m=>new Promise(r=>wq.push({m,r}));
const js=async x=>(await send('Runtime.evaluate',{expression:x,awaitPromise:true,returnByValue:true}))
  .result?.result?.value;
await send('Page.enable'); await send('Runtime.enable');
for(const s of SLUGS){
  const loaded=ev('Page.loadEventFired');
  await send('Page.navigate',{url:`https://www.sovrn.art/curated/${s}`});
  await loaded; await new Promise(r=>setTimeout(r,3000));
  await js(`(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);
    await new Promise(r=>setTimeout(r,150));}scrollTo(0,0);
    await new Promise(r=>setTimeout(r,1500));return 1})()`);
  const data=await js(`(()=>{
    const out=[];
    const push=(t,el,extra)=>{const r=el.getBoundingClientRect();
      if(r.width<8||r.height<8)return;
      out.push(Object.assign({t,x:Math.round(r.left+scrollX),y:Math.round(r.top+scrollY),
        w:Math.round(r.width),h:Math.round(r.height)},extra));};
    document.querySelectorAll('img').forEach(i=>{
      if(!i.src.includes('googleusercontent'))return;
      push('img',i,{src:i.src,nw:i.naturalWidth,nh:i.naturalHeight});});
    const seen=new Set();
    document.querySelectorAll('p,h1,h2,h3,h4,li').forEach(e=>{
      const s=(e.innerText||'').trim();
      if(s.length<2||seen.has(s))return; seen.add(s);
      const cs=getComputedStyle(e);
      push('txt',e,{text:s.slice(0,400),tag:e.tagName.toLowerCase(),
        size:Math.round(parseFloat(cs.fontSize)),color:cs.color,
        align:cs.textAlign,weight:cs.fontWeight,style:cs.fontStyle});});
    return {h:document.body.scrollHeight,items:out.sort((a,b)=>a.y-b.y||a.x-b.x)};})()`);
  fs.writeFileSync(`${OUT}/${s}.json`,JSON.stringify(data,null,1));
  console.log(`  ${s.padEnd(26)} ${data.items.length} boxes, page ${data.h}px`);
}
ws.close(); process.exit(0);
