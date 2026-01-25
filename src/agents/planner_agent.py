import yaml
import json
from openai import OpenAI
from typing import Dict, Any

class PlannerAgent:
    def __init__(self, api_key: str, model: str = "Qwen/Qwen2-7B-Instruct", yaml_path: str = "./configs/universities.yaml"):
        """
        :param api_key: SiliconFlow API Key
        :param model: SiliconFlow 模型名称
        :param yaml_path: 学校映射文件路径
        """
        self.client = OpenAI(
            base_url="https://api.siliconflow.cn/v1",
            api_key=api_key
        )
        self.model = model
        self.university_map = self._load_university_map(yaml_path)

    def _load_university_map(self, yaml_path: str) -> Dict[str, Any]:
        """加载学校别名映射表"""
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)
            mapping = {}
            for uni in raw_data:
                name = uni["name"].lower()
                domain = uni["domain"]
                mapping[name] = domain
                for alias in uni.get("aliases", []):
                    mapping[alias.lower()] = domain
            return mapping
        except FileNotFoundError:
            print(f"警告：未找到映射文件 {yaml_path}，将仅依赖大模型标准化")
            return {}

    async def normalize_university(self, raw_name: str) -> Dict[str, str]:
        """
        标准化学校名称并返回官方域名。
        优先使用本地 YAML 映射，失败则调用 SiliconFlow。
        """
        # 1. 本地映射匹配
        lower_name = raw_name.lower().strip()
        if lower_name in self.university_map:
            return {
                "standard_name": raw_name,
                "domain": self.university_map[lower_name]
            }

        # 2. 调用 SiliconFlow 大模型
        prompt = (
            "你是一个大学名称标准化专家。请将用户输入的大学名称转换为官方英文全称及其主官网域名（必须是 .edu 或对应国家教育域名）。\n"
            "要求：\n"
            "- 返回纯 JSON 对象，格式：{\"standard_name\": \"...\", \"domain\": \"...\"}\n"
            "- domain 必须是有效的官网主域名（如 stanford.edu），不要包含 http/路径\n"
            "- 如果不确定，请尽量推测最可能的官方名称和域名\n\n"
            f"用户输入: {raw_name}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你必须返回严格符合 JSON 格式的响应，不要包含任何额外文本。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=256,
                response_format={"type": "json_object"}  # 强制 JSON 输出
            )
            result = json.loads(response.choices[0].message.content)
            return {
                "standard_name": result.get("standard_name", raw_name),
                "domain": result.get("domain", "").lower().replace("http://", "").replace("https://", "").split('/')[0]
            }
        except Exception as e:
            print(f"⚠️ SiliconFlow 标准化失败: {e}")
            # 3. 降级策略
            fallback_domain = ''.join(c for c in raw_name if c.isalnum() or c in [' ', '-']).split()[0].lower() + ".edu"
            return {
                "standard_name": raw_name,
                "domain": fallback_domain
            }
        
async def main():
    API_KEY = "sk-rcbqhobnnnytzvyvqxcfsiaejkaoxmyfsenxpakjbimtegrp"

    agent = PlannerAgent(api_key=API_KEY, model="Qwen/Qwen2-7B-Instruct")

    test_cases = [
        "UNC",
        "UCLA",
    ]

    for case in test_cases:
        print(f"\n🔍 输入: \"{case}\"")
        result = await agent.normalize_university(case)
        print(f"✅ 标准化结果: {result['standard_name']}")
        print(f"🌐 推荐域名: {result['domain']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())