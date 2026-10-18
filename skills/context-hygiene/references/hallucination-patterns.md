# 老项目十大 Agent 幻觉毒源图谱与处置准则 (Hallucination Patterns)

AI Agent 在阅读与修改老旧代码库时，其注意力机制与检索机制（Grep / 向量检索 / 文件树遍历）同人类开发者存在本质差异：
- **人类开发者**对置灰的注释代码、带 `old_` 前缀的文件具有天然的视觉免疫；
- **AI Agent** 则会将自然语言注释、文档描述与函数签名视为高可信度契约，甚至优先于复杂的函数体实现逻辑。

以下为按“致幻严重度”排序的十大上下文污染源（Context Poisoning Patterns）及其标准化处置方案。

---

## 1. 注释漂移与契约欺骗 (Comment-Code Drift)

### 致幻机理
函数内部实现历经多次迭代（例如返回值格式变更、时间单位从秒改为毫秒、由抛异常改为返回默认值、由同步改为异步），但函数头部的 Docstring 或行内注释仍停留在数年前的版本。Agent 调用该函数时直接采信 Docstring，写出错误的调用侧逻辑。

### 典型反例（污染态）
```python
def fetch_user_quota(user_id: str) -> int:
    """
    获取用户剩余配额（单位：GB）。
    当用户不存在时返回 -1，调用方需判断返回值是否小于 0。
    """
    record = db.query_quota(user_id)
    if not record:
        raise UserNotFoundError(f"User {user_id} not found")
    # 2024年重构后底层统一存储并返回字节数 (Bytes)
    return record.remaining_bytes
```

### 处置方案
- **核对五要素**：核对每个导出函数 Docstring 中的 **参数含义、单位/量纲、返回值类型、空值/边界行为、异常抛出** 是否与函数体完全一致。
- **修正或精简**：若代码自解释性足够强（借助类型注解与清晰命名），直接删掉赘述的注释；若业务规则非显而易见（如单位是 `Bytes` 且抛 `UserNotFoundError`），直接修正 Docstring 以对齐当前真实代码。

---

## 2. 空心参数与僵尸配置 (Hollow Parameters & Zombie Configs)

### 致幻机理
函数签名或配置类（Config Struct / TypedDict / Interface）中保留了历史遗留参数（如 `use_cache=True`、`retry_count=3`、`legacy_format=False`），但函数体内部早已不再读取该参数，或仅将其原样传给另一个同样忽略它的下游函数。Agent 在修 Bug 或加功能时，误以为传入该参数就能改变行为，陷入无效调试死循环。

### 典型反例（污染态）
```typescript
export interface RequestOptions {
  timeoutMs: number;
  enableCompression?: boolean; // 底层 HTTP 客户端早已默认托管压缩，此字段无人读取
  maxRetries?: number;         // 历史遗留字段，实际重试逻辑已迁移至网关层
}

export async function sendPayload(url: string, data: unknown, options: RequestOptions) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs);
  try {
    return await fetch(url, {
      method: "POST",
      body: JSON.stringify(data),
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}
```

### 处置方案
- 若该参数在全库调用点均未传值，或虽有传值但函数体完全未消费：将其归入 **🟡 Tier 2**，连同接口字段与调用侧冗余传参一并移除。
- 若因外部接口契约强制要求保留参数位置（如实现第三方接口或回调函数）：将参数名显式重命名为 `_unused_options` 或 `_`，消除语义误导。

---

## 3. 高权重文档中的幽灵引用 (Ghost Paths & Dead Commands)

### 致幻机理
`AGENTS.md`、`GEMINI.md`、`CLAUDE.md`、`README.md`、`CONTRIBUTING.md` 在 Agent 会话启动时具有最高上下文权重。若其中记载了早已删除的目录（如 `src/controllers/` 实际已迁移为 `src/modules/`）、失效的启动脚本（如 `npm run dev:legacy`）或废弃的架构分层，Agent 会在不存在的路径下盲目搜索甚至重新创建已废弃的目录。

### 处置方案
- 使用 `scripts/hygiene_scan.py` 自动扫描所有 Markdown 文档与 `package.json` 中的路径和脚本引用。
- **路径已迁移且唯一对应**：属于 **🟢 Tier 1**，直接更新为当前真实存在的路径。
- **整段功能或模块已彻底下线**：属于 **🟡 Tier 2**，列出过期章节清单交由用户确认后直接删除，切勿保留“某年某月已废弃”的长篇历史说明。

---

## 4. 半拉子迁移与双轨迷宫 (Half-Baked Dual-Track Migrations)

### 致幻机理
项目曾进行过架构或协议升级（如 `OrderServiceV1` 与 `OrderServiceV2`、`auth_legacy.py` 与 `auth_provider.py`），但迁移完成后未清理旧代码。当 Agent 使用关键词搜索 `OrderService` 或 `auth` 时，新旧两套实现同时出现在检索结果中。Agent 极易将新功能写进早已废弃的 V1 代码，或者在 V2 代码中错误调用 V1 的数据结构。

### 处置方案
- 追踪路由表、依赖注入容器及主入口（`main` / `app`），确认旧版模块是否还有任何生产流量入口。
- 若旧轨已无生产调用（哪怕还有专测旧轨的废弃单元测试）：将其连同专属旧测试一并列入 **🟡 Tier 2** 彻底清除。
- 若旧轨仍承担少量兼容流量、暂不可删：必须在旧模块顶部及函数签名处添加明确的边界说明（指明新逻辑应写往哪个具体的新模块路径），阻断 Agent 误写入。

---

## 5. 石化特性开关与不可达分支 (Fossilized Feature Flags & Dead Branches)

### 致幻机理
代码中充斥着已全量上线数年的 Feature Flag（如 `if ENABLE_NEW_BILLING:` 且常量 `ENABLE_NEW_BILLING = True` 写死在配置中），或永远不可能满足的防御条件。Agent 阅读函数时必须同时解析两条分支，不仅浪费上下文窗口，还常在死分支上耗费精力做同步修改。

### 典型反例（污染态）
```python
USE_ASYNC_PIPELINE = True

def dispatch_job(job_payload: dict) -> str:
    if USE_ASYNC_PIPELINE:
        return enqueue_async_worker(job_payload)
    else:
        client = LegacySyncClient()
        client.connect()
        return client.run_blocking(job_payload)
```

### 处置方案
- **局部恒真/恒假条件与 `return` 后死语句**：属于 **🟢 Tier 1**，直接裁剪死分支，拉平控制流缩进。
- **跨模块配置的石化开关**：属于 **🟡 Tier 2**，核查配置中心/环境变量与全库引用后，移除开关判断，仅保留生效主干，并级联清理死分支独占的 `LegacySyncClient` 等关联符号。

---

## 6. 注释代码坟场与墓碑注释 (Commented-Out Graveyards & Tombstones)

### 致幻机理
开发者因担心“以后可能还要参考”而将大段旧实现注释留在原函数内，或在删除代码后留下 `# 2023-05 删除旧计费逻辑，改用新接口` 等墓碑注释。Agent 在阅读上下文时，这些旧代码的变量名与调用方式会严重干扰模型的模式匹配（In-Context Learning）。

### 处置方案
- 属于 **🟢 Tier 1**：只要是注释掉的程序代码或墓碑注释，直接物理删除。版本历史由 Git 负责管理，源码文件只保留当前生效的真相。
- **区分注意**：保留合法的文档示例（如 Docstring 中明确置于 `Examples:` / `Usage:` 标题下的调用示范，且须同步核验该示范代码是否仍匹配当前 API）。

---

## 7. 误导性命名与语义倒挂 (Semantic Naming Inversion)

### 致幻机理
函数名或变量名表达的含义与函数当前实际行为完全相反或严重偏离。例如：
- 名为 `check_user_permission(user)` 或 `is_valid_order(order)` 的谓词函数，内部不仅做检查，还悄悄修改了数据库状态并发送了通知（隐式副作用）；
- 名为 `save_to_redis(data)` 的函数，内部因架构迁移早已改为写入 PostgreSQL。

### 处置方案
- 在审计过程中发现“函数名声称做 A，实际做 B”时：
  - 若属文件内部私有函数：直接在文件内重命名以匹配真实行为（🟢 Tier 1）。
  - 若属跨模块公开函数：列入 **🟡 Tier 2** 建议重命名，或在未重命名前补充准确的头部说明以消除命名欺骗。

---

## 8. 孤岛模块与检索诱饵 (Orphan Files Acting as Grep Bait)

### 致幻机理
仓库中遗留了早已脱离主调用链的脚本、旧组件、旧工具类（如 `utils_backup.py`、`UserFormOld.tsx`、`temp_test_script.py`）。当 Agent 按文件名或符号名全局检索时，这些孤岛文件作为高相似度噪音混入上下文，诱导 Agent 引用死模块或照抄已被淘汰的代码风格。

### 处置方案
- 通过导入图分析（`scripts/hygiene_scan.py` 的 `orphan_candidates`）筛选 0 入度文件。
- 排除框架路由、入口脚本、动态加载插件后，将确认为孤岛的文件列入 **🟡 Tier 2** 提请整文件删除。

---

## 9. 影子环境变量与死依赖 (Shadow Env Vars & Dead Dependencies)

### 致幻机理
例如在 `.env.example`、`config/default.yaml` 或 `docker-compose.yml` 中罗列了 30 个配置项，但当前代码中实际只读取其中 12 个；`package.json` / `requirements.txt` 中残留了早已弃用的第三方库（如同时存在 `moment`、`dayjs`、`date-fns`，而项目实际已统一为 `dayjs`）。Agent 看到依赖列表里有 `moment`，便在新代码里继续引入 `moment`，导致技术栈倒退分裂。

### 处置方案
- 抽取 `.env.example` 中的键名，在源码中执行全字匹配检索；0 引用的环境变量列入 **🟡 Tier 2** 清单。
- 核对依赖声明文件与源码真实 `import` 集合，识别已被替代的旧库并建议移除。

---

## 10. 陈旧债务标记 (Fossilized Workaround & Debt Markers)

### 致幻机理
代码中残留着数年前留下的“临时修复”说明（例如注释写着“等待下游服务升级到 v2.1 后移除此兼容逻辑”），而实际上外部服务早已升至 v4.0，或者该临时补丁已经演变为引发新问题的隐患。

### 处置方案
- 扫描所有包含时间锚点、版本号锚点或临时性词汇（`workaround`、`hack`、`temporary`、`legacy`、`deprecated`）的注释。
- 核查其前置条件是否早已满足：若对应旧兼容分支已不再需要，将其归入 **🟡 Tier 2** 提请移除；若该逻辑已成为永久性正式逻辑，则剥离“临时/Hack”等误导性措辞，直接说明其当前客观技术原因。
