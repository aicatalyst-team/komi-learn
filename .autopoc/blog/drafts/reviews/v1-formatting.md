# Formatting Review -- v1

## Scores
| Dimension | Raw (1-10) | Weight | Weighted |
|---|---|---|---|
| Heading hierarchy | 7 | 1x | 7 |
| Code formatting | 5 | 1x | 5 |
| CTA placement | 5 | 2x | 10 |
| SEO readiness | 7 | 1x | 7 |
| Link strategy | 5 | 1x | 5 |
| Editorial compliance | 6 | 2x | 12 |
| Brand standards | 7 | 1x | 7 |
| Word count | 8 | 1x | 8 |
| **Total** | | | **61 / 100 -> 6.1** |

## Line-Level Feedback
### Heading hierarchy
- **Location**: Title (line 1)
- **Issue**: Title uses title case: "Containerizing komi-learn: Testing AI Agent Memory on OpenShift". Should be sentence case per Red Hat editorial standards.
- **Current**: "## Containerizing komi-learn: Testing AI Agent Memory on OpenShift"
- **Suggested**: "## Containerizing komi-learn: testing AI agent memory on OpenShift"

### Code formatting
- **Location**: Throughout (lines 26, 30, 37, 39, 50-53, 79, 95, 99)
- **Issue**: Inline backticks used extensively: `chgrp -R 0`, `git`, `USER 1001`, `komi-learn`, `test_prepare_publish_pull_roundtrip`, etc. The rubric states no backticks in final output. These should be rendered as monospace through the publishing platform's formatting or rephrased to avoid inline code.
- **Suggested**: Remove backticks and use the publishing platform's monospace styling, or rephrase to minimize inline code references.

### CTA placement
- **Location**: Post structure
- **Issue**: CTA only appears at the end ("Try it yourself" section). The rubric requires CTA placement near the top, mid-post, and at the closing. There is no link to redhat.com or any Red Hat product page anywhere.
- **Suggested**: Add a brief mention near the top linking to OpenShift or Red Hat AI resources. Add a mid-post callout (e.g., after the Dockerfile section, link to UBI documentation on redhat.com). Keep the closing CTA but add a link to the OpenShift developer console or Red Hat Developer site.

### SEO readiness
- **Location**: Title
- **Issue**: Title is 63 characters, slightly over the 50-60 char target. Keywords "komi-learn" and "OpenShift" are present, which is good.
- **Suggested**: Shorten to "Containerizing komi-learn on OpenShift" (40 chars) or "Testing AI agent memory on OpenShift with komi-learn" (53 chars).

### Link strategy
- **Location**: Entire post
- **Issue**: All links point to GitHub. Zero links to redhat.com, Red Hat Developer, or official OpenShift documentation. This is a significant gap for a Red Hat Developer Blog post.
- **Suggested**: Add links to:
  - Red Hat UBI documentation: https://developers.redhat.com/products/rhel/ubi
  - OpenShift documentation on Jobs: https://docs.openshift.com/
  - Red Hat Developer landing page: https://developers.redhat.com/

### Editorial compliance
- **Location**: Line 3
- **Issue**: "UBI" acronym not expanded on first use. Should be "Red Hat Universal Base Image (UBI)" on first mention.
- **Current**: "package it with Red Hat UBI"
- **Suggested**: "package it with a Red Hat Universal Base Image (UBI)"

- **Location**: Line 3
- **Issue**: "CLI" not expanded on first use.
- **Current**: appears first in context without expansion
- **Suggested**: "command-line interface (CLI)" on first use, or spell out

- **Location**: Various
- **Issue**: Contractions could be used more aggressively per Red Hat style. "It runs entirely on" -> "It runs entirely on" is fine, but "This is a good pattern to know" -> "This is a good pattern to know" could be "Here's a good pattern to know".

## Editorial Compliance Checklist
- [ ] Sentence case headings -- FAIL (title is title case)
- [x] Oxford commas -- PASS (used correctly where needed)
- [ ] No backticks -- FAIL (extensive inline backtick usage)
- [ ] Full product name on first mention -- FAIL (UBI not expanded)
- [x] Lowercase component descriptors -- PASS
- [x] No H1 in body -- PASS
- [ ] Expand acronyms on first use -- FAIL (UBI, CLI not expanded)
- [ ] Use contractions aggressively -- PARTIAL
- [x] Numerals in running text -- PASS ("14 subcommands", "153 passed")
- [x] No em dashes -- PASS

## Summary
The most important formatting changes are: (1) add CTA links to redhat.com near the top and mid-post, not just at the end; (2) remove inline backticks throughout; (3) expand UBI and CLI acronyms on first use. The CTA placement and backtick issues are the primary blockers pulling the score down.
