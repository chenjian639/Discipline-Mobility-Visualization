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



### 1. 孤立者 (Isolated)

条件说明：`total_flow ≤ 20th percentile` —— 总活跃度排名最低的 20%
**含义**：这些学科与其他学科的交流极少，研究活动高度内部化，边界封闭。

**示例**：一些小众的细分学科，如 `Mycology`（真菌学）、`Mineralogy`（矿物学）可能属于此类。

---

### 2. 传播者 (Outflow-dominant)

条件说明：`outflow > inflow × 2` —— 流出量是流入量的 2 倍以上
**含义**：这些学科是知识的**主要输出者**，对其他学科有较强的辐射作用。

**示例**：`Physics`、`Chemistry` 等基础学科可能属于此类，它们的方法和理论被广泛引用到其他领域。

---

### 3. 定居者 (Inflow-dominant)

条件说明：`inflow > outflow × 2` —— 流入量是流出量的 2 倍以上
**含义**：这些学科是知识的**主要吸收者**，大量借鉴其他学科的研究成果。

**示例**：一些应用型学科，如 `Oncology`、`Cardiovascular System` 可能属于此类，它们吸收基础研究的成果用于临床应用。

---

### 4. 超越者 (Bridge)

条件说明：`total_flow ≥ 70th percentile` —— 总活跃度排名前 30%；且 `outflow > 0 AND inflow > 0`（既有流出也有流入）
**含义**：这些学科是知识流动的**枢纽**，既大量吸收外部知识，也大量输出自己的成果，连接不同学科领域。

**示例**：`Biochemistry & Molecular Biology`、`Neurosciences` 等跨学科领域可能属于此类。

---

以上为用于分类的具体规则；请确保 `scripts/analyze_mobility.py` 在计算并输出时遵循这些判定条件（避免将不可序列化的 `Infinity` 写入 JSON）。

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
