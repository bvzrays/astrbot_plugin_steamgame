# AstrBot Steam Game Plugin

一个用于 AstrBot 的 Steam 玩家数据可视化插件。支持查询个人资料、游戏库 Mosaic 墙、成就进度、好友对比以及群内趣味排行。

## ✨ 特性

*   **Apple 风格 UI**: 精美的毛玻璃效果和动态背景。
*   **Mosaic 游戏墙**: 自动生成壮观的游戏封面墙，按游玩时长排列。
*   **群内趣味排行**: `/steam排行 <关键词>`，看看谁是群里的“类型游戏之王”。
*   **成就查询**: 支持模糊搜索，一键生成成就进度卡片。
*   **好友对比**: 生成 PK 卡片，展示共同游戏。
*   **智能绑定**: 全局绑定 Steam ID，一次绑定，处处可用。

## 🚀 安装

1.  将本插件目录放入 `AstrBot/data/plugins/`。
2.  在 AstrBot 管理面板中启用插件。
3.  配置 `steam_api_key` (必填) 和 `proxy` (选填)。

## 📖 指令列表

| 指令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `/绑定steam <ID>` | 绑定 Steam ID (17位数字) | `/绑定steam 76561198000000000` |
| `/steam动态` | 查看头像、状态和最近活动 | `/steam动态` 或 `/steam动态 @某人` |
| `/steam游戏库` | 查看完整的 Mosaic 游戏墙 | `/steam游戏库` |
| `/steam排行 <关键词>` | 群内拥有指定关键词游戏的排行 | `/steam排行 射击` |
| `/steam成就 <游戏名>` | 查询成就进度 (支持模糊搜索) | `/steam成就 黑神话` |
| `/steam对比 @用户` | 对比两人的共同游戏 | `/steam对比 @Tom` |

## ⚙️ 配置

在 `data/config/astrbot_plugin_steamgame_config.json` 或管理面板中配置：

```json
{
  "steam_api_key": "YOUR_API_KEY",
  "proxy": "http://127.0.0.1:7890"
}
```

## 🛠️ 开发

*   `main.py`: 核心逻辑
*   `steam_api.py`: API 封装
*   `templates/`: HTML 模板

## 📝 License

MIT
