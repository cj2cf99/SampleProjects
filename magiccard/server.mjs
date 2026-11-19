import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import major from "./deck.js";
import minor from "./minor.js";

const deck = [...major, ...minor];
const topics = { 姻缘: "怎样靠近合适的人？", 前路: "下一步该往哪里走？", 事业: "工作中该把力气放在哪？" };
const types = { html: "text/html; charset=utf-8", js: "text/javascript; charset=utf-8", css: "text/css; charset=utf-8", jpg: "image/jpeg", png: "image/png", webp:"image/webp", mp4: "video/mp4" };
const port = Number(process.env.PORT || 8786);
const upstream = process.env.AI_BASE_URL || "http://127.0.0.1:18786/v1";
const model = process.env.AI_MODEL || "tarot-local";
const adviceFormat = {type:"json_schema",json_schema:{name:"reading",strict:true,schema:{
  type:"object",properties:{advice:{type:"string"},action:{type:"string"}},
  required:["advice","action"],additionalProperties:false
}}};
function json(response, status, body) {
  response.writeHead(status, {"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"});
  response.end(JSON.stringify(body));
}
async function reading(request, response) {
  const origin = request.headers.origin;
  if (origin && origin !== `http://${request.headers.host}`) return json(response,403,{error:"请从本机牌桌打开解读。"});
  if (!request.headers["content-type"]?.startsWith("application/json")) return json(response,415,{error:"需要 JSON 牌阵。"});
  let raw = "";
  for await (const chunk of request) {
    raw += chunk;
    if (raw.length > 2048) return json(response,413,{error:"牌阵过长。"});
  }
  let body;
  try { body = JSON.parse(raw); } catch { return json(response,400,{error:"牌阵格式有误。"}); }
  const {topic,cards} = body || {};
  if (!Object.hasOwn(topics,topic) || !Array.isArray(cards) || cards.length !== 3 ||
      cards.some(c => !c || !Number.isInteger(c.id) || !deck[c.id] || !["upright","reversed"].includes(c.orientation)) ||
      new Set(cards.map(c => c.id)).size !== 3) return json(response,400,{error:"需要一个问题与三张不同的牌。"});
  const rows = cards.map(({id,orientation}, i) => {
    const card = deck[id];
    return `${["来处","当下","下一步"][i]}：${card[orientation].meaning}`;
  });
  const abort = new AbortController();
  response.on("close", () => abort.abort());
  const timer = setTimeout(() => abort.abort(), 150000);
  try {
    const messages = [
      {role:"system",content:"你在和一位坐在对面的客人说话。用温柔、亲切的日常中文直接回答对方选的问题，像认真听完后的回应。综合三条线索。advice 用一两句回应对方在意的事，action 给一个今天可以尝试的小举动。把选择留给对方，不编造对方的经历、关系或感受。仅输出含 advice 和 action 的 JSON，总计约60至100字。正文直接从回答开始，省略署名、称谓、标题、场景描写和逐条复述。"},
      {role:"user",content:`问题：${topics[topic]}\n参考材料：\n${rows.join("\n")}\n请将三条线索融合成一个回答。`},
    ];
    const complete = format => fetch(upstream.replace(/\/$/,"")+"/chat/completions",{
      method:"POST",signal:abort.signal,
      headers:{"Content-Type":"application/json",...(process.env.AI_API_KEY ? {Authorization:"Bearer "+process.env.AI_API_KEY}:{})},
      body:JSON.stringify({model,temperature:.6,max_tokens:500,messages,...(format ? {response_format:format} : {})})
    });
    let answer = await complete(adviceFormat);
    if ([400,422].includes(answer.status)) answer = await complete(null);
    if (!answer.ok) throw new Error("upstream");
    const result = await answer.json();
    const content = result.choices?.[0]?.message?.content;
    const bodyText = typeof content === "string" ? content.replace(/<think>[\s\S]*?<\/think>/gi,"").trim() : "";
    const reading = JSON.parse(bodyText.replace(/^```(?:json)?\s*|\s*```$/gi,""));
    const text = [reading.advice,reading.action].map(part => {
      if (typeof part !== "string" || !part.trim()) throw new Error("empty");
      return part.trim().replace(/^(?:(?:我是)?(?:薇拉|月下占卜(?:屋的)?女巫|女巫)(?:[，、\s]*(?:薇拉|月下占卜(?:屋的)?女巫|女巫))*(?:说|答道)?[：:。！]\s*|(?:建议|行动|结论|解读)[：:]\s*)+/u,"");
    }).join("\n\n");
    json(response,200,{text});
  } catch {
    if (!response.destroyed) json(response,503,{error:"AI 服务暂未返回解读。可稍后重试，本局牌阵仍保留。"});
  } finally { clearTimeout(timer); }
}
const root = new URL("./",import.meta.url);
http.createServer(async (request,response) => {
  try {
    const path = new URL(request.url,"http://localhost").pathname;
    if (path === "/api/reading" && request.method === "POST") return await reading(request,response);
    if (!["GET","HEAD"].includes(request.method)) return json(response,405,{error:"请求方法不支持。"});
    const file = path === "/" ? "index.html" : path.slice(1);
    if (!/^(index\.html|(?:sky|deck|minor|game)\.js|(?:styles|salon)\.css|assets\/(?:sigil\.png|salon\/[a-z]+\.webp|(?:backs|cards)\/[a-z0-9]+\.jpg|performances\/\d\d\.mp4))$/.test(file)) return json(response,404,{error:"文件不存在。"});
    const bytes = await readFile(fileURLToPath(new URL(file,root)));
    const headers = {"Content-Type": types[file.split(".").pop()], "Cache-Control":"no-cache","Accept-Ranges":"bytes"};
    const range = /^bytes=(\d+)-(\d*)$/.exec(request.headers.range || "");
    let content = bytes;
    if (range) {
      const start = Number(range[1]), end = Math.min(bytes.length-1,range[2]?Number(range[2]):bytes.length-1);
      if(start>end){response.writeHead(416,{"Content-Range":`bytes */${bytes.length}`});return response.end();}
      content = bytes.subarray(start,end+1);
      headers["Content-Range"] = `bytes ${start}-${end}/${bytes.length}`;
    }
    response.writeHead(range?206:200,{...headers,"Content-Length":content.length});
    response.end(request.method === "HEAD" ? undefined : content);
  } catch { if (!response.headersSent) json(response,404,{error:"文件无法读取。"}); }
}).listen(port,"127.0.0.1",()=>console.log(`http://127.0.0.1:${port}/`));
