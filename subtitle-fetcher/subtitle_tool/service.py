from __future__ import annotations

from pathlib import Path

from .env_check import CheckReport, run_checks
from .extractor import collect_subtitles
from .models import AuthOptions, RunResult
from .writer import write_outputs


class EnvironmentCheckError(RuntimeError):
    def __init__(self, report: CheckReport):
        super().__init__("环境检查未通过")
        self.report = report


def run_subtitle_job(
    source_url: str,
    output_dir: Path,
    languages: list[str],
    auth_options: AuthOptions | None = None,
) -> RunResult:
    report = run_checks(output_dir)
    if not report.ok:
        raise EnvironmentCheckError(report)

    result = collect_subtitles(source_url, output_dir, languages, auth_options)
    write_outputs(result)
    return result
