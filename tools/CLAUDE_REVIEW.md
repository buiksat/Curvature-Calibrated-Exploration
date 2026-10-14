# Automated Claude Fable research review

This workflow sends the TMLR manuscript and requested research-source excerpts
to Anthropic, then saves the written review outside the checkout. It uses the
Claude API and its separate usage billing; it does not inherit access from a
Claude chat subscription or open browser session.

One-time requirement: configure `ANTHROPIC_API_KEY` securely in the execution
environment and allow HTTPS to `api.anthropic.com`. Do not put the key in the
repository, a command-line argument, or a chat message. For the Codex cloud
environment, the secret requirement and destination are saved in environment
settings; enter the value there, save, and publish the configuration.

From the repository root:

```bash
python3 tools/claude_review.py
```

The runner checks that the account exposes `claude-fable-5-1`, pins the local
`main` and `origin/cce-review-revisions` refs to exact commits, supplies the research
review prompt, handles read-only file-inspection calls, and saves the response
with its revision and usage manifest. It never silently substitutes a different
model. To select another model explicitly, use `--model` or `CLAUDE_MODEL`.

The snapshots use locally available Git refs. To review newer remote commits,
fetch the relevant branch first; fetching does not switch or reset the working
tree:

```bash
git fetch origin \
  main:refs/remotes/origin/main \
  cce-review-revisions:refs/remotes/origin/cce-review-revisions
python3 tools/claude_review.py \
  --manuscript-ref origin/main \
  --implementation-ref origin/cce-review-revisions
```

The explicit fetch destinations also create the required remote-tracking refs
in checkouts configured to fetch only `main`.

`cce-review-revisions` carries the implementation follow-up to the revised
manuscript. The earlier `cce-experiments` branch retains the historical study;
review it only when explicitly requested with
`--implementation-ref origin/cce-experiments`. A missing revision branch causes
an error rather than a fallback to historical code. The saved manifest records
the exact requested refs and resolved commits for either choice.

The workflow does not submit the paper or change either branch. Its
inspection tools cannot execute tests or experiments, and the prompt requires
the review to acknowledge that limitation.

Offline preparation and an access check without paid inference:

```bash
python3 tools/claude_review.py --prepare-only
python3 tools/claude_review.py --check-access
```

Use `--help` for output-directory and request-budget options. Calls are bounded
by a turn limit and a per-response token limit. An exhausted budget or truncated
answer is marked incomplete; it is not presented as a finished review. Paid
message requests are not automatically retried after uncertain network errors.

The source, prompt, and offline tests can be prepared without a key. An offline
pass does not establish API authentication, model access, billing availability,
or completion of a Claude review.

Run the offline runner tests without making API requests:

```bash
python3 -m unittest discover -s tools -p test_claude_review.py -v
```
