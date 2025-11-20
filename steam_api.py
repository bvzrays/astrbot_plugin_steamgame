import aiohttp
import time
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("astrbot_plugin_steamgame")

class SteamAPI:
    BASE_URL = "http://api.steampowered.com"

    def __init__(self, api_key: str, proxy: str = None):
        self.api_key = api_key
        self.proxy = proxy
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes

    def _get_cache(self, key: str) -> Optional[Any]:
        if key in self._cache:
            data = self._cache[key]
            if time.time() - data["timestamp"] < self._cache_ttl:
                return data["value"]
            else:
                del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any):
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
                        logger.error(f"Steam API Error: {response.status} - {await response.text()}")
                        return {}
                    try:
                        return await response.json()
                    except Exception as e:
                        logger.error(f"Failed to parse JSON: {e}")
                        return {}
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return {}

    async def get_player_summaries(self, steam_ids: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get player summaries for a list of Steam IDs (comma separated).
        force_refresh: If True, bypass cache to get fresh data.
        """
        cache_key = f"summary_{steam_ids}"
        if not force_refresh:
            cached = self._get_cache(cache_key)
            if cached:
                return cached

        data = await self._request("ISteamUser/GetPlayerSummaries/v0002/", {"steamids": steam_ids})
        if "response" in data and "players" in data["response"]:
            players = data["response"]["players"]
            if players:
                # We usually query for one player, so return the first one if it's a single ID query
                result = players[0] if "," not in steam_ids else players
                self._set_cache(cache_key, result)
                return result
        return None

    async def get_owned_games(self, steam_id: str) -> List[Dict[str, Any]]:
        """
        Get owned games for a Steam ID.
        """
        cache_key = f"games_{steam_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        params = {
            "steamid": steam_id,
            "include_appinfo": 1,
            "include_played_free_games": 1
        }
        data = await self._request("IPlayerService/GetOwnedGames/v0001/", params)
        
        if "response" in data and "games" in data["response"]:
            games = data["response"]["games"]
            # Sort by playtime_forever descending
            games.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)
            self._set_cache(cache_key, games)
            return games
        return []

    async def get_recently_played_games(self, steam_id: str) -> List[Dict[str, Any]]:
        """
        Get recently played games for a Steam ID.
        """
        cache_key = f"recent_{steam_id}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached

        params = {
            "steamid": steam_id,
            "count": 10
        }
        data = await self._request("IPlayerService/GetRecentlyPlayedGames/v0001/", params)

        if "response" in data and "games" in data["response"]:
            games = data["response"]["games"]
            self._set_cache(cache_key, games)
            return games
        return []

    async def get_user_stats_for_game(self, steam_id: str, app_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user stats and achievements for a game.
        """
        cache_key = f"stats_{steam_id}_{app_id}"
        cached = self._get_cache(cache_key)
        if cached: return cached

        params = {"steamid": steam_id, "appid": app_id}
        data = await self._request("ISteamUserStats/GetUserStatsForGame/v0002/", params)
        
        if "playerstats" in data:
            self._set_cache(cache_key, data["playerstats"])
            return data["playerstats"]
        return None

    async def get_schema_for_game(self, app_id: int) -> Optional[Dict[str, Any]]:
        """
        Get game schema (achievement names, icons).
        """
        cache_key = f"schema_{app_id}"
        cached = self._get_cache(cache_key)
        if cached: return cached

        params = {"appid": app_id}
        data = await self._request("ISteamUserStats/GetSchemaForGame/v2/", params)
        
        if "game" in data:
            self._set_cache(cache_key, data["game"])
            return data["game"]
        return None
