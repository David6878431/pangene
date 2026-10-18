# 迁移与结果解释

旧脚本是特定数据集的操作记录，不把其中路径和示例参数视为用户此次的分析指令。源文件保留在原路径，未改动；仓库忽略原脚本与交换文件。

| 原脚本 | 新实现 |
|---|---|
| shells/01、02、03 | prepare、orthogroups、family-pav、eggnog |
| shells/04、05、06 | alignments、syri、sequence-pav、variant-annotation |
| shells/10、11 | graph-build、graph-call |
| shells2/01、02 | prepare-reference、qc |
| shells2/11、12、13、14 | unmapped 加相应组装策略 |
| shells2/20、30、40、41 | contaminants、annotate、gene-pav、真实多样本 orthogroups/family-pav |

shells3 与 shells2 的编号脚本重复，不作为第二条独立流程。两个 _1 重复脚本也不发布。

MUMmer 输出保留为 raw VCF：不同 delta2vcf 版本的 header/FORMAT 不一致，不能机械把 0: 改成 1/1: 或把 ./ . 改参考。多样本 VCF 合并需先规范化并确保可分型区域；本包不再用“没检测到”代替“参考纯合”。SyRI 保留逐样本输出，不在缺乏共同 callable regions 时拼成虚假的完整基因型矩阵。方向需先人工检查；重定向 query 染色体后必须重比对，不能混用原 mdelta。

sequence-pav/map-to-pan 现在筛选低参考覆盖的整 contig，按 PAF query 区间并集计数，不沿用特定 QUAST 报表字段或把 fasta header 反向解析成坐标。它们是保守的候选 novel-contig 分支，不是逐碱基互补区间的等价实现；保留报告供审核。

未比对 reads 要求 read 和 mate 均 unmapped（flag 12），排除 secondary，name-sort 后提取；不把单端未比对记录直接当成有效成对输入。MEGAHIT 使用双端文件，未自动混入单端 reads。迭代路线受样本顺序影响，按清单顺序执行。

污染策略只移除用户明确列出的 taxid 范围内、identity 和 query coverage 同时达标的命中；这并不证明其余 contig 无污染。旧脚本将真菌列入排除库、0.8 当百分比等选择不再沿用。MAKER 依赖经训练的模型和证据配置；不自动将没有 eggNOG 命中的基因当成假基因剔除。

gene-pav 使用 BED4 基因区间的覆盖比例，替代未附带的 SGSGeneLoss.jar；与旧 exon-based 算法并不数值等价。0 是覆盖不足的候选缺失，可受低深度/重复序列/比对偏差影响，不是确认的基因缺失。家族 PAV 必须从真实多样本蛋白聚类获得，取消复制同一份蛋白作两个假样本。

原脚本引用但未附带的自定义 R/Perl 绘图、GO/KEGG 富集、交互式 Bandage/TubeMap、Circos 特定染色体布局没有静默复制或伪造依赖。现在导出标准 TSV、GFF3、FASTA、VCF、树和 motif 结果，保留这些功能的可复现输入；专门统计/绘图应基于你的设计单独添加。

工具接口参考：[HMMER domtblout](https://github.com/EddyRivasLab/hmmer/blob/master/documentation/userguide/tabular.tex)、[SyRI](https://github.com/schneebergerlab/syri)、[OrthoFinder](https://orthofinder.github.io/OrthoFinder/tutorials/beginner-tutorial/)、[Minigraph-Cactus](https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/pangenome.md)、[samtools fastq](https://www.htslib.org/doc/samtools-fasta.html)、[vg](https://github.com/vgteam/vg/wiki/Basic-Operations)、[PAL2NAL](https://www.bork.embl.de/pal2nal/)。接口随版本改变，以实际镜像内 --help 为准。
