# swu-checkin-fixed

本项目用于西南大学钉钉无视地理位置自动定位打卡，修复了 2026 年 4 月 SWU CAS 登录升级后原 [swu-checkin](https://github.com/Sorynthia/swu-checkin) 项目失效的问题。改变了原来的硬编码方式和登录方式，签到方式基本不变。

每天 21:30（北京时间）自动签到，由 cron-job.org 外部定时触发 GitHub Actions 运行。

## 功能

- 自动登录 SWU 统一身份认证（支持验证码 OCR 识别）
- 自动查询今日签到任务并提交
- 检测是否已签到，避免重复打卡
- 检测请假状态，请假中不打卡
- 定时自动运行（cron-job.org 外部定时触发 GitHub Actions）
- 手动触发运行（workflow_dispatch）

## 与原项目的主要改进

| 问题 | 原项目 | 本修复 |
|------|--------|--------|
| 登录路径 | `of → idm` 直连，2026-04 失效 | 增加 `uaaap.swu.edu.cn` 联邦登录中间层，带 `federalEnable=true` |
| 加密密钥 | 硬编码密钥调用 `des()` | 从登录页动态提取 `random` 值，用 `strEnc(data, random_key, '', '')` 3DES 加密 |
| 验证码 | 不支持（升级前无验证码） | 集成 ddddocr 自动识别，降级为手动输入 |
| Token 兑换 | 调 `callbackAuthorize` API（返回 412 反爬） | 将 uaaap 签发的 ST 转换为 CD code 格式，走正常 OAuth 回调流程 |
| CI 部署 | 无 | GitHub Actions 定时任务（cron-job.org 外部触发），每天 21:30 自动签到 |

## 使用方法

### 本地运行

#### 环境要求

- Python 3.8+（建议 3.11，与 CI 环境一致）
- 依赖见 `requirements.txt`：`requests` + `ddddocr`（ddddocr 仅用于自动识别登录验证码，可不装，见下文"验证码处理"）

#### 步骤

```bash
# 1. 安装依赖（建议先创建虚拟环境）
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate  # Linux / macOS
pip install -r requirements.txt

# 2. 设置环境变量（学号 + 密码）
# Windows PowerShell
$env:SWU_USERNAME = "你的学号"
$env:SWU_PASSWORD = "你的密码"
# Linux / macOS
export SWU_USERNAME="你的学号"
export SWU_PASSWORD="你的密码"

# 3. 运行签到
python check_in.py
```

程序会打印签到结果（成功 / 已签到 / 暂无任务 / 账号错误等），对应返回码见下表。

#### 验证码处理

登录时自动从 `idm.swu.edu.cn` 获取验证码：

- **已安装 ddddocr** → 自动 OCR 识别，无需人工干预；
- **未安装 ddddocr**（ImportError）→ 验证码图片保存为当前目录 `captcha.png`，脚本提示你手动输入验证码（直接输入图片上的字符回车即可）；
- 识别失败时按空验证码重试，若连续失败请检查网络能否正常访问 `idm.swu.edu.cn`。

#### 常见问题

- **提示缺少账号密码** → 先设置 `SWU_USERNAME` / `SWU_PASSWORD` 环境变量再运行；
- **返回码 3（账号或密码验证失败）** → 检查学号/密码是否正确、验证码是否识别错误；
- **返回码 4（连接错误或超时）** → 脚本已通过 `trust_env=False` 跳过系统代理，若你的网络必须走代理才能访问学校站点，请自行适配；
- **只验证账号密码** → 可临时用 `python -c "from verify import verify; print(bool(verify('学号', '密码')))"`（`verify.py` 为库，无独立入口）。

### GitHub Actions + cron-job.org 定时签到

> 说明：本仓库的 workflow 不再内置 `schedule` 定时。由于 **GitHub Actions 的 `schedule` 定时触发非常不稳定**（常出现延迟数十分钟甚至漏触发的情况），因此改用第三方 **cron-job.org** 每天定时调用 GitHub Actions API 触发 `workflow_dispatch` 运行，触发准时且免费。
>
> 免费额度：cron-job.org 免费计划提供 **每年 10,000 次请求**（最小执行间隔 5 分钟）。本项目每天仅触发 1 次，一年约 365 次，**远低于免费额度**，无需付费。

1. Fork / 推送本仓库到 GitHub
2. 在仓库 Settings → Secrets and variables → Actions 中添加：
   - `SWU_USERNAME` — 学号
   - `SWU_PASSWORD` — 密码
3. 生成一个 Personal Access Token（需勾选 `workflow` 权限），用于授权外部调用
4. 在 [cron-job.org](https://cron-job.org) 创建一个定时任务：
   - **URL**：`https://api.github.com/repos/你的用户名/swu-checkin-fixed/actions/workflows/checkin.yml/dispatches`
   - **Method**：`POST`
   - **Headers**（在 cron-job.org 的请求头设置里添加）：
     - `Authorization: Bearer 你的PAT`
     - `Accept: application/vnd.github+json`
   - **Body**：`{"ref":"main"}`（POST body）
   - 设置执行频率：每天 21:30（注意 cron-job.org 默认 UTC 时间，需按北京时间换算或调整时区）
5. 保存后可在 cron-job.org 手动执行一次验证，也可在 GitHub Actions 页面手动 Run workflow

> 提示：GitHub Actions 每次触发/执行都会消耗免费额度，若发现 cron-job 触发失败，请检查 PAT 是否过期或权限不足。

## 返回码

| 代码 | 含义 |
|------|------|
| 0 | 今日暂无签到任务 |
| 1 | 签到成功 |
| 2 | 今日已签到，无需重复 |
| 3 | 账号或密码验证失败 |
| 4 | 连接错误或请求超时 |
| 5 | 请假中 |

## 文件说明

```
├── check_in.py      # 主入口：签到主逻辑 + 返回码映射
├── get_info.py      # 登录链（uaaap→federal→idm）+ token兑换 + 信息查询
├── verify.py        # 仅验证账号密码（登录链同上不换token）
├── des.py           # 3DES 加密实现（strEnc），对应前端 JS 逻辑
└── .github/workflows/checkin.yml  # GitHub Actions 定时任务配置
```

## 项目来源

本项目源自 [Sorynthia/swu-checkin](https://github.com/Sorynthia/swu-checkin) 的签到逻辑，由 [@rebornnight](https://github.com/rebornnight) 维护修复。

## 免责声明

1. 本项目仅供**学习交流与技术研究**使用，请勿用于任何违反校规校纪、法律法规的用途。
2. 使用者应自行了解并遵守西南大学及当地关于考勤、签到的相关规定；使用本项目产生的一切后果（包括但不限于学校处分、账号封禁、数据泄露等）**由使用者自行承担**。
3. 本项目涉及自动登录与打卡操作，请合理使用，不建议代替本人真实出勤行为。
4. 作者不对因使用本项目而造成的任何直接或间接损失负责，亦不对第三方修改、二次分发后的版本负责。
5. 作者**不负责本项目的后续维护与使用支持**；本项目按"现状"提供，如因学校系统升级、接口变更等导致失效，请使用者自行处理，作者不承担任何后续维护义务。
6. 使用本项目即视为同意以上条款；不同意请勿使用。
