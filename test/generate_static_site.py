import json
import os
from pathlib import Path

# ==============================
# 配置
# ==============================
UNI_NAME = "UMD"  # 可修改为你想要的大学名
INPUT_JSON_PATH = f"./runs/{UNI_NAME}_parsed.json"
OUTPUT_HTML_PATH = f"./static_sites/{UNI_NAME}_faculty.html"

# 创建输出目录
Path("./static_sites").mkdir(exist_ok=True)

# ==============================
# 加载数据
# ==============================
def load_faculty_data():
    if not os.path.exists(INPUT_JSON_PATH):
        print(f"⚠️  Warning: {INPUT_JSON_PATH} not found. Generating demo data.")
        return generate_demo_data()
    try:
        with open(INPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('faculty', [])
    except Exception as e:
        print(f"❌ Error loading JSON: {e}")
        return generate_demo_data()

def generate_demo_data():
    return [
        {
            "name": "Dr. Jane Smith",
            "title": "Professor of Computer Science",
            "email": "jane.smith@umd.edu",
            "research_areas": ["Artificial Intelligence", "Natural Language Processing", "Ethics in AI"]
        },
        {
            "name": "Dr. Alex Johnson",
            "title": "Associate Professor",
            "email": "alex.j@umd.edu",
            "research_areas": ["Computer Vision", "Robotics"]
        },
        {
            "name": "Dr. Mei Lin",
            "title": "Assistant Professor",
            "email": "meilin@umd.edu",
            "research_areas": ["未提供"]
        }
    ]

# ==============================
# 生成 HTML
# ==============================
def render_html(faculty_data):
    # 统计信息
    faculty_count = len(faculty_data)
    faculty_with_email = sum(1 for f in faculty_data if f.get('email') and f['email'] != '未提供')
    unique_titles = set(f['title'] for f in faculty_data if f.get('title') and f['title'] != '未提供')
    unique_research_areas = set(
        area for f in faculty_data for area in (f.get('research_areas') or [])
        if area and area != '未提供'
    )

    # 构建 faculty cards HTML
    cards_html = ""
    for f in faculty_data:
        name = f.get("name", "N/A")
        title = f.get("title", "未提供") or "未提供"
        email = f.get("email", "未提供") or "未提供"
        research_areas = f.get("research_areas", []) or []

        # 处理研究领域
        tags = ""
        if research_areas and research_areas != ["未提供"]:
            for area in research_areas:
                if area != "未提供":
                    tags += f'<span class="tag">{area}</span>\n                        '
        else:
            tags = '<span class="tag disabled">未提供</span>'

        # 构建卡片
        card = f'''
                <div class="card" data-name="{name.lower()}" data-title="{title.lower()}" data-research="{' '.join([a.lower() for a in research_areas if a != '未提供'])}">
                    <div class="card-inner">
                        <div class="card-front">
                            <div class="avatar">{name[0].upper()}</div>
                            <h3>{name}</h3>
                            <p class="title">{title}</p>
                            <div class="tags">
                                {tags}
                            </div>
                        </div>
                        <div class="card-back">
                            <div class="email">
                                <i class="fas fa-envelope"></i>
                                <a href="mailto:{email}">{email}</a>
                            </div>
                            <button class="back-btn" onclick="flipBack(this)">← Back</button>
                        </div>
                    </div>
                </div>'''
        cards_html += card

    # 完整 HTML
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>{UNI_NAME} Faculty Directory</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css"/>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }}
        body {{
            background: #0f0c29;
            background: linear-gradient(to right, #24243e, #302b63, #0f0c29);
            color: #fff;
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        h1 {{
            font-size: 3.2rem;
            margin-bottom: 12px;
            background: linear-gradient(90deg, #00dbde, #fc00ff);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            text-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }}
        .subtitle {{
            font-size: 1.2rem;
            opacity: 0.85;
            margin-bottom: 20px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 25px;
            flex-wrap: wrap;
            margin: 25px 0;
        }}
        .stat-box {{
            background: rgba(255,255,255,0.08);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 20px 25px;
            text-align: center;
            min-width: 140px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .stat-number {{
            font-size: 2.2rem;
            font-weight: bold;
            background: linear-gradient(90deg, #00c9ff, #92fe9d);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
        }}
        .stat-label {{
            font-size: 0.95rem;
            opacity: 0.8;
            margin-top: 6px;
        }}
        .search-box {{
            max-width: 600px;
            margin: 0 auto 40px;
            position: relative;
        }}
        .search-box input {{
            width: 100%;
            padding: 16px 20px 16px 50px;
            border-radius: 50px;
            border: none;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            color: white;
            font-size: 1.1rem;
            outline: none;
            border: 1px solid rgba(255,255,255,0.2);
            transition: all 0.3s ease;
        }}
        .search-box input::placeholder {{
            color: rgba(255,255,255,0.5);
        }}
        .search-box input:focus {{
            background: rgba(255,255,255,0.15);
            box-shadow: 0 0 0 3px rgba(0, 201, 255, 0.4);
        }}
        .search-icon {{
            position: absolute;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            color: rgba(255,255,255,0.7);
            font-size: 1.3rem;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 30px;
            padding: 10px;
        }}
        .card {{
            perspective: 1000px;
        }}
        .card-inner {{
            position: relative;
            width: 100%;
            height: 320px;
            transform-style: preserve-3d;
            transition: transform 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            cursor: pointer;
        }}
        .card:hover .card-inner {{
            transform: rotateY(180deg);
        }}
        .card-front, .card-back {{
            position: absolute;
            width: 100%;
            height: 100%;
            backface-visibility: hidden;
            border-radius: 20px;
            padding: 25px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
        }}
        .card-front {{
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .card-back {{
            background: linear-gradient(135deg, #0f3460, #1a1a2e);
            transform: rotateY(180deg);
            justify-content: space-between;
        }}
        .avatar {{
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #00c9ff, #92fe9d);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.2rem;
            font-weight: bold;
            color: #0f0c29;
            margin-bottom: 20px;
        }}
        .card h3 {{
            font-size: 1.6rem;
            margin-bottom: 10px;
            color: #fff;
        }}
        .title {{
            font-size: 1.05rem;
            opacity: 0.85;
            margin-bottom: 20px;
        }}
        .tags {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px;
            margin-top: 15px;
        }}
        .tag {{
            background: rgba(0, 201, 255, 0.2);
            color: #00c9ff;
            padding: 6px 14px;
            border-radius: 30px;
            font-size: 0.85rem;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(0, 201, 255, 0.3);
        }}
        .tag.disabled {{
            background: rgba(100,100,100,0.2);
            color: #aaa;
            border-color: rgba(100,100,100,0.3);
        }}
        .email {{
            font-size: 1.2rem;
            margin-bottom: 20px;
        }}
        .email a {{
            color: #92fe9d;
            text-decoration: none;
        }}
        .email a:hover {{
            text-decoration: underline;
        }}
        .back-btn {{
            background: rgba(255,255,255,0.1);
            color: white;
            border: 1px solid rgba(255,255,255,0.2);
            padding: 8px 20px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 0.95rem;
        }}
        .back-btn:hover {{
            background: rgba(255,255,255,0.2);
        }}
        footer {{
            text-align: center;
            margin-top: 60px;
            padding: 20px;
            color: rgba(255,255,255,0.6);
            font-size: 0.95rem;
        }}
        @media (max-width: 768px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
            h1 {{
                font-size: 2.4rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{UNI_NAME} Faculty Directory</h1>
            <p class="subtitle">Explore our world-class researchers and educators</p>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{faculty_count}</div>
                    <div class="stat-label">Faculty</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{len(unique_titles)}</div>
                    <div class="stat-label">Titles</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{len(unique_research_areas)}</div>
                    <div class="stat-label">Research Areas</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{faculty_with_email}</div>
                    <div class="stat-label">With Email</div>
                </div>
            </div>

            <div class="search-box">
                <i class="fas fa-search search-icon"></i>
                <input type="text" id="searchInput" placeholder="Search by name, title, or research area..." />
            </div>
        </header>

        <div class="grid" id="facultyGrid">
{cards_html}
        </div>
    </div>

    <footer>
        &copy; 2025 {UNI_NAME} Faculty Directory. All rights reserved.
    </footer>

    <script>
        function flipBack(btn) {{
            const card = btn.closest('.card');
            card.querySelector('.card-inner').style.transform = 'rotateY(0deg)';
        }}

        document.getElementById('searchInput').addEventListener('input', function() {{
            const term = this.value.trim().toLowerCase();
            const cards = document.querySelectorAll('.card');

            cards.forEach(card => {{
                const name = card.dataset.name || '';
                const title = card.dataset.title || '';
                const research = card.dataset.research || '';

                const match = name.includes(term) || title.includes(term) || research.includes(term);
                card.style.display = match ? 'block' : 'none';
            }});
        }});
    </script>
</body>
</html>'''
    return html

# ==============================
# 主程序
# ==============================
if __name__ == "__main__":
    faculty_data = load_faculty_data()
    html_content = render_html(faculty_data)
    
    with open(OUTPUT_HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ 静态网页已生成：{os.path.abspath(OUTPUT_HTML_PATH)}")
    print("💡 双击该 HTML 文件即可在浏览器中打开！")