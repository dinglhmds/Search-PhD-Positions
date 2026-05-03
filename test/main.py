import asyncio
import os
from src.agents.search_agent import SearchAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.crawler_agent import CrawlerAgent
from src.agents.parser_agent import ParserAgent

async def main():
    SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    if not SEARCH_API_KEY or not LLM_API_KEY:
        print("❌ 请先设置 SEARCH_API_KEY 和 LLM_API_KEY 环境变量")
        return

    uni = "GMU"

    # 1. 标准化学校
    planner = PlannerAgent(api_key=LLM_API_KEY)
    uni_info = await planner.normalize_university(uni)

    # print(uni_info)

    # 2. 智能搜索师资页
    searcher = SearchAgent(serpapi_key=SEARCH_API_KEY, top_k=10)
    results = await searcher.search_faculty_pages(uni_info["domain"])

    # print(results)

    # 3. 输出
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f"   {r['url']}\n")

    # 4. 爬取第一个搜索结果的师资信息
    if results:
        target_url = results[0]['url']
        print(f"开始爬取: {target_url}")

        async with CrawlerAgent() as crawler_agent:
            await crawler_agent.crawl_faculty(target_url, save_md=True, md_path=f"./runs/{uni}.md")

    # 5. 解析保存的MD文件
    import os
    md_file_path = f"./runs/{uni}.md"
    if os.path.exists(md_file_path):
        print(f"\n开始解析: {md_file_path}")

        # 初始化ParserAgent并解析内容
        from src.agents.parser_agent import ParserAgent
        parser = ParserAgent(api_key=LLM_API_KEY)

        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        parsed_result = parser.parse(content)

        # 保存解析结果
        import json
        output_file = f"./runs/{uni}_parsed.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(parsed_result, f, ensure_ascii=False, indent=2)

        print(f"解析结果已保存到: {output_file}")

        # 打印解析结果摘要
        faculty_count = len(parsed_result['faculty'])
        print(f"共解析出 {faculty_count} 位教师的信息")

        if faculty_count > 0:
            print(f"\n前3位教师信息:")
            for i, prof in enumerate(parsed_result["faculty"][:3]):
                print(f"\n{i+1}. {prof['name']}")
                print(f"   职称: {prof['title']}")
                print(f"   研究方向: {', '.join(prof['research_areas'])}")
                print(f"   邮箱: {prof['email']}")
    else:
        print(f"警告: 未找到文件 {md_file_path}，跳过解析步骤")

if __name__ == "__main__":
    asyncio.run(main())