# 💊 Morphe Cloud Builder (GitHub Actions)

Yeh repository GitHub Actions ke zariye **YouTube** aur **YouTube Music** ko automatically Morphe patches ke sath build, patch aur sign karne ke liye banayi gayi hai.

---

## 🚀 Kaise Use Karein?

1. **Default URLs configure karein (Optional)**:
   - File `.github/workflows/build-morphe-apk.yml` open karein.
   - `DEFAULT_YOUTUBE_URL` aur `DEFAULT_YTMUSIC_URL` me apne direct APK download links paste karein.

2. **Workflow Run karein**:
   - GitHub par **Actions** tab me jayein.
   - Left side me **"Build Morphe Patched APK"** select karein.
   - **"Run workflow"** button dabayein:
     - **App:** `YouTube` ya `YouTube-Music` select karein.
     - **Custom URL (Optional):** Agar koi specific version ka link daalna hai toh yahan paste karein, warna blank chhod dein (workflow automatically default URL use karega).
   - Green **Run workflow** button dabayein.

3. **Download Patched APK**:
   - 1–2 minutes me build complete hone ke baad **Releases** ya **Artifacts** section se `Morphe-*-signed.apk` download kar lijiye.
