# 学科流动可视化

这是一个纯前端静态页面项目（HTML + CSS + JS），用 D3 展示学科流动的弦图、桑基图、净流动与热力矩阵。

## 本地打开

- 直接双击打开 `index.html`（或 `discipline_mobility.html`）即可。

> 说明：本项目当前使用 `app.js` 内嵌数据（`FULLDATA`），不依赖后端。

## GitHub Pages 部署

1. 把代码推送到 GitHub 仓库
2. 在 GitHub 仓库 Settings → Pages
3. Build and deployment：选择 `Deploy from a branch`
4. Branch：选择 `main`，Folder：选择 `/ (root)`
5. 保存后等待 1–3 分钟，即可获得公开访问链接

入口文件为 `index.html`。

## 清洗与分类逻辑（按当前代码实现）

以下说明与 `scripts/clean_network.py`、`scripts/analyze_mobility.py` 当前实现保持一致。

### A. 清洗逻辑（`scripts/clean_network.py`）

1. 输入与输出
- 输入：`data/raw/Discipline_Mobility_Network.xlsx`（默认，可通过 `--input` 覆盖）。
- 输出：
	- `data/processed/Discipline_Mobility_Network.xlsx`（逐 sheet 清洗后结果）；
	- `data/processed/Discipline_Mobility_Network.json`（前端使用的 periods + cats）。

2. From-To 拆分规则
- 只把“前后都没有空格”的连字符 `-` 视为 From/To 分隔符。
- 例如：`A-B` 会拆分；`A - B` 不会按该规则拆分。
- 目的：尽量保留学科名内部或后缀中的 ` - Other Topics` 结构。

3. 数据清洗步骤
- 自动识别列：优先找列名同时包含 `from` 和 `to` 的列作为 pair 列，另找 times/count/value/freq 作为数值列。
- 将次数列转为数值，去掉无法转换的数据行。
- 解析 pair 列得到 `From` 与 `To`；缺失任一端的行会被丢弃。
- `Times` 转 int，并按 `--min-times`（默认 1）过滤低频记录。
- 按 `(From, To)` 聚合求和。

4. 构建前端网络结构
- 节点集：`From ∪ To`。
- 邻接矩阵：`matrix[i][j] += Times(From_i -> To_j)`。
- 每个节点写入：
	- `n`: 名称
	- `c`: 大类（由 `classify_category` 规则匹配）
	- `o`: 流出总和
	- `i`: 流入总和
	- `s`: 自环（`i == j`）

 其中 `classify_category` 里 `Mathematics & Computer Science` 的判断已经提前，`mathematics` 和 `computer science` 会优先进入该大类，而不是被工程类先截走。

5. 时间分段键映射
- sheet 名含 `2008-2018` -> `full`
- 含 `2009-2013` -> `early`
- 含 `2014-2018` -> `late`
- 其它 sheet 名转小写并规范化为 key。

### B. 角色分类逻辑（`scripts/analyze_mobility.py`）

1. 基础量计算
- `outflow[d] = Σ_j m[d][j]`（仅累计 `> 0` 的值）
- `inflow[d] = Σ_i m[i][d]`（仅累计 `> 0` 的值）
- `self[d] = m[d][d]`
- `total_flow[d] = outflow[d] + inflow[d]`

2. 分位点
- `p20 = percentile(total_flow, 20)`
- `p70 = percentile(total_flow, 70)`

3. 角色判定顺序（严格按代码 if/elif）
- 若 `total_flow <= p20` -> `isolated`
- 否则若 `outflow > inflow * 2` -> `output-dominant`
- 否则若 `inflow > outflow * 2` -> `input-dominant`
- 否则若 `total_flow >= p70` 且 `outflow > 0` 且 `inflow > 0` -> `bridge`
- 否则 -> `bridge`（默认兜底）

这意味着：只要不满足前三个条件，最终都会归到 `bridge`。

4. 当前输出字段
- 每个学科输出：`name`, `category`, `out`, `in`, `self`, `net`, `out_in_ratio`, `strength`, `role`。
- 另外附加：`pagerank`（脚本内实现）与 `community`（networkx 可用时）。

5. 已知注意点
- 当 `inflow == 0` 且 `outflow > 0` 时，`out_in_ratio` 会写成空值（JSON 中为 `null`，CSV 中留空）。
- 社区发现依赖 `networkx`，未安装时会回退为 `-1`。

### C. 四类角色含义（解释层）

1. 孤立者（Isolated）
- 条件：`total_flow <= 20th percentile`
- 含义：跨学科流动较弱，整体活跃度低。

2. 传播者（Outflow-dominant）
- 条件：`outflow > inflow × 2`
- 含义：知识净输出明显。

3. 定居者（Inflow-dominant）
- 条件：`inflow > outflow × 2`
- 含义：知识净输入明显。

4. 超越者（Bridge）
- 条件：满足高活跃桥接条件，或作为当前逻辑的默认兜底类别。
- 含义：在当前实现中，除前三类之外均归入该类。

## 文件说明（主要文件与目录）

- `discipline_mobility.html`：主交互页面，承载可视化容器 `#chartArea`、视图切换控件与内联的 `renderRoleSankey()`（由 `app.js` 调用）。
- `index.html`：项目入口页面。
- `app.js`：前端渲染与交互逻辑核心，包含视图调度（`render()`）和主要视图渲染函数（`renderHeatmap()`、`renderNetFlow()`、`renderNetwork()`、`renderFocusSankey()` 等）。
- `styles.css`：页面样式文件，定义布局、tooltip、图例与统计栏视觉规则。
- `data/raw/`：原始未处理数据目录。
- `data/processed/Discipline_Mobility_Network.json`：清洗后网络数据（periods + 节点/矩阵）。
- `data/processed/Discipline_Mobility_Analysis.json`：角色分析输出，包含 `name`、`category`、`out`、`in`、`self`、`net`、`out_in_ratio`、`strength`、`role`，并附加 `pagerank`、`community`。
- `outputs/`：分析脚本输出目录（如 `classification.csv`）。
- `scripts/clean_network.py`：清洗原始 Excel，生成 processed Excel 与 Network JSON。
- `scripts/analyze_mobility.py`：基于 Network JSON 计算角色分类，并输出 Analysis JSON 与 classification.csv。
