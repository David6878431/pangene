---
name: pangene-workflows
description: 配置、检查和运行 pangene 的组装型或短读长泛基因组 Python/Docker 工作流，解释 PAV、变异和图结果。用于 pangene-workflows 包及其配置，不用于通用生物学问答。
---

# pangene 工作流

用本技能携带的 Python 包配置和运行分析。宿主机 Python ≥3.11，Docker 镜像内辅助脚本 Python ≥3.8、Bash ≥4。宿主机不必 pip 安装：

```bash
python <skill-dir>/scripts/launch.py stages
python <skill-dir>/scripts/launch.py init /path/to/run
python <skill-dir>/scripts/launch.py validate prepare --config /path/to/run/config.toml --check-files
python <skill-dir>/scripts/launch.py run prepare --config /path/to/run/config.toml --dry-run
```

## 配置与执行

先检查已有配置、样本清单和已完成阶段；不覆盖 init 已存在的文件。参数含义不明确时读取 [参数参考](references/configuration.md)，迁移和结果边界读取 [路线参考](references/workflows.md)。

样本表以制表符分隔，sample 唯一；genome/gff/read1/read2 按所选阶段需要填写。Docker pipeline 数据路径是容器绝对路径，SAMPLES_TSV 是宿主机路径；host_* 相对于 TOML。local 的数据路径相对配置，样本表内相对路径相对样本表。工具输出基因 ID 为 sample::gene，保留 ids.tsv 中原 gene/transcript 的精确映射，不拆下划线或模糊 grep。

按所选阶段校验、检查文件、dry-run 查看实际 argv 和脚本；授权已经覆盖执行时继续运行，无需重复确认。仅缺少影响结果的输入或决定时询问。数据或模型不可用时保留可复现配置/预览并解释缺项，不制造科学结果。

每阶段实时日志和 run.json 在配置同目录的 .pangene-workflows/runs/。失败即停止后续阶段；结果目录已存在会拒绝覆盖，明确归档或改用新工作目录后再重跑，不自动删除数据。Docker 与真实生信工具没有在作者 Windows 主机端到端验证；原镜像标签可能需要按实际版本调整。

## 本流程的关键约束

组装路线使用 prepare → orthogroups → family-pav；OrthoFinder 的精确输出路径要回填，不能用 Results_* 猜测。短读长路线使用 prepare-reference（REF_FASTA/REF_GFF）→ qc → unmapped，然后选择合适的组装策略。prepare-reference 不要求每个 reads 样本有自己的组装。不要一次运行所有互斥的组装分支。novel 输出经明确选择与 QC 后再进入污染过滤和 MAKER；MAKER 配置/训练物种模型由用户数据决定。gene-pav 的 0 是覆盖不足的候选缺失。图流程需确认 Cactus/vg 及索引版本一致。

不把 ./ . 缺失基因型改成参考，不把低覆盖或未注释直接断言为真实基因缺失。所有生信阈值应结合目标物种、深度和设计判断。运行分析的授权不包含将序列、数据库、凭证或结果发布到 GitHub。
