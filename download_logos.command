#!/bin/bash
LOGOS="/Users/marcgreteau/Desktop/freeride/logos"

echo "Downloading Red Bull..."
curl -sL "https://www.redbull.com/v3/resources/images/client/header/redbullcom-logo_double-with-text.svg" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  -o "$LOGOS/redbull.svg" && echo "✓ redbull.svg" || echo "✗ redbull FAIL"

echo "Downloading Saalbach..."
curl -sL "https://www.saalbach.com/fotos-marketing/logos/Saalbach%20TVB%20-%20MIT%20-%20RGB.svg" \
  -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  -o "$LOGOS/saalbach.svg" && echo "✓ saalbach.svg" || echo "✗ saalbach FAIL"

echo "Downloading Ergon..."
curl -sL "https://www.ergon-bike.com/img/ergon-logo.svg" \
  -H "User-Agent: Mozilla/5.0" \
  -o "$LOGOS/ergon_tmp.svg"
# Check if it's a real SVG
if grep -q "<svg" "$LOGOS/ergon_tmp.svg" 2>/dev/null; then
  mv "$LOGOS/ergon_tmp.svg" "$LOGOS/ergon.svg" && echo "✓ ergon.svg"
else
  echo "✗ ergon FAIL - checking size: $(wc -c < $LOGOS/ergon_tmp.svg 2>/dev/null)"
fi

echo "Done. Listing logos:"
ls -la "$LOGOS/"
