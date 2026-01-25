import os
import json
import re
import time
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# 硅基流动API配置（请确保此处或环境变量中有你的API Key）
SILICON_FLOW_API_KEY = os.getenv("SILICON_FLOW_API_KEY", "sk-rcbqhobnnnytzvyvqxcfsiaejkaoxmyfsenxpakjbimtegrp")
SILICON_FLOW_BASE_URL = "https://api.siliconflow.cn/v1"

class ParserAgent:
    """使用硅基流动API + Qwen3-VL-32B-Instruct的并行解析器"""
    
    def __init__(self, api_key: str = SILICON_FLOW_API_KEY, model_name: str = "Qwen/Qwen3-VL-32B-Instruct", max_workers: int = 8):
        """
        初始化解析器
        :param api_key: 硅基流动API密钥
        :param model_name: 模型名称
        :param max_workers: 最大并发线程数（避免API限流）
        """
        self.api_key = api_key
        self.model_name = model_name
        self.max_chunk_size = 8000  # 每个分块的最大字符数
        self.max_workers = max(1, min(8, max_workers))  # 限制在1-8之间
    
    def _split_content(self, content: str) -> List[str]:
        """简单按长度分块（优化在行尾分割）"""
        chunks = []
        start = 0
        n = len(content)
        
        while start < n:
            end = start + self.max_chunk_size
            if end >= n:
                chunks.append(content[start:])
                break
            
            # 尝试在行尾分割
            split_index = end
            for i in range(end, start - 1, -1):
                if content[i] == '\n':
                    split_index = i + 1
                    break
            
            chunks.append(content[start:split_index])
            start = split_index
        
        return chunks

    def _parse_chunk(self, chunk: str) -> Dict[str, List[Dict]]:
        """解析单个内容块（使用硅基流动API）"""
        prompt = f"""你是一个专业的学术信息提取助手，负责从CS院系的教授列表中提取关键信息。
        
        请严格按照以下要求处理：
        1. 提取教授信息：姓名、职称、研究方向、邮箱、**个人主页链接**。
        2. 研究方向以列表形式呈现（例如：["machine learning", "Computer Vision"]）。
        3. 链接提取规则：如果教授姓名在原文中是Markdown链接（如 [Name](url)），请提取该url作为link；否则link填"未提供"。
        4. 如果没有明确邮箱，使用"未提供"。
        5. 仅输出JSON格式，不要任何其他说明。
        
        输出格式：
        {{
            "faculty": [
                {{
                    "name": "姓名",
                    "title": "职称",
                    "research_areas": ["方向1", "方向2"],
                    "email": "邮箱",
                    "link": "URL链接或'未提供'"
                }}
            ]
        }}
        
        内容：
        {chunk}"""
        
        # 调用硅基流动API
        from langchain_community.chat_models import ChatOpenAI
        llm = ChatOpenAI(
            model_name=self.model_name,
            openai_api_key=self.api_key,
            openai_api_base=SILICON_FLOW_BASE_URL,
            temperature=0,
            max_tokens=4096,
            model_kwargs={"top_p": 0.9}
        )
        
        response = llm.invoke(prompt)
        content = response.content
        
        # 尝试解析JSON
        try:
            clean_content = re.sub(r"```json|```", "", content).strip()
            return json.loads(clean_content)
        except json.JSONDecodeError:
            print(f"⚠️ JSON解析失败，尝试回退处理: {content[:500]}...")
            return self._fallback_parse(chunk)
    
    def _fallback_parse(self, content: str) -> Dict[str, List[Dict]]:
        """JSON解析失败时的回退处理"""
        faculty_list = []
        names = re.findall(r"(\*\*[^*]+\*\*)", content)
        
        for name in names:
            clean_name = name.strip("**")
            
            # 尝试正则提取 Title
            title_match = re.search(rf"{re.escape(clean_name)}\s*([^\n]+?)(?=\n|$)", content)
            title = title_match.group(1).strip() if title_match else "教授"
            
            # 尝试正则提取 Email
            email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", content)
            email = email_match.group(0) if email_match else "未提供"
            
            # 尝试正则提取 Link (如果在Markdown中是链接格式)
            # 匹配模式: [**Name**](url) 或 [Name](url)
            link = "未提供"
            link_match = re.search(rf"\[{re.escape(name)}\]\((http[^)]+)\)", content)
            if not link_match:
                 link_match = re.search(rf"\[{re.escape(clean_name)}\]\((http[^)]+)\)", content)
            if link_match:
                link = link_match.group(1)

            research_areas = ["未提供"]
            
            faculty_list.append({
                "name": clean_name,
                "title": title,
                "research_areas": research_areas,
                "email": email,
                "link": link
            })
        
        return {"faculty": faculty_list}
    
    def parse(self, content: str) -> Dict[str, List[Dict]]:
        """主解析函数（并行版）"""
        # 1. 分块处理
        chunks = self._split_content(content)
        print(f"✅ 已分割为 {len(chunks)} 个分块，开始并行解析...")
        
        # 2. 并行解析每个分块
        all_faculty = []
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = {}
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                futures[executor.submit(self._parse_chunk, chunk)] = i
            
            # 处理完成的任务
            completed = 0
            for future in as_completed(futures):
                i = futures[future]
                chunk = chunks[i]
                try:
                    result = future.result()
                    all_faculty.extend(result.get("faculty", []))
                    completed += 1
                    print(f"✅ 分块 {i+1}/{len(chunks)} 解析完成 (进度: {completed}/{len(chunks)})")
                except Exception as e:
                    print(f"❌ 分块 {i+1}/{len(chunks)} 失败: {str(e)}")
        
        # 3. 去重
        seen = set()
        unique_faculty = []
        for prof in all_faculty:
            # 优先保留信息更全的（如果有link优先保留有link的）
            if prof["name"] not in seen:
                seen.add(prof["name"])
                unique_faculty.append(prof)
        
        # 4. 性能统计
        duration = time.time() - start_time
        print(f"\n✨ 解析完成! 总耗时: {duration:.2f}秒 ({len(chunks)}个分块, {self.max_workers}线程)")
        
        return {"faculty": unique_faculty}

if __name__ == "__main__":
    pass