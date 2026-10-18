# 验证记录

日期：2026-10-18。环境：Windows 11、Python 3.12.14、Git Bash 5.2。

- 16 项标准库 unittest 全通过；包括真实 Bash → 生成配置 → 包内数据脚本 → 结果 TSV 的联动执行，并验证再次执行拒绝覆盖。
- 21 个 Bash 文件全部通过 `bash -n`。
- wheel 无依赖离线安装到隔离目录后，在项目目录外调用 CLI、init、stages 和 data 工具。
- 便携 Skill 启动器使用所带 wheel 测试 init/stages/validate/dry-run，Skill Creator 验证结构。
- sdist 可重新生成包含相同 Python/工作流源码的 wheel。

没有 Docker 可执行程序，没有拉取镜像或运行大型生信工具，没有在真实生物数据上做性能或科学准确性验证。以上测试证明软件封装和所测数据逻辑可用，不证明整套计算在任意镜像或物种中必然成功。镜像标签和工具版本需在实际计算服务器确认；GitHub Actions 已配置，但远端执行结果单独报告。
