#!/usr/bin/env python3
"""
CurseForge Modpack Downloader v4.0

Downloads mods, shaderpacks, and resourcepacks from CurseForge modpacks.
Sorts files into subfolders automatically.
Downloads mod dependencies.
Skips already downloaded files.

Requirements:
    pip install requests beautifulsoup4

API Key (free):
    https://console.curseforge.com/
"""

import os
import re
import sys
import time
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse, urljoin
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

DELAY_BETWEEN_DOWNLOADS = 0.5
REQUEST_TIMEOUT = 60
CHUNK_SIZE = 8192
CACHE_FILENAME = "_download_cache.json"
REPORT_FILENAME = "_download_report.json"
CF_API_BASE = "https://api.curseforge.com/v1"

CDN_URLS = [
    "https://edge.forgecdn.net/files",
    "https://mediafilez.forgecdn.net/files",
]

# CurseForge class IDs — determine file type
# These IDs tell us what kind of file we are downloading
CF_CLASS_IDS = {
    6:    "mods",            # Mods
    12:   "resourcepacks",   # Resource Packs (Texture Packs)
    17:   "worlds",          # Worlds
    4546: "shaderpacks",     # Shader Packs
    4471: "modpacks",        # Modpacks
    6552: "shaderpacks",     # Shaders (alternative ID)
    6945: "datapacks",       # Data Packs
}

# Relation type for dependencies
# 1 = embedded library
# 2 = optional dependency
# 3 = required dependency
# 4 = tool
# 5 = incompatible
# 6 = include
REQUIRED_DEPENDENCY = 3


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


# ============================================================
# API KEY LOADING
# ============================================================

def load_api_key_from_file(filename="api_key.txt"):
    """
    Load API key from file.
    Tries multiple encodings for Windows compatibility.
    """
    try:
        script_dir = Path(__file__).parent
        path = script_dir / filename

        if not path.exists():
            path = Path(filename)
            if not path.exists():
                return None

        for enc in ["utf-8-sig", "utf-8", "utf-16", "utf-16-le", "cp1251", "cp1252"]:
            try:
                text = path.read_text(encoding=enc).strip()
                text = text.strip('"').strip("'").strip()
                if text and len(text) > 10:
                    return text
            except (UnicodeDecodeError, UnicodeError):
                continue

        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        text = raw.decode("utf-8", errors="ignore").strip()
        text = text.strip('"').strip("'").strip()
        if text and len(text) > 10:
            return text

    except Exception as e:
        print(f"[WARN] Could not read {filename}: {e}")

    return None


def get_best_api_key(provided_key=None):
    """Get the best available API key."""
    if provided_key:
        provided_key = provided_key.strip().strip('"').strip("'").strip()
        if len(provided_key) < 10:
            provided_key = None

    file_key = load_api_key_from_file("api_key.txt")

    if provided_key:
        print(f"[API] Using key from argument (length: {len(provided_key)})")
        return provided_key
    elif file_key:
        print(f"[API] Using key from api_key.txt (length: {len(file_key)})")
        return file_key
    else:
        print("[API] WARNING: No valid API key found!")
        print("[API] Put your key in 'api_key.txt' next to the script.")
        print("[API] Get free key at: https://console.curseforge.com/")
        return None


# ============================================================
# CACHE MANAGER
# ============================================================

class CacheManager:
    """Tracks downloaded files to avoid re-downloading."""

    def __init__(self, cache_file):
        self.cache_file = cache_file
        self.cache = self._load()

    def _load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"[CACHE] Loaded: {len(data)} entries")
                return data
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def save(self):
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            print(f"[CACHE] Saved: {len(self.cache)} entries")
        except IOError as e:
            print(f"[CACHE] Error saving: {e}")

    def is_downloaded(self, key):
        if key in self.cache:
            entry = self.cache[key]
            filepath = entry.get("filepath", "")
            filename = entry.get("filename", "")
            if filepath and Path(filepath).exists():
                return True, filename
        return False, ""

    def mark_downloaded(self, key, filename, filepath, file_size, file_type="mods"):
        self.cache[key] = {
            "filename": filename,
            "filepath": filepath,
            "file_size": file_size,
            "file_type": file_type,
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================
# FILE TYPE DETECTOR
# ============================================================

class FileTypeDetector:
    """
    Determines what type of file we are downloading.
    Uses CurseForge API to check the classId of each project.

    Types:
    - mods          -> output/mods/
    - resourcepacks -> output/resourcepacks/
    - shaderpacks   -> output/shaderpacks/
    - worlds        -> output/worlds/
    - datapacks     -> output/datapacks/
    """

    def __init__(self, session, api_key=None):
        self.session = session
        self.api_key = api_key
        # Cache project info to avoid repeated API calls
        self._project_cache = {}

    def get_project_info(self, project_id):
        """
        Get project info from CurseForge API.
        Returns dict with classId, name, slug, etc.
        Caches results to avoid repeated calls.
        """
        if project_id in self._project_cache:
            return self._project_cache[project_id]

        if not self.api_key:
            return None

        try:
            url = f"{CF_API_BASE}/mods/{project_id}"
            resp = self.session.get(url, timeout=30)

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                self._project_cache[project_id] = data
                return data

        except Exception:
            pass

        return None

    def get_file_type(self, project_id):
        """
        Determine the type of file based on project classId.

        Returns folder name: "mods", "resourcepacks", "shaderpacks", etc.
        """
        info = self.get_project_info(project_id)

        if info:
            class_id = info.get("classId", 6)
            return CF_CLASS_IDS.get(class_id, "mods")

        # Default to mods if we can't determine
        return "mods"

    def get_project_name(self, project_id):
        """Get human-readable project name."""
        info = self.get_project_info(project_id)
        if info:
            return info.get("name", f"Project {project_id}")
        return f"Project {project_id}"

    def get_dependencies(self, project_id, file_id):
        """
        Get required dependencies for a specific file.

        Returns list of dicts:
        [{"modId": 12345, "relationType": 3}, ...]

        relationType 3 = required dependency
        """
        if not self.api_key:
            return []

        try:
            url = f"{CF_API_BASE}/mods/{project_id}/files/{file_id}"
            resp = self.session.get(url, timeout=30)

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                deps = data.get("dependencies", [])

                # Filter only required dependencies
                required = []
                for dep in deps:
                    if dep.get("relationType") == REQUIRED_DEPENDENCY:
                        required.append(dep)

                return required

        except Exception:
            pass

        return []

    def get_latest_file_id(self, project_id, game_version=None, mod_loader=None):
        """
        Get the latest file ID for a project.
        Used when downloading dependencies (we know project ID but not file ID).

        Args:
            project_id: CurseForge project ID
            game_version: e.g. "1.21.1"
            mod_loader: e.g. "neoforge", "forge", "fabric"

        Returns:
            file_id or None
        """
        if not self.api_key:
            return None

        try:
            url = f"{CF_API_BASE}/mods/{project_id}/files"
            params = {"pageSize": 10}

            if game_version:
                params["gameVersion"] = game_version

            resp = self.session.get(url, params=params, timeout=30)

            if resp.status_code == 200:
                files = resp.json().get("data", [])

                if not files:
                    return None

                # If mod_loader specified, try to find matching file
                if mod_loader:
                    loader_lower = mod_loader.lower()
                    for f in files:
                        game_versions = [v.lower() for v in f.get("gameVersions", [])]
                        if any(loader_lower in v for v in game_versions):
                            return f["id"]

                # Return the first (latest) file
                return files[0]["id"]

        except Exception:
            pass

        return None


# ============================================================
# MAIN DOWNLOADER
# ============================================================

class CurseForgeDownloader:
    """
    Downloads mods, shaders, resourcepacks from CurseForge.
    Sorts into subfolders. Downloads dependencies.
    """

    def __init__(self, output_dir="mods_output", api_key=None):
        """
        Args:
            output_dir: root output folder.
                        Subfolders will be created:
                        output_dir/mods/
                        output_dir/resourcepacks/
                        output_dir/shaderpacks/
                        etc.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.api_key = get_best_api_key(api_key)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key

        self.failed = []
        self.succeeded = []
        self.skipped = []
        self.dependencies_downloaded = []

        self.report_file = self.output_dir / REPORT_FILENAME
        self.cache = CacheManager(self.output_dir / CACHE_FILENAME)
        self.detector = FileTypeDetector(self.session, self.api_key)

        # Track which project IDs we have already processed
        # to avoid downloading same dependency twice
        self._processed_projects = set()

        # Store game version and loader from manifest
        self.game_version = None
        self.mod_loader = None

    def _get_subfolder(self, file_type):
        """
        Get or create the subfolder for a file type.

        Args:
            file_type: "mods", "resourcepacks", "shaderpacks", etc.

        Returns:
            Path to the subfolder
        """
        subfolder = self.output_dir / file_type
        subfolder.mkdir(parents=True, exist_ok=True)
        return subfolder

    # ============================================================
    # PARSING
    # ============================================================

    def parse_modlist(self, modlist_path):
        """Read modlist.html and extract mod links."""
        modlist_path = Path(modlist_path)
        if not modlist_path.exists():
            print(f"[ERROR] File not found: {modlist_path}")
            return []

        with open(modlist_path, "r", encoding="utf-8") as f:
            content = f.read()

        soup = BeautifulSoup(content, "html.parser")
        mods = []

        for link in soup.find_all("a"):
            href = link.get("href", "")
            name = link.get_text(strip=True)
            if "curseforge.com" in href:
                mods.append({"name": name, "url": href})

        print(f"[INFO] Found {len(mods)} entries in modlist.html")
        return mods

    def parse_manifest(self, manifest_path):
        """Read manifest.json."""
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        files = manifest.get("files", [])
        print(f"[INFO] Found {len(files)} files in manifest.json")
        print(f"[INFO] Modpack: {manifest.get('name', 'Unknown')}")

        # Extract game version and loader for dependency resolution
        mc_info = manifest.get("minecraft", {})
        self.game_version = mc_info.get("version")
        loaders = mc_info.get("modLoaders", [])

        if loaders:
            loader_id = loaders[0].get("id", "")
            print(f"[INFO] Minecraft: {self.game_version}")
            print(f"[INFO] Loader: {loader_id}")

            # Extract loader name
            if "neoforge" in loader_id.lower():
                self.mod_loader = "neoforge"
            elif "forge" in loader_id.lower():
                self.mod_loader = "forge"
            elif "fabric" in loader_id.lower():
                self.mod_loader = "fabric"
            elif "quilt" in loader_id.lower():
                self.mod_loader = "quilt"

        return files, manifest

    # ============================================================
    # URL HELPERS
    # ============================================================

    def _extract_ids_from_url(self, url):
        match = re.search(
            r"curseforge\.com/minecraft/mc-mods/([^/]+)/files/(\d+)", url
        )
        if match:
            return match.group(1), match.group(2)

        match = re.search(
            r"curseforge\.com/minecraft/mc-mods/([^/]+)/download/(\d+)", url
        )
        if match:
            return match.group(1), match.group(2)

        return None

    def _split_file_id(self, file_id):
        fid = str(file_id)
        return fid[:4], fid[4:].lstrip("0") or "0"

    # ============================================================
    # DEPENDENCY RESOLUTION
    # ============================================================

    def _download_dependencies(self, project_id, file_id):
        """
        Check and download required dependencies for a mod.

        Args:
            project_id: the mod's project ID
            file_id: the mod's file ID
        """
        if not self.api_key:
            return

        deps = self.detector.get_dependencies(project_id, file_id)

        if not deps:
            return

        print(f"  [DEPS] Found {len(deps)} required dependencies")

        for dep in deps:
            dep_project_id = dep.get("modId")

            if not dep_project_id:
                continue

            # Skip if already processed
            if dep_project_id in self._processed_projects:
                dep_name = self.detector.get_project_name(dep_project_id)
                print(f"  [DEPS] Already have: {dep_name}")
                continue

            # Mark as processed
            self._processed_projects.add(dep_project_id)

            dep_name = self.detector.get_project_name(dep_project_id)
            print(f"  [DEPS] Downloading dependency: {dep_name}")

            # Get the best file ID for this dependency
            dep_file_id = self.detector.get_latest_file_id(
                dep_project_id,
                game_version=self.game_version,
                mod_loader=self.mod_loader
            )

            if not dep_file_id:
                print(f"  [DEPS] Could not find file for: {dep_name}")
                continue

            # Check cache
            cache_key = f"cf:{dep_project_id}:{dep_file_id}"
            cached, cached_fn = self.cache.is_downloaded(cache_key)
            if cached:
                print(f"  [DEPS] Already downloaded: {cached_fn}")
                continue

            # Determine file type
            file_type = self.detector.get_file_type(dep_project_id)

            # Download
            ok, fn, sz = self._download_by_ids(dep_project_id, dep_file_id, file_type)

            if ok:
                self.dependencies_downloaded.append({
                    "projectID": dep_project_id,
                    "fileID": dep_file_id,
                    "filename": fn,
                    "name": dep_name,
                    "type": file_type,
                    "parent_project": project_id,
                })
                subfolder = self._get_subfolder(file_type)
                self.cache.mark_downloaded(
                    cache_key, fn, str(subfolder / fn), sz, file_type
                )

                # Recursively check dependencies of this dependency
                self._download_dependencies(dep_project_id, dep_file_id)
            else:
                print(f"  [DEPS] Failed to download: {dep_name}")

            time.sleep(DELAY_BETWEEN_DOWNLOADS * 0.3)

    # ============================================================
    # DOWNLOAD METHODS
    # ============================================================

    def _download_by_url(self, url, mod_name, file_type="mods"):
        """Download mod by URL."""
        try:
            parsed = self._extract_ids_from_url(url)

            if parsed:
                slug, file_id = parsed

                if self.api_key:
                    ok, fn, sz = self._download_by_slug(slug, file_id, file_type)
                    if ok:
                        return ok, fn, sz

                dl_url = (
                    f"https://www.curseforge.com/minecraft/mc-mods/"
                    f"{slug}/download/{file_id}"
                )
                try:
                    resp = self.session.get(
                        dl_url, allow_redirects=True,
                        timeout=REQUEST_TIMEOUT, stream=True
                    )
                    if resp.status_code == 200:
                        ok, fn, sz = self._save_response(resp, mod_name, file_type)
                        if ok:
                            return ok, fn, sz
                except Exception:
                    pass

            return False, "", 0
        except Exception as e:
            print(f"  [ERROR] {mod_name}: {e}")
            return False, "", 0

    def _download_by_slug(self, slug, file_id, file_type="mods"):
        """Search by slug, then download by IDs."""
        if not self.api_key:
            return False, "", 0

        try:
            search_url = f"{CF_API_BASE}/mods/search"
            params = {"gameId": 432, "slug": slug}
            resp = self.session.get(search_url, params=params, timeout=30)

            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    project_id = data[0]["id"]
                    # Detect actual file type from API
                    actual_type = self.detector.get_file_type(project_id)
                    return self._download_by_ids(project_id, int(file_id), actual_type)

        except Exception as e:
            print(f"  [ERROR] Search {slug}: {e}")

        return False, "", 0

    def _download_by_ids(self, project_id, file_id, file_type="mods"):
        """
        Download by projectID + fileID.
        Saves to the correct subfolder based on file_type.
        """
        # Mark project as processed
        self._processed_projects.add(project_id)

        # Method 1: Official API
        if self.api_key:
            ok, fn, sz = self._download_via_api(project_id, file_id, file_type)
            if ok:
                return ok, fn, sz

        # Method 2: Edge API
        try:
            url = (
                f"https://www.curseforge.com/api/v1/mods/{project_id}"
                f"/files/{file_id}/download"
            )
            resp = self.session.get(
                url, allow_redirects=True,
                timeout=REQUEST_TIMEOUT, stream=True
            )
            if resp.status_code == 200:
                ct = resp.headers.get("Content-Type", "")
                if "text/html" not in ct:
                    ok, fn, sz = self._save_response(
                        resp, f"mod_{project_id}", file_type
                    )
                    if ok:
                        return ok, fn, sz
        except Exception:
            pass

        # Method 3: CDN
        if self.api_key:
            ok, fn, sz = self._download_via_cdn_info(project_id, file_id, file_type)
            if ok:
                return ok, fn, sz

        return False, "", 0

    def _download_via_api(self, project_id, file_id, file_type="mods"):
        """Download via official API."""
        if not self.api_key:
            return False, "", 0

        try:
            # Try download-url
            url = f"{CF_API_BASE}/mods/{project_id}/files/{file_id}/download-url"
            resp = self.session.get(url, timeout=30)

            if resp.status_code == 200:
                dl_url = resp.json().get("data")
                if dl_url:
                    ok, fn, sz = self._download_from_direct_url(dl_url, None, file_type)
                    if ok:
                        return ok, fn, sz

            # Try file info
            info_url = f"{CF_API_BASE}/mods/{project_id}/files/{file_id}"
            resp = self.session.get(info_url, timeout=30)

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                dl_url = data.get("downloadUrl", "")
                filename = data.get("fileName", "")

                if dl_url:
                    ok, fn, sz = self._download_from_direct_url(
                        dl_url, filename, file_type
                    )
                    if ok:
                        return ok, fn, sz

                if filename:
                    ok, fn, sz = self._try_cdn_download(file_id, filename, file_type)
                    if ok:
                        return ok, fn, sz

        except Exception as e:
            print(f"  [ERROR API] project={project_id}: {e}")

        return False, "", 0

    def _download_via_cdn_info(self, project_id, file_id, file_type="mods"):
        """Get filename from API, download from CDN."""
        if not self.api_key:
            return False, "", 0

        try:
            info_url = f"{CF_API_BASE}/mods/{project_id}/files/{file_id}"
            resp = self.session.get(info_url, timeout=30)

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                filename = data.get("fileName", "")
                if filename:
                    return self._try_cdn_download(file_id, filename, file_type)

        except Exception:
            pass

        return False, "", 0

    def _try_cdn_download(self, file_id, filename, file_type="mods"):
        """Try CDN servers."""
        id1, id2 = self._split_file_id(file_id)
        subfolder = self._get_subfolder(file_type)

        for cdn_base in CDN_URLS:
            cdn_url = f"{cdn_base}/{id1}/{id2}/{filename}"
            try:
                resp = self.session.get(
                    cdn_url, timeout=REQUEST_TIMEOUT, stream=True
                )
                if resp.status_code == 200:
                    ct = resp.headers.get("Content-Type", "")
                    if "text/html" not in ct:
                        filepath = subfolder / filename
                        size = 0
                        with open(filepath, "wb") as f:
                            for chunk in resp.iter_content(CHUNK_SIZE):
                                if chunk:
                                    f.write(chunk)
                                    size += len(chunk)

                        if size > 0:
                            print(f"  [OK CDN] [{file_type}] {filename} ({size/1024/1024:.2f} MB)")
                            return True, filename, size
                        else:
                            filepath.unlink(missing_ok=True)

            except Exception:
                continue

        return False, "", 0

    def _download_from_direct_url(self, url, filename=None, file_type="mods"):
        """Download from direct URL into correct subfolder."""
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT, stream=True)

            if resp.status_code != 200:
                return False, "", 0

            ct = resp.headers.get("Content-Type", "")
            if "text/html" in ct:
                return False, "", 0

            if not filename:
                cd = resp.headers.get("Content-Disposition", "")
                if cd:
                    m = re.search(r'filename[*]?=["\']?([^"\';\n]+)', cd)
                    if m:
                        filename = m.group(1).strip()

            if not filename:
                filename = os.path.basename(urlparse(url).path)

            if not filename:
                filename = "unknown_file.jar"

            subfolder = self._get_subfolder(file_type)
            filepath = subfolder / filename
            size = 0

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)

            if size > 0:
                print(f"  [OK] [{file_type}] {filename} ({size/1024/1024:.2f} MB)")
                return True, filename, size
            else:
                filepath.unlink(missing_ok=True)

        except Exception as e:
            print(f"  [ERROR] Download: {e}")

        return False, "", 0

    def _save_response(self, response, mod_name, file_type="mods"):
        """Save response to correct subfolder."""
        filename = None
        cd = response.headers.get("Content-Disposition", "")
        if cd:
            m = re.search(r'filename[*]?=["\']?([^"\';\n]+)', cd)
            if m:
                filename = m.group(1).strip()

        if not filename:
            filename = os.path.basename(urlparse(response.url).path)

        if not filename or not filename.endswith((".jar", ".zip")):
            safe_name = re.sub(r'[^\w\-.]', '_', mod_name)
            filename = f"{safe_name}.jar"

        ct = response.headers.get("Content-Type", "")
        if "text/html" in ct:
            return False, "", 0

        subfolder = self._get_subfolder(file_type)
        filepath = subfolder / filename

        try:
            downloaded = 0
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            if downloaded > 0:
                print(f"  [OK] [{file_type}] {filename} ({downloaded/1024/1024:.2f} MB)")
                return True, filename, downloaded
            else:
                filepath.unlink(missing_ok=True)
                return False, "", 0

        except Exception as e:
            filepath.unlink(missing_ok=True)
            print(f"  [ERROR] Saving {filename}: {e}")
            return False, "", 0

    # ============================================================
    # MAIN DOWNLOAD LOOPS
    # ============================================================

    def download_modlist(self, mods):
        """Download all entries from modlist.html."""
        print(f"\n{'='*60}")
        print(f"  Downloading {len(mods)} entries (modlist.html)")
        print(f"  Output: {self.output_dir.absolute()}")
        print(f"{'='*60}\n")

        for i, mod in enumerate(mods, 1):
            name = mod["name"]
            url = mod["url"]

            print(f"\n[{i}/{len(mods)}] {name}")

            # Check cache
            cached, cached_fn = self.cache.is_downloaded(url)
            if cached:
                print(f"  [SKIP] Already downloaded: {cached_fn}")
                self.skipped.append({"name": name, "url": url, "filename": cached_fn})
                continue

            # Determine file type from URL
            file_type = "mods"
            if "/texture-packs/" in url or "/resource-packs/" in url:
                file_type = "resourcepacks"
            elif "/shaders/" in url or "/shader-packs/" in url:
                file_type = "shaderpacks"
            elif "/worlds/" in url:
                file_type = "worlds"
            elif "/data-packs/" in url:
                file_type = "datapacks"

            ok, fn, sz = self._download_by_url(url, name, file_type)

            if ok:
                subfolder = self._get_subfolder(file_type)
                self.succeeded.append({
                    "name": name, "url": url, "filename": fn, "type": file_type
                })
                self.cache.mark_downloaded(
                    url, fn, str(subfolder / fn), sz, file_type
                )
            else:
                self.failed.append({"name": name, "url": url})

            time.sleep(DELAY_BETWEEN_DOWNLOADS)

        self._save_report(mods, "modlist")
        self.cache.save()
        self._print_summary()

    def download_manifest(self, files, manifest):
        """
        Download all files from manifest.json.
        Detects file types and downloads dependencies.
        """
        print(f"\n{'='*60}")
        print(f"  Downloading {len(files)} files (manifest.json)")
        print(f"  Modpack: {manifest.get('name', 'Unknown')}")
        print(f"  Output: {self.output_dir.absolute()}")
        print(f"{'='*60}")
        print(f"  Files will be sorted into subfolders:")
        print(f"    mods/          - Mods")
        print(f"    resourcepacks/ - Resource Packs")
        print(f"    shaderpacks/   - Shader Packs")
        print(f"{'='*60}\n")

        for i, fi in enumerate(files, 1):
            pid = fi["projectID"]
            fid = fi["fileID"]
            cache_key = f"cf:{pid}:{fid}"

            # Get project name and type
            proj_name = self.detector.get_project_name(pid)
            file_type = self.detector.get_file_type(pid)

            print(f"\n[{i}/{len(files)}] {proj_name} [{file_type}]")

            # Check cache
            cached, cached_fn = self.cache.is_downloaded(cache_key)
            if cached:
                print(f"  [SKIP] Already downloaded: {cached_fn}")
                self.skipped.append({
                    "projectID": pid, "fileID": fid,
                    "filename": cached_fn, "type": file_type,
                    "name": proj_name,
                })
                self._processed_projects.add(pid)
                continue

            # Download
            ok, fn, sz = self._download_by_ids(pid, fid, file_type)

            if ok:
                subfolder = self._get_subfolder(file_type)
                self.succeeded.append({
                    "projectID": pid, "fileID": fid,
                    "filename": fn, "type": file_type,
                    "name": proj_name,
                })
                self.cache.mark_downloaded(
                    cache_key, fn, str(subfolder / fn), sz, file_type
                )

                # Download dependencies (only for mods)
                if file_type == "mods":
                    self._download_dependencies(pid, fid)
            else:
                self.failed.append({
                    "projectID": pid, "fileID": fid,
                    "type": file_type, "name": proj_name,
                })

            time.sleep(DELAY_BETWEEN_DOWNLOADS)

        self._save_report(files, "manifest", manifest)
        self.cache.save()
        self._print_summary()

    # ============================================================
    # REPORTS
    # ============================================================

    def _save_report(self, all_items, source, manifest=None):
        """Save download report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "modpack_name": manifest.get("name", "?") if manifest else "?",
            "modpack_version": manifest.get("version", "?") if manifest else "?",
            "total": len(all_items),
            "succeeded": len(self.succeeded),
            "skipped": len(self.skipped),
            "failed": len(self.failed),
            "dependencies_downloaded": len(self.dependencies_downloaded),
            "succeeded_mods": self.succeeded,
            "skipped_mods": self.skipped,
            "failed_mods": self.failed,
            "dependencies": self.dependencies_downloaded,
        }

        # Count files by type
        type_counts = {}
        for item in self.succeeded + self.skipped:
            ft = item.get("type", "mods")
            type_counts[ft] = type_counts.get(ft, 0) + 1

        report["files_by_type"] = type_counts

        with open(self.report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n[INFO] Report saved: {self.report_file}")

    def _print_summary(self):
        """Print results summary."""
        total = len(self.succeeded) + len(self.skipped) + len(self.failed)

        # Count by type
        type_counts = {}
        for item in self.succeeded:
            ft = item.get("type", "mods")
            type_counts[ft] = type_counts.get(ft, 0) + 1

        print(f"\n{'='*60}")
        print(f"  RESULTS:")
        print(f"{'='*60}")
        print(f"  Downloaded:    {len(self.succeeded)}")
        print(f"  Skipped:       {len(self.skipped)} (already had)")
        print(f"  Failed:        {len(self.failed)}")
        print(f"  Dependencies:  {len(self.dependencies_downloaded)}")

        if type_counts:
            print(f"\n  By type:")
            for ft, count in sorted(type_counts.items()):
                print(f"    {ft}: {count}")

        # Count actual files in subfolders
        print(f"\n  Files on disk:")
        for folder_name in ["mods", "resourcepacks", "shaderpacks", "worlds", "datapacks"]:
            folder = self.output_dir / folder_name
            if folder.exists():
                count = len(list(folder.glob("*")))
                if count > 0:
                    print(f"    {folder_name}/: {count} files")

        print(f"{'='*60}")

        if self.failed:
            print(f"\n  FAILED ({len(self.failed)}):")
            print(f"  {'-'*50}")
            for mod in self.failed:
                name = mod.get("name", "")
                url = mod.get("url", "")
                pid = mod.get("projectID", "")
                fid = mod.get("fileID", "")
                ft = mod.get("type", "mods")

                if name:
                    print(f"\n    Name: {name} [{ft}]")
                if url:
                    print(f"    URL:  {url}")
                if pid and fid:
                    print(f"    Project: {pid}, File: {fid}")
                    print(f"    Link: https://www.curseforge.com/minecraft/mc-mods/_/download/{fid}")

        if self.dependencies_downloaded:
            print(f"\n  DEPENDENCIES DOWNLOADED ({len(self.dependencies_downloaded)}):")
            print(f"  {'-'*50}")
            for dep in self.dependencies_downloaded:
                print(f"    {dep.get('name', '?')} -> {dep.get('filename', '?')}")

        print()


# ============================================================
# VERIFIER
# ============================================================

class Verifier:
    """Checks if all files were downloaded."""

    def __init__(self, mods_dir="mods_output"):
        self.mods_dir = Path(mods_dir)

    def verify(self, source=None):
        if source and Path(source).exists():
            if source.endswith((".html", ".htm")):
                self._verify_modlist(source)
            elif source.endswith(".json"):
                self._verify_manifest(source)
            else:
                self._verify_report()
        else:
            self._verify_report()

    def _count_all_files(self):
        """Count files in all subfolders."""
        counts = {}
        total = 0
        for folder_name in ["mods", "resourcepacks", "shaderpacks", "worlds", "datapacks"]:
            folder = self.mods_dir / folder_name
            if folder.exists():
                count = len([f for f in folder.iterdir() if f.is_file()])
                if count > 0:
                    counts[folder_name] = count
                    total += count
        return counts, total

    def _verify_report(self):
        rf = self.mods_dir / REPORT_FILENAME
        if not rf.exists():
            print("[ERROR] No report found. Download mods first!")
            return

        with open(rf, "r", encoding="utf-8") as f:
            report = json.load(f)

        failed = report.get("failed_mods", [])
        succeeded = report.get("succeeded_mods", [])
        total = report.get("total", 0)
        deps = report.get("dependencies_downloaded", 0)
        type_counts = report.get("files_by_type", {})
        folder_counts, total_files = self._count_all_files()

        print(f"\n{'='*60}")
        print(f"  VERIFICATION")
        print(f"{'='*60}")
        print(f"  Modpack:       {report.get('modpack_name', '?')}")
        print(f"  Expected:      {total}")
        print(f"  Succeeded:     {len(succeeded)}")
        print(f"  Failed:        {len(failed)}")
        print(f"  Dependencies:  {deps}")

        if folder_counts:
            print(f"\n  Files on disk:")
            for fn, count in sorted(folder_counts.items()):
                print(f"    {fn}/: {count}")
            print(f"    TOTAL: {total_files}")

        if not failed:
            print(f"\n  ALL FILES PRESENT!")
        else:
            print(f"\n  MISSING ({len(failed)}):")
            print(f"  {'-'*50}")
            for mod in failed:
                name = mod.get("name", "")
                pid = mod.get("projectID", "")
                fid = mod.get("fileID", "")
                ft = mod.get("type", "mods")
                if name:
                    print(f"\n    Name: {name} [{ft}]")
                if pid and fid:
                    print(f"    Link: https://www.curseforge.com/minecraft/mc-mods/_/download/{fid}")

        print(f"{'='*60}")

    def _verify_modlist(self, path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        soup = BeautifulSoup(content, "html.parser")
        mods = [l for l in soup.find_all("a") if "curseforge.com" in l.get("href", "")]
        folder_counts, total_files = self._count_all_files()

        print(f"\n  Entries in modlist: {len(mods)}")
        print(f"  Files on disk:     {total_files}")
        if total_files >= len(mods):
            print(f"  ALL OK!")
        else:
            print(f"  Missing: {len(mods) - total_files}")

    def _verify_manifest(self, path):
        with open(path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        files = manifest.get("files", [])
        folder_counts, total_files = self._count_all_files()

        print(f"\n  Modpack:          {manifest.get('name', '?')}")
        print(f"  Files in manifest: {len(files)}")
        print(f"  Files on disk:     {total_files}")
        if total_files >= len(files):
            print(f"  ALL OK!")
        else:
            print(f"  Missing: {len(files) - total_files}")


# ============================================================
# MODPACK INFO
# ============================================================

def show_modpack_info(manifest_path):
    """Display modpack information."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    name = manifest.get("name", "Unknown")
    version = manifest.get("version", "?")
    author = manifest.get("author", "Unknown")
    mc = manifest.get("minecraft", {})
    mc_ver = mc.get("version", "?")
    loaders = mc.get("modLoaders", [])
    files = manifest.get("files", [])

    loader_name = "Unknown"
    loader_ver = "?"
    download_url = ""

    if loaders:
        lid = loaders[0].get("id", "")
        if "neoforge" in lid.lower():
            loader_name = "NeoForge"
            loader_ver = lid.replace("neoforge-", "")
            download_url = "https://neoforged.net/"
        elif "forge" in lid.lower():
            loader_name = "Forge"
            loader_ver = lid.replace("forge-", "")
            download_url = "https://files.minecraftforge.net/"
        elif "fabric" in lid.lower():
            loader_name = "Fabric"
            loader_ver = lid.replace("fabric-", "")
            download_url = "https://fabricmc.net/use/installer/"
        elif "quilt" in lid.lower():
            loader_name = "Quilt"
            loader_ver = lid.replace("quilt-", "")
            download_url = "https://quiltmc.org/install/"
        else:
            loader_name = lid

    print(f"\n{'='*50}")
    print(f"  MODPACK INFO")
    print(f"{'='*50}")
    print(f"  Name:          {name}")
    print(f"  Version:       {version}")
    print(f"  Author:        {author}")
    print(f"  Minecraft:     {mc_ver}")
    print(f"  Loader:        {loader_name} {loader_ver}")
    print(f"  Total files:   {len(files)}")
    if download_url:
        print(f"  Get loader at: {download_url}")
    print(f"{'='*50}")

    return manifest


# ============================================================
# ZIP HANDLER
# ============================================================

def extract_and_download(zip_path, output_dir, api_key=None):
    """Process a CurseForge modpack ZIP file."""
    import zipfile
    import tempfile
    import shutil

    zip_path = Path(zip_path)
    if not zip_path.exists():
        print(f"[ERROR] File not found: {zip_path}")
        return

    print(f"[INFO] Opening: {zip_path.name}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        print(f"[INFO] Archive contains {len(names)} files")

        with tempfile.TemporaryDirectory() as tmpdir:
            zf.extractall(tmpdir)
            tmpdir = Path(tmpdir)

            manifests = list(tmpdir.rglob("manifest.json"))
            modlists = list(tmpdir.rglob("modlist.html"))

            # Copy overrides
            for od in tmpdir.rglob("overrides"):
                if od.is_dir():
                    # Copy mods
                    for subfolder_name in ["mods", "resourcepacks", "shaderpacks", "config"]:
                        src = od / subfolder_name
                        if src.exists():
                            dst = Path(output_dir) / subfolder_name
                            dst.mkdir(parents=True, exist_ok=True)
                            copied = 0
                            for f in src.rglob("*"):
                                if f.is_file():
                                    rel = f.relative_to(src)
                                    dest = dst / rel
                                    dest.parent.mkdir(parents=True, exist_ok=True)
                                    if not dest.exists():
                                        shutil.copy2(f, dest)
                                        copied += 1
                            if copied > 0:
                                 print(f"  [OVERRIDE] Copied {copied} files from overrides/{subfolder_name}/")

            dl = CurseForgeDownloader(output_dir=output_dir, api_key=api_key)

            if manifests:
                print(f"\n[INFO] Found manifest.json")
                show_modpack_info(str(manifests[0]))
                files, manifest = dl.parse_manifest(str(manifests[0]))
                if files:
                    dl.download_manifest(files, manifest)
            elif modlists:
                print(f"\n[INFO] Found modlist.html")
                mods = dl.parse_modlist(str(modlists[0]))
                if mods:
                    dl.download_modlist(mods)
            else:
                print("[ERROR] No manifest.json or modlist.html found!")


# ============================================================
# INPUT HELPERS
# ============================================================

def ask_file_path(prompt, extensions, hint=""):
    """Ask user for a file path."""
    while True:
        if hint:
            print(f"\n  Hint: {hint}")
        path = input(f"  {prompt}: ").strip().strip('"').strip("'")
        if not path:
            print("  Path cannot be empty!")
            continue
        if not Path(path).exists():
            print(f"  File not found: {path}")
            continue
        ext = Path(path).suffix.lower()
        if extensions and ext not in extensions:
            print(f"  Wrong format! Expected: {', '.join(extensions)}")
            continue
        print(f"  Found: {Path(path).name}")
        return path


def ask_output_dir():
    """Ask user for output folder."""
    print(f"\n  Where to save files? (press Enter for 'mods_output')")
    path = input("  Output folder [mods_output]: ").strip().strip('"').strip("'")
    if not path:
        path = "mods_output"
    Path(path).mkdir(parents=True, exist_ok=True)
    print(f"  Folder: {Path(path).absolute()}")
    return path


def ask_api_key():
    """Ask for API key. Auto-loads from file if available."""
    file_key = load_api_key_from_file("api_key.txt")
    if file_key:
        print(f"\n  API key loaded from api_key.txt (length: {len(file_key)})")
        use_it = input("  Use this key? (Y/n): ").strip().lower()
        if use_it in ("", "y", "yes"):
            return file_key

    print(f"\n  CurseForge API key")
    print(f"  Get free key at: https://console.curseforge.com/")
    key = input("  API key: ").strip().strip('"').strip("'")
    return key if key else None


# ============================================================
# INTERACTIVE MENU
# ============================================================

def interactive_mode():
    """Interactive menu with screen clearing."""

    clear_screen()
    print()
    print("=" * 50)
    print("  CurseForge Modpack Downloader v4.0")
    print("=" * 50)
    print()
    print("  1. zip      - Download from ZIP archive")
    print("  2. modlist  - Download from modlist.html")
    print("  3. manifest - Download from manifest.json")
    print("  4. verify   - Check what was downloaded")
    print("  5. info     - Show modpack info")
    print("  6. exit     - Exit")
    print()

    while True:
        choice = input("  Choose (1-6): ").strip().lower()
        if choice in ("1", "zip"):
            mode = "zip"
            break
        elif choice in ("2", "modlist"):
            mode = "modlist"
            break
        elif choice in ("3", "manifest"):
            mode = "manifest"
            break
        elif choice in ("4", "verify"):
            mode = "verify"
            break
        elif choice in ("5", "info"):
            mode = "info"
            break
        elif choice in ("6", "exit", "quit", "q"):
            clear_screen()
            print("\n  Bye!\n")
            return
        else:
            print("  Invalid choice! Enter 1-6.")

    if mode == "zip":
        clear_screen()
        print(f"\n{'='*50}")
        print("  MODE: ZIP ARCHIVE")
        print(f"{'='*50}\n")
        fp = ask_file_path("Path to ZIP file", [".zip"], "Drag and drop here")
        od = ask_output_dir()
        ak = ask_api_key()
        clear_screen()
        extract_and_download(fp, od, ak)

    elif mode == "modlist":
        clear_screen()
        print(f"\n{'='*50}")
        print("  MODE: MODLIST.HTML")
        print(f"{'='*50}\n")
        fp = ask_file_path("Path to modlist.html", [".html", ".htm"], "Drag and drop here")
        od = ask_output_dir()
        ak = ask_api_key()
        clear_screen()
        dl = CurseForgeDownloader(output_dir=od, api_key=ak)
        mods = dl.parse_modlist(fp)
        if mods:
            dl.download_modlist(mods)

    elif mode == "manifest":
        clear_screen()
        print(f"\n{'='*50}")
        print("  MODE: MANIFEST.JSON")
        print(f"{'='*50}\n")
        fp = ask_file_path("Path to manifest.json", [".json"], "Drag and drop here")
        od = ask_output_dir()
        ak = ask_api_key()
        clear_screen()
        dl = CurseForgeDownloader(output_dir=od, api_key=ak)
        files, manifest = dl.parse_manifest(fp)
        if files:
            dl.download_manifest(files, manifest)

    elif mode == "verify":
        clear_screen()
        print(f"\n{'='*50}")
        print("  MODE: VERIFICATION")
        print(f"{'='*50}\n")
        od = ask_output_dir()
        print("\n  Verify against:")
        print("  1. Saved report")
        print("  2. modlist.html")
        print("  3. manifest.json")
        while True:
            vc = input("\n  Choose (1-3): ").strip()
            if vc in ("1", "2", "3"):
                break
        source = None
        if vc == "2":
            source = ask_file_path("Path to modlist.html", [".html", ".htm"])
        elif vc == "3":
            source = ask_file_path("Path to manifest.json", [".json"])
        clear_screen()
        Verifier(mods_dir=od).verify(source)

    elif mode == "info":
        clear_screen()
        print(f"\n{'='*50}")
        print("  MODE: MODPACK INFO")
        print(f"{'='*50}\n")
        print("  What do you have?")
        print("  1. ZIP archive")
        print("  2. manifest.json")
        while True:
            ic = input("\n  Choose (1-2): ").strip()
            if ic in ("1", "2"):
                break
        if ic == "1":
            fp = ask_file_path("Path to ZIP", [".zip"])
        else:
            fp = ask_file_path("Path to manifest.json", [".json"])
        clear_screen()
        path = Path(fp)
        if path.suffix == ".zip":
            import zipfile
            import tempfile
            with zipfile.ZipFile(path, "r") as zf:
                with tempfile.TemporaryDirectory() as td:
                    zf.extractall(td)
                    ms = list(Path(td).rglob("manifest.json"))
                    if ms:
                        show_modpack_info(str(ms[0]))
                    else:
                        print("  manifest.json not found!")
        else:
            show_modpack_info(fp)

    print()
    again = input("  Do something else? (y/n): ").strip().lower()
    if again in ("y", "yes", "1"):
        interactive_mode()
    else:
        clear_screen()
        print(f"\n{'='*50}")
        print("  Done! Goodbye!")
        print(f"{'='*50}\n")


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) <= 1:
        interactive_mode()
        return

    import argparse

    parser = argparse.ArgumentParser(
        description="CurseForge Modpack Downloader v4.0"
    )
    sub = parser.add_subparsers(dest="cmd", help="Command")

    p = sub.add_parser("zip", help="Download from ZIP")
    p.add_argument("file")
    p.add_argument("-o", "--output", default="mods_output")
    p.add_argument("--api-key", default=None)

    p = sub.add_parser("modlist", help="Download from modlist.html")
    p.add_argument("file")
    p.add_argument("-o", "--output", default="mods_output")
    p.add_argument("--api-key", default=None)

    p = sub.add_parser("manifest", help="Download from manifest.json")
    p.add_argument("file")
    p.add_argument("-o", "--output", default="mods_output")
    p.add_argument("--api-key", default=None)

    p = sub.add_parser("verify", help="Verify downloads")
    p.add_argument("-o", "--output", default="mods_output")
    p.add_argument("--source", default=None)

    p = sub.add_parser("info", help="Show modpack info")
    p.add_argument("file")

    args = parser.parse_args()

    if args.cmd == "zip":
        extract_and_download(args.file, args.output, args.api_key)
    elif args.cmd == "modlist":
        dl = CurseForgeDownloader(output_dir=args.output, api_key=args.api_key)
        mods = dl.parse_modlist(args.file)
        if mods:
            dl.download_modlist(mods)
    elif args.cmd == "manifest":
        dl = CurseForgeDownloader(output_dir=args.output, api_key=args.api_key)
        files, manifest = dl.parse_manifest(args.file)
        if files:
            dl.download_manifest(files, manifest)
    elif args.cmd == "verify":
        Verifier(mods_dir=args.output).verify(args.source)
    elif args.cmd == "info":
        path = Path(args.file)
        if path.suffix == ".zip":
            import zipfile
            import tempfile
            with zipfile.ZipFile(path, "r") as zf:
                with tempfile.TemporaryDirectory() as td:
                    zf.extractall(td)
                    ms = list(Path(td).rglob("manifest.json"))
                    if ms:
                        show_modpack_info(str(ms[0]))
                    else:
                        print("  manifest.json not found!")
        elif path.suffix == ".json":
            show_modpack_info(str(path))
        else:
            print("[ERROR] Requires .zip or .json file")
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelled.")
    except Exception as e:
        print(f"\n  ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()
    input("  Press Enter to close...")