# AstrBot Steam Game Plugin

一个用于 AstrBot 的 Steam 玩家数据可视化插件，生成精美图，支持群排行、好友对比、成就卡片、热点游戏推荐、VAC 提示与 Steam 联动等功能。

> ✅ **建议在这里插入“功能总览”截图（1200px 宽）**

---

## ✨ 功能截图

> 每个小节请插入对应截图（示例路径：`docs/*.jpg`）

### 1. 个人资料 & 最近动态（`/steam动态`）
- 展示头像、在线状态、最近游玩
- **截图位置**：此段落下方，命名 `docs/profile.jpg`

### 2. Mosaic 游戏墙（`/steam游戏库`）
- 依据游玩时长自动排布封面墙
- **截图位置**：此段落下方，命名 `docs/mosaic.jpg`

### 3. 成就卡片（`/steam成就 <游戏名>`）
- 进度环 + 最近解锁成就
- **截图位置**：此段落下方，命名 `docs/achievements.jpg`

### 4. 好友对比（`/steam对比 @用户`）
- 多维 PK 卡片（游戏数 / 总时长 / 成就），共同游戏墙
- **截图位置**：此段落下方，命名 `docs/compare.jpg`

### 5. 群内排行（`/steam排行 [游戏数/时长/关键词]`）
- 群友拥有/游玩数据排行榜
- **截图位置**：此段落下方，命名 `docs/rank.jpg`

### 6. 群聊热门推荐（`/steam推荐`）
- 根据群友游玩时长推荐你未拥有的热门游戏（渲染图示含拥有者头像）
- **截图位置**：此段落下方，命名 `docs/recommend.jpg`

### 7. VAC / Ban 状态提示（`/steam动态` 与 `/steam游戏库`）
- 在个人卡片中高亮 VAC / Game / Community Ban 状态
- **截图位置**：可与“个人资料”同图

### 8. Steam 联动（`/steam联动`）
- 列出群友之间的 Steam 好友关系以及正在一起游玩的游戏
- **截图位置**：可插入命令输出示例

---

## 🚀 安装

1. 将本插件放入 `AstrBot/data/plugins/`。
2. 在 AstrBot 管理面板启用插件。
3. 在配置页填写 `steam_api_key`（必填）和 `proxy`（选填）。

## 📖 指令列表

| 指令 | 说明 | 示例 |
| :--- | :--- | :--- |
| `/绑定steam <ID>` | 绑定 Steam ID (17 位) | `/绑定steam 76561198000000000` |
| `/steam动态` | 查看头像、状态、最近活动 | `/steam动态 @某人` |
| `/steam游戏库` | 生成 Mosaic 游戏墙 | `/steam游戏库` |
| `/steam排行 [游戏数/时长/关键词]` | 群排行或关键词排行 | `/steam排行 游戏数` |
| `/steam成就 <游戏名>` | 成就进度卡片（模糊匹配） | `/steam成就 黑神话` |
| `/steam对比 @用户` | 两人共同游戏 + 多维对比 | `/steam对比 @Tom` |
| `/steam推荐 [@用户]` | 群聊热门但未拥有的游戏推荐（渲染图） | `/steam推荐` |
| `/steam联动` | 查看群友 Steam 好友 & 同玩状况 | `/steam联动` |

## ⚙️ 配置

```json
{
  "steam_api_key": "YOUR_API_KEY",
  "proxy": "http://127.0.0.1:7890",
  "image_quality": 95,
  "recommend_source_limit": 40,
  "recommend_result_limit": 6
}
```

## 🛠️ 目录结构

- `main.py`：插件入口 & 指令逻辑  
- `steam_api.py`：Steam API 封装、缓存、好友/VAC 接口  
- `templates/`：HTML 模板（动态、游戏库、成就、对比、排行、推荐）

## 📝 License

MIT
