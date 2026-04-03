// ============================================================
// PAC (Proxy Auto-Configuration) File — Setup Instructions
// ============================================================
//
// [Firefox]
//   1. Menu → Settings → search "proxy" → click "Settings..."
//   2. Select "Automatic proxy configuration URL"
//   3. Enter the path to this file, e.g.:
//        Windows: file:///C:/Users/yourname/Documents/proxy.pac
//        macOS:   file:///Users/yourname/Documents/proxy.pac
//        Linux:   file:///home/yourname/proxy.pac
//   4. Click "OK" and restart the browser
//
// [Chrome]
//   Option A — System proxy settings (recommended):
//     Windows: Settings → System → Proxy → "Use setup script" → enter file path
//     macOS:   System Settings → Network → Proxies → "Automatic Proxy Config" → enter file path
//     Linux:   Settings → Network → Proxy → "Automatic" → enter file path
//   Option B — Command-line flag:
//     Windows: chrome.exe --proxy-pac-url="file:///C:/Users/yourname/Documents/proxy.pac"
//     macOS:   open -a "Google Chrome" --args --proxy-pac-url="file:///Users/yourname/Documents/proxy.pac"
//     Linux:   google-chrome --proxy-pac-url="file:///home/yourname/proxy.pac"
//
// [Notes]
//   - Chrome may block local file:// PAC URLs due to sandbox restrictions;
//     serve the file over HTTP instead (e.g. python3 -m http.server)
//   - The proxy servers must be running before use:
//       autossh -M 0 -D 1081 -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3 vdi
//       ssh     -D 1080 -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3 vdi
//   - Changes to this file require a browser restart (or manual refresh) to take effect
// ============================================================

function FindProxyForURL(url, host) {
    // ============================================================
    // >> CONFIG: All direct connection rules are maintained here
    // ============================================================
    // Keyword list (if host contains any keyword below, use DIRECT)
    var DIRECT_KEYWORDS = [
        "nvidia", "nvda", "mellanox",       // NVIDIA related
        "microsoft",                        // Microsoft related
        "taobao", "tmall", "alibaba",       // Alibaba ecosystem
        "alicdn", "alipay", "1688",
        "jd.com", "360buyimg",              // JD.com ecosystem
        "pinduoduo", "yangkeduo", "pddpic", // Pinduoduo ecosystem
        "xiaohongshu", "xhslink"            // Xiaohongshu
    ];
    // Internal subnets [network address, subnet mask]
    var DIRECT_SUBNETS = [
        ["10.19.174.0",  "255.255.252.0"],
        ["10.19.176.0",  "255.255.255.0"],
        ["10.19.177.0",  "255.255.255.0"],
        ["10.19.242.0",  "255.255.252.0"],
        ["10.19.244.0",  "255.255.255.0"],
        ["10.19.245.0",  "255.255.255.0"],
        ["10.18.128.0",  "255.255.248.0"],
        ["172.29.224.0", "255.240.0.0"  ],
        ["172.29.240.0", "255.255.248.0"],
        ["172.29.248.0", "255.255.248.0"],
        ["192.168.0.0",  "255.255.0.0"  ],
        ["172.16.0.0",   "255.240.0.0"  ],
        ["10.0.0.0",     "255.0.0.0"    ]
    ];
    // Proxy servers (in order of priority)
    // Launch with: autossh -M 0 -D 1081 -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3 vdi
    //              ssh     -D 1080 -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3 vdi
    var PROXY  = "SOCKS5 127.0.0.1:1081; SOCKS5 127.0.0.1:1080; DIRECT";
    var DIRECT = "DIRECT";
    // ============================================================
    // >> LOGIC: No changes typically needed below this line
    // ============================================================
    // 1. Bypass proxy for local and plain hostnames
    if (isPlainHostName(host) ||
        host === "127.0.0.1"  ||
        host === "localhost"   ||
        host === "[::1]") {
        return DIRECT;
    }
    // 2. Keyword matching
    var lowerHost = host.toLowerCase();
    for (var i = 0; i < DIRECT_KEYWORDS.length; i++) {
        if (lowerHost.indexOf(DIRECT_KEYWORDS[i]) !== -1) {
            return DIRECT;
        }
    }
    // 3. Subnet matching (only when host is a plain IP address)
    if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) {
        for (var j = 0; j < DIRECT_SUBNETS.length; j++) {
            if (isInNet(host, DIRECT_SUBNETS[j][0], DIRECT_SUBNETS[j][1])) {
                return DIRECT;
            }
        }
    }
    // 4. Default: route all unmatched traffic through proxy
    return PROXY;
}