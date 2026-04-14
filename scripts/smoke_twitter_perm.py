"""Try every plausible combination of the 4 Twitter OAuth credentials.

Goal: prove whether the 401 is caused by our env mapping vs invalid keys.
Tests the same 4 strings against multiple endpoints with multiple role swaps.
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
from requests_oauthlib import OAuth1Session

load_dotenv(override=True)

K = os.getenv("TWITTER_API_KEY") or ""
S = os.getenv("TWITTER_API_SECRET") or ""
AT = os.getenv("TWITTER_ACCESS_TOKEN") or ""
ATS = os.getenv("TWITTER_ACCESS_TOKEN_SECRET") or ""

print(f"lengths: K={len(K)} S={len(S)} AT={len(AT)} ATS={len(ATS)}")
print(f"          (standard: 25, 50, ~50, 45)")
print()

ENDPOINTS = [
    ("v2 GET /2/users/me",            "GET",  "https://api.x.com/2/users/me"),
    ("v1.1 verify_credentials",       "GET",  "https://api.twitter.com/1.1/account/verify_credentials.json"),
    ("v2 GET /2/tweets/search/recent","GET",  "https://api.x.com/2/tweets/search/recent?query=hello"),
]

# All 4-tuple orderings of (client_key, client_secret, resource_owner_key, resource_owner_secret)
# Standard is (K, S, AT, ATS). Also try swapping AT <-> ATS and K <-> S in case user mislabeled.
COMBOS = [
    ("standard (K,S,AT,ATS)",        K,   S,   AT,  ATS),
    ("swap token:secret (K,S,ATS,AT)", K, S,   ATS, AT),
    ("swap consumer (S,K,AT,ATS)",   S,   K,   AT,  ATS),
    ("swap both (S,K,ATS,AT)",       S,   K,   ATS, AT),
]

def try_combo(label, ck, cs, rok, ros):
    print(f"=== {label} ===")
    sess = OAuth1Session(client_key=ck, client_secret=cs,
                         resource_owner_key=rok, resource_owner_secret=ros)
    for name, method, url in ENDPOINTS:
        try:
            r = sess.request(method, url, timeout=20)
            code = r.status_code
            body = r.text[:180].replace("\n", " ")
            print(f"  {name:35} -> {code}  {body}")
        except Exception as e:
            print(f"  {name:35} -> EXC {e}")
    print()


for label, ck, cs, rok, ros in COMBOS:
    try_combo(label, ck, cs, rok, ros)

print("If every combo returns 401, the problem is in the keys themselves")
print("(revoked, truncated, app not approved for this endpoint).")
print("If exactly one combo succeeds, that tells us the right mapping.")
