import os
import json
import re
import time
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# 硅基流动API配置（请替换为你的实际API密钥）
SILICON_FLOW_API_KEY = "sk-rcbqhobnnnytzvyvqxcfsiaejkaoxmyfsenxpakjbimtegrp"
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
        # 提示词设计
        prompt = f"""你是一个专业的学术信息提取助手，负责从CS院系的教授列表中提取关键信息。
        
        请严格按照以下要求处理：
        1. 只提取教授信息（姓名、职称、研究方向、邮箱）
        2. 研究方向以列表形式呈现（例如：["machine learning", "Computer Vision", ...]）
        3. 如果没有明确邮箱，使用"未提供"
        4. 仅输出JSON格式，不要任何其他说明
        
        输出格式：
        {{
            "faculty": [
                {{
                    "name": "姓名",
                    "title": "职称",
                    "research_areas": ["方向1", "方向2"],
                    "email": "邮箱"
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
            model_kwargs={"top_p": 0.9}  # 优化生成质量
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
            name = name.strip("**")
            title_match = re.search(rf"{re.escape(name)}\s*([^\n]+?)(?=\n|$)", content)
            title = title_match.group(1).strip() if title_match else "教授"
            
            email_match = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", content)
            email = email_match.group(0) if email_match else "未提供"
            
            research_areas = ["未提供"]
            
            faculty_list.append({
                "name": name,
                "title": title,
                "research_areas": research_areas,
                "email": email
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
            if prof["name"] not in seen:
                seen.add(prof["name"])
                unique_faculty.append(prof)
        
        # 4. 性能统计
        duration = time.time() - start_time
        print(f"\n✨ 解析完成! 总耗时: {duration:.2f}秒 ({len(chunks)}个分块, {self.max_workers}线程)")
        print(f"🔍 平均每分块耗时: {duration/len(chunks):.2f}秒")
        
        return {"faculty": unique_faculty}

def main():
    """测试函数：从本地指定目录加载MD文件并解析"""
    # 配置要解析的MD文件路径（修改为你的实际路径）
    MD_FILE_PATH = "./runs/MIT.md"
    
    # 检查文件是否存在
    if not os.path.exists(MD_FILE_PATH):
        print(f"❌ 错误：文件 {MD_FILE_PATH} 不存在！")
        print("请将MD文件放在当前目录，或修改代码中的MD_FILE_PATH")
        print("示例：MD_FILE_PATH = 'path/to/your/faculty_list.md'")
        return
    
    # 1. 读取MD文件
    print(f"🔍 正在加载文件: {MD_FILE_PATH}")
    try:
        with open(MD_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"✅ 文件加载成功，长度: {len(content)} 字符")
    except Exception as e:
        print(f"❌ 读取文件失败: {str(e)}")
        return
    
    # 2. 初始化解析器
    parser = ParserAgent(api_key=SILICON_FLOW_API_KEY)
    
    # 3. 解析内容
    print("\n🚀 开始解析教授信息...")
    result = parser.parse(content)
    
    # 4. 打印结果
    print(f"\n✅ 成功提取 {len(result['faculty'])} 位教授信息")
    print("\n前3位教授信息:")
    for i, prof in enumerate(result["faculty"][:3]):
        print(f"\n{i+1}. {prof['name']}")
        print(f"   职称: {prof['title']}")
        print(f"   研究方向: {', '.join(prof['research_areas'])}")
        print(f"   邮箱: {prof['email']}")
    
    # 5. 保存为JSON文件
    output_file = "faculty_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n📊 结果已保存到: {output_file}")

if __name__ == "__main__":
    # 检查API密钥是否设置
    if SILICON_FLOW_API_KEY == "YOUR_SILICON_FLOW_API_KEY":
        print("⚠️ 请先设置SILICON_FLOW_API_KEY环境变量或修改代码中的API密钥")
        print("示例: export SILICON_FLOW_API_KEY='your_api_key'")
        print("或在代码中替换SILICON_FLOW_API_KEY变量")
    else:
        main()