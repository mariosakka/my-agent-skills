---
name: seed-orders
description: Seed the database with mock test orders using the direct DB script
---

You help the user create mock test orders for local development by inserting them directly into the delivery database via Prisma.

**Run from:** the `server/` directory of the current checkout — `cd server` from the repo root (skip the `cd` if you're already in `server/`). Don't hardcode an absolute path; the script resolves `.env.local` relative to its own location, so the only requirement is that `scripts/seed-orders/seed-orders-db.ts` resolves from your cwd.
**Requires:** `.env.local` with a valid `DELIVERY_DATABASE_URL`

**Locker rendering note:** locker orders insert correctly regardless of network/config — the question is whether the orders list UI can resolve the locker name/icon via `ShippingPointsProxy` (a small backend client that talks to a shipping-points service to look up locker metadata by id).

The proxy's target host depends on the `USE_LOCAL_SHIPPING_POINTS` flag in `server/src/config/constants.ts`:
- `false` (default) → `10.10.0.190:3022` (the office-network address of the shared upstream shipping-points service; reachable only from the office Wi-Fi or VPN — same IP for every developer).
- `true` → `localhost:3022` (the developer's own `shipping_points_server.ts` sub-process, run manually in a second terminal).

Verified states:

- **On office LAN/VPN:** No setup needed.
- **Off-VPN, `USE_LOCAL_SHIPPING_POINTS = false`:** the entire orders list **fails to load** — proxy hangs trying to reach the unreachable upstream IP until the API request times out.
- **Off-VPN, `USE_LOCAL_SHIPPING_POINTS = true`, local sub-server NOT running:** list loads but locker rows show **"Err / Err"** (the connection to `localhost:3022` refuses fast because nothing is listening).
- **Off-VPN, `USE_LOCAL_SHIPPING_POINTS = true`, local sub-server running:** locker names render.

If the user is seeding locker orders off-VPN, mention they need **both** `USE_LOCAL_SHIPPING_POINTS = true` in `server/src/config/constants.ts` **and** `NODE_ENV=development npx tsx watch src/shipping_points_server.ts` running in a second terminal. See `server/scripts/seed-orders/README.md`.

The script handles the DB mechanics. **You** generate the address/recipient data fresh on each call and pipe it in via stdin — never use a file, never reuse the previous pool verbatim. Vary names, cities, countries between runs.

**Address tables written per order:**
Every order the script creates now writes the full contact address chain required by the mobile app:
- `addresses` (user_addresses) — sender reuses the shared row; recipient gets its own row
- `contact_persons` + `phone_numbers` + `phone_numbers_to_contact_persons`
- `contact_addresses` linking contact info → address row
- `contact_addresses_to_orders` (type 1 = sender, type 2 = recipient)

Without these, orders are invisible to the mobile app list (the formatter silently skips orders missing the chain).

**`--random` mode ignores `--email` entirely.** It assigns ~87% of orders to the main user (`maria@colete-online.ro`, resolved **by email** — `runRandom()` aborts if that user doesn't exist) and the remaining ~13% to a small pool of pre-created guest accounts (`guest-pool-*@guest.local`). The numeric id is whatever those rows happen to be locally, so don't assume a specific id. If you need every order owned by a specific user (e.g. for mobile testing), use non-random mode (`--from` / `--to` flags) with `--email user@example.com`. In random mode, use `--link-phone` instead to make orders reachable by phone number regardless of owner.

**Mobile visibility — `--link-phone <E.164>`** (e.g. `--link-phone +40200000000`):
Writes a `phone_number_to_order` entry (type 1 = sender) for every order created, linking it to the given phone number. This makes orders show up in the mobile app's "Expedieri" tab for the account registered with that phone, independent of which user account the orders belong to. The phone number is found-or-created in `phone_numbers`.
Use this whenever seeding orders that need to be visible on a test device:
```bash
echo '{...}' | npx tsx scripts/seed-orders/seed-orders-db.ts --random --count 50 --link-phone "+40200000000"
```

---

## Default: random mode (use this 95% of the time)

For "give me N varied test orders", compose a pool JSON inline and pipe it into the script via stdin. **Do not use the Write tool.** It's one Bash call:

```bash
cd server && \
echo '{
  "senders": [<3-5 RO senders>],
  "recipients": [<6-9 mixed RO + intl>],
  "lockerOperators": ["Sameday","DPD","GLS","Cargus"]
}' | npx tsx scripts/seed-orders/seed-orders-db.ts --random --count 20
```

The script picks a random sender + recipient per order. With `lockerOperators` present, ~35% of orders become locker orders (the real `shippingPointId` is stored; the backend resolves the name and icon at render time via the local shipping-points proxy — see prerequisites above).

### Pool composition guidance

- **3-5 senders**: mostly RO, with **exactly 1 international** sender (cross-border outbound is the rare case — keep it rare). RO senders use realistic Romanian names, phones `+407xx...`, cities (Bucharest, Cluj, Timișoara, Iași, Brașov, Constanța, Sibiu, Craiova, Oradea, Galați, etc.), county, postal code, street, number.
- **6-9 recipients**: mostly RO, with **exactly 1 international** mixed in. Vary which country each run — pick from `RO`, `DE`, `FR`, `IT`, `HU`, `GB`, `US`, `MD`, `CN`, `ES`, `NL`, `BE`, `AT`, `PL`, etc.
- **lockerOperators**: usually all four (`Sameday`, `DPD`, `GLS`, `Cargus`). Omit the field entirely if the user explicitly wants no lockers.

Each order picks one sender and one recipient independently, so the intl frequency seen in the order list ≈ (intl-senders / total-senders) for senders and (intl-recipients / total-recipients) for recipients. With 1 intl entry among 3-5 senders you get ~20-33% intl senders, and 1 intl among 6-9 recipients gives ~11-17% intl recipients — the right ballpark. Don't stack multiple intl entries on the same side unless the user explicitly asks for more.

If the user nudges the mix ("more international", "only RO", "no lockers"), adjust the pool composition you pipe in. The script's internal weights (guest 13%, status favoring delivered/picked_up, COD/insurance/plugin frequencies) stay fixed.

### Required and optional address fields

Required: `contactName`, `contactPhone`, `countryCode`, `city`, `street`, `number`
Optional: `contactPhone2`, `contactCompany`, `contactEmail`, `county`, `postalCode`, `block`, `stair`, `intercom`, `floor`, `apartment`, `landmark`, `additionalInfo`

Exception: when an address is paired with `--locker` or `--from-locker`, `city`, `street`, and `number` are not required — the locker location is auto-resolved (see the Sameday locker example at lines 99-101). Only `contactName`, `contactPhone`, and `countryCode` are needed on the locker side.

For a reference pool and CLI examples, see `server/scripts/seed-orders/README.md`. Generate fresh addresses every run — never reuse the examples verbatim.

---

## Specific overrides (when the user asks for something particular)

If the user constrains a dimension ("5 delivered DPD orders to a Sameday locker", "a Shopify order with COD 150"), use the flag-based single call (no pool, no random):

Common flags:
- `--count / -n N` — number of orders
- `--service / -s ID` — courier (IDs: `13` DPD, `17` Sameday, `70` GLS, `1800` FAN Courier, `15` Cargus, `110` DPD International, `1500` UPS)
- `--status` — `pending` | `picked_up` | `delivered` | `cancelled` | `returning` | `returned` | `with_problems`
- `--from <json>` / `--to <json>` — sender/recipient address JSON (single-quoted on CLI)
- `--locker <op>` — auto-resolve recipient locker by operator (`Sameday`, `DPD`, `GLS`, `Cargus`); pair with matching `--service`
- `--locker-city <city>` — narrow recipient locker to a specific city (substring match on `fullAddress`, e.g. `--locker-city Iasi`); combine with `--locker`
- `--from-locker <op>` — auto-resolve sender locker
- `--from-locker-city <city>` — narrow sender locker to a specific city
- `--email / -e` — user email (default: `maria@colete-online.ro`; **ignored in `--random` mode**)
- `--link-phone <E.164>` — write `phone_number_to_order` entry for this phone number on every order (makes orders visible on mobile for that account's "Expedieri" tab)
- `--guest` — guest order with random email (do not combine with `--email`)
- `--cod` / `--price` / `--account-repayment` / `--insurance` — RON amounts
- `--days-ago N` / `--date YYYY-MM-DD` / `--spread`
- `--awb VALUE` — custom AWB
- `--open-at-delivery` / `--swap` / `--saturday-delivery` / `--documents-return`
- `--test` / `--awaiting-cancellation` / `--watched`
- `--plugin shopify|woocommerce|prestashop|cel` / `--api` / `--file-import`
- `--list-services` / `--list-lockers` — discovery
- `--help / -h`

### Examples

```bash
# 5 delivered DPD orders, RO → RO
npx tsx scripts/seed-orders/seed-orders-db.ts --count 5 --service 13 --status delivered \
  --from '{"contactName":"Alexandru Neagoe","contactPhone":"+40722493333","countryCode":"RO","city":"București","county":"Ilfov","postalCode":"010011","street":"Calea Victoriei","number":"12"}' \
  --to '{"contactName":"Ion Popescu","contactPhone":"+40721000001","countryCode":"RO","city":"Cluj-Napoca","county":"Cluj","postalCode":"400001","street":"Strada Memorandumului","number":"5"}'

# Sameday locker delivery with COD
npx tsx scripts/seed-orders/seed-orders-db.ts --service 17 --status pending --locker Sameday --cod 150 \
  --from '{"contactName":"Alexandru Neagoe","contactPhone":"+40722493333","countryCode":"RO","city":"București","county":"Ilfov","postalCode":"010011","street":"Calea Victoriei","number":"12"}' \
  --to '{"contactName":"Ion Popescu","contactPhone":"+40721000001","countryCode":"RO"}'

# International to Germany
npx tsx scripts/seed-orders/seed-orders-db.ts --service 110 \
  --from '{"contactName":"Alexandru Neagoe","contactPhone":"+40722493333","countryCode":"RO","city":"București","county":"Ilfov","postalCode":"010011","street":"Calea Victoriei","number":"12"}' \
  --to '{"contactName":"Hans Müller","contactPhone":"+4915100000001","countryCode":"DE","city":"München","postalCode":"80331","street":"Marienplatz","number":"1"}'
```

---

## Multiple different specs in one run

When the user wants several *different* targeted combinations at once (e.g. "5 delivered DPD orders AND 3 pending Sameday locker orders with COD"), **chain `npx tsx ...` invocations with `&&` in a single Bash call** — one per spec. Do not write a JSON file and use `--batch`; the Write-tool approval and `/tmp` cleanup are worse than just chaining.

```bash
cd server && \
  npx tsx scripts/seed-orders/seed-orders-db.ts --count 5 --service 13 --status delivered \
    --from '{...}' --to '{...}' && \
  npx tsx scripts/seed-orders/seed-orders-db.ts --count 3 --service 17 --status pending --locker Sameday --cod 150 \
    --from '{...}' --to '{...}'
```

`--batch <file>` does exist as an escape hatch (the script accepts a JSON array of `BatchSpec` objects) — use it only if the user explicitly asks for a saved batch file, or if there are so many specs (~6+) that the chained line becomes unreadable.

---

## How to respond

1. **Before any tool calls**, output one short status line (e.g. `Seeding 20 random orders…`).
2. If the user wants "N orders" with no specifics → compose a fresh inline pool and pipe it into `--random --count N` in a single Bash call. Use `echo '...' | npx tsx ...` (or a heredoc for readability). **Never use the Write tool for the pool.**
3. If the user constrains dimensions → flag-based single Bash call with the specific overrides.
4. If the user wants multiple *different* targeted specs → chain `npx tsx ...` calls with `&&` in one Bash call. Reserve `--batch` for the explicit-batch-file case only.
5. Use service IDs, never names. Only run `--list-services` if the script errors with "service not found".
6. Never ask the user to run `--list-lockers` first — `--locker <op>` resolves automatically.
