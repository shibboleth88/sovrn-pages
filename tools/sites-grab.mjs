/* Drive a real Chrome over the DevTools protocol.
   The Sites image CDN only serves these URLs to a browser that has actually
   loaded the page, and the token in each URL differs per render — so the URLs
   have to be read and fetched inside the same page context. Bytes go
   Chrome -> here -> disk, and never through anything else. */
import fs from 'node:fs';
import path from 'node:path';

const PORT = 9222;
const OUT = process.argv[2];
const SLUGS = process.argv.slice(3);

const list = async () => (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json())
  .find(t => t.type === 'page');

let target = null;
for (let i = 0; i < 40 && !target; i++) {
  try { target = await list(); } catch {}
  if (!target) await new Promise(r => setTimeout(r, 500));
}
if (!target) { console.error('no chrome target'); process.exit(1); }

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));

let id = 0;
const pending = new Map();
const waiters = [];
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  if (m.method) for (let i = waiters.length - 1; i >= 0; i--)
    if (waiters[i].m === m.method) { waiters[i].r(m); waiters.splice(i, 1); }
});
const send = (method, params = {}) => new Promise(r => {
  const n = ++id; pending.set(n, r); ws.send(JSON.stringify({ id: n, method, params }));
});
const event = m => new Promise(r => waiters.push({ m, r }));
const evaluate = async expr => {
  const r = await send('Runtime.evaluate',
    { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.text);
  return r.result?.result?.value;
};

await send('Page.enable');
await send('Runtime.enable');

const EXT = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/gif': 'gif', 'image/webp': 'webp' };

for (const slug of SLUGS) {
  const url = slug === 'cents' ? 'https://www.sovrn.art/cents'
                               : `https://www.sovrn.art/curated/${slug}`;
  const loaded = event('Page.loadEventFired');
  await send('Page.navigate', { url });
  await loaded;
  await new Promise(r => setTimeout(r, 3500));          // let lazy images settle
  // scroll the whole page so anything below the fold actually loads
  await evaluate(`(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){
    scrollTo(0,y); await new Promise(r=>setTimeout(r,120));} scrollTo(0,0);
    await new Promise(r=>setTimeout(r,1200)); return 1;})()`);

  const shots = await evaluate(`(()=>[...document.querySelectorAll('img')]
    .filter(i=>i.src.includes('googleusercontent')&&i.naturalWidth>80)
    .map(i=>({src:i.src,w:i.naturalWidth,h:i.naturalHeight,alt:i.alt||''}))
    .filter((v,n,a)=>a.findIndex(x=>x.src===v.src)===n))()`);

  const dir = path.join(OUT, slug);
  fs.mkdirSync(dir, { recursive: true });
  const man = [];
  for (let n = 0; n < shots.length; n++) {
    const s = shots[n];
    let got = null;
    try {
      got = await evaluate(`(async()=>{
        const r=await fetch(${JSON.stringify(s.src)});
        if(!r.ok) return {err:r.status};
        const b=await r.blob();
        const buf=await b.arrayBuffer();
        let bin=''; const u=new Uint8Array(buf);
        const CH=0x8000;
        for(let i=0;i<u.length;i+=CH) bin+=String.fromCharCode.apply(null,u.subarray(i,i+CH));
        return {mime:b.type,b64:btoa(bin)};})()`);
    } catch (e) { got = { err: String(e).slice(0, 80) }; }
    if (!got || got.err) { console.log(`  ${slug} ${n + 1}: FAIL ${got?.err}`); continue; }
    const ext = EXT[got.mime] || 'bin';
    const file = path.join(dir, `${String(n + 1).padStart(2, '0')}.${ext}`);
    fs.writeFileSync(file, Buffer.from(got.b64, 'base64'));
    man.push({ n: n + 1, file, w: s.w, h: s.h, alt: s.alt, mime: got.mime,
               bytes: fs.statSync(file).size });
  }
  fs.writeFileSync(path.join(dir, 'manifest.json'), JSON.stringify(man, null, 1));
  const mb = man.reduce((a, b) => a + b.bytes, 0) / 1e6;
  console.log(`  ${slug.padEnd(20)} ${String(man.length).padStart(2)} images  ${mb.toFixed(1)} MB`);
}
ws.close();
process.exit(0);
