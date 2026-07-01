#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.appstore ]]; then
  echo ".env.appstore is required" >&2
  exit 1
fi

set -a
source .env.appstore
set +a

APPLE_TEAM_ID="${APPLE_TEAM_ID:-MC77VJ8M9D}"
ARCHIVE_PATH="${ARCHIVE_PATH:-$ROOT/build/ios/archive/gitai.xcarchive}"
EXPORT_PATH="${EXPORT_PATH:-$ROOT/build/ios/testflight}"
DERIVED_DATA_PATH="${DERIVED_DATA_PATH:-$ROOT/build/xcode/DerivedData}"
SOURCE_PACKAGES_PATH="${SOURCE_PACKAGES_PATH:-$ROOT/build/xcode/SourcePackages}"
PACKAGE_CACHE_PATH="${PACKAGE_CACHE_PATH:-$ROOT/build/xcode/swiftpm}"
EXPORT_OPTIONS="$ROOT/build/ios/ExportOptions.plist"

mkdir -p "$(dirname "$ARCHIVE_PATH")" "$EXPORT_PATH" "$DERIVED_DATA_PATH" "$SOURCE_PACKAGES_PATH" "$PACKAGE_CACHE_PATH"

GITAI_IOS_API_BASE="${GITAI_IOS_API_BASE:-https://api.gitai.game}" npm run ios:sync

xcodebuild \
  -resolvePackageDependencies \
  -project ios/App/App.xcodeproj \
  -scheme App \
  -derivedDataPath "$DERIVED_DATA_PATH" \
  -clonedSourcePackagesDirPath "$SOURCE_PACKAGES_PATH" \
  -packageCachePath "$PACKAGE_CACHE_PATH"

xcodebuild \
  -project ios/App/App.xcodeproj \
  -scheme App \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE_PATH" \
  -derivedDataPath "$DERIVED_DATA_PATH" \
  -clonedSourcePackagesDirPath "$SOURCE_PACKAGES_PATH" \
  -packageCachePath "$PACKAGE_CACHE_PATH" \
  DEVELOPMENT_TEAM="$APPLE_TEAM_ID" \
  CODE_SIGN_STYLE=Automatic \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$ASC_PRIVATE_KEY_PATH" \
  -authenticationKeyID "$ASC_KEY_ID" \
  -authenticationKeyIssuerID "$ASC_ISSUER_ID" \
  clean archive

cat > "$EXPORT_OPTIONS" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>destination</key>
  <string>upload</string>
  <key>method</key>
  <string>app-store-connect</string>
  <key>signingStyle</key>
  <string>automatic</string>
  <key>teamID</key>
  <string>${APPLE_TEAM_ID}</string>
  <key>manageAppVersionAndBuildNumber</key>
  <true/>
  <key>testFlightInternalTestingOnly</key>
  <true/>
  <key>uploadSymbols</key>
  <true/>
</dict>
</plist>
PLIST

xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE_PATH" \
  -exportPath "$EXPORT_PATH" \
  -exportOptionsPlist "$EXPORT_OPTIONS" \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$ASC_PRIVATE_KEY_PATH" \
  -authenticationKeyID "$ASC_KEY_ID" \
  -authenticationKeyIssuerID "$ASC_ISSUER_ID"

echo "Uploaded archive to App Store Connect for TestFlight processing."
