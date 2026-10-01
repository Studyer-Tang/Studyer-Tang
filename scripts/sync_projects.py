"""Fetch public GitHub facts once; render static website data and profile tables.

Python standard library only. A failed request aborts before any file is changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
    'academic-clipboard': ('Academic Clipboard', 'Academic Clipboard', '科研摘录', 'Research snippets'),
    'ThesisCraft': ('ThesisCraft · 学研排版', 'ThesisCraft', '论文写作', 'Academic writing'),
    'advanced-mathematical-statistics-notes': ('高等统计学笔记', 'Statistics Notes', '学习笔记', 'Study notes'),
    'paperstage-skill': ('PaperStage', 'PaperStage', '学术演示', 'Presentations'),
}


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
        labels = FEATURED.get(name, (name, name, '开源项目', 'Open source'))
        releases = [r for r in pages(f'repos/{OWNER}/{name}/releases', fetch)
                    if not r['draft'] and r.get('published_at')]
        latest = max(releases, key=lambda r: (r['published_at'], r['id']), default=None)
        projects.append({
            'repo': name, 'name': list(labels[:2]), 'label': list(labels[2:]),
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
            status = ('预览版' if zh else 'Preview') if release['prerelease'] else ('正式版' if zh else 'Stable')
            version = f"[{markdown(release['tag'])}]({release['url']}) · {status}"
        description = markdown(p['description']) or ('见仓库说明' if zh else 'See repository')
        lines.append(f"| **[{markdown(p['name'][0 if zh else 1])}]({p['url']})** | {description} | {version} |")
    if not catalog['projects']:
        lines.append('| — | 暂无公开项目 / No public projects | — |')
    date = catalog['updatedAt'][:10]
    lines.extend(['', (f'项目数据更新于 {date} · 每 6 小时自动核对公开仓库、简介与发布版本。'
                       if zh else f'Project data updated {date} · Public repositories, descriptions and releases checked every 6 hours.'),
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
