"""Worker ichki vazifalari navbat vazifalari nomlarini to'smasligi kerak (barqarorlik sinovida topilgan xato)."""

from darsstudio.jobs import tasks, worker


def test_no_task_name_shadowing() -> None:
    assert not set(worker.TASKS) & set(tasks.TASKS)
    for name, (fn, _) in tasks.TASKS.items():
        assert worker.resolve(name) is getattr(tasks, fn)
