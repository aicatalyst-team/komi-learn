# Image Review -- v1

## Scores
| Dimension | Raw (1-10) | Weight | Weighted |
|---|---|---|---|
| Placement rationale | 6 | 2x | 12 |
| Prompt specificity | 5 | 2x | 10 |
| Brand compliance | 9 | 2x | 18 |
| Aspect ratio & sizing | 8 | 1x | 8 |
| Alt text quality | 5 | 1x | 5 |
| Image count | 5 | 1x | 5 |
| **Total** | | | **58 / 90 -> 6.4** |

## Per-Image Feedback

### Mermaid diagram: komi-learn learning loop (lines 16-24)
- **Placement**: After the numbered list explaining the core loop. Good placement -- diagram reinforces the textual description.
- **Diagram clarity**: Clear and readable. Linear flow from Session Start through Recall, Distill, Curate to Community Pool. Appropriate use of `graph LR`.
- **Diagram type**: Flowchart is the right choice for a linear pipeline.
- **Brand theming**: `%%{init}%%` block present with correct Red Hat brand variables: `primaryColor: '#EE0000'`, `primaryBorderColor: '#A30000'`, `secondaryColor: '#F0F0F0'`, `tertiaryColor: '#0066CC'`. Compliant.
- **Alt text**: No alt text or caption provided for the Mermaid diagram. Should include a descriptive caption for accessibility (e.g., "Diagram: komi-learn's four-phase learning loop from session recall through community sharing").

## Missing Image Opportunities

### 1. Hero image
- **Location**: Before or after the title
- **Rationale**: A hero image is standard for Red Hat Developer Blog posts. Should show the concept visually (e.g., a container with AI/memory iconography on an OpenShift grid).
- **Suggested prompt**: "Flat illustration, 16:9 aspect ratio, showing a shipping container labeled with a brain icon being placed onto a Red Hat OpenShift cluster grid. Use Red Hat brand colors: primary red #EE0000, dark background #151515, light accents #F0F0F0. Minimalist developer blog style, no text overlay."

### 2. Deployment architecture diagram
- **Location**: "Deploying as OpenShift Jobs" section, before or after the YAML
- **Rationale**: A Mermaid diagram showing the 3 Jobs (CLI help, demo loop, test suite) running in the OpenShift namespace would clarify the deployment topology.
- **Suggested Mermaid**:
```
graph TD
  subgraph OpenShift Namespace
    J1[Job: CLI Help] --> P1[Pod: komi-learn --help]
    J2[Job: Demo Loop] --> P2[Pod: python demo_loop.py]
    J3[Job: Test Suite] --> P3[Pod: pytest]
  end
```

### 3. Test results visualization
- **Location**: "Test results" section, alongside the table
- **Rationale**: A simple bar chart or pass/fail visual would make the results more scannable, though the table already does a reasonable job. Lower priority.

## Summary
The most important image change is adding at least 1-2 more visuals: a deployment architecture Mermaid diagram in the "Deploying as OpenShift Jobs" section and a hero image placeholder. The existing Mermaid diagram is well-executed with proper brand theming, but a single visual is insufficient for a developer blog post. Also add alt text/captions to all diagrams.
