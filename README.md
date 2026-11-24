# ReviewLens: Serverless Data & AI Pipeline on Azure

> Work in progress. The full README (architecture diagram, skills table, results) is written in Phase 9.

A serverless data and AI pipeline on Azure that ingests Thai restaurant reviews daily, classifies them with an LLM, and serves analytics through a dashboard. Provisioned with Terraform and deployed through GitHub Actions.

## Dataset credit and license

Reviews come from the [Wongnai Reviews dataset](https://huggingface.co/datasets/Wongnai/wongnai_reviews) (`Wongnai/wongnai_reviews`), licensed under **LGPL-3.0**. This repository does not redistribute the dataset, apart from a 20-row sample in `sample-data/sample.jsonl` used by the tests. The project code is MIT licensed (see `LICENSE`).
