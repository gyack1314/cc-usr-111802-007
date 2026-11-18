# 气候指标数据约定

observation、reference、rule、claim 四种记录分别表示观测、参照、区域规则和简报主张。
metric、region、unit 共同表示单期可比口径，来源版次与取得时间独立保留。

## 观测记录必备元数据

每条 observation 的 payload 除 metric/region/unit/value 外，必须包含：

| 字段 | 含义 |
| --- | --- |
| period_start / period_end | 观测期间（ISO 日期），结束不得早于开始 |
| published_at | 该版次的发布时点（ISO 时间），与文档 received_at 独立 |
| revision_status | 修订状态，取值限于 preliminary（初步）、revised（已修订）、final（定稿） |
| spatial_coverage | 空间覆盖代码，见下表 |

空间覆盖层级（父完全包含子）：

```
global
└─ global_ocean
   ├─ ocean_0_700m
   └─ ocean_700_2000m
```

联读时按 coverage_fit 判定 exact（一致）、nested（层级包含，只能带保留外推）或 none（不兼容）。

## 简报主张（claim）

claim 由简报编制组登记，payload 含：metrics（参与联读的指标）、scope（要求覆盖范围）、
require_coverage_exact（必须精确匹配覆盖的指标，其余允许层级近似）、expect_direction（期望方向）。
初步值、覆盖不足、期间不重叠、缺系列分别形成 blocker，不满足时主张不得写成确定结论；
即使全部满足，同向也只记为共变，causal_claim_supported 恒为 false——因果链需要额外证据，
不能由三条曲线同向推出。

## 已知时点与不可变性

报告绑定 known_at：只采用该时点之前 received_at 可见的版次。观测修订以新 record revision
入库（r1→r2），旧版次不删除、不覆盖。每个报告带 sha256 指纹；修订只产生新时点报告，
旧报告不能被新数字回写。revisions 模块比较两个时点，标注每项原结论“失去依据/仍成立/新增”。
