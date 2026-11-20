import test from "node:test";
import assert from "node:assert/strict";
import {createTarotApi, readTarot, readingPath} from "../api/reading.mjs";
import major from "../deck.js";
import minor from "../minor.js";

const spread = {topic:"前路", cards:[
  {id:0, orientation:"upright"},
  {id:21, orientation:"reversed"},
  {id:77, orientation:"upright"}
]};
const url = "https://example.test" + readingPath;
function post(body, headers = {}) {
  return new Request(url,{method:"POST",headers:{Origin:new URL(url).origin,"Content-Type":"application/json",...headers},body});
}

test("宿主鉴权后使用共享文字客户端，按提交顺序提供本地牌义", async () => {
  const env = {};
  const request = post(JSON.stringify({...spread, prompt:"客户端额外提示"}));
  const calls = [];
  const handler = createTarotApi({
    authorizeMarket(req, bindings) {
      assert.equal(req,request);
      assert.equal(bindings,env);
      calls.push("auth");
    },
    createEnvAiClient(bindings,options) {
      assert.equal(bindings,env);
      assert.deepEqual(options,{textProvider:"cloudflare",cloudflareThinking:false,timeoutMs:30000});
      calls.push("model");
      return {async generate(input,{signal}) {
        assert.equal(signal,request.signal);
        assert.equal(input.version,1);
        assert.equal(input.route,"text");
        assert.deepEqual(input.messages.map(m=>m.role),["system","user"]);
        const user = input.messages[1].content;
        assert.ok(user.includes("下一步该往哪里走？"));
        assert.ok(user.includes(["来处："+major[0].upright.meaning,"当下："+major[21].reversed.meaning,
          "下一步："+minor.at(-1).upright.meaning].join("\n")));
        assert.ok(!user.includes("客户端额外提示"));
        return {text:JSON.stringify({advice:"我是薇拉，留点时间想一想。",action:"行动：今天先写下一件想做的事。"})};
      }};
    }
  });
  assert.equal(await handler(new Request("https://example.test/api/assistant/message"),env),null);
  const response = await handler(request,env);
  assert.equal(response.status,200);
  assert.deepEqual(await response.json(),{text:"留点时间想一想。\n\n今天先写下一件想做的事。"});
  assert.deepEqual(calls,["auth","model"]);
});

test("无效牌阵、跨站来源及错误请求格式在调用模型前返回", async () => {
  let modelCalls = 0;
  const handler = createTarotApi({authorizeMarket(){},createEnvAiClient(){modelCalls++;}});
  for (const [req,status] of [
    [new Request(url),405], [post("{"),400], [post("x".repeat(2049)),413],
    [post("{}",{"Content-Type":"text/plain"}),415], [post("{}",{Origin:"https://elsewhere.test"}),403],
    [post(JSON.stringify({...spread,cards:[spread.cards[0],...spread.cards.slice(0,2)]})),400],
    [post(JSON.stringify({...spread,topic:"未知"})),400],
    [post(JSON.stringify({...spread,cards:[...spread.cards.slice(0,2),{id:78,orientation:"upright"}]})),400]
  ]) assert.equal((await handler(req,{})).status,status);
  assert.equal(modelCalls,0);
});

test("鉴权失败交还宿主处理，模型失效返回可重试错误", async () => {
  const req = () => post(JSON.stringify(spread));
  const blocked = createTarotApi({authorizeMarket(){throw Error("unauthorized");},createEnvAiClient(){assert.fail();}});
  await assert.rejects(blocked(req(),{}),/unauthorized/);
  const invalid = createTarotApi({authorizeMarket(){},createEnvAiClient(){return {generate:()=>({text:"{}"})};}});
  assert.equal((await invalid(req(),{})).status,503);
});

test("主站执行精灵同源写入规则，本机保留脚本调用", async () => {
  let calls = 0;
  const client = () => ({generate() {
    calls++;
    return {text:JSON.stringify({advice:"先看看眼前的选择。",action:"写下第一步。"})};
  }});
  const handler = createTarotApi({authorizeMarket(){},createEnvAiClient:client});
  const withoutOrigin = () => {
    const request = post(JSON.stringify(spread));
    request.headers.delete("origin");
    return request;
  };
  assert.equal((await handler(withoutOrigin(),{})).status,403);
  assert.equal((await handler(post(JSON.stringify(spread),{"Sec-Fetch-Site":"cross-site"}),{})).status,403);
  assert.equal((await handler(new Request(url),{})).headers.get("Allow"),"POST");
  assert.equal(calls,0);
  assert.equal((await readTarot(withoutOrigin(),client)).status,200);
  assert.equal(calls,1);
});
