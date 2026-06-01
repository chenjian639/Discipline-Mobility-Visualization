# 学科流动可视化

这是一个纯前端静态页面项目（HTML + CSS + JS），用 D3 展示学科流动的净流动、热力矩阵、学科网络、角色桑基图与学科开放度。

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

## 学科开放度说明

开放度用于衡量一个学科更偏“流出”还是更偏“流入”。当前页面中采用的计算方式是：

$$
开放度 = \frac{o - s}{o + i - s}
$$

其中：

- `o`：流出总量
- `i`：流入总量
- `s`：学科自留 / 自引量

这个指标的取值通常在 $[-1, 1]$ 之间。数值越高，说明该学科更偏向向外输出；数值越低，说明更偏向接收外部流入。页面里的“学科开放度”视图会展示：

- 左侧：开放度最高的小学科 Top 10
- 下方：按大类汇总后的平均开放度环形图

## 清洗与分类逻辑（按当前代码实现）

以下说明与 `scripts/clean_network.py`、`scripts/analyze_mobility.py` 当前实现保持一致。

### A. 清洗逻辑（`scripts/clean_network.py`）

1. 输入与输出
输入：data/raw/Discipline_Mobility_Matrix.xlsx（原始矩阵格式）

输出：

data/processed/Discipline_Mobility_Network.xlsx（按 sheet 清洗后）

data/processed/Discipline_Mobility_Network.json（前端使用的主数据）

2. 矩阵解析与对齐
每个 sheet 预期是一个 方阵：

行标签：来源学科（From）

列标签：目标学科（To）

单元格：累计流动次数

自动检测行标签列和列标签，对齐行列名后构建完整的 n × n 矩阵，缺失值补 0。

3. 学科分类逻辑（classify_category）

   小类名称采用 Web of Science (WoS) Subject Categories 分类体系。
   通过 `SUBDISCIPLINE_TO_CATEGORY` 映射表将每个小类归入 10 个大类，
   未在映射表中的小类通过正则规则兜底匹配。
   
   共 151 个小类，各大类包含小类数如下：
   
   | 大类 | 小类数 |
   |------|--------|
   | Medicine & Health | 51 |
   | Social Sciences | 25 |
   | Biology & Biochemistry | 15 |
   | Arts & Humanities | 15 |
   | Earth & Environmental | 14 |
   | Engineering & Technology | 14 |
   | Chemistry | 7 |
   | Physics & Astronomy | 6 |
   | Mathematics & Computer Science | 2 |
   | Multidisciplinary | 2 |
    
4. 节点指标计算

o（流出总量）：Σⱼ matrix[i][j]

i（流入总量）：Σᵢ matrix[i][j]

s（自留量）：matrix[i][i]

每个节点写入：

n: 学科名称

c: 大类（由 classify_category 规则匹配）

o: 流出总和

i: 流入总和

s: 自环（i == j）

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
- 否则 -> `balanced`（中等活跃 + 出入相对平衡）

4. 当前输出字段
- 每个学科输出：`name`, `category`, `out`, `in`, `self`, `net`, `out_in_ratio`, `strength`, `role`。
- 另外附加：`pagerank`（脚本内实现）与 `community`（networkx 可用时）。

5. 已知注意点
- 传播者与定居者阈值 2 倍：当前数据中所有学科的 inflow/outflow 比值在 0.67–1.50 之间，无学科超过阈值，因此运行结果中这两类角色数量为 0。这是数据本身的特征（WoS 学科间流动整体均衡），非代码 bug。如需恢复这两类角色，可降低阈值（如 1.5 倍），但会影响分类严谨性。
- 当 `inflow == 0` 且 `outflow > 0` 时，`out_in_ratio` 会写成空值（JSON 中为 `null`，CSV 中留空）。
- 社区发现依赖 `networkx`，未安装时会回退为 `-1`。

### C. 五类角色含义（解释层）

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
- 条件：`total_flow >= 70th percentile` 且双向流动均 > 0。
- 含义：高活跃度的知识枢纽，出入均强。

5. 均衡者（Balanced）
- 条件：不满足以上任一条件的中等活跃学科。
- 含义：流动总量在 p20–p70 之间，且出入相对平衡（比值在 0.5–2 之间）。

## 文件结构说明

### 页面与前端

- `index.html`：入口页，默认跳转到可视化页面。
- `discipline_mobility.html`：主可视化页面，放置图表容器、筛选按钮和 `renderRoleSankey()` 的内联实现。
- `app.js`：前端核心逻辑，负责读取数据、切换视图、绘制图表与处理 tooltip 交互。
- `styles.css`：页面样式，包括布局、字体、图例、tooltip 和统计栏。

### 数据与输出

- `data/raw/`：原始 Excel 数据目录。
- `data/processed/Discipline_Mobility_Network.json`：处理后的网络主数据，包含各时间段的节点列表、矩阵和大类配色。
- `data/processed/Discipline_Mobility_Analysis.json`：角色分类与中心性分析结果。
- `outputs/`：脚本导出的辅助结果，例如分类统计 CSV。

### 脚本

- `scripts/clean_network.py`：读取原始矩阵，清洗并生成 `Discipline_Mobility_Network.json` 和 Excel。
- `scripts/analyze_mobility.py`：基于网络数据计算角色、PageRank 和社区信息，生成 `Discipline_Mobility_Analysis.json`。
- `scripts/统计小学科.ipynb`：重新统计小学科、按 total 排序并导出 CSV。

### 图表数据来源总览

当前前端所有视图优先使用 `data/processed/Discipline_Mobility_Network.json`，若加载失败才回退到内嵌的 `FULLDATA`。

- 净流动：使用 `Discipline_Mobility_Network.json` 中当前时间段的节点与矩阵，按大类聚合；固定展示完整 10 类大类，0 值也保留占位。
- 热力矩阵：使用同一份网络 JSON 中的当前时间段矩阵，按大类聚合成大类 × 大类热力图。
- 学科网络：使用同一份网络 JSON 的当前时间段原始节点与矩阵，显示学科网络结构。
- 角色桑基图：使用 `Discipline_Mobility_Analysis.json` 中的角色分类结果，结合网络大类数据生成角色到大类的桑基图。
- 学科开放度：使用当前时间段的网络 JSON，按小学科计算开放度，再汇总为大类平均开放度。
