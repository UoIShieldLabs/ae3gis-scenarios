#!/bin/bash

/opt/OpenPLC_v3/start_openplc.sh &
/usr/sbin/sshd &

sleep 2

PLC_SUBNET="$(ip -4 -o addr show dev eth1 | awk '{print $4}')"
PLC_URL="$(echo $PLC_SUBNET| cut -d/ -f1):8080"
PLC_USERNAME="openplc"
PLC_PASSWORD="openplc"
COOKIE_JAR="plc_cookie.txt"
# SUBNET=$1

SIM_IP=$(nmap --open -T4 -n --max-retries 0 -p 5555 $PLC_SUBNET -oG - | grep "5555/open" | awk '{print $2}')

echo "$SIM_IP:5555" > /opt/OpenPLC_v3/webserver/core/psm/SIM_NET_ADDR.txt
cat /opt/OpenPLC_v3/webserver/core/psm/SIM_NET_ADDR.txt

# Login and get session cookie
echo "Login..."
rm -f "$COOKIE_JAR"

# First, GET the login page to extract CSRF token
echo "DEBUG: Fetching login page for CSRF token..."
echo "DEBUG: Using cookie jar: $COOKIE_JAR"
LOGIN_PAGE=$(curl -s -c "$COOKIE_JAR" "$PLC_URL/login")

echo "DEBUG: Cookies saved: $([ -f "$COOKIE_JAR" ] && echo 'YES' || echo 'NO')"
if [ -f "$COOKIE_JAR" ]; then
    echo "DEBUG: Cookie jar size: $(wc -c < "$COOKIE_JAR") bytes"
fi

# Try multiple CSRF token extraction patterns
echo "DEBUG: Trying to extract CSRF token..."

# Pattern 1: Extract from value='TOKEN' format (single quotes)
CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -o "value='[^']*'" | grep csrf_token -B1 -A1 | grep "value='" | cut -d"'" -f2)

# Pattern 2: If not found, try a different approach - grep for csrf_token then extract the preceding value
if [ -z "$CSRF_TOKEN" ]; then
    CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep "csrf_token" | grep -o "value='[^']*'" | cut -d"'" -f2)
fi

# Pattern 3: Try extracting any value attribute before csrf_token name
if [ -z "$CSRF_TOKEN" ]; then
    CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -o "<input[^>]*csrf_token[^>]*>" | grep -o "value='[^']*'" | cut -d"'" -f2)
fi

if [ -z "$CSRF_TOKEN" ]; then
    echo "ERROR: Could not extract CSRF token from login page"
    echo "Page content (first 30 lines):"
    echo "$LOGIN_PAGE" | head -30
    echo ""
    echo "Searching for 'csrf' in page:"
    echo "$LOGIN_PAGE" | grep -i csrf || echo "No 'csrf' found in page"
    exit 1
fi

CSRF_TOKEN_LOGIN="$CSRF_TOKEN"
echo "DEBUG: Found login CSRF token: $CSRF_TOKEN_LOGIN"

# Check what cookies were saved from the login page fetch
echo "DEBUG: Current cookie jar contents:"
if [ -f "$COOKIE_JAR" ]; then
    cat "$COOKIE_JAR"
else
    echo "WARNING: Cookie jar file not created yet"
fi

# Now POST the login with CSRF token
# Try sending CSRF token as both a form parameter AND as a header
echo "Posting login credentials..."
LOGIN_RESPONSE=$(curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
     -X POST "$PLC_URL/login" \
     -H "X-CSRFToken: $CSRF_TOKEN" \
     -d "username=$PLC_USERNAME&password=$PLC_PASSWORD&csrf_token=$CSRF_TOKEN")

echo "DEBUG: Login response length: ${#LOGIN_RESPONSE}"
echo "DEBUG: First 300 chars of login response:"
echo "${LOGIN_RESPONSE:0:300}"

if echo "$LOGIN_RESPONSE" | grep -q "Bad Request\|missing\|error" -i; then
    echo "ERROR: Login failed"
    echo "Full response:"
    echo "$LOGIN_RESPONSE"
    echo ""
    echo "DEBUG: Cookies after login attempt:"
    if [ -f "$COOKIE_JAR" ]; then
        cat "$COOKIE_JAR"
    else
        echo "Cookie jar file still not created"
    fi
    exit 1
fi

# Check if we got redirected to dashboard (successful login)
if echo "$LOGIN_RESPONSE" | grep -qi "dashboard\|topology"; then
    echo "Login successful"
elif [ -z "$LOGIN_RESPONSE" ]; then
    echo "Login POST returned empty response - may have redirected"
else
    echo "Login response received, continuing..."
fi

# Start PLC
echo "Start PLC..."
curl -s -b "$COOKIE_JAR" \
        -X GET "$PLC_URL/start_plc" > /dev/null

tail -f /dev/null