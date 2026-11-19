# Automotive Marketing GTM Template

A reusable Google Tag Manager Web container for automotive dealership measurement. The container is named **Sophos Automotive Marketing GTM Container**. Tags, triggers and variables use neutral names.

**[Download the Automotive container](containers/automotive.json)** — open the file, then choose **Download raw file**. Save the `.json` file, not the GitHub page.

## What is included

| Destination | Included |
| --- | --- |
| Google Analytics 4 | 33 draft Automotive Standards Council (ASC) event mappings |
| Meta | Successful inquiry → `Lead`; phone-link click → `Contact` |
| Microsoft Advertising | UET page view, `successful_inquiry` and `phone_link_click` |

The export contains **38 tags, 39 triggers, 52 custom variables and 5 built-in variables**. All tags are paused. Destination IDs are placeholders, and the enable/readiness switches are off. No dealership account IDs, measurement IDs, Pixel IDs or website mappings are supplied.

This repository contains the Automotive template only.

## 1. Create your Tag Manager account

1. Sign in at [Google Tag Manager](https://tagmanager.google.com/).
2. Choose **Create Account**. Enter your business name and country.
3. Name the container for the dealership website and choose **Web**.
4. Choose **Create**, then review and accept Google's terms yourself.

Use a separate container for each dealership website. Keep access under the dealership's control and add the people who will manage it. [Google's account setup instructions](https://support.google.com/tagmanager/answer/14842164).

## 2. Import the template

1. Download [automotive.json](containers/automotive.json).
2. Open your target Web container. Go to **Admin → Import Container**.
3. Select the downloaded JSON file and create a workspace named **Automotive Measurement Setup**.
4. For a new, empty container, choose **Overwrite**.
5. Continue to the change preview. Review the tags, triggers and variables, then choose **Add to workspace** (or **Confirm**, depending on the UI) when the changes match your plan.

**For an existing working container:** export a backup first. Use a separate workspace and review **Merge**, including its same-name conflicts. Overwrite replaces the workspace's existing tags, triggers and variables. Importing does not install GTM on your website or publish your workspace. [Google's import/export instructions](https://support.google.com/tagmanager/answer/6106997?hl=en).

## 3. Add the dealership settings

Open **Variables** and configure only the destinations you plan to use.

| Variable | What to enter |
| --- | --- |
| `CONFIG - Allowed Hostname` | The exact website hostname you have verified, without `https://` or a path |
| `CONFIG - GA4 Measurement ID` | The dealership's GA4 Web stream measurement ID |
| `CONFIG - Enabled` | Keep `false` until the shared events and GA4 configuration are ready for testing |
| `LOOKUP - Dealer GA4 Measurement ID` | Optional hostname-to-measurement-ID lookup. Replace its empty placeholder row if you use it; keep the fallback unconfigured |
| `META - Pixel ID` | The intended dealership Pixel/Dataset ID |
| `META - Enabled` | Keep `false` until the Meta module is ready |
| `META - Consent Granted` | Replace the disabled placeholder with the actual consent state from your consent platform |
| `MICROSOFT - UET ID` | The dealership's Microsoft Advertising UET tag ID |
| `MICROSOFT - Enabled` | Keep `false` until the Microsoft module is ready |
| `MICROSOFT - Consent Ready` | A configuration-readiness flag; keep `false` until consent integration has been checked |

The GA4 tags use `CONFIG - GA4 Measurement ID`. The optional dealer lookup is not automatically substituted for that setting. Check each hostname variant you intend to support instead of opening the hostname gate to every website.

### GA4

Configure or verify the site's base Google tag for the same GA4 destination. This template supplies event tags, not a base Google tag. Review existing tracking so the same event is not sent twice.

### Meta

The two Meta event tags use an **existing, initialized Meta Pixel** through `window.fbq` and target the configured Pixel ID. They do not install the base Pixel or Conversions API. Verify the intended Pixel is initialized before enabling the event tags. If browser and server events both exist, review their deduplication separately.

### Microsoft Advertising

The Microsoft module includes the native UET base tag and two custom-event tags. All three use the same `marketing_uetq` queue. Configure conversion goals in Microsoft Advertising separately; importing this template does not create them. Automatic SPA tracking and enhanced conversions are off. Review page URL/query handling before activation; native query stripping is off.

## 4. Connect the website's events and consent

The shared triggers listen for normalized events named `measurement__asc_*`. Shared data-layer variables read fields under `measurement.parameters.*`. GA4 receives the corresponding standard `asc_*` event names.

**Importing this container does not create a website-provider adapter or establish ASC certification.** Verify how your provider emits ASC events, then map its event names and parameters to this contract or use independently verified provider-specific triggers. Dealer Inspire, Dealer.com, DealerOn and TeamVelocity can differ. The two included Dealer Inspire trigger examples are unattached and use invalid placeholder hostnames; they are not a complete adapter.

GA4 event tags require `analytics_storage`. Meta and Microsoft tags require `ad_storage`, `ad_user_data` and `ad_personalization`. Connect these states to the website's real consent platform and test default, accepted and revoked consent. Do not replace visitor consent with an unconditional `true` or a blanket grant. Microsoft's **Consent Ready** flag only describes setup readiness; it is not the visitor's permission.

The Microsoft page-view trigger runs on page load. When consent is granted later on the first page, verify that the UET base initializes before the first custom event. If consent blocked the base, add client-specific consent-update wiring that initializes it once before custom events. Changing a readiness flag or unpausing a tag does not replay an earlier page-load trigger.

## 5. Install, preview and test

1. Use **your target container's** installation instructions and snippets from GTM. Follow your website provider's installation process. If GTM is already installed, confirm the correct container before adding another copy. [Google's installation guide](https://support.google.com/tagmanager/answer/14847097).
2. Keep your changes in the unpublished workspace. Set the required enable flags and unpause only the ready tags you intend to test there.
3. Choose **Preview** and connect to the dealership website with Tag Assistant.
4. Perform the actual actions: navigation, inventory filtering, phone-link clicks and a permitted successful test inquiry. Confirm the event name, parameters, consent state and tag firing count.
5. Check destination receipt in GA4 DebugView, Meta Test Events or Microsoft UET Tag Helper, as applicable. A tag marked fired in GTM alone does not establish that the destination accepted it.
6. Confirm events are not duplicated by existing tags. For Microsoft, verify the base tag loads before custom events, including when consent changes during the page visit.
7. Publish a clearly named version only after the selected modules pass your checks.

A phone-link click is not a completed call. A form-start interaction is not a successful inquiry. Choose conversion goals using the verified underlying action, and avoid counting both native advertising conversions and imported GA4 equivalents for the same bidding goal.

## Optional: audit the downloaded template

With Python 3 installed, run this from the repository folder:

```sh
python3 scripts/audit_export.py
```

The read-only audit checks the original download's structure, paused state, placeholder settings, references and manifest hash. It makes no network requests. Once you configure your own IDs or change the export, its original-template hash check should fail; keep your configured customer export private.
