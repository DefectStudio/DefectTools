"""Create private V2 role credentials once and provision local client profiles."""

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
from urllib.parse import urlparse


def private_json(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")
    if os.name == "nt":
        subprocess.run(["icacls.exe", str(path), "/inheritance:r", "/grant:r", f"{os.environ['USERNAME']}:(F)"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url")
    args = parser.parse_args()
    base = Path(os.environ["LOCALAPPDATA"]) / "DefectStudio/RenderFarmV2"
    secret_path = base / "company-service-secrets.json"
    roles = ("submit", "worker", "manager", "viewer")
    if secret_path.exists():
        credentials = json.loads(secret_path.read_text(encoding="utf-8"))
        if any(not isinstance(credentials.get(role.upper() + "_TOKEN"), str) or
               not credentials[role.upper() + "_TOKEN"].startswith("defect_v2_") for role in roles):
            raise ValueError("Existing company secret file is not a complete V2 credential set.")
        print("Reusing existing private V2 service credentials.")
    else:
        credentials = {role.upper() + "_TOKEN": f"defect_v2_{role}_" + secrets.token_urlsafe(48) for role in roles}
        private_json(secret_path, credentials)
        print("Created four private V2 role credentials.")
    if args.api_url:
        url = args.api_url.strip().rstrip("/")
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.hostname == "defect-farm-api.twilight-tooth-7b7c.workers.dev"):
            raise ValueError("A separate HTTPS V2 endpoint is required.")
        for role in roles:
            private_json(base / f"company-{role}.json", {"api_url": url, f"{role}_token": credentials[role.upper() + "_TOKEN"]})
        print("Provisioned separate worker, manager, submitter and viewer profiles.")
    print(f"Service secrets file: {secret_path}")


if __name__ == "__main__":
    main()
