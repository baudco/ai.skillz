Evaluate FOSS + source-available license options for `ai.skillz`

Research and compare licensing strategies for the `ai.skillz`
repo, informed by the longstanding discussion at
[tractor#103](https://github.com/goodboy/tractor/issues/103).

## Core requirement

> any corp trying to use this project for profit pays
> back into it; if you're using it for free and sharing
> what you add then 100% it's acceptable.
> — goodboy, tractor#103

## Licenses evaluated

### Public domain dedications (rejected)

- **Unlicense**: public domain dedication + MIT fallback.
  OSI-approved but "poorly drafted" per OSI's own review.
  No patent grant. Google bans employee contributions.
  Zero reciprocity — directly contradicts the core
  requirement.
- **CC0 (Creative Commons Zero)**: better-drafted public
  domain dedication, internationally robust. No patent
  grant. FSF recommends against it for software. Same
  problem: no protection against commercial extraction.

### Source-available with time delay

- **BSL (Business Source License)**: MariaDB's creation,
  adopted by CockroachDB (2019). Source available but
  commercial use restricted; auto-converts to Apache 2.0
  after 3-4 years. Fill-in-the-blank "Additional Use
  Grant" means every BSL is effectively a different
  license. CockroachDB eventually went fully proprietary
  (2024) — cautionary outcome. **Not OSI-approved.**
- **FSL (Functional Source License)**: Sentry's evolution
  of BSL (Nov 2023). Opinionated defaults: 2-year
  conversion (half BSL), converts to Apache 2.0 or MIT.
  No fill-in-the-blank ambiguity. Restriction: can't run
  as competing hosted service. "Competing service" maps
  awkwardly to skill definitions — ambiguous what counts.
  **Not OSI-approved.**

### Revenue-threshold approach

- **Big Time Public License 2.0**: Kyle Mitchell's
  FRAND-ly license. Free for noncommercial + small
  business (<$1M revenue, <20 employees, <$1M
  investment/5yr). Big companies get free trial +
  guarantee of fair paid license terms. Closest
  philosophical match to the tractor#103 position.
  **Not OSI-approved.** Very novel, untested in courts,
  minimal adoption footprint.

### Copyleft (OSI-approved)

- **AGPL-3.0**: strongest OSI-approved copyleft. Network
  use clause triggers copyleft obligation — if someone
  deploys an AI agent service using these skills, they
  must release modifications. Well-understood,
  battle-tested. Some corps blanket-ban AGPL deps.
  Whether markdown prompt files constitute "source code"
  under AGPL is genuinely untested territory.
- **MPL-2.0**: file-level copyleft (weaker). Modifications
  to original files must be shared; surrounding code can
  be proprietary. More corporate-friendly but weaker
  protection — someone can build a proprietary skill
  suite around yours and only share back changes to
  your files.

### Other references

- **Darklang**: was custom restrictive license, now
  Apache 2.0. Their conclusion ("licensing wasn't the
  bottleneck, product quality was") is valid for hosted
  platforms but less applicable to skill definitions
  where content itself is the product.
- **@ryanhiebert's MIT argument** (tractor#103): maximum
  adoption, minimum friction. Counter: the "free lunch"
  problem — no mechanism to ensure compensation from
  profitable commercial use.

## Ranking vs requirements

| License         | Matches philosophy | FOSS | Adoption | Tested |
|-----------------|--------------------|------|----------|--------|
| Big Time 2.0    | best               | no   | high     | no     |
| AGPL-3.0        | good               | yes  | medium   | yes    |
| FSL             | good               | no   | medium   | some   |
| BSL             | ok                 | no   | medium   | yes    |
| MPL-2.0         | partial            | yes  | low      | yes    |
| CC0/Unlicense   | opposite           | ~yes | none     | yes    |

## Recommendation

**Pragmatic path**: AGPL-3.0 now with an explicit note
that dual commercial licensing is available via `baudco`
for corps that can't comply with copyleft. This gives
FOSS credibility, copyleft protection, and a revenue
path without betting on an untested license.

**Philosophical best-fit**: Big Time Public License 2.0
if willing to go source-available (not OSI FOSS). It
literally encodes the revenue-threshold boundary from
tractor#103 and the FRAND guarantee addresses corporate
"can I buy a license?" concerns.

## Decision

Pending org review.

## Sources

- https://bigtimelicense.com/versions/2.0.1
- https://writing.kemitchell.com/series/big-time-license.html
- https://blog.sentry.io/introducing-the-functional-source-license-freedom-without-free-riding/
- https://www.cockroachlabs.com/blog/oss-relicensing-cockroachdb/
- https://blog.darklang.com/darklang-goes-open-source/
- https://github.com/goodboy/tractor/issues/103
- https://chrismorgan.info/blog/unlicense/
- https://creativecommons.org/public-domain/cc0/
- https://choosealicense.com/licenses/cc0-1.0/

(this patch was generated in some part by [`claude-code`][claude-code-gh])
[claude-code-gh]: https://github.com/anthropics/claude-code
