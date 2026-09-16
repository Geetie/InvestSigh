"""`facts/` 事实表 stem 注册表 —— **stem 清单的唯一真源**，且**不依赖 pydantic**。

**为什么单独一个模块**（实测依据，不是风格偏好）：

| 事实 | 实测 |
|---|---|
| `schema/models.py` 的导入成本 | **≈1.2s** —— 其中 0.5s 是 pydantic 首次建模（`_model_construction`），与模型数量无关（一个只有 1 个类的模块也要 0.5s） |
| `tests/conftest.py` 需要 stem 清单 | 需要（`_reset_truth_source` 要把夹具副本的 22 个 `facts/*.jsonl` 清空） |
| conftest 的加载时机 | **每个 pytest 批次**都会加载 |
| 最轻的批次耗时 | `conflict` 批 **≈0.3s** |

→ 若 conftest 直接 `from schema.models import JSONL_MODELS`，则每个批次白付 ≈1.2s
（`conflict` 批会变成 ≈1.5s，**5 倍**），而这份清单的**内容**（一串 stem）与 pydantic 毫无关系。
故把清单放在本模块（导入 ≈0ms），`schema/models.py` 在**导入时**断言两者集合相等。

**"不得手工维护两份清单"是如何被强制的**（本项目栽过 4 次的那一族缺陷）：

- 本模块 = **清单本身**（22 个 stem）；
- `schema/models.py::JSONL_MODELS` = stem → 模型的映射，其**键集合**必须与本清单相等；
- 该断言在 **`models.py` 导入时**执行 —— 漂移即 `AssertionError`（**响亮失败**），
  而不是"某天有人加了第 23 张表却忘了改夹具清单"（那时夹具清空真源会**漏掉那张表**，
  测试又会依赖"真仓库恰好有什么"）。
- 测试侧另有 `tests/unit/test_schema_expand.py` 复核该等式（不在导入期，便于给出可读失败）。

**权威出处**：`09_数据与实现约束/09_需求拆解与实现方案_v1.md §3.3.3`（原 18 个 JSONL）
+ 需求方 2026-09-16 裁定（**18 → 22**，见 `system/reports/phase1_open_tensions.md::T-13` 备选②）：

| 新表 | 设计逐字出处 |
|---|---|
| `businesses` | `Ch4 §B.1`（方案比选**否决**"挂 `baselines` 下"）+ `Ch4 §0` 表第 19 行 + `Ch7 §0` 表第 19 行 |
| `drivers` | `Ch4 §D.1`（驱动对象 schema）+ `Ch4 §C.4`（`financial_link` 三层映射）+ `Ch4 §0` 表第 20 行 |
| `implied_requirements` | `Ch5 §B.2`（多组解的输出结构）+ `Ch5 §B.1/§B.3` |
| `relation_flows` | `Ch7 §B.3`（方案比选**否决**"同一 `relations` 表三行"，并给出 MSFT↔NVDA 反例）+ `Ch7 §0` 表第 19 行 |

> ⚠️ **设计区（`00_*` 与 `01_`~`11_`）仍写"18 个 JSONL"**，其回改由需求方在文档侧执行
> （`T-13` 备选② 的代价之一已如此写明）。本模块与 `models.py` 是**代码区**的事实陈述。
"""

from __future__ import annotations

__all__ = ["JSONL_STEMS"]

#: `facts/` 下全部事实表的 stem（顺序 = "公司与证券 → 产品与关系 → 来源与主张 →
#: 事件与影响 → 研究基线 → 价格与预期 → 基准与建议 → 任务与复盘"，仅是**可读分组**，
#: 不承载语义；任何消费方都必须用集合比较，不得依赖顺序）。
JSONL_STEMS: tuple[str, ...] = (
    # 公司与证券
    "industry_nodes",
    "companies",
    "securities",
    "business_positions",
    # 产品与关系
    "products",
    "relations",
    "relation_flows",          # 新增（Ch7 §B.3）：1 关系 → 0..3 流（产品流/资金流/需求信号）
    # 来源与主张
    "sources",
    "claims",
    "claim_propagation",
    # 事件与影响
    "events",
    "impacts",
    # 研究基线
    "businesses",              # 新增（Ch4 §B.1）：业务单元 + 赚钱机制
    "drivers",                 # 新增（Ch4 §D.1）：增长驱动 + 财务连接 + 增长代价
    "baselines",
    # 价格与预期
    "prices",
    "expectations",
    "implied_requirements",    # 新增（Ch5 §B.2）：价格隐含要求（多组解）
    # 基准与建议
    "benchmarks",
    "recommendations",
    # 任务与复盘
    "tasks",
    # 依赖图边
    "dependency_edges",
)
