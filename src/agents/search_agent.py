import asyncio
import aiohttp
from typing import List, Dict, Any

class SearchAgent:
    def __init__(
        self,
        serpapi_key: str,
        top_k: int = 10
    ):
        self.serpapi_key = serpapi_key
        self.top_k = top_k  # 最终返回结果数量（SerpApi 的 num 参数）
        self.search_url = "https://serpapi.com/search"

    async def _execute_google_search(self, query: str) -> List[Dict[str, str]]:
        """执行 Google 搜索 via SerpApi，返回原始 organic results"""
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "num": self.top_k,  # 控制每页结果数
            "output": "json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.search_url, params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise Exception(f"Search API error {resp.status}: {text}")
                data = await resp.json()

                # 提取 organic_results（自然搜索结果）
                organic = data.get("organic_results", [])
                results = []
                for item in organic:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", "")[:300]
                    })
                return results

    async def search_faculty_pages(self, domain: str) -> List[Dict[str, str]]:
        """主入口：构造查询并返回 Google 搜索结果（无过滤）"""
        query = (
            f'site:{domain} "computer science" '
            f'("faculty" OR "professor" OR "people" OR "directory")'
        )
        print("Search query:", query)
        results = await self._execute_google_search(query)
        return results
    
async def main():
    import os
    api_key = os.getenv("SEARCH_API_KEY", "")
    if not api_key:
        print("❌ 请先设置 SEARCH_API_KEY 环境变量")
        return
    agent = SearchAgent(serpapi_key=api_key, top_k=10)
    results = await agent.search_faculty_pages("uncc.edu")
    for r in results:
        print(f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}\n")

if __name__ == "__main__":
    asyncio.run(main())