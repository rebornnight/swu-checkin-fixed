# swu-checkin-fixed

本项目用于西南大学钉钉无视地理位置自动定位打卡，修复了 2026 年 4 月 SWU CAS 登录升级后原 [swu-checkin](https://github.com/Sorynthia/swu-checkin) 项目失效的问题。改变了原来的硬编码方式和登录方式，签到方式基本不变。

每天 21:30（北京时间）自动签到，支持 GitHub Actions 定时运行。

## 功能

- 自动登录 SWU 统一身份认证（支持验证码 OCR 识别）
- 自动查询今日签到任务并提交
- 检测是否已签到，避免重复打卡
- 检测请假状态，请假中不打卡
- 定时自动运行（GitHub Actions）
- 手动触发运行（workflow_dispatch）

## 与原项目的主要改进

| 问题 | 原项目 | 本修复 |
|------|--------|--------|
| 登录路径 | `of → idm` 直连，2026-04 失效 | 增加 `uaaap.swu.edu.cn` 联邦登录中间层，带 `federalEnable=true` |
| 加密密钥 | 硬编码密钥调用 `des()` | 从登录页动态提取 `random` 值，用 `strEnc(data, random_key, '', '')` 3DES 加密 |
| 验证码 | 不支持（升级前无验证码） | 集成 ddddocr 自动识别，降级为手动输入 |
| Token 兑换 | 调 `callbackAuthorize` API（返回 412 反爬） | 将 uaaap 签发的 ST 转换为 CD code 格式，走正常 OAuth 回调流程 |
| CI 部署 | 无 | GitHub Actions 定时任务，每天 21:30 自动签到 |

## 使用方法

### 本地运行

```bash
# 安装依赖
pip install requests ddddocr

# 运行签到
SWU_USERNAME="你的学号" SWU_PASSWORD="你的密码" python check_in.py
```

### GitHub Actions 定时签到

1. Fork / 推送本仓库到 GitHub
2. 在仓库 Settings → Secrets and variables → Actions 中添加：
   - `SWU_USERNAME` — 学号
   - `SWU_PASSWORD` — 密码
3. 每天 21:30（北京时间）自动执行签到

也可在 Actions 页面手动触发运行。

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
5. 使用本项目即视为同意以上条款；不同意请勿使用。
