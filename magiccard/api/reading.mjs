import major from "../deck.js";
import minor from "../minor.js";

export const readingPath = "/api/tarot/reading";
const deck = [...major, ...minor];
const topics = { 姻缘: "怎样靠近合适的人？", 前路: "下一步该往哪里走？", 事业: "工作中该把力气放在哪？" };
const positions = ["来处", "当下", "下一步"];
const system = "你在和一位坐在对面的客人说话。用温柔、亲切的日常中文直接回答对方选的问题，像认真听完后的回应。综合三条线索。advice 用一两句回应对方在意的事，action 给一个今天可以尝试的小举动。把选择留给对方，不编造对方的经历、关系或感受。仅输出含 advice 和 action 的 JSON，总计约60至100字。正文直接从回答开始，省略署名、称谓、标题、场景描写和逐条复述。";

function json(status, body, headers = {}) {
  return Response.json(body, {status, headers: {"Cache-Control":"no-store", ...headers}});
}

async function readSpread(request) {
  const limit = 2048;
  if (Number(request.headers.get("content-length")) > limit) return json(413,{error:"牌阵过长。"});
  const reader = request.body?.getReader();
  if (!reader) return json(400,{error:"牌阵格式有误。"});
  const bytes = new Uint8Array(limit);
  let size = 0;
  try {
    for (;;) {
      const {done,value} = await reader.read();
      if (done) break;
      if (size + value.byteLength > limit) return json(413,{error:"牌阵过长。"});
      bytes.set(value,size);
      size += value.byteLength;
    }
    return JSON.parse(new TextDecoder().decode(bytes.subarray(0,size)));
  } catch {
    return json(400,{error:"牌阵格式有误。"});
  } finally {
    reader.releaseLock();
  }
}

function answerText(content) {
  const cleaned = content.replace(/<think>[\s\S]*?<\/think>/gi,"").trim();
  const answer = JSON.parse(cleaned.replace(/^```(?:json)?\s*|\s*```$/gi,""));
  return [answer.advice,answer.action].map(part => {
    if (typeof part !== "string") throw new Error("Invalid reading");
    const text = part.trim().replace(/^(?:(?:我是)?(?:薇拉|月下占卜(?:屋的)?女巫|女巫)(?:[，、\s]*(?:薇拉|月下占卜(?:屋的)?女巫|女巫))*(?:说|答道)?[：:。！,，]\s*|(?:建议|行动|结论|解读)[：:]\s*)+/u,"").trim();
    if (!text) throw new Error("Empty reading");
    return text;
  }).join("\n\n");
}

export async function readTarot(request, getClient, {requireOrigin = false} = {}) {
  if (request.method !== "POST") return json(405,{error:"请使用 POST 提交牌阵。"},{Allow:"POST"});
  const origin = request.headers.get("origin");
  if (((requireOrigin || origin !== null) && origin !== new URL(request.url).origin) ||
      request.headers.get("sec-fetch-site") === "cross-site") return json(403,{error:"请从当前牌桌打开解读。"});
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") {
    return json(415,{error:"需要 JSON 牌阵。"});
  }
  const body = await readSpread(request);
  if (body instanceof Response) return body;
  const {topic,cards} = body ?? {};
  if (typeof topic !== "string" || !Object.hasOwn(topics,topic) || !Array.isArray(cards) || cards.length !== 3 ||
      cards.some(c => !c || !Number.isInteger(c.id) || !deck[c.id] || !["upright","reversed"].includes(c.orientation)) ||
      new Set(cards.map(c => c.id)).size !== 3) return json(400,{error:"需要一个问题与三张不同的牌。"});
  const rows = cards.map(({id,orientation},i) => `${positions[i]}：${deck[id][orientation].meaning}`);
  const messages = [
    {role:"system",content:system},
    {role:"user",content:`问题：${topics[topic]}\n参考材料：\n${rows.join("\n")}\n请将三条线索融合成一个回答。`}
  ];
  try {
    const result = await getClient().generate({version:1,route:"text",messages,maxOutputTokens:500},
      {signal:request.signal});
    return json(200,{text:answerText(result.text)});
  } catch {
    return json(503,{error:"AI 服务暂未返回解读。可稍后重试，本局牌阵仍保留。"});
  }
}

// Use the receiving Worker's own Access verifier and companion text client.
export function createTarotApi({authorizeMarket,createEnvAiClient}) {
  if (typeof authorizeMarket !== "function" || typeof createEnvAiClient !== "function") {
    throw new TypeError("需要宿主鉴权与共享 AI 客户端");
  }
  return async function handleTarot(request,env) {
    if (new URL(request.url).pathname !== readingPath) return null;
    await authorizeMarket(request,env);
    return readTarot(request,() => createEnvAiClient(env,{
      textProvider:"cloudflare",cloudflareThinking:false,timeoutMs:30000
    }),{requireOrigin:true});
  };
}
