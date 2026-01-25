import asyncio
from crawl4ai import AsyncWebCrawler

class CrawlerAgent:
    def __init__(self):
        self.crawler = None

    async def __aenter__(self):
        self.crawler = AsyncWebCrawler()
        await self.crawler.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.crawler.__aexit__(exc_type, exc_val, exc_tb)

    async def save_markdown_to_file(self, markdown_content: str, filename: str):
        """Save the crawled markdown content to a local file"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)

    async def crawl_faculty(self, base_url: str, save_md: bool = False, md_path: str=f"./runs/faculty.md"):
        result = await self.crawler.arun(url=base_url)
        if save_md:
            await self.save_markdown_to_file(result.markdown, md_path)
        
        return result


# Example usage
async def main():
    async with CrawlerAgent() as agent:
        await agent.crawl_faculty("https://www.cms.caltech.edu/people/faculty", save_md=True)

if __name__ == "__main__":
    asyncio.run(main())