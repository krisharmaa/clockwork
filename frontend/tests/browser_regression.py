"""Exercise Clockwork in Chromium against a running Vite dev server and a disposable API database.

Run: python frontend/tests/browser_regression.py --web http://127.0.0.1:15174
Requires Python Playwright and system Chromium (or Playwright's installed Chromium).
The check publishes timetables, creates accounts and records leave/disruptions. Use a test database.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--web', default='http://127.0.0.1:5173')
    parser.add_argument('--artifacts', default='/tmp/clockwork-browser')
    args = parser.parse_args()
    artifacts = Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    passed: list[str] = []
    errors: list[str] = []

    def check(name: str) -> None:
        passed.append(name)
        print(f'[PASS] {name}', flush=True)

    with sync_playwright() as pw:
        executable = shutil.which('chromium') or shutil.which('google-chrome')
        browser = pw.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(15000)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept())

        def nav(name: str) -> None:
            page.get_by_role('link', name=name, exact=True).click()

        def store() -> dict:
            return page.evaluate("""async () => {
                const { useStore } = await import('/src/store.ts');
                const s = useStore.getState();
                return { instance: s.instance, solutions: s.solutions, stats: s.stats, runId: s.runId, view: s.view };
            }""")

        def login(username: str, password: str) -> None:
            page.goto(args.web)
            page.get_by_label('Username', exact=True).fill(username)
            page.get_by_label('Password', exact=True).fill(password)
            page.get_by_role('button', name='Sign in', exact=True).click()
            expect(page.locator('.shell')).to_be_visible()
            if page.locator('.inbox').count():
                page.get_by_role('button', name='Mark read', exact=True).click()

        def logout() -> None:
            page.locator('.account-btn').click()
            page.get_by_role('button', name='Log out', exact=True).click()
            expect(page.get_by_role('button', name='Sign in', exact=True)).to_be_visible()

        def run(advanced: bool = False, baseline: bool = True) -> None:
            if not page.locator('details.advanced').get_attribute('open'):
                page.locator('details.advanced summary').click()
            budget = page.get_by_label('Evaluation budget', exact=False)
            budget.focus()
            budget.press('Home')
            population = page.get_by_label('Population:', exact=False)
            population.focus()
            population.press('Home')
            page.get_by_label('Time cap (s)', exact=True).fill('0.5')
            page.get_by_label('Also run the repeated greedy baseline', exact=False).set_checked(baseline)
            page.get_by_label('Advanced benchmark: also run', exact=False).set_checked(advanced)
            page.get_by_role('button', name='Run optimiser', exact=False).click()
            expect(page.get_by_role('button', name='Optimising…', exact=False)).to_be_visible()
            expect(page.get_by_role('button', name='Run optimiser', exact=False)).to_be_enabled(timeout=180000)
            expect(page.locator('.run-controls .error-box')).to_have_count(0)
            expect(page.get_by_text('● Optimiser results', exact=True)).to_be_visible()

        try:
            login('admin', 'admin')
            run()
            normal = store()
            assert normal['stats']['verified'] and normal['stats']['baselineMethod']
            assert not normal['stats'].get('advancedBenchmark')
            chart = page.get_by_role('img', name=re.compile('^Measured convergence of'))
            chart.scroll_into_view_if_needed()
            bounds = chart.bounding_box()
            assert bounds
            page.mouse.move(bounds['x'] + bounds['width'] / 2, bounds['y'] + bounds['height'] / 2)
            expect(chart.get_by_text('Last sample at/before eval', exact=False)).to_be_visible()
            recorded = {f"{point['hypervolume']:.3f} @ {point['evaluations']}"
                        for points in normal['stats']['multiConvergence'].values() for point in points}
            shown = {text for text in chart.locator('text').all_text_contents() if re.fullmatch(r'\d+\.\d{3} @ \d+', text)}
            assert shown and shown <= recorded, (shown, recorded)
            check('administrator signs in and runs the optimiser with measured baseline')

            nav('Pareto front')
            comparison = page.get_by_role('table').filter(has=page.get_by_role('columnheader', name='Algorithm', exact=True))
            expect(comparison.get_by_text('Not run', exact=True)).to_have_count(3)
            expect(page.get_by_text('Recommended', exact=True)).to_be_visible(timeout=30000)
            page.get_by_role('button', name='Students first', exact=True).click()
            expect(page.get_by_text('Recommended', exact=True)).to_be_visible(timeout=30000)
            page.get_by_role('button', name='Derive weights by pairwise comparison (AHP)', exact=True).click()
            expect(page.get_by_text('AHP weights:', exact=False)).to_be_visible(timeout=30000)
            check('Pareto comparison marks omitted algorithms Not run; TOPSIS and AHP render')

            nav('Overview')
            run(advanced=True)
            advanced = store()
            rows = advanced['stats']['algorithmComparison']
            assert len(rows) == 5 and all(row.get('status') in ('ok', 'no_feasible', 'failed') for row in rows)
            nav('Pareto front')
            expect(comparison.get_by_text('Not run', exact=True)).to_have_count(0)
            row_names = {'memetic': 'Memetic NSGA-II', 'moead': 'MOEA/D', 'amosa': 'AMOSA', 'nsga2': 'Standard NSGA-II', 'greedy': 'Repeated greedy'}
            for row in rows:
                if row['hv'] is not None:
                    expect(comparison.get_by_role('row').filter(has_text=row_names[row['id']]).get_by_text(f"{row['hv']:.4f}", exact=True)).to_be_visible()
            check('advanced run displays all five measured algorithm rows')

            # Upload labels accepted by the backend that used to crash the poster and CSV export.
            nav('Overview')
            custom = json.loads(json.dumps(normal['instance']))
            custom['name'] = 'Browser imported period labels'
            custom['grid'].update(periods=[f'Period {i + 1}' for i in range(len(custom['grid']['periods']))], lunchPeriod=-1, lunchPeriods=[])
            page.locator('input[type=file]').set_input_files({'name': 'custom-periods.json', 'mimeType': 'application/json', 'buffer': json.dumps(custom).encode()})
            run(baseline=False)
            nav('Designer')
            expect(page.locator('.poster .tt-block').first).to_be_visible()
            expect(page.locator('.poster .tt-lunch')).to_have_count(0)
            page.get_by_role('button', name='📝 Content', exact=True).click()
            page.get_by_label('Title', exact=True).fill('Browser Export Schedule')
            page.get_by_role('button', name='Teacher', exact=True).click()
            expect(page.locator('.poster-view')).to_have_text(custom['faculty'][0]['name'])
            page.get_by_role('button', name='Class', exact=True).click()
            page.get_by_role('button', name='✨ Decorate', exact=True).click()
            page.get_by_role('button', name='🗒 Sticky note', exact=True).click()
            page.get_by_role('textbox', name='Text', exact=True).fill('Browser poster note')
            note = page.locator('.poster .deco').first
            note.scroll_into_view_if_needed()
            before = note.bounding_box()
            assert before
            page.mouse.move(before['x'] + before['width'] / 2, before['y'] + before['height'] / 2)
            page.mouse.down()
            page.mouse.move(before['x'] + before['width'] / 2 + 35, before['y'] + before['height'] / 2 + 20, steps=4)
            page.mouse.up()
            after = note.bounding_box()
            assert after and abs(after['x'] - before['x']) > 20
            page.locator('.poster .tt-block').first.click()
            page.get_by_label('Note (appears as a footnote)', exact=True).fill('Browser class annotation')
            expect(page.locator('.foot-notes')).to_contain_text('Browser class annotation')
            check('designer edits content, switches entities, drags a decoration and annotates a class')
            with page.expect_download() as download:
                page.get_by_role('button', name='⤓ CSV', exact=True).click()
            csv = artifacts / download.value.suggested_filename
            download.value.save_as(csv)
            assert csv.read_text().startswith('Day,Time,Code,Subject,Teacher,Room,Groups\n')
            assert 'Period ' in csv.read_text()
            with page.expect_download(timeout=60000) as download:
                page.get_by_role('button', name='Export PNG', exact=False).click()
            png = artifacts / download.value.suggested_filename
            download.value.save_as(png)
            assert png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
            check('custom non-clock period labels render and export CSV/PNG without phantom lunch')

            page.evaluate("""async () => {
                const { useStore } = await import('/src/store.ts');
                const s = useStore.getState();
                useStore.setState({ instance: { ...s.instance, grid: { ...s.instance.grid, lunchPeriods: [3, 4], lunchPeriod: 3 } } });
            }""")
            expect(page.locator('.poster .tt-lunch')).to_have_count(2)
            check('poster renders every configured lunch period')

            # Restore the independently checked run before publishing and exercising campus flows.
            page.evaluate("""async (run) => {
                const { useStore } = await import('/src/store.ts');
                useStore.setState({ instance: run.instance, solutions: run.solutions, stats: run.stats,
                    runId: run.runId, selectedId: run.solutions[0].id, view: { kind: 'group', entityId: run.instance.groups[0].id } });
            }""", normal)
            page.get_by_role('button', name='★ Publish', exact=True).click()
            expect(page.get_by_text('Published. Teachers and students now see this timetable.', exact=True)).to_be_visible()
            nav('Manage')
            accounts: dict[str, tuple[str, str]] = {}
            suffix = str(time.time_ns())[-9:]
            for role, key, entity in [('teacher', 'Teacher', normal['instance']['faculty'][0]['id']), ('student', 'Class', normal['instance']['groups'][0]['id'])]:
                username, password = f'browser-{role}-{suffix}', 'browser-test-password'
                page.get_by_label('Username', exact=True).fill(username)
                page.get_by_label('Initial password', exact=True).fill(password)
                page.get_by_role('combobox', name='Role', exact=True).select_option(role)
                page.get_by_label('Display name', exact=True).fill(f'Browser {role}')
                page.get_by_role('combobox', name=key, exact=True).select_option(entity)
                page.get_by_role('button', name='Create account', exact=True).click()
                expect(page.get_by_text(f'Account {username} created.', exact=True)).to_be_visible()
                accounts[role] = username, password
            check('administrator publishes and creates linked teacher/student accounts through forms')

            nav('Calendar')
            expect(page.locator('.occ').first).to_be_visible()
            page.locator('.occ').first.click()
            reason = page.get_by_label('Reason (optional)', exact=True)
            reason.fill('This text belongs only to the first lecture')
            page.locator('.occ').nth(1).click()
            expect(reason).to_have_value('')
            page.get_by_role('button', name='Close', exact=True).click()
            check('switching calendar lectures resets drawer form state')

            nav('Disruptions')
            page.get_by_role('combobox', name='What happened', exact=True).select_option('room_closed')
            assignment = normal['solutions'][0]['assignments'][0]
            page.get_by_role('combobox', name='Room', exact=True).select_option(assignment['roomId'])
            page.get_by_role('combobox', name='When (every week)', exact=True).select_option(str(assignment['day']))
            page.get_by_role('button', name='Check impact', exact=True).click()
            expect(page.get_by_text('Disruption recorded:', exact=False)).to_be_visible()
            page.get_by_role('button', name='Re-optimise with minimal changes', exact=False).first.click()
            expect(page.get_by_role('button', name='Publish this version', exact=False)).to_be_visible(timeout=180000)
            expect(page.get_by_role('img', name='Changes against quality', exact=True)).to_be_visible()
            check('reported room closure produces measured repair options and before/after preview')

            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.get_by_role('link', name='Calendar', exact=True)).to_be_visible()
            page.get_by_role('link', name='Calendar', exact=True).click()
            expect(page.get_by_role('heading', name='Calendar', exact=True)).to_be_visible()
            check('responsive icon navigation retains accessible link names')
            page.set_viewport_size({'width': 1440, 'height': 1000})
            logout()

            login(*accounts['student'])
            expect(page.get_by_role('link', name='Overview', exact=True)).to_have_count(0)
            expect(page.get_by_role('link', name='Manage', exact=True)).to_have_count(0)
            nav('Timetable')
            expect(page.locator('.poster-view')).to_have_text(normal['instance']['groups'][0]['name'])
            nav('Calendar')
            expect(page.locator('.occ').first).to_be_visible()
            page.locator('.occ').first.click()
            expect(page.get_by_text('Students can view the calendar;', exact=False)).to_be_visible()
            expect(page.get_by_role('button', name='Cancel this lecture', exact=True)).to_have_count(0)
            check('student sees linked timetable and read-only calendar with role navigation')
            logout()

            login(*accounts['teacher'])
            nav('My teaching')
            expect(page.get_by_role('button', name='Save availability', exact=True)).to_be_enabled()
            page.get_by_label('Note for the administrator', exact=True).fill('Browser regression availability')
            page.get_by_role('button', name='Save availability', exact=True).click()
            expect(page.get_by_text('Saved. The next optimiser run will respect it.', exact=True)).to_be_visible()
            semester = page.evaluate("async () => { const { api } = await import('/src/auth.ts'); return api('/semester'); }")
            dates = page.locator('input[type=date]')
            dates.nth(0).fill(semester['start'])
            dates.nth(1).fill(semester['start'])
            page.get_by_placeholder('Reason', exact=True).fill('Browser regression leave')
            page.get_by_role('button', name='Add leave', exact=True).click()
            expect(page.get_by_text('(Browser regression leave)', exact=True)).to_be_visible()
            page.get_by_role('button', name='Remove', exact=True).click()
            expect(page.get_by_text('(Browser regression leave)', exact=True)).to_have_count(0)
            nav('Requests')
            expect(page.get_by_role('heading', name='Requests', exact=True)).to_be_visible()
            check('teacher saves availability, adds/removes leave and opens requests')
            assert not errors, f'Uncaught browser errors: {errors}'
            check('all browser flows complete without uncaught JavaScript errors')
            page.screenshot(path=str(artifacts / 'final.png'), full_page=True)
        except Exception:
            page.screenshot(path=str(artifacts / 'failure.png'), full_page=True)
            (artifacts / 'failure.txt').write_text(page.locator('body').inner_text() + '\n\nJS errors:\n' + '\n'.join(errors))
            raise
        finally:
            (artifacts / 'results.json').write_text(json.dumps({'passed': passed, 'pageErrors': errors}, indent=2))
            browser.close()
    print(f'{len(passed)} browser checks passed; artifacts: {artifacts}', flush=True)


if __name__ == '__main__':
    main()
