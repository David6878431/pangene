# pangene

将原来的物种示例脚本整理为统一配置的 Python/Docker 生信工作流。Python 包名与命令为 **pangene-workflows**，导入名为 `pangene_workflows`，避免与已有 `pangene` 等生信工具重名。

宿主机需要 Python ≥3.11；Python 包只有标准库依赖。Docker 镜像仍负责提供各阶段的 Linux 生信软件；本包不会安装这些工具或下载大型数据库。镜像内辅助脚本要求 Python ≥3.8 和 Bash ≥4。

## 安装和起步

```bash
python -m pip install .
pangene-workflows init run01
cd run01
# 编辑 config.toml 和 samples.tsv，准备 data/，按阶段准备 database/
pangene-workflows stages
pangene-workflows validate prepare --config config.toml --check-files
pangene-workflows run prepare --config config.toml --dry-run
pangene-workflows run prepare --config config.toml
```

源码安装也可使用 `python -m pip install -e .`。下载 wheel 后用 `python -m pip install /path/to/pangene_workflows-0.1.0-py3-none-any.whl`。没有上传 PyPI，不能假设 `pip install pangene-workflows` 可从公共索引安装。也可用 `python -m pangene_workflows` 代替命令名。

`init` 不覆盖已有配置或样本表。`--dry-run` 输出阶段脚本和 Docker argv，不启动分析、不创建结果目录。默认 executor 为 Docker；Linux 原生工具环境可用 `--executor local`，此时 WORKDIR 和输入路径以配置文件为基准，样本表的相对文件路径以样本表所在目录为基准。

## 样本清单

TSV 必须是制表符分隔，有表头：

```text
sample  genome  gff  read1  read2
```

列可以按所选阶段省略；prepare 要求 genome/gff，qc 和 graph-call 要求 read1/read2。每行一个唯一 sample ID，格式 `[A-Za-z][A-Za-z0-9_.-]*`。不要从文件名猜样本，不依赖固定样本数。Docker 模式单元格示例为 `/data/sampleA.fa.gz`，宿主机样本表的位置仍填写在 SAMPLES_TSV。FASTA 第一段 ID 必须唯一，GFF3 的 ID/Parent 必须一致；不自动删 `gene:` 前缀、不替换染色体名称。规范输出基因 ID 为 `sample::原geneID`，保留含下划线的原始 ID。

## 选择路线

组装路线：`prepare → orthogroups → family-pav`；变异分支为 `alignments`、`syri`、`sequence-pav`；图分支为 `graph-build → graph-call`。

短读长路线：`prepare-reference → qc → unmapped`，随后从 `pooled-assembly`、`independent-assembly`、`iterative-assembly`、`map-to-pan` 中选择适合的策略。`map-to-pan` 直接使用 QC reads。各策略的 `novel.fa` 由你明确选择后填入 `NOVEL_FASTA`，再运行 `contaminants`。MAKER 需先准备证据和训练模型的 `.ctl`，填写 `MAKER_INDEX` 为本次预期生成的绝对输出路径后运行 `annotate`。审核后再组装 `PAN_FASTA/PAN_GENES_BED`，运行 `gene-pav`。

`prepare` 和 `prepare-reference` 都产生 `prepare/`，两者选其一。短读长样本没有自己的组装时，TSV 的 genome/gff 单元格留空；用 `REF_FASTA/REF_GFF` 单独指定参考，`REFERENCE` 可为独立名称。组装路线的 REFERENCE 则必须是 TSV 中的样本。

OrthoFinder 返回的精确 `Orthogroups.tsv` 及可选 `Orthogroups_UnassignedGenes.tsv` 要回填配置；不使用 `Results_*` 通配符猜最新结果。两个表的样本列必须与 TSV 顺序一致，必要时显式重排列。

两项目均提供可选 `eggnog` 和 `variant-annotation`。路径和分类范围由配置指定，不固定植物或真菌数据库。

| 阶段 | 输出目录 | 功能 |
|---|---|---|
| `prepare` | `prepare/` | 从任意物种 GFF3 提取最长转录本及带样本前缀的 CDS/蛋白 |
| `prepare-reference` | `prepare/` | 短读长路线单独准备参考，不要求每个测序样本均有组装 |
| `orthogroups` | `orthogroups/` | 独立样本蛋白聚类；输出明确指定目录的 OrthoFinder 结果 |
| `family-pav` | `family-pav/` | 按真实样本数生成家族拷贝数、PAV、分类及有种子的累积曲线 |
| `alignments` | `alignments/` | MUMmer 全基因组比对；保留原始染色体名称 |
| `syri` | `syri/` | Minimap2/SyRI 每个样本独立调用结构变异；输入需同向同源染色体 |
| `sequence-pav` | `sequence-pav/` | 通过参考覆盖不足识别候选新序列；输出候选而非断言真实缺失 |
| `qc` | `qc/` | 配对短读长 fastp 过滤；报告每个样本的 QC |
| `unmapped` | `unmapped/` | 提取双端均未比对的 reads；按 read name 排序保证配对 |
| `pooled-assembly` | `pooled-assembly/` | 合并未比对 reads 后 MEGAHIT 组装 |
| `independent-assembly` | `independent-assembly/` | 逐样本 MaSuRCA 组装未比对 reads，再 CD-HIT-EST 去冗余 |
| `iterative-assembly` | `iterative-assembly/` | 按样本清单顺序迭代扩充参考；参考可比性与顺序依赖需报告 |
| `map-to-pan` | `map-to-pan/` | 全 reads 独立组装后按参考覆盖筛选候选新 contig |
| `contaminants` | `contaminants/` | 对用户指定排除类群做 BLAST；仅按 identity/coverage 达标命中移除 |
| `annotate` | `annotate/` | 运行用户准备的 MAKER 证据/模型配置；保留所有预测结果供后续 QC |
| `gene-pav` | `gene-pav/` | 按基因组覆盖调用候选 gene PAV；低测序深度不等同真实缺失 |
| `graph-build` | `graph-build/` | Minigraph-Cactus 图泛基因组；所有资源上限显式指定 |
| `graph-call` | `graph-call/` | vg giraffe/pack/call 图上分型；合并保留缺失值 |
| `eggnog` | `eggnog/` | 对用户指定蛋白运行 eggNOG；数据库和可选分类范围显式配置 |
| `variant-annotation` | `variant-annotation/` | 构建 ANNOVAR 数据库并注释已规范化的 VCF；不改写未知基因型 |

不会自动把所有阶段串起来，也不把失败阶段当作完成。每次执行写入 `.pangene-workflows/runs/<UTC时间-唯一ID>/`，包含实时日志、配置哈希、阶段 argv、退出码和 `run.json`。失败停止后续阶段；Ctrl+C 尝试终止进程或移除本次容器。阶段目录已存在时拒绝覆盖；需要重跑时先明确归档旧目录，或使用新 WORKDIR/host_workdir。工具自己的 checkpoint 不等于本包提供自动恢复。

## Docker

```toml
[docker]
host_workdir = "D:/analysis/pangene/results"
host_data = "D:/analysis/pangene/data"
host_database = "D:/analysis/databases"
image = "omicsclass/pan-genome:v1.0"
annotation_image = "omicsclass/genome-annotation:v1.0"
```

Linux 改为 `/path/to/...`。镜像标签来自原脚本，**尚未在此 Windows 主机拉取或验证**。先在计算服务器检查镜像内的程序版本；版本不兼容时用自己验证过的镜像替换配置，不声称这些标签都包含新版工具。图流程的 Cactus/vg 索引格式尤其需要版本相容。

```bash
docker pull omicsclass/pan-genome:v1.0
docker run --rm --entrypoint /bin/bash omicsclass/pan-genome:v1.0 -lc 'bash --version; python3 --version'
```

每个阶段自动挂载包内脚本为只读 `/opt/workflows`、临时配置为只读 `/opt/config.sh`；结果目录读写 `/work`，输入 `/data` 与数据库 `/database` 只读。使用 `--rm --init`，无 `--group-add keep-groups`，无特权模式。目录名不能含逗号、双引号或换行（Docker --mount 语法限制）。host_data/host_database 未使用时可删除对应行，避免要求空目录。MAKER 控制文件里的路径也必须指向已挂载的位置。

线程数和内存参数见 [完整参数表](docs/parameters.md)；宿主机 Python 不消耗组装工作内存。默认只是起点，不能替代物种、数据规模和测序深度的判断。此工具不保证产生 T2T、正确 SV 或可靠缺失结论。

## 便携 Skill

`skills/pangene-workflows/` 是同名 Codex Skill，携带 wheel 和免安装启动器。把整个文件夹复制到 `~/.codex/skills/`，新会话中使用 `$pangene-workflows`（字面 `$` 加技能名）。也可直接调用：

```bash
python skills/pangene-workflows/scripts/launch.py stages
python skills/pangene-workflows/scripts/launch.py init run02
```

Skill 会配置、校验和预览命令，按已授权范围运行分析，不能替你编造 HMM、物种模型或人工确认结果。

## 验证与原流程差异

```bash
python -m unittest discover -s tests -v
```

测试覆盖配置、Docker 路径、精确 ID、HMMER model coverage、0-based domain 坐标、VCF END、PAV singleton/首行、随机曲线可重复性、PAF 区间并集和失败停止。另检查全部 Bash 语法及 wheel 的离线安装与便携 Skill。真实生物数据、大型工具和 Docker 端到端流程未在本机运行，详见 [验证记录](docs/validation.md)。

原脚本如何对应、哪些手工图形或外部辅助脚本没有自动迁移，见 [迁移说明](docs/migration.md)。原始文件保留在本地，仓库只发布规范化的新实现，未上传原数据、编辑器交换文件或凭证。
