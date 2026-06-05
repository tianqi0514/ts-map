# 运行说明 · manus 式 Agent（用你自己的 LLM key）

## 0. 形态
- 工具调用 = **function-calling**（OpenAI 兼容 `/v1/chat/completions`，传 `tools`）。
- 工具结果 = **JSON** 以 `role:"tool"` 回灌。
- **Agent 自主多轮**：模型自己决定调哪个工具、调几次、何时停、最后给结论——不预设步骤。

## 1. 准备
- Neo4j：`cypher-shell -f seed.cypher` 灌图（故事一/三的图查询底座）。
- 实现 `tools.json` 里 8 个工具的后端（多数是 Neo4j 查询 + 读 seed.json；`rule_evaluate` 调你们的规则引擎；`clause_read_text` 返回 seed.json 里条款的 `text`）。
- LLM：填你自己的 key（占位 `YOUR_API_KEY`），选支持 function-calling 的模型。

## 2. Agent 主循环（伪代码，~30 行）
```python
import json, openai
openai.api_key = "YOUR_API_KEY"   # ← 你的 key
TOOLS = json.load(open("tools.json"))["tools"]

def run_agent(system_prompt, task):
    msgs = [{"role":"system","content":system_prompt},
            {"role":"user","content":task}]
    for _ in range(20):                       # 自主多轮上限
        r = openai.chat.completions.create(
            model="<your-model>", messages=msgs, tools=TOOLS, tool_choice="auto")
        m = r.choices[0].message
        msgs.append(m)
        if not m.tool_calls:                  # 模型自己决定停 → 出结论
            return m.content
        for tc in m.tool_calls:               # 执行模型选择的工具
            args = json.loads(tc.function.arguments)
            result = dispatch(tc.function.name, args)   # 你的工具后端
            msgs.append({"role":"tool","tool_call_id":tc.id,
                         "content": json.dumps(result, ensure_ascii=False)})  # JSON 回灌
    return "达到步数上限"
```

## 3. system prompt 模板（manus 式：目标驱动 + 自主 + 可回溯 + 反幻觉）
```
你是合同风控调查智能体。给你一个目标，不给步骤——你要自己规划、调用工具调查、根据结果修正假设、必要时深挖或横向扩展，最后给出有依据的判断。

【世界模型】先调用 ontology_get_slice 取本体切片，明确你能查哪些实体/字段/关系，越界字段不可用。
【可用工具】见 tools（图穿透/共同邻居/最短路径/读条款原文/外部事实/符号规则评估/实体读取）。自主决定调谁、几次、顺序、何时停。
【方法】think→调用工具→观察 JSON 结果→修正假设→继续，直到证据足够。鼓励：对可疑点主动深挖、把多条弱信号在图上拼成关系判断、读条款原文做语义研判、用 rule_evaluate 拿确定性硬地基（不要重复规则已能做的事，把精力放在规则做不到的语义与关系判断上）。
【输出】给出：① 调查轨迹摘要(你做了哪些判断及理由) ② 最终结论与风险等级 ③ 每条结论引用的证据 id(必须是工具返回中真实存在的 id，禁止编造) ④ 不确定性自评与建议的下一步人工动作。
【边界】只在切片授权范围内取数；不量化无依据的概率/金额；证据不足时如实说明并建议补证，不臆测。
```

## 4. 三故事的起始 user 消息（任务，不给步骤）
- 故事一：`评估即将与 海岳贸易(S-301) 签订的 250 万合同 C-2024-007 的对手方风险，给出是否可签的判断与依据。`
- 故事二：`评估合同 C-2024-001 对我方的真实风险敞口，并给出修订优先级。`
- 故事三：`政策已升级到 v2(新增"数据合规"强制条款)。评估我方在手合同的暴露面，并对每份给出差异化处置方案。`

## 5. 验收
对照 `故事脚本_Agent版.md` 的期望轨迹与 `验证数据集.xlsx → 16_期望结果 golden`，重点看 **Agent 专属断言 A4 / B3 / B4 / C3**（自主深挖、语义发现、交叉推理、差异化处置）——这些是 workflow 给不出的，过了即证明本体+图+Agent 的价值。
