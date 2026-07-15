# SPDX-License-Identifier: AGPL-3.0-or-later
# © 2026 Harald Weiss
from pathlib import Path


def test_job_pipeline_cron_requests_send_a_valid_token_header():
    crontab = Path("deploy/container/crontab").read_text()

    cron_curl_lines = [line for line in crontab.splitlines() if "/usr/bin/curl" in line]

    assert cron_curl_lines
    assert all('X-Cron-Token: ${JOB_CRON_TOKEN}' in line for line in cron_curl_lines)
