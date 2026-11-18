# 气候指标指标分析

项目保存气候指标的来源版次，按资料取得时间比较单期指标并给出区域规则判断。evidence 保存来源，
metrics 计算同口径偏离，context 解释当前区域规则，lineup 做跨指标联读，revisions 分析修订影响，
report 保存不可变报告。样本是合成数据。

## 解决的问题

政策简报同时解释地球能量失衡（energy）、海洋热含量（ocean_heat，分浅层/深层产品）和
海平面变化（sea_level）。三条曲线同向不等于存在确定因果链；且能量收支近期值是初步值、
海平面月值与海洋深层产品发布周期不同。本项目让每项观测保留观测期间、发布时点、修订状态
和空间覆盖，联读时区分：

- **可同时比较的证据**：共同观测窗口内、覆盖适配且非初步值的观测；
- **尚不能支持的判断**：初步值、覆盖只能层级近似、期间不重叠，逐条记为 blocker/caveat；
- **缺口**：尚未发布的产品、等待修订的初步值、发布滞后天数；
- **共变不是因果**：即使三指标同向，causal_claim_supported 恒为 false。

初步值修订后，`impact` 命令指出哪些原结论因依据记录换版而失去依据、哪些因依据未修订仍成立、
哪些是缺口补齐后新获得依据；旧报告由指纹封存，不会被新数字改写。

Python 3.11 以上，在项目根目录执行：

    python -m unittest discover -s tests -v
    python -m compileall -q climate_analysis tests
    python -m climate_analysis.cli inspect data/example.json
    python -m climate_analysis.cli impact data/example.json

Dockerfile 可在 Linux 容器运行：docker build -t climate-analysis-007 .；docker run --rm climate-analysis-007。
