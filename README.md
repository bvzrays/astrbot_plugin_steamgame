# AstrBot Steam Game Plugin

一个用于 AstrBot 的 Steam 玩家数据可视化插件，生成精美图，支持群排行、好友对比、成就卡片等功能。

> ✅ **建议在这里插入插件总览截图**（推荐 1200px 宽，放在标题下方，让读者一眼看到成品效果）

## ✨ 特性

- Apple 风格 UI：毛玻璃、渐变背景、一致的头像样式。
- Mosaic 游戏墙：依据游玩时长自动排布封面墙。
- 好友对比：新增多维 PK 卡片（游戏数、总时长、成就），支持 WIN/LOSE 徽章。
- 群内排行：`/steam排行 <关键词>`，按拥有数量 / 时长排名。
- 成就卡片：模糊搜索 + 成就进度展示。
- 智能绑定：全局持久化 Steam ID，一次绑定到处可用。

## 🚀 安装

1. 将本插件目录放入 `AstrBot/data/plugins/`。
2. 在 AstrBot 管理面板中启用插件。
3. 在配置页填写 `steam_api_key`（必填）和 `proxy`（选填）。

## 📖 指令列表

| 指令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `/绑定steam <ID>` | 绑定 Steam ID (17位数字) | `/绑定steam 76561198000000000` |
| `/steam动态` | 查看头像、状态和最近活动 | `/steam动态` 或 `/steam动态 @某人` |
| `/steam游戏库` | 生成 Mosaic 游戏墙 | `/steam游戏库` |
| `/steam排行 [游戏数/时长/关键词]` | 群排行（支持关键词过滤） | `/steam排行 游戏数` |
| `/steam成就 <游戏名>` | 成就进度卡片（模糊匹配） | `/steam成就 黑神话` |
| `/steam对比 @用户` | 两人共同游戏 + 多维对比 | `/steam对比 @Tom` |

## 📷 推荐截图位置

- “安装”段落和“指令列表”之间：可插入 Mosaic 游戏墙示例。
- “指令列表”后：加入好友对比 PK 卡片截图（突出新增三维徽章）。

## ⚙️ 配置

管理面板或 `data/config/astrbot_plugin_steamgame_config.json`：

```json
{
  "steam_api_key": "YOUR_API_KEY",
  "proxy": "http://127.0.0.1:7890",
  "image_quality": 95
}
```

## 🛠️ 结构

- `main.py`：插件入口 & 指令逻辑
- `steam_api.py`：Steam API 包装与缓存
- `templates/`：HTML 模板（Mosaic、成就、对比、排行）

## 📝 License

MIT
