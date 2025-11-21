import aiohttp
import time
import asyncio
from typing import Dict, List, Optional, Any

class SteamAPI:
    BASE_URL = "http://api.steampowered.com"

    def __init__(self, api_key: str, proxy: str = None, logger=None):
        self.api_key = api_key
        self.proxy = proxy
        self.logger = logger
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._cache_lock = asyncio.Lock()

    async def _get_cache(self, key: str) -> Optional[Any]:
        async with self._cache_lock:
            if key in self._cache:
                data = self._cache[key]
                if time.time() - data["timestamp"] < self._cache_ttl:
                    return data["value"]
                del self._cache[key]
            return None

    async def _set_cache(self, key: str, value: Any):
        async with self._cache_lock:
            self._cache[key] = {
                "timestamp": time.time(),
                "value": value
            }

    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params["key"] = self.api_key
        params["format"] = "json"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.BASE_URL}/{endpoint}", params=params, proxy=self.proxy) as response:
                    if response.status != 200:
                        if self.logger:
                            self.logger.error(f"Steam API 请求失败，状态码 {response.status}，内容：{await response.text()}")
                        return {}
                    try:
                        return await response.json()
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Steam API 返回内容解析失败：{e}")
                        return {}
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Steam API 请求异常：{e}")
                return {}

    async def get_player_summaries(self, steam_ids: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get player summaries for a list of Steam IDs (comma separated).
        force_refresh: If True, bypass cache to get fresh data.
        """
        cache_key = f"summary_{steam_ids}"
        if not force_refresh:
            cached = await self._get_cache(cache_key)
            if cached:
                if isinstance(cached, dict):
                    return dict(cached)
                if isinstance(cached, list):
                    return [dict(player) for player in cached]
                return cached

        data = await self._request("ISteamUser/GetPlayerSummaries/v0002/", {"steamids": steam_ids})
        if "response" in data and "players" in data["response"]:
            players = data["response"]["players"]
            if players:
                # We usually query for one player, so return the first one if it's a single ID query
                result = players[0] if "," not in steam_ids else players
                await self._set_cache(cache_key, result)
                if isinstance(result, dict):
                    return dict(result)
                if isinstance(result, list):
                    return [dict(player) for player in result]
                return result
        return None

    async def get_owned_games(self, steam_id: str) -> List[Dict[str, Any]]:
        """
        Get owned games for a Steam ID.
        """
        cache_key = f"games_{steam_id}"
        cached = await self._get_cache(cache_key)
        if cached:
            return [dict(g) for g in cached]

        params = {
            "steamid": steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1
        }
        data = await self._request("IPlayerService/GetOwnedGames/v0001/", params)
        
        if "response" in data and "games" in data["response"]:
            games = [dict(g) for g in data["response"]["games"]]
            # Sort by playtime_forever descending
            games.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)
            await self._set_cache(cache_key, games)
            return [dict(g) for g in games]
        return []

    async def get_recently_played_games(self, steam_id: str) -> List[Dict[str, Any]]:
        """
        Get recently played games for a Steam ID.
        """
        cache_key = f"recent_{steam_id}"
        cached = await self._get_cache(cache_key)
        if cached:
            return [dict(g) for g in cached]

        params = {
            "steamid": steam_id,
            "count": 10
        }
        data = await self._request("IPlayerService/GetRecentlyPlayedGames/v0001/", params)

        if "response" in data and "games" in data["response"]:
            games = [dict(g) for g in data["response"]["games"]]
            await self._set_cache(cache_key, games)
            return [dict(g) for g in games]
        return []

    async def get_user_stats_for_game(self, steam_id: str, app_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user stats and achievements for a game.
        """
        cache_key = f"stats_{steam_id}_{app_id}"
        cached = await self._get_cache(cache_key)
        if cached: return cached

        params = {"steamid": steam_id, "appid": app_id}
        data = await self._request("ISteamUserStats/GetUserStatsForGame/v0002/", params)
        
        if "playerstats" in data:
            await self._set_cache(cache_key, data["playerstats"])
            return data["playerstats"]
        return None

    async def get_schema_for_game(self, app_id: int) -> Optional[Dict[str, Any]]:
        """
        Get game schema (achievement names, icons).
        """
        cache_key = f"schema_{app_id}"
        cached = await self._get_cache(cache_key)
        if cached: return cached

        params = {"appid": app_id}
        data = await self._request("ISteamUserStats/GetSchemaForGame/v2/", params)
        
        if "game" in data:
            await self._set_cache(cache_key, data["game"])
            return data["game"]
        return None

    async def get_player_bans(self, steam_ids: str | List[str]) -> Optional[List[Dict[str, Any]]]:
        """
        获取 VAC / Game / Community Ban 信息
        """
        if isinstance(steam_ids, list):
            joined = ",".join(steam_ids)
        else:
            joined = steam_ids
        cache_key = f"bans_{joined}"
        cached = await self._get_cache(cache_key)
        if cached:
            return [dict(p) for p in cached]

        data = await self._request("ISteamUser/GetPlayerBans/v1/", {"steamids": joined})
        if "players" in data:
            await self._set_cache(cache_key, data["players"])
            return [dict(p) for p in data["players"]]
        return None

    async def get_friend_list(self, steam_id: str) -> List[str]:
        """
        获取好友列表（仅限 relationship=friend）
        """
        cache_key = f"friends_{steam_id}"
        cached = await self._get_cache(cache_key)
        if cached:
            return list(cached)

        data = await self._request(
            "ISteamUser/GetFriendList/v0001/",
            {"steamid": steam_id, "relationship": "friend"},
        )
        if "friendslist" in data and "friends" in data["friendslist"]:
            friends = [f.get("steamid") for f in data["friendslist"]["friends"] if f.get("steamid")]
            await self._set_cache(cache_key, friends)
            return list(friends)
        return []

    async def _request_store_json(self, url: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, proxy=self.proxy, headers={"Accept": "application/json"}) as response:
                    if response.status != 200:
                        if self.logger:
                            self.logger.error(f"Steam 商店接口请求失败，状态码 {response.status}")
                        return {}
                    try:
                        return await response.json(content_type=None)
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Steam 商店接口返回内容解析失败：{e}")
                        return {}
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Steam 商店接口请求异常：{e}")
                return {}

