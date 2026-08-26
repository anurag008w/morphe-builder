import subprocess
import re
import os
import sys

os.makedirs("config", exist_ok=True)
cli_jar = "build-tools/morphe-desktop.jar"
patches_mpp = "build-tools/patches.mpp"

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

print("Fetching patches from bundle...")
yt_patches = get_patches("com.google.android.youtube")
ytm_patches = get_patches("com.google.android.apps.youtube.music")
reddit_patches = get_patches("com.reddit.frontpage")

# 1. Update config/*.txt files
def write_config_file(patches, app_name, package_name, out_file):
    lines = [
        f"# ========================================================",
        f"#  Morphe Patches for {app_name} ({package_name})",
        f"# ========================================================",
        f"# Instructions:",
        f"# - Jo patch chahiye, use waise hi rehne dein (ENABLED).",
        f"# - Jo patch NAHI chahiye, us line ke aage # laga dein (DISABLED).",
        f"# ========================================================\n"
    ]
    for p in patches:
        if p["enabled"]:
            lines.append(f"# [ENABLED] {p['desc']}")
            lines.append(f"{p['name']}\n")
        else:
            lines.append(f"# [DISABLED] {p['desc']}")
            lines.append(f"# {p['name']}\n")
    with open(out_file, "w") as f:
        f.write("\n".join(lines))
    print(f"Updated {out_file} ({len(patches)} patches)")

write_config_file(yt_patches, "YouTube", "com.google.android.youtube", "config/youtube-patches.txt")
write_config_file(ytm_patches, "YouTube Music", "com.google.android.apps.youtube.music", "config/ytmusic-patches.txt")
write_config_file(reddit_patches, "Reddit", "com.reddit.frontpage", "config/reddit-patches.txt")

print("All patch config files successfully updated from official Morphe bundle!")
