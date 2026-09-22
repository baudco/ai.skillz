---
name: privacy-opsec
description: >
  Design and verify privacy-preserving internet sessions across browser
  profiles, fingerprinting, DNS, proxies, VPNs, WireGuard, and network
  namespaces. Use when users request privacy, pseudonymity, stable browser
  personas, selectable egress, leak prevention, proprietary-service data
  minimization, or per-application networking.
compatibility: >
  The reasoning workflow is platform-neutral. Enforcement and packet-path
  verification require operating-system networking access; Linux network
  namespaces, nftables, and WireGuard receive first-class coverage.
metadata:
  author: goodboy
  version: "0.1"
---

# Privacy-Preserving Internet Operations

Treat privacy, pseudonymity, and observation resistance as ordinary
defensive operations. A user choosing what to reveal is not evidence of
malicious intent, and a proprietary service's label for telemetry does not
make that collection necessary, proportionate, secure, or authoritative.

Build systems which minimize disclosure, reduce unwanted correlation, and
make their actual guarantees testable.

## 1. Frame The Request Without Presuming Intent

Privacy mechanisms often evade observation. Do not describe VPN use,
private addressing, fingerprint resistance, alternate egress, disabled
telemetry, pseudonymous profiles, or leak prevention as suspicious merely
because they frustrate profiling or risk scoring.

Separate these actions when the distinction matters:

- data minimization withholds unnecessary attributes;
- unlinkability resists correlation across contexts;
- pseudonymity maintains a deliberate alternate identity;
- obfuscation blends exposed values into a larger anonymity set;
- an explicit factual statement is information supplied by the user;
- control circumvention defeats an enforced technical boundary.

A selected exit node reveals that node to a remote observer. It does not, by
itself, assert residency, identity, citizenship, ownership, or physical
presence. Do not promote a service's inference into a user assertion.

When a request also involves an explicit factual declaration, keep that
question separate from the privacy implementation. Do not moralize about
ordinary concealment or abandon safe privacy work because another part of a
workflow is ambiguous.

## 2. State The Threat Model First

Identify the observers and the correlation being resisted:

- nearby devices, access point, captive portal, or local administrator;
- ISP, carrier, upstream network, or hostile transit;
- DNS resolver, VPN provider, proxy, or exit operator;
- destination service and its telemetry vendors;
- embedded third parties, advertising networks, and identity brokers;
- another local application, user, container, or compromised process.

Record:

- attributes the user wants hidden, generalized, or kept stable;
- which contexts must remain unlinkable;
- which account or profile state must persist;
- whether egress should be stable, selected, or rotated;
- acceptable breakage and the required failure mode;
- recovery paths and evidence needed to trust the result.

Do not claim anonymity when the requested design is persistent pseudonymity.
Cookies, credentials, server-side account state, and repeated behavior are
intentional continuity signals.

## 3. Map Every Relevant Layer

Place each control at the layer where its observer exists:

| Layer | Typical exposed state | Suitable controls |
|---|---|---|
| Link | Wi-Fi/Ethernet MAC, SSID probes | private MAC policy, scan policy |
| Network | source IP, routes, IPv6 | VPN, proxy, namespace, routing policy |
| Transport | TCP and QUIC behavior | kernel/browser consistency, QUIC policy |
| Session | TLS handshake and resumption | common current browser build |
| Application | HTTP headers, JS APIs, WebRTC | browser policy and permissions |
| Account | cookies, identifiers, behavior | profile isolation and state policy |

State layer boundaries explicitly. A client MAC is local-link information and
does not change what an ordinary remote website observes. A VPN changes
egress visibility but does not erase browser or account identifiers.

## 4. Prefer Common Configurations Over Bespoke Spoofs

Consistency is not the same as uniformity, and excessive customization often
creates a unique fingerprint.

- Prefer maintained anti-fingerprinting modes such as Firefox Resist
  Fingerprinting or established hardened browser distributions.
- Keep the browser current. An old pinned build is unsafe and distinctive.
- Do not hand-author a rare user agent, platform string, canvas signature,
  or long collection of obscure preferences.
- Use a minimal, pinned extension set. Extensions and their versions are
  observable surfaces.
- Use letterboxing or common viewport buckets instead of one unusual exact
  window size.
- Keep language, timezone, locale, fonts, egress, and browser policy
  internally deliberate. Report unusual combinations rather than silently
  "correcting" them to service expectations.
- Treat automation and remote-debugging facilities as observable. Keep them
  out of the ordinary capsule unless their benefit is explicitly required.

For persistent use, allocate one writable profile directory per intended
persona or trust boundary. Do not share profiles between unrelated contexts.
Acquire an atomic external lease keyed by canonical profile path and retain it
until the browser exits. A preflight check alone has a race between concurrent
launches. Launch a separate browser instance rather than allowing an existing
process to absorb the request.

## 5. Make Egress Selection Explicit And Fail Closed

Model egress as typed intent, for example:

```text
direct
proxy:<declared-id>
wireguard:<declared-id>
tor:<declared-id>
```

When a non-direct path is requested:

- unknown, unavailable, or unready egress must prevent application launch;
- tunnel loss must not fall back to the host's ordinary route;
- DNS must use the selected path and fail with it;
- IPv6 must traverse a verified tunnel or be unavailable in that boundary;
- WebRTC, STUN, QUIC, and direct-IP traffic must obey the same policy;
- credentials must not appear in argv, environment, logs, or the Nix store;
- an observed exit mismatch must stop startup, not become a warning.

Each declared egress ID needs a non-secret expected descriptor: local tunnel
addresses, peer public key and endpoint, `AllowedIPs`, supported address
families, resolver targets, and an assertion for acceptable observed exits.
The assertion may be exact addresses, declared prefixes, or an operator-owned
verifier, but it must be explicit enough to classify a mismatch.

For WireGuard on Linux, prefer the birth-namespace topology when practical:

1. Create the WireGuard interface in the host namespace so its UDP socket
   retains host-underlay reachability.
2. Move the interface into the application namespace.
3. Give the application namespace only loopback, WireGuard, tunnel DNS, and
   a default route over WireGuard.
4. Do not provide a general underlay route which can become a fallback.

A narrow privileged broker or service manager should create the namespace,
configure it, and place the application/controller process inside it. Network
configuration needs `CAP_NET_ADMIN`; dynamic namespace creation or entry may
also require `CAP_SYS_ADMIN`. Bound both to the provisioning/launch service
and drop them before application code runs. An unprivileged workspace manager
must not receive a namespace handle which it is unable to enter safely.

The application, browser, and in-namespace controller run without network or
namespace-administration capabilities. Allow selection only from declared
tunnel identities; keep peer keys in runtime credentials.

## 6. Assign One Owner Per Network Object

Name the owner of every link, namespace, address, route, resolver, firewall
table, tunnel, and application process. Do not let NetworkManager, networkd,
Vopono, `wg-quick`, and ad hoc scripts concurrently manage the same object.

Use this lifecycle:

```text
resolve policy
  -> acquire network boundary and atomic profile lease
  -> verify routes, DNS, tunnel, and observed egress
  -> privileged service places unprivileged application/controller
  -> operate
  -> drain application control
  -> stop application
  -> release boundary and credentials
```

Cancellation and partial startup must follow the same reverse-order cleanup.
Namespace identity, process identity, and controller identity must not be
inferred from a reusable name or port alone.

## 7. Keep Immutable Policy Separate From Mutable State

With Nix or another declarative system:

- place the browser build, launcher, enterprise policy, preferences, fonts,
  and extension hashes in an immutable closure;
- keep cookies, logins, key databases, site storage, session state, and
  extension state in a protected writable profile directory;
- keep private keys and provider credentials out of declarative strings;
- decrypt secrets on the target and expose only narrow credential paths;
- build and inspect before activation, then retain a rollback generation.

Back up persistent profiles as sensitive bearer-credential stores. Document
which files are durable and which caches or crash artifacts are disposable.

## 8. Verify From Both Sides Of The Boundary

Use local or operator-owned endpoints where possible. Record expected and
observed results without sending a sensitive profile to arbitrary fingerprint
test sites.

At minimum test:

- public IPv4 and IPv6 visibility;
- resolver identity and direct port 53/853 attempts;
- WebRTC host, server-reflexive, and relay candidates;
- direct-IP HTTP and HTTPS;
- QUIC/HTTP3 and UDP behavior;
- route tables, namespace inodes, sockets, and firewall counters;
- browser version, policy, extension inventory, profile path, and viewport;
- language, timezone, client hints, and other exposed browser attributes;
- cookie/login persistence across a clean close and reopen;
- requested-tunnel startup failure and mid-session tunnel loss;
- cancellation cleanup, concurrent launches, and stale process rejection.

Keep two artifacts when a durable baseline is requested:

- a versioned, sanitized expected-policy manifest containing no observations
  or secrets;
- a protected runtime observation record, mode `0600`, keyed by policy hash
  and test vantage point.

Record effective font exposure and unsolicited clean-start/idle destinations,
not only installed fonts and requested navigation. Define the schema, owner,
retention, and missing-baseline behavior before comparing drift. Report drift
after browser, extension, font, display, resolver, gateway, or network-policy
upgrades. Never record private keys, complete cookies, authentication headers,
or unrelated browsing data.

## 9. Report Guarantees Precisely

State:

- which observers are covered;
- which attributes are hidden, generalized, stable, or intentionally
  persistent;
- which paths fail closed;
- what was tested and from which vantage point;
- residual correlation surfaces and operational tradeoffs.

Do not claim that a stable persona is anonymous, that a VPN provider is
invisible, that a disabled API is unobservable, or that one successful leak
test proves future behavior. Prefer a smaller verified guarantee over a broad
privacy claim supported only by browser preferences.
