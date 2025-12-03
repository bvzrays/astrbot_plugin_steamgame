# AstrBot Steam Game 插件

> Steam 数据一键拉取、制作高颜值战报，覆盖群排行、好友对比、成就卡片、热门推荐、VAC 预警与联动分析等场景。

<p align="center">
  <a href="https://github.com/bvzrays/astrbot_plugin_steamgame/stargazers">
    <img src="https://img.shields.io/github/stars/bvzrays/astrbot_plugin_steamgame?style=flat-square" />
  </a>
  <a href="https://github.com/bvzrays/astrbot_plugin_steamgame/releases">
    <img src="https://img.shields.io/github/v/release/bvzrays/astrbot_plugin_steamgame?style=flat-square" />
  </a>
  <a href="https://github.com/bvzrays/astrbot_plugin_steamgame/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" />
  </a>
</p>

<p align="center">
  <img width="1302" height="568" alt="preview" src="https://github.com/user-attachments/assets/a9995a1f-870b-40c0-9671-bde89dabb999" />
</p>

---

## 📌 功能速览

- 🎮 `/steam动态`：头像、在线状态、最近 2 周游玩 + VAC/Game Ban 提示  
- 🧱 `/steam游戏库`：100 张 Mosaic 贴图墙，自动根据时长排版  
- 🏅 `/steam成就 <游戏名>`：进度环 + 最近解锁 + 成就图标阵列  
- ⚔ `/steam对比 @用户`：游戏数/时长/成就多维 PK，自动列出共同 & 独占游戏  
- 📈 `/steam排行 [游戏数/时长]`：群内榜单，带 Top 游戏封面条  
- 🔥 `/steam推荐 [@用户]`：群友最常玩的但你未拥有的游戏，附群友头像  
- 🤝 `/steam联动`：分析群友是否互为 Steam 好友、是否正在同玩  
- 🔗 `/绑定steam`：17 位 Steam64 绑定 + 群聊自动同步，@ 也能触发

---

## 🚀 快速上手

### 1. 安装

1. 将仓库 clone/下载至 `AstrBot/data/plugins/astrbot_plugin_steamgame`。  
2. 启用插件，并在管理面板的配置页填写 `steam_api_key`（必填）与代理（可选）。  
3. 群内执行 `/绑定steam <SteamID64>` 绑定账号后即可使用所有指令。

### 2. 指令列表

| 指令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `/绑定steam <ID>` | 绑定 Steam64 ID 或同步到当前群 | `/绑定steam 76561198000000000` |
| `/steam动态 [@用户]` | 个人资料、最近活动、Ban 状态 | `/steam动态 @某人` |
| `/steam游戏库 [@用户]` | Mosaic 游戏墙 | `/steam游戏库` |
| `/steam排行 [游戏数/时长]` | 群排行（含 Top 游戏封面） | `/steam排行 游戏数` |
| `/steam成就 <游戏名>` | 指定游戏的成就进度卡片 | `/steam成就 黑神话` |
| `/steam对比 @用户` | 共同游戏 + 多维 Metrics + PK 结果 | `/steam对比 @Tom` |
| `/steam推荐 [@用户]` | 群友热门但目标未拥有的游戏推荐 | `/steam推荐` |
| `/steam联动` | 群友互为好友情况 & 正在联机的游戏 | `/steam联动` |

### 3. 配置示例

```json
{
  "steam_api_key": "YOUR_API_KEY",
  "proxy": "http://127.0.0.1:7890",
  "image_quality": 95,
  "recommend_source_limit": 40,
  "recommend_result_limit": 6
}
```

> 所有配置写在插件根目录的 `_conf_schema.json` 对应的 AstrBot WebUI 表单里即可。

---

## 📸 功能截图

- 个人资料 & 动态  
  ![profile](https://github.com/user-attachments/assets/bb432769-e159-437a-97a3-db878f2bab24)

- Mosaic 游戏墙  
  ![library](https://github.com/user-attachments/assets/99d3351b-18cb-4e89-a0ca-7891f7fe58c1)

- 成就卡片  
  ![achievement](https://github.com/user-attachments/assets/072b1406-0e2f-4b5f-a44d-505cd9567c68)

- 好友对比  
  ![compare](https://github.com/user-attachments/assets/ae377c79-5d9e-4626-a1d5-a0e0556f917b)

- 群内排行  
  ![rank](https://github.com/user-attachments/assets/96913c05-efa2-40f3-936d-f2dc145cc6ca)

- 热门推荐  
  ![recommend](https://github.com/user-attachments/assets/a4055ca2-a7f9-4b55-a77e-fd6d6d19e066)

- VAC/Game Ban 提示  
  <img width="276" height="43" alt="ban" src="https://github.com/user-attachments/assets/09249bf9-8a7c-4b7c-afb8-5c3c45fba312" />

---

## 🛠️ 目录结构

```
astrbot_plugin_steamgame/
├── main.py           # 指令入口与逻辑
├── steam_api.py      # Steam Web API 封装、缓存、好友/VAC 请求
├── templates/        # 所有 HTML 模板（动态、库、成就、对比、排行、推荐）
├── _conf_schema.json # 插件配置 Schema
└── requirements.txt  # 依赖（如 httpx/aiohttp 等）
```

---

## 🆕 更新日志

### 1.6.0
- 所有指令在群聊中支持直接 `@机器人` 触发，同时在处理 @、私聊回落时会自动同步 `group_bindings`，避免“提示成功但依然查不到数据”的情况。
- 新增动态头像转静态 JPG 逻辑，排行榜、推荐、对比卡片中不会再出现动画头像。
- HTML 模板全面自适应，`/steam排行`、`/steam成就`、`/steam对比`、`/steam推荐` 等渲染图不会再只占整个截图的一小块。

### 1.5.0
- 初次公开版本，包含动态、游戏库、成就、对比、排行、推荐、联动等基础功能。

---

## 📝 License

MIT
