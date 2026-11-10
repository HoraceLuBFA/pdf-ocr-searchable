# pdf-ocr-searchable 安装指南

源码仓库：https://github.com/HoraceLuBFA/pdf-ocr-searchable
详情页：https://www.lumenghe.com/skills/pdf-ocr-searchable/
发布元数据：https://www.lumenghe.com/skills/pdf-ocr-searchable/release.json
当前安装包及校验值：https://www.lumenghe.com/skills/pdf-ocr-searchable/install.txt

从详情页或发布元数据选定版本、来源提交、ZIP 下载链接及 SHA-256，记录这组信息后再下载。安装依据用户本次授权执行，并保留已有安装与本地修改。

## 安装前

1. 识别操作系统、当前编码 Agent 和所用宿主；读取本页 README 与依赖条件。仅支持 macOS。检查 Homebrew、uv、OCRmyPDF、ocrmypdf-appleocr、Ghostscript 和 Poppler；OCRmyPDF 与插件必须在同一 Python 环境。ZIP 不包含这些依赖。按 README 的命令安装缺失依赖，检查插件可用性；未处理真实 PDF 时只报告依赖检查结果，不宣称 OCR 全流程已验收。
2. 以只读方式检查 ~/.agents/skills/pdf-ocr-searchable 以及宿主中的同名入口，包括目录、文件、符号链接及断开的符号链接。存在任何同名内容时，先报告当前版本和本地修改；先备份，再由用户决定合并或替换，不静默覆盖、删除或 reset。不要修改宿主的其他配置、其他技能或已有认证。
3. 从选定发布元数据中的 HTTPS 下载地址下载完整 ZIP 到临时工作目录。计算 SHA-256 并与当前官网发布信息逐字比较；摘要缺失、仍是模板占位或不匹配时停止，不安装。README 同时提供 GitHub 安装入口，可按本次选定的方式安装。

## 解压与安装

4. 解压前检查 ZIP 成员路径：只允许一个 pdf-ocr-searchable/ 根目录，拒绝绝对路径、.. 路径穿越和将内容写出目标目录的链接。完整包应有 pdf-ocr-searchable/SKILL.md、README.md、README.en.md、LICENSE 及原有脚本和参考文件。不要只下载 SKILL.md。
5. 解压到临时目录并确认文件清单。保留目录结构和可执行权限；尤其不要把 pdf-ocr-searchable/pdf-ocr-searchable/ 两层根目录当成正确安装。确认目标不存在后，将整个 pdf-ocr-searchable/ 文件夹放到 ~/.agents/skills/pdf-ocr-searchable/。现有指令和脚本引用此共享真身路径，不随意改成其他位置。
6. 按宿主设置发现入口。Codex 的个人技能目录为 ~/.agents/skills；Claude Code 的个人入口为 ~/.claude/skills。仅当 Claude Code 的 ~/.claude/skills/pdf-ocr-searchable 不存在且不是断开链接时，建立指向 ~/.agents/skills/pdf-ocr-searchable 的符号链接；存在时检查并报告，不覆盖。其他宿主按其当前官方文档配置，不能宣称所有 Agent 都自动扫描共享目录。

## 验证与交付

7. 检查 SKILL.md 和必要脚本、参考文件可读；有需要的脚本权限正确。通过宿主技能列表、显式点名或新会话确认技能发现。文件已写入、宿主已发现、依赖已就绪、实际任务已通过是不同结论，分别报告。用最小且不改动用户原件的样例验证需要验证的行为。
8. 报告安装目录、来源版本和提交、下载摘要、宿主发现结果、依赖缺口，以及为已有安装保留的备份位置。不要在报告中输出认证值；需要用户交互登录时交由用户完成。

目录发现依据：
- OpenAI 官方文档：https://learn.chatgpt.com/docs/build-skills
- Claude Code 官方文档：https://code.claude.com/docs/en/skills
