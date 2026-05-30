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

## 学科大类聚合与角色分类（详细说明）

下面给出本项目中“学科大类聚合”和“角色（role）划分”的具体计算方法、公式与默认阈值。要在 `scripts/analyze_mobility.py` 中复现或调整这些策略，请参考并修改相应参数。

1) 学科间流动与按大类聚合

- 原始网络：令 f_{i→j} 表示从学科 i 流向学科 j 的流量（如迁移计数或事件数）。
- 按大类（category）聚合：若学科 i 属于类别 A，学科 j 属于类别 B，则类别级别的流量定义为：

$$F_{A\\to B} = \\\sum_{i\\in A}\\sum_{j\\in B} f_{i\\to j}$$

此聚合用于热力矩阵与类别级桑基图。

2) 单个学科的基础量度

- 总流出：$O_d = \\\sum_j f_{d\\to j}$
- 总流入：$I_d = \\\sum_i f_{i\\to d}$
- 总流量：$T_d = O_d + I_d$
- 净流量比（归一化）：

$$r_d = \\\frac{O_d - I_d}{T_d} \\\quad (\\text{若 }T_d>0)$$

取值范围 $r_d\\in(-1,1)$，正值表示净流出倾向，负值表示净流入倾向。

另外可计算度数（不加权）: 入度 $k^{in}_d$ 为有流入到 $d$ 的不同来源学科数量，出度 $k^{out}_d$ 类似。

3) 角色分类规则（默认顺序与阈值）

为确保角色互斥且易于调参，采用按优先级匹配的流程：先检测“孤立（Isolated）”，再检测“传播/定居”，最后将剩余候选按桥梁特征判定为“超越者（Bridge）”。默认推荐参数（可在脚本中修改）：

- 最小有效流量门槛：$T_{min}=30$（若 $T_d < T_{min}$，认为样本数据太少，归为 `Isolated`）。
- 净流出/入显著阈值：$r_{th}=0.6$（若 $r_d\\ge r_{th}$ 则判为 `Outflow-dominant`；若 $r_d\\le -r_{th}$ 则判为 `Inflow-dominant`）。
- 桥梁判定：计算学科的介数中心性（betweenness，简称 $B_d$）或使用度数与双向流量的组合：若 $T_d\\ge T_{min}$ 且 $|r_d|<r_{bridge}$（默认 $r_{bridge}=0.4$）且满足下列任一条件，则判为 `Bridge`：

	- $B_d$ 位于全体学科的前 $p_{B}$ 百分位（默认 $p_{B}=80\\%$）；或
	- 同时满足 $k^{in}_d\\ge k_{deg}$ 且 $k^{out}_d\\ge k_{deg}$（默认 $k_{deg}=4$），即该学科既有多来源也有多去向。

- 孤立（Isolated）：若 $T_d < T_{min}$ 或 $(k^{in}_d + k^{out}_d) < k_{iso}$（默认 $k_{iso}=2$），则归类为 `Isolated`。

默认匹配逻辑（伪代码）：

```text
for each discipline d:
	if T_d < T_min or (k_in+d + k_out_d) < k_iso:
		role = 'Isolated'
	else if r_d >= r_th:
		role = 'Outflow-dominant'
	else if r_d <= -r_th:
		role = 'Inflow-dominant'
	else if (B_d >= percentile(B, p_B)) or (k_in_d >= k_deg and k_out_d >= k_deg):
		role = 'Bridge'
	else:
		role = 'Isolated'  # fallback for very small / ambiguous cases
```

4) 关于阈值与可配置项

- 上面列出的 $T_{min}$、$r_{th}$、$r_{bridge}$、$p_{B}$、$k_{deg}$、$k_{iso}$ 都应作为 `scripts/analyze_mobility.py` 的参数暴露，以便基于不同语料调整。默认值是根据经验与项目数据规模设定的起点，实际可通过敏感性分析调整。

5) 输出与可视化对接

- 脚本输出的 `Discipline_Mobility_Analysis.json` 应包含每个学科的 `id/name/category` 和以下字段：`O`、`I`、`T`、`r`、`k_in`、`k_out`、`B`（若计算）、`role`（字符串）。前端读取后即可据此为节点着色与生成角色桑基图。

6) 建议的验证步骤

- 在 `scripts/analyze_mobility.py` 中将阈值设为常量或命令行参数，运行并导出 `Discipline_Mobility_Analysis.json`；
- 用小样本（人工构造的 10–20 条流动记录）验证分类结果是否符合直觉；
- 若某类样本过多或过少，调整 $T_{min}$ 与 $r_{th}$ 并重新运行。

如需我把这些公式和默认参数直接写回 `scripts/analyze_mobility.py`（并生成新解析后的 `Discipline_Mobility_Analysis.json`），我可以继续实现并运行脚本。 

## 文件说明（主要文件与目录）

- `discipline_mobility.html`：主交互页面，承载可视化容器 `#chartArea`、视图切换控件与内联的 `renderRoleSankey()`（由 `app.js` 调用）；适合直接在浏览器中打开用于交互查看。
- `index.html`：项目入口页面（通常为轻量示例或重定向至 `discipline_mobility.html`）。
- `app.js`：前端渲染与交互逻辑核心，包含视图调度（`render()`）、各视图渲染函数（`renderHeatmap()`、`renderNetFlow()`、`renderNetwork()`、`renderFocusSankey()` 等）以及与 `#tooltip`、`#legend` 的事件绑定与状态管理。
- `styles.css`：页面与可视化容器的样式表，定义布局、tooltip、图例与统计栏的视觉规则。
- `data/processed/Discipline_Mobility_Network.json`：处理后的网络数据（按学科或按大类聚合的节点/链接），可供前端直接加载或替换内嵌数据。
- `data/processed/Discipline_Mobility_Analysis.json`：分析输出，包含每个学科的统计字段（`O`、`I`、`T`、`r`、`k_in`、`k_out`、`B`、`role` 等），前端据此进行着色与角色桑基渲染。
- `data/raw/`：原始未处理数据文件夹，保留用于审计与重现数据处理流程。
- `outputs/`：脚本运行产物（例如 `classification.csv`、导出的图像或 HTML 报表等）。
- `scripts/analyze_mobility.py`：计算学科流入/流出/度数/中心性并生成 `Discipline_Mobility_Analysis.json` 的主脚本，建议将前述阈值作为参数或常量置于此处以便配置。
- `scripts/generate_figures.py`：用于批量生成或导出静态图表的脚本（用于报告或离线检查）。
- `scripts/visualize_mobility.py`：辅助导出交互式 HTML 的脚本（如存在），可用于把分析结果打包成独立 HTML 报告。
- `scripts/clean_network.py`：数据清洗脚本，负责标准化学科名、合并重复记录并生成初始网络表。

如果你希望，我可以把这些说明拆分到 `docs/FILES.md`，并在 `README.md` 中保留简短索引；或者我可以把默认阈值写入 `scripts/analyze_mobility.py` 并运行生成新的 `Discipline_Mobility_Analysis.json`。 
