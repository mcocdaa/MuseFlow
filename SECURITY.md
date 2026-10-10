# 安全策略 (Security Policy)

## 支持的版本 (Supported Versions)

我们仅针对最新主分支 (`main`) 及发布的稳定版本提供安全更新与技术维护。

| 版本 (Version) | 支持状态 (Supported) | 说明 |
| :--- | :--- | :--- |
| `0.1.x` | :white_check_mark: 当前主线支持 | 推荐所有用户与开发者部署 |
| `< 0.1.0` | :x: 不再维护 | 历史预览版本 |

---

## 漏洞报告 (Reporting a Vulnerability)

如果您在 **MuseFlow (灵眸流)** 中发现了任何安全漏洞（包括但不限于：任意路径遍历、未授权文件访问、流媒体 Range 越界泄露、沙箱穿透或第三方依赖已知漏洞），请**不要**直接公开发布 GitHub Issue。

请通过以下途径向维护团队报告：
1. **GitHub Private Vulnerability Reporting**：在仓库顶部的 **Security** -> **Advisories** -> **Report a vulnerability** 提交加密报告。
2. **Email 联系**：发送至维护者公开主页邮箱 (`mcocdaa` / `2021137961@qq.com`)，标题注明 `[SECURITY] MuseFlow Vulnerability Report`。

### 报告时请尽可能包含以下信息：
- 漏洞类别及潜在危害评估（如本地文件包含、越界读取等）。
- 受影响的模块、操作系统环境（Linux / Windows / macOS）与重现版本。
- 最小可复现步骤 (Minimal Reproducible Example / PoC)。
- 任何修复建议或临时缓解方案。

### 响应承诺
- 维护团队将在 **48 小时** 内完成初步审阅并给出评估反馈。
- 修复补丁将在独立私有分支上验证完毕后发布正式安全更新，并在安全通告中公开致谢报告者。
