import sys

HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
REDIRECT = "127.0.0.1"

websites = sys.argv[1:]

with open(HOSTS_PATH, "r+") as file:

    content = file.read()

    for site in websites:

        if site not in content:
            file.write(f"{REDIRECT} {site}\n")
            file.write(f"{REDIRECT} www.{site}\n")

print("Blocked websites:", websites)