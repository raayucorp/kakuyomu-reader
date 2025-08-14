import re
import time
import json
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template_string, request, redirect, url_for

# --- Flaskアプリケーションの初期化 ---
app = Flask(__name__)

# --- グローバル設定 ---
BASE_URL = "https://kakuyomu.jp/"
SEARCH_URL = "https://kakuyomu.jp/search"
RANKING_URL_BASE = "https://kakuyomu.jp/rankings"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
HEADERS = {"User-Agent": USER_AGENT}

# ==============================================================================
# --- HTMLテンプレート ---
# ==============================================================================

# --- 共通のベーステンプレート ---
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}軽量カクヨムリーダー{% endblock %}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body, input, button {
            /* サイト全体のフォントを明朝体に統一 */
            font-family: "游明朝体", "Yu Mincho", "YuMincho", "ヒラギノ明朝 ProN W3", "Hiragino Mincho ProN", "HG明朝E", "ＭＳ Ｐ明朝", "MS PMincho", serif;
            line-height: 1.8;
            margin: 8px;
            letter-spacing: 0.05em;
        }
        h1, h2, h3 {
            margin: 1em 0 0.5em 0;
            padding-bottom: 0.2em;
            border-bottom: 1px solid #ccc;
        }
        a { color: #007bff; text-decoration: none; }
        .container { max-width: 800px; margin: 0 auto; }
        .nav { margin: 1em 0; padding: 0.5em 0; border-top: 1px solid #ccc; border-bottom: 1px solid #ccc; }
        .nav a, .nav strong { margin-right: 1em; }
        .summary { background: #f4f4f4; padding: 0.8em; border-left: 4px solid #ccc; margin: 1em 0; font-size: 0.9em; white-space: pre-wrap; }
        .pagination { margin: 1em 0; text-align: center; }
        .pagination a { margin: 0 0.5em; }
        .error { color: red; font-weight: bold; }
        ul, ol { padding-left: 20px; }
        li { margin-bottom: 0.5em; }
        .form-group { margin-bottom: 1em; }
        input[type="text"] { width: 70%; padding: 5px; }
        input[type="submit"] { padding: 5px 10px; cursor: pointer; }
        .chapter-title { background-color: #eee; padding: 0.3em 0.5em; font-weight: bold; margin-top: 1.5em; }
        .footer-note { font-size: 0.8em; color: #666; text-align: center; margin-top: 2em; }
        .ranking-item { margin-bottom: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 1em; }
        .ranking-item h3 { border: none; margin-top: 0; padding-bottom: 0; }
        .ranking-item p { margin: 0.2em 0; }
        .ranking-item small { color: #555; font-size: 0.8em; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1><a href="/">軽量カクヨムリーダー</a></h1>
        </header>
        <main>
            {% block content %}{% endblock %}
        </main>
        <footer>
            <hr>
            <p class="footer-note">
                このサイトは「カクヨム」のコンテンツをスクレイピングし、軽量化して表示しています。<br>
                個人利用の範囲でご利用ください。
            </p>
        </footer>
    </div>
</body>
</html>
"""

# --- トップページ（検索フォーム） ---
INDEX_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
    <h2>小説検索</h2>
    <form action="{{ url_for('search') }}" method="get">
        <div class="form-group">
            <input type="text" name="q" placeholder="作品名、作者名など" required>
            <input type="submit" value="検索">
        </div>
    </form>
    <hr>
    <h2>ランキング</h2>
    <h3>総合ランキング</h3>
    <p>
        <a href="{{ url_for('ranking', genre='all', period='daily') }}">日間</a> |
        <a href="{{ url_for('ranking', genre='all', period='weekly') }}">週間</a> |
        <a href="{{ url_for('ranking', genre='all', period='monthly') }}">月間</a> |
        <a href="{{ url_for('ranking', genre='all', period='yearly') }}">年間</a> |
        <a href="{{ url_for('ranking', genre='all', period='entire') }}">累計</a>
    </p>
    {% endblock %}"""
)

# --- ランキングページ ---
RANKING_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}軽量カクヨムリーダー{% endblock %}",
    "{% block title %}{{ title }}{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
    <h2>{{ title }}</h2>

    <div class="nav">
        <strong>期間:</strong>
        <a href="{{ url_for('ranking', genre=genre, period='daily') }}" {% if period == 'daily' %}style="font-weight:bold;"{% endif %}>日間</a>
        <a href="{{ url_for('ranking', genre=genre, period='weekly') }}" {% if period == 'weekly' %}style="font-weight:bold;"{% endif %}>週間</a>
        <a href="{{ url_for('ranking', genre=genre, period='monthly') }}" {% if period == 'monthly' %}style="font-weight:bold;"{% endif %}>月間</a>
        <a href="{{ url_for('ranking', genre=genre, period='yearly') }}" {% if period == 'yearly' %}style="font-weight:bold;"{% endif %}>年間</a>
        <a href="{{ url_for('ranking', genre=genre, period='entire') }}" {% if period == 'entire' %}style="font-weight:bold;"{% endif %}>累計</a>
    </div>

    {% if results %}
        <div>
        {% for novel in results %}
            <div class="ranking-item">
                <h3>{{ novel.rank }}. <a href="{{ url_for('table_of_contents', work_id=novel.work_id) }}">{{ novel.title }}</a></h3>
                <p>作者: {{ novel.author }}</p>
                <small>{{ novel.meta }}</small>
                <div class="summary">{{ novel.summary }}</div>
            </div>
        {% endfor %}
        </div>
    {% else %}
        <p>ランキング情報が取得できませんでした。</p>
    {% endif %}

    <div class="pagination">
        {% if pagination.prev %}
            <a href="{{ url_for('ranking', genre=genre, period=period, page=pagination.prev) }}">< 前のページ</a>
        {% endif %}
        {% if pagination.prev or pagination.next %}
            <span>- {{ current_page }} -</span>
        {% endif %}
        {% if pagination.next %}
            <a href="{{ url_for('ranking', genre=genre, period=period, page=pagination.next) }}">次のページ ></a>
        {% endif %}
    </div>
    {% endblock %}"""
)

# --- 検索結果ページ ---
SEARCH_RESULTS_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}軽量カクヨムリーダー{% endblock %}",
    "{% block title %}{{ query }} の検索結果{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
    <h2>「{{ query }}」の検索結果 ({{ total }}件)</h2>

    {% if results %}
        <ol>
        {% for novel in results %}
            <li>
                <strong><a href="{{ url_for('table_of_contents', work_id=novel.work_id) }}">{{ novel.title }}</a></strong><br>
                作者: {{ novel.author }}<br>
                <div class="summary">{{ novel.summary }}</div>
            </li>
        {% endfor %}
        </ol>
    {% else %}
        <p>作品が見つかりませんでした。</p>
    {% endif %}

    <div class="pagination">
        {% if pagination.prev %}
            <a href="{{ url_for('search', q=query, page=pagination.prev) }}">< 前のページ</a>
        {% endif %}
        {% if pagination.prev or pagination.next %}
            <span>- {{ current_page }} -</span>
        {% endif %}
        {% if pagination.next %}
            <a href="{{ url_for('search', q=query, page=pagination.next) }}">次のページ ></a>
        {% endif %}
    </div>
    {% endblock %}"""
)

# --- 目次ページ ---
TOC_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}軽量カクヨムリーダー{% endblock %}",
    "{% block title %}{{ novel.title }}{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
    <h2>{{ novel.title }}</h2>
    <p>作者: {{ novel.author }}</p>

    <h3>あらすじ</h3>
    <div class="summary">{{ novel.summary | safe }}</div>

    <h3>目次</h3>
    {% if novel.episodes %}
        <div>
        {% for item in novel.episodes %}
            {% if item.is_chapter %}
                <div class="chapter-title">{{ item.title }}</div>
            {% else %}
                <ul style="list-style-type: none; padding-left: 10px;">
                    <li><a href="{{ url_for('viewer', work_id=novel.work_id, episode_id=item.episode_id) }}">{{ item.title }}</a></li>
                </ul>
            {% endif %}
        {% endfor %}
        </div>
    {% else %}
        <p>目次が取得できませんでした。</p>
    {% endif %}
    {% endblock %}"""
)

# --- 本文表示ページ ---
VIEWER_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}軽量カクヨムリーダー{% endblock %}",
    "{% block title %}{{ novel.title }} - {{ novel.subtitle }}{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
    <h2><a href="{{ url_for('table_of_contents', work_id=work_id) }}">{{ novel.title }}</a></h2>
    <h3>{{ novel.subtitle }}</h3>

    <div class="nav">
        {% if nav.prev %}<a href="{{ nav.prev }}">＜ 前の話</a>{% endif %}
        <a href="{{ nav.toc }}">目次</a>
        {% if nav.next %}<a href="{{ nav.next }}">次の話 ＞</a>{% endif %}
    </div>

    <div id="novel_body">
        {% for line in novel.body %}
            <p>{{ line | safe }}</p>
        {% endfor %}
    </div>

    <div class="nav">
        {% if nav.prev %}<a href="{{ nav.prev }}">＜ 前の話</a>{% endif %}
        <a href="{{ nav.toc }}">目次</a>
        {% if nav.next %}<a href="{{ nav.next }}">次の話 ＞</a>{% endif %}
    </div>
    {% endblock %}"""
)

# --- エラーページ ---
ERROR_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block title %}軽量カクヨムリーダー{% endblock %}",
    "{% block title %}エラー{% endblock %}"
).replace(
    "{% block content %}{% endblock %}",
    """{% block content %}
    <h2>エラーが発生しました</h2>
    <p class="error">{{ message }}</p>
    <a href="/">トップに戻る</a>
    {% endblock %}"""
)


# ==============================================================================
# --- ヘルパー関数 ---
# ==============================================================================

def get_page_content(url, params=None):
    """指定されたURLのHTMLコンテンツを取得する"""
    try:
        time.sleep(1) # サーバー負荷軽減のため1秒待機
        response = requests.get(url, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_work_id_from_url(url):
    """URLから作品IDを抽出する"""
    if not url: return None
    match = re.search(r'/works/(\d+)', url)
    return match.group(1) if match else None

def get_episode_id_from_url(url):
    """URLからエピソードIDを抽出する"""
    if not url: return None
    match = re.search(r'/episodes/(\d+)', url)
    return match.group(1) if match else None

# ==============================================================================
# --- スクレイピング関数 ---
# ==============================================================================

def scrape_ranking_page(genre, period, page=1):
    """ランキングページをスクレイピングする"""
    url = f"{RANKING_URL_BASE}/{genre}/{period}"
    params = {'page': page}
    soup = get_page_content(url, params)
    if not soup:
        return None

    results = []
    # 広告枠などを除外し、純粋なランキングアイテム(`.widget-work.float-parent`)のみを選択
    ranking_items = soup.select('div.widget-work.float-parent')
    
    for item in ranking_items:
        # find_parentで広告枠内の要素でないことを確認
        if item.find_parent(class_='widget-workRankingBoxForNext'):
            continue

        rank_tag = item.select_one('p.widget-work-rank')
        title_tag = item.select_one('h3.widget-workCard-title a.widget-workCard-titleLabel')
        author_tag = item.select_one('a.widget-workCard-authorLabel')
        summary_tag = item.select_one('p.widget-workCard-introduction a')
        meta_tag = item.select_one('p.widget-workCard-meta')

        # 必須要素がなければスキップ
        if not (rank_tag and title_tag and title_tag.get('href')):
            continue

        work_id = get_work_id_from_url(title_tag['href'])
        if work_id:
            meta_text = ""
            if meta_tag:
                # get_text() を使ってシンプルに取得し、不要な空白や改行を整理
                meta_text_raw = meta_tag.get_text(separator=' | ', strip=True)
                # ' | ' で分割し、空でない要素だけを再結合
                meta_text = ' | '.join(part for part in meta_text_raw.split(' | ') if part)

            results.append({
                'rank': rank_tag.get_text(strip=True),
                'title': title_tag.get_text(strip=True),
                'work_id': work_id,
                'author': author_tag.get_text(strip=True) if author_tag else '作者不明',
                'summary': summary_tag.get_text(strip=True) if summary_tag else 'あらすじなし',
                'meta': meta_text
            })

    pagination = {'prev': None, 'next': None}
    next_page_tag = soup.select_one('p.widget-pagerNext a')
    if next_page_tag and next_page_tag.get('href'):
        pagination['next'] = page + 1
        
    if page > 1:
        pagination['prev'] = page - 1
        
    title_tag = soup.select_one('header.widget-media-genresWorkList-listTitle h3')
    title = title_tag.get_text(strip=True) if title_tag else 'ランキング'

    return {'results': results, 'pagination': pagination, 'title': title}


def scrape_search_page(query, page=1):
    """検索結果ページをスクレイピングする"""
    params = {'q': query, 'page': page}
    soup = get_page_content(SEARCH_URL, params)
    if not soup:
        return None

    results = []
    # Next.jsの動的クラス名に対応するため、より一般的なセレクタを使用
    search_results = soup.select('#search-result-main div[class*="WorkListItem_container"]')
    if not search_results:
        # 代替セレクタ
        title_links = soup.select('h3[class*="Heading_heading"] a[href^="/works/"]')
        search_results = [tag.find_parent('div', class_=lambda c: c and 'NewBox_box' in c and 'padding-py-m' in c) for tag in title_links]


    for item in search_results:
        if not item: continue
        title_tag = item.select_one('h3[class*="Heading_heading"] a')
        author_tag = item.select_one('span[class*="WorkTitle_workLabelAuthor"] a')
        summary_tag = item.select_one('a[href^="/works/"] > div[class*="partialGiftWidgetWeakText"]')

        if title_tag and title_tag.get('href'):
            work_id = get_work_id_from_url(title_tag['href'])
            if work_id:
                results.append({
                    'title': title_tag.get_text(strip=True),
                    'work_id': work_id,
                    'author': author_tag.get_text(strip=True) if author_tag else '作者不明',
                    'summary': summary_tag.get_text(strip=True, separator='\n') if summary_tag else 'あらすじなし'
                })

    pagination = {'prev': None, 'next': None}
    total_text_container = soup.select_one('div[class*="Typography_align-right"]')
    total_text = total_text_container.get_text(strip=True) if total_text_container else ""
    total_count_match = re.search(r'全(\d+)件', total_text)
    total = total_count_match.group(1) if total_count_match else '多数'
    
    # ページネーションの有無を判定
    # 検索結果が20件（1ページの最大数）あれば、次のページがある可能性があるとみなす
    if len(results) >= 20:
        pagination['next'] = page + 1
    if page > 1:
        pagination['prev'] = page - 1

    return {'results': results, 'pagination': pagination, 'total': total}

def scrape_toc_page(work_id):
    """作品の目次ページをスクレイピングする（__NEXT_DATA__ JSONを解析する方式）"""
    url = urljoin(BASE_URL, f"works/{work_id}")
    soup = get_page_content(url)
    if not soup:
        return None

    script_tag = soup.find('script', id='__NEXT_DATA__')
    if not script_tag:
        return None

    try:
        data = json.loads(script_tag.string)
        apollo_state = data['props']['pageProps']['__APOLLO_STATE__']
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing JSON data: {e}")
        return None

    work_key = f'Work:{work_id}'
    if work_key not in apollo_state:
        return None
    work_data = apollo_state[work_key]

    author_key = work_data.get('author', {}).get('__ref')
    author_name = apollo_state.get(author_key, {}).get('activityName', '作者不明')

    novel_info = {
        'title': work_data.get('title', 'タイトル不明'),
        'work_id': work_id,
        'author': author_name,
        'summary': work_data.get('introduction', '').replace('\\n', '\n'),
        'episodes': []
    }

    toc_refs = work_data.get('tableOfContents', [])
    for toc_ref in toc_refs:
        chapter_key = toc_ref.get('__ref')
        chapter_data = apollo_state.get(chapter_key)
        
        if not chapter_data:
            continue
            
        # 章タイトルを追加 (章が存在する場合のみ)
        # 'chapter'キーの値がnull (PythonではNone) の場合があるため、チェックを強化
        chapter_ref = chapter_data.get('chapter')
        if chapter_ref and chapter_ref.get('__ref'):
            chapter_info_key = chapter_ref.get('__ref')
            chapter_info = apollo_state.get(chapter_info_key)
            if chapter_info:
                novel_info['episodes'].append({
                    'is_chapter': True,
                    'title': chapter_info.get('title', '章タイトル不明')
                })

        # エピソードリストを追加
        episode_refs = chapter_data.get('episodeUnions', [])
        for episode_ref in episode_refs:
            episode_key = episode_ref.get('__ref')
            episode_data = apollo_state.get(episode_key)
            if episode_data:
                episode_id = episode_data.get('id')
                if episode_id:
                    novel_info['episodes'].append({
                        'is_chapter': False,
                        'title': episode_data.get('title', 'エピソード不明'),
                        'episode_id': episode_id
                    })
                
    return novel_info

def scrape_viewer_page(work_id, episode_id):
    """小説の本文ページをスクレイピングする"""
    url = urljoin(BASE_URL, f"works/{work_id}/episodes/{episode_id}")
    soup = get_page_content(url)
    if not soup:
        return None

    title_tag = soup.select_one('#worksEpisodesEpisodeHeader-breadcrumbs h1 a')
    subtitle_tag = soup.select_one('.widget-episodeTitle, p[class*="WorkEpisode_title__"]')

    title = title_tag.get_text(strip=True) if title_tag else '作品タイトル不明'
    subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else 'サブタイトル不明'
    
    novel_honbun = soup.select_one('div.widget-episodeBody, div[class*="Viewer_viewer__"]')

    if novel_honbun:
        for ruby in novel_honbun.find_all('ruby'):
            rt = ruby.find('rt')
            if not rt: continue
            for rp in ruby.find_all('rp'): rp.decompose()
            rt_text = rt.get_text(strip=True)
            rt.decompose()
            rb_text = ruby.get_text(strip=True)
            ruby.replace_with(f'{rb_text}({rt_text})')
        
        body_lines = [p.get_text('\n', strip=True) for p in novel_honbun.find_all('p') if p.get_text(strip=True)]
    else:
        body_lines = ['本文が取得できませんでした。']

    novel = {
        'title': title,
        'subtitle': subtitle,
        'body': body_lines
    }

    nav = {'prev': None, 'toc': url_for('table_of_contents', work_id=work_id), 'next': None}
    
    prev_tag = soup.select_one('link[rel="prev"], a[class*="ChapterLink_prev__"]')
    if prev_tag and prev_tag.get('href'):
        prev_episode_id = get_episode_id_from_url(prev_tag['href'])
        if prev_episode_id:
            nav['prev'] = url_for('viewer', work_id=work_id, episode_id=prev_episode_id)

    next_tag = soup.select_one('link[rel="next"], a[class*="ChapterLink_next__"]')
    if next_tag and next_tag.get('href'):
        next_episode_id = get_episode_id_from_url(next_tag['href'])
        if next_episode_id:
            nav['next'] = url_for('viewer', work_id=work_id, episode_id=next_episode_id)

    return novel, nav


# ==============================================================================
# --- Flask ルート定義 ---
# ==============================================================================

@app.route('/')
def index():
    """トップページ: 検索フォームを表示"""
    return render_template_string(INDEX_TEMPLATE)

@app.route('/ranking/<genre>/<period>')
def ranking(genre, period):
    """ランキングを表示"""
    page = request.args.get('page', 1, type=int)
    
    allowed_genres = ['all', 'fantasy', 'action', 'sf', 'love_story', 'romance', 'drama', 'horror', 'mystery', 'nonfiction', 'history', 'criticism', 'others']
    allowed_periods = ['daily', 'weekly', 'monthly', 'yearly', 'entire']
    if genre not in allowed_genres or period not in allowed_periods:
        return render_template_string(ERROR_TEMPLATE, message="無効なランキングの指定です。")

    data = scrape_ranking_page(genre, period, page)
    if data is None:
        return render_template_string(ERROR_TEMPLATE, message="ランキングページの取得に失敗しました。")

    return render_template_string(
        RANKING_TEMPLATE,
        title=data['title'],
        results=data['results'],
        pagination=data['pagination'],
        current_page=page,
        genre=genre,
        period=period
    )

@app.route('/search')
def search():
    """検索結果を表示"""
    query = request.args.get('q')
    page = request.args.get('page', 1, type=int)
    if not query:
        return redirect(url_for('index'))

    data = scrape_search_page(query, page)
    if data is None:
        return render_template_string(ERROR_TEMPLATE, message="検索結果の取得に失敗しました。時間をおいて再試行してください。")

    return render_template_string(
        SEARCH_RESULTS_TEMPLATE,
        query=query,
        results=data['results'],
        total=data['total'],
        pagination=data['pagination'],
        current_page=page
    )

@app.route('/novel/<work_id>')
def table_of_contents(work_id):
    """作品の目次を表示"""
    novel_data = scrape_toc_page(work_id)
    if novel_data is None or not novel_data.get('episodes'):
        return render_template_string(ERROR_TEMPLATE, message="目次ページの取得に失敗しました。作品IDが正しいか、サイトの構造が変更されていないか確認してください。")
    
    return render_template_string(
        TOC_TEMPLATE,
        novel=novel_data
    )

@app.route('/novel/<work_id>/<episode_id>')
def viewer(work_id, episode_id):
    """小説の本文を表示"""
    result = scrape_viewer_page(work_id, episode_id)
    if result is None:
        return render_template_string(ERROR_TEMPLATE, message="本文ページの取得に失敗しました。")
    
    novel_data, nav_data = result
    return render_template_string(
        VIEWER_TEMPLATE,
        work_id=work_id,
        novel=novel_data,
        nav=nav_data
    )

# --- 実行 ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
