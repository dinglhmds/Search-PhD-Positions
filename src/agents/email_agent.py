import json
from openai import OpenAI
from typing import Dict, Any, Optional

class EmailAgent:
    def __init__(self, api_key: str, model: str = "Qwen/Qwen3-VL-32B-Instruct"):
        """
        :param api_key: SiliconFlow API Key
        :param model: model name
        """
        self.client = OpenAI(
            base_url="https://api.siliconflow.cn/v1",
            api_key=api_key
        )
        self.model = model

    def generate_email(self, applicant_profile: Dict[str, Any], prof_info: Dict[str, Any]) -> str:
        """
        生成套磁信
        :param applicant_profile: 申请者信息 (姓名, 学校, GPA, 经历等)
        :param prof_info: 导师信息 (姓名, 职称, 研究方向, 所在学校)
        """
        
        # 构造 Prompt
        system_prompt = (
            "你是一位专业的留学申请顾问和学术写作专家。你的任务是帮助学生撰写一封发给教授的“套磁信”（Cold Email）。"
            "邮件必须专业、礼貌、简洁（300词以内），并重点展示学生背景与教授研究方向的契合度（Fit）。"
            "请直接输出邮件正文，不需要包含 Subject 行以外的解释性文字。"
        )

        user_prompt = f"""
请根据以下信息撰写一封套磁信。

### 1. 目标教授信息
- 姓名: {prof_info.get('name')}
- 职称: {prof_info.get('title')}
- 学校: {prof_info.get('uni_name')}
- 研究方向: {prof_info.get('research_areas')}

### 2. 申请者（学生）信息
- 姓名: {applicant_profile.get('name', '[My Name]')}
- 当前/毕业院校: {applicant_profile.get('university', '[My University]')}
- 专业: {applicant_profile.get('major', '[My Major]')}
- 核心指标: GPA {applicant_profile.get('gpa', 'N/A')}, 语言成绩 {applicant_profile.get('language_score', 'N/A')}
- 研究经历/亮点: {applicant_profile.get('experience', 'N/A')}
- 申请意向: {applicant_profile.get('intent', 'PhD/Master application')}

### 撰写要求：
1. **邮件主题 (Subject)**: 必须清晰，包含 "Prospective Student" 和具体研究兴趣。
2. **开头**: 简要介绍自己。
3. **核心段落 (The Hook)**: 极其重要！请结合【学生的经历】和【教授的研究方向】。不要只说“我对你的研究感兴趣”，要具体说明学生的背景（如掌握的技术、做过的项目）如何能为教授的课题组做出贡献。
4. **结尾**: 礼貌地询问是否有招生名额，并提到附件附上了 CV。
5. **语气**: 即使学生经历一般，也要写得自信、积极、好学。
6. **语言**: 纯正的学术英语。

请直接生成邮件内容：
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error generating email: {str(e)}"