# Thank you Ty Fiero for making this!

import hashlib
import json
import math
import os
import platform
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import inquirer
import psutil
import requests


CATALOG_URL = os.environ.get(
    "OI_LOCAL_MODEL_CATALOG_URL",
    "https://raw.githubusercontent.com/OpenInterpreter/models/main/catalog.json",
)
CATALOG_TIMEOUT = 15
DOWNLOAD_RETRY_ATTEMPTS = 3
PROGRESS_UPDATE_INTERVAL = 0.5
RESUME_EXTENSION = ".part"


STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "step_heading": "[Step {index}/{total}] {label}",
        "step_provider": "Choose a local model provider",
        "step_checks": "Review system and provider requirements",
        "step_download": "Download or connect a model",
        "step_finish": "Complete setup",
        "step_complete": "✓ Done.",
        "step_skipped": "Skipping (not required for this provider).",
        "provider_prompt": "Select a provider",
        "checks_accessibility_hint": "This step highlights RAM, disk usage, and recommended models for accessibility.",
        "download_accessibility_hint": "Progress updates include percentage, speed, and estimated time remaining.",
        "hardware_summary": "Your machine has `{ram:.2f}GB` RAM and `{disk:.2f}GB` of free storage.",
        "hardware_guidance_small": "Only lightweight models (under 4GB) are recommended for this hardware profile.",
        "hardware_guidance_medium": "Mid-sized models (4-10GB) should run reliably on this machine.",
        "hardware_guidance_large": "This machine can run any of the available models.",
        "checks_not_required": "No additional checks required for this provider.",
        "catalog_fetch": "Fetching the latest local model catalog…",
        "catalog_error": "Unable to reach the remote catalog. Using the bundled list instead.",
        "no_catalog_entries": "No catalog entries are available for download at this time.",
        "no_models_downloaded": "No models currently downloaded.",
        "existing_models_prompt": "Select a downloaded model or choose a new one:",
        "download_prompt": "Select a model to download:",
        "download_not_required": "No download is required for this provider.",
        "download_estimate": "Estimated remaining size: {size:.2f}GB. Approximate download time: {eta}. Free disk after download: {disk:.2f}GB.",
        "download_start": "Preparing to download `{name}` ({size:.2f}GB)…",
        "download_progress": "Downloaded {downloaded:.2f}GB of {total:.2f}GB ({percent:.1f}%). Speed: {speed:.1f} MB/s. ETA: {eta}.",
        "download_complete": "Download complete.",
        "download_failed": "Download error: {error}",
        "download_cancelled": "Download cancelled.",
        "resume_detected": "Resuming download from {progress:.1f}% completion.",
        "resume_option": "Resume download",
        "restart_option": "Restart download",
        "cancel_option": "Cancel setup",
        "retry_prompt": "The download did not complete. What would you like to do?",
        "restart_notice": "Restarting download from the beginning…",
        "checksum_verifying": "Verifying file checksum…",
        "checksum_ok": "Checksum verified.",
        "checksum_failed": "The downloaded file failed checksum validation.",
        "finish_message_generic": "Setup complete. You can now continue in the terminal.",
        "finish_message_llamafile": "To manage your downloaded Llamafile models later, run `interpreter --local_models`.",
        "ollama_check": "Checking for Ollama installation…",
        "ollama_missing": "Ollama is not installed or not recognized. Visit https://ollama.com/ to install it and run this setup again.",
        "ollama_select_model": "Select an Ollama model",
        "ollama_downloading": "Downloading `{model}` with `ollama pull`…",
        "ollama_ready": "Ollama is ready. Selected model: `{model}`.",
        "ollama_library": "Browse models on https://ollama.com/library",
        "ollama_launch_browser": "Opening https://ollama.com/library in your default browser.",
        "lmstudio_instructions": (
            "To use Open Interpreter with **LM Studio**, ensure the LM Studio server is running:\n"
            "1. Download LM Studio from https://lmstudio.ai/ and launch it.\n"
            "2. Download a model, then open the API Server view (the `<->` button).\n"
            "3. Select your model and click **Start Server** before returning to this terminal."
        ),
        "jan_instructions": (
            "To use Open Interpreter with **Jan**, ensure the local API server is running:\n"
            "1. Download Jan from https://jan.ai/ and start the application.\n"
            "2. Download a model from the Hub, then start the Local API Server."
        ),
        "jan_loading_models": "Retrieving models from Jan…",
        "jan_select_model": "Select the model running in Jan",
        "jan_custom_model": "Type a custom model ID",
        "jan_connection_error": "Unable to retrieve models from Jan. Ensure Jan is running and the local API server is enabled.",
        "partial_download_choice": "Resume `{name}` ({progress:.1f}% complete)",
        "catalog_filtered_none": "No models meet your current storage requirements.",
        "llamafile_intro": "Only models you have the storage space to download are shown below.",
    }
}


@dataclass
class ModelCatalogEntry:
    name: str
    url: str
    size_gb: float
    checksum: Optional[str] = None
    checksum_algorithm: str = "sha256"

    @property
    def file_name(self) -> str:
        base = os.path.basename(self.url)
        return base.split("?")[0]

    @property
    def size_bytes(self) -> Optional[int]:
        if math.isfinite(self.size_gb):
            return int(self.size_gb * 1024 * 1024 * 1024)
        return None


class DownloadError(Exception):
    """Raised when a download cannot be completed."""


class SetupStepper:
    def __init__(self, interpreter, strings: Dict[str, str], total_steps: int = 4):
        self.interpreter = interpreter
        self.strings = strings
        self.total_steps = total_steps
        self.current_index = 0

    def start(self, label_key: str) -> None:
        self.current_index += 1
        label = self.strings.get(label_key, label_key)
        heading = self.strings["step_heading"].format(
            index=self.current_index, total=self.total_steps, label=label
        )
        self.interpreter.display_message(heading)

    def complete(self, key: str = "step_complete") -> None:
        self.interpreter.display_message(self.strings.get(key, key))

    def skip(self) -> None:
        self.interpreter.display_message(self.strings["step_skipped"])


def get_locale(interpreter) -> str:
    for attr in ("locale", "language", "lang"):
        value = getattr(interpreter, attr, None)
        if value:
            return str(value).split("-")[0].lower()
    return "en"


def get_strings(interpreter) -> Dict[str, str]:
    locale = get_locale(interpreter)
    return STRINGS.get(locale, STRINGS["en"])


def format_eta(seconds: Optional[float]) -> str:
    if not seconds or seconds <= 0:
        return "calculating…"
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    if minutes == 0:
        return f"{sec}s"
    hours, minutes = divmod(minutes, 60)
    if hours == 0:
        return f"{minutes}m {sec}s"
    days, hours = divmod(hours, 24)
    if days == 0:
        return f"{hours}h {minutes}m"
    return f"{days}d {hours}h"


def recommended_model_text(strings: Dict[str, str], ram_gb: float) -> str:
    if ram_gb < 10:
        return strings["hardware_guidance_small"]
    if ram_gb < 30:
        return strings["hardware_guidance_medium"]
    return strings["hardware_guidance_large"]


def bundled_catalog() -> List[ModelCatalogEntry]:
    return [
        ModelCatalogEntry(
            name="Llama-3.1-8B-Instruct",
            url="https://huggingface.co/Mozilla/Meta-Llama-3.1-8B-Instruct-llamafile/resolve/main/Meta-Llama-3.1-8B-Instruct.Q4_K_M.llamafile?download=true",
            size_gb=4.95,
        ),
        ModelCatalogEntry(
            name="Gemma-2-9b",
            url="https://huggingface.co/jartine/gemma-2-9b-it-llamafile/resolve/main/gemma-2-9b-it.Q4_K_M.llamafile?download=true",
            size_gb=5.79,
        ),
        ModelCatalogEntry(
            name="Phi-3-mini",
            url="https://huggingface.co/Mozilla/Phi-3-mini-4k-instruct-llamafile/resolve/main/Phi-3-mini-4k-instruct.Q4_K_M.llamafile?download=true",
            size_gb=2.42,
        ),
        ModelCatalogEntry(
            name="Moondream2 (vision)",
            url="https://huggingface.co/cjpais/moondream2-llamafile/resolve/main/moondream2-q5km-050824.llamafile?download=true",
            size_gb=1.98,
        ),
        ModelCatalogEntry(
            name="Mistral-7B-Instruct",
            url="https://huggingface.co/Mozilla/Mistral-7B-Instruct-v0.3-llamafile/resolve/main/Mistral-7B-Instruct-v0.3.Q4_K_M.llamafile?download=true",
            size_gb=4.40,
        ),
        ModelCatalogEntry(
            name="Gemma-2-27b",
            url="https://huggingface.co/jartine/gemma-2-27b-it-llamafile/resolve/main/gemma-2-27b-it.Q4_K_M.llamafile?download=true",
            size_gb=16.7,
        ),
        ModelCatalogEntry(
            name="TinyLlama-1.1B",
            url="https://huggingface.co/Mozilla/TinyLlama-1.1B-Chat-v1.0-llamafile/resolve/main/TinyLlama-1.1B-Chat-v1.0.Q4_K_M.llamafile?download=true",
            size_gb=0.70,
        ),
        ModelCatalogEntry(
            name="Rocket-3B",
            url="https://huggingface.co/Mozilla/rocket-3B-llamafile/resolve/main/rocket-3b.Q4_K_M.llamafile?download=true",
            size_gb=1.74,
        ),
        ModelCatalogEntry(
            name="LLaVA 1.5 (vision)",
            url="https://huggingface.co/Mozilla/llava-v1.5-7b-llamafile/resolve/main/llava-v1.5-7b-q4.llamafile?download=true",
            size_gb=4.29,
        ),
        ModelCatalogEntry(
            name="WizardCoder-Python-13B",
            url="https://huggingface.co/jartine/wizardcoder-13b-python/resolve/main/wizardcoder-python-13b.llamafile?download=true",
            size_gb=7.33,
        ),
        ModelCatalogEntry(
            name="WizardCoder-Python-34B",
            url="https://huggingface.co/Mozilla/WizardCoder-Python-34B-V1.0-llamafile/resolve/main/wizardcoder-python-34b-v1.0.Q4_K_M.llamafile?download=true",
            size_gb=20.22,
        ),
        ModelCatalogEntry(
            name="Mixtral-8x7B-Instruct",
            url="https://huggingface.co/jartine/Mixtral-8x7B-Instruct-v0.1-llamafile/resolve/main/mixtral-8x7b-instruct-v0.1.Q5_K_M.llamafile?download=true",
            size_gb=30.03,
        ),
    ]


def parse_catalog_entries(data: Iterable[dict]) -> List[ModelCatalogEntry]:
    entries: List[ModelCatalogEntry] = []
    for entry in data:
        name = entry.get("name") or entry.get("model")
        url = entry.get("url")
        if not name or not url:
            continue
        size_gb: float
        if "size_gb" in entry:
            size_gb = float(entry["size_gb"])
        elif "sizeGB" in entry:
            size_gb = float(entry["sizeGB"])
        elif "size" in entry:
            size_value = entry["size"]
            if isinstance(size_value, str) and size_value.lower().endswith("gb"):
                size_gb = float(size_value[:-2])
            else:
                size_gb = float(size_value) / (1024 * 1024 * 1024)
        else:
            size_gb = math.nan
        checksum = entry.get("checksum")
        checksum_algorithm = entry.get("checksum_algorithm", "sha256")
        entries.append(
            ModelCatalogEntry(
                name=name,
                url=url,
                size_gb=size_gb,
                checksum=checksum,
                checksum_algorithm=checksum_algorithm,
            )
        )
    return entries


def fetch_model_catalog(interpreter, strings: Dict[str, str]) -> List[ModelCatalogEntry]:
    interpreter.display_message(strings["catalog_fetch"])
    session = requests.Session()
    try:
        response = session.get(CATALOG_URL, timeout=CATALOG_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "models" in data:
            data = data["models"]
        if isinstance(data, list):
            entries = parse_catalog_entries(data)
            if entries:
                return entries
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        pass

    interpreter.display_message(strings["catalog_error"])
    return bundled_catalog()


def display_hardware_summary(interpreter, strings: Dict[str, str]) -> Dict[str, float]:
    total_ram_gb = psutil.virtual_memory().total / (1024 * 1024 * 1024)
    free_disk_gb = psutil.disk_usage("/").free / (1024 * 1024 * 1024)
    interpreter.display_message(strings["checks_accessibility_hint"])
    interpreter.display_message(
        strings["hardware_summary"].format(ram=total_ram_gb, disk=free_disk_gb)
    )
    interpreter.display_message(recommended_model_text(strings, total_ram_gb))
    return {"ram_gb": total_ram_gb, "disk_gb": free_disk_gb}


def ensure_models_dir(interpreter) -> str:
    models_dir = os.path.join(interpreter.get_oi_dir(), "models")
    os.makedirs(models_dir, exist_ok=True)
    return models_dir


def filter_catalog_for_disk(
    catalog: List[ModelCatalogEntry], models_dir: str, free_disk_gb: float
) -> List[ModelCatalogEntry]:
    filtered: List[ModelCatalogEntry] = []
    for entry in catalog:
        if entry.size_gb and entry.size_gb > free_disk_gb:
            continue
        dest_path = os.path.join(models_dir, entry.file_name)
        if os.path.exists(dest_path):
            continue
        filtered.append(entry)
    return filtered


def prompt_retry_action(strings: Dict[str, str]) -> str:
    question = [
        inquirer.List(
            "action",
            message=strings["retry_prompt"],
            choices=[
                strings["resume_option"],
                strings["restart_option"],
                strings["cancel_option"],
            ],
        )
    ]
    answer = inquirer.prompt(question)
    if not answer:
        raise SystemExit()
    return answer["action"]


def render_progress(
    interpreter, strings: Dict[str, str], downloaded: int, total: Optional[int], start_time: float
) -> None:
    now = time.time()
    elapsed = max(now - start_time, 1e-6)
    speed = downloaded / elapsed / (1024 * 1024)
    if total and total > 0:
        percent = downloaded / total * 100
        eta_seconds = (total - downloaded) / max(downloaded / elapsed, 1e-6)
        message = strings["download_progress"].format(
            downloaded=downloaded / (1024 * 1024 * 1024),
            total=total / (1024 * 1024 * 1024),
            percent=percent,
            speed=speed,
            eta=format_eta(eta_seconds),
        )
    else:
        message = strings["download_progress"].format(
            downloaded=downloaded / (1024 * 1024 * 1024),
            total=downloaded / (1024 * 1024 * 1024),
            percent=100.0,
            speed=speed,
            eta=format_eta(None),
        )
    print(f"\r{message}", end="", flush=True)


def finalize_progress_line() -> None:
    print()


def download_with_resume(
    interpreter,
    strings: Dict[str, str],
    entry: ModelCatalogEntry,
    dest_path: str,
    free_disk_gb: float,
) -> str:
    session = requests.Session()
    temp_path = dest_path + RESUME_EXTENSION
    if os.path.exists(dest_path):
        return dest_path

    resume_bytes = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
    total_bytes = entry.size_bytes
    required_bytes = (total_bytes or 0) - resume_bytes if total_bytes else None
    if required_bytes and required_bytes > free_disk_gb * 1024 * 1024 * 1024:
        raise DownloadError("Insufficient disk space for download.")

    interpreter.display_message(
        strings["download_start"].format(name=entry.name, size=entry.size_gb)
    )
    interpreter.display_message(strings["download_accessibility_hint"])

    if resume_bytes and total_bytes:
        progress = resume_bytes / total_bytes * 100
        interpreter.display_message(strings["resume_detected"].format(progress=progress))

    estimated_bytes = (total_bytes - resume_bytes) if total_bytes else None
    if estimated_bytes:
        assumed_speed = 25 * 1024 * 1024  # 25 MB/s
        eta = format_eta(estimated_bytes / assumed_speed)
        remaining_gb = estimated_bytes / (1024 * 1024 * 1024)
        projected_disk = max(free_disk_gb - remaining_gb, 0)
        interpreter.display_message(
            strings["download_estimate"].format(size=remaining_gb, eta=eta, disk=projected_disk)
        )

    attempt = 0
    current_resume_bytes = resume_bytes
    while True:
        current_resume_bytes = (
            os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
        )
        attempt += 1
        try:
            headers = {}
            mode = "ab"
            if current_resume_bytes:
                headers["Range"] = f"bytes={current_resume_bytes}-"
            response = session.get(entry.url, headers=headers, stream=True, timeout=60)
            if current_resume_bytes and response.status_code == 200:
                current_resume_bytes = 0
                mode = "wb"
            response.raise_for_status()
            total_from_headers = response.headers.get("Content-Length")
            if total_from_headers is not None:
                content_length = int(total_from_headers)
                total = current_resume_bytes + content_length
            else:
                total = total_bytes
            downloaded = current_resume_bytes
            start_time = time.time()
            last_update = 0.0
            with open(temp_path, mode) as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_update >= PROGRESS_UPDATE_INTERVAL:
                        render_progress(interpreter, strings, downloaded, total, start_time)
                        last_update = now
            render_progress(interpreter, strings, downloaded, total, start_time)
            finalize_progress_line()
            os.replace(temp_path, dest_path)
            interpreter.display_message(strings["download_complete"])
            verify_checksum(interpreter, strings, entry, dest_path)
            return dest_path
        except (requests.RequestException, OSError, DownloadError) as exc:
            finalize_progress_line()
            interpreter.display_message(strings["download_failed"].format(error=str(exc)))
            should_prompt = isinstance(exc, DownloadError)
            if not should_prompt and attempt < DOWNLOAD_RETRY_ATTEMPTS:
                time.sleep(1)
                continue
            action = prompt_retry_action(strings)
            if action == strings["resume_option"]:
                attempt = 0
                continue
            if action == strings["restart_option"]:
                interpreter.display_message(strings["restart_notice"])
                current_resume_bytes = 0
                attempt = 0
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                continue
            raise SystemExit()


def verify_checksum(
    interpreter,
    strings: Dict[str, str],
    entry: ModelCatalogEntry,
    dest_path: str,
) -> None:
    if not entry.checksum:
        return
    interpreter.display_message(strings["checksum_verifying"])
    try:
        hasher = hashlib.new(entry.checksum_algorithm)
    except ValueError:
        return

    with open(dest_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest.lower() == entry.checksum.lower():
        interpreter.display_message(strings["checksum_ok"])
    else:
        raise DownloadError(strings["checksum_failed"])


def list_existing_models(models_dir: str) -> List[str]:
    return [f for f in os.listdir(models_dir) if f.endswith(".llamafile")]


def list_partial_downloads(models_dir: str) -> Dict[str, str]:
    partials: Dict[str, str] = {}
    for file_name in os.listdir(models_dir):
        if file_name.endswith(RESUME_EXTENSION):
            partials[file_name] = os.path.join(models_dir, file_name)
    return partials


def select_llamafile_model(
    interpreter,
    strings: Dict[str, str],
    models_dir: str,
    catalog: List[ModelCatalogEntry],
    free_disk_gb: float,
) -> Optional[str]:
    existing_models = list_existing_models(models_dir)
    partial_downloads = list_partial_downloads(models_dir)

    filtered_catalog = filter_catalog_for_disk(catalog, models_dir, free_disk_gb)

    choices: List[str] = []
    mapping: Dict[str, ModelCatalogEntry] = {}

    if existing_models:
        choices.extend(existing_models)
    if partial_downloads:
        for partial_file, full_path in partial_downloads.items():
            entry_name = partial_file[: -len(RESUME_EXTENSION)]
            for entry in catalog:
                if entry.file_name == entry_name:
                    size = entry.size_bytes or 0
                    downloaded = os.path.getsize(full_path)
                    progress = downloaded / size * 100 if size else 0
                    label = strings["partial_download_choice"].format(
                        name=entry.name, progress=progress
                    )
                    choices.append(label)
                    mapping[label] = entry
                    break

    if filtered_catalog:
        for entry in filtered_catalog:
            label = f"{entry.name} ({entry.size_gb:.2f}GB)"
            choices.append(label)
            mapping[label] = entry
    else:
        interpreter.display_message(strings["catalog_filtered_none"])

    if not choices:
        interpreter.display_message(strings["no_catalog_entries"])
        return None

    question = [
        inquirer.List(
            "selection",
            message=strings["existing_models_prompt"],
            choices=choices,
        )
    ]
    answer = inquirer.prompt(question)
    if not answer:
        raise SystemExit()
    selection = answer["selection"]

    if selection in mapping:
        entry = mapping[selection]
        dest_path = os.path.join(models_dir, entry.file_name)
        free_disk_bytes = psutil.disk_usage(models_dir).free / (1024 * 1024 * 1024)
        return download_with_resume(interpreter, strings, entry, dest_path, free_disk_bytes)

    if selection in existing_models:
        return os.path.join(models_dir, selection)

    return None


def start_llamafile_server(model_path: str) -> None:
    process = subprocess.Popen(
        f'"{model_path}" ' + " ".join(["--nobrowser", "-ngl", "9999"]),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if "llama server listening" in line:
                break
    except Exception:
        process.kill()
        raise


def handle_llamafile(interpreter, strings: Dict[str, str], stepper: SetupStepper) -> None:
    if platform.system() == "Darwin":
        result = subprocess.run(
            ["xcode-select", "-p"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        if result.returncode != 0:
            interpreter.display_message(
                "To use Llamafile, Mac users must install Xcode from https://developer.apple.com/xcode/."
            )
            interpreter.display_message(
                "Alternatively, use LM Studio, Jan.ai, or Ollama to manage local language models."
            )
            raise SystemExit(1)

    models_dir = ensure_models_dir(interpreter)

    stepper.start("step_checks")
    hardware = display_hardware_summary(interpreter, strings)
    interpreter.display_message(strings["llamafile_intro"])
    stepper.complete()

    stepper.start("step_download")
    catalog = fetch_model_catalog(interpreter, strings)
    if not catalog:
        interpreter.display_message(strings["no_catalog_entries"])
        stepper.complete()
        return
    free_disk_gb = hardware["disk_gb"]
    model_path = select_llamafile_model(
        interpreter, strings, models_dir, catalog, free_disk_gb
    )
    if model_path is None:
        interpreter.display_message(strings["download_cancelled"])
        stepper.complete()
        return

    if platform.system() != "Windows":
        subprocess.run(["chmod", "+x", model_path], check=False)

    start_llamafile_server(model_path)

    interpreter.llm.model = "openai/local"
    interpreter.llm.api_key = "dummy"
    interpreter.llm.temperature = 0
    interpreter.llm.api_base = "http://localhost:8080/v1"
    interpreter.llm.supports_functions = False

    model_name = os.path.basename(model_path)
    interpreter.display_message(f"> Model set to `{model_name}`")
    stepper.complete()

    stepper.start("step_finish")
    interpreter.display_message(strings["finish_message_llamafile"])
    stepper.complete()


def handle_lmstudio(interpreter, strings: Dict[str, str], stepper: SetupStepper) -> None:
    stepper.start("step_checks")
    interpreter.display_message(strings["lmstudio_instructions"])
    stepper.complete()

    stepper.start("step_download")
    stepper.skip()
    stepper.complete()

    interpreter.llm.supports_functions = False
    interpreter.llm.api_base = "http://localhost:1234/v1"
    interpreter.llm.api_key = "dummy"

    stepper.start("step_finish")
    interpreter.display_message(strings["finish_message_generic"])
    stepper.complete()


def handle_ollama(interpreter, strings: Dict[str, str], stepper: SetupStepper) -> None:
    stepper.start("step_checks")
    interpreter.display_message(strings["ollama_check"])
    try:
        subprocess.run(["ollama", "version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        interpreter.display_message(strings["ollama_missing"])
        raise SystemExit(1)
    stepper.complete()

    stepper.start("step_download")
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        interpreter.display_message(strings["ollama_missing"])
        raise SystemExit(1)

    lines = result.stdout.splitlines()
    names = [
        line.split()[0].replace(":latest", "")
        for line in lines
        if line.strip() and not line.startswith("failed") and not line.startswith("NAME")
    ]
    priority_models = ["llama3", "codestral"]
    priority_models_found: List[str] = []
    for word in priority_models:
        models_to_move = [name for name in names if word.lower() in name.lower()]
        priority_models_found.extend(models_to_move)
    names = [
        name
        for name in names
        if not any(word.lower() in name.lower() for word in priority_models)
    ]
    names = priority_models_found + names

    for model in ["llama3.1", "phi3", "mistral-nemo", "gemma2", "codestral"]:
        if model not in names:
            names.append("↓ Download " + model)

    names.append(strings["ollama_library"])

    question = [
        inquirer.List(
            "name",
            message=strings["ollama_select_model"],
            choices=names,
        )
    ]
    answer = inquirer.prompt(question)
    if not answer:
        raise SystemExit()
    selected_name = answer["name"]

    if selected_name.startswith("↓ Download "):
        model = selected_name.split(" ")[-1]
        interpreter.display_message(
            strings["ollama_downloading"].format(model=model)
        )
        subprocess.run(["ollama", "pull", model], check=True)
    elif selected_name == strings["ollama_library"]:
        interpreter.display_message(strings["ollama_launch_browser"])
        import webbrowser

        webbrowser.open("https://ollama.com/library")
        raise SystemExit()
    else:
        model = selected_name.strip()

    interpreter.llm.model = f"ollama/{model}"
    old_max_tokens = interpreter.llm.max_tokens
    old_context_window = interpreter.llm.context_window
    interpreter.llm.max_tokens = 1
    interpreter.llm.context_window = 100
    interpreter.computer.ai.chat("ping")
    interpreter.llm.max_tokens = old_max_tokens
    interpreter.llm.context_window = old_context_window
    interpreter.display_message(strings["ollama_ready"].format(model=model))
    stepper.complete()

    stepper.start("step_finish")
    interpreter.display_message(strings["finish_message_generic"])
    stepper.complete()


def handle_jan(interpreter, strings: Dict[str, str], stepper: SetupStepper) -> None:
    stepper.start("step_checks")
    interpreter.display_message(strings["jan_instructions"])
    stepper.complete()

    stepper.start("step_download")
    interpreter.display_message(strings["jan_loading_models"])
    try:
        response = requests.get("http://localhost:1337/v1/models", timeout=10)
        response.raise_for_status()
        models = response.json().get("data", [])
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        interpreter.display_message(strings["jan_connection_error"])
        raise SystemExit(1)

    model_ids = [model.get("id") for model in models if model.get("id")]
    model_ids.insert(0, strings["jan_custom_model"])

    question = [
        inquirer.List(
            "jan_model_name",
            message=strings["jan_select_model"],
            choices=model_ids,
        )
    ]
    answer = inquirer.prompt(question)
    if not answer:
        raise SystemExit()
    jan_model_name = answer["jan_model_name"]
    if jan_model_name == strings["jan_custom_model"]:
        jan_model_name = input("Enter the custom model ID: ")

    interpreter.llm.model = jan_model_name
    interpreter.llm.api_key = "dummy"
    interpreter.display_message(f"\nUsing Jan model: `{jan_model_name}`\n")
    stepper.complete()

    stepper.start("step_finish")
    interpreter.display_message(strings["finish_message_generic"])
    stepper.complete()


def apply_token_defaults(interpreter) -> None:
    user_ram = psutil.virtual_memory().total / (1024 * 1024 * 1024)
    if user_ram > 9:
        interpreter.llm.max_tokens = 1200
        interpreter.llm.context_window = 8000
    else:
        interpreter.llm.max_tokens = 1000
        interpreter.llm.context_window = 3000


def local_setup(interpreter, provider=None, model=None):
    strings = get_strings(interpreter)
    stepper = SetupStepper(interpreter, strings)

    stepper.start("step_provider")
    choices = ["Ollama", "Llamafile", "LM Studio", "Jan"]
    question = [
        inquirer.List(
            "model",
            message=strings["provider_prompt"],
            choices=choices,
        )
    ]
    answers = inquirer.prompt(question)
    if not answers:
        raise SystemExit()
    selected_provider = answers["model"]
    stepper.complete()

    if selected_provider == "Llamafile":
        handle_llamafile(interpreter, strings, stepper)
    elif selected_provider == "LM Studio":
        handle_lmstudio(interpreter, strings, stepper)
    elif selected_provider == "Jan":
        handle_jan(interpreter, strings, stepper)
    elif selected_provider == "Ollama":
        handle_ollama(interpreter, strings, stepper)
    else:
        stepper.start("step_checks")
        interpreter.display_message(strings["checks_not_required"])
        stepper.complete()
        stepper.start("step_download")
        interpreter.display_message(strings["download_not_required"])
        stepper.complete()
        stepper.start("step_finish")
        interpreter.display_message(strings["finish_message_generic"])
        stepper.complete()

    apply_token_defaults(interpreter)

    if interpreter.auto_run is False:
        interpreter.display_message(
            "**Open Interpreter** will require approval before running code."
            + "\n\nUse `interpreter -y` to bypass this."
            + "\n\nPress `CTRL-C` to exit.\n"
        )

    return interpreter

