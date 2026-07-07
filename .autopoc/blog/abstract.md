# Blog Abstract: komi-learn on OpenShift

## Thesis
Deploying komi-learn, a continuous memory layer for AI coding agents, on OpenShift demonstrates that Python CLI tooling can be containerized and validated as Job workloads with minimal friction.

## Target Audience
Platform engineers and developer experience teams evaluating how to validate and test AI coding agent tooling in containerized CI/CD environments.

## Blog Type
Red Hat Developer Blog

## Key Points
1. Zero-dependency Python packages containerize cleanly on UBI9 with no platform-specific issues
2. OpenShift's Job workload pattern is ideal for validating CLI tools and libraries
3. The full komi-learn learning pipeline (distill, recall, curate, pool) runs correctly under OpenShift's security constraints

## Products/Projects
- Red Hat OpenShift AI
- Open Data Hub
- Red Hat UBI9

## CTA
Try containerizing your own AI coding agent tooling on OpenShift using UBI-based images and Job workloads.

## Proposed Section Outline
1. What is komi-learn?
2. Why containerize CLI tooling on OpenShift?
3. Building a UBI container for komi-learn
4. Running the learning pipeline as OpenShift Jobs
5. Test results and what we learned
6. Try it yourself
