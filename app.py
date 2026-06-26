from flask import Flask, render_template, jsonify
import xml.etree.ElementTree as ET
from datetime import datetime
import os

import aim_data

app = Flask(__name__)

XML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'AI_трансформация_Банка_план_Actual_status_040626.xml')
NS = {'ms': 'http://schemas.microsoft.com/project'}
_cache = None


def _pdate(s):
    return s[:10] if s else None


def _status(pct, finish, today):
    if pct == 100:
        return 'done'
    if finish and finish < today and pct < 100:
        return 'overdue'
    if pct > 0:
        return 'active'
    return 'pending'


def _get(element, tag, ns):
    el = element.find(f'ms:{tag}', ns)
    return el.text if el is not None else None


def load():
    global _cache
    tree = ET.parse(XML_FILE)
    root = tree.getroot()

    resources = {}
    for r in root.findall('.//ms:Resources/ms:Resource', NS):
        uid = _get(r, 'UID', NS)
        name = _get(r, 'Name', NS)
        if uid and name:
            resources[uid] = name

    assign = {}
    for a in root.findall('.//ms:Assignments/ms:Assignment', NS):
        tuid = _get(a, 'TaskUID', NS)
        ruid = _get(a, 'ResourceUID', NS)
        if tuid and ruid and ruid in resources:
            assign.setdefault(tuid, [])
            rname = resources[ruid]
            if rname not in assign[tuid]:
                assign[tuid].append(rname)

    today = datetime.now().strftime('%Y-%m-%d')
    tasks = []
    total = done = active = pending = overdue = 0

    for t in root.findall('.//ms:Tasks/ms:Task', NS):
        uid = _get(t, 'UID', NS)
        if uid == '0':
            continue

        is_sum = _get(t, 'Summary', NS) == '1'
        pct = int(_get(t, 'PercentComplete', NS) or 0)
        fin = _pdate(_get(t, 'Finish', NS))
        st = _status(pct, fin, today)

        if not is_sum:
            total += 1
            if st == 'done':
                done += 1
            elif st == 'active':
                active += 1
            elif st == 'overdue':
                overdue += 1
            else:
                pending += 1

        in_pres = False
        text10 = ''
        for ea in t.findall('ms:ExtendedAttribute', NS):
            fid = _get(ea, 'FieldID', NS)
            val = _get(ea, 'Value', NS)
            if fid == '188743731':
                in_pres = val == '1'
            elif fid == '188743750':
                text10 = val or ''

        tasks.append({
            'uid': uid,
            'id': _get(t, 'ID', NS),
            'name': _get(t, 'Name', NS) or '',
            'wbs': _get(t, 'WBS', NS) or '',
            'level': int(_get(t, 'OutlineLevel', NS) or 0),
            'summary': is_sum,
            'milestone': _get(t, 'Milestone', NS) == '1',
            'critical': _get(t, 'Critical', NS) == '1',
            'start': _pdate(_get(t, 'Start', NS)),
            'finish': fin,
            'pct': pct,
            'resources': assign.get(uid, []),
            'status': st,
            'pres': in_pres,
            'text10': text10,
        })

    def _find_text(path):
        el = root.find(path, NS)
        return _pdate(el.text) if el is not None else None

    meta = {
        'name': 'AI Трансформация SQB',
        'start': _find_text('.//ms:StartDate'),
        'finish': _find_text('.//ms:FinishDate'),
        'saved': _find_text('.//ms:LastSaved'),
        'today': today,
    }

    good_res = sorted({v for v in resources.values()
                       if v and '\\' not in v and v not in ('SQB.', 'vf', 'F\\')})

    _cache = {
        'meta': meta,
        'tasks': tasks,
        'stats': {'total': total, 'done': done, 'active': active,
                  'pending': pending, 'overdue': overdue},
        'resources': good_res,
    }
    return _cache


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/data')
def api_data():
    global _cache
    if not _cache:
        load()
    return jsonify(_cache)


@app.route('/api/reload')
def api_reload():
    load()
    return jsonify({'ok': True, 'stats': _cache['stats']})


@app.route('/api/aim')
def api_aim():
    return jsonify(aim_data.build_aim())


if __name__ == '__main__':
    print('Загрузка данных...')
    load()
    print(f'Задач загружено: {_cache["stats"]["total"]}')
    print('Портал запущен: http://localhost:5000')
    app.run(port=5000, host='0.0.0.0', debug=False)
