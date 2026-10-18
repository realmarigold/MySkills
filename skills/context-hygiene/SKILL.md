---
name: context-hygiene
description: >-
  清理老项目中的死代码、死逻辑分支、言行不一的旧注释、被注释掉的代码块以及过期文档与幽灵引用，消除导致 AI Agent 产生幻觉的上下文污染源（Context Poisoning）。
  当用户提到“清理死代码（dead code）”、“清理旧注释/过期文档”、“项目瘦身/降噪”、“老项目重构前清理”、“防止 Agent 幻觉”、“上下文卫生（context hygiene）”、“删除废弃逻辑/Feature Flag/v1兼容代码”或“对齐文档与代码实现”时，必须激活此技能。
---

# 上下文卫生与防幻觉清理技能 (Context Hygiene)

老旧代码库使 AI Agent 产生幻觉的根源，往往不是代码复杂度本身，而是**上下文投毒（Context Poisoning）**：检索工具（Grep/语义搜索）将死文件与活代码平权召回，言行不一的旧注释误导模型对函数契约的理解，过期文档（`README.md` / `AGENTS.md`）中的幽灵路径与失效命令诱导模型虚构文件结构，空心参数与石化开关让模型在无效分支上空转。

本技能提供一套**证据驱动、分级推进、强制验证闭环**的上下文排毒工作流，确保在不破坏生产行为的前提下，系统性清除幻觉毒源。

---

## 一、 核心铁律 (Core Directives)

1. **代码即唯一事实来源 (Code is the Single Source of Truth)**：
   - 当文档、注释与实际生效的代码逻辑冲突时，默认以运行期真实执行的代码为准来修正或删除注释/文档。
   - **唯一例外（真 Bug 熔断）**：若通过上下文或 Git 历史判断是“代码实现漏写了关键逻辑（如权限校验、边界防御），而注释描述的才是正确业务意图”，**严禁修改注释掩盖问题**，必须将其列为 **🔴 Tier 3 疑似业务 Bug** 单独呈报用户。
2. **减法优于加法 (Subtraction over Addition)**：
   - 清理的目标是降低信息熵。代码本身能清晰表达逻辑时，直接删除冗余注释而非重写注释。
   - 仅对项目中**已有的**文档（`AGENTS.md`、`GEMINI.md`、`README.md`、`docs/`）修剪过期内容与断链，**绝不画蛇添足新建架构总结文档**——每多一份脱离代码自动校验的文档，就多一个未来的高权重幻觉源。
3. **禁绝墓碑注释 (Zero Tombstone Comments)**：
   - 删除死代码、死分支或废弃参数时，必须彻底物理移除（Git 历史已完整保留记录）。
   - **严禁**在原处留下诸如 `// Removed legacy handler`、`# 已废弃并删除` 等“墓碑注释”继续污染上下文。
4. **无安全网不清理 (No Pruning Without a Safety Net)**：
   - 动手删除任何代码前，必须先运行项目的构建、类型检查或测试套件，建立可重复执行的基准反馈闭环。

---

## 二、 四阶段标准工作流 (Workflow Phases)

### Phase 1: 建立安全网与自动化初筛 (Safety Net & Automated Scan)

1. **确立基准验证命令 (Baseline Loop)**：
   - 探测并实跑一次项目的静态检查与测试命令（例如：`tsc --noEmit`、`pytest`、`go test ./...`、`cargo check`、`mvn test-compile` 或语法导入冒烟测试）。
   - 记录初始通过状态。若初始构建本身已损坏，先记录已有错误，确保后续清理不引入新回归。
2. **执行原生静态死代码工具（若环境已安装）**：
   - 优先调用项目语言生态的确定性工具获取编译器级线索（各语言命令速查见 [`references/language-traps.md`](references/language-traps.md)）。
3. **运行内置上下文卫生扫描脚本**：
   - 调用本技能附带的零依赖扫描器，快速提取文档断链、注释代码坟场、陈旧标记、空心参数与孤立文件候选：
     ```bash
     python <skill-dir>/scripts/hygiene_scan.py <target-project-path>
     ```
   - 如需 JSON 结构化输出用于进一步脚本分析，可附加 `--format json`。

---

### Phase 2: 四维幻觉毒源深度核查 (Deep Audit Across 4 Dimensions)

结合扫描器输出与代码精读，按以下四个维度排查（典型幻觉模式与正反案例详见 [`references/hallucination-patterns.md`](references/hallucination-patterns.md)）：

#### 维度 A：高权重上下文与文档腐烂 (High-Authority Context Rot)
Agent 启动任务时会优先读取规则文件与顶层文档，这里的错误信息杀伤力最大。按以下优先级逐一核验：
1. **Agent 规则与指引**：`AGENTS.md`、`GEMINI.md`、`CLAUDE.md`、`.cursorrules`、`.agents/`。
2. **入口文档与工程配置**：`README.md`、`CONTRIBUTING.md`、`ARCHITECTURE.md`、`package.json` (scripts)、`Makefile`、`.env.example`。
3. **核查要点**：
   - 文档中提到的文件路径、目录结构、核心入口类名是否真实存在（幽灵路径）？
   - 文档中推荐的构建、启动、测试、迁移命令是否仍然有效（失效命令）？
   - `.env.example` 或配置说明中的环境变量，在当前源码中是否仍有读取点（影子配置）？

#### 维度 B：语义欺骗——言行不一的注释与空心契约 (Semantic Lies)
1. **注释漂移 (Comment-Code Drift)**：
   - 核对函数 Docstring / 头部注释与真实实现：返回值类型、可能抛出的异常、参数单位（如秒 vs 毫秒）、同步/异步行为、副作用是否早已改变？
2. **空心参数与虚假配置 (Hollow Parameters & Dead Options)**：
   - 检查函数签名或配置结构体：是否存在声明了参数/字段（甚至注释里写了说明），但函数体内根本未读取，或往下传递后被静默丢弃的情况？这类“虚假契约”极易诱导 Agent 传参调优却毫无效果。
3. **注释代码坟场 (Commented-Out Code Graveyards)**：
   - 定位连续被注释掉的历史代码块、旧查询语句、旧配置块及“墓碑注释”。

#### 维度 C：死逻辑与僵尸控制流 (Dead Logic & Zombie Control Flow)
1. **石化特性开关 (Fossilized Feature Flags)**：
   - 定位长期硬编码为常开（`true`）或常闭（`false`）的开关常量、环境变量默认值，以及永远不会走的另一侧死分支。
2. **不可达分支與冗余防御 (Unreachable Branches)**：
   - 提前 `return` / `raise` / `throw` 后的死语句；恒真/恒假条件；上游已强校验非空但下游仍在执行的废弃兼容分支。
3. **半拉子迁移遗留 (Half-Baked Migrations)**：
   - 搜索代码库中并存的 `v1` / `v2`、`old` / `new`、`legacy` / `modern`、`Deprecated` 适配层。确认旧轨道是否已无真实生产入口调用。

#### 维度 D：孤岛代码与检索诱饵 (Orphaned Code & Grep Bait)
1. **模块内私有死符号**：未使用的导入（Imports）、未使用的私有函数/方法/变量、未使用的内部类型与常量。
2. **跨模块孤岛资产**：全库 0 引用的导出函数、类、组件、工具脚本、样式文件及孤立测试夹具。
3. **仅被测试引用的僵尸模块 (`test_only_module`)**：生产代码与配置中 0 引用，仅靠自身陈旧单元测试（`tests/`）导入而维持“非零引用假象”的废弃业务模块。

---

### Phase 3: 假死排雷与证据分级 (False-Positive Guardrails & Tiering)

**在将任何文件、函数或参数判定为“可删除”之前，必须执行五项排雷核查**（各语言隐式调用陷阱详见 [`references/language-traps.md`](references/language-traps.md)）：
- **框架约定与隐式入口**：是否为框架路由文件（如 Next.js `pages/`、`app/`）、生命周期钩子、依赖注入组件（Spring `@Bean`/`@Service`）、测试发现函数（`test_*`）或独立 CLI 脚本（含 `main` 入口或 `#!` Shebang）？
- **动态反射与序列化**：是否通过字符串拼接、`getattr`、`Reflect`、动态导入（`import()`）或 JSON/ORM 序列化反射调用？
- **公共契约边界**：若项目是对外发布的 SDK/Library，该符号是否属于对外暴露的 Public API（存在于 `__all__`、`index.ts` 主导出或公开头文件中）？
- **自动生成与历史迁移禁区**：凡包含 `@generated`、`DO NOT EDIT` 的代码生成物（如 Protobuf `*_pb2.py`/`*.pb.go`、OpenAPI/GraphQL 客户端、打包产物 `*.min.js`）以及数据库历史迁移记录（`migrations/`、`alembic/`），**一律跳过，严禁手动修改或清理**。
- **近期在途开发保护 (WIP Protection)**：对全库 0 引用的文件或函数，执行 `git log -1 --format="%cr | %s" -- <file>` 检查最近提交时间。若是近期刚新增但尚未接线的半成品（WIP），必须归入 **🔴 Tier 3** 提示用户，严禁当作陈年死代码误删。

完成排雷后，将所有发现严格归入以下三个风险层级：

| 分级 | 判定标准 | 典型包含项 | 执行策略 |
| :--- | :--- | :--- | :--- |
| **🟢 Tier 1**<br>确定性安全 | 100% 不影响运行期行为与外部契约，证据确凿 | • 被注释掉的旧代码块（含 `#`/`//`、`/* */` 及非 Docstring 的孤立多行字符串）与墓碑注释<br>• 与代码实现明显矛盾的过期注释/Docstring（修正或移除）<br>• 作用域完全封闭的未引用 import、局部变量、模块内私有死函数<br>• 编译器确定的不可达语句（如 `return` 之后）与字面量恒真/恒假分支<br>• 文档中指向已重命名文件的断链（新路径唯一且明确） | **直接执行清理**，并在报告中汇总变更明细 |
| **🟡 Tier 2**<br>结构性清理 | 跨模块影响、改变函数签名或删除完整文件/文档章节，静态全库搜索 0 生产引用但需人工把关 | • 跨文件 0 引用的导出函数、类、组件或孤立源码文件<br>• 仅被测试文件引用的僵尸生产模块（连同其废弃测试一并提请清理）<br>• 生产代码中的空心参数移除（需同步修改调用方签名）<br>• 石化 Feature Flag 及其死分支剥离<br>• 废弃的 `v1/legacy` 兼容层、影子环境变量与未使用的第三方依赖<br>• 过期文档章节的整体删除或归档 | **先输出证据清单**（路径、0 生产引用检索证明、Git 最后修改时间、拟执行动作），**经用户确认后执行** |
| **🔴 Tier 3**<br>高危/存疑熔断 | 存在动态调用可能、属近期 WIP 代码，或注释与代码冲突疑似由**代码自身 Bug** 引起 | • 疑似通过反射、外部跨仓调用或插件机制消费的接口<br>• 近期刚提交但尚未接入主流程的 WIP 模块<br>• 注释写明业务强约束（如鉴权/幂等）但代码缺失，疑似真 Bug | **严禁自动修改**，在报告中亮红灯附上证据供用户决策 |

---

### Phase 4: 外科手术式清理、级联修剪与闭环验证 (Surgical Pruning & Verification)

1. **执行 Tier 1 并呈报 Tier 2/3 清单**：
   - 先完成所有 🟢 Tier 1 项的无痕清理。
   - 若存在 🟡 Tier 2 或 🔴 Tier 3 项，按照下方标准模板输出《上下文卫生审计与清理报告》，向用户确认 Tier 2 的执行范围。
2. **级联修剪 (Cascade Pruning)**：
   - 删除任何死函数、死分支或孤立代码块后，必须立即检查其内部原本引用的**子函数、专属类型定义、常量、导入语句及配置项**。
   - 若这些上游/下游符号因为本次删除而变成了新的 0 引用死代码，必须在同一批次内顺藤摸瓜清理干净，严禁留下“半截死依赖”。
3. **验证闭环 (Verification Loop)**：
   - 每完成一批清理，立即重跑 Phase 1 的构建/类型检查/测试命令。
   - 重新运行 `hygiene_scan.py`，确认已清理项不再报警且未引入新的文档断链或孤立引用。
   - 使用 `git diff` 复核所有改动，确认零墓碑注释、零占位符、零意外格式化噪音。

---

## 三、 标准输出报告模板 (Audit & Cleanup Report Template)

向用户汇报审计结果或清理进展时，始终使用以下结构：

```markdown
# 上下文卫生与防幻觉清理报告 (Context Hygiene Report)

## 1. 基准安全网状态 (Safety Net)
- **验证命令**：`<已执行的构建/类型检查/测试命令>`
- **基准状态**：[通过 / 存在既有问题（已隔离）]

## 2. 已执行清理项 (🟢 Tier 1 - 已自动完成并验证)
| 类别 | 文件与行号 | 原状（幻觉风险点） | 处置结果 |
| :--- | :--- | :--- | :--- |
| 注释漂移 / 注释坟场 / 局部死代码 / 文档断链 | `[file.ext](file:///abs/path#L10-L20)` | 简述过期内容为何会误导 Agent | 已删除 / 已对齐真实逻辑 |

## 3. 待确认结构性清理清单 (🟡 Tier 2 - 证据确凿，请确认是否清理)
| 编号 | 类别 | 目标对象与位置 | 核查证据（引用检索与排雷结论） | 拟执行动作（含级联清理范围） |
| :--- | :--- | :--- | :--- | :--- |
| T2-1 | 孤岛文件 / 死导出 / 空心参数 / 石化开关 | `[file.ext](file:///abs/path#L30-L80)` | 全库检索 `<symbol>` 仅定义处出现；非反射/非路由入口 | 删除该函数及关联私有辅助函数 `helper_x` |

## 4. 高危存疑与疑似 Bug 预警 (🔴 Tier 3 - 仅标记不触碰)
- **[T3-1]** `[file.ext](file:///abs/path#L45)`：注释声明会校验权限，但代码直接放行。通过 Git 历史核查疑似代码漏写而非注释过期，请确认是否需要按 Bug 修复。
```

---

## 四、 附属参考与工具索引 (Bundled Resources)

- **[`scripts/hygiene_scan.py`](scripts/hygiene_scan.py)**：零依赖多语言上下文卫生扫描器（检测文档幽灵断链、注释代码坟场、陈旧标记、Python AST 死分支/空心参数、全库孤立文件候选）。
- **[`references/hallucination-patterns.md`](references/hallucination-patterns.md)**：老项目十大 Agent 幻觉毒源图谱与正反重构对比（深入理解哪些内容最容易毒害 LLM 上下文）。
- **[`references/language-traps.md`](references/language-traps.md)**：主流语言（Python / TS / JS / Go / Rust / Java）假死代码排雷清单与原生静态分析工具速查表。
