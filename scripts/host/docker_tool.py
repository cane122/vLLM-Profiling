#!/usr/bin/env python3

"""

docker_tool.py is a script used to run provided docker images. In the future it might
also be used to build custom dockerfiles as well as run them in one command.

Current usage:

scripts/host/docker_tool.py --device /dev/dri/<folder_of_desired_device_to_mount>

While it can be used standalone, it's mostly used by orchestrator.py to run the entire config on all
available GPUs.

"""

# TODO: add logging to files of the docker run command

import argparse
import subprocess
import sys
from pathlib import Path
import os
import yaml

ROOT_DIR = Path(__file__).parent.parent.parent


def prepare_env():
    path_to_env_vars = ROOT_DIR / "yaml" / "env_vars.yaml"
    with open(path_to_env_vars, "r") as f:
        env_vars_to_propagate = yaml.safe_load(f)["env_vars"]
    docker_env = {
        env_var: os.getenv(env_var)
        for env_var in env_vars_to_propagate
        if os.getenv(env_var)
    }
    return docker_env


def run_container(args, script_args):
    env = prepare_env()
    hf_cache_dir = Path(args.hf_cache_dir)
    if not hf_cache_dir.is_absolute():
        hf_cache_dir = (ROOT_DIR / hf_cache_dir).resolve()

    # Dynamic User and Group IDs matching your host system user
    host_uid = os.getuid()
    host_gid = os.getgid()

    cmd = [
        "docker",
        "run",
        # Force the container to run as the host user, preventing root locks
        "--user", f"{host_uid}:{host_gid}",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        # first, unpack environment key-value pairs into a list of k=v strings
        # then unpack the kv pairs into lists of ["-e", kv]
        *[item for key, value in env.items() for item in ("-e", f"{key}={value}")],
        "--rm",
        "--pull=missing",
        "--ipc=host",
        "--network=host",
        "--group-add",
        "video",
        "--cap-add=SYS_PTRACE",
        "--security-opt",
        "seccomp=unconfined",
        "--device",
        "/dev/kfd",
        "-w",
        "/workspace",
    ]

    interactive = not args.script
    if interactive:
        cmd.append("-it")
    """
    TODO: remove or fix this, needed for parallelism probably
    else:
        cmd.append("-d")
    """

    # mount appropriate gpu
    cmd.extend(["--device", args.device])

    # set env var to remember device name
    cmd.extend(["-e", f"DEVICE_NAME={args.device_name}"])

    # mount dirs from host to container
    container_workspace = Path("/workspace")

    # Set up a generic home cache folder inside the container that our user can write to
    container_home_cache = "/tmp/.cache"

    # huggingface cache dir
    hf_cache_container = f"{container_home_cache}/huggingface"
    hf_cache_dir.mkdir(parents=True, exist_ok=True)
    cmd.extend(["-v", f"{hf_cache_dir}:{hf_cache_container}"])
    
    # Overwrite the HF environment variable so vLLM looks in our writable path
    cmd.extend(["-e", f"HF_HOME={hf_cache_container}"])
    print(f"Mounting HuggingFace cache: {hf_cache_dir} -> {hf_cache_container}")

    # vLLM and Triton compile caches
    cache_mounts = {
        f"{container_home_cache}/vllm": ROOT_DIR / ".cache" / "vllm",
        f"{container_home_cache}/triton": ROOT_DIR / ".cache" / "triton",
    }
    for container_cache_dir, host_cache_dir in cache_mounts.items():
        host_cache_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["-v", f"{host_cache_dir}:{container_cache_dir}"])
        print(f"Mounting cache: {host_cache_dir} -> {container_cache_dir}")

    # local container scripts dir
    scripts_container = str(container_workspace / "scripts")
    host_scripts_dir = ROOT_DIR / "scripts" / "container"
    cmd.extend(["-v", f"{host_scripts_dir}:{scripts_container}"])
    print(f"Mounting {host_scripts_dir} -> {scripts_container}")

    # local prompts dir
    prompts_container = str(container_workspace / "prompts")
    host_prompts_dir = ROOT_DIR / "prompts"
    cmd.extend(["-v", f"{host_prompts_dir}:{prompts_container}"])
    print(f"Mounting {host_prompts_dir} -> {prompts_container}")

    # logs dir
    logs_container = str(container_workspace / "logs")
    host_logs_dir = ROOT_DIR / ".logs"
    host_logs_dir.mkdir(parents=True, exist_ok=True)
    cmd.extend(["-v", f"{host_logs_dir}:{logs_container}"])
    print(f"Mounting {host_logs_dir} -> {logs_container}")

    # images dir
    images_container = str(container_workspace / "images")
    host_images_dir = ROOT_DIR / "images"
    cmd.extend(["-v", f"{host_images_dir}:{images_container}"])
    print(f"Mounting {host_images_dir} -> {images_container}")

    # yaml dir
    yaml_container = str(container_workspace / "yaml")
    host_yaml_dir = ROOT_DIR / "yaml"
    cmd.extend(["-v", f"{host_yaml_dir}:{yaml_container}"])
    print(f"Mounting {host_yaml_dir} -> {yaml_container}")

    shell_cmd = []

    shell_cmd.append(
        f"pip install --no-cache-dir -r {scripts_container}/requirements.txt"
    )

    if args.script:
        # removing prefix -- from remainder args
        script_args = script_args[1:]
        shell_cmd.append(
            "python3 /workspace/scripts/" + args.script + " " + " ".join(script_args)
        )
    else:
        shell_cmd.append("bash")

    cmd.extend(
        [
            args.image_name,
            "/bin/bash",
            "-c",
            " && ".join(shell_cmd),
        ]
    )

    print(f"Running Docker container: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Docker run failed.", file=sys.stderr)
        sys.exit(result.returncode)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Tool for building and running docker images."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run an existing Docker image.")
    run_parser.add_argument(
        "--image-name",
        help="Docker image to run",
        default="hyoon11/vllm-dev:20260121_43_py3.12_torch2.9_triton3.5_navi_upstream_6a09612_ubuntu24.04",
    )
    run_parser.add_argument("--script", help="Script to run inside container.")
    run_parser.add_argument(
        "--hf-cache-dir",
        help="Location of host folder which will be mounter under /root/.cache/huggingface in docker container.",
        default="./.cache/huggingface",
    )
    run_parser.add_argument(
        "--device", help="/dev/dri/<dir> location of the device", required=True
    )
    run_parser.add_argument("--device-name", help="Actual name of the device.")

    return parser.parse_known_args()


def main():
    args, extra_args = parse_args()

    if args.command == "run":
        if not args.hf_cache_dir.endswith(".cache/huggingface"):
            print("Huggingface cache dir invalid: must end with .cache/huggingface")
            sys.exit(1)
        run_container(args, extra_args)
    else:
        # TODO: implement build functionality?
        print("Currently only running existing docker images is supported.")
        exit(1)


if __name__ == "__main__":
    main()