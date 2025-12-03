import base64
import json
import difflib
import asyncio
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any
import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger
from astrbot.api import message_components as Comp
from .steam_api import SteamAPI

@register("steam_game", "bvzrays", "Steam Player Data Visualization", "1.6.0", "https://github.com/bvzrays/astrbot_plugin_steamgame")
class SteamGamePlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.api_key = self.config.get("steam_api_key", "")
        self.proxy = self.config.get("proxy", "")
        self.image_quality = int(self.config.get("image_quality", 90))
        self.image_quality = max(10, min(100, self.image_quality))
        self.recommend_source_limit = max(10, int(self.config.get("recommend_source_limit", 40)))
        self.recommend_result_limit = max(3, int(self.config.get("recommend_result_limit", 6)))
        
        if not self.api_key:
            logger.warning("Steam API Key not set in config! Plugin will not work correctly.")
            
        self.steam_api = SteamAPI(self.api_key, self.proxy, logger=logger)
        
        # Data storage for bindings
        plugin_dir = Path(__file__).resolve().parent
        plugin_name = plugin_dir.name
        self.data_dir: Path = StarTools.get_data_dir(plugin_name)
        self.data_file: Path = self.data_dir / "steam_binding.json"
        self.cover_dir: Path = self.data_dir / "covers"
        self.templates_dir: Path = plugin_dir / "templates"
        self.bindings, self.group_bindings = self._load_bindings()
        logger.info(f"SteamGamePlugin: 已载入 {len(self.bindings)} 个绑定，数据文件 {self.data_file}")

    def _load_bindings(self):
        if self.data_file.exists():
            try:
                with self.data_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Backward compatibility: older versions stored a flat dict
                    if isinstance(data, dict) and "users" in data and "groups" in data:
                        return data.get("users", {}), data.get("groups", {})
                    if isinstance(data, dict):
                        return data, {}
            except Exception as e:
                logger.error(f"Failed to load bindings: {e}")
                return {}, {}
        return {}, {}

    def _save_bindings(self):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with self.data_file.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "users": self.bindings,
                        "groups": self.group_bindings,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
        except Exception as e:
            logger.error(f"Failed to save bindings: {e}")

    def _link_user_to_group(self, user_id: str, group_id: Optional[str]) -> bool:
        """Track which group has access to which binding."""
        if not group_id:
            return False
        steam_id = self.bindings.get(user_id)
        if not steam_id:
            return False
        group_map = self.group_bindings.setdefault(group_id, {})
        if group_map.get(user_id) != steam_id:
            group_map[user_id] = steam_id
            return True
        return False

    def _sync_group_binding_value(self, user_id: str) -> bool:
        """Ensure historical group bindings use the latest steam id."""
        changed = False
        steam_id = self.bindings.get(user_id)
        if not steam_id:
            return False
        for group_map in self.group_bindings.values():
            if user_id in group_map and group_map[user_id] != steam_id:
                group_map[user_id] = steam_id
                changed = True
        return changed

    def _format_playtime(self, minutes):
        if minutes < 60:
            return f"{minutes} 分钟"
        hours = minutes / 60
        days = hours / 24
        return f"{int(hours)}h ({days:.1f}d)"

    async def _aggregate_achievements(self, steam_id: str, games: list, limit: int = 12) -> dict:
        """Estimate achievement progress by sampling top games."""
        unlocked = 0
        total = 0
        if not games or not steam_id:
            return {"unlocked": 0, "total": 0}

        sampled_games = games[:limit]
        for game in sampled_games:
            app_id = game.get("appid")
            if not app_id:
                continue
            stats = await self.steam_api.get_user_stats_for_game(steam_id, app_id)
            if not stats:
                continue
            schema = await self.steam_api.get_schema_for_game(app_id)
            if not schema:
                continue
            achievements_schema = schema.get("availableGameStats", {}).get("achievements", [])
            total += len(achievements_schema)

            user_achievements = stats.get("achievements", [])
            unlocked += sum(1 for ach in user_achievements if ach.get("achieved", 0) == 1 or ach.get("unlocktime"))

        return {"unlocked": unlocked, "total": total}

    def _build_metric(
        self,
        label: str,
        left_value: float,
        right_value: float,
        left_display: Optional[str] = None,
        right_display: Optional[str] = None,
    ) -> dict:
        if left_display is None:
            left_display = str(left_value)
        if right_display is None:
            right_display = str(right_value)

        if left_value > right_value:
            left_result, right_result = "win", "lose"
        elif left_value < right_value:
            left_result, right_result = "lose", "win"
        else:
            left_result = right_result = "draw"

        badge_map = {"win": "WIN!", "lose": "LOSE", "draw": "DRAW"}

        return {
            "label": label,
            "left": {"value": left_display, "result": left_result, "badge": badge_map[left_result]},
            "right": {"value": right_display, "result": right_result, "badge": badge_map[right_result]},
        }

    def _bytes_to_data_uri(self, data: bytes, mime: str = "jpeg") -> str:
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/{mime};base64,{encoded}"

    def _load_cached_cover(self, dest_path: Path) -> Optional[str]:
        if not dest_path.exists():
            return None
        try:
            with dest_path.open("rb") as f:
                data = f.read()
            mime = "png" if dest_path.suffix.lower() == ".png" else "jpeg"
            return self._bytes_to_data_uri(data, mime)
        except Exception as e:
            logger.warning(f"Failed to read cached cover {dest_path}: {e}")
            return None

    async def _download_cover(self, url: str, dest_path: Path) -> Optional[bytes]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with dest_path.open("wb") as f:
                            f.write(data)
                        return data
        except Exception as e:
            logger.warning(f"Failed to download cover {url}: {e}")
        return None

    async def _ensure_cover_uri(self, app_id: int, variant: str = "poster") -> str:
        if not app_id:
            return ""
        app_id = str(app_id)
        base = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}"
        url_candidates = []
        if variant == "hero":
            url_candidates = [
                f"{base}/library_hero.jpg",
                f"{base}/library_hero.png",
                f"{base}/header.jpg"
            ]
        else:
            url_candidates = [
                f"{base}/library_600x900.jpg",
                f"{base}/library_600x900.png",
                f"{base}/header.jpg"
            ]

        for url in url_candidates:
            ext = ".png" if url.lower().endswith(".png") else ".jpg"
            dest_path = self.cover_dir / f"{app_id}_{variant}{ext}"
            cached = self._load_cached_cover(dest_path)
            if cached:
                return cached
            data = await self._download_cover(url, dest_path)
            if data:
                mime = "png" if ext == ".png" else "jpeg"
                return self._bytes_to_data_uri(data, mime)

        # Download failed, fall back to last candidate URL
        return url_candidates[-1]

    async def _decorate_games_with_cover(self, games, variant: str = "poster"):
        tasks = []
        index_map = []
        for idx, game in enumerate(games):
            appid = game.get("appid")
            if not appid:
                continue
            tasks.append(self._ensure_cover_uri(appid, variant))
            index_map.append(idx)

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for idx, cover in zip(index_map, results):
            if isinstance(cover, Exception):
                logger.warning(f"Cover fetch failed: {cover}")
                continue
            games[idx]["cover_uri"] = cover

    def _ensure_static_avatar(self, summary: Optional[Dict[str, Any]], size: str = "full") -> str:
        """
        Steam 会在用户设置动态头像时返回 gif，这里将其转换为 jpg，避免 HTML 渲染时出现动图。
        """
        if not summary:
            return ""
        avatar_url = summary.get("avatarfull", "") if size == "full" else summary.get("avatarmedium", "")
        avatar_hash = summary.get("avatarhash")
        if avatar_url and avatar_url.endswith(".gif"):
            if avatar_hash:
                suffix_map = {
                    "full": "_full",
                    "medium": "_medium",
                    "small": "",
                }
                suffix = suffix_map.get(size, "_full")
                avatar_url = f"https://avatars.cloudflare.steamstatic.com/{avatar_hash}{suffix}.jpg"
            else:
                avatar_url = avatar_url[:-4] + ".jpg"
        if avatar_url:
            summary["avatarfull"] = avatar_url
        return avatar_url

    async def _resolve_target(self, event: AstrMessageEvent, arg: str, allow_fallback: bool = True) -> str:
        """
        Resolve Steam ID from argument.
        Arg can be:
        - Empty: Use sender's bound ID.
        - @Mention: Use mentioned user's bound ID.
        - Digits: Use as Steam ID directly.
        """
        # 1. Check if mentioned
        save_needed = False
        group_id = event.get_group_id()
        steam_id = None

        for component in event.message_obj.message:
            if isinstance(component, Comp.At):
                target_user_id = str(component.qq)
                steam_id = self.bindings.get(target_user_id)
                if steam_id and group_id and self._link_user_to_group(target_user_id, group_id):
                    save_needed = True
                break
        
        # 2. Check if explicit ID (digits)
        if not steam_id and arg and arg.isdigit() and len(arg) > 10: # Simple check for Steam ID format
            steam_id = arg
            
        # 3. Default: Use sender's ID
        if not steam_id and allow_fallback:
            user_id = str(event.get_sender_id())
            steam_id = self.bindings.get(user_id)
            if steam_id and group_id and self._link_user_to_group(user_id, group_id):
                save_needed = True
        if save_needed:
            self._save_bindings()
        return steam_id

    @filter.command("绑定steam", prefix_optional=True)
    async def bind(self, event: AstrMessageEvent, steam_id: str = ""):
        '''绑定 Steam ID（在新的群聊中可不填参数同步已有绑定）'''
        user_id = str(event.get_sender_id())
        group_id = event.get_group_id()
        message = ""

        data_changed = False

        if steam_id:
            # Validate Steam ID (must be 64-bit integer, usually 17 digits)
            if not steam_id.isdigit() or len(steam_id) != 17:
                yield event.plain_result("绑定失败：请输入正确的 17 位 Steam ID 64 (例如 76561198000000000)。")
                return
            self.bindings[user_id] = steam_id
            data_changed = True
            message = f"绑定成功！已关联 Steam ID: {steam_id}"
        else:
            if user_id not in self.bindings:
                yield event.plain_result("你还没有绑定 Steam ID，请使用 /绑定steam <SteamID64>。")
                return
            steam_id = self.bindings[user_id]
            message = "已将现有绑定同步至当前群聊。"

        if self._sync_group_binding_value(user_id):
            data_changed = True
        if self._link_user_to_group(user_id, group_id):
            data_changed = True
        if data_changed:
            self._save_bindings()
        yield event.plain_result(message)

    async def _render_profile(self, event: AstrMessageEvent, steam_id: str, mode: str):
        if not self.api_key:
            yield event.plain_result("请先在配置文件中设置 Steam API Key。")
            return

        if not steam_id:
            yield event.plain_result("未找到绑定的 Steam ID。请先绑定 (/绑定steam <id>) 或指定 ID。")
            return

        # Fetch Data (force refresh for summary mode to get current playing status)
        summary = await self.steam_api.get_player_summaries(steam_id, force_refresh=(mode == "summary"))
        if not summary:
            yield event.plain_result("未找到该 Steam 用户，请检查 ID 是否正确，或检查网络/代理设置。")
            return
        self._ensure_static_avatar(summary)

        is_private = summary.get("communityvisibilitystate", 1) != 3
        
        owned_games = []
        recent_games = []
        hero_cover = summary.get("avatarfull", "")

        if not is_private:
            # Always fetch owned games to show total count and playtime
            owned_games = await self.steam_api.get_owned_games(steam_id)
            recent_games = await self.steam_api.get_recently_played_games(steam_id)
            await self._decorate_games_with_cover(owned_games, "poster")
            await self._decorate_games_with_cover(recent_games, "poster")
            if owned_games:
                hero_cover = await self._ensure_cover_uri(owned_games[0]["appid"], "hero")
                if not hero_cover:
                    hero_cover = summary.get("avatarfull", "")

        # Process Data
        for game in owned_games:
            game["playtime_forever_formatted"] = self._format_playtime(game.get("playtime_forever", 0))
        
        for game in recent_games:
            game["playtime_2weeks_formatted"] = self._format_playtime(game.get("playtime_2weeks", 0))

        # Mosaic Layout Logic (Only for Library mode)
        mosaic_games = []
        if mode == "library" and owned_games:
            mosaic_games = owned_games[:100] # Take top 100
            for i, game in enumerate(mosaic_games):
                if i == 0: game["grid_class"] = "span-4x4"
                elif i < 5: game["grid_class"] = "span-2x2"
                elif i < 15: game["grid_class"] = "span-2x1" if i % 2 == 0 else "span-1x2"
                else: game["grid_class"] = "span-1x1"

        # Check if playing
        playing_game = None
        if summary.get("gameextrainfo"):
            playing_game = {
                "name": summary.get("gameextrainfo"),
                "appid": summary.get("gameid")
            }
            cover_uri = await self._ensure_cover_uri(summary.get("gameid"), "hero")
            playing_game["cover_uri"] = cover_uri or hero_cover

        # Render
        template_path = self.templates_dir / "profile.html"
        with template_path.open("r", encoding="utf-8") as f:
            template_content = f.read()
            
        bans_data = await self.steam_api.get_player_bans(steam_id)
        ban_info = bans_data[0] if bans_data else None

        img_url = await self.html_render(
            template_content, {
                "player": summary,
                "owned_games": mosaic_games if mode == "library" else owned_games,
                "recent_games": recent_games,
                "total_games": len(owned_games),
                "total_playtime": self._format_playtime(sum(g.get("playtime_forever", 0) for g in owned_games)),
                "is_private": is_private,
                "mode": mode,
                "playing_game": playing_game,
                "hero_cover": hero_cover,
                "ban_info": ban_info
            },
            options={
                "width": 880,
                "full_page": True,
                "omit_background": True,
                "type": "jpeg",
                "quality": self.image_quality
            }
        )
        yield event.image_result(img_url)

    @filter.command("steam动态", prefix_optional=True)
    async def steam_activity(self, event: AstrMessageEvent, arg: str = ""):
        '''查看 Steam 动态 (头像 + 最近活动)'''
        steam_id = await self._resolve_target(event, arg)
        async for result in self._render_profile(event, steam_id, "summary"):
            yield result



    @filter.command("steam游戏库", prefix_optional=True)
    async def steam_library(self, event: AstrMessageEvent, arg: str = ""):
        '''查看 Steam 完整游戏库 (Mosaic 墙)'''
        steam_id = await self._resolve_target(event, arg)
        async for result in self._render_profile(event, steam_id, "library"):
            yield result


    @filter.command("steam成就", prefix_optional=True)
    async def steam_achievement(self, event: AstrMessageEvent, game_name: str):
        '''查看 Steam 游戏成就 (/steam成就 <游戏名>)'''
        if not game_name:
            yield event.plain_result("请输入游戏名称，例如：/steam成就 黑神话")
            return

        steam_id = await self._resolve_target(event, "") # Always check sender's achievements
        if not steam_id:
            yield event.plain_result("请先绑定 Steam ID。")
            return

        # 1. Search for game in owned games
        owned_games = await self.steam_api.get_owned_games(steam_id)
        
        # Fuzzy Search Logic
        game_names = [g["name"] for g in owned_games]
        matches = difflib.get_close_matches(game_name, game_names, n=5, cutoff=0.4)
        
        target_game = None
        
        # Exact match check (case-insensitive)
        for game in owned_games:
            if game_name.lower() == game["name"].lower():
                target_game = game
                break
        
        if not target_game:
            # Substring match check
            for game in owned_games:
                if game_name.lower() in game["name"].lower():
                    target_game = game
                    break
        
        if not target_game:
            if matches:
                # If multiple matches found, ask user to be specific
                # But for better UX, if the first match is very close, we might just use it?
                # Let's just list them.
                msg = "未找到精确匹配的游戏，你是不是想找：\n"
                for i, m in enumerate(matches):
                    msg += f"{i+1}. {m}\n"
                msg += "请尝试使用更完整的名称。"
                yield event.plain_result(msg)
                return
            else:
                yield event.plain_result(f"在你拥有的游戏中未找到包含“{game_name}”的游戏。")
                return

        app_id = target_game["appid"]
        
        # 2. Fetch Schema & Stats
        schema = await self.steam_api.get_schema_for_game(app_id)
        achievements_all = schema.get("availableGameStats", {}).get("achievements", []) if schema else []
        if not achievements_all:
            yield event.plain_result(f"《{target_game['name']}》似乎没有可查询的 Steam 成就。")
            return

        stats = await self.steam_api.get_user_stats_for_game(steam_id, app_id)
        user_achievements = stats.get("achievements", []) if stats else []
        user_achievements_map = {a["name"]: a for a in user_achievements}
        
        unlocked_count = sum(
            1 for a in user_achievements_map.values() if a.get("achieved", 0) == 1 or a.get("unlocktime")
        )
        total_count = len(achievements_all)
        completion_rate = (unlocked_count / total_count * 100) if total_count > 0 else 0
        
        unlocked_display = []
        locked_display = []
        for ach in achievements_all:
            base_info = {
                "name": ach.get("displayName", ach.get("name", "")),
                "icon": ach.get("icon"),
                "desc": ach.get("description", ""),
            }
            if ach.get("name") in user_achievements_map:
                info = dict(base_info)
                info["unlocktime"] = user_achievements_map[ach["name"]].get("unlocktime", 0)
                unlocked_display.append(info)
            else:
                locked_display.append(base_info)

        unlocked_display.sort(key=lambda x: x.get("unlocktime", 0), reverse=True)
        display_achievements = unlocked_display[:6]
        if len(display_achievements) < 8:
            display_achievements.extend(locked_display[: 8 - len(display_achievements)])

        cover_uri = await self._ensure_cover_uri(app_id, "hero")

        render_data = {
            "game": target_game,
            "unlocked": unlocked_count,
            "total": total_count,
            "rate": f"{completion_rate:.1f}",
            "achievements": display_achievements,
            "player_name": event.get_sender_name(),
            "game_cover": cover_uri
        }
        
        template_path = self.templates_dir / "achievement.html"
        if not template_path.exists():
             yield event.plain_result("成就模板尚未上传。")
             return

        with template_path.open("r", encoding="utf-8") as f:
            template_content = f.read()
            
        img_url = await self.html_render(
            template_content,
            render_data,
            options={
                "width": 700,
                "full_page": True,
                "omit_background": True,
                "type": "jpeg",
                "quality": self.image_quality
            }
        )
        yield event.image_result(img_url)

    @filter.command("steam对比", prefix_optional=True)
    async def steam_compare(self, event: AstrMessageEvent, target: str):
        '''对比两人游戏库 (/steam对比 @User)'''
        # Fix: Directly get sender's ID from binding, don't use _resolve_target(event, "") 
        # because it might pick up the @mention in the message intended for the target.
        sender_user_id = str(event.get_sender_id())
        my_id = self.bindings.get(sender_user_id)
        
        target_id = await self._resolve_target(event, target, allow_fallback=False)
        
        if not my_id:
            yield event.plain_result("你还没有绑定 Steam ID 哦。")
            return
            
        if not target_id:
            yield event.plain_result("目标用户未绑定 Steam ID，或未指定对比对象。")
            return
            
        if my_id == target_id:
            yield event.plain_result("不能和自己对比哦。")
            return

        # Fetch both
        my_games = await self.steam_api.get_owned_games(my_id)
        target_games = await self.steam_api.get_owned_games(target_id)
        
        if not my_games or not target_games:
            yield event.plain_result("无法获取双方的游戏库，请检查 Steam API Key 或网络代理。")
            return
        
        my_summary = await self.steam_api.get_player_summaries(my_id) or {}
        target_summary = await self.steam_api.get_player_summaries(target_id) or {}
        self._ensure_static_avatar(my_summary)
        self._ensure_static_avatar(target_summary)

        # Calculate Intersection
        my_game_ids = {g["appid"] for g in my_games}
        target_game_ids = {g["appid"] for g in target_games}
        common_ids = my_game_ids.intersection(target_game_ids)
        
        common_games = []
        for gid in common_ids:
            # Find game info
            g = next((x for x in my_games if x["appid"] == gid), None)
            if g: common_games.append(g)
            
        # Sort by my playtime
        common_games.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)
        
        # Calculate unique games
        only_me_ids = my_game_ids - target_game_ids
        only_target_ids = target_game_ids - my_game_ids

        only_me = [g for g in my_games if g["appid"] in only_me_ids]
        only_target = [g for g in target_games if g["appid"] in only_target_ids]

        # Sort unique games by playtime
        only_me.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)
        only_target.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)

        my_total_minutes = sum(g.get("playtime_forever", 0) for g in my_games)
        target_total_minutes = sum(g.get("playtime_forever", 0) for g in target_games)

        # Achievement aggregation (sample top games to avoid heavy requests)
        my_ach_task = asyncio.create_task(self._aggregate_achievements(my_id, my_games))
        target_ach_task = asyncio.create_task(self._aggregate_achievements(target_id, target_games))
        my_achievements, target_achievements = await asyncio.gather(my_ach_task, target_ach_task)

        if not common_games:
            yield event.plain_result("双方似乎没有共同拥有的游戏。")
            return

        top_common = common_games[:12]
        await self._decorate_games_with_cover(top_common, "poster")

        render_data = {
            "me": {
                "personaname": my_summary.get("personaname", "Player 1"),
                "avatarfull": my_summary.get("avatarfull", ""),
                "count": len(my_games)
            },
            "target": {
                "personaname": target_summary.get("personaname", "Player 2"),
                "avatarfull": target_summary.get("avatarfull", ""),
                "count": len(target_games)
            },
            "common_games": top_common,
            "common_count": len(common_games),
            "only_me": only_me[:12],
            "only_target": only_target[:12],
            "metrics": [
                self._build_metric("游戏数量", len(my_games), len(target_games)),
                self._build_metric(
                    "总时长",
                    my_total_minutes,
                    target_total_minutes,
                    left_display=self._format_playtime(my_total_minutes),
                    right_display=self._format_playtime(target_total_minutes),
                ),
                self._build_metric(
                    "成就完成数",
                    my_achievements.get("unlocked", 0),
                    target_achievements.get("unlocked", 0),
                    left_display=f"{my_achievements.get('unlocked', 0)}/{my_achievements.get('total', 0)}"
                    if my_achievements.get("total")
                    else f"{my_achievements.get('unlocked', 0)}/-",
                    right_display=f"{target_achievements.get('unlocked', 0)}/{target_achievements.get('total', 0)}"
                    if target_achievements.get("total")
                    else f"{target_achievements.get('unlocked', 0)}/-",
                ),
            ]
        }
        
        template_path = self.templates_dir / "compare.html"
        if not template_path.exists():
             yield event.plain_result("对比模板尚未上传。")
             return
        with template_path.open("r", encoding="utf-8") as f:
            template_content = f.read()
        img_url = await self.html_render(
            template_content,
            render_data,
            options={
                "width": 800,
                "full_page": True,
                "omit_background": True,
                "type": "jpeg",
                "quality": self.image_quality
            }
        )
        yield event.image_result(img_url)

    @filter.command("steam推荐", prefix_optional=True)
    async def steam_recommend(self, event: AstrMessageEvent, arg: str = ""):
        '''群友热门游戏推荐 (/steam推荐 [@用户])'''
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用该指令。")
            return

        group_binding_map = self.group_bindings.get(group_id, {})
        if not group_binding_map:
            yield event.plain_result("本群暂无绑定信息，无法生成推荐。")
            return

        target_steam_id = await self._resolve_target(event, arg)
        if not target_steam_id:
            yield event.plain_result("未找到目标用户的 Steam 绑定。")
            return

        user_games = await self.steam_api.get_owned_games(target_steam_id)
        if not user_games:
            yield event.plain_result("无法获取目标用户的游戏库。")
            return

        user_appids = {g.get("appid") for g in user_games}

        others = [sid for sid in group_binding_map.values() if sid and sid != target_steam_id]
        if not others:
            yield event.plain_result("群内没有其他已绑定的用户，暂无法推荐。")
            return

        tasks = [self.steam_api.get_owned_games(steam_id) for steam_id in others]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        recommendations = {}
        for steam_id, games in zip(others, results):
            if not isinstance(games, list):
                continue
            for game in games[: self.recommend_source_limit]:
                appid = game.get("appid")
                if not appid or appid in user_appids:
                    continue
                minutes = game.get("playtime_forever", 0)
                if minutes <= 0:
                    continue
                entry = recommendations.setdefault(
                    appid,
                    {
                        "appid": appid,
                        "name": game.get("name", f"App {appid}"),
                        "score": 0,
                        "owners": set(),
                        "cover_uri": game.get("cover_uri"),
                    },
                )
                entry["score"] += minutes
                entry["owners"].add(steam_id)

        if not recommendations:
            yield event.plain_result("未找到可推荐的游戏，可能你已经拥有群友的热门作品。")
            return

        top_items = sorted(
            recommendations.values(),
            key=lambda x: (x["score"], len(x["owners"])),
            reverse=True,
        )[: self.recommend_result_limit]

        await self._decorate_games_with_cover(top_items, "poster")

        summary_cache = {}

        async def get_summary_cached(steam_id: str):
            if steam_id not in summary_cache:
                summary_cache[steam_id] = await self.steam_api.get_player_summaries(steam_id) or {}
                self._ensure_static_avatar(summary_cache[steam_id])
            return summary_cache[steam_id]

        render_recommendations = []
        for item in top_items:
            hours = item["score"] / 60
            owner_avatars = []
            for owner_id in list(item["owners"])[:6]:
                summary = await get_summary_cached(owner_id)
                self._ensure_static_avatar(summary)
                avatar = summary.get("avatarfull")
                if avatar:
                    owner_avatars.append(avatar)
            render_recommendations.append({
                "name": item["name"],
                "score": item["score"],
                "playtime": f"{hours:.1f}",
                "owners": len(item["owners"]),
                "owner_avatars": owner_avatars,
                "cover_uri": item.get("cover_uri"),
            })

        target_summary = await get_summary_cached(target_steam_id)
        self._ensure_static_avatar(target_summary)
        render_data = {
            "target": {
                "personaname": target_summary.get("personaname", event.get_sender_name()),
                "avatar": target_summary.get("avatarfull", ""),
            },
            "recommendations": render_recommendations
        }

        template_path = self.templates_dir / "recommend.html"
        if not template_path.exists():
            yield event.plain_result("推荐模板尚未上传。")
            return
        with template_path.open("r", encoding="utf-8") as f:
            template_content = f.read()

        img_url = await self.html_render(
            template_content,
            render_data,
            options={
                "width": 800,
                "full_page": True,
                "omit_background": True,
                "type": "jpeg",
                "quality": self.image_quality
            }
        )
        yield event.image_result(img_url)

    @filter.command("steam联动", prefix_optional=True)
    async def steam_network(self, event: AstrMessageEvent):
        '''群内 Steam 好友联动与同玩提醒'''
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用该指令。")
            return

        group_binding_map = self.group_bindings.get(group_id, {})
        if not group_binding_map:
            yield event.plain_result("本群暂无绑定信息。")
            return

        steam_to_user = {steam: user for user, steam in group_binding_map.items() if steam}
        steam_ids = list(steam_to_user.keys())
        if len(steam_ids) < 2:
            yield event.plain_result("至少需要两位已绑定用户才能分析联动。")
            return

        summary_cache: Dict[str, Dict[str, Any]] = {}

        async def get_summary_cached(steam_id: str):
            if steam_id not in summary_cache:
                summary_cache[steam_id] = await self.steam_api.get_player_summaries(steam_id) or {}
            return summary_cache[steam_id]

        friend_tasks = {sid: asyncio.create_task(self.steam_api.get_friend_list(sid)) for sid in steam_ids}

        playing_map: Dict[str, Dict[str, Any]] = {}
        for sid in steam_ids:
            summary = await get_summary_cached(sid)
            game_id = summary.get("gameid")
            if summary.get("gameextrainfo") and game_id:
                playing_entry = playing_map.setdefault(
                    str(game_id),
                    {"name": summary.get("gameextrainfo"), "players": []},
                )
                playing_entry["players"].append(sid)

        edges = set()
        for sid, task in friend_tasks.items():
            friends = await task
            for fid in friends:
                if fid in steam_to_user and sid in steam_to_user and fid != sid:
                    pair = tuple(sorted([sid, fid]))
                    edges.add(pair)

        def display_name(steam_id: str) -> str:
            summary = summary_cache.get(steam_id, {})
            self._ensure_static_avatar(summary)
            return summary.get("personaname") or steam_id

        lines = ["👥 群内 Steam 联动概览"]
        if edges:
            lines.append(f"- 发现 {len(edges)} 对群友互为 Steam 好友：")
            for idx, (a, b) in enumerate(list(edges)[:10], start=1):
                lines.append(f"  {idx}. {display_name(a)} ↔ {display_name(b)}")
            if len(edges) > 10:
                lines.append(f"  … 其余 {len(edges) - 10} 对略")
        else:
            lines.append("- 暂未发现群友之间的 Steam 好友关系。")

        active_groups = [
            entry for entry in playing_map.values() if len(entry["players"]) > 1
        ]
        if active_groups:
            lines.append("\n🔥 正在一起玩的游戏：")
            for entry in active_groups:
                names = [display_name(sid) for sid in entry["players"]]
                lines.append(f"- {entry['name']}: {', '.join(names)}")
        else:
            lines.append("\n🔥 暂时没有群友在同一款游戏里。")

        yield event.plain_result("\n".join(lines))

    @filter.command("steam排行", prefix_optional=True)
    async def steam_top(self, event: AstrMessageEvent, dimension: str = "游戏数"):
        '''群内排行 (/steam排行 [游戏数/时长])'''
        group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用该指令。")
            return
        # Ensure caller至少同步
        if self._link_user_to_group(str(event.get_sender_id()), group_id):
            self._save_bindings()

        # Map dimension to internal key
        dim_map = {
            "游戏数": "count",
            "数量": "count",
            "时长": "time",
            "时间": "time",
            "肝度": "time"
        }
        sort_by = dim_map.get(dimension, "count")
        group_binding_map = self.group_bindings.get(group_id, {})
        if not group_binding_map:
            yield event.plain_result("本群尚无用户绑定 Steam ID。请先使用 /绑定steam <SteamID64> 或在本群输入 /绑定steam 同步已有绑定。")
            return

        title = "群内 Steam 游戏数排行" if sort_by == "count" else "群内 Steam 肝帝排行"
        yield event.plain_result(f"正在统计{title}，请稍候...")

        rank_data = []
        
        tasks = []
        user_ids = []
        
        for user_id, steam_id in group_binding_map.items():
            tasks.append(self.steam_api.get_owned_games(steam_id))
            user_ids.append(user_id)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Also fetch summaries for avatars
        summary_tasks = [self.steam_api.get_player_summaries(group_binding_map[uid]) for uid in user_ids]
        summaries = await asyncio.gather(*summary_tasks, return_exceptions=True)
        
        for i, games in enumerate(results):
            if isinstance(games, list):
                user_id = user_ids[i]
                summary = summaries[i] if isinstance(summaries[i], dict) else {}
                self._ensure_static_avatar(summary)
                
                # Calculate metrics
                game_count = len(games)
                total_minutes = sum(g.get("playtime_forever", 0) for g in games)
                
                # Sort games by playtime for display
                games.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)
                
                top_games = games[:5]
                await self._decorate_games_with_cover(top_games, "poster")

                rank_data.append({
                    "user_id": user_id,
                    "name": summary.get("personaname", f"User {user_id}"),
                    "avatar": summary.get("avatarfull", ""),
                    "count": game_count,
                    "time_minutes": total_minutes,
                    "time_str": self._format_playtime(total_minutes),
                    "top_games": top_games # Top 5 games for display
                })
        
        # Sort
        if sort_by == "time":
            rank_data.sort(key=lambda x: x["time_minutes"], reverse=True)
        else:
            rank_data.sort(key=lambda x: x["count"], reverse=True)
        
        if not rank_data:
            yield event.plain_result("无法获取排行数据。")
            return
            
        render_data = {
            "title": title,
            "sort_by": sort_by,
            "ranks": rank_data[:10] # Top 10
        }
        
        template_path = self.templates_dir / "group_rank.html"
        with template_path.open("r", encoding="utf-8") as f:
            template_content = f.read()
        
        img_url = await self.html_render(
            template_content,
            render_data,
            options={
                "width": 800,
                "full_page": True,
                "omit_background": True,
                "type": "jpeg",
                "quality": self.image_quality
            }
        )
        yield event.image_result(img_url)

