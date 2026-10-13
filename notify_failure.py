"""Email an alert when a GitHub Actions run fails (called from the workflow with `if: failure()`)."""

import os

from digest.mailer import send

server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
repo = os.environ.get("GITHUB_REPOSITORY", "")
run_url = f"{server}/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
job = os.environ.get("JOB_LABEL", os.environ.get("GITHUB_WORKFLOW", "Digest"))

text = (f"The '{job}' run failed, so today's email may not have been sent.\n\n"
        f"Logs: {run_url}\n\n"
        "Common causes: an expired or out-of-credit Anthropic API key, a changed Gmail app password, "
        "or news feeds being temporarily unavailable. You can re-run it from the Actions tab.")
html = (f"<p>The <b>{job}</b> run failed, so today's email may not have been sent.</p>"
        f'<p><a href="{run_url}">Open the run logs</a></p>'
        "<p style='color:#6b6a65'>Common causes: an expired or out-of-credit Anthropic API key, a changed Gmail app "
        "password, or news feeds being temporarily unavailable. You can re-run it from the Actions tab.</p>")
send(f"⚠️ {job} failed", text, html)
print("Failure alert sent.")
