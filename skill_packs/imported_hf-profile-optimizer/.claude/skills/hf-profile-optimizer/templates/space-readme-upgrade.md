# Space README Upgrade (template)

> Reusable output template for upgrading a Hugging Face Space README. Replace every [placeholder]. Never invent metrics or results: use "More Information Needed" or "[needs evidence]" where unknown.

```yaml
# YAML frontmatter placeholder for a Hugging Face Space.
# NOTE: verify the current Hugging Face Spaces configuration reference for the exact, up-to-date field names and allowed values before publishing.
title: [Space title]
emoji: [single emoji, e.g. 🤗]
colorFrom: [gradient start color, e.g. blue]
colorTo: [gradient end color, e.g. indigo]
sdk: [gradio | streamlit | docker | static]
sdk_version: [e.g. 4.44.0 - verify against current reference]
app_file: [entry file, e.g. app.py]
pinned: [true | false]
license: [SPDX identifier, e.g. apache-2.0]
```

## What the demo does
One-line guidance: state in one or two sentences what a visitor can do here and what problem it solves.
[Describe the demo in plain language.]

## Try it
One-line guidance: give the most direct path to a first successful interaction.
- Live demo: [link placeholder]

## Inputs / outputs
One-line guidance: list what the user provides and what they get back, with types.
- Inputs: [placeholder]
- Outputs: [placeholder]

## Example use cases
One-line guidance: give 2-3 concrete situations where this demo is useful.
- [Use case 1]
- [Use case 2]
- [Use case 3]

## Model / data dependencies
One-line guidance: name the model(s) and dataset(s) this Space relies on, with links.
- Model(s): [placeholder]
- Dataset(s): [placeholder]

## Hardware / runtime expectations
One-line guidance: state the expected hardware tier and typical response time so users know what to expect.
- Hardware: [placeholder, e.g. CPU basic / T4 small]
- Runtime: [placeholder or "More Information Needed"]

## Limitations
One-line guidance: be honest about failure modes, scope limits, and known issues.
- [Limitation 1]
- [Limitation 2 or "More Information Needed"]

## Local run
One-line guidance: give copy-paste commands to clone and run the Space locally.

```bash
# Clone the Space repository
git clone https://huggingface.co/spaces/[username]/[space-name]
cd [space-name]

# Install dependencies
pip install -r requirements.txt

# Run locally
python [app_file, e.g. app.py]
```

## License
One-line guidance: match the SPDX identifier declared in the frontmatter and link to the full text.
[SPDX identifier and link placeholder]

## Contact
One-line guidance: give one reliable way to reach the maintainer for questions or issues.
[Contact placeholder]
