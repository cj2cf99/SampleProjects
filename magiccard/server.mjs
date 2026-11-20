import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { Readable } from "node:stream";
import { readTarot, readingPath } from "./api/reading.mjs";

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
const localAiClient = {
  async generate({messages,maxOutputTokens},{signal}) {
    const complete = format => fetch(upstream.replace(/\/$/,"")+"/chat/completions",{
      method:"POST", signal,
      headers:{"Content-Type":"application/json",...(process.env.AI_API_KEY ? {Authorization:"Bearer "+process.env.AI_API_KEY}:{})},
      body:JSON.stringify({model,temperature:.6,max_tokens:maxOutputTokens,messages,...(format ? {response_format:format} : {})})
    });
    let answer = await complete(adviceFormat);
    if ([400,422].includes(answer.status)) {
      await answer.body?.cancel();
      answer = await complete(null);
    }
    if (!answer.ok) throw new Error("Upstream unavailable");
    const result = await answer.json();
    return {text:result.choices?.[0]?.message?.content};
  }
};

async function reading(request,response) {
  const abort = new AbortController();
  const cancel = () => abort.abort();
  response.once("close",cancel);
  const timer = setTimeout(cancel,150000);
  try {
    const webRequest = new Request(new URL(request.url,`http://${request.headers.host}`),{
      method:request.method, headers:request.headers, signal:abort.signal,
      ...(request.method === "POST" ? {body:Readable.toWeb(request),duplex:"half"} : {})
    });
    const result = await readTarot(webRequest,() => localAiClient);
    if (!response.destroyed) {
      response.writeHead(result.status,Object.fromEntries(result.headers));
      response.end(await result.text());
    }
  } finally {
    clearTimeout(timer);
    response.off("close",cancel);
  }
}
const root = new URL("./",import.meta.url);
http.createServer(async (request,response) => {
  try {
    const path = new URL(request.url,"http://localhost").pathname;
    if (path === readingPath || path === "/api/reading") return await reading(request,response);
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
