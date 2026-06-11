# VLLM Profiling on Radeon

## Overview

This project provides tooling to **profile vLLM workloads on consumer AMD Radeon GPUs**.
It orchestrates model runs inside Docker containers, isolates GPUs per run, and captures logs and profiling artifacts for analysis.

> ⚠️ **Status:** Early-stage
> ✅ **Platform:** Linux only (for now)

---

## Goals

* Enable reproducible profiling of vLLM workloads on Radeon GPUs
* Support multi-GPU systems with per-run isolation
* Preserve model downloads between runs
* Collect logs, traces, and performance data in a structured way

---

## Project Structure

### `.cache/huggingface/`

This directory is mounted into Docker containers as the Hugging Face cache.

Purpose:

* Preserve downloaded models between runs
* Avoid repeated downloads across container executions

### `.cache/vllm/` and `.cache/triton/`

These directories are mounted into Docker containers to persist vLLM and Triton compile caches.

Purpose:

* Reduce repeated `torch.compile` and CUDA graph capture time across runs
* Make Strix Halo profiling runs closer to steady-state behavior after the first cold start
* Improve repeatability when comparing baselines across models

---

### `.config/`

This directory contains **local, user-specific configuration files**.
It is expected to be customized per machine and **not shared verbatim across systems**.

#### `gpus.yaml`

Defines the GPUs available to the orchestrator and their associated settings.

Example:

```yaml
gpus:
  - name: Radeon RX 7900 XTX
    device: /dev/dri/renderD128
    env:
      GPU_MEM_UTIL: "0.9"

  - name: AMD Radeon RX 9070 XT
    device: /dev/dri/renderD129
    env:
      GPU_MEM_UTIL: "0.85"

  - name: AMD Radeon RX 6700 XT
    device: /dev/dri/renderD130
    disabled: true
```

Notes:

* Used by `orchestrator.py` to:

  * isolate GPUs per model run
  * pass GPU-specific environment variables to containers
* **GPU environment variables take precedence**, overriding model-specific env vars
* GPUs marked as `disabled: true` will be ignored

---

#### `tokens.yaml`

Provides token-based credentials to Docker containers.

Example:

```yaml
tokens:
  HF_TOKEN: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Notes:

* Currently only the Hugging Face token is supported
* Required only for certain models (e.g. the currently disabled `google/embeddinggemma`)

---

### `.logs/`

All logs, traces, and profiling outputs are written here.

Directory layout:

```
.logs/
  └── GPU_NAME/
      └── MODEL_NAME/
          └── <log_and_trace_files>
```

This structure allows easy comparison:

* across GPUs
* across models
* across multiple runs

---

### `images/`

Holds inference-time image data used by multimodal models.

Notes:

* Empty by default in the repository
* You may provide your own images
* Image filenames **must match** what the prompt YAML files expect (see `yaml/prompts/`)

TODO: rework the way images are handled (repo should provide default images via links)
---

### `scripts/`

Contains all project scripts, split into **host-side** and **container-side** logic.

#### Host-side scripts

Run directly on the host system:

* `orchestrator.py`
  The main entry point. Coordinates:

  * GPU selection
  * container execution
  * model runs
  * log collection

* `docker_tool.py`
  Docker-related utilities used by the orchestrator

* `generate_gpu_yaml.sh`
  Helper script to auto-generate a `gpus.yaml` template

  Usage:

  ```bash
  scripts/host/generate_gpu_yaml.sh
  ```

  This generates `.config/gpus.yaml` from the local `/dev/dri/renderD*` devices.

* Future host utilities will also live here

---

#### Container-side scripts

Executed **inside** Docker containers:

* `run_model.py`
  Entry point for all model runs:

  * sets up environment variables
  * launches the appropriate model runner
  * captures stdout/stderr and artifacts

* Model-specific runner scripts
  Tailored to individual models or groups of models

---

### `yaml/`

Contains configuration files that define **what to run and how to run it**.

#### `models.yaml`

Defines which models should be executed.

---

#### `env_vars.yaml`

Specifies environment variables to forward into model runners.

---

#### `prompts/`

Contains prompt definitions, grouped by model type.

Notes:

* Each model (or model family) has its own prompt YAML
* Prompts may optionally reference multimedia inputs (e.g. images)
* If a prompt references images, corresponding files must exist in the `images/` directory

---

## Notes & Limitations

* Linux-only support at this stage
* Some models may be temporarily disabled
* Image-based prompts require manual population of the `images/` directory

---

## Future Work

* Broader model coverage
* Improved automation and validation
* Expanded profiling support
* Potential non-Linux support

---

## Portability Notes

* Host scripts now resolve workspace paths from the repository root, so running commands from different working directories is supported.
* Use `disabled_on` in `yaml/models.yaml` to prevent known-problematic models on specific devices.

Example:

```yaml
models:
  - name: Qwen/Qwen3-VL-4B-Instruct
    type: multimodal
    script: qwen_vl.py
    disabled_on:
      - Strix Halo
```
