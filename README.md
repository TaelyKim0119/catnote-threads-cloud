# Catnote Threads cloud publisher

This is an unpublished, disabled-by-default prototype for @emilykim0503.
It prepares and publishes two daily pairs: one factual AI/IT news card and one
quoted question post at 09:00 and 18:00 Asia/Seoul. A retry is scheduled 17
minutes later because GitHub scheduled runs can be delayed or dropped.

## No-charge boundary

- Use only a **public** GitHub repository with standard `ubuntu-latest` Actions.
- Use a Google AI Studio key from a project visibly marked **Free Tier**, with
  **no linked billing account**. The only model in code is `gemini-3.6-flash`.
- Do not turn on Cloud Billing, larger runners, paid model tiers, packages,
  artifact uploads, Codespaces, or paid image generation.
- Repository variable `CATNOTE_LIVE_ENABLED` must equal `true` before any live
  posting occurs. It is absent by default. Missing credentials fail closed.

## Still required before activation

1. Verify the official-source finder and Korean drafts in a manual dry run.
2. Add the official Threads API use case to a Meta app and authorize only the
   @emilykim0503 account with publish/read permissions. Obtain a long-lived
   token via Meta's supported flow.
3. Store the Threads token, Free Tier Gemini key, and Fernet encryption key as
   repository Actions secrets. Never commit plaintext tokens.
4. Deploy to a new public repository with only the files in this directory.
5. Confirm that the public card URL loads, run one live test pair, and verify
   both Threads detail pages, including the quote attachment.
6. Set `CATNOTE_LIVE_ENABLED=true` and only then pause the old PC-bound task.

## Content policy

GeekNews RSS supplies leads but does **not** supply the vote-based Top ranking.
The job searches for a primary announcement, fetches the official page, and
requires verbatim evidence for a dated, concrete announcement. If it cannot
verify one, it skips the slot. It never promises that two suitable stories
exist every day. The illustration is composed locally from the user's cat
asset and a muted topic prop; no paid image API or text in the cartoon.

The public repository contains code, source URLs, post copy, and published
card PNGs. The only persistent Threads token is an encrypted file; its
encryption key stays in a GitHub Actions secret.
