# 贡献指南

感谢你对 **trading-agents.skill** 的关注！在提交代码之前，请阅读以下流程。

---

## 分支保护规则

`main` 分支受保护，**任何人（包括管理员）不得直接 push**。所有变更必须通过 Pull Request 合并。

---

## 贡献流程

1. **Fork 或新建分支**

   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **在本地完成开发并测试**

   - 运行脚本验证：
     ```bash
     uv sync
     uv run python scripts/fetch_market_data.py AAPL
     uv run python scripts/technical_indicators.py AAPL
     ```
   - 如涉及智能体提示词改动，请手动触发完整分析流程验证输出。

3. **提交规范（Conventional Commits）**

   提交信息必须遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式，并带 `--signoff`：

   ```bash
   git commit -s -m "feat: add new analyst agent for macro analysis"
   ```

   常用前缀：

   | 前缀 | 适用场景 |
   |------|----------|
   | `feat:` | 新功能 |
   | `fix:` | 缺陷修复 |
   | `refactor:` | 重构，不改变外部行为 |
   | `docs:` | 文档更新 |
   | `chore:` | 构建/配置/依赖变更 |
   | `test:` | 测试相关 |

4. **发起 Pull Request**

   - 推送分支到远端后，在 GitHub 上创建 PR，**按模板填写完整描述**。
   - PR 标题同样遵循 Conventional Commits 格式。
   - 至少需要 **1 名 Code Owner 审批**后方可合并。

5. **Code Review**

   - Reviewer 会在 1–2 个工作日内回复。
   - 请根据反馈及时更新代码；新的 push 会使已有的 approve 失效，需重新审批。

---

## 代码规范

- Python 脚本遵循 [PEP 8](https://peps.python.org/pep-0008/)。
- 智能体提示词（`agents/*.md`）中的模板占位符使用 `{TICKER}`、`{DATE}`、`{SKILL_PATH}`、`{OUTPUT_DIR}` 格式。
- 所有分析报告**不得包含**内部文件系统路径；引用其他报告时只写文件名。
- 分析报告末尾必须包含 AI 免责声明。

---

## 问题反馈

如发现 Bug 或有功能建议，欢迎[提交 Issue](../../issues/new)。
