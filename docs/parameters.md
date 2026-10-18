# 参数说明

未设置的可选路径为空字符串。所选阶段的必要输入缺失时，命令会在执行前报错。

| 参数 | 默认值 | 含义 |
|---|---|---|
| `SAMPLES_TSV` | `"samples.tsv"` | 宿主机样本表路径，相对于此 TOML；表头见下文。 |
| `WORKDIR` | `"./results"` | 仅 local 模式使用的结果目录；Docker 固定为 /work，由 host_workdir 绑定。 |
| `REFERENCE` | `""` | 参考的样本名。组装路线必须出现在样本表；短读长路线可指定独立参考名。 |
| `THREADS` | `8` | 工具主线程数，正整数；管道两端可能同时运行，并非总 CPU 严格配额。 |
| `SOFTCORE` | `0.95` | softcore 最低出现比例，默认 0.95；全部样本出现先判 core，单样本先判 private。 |
| `PERMUTATIONS` | `100` | 泛/核心累积曲线的随机排列次数，正整数。 |
| `SEED` | `42` | 累积曲线和树推断的随机种子，非负整数。 |
| `ORTHOGROUPS_TSV` | `""` | OrthoFinder Orthogroups.tsv 完整路径；列名及顺序须与样本表一致。 |
| `UNASSIGNED_TSV` | `""` | 可选 Orthogroups_UnassignedGenes.tsv；同样列序，用于保留 singleton。 |
| `PROTEIN_FASTA` | `""` | eggNOG 输入蛋白 FASTA。 |
| `EGGNOG_DB` | `""` | eggNOG-mapper 数据库目录，含 eggnog_proteins.dmnd。 |
| `TAX_SCOPE` | `""` | 可选 eggNOG 分类范围；留空采用工具默认值，物种范围由用户选择。 |
| `REF_GFF` | `""` | 参考基因组 GFF3；variant-annotation 或 prepare-reference 输入。 |
| `REF_FASTA` | `""` | 参考 FASTA；与 REF_GFF/VCF 序列名称、坐标版本必须一致。 |
| `VARIANT_VCF` | `""` | ANNOVAR 输入的规范化 VCF，可 .gz；保留原始缺失基因型。 |
| `NEAR_GENE` | `2000` | ANNOVAR near-gene 距离，bp。 |
| `ORTHO_THREADS` | `2` | OrthoFinder 内部分析线程 -a，独立于搜索线程 -t。 |
| `MIN_IDENTITY` | `90` | MUMmer delta-filter 最低 identity，百分比 0–100。 |
| `MIN_ALIGNMENT` | `100` | MUMmer delta-filter 最低比对长度，bp。 |
| `ASM_PRESET` | `"asm10"` | minimap2 asm5/asm10/asm20，比对发散程度须按样本选择。 |
| `MIN_CONTIG` | `500` | 候选 contig 最短长度，bp。 |
| `MAX_REF_COVERAGE` | `0.2` | 候选 novel contig 在参考上比对覆盖比例的最大值，默认 0.2；按 query 区间并集计算。 |
| `QUALITY` | `20` | fastp 合格碱基最低 Phred 值。 |
| `UNQUALIFIED` | `40` | fastp 允许低质量碱基的百分比 0–100。 |
| `N_BASE_LIMIT` | `5` | fastp 每 read 的 N 上限。 |
| `SORT_MEMORY` | `"1G"` | samtools sort 每线程内存，如 1G；总量与线程数有关。 |
| `MEGAHIT_MEMORY` | `0.4` | MEGAHIT -m 内存比例 0–1，默认 0.4。 |
| `CLUSTER_IDENTITY` | `0.95` | CD-HIT-EST 序列 identity 比例，默认 0.95；须符合安装版本的 word length 限制。 |
| `CLUSTER_MEMORY_MB` | `16000` | CD-HIT-EST 内存上限，MB；默认 16000，不使用无限制的 -M 0。 |
| `NOVEL_FASTA` | `""` | 由用户明确选择的候选新序列 FASTA，不默认选某一种组装策略。 |
| `NT_DATABASE` | `""` | BLAST nt 数据库前缀，非单个 FASTA；检查前缀或同名前缀的分卷。 |
| `EXCLUDE_TAXIDS` | `""` | 用户选择要排除的 taxid 列表，每行一个；不要将自己的目标类群误列入。 |
| `BLAST_EVALUE` | `"1e-5"` | 污染比对 E-value，必须正且有限。 |
| `CONTAM_IDENTITY` | `95` | 判定候选污染所需最低 BLAST identity，百分比。 |
| `CONTAM_COVERAGE` | `80` | 判定候选污染所需最低 query coverage，百分比。 |
| `MAKER_OPTS` | `""` | 用户事先生成并编辑的 maker_opts.ctl；genome、证据、模型都用执行环境绝对路径。 |
| `MAKER_BOPTS` | `""` | maker_bopts.ctl 输入路径。 |
| `MAKER_EXE` | `""` | maker_exe.ctl 输入路径。 |
| `MAKER_INDEX` | `""` | 本次 MAKER 预计生成的 master_datastore_index.log 绝对路径；属于输出，启动前不要求已存在。 |
| `PAN_FASTA` | `""` | 已审核的参考+novel 泛基因组 FASTA；本工具不猜选哪套 novel 结果。 |
| `PAN_GENES_BED` | `""` | 与 PAN_FASTA 一致的 BED4：chrom/start0/end/gene；gene ID 唯一，不可有额外列。 |
| `MIN_MAPQ` | `20` | 比对质量阈值；gene-pav 用于 samtools，graph-call 用于 vg pack（具体含义以该版本帮助为准）。 |
| `MIN_DEPTH` | `2` | 被认作覆盖的碱基最低深度。 |
| `GENE_COVERAGE` | `0.8` | 覆盖基因长度比例达到此值判候选存在；0 仅为覆盖不足的候选缺失。 |
| `CACTUS_MEMORY` | `"32Gi"` | Cactus 总内存上限，如 32Gi；需与实际 Docker 可用内存匹配。 |
| `GRAPH_PREFIX` | `""` | 与所安装 vg 版本相容的图索引公共前缀，需要 .gbz/.min/.dist/.snarls。 |

## Docker 参数

使用 Docker 运行本流程需要相应的生信镜像。**需要 Docker 镜像，请联系 [1394248709@qq.com](mailto:1394248709@qq.com)。** 镜像文件单独提供；导入后以实际镜像名和标签设置下方参数。

| 参数 | 含义 |
|---|---|
| `host_workdir` | 宿主机可写结果目录，运行时创建并挂载到 `/work`。 |
| `host_data` | 已存在的宿主机输入目录，只读挂载到 `/data`。不需要时删除此项。 |
| `host_database` | 已存在的宿主机数据库目录，只读挂载到 `/database`。不需要时删除此项。 |
| `image` | 主流程镜像，使用原脚本引用的标签；可以改为自己验证过的 digest。 |
| `annotation_image` | MAKER/eggNOG 等注释阶段使用的镜像，可独立配置。 |

所有宿主机相对路径以 TOML 所在目录为基准。挂载目录不得彼此包含或重叠。Docker 的 pipeline/TSV 文件路径必须是 `/data/...`、`/database/...`、`/work/...` 等 POSIX 绝对路径。`SAMPLES_TSV` 本身始终是宿主机路径。
