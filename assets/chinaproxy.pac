function FindProxyForURL(url, host) {

    // ============================================================
    // >> CONFIG: All direct connection rules are maintained here 
    // ============================================================

    // Keyword list (if host contains any keyword below, use DIRECT)
    var DIRECT_KEYWORDS = [
        "nvidia", "nvda", "mellanox",     // NVIDIA related
        "microsoft",                      // Microsoft related
        "taobao", "tmall", "alibaba",     // Alibaba ecosystem
        "alicdn", "alipay", "1688",
        "jd.com", "360buyimg",            // JD.com ecosystem
        "pinduoduo", "yangkeduo", "pddpic", // Pinduoduo ecosystem
        "xiaohongshu", "xhslink"          // Added Xiaohongshu
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
    // Proxy servers are launched using: autossh -M 0 -D 1081 -N vdi or ssh -D 1080 -N vdi
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

    // 3. Subnet matching
    var myIp = myIpAddress();
    for (var j = 0; j < DIRECT_SUBNETS.length; j++) {
        var net  = DIRECT_SUBNETS[j][0];
        var mask = DIRECT_SUBNETS[j][1];
        if (isInNet(myIp, net, mask) || isInNet(host, net, mask)) {
            return DIRECT;
        }
    }

    // 4. Default: route all unmatched traffic through proxy
    return PROXY;
}