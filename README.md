# 知据：思政内容辅助审校原型

JEV 快速分流、带出处的知识图谱和 DeepSeek 深度审校协作，核对教育文本中的事实、日期、术语、政策适用范围与引用语境。结果是编辑建议，不是对观点或作者的价值判定，也不是全文合规认证。

## 先运行

Python 3.10+、CPU 即可；核心代码只使用标准库，不需要下载模型权重。

```bash
git clone https://github.com/Abchyy/sizheng-review-prototype.git
cd sizheng-review-prototype
python3 -m venv .venv
source .venv/bin/activate
python -m sizheng verify
python -m unittest discover -s tests -v
python -m sizheng serve --offline
```

也可以解压交付 ZIP 后从 `cd sizheng-review-prototype` 开始。Windows 激活命令为 `.venv\Scripts\activate`。

打开 <http://127.0.0.1:8765>。离线模式只显示图谱取证，明确返回 `insufficient`，不伪装成模型审校。

真实运行可在本地终端隐藏输入两把密钥，密钥只存在于进程环境：

```bash
python scripts/run_with_keys.py serve
```

也可以自行设置 `DEEPSEEK_API_KEY`、`OPENROUTER_API_KEY` 后运行 `python -m sizheng serve`。不要将真实密钥加入 Git；`.env.example` 只是变量说明，程序不会自动读取 `.env`。

## 一个完整流程

```bash
python scripts/run_with_keys.py review --text '《高等学校课程思政建设指导纲要》明确，只有思政课教师承担育人责任，其他专业课教师无需承担。'
```

程序链接“课程思政”实体，沿图谱查询对应规定；JEV 返回 `routine/deep/human` 的概率；明确事实断言强制进入深度审校；DeepSeek 生成“原文片段—问题类型—依据—修改建议”；程序核验依据编号、连续原文片段和引用原句。不合格引用、缺失证据、调用异常转人工。具体政策断言不会因 JEV 高概率判断而直接放行。

输出在 `runtime/latest.json`，包含实际模型标识、原始响应、分流理由与检索证据。网页只绑定本机回环地址，不上传密钥到浏览器。

## 已交付内容

| 位置 | 内容 |
|---|---|
| `sizheng/` | 图谱查询、API 客户端、Harness、审校 CLI、网页界面、评测和复算 |
| `config.json` | 冻结的模型配置、JEV 判断标准和分流阈值 |
| `data/sources/` | 5 份真实政府资料的短原文摘录、URL、抓取时间和哈希 |
| `data/graph.json` | 17 节点、13 条有出处的关系；可导出 SQLite |
| `data/benchmark/` | 30 条明确标注的合成案例，6 开发、24 测试，按文档/主题组隔离 |
| `results/` | 真实调用、逐例结果、CSV、指标及费用记录 |
| `REPORT.md` | 中文实测结果和限制 |
| `docs/ARCHITECTURE.md` | 组件职责、路由规则和图谱如何参与 |
| `docs/EXAM_NOTES.md` | 科研实训与黑客松的讲解要点 |
| `tests/` | 关键分流、证据、概率、失败处理和数据完整性验证 |

## 模型版本说明

请求的 DeepSeek 模型名是用户指定的 `deepseek-v4-flash`。2026-10-02 的官方文档说明旧版已退役，旧名称请求由 **V4.1-Flash** 服务；真实响应标识为 `deepseek-flash`。因此，本项目不声称实测了旧版 V4-Flash 权重。JEV 请求 `typesafe/jev-1.13`，smoke test 实际响应为 `typesafe/jev-1.13-20260917`。

官方文档：

- <https://api-docs.deepseek.com/quick_start/pricing/>
- <https://api-docs.deepseek.com/guides/thinking_mode/>
- <https://openrouter.ai/docs/guides/community/jev-tutorial>

## 评测与复现

交付结果无需 API 密钥即可复算：

```bash
python -m sizheng verify
```

再次进行真实调用：

```bash
python scripts/run_with_keys.py evaluate --split test --out runtime/new-evaluation
```

默认比较 `llm_only`（允许模型已有知识，不伪造外部来源）、`llm_graph`、`hybrid` 三个方案。缓存键覆盖完整输入、提示词、模型、证据与 URL，相同成功请求不会重复付费。默认每个运行目录累计最多 100 次请求，已知/估算费用达到 $1 停止；不自动重试。原始失败和中断记录保留，超时/中断可能计费，估算不是账户账单。

`runtime/` 是本地工作目录，不纳入 Git。公开结果在 `results/`。其中逐条记录包含自造教育文本、公开原文摘录及真实响应，不含内部数据库或用户私有材料。

## 评测边界

案例和标签由同一代理编写，未经领域专家审定，不是独立盲测或生产 benchmark。以政府原文核对可验证错误，不训练/筛选人的政治立场。合成案例的准确率不能外推真实稿件；只验证了有限语料覆盖下的流程。核心价值观案例属于开发集，其余主题是演示测试集，不据测试结果调参。

“引用验证成功”只证明编号存在、出处对应和原句逐字匹配，不证明证据逻辑上支持结论。“无问题”只表示本次取证范围没有发现问题。发现问题和证据不足均需要人工；人工复核不被假设为必然正确。

长文最多 8000 字，分块保留相邻上下文。该实现没有全篇篇章推理、并发调度、生产身份认证或内部数据库接入。

图谱的有效起止日期未知时为 `null`；历史事件日期和资料发表日期分开存储。未核验的模型建议只写入审计记忆，绝不会自动改写权威图谱。

代码为 MIT 许可；政府资料摘录权利属于原发布主体，不受代码许可重新授权。
