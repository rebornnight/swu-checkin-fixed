# swu-checkin-fixed

西南大学钉钉（签到通）**自动签到脚本**：每天定时登录统一身份认证，自动完成今日签到任务。修复了 2026 年 4 月 SWU CAS 登录升级后原 [swu-checkin](https://github.com/Sorynthia/swu-checkin) 项目失效的问题。

> ⚠️ 本项目仅供学习交流与技术研究，请勿用于违反校规校纪、法律法规的用途。使用本项目产生的一切后果由使用者自行承担，详见文末[免责声明](#免责声明)。

## 功能特性

- ✅ 自动登录 SWU 统一身份认证（[详见登录流程](#登录原理)）
- ✅ 验证码自动识别（ddddocr OCR），无依赖时降级为手动输入
- ✅ 自动查询今日签到任务并提交，无需人工操作
- ✅ 自动提交宿舍定位（无视地理位置打卡），打卡时间段 21:00–23:30
- ✅ 智能状态判断：已签到自动跳过、请假中不打卡
- ✅ 定时自动运行：GitHub Actions + cron-job.org 外部触发，每天 21:30（北京时间）
- ✅ 支持手动触发（workflow_dispatch）

## 与原项目的主要改进

| 问题 | 原项目 | 本修复 |
|------|--------|--------|
| 登录路径 | `of → idm` 直连，2026-04 起失效 | 增加 `uaaap.swu.edu.cn` 联邦登录中间层，带 `federalEnable=true` |
| 加密密钥 | 硬编码密钥调用 `des()` | 从登录页**动态提取** `random` 值，用 `strEnc(data, random_key, '', '')` 3DES 加密 |
| 验证码 | 不支持（升级前无验证码） | 集成 ddddocr 自动识别，降级为手动输入 |
| Token 兑换 | 调 `callbackAuthorize` API（返回 412 反爬） | 将 uaaap 签发的 ST 转换为 CD code 格式，走正常 OAuth 回调流程 |
| CI 部署 | 无 | GitHub Actions 定时任务（cron-job.org 外部触发） |

## 登录原理

2026-04 升级后的 SWU CAS 登录链为联邦登录（`uaaap` 中间层 + 动态密钥 + 验证码）：

```
of.swu.edu.cn 获取 state
  → uaaap.swu.edu.cn（带 federalEnable=true）→ 302 到 idm.swu.edu.cn 登录页
  → 提取动态 random 密钥 / goto / SunQueryParamsString
  → 获取验证码（ddddocr OCR 或手动输入）
  → strEnc() 3DES 加密账号密码 → POST 登录
  → 跟随重定向获取 uaaap 签发的 ST
  → transform() 转换为 CD code 回调 of.swu.edu.cn
  → exchange-token 换取 fighter-auth-token
```

## 使用方法

### 方式一：本地运行（推荐先验证）

#### 环境要求

- Python 3.8+（建议 3.11，与 CI 环境一致）
- 依赖见 [`requirements.txt`](requirements.txt)：`requests` + `ddddocr`
  - `ddddocr` 仅用于自动识别登录验证码；**不安装也可以运行**，会降级为手动输入验证码（见[验证码处理](#验证码处理)）

#### 安装依赖

```bash
# 建议创建虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate  # Linux / macOS

pip install -r requirements.txt
```

#### 设置环境变量

学号（`SWU_USERNAME`）和密码（`SWU_PASSWORD`）**只能通过环境变量传入**，脚本不接收命令行参数：

```powershell
# Windows PowerShell
$env:SWU_USERNAME = "你的学号"
$env:SWU_PASSWORD = "你的密码"
```

```bash
# Linux / macOS
export SWU_USERNAME="你的学号"
export SWU_PASSWORD="你的密码"
```

#### 运行签到

```bash
python check_in.py
```

程序打印签到结果（成功 / 已签到 / 暂无任务 / 账号错误等），对应含义见[返回码](#返回码)表。

#### 只验证账号密码

想先确认账号密码、验证码链路能通，不实际打卡：

```bash
python -c "from verify import verify; print(verify('学号', '密码'))"
```

`verify()` 完整走一遍登录链（不含 token 兑换与打卡）：成功返回登录响应对象，失败返回 `None`。

### 方式二：GitHub Actions + cron-job.org 定时签到（推荐）

本仓库的 workflow **不再内置 `schedule` 定时**，原因：GitHub Actions 的 `schedule` 定时触发很不稳定（常延迟数十分钟甚至漏触发）。改用第三方 **cron-job.org** 每天准时调用 GitHub Actions API 触发 `workflow_dispatch`，免费且准时。

> 免费额度：cron-job.org 免费计划提供每年 **10,000 次请求**（最小间隔 5 分钟）。本项目每天仅触发 1 次，一年约 365 次，远低于额度。

**Step 1 — Fork / 推送仓库到你的 GitHub**

**Step 2 — 配置 Secrets**

仓库 `Settings → Secrets and variables → Actions → New repository secret`，添加两条：

| 名称 | 值 |
|------|-----|
| `SWU_USERNAME` | 学号 |
| `SWU_PASSWORD` | 密码 |

**Step 3 — 生成 Personal Access Token**

用于授权外部调用 Actions API，需勾选 **`workflow`** 权限（推荐使用 fine-grained token，仅授予本仓库）。

**Step 4 — 创建 cron-job.org 定时任务**

在 [cron-job.org](https://cron-job.org) 新建任务：

- **URL**：`https://api.github.com/repos/你的用户名/swu-checkin-fixed/actions/workflows/checkin.yml/dispatches`
- **Method**：`POST`
- **Headers**：
  - `Authorization: Bearer 你的PAT`
  - `Accept: application/vnd.github+json`
  - `Content-Type: application/json`
- **Body**：`{"ref":"main"}`
- **频率**：**强烈建议设置多个触发时间错峰打卡**，推荐每天 `21:05`、`22:05`、`23:05`（北京时间）各触发一次，保证当天必打卡成功：
  - 学校服务器在整点（如 21:00）常出现高并发，整点打卡容易失败；
  - 实测晚 5 分钟打卡（`21:05` 等）可避开服务器高峰，成功率显著更高；
  - 注意：无论是否打卡成功，钉钉都会发送一条打卡提醒——若正好卡在整点且打卡失败，就会收到失败提醒，因此**不推荐卡 `21:00` 整点打卡**；
  - 多次触发不用担心重复打卡：脚本自带去重（返回码 `2` = 今日已签到，自动跳过），安全幂等。
  - cron-job.org 默认使用 UTC 时间，需换算：北京时间 21:05/22:05/23:05 = UTC 13:05/14:05/15:05，即 cron 表达式 `05 13 * * *`、`05 14 * * *`、`05 15 * * *`；也可以在 cron-job.org 的时区设置中直接改为「Asia/Shanghai」再按北京时间填写。

**Step 5 — 验证**

- 在 cron-job.org 点一次「Run」手动执行验证；或在 GitHub Actions 页面手动 `Run workflow`
- 到 Actions 标签页查看运行日志，确认签到结果

> 提示：每次触发/执行都会消耗 GitHub 免费额度；若 cron-job 触发失败，先检查 PAT 是否过期、权限是否足够。

## 验证码处理

登录时自动从 `idm.swu.edu.cn` 获取验证码：

- **已安装 ddddocr** → 自动 OCR 识别，无需人工干预；
- **未安装 ddddocr**（ImportError）→ 验证码图片保存为当前目录 `captcha.png`，脚本提示你**手动输入**（直接输入图片上的字符回车即可）；
- OCR 识别失败时按空验证码重试；若连续失败，检查网络能否正常访问 `idm.swu.edu.cn`。

> 注意：代码已通过 `trust_env = False` 跳过系统代理，本地运行请**关闭 VPN / 代理**，否则可能 SSL 握手失败。

## 返回码

| 代码 | 含义 |
|------|------|
| 0 | 今日暂无签到任务 |
| 1 | 签到成功 |
| 2 | 今日已签到，无需重复 |
| 3 | 账号或密码验证失败 |
| 4 | 连接错误或请求超时 |
| 5 | 请假中 |

> 该表对应 `check_in()` 的返回值；直接运行 `python check_in.py` 时，脚本会把对应文案打印到控制台。

## 常见问题（FAQ）

- **提示缺少账号密码** → 先设置 `SWU_USERNAME` / `SWU_PASSWORD` 环境变量再运行。
- **返回码 3（账号或密码验证失败）** → 检查学号/密码是否正确、验证码是否识别错误。
- **返回码 4（连接错误或超时）** → 本地先确认能正常访问 `of.swu.edu.cn` 且未开代理；GitHub Actions 场景多为美国服务器连不上校园网（见下条）。
- **GitHub Actions 运行超时/连不上学校服务器** → GitHub 免费 Runner 在美国，访问 SWU 校园网可能超时。可改用阿里云·云效、腾讯云 CODING、Gitee Go 等国内 CI 平台，或本地+系统计划任务（Windows 任务计划程序 / crontab）方式运行。
- **定时任务没触发** → 先确认 cron-job.org 的时区与频率设置；再检查 PAT 是否过期或缺少 `workflow` 权限。
- **不想定时、只要手动** → 直接在 GitHub Actions 页面点 `Run workflow`，或本地运行 `python check_in.py`。
- **打卡时段是多少？** → 代码内置为 21:00–23:30（`check_in.py` 中 `qdsj` 字段），与学院要求一致。

## 文件说明

```
├── check_in.py              # 主入口：签到主逻辑 + 返回码映射
├── get_info.py              # 登录链（uaaap→federal→idm）+ token 兑换 + 信息查询
├── verify.py                # 仅验证账号密码（登录链同上，不换 token）
├── des.py                   # 3DES 加密实现（strEnc），对应前端 JS 逻辑
├── requirements.txt         # Python 依赖（requests + ddddocr）
└── .github/workflows/
    └── checkin.yml          # GitHub Actions 手动/外部触发的签到任务
```

## 项目来源

本项目源自 [Sorynthia/swu-checkin](https://github.com/Sorynthia/swu-checkin) 的签到逻辑，由 [@rebornnight](https://github.com/rebornnight) 维护修复。

## 赞赏支持

如果这个脚本帮到了你，欢迎扫码支持一下～开发维护不易，你的鼓励是持续更新的动力 🤗

<p align="center"><img src="assets/sponsor.jpg" width="220" alt="赞赏码"></p>

## 免责声明

1. 本项目仅供**学习交流与技术研究**使用，请勿用于任何违反校规校纪、法律法规的用途。
2. 使用者应自行了解并遵守西南大学及当地关于考勤、签到的相关规定；使用本项目产生的一切后果（包括但不限于学校处分、账号封禁、数据泄露等）**由使用者自行承担**。
3. 本项目涉及自动登录与打卡操作，请合理使用，不建议代替本人真实出勤行为。
4. 作者不对因使用本项目而造成的任何直接或间接损失负责，亦不对第三方修改、二次分发后的版本负责。
5. 作者**不负责本项目的后续维护与使用支持**；本项目按"现状"提供，如因学校系统升级、接口变更等导致失效，请使用者自行处理，作者不承担任何后续维护义务。
6. 使用本项目即视为同意以上条款；不同意请勿使用。