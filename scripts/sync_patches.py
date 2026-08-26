import subprocess
import re
import os
import sys
import json

os.makedirs("config", exist_ok=True)
cli_jar = "build-tools/morphe-desktop.jar"
patches_mpp = "build-tools/patches.mpp"
workflow_file = ".github/workflows/build-morphe-apk.yml"

KNOWN_NAMES = {
    "com.google.android.youtube": ("YouTube", "youtube", "🔴"),
    "com.google.android.apps.youtube.music": ("YouTube-Music", "ytmusic", "🎵"),
    "com.reddit.frontpage": ("Reddit", "reddit", "🟠"),
    "com.twitter.android": ("Twitter", "twitter", "🐦"),
    "com.instagram.android": ("Instagram", "instagram", "📸"),
    "tv.twitch.android.app": ("Twitch", "twitch", "🟣"),
    "com.spotify.music": ("Spotify", "spotify", "🟢")
}

def slugify(text):
    return re.sub(r'[^a-zA-Z0-9_]', '_', text.lower()).strip('_')

def discover_packages():
    cmd = ["java", "-jar", cli_jar, "list-patches", f"--patches={patches_mpp}", "-p"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    raw = res.stdout + res.stderr
    pkgs = set(re.findall(r"Package name:\s*([a-zA-Z0-9._]+)", raw))
    return sorted(pkgs)

def get_patches_with_options(package_name):
    # 1. Generate options JSON to get raw options
    temp_opts_file = f"/tmp/opts_{slugify(package_name)}.json"
    cmd_opts = ["java", "-jar", cli_jar, "options-create", f"-p={patches_mpp}", f"-f={package_name}", f"-o={temp_opts_file}"]
    subprocess.run(cmd_opts, capture_output=True, text=True)
    
    opts_map = {}
    if os.path.exists(temp_opts_file):
        try:
            with open(temp_opts_file, "r") as f:
                d = json.load(f)
                opts_map = d[0].get("patches", {})
        except Exception:
            pass

    # 2. Get list of patches with descriptions
    cmd = ["java", "-jar", cli_jar, "list-patches", f"--patches={patches_mpp}", f"-f={package_name}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    raw = res.stdout + res.stderr
    entries = raw.split("Index: ")
    patches = []
    
    for entry in entries:
        if not entry.strip(): continue
        name_m = re.search(r"Name:\s*(.+)", entry)
        desc_m = re.search(r"Description:\s*(.+)", entry)
        enabled_m = re.search(r"Enabled:\s*(true|false)", entry)
        if name_m and enabled_m:
            p_name = name_m.group(1).strip()
            p_opts = opts_map.get(p_name, {}).get("options", None)
            patches.append({
                "name": p_name,
                "desc": desc_m.group(1).strip() if desc_m else "",
                "enabled": enabled_m.group(1).strip() == "true",
                "options": p_opts
            })
    return patches

def write_config_file(patches, app_name, package_name, out_file):
    lines = [
        f"# ========================================================",
        f"#  Morphe Patches for {app_name} ({package_name})",
        f"#  Total Patches: {len(patches)}",
        f"# ========================================================",
        f"# Instructions:",
        f"# - Jo patch chahiye, use waise hi rehne dein (ENABLED).",
        f"# - Jo patch NAHI chahiye, us line ke aage # laga dein (DISABLED).",
        f"# - Agar kisi patch ke options set karne hain (e.g. appName),",
        f"#   aap options-{out_file.split('/')[-1].replace('-patches.txt', '')}.json me edit kar sakte hain.",
        f"# ========================================================\n"
    ]
    for idx, p in enumerate(patches, 1):
        clean_desc = p['desc'].replace('\n', ' ')
        opt_str = ""
        if p["options"]:
            opt_str = f"\n#   ↳ Available Options: {json.dumps(p['options'])}"

        if p["enabled"]:
            lines.append(f"# [{idx}/{len(patches)}] [ENABLED] {clean_desc}{opt_str}")
            lines.append(f"{p['name']}\n")
        else:
            lines.append(f"# [{idx}/{len(patches)}] [DISABLED] {clean_desc}{opt_str}")
            lines.append(f"# {p['name']}\n")
    with open(out_file, "w") as f:
        f.write("\n".join(lines))
    print(f"✅ Generated {out_file} with options & numbering ({len(patches)} patches)")

def write_options_json(package_name, out_file):
    cmd = ["java", "-jar", cli_jar, "options-create", f"-p={patches_mpp}", f"-f={package_name}", f"-o={out_file}"]
    subprocess.run(cmd, capture_output=True, text=True)
    print(f"✅ Generated {out_file} (Options JSON)")

print("Scanning all supported apps in Morphe Patches bundle...")
packages = discover_packages()
print(f"Discovered {len(packages)} supported apps: {packages}")

app_data = []

for pkg in packages:
    if pkg in KNOWN_NAMES:
        app_name, slug, emoji = KNOWN_NAMES[pkg]
    else:
        app_name = pkg.split(".")[-1].capitalize()
        slug = app_name.lower()
        emoji = "📱"
    
    patches = get_patches_with_options(pkg)
    out_file = f"config/{slug}-patches.txt"
    out_opts_json = f"config/options-{slug}.json"
    
    write_config_file(patches, app_name, pkg, out_file)
    if not os.path.exists(out_opts_json):
        write_options_json(pkg, out_opts_json)
    
    disabled_patches = [p for p in patches if not p["enabled"]]
    app_data.append({
        "name": app_name,
        "slug": slug,
        "pkg": pkg,
        "emoji": emoji,
        "disabled_patches": disabled_patches
    })

# Dynamically generate workflow inputs
all_app_names = [a["name"] for a in app_data]
all_option = f"All ({' + '.join(all_app_names)})"

app_options_yaml = "\n".join([f"          - '{all_option}'"] + [f"          - '{name}'" for name in all_app_names])

# Generate checkboxes for disabled patches across ALL apps
checkbox_inputs = []
for app in app_data:
    if app["disabled_patches"]:
        checkbox_inputs.append(f"      # --- {app['emoji']} {app['name']} Disabled Patches ---")
        for dp in app["disabled_patches"]:
            p_key = f"enable_{app['slug']}_{slugify(dp['name'])}"
            desc_text = f"{app['emoji']} [{app['name']}] {dp['name']}"
            checkbox_inputs.append(f"      {p_key}:")
            checkbox_inputs.append(f"        description: '{desc_text}'")
            checkbox_inputs.append(f"        required: true")
            checkbox_inputs.append(f"        default: false")
            checkbox_inputs.append(f"        type: boolean\n")

checkboxes_yaml = "\n".join(checkbox_inputs)

# Construct full workflow YAML
workflow_yaml = f"""name: Build Morphe Patched APK

on:
  workflow_dispatch:
    inputs:
      app_type:
        description: '📱 1. Kaunsa app patch karna hai?'
        required: true
        default: '{all_option}'
        type: choice
        options:
{app_options_yaml}

      install_type:
        description: '🔑 2. Install Type (Non-Root vs Root)'
        required: true
        default: 'Non-Root (with GmsCore)'
        type: choice
        options:
          - 'Non-Root (with GmsCore)'
          - 'Root (without GmsCore)'

      # =========================================================
      # ⚙️ DISABLED-BY-DEFAULT PATCH TOGGLES (AUTO-DISCOVERED)
      # =========================================================
{checkboxes_yaml}
      # =========================================================
      # ⚡ BUILD & DEVICE SETTINGS
      # =========================================================
      architecture:
        description: '⚡ Architecture (arm64-v8a se APK chhota banta hai)'
        required: true
        default: 'arm64-v8a'
        type: choice
        options:
          - 'arm64-v8a'
          - 'armeabi-v7a'
          - 'all'

      include_microg:
        description: '📦 Release me latest MicroG (GmsCore) APK include karein?'
        required: true
        default: true
        type: boolean

      custom_apk_url:
        description: '🔗 Custom APK URL (Khaali chhodoge toh default use hoga)'
        required: false
        default: ''
        type: string

# ------------------------------------------------------------------
# 🔗 DEFAULT APK DOWNLOAD LINKS
# ------------------------------------------------------------------
env:
  DEFAULT_YOUTUBE_URL: "https://www.apkmirror.com/apk/google-inc/youtube/youtube-21-04-223-release/youtube-21-04-223-android-apk-download/download/?key=b87ce717c47f3920c139dae8e15df2ba744764e9&forcebaseapk=true"
  DEFAULT_YTMUSIC_URL: "https://www.apkmirror.com/apk/google-inc/youtube-music/youtube-music-9-15-51-release/youtube-music-9-15-51-4-android-apk-download/download/?key=fed902f297975b9851e611188d3a3764d9217718&forcebaseapk=true"
  DEFAULT_REDDIT_URL: "https://www.apkmirror.com/apk/redditinc/reddit/reddit-2025-08-0-release/reddit-2025-08-0-android-apk-download/download/"

permissions:
  contents: write

jobs:
  build-morphe-apk:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Java 21
        uses: actions/setup-java@v4
        with:
          distribution: 'zulu'
          java-version: '21'

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Setup Android Build Tools & SDK
        uses: android-actions/setup-android@v3

      - name: Clone & Download Official Morphe Tools
        run: |
          python3 - << 'EOF'
          import urllib.request, json, os, sys

          os.makedirs("build-tools", exist_ok=True)
          os.makedirs("output", exist_ok=True)
          headers = {{"User-Agent": "Mozilla/5.0"}}

          # 1. Fetch Morphe Desktop CLI
          print("Fetching latest Morphe Desktop CLI...")
          req_cli = urllib.request.Request("https://api.github.com/repos/MorpheApp/morphe-desktop/releases/latest", headers=headers)
          cli_data = json.loads(urllib.request.urlopen(req_cli).read().decode())
          cli_url = None
          for a in cli_data.get("assets", []):
              if a["name"].endswith(".jar"):
                  cli_url = a["browser_download_url"]
                  break
          if not cli_url:
              print("Error: Could not find Morphe CLI jar asset.")
              sys.exit(1)
          print(f"Downloading CLI from {{cli_url}}...")
          urllib.request.urlretrieve(cli_url, "build-tools/morphe-desktop.jar")

          # 2. Fetch Morphe Patches (.mpp)
          print("Fetching latest Morphe Patches bundle...")
          req_patches = urllib.request.Request("https://api.github.com/repos/MorpheApp/morphe-patches/releases/latest", headers=headers)
          patches_data = json.loads(urllib.request.urlopen(req_patches).read().decode())
          mpp_url = None
          for a in patches_data.get("assets", []):
              if a["name"].endswith(".mpp"):
                  mpp_url = a["browser_download_url"]
                  break
          if not mpp_url:
              print("Error: Could not find Morphe .mpp patch asset.")
              sys.exit(1)
          print(f"Downloading Patches from {{mpp_url}}...")
          urllib.request.urlretrieve(mpp_url, "build-tools/patches.mpp")

          # 3. Fetch Latest MicroG (GmsCore)
          if "${{{{ github.event.inputs.include_microg }}}}" == "true":
              try:
                  print("Fetching latest MicroG GmsCore...")
                  req_microg = urllib.request.Request("https://api.github.com/repos/MorpheApp/MicroG-RE/releases/latest", headers=headers)
                  microg_data = json.loads(urllib.request.urlopen(req_microg).read().decode())
                  for a in microg_data.get("assets", []):
                      if a["name"].endswith(".apk"):
                          print(f"Downloading MicroG from {{a['browser_download_url']}}...")
                          urllib.request.urlretrieve(a["browser_download_url"], f"output/{{a['name']}}")
                          break
              except Exception as e:
                  print(f"MicroG download notice: {{e}}")

          print("✅ Official Morphe tools ready!")
          EOF

      - name: Process, Patch and Sign Target APK(s)
        run: |
          python3 - << 'EOF'
          import urllib.request, re, sys, os, subprocess, json

          app_choice = "${{{{ github.event.inputs.app_type }}}}"
          custom_url = "${{{{ github.event.inputs.custom_apk_url }}}}".strip()
          install_type = "${{{{ github.event.inputs.install_type }}}}"
          arch = "${{{{ github.event.inputs.architecture }}}}"

          all_available = {json.dumps(all_app_names)}

          if app_choice.startswith("All"):
              targets = all_available
          else:
              targets = [app_choice]

          default_urls = {{
              "YouTube": "${{{{ env.DEFAULT_YOUTUBE_URL }}}}",
              "YouTube-Music": "${{{{ env.DEFAULT_YTMUSIC_URL }}}}",
              "Reddit": "${{{{ env.DEFAULT_REDDIT_URL }}}}"
          }}

          cfg_map = {{
              "YouTube": "config/youtube-patches.txt",
              "YouTube-Music": "config/ytmusic-patches.txt",
              "Reddit": "config/reddit-patches.txt"
          }}

          user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
          headers = {{
              "User-Agent": user_agent,
              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
              "Accept-Language": "en-US,en;q=0.5"
          }}

          def download_apk(url, dest_file):
              print(f"Downloading from URL: {{url}}")
              headers_with_ref = dict(headers)
              headers_with_ref["Referer"] = url
              req = urllib.request.Request(url, headers=headers_with_ref)
              with urllib.request.urlopen(req) as resp:
                  content_type = resp.headers.get("Content-Type", "").lower()
                  if "application/vnd.android.package-archive" in content_type or "application/zip" in content_type or "octet-stream" in content_type:
                      with open(dest_file, "wb") as f:
                          f.write(resp.read())
                  else:
                      html = resp.read().decode("utf-8", errors="ignore")
                      matches = re.findall(r"href=[\"']([^\"']*download\.php[^\"']*)[\"']", html)
                      if not matches:
                          matches = re.findall(r"href=[\"']([^\"']*(?:download|downloading)[^\"']*)[\"']", html)
                      if not matches:
                          raise Exception(f"Failed to parse direct link from webpage: {{url}}")
                      
                      sub_link = matches[0]
                      direct_url = "https://www.apkmirror.com" + sub_link if sub_link.startswith("/") else sub_link
                      sub_req = urllib.request.Request(direct_url, headers=headers_with_ref)
                      with urllib.request.urlopen(sub_req) as sub_resp, open(dest_file, "wb") as out_f:
                          while True:
                              chunk = sub_resp.read(2 * 1024 * 1024)
                              if not chunk:
                                  break
                              out_f.write(chunk)

          # Inputs payload from workflow
          workflow_inputs = dict(os.environ)

          for app in targets:
              print(f"\\n=======================================================")
              print(f"  PROCESSING TARGET: {{app}}")
              print(f"=======================================================")
              
              apk_url = custom_url if (custom_url and len(targets) == 1) else default_urls.get(app)
              if not apk_url:
                  print(f"Notice: No default URL for {{app}}. Please provide custom_apk_url.")
                  continue

              input_apk = f"input-{{app}}.apk"
              output_apk = f"output/Morphe-{{app}}.apk"

              download_apk(apk_url, input_apk)
              print(f"✅ {{app}} stock APK downloaded: {{os.path.getsize(input_apk) / (1024*1024):.2f}} MB")

              args = ["java", "-jar", "build-tools/morphe-desktop.jar", "patch"]
              args.extend(["-p", "build-tools/patches.mpp"])
              args.extend(["-o", output_apk])

              if arch != "all":
                  args.append(f"--striplibs={{arch}}")

              slug = app.lower().replace("-", "")
              opts_json_file = f"config/options-{{slug}}.json"

              # 1. Pass options JSON file if available
              if os.path.exists(opts_json_file):
                  args.append(f"--options-file={{opts_json_file}}")
                  print(f"Using Options JSON file: {{opts_json_file}}")

              # 2. READ EXACT PATCH STATUS FROM TXT FILE
              cfg_file = cfg_map.get(app, f"config/{{slug}}-patches.txt")
              enabled_patches = set()
              disabled_patches = set()

              if os.path.exists(cfg_file):
                  print(f"Reading exact patch list from: {{cfg_file}}")
                  with open(cfg_file, "r") as f:
                      for line in f:
                          line = line.strip()
                          if not line or line.startswith("# =") or line.startswith("# [") or line.startswith("# -") or line.startswith("# Morphe") or line.startswith("# Instructions") or line.startswith("#   ↳"):
                              continue
                          if line.startswith("#"):
                              p_name = line.lstrip("#").strip()
                              if p_name: disabled_patches.add(p_name)
                          else:
                              enabled_patches.add(line)
                  print(f"[{{app}}] Loaded: {{len(enabled_patches)}} Enabled, {{len(disabled_patches)}} Disabled")

              # 3. CHECK DYNAMIC DISABLED TOGGLES FROM POPUP
              for key, val in workflow_inputs.items():
                  if key.startswith(f"INPUT_ENABLE_{{slug.upper()}}_") and val == "true":
                      for dp in list(disabled_patches):
                          if re.sub(r'[^a-zA-Z0-9_]', '_', dp.lower()) in key.lower():
                              enabled_patches.add(dp)
                              disabled_patches.discard(dp)
                              print(f"[{{app}}] Enabled via popup toggle: {{dp}}")

              # Root mode handling
              if install_type == "Root (without GmsCore)":
                  disabled_patches.add("GmsCore support")
                  enabled_patches.discard("GmsCore support")

              for d in disabled_patches:
                  args.extend(["-d", d])

              for e in enabled_patches:
                  args.extend(["-e", e])

              args.append(input_apk)
              print(f"Applying {{len(enabled_patches)}} enabled patches for {{app}}...")
              res = subprocess.run(args)
              if res.returncode != 0:
                  print(f"❌ Patching failed for {{app}}")
                  sys.exit(res.returncode)
              print(f"✅ {{app}} successfully patched!")

          # Generate SHA256 Checksums
          with open("output/sha256sum.txt", "w") as chk_file:
              for f_name in os.listdir("output"):
                  if f_name.endswith(".apk"):
                      import hashlib
                      with open(os.path.join("output", f_name), "rb") as af:
                          h = hashlib.sha256(af.read()).hexdigest()
                          chk_file.write(f"{{h}}  {{f_name}}\\n")
          EOF

          echo "Generated Files in output directory:"
          ls -lh output/

      - name: Upload Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: Morphe-Build-Output
          path: output/
          retention-days: 14

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        if: success()
        with:
          tag_name: build-v${{{{ github.run_number }}}}
          name: "Morphe Apps Build #${{{{ github.run_number }}}}"
          body: |
            ### 💊 Morphe Patched Apps Release
            - **Target:** ${{{{ github.event.inputs.app_type }}}}
            - **Architecture:** ${{{{ github.event.inputs.architecture }}}}
            - **Install Type:** ${{{{ github.event.inputs.install_type }}}}
            - **Built on:** ${{{{ github.event.repository.updated_at }}}}

            #### 📦 Included Downloads:
            - Patched APKs are listed in Assets below (Built strictly using `config/*.txt` and `config/options-*.json`).
            - GmsCore (MicroG) included for non-root Google account login.
            - `sha256sum.txt` included for file integrity verification.
          files: output/*
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
"""

with open(workflow_file, "w") as wf:
    wf.write(workflow_yaml)

print("✅ Successfully generated build-morphe-apk.yml with dynamic patch options!")
