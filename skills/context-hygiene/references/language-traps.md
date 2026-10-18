# 主流语言静态死代码工具与“假死”排雷指南 (Language Traps & Native Tools)

静态检索（Grep）显示“0 引用”并不总是等同于“死代码”。在执行 Phase 1 初筛与 Phase 3 证据分级时，请优先结合以下各语言原生工具，并严格对照“假死陷阱清单”排除隐式调用。

---

## 1. Python

### 推荐原生检测命令（若环境已安装）
- **Ruff（极速检测未使用导入、变量、注释掉的代码）**：
  ```bash
  ruff check --select F401,F811,F841,ERA001,ARG .
  ```
  - `F401`：未使用的 `import`
  - `F841`：赋值后从未读取的局部变量
  - `ERA001`（eradicate）：被注释掉的代码块
  - `ARG`（flake8-unused-arguments）：未使用的函数/方法参数
- **Vulture（静态死代码分析）**：
  ```bash
  vulture . --min-confidence 80
  ```

### Python 常见“假死”陷阱（切勿直接误删）
1. **`__all__` 与重导出（Re-exports）**：`__init__.py` 中导入但未在本文件使用的符号，若用于对外暴露包接口（如 `from .core import Client`），不可当作普通未使用导入删除，需先检查外部是否有 `from pkg import Client`。
2. **动态属性反射**：代码中存在 `getattr(obj, f"handle_{action}")`、`globals()[name]` 或 `importlib.import_module` 时，所有匹配前缀（如 `handle_*`）的方法均属于动态活跃代码。
3. **测试与框架钩子**：
   - `pytest`：`conftest.py` 中的 `@pytest.fixture` 函数通过参数名同注入，全库不会有显式函数调用。
   - `Pydantic`：`@field_validator`、`@model_validator`、`model_post_init` 由框架反射调用。
   - `Django`：`migrations/` 目录文件、`signals.py` 接收器、`admin.py` 注册类、Management Commands（`management/commands/*.py`）。
   - `FastAPI / Flask`：被路由装饰器（`@app.get`、`@router.post`）修饰的函数。
4. **AST 访问者模式**：继承自 `ast.NodeVisitor` 的类中，所有 `visit_<NodeType>` 方法均由 `generic_visit` 动态分发调用。

---

## 2. TypeScript / JavaScript (Node.js & Frontend)

### 推荐原生检测命令（若环境已安装）
- **TypeScript 编译器内建未使用检查**：
  ```bash
  npx tsc --noEmit --noUnusedLocals --noUnusedParameters
  ```
- **Knip（全项目死文件、死导出、死依赖全能扫描）**：
  ```bash
  npx knip --no-exit-code
  ```

### TS / JS 常见“假死”陷阱（切勿直接误删）
1. **文件约定式路由（File-Based Routing）**：
   - **Next.js**：`pages/**`、`app/**/(page|layout|loading|error|route|middleware|instrumentation).tsx` 及其导出的 `getServerSideProps`、`generateMetadata`、`GET`/`POST` 函数。
   - **Nuxt / Remix / Astro / SvelteKit**：`routes/`、`pages/`、`server/api/` 下的约定导出。
2. **构建工具与配置入口**：`vite.config.ts`、`webpack.config.js`、`tailwind.config.js`、`jest.config.js`、`playwright.config.ts`、`.eslintrc.*`。
3. **桶文件（Barrel Files `index.ts`）与外部库边界**：若项目是发布到 npm 的包，检查 `package.json` 的 `main`、`module`、`exports` 字段指向的入口导出。
4. **Vue / React 动态组件与全局注册**：通过字符串名称全局注册的组件（`app.component('MyComp', MyComp)`）或在模板中按约定自动导入（`unplugin-vue-components`）的组件。

---

## 3. Go

### 推荐原生检测命令（若环境已安装）
- **Go 编译与 Vet 检查**：
  ```bash
  go vet ./...
  ```
- **官方 `deadcode` 工具（基于 `main` 入口可达性分析）**：
  ```bash
  deadcode ./...
  ```
- **Staticcheck / GolangCI-Lint**：
  ```bash
  golangci-lint run --disable-all -E unused,ineffassign
  ```

### Go 常见“假死”陷阱（切勿直接误删）
1. **接口隐式实现（Implicit Interface Satisfaction）**：某个结构体的方法看似没有直接按具体类型调用，但它实现了 `io.Reader`、`fmt.Stringer`、`json.Marshaler`、`sql.Scanner`、`driver.Valuer` 或项目内部的业务 `interface`。删除前必须检索方法名在所有 `interface` 定义中的出现情况。
2. **`init()` 函数与空导入（Blank Import `_ "pkg"`）**：驱动注册、监控埋点常通过 `init()` 隐式执行。
3. **结构体标签与反射（Struct Tags & Reflection）**：被 `encoding/json`、`gorm`、`mapstructure`、`validator` 消费的导出字段。
4. **CGO 与编译指令**：带有 `//export FuncName` 或 `//go:linkname`、`//go:embed` 注释关联的变量与函数。

---

## 4. Rust

### 推荐原生检测命令
- **Cargo 原生死代码与未使用告警**：
  ```bash
  cargo check --all-targets
  ```
- **重点排查方向**：全局搜索 `#[allow(dead_code)]` 与 `#[allow(unused`——老项目中开发者常为了掩盖编译警告而顺手加上该属性，导致真正的死代码长期潜伏！

### Rust 常见“假死”陷阱（切勿直接误删）
1. **Serde 序列化回调**：`#[serde(default = "func_name", serialize_with = "...", deserialize_with = "...")]` 中通过字符串引用的函数，对编译器和简单检索而言看似无直接调用点。
2. **条件编译（Conditional Compilation）**：带有 `#[cfg(target_os = "...")]`、`#[cfg(feature = "...")]` 的模块与函数，在当前默认平台或默认 feature 下未激活，但在其他目标平台下是核心代码。运行检查时应优先使用 `cargo check --all-targets --all-features`。
3. **FFI 导出**：带有 `#[no_mangle] pub extern "C" fn` 的函数供外部 C/Python/Wasm 宿主调用。

---

## 5. Java / Kotlin (Spring / JVM)

### 推荐原生检测命令
- **Maven / Gradle 编译检查**：
  ```bash
  mvn test-compile
  ```

### JVM 常见“假死”陷阱（切勿直接误删）
1. **IoC 依赖注入与切面注解**：带有 `@Component`、`@Service`、`@Repository`、`@Controller`、`@RestController`、`@Configuration`、`@Bean`、`@Aspect`、`@Scheduled`、`@EventListener`、`@KafkaListener`、`@RabbitListener` 的类与方法由容器在运行时托管调用。
2. **MyBatis / JPA 映射**：Mapper 接口方法可能仅在 `resources/**/*.xml` 中通过 `<select id="methodName">` 关联，或由 Spring Data JPA 按方法名自动派生查询。排查 Java 死方法时必须同步检索 `.xml` 资源文件。
3. **SPI 服务发现**：检查 `META-INF/services/` 与 `META-INF/spring.factories` / `org.springframework.boot.autoconfigure.AutoConfiguration.imports` 中注册的实现类。
4. **序列化 Getter / Setter / 无参构造器**：Jackson、Fastjson、Hibernate 实体类依赖的访问器方法。
