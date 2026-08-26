import subprocess
import re
import os
import sys

os.makedirs("config", exist_ok=True)
cli_jar = "build-tools/morphe-desktop.jar"
patches_mpp = "build-tools/patches.mpp"
workflow_file = ".github/workflows/build-morphe-apk.yml"

KNOWN_NAMES = {
    "com.google.android.youtube": ("YouTube", "youtube"),
    "com.google.android.apps.youtube.music": ("YouTube-Music", "ytmusic"),
    "com.reddit.frontpage": ("Reddit", "reddit"),
    "com.twitter.android": ("Twitter", "twitter"),
    "com.instagram.android": ("Instagram", "instagram"),
    "tv.twitch.android.app": ("Twitch", "twitch"),
    "com.spotify.music": ("Spotify", "spotify"),
    "com.zhiliaoapp.musically": ("TikTok", "tiktok"),
    "com.facebook.katana": ("Facebook", "facebook")
}

def discover_packages():
    cmd = ["java", "-jar", cli_jar, "list-patches", f"--patches={patches_mpp}", "-p"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    raw = res.stdout + res.stderr
    pkgs = set(re.findall(r"Package name:\s*([a-zA-Z0-9._]+)", raw))
    return sorted(pkgs)

def get_patches(package_name):
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
            patches.append({
                "name": name_m.group(1).strip(),
                "desc": desc_m.group(1).strip() if desc_m else "",
                "enabled": enabled_m.group(1).strip() == "true"
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
        f"# ========================================================\n"
    ]
    for idx, p in enumerate(patches, 1):
        clean_desc = p['desc'].replace('\n', ' ')
        if p["enabled"]:
            lines.append(f"# [{idx}/{len(patches)}] [ENABLED] {clean_desc}")
            lines.append(f"{p['name']}\n")
        else:
            lines.append(f"# [{idx}/{len(patches)}] [DISABLED] {clean_desc}")
            lines.append(f"# {p['name']}\n")
    with open(out_file, "w") as f:
        f.write("\n".join(lines))
    print(f"✅ Generated {out_file} with numbering ({len(patches)} patches)")

print("Scanning all supported apps in Morphe Patches bundle...")
packages = discover_packages()
print(f"Discovered {len(packages)} supported apps: {packages}")

discovered_apps = []

for pkg in packages:
    if pkg in KNOWN_NAMES:
        app_name, slug = KNOWN_NAMES[pkg]
    else:
        # Dynamic fallback for future unannounced apps
        app_name = pkg.split(".")[-1].capitalize()
        slug = app_name.lower()
    
    discovered_apps.append(app_name)
    out_file = f"config/{slug}-patches.txt"
    patches = get_patches(pkg)
    write_config_file(patches, app_name, pkg, out_file)

# 2. Automatically update app_type options in build-morphe-apk.yml
if os.path.exists(workflow_file):
    with open(workflow_file, "r") as wf:
        content = wf.read()
    
    all_option = f"All ({' + '.join(discovered_apps)})"
    new_options = [f"          - '{all_option}'"] + [f"          - '{app}'" for app in discovered_apps]
    new_options_str = "\n".join(new_options)

    # Replace options block in workflow
    pattern = r"(app_type:.*?\n\s+options:\n)(?:\s+-\s+'[^']+'\n)+"
    replacement = r"\g<1>" + new_options_str + "\n"
    
    updated_content = re.sub(pattern, replacement, content, count=1, flags=re.DOTALL)
    
    # Also update default
    updated_content = re.sub(r"(app_type:.*?\n\s+default:\s+)'[^']+'", rf"\g<1>'{all_option}'", updated_content, count=1)
    
    with open(workflow_file, "w") as wf:
        wf.write(updated_content)
    print("✅ Successfully updated build-morphe-apk.yml with all discovered apps!")

print("All current and upcoming apps synced successfully!")
