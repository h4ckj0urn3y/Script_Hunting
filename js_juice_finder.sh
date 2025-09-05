#!/bin/bash

input="js_urls.txt"
mkdir -p js_out

# Step 1: dedup + check alive JS
sort -u $input | httpx -mc 200 -silent -o js_out/js_alive.txt

# Step 2: LinkFinder
cat js_out/js_alive.txt | xargs -n 1 -P 10 -I {} \
python3 /opt/LinkFinder/linkfinder.py -i {} -o cli | sort -u > js_out/js_endpoints.txt

# Step 3: SecretFinder
cat js_out/js_alive.txt | xargs -n 1 -P 10 -I {} \
python3 /opt/SecretFinder/SecretFinder.py -i {} -o cli | tee js_out/js_secrets.txt
