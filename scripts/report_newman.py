from pathlib import Path
import json, html, sys, shutil

ROOT = Path(__file__).resolve().parent.parent
raw = json.loads(Path(sys.argv[1]).read_text())
run = raw["run"]
stats = run["stats"]
steps = []
for x in run["executions"]:
    tests = [
        {"name": a["assertion"], "passed": not bool(a.get("error"))}
        for a in x.get("assertions", [])
    ]
    steps.append(
        {
            "name": x["item"]["name"],
            "method": x["request"]["method"],
            "status": x["response"]["code"],
            "duration_ms": x["response"]["responseTime"],
            "tests": tests,
        }
    )
result = {
    "tool": "Newman",
    "source": "Postman collection v2.1",
    "base_url": sys.argv[2],
    "stats": {k: stats[k] for k in ["requests", "assertions"]},
    "steps": steps,
    "failures": len(run["failures"]),
}
assert not result["failures"]
(ROOT / "docs/newman-summary.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2)
)
style = "body{background:#f3f4f0;color:#243d33;font:16px system-ui;max-width:1000px;margin:45px auto;padding:0 24px}h1{font-size:38px}section{display:flex;gap:25px;margin:28px 0}.stat{background:white;border:1px solid #d9e3d9;border-radius:12px;padding:20px 35px}.stat b{display:block;font-size:36px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #e2e8df}th{background:#e1eadf}.ok{color:#256343}.muted{color:#68766a}"
rows = "".join(
    "<tr><td>"
    + html.escape(x["name"])
    + "</td><td>"
    + x["method"]
    + "</td><td>"
    + str(x["status"])
    + '</td><td class="ok">'
    + str(sum(t["passed"] for t in x["tests"]))
    + "/"
    + str(len(x["tests"]))
    + "</td></tr>"
    for x in steps
)
doc = (
    '<!doctype html><html lang="ru"><meta charset="utf-8"><title>Котосмена — проверка коллекции Postman</title><style>'
    + style
    + '</style><h1>Проверка коллекции Postman</h1><p class="muted">Исполнитель — Newman. Отчёт сформирован по результату реального прогона коллекции.<br>Сервер: '
    + html.escape(sys.argv[2])
    + '</p><section><div class="stat"><b>'
    + str(stats["requests"]["total"])
    + '</b>запроса</div><div class="stat"><b>'
    + str(stats["assertions"]["total"])
    + '</b>проверки</div><div class="stat"><b>0</b>ошибок</div></section><table><thead><tr><th>Шаг</th><th>Метод</th><th>HTTP</th><th>Пройдено</th></tr></thead><tbody>'
    + rows
    + "</tbody></table><p>Тела запросов, пароли и токены в этот отчёт не включены.</p></html>"
)
(ROOT / "docs/newman-report.html").write_text(doc)
(ROOT / "backend/web/static/web/newman-report.html").write_text(doc)
print(
    "Newman:",
    stats["requests"]["total"],
    "requests;",
    stats["assertions"]["total"],
    "assertions; 0 failures",
)
