import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync', Path(__file__).parents[1] / 'scripts/sync_projects.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def repo(name, **kwargs):
    return dict(name=name, fork=False, archived=False, private=False,
                html_url='https://github.com/Studyer-Tang/' + name, description='Text | <tag>',
                language='Python', pushed_at='2026-10-01T00:00:00Z', **kwargs)


def fetch(path):
    if path.startswith('users/'):
        return [repo('academic-clipboard'), repo('new-tool'), repo('Studyer-Tang'), repo('Studyer-Tang.github.io')]
    return []


class SyncTests(unittest.TestCase):
    def test_new_projects_included_admin_repos_excluded(self):
        self.assertEqual([p['repo'] for p in sync.collect(fetch)], ['academic-clipboard', 'new-tool'])

    def test_private_archived_forks_excluded(self):
        items = [repo('a'), repo('b'), repo('c')]
        for item, flag in zip(items, ['private', 'fork', 'archived']):
            item[flag] = True
        self.assertEqual(sync.collect(lambda _: items), [])

    def test_release_uses_publication_time_and_labels_preview(self):
        def api(path):
            if path.startswith('users/'):
                return [repo('new-tool')]
            return [dict(id=1, tag_name='stable', html_url='https://github.com/stable', draft=False,
                         prerelease=False, published_at='2026-09-01'),
                    dict(id=2, tag_name='beta', html_url='https://github.com/beta', draft=False,
                         prerelease=True, published_at='2026-10-01'),
                    dict(id=3, draft=True, published_at='2026-11-01')]
        projects = sync.collect(api)
        self.assertEqual(projects[0]['release']['tag'], 'beta')
        rendered = sync.table({'projects': projects, 'updatedAt': '2026-10-01'}, False)
        self.assertIn('Preview', rendered)
        self.assertIn(r'Text \| &lt;tag&gt;', rendered)

    def test_pagination(self):
        calls = []
        def api(path):
            calls.append(path)
            return [1] * 100 if path.endswith('page=1') else [2]
        self.assertEqual(len(list(sync.pages('users/x/repos?type=owner', api))), 101)
        self.assertIn('&per_page=100&page=2', calls[-1])

    def test_no_churn_and_removed_projects_disappear(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.json'
            self.assertTrue(sync.sync(path, fetch=fetch))
            before = path.read_bytes()
            self.assertFalse(sync.sync(path, fetch=fetch))
            self.assertEqual(path.read_bytes(), before)
            self.assertTrue(sync.sync(path, fetch=lambda _: []))
            self.assertEqual(json.loads(path.read_text())['projects'], [])

    def test_api_failure_keeps_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'projects.json'
            sync.sync(path, fetch=fetch)
            before = path.read_bytes()
            def unavailable(_):
                raise OSError('rate limited')
            with self.assertRaises(OSError):
                sync.sync(path, fetch=unavailable)
            self.assertEqual(path.read_bytes(), before)

    def test_manual_content_preserved_and_markers_validated(self):
        data = {'projects': [], 'updatedAt': '2026-10-01'}
        original = 'Biography\n' + sync.START + '\nold\n' + sync.END + '\nReading'
        rendered = sync.render_readme(original, data, True)
        self.assertTrue(rendered.startswith('Biography\n'))
        self.assertTrue(rendered.endswith('\nReading'))
        for invalid in ['No markers', sync.END + sync.START, original + sync.START]:
            with self.assertRaises(ValueError):
                sync.render_readme(invalid, data, True)


if __name__ == '__main__':
    unittest.main()
