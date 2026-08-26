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

def generate_and_merge_options_json(package_name, out_file):
    temp_file = f"/tmp/new_opts_{slugify(package_name)}.json"
    cmd = ["java", "-jar", cli_jar, "options-create", f"-p={patches_mpp}", f"-f={package_name}", f"-o={temp_file}"]
    subprocess.run(cmd, capture_output=True, text=True)
    
    if not os.path.exists(temp_file):
        print(f"Error: Could not generate options for {package_name}")
        return {}

    with open(temp_file, "r") as f:
        new_data = json.load(f)

    # If user already had a config/options-*.json file, preserve their custom edits
    if os.path.exists(out_file):
        try:
            with open(out_file, "r") as f:
                existing_data = json.load(f)
            
            existing_patches = existing_data[0].get("patches", {})
            new_patches = new_data[0].get("patches", {})

            for p_name, p_data in existing_patches.items():
                if p_name in new_patches:
                    # Preserve user's enabled status
                    if "enabled" in p_data:
                        new_patches[p_name]["enabled"] = p_data["enabled"]
                    # Preserve user's customized options
                    if "options" in p_data and "options" in new_patches[p_name]:
                        new_patches[p_name]["options"].update(p_data["options"])
            
            new_data[0]["patches"] = new_patches
        except Exception as e:
            print(f"Note: Overwriting options due to parse error: {e}")

    with open(out_file, "w") as f:
        json.dump(new_data, f, indent=4)
    
    print(f"✅ Synced & formatted {out_file} (Total Patches: {len(new_data[0].get('patches', {}))})")
    return new_data[0].get("patches", {})

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
    
    out_opts_json = f"config/options-{slug}.json"
    patches_dict = generate_and_merge_options_json(pkg, out_opts_json)
    
    disabled_patches = []
    for p_name, p_val in patches_dict.items():
        if not p_val.get("enabled", True):
            disabled_patches.append({"name": p_name})

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
                  print(f"Notice: No default URL configured for {{app}}. Please provide custom_apk_url.")
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

              # Load options JSON file
              options_data = None
              if os.path.exists(opts_json_file):
                  with open(opts_json_file, "r") as f:
                      options_data = json.load(f)

              runtime_opts_file = f"/tmp/runtime_options_{{slug}}.json"
              if options_data:
                  patches_dict = options_data[0].get("patches", {{}})

                  # 1. Apply UI popup toggles for disabled patches if checked
                  for key, val in workflow_inputs.items():
                      if key.startswith(f"INPUT_ENABLE_{{slug.upper()}}_") and val == "true":
                          for p_name in patches_dict:
                              if re.sub(r'[^a-zA-Z0-9_]', '_', p_name.lower()) in key.lower():
                                  patches_dict[p_name]["enabled"] = True
                                  print(f"[{{app}}] Enabled via popup toggle: {{p_name}}")

                  # 2. Apply Root mode handling
                  if install_type == "Root (without GmsCore)":
                      if "GmsCore support" in patches_dict:
                          patches_dict["GmsCore support"]["enabled"] = False

                  options_data[0]["patches"] = patches_dict
                  with open(runtime_opts_file, "w") as f:
                      json.dump(options_data, f, indent=4)

                  args.append(f"--options-file={{runtime_opts_file}}")
                  print(f"✅ Loaded Options JSON: {{opts_json_file}} with {len(patches_dict)} patches")

              args.append(input_apk)
              print(f"Executing patcher for {{app}}...")
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
            - Patched APKs are listed in Assets below (Built strictly using pure JSON options).
            - GmsCore (MicroG) included for non-root Google account login.
            - `sha256sum.txt` included for file integrity verification.
          files: output/*
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
"""

with open(workflow_file, "w") as wf:
    wf.write(workflow_yaml)

print("✅ Pure JSON workflow & sync scripts successfully generated!")
