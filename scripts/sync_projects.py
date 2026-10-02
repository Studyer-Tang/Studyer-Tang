"""Fetch public GitHub facts once; render static website data and profile tables.

Python standard library only. A failed request aborts before any file is changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html
import json
import os
from pathlib import Path
import re
import urllib.request

OWNER = 'Studyer-Tang'
ROOT = Path(__file__).resolve().parents[1]
START = '<!-- projects:start -->'
END = '<!-- projects:end -->'
FEATURED = {
    'advanced-mathematical-statistics-notes': ('高等统计学笔记', 'Statistics Notes', '学习笔记', 'Study notes'),
    'learning-theory-to-optimization': ('学习理论与优化', 'Learning Theory & Optimization', '数学推导与实验', 'Derivations & experiments'),
    'ThesisCraft': ('ThesisCraft · 学研排版', 'ThesisCraft', '论文写作', 'Academic writing'),
    'academic-clipboard': ('Academic Clipboard', 'Academic Clipboard', '科研摘录', 'Research snippets'),
    'paperstage-skill': ('PaperStage', 'PaperStage', '学术演示', 'Presentations'),
}
# Human-edited summaries describe existing scope; GitHub facts remain automatic.
SUMMARIES = {
    'advanced-mathematical-statistics-notes': (
        '高等统计学课程学习笔记，包含证明展开、例题与实际学习进度。',
        'Course notes in mathematical statistics, with expanded proofs, examples and a learning log.'),
    'learning-theory-to-optimization': (
        '学习理论与优化的学习材料，包含数学推导、练习与可复现的 NumPy 实验。',
        'Study materials in learning theory and optimization, with derivations, exercises and reproducible NumPy experiments.'),
    'ThesisCraft': (
        '本地 Word / WPS 论文排版工具，提供模板、编号、交叉引用与格式检查。',
        'Local thesis formatting for Word and WPS, with templates, numbering, cross-references and format checks.'),
    'academic-clipboard': (
        '本地研究摘录工具，保存来源信息，整理 PDF 文本、BibTeX 与表格。',
        'A local research clipboard for source-aware excerpts, PDF text, BibTeX and tables.'),
    'paperstage-skill': (
        '学术演示技能与 PPTX 工具，支持中文排版、可编辑数学公式与表格。',
        'A presentation skill and PPTX tools for Chinese typography, editable equations and tables.'),
}


def presentation(name: str, description: str):
    labels = FEATURED.get(name, (name, name, '开源项目', 'Open source'))
    return {'name': list(labels[:2]), 'label': list(labels[2:]),
            'summary': list(SUMMARIES.get(name, (description, description)))}


def get_json(path: str):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Studyer-Tang-project-sync',
               'X-GitHub-Api-Version': '2022-11-28'}
    if token := os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('https://api.github.com/' + path, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def pages(path: str, fetch=get_json):
    for page in range(1, 1001):
        batch = fetch(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
        if not isinstance(batch, list):
            raise ValueError('Expected a GitHub list response')
        yield from batch
        if len(batch) < 100:
            return
    raise ValueError('Pagination limit exceeded; keeping the previous snapshot')


def collect(fetch=get_json) -> list[dict]:
    projects = []
    for repo in pages(f'users/{OWNER}/repos?type=owner', fetch):
        name = repo['name']
        if (repo.get('private') or repo['fork'] or repo['archived']
                or name.lower() in {OWNER.lower(), f'{OWNER}.github.io'.lower()}):
            continue
        releases = [r for r in pages(f'repos/{OWNER}/{name}/releases', fetch)
                    if not r['draft'] and r.get('published_at')]
        latest = max(releases, key=lambda r: (r['published_at'], r['id']), default=None)
        projects.append({
            'repo': name, **presentation(name, repo.get('description') or ''),
            'description': repo.get('description') or '', 'url': repo['html_url'],
            'language': repo.get('language'), 'pushedAt': repo['pushed_at'],
            'release': ({'tag': latest['tag_name'], 'url': latest['html_url'],
                         'prerelease': latest['prerelease'], 'publishedAt': latest['published_at']}
                        if latest else None),
        })
    priority = {name: i for i, name in enumerate(FEATURED)}
    return sorted(projects, key=lambda p: (priority.get(p['repo'], len(priority)), p['repo'].lower()))


def markdown(value: str) -> str:
    value = html.escape(' '.join(value.split()), quote=False)
    return re.sub(r'([\\`*_{}\[\]()|])', r'\\\1', value)


def table(catalog: dict, zh: bool) -> str:
    lines = ['| 项目 | 简介 | 最新发布 |' if zh else '| Project | About | Latest release |',
             '| :--- | :--- | :--- |']
    for p in catalog['projects']:
        release = p['release']
        version = ('暂无发布' if zh else 'Source only')
        if release:
            status = ('预览版' if zh else 'Preview') if release['prerelease'] else ('已发布' if zh else 'Published')
            version = f"[{markdown(release['tag'])}]({release['url']}) · {status}"
        description = markdown(p.get('summary', [p['description'], p['description']])[0 if zh else 1]) or ('见仓库说明' if zh else 'See repository')
        lines.append(f"| **[{markdown(p['name'][0 if zh else 1])}]({p['url']})** | {description} | {version} |")
    if not catalog['projects']:
        lines.append('| — | 暂无公开项目 / No public projects | — |')
    changed_at = datetime.fromisoformat(catalog['updatedAt'].replace('Z', '+00:00'))
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    date = changed_at.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    lines.extend(['', (f'项目资料变更于 {date}（北京时间）· 每 6 小时自动核对公开仓库与发布版本；上列日期为资料变更时间。'
                       if zh else f'Catalog changed {date} (Asia/Shanghai). Public repositories and releases are checked every six hours; the date records a catalog change.'),
                  '', '[全部仓库 / All repositories](https://github.com/Studyer-Tang?tab=repositories)'])
    return '\n'.join(lines)


def render_readme(text: str, catalog: dict, zh: bool) -> str:
    if text.count(START) != 1 or text.count(END) != 1 or text.index(START) >= text.index(END):
        raise ValueError('README must contain exactly one ordered pair of project markers')
    before, rest = text.split(START)
    _, after = rest.split(END)
    return before + START + '\n\n' + table(catalog, zh) + '\n\n' + END + after


def sync(output: Path, profile: bool = False, fetch=get_json) -> bool:
    projects = collect(fetch)  # Finish every request before replacing any existing data.
    previous = json.loads(output.read_text()) if output.exists() else {}
    catalog = previous if previous.get('projects') == projects and previous.get('schema') == 1 else {
        'schema': 1, 'updatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'projects': projects,
    }
    files = {output: json.dumps(catalog, ensure_ascii=False, indent=2) + '\n'}
    if profile:
        for name, zh in [('README.md', False), ('README.zh-CN.md', True)]:
            path = ROOT / name
            files[path] = render_readme(path.read_text(), catalog, zh)
    changed = False
    for path, content in files.items():
        if not path.exists() or path.read_text() != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + '.tmp')
            temporary.write_text(content, encoding='utf-8')
            temporary.replace(path)
            changed = True
    return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'projects.json')
    parser.add_argument('--profile', action='store_true', help='Also update only the marked README sections')
    args = parser.parse_args()
    print('Updated' if sync(args.output, args.profile) else 'No project changes')
