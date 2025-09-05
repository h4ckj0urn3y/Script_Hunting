# Script_Hunting
Contains the scripts, That make my life easy while hunting.

## Content_type_converter
This script helps me to convert content types for web requests.
Features:
Convets Content types from :
json-form
Json-xms
form-json
form-xml
xml-form
xml-json

Very simple to use copy paste the request from burp and specify sourse type and to target conversion type .
For more info : "python3 Content_type_converter.py --help"  
![Image]()

## js_Juice_finder.sh
JS Automation Script for Endpoints & Secrets

This is a simple Bash script that takes a js_urls.txt file (a list of JS file URLs collected using tools like gau, Wayback, Katana, etc.) 
and automates the process of finding endpoints and secrets in JavaScript files.

The script uses:
[Secretfiner.py](https://github.com/m4ll0k/SecretFinder.git)
[Linkfinder.py](https://github.com/GerbenJavado/LinkFinder.git)

Features:
Creates a folder js_out to store output
Saves secrets in js_secrets.txt and endpoints in js_endpoints.txt
Makes it easier to use regexes or fuzzing
