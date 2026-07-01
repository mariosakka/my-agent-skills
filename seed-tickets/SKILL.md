---
name: seed-tickets
description: >-
  Seed the local delivery database with comprehensive mock support tickets for
  testing the ticketing feature. Use when the user asks to "seed tickets",
  "create mock tickets", "generate test tickets", "populate tickets", needs a
  ticket test environment, or wants tickets across all categories / statuses /
  priorities / attachment types. Inserts rows directly via Prisma (mirrors the
  seed-orders skill) and writes attachment + thumbnail files to the same storage
  root the server reads from. Local/dev only.
---

# seed-tickets — comprehensive mock support tickets

Inserts mock support **tickets** straight into the delivery DB via Prisma, so
the ticketing UI can be tested end-to-end without clicking through the create
flow. It reproduces the exact rows the real `CreateTicketUseCase` writes
(`TicketUser` → `Ticket` → `TicketMessage` → `TicketMessageFormValue` →
`content` / `attachments` / `thumbnails`), bypassing the attachment-draft
staging step and writing final rows directly.

**Run from:** the `server/` directory of the current checkout (`cd server`).
The script resolves `.env.local` relative to its own location, talks to the DB
through the generated **delivery** Prisma client, and writes attachment bytes to
the storage root `SambaFile` reads from. No HTTP server needs to be running.

**Requires:** `.env.local` with a valid local `DELIVERY_DATABASE_URL`. The
script **refuses to run** if that URL points at a non-local host (dev-only
guard).

## What it covers

A curated set of 12 scenarios spanning the full test matrix:

- **All 4 customer-creatable categories** — `OTHER_REASON`, `DAMAGED_PACKAGE`,
  `EXPEDITE_DELIVERY`, `EXPEDITE_PICKUP`. Each category's message-type bindings
  are resolved **dynamically from the DB**; the seeded category set itself is the
  curated four above (defined in `buildScenarios()`).
- **All statuses** — `NEW`, `OPEN`, `CLOSED`.
- **All priorities** — `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- **Every supported attachment MIME type** — jpeg, png, gif, webp (images, each
  with a generated 240px JPEG thumbnail), plus pdf, txt, doc, docx, xls, xlsx,
  zip. Includes tickets with multiple attachments.
- **Anonymous (email-only) vs authenticated** reporters.
- **Single-message tickets and multi-message threads** (customer ↔ admin
  replies, with the correct reply message types and `senderRole`).
- **Order/AWB-linked** tickets (EXPEDITE_*/DAMAGED link to a real order) and
  tickets with no order (OTHER_REASON).
- **Edge cases** — long bodies, special characters / diacritics / emoji in
  titles, and the per-category form-field (`formValues`) variants incl.
  DAMAGED_PARCEL_REPORT booleans + named attachment fields.

## Prerequisites

1. A local delivery DB must be running and migrated, and `.env.local` must point
   at it (`DELIVERY_DATABASE_URL=mysql://…@127.0.0.1:<port>/delivery_local`).
2. The ticket **categories / message types / form fields must be seeded** — they
   come from `npm run seed:delivery` (`src/prisma/delivery/seed.ts`). The script
   errors clearly if a category or its bindings are missing.
3. For EXPEDITE_*/DAMAGED tickets, at least one **order with an AWB** must exist
   (these link to a real order). If none exist, the script warns and skips those
   scenarios — run the `seed-orders` skill first to create some.

## Usage

```bash
cd server

# Seed the full curated set (default):
npx tsx scripts/seed-tickets/seed-tickets-db.ts

# Wipe previously seeded mock tickets, then seed fresh (idempotent re-run):
npx tsx scripts/seed-tickets/seed-tickets-db.ts --reset

# Remove everything this skill created (DB rows + attachment files) and stop:
npx tsx scripts/seed-tickets/seed-tickets-db.ts --clean
```

### Options

| Flag | Meaning |
|---|---|
| `-n, --count <N>` | Number of tickets (cycles through the curated set if N exceeds it). Default: the full set. |
| `-e, --email <email>` | Reporter email for "authenticated" tickets. **Log in as this user (or as an admin) to view them.** Default: `maria@colete-online.ro`. |
| `--admin-email <email>` | `TicketUser` email used as the admin reply sender. Default: `support@colete-online.ro`. |
| `--categories <list>` | Restrict to a comma list, e.g. `--categories OTHER_REASON,DAMAGED_PACKAGE`. Default: all. |
| `--clean` | Delete all previously seeded mock tickets (those tagged `seed:mock`) and their on-disk files, then exit. |
| `--reset` | `--clean`, then seed fresh. |
| `-h, --help` | Show help (also prints the resolved storage root). |

## How to respond

1. Before running, output one short status line (e.g. `Seeding mock tickets…`).
2. For a plain request → run the default full set with `--reset` (idempotent).
3. If the user names categories / a count / a reporter email → pass the matching
   flags.
4. After seeding, tell the user **which email to log in as** (the reporter, or
   an admin) — attachment serving is owner/admin-gated, so anonymous/guest
   tickets are only fully visible to an admin.

## How it works (for maintenance)

- **Idempotency / cleanup** — every seeded ticket is tagged `seed:mock`
  (`TicketTag`). `--clean`/`--reset` delete exactly those tickets (cascades to
  messages / form values / attachments / thumbnails) and remove the on-disk
  files written under `drafts/seed-mock/…`.
- **Attachment storage** — files are written to `<base>/drafts/seed-mock/<ticket
  uuid>/<uuid>/<filename>`, where `<base>` is `/media/sambaserver/` if mounted
  (`mount_check` starts with `mounted`), else `~/www/samba_fallback`. This
  matches `server/src/helpers/file_writer/samba_file.ts`, so the
  `GET /tickets/attachments/:identifier[/thumbnail]` endpoints serve them.
- **Thumbnails** — generated with the same `sharp` pipeline as
  `UploadAttachmentDraftUseCase` (resize 240px `inside`, JPEG q80), stored at
  `<filepath>.thumb.jpg` with a `TicketAttachmentThumbnail` row.
- **AWB fields** — for AWB-linked categories the script writes the `awb`
  `TicketMessageFormValue` (`{ awb, orderId }`), a `TicketMessageOrderRef`, and a
  `TicketOrdersLink` to a real order. (Direct Prisma inserts skip the use case's
  live-AWB validation, so the order just has to exist.)
- **Reply types** — admin replies use each category's `ADMIN_COMPOSE` message
  type; customer replies use the `TEXT` reply slot — both resolved from the DB
  bindings, not hardcoded.

## Verifying in an isolated worktree

To test without disturbing the current branch, use the `worktree-setup` skill to
create a worktree off `development`, then run the server + client and this
script. See `server/scripts/seed-tickets/README.md` for the exact step-by-step
commands.
